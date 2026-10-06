"""Local MySQL transaction/transport test on archived MX080 seconds.

Only ht9046mx_rehearsal_* tables are written. No profile promotion/PM alert.
"""
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from time import perf_counter
from uuid import uuid4

import pandas as pd
from sqlalchemy import BigInteger, Column, String, Table, Text, create_engine, select

from apps.api.app.config import Settings
from apps.api.app.qualified_persistence import PersistentRehearsal, canonical, metadata, runs
from apps.api.app.qualified_scoring import QualifiedShadowScorer
from apps.api.app.qualified_stream import CompletedMinuteStream
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows
from notebooks.support.case_incremental_replay import ZONE, rows080, candidate


inputs = Table("ht9046mx_rehearsal_input", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("ingestion_id", BigInteger, primary_key=True),
    Column("payload_json", Text, nullable=False))


def run():
    settings = Settings(_env_file="apps/api/.env")
    if settings.analytics_db_host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("This rehearsal targets localhost only")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    store = PersistentRehearsal(engine)
    store.create_tables()
    policy = WindowPolicy("Asia/Bangkok", late_arrival_seconds=30)
    calibration = []
    for day in pd.date_range("2026-09-03", "2026-09-06"):
        start = day.to_pydatetime()
        calibration += build_completed_windows(rows080(start, start+timedelta(days=1)),
            as_of=(start+timedelta(days=1)).replace(tzinfo=ZONE),
            policy=WindowPolicy("Asia/Bangkok"), modules=(6,))
    _, profile = candidate(calibration, "MX080", 6, datetime(2026,9,3),
                           datetime(2026,9,7), datetime(2026,9,8))
    profiles = {("MX080", 6): profile}
    start, end = datetime(2026,9,7,11,45), datetime(2026,9,7,13)
    raw = list(rows080(start, end))
    run_id = "mx080-m6-" + uuid4().hex[:12]
    store.initialize(run_id, CompletedMinuteStream(policy, (6,)), profiles)
    # Archived source copy is intentionally separate from live telemetry.
    with engine.begin() as conn:
        conn.execute(inputs.insert(), [{"run_id": run_id, "ingestion_id": i+1,
            "payload_json": canonical(row)} for i, row in enumerate(raw)])
    reference_windows = build_completed_windows(raw, as_of=(end+timedelta(seconds=30)).replace(tzinfo=ZONE),
                                               policy=policy, modules=(6,))
    scorer = QualifiedShadowScorer()
    expected = [json.loads(canonical({"window": asdict(w), "score": asdict(scorer.score(w, profile))}))
                for w in reference_windows]
    cursor = 0
    clock = start+timedelta(minutes=5)
    retry_count = 0
    rollback_count = 0
    cycle_ms = []
    while clock <= end:
        next_cursor = cursor
        while next_cursor < len(raw) and raw[next_cursor]["recorded_at"] < clock:
            next_cursor += 1
        began = perf_counter()
        with engine.connect() as conn:
            fetched = [json.loads(item[0]) for item in conn.execute(select(inputs.c.payload_json).where(
                inputs.c.run_id == run_id, inputs.c.ingestion_id > cursor,
                inputs.c.ingestion_id <= next_cursor).order_by(inputs.c.ingestion_id))]
        for item in fetched:
            item["recorded_at"] = datetime.fromisoformat(item["recorded_at"])
        token = clock.isoformat()
        def crash():
            raise RuntimeError("TEST_CRASH_BEFORE_COMMIT")
        if clock == start+timedelta(minutes=10):
            before = store.points(run_id)
            try:
                store.consume(run_id, token, fetched, as_of=clock.replace(tzinfo=ZONE),
                              next_cursor=next_cursor, profiles=profiles, before_commit=crash)
            except RuntimeError as exc:
                assert str(exc) == "TEST_CRASH_BEFORE_COMMIT"
                rollback_count += 1
            else:
                raise AssertionError("crash injection did not execute")
            assert store.points(run_id) == before
            with engine.connect() as conn:
                assert conn.execute(select(runs.c.source_cursor).where(runs.c.run_id == run_id)).scalar() == cursor
        result = store.consume(run_id, token, fetched, as_of=clock.replace(tzinfo=ZONE),
                               next_cursor=next_cursor, profiles=profiles)
        duplicate = store.consume(run_id, token, fetched, as_of=clock.replace(tzinfo=ZONE),
                                  next_cursor=next_cursor, profiles=profiles)
        assert duplicate["duplicate_batch"] and result["source_cursor"] == next_cursor
        retry_count += 1
        # Reconnect as a new worker: every cycle restores both states from MySQL.
        engine.dispose()
        store = PersistentRehearsal(engine)
        cycle_ms.append((perf_counter()-began)*1000)
        cursor = next_cursor
        clock += timedelta(minutes=5)
    store.consume(run_id, "grace-flush", [], as_of=(end+timedelta(seconds=30)).replace(tzinfo=ZONE),
                  next_cursor=cursor, profiles=profiles)
    points = store.points(run_id)
    actual = [{"window": p["window"], "score": p["score"]} for p in points]
    assert actual == expected, "persisted replay differs from full batch"
    report = {"run_id": run_id, "mysql_local": True, "source": "archived MX080/M6 forensic seconds",
        "period_start": start.isoformat(), "period_end_exclusive": end.isoformat(),
        "timezone": "Asia/Bangkok", "raw_rows": len(raw), "windows": len(points),
        "parity_mismatches": 0, "retry_batches": retry_count, "reconnect_cycles": retry_count,
        "rollback_tests": rollback_count, "cycle_ms_p95": float(pd.Series(cycle_ms).quantile(.95)),
        "candidate_reference_days": 4, "profile_mode": "LOCAL_CASE_CANDIDATE_NOT_ACTIVE",
        "active_profiles_changed": 0, "pm_alerts_created": 0}
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
