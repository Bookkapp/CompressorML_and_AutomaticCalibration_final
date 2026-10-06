"""Bounded SELECT-only source-day inventory, not a healthy/qualified-day selector.

Suggestions use coverage only, never values, anomaly scores or Shadow outcomes.
Exact observed-second qualification remains in the asynchronous Preview.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from .calibration import _latest_source_time
from .config import Settings
from .db import source_connection
from .inference import _qualified_source_table, get_machine_candidates
from .qualified_calibration import IDENTIFIER
from .reference_review import ReferencePreviewRequest, resolve_selection


def summarize_availability(payload: ReferencePreviewRequest, latest: datetime, daily: list[dict],
                           settings: Settings, *, now: datetime | None = None) -> dict:
    selection = resolve_selection(payload, latest, settings)
    cutoff = datetime.fromisoformat(selection["latest_complete_end"])
    first = cutoff - timedelta(days=93)
    by_day = {str(row["date"]): row for row in daily}
    rows = []
    cursor = first
    while cursor.date() <= datetime.fromisoformat(selection["source_latest"]).date():
        row = by_day.get(cursor.date().isoformat(), {})
        rows.append({"date": cursor.date().isoformat(), "raw_rows": int(row.get("raw_rows", 0)),
            "module_rows": int(row.get("module_rows", 0)),
            "observed_minutes": int(row.get("observed_minutes", 0)),
            "module_minutes": int(row.get("module_minutes", 0)),
            "complete_day": cursor < cutoff})
        cursor += timedelta(days=1)

    def period(end: datetime):
        shadow_start = end - timedelta(days=3)
        ref_start = shadow_start - timedelta(days=payload.history_days)
        ref = [r for r in rows if ref_start.date().isoformat() <= r["date"] < shadow_start.date().isoformat()]
        shadow = [r for r in rows if shadow_start.date().isoformat() <= r["date"] < end.date().isoformat()]
        return {"reference_start": ref_start.date().isoformat(), "reference_end": shadow_start.date().isoformat(),
            "shadow_start": shadow_start.date().isoformat(), "shadow_end": end.date().isoformat(),
            "reference_observed_days": sum(r["module_rows"] > 0 for r in ref),
            "reference_raw_days": sum(r["raw_rows"] > 0 for r in ref),
            "reference_observed_minutes": sum(r["module_minutes"] for r in ref),
            "shadow_observed_days": sum(r["module_rows"] > 0 for r in shadow),
            "shadow_raw_days": sum(r["raw_rows"] > 0 for r in shadow),
            "shadow_observed_minutes": sum(r["module_minutes"] for r in shadow),
            "shadow_missing_dates": [r["date"] for r in shadow if not r["module_rows"]],
            "shadow_no_log_dates": [r["date"] for r in shadow if not r["raw_rows"]],
            "shadow_missing_sensor_dates": [r["date"] for r in shadow if r["raw_rows"] and not r["module_rows"]]}

    default = period(cutoff)
    suggested = None
    # A suggestion must have three adjacent populated calendar days AND enough
    # observed Reference days/minutes. These are necessary, not sufficient,
    # conditions: minute-grain telemetry can still fail the second-level gate.
    for back in range(91):
        end = cutoff - timedelta(days=back)
        if end - timedelta(days=3 + payload.history_days) < first:
            break
        p = period(end)
        if (p["shadow_observed_days"] == 3
            and p["shadow_observed_minutes"] >= settings.profile_min_shadow_windows
            and p["reference_observed_days"] >= settings.profile_min_calibration_days
            and p["reference_observed_minutes"] >= settings.profile_min_calibration_windows):
            suggested = {**p, "backtrack_days": back}
            break
    module_latest = next((r["date"] for r in reversed(rows) if r["module_rows"]), None)
    local_latest = datetime.fromisoformat(selection["source_latest"])
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings.source_timezone)).replace(tzinfo=None)
    return {"machine_number": payload.machine_number, "module": payload.module,
        "source_timezone": settings.source_timezone, "source_latest": selection["source_latest"],
        "module_latest_date": module_latest, "latest_complete_end": cutoff.date().isoformat(),
        "checked_start": first.date().isoformat(), "source_age_days": (current - local_latest).total_seconds()/86400,
        "default_period": default, "suggested_period": suggested, "daily": rows,
        "min_reference_days": settings.profile_min_calibration_days,
        "min_reference_minutes": settings.profile_min_calibration_windows,
        "min_shadow_minutes": settings.profile_min_shadow_windows,
        "inventory_grain": "observed source minutes with all seven module sensors non-null; NOT qualified Cold minutes",
        "limitations": ["Coverage-only suggestion; no health label or approval", "Preview must check actual seconds, duplicates, gaps and state", "Search is bounded to 93 closed calendar days"]}


def source_availability(settings: Settings, *, machine_number: str, module: int, history_days: int = 28) -> dict:
    payload = ReferencePreviewRequest(idempotency_key="read-only-availability", machine_number=machine_number,
        module=module, history_days=history_days)
    latest = _latest_source_time(settings, payload.machine_number)
    if latest is None:
        return {"machine_number": payload.machine_number, "module": module, "source_latest": None,
                "suggested_period": None, "daily": [], "reason": "NO_SOURCE_DATA"}
    selection = resolve_selection(payload, latest, settings)
    end = datetime.fromisoformat(selection["source_latest"])
    start = datetime.fromisoformat(selection["latest_complete_end"]) - timedelta(days=93)
    fields = [template.format(module=module) for template in (
        settings.source_hp1_template, settings.source_lp1_template, settings.source_hp2_template,
        settings.source_lp2_template, settings.source_valve_template,
        settings.source_temp_high_template, settings.source_temp_low_template)]
    machine_col, time_col = settings.source_machine_column, settings.source_timestamp_column
    if not all(IDENTIFIER.fullmatch(c) for c in [machine_col, time_col, *fields]):
        raise ValueError("Unsafe source mapping")
    table = _qualified_source_table(settings.source_db_name, settings.source_table)
    present = " AND ".join(f"`{c}` IS NOT NULL" for c in fields)
    # Large 93-day ranges can make MySQL choose a full-table scan/filesort.
    # Bounded daily ranges reuse the existing machine/time index; keeping one
    # connection/transaction gives one consistent source snapshot. All aliases
    # remain combined. Inside a single calendar day, integer minute-of-day is
    # equivalent to the old distinct DATE_FORMAT string without string sorting.
    minute = f"(HOUR(`{time_col}`)*60+MINUTE(`{time_col}`))"
    query = text(f"SELECT COUNT(*) AS raw_rows, "
        f"COALESCE(SUM(CASE WHEN {present} THEN 1 ELSE 0 END),0) AS module_rows, "
        f"COUNT(DISTINCT {minute}) AS observed_minutes, "
        f"COUNT(DISTINCT CASE WHEN {present} THEN {minute} ELSE NULL END) AS module_minutes "
        f"FROM {table} WHERE `{machine_col}` IN :machines AND `{time_col}` >= :start "
        f"AND `{time_col}` < :day_end AND `{time_col}` <= :end").bindparams(bindparam("machines", expanding=True))
    daily = []
    with source_connection() as conn:
        cursor = start
        while cursor <= end:
            next_day = cursor + timedelta(days=1)
            row = conn.execute(query, {"machines": get_machine_candidates(payload.machine_number),
                "start": cursor, "day_end": next_day, "end": end}).mappings().one()
            daily.append({**dict(row), "date":cursor.date().isoformat()})
            cursor = next_day
    return summarize_availability(payload, latest, daily, settings)
