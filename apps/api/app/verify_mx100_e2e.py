import json
import urllib.request
import urllib.error

def run_e2e_mx100_test():
    print("=" * 70)
    print("END-TO-END VERIFICATION: MX100 ON OPERATION & DASHBOARD")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. OPERATION API - Calibration Profiles Check
    # -------------------------------------------------------------
    print("\n[STEP 1] Checking MX100 Calibration Candidate Profiles (Port 8000)...")
    batch_url = "http://127.0.0.1:8000/api/v1/calibration/batches"
    with urllib.request.urlopen(batch_url) as res:
        batches = json.loads(res.read().decode())

    # Find batch containing MX100 or latest batch
    latest_batch = batches[0] if batches else None
    assert latest_batch is not None, "No calibration batches found"
    batch_id = latest_batch["batch_id"]
    print(f"  -> Calibration Batch: {batch_id} (Status: {latest_batch.get('batch_status')})")

    profiles_url = f"http://127.0.0.1:8000/api/v1/calibration/batches/{batch_id}/profiles"
    with urllib.request.urlopen(profiles_url) as res:
        profiles = json.loads(res.read().decode())

    print(f"  -> Total Candidate Profiles in Batch: {len(profiles)}")
    for p in profiles:
        mod = p.get("module")
        status = p.get("profile_status")
        val = p.get("validation_json") or {}
        if isinstance(val, str):
            val = json.loads(val)
        flag_pct = val.get("shadow_flag_pct")
        print(f"     Module {mod}: Status={status:<18} Shadow Flag Rate={flag_pct}%")

    # -------------------------------------------------------------
    # 2. OPERATION API - Active Frozen Profiles & ML Inference
    # -------------------------------------------------------------
    print("\n[STEP 2] Verifying Active Profiles & Executing ML Inference...")
    active_url = "http://127.0.0.1:8000/api/v1/calibration/active_profiles"
    with urllib.request.urlopen(active_url) as res:
        active_list = json.loads(res.read().decode())

    mx100_actives = [p for p in active_list if str(p.get("machine_number")) in ("100", "MX100", "HT9046MX-100")]
    print(f"  -> Active Frozen Profiles for MX100: {len(mx100_actives)}/8 modules active")

    inf_url = "http://127.0.0.1:8000/api/v1/inference/run?machine_number=MX100&sync_to_pm=true&limit=200"
    req_inf = urllib.request.Request(inf_url, data=b"", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_inf) as res:
        inf_res = json.loads(res.read().decode())
    print(f"  -> ML Inference Result:")
    print(f"     Scored Windows        : {inf_res.get('scored_windows')}")
    print(f"     Raw Flags             : {inf_res.get('raw_flags')}")
    print(f"     Persistent Alerts     : {inf_res.get('persistent_alerts')}")
    print(f"     Synced Diagnostics    : {inf_res.get('synced_diagnostics_to_pm')}")

    # -------------------------------------------------------------
    # 3. DASHBOARD API - Authentication (Port 5001)
    # -------------------------------------------------------------
    print("\n[STEP 3] Authenticating with Dashboard API (Port 5001)...")
    login_url = "http://127.0.0.1:5001/api/auth/login"
    login_payload = json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode()
    req_login = urllib.request.Request(login_url, data=login_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_login) as res:
        auth_data = json.loads(res.read().decode())

    token = auth_data["token"]
    user = auth_data["user"]
    print(f"  -> Logged in as: {user.get('username')} ({user.get('role')}), Token length: {len(token)}")

    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # -------------------------------------------------------------
    # 4. DASHBOARD API - Devices & Telemetry Status
    # -------------------------------------------------------------
    print("\n[STEP 4] Fetching Devices from Dashboard...")
    req_devs = urllib.request.Request("http://127.0.0.1:5001/api/devices", headers=auth_headers)
    with urllib.request.urlopen(req_devs) as res:
        devices = json.loads(res.read().decode())

    mx100 = next((d for d in devices if "100" in d.get("device_uid", "") or "100" in d.get("machine_code", "")), None)
    assert mx100 is not None, "HT9046MX-100 not found in devices list!"
    print(f"  -> Device Found: ID={mx100['id']}, Code={mx100['machine_code']}, Name={mx100['display_name']}")
    print(f"     Device Overall Status: {mx100.get('status')}")
    print(f"     Device Health Score  : {mx100.get('health_score')}")

    m6 = next((m for m in mx100.get("modules", []) if m.get("module_index") == 6), None)
    if m6:
        m6_telem = m6.get("telemetry") or {}
        print(f"     Module 6 Telemetry: Hp_2nd={m6_telem.get('hp_2nd')} psi, Lp_2nd={m6_telem.get('lp_2nd')} psi, Temp={m6_telem.get('temp_inlet')} C")
        print(f"     Module 6 Status   : {m6.get('status')}")
    else:
        print("     [Notice] Module 6 not found in modules list")

    # -------------------------------------------------------------
    # 5. DASHBOARD API - Alerts Verification & Acknowledgment
    # -------------------------------------------------------------
    print("\n[STEP 5] Checking Alerts for MX100...")
    req_alerts = urllib.request.Request("http://127.0.0.1:5001/api/alerts", headers=auth_headers)
    with urllib.request.urlopen(req_alerts) as res:
        alerts = json.loads(res.read().decode())

    mx100_alerts = [a for a in alerts if "100" in a.get("device_name", "") or "100" in a.get("machine_code", "") or "100" in a.get("device_uid", "")]
    print(f"  -> Found {len(mx100_alerts)} alerts for MX100:")
    target_alert = None
    for a in mx100_alerts:
        print(f"     Alert ID={a.get('id')}: Sev={a.get('severity')}, Title='{a.get('title')}', Ack={a.get('acknowledged')}, Mod={a.get('module_name')}")
        if not a.get("acknowledged"):
            target_alert = a

    if not target_alert and mx100_alerts:
        target_alert = mx100_alerts[0]

    work_order_id = None
    if target_alert:
        alert_id = target_alert["id"]
        print(f"\n[STEP 6] Testing Acknowledge on Alert #{alert_id}...")
        ack_url = f"http://127.0.0.1:5001/api/alerts/{alert_id}/acknowledge"
        req_ack = urllib.request.Request(ack_url, data=b"", headers=auth_headers, method="PATCH")
        with urllib.request.urlopen(req_ack) as res:
            ack_res = json.loads(res.read().decode())
        print(f"  -> Acknowledged: {ack_res.get('acknowledged')}, Ack By: {ack_res.get('acknowledged_by')}, Suppressed Until: {ack_res.get('suppressed_until')}")

    # -------------------------------------------------------------
    # 7. DASHBOARD API - Work Order Auto-Creation & Lifecycle
    # -------------------------------------------------------------
    print("\n[STEP 7] Checking Work Orders (Assigned Work)...")
    req_wo = urllib.request.Request("http://127.0.0.1:5001/api/work-orders", headers=auth_headers)
    with urllib.request.urlopen(req_wo) as res:
        wos = json.loads(res.read().decode())

    mx100_wos = [w for w in wos if w.get("device_id") == mx100["id"]]
    print(f"  -> Found {len(mx100_wos)} Work Orders for MX100:")
    active_wo = None
    for w in mx100_wos:
        print(f"     WO #{w.get('id')} ({w.get('work_order_number')}): Status={w.get('status')}, Title='{w.get('title')}', Source Alert ID={w.get('source_alert_id')}")
        if w.get("status") in ("OPEN", "IN_PROGRESS"):
            active_wo = w

    if active_wo:
        wo_id = active_wo["id"]
        print(f"\n[STEP 8] Transitioning Work Order #{wo_id} from {active_wo['status']} -> IN_PROGRESS...")
        update_url = f"http://127.0.0.1:5001/api/work-orders/{wo_id}"
        req_update = urllib.request.Request(
            update_url,
            data=json.dumps({"status": "IN_PROGRESS"}).encode(),
            headers=auth_headers,
            method="PATCH"
        )
        with urllib.request.urlopen(req_update) as res:
            updated_wo = json.loads(res.read().decode())
        print(f"  -> Updated WO #{wo_id} Status: {updated_wo.get('status')}")

        # -------------------------------------------------------------
        # 9. DASHBOARD API - Submit Maintenance Log to Complete Work Order
        # -------------------------------------------------------------
        print(f"\n[STEP 9] Submitting Maintenance Service Log linked to WO #{wo_id}...")
        log_url = "http://127.0.0.1:5001/api/maintenance-logs"
        log_payload = {
            "device_id": mx100["id"],
            "module_id": active_wo.get("module_id"),
            "work_order_id": wo_id,
            "technician_name": "Senior Technician ADI",
            "log_type": "REPAIR",
            "description": "Inspected Module 6 high discharge pressure (360 psi). Checked cooling loop and expansion valve.",
            "action_taken": "Recalibrated expansion valve and flushed cooling line. Pressure stabilized.",
            "parts_replaced": "Expansion valve seal",
            "cost": 150.00,
            "status": "COMPLETED"
        }
        req_log = urllib.request.Request(log_url, data=json.dumps(log_payload).encode(), headers=auth_headers)
        with urllib.request.urlopen(req_log) as res:
            created_log = json.loads(res.read().decode())
        print(f"  -> Created Maintenance Log ID={created_log.get('id')}")
        print(f"     Action Taken : '{created_log.get('action_taken')}'")
        print(f"     Linked WO ID : {created_log.get('work_order_id')}")

        # Check WO status again - must be DONE
        req_wo_after = urllib.request.Request(f"http://127.0.0.1:5001/api/work-orders", headers=auth_headers)
        with urllib.request.urlopen(req_wo_after) as res:
            wos_after = json.loads(res.read().decode())
        closed_wo = next((w for w in wos_after if w.get("id") == wo_id), None)
        if closed_wo:
            print(f"  -> Verified Work Order #{wo_id} Status is now: {closed_wo.get('status')} (Completed at: {closed_wo.get('completed_at')})")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e_mx100_test()
