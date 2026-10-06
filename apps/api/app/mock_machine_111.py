"""
mock_machine_111.py
Prepares Machine 111 (HT9046MX-111) with a realistic mixture of normal baseline operating data
and severe Module 6 defect data mimicking the MX080 incident (high CP2 discharge pressure,
transient bypass balancing, and alarm trip).

Purpose:
Allows user to test and observe:
1. How State Qualification Gate quarantines SV=On, Busy=1, and Alarm states.
2. How Robust Medians protect the baseline from being corrupted by outlier spikes.
3. How 3-Day Forward Shadow Validation catches the high defect rate and flags Module 6 as REVIEW_REQUIRED (SHADOW_FLAG_RATE_EXCEEDED).
4. How ML Scoring identifies the anomaly and flips Module 6 to MAINTENANCE_REQUIRED (Repair Now).
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta

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
    """
    Generate telemetry dict for mod_num.
    Modes:
      'normal': clean Cold Run baseline
      'balancing': transient pressure balancing attempt (SV=On, Busy=1)
      'drift': developing CP2 pressure drift
      'severe_anomaly': severe persistent high CP2 pressure (mimicking MX080)
      'alarm': compressor alarm trip (Status=Alarm)
    """
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
            # SV=On bypass, Busy=1
            sv = "On"
            busy = "1"
            hp2 = 135.0 + random.gauss(0, 1.0)
            lp2 = 35.0 + random.gauss(0, 0.5)
            temphi = 72.0 + random.gauss(0, 0.5)
        elif mode == "drift":
            # Drifting up
            hp2 = 248.0 + random.gauss(0, 1.5)
            temphi = 86.5 + random.gauss(0, 0.5)
        elif mode == "severe_anomaly":
            # Severe persistent high CP2 discharge pressure defect (like MX080 on Sep 7-8)
            hp2 = 352.0 + random.gauss(0, 2.0)
            lp2 = 28.5 + random.gauss(0, 0.5)
            temphi = 96.5 + random.gauss(0, 0.8)
            templo = -10.5 + random.gauss(0, 0.5)
        elif mode == "alarm":
            st = "Alarm"
            hp2 = 385.0 + random.gauss(0, 2.0)
            temphi = 99.0 + random.gauss(0, 0.5)

    return {
        f"Hp_1st_{mod_num}": round(hp1, 2),
        f"Lp_1st_{mod_num}": round(lp1, 2),
        f"Hp_2nd_{mod_num}": round(hp2, 2),
        f"Lp_2nd_{mod_num}": round(lp2, 2),
        f"Valve_{mod_num}": round(valve, 1),
        f"TempHi_{mod_num}": round(temphi, 2),
        f"TempLo_{mod_num}": round(templo, 2),
        f"Status_{mod_num}": st,
        f"Busy_{mod_num}": busy,
        f"SV_{mod_num}": sv,
    }


def generate_and_insert_mock_data(machine_number: str = "111") -> int:
    now_utc = datetime.now(timezone.utc)
    t_calib_start = now_utc - timedelta(days=2)
    t_shadow_start = now_utc - timedelta(days=1)
    t_live_start = now_utc - timedelta(minutes=15)

    rows: list[dict[str, Any]] = []

    print(f"\n=================================================================")
    print(f" Generating Mock Telemetry for Machine {machine_number} (HT9046MX-{machine_number})")
    print(f"=================================================================")

    # -------------------------------------------------------------
    # 1. Calibration Period (2 days ago, 45 minutes)
    #    - 30 mins: clean Steady Cold Run (M1-M8 normal)
    #    - 5 mins: transient bypass balancing on M6 (SV=On, Busy=1) -> State Gate Quarantines!
    #    - 10 mins: early drift on M6 (Hp2 ~ 250 psi) -> Robust Median protects baseline
    # -------------------------------------------------------------
    print("  [1/3] Generating Calibration Period data (45 minutes, 2 days ago)...")
    for minute in range(45):
        if minute < 30:
            m6_mode = "normal"
        elif minute < 35:
            m6_mode = "balancing"
        else:
            m6_mode = "drift"

        global_status = "Run"
        # 1 reading every 3 seconds = 20 readings/minute
        for s in range(0, 60, 3):
            rec_at = t_calib_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": global_status,
            }
            for m in range(1, 9):
                mode = m6_mode if m == 6 else "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    # -------------------------------------------------------------
    # 2. Shadow Period (1 day ago, 35 minutes)
    #    - 25 mins: severe persistent high CP2 pressure defect on M6 (Hp2 ~ 352 psi, like MX080!)
    #               M1-M5, M7, M8 stay normal
    #    - 10 mins: PLC Alarm trip (Status = Alarm)
    # -------------------------------------------------------------
    print("  [2/3] Generating 3-Day Forward Shadow Validation data (35 minutes, 1 day ago)...")
    for minute in range(35):
        if minute < 25:
            m6_mode = "severe_anomaly"
            global_status = "Run"
        else:
            m6_mode = "alarm"
            global_status = "Alarm"

        for s in range(0, 60, 3):
            rec_at = t_shadow_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": global_status,
            }
            for m in range(1, 9):
                mode = m6_mode if m == 6 else "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    # -------------------------------------------------------------
    # 3. Live Stream Period (recent 15 minutes up to now)
    #    - Machine is currently running with Module 6 high pressure defect
    #    - Modules 1-5, 7, 8 healthy
    # -------------------------------------------------------------
    print("  [3/3] Generating Live Stream Telemetry (15 minutes up to now)...")
    for minute in range(15):
        global_status = "Run"
        m6_mode = "severe_anomaly"
        for s in range(0, 60, 3):
            rec_at = t_live_start + timedelta(minutes=minute, seconds=s)
            row = {
                "machine_number": machine_number,
                "recorded_at": rec_at,
                "Status": global_status,
            }
            for m in range(1, 9):
                mode = m6_mode if m == 6 else "normal"
                row.update(make_module_row(m, mode))
            rows.append(row)

    print(f"  Total rows generated: {len(rows):,} rows across 95 minutes of operation")

    # -------------------------------------------------------------
    # Database Ingestion & Reset
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    columns = list(rows[0].keys())
    col_str = ", ".join(f"`{c}`" for c in columns)
    val_str = ", ".join(f":{c}" for c in columns)
    insert_sql = text(f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})")

    with connection() as conn:
        print("  Cleaning up prior records for Machine 111...")
        conn.execute(text("DELETE FROM ht9046mx_iot.ht9046mx_readings WHERE machine_number IN ('111', 'MX111')"))
        p_ids = [r[0] for r in conn.execute(text("SELECT profile_id FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN ('111', 'MX111')")).fetchall()]
        if p_ids:
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_review WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
            conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_shadow_point WHERE profile_id IN :pids"), {"pids": tuple(p_ids)})
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_active_calibration_profile WHERE machine_number IN ('111', 'MX111')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_calibration_profile WHERE machine_number IN ('111', 'MX111')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_score WHERE machine_number IN ('111', 'MX111')"))
        conn.execute(text("DELETE FROM ht9046mx_analytics.ht9046mx_shadow_alert_episode WHERE machine_number IN ('111', 'MX111')"))
        conn.execute(text("DELETE FROM predictive_maintenance.pm_alerts WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-111', 'MX111', '111'))"))
        conn.execute(text("DELETE FROM predictive_maintenance.pm_diagnostic_snapshots WHERE device_id IN (SELECT id FROM predictive_maintenance.pm_devices WHERE machine_code IN ('HT9046MX-111', 'MX111', '111'))"))

        # Prepare pm_devices and pm_modules
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
    generate_and_insert_mock_data("111")
