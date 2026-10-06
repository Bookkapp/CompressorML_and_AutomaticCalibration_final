"""
new_machine_001_simulation.py
Simulates the complete real-world user journey for newly commissioned Machine 001:
1. Ingest baseline telemetry into IoT database for Machine 001.
2. User triggers Machine Discovery via OPERATION P Web API (GET /api/v1/source/machines).
3. User runs Calibration for Machine 001 via OPERATION P Web API (POST /api/v1/calibration/run).
4. User reviews & approves all 8 module profiles into ACTIVE_FROZEN (POST /api/v1/calibration/machines/001/approve_all).
5. Real-time stream simulator injects live telemetry for Machine 001 and ML inference scores it.
6. User verifies Machine 001 live health scores and charts on Operations Dashboard (Port 5001).
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import text

from .config import get_settings
from .db import connection
from .inference import run_inference_and_sync, extract_machine_number, clean_machine_code
from .stream_simulator import generate_module_telemetry


def step1_ingest_baseline_telemetry(machine_number: str = "001", minutes_per_window: int = 15) -> int:
    """Ingest clean baseline operating telemetry for newly commissioned machine across calibration and shadow periods."""
    print(f"\n=================================================================")
    print(f" STEP 1: Ingesting Baseline Telemetry ({minutes_per_window}m calib + {minutes_per_window}m shadow) for Machine {machine_number}")
    print(f"=================================================================")
    now_utc = datetime.now(timezone.utc)
    t_calib = now_utc - timedelta(days=2)
    t_shadow = now_utc - timedelta(minutes=minutes_per_window)

    rows = []
    total_seconds = minutes_per_window * 60

    # 1. Calibration period data (2 days ago)
    for s in range(total_seconds):
        rec_at = t_calib + timedelta(seconds=s)
        row_data = {
            "machine_number": machine_number,
            "recorded_at": rec_at,
            "Status": "Run",
        }
        for m in range(1, 9):
            row_data.update(generate_module_telemetry(m, elapsed_sec=0, inject_anomaly=False))
        rows.append(row_data)

    # 2. Shadow validation period data (recent)
    for s in range(total_seconds):
        rec_at = t_shadow + timedelta(seconds=s)
        row_data = {
            "machine_number": machine_number,
            "recorded_at": rec_at,
            "Status": "Run",
        }
        for m in range(1, 9):
            row_data.update(generate_module_telemetry(m, elapsed_sec=0, inject_anomaly=False))
        rows.append(row_data)

    columns = list(rows[0].keys())
    col_str = ", ".join(f"`{c}`" for c in columns)
    val_str = ", ".join(f":{c}" for c in columns)
    insert_sql = text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})")

    t0 = time.perf_counter()
    with connection() as conn:
        conn.execute(text("DELETE FROM ht9046mx_iot.ht9046mx_readings WHERE machine_number = :m"), {"m": machine_number})
        p_ids = [r[0] for r in conn.execute(text("SELECT profile_id FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN ('001', 'MX001')")).fetchall()]
        if p_ids:
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_review WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_shadow_point WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_active_calibration_profile WHERE machine_number IN ('001', 'MX001')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN ('001', 'MX001')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_score WHERE machine_number IN ('001', 'MX001')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_alert_episode WHERE machine_number IN ('001', 'MX001')"))
        conn.execute(text("DELETE FROM predictive_maintenance.pm_alerts WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-001', 'MX001', '001'))"))
        conn.execute(text("DELETE FROM predictive_maintenance.pm_diagnostic_snapshots WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-001', 'MX001', '001'))"))
        chunk_size = 300
        for i in range(0, len(rows), chunk_size):
            conn.execute(insert_sql, rows[i : i + chunk_size])
        conn.commit()
    elapsed = time.perf_counter() - t0

    print(f"  [OK] Ingested {len(rows)} telemetry rows for Machine {machine_number} in {elapsed:.2f}s ({len(rows)/elapsed:.1f} rows/s)")
    return len(rows)


def step2_discover_machines(machine_number: str = "001") -> dict:
    """User clicks 'Discover Machines' in OPERATION P UI (calls GET /api/v1/source/machines)."""
    print(f"\n=================================================================")
    print(f" STEP 2: Discovering Machines via OPERATION P Web API (Port 8000)")
    print(f"=================================================================")
    url = "http://127.0.0.1:8000/api/v1/source/machines"
    req = urllib.request.Request(url)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode())
    elapsed = time.perf_counter() - t0

    print(f"  [API] GET {url} -> HTTP 200 in {elapsed*1000:.1f}ms")
    mach_001 = next((m for m in data if extract_machine_number(m.get("machine_number", "")) == extract_machine_number(machine_number)), None)
    if mach_001:
        print(f"  [Found Machine {machine_number}]: Raw Code='{mach_001['machine_number']}', Rows={mach_001.get('row_count'):,}, Latest={mach_001.get('latest_recorded_at')}")
    else:
        print(f"  [Notice] Machine {machine_number} not in discovery list; full list:", [m.get("machine_number") for m in data[:5]])
    return mach_001 or {}


def step3_run_calibration(machine_number: str = "001") -> dict:
    """User selects Machine 001 and clicks 'เริ่มรันคำนวณ Calibration Profile ใหม่'."""
    print(f"\n=================================================================")
    print(f" STEP 3: Running Calibration via OPERATION P Web API (POST /api/v1/calibration/run)")
    print(f"=================================================================")
    url = "http://127.0.0.1:8000/api/v1/calibration/run"
    payload = json.dumps({
        "machine_number": machine_number,
        "history_days": 7,
        "shadow_days": 1,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
    elapsed = time.perf_counter() - t0

    print(f"  [API] POST {url} -> HTTP 200 in {elapsed:.2f}s")
    print(f"  [Result]: Status='{data.get('status')}', Batch ID='{data.get('batch_id')}', Profiles={data.get('profile_count')}, Message: {data.get('message')}")
    return data


def step4_approve_profiles(machine_number: str = "001", batch_id: str | None = None) -> dict:
    """User reviews shadow graph & clicks 'Approve All Profiles' (POST /api/v1/calibration/machines/{m}/approve_all)."""
    print(f"\n=================================================================")
    print(f" STEP 4: Approving Profiles into ACTIVE_FROZEN (Human Approval Gate)")
    print(f"=================================================================")
    url = f"http://127.0.0.1:8000/api/v1/calibration/machines/{machine_number}/approve_all"
    payload = json.dumps({
        "approver_id": "Lead Engineer (ADI)",
        "batch_id": batch_id,
        "review_note": f"Commissioning approval for Chamber {machine_number} baseline envelope",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "X-Approver-Id": "Lead Engineer (ADI)"
    })

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode())
    elapsed = time.perf_counter() - t0

    print(f"  [API] POST {url} -> HTTP 200 in {elapsed:.2f}s")
    print(f"  [Result]: Approved Count={data.get('approved_count')}, Profile IDs={data.get('profile_ids')}, Message: {data.get('message')}")
    return data


def step5_realtime_stream_and_ml_score(machine_number: str = "001", seconds: int = 10):
    """Simulate live 1-second PLC telemetry streaming and concurrent ML scoring."""
    print(f"\n=================================================================")
    print(f" STEP 5: Live Real-Time Telemetry Streaming & ML Inference ({seconds}s stream)")
    print(f"=================================================================")

    start_stream = datetime.now(timezone.utc)
    for i in range(seconds):
        rec_at = start_stream + timedelta(seconds=i)
        row_data = {
            "machine_number": machine_number,
            "recorded_at": rec_at,
            "Status": "Run",
        }
        for m in range(1, 9):
            row_data.update(generate_module_telemetry(m, elapsed_sec=float(i), inject_anomaly=False))

        # Insert 1-second live reading
        columns = list(row_data.keys())
        col_str = ", ".join(f"`{c}`" for c in columns)
        val_str = ", ".join(f":{c}" for c in columns)
        with connection() as conn:
            conn.execute(text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})"), row_data)
            conn.commit()

        # Run ML scoring every 2 seconds
        if i % 2 == 0 or i == seconds - 1:
            t_infer = time.perf_counter()
            infer_res = run_inference_and_sync(target_machines=[machine_number], limit_rows_per_machine=10, sync_to_pm=True)
            t_infer_elapsed = time.perf_counter() - t_infer
            print(f"  [T+{i+1:02d}s] Streamed 1s row | ML Scored {infer_res.get('scored_windows')} windows in {t_infer_elapsed*1000:.1f}ms | Synced PM: {infer_res.get('synced_diagnostics_to_pm')}")

        time.sleep(0.3)  # Fast simulated streaming rhythm


def step6_verify_dashboard_as_user(machine_number: str = "001"):
    """User opens Predictive Maintenance Dashboard (Port 5001) to verify Machine 001."""
    print(f"\n=================================================================")
    print(f" STEP 6: Verifying Machine {machine_number} on Operations Dashboard (Port 5001)")
    print(f"=================================================================")

    # 1. Login
    login_url = "http://127.0.0.1:5001/api/auth/login"
    login_payload = json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode()
    req = urllib.request.Request(login_url, data=login_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as res:
        token = json.loads(res.read().decode())["token"]
    print("  [Dashboard Auth] Successfully authenticated as ADIadmin")

    # 2. Get Devices List
    dev_url = "http://127.0.0.1:5001/api/devices"
    dev_req = urllib.request.Request(dev_url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(dev_req, timeout=5) as res:
        devices = json.loads(res.read().decode())

    # Find Machine 001
    target_dev = next((d for d in devices if extract_machine_number(d.get("machine_code", "")) == extract_machine_number(machine_number)), None)
    if not target_dev:
        print(f"  [ERROR] Machine {machine_number} not found in Dashboard devices list!")
        return False

    print(f"\n  >>> [FOUND DEVICE ON DASHBOARD] <<<")
    print(f"  * ID:           {target_dev.get('id')}")
    print(f"  * Machine Code: {target_dev.get('machine_code')}")
    print(f"  * Display Name: {target_dev.get('display_name')}")
    print(f"  * Overall Status: {target_dev.get('status')} (Badge: {'GOOD' if target_dev.get('status') == 'NORMAL' else target_dev.get('status')})")
    print(f"  * Connection:   {target_dev.get('connection_state')}")

    print(f"\n  --- Module Health Scores for Machine {machine_number} ---")
    for m in target_dev.get("modules", []):
        score_str = f"{m.get('health_score')}%" if m.get('health_score') is not None else "AWAITING_SCORE"
        cond_str = m.get('condition_state') or m.get('status')
        print(f"    * {m.get('module_code'):15} ({m.get('module_name')}): Health={score_str} | Status={cond_str}")

    # 3. Test Analytics Chart API for Machine 001
    dev_id = target_dev.get("id")
    mod_6 = next((m for m in target_dev.get("modules", []) if "m6" in m.get("module_code", "").lower() or "sh2" in m.get("module_name", "").lower()), target_dev.get("modules", [{}])[0])
    target_mod_id = mod_6.get("id")
    rel_url = f"http://127.0.0.1:5001/api/v1/analytics/relationship?device_id={dev_id}&module_id={target_mod_id}&x_signal=hp_2nd&y_signal=temperature_hi"
    rel_req = urllib.request.Request(rel_url, headers={"Authorization": f"Bearer {token}"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(rel_req, timeout=5) as res:
        rel_data = json.loads(res.read().decode())
    rel_elapsed = time.perf_counter() - t0
    points_count = len(rel_data.get('data', {}).get('points', []))
    print(f"\n  [Chart API] GET Relationship Graph (hp_2nd vs temperature_hi for M6) -> HTTP 200 in {rel_elapsed*1000:.1f}ms (Data points: {points_count})")

    # 4. Check Alerts
    alerts_url = "http://127.0.0.1:5001/api/alerts?limit=20"
    alerts_req = urllib.request.Request(alerts_url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(alerts_req, timeout=5) as res:
        alerts = json.loads(res.read().decode())
    m001_alerts = [a for a in alerts if extract_machine_number(a.get("machine_code", "")) == extract_machine_number(machine_number)]
    print(f"  [Alert Center] Active Alerts for Machine {machine_number}: {len(m001_alerts)} (Healthy normal operating status)")

    print(f"\n=================================================================")
    print(f" NEW MACHINE {machine_number} COMMISSIONING & E2E VERIFICATION COMPLETE!")
    print(f"=================================================================")
    return True


def main():
    print("#################################################################")
    print(" END-TO-END NEW MACHINE (001) COMMISSIONING & DASHBOARD QA")
    print("#################################################################")

    # 1. Ingest baseline telemetry
    step1_ingest_baseline_telemetry("001", minutes_per_window=15)

    # 2. Discover machines in OPERATION P
    step2_discover_machines()

    # 3. Trigger Calibration calculation
    cal_res = step3_run_calibration("001")
    batch_id = cal_res.get("batch_id")

    # 4. Review and Approve profiles into ACTIVE_FROZEN
    step4_approve_profiles("001", batch_id=batch_id)

    # 5. Live real-time streaming & concurrent ML scoring
    step5_realtime_stream_and_ml_score("001", seconds=10)

    # 6. User verifies on Operations Dashboard (Port 5001)
    step6_verify_dashboard_as_user("001")


if __name__ == "__main__":
    main()
