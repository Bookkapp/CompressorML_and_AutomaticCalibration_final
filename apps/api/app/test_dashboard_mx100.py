import json
import urllib.request

def test_dashboard():
    base_url = "http://127.0.0.1:5001/api"

    # 1. GET /api/devices
    url_devs = f"{base_url}/devices"
    with urllib.request.urlopen(url_devs) as res:
        devs = json.loads(res.read().decode())
        mx100 = next((d for d in devs if "100" in d.get("device_uid", "") or "100" in d.get("machine_code", "")), None)
        print("--- 1. Devices API Check ---")
        if mx100:
            print(f"Found Device: ID={mx100.get('id')}, Code={mx100.get('machine_code')}, Status={mx100.get('status')}, HealthScore={mx100.get('health_score')}")
            modules = mx100.get("modules", [])
            print(f"Total modules: {len(modules)}")
            for m in modules:
                print(f"  Mod {m.get('module_index')} ({m.get('name')}): Status={m.get('status')}, Health={m.get('health_score')}, Hp_2nd={m.get('telemetry', {}).get('hp_2nd')} psi")
        else:
            print("MX100 not found in /api/devices! Available devices:", [d.get("machine_code") for d in devs])

    # 2. GET /api/alerts
    url_alerts = f"{base_url}/alerts"
    with urllib.request.urlopen(url_alerts) as res:
        alerts = json.loads(res.read().decode())
        mx100_alerts = [a for a in alerts if "100" in a.get("device_name", "") or "100" in a.get("machine_code", "") or "100" in a.get("device_uid", "")]
        print("\n--- 2. Alerts API Check ---")
        print(f"Total alerts: {len(alerts)}, MX100 alerts: {len(mx100_alerts)}")
        for a in mx100_alerts:
            print(f"  Alert ID={a.get('id')}: Sev={a.get('severity')}, Title='{a.get('title')}', Ack={a.get('acknowledged')}, Mod={a.get('module_name')}, Msg='{a.get('message')}'")

    # 3. GET /api/maintenance/work-orders
    url_wo = f"{base_url}/maintenance/work-orders"
    with urllib.request.urlopen(url_wo) as res:
        wos = json.loads(res.read().decode())
        print(f"\n--- 3. Work Orders Check ---")
        print(f"Total work orders: {len(wos)}")
        for w in wos[:5]:
            print(f"  WO #{w.get('id')} ({w.get('work_order_number')}): Status={w.get('status')}, Title={w.get('title')}, Source={w.get('source_alert_id')}")

if __name__ == "__main__":
    test_dashboard()
