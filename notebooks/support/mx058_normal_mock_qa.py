"""Read-only synthetic HTTP output export/load QA, no source or Profile writes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,gzip,time,hashlib
import requests
from .context_scope_qa import registry
from apps.api.app.context_reference import get_profile
from apps.api.app.db import get_engine

OUT=Path(__file__).resolve().parents[1]/"outputs/mx058_normal_mock_20261006"
PROFILE="2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e"


def fetch(day=None):
    start=time.perf_counter()
    response=requests.get(f"http://127.0.0.1:8000/api/v1/calibration/context/profiles/{PROFILE}/mock-validation",
        params={"day":day} if day else {},headers={"X-Approver-Id":"MockReadOnlyQA_20261006"},timeout=15)
    response.raise_for_status()
    data=response.json()
    assert data["profile_id"]==PROFILE and data["source_kind"]=="MOCK" and data["module"]==1
    assert data["machine_number"]=="MX058" and not data["receipt"]["prospective"]
    if day:assert data["selected_day"]==day and all(p["time"].startswith(day) for p in data["chart"])
    return data,(time.perf_counter()-start)*1000


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    first,cold=fetch()
    for day in first["days"]:
        result,_=fetch(day)
        (OUT/f"mock-{day}.json.gz").write_bytes(gzip.compress(json.dumps(result,separators=(",",":"),ensure_ascii=False).encode(),mtime=0))
    def sample(i):return fetch(first["days"][i%3])[1]
    with ThreadPoolExecutor(max_workers=8) as pool:times=sorted(pool.map(sample,range(48)))
    m=get_profile(get_engine(),PROFILE)
    after={"registry":registry(),"frozen_profile_sha256":hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest(),"profile_id":PROFILE}
    before=json.loads((OUT/'before.json').read_text(encoding='utf-8'))
    assert before==after,"Frozen Profile/legacy Active/import registry changed"
    (OUT/'after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
    receipt={k:first[k] for k in ("mock_id","version","machine_number","module","profile_id","days","sv","missing_reference_states","normal_test_passed","receipt","actual_readiness")}
    receipt.update(clients=8,requests=48,successes=48,warm_p50_ms=times[23],warm_p95_ms=times[45],warm_max_ms=max(times),
                   first_http_ms=cold,scope="Prepared mock HTTP reads; excludes browser rendering/source preparation",registry_unchanged=True)
    (OUT/'qa.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print({k:receipt[k] for k in ('days','normal_test_passed','receipt','warm_p95_ms','warm_max_ms','registry_unchanged')})


if __name__=='__main__':main()
