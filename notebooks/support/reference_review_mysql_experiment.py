"""Local experiment: actual configured MySQL SELECT, isolated reference jobs.

No archive adapter, fixture insertion, Active approval, scheduler or PM bridge.
Source timestamps/units remain exactly as configured, including unknown units.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import math
import os
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, event, text, bindparam
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "ht9046mx_reference_mysql_experiment_20261002"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
KNOWN_FIXTURES = {"001", "100", "111", "777"}


def is_experiment_write(method: str, path: str) -> bool:
    return method == "POST" and (path == "/api/v1/calibration/reference/preview" or
        re.fullmatch(r"/api/v1/calibration/reference/jobs/[0-9a-f-]{36}/build", path) is not None)


def select_only(conn, cursor, statement, parameters, context, executemany):
    if not statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "EXPLAIN ")):
        raise RuntimeError("Experimental source connection permits SELECT/SHOW/EXPLAIN only")


def setup():
    from apps.api.app.config import get_settings
    original = get_settings()
    if not original.database_url or not original.source_database_url:
        raise RuntimeError("Both configured MySQL connections are required")
    if any(make_url(url).host not in LOCAL_HOSTS for url in
           (original.database_url, original.source_database_url)):
        raise RuntimeError("This experiment runner is localhost-only; it never probes the target Server")
    admin = create_engine(original.database_url, pool_pre_ping=True)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{SCHEMA}`"))
    admin.dispose()
    settings = original.model_copy(update={"analytics_db_name": SCHEMA, "app_mode": "live",
        "profile_candidate_enabled": False, "detector_worker_enabled": False,
        "detector_bridge_enabled": False, "detector_alerts_enabled": False})
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    for name in ("mysql_phase6_calibration_registry.sql", "mysql_reference_review.sql"):
        sql = (ROOT / "deployment" / name).read_text(encoding="utf-8")
        sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        with engine.begin() as conn:
            for statement in sql.split(";"):
                if statement.strip():
                    conn.execute(text(statement))
    # Read-only session plus a SQL statement guard; no source writer is installed.
    source_engine = create_engine(settings.source_database_url, pool_pre_ping=True,
        connect_args={"init_command": "SET SESSION TRANSACTION READ ONLY"})
    event.listen(source_engine, "before_cursor_execute", select_only)
    from apps.api.app import db, main, reference_jobs as jobs, repository
    from apps.api.app.inference import _qualified_source_table, get_machine_candidates
    from apps.api.app.qualified_calibration import IDENTIFIER, policy_from_settings
    from apps.api.app.qualified_windows import build_completed_windows
    db._engine = engine
    db._source_engine = source_engine
    db.get_settings = lambda: settings
    jobs.get_settings = lambda: settings
    main.get_settings = lambda: settings
    main.settings = settings
    repository.get_settings = lambda: settings
    # Keep the REAL latest-time query and observed-second source loader unchanged.
    class ExperimentRepository(repository.AnalyticsRepository):
        def source_machines(self):
            return [{"machine_number": r["machine_number"], "display_name": str(r["machine_number"]) +
                (" · MOCK" if r["origin"] == "known local fixture" else " · local SQL"),
                "record_count": r["record_count"], "latest_recorded_at": r["last_time"]}
                for r in source_context()["machines"]]
        def incidents(self, *a, **k): return []
        def automation_runs(self, *a, **k): return []
        def fleet_machines(self, *a, **k): return []
    main.source = lambda: ExperimentRepository()
    main.is_demo = lambda: False
    from fastapi import HTTPException, Query
    from fastapi.responses import JSONResponse
    @main.app.middleware("http")
    async def experimental_boundary(request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS") and not is_experiment_write(request.method, request.url.path):
            return JSONResponse(status_code=409, content={"detail": "MySQL experiment: only isolated Reference preview/build writes; no approval, alerts or feedback"})
        return await call_next(request)
    main.app.router.routes = [r for r in main.app.router.routes if getattr(r, "path", None) != "/api/v1/fleet/summary"]
    @main.app.get("/api/v1/fleet/summary")
    def fleet():
        return {"mode": "LOCAL_MYSQL_EXPERIMENT", "release_state": "EXPERIMENT_NO_ACTIVATION",
            "configured_machines": 0, "scored_machines": 0, "open_incidents": 0, "data_quality_issues": 0,
            "condition_index_available": False, "dashboard_refresh_minutes": 5,
            "scoring_interval_minutes": 1, "cadence_gate": "ACTUAL_SQL_REVIEW_ONLY", "machines": []}

    table = _qualified_source_table(settings.source_db_name, settings.source_table)
    identifiers = (settings.source_machine_column, settings.source_timestamp_column, settings.source_global_status_column)
    if not all(IDENTIFIER.fullmatch(item) for item in identifiers):
        raise RuntimeError("Invalid configured source columns")
    machine_col, time_col, status_col = identifiers
    @main.app.get("/api/v1/experiment/source-context")
    def source_context():
        with source_engine.connect() as conn:
            inventory = [dict(r) for r in conn.execute(text(
                f"SELECT `{machine_col}` AS machine_number,COUNT(*) AS record_count,"
                f"MIN(`{time_col}`) AS first_time,MAX(`{time_col}`) AS last_time FROM {table} "
                f"GROUP BY `{machine_col}` ORDER BY `{machine_col}`")).mappings()]
        for item in inventory:
            key = str(item["machine_number"]).upper().removeprefix("MX").zfill(3)
            item["origin"] = "known local fixture" if key in KNOWN_FIXTURES else "local source; historical/imported or unverified additions"
        return {"mode": "LOCAL_MYSQL_EXPERIMENT", "host": settings.source_db_host,
            "schema": settings.source_db_name, "table": settings.source_table,
            "timezone": settings.source_timezone, "pressure_unit": settings.source_pressure_unit or "source unit (unverified)",
            "experimental_schema": SCHEMA, "normal_analytics_schema": original.analytics_db_name,
            "read_at_utc": datetime.now(timezone.utc).isoformat(), "machines": inventory,
            "source_read_only": True, "active_approval_enabled": False, "alerts_enabled": False}

    @main.app.get("/api/v1/experiment/source-day")
    def source_day(machine: str = Query("MX080", min_length=1, max_length=64),
                   module: int = Query(6, ge=1, le=8), day: date = Query(date(2026, 9, 7))):
        start, end = datetime.combine(day, datetime.min.time()), datetime.combine(day + timedelta(days=1), datetime.min.time())
        templates = {"hp1": settings.source_hp1_template, "lp1": settings.source_lp1_template,
            "hp2": settings.source_hp2_template, "lp2": settings.source_lp2_template,
            "valve": settings.source_valve_template, "temphi": settings.source_temp_high_template,
            "templo": settings.source_temp_low_template, "module_status": settings.source_module_status_template,
            "busy": settings.source_busy_template, "sv": settings.source_sv_template}
        mapped = {name: template.format(module=module) for name, template in templates.items()}
        if not all(IDENTIFIER.fullmatch(column) for column in mapped.values()):
            raise HTTPException(503, "Invalid source mapping")
        select = ",".join([f"`{time_col}` AS stamp", f"`{machine_col}` AS machine_number",
            f"`{status_col}` AS compressor_status", *(f"`{col}` AS `{name}`" for name, col in mapped.items())])
        query = text(f"SELECT {select} FROM {table} WHERE `{machine_col}` IN :machines "
            f"AND `{time_col}`>=:start AND `{time_col}`<:end ORDER BY `{time_col}` LIMIT 100001").bindparams(bindparam("machines", expanding=True))
        with source_engine.connect() as conn:
            records = [dict(r) for r in conn.execute(query, {"machines": get_machine_candidates(machine), "start": start, "end": end}).mappings()]
        if len(records) > 100000:
            raise HTTPException(409, "Day exceeds experimental 100,000-row bound; inspect source duplicates/grain")
        numeric = ("hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo")
        points = []
        positive_gaps = np.array([])
        duplicate_times = 0
        if records:
            frame = pd.DataFrame(records)
            stamps = pd.to_datetime(frame.stamp)
            duplicate_times = int(stamps.duplicated(keep=False).sum())
            gaps = stamps.sort_values().diff().dt.total_seconds().dropna().to_numpy()
            positive_gaps = gaps[gaps > 0]
            frame["minute"] = stamps.dt.floor("min")
            for name in numeric:
                frame[name] = pd.to_numeric(frame[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
            means = frame.groupby("minute")[list(numeric)].mean()
            counts = frame.groupby("minute").size()
            for stamp in pd.date_range(start, end - timedelta(minutes=1), freq="min"):
                values = {name: float(means.at[stamp, name]) if stamp in means.index and pd.notna(means.at[stamp, name]) else None for name in numeric}
                points.append({"stamp": stamp.isoformat(), "observations": int(counts.get(stamp, 0)), **values})
        # Apply the SAME strict builder to the actual selected day's rows, without relaxing cadence.
        from apps.api.app.inference import clean_machine_code
        from zoneinfo import ZoneInfo
        raw = [{"recorded_at": r["stamp"], "machine_number": clean_machine_code(r["machine_number"]),
            "Status": r["compressor_status"], **{mapped[k]: r[k] for k in mapped}} for r in records]
        windows = build_completed_windows(raw, as_of=(end + timedelta(minutes=1)).replace(tzinfo=ZoneInfo(settings.source_timezone)),
            policy=policy_from_settings(settings), modules=(module,),
            source_fields={name: template for name, template in templates.items() if name in numeric},
            module_status_template=settings.source_module_status_template, busy_template=settings.source_busy_template,
            sv_template=settings.source_sv_template)
        reasons = Counter(w.reason or "PASS" for w in windows)
        def safe_record(r):
            return {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in r.items()}
        return {"machine": machine, "module": module, "day": day.isoformat(), "start": start, "end_exclusive": end,
            "rows": len(records), "duplicate_timestamp_rows": duplicate_times,
            "median_positive_interval_seconds": float(np.median(positive_gaps)) if len(positive_gaps) else None,
            "occupied_minutes": len({r["stamp"].replace(second=0, microsecond=0) for r in records}),
            "strict_qualified_minutes": sum(w.features is not None for w in windows), "gate_reasons": dict(reasons),
            "chart_grain": "one-minute mean of observed SQL rows; NOT reconstructed seconds, NOT qualified profile features",
            "points": points, "raw_preview": [safe_record(r) for r in records[:10]]}
    return main.app, engine


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8178)
    args = parser.parse_args()
    os.environ["HT9046MX_API_CORS_ORIGINS"] = "http://127.0.0.1:5175,http://localhost:5175"
    app, _ = setup()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port)
