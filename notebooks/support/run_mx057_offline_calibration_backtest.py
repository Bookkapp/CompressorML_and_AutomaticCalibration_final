"""Offline MX057 calibration backtest using historical handler exports only.

This is a read-only source experiment.  It deliberately excludes the partial
2026-08-10 export and never writes a Server profile, database row or PLC value.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(r"C:\Users\Book\OneDrive\เดสก์ท็อป\Data Analysis\MX057")
OUTPUT = ROOT / "notebooks" / "outputs" / "mx057_offline_calibration_backtest_v4_confirmed_state"
SHADOW_START = pd.Timestamp("2026-08-07 00:00:00")
SOURCE_END_EXCLUSIVE = pd.Timestamp("2026-08-10 00:00:00")

sys.path.insert(0, str(ROOT))
from apps.api.app.calibration import FEATURES, _state_records, build_candidate_profiles  # noqa: E402


@dataclass(frozen=True)
class SourceItem:
    label: str
    date: pd.Timestamp
    content: bytes


def source_items() -> list[SourceItem]:
    """Use the most recent available historical days, excluding partial Aug 10."""
    items: list[SourceItem] = []
    may_zip = DATA_ROOT / "2026_05.zip"
    with zipfile.ZipFile(may_zip) as archive:
        for member in archive.namelist():
            if not member.endswith(".txt") or "static" in member.casefold():
                continue
            date = pd.Timestamp(member.rsplit("/", 1)[-1].replace(".txt", "").replace("_", "-"))
            if date >= pd.Timestamp("2026-05-12"):
                items.append(SourceItem(f"{may_zip}!{member}", date, archive.read(member)))
    for path in sorted(DATA_ROOT.glob("2026_*/*.txt")):
        date = pd.Timestamp(path.stem.replace("_", "-"))
        if date < SOURCE_END_EXCLUSIVE:
            items.append(SourceItem(str(path), date, path.read_bytes()))
    return sorted(items, key=lambda item: (item.date, item.label))


def read_export(item: SourceItem) -> pd.DataFrame:
    lines = item.content.decode("utf-8-sig", errors="replace").splitlines()
    header_index = next(index for index, line in enumerate(lines) if line.split(",", 1)[0].strip() == "Time")
    frame = pd.read_csv(io.StringIO("\n".join(lines[header_index:])), skipinitialspace=True)
    frame.columns = [str(column).strip() for column in frame.columns]
    timestamp = pd.to_datetime(item.date.strftime("%Y-%m-%d") + " " + frame["Time"].astype(str).str.strip(), errors="coerce")
    frame.index = timestamp
    return frame.loc[frame.index.notna()].copy()


def minute_wide(frame: pd.DataFrame) -> pd.DataFrame:
    index = pd.date_range(frame.index.min().floor("min"), frame.index.max().floor("min"), freq="min")
    columns: dict[str, object] = {"minute": index, "machine_number": "MX057"}
    global_status = frame["Status"].astype(str).str.strip()
    columns["global_status_min"] = global_status.resample("min").min().reindex(index).to_numpy()
    columns["global_status_max"] = global_status.resample("min").max().reindex(index).to_numpy()
    raw_names = {"hp1": "Hp_1st", "lp1": "Lp_1st", "hp2": "Hp_2nd", "lp2": "Lp_2nd", "valve": "Valve", "temphi": "TempHi", "templo": "TempLo"}
    for module in range(1, 9):
        for output, raw in raw_names.items():
            series = pd.to_numeric(frame[f"{raw}_{module}"], errors="coerce")
            columns[f"m{module}_{output}"] = series.resample("min").mean().reindex(index).to_numpy()
        for output, raw in {"status": "Status", "busy": "Busy", "sv": "SV"}.items():
            series = frame[f"{raw}_{module}"].astype(str).str.strip()
            columns[f"m{module}_{output}_min"] = series.resample("min").min().reindex(index).to_numpy()
            columns[f"m{module}_{output}_max"] = series.resample("min").max().reindex(index).to_numpy()
    return pd.DataFrame(columns)


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        source_sv_on_values="On,1,True",
        source_sv_off_values="Off,0,False",
        source_busy_normal_values="0,Off,False",
        source_compressor_on_status="Run",
        source_module_on_status="On",
        profile_settle_minutes=3,
        profile_min_calibration_windows=200,
        profile_min_calibration_days=7,
        profile_quarantine_z=8.0,
        profile_max_quarantine_pct=5.0,
        profile_max_half_shift_rz=1.5,
        profile_shadow_days=3,
        profile_min_shadow_windows=200,
        profile_max_shadow_flag_pct=1.0,
        profile_state_contract_version="owner-confirmed-cold-state-v2",
        profile_controller_codebook_version="UNVERIFIED_OFFLINE_BACKTEST",
        profile_service_epoch_version="UNVERIFIED_OFFLINE_BACKTEST",
        source_timezone="Asia/Bangkok",
    )


def render_shadow(profiles: list[dict]) -> None:
    selected = [item for item in profiles if not item["shadow"].empty]
    fig, axes = plt.subplots(4, 2, figsize=(16, 14), sharex=True)
    for axis, module in zip(axes.flat, range(1, 9)):
        candidates = [item for item in selected if item["key"]["module"] == module]
        if not candidates:
            axis.set_title(f"Module {module}: no qualified shadow windows")
            axis.axis("off")
            continue
        for item in candidates:
            shadow = item["shadow"]
            below = shadow.loc[~shadow["raw_flag"]]
            above = shadow.loc[shadow["raw_flag"]]
            label = f"SV {item['key']['sv_state']}"
            axis.plot(below["minute"], below["deviation_score"], color="#247ba0", lw=.7, label=f"{label}: below")
            axis.scatter(above["minute"], above["deviation_score"], color="#c62828", s=8, label=f"{label}: above")
            threshold = item["threshold"]["deviation_score_q995"]
            if threshold is not None:
                axis.axhline(threshold, color="#616161", ls="--", lw=.8)
        axis.set_title(f"MX057 Module {module}")
        axis.set_ylabel("local deviation score")
        axis.grid(alpha=.2)
    axes[0, 0].legend(fontsize=7, ncol=2)
    fig.suptitle("MX057 offline backtest — 7–9 Aug 2026 shadow only\nconfirmed Cold gate: Compressor ON, Busy=0, SV=Off; blue: below threshold; red: above", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUTPUT / "mx057_shadow_scores.png", dpi=160)
    plt.close(fig)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    items = source_items()
    wide_parts: list[pd.DataFrame] = []
    source_rows: list[dict] = []
    for item in items:
        raw = read_export(item)
        source_rows.append({"source": item.label, "date": item.date.date().isoformat(), "raw_rows": len(raw), "unique_seconds": int(raw.index.nunique()), "sha256": hashlib.sha256(item.content).hexdigest()})
        wide_parts.append(minute_wide(raw))
    wide = pd.concat(wide_parts, ignore_index=True)
    duplicate_wide_minutes = int(wide.duplicated(["minute", "machine_number"]).sum())
    if duplicate_wide_minutes:
        raise RuntimeError(f"Duplicate machine-minute rows: {duplicate_wide_minutes}")
    qualified = _state_records(wide, settings())
    qualified = qualified.loc[qualified["minute"] < SOURCE_END_EXCLUSIVE].copy()
    profiles = build_candidate_profiles(qualified, settings(), SHADOW_START.to_pydatetime())
    rows: list[dict] = []
    points: list[pd.DataFrame] = []
    for item in profiles:
        row = {**item["key"], "status": item["status"], "reasons": ";".join(item["reasons"]), "calibration_windows": len(item["calibration"]), "retained_windows": len(item["retained"]), "shadow_windows": len(item["shadow"]), "calibration_days": int(item["calibration"]["day"].nunique()), "shadow_days": int(item["shadow"]["day"].nunique()), "quarantine_pct": item["quarantine_pct"], **item["validation"]}
        rows.append(row)
        if not item["shadow"].empty:
            part = item["shadow"][["minute", "deviation_score", "threshold_value", "raw_flag", "persistent_flag"]].copy()
            part = part.assign(**item["key"], profile_status=item["status"])
            points.append(part)
    profiles_frame = pd.DataFrame(rows).sort_values(["module", "sv_state", "state_code"])
    points_frame = pd.concat(points, ignore_index=True) if points else pd.DataFrame()
    profiles_frame.to_csv(OUTPUT / "profile_summary.csv", index=False)
    points_frame.to_csv(OUTPUT / "shadow_points.csv", index=False)
    pd.DataFrame(source_rows).to_csv(OUTPUT / "source_manifest.csv", index=False)
    render_shadow(profiles)
    eligible = profiles_frame.loc[profiles_frame["status"].eq("READY_FOR_APPROVAL"), ["module", "sv_state", "state_code"]]
    dry_run = {"operation": "APPROVAL_DRY_RUN_ONLY", "actual_server_or_database_activation": False, "eligible_profile_keys": eligible.to_dict(orient="records"), "not_eligible_count": int(len(profiles_frame) - len(eligible))}
    (OUTPUT / "approval_dry_run.json").write_text(json.dumps(dry_run, indent=2), encoding="utf-8")
    summary = {"scope": {"machine": "MX057", "timezone_assumption": "Asia/Bangkok", "source_days": len(items), "source_start": min(item.date for item in items).date().isoformat(), "source_end_exclusive": SOURCE_END_EXCLUSIVE.date().isoformat(), "shadow_start": SHADOW_START.date().isoformat(), "shadow_end": "2026-08-09"}, "quality": {"raw_rows": int(sum(row["raw_rows"] for row in source_rows)), "duplicate_machine_minutes": duplicate_wide_minutes, "qualified_minutes": int(len(qualified)), "qualified_days": int(qualified["day"].nunique())}, "profiles": {"total": int(len(profiles_frame)), "by_status": profiles_frame["status"].value_counts().to_dict(), "approval_dry_run_eligible": int(len(eligible))}, "boundary": dry_run}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
