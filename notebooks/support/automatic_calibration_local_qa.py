"""Local analytics migration/audit only. Calibration UI actions remain manual."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from sqlalchemy import text
from apps.api.app.config import get_settings
from apps.api.app.db import connection

OUTPUT=ROOT/"notebooks/outputs/automatic_calibration_qa_20261003"


def active_snapshot():
    with connection() as conn:
        rows=[dict(r) for r in conn.execute(text("SELECT * FROM ht9046mx_active_calibration_profile ORDER BY machine_number,module,sv_state,state_code")).mappings()]
    payload=json.dumps(rows,sort_keys=True,default=str)
    return {"count":len(rows),"sha256":hashlib.sha256(payload.encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["setup","audit","reader-parity","reader-day-parity","expire-qa-leases","load-benchmark"]);args=parser.parse_args()
    settings=get_settings()
    if settings.analytics_db_host not in ("localhost","127.0.0.1","::1"):
        raise RuntimeError("This helper only accepts local analytics")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if args.mode=="setup":
        before=active_snapshot()
        statement=(ROOT/"deployment/mysql_qualified_day_cache.sql").read_text(encoding="utf-8")
        stamp=perf_counter()
        with connection() as conn:conn.execute(text(statement))
        after=active_snapshot()
        assert before==after
        receipt={"migration":"mysql_qualified_day_cache.sql","elapsed_seconds":perf_counter()-stamp,"active_before":before,"active_after":after}
        (OUTPUT/"setup.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        print(json.dumps(receipt))
    elif args.mode in ("reader-parity","reader-day-parity"):
        from zoneinfo import ZoneInfo
        from apps.api.app.qualified_calibration import load_observed_one_minute_windows
        zone=ZoneInfo(settings.source_timezone)
        minutes=1440 if args.mode=="reader-day-parity" else 30
        start=datetime(2026,9,21,0 if minutes==1440 else 12,tzinfo=zone);end=start+timedelta(minutes=minutes)
        common=dict(machine_number="MX017",start=start,end=end)
        from apps.api.app.qualified_cache import source_revision
        revisions={}
        stamp=perf_counter();plain=load_observed_one_minute_windows(settings,**common,revision_out=revisions);plain_time=perf_counter()-stamp
        compact_revision={}
        stamp=perf_counter();compact=load_observed_one_minute_windows(settings,**common,compact_json=True,revision_out=compact_revision);compact_time=perf_counter()-stamp
        assert plain==compact,"Compact transport must retain exact feature/gate parity"
        assert revisions==compact_revision
        if minutes==1440:assert source_revision(settings,"MX017",start,end)==revisions[start.date().isoformat()]
        receipt={"machine":"MX017","modules":8,"minutes":minutes,"windows":len(plain),"exact_parity":True,"revision_parity":True,
                 "plain_seconds":plain_time,"compact_seconds":compact_time}
        (OUTPUT/f"{args.mode}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        print(json.dumps(receipt))
    elif args.mode=="expire-qa-leases":
        from apps.api.app.reference_jobs import utcnow
        with connection() as conn:
            rows=conn.execute(text("SELECT job_id,request_json FROM ht9046mx_reference_review_job WHERE actor_id='MANUAL_QA_20261003' AND module=0 AND status='PREVIEW_RUNNING'")).mappings().all()
            for row in rows:
                assert json.loads(row["request_json"]).get("mode")=="automatic-reference-v1"
                conn.execute(text("UPDATE ht9046mx_reference_review_job SET lease_until=:past WHERE job_id=:job AND status='PREVIEW_RUNNING'"),{"past":utcnow()-timedelta(seconds=1),"job":row["job_id"]})
        print(json.dumps({"expired_own_qa_leases":[r["job_id"] for r in rows]}))
    elif args.mode=="load-benchmark":
        from concurrent.futures import ThreadPoolExecutor
        from urllib.request import Request,urlopen
        with connection() as conn:
            parent=conn.execute(text("SELECT job_id FROM ht9046mx_reference_review_job WHERE actor_id='MANUAL_QA_20261003' AND module=0 ORDER BY created_at DESC LIMIT 1")).scalar()
            review=conn.execute(text("SELECT job_id FROM ht9046mx_reference_review_job WHERE actor_id='MANUAL_QA_20261003' AND module=1 AND result_json LIKE '%automatic_parent_id%' ORDER BY created_at DESC LIMIT 1")).scalar()
        def read(job):
            stamp=perf_counter()
            with urlopen(Request(f"http://127.0.0.1:8000/api/v1/calibration/reference/jobs/{job}",headers={"X-Approver-Id":"MANUAL_QA_20261003"}),timeout=30) as response:
                payload=response.read();assert response.status==200;json.loads(payload)
            return (perf_counter()-stamp)*1000
        receipt={"clients":10,"method":"GET only; no workflow POST","initial_parent_ms":read(parent),"initial_review_ms":read(review)}
        with ThreadPoolExecutor(max_workers=10) as pool:
            for label,job,count in (("parent_poll",parent,100),("review_graph",review,20)):
                durations=sorted(pool.map(read,[job]*count))
                receipt[label]={"requests":count,"success":count,"p50_ms":durations[count//2],"p95_ms":durations[min(count-1,int(count*.95))],"max_ms":durations[-1]}
        (OUTPUT/"load-benchmark.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        print(json.dumps(receipt))
    else:
        with connection() as conn:
            jobs=[dict(r) for r in conn.execute(text("SELECT job_id,machine_number,module,status,progress_message,error_code,created_at,updated_at,result_json FROM ht9046mx_reference_review_job WHERE created_at >= '2026-10-02 17:00:00' ORDER BY created_at,module")).mappings()]
            count=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_qualified_day_cache")).scalar()
        before=json.loads((OUTPUT/"setup.json").read_text(encoding="utf-8"))["active_before"]
        after=active_snapshot();assert before==after
        receipt={"active":after,"active_unchanged":True,"cache_rows":count,"jobs":jobs}
        (OUTPUT/"audit.json").write_text(json.dumps(receipt,indent=2,default=str),encoding="utf-8")
        print(json.dumps({"active_unchanged":True,"cache_rows":count,"jobs":len(jobs)}))


if __name__=="__main__":main()
