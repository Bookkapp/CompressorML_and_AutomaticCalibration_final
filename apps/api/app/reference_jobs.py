"""Durable, bounded reference-review jobs with atomic Candidate completion.

HTTP requests enqueue/poll. Daily source reads happen outside the HTTP thread.
SQL leases survive browser retries and detect interrupted runs after a restart.
The build transaction locks the job and commits Candidate + completion together.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .calibration import _latest_source_time, persist_batch
from .config import get_settings
from .db import connection, get_engine
from .qualified_cache import load_cached_windows as load_observed_one_minute_windows
from .reference_review import (ReferencePreviewRequest, bounds, make_preview,
                               minute_detail, resolve_selection, selected_candidate, snapshot_digest)

TABLE = "ht9046mx_reference_review_job"
ACTIVE = ("PREVIEW_QUEUED", "PREVIEW_RUNNING", "BUILD_QUEUED", "BUILD_RUNNING")
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reference-review")
DISPATCHED: set[str] = set()
DISPATCH_LOCK = Lock()
LOG = logging.getLogger(__name__)


class ReviewConflict(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, default=str)


def _row(conn, job_id: str, *, lock=False):
    suffix = " FOR UPDATE" if lock and conn.dialect.name == "mysql" else ""
    row = conn.execute(text(f"SELECT * FROM {TABLE} WHERE job_id=:job{suffix}"), {"job": job_id}).mappings().first()
    if row is None:
        raise KeyError("Reference review job not found")
    result = dict(row)
    for key in ("created_at", "updated_at", "lease_until"):
        if isinstance(result[key], str):
            result[key] = datetime.fromisoformat(result[key])
    return result


def _expire(conn, job_id: str | None = None):
    # A range UPDATE, even with no expired jobs, can lock the status index
    # while a worker changes status/lease. Ordinary polling must be read-only.
    # Admission cleans up only observed expired IDs, in primary-key order.
    now = utcnow()
    predicate = "status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING') AND lease_until < :now"
    params = {"now": now}
    if job_id is not None:
        predicate += " AND job_id=:job"
        params["job"] = job_id
    expired = conn.execute(text(f"SELECT job_id,module,request_json FROM {TABLE} WHERE {predicate} ORDER BY job_id"), params).mappings().all()
    for row in expired:
        job = row["job_id"]
        if row["module"] == 0 and json.loads(row["request_json"]).get("mode") in {"automatic-reference-v1","context-reference-v1","context-followup-v1"}:
            # Automatic preparation has no partial Candidate commits. A new
            # owner can safely reuse completed days after the old lease expires.
            conn.execute(text(f"UPDATE {TABLE} SET status='PREVIEW_QUEUED', lease_owner=NULL, lease_until=:lease, updated_at=:now, progress_message='Resuming automatic preparation' "
                "WHERE job_id=:job AND status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING') AND lease_until < :now"),
                {"now": now, "lease": now + timedelta(hours=2), "job": job})
            continue
        # Recheck the lease on the current row: a worker may have renewed it
        # since the non-locking SELECT. Never expire that renewed lease.
        conn.execute(text(f"UPDATE {TABLE} SET status='FAILED', error_code='INTERRUPTED_OR_TIMED_OUT', updated_at=:now "
            "WHERE job_id=:job AND status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING') AND lease_until < :now"),
            {"now": now, "job": job})


def _admission(conn):
    # Serializes capacity/context checks across API processes, not merely tabs.
    if conn.dialect.name == "mysql":
        if conn.execute(text("SELECT GET_LOCK('ht9046mx-reference-admission-v1', 3)")).scalar() != 1:
            raise ReviewConflict("QUEUE_BUSY")


def _release(conn):
    if conn.dialect.name == "mysql":
        conn.execute(text("SELECT RELEASE_LOCK('ht9046mx-reference-admission-v1')"))


@contextmanager
def admission_connection():
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Analytics database is not configured")
    with engine.connect() as conn:
        _admission(conn)
        conn.commit()  # named lock survives the transaction on this connection
        try:
            with conn.begin():
                yield conn
        finally:
            # Release AFTER transaction completion, never before its commit.
            _release(conn)
            conn.commit()


def create_preview(payload: ReferencePreviewRequest, actor: str) -> str:
    request = payload.model_dump(mode="json")
    digest = hashlib.sha256(encode({"actor": actor, "request": request}).encode()).hexdigest()
    with admission_connection() as conn:
        _expire(conn)
        previous = conn.execute(text(f"SELECT * FROM {TABLE} WHERE idempotency_key=:key"), {"key": payload.idempotency_key}).mappings().first()
        if previous:
            if previous["request_digest"] != digest:
                raise ReviewConflict("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_INPUT")
            return str(previous["job_id"])
        busy = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING') "
            "AND machine_number=:machine AND (module=:module OR module=0)"), {"machine": payload.machine_number, "module": payload.module}).scalar()
        count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING')")).scalar()
        if busy or count >= 4:
            raise ReviewConflict("CONTEXT_BUSY" if busy else "QUEUE_BUSY")
        job_id, now = str(uuid.uuid4()), utcnow()
        conn.execute(text(f"INSERT INTO {TABLE} (job_id,idempotency_key,request_digest,actor_id,machine_number,module,status,request_json,created_at,updated_at,lease_until) "
            "VALUES (:job,:key,:digest,:actor,:machine,:module,'PREVIEW_QUEUED',:request,:now,:now,:lease)"),
            {"job": job_id, "key": payload.idempotency_key, "digest": digest, "actor": actor,
             "machine": payload.machine_number, "module": payload.module, "request": encode(request), "now": now, "lease": now + timedelta(hours=2)})
        return job_id


def queue_build(job_id: str, actor: str, digest: str, note: str):
    with admission_connection() as conn:
        _expire(conn)
        row = _row(conn, job_id, lock=True)
        if row["actor_id"] != actor:
            raise PermissionError("Reference review belongs to another reviewer")
        if row["source_digest"] != digest:
            raise ReviewConflict("PREVIEW_MISMATCH")
        if row["status"] in ("BUILD_QUEUED", "BUILD_RUNNING", "COMPLETED"):
            if json.loads(row["selection_json"])["approval_note"] != note:
                raise ReviewConflict("BUILD_REQUEST_CHANGED")
            return
        if row["status"] != "READY" or not json.loads(row["preview_json"])["can_build"]:
            raise ReviewConflict("REFERENCE_NOT_READY")
        from .qualified_policy import manifest
        if json.loads(row['selection_json']).get('scoring_policy') != manifest():
            raise ReviewConflict('POLICY_CHANGED_REVIEW_AGAIN')
        if utcnow() - row["updated_at"] > timedelta(hours=24):
            raise ReviewConflict("PREVIEW_EXPIRED_REVIEW_AGAIN")
        busy = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE job_id<>:job AND status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING') "
            "AND machine_number=:machine AND (module=:module OR module=0)"), {"job": job_id, "machine": row["machine_number"], "module": row["module"]}).scalar()
        count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING')")).scalar()
        if busy or count >= 4:
            raise ReviewConflict("CONTEXT_BUSY" if busy else "QUEUE_BUSY")
        selection = json.loads(row["selection_json"])
        selection["approval_note"] = note
        now = utcnow()
        conn.execute(text(f"UPDATE {TABLE} SET status='BUILD_QUEUED',selection_json=:selection,lease_until=:lease,updated_at=:now WHERE job_id=:job"),
            {"job": job_id, "selection": encode(selection), "now": now, "lease": now + timedelta(hours=2)})


def get_job(job_id: str, actor: str) -> dict:
    with connection() as conn:
        row = _row(conn, job_id)
        if row["actor_id"] != actor and row["module"] != 0:
            raise PermissionError("Reference review belongs to another reviewer")
        if row["status"] in ACTIVE and row["lease_until"] is not None and row["lease_until"] < utcnow():
            _expire(conn, job_id)
            # MySQL REPEATABLE READ would otherwise reuse the first snapshot
            # when a concurrent renewal wins; locking read sees the current row.
            row = _row(conn, job_id, lock=True)
    return {"job_id": row["job_id"], "status": row["status"],
        "machine_number": row["machine_number"], "module": row["module"],
        "progress_message": row["progress_message"], "error_code": row["error_code"],
        "created_at": row["created_at"].isoformat() + "Z", "updated_at": row["updated_at"].isoformat() + "Z",
        "preview": json.loads(row["preview_json"]) if row["preview_json"] else None,
        "result": json.loads(row["result_json"]) if row["result_json"] else None}


def dispatch(job_id: str):
    # Concurrent poll/POST may submit duplicates, but only one SQL lease wins.
    with DISPATCH_LOCK:
        if job_id in DISPATCHED or len(DISPATCHED) >= 4:
            return
        DISPATCHED.add(job_id)
    def finished(_):
        with DISPATCH_LOCK:
            DISPATCHED.discard(job_id)
    POOL.submit(execute_job, job_id).add_done_callback(finished)


def recent_jobs(actor: str, machine_number: str, module: int) -> list[dict]:
    """Resume only this reviewer's context; listing never queues or changes a job."""
    from .inference import clean_machine_code
    with connection() as conn:
        rows = conn.execute(text(f"SELECT job_id,status,created_at,request_json FROM {TABLE} "
            "WHERE actor_id=:actor AND machine_number=:machine AND module=:module "
            "ORDER BY created_at DESC,job_id DESC LIMIT 12"),
            {"actor": actor, "machine": clean_machine_code(machine_number), "module": module}).mappings().all()
    return [{"job_id": row["job_id"], "status": row["status"],
             "created_at": row["created_at"].isoformat() + "Z", "request": json.loads(row["request_json"])} for row in rows]


