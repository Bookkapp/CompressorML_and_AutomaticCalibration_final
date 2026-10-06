"""Read-only local registry and prepared-HTTP QA; browser owns review clicks."""
from pathlib import Path
import argparse,json,hashlib,time
from concurrent.futures import ThreadPoolExecutor
import requests
from sqlalchemy import text
from sqlalchemy.engine import make_url
from apps.api.app.config import get_settings
from apps.api.app.db import get_engine

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"notebooks/outputs/context_scope_20261006"
ACTOR="ScopeManualQA_20261006"


def registry():
    if make_url(get_settings().database_url).host not in ("localhost","127.0.0.1","::1"):
        raise RuntimeError("This QA only reads the local registry")
    result={}
    with get_engine().connect() as conn:
        for table in ("ht9046mx_calibration_profile","ht9046mx_active_calibration_profile"):
            rows=sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in conn.execute(text(f"SELECT * FROM {table}")).mappings())
            result[table]={"rows":len(rows),"sha256":hashlib.sha256("\n".join(rows).encode()).hexdigest()}
        result["context_active_count"]=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_context_active")).scalar()
        result["import_receipts"]=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_history_import_file")).scalar()
    return result


def get(path):
    response=requests.get("http://127.0.0.1:8000"+path,headers={"X-Approver-Id":ACTOR},timeout=15)
    response.raise_for_status()
    return response.json()


def main():
    parser=argparse.ArgumentParser();parser.add_argument("phase",choices=("before","after"));args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    current=registry();(OUT/f"registry-{args.phase}.json").write_text(json.dumps(current,indent=2),encoding="utf-8")
    jobs={m:get(f"/api/v1/calibration/context/latest?machine_number={m}&completed_only=true") for m in ("017","024")}
    (OUT/"prepared-jobs.json").write_text(json.dumps(jobs,indent=2,ensure_ascii=False),encoding="utf-8")
    print({"phase":args.phase,"registry":current,"prepared":{m:j["job_id"] if j else None for m,j in jobs.items()}})
    if args.phase=="before":return
    before=json.loads((OUT/"registry-before.json").read_text(encoding="utf-8"))
    assert current==before,"Legacy Active/Profile/import registry changed"
    paths=[]
    reviewed=[]
    for machine,job in jobs.items():
        if not job:continue
        path=f'/api/v1/calibration/context/jobs/{job["job_id"]}/coverage';coverage=get(path)
        assert len(coverage["modules"])==8
        paths.append((path,"coverage",machine,None))
        for module in coverage["modules"]:
            model=get(f'/api/v1/calibration/context/profiles/{module["profile_id"]}')
            if (model.get("reference_review") or {}).get("evaluation_scope"):
                reviewed.append({"machine":machine,"module":module["module"],"profile_id":model["profile_id"],
                    "scope":model["reference_review"]["evaluation_scope"],"actor":model["reference_review"]["actor"],
                    "readiness":get(f'/api/v1/calibration/context/profiles/{model["profile_id"]}/readiness')})
            day=model["shadow_start"][:10]
            paths.append((f'/api/v1/calibration/context/profiles/{module["profile_id"]}/day?day={day}',"day",machine,module["module"]))
    for p,_,_,_ in paths:get(p)
    (OUT/"reviewed-scopes.json").write_text(json.dumps(reviewed,indent=2,ensure_ascii=False),encoding="utf-8")
    def fetch(i):
        path,kind,machine,module=paths[i%len(paths)]
        start=time.perf_counter();data=get(path);elapsed=(time.perf_counter()-start)*1000
        if kind=="coverage":assert data["machine_number"]=="MX"+machine
        else:assert all(p["module"]==module for p in data["chart"])
        return elapsed
    with ThreadPoolExecutor(max_workers=10) as pool:times=list(pool.map(fetch,range(120)))
    times.sort();receipt={"clients":10,"requests":120,"successes":len(times),"distinct_views":len(paths),
        "warm_p50_ms":times[59],"warm_p95_ms":times[113],"warm_max_ms":max(times),"legacy_registry_unchanged":True,
        "scope":"Prepared context coverage/day GETs; excludes source preparation and browser rendering"}
    (OUT/"http-qa.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(receipt)


if __name__=="__main__":main()
