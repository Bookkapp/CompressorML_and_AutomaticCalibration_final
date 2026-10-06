from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import text

from .config import get_settings
from .db import connection
from .schemas import CalibrationReviewCreate, TechnicianConfirmationCreate


def _merge_source_aliases(rows):
    """One selector entry per canonical machine; source alias rows stay intact."""
    from .inference import clean_machine_code
    grouped={}
    for source in rows:
        key=clean_machine_code(source['machine_number'])
        if key not in grouped:
            grouped[key]={**source,'machine_number':key,'display_name':key}
            continue
        target=grouped[key]
        for field in ('row_count','record_count'):
            left,right=target.get(field),source.get(field)
            target[field]=None if left is None and right is None else (left or 0)+(right or 0)
        for field,latest in (('first_event',False),('latest_recorded_at',True),('last_event',True)):
            values=[v for v in (target.get(field),source.get(field)) if v is not None]
            if values:target[field]=sorted(values,key=lambda v:str(v).replace('T',' '),reverse=latest)[0]
    return [grouped[key] for key in sorted(grouped)]


def profile_is_approval_eligible(profile: dict[str, Any]) -> bool:
    """Do not turn a provisional/empty or unverified profile into live state."""
    settings = get_settings()
    reasons = profile.get("reason_codes") or []
    if isinstance(reasons, str):
        reasons = json.loads(reasons)
    return (
        profile.get("profile_status") == "READY_FOR_APPROVAL"
        and int(profile.get("calibration_windows") or 0) >= settings.profile_min_calibration_windows
        and int(profile.get("calibration_days") or 0) >= settings.profile_min_calibration_days
        and int(profile.get("shadow_windows") or 0) >= settings.profile_min_shadow_windows
        and int(profile.get("shadow_days") or 0) >= settings.profile_shadow_days
        and not any("UNVERIFIED" in str(reason) for reason in reasons)
    )