def get_day(job_id: str, actor: str, day: date) -> dict:
    with connection() as conn:
        row = _row(conn, job_id)
    if row["actor_id"] != actor:
        raise PermissionError("Reference review belongs to another reviewer")
    if row["status"] not in ("READY", "BUILD_QUEUED", "BUILD_RUNNING", "COMPLETED"):
        raise ReviewConflict("REFERENCE_NOT_READY")
    preview = json.loads(row["preview_json"])
    selected_day = next((d for d in preview["daily"] if d["date"] == day.isoformat()), None)
    if selected_day is None:
        raise ReviewConflict("DETAIL_DAY_OUTSIDE_REFERENCE")
    if not selected_day.get("source_digest"):
        raise ReviewConflict("PREVIEW_EXPIRED_REVIEW_AGAIN")
    selection = json.loads(row["selection_json"])
    selection.pop("approval_note", None)
    settings = get_settings()
    payload = ReferencePreviewRequest.model_validate_json(row["request_json"])
    try:
        same_policy = resolve_selection(payload, datetime.fromisoformat(selection["source_latest"]), settings) == selection
    except ValueError as exc:
        raise ReviewConflict("POLICY_CHANGED_REVIEW_AGAIN") from exc
    if not same_policy:
        raise ReviewConflict("POLICY_CHANGED_REVIEW_AGAIN")
    start = datetime.combine(day, datetime.min.time())
    zone = ZoneInfo(settings.source_timezone)
    windows = load_observed_one_minute_windows(settings, machine_number=row["machine_number"],
        start=start.replace(tzinfo=zone), end=(start+timedelta(days=1)).replace(tzinfo=zone),
        as_of=datetime.fromisoformat(selection["source_latest"]).replace(tzinfo=zone), modules=(row["module"],))
    try:
        detail=minute_detail(windows, selection, day, selected_day["source_digest"])
        from .calibration_diagnostics import annotate_points
        annotate_points(detail["chart"],preview.get("diagnostics",{}),preview.get("baseline",{}))
        return detail
    except ValueError as exc:
        raise ReviewConflict(str(exc)) from exc


