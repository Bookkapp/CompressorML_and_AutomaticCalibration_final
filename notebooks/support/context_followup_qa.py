"""Read-only actual localhost progress/concurrency QA. No source or profile writes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import time

import requests
from sqlalchemy import text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings
from apps.api.app.db import get_engine
from notebooks.support.context_scope_qa import registry

OUT=Path(__file__).resolve().parents[1]/'outputs/context_followup_20261006'
PROFILES=['2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e',
          '65a3e0210722f339c00ee6fc8118e4f7c093e5f7a158a679150aec6526a61416']


def snapshot():
    result=registry();digest=hashlib.sha256()
    with get_engine().connect() as conn:
        for row in conn.execute(text('SELECT profile_id,payload FROM ht9046mx_context_profile ORDER BY profile_id')):
            digest.update(row.profile_id.encode());digest.update(row.payload)
        result['context_profile_sha256']=digest.hexdigest()
        result['context_profile_count']=conn.execute(text('SELECT COUNT(*) FROM ht9046mx_context_profile')).scalar()
    return result


def fetch(profile):
    started=time.perf_counter()
    response=requests.get('http://127.0.0.1:8000/api/v1/calibration/context/profiles/'+profile+'/followup',
        headers={'X-Approver-Id':'ReadOnlyFollowupQA'},timeout=20)
    response.raise_for_status();data=response.json()
    assert data['profile_id']==profile and data['approval_eligible'] is False
    assert len(data['daily'])<=4 and not data['clock_error']
    return (time.perf_counter()-started)*1000,data


def main():
    if make_url(get_settings().source_database_url).host not in ('127.0.0.1','localhost','::1'):
        raise RuntimeError('Localhost-only QA')
    OUT.mkdir(parents=True,exist_ok=True)
    before=snapshot();cold=[fetch(p) for p in PROFILES]
    with ThreadPoolExecutor(max_workers=10) as pool:
        samples=list(pool.map(lambda i:fetch(PROFILES[i%2]),range(120)))
    elapsed=sorted(t for t,_ in samples);after=snapshot()
    assert before==after
    receipt={'clients':10,'requests':120,'successes':len(samples),'warm_p50_ms':elapsed[59],
        'warm_p95_ms':elapsed[113],'warm_max_ms':elapsed[-1],'first_reads_ms':[r[0] for r in cold],
        'registry_unchanged':True,'scope':'Live progress metadata GETs on localhost; excludes queued source capture, scoring and browser rendering'}
    for name,value in [('registry-before',before),('registry-after',after),('http-load',receipt),('actual-progress',[r[1] for r in cold])]:
        (OUT/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
