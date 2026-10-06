from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .config import get_settings
from .db import connection

# In-memory persistence tracker across cycles: (machine_clean, module) -> int
_MODULE_PERSISTENCE_STATE: dict[tuple[str, int], int] = {}
_PERSISTENCE_BOOTSTRAPPED: bool = False

# The live worker currently computes a robust-z envelope, not ARX-Ridge.
RUNTIME_SCORER_VERSION = "robust-z-envelope-v1"
RUNTIME_FEATURE_VERSION = "live-robust-z-core-v1"
RUNTIME_THRESHOLD_VERSION = "active-profile-deviation-q995-v1"


def bootstrap_persistence_state() -> None:
    """Recover persistence counters from the last shadow_score rows on startup.

    For each (machine, module) pair, count the trailing consecutive raw_flag=1
    rows from the most recent scores. This prevents episode onset misses after
    server restart.
    """
    global _PERSISTENCE_BOOTSTRAPPED
    if _PERSISTENCE_BOOTSTRAPPED:
        return
    try:
        with connection() as conn:
            # Get the last 10 rows per machine/module (enough to detect persistence>=3)
            rows = conn.execute(text("""
                SELECT machine_number, module, raw_flag
                FROM (
                    SELECT machine_number, module, raw_flag,
                           ROW_NUMBER() OVER (PARTITION BY machine_number, module ORDER BY event_time DESC) AS rn
                    FROM ht9046mx_shadow_score
                    WHERE event_time >= NOW() - INTERVAL 2 HOUR
                ) t
                WHERE rn <= 10
                ORDER BY machine_number, module, rn ASC
            """)).mappings().all()

            # Group by (machine, module) and count trailing consecutive flags
            from collections import defaultdict
            grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
            for r in rows:
                grouped[(r["machine_number"], r["module"])].append(r["raw_flag"])

            for key, flags in grouped.items():
                # flags are ordered rn ASC (most recent first)
                count = 0
                for f in flags:
                    if f == 1:
                        count += 1
                    else:
                        break
                if count > 0:
                    _MODULE_PERSISTENCE_STATE[key] = count

        _PERSISTENCE_BOOTSTRAPPED = True
    except Exception:
        # If DB is unavailable at startup, skip — will bootstrap on first inference
        pass


def extract_machine_number(machine_str: Any) -> int | None:
    """Robustly extract machine number, ignoring model prefix numbers like '9046' in 'HT9046MX'."""
    raw = str(machine_str).strip()
    m = re.search(r"(?:HT9046MX[-_]?|HT9046[-_]?|MX[-_]?|VP[-_]?|VACUUM[-_]?|HANDLER[-_ ]?)?0*(\d+)$", raw, re.IGNORECASE)
    if m:
        return int(m.group(1))
    all_nums = re.findall(r"(\d+)", raw)
    if all_nums:
        return int(all_nums[-1])
    return None


def clean_machine_code(machine_str: str) -> str:
    """Normalize any machine string to canonical 'MX080', 'MX057', etc."""
    num = extract_machine_number(machine_str)
    if num is not None:
        return f"MX{num:03d}"
    return str(machine_str).strip().upper()


def get_machine_candidates(machine_str: str) -> list[str]:
    """Generate all candidate aliases for machine code matching across databases and UI."""
    raw = str(machine_str).strip()
    num = extract_machine_number(raw)
    if num is None:
        return [raw] if raw else []
    cands = [
        raw,
        f"{num:03d}",
        str(num),
        f"MX{num:03d}",
        f"MX{num}",
        f"HT9046MX-{num:03d}",
        f"HT9046MX-{num}",
        f"HT9046-{num:03d}",
        f"HT9046-{num}",
        f"VP{num:03d}",
        f"VP{num}",
    ]
    return list(dict.fromkeys(cands))