def execute_job(job_id: str):
    owner, now = str(uuid.uuid4()), utcnow()
    with connection() as conn:
        row = _row(conn, job_id, lock=True)
        if row["status"] in ACTIVE and row["lease_until"] is not None and row["lease_until"] < now:
            _expire(conn, job_id)
            return
        if row["status"] not in ("PREVIEW_QUEUED", "BUILD_QUEUED"):
            return
        phase = "PREVIEW_RUNNING" if row["status"] == "PREVIEW_QUEUED" else "BUILD_RUNNING"
        changed = conn.execute(text(f"UPDATE {TABLE} SET status=:phase,lease_owner=:owner,lease_until=:lease,updated_at=:now "
            "WHERE job_id=:job AND status=:previous"), {"job": job_id, "previous": row["status"], "phase": phase,
            "owner": owner, "lease": now + timedelta(minutes=15), "now": now}).rowcount
        if changed != 1:
            return

    def progress(day: str):
        message = "Calculating candidate evidence" if day == "calculating candidate evidence" else day if day.startswith(("Preparing ", "Saving ")) else f"Reading source day {day}"
        with connection() as conn:
            changed = conn.execute(text(f"UPDATE {TABLE} SET progress_message=:message,lease_until=:lease,updated_at=:now "
                "WHERE job_id=:job AND status=:phase AND lease_owner=:owner AND lease_until >= :now"),
                {"job": job_id, "phase": phase, "owner": owner, "now": utcnow(),
                 "lease": utcnow() + timedelta(minutes=15), "message": message}).rowcount
            if changed != 1:
                raise ReviewConflict("JOB_LEASE_LOST")

    try:
        settings = get_settings()
        if settings.app_mode == "demo" or settings.profile_window_contract != "qualified_observed_1m":
            raise ReviewConflict("QUALIFIED_LIVE_SOURCE_REQUIRED")
        if row["module"] == 0:
            if json.loads(row["request_json"]).get("mode") == "context-followup-v1":
                from .context_followup import execute_preparation
            elif json.loads(row["request_json"]).get("mode") == "context-reference-v1":
                from .context_reference import execute_preparation
            else:
                from .automatic_reference import execute_preparation
            execute_preparation(job_id,row,owner,phase,progress)
            return
        payload = ReferencePreviewRequest.model_validate_json(row["request_json"])
        if phase == "PREVIEW_RUNNING":
            latest = _latest_source_time(settings, payload.machine_number)
            if latest is None:
                raise ReviewConflict("NO_SOURCE_DATA")
            selection = resolve_selection(payload, latest, settings)
        else:
            selection = json.loads(row["selection_json"])
            note = selection.pop("approval_note")
            same = resolve_selection(payload, datetime.fromisoformat(selection["source_latest"]), settings)
            if same != selection:
                raise ReviewConflict("POLICY_CHANGED_REVIEW_AGAIN")
        start, ref_end, shadow_start, shadow_end = bounds(selection)
        zone = ZoneInfo(settings.source_timezone)
        windows = load_observed_one_minute_windows(settings, machine_number=payload.machine_number,
            start=start.replace(tzinfo=zone), end=shadow_end.replace(tzinfo=zone),
            as_of=datetime.fromisoformat(selection["source_latest"]).replace(tzinfo=zone),
            modules=(payload.module,), progress=progress, fresh=phase == "BUILD_RUNNING")
        progress("calculating candidate evidence")
        if phase == "PREVIEW_RUNNING":
            preview = make_preview(windows, selection, settings)
            with connection() as conn:
                conn.execute(text(f"UPDATE {TABLE} SET status='READY',selection_json=:selection,preview_json=:preview,source_digest=:digest,"
                    "lease_until=NULL,updated_at=:now WHERE job_id=:job AND lease_owner=:owner AND status=:phase AND lease_until>=:now"),
                    {"job": job_id, "owner": owner, "phase": phase, "selection": encode(selection), "preview": encode(preview),
                     "digest": preview["source_digest"], "now": utcnow()})
        else:
            if snapshot_digest(windows, selection) != row["source_digest"]:
                from .qualified_cache import invalidate_period
                start, _, _, end = bounds(selection)
                zone=ZoneInfo(settings.source_timezone)
                invalidate_period(settings,row["machine_number"],start.replace(tzinfo=zone),end.replace(tzinfo=zone))
                raise ReviewConflict("SOURCE_CHANGED_REVIEW_AGAIN")
            candidate = selected_candidate(windows, selection, settings)
            candidate["validation"]["reference_review"] = {**selection, "reviewer_id": row["actor_id"],
                "approval_note": note, "job_id": job_id, "source_digest": row["source_digest"]}
            with connection() as conn:
                current = _row(conn, job_id, lock=True)
                if current["status"] != phase or current["lease_owner"] != owner or current["lease_until"] < utcnow():
                    raise ReviewConflict("JOB_LEASE_LOST")
                result = persist_batch(settings, start, ref_end, shadow_start, shadow_end, [candidate], transaction=conn,
                    reference_review=candidate["validation"]["reference_review"])
                result["candidate_status"] = candidate["status"]
                conn.execute(text(f"UPDATE {TABLE} SET status='COMPLETED',result_json=:result,lease_until=NULL,updated_at=:now WHERE job_id=:job"),
                    {"job": job_id, "result": encode(result), "now": utcnow()})
    except Exception as exc:
        LOG.exception("Reference review job %s failed", job_id)
        error = str(exc) if isinstance(exc, ReviewConflict) else "INVALID_REFERENCE_OR_SOURCE" if isinstance(exc, ValueError) else "SOURCE_OR_DATABASE_UNAVAILABLE"
        with connection() as conn:
            conn.execute(text(f"UPDATE {TABLE} SET status='FAILED',error_code=:error,lease_until=NULL,updated_at=:now "
                "WHERE job_id=:job AND lease_owner=:owner AND status=:phase"),
                {"job": job_id, "owner": owner, "phase": phase, "error": error, "now": utcnow()})
