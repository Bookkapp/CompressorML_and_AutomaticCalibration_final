"""Actual localhost source reads + isolated Preview, no Candidate/Active/Server.

Run the existing reference_review_mysql_experiment API on 8178 first.
Only one QA job is inserted in its named isolated schema. Source is SELECT-only.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine, text

from apps.api.app.config import get_settings
from notebooks.support.reference_review_mysql_experiment import SCHEMA, LOCAL_HOSTS
from sqlalchemy.engine import make_url


def main():
    settings=get_settings()
    if any(make_url(url).host not in LOCAL_HOSTS for url in (settings.database_url,settings.source_database_url)):
        raise RuntimeError("Availability QA is localhost-only")
    base="http://127.0.0.1:8178"
    inventory={}
    for machine,module in (("MX080",6),("MX057",1),("MX057",6),("MX017",6)):
        started=time.perf_counter()
        response=requests.get(base+"/api/v1/calibration/reference/availability",
            params={"machine_number":machine,"module":module},timeout=30)
        response.raise_for_status()
        value=response.json()
        inventory[f"{machine}/M{module}"]={**value,"request_seconds":time.perf_counter()-started}
    mx080=inventory["MX080/M6"]
    assert mx080["source_latest"] == "2026-09-21T03:13:28"
    assert mx080["default_period"]["shadow_missing_dates"] == ["2026-09-18","2026-09-20"]
    assert mx080["default_period"]["shadow_observed_days"] == 1
    assert mx080["suggested_period"] is None  # five consecutive source days cannot cover ref>=3 + shadow3
    engine=create_engine(settings.model_copy(update={"analytics_db_name":SCHEMA}).database_url)
    def counts():
        with engine.connect() as conn:
            return {name:int(conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()) for name in
                ("ht9046mx_calibration_profile","ht9046mx_active_calibration_profile")}
    before=counts()
    actor="local-availability-v2-qa"
    headers={"X-Approver-Id":actor}
    payload={"idempotency_key":"availability-qa-"+str(uuid.uuid4()),"machine_number":"MX080","module":6,
        "shadow_end":"2026-09-08","shadow_selection_reason":"Historical populated days, source coverage QA only"}
    response=requests.post(base+"/api/v1/calibration/reference/preview",json=payload,headers=headers,timeout=30)
    assert response.status_code == 202, response.text
    job=response.json(); deadline=time.monotonic()+90
    while job["status"] in ("PREVIEW_QUEUED","PREVIEW_RUNNING") and time.monotonic()<deadline:
        time.sleep(.5)
        response=requests.get(base+f"/api/v1/calibration/reference/jobs/{job['job_id']}",headers=headers,timeout=30)
        response.raise_for_status(); job=response.json()
    assert job["status"] == "READY", job
    preview=job["preview"]
    assert preview["selection"]["shadow_start"] == "2026-09-05T00:00:00"
    assert preview["selection"]["source_latest"] == mx080["source_latest"]
    assert preview["summary"]["shadow_days"] == 0 and preview["summary"]["shadow_minutes"] == 0
    assert not preview["can_build"]
    assert len([d for d in preview["daily"] if d["phase"]=="shadow" and d["observed"]]) == 3
    response=requests.post(base+f"/api/v1/calibration/reference/jobs/{job['job_id']}/build",headers=headers,
        json={"source_digest":preview["source_digest"],"acknowledge_reference":True,"review_note":"QA insufficient source"},timeout=30)
    assert response.status_code == 409 and response.json()["detail"] == "REFERENCE_NOT_READY"
    after=counts(); engine.dispose()
    assert before==after
    receipt={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"source_schema":settings.source_db_name,
        "source_table":settings.source_table,"isolated_schema":SCHEMA,"inventory":inventory,
        "preview_job_id":job["job_id"],"selection":preview["selection"],"preview_summary":preview["summary"],
        "coverage_issues":preview["coverage_issues"],"profile_counts_before":before,"profile_counts_after":after,
        "checks":{"latest_timestamp_not_coverage":True,"module_specific_inventory":True,
            "explicit_historical_cutoff":True,"three_observed_days_not_three_qualified_days":True,
            "insufficient_build_rejected":True,"profile_active_unchanged":True}}
    output=Path(__file__).resolve().parents[1]/"outputs/reference_availability_v2/receipt.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summary":receipt["preview_summary"],"checks":receipt["checks"],
        "counts":after,"inventory_seconds":{k:round(v["request_seconds"],3) for k,v in inventory.items()}},ensure_ascii=False))


if __name__=="__main__":main()
