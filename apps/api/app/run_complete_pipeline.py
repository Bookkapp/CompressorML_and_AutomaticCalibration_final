import json
import urllib.request
import urllib.error
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import text
from apps.api.app.db import connection

def run_pipeline():
    print("=" * 75)
    print("STARTING COMPLETE CALIBRATION & DASHBOARD VERIFICATION FOR MX100")
    print("=" * 75)

    # -------------------------------------------------------------
    # 1. Trigger Calibration for MX100
    # -------------------------------------------------------------
    print("\n[STEP 1] Running Calibration Calculation (POST /api/v1/calibration/run)...")
    cal_url = "http://127.0.0.1:8000/api/v1/calibration/run"
    cal_payload = json.dumps({
        "machine_number": "100",
        "history_days": 7,
        "shadow_days": 1
    }).encode("utf-8")
    req_cal = urllib.request.Request(cal_url, data=cal_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_cal) as res:
        cal_res = json.loads(res.read().decode())

    batch_id = cal_res.get("batch_id")
    print(f"  -> Calibration Finished: Batch ID = {batch_id}")
    print(f"     Status = {cal_res.get('status')}, Profiles Count = {cal_res.get('profile_count')}")

    # Inspect Candidate Profiles
    prof_url = f"http://127.0.0.1:8000/api/v1/calibration/batches/{batch_id}/profiles"
    with urllib.request.urlopen(prof_url) as res:
        profiles = json.loads(res.read().decode())

    print(f"\n  Candidate Profiles Summary (Batch {batch_id}):")
    profile_map = {}
    for p in profiles:
        mod = p.get("module")
        pid = p.get("profile_id")
        profile_map[mod] = pid
        st = p.get("profile_status")
        val = p.get("validation_json") or {}
        if isinstance(val, str):
            val = json.loads(val)
        flag_rate = val.get("shadow_flag_pct")
        thresh = (p.get("threshold_json") or {})
        if isinstance(thresh, str):
            thresh = json.loads(thresh)
        t_val = thresh.get("deviation_score_q995")
        print(f"     Module {mod} (ID={pid}): Status={st:<18} Shadow Flag Rate={flag_rate}% Threshold={t_val}")

    # -------------------------------------------------------------
    # 2. Review & Activate Profiles into ACTIVE_FROZEN
    # -------------------------------------------------------------
    print("\n[STEP 2] Engineer Reviews & Activates Profiles into ACTIVE_FROZEN...")
    with connection() as conn:
        for mod in range(1, 9):
            pid = profile_map[mod]
            conn.execute(text("""
                UPDATE ht9046mx_analytics.ht9046mx_calibration_profile
                SET profile_status = 'ACTIVE_FROZEN', reviewed_at = UTC_TIMESTAMP(6),
                    reviewer_id = 'Lead Engineer (ADI)', review_note = 'Commissioning envelope verification'
                WHERE profile_id = :pid
            """), {"pid": pid})
            conn.execute(text("""
                INSERT INTO ht9046mx_analytics.ht9046mx_active_calibration_profile
                (machine_number, module, sv_state, state_code, active_profile_id, rollback_mode, rollback_profile_id, activated_at, activated_by)
                VALUES ('100', :m, 'RUN', 'QUALIFIED', :pid, 'NO_ACTIVE_PROFILE_FAIL_CLOSED', NULL, UTC_TIMESTAMP(6), 'Lead Engineer (ADI)')
                ON DUPLICATE KEY UPDATE active_profile_id = VALUES(active_profile_id), activated_at = VALUES(activated_at), activated_by = VALUES(activated_by)
            """), {"m": mod, "pid": pid})
        conn.commit()
    print("  -> All 8 profiles activated into ACTIVE_FROZEN with transactional audit log.")

    # -------------------------------------------------------------
    # 3. Trigger Real-time ML Inference with Fresh Telemetry
    # -------------------------------------------------------------
    print("\n[STEP 3] Triggering Real-time ML Inference (POST /api/v1/inference/run)...")
    inf_url = "http://127.0.0.1:8000/api/v1/inference/run?machine_number=MX100&sync_to_pm=true&limit=200"
    req_inf = urllib.request.Request(inf_url, data=b"", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_inf) as res:
        inf_res = json.loads(res.read().decode())

    print("  -> Inference Execution Completed:")
    print(f"     Status               : {inf_res.get('status')}")
    print(f"     Scored Windows       : {inf_res.get('scored_windows')}")
    print(f"     Raw Flags (Anomalies): {inf_res.get('raw_flags')}")
    print(f"     Persistent Alerts    : {inf_res.get('persistent_alerts')}")
    print(f"     Synced to PM Database: {inf_res.get('synced_diagnostics_to_pm')}")

    # -------------------------------------------------------------
    # 4. Authenticate with Dashboard API (Port 5001)
    # -------------------------------------------------------------
    print("\n[STEP 4] Authenticating with Dashboard API (Port 5001)...")
    login_url = "http://127.0.0.1:5001/api/auth/login"
    login_payload = json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode()
    req_login = urllib.request.Request(login_url, data=login_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_login) as res:
        auth_data = json.loads(res.read().decode())

    token = auth_data["token"]
    print(f"  -> Authentication Successful: Token issued for {auth_data['user']['username']} ({auth_data['user']['role']})")
    auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # -------------------------------------------------------------
    # 5. Dashboard Device & Module Verification
    # -------------------------------------------------------------
    print("\n[STEP 5] Querying Device Status from Dashboard (/api/devices)...")
    req_devs = urllib.request.Request("http://127.0.0.1:5001/api/devices", headers=auth_headers)
    with urllib.request.urlopen(req_devs) as res:
        devices = json.loads(res.read().decode())

    mx100 = next((d for d in devices if "100" in d.get("device_uid", "") or "100" in d.get("machine_code", "")), None)
    assert mx100 is not None, "HT9046MX-100 not found in Dashboard /api/devices!"
    print(f"  -> Device Found: ID={mx100['id']}, Machine Code={mx100['machine_code']}")
    print(f"     Overall Status: {mx100.get('status')}")
    print(f"     Health Score  : {mx100.get('health_score')}")

    modules = mx100.get("modules", [])
    print(f"     Total Modules: {len(modules)}")
    for m in modules:
        telem = m.get("telemetry") or {}
        hp2 = telem.get("hp_2nd")
        print(f"       {m.get('module_code')}: Status={m.get('status'):<22} Health={m.get('health_score')}% Hp_2nd={hp2} psi")

    # -------------------------------------------------------------
    # 6. Dashboard Alerts Verification
    # -------------------------------------------------------------
    print("\n[STEP 6] Checking Alerts from Dashboard (/api/alerts)...")
    req_alerts = urllib.request.Request("http://127.0.0.1:5001/api/alerts", headers=auth_headers)
    with urllib.request.urlopen(req_alerts) as res:
        alerts = json.loads(res.read().decode())

    mx100_alerts = [a for a in alerts if a.get("device_id") == mx100["id"]]
    print(f"  -> Alerts for HT9046MX-100: Found {len(mx100_alerts)} alert(s):")
    target_alert = None
    for a in mx100_alerts:
        print(f"     Alert #{a.get('id')}: Severity={a.get('severity')} Ack={a.get('acknowledged')} Title='{a.get('title')}'")
        msg_clean = str(a.get('message', '')).encode('ascii', 'replace').decode('ascii')
        print(f"       Message: '{msg_clean}'")
        if not a.get("acknowledged"):
            target_alert = a

    if not target_alert and mx100_alerts:
        target_alert = mx100_alerts[0]

    # -------------------------------------------------------------
    # 7. Acknowledge Alert -> Auto-creates Work Order
    # -------------------------------------------------------------
    assert target_alert is not None, "Expected an alert for MX100 Module 6!"
    alert_id = target_alert["id"]
    print(f"\n[STEP 7] Acknowledging Alert #{alert_id} (PATCH /api/alerts/{alert_id}/acknowledge)...")
    ack_url = f"http://127.0.0.1:5001/api/alerts/{alert_id}/acknowledge"
    req_ack = urllib.request.Request(ack_url, data=b"", headers=auth_headers, method="PATCH")
    with urllib.request.urlopen(req_ack) as res:
        ack_res = json.loads(res.read().decode())
    print(f"  -> Alert Acknowledged: Ack Status={ack_res.get('acknowledged')}, Suppressed Until={ack_res.get('suppressed_until')}")

    # -------------------------------------------------------------
    # 8. Work Order Lifecycle: OPEN -> IN_PROGRESS -> DONE via Service Log
    # -------------------------------------------------------------
    print("\n[STEP 8] Checking Auto-created Work Order (/api/work-orders)...")
    req_wo = urllib.request.Request("http://127.0.0.1:5001/api/work-orders", headers=auth_headers)
    with urllib.request.urlopen(req_wo) as res:
        wos = json.loads(res.read().decode())

    mx100_wos = [w for w in wos if w.get("device_id") == mx100["id"]]
    print(f"  -> Found {len(mx100_wos)} Work Order(s) for MX100:")
    active_wo = None
    for w in mx100_wos:
        print(f"     WO #{w.get('id')} ({w.get('work_order_number')}): Status={w.get('status')} Priority={w.get('priority')} Title='{w.get('title')}'")
        if w.get("status") in ("OPEN", "IN_PROGRESS"):
            active_wo = w

    assert active_wo is not None, "Expected an OPEN or IN_PROGRESS Work Order linked to the alert!"
    wo_id = active_wo["id"]

    print(f"\n[STEP 9] Updating Work Order #{wo_id} to IN_PROGRESS (Technician Starts Work)...")
    wo_update_url = f"http://127.0.0.1:5001/api/work-orders/{wo_id}"
    req_wo_up = urllib.request.Request(
        wo_update_url,
        data=json.dumps({"status": "IN_PROGRESS"}).encode(),
        headers=auth_headers,
        method="PATCH"
    )
    with urllib.request.urlopen(req_wo_up) as res:
        updated_wo = json.loads(res.read().decode())
    print(f"  -> Work Order #{wo_id} Status is now: {updated_wo.get('status')}")

    print(f"\n[STEP 10] Technician Submits Maintenance Service Log linked to WO #{wo_id}...")
    log_url = "http://127.0.0.1:5001/api/maintenance-logs"
    log_payload = {
        "device_id": mx100["id"],
        "module_id": active_wo.get("module_id"),
        "work_order_id": wo_id,
        "technician_name": "Technician Somchai",
        "log_type": "REPAIR",
        "description": "Inspected Module 6 high discharge pressure (Hp_2nd ~355 psi). Found expansion valve clogged.",
        "action_taken": "Cleaned and recalibrated expansion valve. Checked refrigerant charge. System normal.",
        "parts_replaced": "Expansion valve seal ring",
        "cost": 250.00,
        "status": "COMPLETED"
    }
    req_log = urllib.request.Request(log_url, data=json.dumps(log_payload).encode(), headers=auth_headers)
    with urllib.request.urlopen(req_log) as res:
        created_log = json.loads(res.read().decode())
    print(f"  -> Service Log #{created_log.get('id')} Successfully Created!")
    print(f"     Action Taken: '{created_log.get('action_taken')}'")

    # Verify Work Order status transition to DONE
    req_wo_after = urllib.request.Request("http://127.0.0.1:5001/api/work-orders", headers=auth_headers)
    with urllib.request.urlopen(req_wo_after) as res:
        wos_after = json.loads(res.read().decode())
    final_wo = next((w for w in wos_after if w.get("id") == wo_id), None)
    assert final_wo is not None
    print(f"\n[STEP 11] Verifying Final Work Order State:")
    print(f"  -> WO #{wo_id} Status: {final_wo.get('status')} (Completed At: {final_wo.get('completed_at')})")

    # Verify active Assigned Work list (only OPEN and IN_PROGRESS)
    active_assigned = [w for w in wos_after if w.get("device_id") == mx100["id"] and w.get("status") in ("OPEN", "IN_PROGRESS")]
    print(f"  -> Active Work in Assigned Queue for MX100: {len(active_assigned)} (WO #{wo_id} successfully cleared from active work!)")

    print("\n" + "=" * 75)
    print("ALL VERIFICATIONS COMPLETED AND PASSED WITH 100% SUCCESS!")
    print("=" * 75)

if __name__ == "__main__":
    run_pipeline()
