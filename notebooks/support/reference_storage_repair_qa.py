"""Opt-in localhost normal-schema Preview/poll QA; never Build or approve.

Creates one labelled technical review job and retries its idempotency key.
Only HTTP review metadata writes are requested. No source DML or migration.
Run after applying mysql_reference_review.sql and restarting the local API.
"""
import hashlib
import json
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings


def main():
    settings = get_settings()
    for url in (settings.database_url, settings.source_database_url):
        if make_url(url).host not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("This technical QA is localhost-only")
    if settings.analytics_db_name != "ht9046mx_analytics":
        raise RuntimeError("Expected normal local analytics schema")
    engine = create_engine(settings.database_url)
    source = create_engine(settings.source_database_url)
    def registry_snapshot():
        with engine.connect() as conn:
            result = {}
            for name in ("ht9046mx_calibration_profile", "ht9046mx_active_calibration_profile"):
                rows = [dict(r) for r in conn.execute(text(f"SELECT * FROM {name}")).mappings()]
                serialized = sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)
                result[name] = {"rows":len(rows), "sha256":hashlib.sha256("\n".join(serialized).encode()).hexdigest()}
            return result
    def source_snapshot():
        with source.connect() as conn:
            return dict(conn.execute(text(f"SELECT COUNT(*) AS rows_total, MAX(recorded_at) AS latest FROM {settings.source_table}")).mappings().one())
    before, source_before = registry_snapshot(), source_snapshot()
    base = "http://127.0.0.1:8000/api/v1/calibration/reference"
    headers = {"X-Approver-Id":"local-storage-repair-qa"}
    payload = {"idempotency_key":"storage-concurrency-qa-"+str(uuid.uuid4()), "machine_number":"MX080", "module":6}
    response = requests.post(base+"/preview", json=payload, headers=headers, timeout=30)
    assert response.status_code == 202, (response.status_code, response.text)
    job = response.json(); job_id = job["job_id"]
    def poll(_):
        values = []
        for attempt in range(10):
            started = time.perf_counter()
            reply = requests.get(base+f"/jobs/{job_id}", headers=headers, timeout=30)
            value = reply.json()
            values.append({"http":reply.status_code, "status":value.get("status"), "seconds":time.perf_counter()-started})
            time.sleep(.05)
        return values
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = [r for group in pool.map(poll, range(10)) for r in group]
    assert all(r["http"] == 200 for r in results), Counter(r["http"] for r in results)
    deadline = time.monotonic()+90
    while time.monotonic() < deadline:
        reply = requests.get(base+f"/jobs/{job_id}", headers=headers, timeout=30)
        reply.raise_for_status(); job = reply.json()
        if job["status"] not in ("PREVIEW_QUEUED", "PREVIEW_RUNNING"):
            break
        time.sleep(.5)
    assert job["status"] == "READY", job.get("error_code")
    retried = requests.post(base+"/preview", json=payload, headers=headers, timeout=30)
    assert retried.status_code == 202 and retried.json()["job_id"] == job_id
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM ht9046mx_reference_review_job WHERE idempotency_key=:key"), {"key":payload["idempotency_key"]}).scalar() == 1
    after, source_after = registry_snapshot(), source_snapshot()
    assert before == after and source_before == source_after
    assert not job["preview"]["can_build"]  # existing minute-grain/gapped local source
    receipt = {"checked_at_utc":datetime.now(timezone.utc).isoformat(), "analytics_schema":settings.analytics_db_name,
        "source_schema":settings.source_db_name, "source_table":settings.source_table, "preview_job_id":job_id,
        "concurrent_clients":10, "polls":len(results), "http_counts":dict(Counter(r["http"] for r in results)),
        "observed_status_counts":dict(Counter(r["status"] for r in results)),
        "max_poll_seconds":max(r["seconds"] for r in results), "idempotent_retry_same_job":True,
        "status":job["status"], "can_build":job["preview"]["can_build"], "summary":job["preview"]["summary"],
        "registry_before":before, "registry_after":after,
        "source_counts_latest_before":source_before, "source_counts_latest_after":source_after,
        "scope":"Technical normal-local Preview only; no Build, Approval, source DML, Server or worker activation"}
    output = Path(__file__).resolve().parents[1]/"outputs/reference_storage_repair_qa/receipt.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, default=str))
    engine.dispose(); source.dispose()


if __name__ == "__main__":
    main()
