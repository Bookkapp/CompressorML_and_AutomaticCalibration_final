"""Read-only source intake; write separate, auditable analysis partitions.

No fitting, threshold selection, automatic health labels or production activation.
Time is retained as source-naive time. Source units are retained without scaling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
import tempfile
import shutil
from pathlib import Path
import polars as pl

VERSION = "external_intake_v2"
MIN_SAMPLES_PER_MINUTE = 55
MAX_SAMPLES_PER_MINUTE = 60
MAX_INTERNAL_GAP_SECONDS = 5
FOLDERS = {"MX_007": "007", "MX017": "017", "MX057": "057", "MX070": "070",
           "Clean Data MX12": "012", "Clean Data MX25": "025"}
TAGS = ["Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "Valve", "Status", "TempHi", "TempLo", "SV", "Busy"]
COLS = ["Status"] + [f"{tag}_{m}" for m in range(1, 9) for tag in TAGS]
NUMERIC = [c for c in COLS if not c.startswith(("Status", "SV"))]
NEW_MACHINES = {"007", "012", "025"}


def sources(root, folder):
    """Materialize one ZIP member at a time under a disposable scratch path."""
    for path in sorted((root / folder).rglob("*")):
        if not path.is_file():
            continue
        source = path.relative_to(root).as_posix()
        yield path, source, None
        if path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path) as z:
                for entry in z.infolist():
                    if entry.is_dir():
                        continue
                    # Ignore internal directories for the temporary path; never extractall.
                    name = Path(entry.filename.replace('\\', '/')).name
                    with tempfile.TemporaryDirectory(prefix='ht9046mx_zip_') as temp:
                        target = Path(temp) / name
                        with z.open(entry) as src, target.open('wb') as dst:
                            shutil.copyfileobj(src, dst)
                        yield target, source + '::' + entry.filename, source


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def kind(path):
    name = path.name.lower()
    if ".tmp." in name:
        return "TEMPORARY_COPY"
    if name.endswith(".zip"):
        return "ARCHIVE_PENDING"
    if "static" in name:
        return "STATIC_SEPARATE"
    if re.search(r"_\d{2}_\d{2}_\d{2}_(am|pm)", name):
        return "EVENT_FRAGMENT"
    if re.match(r"20\d{2}_\d{2}_\d{2}(?:_clean(?:ed)?)?\.(csv|txt)$", name):
        return "DAILY_TELEMETRY"
    return "UNKNOWN_FORMAT"


def read_daily(path):
    match = re.search(r"(20\d{2})_(\d{2})_(\d{2})", path.name)
    date = "-".join(match.groups())
    header = None
    # Count LF-delimited binary lines: these controller logs can use CR-CR-LF.
    # Universal-newline text reading expands that into two logical lines.
    with path.open("rb") as f:
        for i in range(20):
            line = f.readline()
            if b"Hp_1st_1" in line and b"Time" in line:
                header = i
                break
    if header is None:
        raise ValueError("No telemetry header")
    # Header discovery counts physical lines, including empty preamble lines.
    raw = pl.read_csv(path, skip_lines=header, infer_schema=False, truncate_ragged_lines=False)
    raw = raw.rename({c: c.strip() for c in raw.columns})
    missing = sorted(set(COLS + ["Time"]) - set(raw.columns))
    if missing:
        raise ValueError(f"Missing required tags: {missing}")
    raw = raw.filter(pl.col("Time").is_not_null())
    day = pl.col("Date").str.strip_chars() if "Date" in raw.columns else pl.lit(date)
    raw = raw.with_columns(
        pl.concat_str([day, pl.col("Time").str.strip_chars()], separator=" ")
        .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).alias("recorded_at"),
        *[pl.col(c).str.strip_chars().cast(pl.Float64, strict=False) for c in NUMERIC],
        *[pl.col(c).str.strip_chars() for c in COLS if c not in NUMERIC],
    ).select("recorded_at", *COLS)
    return raw, date


def canonical_primary(paths):
    return pl.concat([pl.read_parquet(p, columns=["recorded_at"] + COLS) for p in paths]).with_columns(
        *[pl.col(c).cast(pl.Float64) for c in NUMERIC],
        *[pl.col(c).str.strip_chars() for c in COLS if c not in NUMERIC],
    )


def minute_and_stats(raw, machine, source):
    parts, stats = [], []
    for m in range(1, 9):
        rename = {f"{t}_{m}": n for t, n in zip(TAGS, ["hp1", "lp1", "hp2", "lp2", "valve", "module_status", "temphi", "templo", "sv", "busy"])}
        f = raw.select("recorded_at", pl.col("Status").alias("global_status"), *rename).rename(rename)
        # Broad validity excludes obvious sentinel temperatures; not a physical safety envelope.
        f = f.with_columns((pl.all_horizontal([pl.col(c).is_finite() for c in ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo", "busy"]])
                           & (pl.col("temphi") > -199) & (pl.col("templo") > -199)).fill_null(False).alias("valid_numeric"))
        f = f.with_columns(((pl.col("global_status") == "Run") & (pl.col("module_status") == "On")
                           & (pl.col("busy") == 0) & (pl.col("valve") >= 0)
                           & pl.col("sv").is_in(["Off", "On"]) & pl.col("valid_numeric")).fill_null(False).alias("candidate_sample"))
        for sv in ["Off", "On"]:
            q = f.filter(pl.col("candidate_sample") & (pl.col("sv") == sv))
            if q.height:
                stats.append({"machine": machine, "module": m, "sv": sv, "date": str(raw["recorded_at"].min().date()),
                              "source": source, "candidate_seconds": q.height, "hp2_median": q["hp2"].median(),
                              "hp2_p05": q["hp2"].quantile(.05), "hp2_p95": q["hp2"].quantile(.95),
                              "hp2_below_180_pct": 100 * (q["hp2"] < 180).mean()})
        f = f.with_columns(pl.col("recorded_at").dt.truncate("1m").alias("minute"))
        g = f.group_by("minute", maintain_order=True).agg(
            pl.len().alias("samples"), pl.col("recorded_at").last().alias("available_at"),
            *[pl.col(c).last() for c in ["global_status", "module_status", "sv", "busy", "hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo"]],
            pl.col("candidate_sample").all().alias("all_samples_candidate"),
            (pl.col("sv").n_unique() == 1).alias("sv_pure"),
            (pl.col("recorded_at").diff().dt.total_seconds().drop_nulls().max().fill_null(0) <= MAX_INTERNAL_GAP_SECONDS).alias("continuous"),
        ).with_columns(pl.lit(machine).alias("machine_number"), pl.lit(m).cast(pl.Int8).alias("module"),
                       pl.lit(source).alias("source_file"))
        g = g.with_columns(((pl.col("samples") >= MIN_SAMPLES_PER_MINUTE) &
                            (pl.col("samples") <= MAX_SAMPLES_PER_MINUTE) &
                            pl.col("continuous") & pl.col("sv_pure") &
                            pl.col("all_samples_candidate")).alias("intake_quality_minute"))
        # Compatibility alias for v1 readers. This is EDA data quality, not baseline approval.
        g = g.with_columns(pl.col("intake_quality_minute").alias("intake_candidate_minute"))
        parts.append(g)
    return pl.concat(parts), stats


def run_intake(external_root, primary_root, output):
    external_root, primary_root, output = map(Path, (external_root, primary_root, output))
    if not external_root.is_dir() or not primary_root.is_dir():
        raise FileNotFoundError("Both source roots must exist")
    # Avoid accidental writes to either source tree.
    for source in (external_root, primary_root):
        if output.resolve().is_relative_to(source.resolve()):
            raise ValueError("Output must be outside the source roots")
    output.mkdir(parents=True, exist_ok=True)
    (output / "canonical_novel").mkdir(exist_ok=True)
    primary_index = {}
    for p in primary_root.rglob("*.parquet"):
        match = re.search(r"machine=(\d+).*year=(\d+).*month=(\d+).*day=(\d+)", p.as_posix())
        if match:
            m, y, mo, d = match.groups()
            primary_index.setdefault((m.zfill(3), f"{y}-{mo}-{d}"), []).append(p)
    manifest, minutes, daily, archives, errors = [], [], [], [], []
    seen_files = {}
    telemetry_count = 0
    for folder, machine in FOLDERS.items():
        for p, source_name, archive_parent in sources(external_root, folder):
            digest = sha256(p)
            row = {"source": source_name, "archive_parent": archive_parent, "machine": machine, "kind": kind(p),
                   "bytes": p.stat().st_size, "sha256": digest, "timezone": "SOURCE_NAIVE_UNCONFIRMED",
                   "units": "SOURCE_UNCHANGED_PSI_BASIS_UNCONFIRMED", "train_enabled": False}
            identity = (machine, digest)
            if identity in seen_files:
                row["duplicate_file_of"] = seen_files[identity]
                row["role"] = "DUPLICATE_FILE_EXCLUDED"
                manifest.append(row)
                continue
            seen_files[identity] = row["source"]
            if row["kind"] != "DAILY_TELEMETRY":
                row["role"] = "SEPARATE_REVIEW"
                if row["kind"] == "ARCHIVE_PENDING":
                    with zipfile.ZipFile(p) as z:
                        archives.extend({"archive": row["source"], "member": x.filename, "bytes_uncompressed": x.file_size,
                                         "crc32": x.CRC, "audit_lookup": row["source"] + '::' + x.filename} for x in z.infolist() if not x.is_dir())
                manifest.append(row)
                continue
            try:
                raw, date = read_daily(p)
                row.update(date=date, parsed_rows=raw.height, invalid_timestamps=raw["recorded_at"].null_count())
                valid = raw.drop_nulls("recorded_at")
                row["out_of_order_steps"] = int((valid["recorded_at"].diff().dt.total_seconds() < 0).sum())
                row["duplicate_timestamp_rows"] = valid.height - valid["recorded_at"].n_unique()
                unique_rows = valid.unique(maintain_order=True)
                conflicts = unique_rows.group_by("recorded_at").len().filter(pl.col("len") > 1).select("recorded_at")
                row["conflicting_timestamp_keys"] = conflicts.height
                valid = unique_rows.join(conflicts, on="recorded_at", how="anti").sort("recorded_at")
                row["date_mismatch_rows"] = valid.filter(pl.col("recorded_at").dt.strftime("%Y-%m-%d") != date).height
                if row["date_mismatch_rows"]:
                    raise ValueError("Date in contents disagrees with filename")
                row.update(first_timestamp=str(valid["recorded_at"].min()), last_timestamp=str(valid["recorded_at"].max()),
                           unique_rows=valid.height,
                           cadence_1s_pct=100 * (valid["recorded_at"].diff().dt.total_seconds().drop_nulls() == 1).mean())
                overlap_paths = primary_index.get((machine, date), [])
                row.update(overlap_rows=0, overlap_equal_rows=0, overlap_conflict_rows=0)
                novel = valid
                if overlap_paths:
                    primary = canonical_primary(overlap_paths).unique(maintain_order=True)
                    # No many-to-many expansion: ambiguous primary keys are counted separately.
                    pk = primary.group_by("recorded_at").len()
                    row["primary_ambiguous_keys"] = pk.filter(pl.col("len") > 1).height
                    comparable = primary.join(pk.filter(pl.col("len") == 1).select("recorded_at"), on="recorded_at")
                    joined = valid.join(comparable, on="recorded_at", suffix="__primary")
                    equal = joined.select(pl.all_horizontal([pl.col(c).eq_missing(pl.col(c + "__primary")) for c in COLS]).sum()).item()
                    overlap = valid.join(primary.select("recorded_at").unique(), on="recorded_at", how="semi").height
                    row.update(overlap_rows=overlap, overlap_equal_rows=equal, overlap_conflict_rows=joined.height-equal,
                               overlap_unresolved_rows=overlap-joined.height)
                    novel = valid.join(primary.select("recorded_at").unique(), on="recorded_at", how="anti")
                row["novel_rows"] = novel.height
                row["role"] = "RETROSPECTIVE_NEW_MACHINE_REVIEW" if machine in NEW_MACHINES else "HISTORICAL_EXTENSION_REVIEW"
                if not novel.height:
                    row["role"] = "PRIMARY_OVERLAP_EXCLUDED"
                if novel.height:
                    name = f"MX{machine}_{date}_{digest[:12]}.parquet"
                    target = output / "canonical_novel" / name
                    novel.with_columns(pl.lit(machine).alias("machine_number"), pl.lit(row["source"]).alias("source_file")).write_parquet(target, compression="zstd")
                    row["canonical_partition"] = "canonical_novel/" + name
                    minute, stats = minute_and_stats(novel, machine, row["source"])
                    minutes.append(minute)
                    daily.extend(stats)
                telemetry_count += 1
                if telemetry_count % 20 == 0:
                    print(f"Audited {telemetry_count} daily files", flush=True)
            except Exception as exc:
                row["role"] = "PARSE_OR_SCHEMA_REVIEW"
                row["error"] = str(exc)
                errors.append({"source": row["source"], "error": str(exc)})
            manifest.append(row)
    pl.from_dicts(manifest, infer_schema_length=None).write_csv(output / "source_manifest.csv")
    if archives:
        pl.from_dicts(archives).write_csv(output / "archive_inventory.csv")
    if daily:
        pl.from_dicts(daily).write_csv(output / "daily_module_sv_pressure.csv")
    if minutes:
        combined = pl.concat(minutes).sort("machine_number", "module", "minute")
        # Retain duplicate-minute evidence; exclude these from candidate eligibility.
        combined = combined.with_columns(pl.len().over("machine_number", "module", "minute").alias("minute_key_count"))
        combined = combined.with_columns((pl.col("intake_quality_minute") & (pl.col("minute_key_count") == 1)).alias("intake_quality_minute"))
        combined = combined.with_columns(pl.col("intake_quality_minute").alias("intake_candidate_minute"))
        combined.write_parquet(output / "external_minute_module_state.parquet", compression="zstd")
    summary = {"version": VERSION, "source_root": str(external_root), "primary_root": str(primary_root),
               "source_files": len(manifest), "daily_files_audited": telemetry_count, "errors": errors,
               "parsed_rows": sum(x.get("parsed_rows", 0) for x in manifest),
               "novel_rows": sum(x.get("novel_rows", 0) for x in manifest),
               "overlap_rows": sum(x.get("overlap_rows", 0) for x in manifest),
               "overlap_equal_rows": sum(x.get("overlap_equal_rows", 0) for x in manifest),
               "overlap_conflict_rows": sum(x.get("overlap_conflict_rows", 0) for x in manifest),
               "archive_members": len(archives),
               "archive_daily_audited": sum(bool(x.get('archive_parent')) and 'novel_rows' in x for x in manifest),
               "archive_members_pending": sum(bool(x.get('archive_parent')) and x.get('role') in ['SEPARATE_REVIEW','PARSE_OR_SCHEMA_REVIEW'] for x in manifest), "train_enabled": False,
               "minute_module_rows": combined.height if minutes else 0,
               "quality_minutes": int(combined["intake_quality_minute"].sum()) if minutes else 0,
               "quality_minute_rule": {"minimum_samples": MIN_SAMPLES_PER_MINUTE,
                                       "maximum_samples": MAX_SAMPLES_PER_MINUTE,
                                       "maximum_internal_gap_seconds": MAX_INTERNAL_GAP_SECONDS},
               "limits": ["Units and source timezone require confirmation", "Service epochs and healthy labels absent",
                          "ZIP daily telemetry audited; static, fragments and temporary copies excluded",
                          "New machines are historical external evidence, not prospective future tests",
                          "Quality minutes are EDA-only and require later settling/service gates before baseline fitting",
                          "Existing model tests and thresholds were not changed; no retraining performed"]}
    (output / "analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "artifact_checksums.json").write_text(json.dumps({p.name: sha256(p) for p in output.iterdir() if p.is_file() and p.name != "artifact_checksums.json"}, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-root", required=True)
    parser.add_argument("--primary-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_intake(args.external_root, args.primary_root, args.output)