def sync_pm_alert(
    conn,
    device_id: int,
    mod_id: int,
    severity: str,
    title: str,
    message: str,
    rec_at: datetime,
) -> bool:
    """Emit one Compressor issue per Bangkok day; honor seven-day acknowledgement.

    Unknown source timezone and historical replay fail closed. The caller's
    SQLAlchemy transaction serializes the check on the module row.
    """
    source_timezone = get_settings().source_timezone
    if not source_timezone or not isinstance(rec_at, datetime):
        return False
    source_at = rec_at if rec_at.tzinfo else rec_at.replace(tzinfo=ZoneInfo(source_timezone))
    age = (datetime.now(timezone.utc) - source_at.astimezone(timezone.utc)).total_seconds()
    if not -120 <= age <= 900:
        return False
    now = datetime.now(ZoneInfo("Asia/Bangkok")).replace(tzinfo=None)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    issue_key = "compressor_ml_condition"
    severity = str(severity).lower()
    rank = {"info": 0, "warning": 1, "critical": 2}
    # Locking the parent module also covers the no-existing-alert case.
    conn.execute(text("SELECT id FROM predictive_maintenance.pm_modules WHERE id = :m FOR UPDATE"), {"m": mod_id})
    params = {"d": device_id, "m": mod_id, "issue": issue_key, "start": day_start, "end": day_end, "now": now}
    today = conn.execute(text("""
        SELECT severity FROM predictive_maintenance.pm_alerts
        WHERE device_id = :d AND module_id = :m
          AND issue_key IN (:issue, 'diagnostic_alert')
          AND recorded_at >= :start AND recorded_at < :end
        ORDER BY recorded_at DESC, id DESC LIMIT 1 FOR UPDATE
    """), params).mappings().fetchone()
    if today and rank[severity] <= rank.get(str(today["severity"]).lower(), 0):
        return False
    acknowledged = conn.execute(text("""
        SELECT severity FROM predictive_maintenance.pm_alerts
        WHERE device_id = :d AND module_id = :m
          AND issue_key IN (:issue, 'diagnostic_alert')
          AND acknowledged = 1 AND suppressed_until > :now
        ORDER BY acknowledged_at DESC, id DESC LIMIT 1 FOR UPDATE
    """), params).mappings().fetchone()
    if acknowledged and rank[severity] <= rank.get(str(acknowledged["severity"]).lower(), 0):
        return False
    conn.execute(text("""
        INSERT INTO predictive_maintenance.pm_alerts (
            device_id, module_id, issue_key, severity, title, message, acknowledged, recorded_at
        ) VALUES (
            :d, :m, :issue, :sev, :title, :msg, 0, :rec_at
        )
    """), {
        "d": device_id,
        "m": mod_id,
        "issue": issue_key,
        "sev": severity,
        "title": title,
        "msg": message,
        "rec_at": now,
    })
    return True


def get_active_profiles_map(conn) -> dict[tuple[str, int], dict[str, Any]]:
    """Retrieve all current ACTIVE_FROZEN profiles mapped by (machine_clean, module)."""
    query = text("""
        SELECT a.machine_number, a.module, a.sv_state, a.state_code, a.active_profile_id,
               p.profile_version, p.statistics_json, p.threshold_json, p.validation_json
        FROM ht9046mx_active_calibration_profile a
        JOIN ht9046mx_calibration_profile p ON a.active_profile_id = p.profile_id
        WHERE p.profile_status = 'ACTIVE_FROZEN'
    """)
    rows = conn.execute(query).mappings().all()
    profiles_map = {}
    for r in rows:
        m_clean = clean_machine_code(str(r["machine_number"]))
        mod = int(r["module"])
        stat = json.loads(r["statistics_json"]) if r["statistics_json"] else {}
        thresh = json.loads(r["threshold_json"]) if r["threshold_json"] else {}
        profiles_map[(m_clean, mod)] = {
            "profile_id": r["active_profile_id"],
            "profile_version": r["profile_version"],
            "baseline": stat.get("detailed_baseline", {}),
            "threshold": float(thresh.get("deviation_score_q995", 3.50)),
            "sv_state": r["sv_state"],
            "state_code": r["state_code"],
        }
    return profiles_map


