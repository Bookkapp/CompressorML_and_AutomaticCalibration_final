"""Append the owner-requested MX041/058/081/080 ZIP history to local source.

Imports one daily file per atomic source+receipt transaction. Raw rows are
retained at their observed second; exact occurrences already in MySQL are
reused, while source duplicate occurrences and changed same-time rows remain.
The existing MySQL secure_file_priv is honored. New imports require 15 GiB
before the first daily transaction; resumed imports require 6 GiB before a
daily transaction to leave roughly 5 GiB after a large commit/binlog write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings
from notebooks.support.import_downloads_history import (
    LEDGER, OUTPUT, RAW_COLUMNS, VALUE_COLUMNS, normalize, registry_hash,
    reuse_occurrences,
)
from notebooks.support.october_three_machine_calibration import inventory as prior_inventory, read_day

MACHINES = ("041", "058", "081", "080")
VERSION = "local-raw-zip-import-v2"
DAILY_NAME = re.compile(r"(2026_\d{2}_\d{2})(_Static)?\.txt$")
EXPECTED_DAYS = {"041": 127, "058": 127, "081": 127, "080": 93}
EXPECTED_ROWS = {"041": 10_700_805, "058": 10_700_512, "081": 10_699_626, "080": 7_773_188}
EXPECTED_COLUMNS = {"id", "machine_number", "recorded_at", *VALUE_COLUMNS}
LEDGER_TABLE = "ht9046mx_history_import_file"


def machine_aliases(machine: str) -> tuple[str, ...]:
    return (machine, str(int(machine)), "MX" + machine, "MX-" + machine,
            "HT9046MX-" + machine, "HT9046MX" + machine)


def selected_inventory(downloads: Path):
    entries, handles, archives = [], [], []
    for machine in MACHINES[:3]:
        folder = downloads / ("MX" + machine)
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing download folder for MX{machine}")
        machine_files = 0
        for path in sorted(folder.glob("*.zip")):
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            archives.append({"archive": str(path.relative_to(downloads)), "bytes": path.stat().st_size,
                             "sha256": digest, "machine": machine})
            outer = zipfile.ZipFile(path)
            handles.append(outer)
            for item in outer.infolist():
                match = DAILY_NAME.search(item.filename.rsplit("/", 1)[-1])
                if not match:
                    continue
                entries.append({"archive": path.name, "nested": "", "member": item.filename,
                    "machine": machine, "date": match[1].replace("_", "-"),
                    "kind": "static" if match[2] else "dynamic", "bytes": item.file_size,
                    "crc32": item.CRC, "handle": outer, "info": item})
                if not match[2]:
                    machine_files += 1
        if machine_files != EXPECTED_DAYS[machine]:
            raise ValueError(f"MX{machine}: expected {EXPECTED_DAYS[machine]} canonical daily files, found {machine_files}")

    old_archives, old_entries, old_handles = prior_inventory(downloads)
    handles.extend(old_handles)
    for archive in old_archives:
        archives.append({**archive, "machine": "080-source-archive"})
    entries.extend(e for e in old_entries if e["machine"] == "080" and e["kind"] == "dynamic"
                   and e["archive"].startswith("HT9046MX-Compressor-Data-20261001"))
    counts = Counter(e["machine"] for e in entries if e["kind"] == "dynamic")
    if dict(counts) != EXPECTED_DAYS:
        raise ValueError(f"Expected daily file inventory differs: {dict(counts)}")
    keys = [(e["machine"], e["date"]) for e in entries if e["kind"] == "dynamic"]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate machine/date members; reconcile before importing")
    return archives, sorted(entries, key=lambda e: (e["date"], e["machine"]), reverse=True), handles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Append rows to the actual local MySQL source")
    parser.add_argument("--machines", nargs="+", choices=MACHINES, default=list(MACHINES))
    parser.add_argument("--start-date", help="Inclusive ISO date limit, e.g. 2026-07-01")
    parser.add_argument("--end-date", help="Inclusive ISO date limit, e.g. 2026-10-01")
    args = parser.parse_args()
    start_date = datetime.fromisoformat(args.start_date).date() if args.start_date else None
    end_date = datetime.fromisoformat(args.end_date).date() if args.end_date else None
    if start_date and end_date and start_date > end_date:
        parser.error("--start-date must be on or before --end-date")
    settings = get_settings()
    for url in (settings.database_url, settings.source_database_url):
        if make_url(url).host not in ("localhost", "127.0.0.1", "::1"):
            raise RuntimeError("This intake is restricted to the configured local MySQL instance")
    if (settings.source_db_name, settings.source_table, settings.analytics_db_name) != (
            "ht9046mx_iot", "ht9046mx_readings", "ht9046mx_analytics"):
        raise RuntimeError("Unexpected source/analytics destination")

    downloads = Path("C:/Users/Book/Downloads")
    archives, entries, handles = selected_inventory(downloads)
    chosen = [e for e in entries if e["machine"] in args.machines and e["kind"] == "dynamic"
              and (start_date is None or datetime.fromisoformat(e["date"]).date() >= start_date)
              and (end_date is None or datetime.fromisoformat(e["date"]).date() <= end_date)]
    if not chosen:
        raise ValueError("No dynamic daily files match the selected machine/date scope")
    daily_counts = dict(Counter(e["machine"] for e in chosen))
    plan = {"version": VERSION, "apply": args.apply, "files": daily_counts,
            "dates": {m: [min(e["date"] for e in chosen if e["machine"] == m),
                          max(e["date"] for e in chosen if e["machine"] == m)] for m in args.machines},
            "full_archive_raw_rows": {m: EXPECTED_ROWS[m] for m in args.machines}, "archives": archives,
            "static_and_temp_excluded": True, "order": "balanced newest-to-oldest daily round-robin"}
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    if not args.apply:
        for handle in handles:
            handle.close()
        return

    source = create_engine(settings.source_database_url, pool_pre_ping=True)
    analytics = create_engine(settings.database_url, pool_pre_ping=True)
    registry_before = registry_hash(analytics)
    ledger = f"`{settings.analytics_db_name}`.`{LEDGER_TABLE}`"
    receipts, started = [], time.perf_counter()
    lock_names = [f"ht9046mx-local-history-v2-{m}" for m in sorted(set(args.machines))]
    with source.connect() as conn:
        locked = []
        try:
            for name in lock_names:
                if conn.execute(text("SELECT GET_LOCK(:name,0)"), {"name": name}).scalar() != 1:
                    raise RuntimeError(f"Another v2 importer holds {name}")
                locked.append(name)
            conn.commit()
            secure = conn.execute(text("SELECT @@secure_file_priv")).scalar()
            if not secure:
                raise RuntimeError("MySQL has no restricted secure_file_priv directory")
            secure_dir = Path(secure).resolve()
            if not secure_dir.is_dir():
                raise RuntimeError("MySQL secure import directory is unavailable")
            fields = {r["Field"] for r in conn.execute(text(f"SHOW COLUMNS FROM `{settings.source_table}`")).mappings()}
            if fields != EXPECTED_COLUMNS:
                raise RuntimeError("Source table columns differ from the validated 82-column contract")
            engine = conn.execute(text("SELECT ENGINE FROM information_schema.tables WHERE table_schema=:db AND table_name=:table"),
                                  {"db": settings.source_db_name, "table": settings.source_table}).scalar()
            if engine != "InnoDB":
                raise RuntimeError("Daily atomic source+receipt commit requires InnoDB")
            conn.commit()
            # Apply the higher start-up reserve only when this intake has not
            # committed any daily receipt before. A resumed import already
            # has durable day-level checkpoints and should use the normal
            # six-GiB start threshold (to preserve a five-GiB post-commit
            # floor) rather than resetting the 15-GiB gate.
            machine_params = {f"m{i}": machine for i, machine in enumerate(args.machines)}
            prior_receipts = conn.execute(text(
                f"SELECT COUNT(*) FROM {ledger} WHERE importer_version=:version "
                f"AND machine_number IN ({','.join(':'+k for k in machine_params)})"
            ), {"version": VERSION, **machine_params}).scalar()
            first_new_file = not bool(prior_receipts)
            for index, entry in enumerate(chosen, 1):
                day_start = datetime.fromisoformat(entry["date"])
                candidates = machine_aliases(entry["machine"])
                keys = {f"a{i}": alias for i, alias in enumerate(candidates)}
                keys.update(start=day_start, end=day_start + timedelta(days=1))
                previous = conn.execute(text(f"SELECT file_sha256,importer_version,receipt_json FROM {ledger} "
                    "WHERE machine_number=:m AND source_date=:day"), {"m": entry["machine"], "day": day_start.date()}).mappings().first()
                conn.commit()
                with entry["handle"].open(entry["info"]) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if previous:
                    if previous["file_sha256"] != digest or previous["importer_version"] != VERSION:
                        raise RuntimeError(f"MX{entry['machine']} {entry['date']} has a conflicting prior receipt")
                    receipts.append({**json.loads(previous["receipt_json"]), "already_imported": True})
                    continue

                free = shutil.disk_usage(secure_dir).free
                # A completed day can consume several hundred MiB once ROW
                # binlogs are included. Keep one GiB of transaction headroom
                # above the desired five-GiB minimum free-space floor.
                reserve_gib = 15 if first_new_file else 6
                reserve = reserve_gib * 1024**3
                if free < reserve:
                    print(json.dumps({"paused": True, "completed_files": len(receipts),
                        "next_machine": entry["machine"], "next_date": entry["date"],
                        "free_gib": round(free / 1024**3, 2), "minimum_reserve_gib": reserve_gib}), flush=True)
                    break
                first_new_file = False

                raw, stamps, controller = read_day(entry)
                frame = normalize(raw, stamps)
                if stamps.isna().any() or not frame.recorded_at.dt.strftime("%Y-%m-%d").eq(entry["date"]).all():
                    raise ValueError("Invalid timestamp or row crossing its declared daily file")
                select_fields = ",".join(f"`{column}`" for column in frame.columns)
                params = {**keys, "start": day_start, "end": day_start + timedelta(days=1)}
                existing = conn.execute(text(f"SELECT {select_fields} FROM `{settings.source_table}` "
                    f"WHERE `{settings.source_machine_column}` IN ({','.join(':'+k for k in keys)}) "
                    f"AND `{settings.source_timestamp_column}`>=:start AND `{settings.source_timestamp_column}`<:end"), params).all()
                conn.commit()
                new_rows, reused, overlaps = reuse_occurrences(frame, existing)
                new_rows.insert(0, "machine_number", entry["machine"])
                receipt = {"machine": entry["machine"], "date": entry["date"], "archive": entry["archive"],
                    "member": entry["member"], "file_sha256": digest, "importer_version": VERSION,
                    "controller_header": controller, "raw_rows": len(frame), "inserted_rows": len(new_rows),
                    "reused_identical_occurrences": reused, "overlapping_nonidentical_occurrences": overlaps,
                    "duplicate_timestamp_rows": int(stamps.duplicated(keep=False).sum()),
                    "out_of_order_steps": int(stamps.diff().dt.total_seconds().lt(0).sum()),
                    "null_cells": int(frame.isna().sum().sum()),
                    "source_timezone_assumption": "Asia/Bangkok source wall clock; not independently confirmed"}
                temporary = (secure_dir / f"ht9046mx-owner-history-v2-{uuid.uuid4().hex}.tsv").resolve()
                if temporary.parent != secure_dir:
                    raise RuntimeError("Generated import file escaped secure_file_priv")
                try:
                    new_rows.to_csv(temporary, sep="\t", index=False, header=False, na_rep="\\N",
                                    lineterminator="\n", date_format="%Y-%m-%d %H:%M:%S")
                    with conn.begin():
                        max_id = conn.execute(text(f"SELECT COALESCE(MAX(id),0) FROM `{settings.source_table}`")).scalar()
                        if len(new_rows):
                            columns = ",".join(f"`{column}`" for column in new_rows.columns)
                            conn.execute(text(f"LOAD DATA INFILE :path INTO TABLE `{settings.source_table}` CHARACTER SET utf8mb4 "
                                "FIELDS TERMINATED BY '\\t' OPTIONALLY ENCLOSED BY '\"' ESCAPED BY '\\\\' "
                                f"LINES TERMINATED BY '\\n' ({columns})"), {"path": temporary.as_posix()})
                            warnings = conn.execute(text("SHOW WARNINGS")).all()
                            if warnings:
                                raise RuntimeError(f"MySQL conversion warnings; {entry['date']} transaction rolled back")
                            loaded = conn.execute(text(f"SELECT COUNT(*) FROM `{settings.source_table}` WHERE id>:id AND "
                                f"`{settings.source_machine_column}`=:machine"), {"id": max_id, "machine": entry["machine"]}).scalar()
                            if loaded != len(new_rows):
                                raise RuntimeError("Inserted source row count differs; daily transaction rolled back")
                        receipt["id_floor_exclusive"] = int(max_id)
                        receipt["id_ceiling_inclusive"] = int(conn.execute(text(f"SELECT COALESCE(MAX(id),0) FROM `{settings.source_table}`")).scalar())
                        conn.execute(text(f"INSERT INTO {ledger} VALUES (:m,:day,:sha,:version,:receipt,:completed)"), {
                            "m": entry["machine"], "day": day_start.date(), "sha": digest, "version": VERSION,
                            "receipt": json.dumps(receipt, sort_keys=True),
                            "completed": datetime.now(timezone.utc).replace(tzinfo=None)})
                finally:
                    if temporary.parent == secure_dir and temporary.name.startswith("ht9046mx-owner-history-v2-"):
                        temporary.unlink(missing_ok=True)
                receipts.append(receipt)
                free_after = shutil.disk_usage(secure_dir).free
                print(json.dumps({"file": index, "total": len(chosen), "machine": entry["machine"],
                    "date": entry["date"], "raw_rows": receipt["raw_rows"],
                    "inserted_rows": receipt["inserted_rows"], "reused": reused, "overlap": overlaps,
                    "free_gib": round(free_after / 1024**3, 2),
                    "seconds": round(time.perf_counter() - started, 2)}), flush=True)
        finally:
            for name in locked:
                conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
            conn.commit()
            for handle in handles:
                try:
                    handle.close()
                except Exception:
                    pass

    registry_after = registry_hash(analytics)
    registry_unchanged = registry_before == registry_after
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = {"completed_at_utc": datetime.now(timezone.utc).isoformat(), "plan": plan,
        "completed_receipts": len(receipts), "new_rows": sum(r.get("inserted_rows", 0) for r in receipts),
        "reused_rows": sum(r.get("reused_identical_occurrences", 0) for r in receipts),
        "registry_unchanged": registry_unchanged, "registry_before": registry_before,
        "registry_after": registry_after, "free_gib": round(shutil.disk_usage(secure_dir).free / 1024**3, 2),
        "elapsed_seconds": round(time.perf_counter() - started, 2), "receipts": receipts}
    machine_suffix = "" if set(args.machines) == set(MACHINES) else "-" + "-".join(sorted(set(args.machines)))
    date_suffix = ("-" + (args.start_date or "start").replace("-", "") + "-" +
                   (args.end_date or "end").replace("-", "")) if (args.start_date or args.end_date) else ""
    output_file = OUTPUT / ("requested-machines-v2" + machine_suffix + date_suffix + ".json")
    output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("completed_receipts", "new_rows", "reused_rows",
          "registry_unchanged", "free_gib", "elapsed_seconds")}, ensure_ascii=False), flush=True)
    source.dispose()
    analytics.dispose()


if __name__ == "__main__":
    main()
