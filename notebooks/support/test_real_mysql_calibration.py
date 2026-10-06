"""
Test Real MySQL Data Loading, Streaming Performance & Candidate Calibration.

Connects to local MySQL:
- Source: ht9046mx_iot.ht9046mx_readings
- Target: ht9046mx_analytics

Benchmarks:
1. Bulk ingestion throughput of real production telemetry (machine 057 and MX080).
2. Streaming / query memory efficiency with machine filtering.
3. Candidate profile generation with full 9x9 Pearson correlation and baseline statistics.
"""

import os
import sys
import time
import psutil
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

# Add apps/api to path
sys.path.insert(0, os.path.abspath("apps/api"))
from app.calibration import run_candidate_calibration, discover_source_machines

SOURCE_URL = os.environ.get("HT9046MX_TEST_SOURCE_URL", "")
TARGET_URL = os.environ.get("HT9046MX_TEST_TARGET_URL", "")


def print_ram(stage: str):
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    print(f"[{stage}] Current process RAM: {mem_mb:.2f} MB")


def load_machine_057_data(engine, num_days: int = 3):
    print(f"\n--- Checking Machine 057 Data in MySQL ---")
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_readings WHERE machine_number = '057'")).scalar()
    if cnt and cnt > 50000:
        print(f"Machine 057 already has {cnt:,} rows in MySQL. Skipping ingestion.")
        return cnt

    print(f"\n--- Loading Machine 057 Data (up to {num_days} days) into MySQL ---")
    print_ram("Before 057 load")
    t0 = time.perf_counter()

    files = sorted(glob.glob("HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings/machine=057/**/*.parquet", recursive=True))
    if not files:
        print("Warning: No parquet files found for machine 057.")
        return 0

    selected_files = files[:num_days]
    print(f"Ingesting {len(selected_files)} files: {[os.path.basename(os.path.dirname(f)) for f in selected_files]}")

    with engine.connect() as conn:
        res = conn.execute(text("SHOW COLUMNS FROM ht9046mx_readings"))
        valid_cols = [row[0] for row in res.fetchall() if row[0] != 'id']

    total_inserted = 0
    for fpath in selected_files:
        df = pd.read_parquet(fpath)
        matching_cols = [c for c in df.columns if c in valid_cols]
        df_to_insert = df[matching_cols].copy()
        df_to_insert["recorded_at"] = pd.to_datetime(df_to_insert["recorded_at"])
        df_to_insert["machine_number"] = "057"

        df_to_insert.to_sql("ht9046mx_readings", engine, if_exists="append", index=False, chunksize=10000)
        total_inserted += len(df_to_insert)
        print(f"  Inserted {len(df_to_insert):,} rows from {os.path.basename(fpath)}")

    elapsed = time.perf_counter() - t0
    print(f"Done! Inserted {total_inserted:,} rows in {elapsed:.2f}s ({total_inserted / max(elapsed, 0.001):,.0f} rows/sec)")
    print_ram("After 057 load")
    return total_inserted


def load_mx080_forensic_data(engine):
    print("\n--- Checking MX080 Telemetry in MySQL ---")
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_readings WHERE machine_number = 'MX080'")).scalar()
    if cnt and cnt > 1000:
        print(f"MX080 already has {cnt:,} rows in MySQL. Skipping ingestion.")
        return cnt

    print("\n--- Loading MX080 Telemetry into MySQL ---")
    print_ram("Before MX080 load")
    t0 = time.perf_counter()

    fpath = "notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/mx080_module6_minute_replay_input.parquet"
    if not os.path.exists(fpath):
        print(f"Warning: {fpath} not found.")
        return 0

    df = pd.read_parquet(fpath)
    print(f"Read {len(df):,} minute rows for MX080 Module 6.")

    # Initialize dataframe with matching length
    wide_df = pd.DataFrame(index=df.index)
    wide_df["machine_number"] = "MX080"
    wide_df["recorded_at"] = pd.to_datetime(df["minute"])
    wide_df["Status"] = df["global_status"]

    # Module 6
    wide_df["Hp_1st_6"] = df["hp1"]
    wide_df["Lp_1st_6"] = df["lp1"]
    wide_df["Hp_2nd_6"] = df["hp2"]
    wide_df["Lp_2nd_6"] = df["lp2"]
    wide_df["Valve_6"] = df["valve"]
    wide_df["TempHi_6"] = df["temphi"]
    wide_df["TempLo_6"] = df["templo"]
    wide_df["Status_6"] = df["module_status"]
    wide_df["Busy_6"] = df["busy"]
    wide_df["SV_6"] = df["sv"]

    # Fill modules 1..5, 7..8 with nulls
    for m in [1, 2, 3, 4, 5, 7, 8]:
        wide_df[f"Hp_1st_{m}"] = np.nan
        wide_df[f"Lp_1st_{m}"] = np.nan
        wide_df[f"Hp_2nd_{m}"] = np.nan
        wide_df[f"Lp_2nd_{m}"] = np.nan
        wide_df[f"Valve_{m}"] = np.nan
        wide_df[f"TempHi_{m}"] = np.nan
        wide_df[f"TempLo_{m}"] = np.nan
        wide_df[f"Status_{m}"] = None
        wide_df[f"Busy_{m}"] = None
        wide_df[f"SV_{m}"] = None

    wide_df.to_sql("ht9046mx_readings", engine, if_exists="append", index=False, chunksize=5000)
    elapsed = time.perf_counter() - t0
    print(f"Done! Inserted {len(wide_df):,} rows for MX080 in {elapsed:.2f}s")
    print_ram("After MX080 load")
    return len(wide_df)


