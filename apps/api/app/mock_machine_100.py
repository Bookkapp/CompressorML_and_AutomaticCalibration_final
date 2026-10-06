"""
mock_machine_100.py
Prepares Machine 100 (HT9046MX-100) with 1 hour of 5-minute incoming telemetry data,
mimicking Machine 80 with Module 6 severe CP2 discharge pressure defect,
intermittent spikes on other modules, and clean baseline data for calibration.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import text

from .config import get_settings
from .db import connection
from .inference import extract_machine_number, clean_machine_code, ensure_pm_device_and_modules


MX080_BASELINES = {
    1: {'hp1': 122.94, 'lp1': 42.03, 'hp2': 228.82, 'lp2': 24.61, 'valve': 0.0, 'temphi': 30.27, 'templo': 28.33},
    2: {'hp1': 120.37, 'lp1': 45.88, 'hp2': 242.18, 'lp2': 20.55, 'valve': 0.0, 'temphi': 33.02, 'templo': 30.23},
    3: {'hp1': 115.11, 'lp1': 45.33, 'hp2': 239.60, 'lp2': 0.01,  'valve': 0.0, 'temphi': 32.24, 'templo': 30.15},
    4: {'hp1': 104.27, 'lp1': 50.05, 'hp2': 249.06, 'lp2': 1.21,  'valve': 0.0, 'temphi': 28.93, 'templo': 27.21},
    5: {'hp1': 100.05, 'lp1': 46.62, 'hp2': 242.19, 'lp2': 0.02,  'valve': 0.0, 'temphi': 30.22, 'templo': 28.39},
    6: {'hp1': 150.30, 'lp1': 28.20, 'hp2': 190.20, 'lp2': 18.60, 'valve': 94.0, 'temphi': 81.10, 'templo': -20.10},
    7: {'hp1': 124.05, 'lp1': 39.58, 'hp2': 218.49, 'lp2': 43.31, 'valve': 0.0, 'temphi': 33.21, 'templo': 29.68},
    8: {'hp1': 118.50, 'lp1': 45.54, 'hp2': 239.30, 'lp2': 0.00,  'valve': 0.0, 'temphi': 28.39, 'templo': 26.88},
}


def make_module_row(mod_num: int, mode: str) -> dict[str, Any]:
    base = MX080_BASELINES.get(mod_num, MX080_BASELINES[1])

    hp1 = base['hp1'] + random.gauss(0, 0.20)
    lp1 = base['lp1'] + random.gauss(0, 0.15)
    hp2 = base['hp2'] + random.gauss(0, 0.25)
    lp2 = base['lp2'] + random.gauss(0, 0.15)
    valve = base['valve'] + random.gauss(0, 0.10)
    temphi = base['temphi'] + random.gauss(0, 0.20)
    templo = base['templo'] + random.gauss(0, 0.20)
    st = "On"
    busy = "0"
    sv = "Off"

    if mod_num == 6:
        if mode == "normal":
            pass
        elif mode == "balancing":
            sv = "On"
            busy = "1"
            hp2 = 135.0 + random.gauss(0, 1.0)
            lp2 = 35.0 + random.gauss(0, 0.5)
            temphi = 72.0 + random.gauss(0, 0.5)
        elif mode == "drift":
            hp2 = 255.0 + random.gauss(0, 1.5)
            temphi = 87.0 + random.gauss(0, 0.5)
        elif mode == "severe_anomaly":
            # Severe persistent high CP2 discharge pressure defect (like MX080)
            hp2 = 355.0 + random.gauss(0, 2.0)
            lp2 = 29.0 + random.gauss(0, 0.5)
            temphi = 96.0 + random.gauss(0, 0.8)
            templo = -10.0 + random.gauss(0, 0.5)
        elif mode == "alarm":
            st = "Alarm"
            hp2 = 385.0 + random.gauss(0, 2.0)
            temphi = 99.0 + random.gauss(0, 0.5)
    elif mod_num == 2 and mode == "spike":
        # Temporary pressure spike on M2
        hp2 = 265.0 + random.gauss(0, 1.5)
        temphi = 42.0 + random.gauss(0, 0.5)
    elif mod_num == 4 and mode == "spike":
        # Temporary valve/current activity on M4
        valve = 35.0 + random.gauss(0, 1.0)
        temphi = 38.0 + random.gauss(0, 0.5)

    return {
        f"Hp_1st_{mod_num}": round(hp1, 2),
        f"Lp_1st_{mod_num}": round(lp1, 2),
        f"Hp_2nd_{mod_num}": round(hp2, 2),
        f"Lp_2nd_{mod_num}": round(lp2, 2),
        f"Valve_{mod_num}": round(max(0.0, valve), 1),
        f"TempHi_{mod_num}": round(temphi, 2),
        f"TempLo_{mod_num}": round(templo, 2),
        f"Status_{mod_num}": st,
        f"Busy_{mod_num}": busy,
        f"SV_{mod_num}": sv,
    }


def generate_and_insert_mock_data(machine_number: str = "100") -> int:
    bkk_tz = ZoneInfo("Asia/Bangkok")
    now_bkk = datetime.now(bkk_tz).replace(tzinfo=None)
    t_calib_start = now_bkk - timedelta(days=2)
    t_shadow_start = now_bkk - timedelta(days=1)
    t_live_start = now_bkk - timedelta(hours=1)

    rows: list[dict[str, Any]] = []

    print(f"\n=================================================================")
    print(f" Generating Mock Telemetry for Machine {machine_number} (HT9046MX-{machine_number})")
    print(f"=================================================================")

    # 1. Calibration Baseline Period (2 days ago, 45 minutes)
    #    Steady Cold Run for all modules to provide valid calibration reference
    print("  [1/3] Generating Calibration Period baseline (45 minutes, 2 days ago)...")
    for minute in range(45):
        m6_mode = "normal" if minute < 35 else "drift"
        for s in range(0, 60, 4):  # 1 sample every 4 seconds = 15/min
            rec_at = t_calib_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": "Run",
            }
            for m in range(1, 9):
                mode = m6_mode if m == 6 else "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    # 2. Shadow Validation Period (1 day ago, 35 minutes)
    print("  [2/3] Generating Shadow Validation data (35 minutes, 1 day ago)...")
    for minute in range(35):
        m6_mode = "severe_anomaly" if minute < 25 else "drift"
        for s in range(0, 60, 4):
            rec_at = t_shadow_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": "Run",
            }
            for m in range(1, 9):
                mode = m6_mode if m == 6 else "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    # 3. Live 1-Hour Streaming Data (spanning 60 minutes up to current time!)
    #    12 blocks of 5 minutes:
    #    0-15m: normal with minor transient spike on M2
    #    15-25m: M6 starts drifting up, minor spike on M4
    #    25-60m: M6 severe persistent high CP2 deviation (>350 psi, like MX080)
    print("  [3/3] Generating 1-Hour Live Stream (12 x 5-minute blocks up to now)...")
    for minute in range(60):
        # Determine operating mode
        if minute < 15:
            m6_mode = "normal"
            m2_mode = "spike" if 5 <= minute <= 8 else "normal"
            m4_mode = "normal"
        elif minute < 25:
            m6_mode = "drift"
            m2_mode = "normal"
            m4_mode = "spike" if 18 <= minute <= 21 else "normal"
        else:
            m6_mode = "severe_anomaly"
            m2_mode = "normal"
            m4_mode = "normal"

        for s in range(0, 60, 4):  # 15 samples per minute = 75 samples per 5-min window
            rec_at = t_live_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": "Run",
            }
            for m in range(1, 9):
                if m == 6:
                    mode = m6_mode
                elif m == 2:
                    mode = m2_mode
                elif m == 4:
                    mode = m4_mode
                else:
                    mode = "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    print(f"  Total rows generated: {len(rows):,} rows across calibration, shadow, and 1-hour live stream")

    # Clean and insert into MySQL
    t0 = time.perf_counter()
    columns = list(rows[0].keys())
    col_str = ", ".join(f"`{c}`" for c in columns)
    val_str = ", ".join(f":{c}" for c in columns)
    insert_sql = text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})")

    with connection() as conn:
        print("  Cleaning up prior records for Machine 100...")
        aliases = ("100", "MX100", "HT9046MX-100", "HT9046MX100")
        conn.execute(text("DELETE FROM ht9046mx_iot.ht9046mx_readings WHERE machine_number IN :aliases"), {"aliases": aliases})
        p_ids = [r[0] for r in conn.execute(text("SELECT profile_id FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN :aliases"), {"aliases": aliases}).fetchall()]
        if p_ids:
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_review WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_shadow_point WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_active_calibration_profile WHERE machine_number IN :aliases"), {"aliases": aliases})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN :aliases"), {"aliases": aliases})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_score WHERE machine_number IN :aliases"), {"aliases": aliases})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_alert_episode WHERE machine_number IN :aliases"), {"aliases": aliases})
        conn.execute(text("DELETE FROM predictive_maintenance.pm_alerts WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-100', 'MX100', '100'))"))
        conn.execute(text("DELETE FROM predictive_maintenance.pm_diagnostic_snapshots WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-100', 'MX100', '100'))"))

        # Register device and modules in predictive_maintenance
        ensure_pm_device_and_modules(conn, machine_number)

        print(f"  Inserting {len(rows):,} rows into ht9046mx_iot.ht9046mx_readings...")
        chunk_size = 300
        for i in range(0, len(rows), chunk_size):
            conn.execute(insert_sql, rows[i : i + chunk_size])
        conn.commit()

    elapsed = time.perf_counter() - t0
    print(f"  [OK] Successfully ingested {len(rows):,} rows in {elapsed:.2f}s ({len(rows)/elapsed:.1f} rows/s)")
    return len(rows)


if __name__ == "__main__":
    generate_and_insert_mock_data("100")
