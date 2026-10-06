import sys
sys.path.insert(0, ".")
from apps.api.app.db import connection
from sqlalchemy import text

def check():
    with connection() as conn:
        devs = conn.execute(text("SELECT * FROM predictive_maintenance.pm_devices WHERE machine_code LIKE '%100%' OR device_uid LIKE '%100%'")).mappings().all()
        print("DEVICES:", [dict(d) for d in devs])
        for d in devs:
            dev_id = d["id"]
            mods = conn.execute(text("SELECT id, device_id, module_code, module_name, module_type, status, telemetry_source FROM predictive_maintenance.pm_modules WHERE device_id = :did ORDER BY id"), {"did": dev_id}).mappings().all()
            print(f"MODULES for {d['device_uid']} (count={len(mods)}):")
            for m in mods:
                print(f"  Mod ID={m['id']}: code='{m['module_code']}', name='{m['module_name']}', status='{m['status']}', telem='{m['telemetry_source']}'")
            alerts = conn.execute(text("SELECT * FROM predictive_maintenance.pm_alerts WHERE device_id = :did"), {"did": dev_id}).mappings().all()
            print(f"ALERTS for {d['device_uid']} (count={len(alerts)}):")
            for a in alerts:
                print(" ", dict(a))
            scores = conn.execute(text("SELECT module, COUNT(*) as count, MAX(event_time) as max_time, SUM(raw_flag) as flags FROM ht9046mx_analytics.ht9046mx_shadow_score WHERE machine_number IN ('100', 'MX100') GROUP BY module")).mappings().all()
            print("SHADOW SCORES:")
            for s in scores:
                print(" ", dict(s))

if __name__ == "__main__":
    check()
