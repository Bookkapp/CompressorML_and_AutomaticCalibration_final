"""Explicit localhost-only rehearsal of reference review with archived real data.

Creates only a separate QA analytics schema. Never queries/writes source MySQL,
never approves a Profile, and never launches a scoring/alert worker.
Cache gate reasons are aggregated; this adapter is NOT the Server source reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "ht9046mx_reference_review_qa_20261001"
CACHE = ROOT / "notebooks/outputs/october_three_machine_calibration_v1/minutes"
OUTPUT = ROOT / "notebooks/outputs/reference_review_local_qa_v1"


def setup(as_of: datetime):
    from apps.api.app.config import get_settings
    original = get_settings()
    if make_url(original.database_url).host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Local QA requires a configured localhost analytics MySQL")
    admin = create_engine(original.database_url, pool_pre_ping=True)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{SCHEMA}`"))
    admin.dispose()
    qa = original.model_copy(update={"analytics_db_name": SCHEMA, "app_mode":"live",
        "profile_min_calibration_days":7,"profile_min_calibration_windows":200,
        "profile_shadow_days":3, "profile_min_shadow_windows":200,
        "qualified_1m_late_arrival_seconds":30})
    engine = create_engine(qa.database_url, pool_pre_ping=True)
    for migration in ("mysql_phase6_calibration_registry.sql", "mysql_reference_review.sql"):
        sql = (ROOT / "deployment" / migration).read_text(encoding="utf-8")
        sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        with engine.begin() as conn:
            for statement in sql.split(";"):
                if statement.strip(): conn.execute(text(statement))
    from apps.api.app import db, reference_jobs as jobs, main, repository
    from apps.api.app.qualified_windows import QualifiedWindow, FEATURES, STATE_CODE
    db._engine = engine
    jobs.get_settings = lambda:qa
    main.get_settings = lambda:qa
    repository.get_settings = lambda:qa
    main.settings = qa
    jobs._latest_source_time = lambda *_:as_of
    receipts = {}
    def archived_windows(settings, *, machine_number, start, end, modules, progress=None, **kwargs):
        machine = machine_number.removeprefix("MX")
        first, last = start.replace(tzinfo=None), end.replace(tzinfo=None)
        rows=[]; cursor=first
        while cursor < last:
            if progress: progress(cursor.date().isoformat())
            path=CACHE/f"{machine}_{cursor.date().isoformat()}.parquet"
            if path.exists():
                receipts[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
                data=pd.read_parquet(path)
                data=data.loc[data.module.isin(modules) & data.stamp.ge(first) & data.stamp.lt(last)]
                for row in data.itertuples(index=False):
                    eligible=bool(row.eligible)
                    features={f:float(getattr(row,f)) for f in FEATURES} if eligible else None
                    gap=float(row.gap) if math.isfinite(float(row.gap)) else 60.
                    reason="" if eligible else "CACHE_MANUAL_OR_UNKNOWN_BUSY" if row.manual_seconds > 0 else "CACHE_STATE_NOT_ELIGIBLE" if row.quality else "CACHE_LOW_COVERAGE_OR_GAP"
                    stamp=row.stamp.to_pydatetime()
                    rows.append(QualifiedWindow(machine_number,int(row.module),stamp,stamp+timedelta(minutes=1),
                        "Off" if eligible else "UNKNOWN",STATE_CODE if eligible else "NOT_SCORED",
                        int(row.samples),60,min(1.,int(row.samples)/60),gap,"PASS" if eligible else "NOT_SCORED",reason,features))
            cursor+=timedelta(days=1)
        return rows
    jobs.load_observed_one_minute_windows=archived_windows
    class ArchiveRepository(repository.AnalyticsRepository):
        def source_machines(self):
            return [{"machine_number":"MX080","display_name":"MX080 · LOCAL ARCHIVE QA", "record_count":None,
                "latest_recorded_at":as_of,"earliest_recorded_at":datetime(2026,7,1)}]
        def fleet_machines(self,*a,**k): return []
        def incidents(self,*a,**k): return []
        def automation_runs(self,*a,**k): return []
    main.source=lambda:ArchiveRepository()
    main.is_demo=lambda:False
    # Renderable header with no implication of a live production feed.
    main.app.router.routes = [r for r in main.app.router.routes if getattr(r,"path",None)!="/api/v1/fleet/summary"]
    @main.app.get("/api/v1/fleet/summary")
    def qa_fleet():
        return {"generated_at":datetime.now().isoformat(),"mode":"LOCAL_ARCHIVE_REFERENCE_QA",
            "release_state":"LOCAL_ONLY_NO_ACTIVATION","dashboard_refresh_minutes":5,
            "scoring_interval_minutes":1,"cadence_gate":"LOCAL_ARCHIVE","condition_index_available":False,"machines":[]}
    @main.app.middleware("http")
    async def no_activation(request,call_next):
        if request.method=="POST" and request.url.path not in ("/api/v1/calibration/reference/preview",) and not request.url.path.endswith("/build"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=409,content={"detail":"Local QA never activates profiles or writes alerts"})
        return await call_next(request)
    return qa, engine, receipts


def smoke(as_of: datetime):
    qa,engine,receipts=setup(as_of)
    from apps.api.app import reference_jobs as jobs
    from apps.api.app.reference_review import ReferencePreviewRequest
    start=time.perf_counter()
    request=ReferencePreviewRequest(idempotency_key=f"archive-smoke-{time.time_ns()}",machine_number="MX080",module=6)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(lambda _: jobs.create_preview(request,"local-qa-reviewer"),range(16)))
    assert len(set(ids))==1
    id=ids[0]
    jobs.execute_job(id)
    preview=jobs.get_job(id,"local-qa-reviewer")
    if preview["status"]!="READY": raise RuntimeError(preview["error_code"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _:jobs.queue_build(id,"local-qa-reviewer",preview["preview"]["source_digest"],"Local archived-data QA; not approval"),range(16)))
    jobs.execute_job(id); jobs.execute_job(id)
    result=jobs.get_job(id,"local-qa-reviewer")
    if result["status"]!="COMPLETED": raise RuntimeError(result["error_code"])
    with engine.connect() as conn:
        candidate=conn.execute(text("SELECT profile_id,profile_status,calibration_windows,calibration_days,shadow_windows,shadow_days,source_digest FROM ht9046mx_calibration_profile WHERE batch_id=:batch"),{"batch":result["result"]["batch_id"]}).mappings().one()
        n=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_calibration_profile WHERE batch_id=:batch"),{"batch":result["result"]["batch_id"]}).scalar()
        active=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_active_calibration_profile")).scalar()
        shadow=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_calibration_shadow_point WHERE profile_id=:id"),{"id":candidate["profile_id"]}).scalar()
    assert n==1 and active==0 and shadow==4320
    # Exercise the REAL MySQL Candidate/Shadow transaction, not a SQLite stub.
    # Inject failure after registry inserts but before the completion commit.
    tables=("ht9046mx_calibration_batch","ht9046mx_calibration_profile","ht9046mx_calibration_shadow_point")
    def counts():
        with engine.connect() as conn:
            return {table:conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables}
    before=counts()
    failed_id=jobs.create_preview(request.model_copy(update={"idempotency_key":f"archive-rollback-{time.time_ns()}"}),"local-qa-reviewer")
    jobs.execute_job(failed_id)
    failed_preview=jobs.get_job(failed_id,"local-qa-reviewer")
    assert failed_preview["status"]=="READY"
    jobs.queue_build(failed_id,"local-qa-reviewer",failed_preview["preview"]["source_digest"],"QA injected persistence failure")
    original_persist=jobs.persist_batch
    def fail_after_insert(*args,**kwargs):
        original_persist(*args,**kwargs)
        raise RuntimeError("QA injected failure before Candidate completion commit")
    jobs.persist_batch=fail_after_insert
    try: jobs.execute_job(failed_id)
    finally: jobs.persist_batch=original_persist
    assert jobs.get_job(failed_id,"local-qa-reviewer")["status"]=="FAILED"
    assert counts()==before
    report={"scope":"localhost isolated analytics; actual archived-second-derived minute caches, no source SQL",
        "schema":SCHEMA,"job_id":id,"elapsed_seconds":round(time.perf_counter()-start,2),
        "selection":preview["preview"]["selection"],"summary":preview["preview"]["summary"],
        "candidate":dict(candidate),"shadow_points":shadow,"candidate_count_for_job":n,"active_count":active,
        "concurrent_preview_retries":16,"concurrent_build_retries":16,
        "injected_mysql_transaction_rollback":True,"rollback_job_id":failed_id,
        "input_receipts":receipts,"limitations":["Cache reasons are aggregated", "No real Server integration or approval", "Retrospective, not blind performance validation"]}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"qa_receipt.json").write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("schema","elapsed_seconds","candidate","shadow_points","candidate_count_for_job","active_count")},default=str))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--serve",action="store_true");parser.add_argument("--port",type=int,default=8177)
    parser.add_argument("--as-of",default="2026-09-08T12:00:00")
    args=parser.parse_args();as_of=datetime.fromisoformat(args.as_of)
    if args.serve:
        os.environ["HT9046MX_API_CORS_ORIGINS"]="http://127.0.0.1:5174,http://localhost:5174"
        setup(as_of)
        import uvicorn
        from apps.api.app.main import app
        uvicorn.run(app,host="127.0.0.1",port=args.port)
    else:smoke(as_of)