def ensure_pm_device_and_modules(conn, machine_code: str) -> tuple[int, dict[int, int]]:
    """Ensure pm_devices and pm_modules records exist in predictive_maintenance."""
    cands = get_machine_candidates(machine_code)
    num = extract_machine_number(machine_code)
    device_uid = f"HT9046MX-{num:03d}" if num is not None else str(machine_code).strip()

    dev_row = conn.execute(
        text("SELECT id FROM predictive_maintenance.pm_devices WHERE device_uid IN :cands OR machine_code IN :cands ORDER BY (machine_code LIKE 'HT9046MX%') DESC LIMIT 1"),
        {"cands": tuple(cands)}
    ).fetchone()

    if dev_row:
        device_id = int(dev_row[0])
    else:
        res = conn.execute(
            text("""
                INSERT INTO predictive_maintenance.pm_devices (device_uid, machine_code, display_name, status)
                VALUES (:uid, :m, :name, 'NORMAL')
            """),
            {"uid": device_uid, "m": device_uid, "name": f"Chamber {device_uid}"}
        )
        device_id = int(res.lastrowid)

    # Ensure modules 1 through 8
    existing_mods = conn.execute(
        text("SELECT id, module_code FROM predictive_maintenance.pm_modules WHERE device_id = :d"),
        {"d": device_id}
    ).mappings().all()
    mod_code_to_id = {r["module_code"]: int(r["id"]) for r in existing_mods}

    module_names = {
        1: "Index L Arm1", 2: "Index R Arm1", 3: "Index L Arm2", 4: "Index R Arm2",
        5: "SH1", 6: "SH2", 7: "Hot1", 8: "Hot2",
    }

    for m in range(1, 9):
        code = f"compressor-m{m}"
        if code not in mod_code_to_id:
            res = conn.execute(
                text("""
                    INSERT INTO predictive_maintenance.pm_modules (device_id, module_code, module_name, module_type, status, telemetry_source)
                    VALUES (:d, :code, :name, 'compressor', 'NORMAL', 'compressor')
                """),
                {"d": device_id, "code": code, "name": f"M{m} - {module_names[m]}"}
            )
            mod_code_to_id[code] = int(res.lastrowid)
        else:
            conn.execute(
                text("UPDATE predictive_maintenance.pm_modules SET telemetry_source = 'compressor' WHERE id = :id"),
                {"id": mod_code_to_id[code]}
            )

    mod_num_to_id = {m: mod_code_to_id[f"compressor-m{m}"] for m in range(1, 9)}
    return device_id, mod_num_to_id


def compute_relative_z(val: float | None, stat: dict[str, Any] | None) -> float:
    if val is None or stat is None:
        return 0.0
    med = float(stat.get("median", 0.0))
    scale = float(stat.get("scale", stat.get("std", 1.0)))
    scale_floor = float(stat.get("scale_floor", 0.15))
    effective_scale = max(scale, scale_floor, 0.05)
    return (val - med) / effective_scale


def _qualified_source_table(schema: str, table: str) -> str:
    """Build a configured MySQL identifier without interpolating unchecked input."""
    if "." in table:
        table_schema, table = table.split(".", 1)
        if table_schema != schema:
            raise ValueError("Configured source table schema differs from SOURCE_DB_NAME")
    if not re.fullmatch(r"[A-Za-z0-9_]+", schema) or not re.fullmatch(r"[A-Za-z0-9_]+", table):
        raise ValueError("Source schema/table must be simple MySQL identifiers")
    return f"`{schema}`.`{table}`"


