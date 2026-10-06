"""Owner-authorized LOCAL import of October ZIPs, excluding MX080/Static.

Raw wide rows remain raw (no aggregation, interpolation or label). Existing
identical occurrences are reused; source duplicate occurrences are preserved.
One InnoDB transaction commits each file's new rows and its checksum receipt.
Uses server LOAD DATA INFILE in existing secure_file_priv, never enables LOCAL.
Default is plan-only. --apply adds source rows and analytics import receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings
from notebooks.support.october_three_machine_calibration import inventory, read_day

VERSION = "local-raw-zip-import-v1"
MACHINES = ("017", "024")
TAGS = ("Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "Valve", "Status", "TempHi", "TempLo", "SV", "Busy")
RAW_COLUMNS = ["Time", "Status", *[f"{tag}_{m}" for m in range(1,9) for tag in TAGS]]
VALUE_COLUMNS = RAW_COLUMNS[1:]
NUMERIC = [f"{tag}_{m}" for m in range(1,9) for tag in ("Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "Valve", "TempHi", "TempLo")]
LEDGER = "ht9046mx_history_import_file"
OUTPUT = Path(__file__).resolve().parents[1]/"outputs/downloads_history_import_v1"


def aliases(machine):
    if machine not in MACHINES:
        raise ValueError("Only owner-selected non-MX080 machines are allowed")
    return (machine, str(int(machine)), "MX"+machine, "MX-"+machine, "HT9046MX-"+machine, "HT9046MX"+machine)


def normalize(frame, stamps):
    if set(frame.columns) != set(RAW_COLUMNS) or len(frame.columns) != len(RAW_COLUMNS):
        raise ValueError("Unexpected source columns; no partial mapping")
    if stamps.isna().any() or (stamps.dt.floor("s") != stamps).any():
        raise ValueError("Invalid timestamp or unexpected sub-second grain")
    out = frame[VALUE_COLUMNS].copy()
    for column in NUMERIC:
        out[column] = pd.to_numeric(out[column], errors="raise").astype(float)
        if np.isinf(out[column]).any():
            raise ValueError("Infinite numeric source value")
    for column in set(VALUE_COLUMNS)-set(NUMERIC):
        if out[column].isna().any():
            raise ValueError("Missing categorical state; preserve/review file before import")
        out[column] = out[column].astype(str).str.strip()
        if out[column].str.contains(r'[\t\r\n\\\x00"]', regex=True).any() or out[column].str.len().gt(40).any():
            raise ValueError("Unsupported text escaping/length; no silent coercion")
    out.insert(0, "recorded_at", stamps.values)
    return out


def row_key(values):
    return tuple(None if pd.isna(value) else value.to_pydatetime() if isinstance(value, pd.Timestamp) else value for value in values)


def reuse_occurrences(frame, existing):
    """Multiset subtraction, not drop_duplicates(timestamp)."""
    remaining = Counter(row_key(row) for row in existing)
    times = {row[0] for row in existing}
    keep = np.ones(len(frame), dtype=bool)
    reused = conflicts = 0
    for pos in np.flatnonzero(frame.recorded_at.isin(times).to_numpy()):
        key = row_key(frame.iloc[pos].tolist())
        if remaining[key] > 0:
            remaining[key] -= 1; keep[pos] = False; reused += 1
        else:
            conflicts += 1
    return frame.loc[keep].copy(), reused, conflicts


def registry_hash(engine):
    with engine.connect() as conn:
        result = {}
        for table in ("ht9046mx_calibration_profile", "ht9046mx_active_calibration_profile"):
            rows = sorted(json.dumps(dict(r), sort_keys=True, default=str) for r in conn.execute(text(f"SELECT * FROM {table}")).mappings())
            result[table] = {"rows":len(rows), "sha256":hashlib.sha256("\n".join(rows).encode()).hexdigest()}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Bound files for technical rehearsal")
    parser.add_argument("--machines", nargs="+", choices=MACHINES, default=list(MACHINES), help="Disjoint machine processes may run in parallel")
    args = parser.parse_args()
    settings = get_settings()
    for url in (settings.database_url, settings.source_database_url):
        if make_url(url).host not in ("localhost", "127.0.0.1", "::1"):
            raise RuntimeError("LOCAL import only; target Server is not in scope")
    if settings.source_db_name != "ht9046mx_iot" or settings.source_table != "ht9046mx_readings" or settings.analytics_db_name != "ht9046mx_analytics":
        raise RuntimeError("Unexpected source/analytics target")
    archives, entries, handles = inventory(Path("C:/Users/Book/Downloads"))
    chosen = [e for e in entries if e["machine"] in args.machines and e["kind"] == "dynamic"]
    if args.limit is not None:
        if args.limit < 1: raise ValueError("limit must be positive")
        chosen = chosen[:args.limit]
    plan = {"version":VERSION, "archives":archives, "files":dict(Counter(e["machine"] for e in chosen)), "excluded_machine":"080", "static_excluded":True, "apply":args.apply}
    print(json.dumps(plan), flush=True)
    if not args.apply:
        for handle in handles: handle.close()
        return
    source = create_engine(settings.source_database_url, pool_pre_ping=True)
    analytics = create_engine(settings.database_url, pool_pre_ping=True)
    before = registry_hash(analytics)
    ledger_table = f"`{settings.analytics_db_name}`.`{LEDGER}`"
    with analytics.begin() as conn:
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS {LEDGER} (machine_number VARCHAR(60) NOT NULL, source_date DATE NOT NULL, "
            "file_sha256 CHAR(64) NOT NULL, importer_version VARCHAR(60) NOT NULL, receipt_json LONGTEXT NOT NULL, "
            "completed_at DATETIME(6) NOT NULL, PRIMARY KEY(machine_number,source_date)) ENGINE=InnoDB"))
    results = []; started = time.perf_counter()
    with source.connect() as conn:
        locks = [f"ht9046mx-local-history-v1-{m}" for m in sorted(set(args.machines))]
        acquired = []
        for lock in locks:
            if conn.execute(text("SELECT GET_LOCK(:lock,0)"), {"lock":lock}).scalar() != 1:
                for held in acquired:
                    conn.execute(text("SELECT RELEASE_LOCK(:lock)"), {"lock":held})
                raise RuntimeError("Another importer owns this local machine history lock")
            acquired.append(lock)
        conn.commit()
        try:
            secure = conn.execute(text("SELECT @@secure_file_priv")).scalar()
            if not secure:
                raise RuntimeError("Expected an existing restricted server import directory")
            root = Path(secure).resolve()
            if not root.is_dir():
                raise RuntimeError("Secure import directory unavailable")
            columns = {r["Field"] for r in conn.execute(text("SHOW COLUMNS FROM ht9046mx_readings")).mappings()}
            if columns != {"id", "machine_number", "recorded_at", *VALUE_COLUMNS}:
                raise RuntimeError("Source schema differs from exact wide contract")
            if conn.execute(text("SELECT ENGINE FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='ht9046mx_readings'")).scalar() != "InnoDB":
                raise RuntimeError("Atomic ingestion requires InnoDB")
            conn.commit()
            first_write = True
            for index, entry in enumerate(chosen, 1):
                file_start = time.perf_counter()
                with entry["handle"].open(entry["info"]) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                previous = conn.execute(text(f"SELECT file_sha256,importer_version,receipt_json FROM {ledger_table} WHERE machine_number=:m AND source_date=:day"), {"m":entry["machine"], "day":entry["date"]}).mappings().first()
                conn.commit()
                if previous:
                    if previous["file_sha256"] != digest or previous["importer_version"] != VERSION:
                        raise RuntimeError("Previously imported day changed; explicit reconciliation needed")
                    receipt = json.loads(previous["receipt_json"])
                    results.append({**receipt, "already_imported":True})
                    print(json.dumps({"file":index,"total":len(chosen),"machine":entry["machine"],"date":entry["date"],"already_imported":True}),flush=True)
                    continue
                # Check capacity only before a new write; an all-skipped retry
                # does not need space for another full telemetry import.
                minimum = (15 if first_write else 5)*1024**3
                if shutil.disk_usage(root).free < minimum:
                    raise RuntimeError("Insufficient free space for new rows; committed receipts remain resumable")
                first_write = False
                raw, stamps, controller = read_day(entry)
                frame = normalize(raw, stamps)
                if not frame.recorded_at.dt.strftime("%Y-%m-%d").eq(entry["date"]).all():
                    raise ValueError("Timestamp leaves declared source day")
                day = datetime.fromisoformat(entry["date"])
                names = aliases(entry["machine"])
                params = {f"a{i}":v for i,v in enumerate(names)}
                params.update({"start":day,"end":day+timedelta(days=1)})
                selected = ",".join(f"`{c}`" for c in frame.columns)
                existing = conn.execute(text(f"SELECT {selected} FROM ht9046mx_readings WHERE machine_number IN ({','.join(':'+k for k in params if k.startswith('a'))}) AND recorded_at>=:start AND recorded_at<:end"), params).all()
                conn.commit()
                new, reused, conflicts = reuse_occurrences(frame, existing)
                new.insert(0,"machine_number",entry["machine"])
                receipt = {"machine":entry["machine"],"date":entry["date"],"archive":entry["archive"],"member":entry["member"],"file_sha256":digest,
                    "controller_header":controller,"raw_rows":len(frame),"inserted_rows":len(new),"reused_identical_occurrences":reused,
                    "overlapping_nonidentical_occurrences":conflicts,"duplicate_timestamp_rows":int(stamps.duplicated(keep=False).sum()),
                    "out_of_order_steps":int(stamps.diff().dt.total_seconds().lt(0).sum()),"null_cells":int(frame.isna().sum().sum()),
                    "source_timezone_assumption":"Asia/Bangkok; stored source wall clock, not independently confirmed", "version":VERSION}
                temp = (root/f"ht9046mx-owner-history-{uuid.uuid4().hex}.tsv").resolve()
                if temp.parent != root: raise RuntimeError("Generated file escaped restricted directory")
                try:
                    # No control characters/quotes/backslashes in text; numeric
                    # missing values use MySQL's documented NULL marker.
                    new.to_csv(temp,sep="\t",index=False,header=False,na_rep="\\N",lineterminator="\n",date_format="%Y-%m-%d %H:%M:%S")
                    with conn.begin():
                        max_before = conn.execute(text("SELECT COALESCE(MAX(id),0) FROM ht9046mx_readings")).scalar()
                        sqlcols = ",".join(f"`{c}`" for c in new.columns)
                        if len(new):
                            conn.execute(text(f"LOAD DATA INFILE :path INTO TABLE ht9046mx_readings CHARACTER SET utf8mb4 FIELDS TERMINATED BY '\\t' OPTIONALLY ENCLOSED BY '\"' ESCAPED BY '\\\\' LINES TERMINATED BY '\\n' ({sqlcols})"), {"path":temp.as_posix()})
                            warnings = conn.execute(text("SHOW WARNINGS")).all()
                            if warnings: raise RuntimeError(f"LOAD DATA conversion warnings ({len(warnings)}); file rolled back")
                            actual = conn.execute(text("SELECT COUNT(*) FROM ht9046mx_readings WHERE id>:id AND machine_number=:m"), {"id":max_before,"m":entry["machine"]}).scalar()
                            if actual != len(new): raise RuntimeError("Inserted source count mismatch; file rolled back")
                        receipt["id_floor_exclusive"] = int(max_before)
                        receipt["id_ceiling_inclusive"] = int(conn.execute(text("SELECT COALESCE(MAX(id),0) FROM ht9046mx_readings")).scalar())
                        conn.execute(text(f"INSERT INTO {ledger_table} VALUES (:m,:day,:sha,:version,:receipt,:completed)"),
                            {"m":entry["machine"],"day":entry["date"],"sha":digest,"version":VERSION,"receipt":json.dumps(receipt,sort_keys=True),"completed":datetime.now(timezone.utc).replace(tzinfo=None)})
                finally:
                    # Only this run's exact generated file, never ZIP/source or
                    # the broad MySQL Uploads directory, is removed.
                    if temp.parent == root and temp.name.startswith("ht9046mx-owner-history-"):
                        temp.unlink(missing_ok=True)
                receipt["seconds"] = round(time.perf_counter()-file_start,3)
                results.append(receipt)
                print(json.dumps({"file":index,"total":len(chosen),**{k:receipt[k] for k in ("machine","date","raw_rows","inserted_rows","reused_identical_occurrences","overlapping_nonidentical_occurrences","seconds")}}),flush=True)
        finally:
            for held in acquired:
                conn.execute(text("SELECT RELEASE_LOCK(:lock)"), {"lock":held})
            conn.commit()
            for handle in handles:handle.close()
    after = registry_hash(analytics)
    if before != after: raise RuntimeError("Profile/Active registry changed concurrently; review before completion")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    summary = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"plan":plan,"files":results,"registry_before":before,"registry_after":after,"elapsed_seconds":time.perf_counter()-started}
    receipt_name = "receipt.json" if set(args.machines)==set(MACHINES) else "receipt-"+"-".join(sorted(set(args.machines)))+".json"
    if args.limit is not None:
        receipt_name = receipt_name.removesuffix(".json")+f"-limit{args.limit}.json"
    (OUTPUT/receipt_name).write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"completed_files":len(results),"new_rows_this_run":sum(r["inserted_rows"] for r in results if not r.get("already_imported")),"registry_unchanged":True,"elapsed_seconds":round(summary["elapsed_seconds"],2)}),flush=True)
    source.dispose(); analytics.dispose()


if __name__ == "__main__":main()
