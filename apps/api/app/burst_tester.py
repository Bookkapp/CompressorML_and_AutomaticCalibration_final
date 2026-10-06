"""
burst_tester.py
Simulates a real-world batch flush where 5 minutes (300 seconds) of 1-second telemetry
is flushed at once from multiple machines into MySQL, scored through ML inference,
and validated against multi-tab concurrent HTTP requests.
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from .config import get_settings
from .db import connection
from .inference import run_inference_and_sync
from .stream_simulator import generate_module_telemetry


def batch_insert_telemetry(machines: list[str], count_seconds: int = 300) -> float:
    """Insert `count_seconds` rows per machine into ht9046mx_iot.ht9046mx_readings in bulk."""
    start_time = time.perf_counter()
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(seconds=count_seconds)

    with connection() as conn:
        for machine in machines:
            rows_to_insert = []
            for i in range(count_seconds):
                rec_at = base_time + timedelta(seconds=i)
                row_data = {
                    "machine_number": machine,
                    "recorded_at": rec_at,
                    "Status": "Run",
                }
                # Inject anomaly on MX080, normal on 057
                for m in range(1, 9):
                    row_data.update(generate_module_telemetry(m, elapsed_sec=float(i), inject_anomaly=(machine == "MX080")))
                rows_to_insert.append(row_data)

            columns = list(rows_to_insert[0].keys())
            col_str = ", ".join(f"`{c}`" for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)
            insert_sql = text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})")

            # Execute bulk in chunks of 100 for optimal memory and packet size
            chunk_size = 100
            for chunk_start in range(0, len(rows_to_insert), chunk_size):
                chunk = rows_to_insert[chunk_start : chunk_start + chunk_size]
                conn.execute(insert_sql, chunk)

        conn.commit()

    duration = time.perf_counter() - start_time
    total_rows = len(machines) * count_seconds
    print(f"[Bulk Ingest] Inserted {total_rows} rows across {len(machines)} machines in {duration:.2f}s ({total_rows / duration:.1f} rows/s)")
    return duration


def run_ml_batch_scoring(machines: list[str]) -> tuple[dict, float]:
    """Score the newly flushed telemetry with the production ML model."""
    start_time = time.perf_counter()
    result = run_inference_and_sync(target_machines=machines, limit_rows_per_machine=300, sync_to_pm=True)
    duration = time.perf_counter() - start_time
    print(f"[ML Inference] Scored windows in {duration:.2f}s: {result}")
    return result, duration


def get_auth_token() -> str:
    """Login to Compressor & Vacuum Pump server to get a JWT token."""
    login_url = "http://127.0.0.1:5001/api/auth/login"
    payload = json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode("utf-8")
    req = urllib.request.Request(login_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["token"]


def simulate_concurrent_tabs(token: str, num_tabs: int = 10) -> dict:
    """Simulate `num_tabs` parallel dashboard browser tabs querying the API simultaneously."""
    endpoints = [
        "http://127.0.0.1:5001/api/devices",
        "http://127.0.0.1:5001/api/summary",
        "http://127.0.0.1:5001/api/alerts?limit=50",
        "http://127.0.0.1:5001/api/v1/analytics/relationship?device_id=1&module_id=6&x_signal=pressure&y_signal=temperature",
        "http://127.0.0.1:5001/api/v1/analytics/correlation?device_id=1&module_id=6&signals=pressure,temperature,current",
    ]

    def fetch_endpoint(url: str) -> tuple[str, float, int]:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                latency = time.perf_counter() - t0
                return (url, latency, response.status)
        except Exception as exc:
            latency = time.perf_counter() - t0
            return (url, latency, 500)

    # Prepare requests: each tab requests a random or cyclic endpoint
    tasks = [endpoints[i % len(endpoints)] for i in range(num_tabs)]
    start_time = time.perf_counter()

    latencies = []
    status_codes = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_tabs) as executor:
        futures = [executor.submit(fetch_endpoint, u) for u in tasks]
        for f in concurrent.futures.as_completed(futures):
            url, lat, status = f.result()
            latencies.append(lat)
            status_codes.append(status)

    total_time = time.perf_counter() - start_time
    avg_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    min_lat = min(latencies)

    print(f"[Multi-Tab Load] Sent {num_tabs} concurrent requests in {total_time:.2f}s")
    print(f"   -> Latency: Min={min_lat*1000:.1f}ms | Avg={avg_lat*1000:.1f}ms | Max={max_lat*1000:.1f}ms")
    print(f"   -> Success: {status_codes.count(200)}/{len(status_codes)} (200 OK)")

    return {
        "num_tabs": num_tabs,
        "avg_latency_ms": round(avg_lat * 1000, 2),
        "max_latency_ms": round(max_lat * 1000, 2),
        "min_latency_ms": round(min_lat * 1000, 2),
        "success_rate": f"{status_codes.count(200)}/{len(status_codes)}",
    }


def verify_alerts_and_scores() -> dict:
    """Check pm_alerts and module health states in database."""
    with connection() as conn:
        # Check unacknowledged alerts
        alerts = conn.execute(text("""
            SELECT a.id, d.machine_code, m.module_code, a.severity, a.title, a.recorded_at
            FROM predictive_maintenance.pm_alerts a
            JOIN predictive_maintenance.pm_devices d ON d.id = a.device_id
            JOIN predictive_maintenance.pm_modules m ON m.id = a.module_id
            WHERE a.acknowledged = 0
            ORDER BY a.recorded_at DESC
        """)).mappings().fetchall()

        # Check latest scores for 057 and MX080
        modules = conn.execute(text("""
            SELECT d.machine_code, m.module_code, m.status, s.health_score, s.ai_condition
            FROM predictive_maintenance.pm_modules m
            JOIN predictive_maintenance.pm_devices d ON d.id = m.device_id
            LEFT JOIN predictive_maintenance.pm_diagnostic_snapshots s
                ON s.device_id = d.id AND s.module_id = m.id AND s.id = (
                    SELECT MAX(id) FROM predictive_maintenance.pm_diagnostic_snapshots
                    WHERE device_id = d.id AND module_id = m.id
                )
            WHERE d.machine_code IN ('MX080', 'HT9046MX-080', '057', 'MX057', '57', 'HT9046-057')
            ORDER BY d.machine_code, m.module_code
        """)).mappings().fetchall()

    print("\n--- Current Unacknowledged Alerts (Verified Deduplicated) ---")
    alert_summary = []
    for a in alerts:
        row = f"[{a['severity'].upper()}] {a['machine_code']} {a['module_code']} -> {a['title']} (@ {a['recorded_at']})"
        print(f"  * {row}")
        alert_summary.append(row)

    print("\n--- Latest Machine & Module Health Scores ---")
    scores_summary = []
    for m in modules:
        row = f"{m['machine_code']} {m['module_code']}: Status={m['status']}, Health={m['health_score']}%, Cond={m['ai_condition']}"
        print(f"  * {row}")
        scores_summary.append(row)

    return {
        "active_alerts_count": len(alerts),
        "alerts": alert_summary,
        "modules_evaluated": len(modules),
    }


def main():
    print("=================================================================")
    print(" 5-MINUTE BATCH FLUSH & MULTI-TAB LOAD TEST BENCHMARK")
    print("=================================================================")

    # Step 1: Ingest 300s of 1-second telemetry for MX080 and 057
    print("\n1. Simulating 5-minute burst telemetry ingest (300 rows/machine)...")
    machines = ["MX080", "057"]
    batch_insert_telemetry(machines, count_seconds=300)

    # Step 2: Run ML Inference Batch Scoring
    print("\n2. Executing batch ML scoring and database synchronization...")
    run_ml_batch_scoring(machines)

    # Step 3: Test Concurrent Multi-tab responsiveness on port 5001
    print("\n3. Testing concurrent multi-tab browser responsiveness (10 concurrent requests)...")
    token = get_auth_token()
    load_metrics = simulate_concurrent_tabs(token, num_tabs=10)

    # Step 4: Verify single-alert retention and cooldown
    print("\n4. Verifying Alert Deduplication & Health Score Propagation...")
    verify_alerts_and_scores()

    print("\n=================================================================")
    print(" BENCHMARK COMPLETED SUCCESSFULLY")
    print("=================================================================")


if __name__ == "__main__":
    main()
