"""One-second forensic audit of valve-dominated Cold-profile deviations.

Reads original wide source Parquet. It does not fit a profile, change a model,
select a threshold, or interpret lag/correlation as causation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl


MACHINES = ("041", "083", "072", "070")  # top valve-contributor examples + lower-flag comparison
SETTLE_SECONDS = 180
EVENT_PRE_SECONDS = 20
EVENT_POST_SECONDS = 60
MIN_STEP = 3.0


def _candidate_files(raw_root: Path, machine: str, outer_start: pd.Timestamp) -> list[tuple[Path, str]]:
    base = raw_root / f"machine={machine}" / "year=2026"
    records = []
    for path in base.glob("month=*/day=*/*.parquet"):
        date = pd.Timestamp(f"2026-{path.parent.parent.name.split('=')[1]}-{path.parent.name.split('=')[1]}")
        records.append((date, path))
    records.sort()
    before = [(date, path) for date, path in records if date < outer_start]
    after = [(date, path) for date, path in records if date >= outer_start]
    if not before or not after:
        return []
    indices = sorted(set((0, len(after) // 2, len(after) - 1)))
    return [(before[-1][1], "past_reference_day")] + [(after[index][1], "retrospective_future_day") for index in indices]


def _select_modules(cache_path: Path, profile_path: Path, split_path: Path) -> pd.DataFrame:
    profiles = pd.read_csv(profile_path, dtype={"machine_number": str})
    splits = pd.read_csv(split_path, dtype={"machine_number": str})
    selected = []
    for machine in MACHINES:
        outer_start = pd.Timestamp(splits.set_index("machine_number").loc[machine, "outer_start"])
        minute = pl.scan_parquet(cache_path).filter(
            (pl.col("machine_number") == machine)
            & (pl.col("minute") >= outer_start.to_pydatetime())
            & (pl.col("global_status") == "Run")
            & (pl.col("module_status") == "On")
            & (pl.col("busy") == 0)
            & (pl.col("sv") == "Off")
            & (pl.col("valve") >= 0)
            & (pl.col("minute").dt.minute().mod(5) == 0)
        ).select("module", "minute", "valve").collect().to_pandas()
        local = profiles.loc[(profiles.machine_number == machine) & profiles.state.eq("RUN_ON_SV_OFF") & profiles.sv.eq("Off")]
        minute = minute.merge(local[["module", "valve__median", "valve__scale"]], on="module", how="inner", validate="many_to_one")
        if minute.empty:
            continue
        minute["valve_rz_abs"] = ((minute.valve - minute.valve__median) / minute.valve__scale).abs()
        by_module = minute.groupby("module").agg(
            five_minute_rows=("valve_rz_abs", "size"),
            median_abs_valve_rz=("valve_rz_abs", "median"),
            pct_above_8=("valve_rz_abs", lambda x: 100 * x.gt(8).mean()),
        ).reset_index().sort_values(["pct_above_8", "five_minute_rows"], ascending=False)
        top = by_module.iloc[0]
        p = local.set_index("module").loc[int(top.module)]
        selected.append({
            "machine_number": machine,
            "module": int(top.module),
            "outer_start": str(outer_start),
            "five_minute_rows": int(top.five_minute_rows),
            "five_minute_pct_abs_valve_rz_gt8": float(top.pct_above_8),
            "five_minute_median_abs_valve_rz": float(top.median_abs_valve_rz),
            "train_valve_median": float(p["valve__median"]),
            "train_valve_scale": float(p["valve__scale"]),
            "train_hp2_median": float(p["hp2__median"]),
        })
    return pd.DataFrame(selected)


def _daily_one_second(path: Path, machine: str, module: int, baseline: dict, phase: str) -> tuple[dict, pd.DataFrame, list[dict], list[dict]]:
    fields = [
        "recorded_at", "Status", f"Status_{module}", f"Busy_{module}", f"SV_{module}",
        f"Valve_{module}", f"Hp_1st_{module}", f"Lp_1st_{module}",
        f"Hp_2nd_{module}", f"Lp_2nd_{module}", f"TempLo_{module}",
    ]
    raw = pd.read_parquet(path, columns=fields)
    raw.columns = ["at", "global_status", "module_status", "busy", "sv", "valve", "hp1", "lp1", "hp2", "lp2", "templo"]
    source_rows = len(raw)
    duplicate_rows = int(raw.duplicated("at", keep=False).sum())
    raw = raw.loc[~raw.duplicated("at", keep=False)].sort_values("at").reset_index(drop=True)
    for name in ("valve", "hp1", "lp1", "hp2", "lp2", "templo"):
        raw[name] = pd.to_numeric(raw[name], errors="coerce")
    gaps = raw["at"].diff().dt.total_seconds()
    exact_one_second_pairs = int(gaps.eq(1).sum())
    positive_pairs = int(gaps.gt(0).sum())
    state = (
        raw.global_status.eq("Run") & raw.module_status.eq("On") & raw.busy.eq(0)
        & raw.sv.eq("Off") & raw.valve.ge(0)
        & raw[["hp1", "lp1", "hp2", "lp2", "templo"]].notna().all(axis=1)
    )
    # The source has occasional missing seconds. A missing second is not a
    # state transition; retain the observed samples but never interpolate it.
    breaks = (~state) | (~state.shift(fill_value=False)) | gaps.gt(2) | gaps.isna()
    raw["segment_id"] = breaks.cumsum()
    first_at = raw.groupby("segment_id", sort=False)["at"].transform("first")
    raw["elapsed_in_segment_seconds"] = (raw["at"] - first_at).dt.total_seconds()
    raw["eligible"] = state & raw.elapsed_in_segment_seconds.ge(SETTLE_SECONDS)
    usable = raw.loc[raw.eligible].copy()
    baseline_valve = baseline["train_valve_median"]
    scale_valve = baseline["train_valve_scale"]
    usable["valve_rz"] = (usable.valve - baseline_valve) / scale_valve
    usable["dp2"] = usable.hp2 - usable.lp2

    events: list[dict] = []
    valve = raw.valve.to_numpy(dtype=float)
    qualified = raw.eligible.to_numpy(dtype=bool)
    segment = raw.segment_id.to_numpy()
    timestamp = raw["at"].to_numpy(dtype="datetime64[ns]")
    steps = np.r_[np.nan, np.diff(valve)]
    candidates = np.flatnonzero(qualified & (np.abs(steps) >= MIN_STEP))
    for i in candidates:
        lo, hi = i - EVENT_PRE_SECONDS, i + EVENT_POST_SECONDS
        if lo < 0 or hi >= len(raw) or not qualified[lo:hi + 1].all():
            continue
        if segment[lo] != segment[hi] or (timestamp[hi] - timestamp[lo]) != np.timedelta64(80, "s"):
            continue
        if np.sum(np.abs(steps[lo:hi + 1]) >= MIN_STEP) != 1:
            continue
        pre = raw.iloc[i - 20:i - 5]
        post = raw.iloc[i + 30:i + 61]
        events.append({
            "machine_number": machine, "module": module, "event_at": str(raw["at"].iloc[i]),
            "source_phase": phase, "valve_step": float(steps[i]),
            "hp2_change_30to60s": float(post.hp2.median() - pre.hp2.median()),
            "lp2_change_30to60s": float(post.lp2.median() - pre.lp2.median()),
            "templo_change_30to60s": float(post.templo.median() - pre.templo.median()),
        })

    # Manual ChangeValve is a state boundary, not a Cold response example.
    # Its before/after plateaus can, however, explain persistent local
    # deviation. These comparisons are descriptive and never train a profile.
    manual = raw.module_status.eq("ChangeValve") & raw.busy.eq(1)
    manual_start = manual & (~manual.shift(fill_value=False) | gaps.gt(2))
    manual_group = manual_start.cumsum()
    manual_events: list[dict] = []
    for _, part in raw.loc[manual].groupby(manual_group[manual], sort=False):
        start, end = part["at"].iloc[0], part["at"].iloc[-1]
        if (end - start).total_seconds() > 1800:
            continue
        before = usable.loc[(usable["at"] >= start - pd.Timedelta(minutes=10)) & (usable["at"] < start)]
        after = usable.loc[(usable["at"] > end + pd.Timedelta(minutes=3)) & (usable["at"] <= end + pd.Timedelta(minutes=13))]
        record = {
            "machine_number": machine, "module": module, "source_phase": phase,
            "source_partition": str(path),
            "event_start": str(start), "event_end": str(end), "manual_observed_samples": int(len(part)),
            "pre_10m_qualified_samples": int(len(before)), "post_3to13m_qualified_samples": int(len(after)),
            "paired_plateau_supported": bool(len(before) >= 300 and len(after) >= 300),
        }
        if record["paired_plateau_supported"]:
            for field in ("valve", "hp1", "lp1", "hp2", "lp2", "templo"):
                record[f"{field}_pre_median"] = float(before[field].median())
                record[f"{field}_post_median"] = float(after[field].median())
                record[f"{field}_post_minus_pre"] = record[f"{field}_post_median"] - record[f"{field}_pre_median"]
        manual_events.append(record)

    summary = {
        "machine_number": machine, "module": module, "date": str(raw["at"].dt.date.iloc[0]) if len(raw) else "",
        "phase": phase, "source_partition": str(path), "source_rows": source_rows,
        "duplicate_timestamp_rows_excluded": duplicate_rows,
        "exact_1s_pair_pct": 100 * exact_one_second_pairs / positive_pairs if positive_pairs else None,
        "observed_2s_gap_pairs": int(gaps.eq(2).sum()),
        "observed_over_2s_gap_pairs": int(gaps.gt(2).sum()),
        "qualified_after_180s_observed_samples": int(len(usable)),
        "qualified_pct_of_unique_rows": 100 * len(usable) / len(raw) if len(raw) else None,
        "qualified_segment_count": int(usable.segment_id.nunique()),
        "valve_median": float(usable.valve.median()) if len(usable) else None,
        "valve_q05": float(usable.valve.quantile(.05)) if len(usable) else None,
        "valve_q95": float(usable.valve.quantile(.95)) if len(usable) else None,
        "valve_median_relative_to_train": float(usable.valve.median() - baseline_valve) if len(usable) else None,
        "median_abs_valve_rz": float(usable.valve_rz.abs().median()) if len(usable) else None,
        "hp2_median": float(usable.hp2.median()) if len(usable) else None,
        "hp2_median_relative_to_train": float(usable.hp2.median() - baseline["train_hp2_median"]) if len(usable) else None,
        "dp2_median": float(usable.dp2.median()) if len(usable) else None,
        "isolated_valve_steps_20s_pre_60s_post": len(events),
        "manual_changevalve_events": len(manual_events),
        "manual_changevalve_paired_plateaus": sum(event["paired_plateau_supported"] for event in manual_events),
    }
    return summary, usable, events, manual_events


def _figure(usable: pd.DataFrame, baseline: dict, output: Path, title: str) -> None:
    if len(usable) < 1140:
        return
    # Select a 20-minute observed-sample window with >=95% coverage and the
    # largest median valve displacement. Missing seconds are not imputed.
    part = None
    best = -1.0
    for _, segment in usable.groupby("segment_id", sort=False):
        if len(segment) < 1140:
            continue
        offsets = range(0, len(segment) - 1140 + 1, 600)
        for start in offsets:
            limit = segment["at"].iloc[start] + pd.Timedelta(minutes=20)
            window = segment.iloc[start:]
            window = window.loc[window["at"] < limit]
            if len(window) < 1140:
                continue
            displacement = abs(float(window.valve.median()) - baseline["train_valve_median"])
            if displacement > best:
                best, part = displacement, window
    if part is None:
        return
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True, constrained_layout=True)
    fig.patch.set_facecolor("#ffffff")
    axes[0].plot(part["at"], part.valve, color="#1f6bb8", linewidth=1.3)
    axes[0].axhline(baseline["train_valve_median"], color="#74879c", linestyle="--", linewidth=1.2, label="train-only median")
    axes[0].set_ylabel("Valve command (source units)")
    axes[0].legend(frameon=False, loc="upper right")
    axes[1].plot(part["at"], part.hp2, color="#d04d3d", linewidth=1.2, label="Hp_2nd")
    axes[1].plot(part["at"], part.lp2, color="#34a7a1", linewidth=1.2, label="Lp_2nd")
    axes[1].set_ylabel("CP2 pressure (source units)")
    axes[1].legend(frameon=False, loc="upper right")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    for ax in axes:
        ax.grid(alpha=.16)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title + " | 1-second qualified Cold samples", fontsize=13, fontweight="bold")
    fig.text(.01, .01, "Source timezone/pressure units unverified. Example chosen for diagnostic review, not threshold tuning.", fontsize=8, color="#596b7a")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=170, facecolor="white")
    plt.close(fig)


def _manual_figure(event: dict, output: Path) -> None:
    module = int(event["module"])
    frame = pd.read_parquet(event["source_partition"], columns=[
        "recorded_at", f"Valve_{module}", f"Hp_2nd_{module}", f"Lp_2nd_{module}",
        f"Status_{module}", f"Busy_{module}",
    ])
    frame.columns = ["at", "valve", "hp2", "lp2", "module_status", "busy"]
    start, end = pd.Timestamp(event["event_start"]), pd.Timestamp(event["event_end"])
    frame = frame.loc[(frame["at"] >= start - pd.Timedelta(minutes=15)) & (frame["at"] <= end + pd.Timedelta(minutes=15))]
    fig, axes = plt.subplots(3, 1, figsize=(12, 7.4), sharex=True, constrained_layout=True)
    for ax in axes:
        ax.axvspan(start, end, color="#d8e8f7", alpha=.8, label="Busy=1 / ChangeValve")
        ax.grid(alpha=.17)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].plot(frame["at"], frame.valve, color="#1467a9", linewidth=1.25)
    axes[0].set_ylabel("Valve command (source units)")
    axes[0].legend(frameon=False, loc="upper right")
    axes[1].plot(frame["at"], frame.hp2, color="#d04d3d", linewidth=1.1)
    axes[1].set_ylabel("Hp_2nd (source units)")
    axes[2].plot(frame["at"], frame.lp2, color="#219c96", linewidth=1.1)
    axes[2].set_ylabel("Lp_2nd (source units)")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.suptitle(f"MX{event['machine_number']} · M{module} | ChangeValve · {len(frame):,} observed-second samples", fontsize=13, fontweight="bold")
    fig.supxlabel("Retrospectively selected · source timezone/units unverified · shaded manual state excluded from Cold baseline", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=170, facecolor="white")
    plt.close(fig)


def run(project_root: Path, output_dir: Path) -> dict:
    root = project_root / "HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings"
    candidate = project_root / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v1"
    cache = project_root / "notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet"
    output_dir.mkdir(parents=True, exist_ok=True)
    choices = _select_modules(cache, candidate / "local_profiles.csv", candidate / "split_manifest.csv")
    if choices.empty:
        raise ValueError("No candidate profile/module context for one-second audit")
    choices.to_csv(output_dir / "selected_contexts.csv", index=False)
    daily, all_events, all_manual = [], [], []
    for baseline in choices.to_dict(orient="records"):
        machine, module = baseline["machine_number"], baseline["module"]
        files = _candidate_files(root, machine, pd.Timestamp(baseline["outer_start"]))
        for path, phase in files:
            result, usable, events, manual_events = _daily_one_second(path, machine, module, baseline, phase)
            daily.append(result)
            all_events.extend(events)
            all_manual.extend(manual_events)
            if phase == "retrospective_future_day":
                figure = output_dir / "figures" / f"MX{machine}_M{module}_{result['date']}.png"
                _figure(usable, baseline, figure, f"MX{machine} · M{module} · {result['date']}")
    daily_frame = pd.DataFrame(daily)
    daily_frame.to_csv(output_dir / "one_second_daily_context.csv", index=False)
    pd.DataFrame(all_events, columns=["machine_number", "module", "event_at", "source_phase", "valve_step", "hp2_change_30to60s", "lp2_change_30to60s", "templo_change_30to60s"]).to_csv(output_dir / "isolated_valve_step_responses.csv", index=False)
    pd.DataFrame(all_manual, columns=["machine_number", "module", "source_phase", "source_partition", "event_start", "event_end", "manual_observed_samples", "pre_10m_qualified_samples", "post_3to13m_qualified_samples", "paired_plateau_supported", *[f"{field}_{suffix}" for field in ("valve", "hp1", "lp1", "hp2", "lp2", "templo") for suffix in ("pre_median", "post_median", "post_minus_pre")]]).to_csv(output_dir / "manual_changevalve_plateaus.csv", index=False)
    paired = [event for event in all_manual if event["paired_plateau_supported"]]
    for event in sorted(paired, key=lambda row: abs(row["valve_post_minus_pre"]), reverse=True)[:3]:
        stem = f"MX{event['machine_number']}_M{event['module']}_{pd.Timestamp(event['event_start']).strftime('%Y%m%d_%H%M%S')}"
        _manual_figure(event, output_dir / "figures" / f"{stem}_manual.png")
    summary = {
        "purpose": "Forensic audit of valve-dominated Self flags; not model training or alert threshold selection",
        "row_grain": "one raw machine timestamp; one selected module at a time",
        "selected_contexts": choices.to_dict(orient="records"),
        "source_day_count": int(len(daily_frame)),
        "source_rows": int(daily_frame.source_rows.sum()),
        "duplicate_timestamp_rows_excluded": int(daily_frame.duplicate_timestamp_rows_excluded.sum()),
        "qualified_after_180s_observed_samples": int(daily_frame.qualified_after_180s_observed_samples.sum()),
        "isolated_clean_step_events": int(len(all_events)),
        "manual_changevalve_events": int(len(all_manual)),
        "manual_changevalve_paired_plateaus": int(sum(event["paired_plateau_supported"] for event in all_manual)),
        "event_coverage_status": "EXPLORATORY_ONLY" if len(all_events) >= 30 else "INSUFFICIENT_CLEAN_EVENTS",
        "limits": ["Days/modules selected after reviewing a retrospective test: diagnostic only, not an untouched model test", "Source timezone and pressure units are not encoded", "No recipe/load/water or service/refill epoch data", "Valve is command/position, not measured refrigerant flow", "Correlation or lag cannot establish cause", "No Active MySQL profile was used"],
    }
    (output_dir / "one_second_audit_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output or root / "notebooks/outputs/ht9046mx_one_second_valve_audit_v1"
    print(json.dumps(run(root, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
