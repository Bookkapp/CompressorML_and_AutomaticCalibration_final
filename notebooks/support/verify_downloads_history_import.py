"""Read-only complete import audit; no Preview/Build/Approval writes."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings
from notebooks.support.import_downloads_history import (MACHINES, LEDGER, OUTPUT, normalize,
    aliases, row_key, registry_hash)
from apps.api.app.qualified_calibration import load_observed_one_minute_windows, policy_from_settings
from apps.api.app.qualified_windows import build_completed_windows
from apps.api.app.inference import clean_machine_code
from notebooks.support.october_three_machine_calibration import inventory, read_day

EXPECTED = {"017":7_772_969, "024":7_801_416}
MX080_SHA = "5e7e71bef5425215807565e8fe99cebc82e6a6a7ce682d5d889644154a2f9498"
REGISTRY_SHA = {"ht9046mx_calibration_profile":"2ef0c0af95f76b118dcb005c92b08642741f5995e8edeb64418d86e1f2516522",
    "ht9046mx_active_calibration_profile":"7f05d8a04d3c01a3f0a4513592d1200c8d2096449187ce38ed866ba51f377be1"}


def main():
    settings = get_settings()
    if any(make_url(url).host not in ("localhost","127.0.0.1","::1") for url in (settings.database_url,settings.source_database_url)):
        raise RuntimeError("Local audit only")
    source=create_engine(settings.source_database_url); analytics=create_engine(settings.database_url)
    report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"machines":{},"raw_sql_sample_rows":0,
            "one_minute_parity":{}}
    with source.connect() as conn:
        for m in MACHINES:
            receipts=[json.loads(v) for v in conn.execute(text(f"SELECT receipt_json FROM ht9046mx_analytics.{LEDGER} WHERE machine_number=:m ORDER BY source_date"),{"m":m}).scalars()]
            assert len(receipts)==93, (m,len(receipts))
            assert sum(r["raw_rows"] for r in receipts)==EXPECTED[m]
            assert all(r["raw_rows"]==r["inserted_rows"]+r["reused_identical_occurrences"] for r in receipts)
            actual=dict(conn.execute(text("SELECT COUNT(*) n,MIN(recorded_at) first,MAX(recorded_at) last,COUNT(DISTINCT DATE(recorded_at)) days FROM ht9046mx_readings WHERE machine_number=:m"),{"m":m}).mappings().one())
            inserted=sum(r["inserted_rows"] for r in receipts)
            assert actual["n"]==480+inserted and actual["days"]==93
            assert actual["first"]==datetime(2026,7,1)
            assert actual["last"].date().isoformat()=="2026-10-01"
            report["machines"][m]={"files":93,"raw_rows":EXPECTED[m],"inserted_rows":inserted,
                "reused_identical_occurrences":sum(r["reused_identical_occurrences"] for r in receipts),
                "overlapping_nonreused_occurrences":sum(r["overlapping_nonidentical_occurrences"] for r in receipts),
                "source_duplicate_timestamp_rows":sum(r["duplicate_timestamp_rows"] for r in receipts),
                "source_out_of_order_steps":sum(r["out_of_order_steps"] for r in receipts),
                "source_null_cells":sum(r["null_cells"] for r in receipts),"database":actual}
            print(json.dumps({"stage":"machine_counts", "machine":m,"rows":actual["n"]}),flush=True)
        oldrows=[dict(r) for r in conn.execute(text("SELECT * FROM ht9046mx_readings WHERE machine_number IN ('080','80','MX080','HT9046MX-080') ORDER BY id")).mappings()]
        mxsha=hashlib.sha256(json.dumps(oldrows,sort_keys=True,default=str).encode()).hexdigest()
        assert len(oldrows)==8582 and mxsha==MX080_SHA
        report["mx080"]={"rows":len(oldrows),"sha256":mxsha,"unchanged":True}
        total=conn.execute(text("SELECT COUNT(*) FROM ht9046mx_readings")).scalar()
        assert total==322_200+sum(r["inserted_rows"] for r in report["machines"].values())
        report["source_total_rows"]=total
    archive_info, entries, handles=inventory(Path("C:/Users/Book/Downloads"))
    rng=np.random.default_rng(1302)
    try:
        with source.connect() as conn:
            for m in MACHINES:
                for date in ("2026-07-01","2026-08-15","2026-10-01"):
                    entry=next(e for e in entries if e["machine"]==m and e["date"]==date and e["kind"]=="dynamic")
                    raw,stamps,_=read_day(entry); f=normalize(raw,stamps)
                    positions=sorted({0,len(f)-1,*rng.integers(0,len(f),size=32).tolist()})
                    selected=",".join(f"`{c}`" for c in f.columns)
                    names=aliases(m); params={f"a{i}":v for i,v in enumerate(names)}
                    for pos in positions:
                        params["t"]=f.iloc[pos].recorded_at.to_pydatetime()
                        stored=conn.execute(text(f"SELECT {selected} FROM ht9046mx_readings WHERE machine_number IN ({','.join(':'+k for k in params if k.startswith('a'))}) AND recorded_at=:t"),params).all()
                        key=row_key(f.iloc[pos].tolist())
                        assert key in {row_key(row) for row in stored},(m,date,pos)
                        report["raw_sql_sample_rows"]+=1
                    if date=="2026-07-01":
                        zone=ZoneInfo(settings.source_timezone)
                        start=datetime(2026,7,1,tzinfo=zone); end=start+timedelta(hours=1)
                        observed=f.loc[f.recorded_at < end.replace(tzinfo=None)].to_dict("records")
                        observed=[{**row,"machine_number":clean_machine_code(m)} for row in observed]
                        expected=build_completed_windows(observed,as_of=end+timedelta(days=1),
                            policy=policy_from_settings(settings),modules=(6,))
                        actual=load_observed_one_minute_windows(settings,machine_number=m,start=start,end=end,
                            as_of=end+timedelta(days=1),modules=(6,))
                        assert actual==expected and len(actual)==60,(m,"one-minute parity")
                        report["one_minute_parity"][m]={"module":6,"windows":len(actual),
                            "qualified":sum(w.eligible for w in actual),"exact_match":True}
                    print(json.dumps({"stage":"raw_sql_parity","machine":m,"date":date}),flush=True)
    finally:
        for handle in handles:handle.close()
    registry=registry_hash(analytics)
    assert all(registry[k]["sha256"]==v for k,v in REGISTRY_SHA.items())
    report["registry"]=registry
    api=requests.get("http://127.0.0.1:8000/api/v1/source/machines",timeout=90)
    api.raise_for_status()
    found={r["machine_number"]:r for r in api.json()}
    for m in MACHINES:
        display="MX"+m  # The discovery endpoint exposes display IDs, not raw source keys.
        assert display in found and found[display]["record_count"]==report["machines"][m]["database"]["n"]
    report["source_discovery"]={m:found["MX"+m] for m in MACHINES}
    report["archives"]=archive_info
    report["scope"]="Local raw import only; no Auto-calibration/Profile/Active/ML/Server/Alert activation"
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"verification.json").write_text(json.dumps(report,indent=2,default=str,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,default=str,ensure_ascii=False))
    source.dispose();analytics.dispose()


if __name__=="__main__":main()
