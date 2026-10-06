"""Automatic preparation uses the same complete-day selection and fit as Manual.

Only candidates are written. Each module has a saved review job; an unavailable
module does not prevent candidates for the other modules. Parent completion,
children and candidate batch commit in one transaction under the SQL job lease.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from . import reference_jobs as jobs
from .calibration import _latest_source_time, discover_source_machines, persist_batch
from .config import get_settings
from .db import connection
from .inference import clean_machine_code
from .qualified_cache import prime_period, load_cached_windows
from .reference_review import ReferencePreviewRequest, bounds, resolve_selection, make_preview, selected_candidate
from .reference_selector import propose, VERSION as SELECTOR_VERSION

MODE = "automatic-reference-v1"


class PreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8,max_length=100)
    machine_number: str = Field(min_length=1,max_length=40)
    history_days: int = Field(default=28,ge=7,le=90)

    @model_validator(mode="after")
    def valid(self):
        self.machine_number = clean_machine_code(self.machine_number)
        if not self.machine_number or not any(c.isdigit() for c in self.machine_number):
            raise ValueError("Choose one discovered machine")
        return self


def create_preparation(payload: PreparationRequest, actor: str, *, mode=MODE):
    if mode not in {MODE,"context-reference-v1","context-followup-v1"}: raise ValueError("Unknown preparation mode")
    request = {"mode":mode,**payload.model_dump(mode="json")}
    digest = hashlib.sha256(jobs.encode({"actor":actor,"request":request}).encode()).hexdigest()
    with jobs.admission_connection() as conn:
        jobs._expire(conn)
        old = conn.execute(text(f"SELECT job_id,request_digest FROM {jobs.TABLE} WHERE idempotency_key=:key"),
                           {"key":payload.idempotency_key}).mappings().first()
        if old:
            if old["request_digest"] != digest: raise jobs.ReviewConflict("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_INPUT")
            return old["job_id"]
        active = conn.execute(text(f"SELECT job_id,module,request_json FROM {jobs.TABLE} WHERE machine_number=:machine "
            "AND status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING') ORDER BY created_at LIMIT 1"),
            {"machine":payload.machine_number}).mappings().first()
        if active:
            running = json.loads(active["request_json"])
            comparable = lambda p: {k:v for k,v in p.items() if k != "idempotency_key"}
            if active["module"] == 0 and comparable(running) == comparable(request):
                return active["job_id"]
            raise jobs.ReviewConflict("CONTEXT_BUSY")
        count = conn.execute(text(f"SELECT COUNT(*) FROM {jobs.TABLE} WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING')")).scalar()
        if count >= 4: raise jobs.ReviewConflict("QUEUE_BUSY")
        job_id, stamp = str(uuid.uuid4()), jobs.utcnow()
        conn.execute(text(f"INSERT INTO {jobs.TABLE}(job_id,idempotency_key,request_digest,actor_id,machine_number,module,status,request_json,created_at,updated_at,lease_until) "
            "VALUES(:job,:key,:digest,:actor,:machine,0,'PREVIEW_QUEUED',:request,:stamp,:stamp,:lease)"),
            {"job":job_id,"key":payload.idempotency_key,"digest":digest,"actor":actor,"machine":payload.machine_number,
             "request":jobs.encode(request),"stamp":stamp,"lease":stamp+timedelta(hours=2)})
        return job_id


def latest_preparation(machine: str):
    with connection() as conn:
        rows = conn.execute(text(f"SELECT job_id,actor_id,request_json FROM {jobs.TABLE} WHERE machine_number=:machine AND module=0 ORDER BY created_at DESC,job_id DESC LIMIT 100"),
            {"machine":clean_machine_code(machine)}).mappings().all()
    row = next((r for r in rows if json.loads(r["request_json"]).get("mode")==MODE),None)
    return jobs.get_job(row["job_id"],row["actor_id"]) if row else None


def copy_review(job_id: str, actor: str):
    """Copy immutable automatic evidence into this reviewer's own draft context."""
    with jobs.admission_connection() as conn:
        row = jobs._row(conn,job_id)
        result = json.loads(row["result_json"] or "{}")
        parent_id = result.get("automatic_parent_id")
        if not parent_id or row["status"] not in ("READY","COMPLETED"):
            raise jobs.ReviewConflict("AUTOMATIC_REVIEW_NOT_READY")
        parent = jobs._row(conn,parent_id)
        if json.loads(parent["request_json"]).get("mode") != MODE:
            raise jobs.ReviewConflict("AUTOMATIC_REVIEW_NOT_READY")
        # Stable per reviewer/source child: double clicks and tabs reuse one copy.
        key = "auto-copy-"+hashlib.sha256((job_id+":"+actor).encode()).hexdigest()
        previous = conn.execute(text(f"SELECT job_id FROM {jobs.TABLE} WHERE idempotency_key=:key"),{"key":key}).scalar()
        if previous: return str(previous)
        clone, stamp = str(uuid.uuid4()), jobs.utcnow()
        request = json.loads(row["request_json"]); request["idempotency_key"] = key
        values = {name:row[name] for name in ("machine_number","module","status","selection_json","preview_json","source_digest","result_json")}
        values.update(job=clone,key=key,actor=actor,request=jobs.encode(request),stamp=stamp,
                      digest=hashlib.sha256(jobs.encode({"actor":actor,"request":request}).encode()).hexdigest())
        conn.execute(text(f"INSERT INTO {jobs.TABLE}(job_id,idempotency_key,request_digest,actor_id,machine_number,module,status,request_json,selection_json,preview_json,source_digest,result_json,created_at,updated_at) "
            "VALUES(:job,:key,:digest,:actor,:machine_number,:module,:status,:request,:selection_json,:preview_json,:source_digest,:result_json,:stamp,:stamp)"),values)
        return clone