def run_benchmark():
    if not SOURCE_URL or not TARGET_URL:
        raise RuntimeError(
            "Set HT9046MX_TEST_SOURCE_URL and HT9046MX_TEST_TARGET_URL before running. "
            "Keep credentials in the local environment; never commit them."
        )
    source_engine = create_engine(SOURCE_URL)
    target_engine = create_engine(TARGET_URL)

    # 1. Check existing machines
    machines_before = discover_source_machines(SOURCE_URL)
    print(f"Existing discovered machines in MySQL: {len(machines_before)}")
    for m in machines_before[:5]:
        print(f"  Machine {m['machine_number']}: {m['row_count']:,} rows ({m['first_event']} -> {m['last_event']})")

    # 2. Ingest 3 days of machine 057 (~250,000 rows) and MX080
    load_machine_057_data(source_engine, num_days=3)
    load_mx080_forensic_data(source_engine)

    # 3. Re-check discovered machines
    machines_after = discover_source_machines(SOURCE_URL)
    print(f"\nDiscovered machines after ingestion: {len(machines_after)}")
    for m in machines_after:
        if m['machine_number'] in ['057', 'MX080']:
            print(f"  -> Machine {m['machine_number']}: {m['row_count']:,} rows ({m['first_event']} to {m['last_event']})")

    # 4. Benchmark targeted calibration run for machine 057
    print("\n--- Running Target Calibration for Machine 057 ---")
    print_ram("Before 057 calibration")
    t_start = time.perf_counter()

    from app.config import get_settings
    st = get_settings()

    result_057 = run_candidate_calibration(
        settings=st,
        history_days=14,
        shadow_days=3,
        target_machine="057",
        force=True
    )

    t_elapsed = time.perf_counter() - t_start
    print(f"057 Calibration Execution Time: {t_elapsed:.2f}s")
    print_ram("After 057 calibration")
    print(f"Result Status: {result_057.get('status')}")
    print(f"Batch ID: {result_057.get('batch_id')}")
    print(f"Profiles Generated: {result_057.get('profiles')}")
    print(f"Status Counts: {result_057.get('status_counts')}")

    # 5. Benchmark targeted calibration run for MX080
    print("\n--- Running Target Calibration for Machine MX080 ---")
    print_ram("Before MX080 calibration")
    t_start = time.perf_counter()

    result_mx080 = run_candidate_calibration(
        settings=st,
        history_days=14,
        shadow_days=3,
        target_machine="MX080",
        force=True
    )

    t_elapsed = time.perf_counter() - t_start
    print(f"MX080 Calibration Execution Time: {t_elapsed:.2f}s")
    print_ram("After MX080 calibration")
    print(f"Result Status: {result_mx080.get('status')}")
    print(f"Batch ID: {result_mx080.get('batch_id')}")
    print(f"Profiles Generated: {result_mx080.get('profiles')}")
    print(f"Status Counts: {result_mx080.get('status_counts')}")

    # 6. Verify contents of ht9046mx_analytics
    with target_engine.connect() as conn:
        batches_cnt = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_calibration_batch")).scalar()
        profiles_cnt = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_calibration_profile")).scalar()
        shadow_cnt = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_calibration_shadow_point")).scalar()
        print(f"\n--- Target Database Verification (ht9046mx_analytics) ---")
        print(f"Total Batches: {batches_cnt}")
        print(f"Total Profiles: {profiles_cnt}")
        print(f"Total Shadow Points: {shadow_cnt}")

        # Sample profile baseline & correlation
        sample_p = conn.execute(text("""
            SELECT profile_id, machine_number, module, sv_state, profile_status, statistics_json
            FROM ht9046mx_calibration_profile
            LIMIT 1
        """)).fetchone()
        if sample_p:
            import json
            stats = json.loads(sample_p[5]) if sample_p[5] else {}
            print(f"\nSample Profile #{sample_p[0]}: Machine {sample_p[1]}, Module {sample_p[2]}, Status {sample_p[4]}")
            print(f"  Baseline features: {list(stats.get('detailed_baseline', {}).keys())}")
            if "hp2" in stats.get("detailed_baseline", {}):
                print(f"  Hp2 baseline stat: {stats['detailed_baseline']['hp2']}")
            if "correlations" in stats:
                print(f"  Correlation keys: {list(stats['correlations'].keys())}")


if __name__ == "__main__":
    run_benchmark()