def run_inference_and_sync(
    target_machines: list[str] | None = None,
    limit_rows_per_machine: int = 200,
    sync_to_pm: bool = True
) -> dict[str, Any]:
    """
    End-to-End Real-Time Inference Execution Engine:
    1. Reads raw telemetry from ht9046mx_iot.ht9046mx_readings.
    2. Applies active calibration profiles from ht9046mx_analytics.
    3. Calculates ML Score, Health Score (0-100), Condition State, Dominant Feature.
    4. Evaluates temporal persistence (k=3 consecutive windows).
    5. Saves results to ht9046mx_analytics.ht9046mx_shadow_score.
    6. Syncs real-time diagnostic snapshots and alerts to predictive_maintenance.
    """
    settings = get_settings()
    # The implementation below is historical raw-row scoring. Three adjacent
    # database rows are not three completed qualified one-minute windows, and
    # old minute-snapshot Active Profiles cannot be reused with observed-second
    # aggregation. Block every mutating path until a separately versioned, reviewed one-minute
    # release has passed the Server gates. The opt-in preview is read-only.
    if not settings.qualified_1m_preview_enabled:
        return {
            "status": "BLOCKED_LEGACY_RAW_ROW_SCORER",
            "message": "Qualified one-minute profile and Server release are not enabled; no score or alert was written.",
            "scored_windows": 0, "raw_flags": 0, "persistent_alerts": 0,
            "synced_diagnostics_to_pm": 0, "machines_processed": [],
        }
    if not settings.source_timezone:
        return {"status": "BLOCKED_SOURCE_TIMEZONE_UNVERIFIED", "scored_windows": 0,
                "persistent_alerts": 0, "synced_diagnostics_to_pm": 0}
    if not target_machines:
        return {"status": "TARGET_MACHINE_REQUIRED_FOR_READ_ONLY_PREVIEW", "scored_windows": 0,
                "persistent_alerts": 0, "synced_diagnostics_to_pm": 0}
    from .qualified_shadow_preview import run_read_only_preview
    now = datetime.now(timezone.utc)
    previews = [run_read_only_preview(settings, machine_number=machine,
                                      start=now - timedelta(minutes=30), end=now)
                for machine in target_machines]
    return {
        "status": "READ_ONLY_QUALIFIED_1M_PREVIEW",
        "previews": previews,
        "scored_windows": sum(item["scored_module_windows"] for item in previews),
        "raw_flags": sum(item["primary_raw_flags"] for item in previews),
        "persistent_alerts": 0,
        "synced_diagnostics_to_pm": 0,
        "machines_processed": target_machines,
        "message": "Preview only; no primary/temporal score, episode, Health or PM Alert was persisted.",
    }

    # Historical implementation retained temporarily for audit/rollback
    # comparison. It is unreachable via the public function above.
    source_table = _qualified_source_table(settings.source_db_name, settings.source_table)
    health_table = _qualified_source_table(settings.source_db_name, "compressor_health_scores")
    now_utc = datetime.now(timezone.utc)
    bootstrap_persistence_state()

    with connection() as conn:
        profiles_map = get_active_profiles_map(conn)
    if not profiles_map:
        return {"status": "NO_ACTIVE_PROFILES", "message": "No ACTIVE_FROZEN profiles found in MySQL."}

    # Determine target machines
    if target_machines:
        machines = target_machines
    else:
        machines = sorted(list({k[0] for k in profiles_map.keys()}))

    total_scored_windows = 0
    total_raw_flags = 0
    total_persistent_alerts = 0
    synced_diagnostics = 0

    for machine_str in machines:
        m_clean = clean_machine_code(machine_str)
        cands = get_machine_candidates(machine_str)

        with connection() as conn:

            # Query recent telemetry using all candidate machine aliases (e.g. 'MX057', '057', '57')
            query = text(f"""
                SELECT * FROM {source_table}
                WHERE machine_number IN :cands
                ORDER BY recorded_at DESC
                LIMIT :limit
            """)
            raw_rows = conn.execute(query, {
                "cands": tuple(cands),
                "limit": limit_rows_per_machine
            }).mappings().all()

            if not raw_rows:
                continue

            # Process in chronological order
            raw_rows = list(reversed(raw_rows))
            scored_rows = conn.execute(text("""
                SELECT module, profile_version, MAX(event_time) AS latest_event_time
                FROM ht9046mx_shadow_score
                WHERE machine_number = :machine
                GROUP BY module, profile_version
            """), {"machine": m_clean}).mappings().all()
            score_watermarks = {
                (int(scored["module"]), str(scored["profile_version"])): scored["latest_event_time"]
                for scored in scored_rows
            }

            device_id = None
            mod_ids: dict[int, int] = {}
            if sync_to_pm:
                try:
                    device_id, mod_ids = ensure_pm_device_and_modules(conn, m_clean)
                except Exception as e:
                    print(f"Warning: could not prepare predictive_maintenance device for {m_clean}: {e}")
                    sync_to_pm = False

            latest_mod_status: dict[int, str] = {}
            worst_condition_for_machine = "NORMAL"
            severity_rank = {"NORMAL": 0, "WATCH": 1, "WARNING": 2, "MAINTENANCE_REQUIRED": 3}

            # Batch accumulators: collect rows for bulk INSERT at end of machine
            _score_batch: list[dict] = []
            _diag_batch: list[dict] = []
            _health_batch: list[dict] = []
            latest_alert_candidates: dict[int, tuple[str, str, str, datetime]] = {}

            for row in raw_rows:
                rec_at = row["recorded_at"]
                global_status = str(row.get("Status", "Run"))

                for mod_num in range(1, 9):
                    prof = profiles_map.get((m_clean, mod_num))
                    if not prof:
                        continue
                    if rec_at <= score_watermarks.get((mod_num, prof["profile_version"]), datetime.min):
                        continue

                    # Extract sensor tags for module mod_num
                    hp1 = row.get(f"Hp_1st_{mod_num}")
                    lp1 = row.get(f"Lp_1st_{mod_num}")
                    hp2 = row.get(f"Hp_2nd_{mod_num}")
                    lp2 = row.get(f"Lp_2nd_{mod_num}")
                    valve = row.get(f"Valve_{mod_num}")
                    temphi = row.get(f"TempHi_{mod_num}")
                    templo = row.get(f"TempLo_{mod_num}")
                    status_m = str(row.get(f"Status_{mod_num}") or global_status)
                    busy_m = str(row.get(f"Busy_{mod_num}", "0"))
                    sv_m = str(row.get(f"SV_{mod_num}", "Off"))

                    # If all pressure sensors are null for this module, skip
                    if hp1 is None and hp2 is None:
                        continue

                    # Operational State Gate: Cold Run with SV Off and Busy = 0
                    is_run = status_m in ("On", "Run", "1", "True") and global_status in ("Run", "On", "1", "True")
                    is_sv_off = sv_m in ("Off", "0", "False")
                    is_not_busy = busy_m in ("0", "False", "Off", "")

                    baseline = prof["baseline"]
                    threshold = prof["threshold"]

                    if is_run and is_sv_off and is_not_busy:
                        data_quality = "VALID"
                        state_code = "COMPRESSOR_ON_COLD_SV_OFF"

                        dp1 = (hp1 - lp1) if (hp1 is not None and lp1 is not None) else None
                        dp2 = (hp2 - lp2) if (hp2 is not None and lp2 is not None) else None

                        # Calculate relative Z for all features
                        z_scores = {
                            "hp1": compute_relative_z(hp1, baseline.get("hp1")),
                            "lp1": compute_relative_z(lp1, baseline.get("lp1")),
                            "hp2": compute_relative_z(hp2, baseline.get("hp2")),
                            "lp2": compute_relative_z(lp2, baseline.get("lp2")),
                            "dp1": compute_relative_z(dp1, baseline.get("dp1")),
                            "dp2": compute_relative_z(dp2, baseline.get("dp2")),
                            "valve": compute_relative_z(valve, baseline.get("valve")),
                            "temphi": compute_relative_z(temphi, baseline.get("temphi")),
                            "templo": compute_relative_z(templo, baseline.get("templo")),
                        }

                        # Anomaly Score = maximum absolute deviation
                        abs_z = {k: abs(v) for k, v in z_scores.items()}
                        dominant_feat = max(abs_z, key=abs_z.get)
                        ml_score = round(abs_z[dominant_feat], 3)
                        raw_flag = 1 if ml_score > threshold else 0

                        # Persistence tracking across windows using global module state
                        p_key = (m_clean, mod_num)
                        if raw_flag == 1:
                            _MODULE_PERSISTENCE_STATE[p_key] = _MODULE_PERSISTENCE_STATE.get(p_key, 0) + 1
                        else:
                            _MODULE_PERSISTENCE_STATE[p_key] = 0

                        persistent_count = _MODULE_PERSISTENCE_STATE[p_key]
                        persistent_flag = 1 if persistent_count >= 3 else 0

                        # Compute Health Score (0 - 100%)
                        if ml_score <= threshold:
                            health_score = int(round(100 - (ml_score / threshold) * 35))
                        elif not persistent_flag:
                            health_score = int(round(65 - min(20.0, (ml_score - threshold) * 10)))
                        else:
                            health_score = int(round(max(15.0, 45.0 - (ml_score - threshold) * 15)))

                        # Condition State classification
                        if health_score >= 75:
                            cond_state = "NORMAL"
                            ai_notes = f"All stages operational within baseline envelope (Hp2={hp2:.1f} psi, dom_dev={ml_score:.2f}σ)"
                        elif health_score >= 60:
                            cond_state = "WATCH"
                            ai_notes = f"Mild deviation observed on {dominant_feat} (z={z_scores[dominant_feat]:.2f}σ)"
                        elif not persistent_flag:
                            cond_state = "WARNING"
                            ai_notes = f"Spike deviation exceeded threshold {threshold:.2f}σ on {dominant_feat} (z={z_scores[dominant_feat]:.2f}σ)"
                        else:
                            cond_state = "MAINTENANCE_REQUIRED"
                            ai_notes = f"PERSISTENT ANOMALY (3+ cycles): Severe deviation on {dominant_feat} (z={z_scores[dominant_feat]:.2f}σ)"
                    else:
                        data_quality = "TRANSIENT_SUPPRESSED" if not is_run else "BYPASS_SV_ON"
                        state_code = "CONTROL_TRANSIENT_SUPPRESSED" if not is_run else "HISTORICAL_BYPASS_SV_ON"
                        ml_score = 0.0
                        raw_flag = 0
                        persistent_flag = 0
                        health_score = 90
                        cond_state = "NORMAL"
                        dominant_feat = "none"
                        ai_notes = f"Non-cold operating state ({status_m}, SV={sv_m}, Busy={busy_m}); deviation suppressed."
                        z_scores = {}

                    evidence = {
                        "scoring_method": RUNTIME_SCORER_VERSION,
                        "dominant_feature": dominant_feat,
                        "health_score": health_score,
                        "condition_state": cond_state,
                        "ml_score": ml_score,
                        "threshold": threshold,
                        "raw_flag": raw_flag,
                        "persistent_flag": persistent_flag,
                        "z_scores": z_scores,
                        "sensors": {
                            "hp1": hp1, "lp1": lp1, "hp2": hp2, "lp2": lp2,
                            "valve": valve, "temphi": temphi, "templo": templo
                        }
                    }

                    # 1. Accumulate shadow_score for batch INSERT (executed after row loop)
                    _score_batch.append({
                        "machine": m_clean,
                        "module": mod_num,
                        "event_time": rec_at,
                        "state_code": state_code,
                        "sv_state": sv_m,
                        "data_quality": data_quality,
                        "score": ml_score,
                        "threshold": threshold,
                        "raw_flag": raw_flag,
                        "persistent_flag": persistent_flag,
                        "profile_version": prof["profile_version"],
                        "model_version": RUNTIME_SCORER_VERSION,
                        "feature_version": RUNTIME_FEATURE_VERSION,
                        "threshold_version": RUNTIME_THRESHOLD_VERSION,
                        "evidence": json.dumps(evidence)
                    })
                    total_scored_windows += 1
                    if raw_flag == 1:
                        total_raw_flags += 1

                    # 2. Maintain ht9046mx_analytics.ht9046mx_shadow_alert_episode (Consolidated continuous episode per event)
                    if persistent_flag == 1:
                        # Check if an OPEN episode is already active for this machine/module
                        open_ep = conn.execute(text("""
                            SELECT alert_id FROM ht9046mx_shadow_alert_episode
                            WHERE machine_number = :machine AND module = :module AND alert_status = 'OPEN'
                            ORDER BY alert_id DESC LIMIT 1
                        """), {"machine": m_clean, "module": mod_num}).mappings().first()

                        if open_ep:
                            # Auto-extend the ongoing episode
                            conn.execute(text("""
                                UPDATE ht9046mx_shadow_alert_episode
                                SET last_observed_at = :last, evidence_json = :evidence
                                WHERE alert_id = :aid
                            """), {
                                "last": rec_at,
                                "evidence": json.dumps(evidence),
                                "aid": open_ep["alert_id"]
                            })
                        elif persistent_count >= 3:
                            # Fresh episode onset: create exactly one continuous episode record
                            total_persistent_alerts += 1
                            conn.execute(text("""
                                INSERT INTO ht9046mx_shadow_alert_episode (
                                    machine_number, module, episode_start, detected_at,
                                    last_observed_at, alert_status, severity, claim_level,
                                    release_version, evidence_json
                                ) VALUES (
                                    :machine, :module, :start, :detected,
                                    :last, 'OPEN', 'CRITICAL', 'PERSISTENT_PATTERN',
                                    :release, :evidence
                                )
                                ON DUPLICATE KEY UPDATE
                                    last_observed_at = GREATEST(last_observed_at, VALUES(last_observed_at)),
                                    evidence_json = VALUES(evidence_json)
                            """), {
                                "machine": m_clean,
                                "module": mod_num,
                                "start": rec_at - timedelta(minutes=15),
                                "detected": rec_at,
                                "last": rec_at,
                                "release": prof["profile_version"],
                                "evidence": json.dumps(evidence)
                            })
                    elif raw_flag == 0:
                        # Anomaly condition has cleared -> auto-resolve open episodes
                        conn.execute(text("""
                            UPDATE ht9046mx_shadow_alert_episode
                            SET alert_status = 'RESOLVED', last_observed_at = :last
                            WHERE machine_number = :machine AND module = :module AND alert_status = 'OPEN'
                        """), {
                            "machine": m_clean,
                            "module": mod_num,
                            "last": rec_at
                        })

                    # 3. Accumulate PM sync rows for batch INSERT (executed after row loop)
                    _health_batch.append({
                        "mach": m_clean,
                        "mod": f"compressor-m{mod_num}",
                        "rec_at": rec_at,
                        "health": float(health_score),
                        "cond": cond_state,
                        "model_version": f"{RUNTIME_SCORER_VERSION}|{prof['profile_version']}",
                    })
                    if sync_to_pm and device_id and mod_num in mod_ids:
                        mod_id = mod_ids[mod_num]
                        _diag_batch.append({
                            "dev_id": device_id,
                            "mod_id": mod_id,
                            "rec_at": rec_at,
                            "health": health_score,
                            "cond": cond_state,
                            "temp": temphi if temphi is not None else 0.0,
                            "press": hp2 if hp2 is not None else 0.0,
                            "model_version": RUNTIME_SCORER_VERSION,
                            "ai_cond": f"Deviation {dominant_feat}" if raw_flag else "Normal Operation",
                            "notes": ai_notes
                        })
                        synced_diagnostics += 1
                        latest_mod_status[mod_id] = cond_state

                        # Defer Alert sync until the latest row for each module is known.
                        # This avoids one metadata query/lock per scored sensor row.
                        if persistent_flag == 1:
                            alert_title = f"{m_clean} Module {mod_num}: Repair Now (Critical Deviation)"
                            latest_alert_candidates[mod_id] = ("critical", alert_title, ai_notes, rec_at)
                        elif cond_state == "WARNING":
                            alert_title = f"{m_clean} Module {mod_num}: Parameter Warning (Pre-Fault Deviation)"
                            latest_alert_candidates[mod_id] = ("warning", alert_title, ai_notes, rec_at)
                        else:
                            latest_alert_candidates.pop(mod_id, None)

                        # Track worst condition for device
                        if severity_rank.get(cond_state, 0) > severity_rank.get(worst_condition_for_machine, 0):
                            worst_condition_for_machine = cond_state

            for mod_id, (severity, alert_title, alert_message, alert_at) in latest_alert_candidates.items():
                if sync_pm_alert(conn, device_id, mod_id, severity, alert_title, alert_message, alert_at):
                    total_persistent_alerts += 1

            # === BATCH FLUSH: Execute accumulated INSERTs in bulk ===
            if _score_batch:
                conn.execute(text("""
                    INSERT INTO ht9046mx_shadow_score (
                        machine_number, module, event_time, source_timezone,
                        state_code, sv_state, data_quality_status, anomaly_score,
                        threshold_value, raw_flag, persistent_flag, model_version,
                        profile_version, feature_version, threshold_version,
                        replay_version, evidence_json
                    ) VALUES (
                        :machine, :module, :event_time, 'Asia/Bangkok',
                        :state_code, :sv_state, :data_quality, :score,
                        :threshold, :raw_flag, :persistent_flag, :model_version,
                        :profile_version, :feature_version, :threshold_version,
                        'production-inference-v2-provenance', :evidence
                    )
                    ON DUPLICATE KEY UPDATE
                        anomaly_score = VALUES(anomaly_score),
                        threshold_value = VALUES(threshold_value),
                        raw_flag = VALUES(raw_flag),
                        persistent_flag = VALUES(persistent_flag),
                        evidence_json = VALUES(evidence_json)
                """), _score_batch)

            if _diag_batch:
                conn.execute(text("""
                    INSERT INTO predictive_maintenance.pm_diagnostic_snapshots (
                        device_id, module_id, recorded_at, sample_count,
                        health_score, condition_state, temperature_c,
                        pressure_kpa, ai_model_version, ai_condition,
                        ai_confidence, ai_notes
                    ) VALUES (
                        :dev_id, :mod_id, :rec_at, 60,
                        :health, :cond, :temp,
                        :press, :model_version, :ai_cond,
                        0.95, :notes
                    )
                """), _diag_batch)

            if _health_batch:
                conn.execute(text(f"""
                    INSERT INTO {health_table} (
                        machine_number, module_id, recorded_at, health_score, `condition`, model_version
                    )
                    SELECT :mach, :mod, :rec_at, :health, :cond, :model_version
                    FROM DUAL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {health_table}
                        WHERE machine_number = :mach AND module_id = :mod
                          AND recorded_at = :rec_at AND model_version = :model_version
                    )
                """), _health_batch)

            # Batch update pm_modules status at end of loop (avoiding lock contention on every row)
            if sync_to_pm and mod_ids:
                for m_id, m_stat in latest_mod_status.items():
                    conn.execute(text("""
                        UPDATE predictive_maintenance.pm_modules
                        SET status = :cond
                        WHERE id = :mod_id
                    """), {"cond": m_stat, "mod_id": m_id})

            # Update pm_devices overall status based on latest status of active modules
            if sync_to_pm and device_id:
                current_device_status = max(
                    (m_stat for m_stat in latest_mod_status.values()),
                    key=lambda s: severity_rank.get(s, 0),
                    default="NORMAL"
                )
                conn.execute(text("""
                    UPDATE predictive_maintenance.pm_devices
                    SET status = :stat, last_seen = :now
                    WHERE id = :dev_id
                """), {"stat": current_device_status, "now": now_utc, "dev_id": device_id})

    return {
        "status": "COMPLETED",
        "scored_windows": total_scored_windows,
        "raw_flags": total_raw_flags,
        "persistent_alerts": total_persistent_alerts,
        "synced_diagnostics_to_pm": synced_diagnostics,
        "machines_processed": machines,
    }


if __name__ == "__main__":
    import sys
    print("=== Running End-to-End Real-Time Inference & Synchronization ===")
    result = run_inference_and_sync(limit_rows_per_machine=300, sync_to_pm=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # A scheduled command must not report success merely because a guarded
    # no-write path returned a JSON response. This CLI is not the preview CLI.
    if result.get("status") != "COMPLETED":
        sys.exit(2)