def execute_preparation(job_id, row, owner, phase, progress):
    settings = get_settings()
    if settings.app_mode == "demo" or settings.profile_window_contract != "qualified_observed_1m":
        raise jobs.ReviewConflict("QUALIFIED_LIVE_SOURCE_REQUIRED")
    request = PreparationRequest.model_validate({k:v for k,v in json.loads(row["request_json"]).items() if k != "mode"})
    latest = _latest_source_time(settings,request.machine_number)
    if latest is None: raise jobs.ReviewConflict("NO_SOURCE_DATA")
    payloads = [ReferencePreviewRequest(idempotency_key=f"{job_id}-m{module}",machine_number=request.machine_number,
        module=module,history_days=request.history_days,review_note="Automatic preparation; Reference has not been certified healthy or approved") for module in range(1,9)]
    selections = [resolve_selection(payload,latest,settings) for payload in payloads]
    start, ref_end, shadow_start, shadow_end = bounds(selections[0])
    zone = ZoneInfo(settings.source_timezone)
    args = dict(machine_number=request.machine_number,start=start.replace(tzinfo=zone),end=shadow_end.replace(tzinfo=zone),
                as_of=datetime.fromisoformat(selections[0]["source_latest"]).replace(tzinfo=zone))
    checked_after = prime_period(settings,**args,progress=progress)
    previews, candidates, results = [], [], []
    for index,(payload, selection) in enumerate(zip(payloads,selections)):
        progress(f"Preparing M{payload.module}")
        windows = load_cached_windows(settings,**args,modules=(payload.module,),minimum_checked_at=checked_after)
        proposal=propose(windows,selection,settings)
        if proposal["changed"]:
            payload=payload.model_copy(update={"reference_start":datetime.fromisoformat(proposal["selected"]["start"]).date(),
                "reference_end":datetime.fromisoformat(proposal["selected"]["end"]).date(),
                "review_note":"Automatic past-only Reference proposal; not certified healthy"})
            selection=resolve_selection(payload,latest,settings)
            chosen_start,_,_,chosen_end=bounds(selection)
            windows=[w for w in windows if chosen_start<=w.window_start<chosen_end]
        selections[index]=selection
        candidate = selected_candidate(windows,selection,settings)
        if proposal["needs_review"] and candidate["status"]!="INSUFFICIENT_DATA":
            candidate["reasons"]=sorted(set([*candidate["reasons"],"REFERENCE_SELECTION_NEEDS_REVIEW"]))
            candidate["validation"]["reason_codes"]=candidate["reasons"]
            candidate["status"]="REVIEW_REQUIRED"
        preview = make_preview(windows,selection,settings,candidate=candidate)
        preview["reference_proposal"]=proposal
        child_id = str(uuid.uuid5(uuid.UUID(job_id),f"module-{payload.module}"))
        candidate = candidate if preview["can_build"] else None
        if candidate:
            candidate["validation"]["reference_review"] = {**selection,"preparation_mode":MODE,
                "reference_acknowledged":False,"reviewer_id":row["actor_id"],"job_id":child_id,"automatic_parent_id":job_id,
                "source_digest":preview["source_digest"],"reference_proposal":proposal}
            candidates.append(candidate)
        previews.append((payload,selection,preview,child_id))
        results.append({"module":payload.module,"job_id":child_id,"status":preview["candidate_status"],
            "candidate_created":bool(candidate),"reason_codes":preview["reason_codes"],"coverage_issues":preview["coverage_issues"],
            "summary":preview["summary"],"reference_selection":{"start":selection["reference_start"],"end":selection["reference_end"],"changed":proposal["changed"],"reason":proposal["reason"]}})
    progress("Saving candidates and review evidence")
    with connection() as conn:
        current = jobs._row(conn,job_id,lock=True)
        if current["status"] != phase or current["lease_owner"] != owner or current["lease_until"] < jobs.utcnow():
            raise jobs.ReviewConflict("JOB_LEASE_LOST")
        batch = persist_batch(settings,start,ref_end,shadow_start,shadow_end,candidates,transaction=conn,
            reference_review={"preparation_mode":MODE,"parent_job_id":job_id,"reference_acknowledged":False}) if candidates else {}
        for payload, selection, preview, child_id in previews:
            module_result = next(r for r in results if r["module"] == payload.module)
            result = {"automatic_parent_id":job_id,"candidate_status":preview["candidate_status"],
                      "batch_id":batch.get("batch_id") if module_result["candidate_created"] else None}
            data = payload.model_dump(mode="json")
            conn.execute(text(f"INSERT INTO {jobs.TABLE}(job_id,idempotency_key,request_digest,actor_id,machine_number,module,status,request_json,selection_json,preview_json,source_digest,result_json,created_at,updated_at) "
                "VALUES(:job,:key,:digest,:actor,:machine,:module,:status,:request,:selection,:preview,:source,:result,:stamp,:stamp)"),
                {"job":child_id,"key":payload.idempotency_key,"digest":hashlib.sha256(jobs.encode({"actor":row["actor_id"],"request":data}).encode()).hexdigest(),
                 "actor":row["actor_id"],"machine":payload.machine_number,"module":payload.module,
                 "status":"COMPLETED" if module_result["candidate_created"] else "READY","request":jobs.encode(data),
                 "selection":jobs.encode(selection),"preview":jobs.encode(preview),"source":preview["source_digest"],"result":jobs.encode(result),"stamp":jobs.utcnow()})
        result = {"mode":MODE,"selector_version":SELECTOR_VERSION,"modules":results,"batch_id":batch.get("batch_id"),"profiles":len(candidates),
                  "selection":{k:selections[0][k] for k in ("source_latest","reference_start","reference_end","shadow_start","shadow_end")},
                  "auto_activation_allowed":False}
        conn.execute(text(f"UPDATE {jobs.TABLE} SET status='COMPLETED',result_json=:result,selection_json=:selection,lease_until=NULL,updated_at=:stamp WHERE job_id=:job"),
                     {"job":job_id,"result":jobs.encode(result),"selection":jobs.encode(selections[0]),"stamp":jobs.utcnow()})