class AnalyticsRepository:
    def fleet_machines(self, hours: int = 24) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT s.machine_number, s.scored_rows, s.raw_flag_rate_pct,
                   COALESCE(a.alerts, 0) AS alerts, s.latest_event_time
            FROM (
                SELECT machine_number, COUNT(*) AS scored_rows,
                       100.0 * AVG(raw_flag) AS raw_flag_rate_pct,
                       MAX(event_time) AS latest_event_time
                FROM ht9046mx_shadow_score
                WHERE event_time >= TIMESTAMPADD(HOUR, -:hours, UTC_TIMESTAMP())
                GROUP BY machine_number
            ) s
            LEFT JOIN (
                SELECT machine_number, COUNT(*) AS alerts
                FROM ht9046mx_shadow_alert_episode
                WHERE detected_at >= TIMESTAMPADD(HOUR, -:hours, UTC_TIMESTAMP())
                GROUP BY machine_number
            ) a ON a.machine_number = s.machine_number
            ORDER BY s.machine_number
            """
        )
        with connection() as conn:
            return [dict(row) for row in conn.execute(query, {"hours": hours}).mappings()]

    def incidents(self, limit: int = 100, prospective_only: bool = False) -> list[dict[str, Any]]:
        settings = get_settings()
        where_clause = ""
        params: dict[str, Any] = {"limit": limit}
        if prospective_only:
            if settings.technician_feedback_start_at:
                where_clause = "WHERE a.detected_at >= :feedback_start"
                params["feedback_start"] = settings.technician_feedback_start_at
            else:
                where_clause = "WHERE a.detected_at >= DATE_SUB(UTC_TIMESTAMP(6), INTERVAL 3 DAY)"

        query = text(
            f"""
            SELECT a.alert_id, a.machine_number, a.module, a.episode_start,
                   a.detected_at, a.last_observed_at, a.alert_status, a.severity,
                   a.claim_level, a.release_version, a.evidence_json,
                   COALESCE(c.confirmation_status, 'PENDING') AS confirmation_status
            FROM ht9046mx_shadow_alert_episode a
            LEFT JOIN (
                SELECT t.alert_id, t.confirmation_status
                FROM ht9046mx_technician_confirmation t
                JOIN (
                    SELECT alert_id, MAX(confirmation_id) confirmation_id
                    FROM ht9046mx_technician_confirmation GROUP BY alert_id
                ) latest ON latest.confirmation_id = t.confirmation_id
            ) c ON c.alert_id = a.alert_id
            {where_clause}
            ORDER BY a.detected_at DESC
            LIMIT :limit
            """
        )
        with connection() as conn:
            rows = [dict(row) for row in conn.execute(query, params).mappings()]
        for row in rows:
            evidence = row.pop("evidence_json") or {}
            row["evidence"] = json.loads(evidence) if isinstance(evidence, str) else evidence
            row["is_prospective"] = True
        return rows

    def simulate_prospective_alert(self, machine: str = "MX080", module: int = 6) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        evidence = {
            "score": 9.85,
            "threshold": 7.65,
            "sv": "Off",
            "source": "incoming live telemetry stream",
            "prospective": True,
        }
        query = text("""
            INSERT INTO ht9046mx_shadow_alert_episode
            (machine_number, module, episode_start, detected_at, last_observed_at, alert_status, severity, claim_level, release_version, evidence_json)
            VALUES (:machine, :module, :start, :detected, :last, 'OPEN', 'CRITICAL', 'PERSISTENT_PATTERN', 'live-stream-prospective-v1', :evidence)
        """)
        with connection() as conn:
            existing = conn.execute(text("""
                SELECT alert_id, episode_start, detected_at
                FROM ht9046mx_shadow_alert_episode
                WHERE machine_number = :machine AND module = :module AND alert_status = 'OPEN'
                ORDER BY alert_id DESC LIMIT 1
            """), {"machine": machine.upper(), "module": module}).mappings().first()

            if existing:
                conn.execute(text("""
                    UPDATE ht9046mx_shadow_alert_episode
                    SET last_observed_at = :last, evidence_json = :evidence
                    WHERE alert_id = :aid
                """), {"last": now, "evidence": json.dumps(evidence), "aid": existing["alert_id"]})
                alert_id = existing["alert_id"]
                start_time = existing["episode_start"]
                detected_time = existing["detected_at"]
            else:
                res = conn.execute(query, {
                    "machine": machine.upper(),
                    "module": module,
                    "start": now - timedelta(minutes=15),
                    "detected": now,
                    "last": now,
                    "evidence": json.dumps(evidence),
                })
                alert_id = int(res.lastrowid)
                start_time = now - timedelta(minutes=15)
                detected_time = now

        return {
            "alert_id": alert_id,
            "machine_number": machine.upper(),
            "module": module,
            "episode_start": start_time.isoformat() if hasattr(start_time, "isoformat") else str(start_time),
            "detected_at": detected_time.isoformat() if hasattr(detected_time, "isoformat") else str(detected_time),
            "last_observed_at": now.isoformat(),
            "alert_status": "OPEN",
            "severity": "CRITICAL",
            "claim_level": "PERSISTENT_PATTERN",
            "release_version": "live-stream-prospective-v1",
            "evidence": evidence,
            "confirmation_status": "PENDING",
            "is_prospective": True,
        }

    def timeline(self, machine: str, module: int, start: datetime, end: datetime) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT event_time, hp1, lp1, hp2, lp2, valve, temp_high, temp_low,
                   anomaly_score, threshold_value AS threshold, raw_flag,
                   persistent_flag, sv_state, busy_state, state_code,
                   message_code, message_text, data_quality_status
            FROM ht9046mx_incident_telemetry
            WHERE machine_number = :machine AND module = :module
              AND event_time >= :start AND event_time <= :end
            ORDER BY event_time
            """
        )
        with connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    query,
                    {"machine": machine, "module": module, "start": start, "end": end},
                ).mappings()
            ]

    def alert_metadata(self, alert_id: int) -> dict[str, Any] | None:
        query = text(
            """
            SELECT alert_id, detected_at
            FROM ht9046mx_shadow_alert_episode
            WHERE alert_id = :alert_id
            """
        )
        with connection() as conn:
            row = conn.execute(query, {"alert_id": alert_id}).mappings().first()
        return dict(row) if row else None

    def create_confirmation(
        self,
        alert_id: int,
        technician_id: str,
        payload: TechnicianConfirmationCreate,
    ) -> int:
        query = text(
            """
            INSERT INTO ht9046mx_technician_confirmation (
                alert_id, idempotency_key, confirmation_status,
                technician_note, technician_id, label_status,
                feedback_policy_version
            ) VALUES (
                :alert_id, :idempotency_key, :confirmation_status,
                :technician_note, :technician_id, 'PENDING_QA',
                'prospective-binary-v1'
            )
            ON DUPLICATE KEY UPDATE confirmation_id = LAST_INSERT_ID(confirmation_id)
            """
        )
        values = payload.model_dump()
        values.update(
            alert_id=alert_id,
            technician_id=technician_id,
        )
        with connection() as conn:
            result = conn.execute(query, values)
            return int(result.lastrowid)

    def automation_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT run_id, job_type, started_at, completed_at, result_status,
                   artifact_version, detail_json
            FROM ht9046mx_automation_run
            ORDER BY started_at DESC LIMIT :limit
            """
        )
        with connection() as conn:
            return [dict(row) for row in conn.execute(query, {"limit": limit}).mappings()]

    @staticmethod
    def _decode_json(row: dict[str, Any], *fields: str) -> dict[str, Any]:
        for field in fields:
            value = row.get(field)
            if isinstance(value, str):
                row[field] = json.loads(value)
            elif value is None:
                row[field] = [] if field == "reason_codes" else {}
        return row

    def calibration_batches(self, limit: int = 30) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT b.batch_id, b.batch_status, b.source_start, b.calibration_end,
                   b.shadow_start, b.shadow_end, b.source_timezone,
                   b.profile_algorithm_version, b.feature_version, b.created_at,
                   COUNT(p.profile_id) AS profile_count,
                   SUM(p.profile_status = 'READY_FOR_APPROVAL') AS ready_for_approval_count
            FROM ht9046mx_calibration_batch b
            LEFT JOIN ht9046mx_calibration_profile p ON p.batch_id = b.batch_id
            GROUP BY b.batch_id, b.batch_status, b.source_start, b.calibration_end,
                     b.shadow_start, b.shadow_end, b.source_timezone,
                     b.profile_algorithm_version, b.feature_version, b.created_at
            ORDER BY b.created_at DESC LIMIT :limit
            """
        )
        with connection() as conn:
            rows = [dict(row) for row in conn.execute(query, {"limit": limit}).mappings()]
        for row in rows:
            row["profile_count"] = int(row["profile_count"] or 0)
            row["ready_for_approval_count"] = int(row["ready_for_approval_count"] or 0)
        return rows

    def calibration_profiles(self, batch_id: str, limit: int = 500) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT profile_id, batch_id, profile_version, machine_number, module,
                   sv_state, state_code, profile_status, reason_codes,
                   calibration_windows, calibration_days, quarantine_pct,
                   max_half_shift_rz, shadow_windows, shadow_days,
                   shadow_flag_pct, persistent_flag_pct, statistics_json,
                   threshold_json, validation_json
            FROM ht9046mx_calibration_profile
            WHERE batch_id = :batch_id
            ORDER BY machine_number, module, sv_state, state_code
            LIMIT :limit
            """
        )
        with connection() as conn:
            rows = [dict(row) for row in conn.execute(query, {"batch_id": batch_id, "limit": limit}).mappings()]
        result: list[dict[str, Any]] = []
        for row in rows:
            row = self._decode_json(row, "reason_codes", "statistics_json", "threshold_json", "validation_json")
            row["statistics"] = row.pop("statistics_json")
            row["thresholds"] = row.pop("threshold_json")
            row["validation"] = row.pop("validation_json")
            result.append(row)
        return result

    def calibration_shadow_points(self, profile_id: int, limit: int = 10000) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT event_time, deviation_score, threshold_value, raw_flag,
                   persistent_flag, data_quality_status
            FROM ht9046mx_calibration_shadow_point
            WHERE profile_id = :profile_id
            ORDER BY event_time LIMIT :limit
            """
        )
        with connection() as conn:
            return [dict(row) for row in conn.execute(query, {"profile_id": profile_id, "limit": limit}).mappings()]

    def review_calibration_profile(
        self,
        profile_id: int,
        approver_id: str,
        payload: CalibrationReviewCreate,
    ) -> tuple[int, str, str]:
        with connection() as conn:
            profile = conn.execute(
                text("""
                    SELECT profile_id, batch_id, profile_status, machine_number, module, sv_state, state_code,
                           calibration_windows, calibration_days, shadow_windows, shadow_days, reason_codes
                    FROM ht9046mx_calibration_profile WHERE profile_id = :profile_id FOR UPDATE
                """),
                {"profile_id": profile_id},
            ).mappings().first()
            if profile is None:
                raise KeyError("Calibration profile was not found")
            profile = dict(profile)
            existing = conn.execute(
                text("SELECT review_id FROM ht9046mx_calibration_review WHERE idempotency_key = :idempotency_key"),
                {"idempotency_key": payload.idempotency_key},
            ).scalar_one_or_none()
            if existing is not None:
                return int(existing), str(profile["profile_status"]), str(profile["batch_id"])
            if payload.decision == "APPROVE":
                if not profile_is_approval_eligible(profile):
                    raise ValueError("Profile has not passed calibration, shadow and evidence approval gates")
            if payload.decision == "REJECT" and len(payload.review_note.strip()) < 8:
                raise ValueError("A rejection note of at least 8 characters is required")
            result = conn.execute(text("""
                INSERT INTO ht9046mx_calibration_review (batch_id, profile_id, idempotency_key, decision, review_note, approver_id)
                VALUES (:batch_id, :profile_id, :idempotency_key, :decision, :review_note, :approver_id)
            """), {"batch_id": profile["batch_id"], "profile_id": profile_id, "idempotency_key": payload.idempotency_key, "decision": payload.decision, "review_note": payload.review_note.strip() or None, "approver_id": approver_id})
            review_id = int(result.lastrowid)
            if payload.decision == "REJECT":
                conn.execute(text("""
                    UPDATE ht9046mx_calibration_profile
                    SET profile_status = 'REJECTED', reviewed_at = UTC_TIMESTAMP(6), reviewer_id = :approver_id, review_note = :review_note
                    WHERE profile_id = :profile_id
                """), {"profile_id": profile_id, "approver_id": approver_id, "review_note": payload.review_note.strip()})
                conn.execute(text("UPDATE ht9046mx_calibration_batch SET batch_status = 'PARTIALLY_REVIEWED' WHERE batch_id = :batch_id AND batch_status = 'COMPLETED'"), {"batch_id": profile["batch_id"]})
                return review_id, "REJECTED", str(profile["batch_id"])
            previous = conn.execute(text("""
                SELECT active_profile_id FROM ht9046mx_active_calibration_profile
                WHERE machine_number = :machine_number AND module = :module AND sv_state = :sv_state AND state_code = :state_code
                FOR UPDATE
            """), profile).scalar_one_or_none()
            rollback_mode = "PREVIOUS_ACTIVE_PROFILE" if previous is not None else "NO_ACTIVE_PROFILE_FAIL_CLOSED"
            conn.execute(text("""
                INSERT INTO ht9046mx_active_calibration_profile
                (machine_number, module, sv_state, state_code, active_profile_id, rollback_mode, rollback_profile_id, activated_by)
                VALUES (:machine_number, :module, :sv_state, :state_code, :profile_id, :rollback_mode, :rollback_profile_id, :approver_id)
                ON DUPLICATE KEY UPDATE active_profile_id = VALUES(active_profile_id), rollback_mode = VALUES(rollback_mode), rollback_profile_id = VALUES(rollback_profile_id), activated_at = UTC_TIMESTAMP(6), activated_by = VALUES(activated_by)
            """), {**profile, "rollback_mode": rollback_mode, "rollback_profile_id": previous, "approver_id": approver_id})
            conn.execute(text("""
                UPDATE ht9046mx_calibration_profile
                SET profile_status = 'ACTIVE_FROZEN', reviewed_at = UTC_TIMESTAMP(6), reviewer_id = :approver_id, review_note = :review_note
                WHERE profile_id = :profile_id
            """), {"profile_id": profile_id, "approver_id": approver_id, "review_note": payload.review_note.strip() or None})
            conn.execute(text("UPDATE ht9046mx_calibration_batch SET batch_status = 'PARTIALLY_REVIEWED' WHERE batch_id = :batch_id AND batch_status = 'COMPLETED'"), {"batch_id": profile["batch_id"]})
            return review_id, "APPROVED", str(profile["batch_id"])

    def approve_machine_profiles(
        self,
        machine_number: str,
        approver_id: str,
        batch_id: str | None = None,
        review_note: str | None = None,
    ) -> dict[str, Any]:
        """Approve all candidate profiles for a machine into ACTIVE_FROZEN with transactional rollback pointers."""
        with connection() as conn:
            from .inference import get_machine_candidates
            cands = get_machine_candidates(machine_number)
            query = """
                SELECT profile_id, batch_id, profile_status, machine_number, module, sv_state, state_code,
                       calibration_windows, calibration_days, shadow_windows, shadow_days, reason_codes
                FROM ht9046mx_calibration_profile
                WHERE machine_number IN :cands
                  AND profile_status = 'READY_FOR_APPROVAL'
            """
            params: dict[str, Any] = {"cands": tuple(cands)}
            if batch_id:
                query += " AND batch_id = :batch_id"
                params["batch_id"] = batch_id
            query += " FOR UPDATE"
            profiles = [dict(p) for p in conn.execute(text(query), params).mappings().all()]
            if not profiles:
                return {"approved_count": 0, "profile_ids": [], "message": f"ไม่พบ Candidate Profile ที่รออนุมัติสำหรับเครื่อง {machine_number}"}
            if len(profiles) != 8 or {int(p["module"]) for p in profiles} != set(range(1, 9)) or not all(profile_is_approval_eligible(p) for p in profiles):
                raise ValueError("All eight module profiles in one batch must pass calibration and shadow gates")
            if len({p["batch_id"] for p in profiles}) != 1:
                raise ValueError("Bulk approval must use profiles from exactly one batch")

            approved_ids: list[int] = []
            note = review_note or f"Batch approved all modules for machine {machine_number} by {approver_id}"
            now_ts = datetime.now(timezone.utc).timestamp()
            for p in profiles:
                pid = int(p["profile_id"])
                idem = f"approve-machine-{pid}-{approver_id}-{now_ts}"
                conn.execute(text("""
                    INSERT INTO ht9046mx_calibration_review (batch_id, profile_id, idempotency_key, decision, review_note, approver_id)
                    VALUES (:batch_id, :profile_id, :idempotency_key, 'APPROVE', :review_note, :approver_id)
                """), {"batch_id": p["batch_id"], "profile_id": pid, "idempotency_key": idem, "review_note": note, "approver_id": approver_id})

                previous = conn.execute(text("""
                    SELECT active_profile_id FROM ht9046mx_active_calibration_profile
                    WHERE machine_number = :machine_number AND module = :module AND sv_state = :sv_state AND state_code = :state_code
                    FOR UPDATE
                """), p).scalar_one_or_none()
                rollback_mode = "PREVIOUS_ACTIVE_PROFILE" if previous is not None else "NO_ACTIVE_PROFILE_FAIL_CLOSED"
                conn.execute(text("""
                    INSERT INTO ht9046mx_active_calibration_profile
                    (machine_number, module, sv_state, state_code, active_profile_id, rollback_mode, rollback_profile_id, activated_by)
                    VALUES (:machine_number, :module, :sv_state, :state_code, :profile_id, :rollback_mode, :rollback_profile_id, :approver_id)
                    ON DUPLICATE KEY UPDATE active_profile_id = VALUES(active_profile_id), rollback_mode = VALUES(rollback_mode), rollback_profile_id = VALUES(rollback_profile_id), activated_at = UTC_TIMESTAMP(6), activated_by = VALUES(activated_by)
                """), {**p, "rollback_mode": rollback_mode, "rollback_profile_id": previous, "approver_id": approver_id})
                conn.execute(text("""
                    UPDATE ht9046mx_calibration_profile
                    SET profile_status = 'ACTIVE_FROZEN', reviewed_at = UTC_TIMESTAMP(6), reviewer_id = :approver_id, review_note = :review_note
                    WHERE profile_id = :profile_id
                """), {"profile_id": pid, "approver_id": approver_id, "review_note": note})
                approved_ids.append(pid)

            for bid in set(p["batch_id"] for p in profiles):
                conn.execute(text("UPDATE ht9046mx_calibration_batch SET batch_status = 'APPROVED' WHERE batch_id = :bid"), {"bid": bid})
            return {"approved_count": len(approved_ids), "profile_ids": approved_ids, "message": f"อนุมัติ {len(approved_ids)} โมดูลสำหรับเครื่อง {machine_number} เป็น Active Frozen สำเร็จ"}

    def active_profiles(self) -> list[dict[str, Any]]:
        """Return all current ACTIVE_FROZEN profiles with their statistics, baseline, and audit info."""
        with connection() as conn:
            rows = conn.execute(text("""
                SELECT
                    a.machine_number, a.module, a.sv_state, a.state_code, a.active_profile_id,
                    a.activated_at, a.activated_by, a.rollback_mode, a.rollback_profile_id,
                    p.profile_version, b.feature_version, p.calibration_windows, p.calibration_days, p.quarantine_pct,
                    p.max_half_shift_rz, p.shadow_windows, p.shadow_days, p.shadow_flag_pct,
                    p.persistent_flag_pct, p.statistics_json, p.threshold_json, p.validation_json,
                    p.reason_codes, p.reviewer_id, p.review_note, p.reviewed_at
                FROM ht9046mx_active_calibration_profile a
                JOIN ht9046mx_calibration_profile p ON a.active_profile_id = p.profile_id
                JOIN ht9046mx_calibration_batch b ON b.batch_id = p.batch_id
                ORDER BY a.machine_number, a.module
            """)).mappings().all()
            result = []
            for r in rows:
                item = dict(r)
                item["statistics"] = json.loads(item.pop("statistics_json")) if item.get("statistics_json") else {}
                item["thresholds"] = json.loads(item.pop("threshold_json")) if item.get("threshold_json") else {}
                item["validation"] = json.loads(item.pop("validation_json")) if item.get("validation_json") else {}
                item["reason_codes"] = json.loads(item.pop("reason_codes")) if item.get("reason_codes") else []
                result.append(item)
            return result

    def source_machines(self) -> list[dict[str, Any]]:
        from .qualified_cache import cached_machine_inventory
        from .config import get_settings
        discovered = cached_machine_inventory(get_settings())
        if discovered:
            return _merge_source_aliases(discovered)
        query = text("""
            SELECT DISTINCT machine_number FROM ht9046mx_calibration_profile
            UNION
            SELECT DISTINCT machine_number FROM ht9046mx_shadow_score
            ORDER BY machine_number
        """)
        try:
            with connection() as conn:
                rows = conn.execute(query).mappings().all()
                return [
                    {
                        "machine_number": str(row["machine_number"]),
                        "display_name": str(row["machine_number"]),
                        "record_count": None,
                        "latest_recorded_at": None,
                    }
                    for row in rows
                ]
        except Exception:
            return []
