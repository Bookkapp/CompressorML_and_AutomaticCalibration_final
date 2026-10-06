"""
fleet_qa_tester.py
Simulates 30 minutes of operations across the entire 20-machine fleet with 5-minute intervals.
Evaluates end-to-end performance, database throughput, ML inference latency,
alert deduplication, and concurrent multi-tab API responsiveness.
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from .config import get_settings
from .db import connection
from .inference import run_inference_and_sync, extract_machine_number, clean_machine_code
from .stream_simulator import generate_module_telemetry

FLEET_MACHINES = [
    "017", "022", "024", "029", "041", "056", "057", "058", "063", "070",
    "071", "072", "081", "082", "083", "115", "118", "119", "124", "MX080",
]


def bulk_insert_cycle_telemetry(machines: list[str], cycle_start_time: datetime, seconds_per_cycle: int = 30) -> tuple[int, float]:
    """Bulk insert `seconds_per_cycle` rows for every machine in the fleet."""
    t0 = time.perf_counter()
    rows_to_insert = []

    for machine in machines:
        for s in range(seconds_per_cycle):
            rec_at = cycle_start_time + timedelta(seconds=s)
            row_data = {
                "machine_number": machine,
                "recorded_at": rec_at,
                "Status": "Run",
            }
            # For 057: Module 6 has high lp2 deviation (matching its calibrated anomaly)
            # For MX080: Normal healthy baseline (recovered)
            # For other machines: Normal baseline
            for m in range(1, 9):
                is_057_m6_anomaly = (machine in ("057", "57", "MX057") and m == 6)
                mod_data = generate_module_telemetry(m, elapsed_sec=0, inject_anomaly=False)
                if is_057_m6_anomaly:
                    # Elevate lp2 deviation
                    mod_data[f"Lp_2nd_{m}"] = 28.5 + random.gauss(0, 0.2)
                    mod_data[f"Hp_2nd_{m}"] = 245.0 + random.gauss(0, 0.5)
                row_data.update(mod_data)
            rows_to_insert.append(row_data)

    columns = list(rows_to_insert[0].keys())
    col_str = ", ".join(f"`{c}`" for c in columns)
    val_str = ", ".join(f":{c}" for c in columns)
    insert_sql = text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})")

    with connection() as conn:
        chunk_size = 200
        for i in range(0, len(rows_to_insert), chunk_size):
            chunk = rows_to_insert[i : i + chunk_size]
            conn.execute(insert_sql, chunk)
        conn.commit()

    duration = time.perf_counter() - t0
    return len(rows_to_insert), duration


def get_auth_token() -> str:
    """Obtain JWT auth token from Compressor & Vacuum Pump server."""
    req = urllib.request.Request(
        "http://127.0.0.1:5001/api/auth/login",
        data=json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read().decode())["token"]


def test_concurrent_api(token: str, num_requests: int = 10) -> dict:
    """Test concurrent API responsiveness across multiple tabs."""
    endpoints = [
        "http://127.0.0.1:5001/api/devices",
        "http://127.0.0.1:5001/api/summary",
        "http://127.0.0.1:5001/api/alerts?limit=50",
        "http://127.0.0.1:5001/api/v1/analytics/relationship?device_id=357&module_id=6&x_signal=pressure&y_signal=temperature",
        "http://127.0.0.1:5001/api/v1/analytics/correlation?device_id=344&module_id=6&signals=pressure,temperature,current",
    ]

    def fetch_url(url: str):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                lat = time.perf_counter() - t0
                return (lat, resp.status)
        except Exception:
            return (time.perf_counter() - t0, 500)

    urls = [endpoints[i % len(endpoints)] for i in range(num_requests)]
    t_start = time.perf_counter()
    latencies = []
    statuses = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(fetch_url, u) for u in urls]
        for f in concurrent.futures.as_completed(futures):
            lat, status = f.result()
            latencies.append(lat)
            statuses.append(status)

    total_time = time.perf_counter() - t_start
    return {
        "total_time_s": total_time,
        "min_ms": min(latencies) * 1000,
        "avg_ms": (sum(latencies) / len(latencies)) * 1000,
        "max_ms": max(latencies) * 1000,
        "success_rate": f"{statuses.count(200)}/{len(statuses)}",
    }


def run_fleet_qa_simulation():
    print("=================================================================")
    print(" 30-MINUTE FLEET TELEMETRY INGESTION & QA BENCHMARK")
    print(f" Target: {len(FLEET_MACHINES)} Machines | Interval: Every 5 Minutes (6 Cycles)")
    print("=================================================================\n")

    token = get_auth_token()
    now_utc = datetime.now(timezone.utc)
    base_time = now_utc - timedelta(minutes=30)

    cycle_metrics = []

    # 6 intervals of 5 minutes (T = 0m, 5m, 10m, 15m, 20m, 25m)
    for cycle_idx in range(6):
        minute_offset = cycle_idx * 5
        cycle_time = base_time + timedelta(minutes=minute_offset)
        print(f"--- [Cycle {cycle_idx + 1}/6] Simulation Time: T+{minute_offset:02d}m ({cycle_time.strftime('%H:%M:%S UTC')}) ---")

        # 1. Bulk Ingestion: 30 seconds of telemetry per machine per 5-min cycle
        rows_inserted, ingest_sec = bulk_insert_cycle_telemetry(FLEET_MACHINES, cycle_time, seconds_per_cycle=30)
        ingest_rate = rows_inserted / ingest_sec if ingest_sec > 0 else 0
        print(f"  [1. Ingest]  {rows_inserted} rows across {len(FLEET_MACHINES)} machines in {ingest_sec:.2f}s ({ingest_rate:.1f} rows/s)")

        # 2. ML Scoring: Run inference across all machines
        t_infer_start = time.perf_counter()
        infer_res = run_inference_and_sync(target_machines=FLEET_MACHINES, limit_rows_per_machine=30, sync_to_pm=True)
        infer_sec = time.perf_counter() - t_infer_start
        print(f"  [2. ML Scored] {infer_res.get('scored_windows')} windows in {infer_sec:.2f}s | Alerts: {infer_res.get('persistent_alerts')}")

        # 3. Multi-Tab Concurrent Load Test (10 concurrent requests)
        api_load = test_concurrent_api(token, num_requests=10)
        print(f"  [3. Multi-Tab] 10 concurrent requests in {api_load['total_time_s']:.2f}s | Avg: {api_load['avg_ms']:.1f}ms (Max: {api_load['max_ms']:.1f}ms) | {api_load['success_rate']} OK\n")

        cycle_metrics.append({
            "cycle": cycle_idx + 1,
            "minute_offset": minute_offset,
            "rows_inserted": rows_inserted,
            "ingest_sec": ingest_sec,
            "infer_sec": infer_sec,
            "api_avg_ms": api_load["avg_ms"],
            "api_max_ms": api_load["max_ms"],
        })

    # Final Verification Phase
    print("=================================================================")
    print(" FLEET STATUS & ALERT QA VERIFICATION")
    print("=================================================================")

    with connection() as conn:
        # 1. Check duplicate unacknowledged alerts
        dup_alerts = conn.execute(text("""
            SELECT device_id, module_id, COUNT(*) as cnt
            FROM predictive_maintenance.pm_alerts
            WHERE acknowledged = 0
            GROUP BY device_id, module_id
            HAVING cnt > 1
        """)).fetchall()
        print(f"\n1. Duplicate Active Alerts in pm_alerts: {len(dup_alerts)} (Target: 0)")

        # 2. Check Device Statuses across all machines
        dev_rows = conn.execute(text("""
            SELECT id, machine_code, status, last_seen
            FROM predictive_maintenance.pm_devices
            ORDER BY id
        """)).mappings().fetchall()

        print(f"\n2. Fleet Device Statuses ({len(dev_rows)} devices):")
        for d in dev_rows:
            # Check modules under this device
            mod_rows = conn.execute(text("""
                SELECT module_code, status
                FROM predictive_maintenance.pm_modules
                WHERE device_id = :did
            """), {"did": d["id"]}).mappings().fetchall()
            mod_stats = {m["module_code"]: m["status"] for m in mod_rows}
            print(f"  * {d['machine_code']:14}: Status={d['status']:20} | Modules: {mod_stats.get('compressor-m6', 'N/A')} (M6)")

        # 3. Summary of Cycle Timings
        print("\n3. Performance Summary Across 30 Minutes of Simulation:")
        total_rows = sum(m["rows_inserted"] for m in cycle_metrics)
        total_ingest_time = sum(m["ingest_sec"] for m in cycle_metrics)
        total_infer_time = sum(m["infer_sec"] for m in cycle_metrics)
        avg_api_lat = sum(m["api_avg_ms"] for m in cycle_metrics) / len(cycle_metrics)

        print(f"  * Total Telemetry Rows Inserted: {total_rows:,} rows")
        print(f"  * Total Bulk Ingestion Time:     {total_ingest_time:.2f}s (Avg {total_rows/total_ingest_time:.1f} rows/s)")
        print(f"  * Total ML Inference Time:       {total_infer_time:.2f}s (Avg {total_infer_time/len(cycle_metrics):.2f}s/cycle)")
        print(f"  * Multi-Tab API Latency Average: {avg_api_lat:.1f} ms across all cycles")

    print("\n=================================================================")
    print(" FLEET QA BENCHMARK COMPLETED")
    print("=================================================================")


if __name__ == "__main__":
    run_fleet_qa_simulation()