def run_candidate_cycle(settings, target_machine=None, history_days=None, shadow_days=None, force=False, target_module=None):
    if not settings.profile_candidate_enabled and not force: return {"status":"SKIPPED_NOT_ENABLED"}
    if shadow_days is not None and shadow_days != 3: raise ValueError("Shared reference preparation uses three complete Shadow days")
    if target_module is not None: raise ValueError("Automatic preparation covers all modules; use Manual review for a selected module")
    machines = [clean_machine_code(target_machine)] if target_machine else sorted({clean_machine_code(r["machine_number"]) for r in discover_source_machines(settings)})
    results=[]
    for machine in machines:
        previous = latest_preparation(machine)
        latest = _latest_source_time(settings,machine)
        if latest is None: results.append({"machine_number":machine,"status":"NO_SOURCE_DATA"}); continue
        selection = resolve_selection(ReferencePreviewRequest(idempotency_key="scheduled-reference",machine_number=machine,module=1,
            history_days=history_days or settings.profile_history_days),latest,settings)
        if previous and previous["status"] == "COMPLETED" and not force:
            with connection() as conn: old = jobs._row(conn,previous["job_id"])
            old_selection = json.loads(old["selection_json"] or "{}")
            previous_end = datetime.fromisoformat(old_selection["shadow_end"])
            if (previous.get("result") or {}).get("selector_version")==SELECTOR_VERSION and old_selection.get("scoring_policy") == selection.get("scoring_policy") and old_selection.get("policy") == selection["policy"] and datetime.fromisoformat(selection["shadow_end"]) < previous_end+timedelta(days=settings.profile_retry_min_new_days):
                results.append({"machine_number":machine,"status":"WAITING_FOR_NEW_SOURCE_DAYS"}); continue
        payload = PreparationRequest(idempotency_key="scheduled-"+str(uuid.uuid4()),machine_number=machine,history_days=history_days or settings.profile_history_days)
        try:
            job_id = create_preparation(payload,"AUTO_CALIBRATION")
            jobs.execute_job(job_id)
            value = jobs.get_job(job_id,"AUTO_CALIBRATION")
            results.append({"machine_number":machine,"job_id":job_id,"status":value["status"],**(value["result"] or {})})
        except jobs.ReviewConflict as exc:
            results.append({"machine_number":machine,"status":str(exc)})
    summary = {"status":"AUTOMATIC_REFERENCE_CYCLE","machine_results":results,
               "profiles":sum(r.get("profiles",0) for r in results),"auto_activation_allowed":False,
               "status_counts":{"READY_FOR_APPROVAL":sum(m["status"]=="READY_FOR_APPROVAL" for r in results for m in r.get("modules",[]))}}
    if target_machine and len(results)==1:
        summary.update(batch_id=results[0].get("batch_id"),target_machine=machines[0],
            status="COMPLETED" if results[0]["status"]=="COMPLETED" and summary["profiles"] else
                   "SKIPPED_NO_QUALIFIED_WINDOWS" if results[0]["status"]=="COMPLETED" else results[0]["status"])
    return summary
