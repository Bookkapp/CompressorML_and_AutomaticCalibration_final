from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import pymysql
from sqlalchemy import text

from .config import get_settings
from .db import connection
from .inference import run_inference_and_sync, clean_machine_code


# Calibrated baseline medians for MX080 modules from ACTIVE_FROZEN profiles
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


def generate_module_telemetry(
    mod_num: int,
    elapsed_sec: float,
    inject_anomaly: bool = True
) -> dict[str, Any]:
    """
    Generate realistic compressor sensor values for module mod_num based on
    the exact ACTIVE_FROZEN calibrated profile.
    For module 6: demonstrates a dynamic anomaly scenario.
    """
    base = MX080_BASELINES.get(mod_num, MX080_BASELINES[1])

    # Small Gaussian sensor noise (tight to baseline so normal modules stay 95-100% health)
    hp1 = base['hp1'] + random.gauss(0, 0.15)
    lp1 = base['lp1'] + random.gauss(0, 0.10)
    hp2 = base['hp2'] + random.gauss(0, 0.20)
    lp2 = base['lp2'] + random.gauss(0, 0.10)
    valve = base['valve'] + random.gauss(0, 0.10)
    temphi = base['temphi'] + random.gauss(0, 0.15)
    templo = base['templo'] + random.gauss(0, 0.15)

    # Dynamic Anomaly on Module 6
    if mod_num == 6 and inject_anomaly:
        if 45 <= elapsed_sec < 90:
            # Phase 1: Developing deviation (Watch phase)
            progress = (elapsed_sec - 45) / 45.0
            hp2 += progress * 40.0  # drifts to ~230 psi
            temphi += progress * 10.0
        elif 90 <= elapsed_sec < 320:
            # Phase 2: Severe persistent anomaly (Maintenance Required phase)
            # High discharge pressure, high delta-P, high discharge temp
            hp2 = 340.0 + random.gauss(0, 1.5)
            lp2 = 28.0 + random.gauss(0, 0.5)
            temphi = 96.0 + random.gauss(0, 1.0)
            templo = -12.0 + random.gauss(0, 0.5)
        elif 320 <= elapsed_sec < 420:
            # Phase 3: Recovery / Technician intervention
            recovery = (420 - elapsed_sec) / 100.0
            hp2 = base['hp2'] + recovery * (340.0 - base['hp2']) + random.gauss(0, 0.5)
            temphi = base['temphi'] + recovery * 15.0 + random.gauss(0, 0.3)
        # after 420s: Returns to normal baseline

    return {
        f"Hp_1st_{mod_num}": round(hp1, 2),
        f"Lp_1st_{mod_num}": round(lp1, 2),
        f"Hp_2nd_{mod_num}": round(hp2, 2),
        f"Lp_2nd_{mod_num}": round(lp2, 2),
        f"Valve_{mod_num}": round(valve, 1),
        f"TempHi_{mod_num}": round(temphi, 2),
        f"TempLo_{mod_num}": round(templo, 2),
        f"Status_{mod_num}": "On",
        f"Busy_{mod_num}": "0",
        f"SV_{mod_num}": "Off",
    }


def insert_stream_row(conn, machine_number: str, recorded_at: datetime, elapsed_sec: float) -> dict[str, Any]:
    """Generate and insert 1 complete row for all 8 modules into ht9046mx_iot.ht9046mx_readings."""
    row_data: dict[str, Any] = {
        "machine_number": machine_number,
        "recorded_at": recorded_at,
        "Status": "Run",
    }
    for m in range(1, 9):
        row_data.update(generate_module_telemetry(m, elapsed_sec, inject_anomaly=(machine_number == "MX080")))

    columns = list(row_data.keys())
    col_str = ", ".join(f"`{c}`" for c in columns)
    val_str = ", ".join(f":{c}" for c in columns)
    sql = f"INSERT INTO ht9046mx_iot.ht9046mx_readings ({col_str}) VALUES ({val_str})"

    conn.execute(text(sql), row_data)
    return row_data


def run_stream_simulation(duration_seconds: int = 600, inference_interval_sec: int = 2):
    """
    Simulates real-time 1-second telemetry stream into MySQL,
    and runs ML Inference & Synchronization to Dashboards.
    """
    print(f"=====================================================================")
    print(f"  STARTING REAL-TIME TELEMETRY STREAM & ML INFERENCE SIMULATION")
    print(f"  Duration: {duration_seconds} seconds ({duration_seconds/60:.1f} minutes)")
    print(f"  Cadence: Telemetry 1-sec | Inference {inference_interval_sec}-sec sync")
    print(f"  Target: MX080 (8 Modules, M6 Dynamic Anomaly) + MX057 (Normal)")
    print(f"=====================================================================\n")

    start_time = time.time()
    last_inference_time = 0.0
    sec_count = 0

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            if elapsed >= duration_seconds:
                print(f"\n[Completed] Simulation reached target duration of {duration_seconds}s.")
                break

            now_dt = datetime.now()

            # Insert 1-second telemetry row into ht9046mx_iot.ht9046mx_readings
            with connection() as conn:
                r_080 = insert_stream_row(conn, "MX080", now_dt, elapsed)
                r_057 = insert_stream_row(conn, "057", now_dt, elapsed)

            sec_count += 1

            # Run ML Inference & Database Synchronization every `inference_interval_sec`
            if (now - last_inference_time) >= inference_interval_sec:
                last_inference_time = now
                res = run_inference_and_sync(
                    target_machines=["MX080", "MX057"],
                    limit_rows_per_machine=3,
                    sync_to_pm=True
                )

                # Query latest status of Module 6 and Module 1 for live reporting
                with connection() as conn:
                    mod6_score = conn.execute(text("""
                        SELECT health_score, `condition`, recorded_at
                        FROM ht9046mx_iot.compressor_health_scores
                        WHERE machine_number = 'MX080' AND module_id = 'compressor-m6'
                        ORDER BY recorded_at DESC LIMIT 1
                    """)).mappings().fetchone()

                    mod1_score = conn.execute(text("""
                        SELECT health_score, `condition`, recorded_at
                        FROM ht9046mx_iot.compressor_health_scores
                        WHERE machine_number = 'MX080' AND module_id = 'compressor-m1'
                        ORDER BY recorded_at DESC LIMIT 1
                    """)).mappings().fetchone()

                m6_hp2 = r_080.get("Hp_2nd_6")
                m6_hs = mod6_score["health_score"] if mod6_score else None
                m6_cond = mod6_score["condition"] if mod6_score else "N/A"
                m1_hs = mod1_score["health_score"] if mod1_score else None

                print(
                    f"[{now_dt.strftime('%H:%M:%S')} | {elapsed:4.0f}s/{duration_seconds}s] "
                    f"M1 Health: {m1_hs}% | "
                    f"M6 Hp2: {m6_hp2:5.1f} psi | M6 Health: {m6_hs}% ({m6_cond}) | "
                    f"Scored: {res.get('scored_windows')} wins | Synced PM: {res.get('synced_diagnostics_to_pm')}"
                )

            # Wait to maintain 1-second rhythm
            sleep_time = max(0.05, 1.0 - (time.time() - now))
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[Stopped] Simulator interrupted by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-time Telemetry & ML Inference Simulator")
    parser.add_argument("--duration", type=int, default=600, help="Duration in seconds (default: 600 = 10 min)")
    parser.add_argument("--interval", type=int, default=2, help="Inference sync interval in seconds (default: 2)")
    args = parser.parse_args()
    run_stream_simulation(duration_seconds=args.duration, inference_interval_sec=args.interval)
