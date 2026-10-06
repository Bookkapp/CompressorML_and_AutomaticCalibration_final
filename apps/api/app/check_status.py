import pymysql
import urllib.request
import json
import os
from datetime import datetime

def main():
    print("=== LIVE END-TO-END TELEMETRY & ML SCORE STATUS ===")
    db_user = os.environ.get("HT9046MX_CHECK_DB_USER", "")
    db_password = os.environ.get("HT9046MX_CHECK_DB_PASSWORD", "")
    api_user = os.environ.get("HT9046MX_CHECK_API_USER", "")
    api_password = os.environ.get("HT9046MX_CHECK_API_PASSWORD", "")
    if not all((db_user, db_password, api_user, api_password)):
        raise RuntimeError(
            "Set HT9046MX_CHECK_DB_USER, HT9046MX_CHECK_DB_PASSWORD, "
            "HT9046MX_CHECK_API_USER and HT9046MX_CHECK_API_PASSWORD"
        )
    conn = pymysql.connect(
        host=os.environ.get("HT9046MX_CHECK_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("HT9046MX_CHECK_DB_PORT", "3306")),
        user=db_user,
        password=db_password,
    )
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT COUNT(*) as cnt, MAX(recorded_at) as latest FROM ht9046mx_iot.ht9046mx_readings WHERE recorded_at >= '2026-09-19 19:29:00'")
        row = cur.fetchone()
        print(f"1. Telemetry Ingested (ht9046mx_readings): {row['cnt']} rows | Latest: {row['latest']}")

        cur.execute("SELECT COUNT(*) as cnt, MAX(event_time) as latest FROM ht9046mx_analytics.ht9046mx_shadow_score WHERE event_time >= '2026-09-19 19:29:00'")
        row = cur.fetchone()
        print(f"2. ML Shadow Scores (ht9046mx_shadow_score): {row['cnt']} scores | Latest: {row['latest']}")

        cur.execute("SELECT COUNT(*) as cnt, MAX(recorded_at) as latest FROM predictive_maintenance.pm_diagnostic_snapshots WHERE recorded_at >= '2026-09-19 19:29:00'")
        row = cur.fetchone()
        print(f"3. Diagnostic Snapshots Synced (pm_diagnostic_snapshots): {row['cnt']} snapshots | Latest: {row['latest']}")

        cur.execute("SELECT COUNT(*) as cnt FROM predictive_maintenance.pm_alerts WHERE recorded_at >= '2026-09-19 19:29:00'")
        row = cur.fetchone()
        print(f"4. Alerts in Operations Center (pm_alerts): {row['cnt']} alerts")

        cur.execute("""
            SELECT m.module_name, m.status, ds.health_score, ds.condition_state, ds.recorded_at, ds.ai_notes
            FROM predictive_maintenance.pm_modules m
            JOIN predictive_maintenance.pm_diagnostic_snapshots ds ON ds.module_id = m.id
            WHERE m.device_id = 357 AND ds.id = (
                SELECT MAX(id) FROM predictive_maintenance.pm_diagnostic_snapshots WHERE module_id = m.id
            )
            ORDER BY m.id
        """)
        print("\n5. Current Module Status on Dashboard (MX080 Device #357):")
        for r in cur.fetchall():
            print(f"   [{r['status']:20}] {r['module_name']:18} | Health: {r['health_score']:3}% | Condition: {r['condition_state']:20} | Time: {r['recorded_at']}")

    # Check Compressor_and_VacuumPump Live API
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:5001/api/auth/login',
            data=json.dumps({'username': api_user, 'password': api_password}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        token = json.loads(urllib.request.urlopen(req, timeout=10).read())['token']
        req2 = urllib.request.Request(
            'http://127.0.0.1:5001/api/devices/357',
            headers={'Authorization': f'Bearer {token}'}
        )
        dev = json.loads(urllib.request.urlopen(req2, timeout=10).read())
        print(f"\n6. Compressor & Vacuum Pump Web API Response (port 5001):")
        print(f"   Device: {dev['display_name']} | Overall Status: {dev['status']}")
        for m in dev.get('modules', []):
            print(f"   - {m['module_name']}: HealthScore={m.get('health_score')}% | AI_Condition={m.get('ai_condition')} | Status={m.get('status')}")
    except Exception as e:
        print(f"   Error checking 5001 API: {e}")

if __name__ == "__main__":
    main()
