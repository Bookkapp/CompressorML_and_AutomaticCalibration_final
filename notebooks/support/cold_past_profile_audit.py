"""Past-only Cold profile QA and observed-second manual-operation ledger.

This is a diagnostic, not a new model/profile or service-epoch detector. It
reuses the existing full-snapshot date split, then excludes outer-temporal
feature rows from every diagnostic calculation, fit, selection and report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from notebooks.support.phase7_benchmark import DEVELOPMENT_MACHINES, assign_splits, load_and_engineer
from notebooks.support.phase7_cold_candidate import PROFILE_FEATURES, PROFILE_KEYS, STATE


PAST_SPLITS = ("inner_train", "inner_validation", "calibration")
EXISTING_REVIEW_Z = 8.0
MANUAL_CODES = ("ChangeValve", "MValveHome", "AdjustValve")
EXAMPLE_CONTEXTS = (("022", 2), ("024", 6), ("058", 4), ("058", 6), ("083", 8))


def _past_profile_diagnostics(project_root: Path, candidate_dir: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cache = project_root / "notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet"
    profiles = pd.read_csv(candidate_dir / "local_profiles.csv", dtype={"machine_number": str})
    source_splits = pd.read_csv(candidate_dir / "split_manifest.csv", dtype={"machine_number": str})
    engineered = load_and_engineer(cache)
    qualified = engineered.loc[(engineered.state == STATE) & (engineered.sv == "Off")].copy()
    split, actual_splits = assign_splits(qualified)
    if not source_splits.equals(actual_splits):
        raise AssertionError("Candidate split manifest differs from current source/split code")
    past = split.loc[split.machine_number.isin(DEVELOPMENT_MACHINES) & split.split.isin(PAST_SPLITS)].copy()
    if past.empty or past.machine_number.nunique() != len(DEVELOPMENT_MACHINES):
        raise ValueError("Development past data missing")
    outer_starts = pd.to_datetime(source_splits.set_index("machine_number")["outer_start"])
    if not (past["minute"] < past.machine_number.map(outer_starts)).all():
        raise AssertionError("An outer or later row entered the past-only audit")
    joined = past.merge(profiles, on=PROFILE_KEYS, how="left", validate="many_to_one", indicator=True)
    joined["profile_supported"] = joined["_merge"].eq("both")
    supported = joined.loc[joined.profile_supported].copy()
    for feature in PROFILE_FEATURES:
        supported[f"rz_{feature}"] = ((supported[feature] - supported[f"{feature}__median"])
                                       / supported[f"{feature}__scale"]).clip(-25, 25)
    rz_columns = [f"rz_{feature}" for feature in PROFILE_FEATURES]
    supported["self_score"] = supported[rz_columns].abs().max(axis=1, skipna=False)
    supported["review_flag"] = supported.self_score.gt(EXISTING_REVIEW_Z)
    supported["dominant_feature"] = supported[rz_columns].abs().idxmax(axis=1).str.removeprefix("rz_")

    per_context = supported.groupby(["machine_number", "module", "split"], observed=True).agg(
        windows=("review_flag", "size"),
        days=("date", "nunique"),
        first_window=("minute", "min"),
        last_window=("minute", "max"),
        review_windows=("review_flag", "sum"),
        median_self_score=("self_score", "median"),
        p95_self_score=("self_score", lambda values: values.quantile(.95)),
    ).reset_index()
    per_context["review_pct"] = 100 * per_context.review_windows / per_context.windows
    daily = supported.groupby(["machine_number", "module", "split", "date"], observed=True).agg(
        windows=("review_flag", "size"), review_windows=("review_flag", "sum"),
        median_self_score=("self_score", "median"),
    ).reset_index()
    daily["review_pct"] = 100 * daily.review_windows / daily.windows
    contributors = (supported.loc[supported.review_flag]
                    .groupby(["split", "dominant_feature"], observed=True).size()
                    .reset_index(name="review_windows")
                    .sort_values(["split", "review_windows"], ascending=[True, False]))
    context_contributors = (supported.loc[supported.review_flag]
                            .groupby(["machine_number", "module", "split", "dominant_feature"], observed=True).size()
                            .reset_index(name="review_windows")
                            .sort_values(["machine_number", "module", "split", "review_windows"],
                                         ascending=[True, True, True, False]))
    split_summary = supported.groupby("split", observed=True).agg(
        supported_windows=("review_flag", "size"), review_windows=("review_flag", "sum"),
        source_days=("date", "nunique"),
    ).reset_index()
    split_summary["review_pct"] = 100 * split_summary.review_windows / split_summary.supported_windows
    summary = {
        "source": str(cache.relative_to(project_root)),
        "candidate_profile": str((candidate_dir / "local_profiles.csv").relative_to(project_root)),
        "period_start": str(past.minute.min()), "period_end": str(past.minute.max()),
        "source_timezone": "NOT_ENCODED_UNVERIFIED",
        "grain": "machine x module x qualified five-minute settled Cold window",
        "filters": "Run + On + Busy=0 + SV=Off + nonnegative Valve; 12 development machines; inner_train/inner_validation/calibration only",
        "outer_feature_rows_used_for_diagnostic": 0,
        "past_qualified_windows": int(len(past)),
        "supported_windows": int(len(supported)),
        "unsupported_windows": int(len(joined) - len(supported)),
        "profile_count": int(len(profiles)),
        "existing_review_z": EXISTING_REVIEW_Z,
        "split": split_summary.to_dict(orient="records"),
    }
    return summary, per_context, contributors, daily, context_contributors


def _source_files_before_outer(raw_root: Path, machine: str, outer_start: pd.Timestamp) -> list[Path]:
    base = raw_root / f"machine={machine}" / "year=2026"
    files = []
    for path in base.glob("month=*/day=*/*.parquet"):
        month = int(path.parent.parent.name.split("=")[1])
        day = int(path.parent.name.split("=")[1])
        if pd.Timestamp(2026, month, day) < outer_start:
            files.append(path)
    return sorted(files)


def _manual_event_ledger(project_root: Path, candidate_dir: Path) -> tuple[pd.DataFrame, dict]:
    raw_root = project_root / "HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings"
    splits = pd.read_csv(candidate_dir / "split_manifest.csv", dtype={"machine_number": str})
    events = []
    files_read = 0
    raw_candidate_rows = 0
    duplicate_module_rows_excluded = 0
    for spec in splits.itertuples(index=False):
        machine = spec.machine_number
        outer_start = pd.Timestamp(spec.outer_start)
        files = _source_files_before_outer(raw_root, machine, outer_start)
        if not files:
            raise ValueError(f"No pre-outer raw files for MX{machine}")
        files_read += len(files)
        status_names = [f"Status_{module}" for module in range(1, 9)]
        busy_names = [f"Busy_{module}" for module in range(1, 9)]
        scan = pl.scan_parquet(files)
        predicate = pl.any_horizontal(*(
            [pl.col(name).is_in(MANUAL_CODES) for name in status_names]
            + [pl.col(name) == 1 for name in busy_names]
        ))
        rows = scan.filter(pl.col("recorded_at") < outer_start.to_pydatetime()).filter(predicate).select(
            "recorded_at", *status_names, *busy_names
        ).collect().to_pandas()
        raw_candidate_rows += len(rows)
        for module in range(1, 9):
            status = f"Status_{module}"
            busy = f"Busy_{module}"
            part = rows.loc[rows[status].isin(MANUAL_CODES) | rows[busy].eq(1), ["recorded_at", status, busy]].copy()
            if part.empty:
                continue
            part = part.sort_values("recorded_at")
            duplicates = part.duplicated("recorded_at", keep=False)
            duplicate_rows = int(duplicates.sum())
            duplicate_module_rows_excluded += duplicate_rows
            part = part.loc[~duplicates].copy()
            if part.empty:
                continue
            part["event_group"] = part.recorded_at.diff().dt.total_seconds().gt(2).fillna(True).cumsum()
            for _, episode in part.groupby("event_group", sort=False):
                codes = sorted(set(episode[status].dropna().astype(str)) & set(MANUAL_CODES))
                events.append({
                    "machine_number": machine, "module": module,
                    "event_start": episode.recorded_at.iloc[0],
                    "event_end": episode.recorded_at.iloc[-1],
                    "observed_samples": len(episode),
                    "elapsed_seconds": (episode.recorded_at.iloc[-1] - episode.recorded_at.iloc[0]).total_seconds(),
                    "manual_codes_observed": ";".join(codes),
                    "busy_1_observed": bool(episode[busy].eq(1).any()),
                    "review_state": "MANUAL_CONTEXT_REVIEW_ONLY",
                    "service_or_refill_confirmed": False,
                    "new_profile_authorized": False,
                })
    ledger = pd.DataFrame(events, columns=[
        "machine_number", "module", "event_start", "event_end", "observed_samples",
        "elapsed_seconds", "manual_codes_observed", "busy_1_observed",
        "review_state", "service_or_refill_confirmed", "new_profile_authorized",
    ])
    machine_clusters = 0
    for _, machine_events in ledger.groupby("machine_number", sort=False):
        right_edge = None
        for event in machine_events.sort_values("event_start").itertuples(index=False):
            start, end = pd.Timestamp(event.event_start), pd.Timestamp(event.event_end)
            if right_edge is None or start > right_edge + pd.Timedelta(seconds=2):
                machine_clusters += 1
                right_edge = end
            else:
                right_edge = max(right_edge, end)
    qa = {"source": str(raw_root.relative_to(project_root)),
          "grain": "observed-second manual-status run per machine x module (gap >2 s splits episodes)",
          "files_read_pre_outer_only": files_read,
          "raw_rows_with_any_manual_marker": raw_candidate_rows,
          "duplicate_module_timestamp_rows_excluded": duplicate_module_rows_excluded,
          "per_module_manual_marker_episodes": len(ledger),
          "machine_level_overlapping_marker_clusters": machine_clusters,
          "changevalve_episodes": int(ledger.manual_codes_observed.str.contains("ChangeValve").sum()) if len(ledger) else 0,
          "no_service_or_refill_inference": True}
    return ledger, qa


def _make_review_figures(daily: pd.DataFrame, ledger: pd.DataFrame,
                         contributors: pd.DataFrame, output_dir: Path) -> None:
    colors = {"review": "#c75a45", "manual": "#1e6ca8", "grid": "#dce2e8", "ink": "#243447"}
    fig, axes = plt.subplots(len(EXAMPLE_CONTEXTS), 1, figsize=(12.5, 11), sharex=True,
                             constrained_layout=True)
    fig.patch.set_facecolor("white")
    for ax, (machine, module) in zip(axes, EXAMPLE_CONTEXTS, strict=True):
        part = daily.loc[daily.machine_number.eq(machine) & daily.module.eq(module)].copy()
        part["date"] = pd.to_datetime(part.date)
        part = part.sort_values("date")
        manual = ledger.loc[ledger.machine_number.eq(machine) & ledger.module.eq(module)].copy()
        if not manual.empty:
            manual["event_day"] = pd.to_datetime(manual.event_start).dt.normalize()
            manual = manual.groupby("event_day").size().reset_index(name="episodes")
            manual = manual.loc[manual.event_day.isin(part.date)]
        ax.bar(part.date, part.review_pct, width=.72, color=colors["review"],
               alpha=.88, label="review share")
        if not manual.empty:
            ax.scatter(manual.event_day, [104] * len(manual), color=colors["manual"],
                       marker="|", s=110, linewidths=2, label="manual marker day")
        ax.set_ylim(-4, 112)
        ax.set_yticks((0, 50, 100))
        ax.set_ylabel("% of windows", color=colors["ink"])
        ax.set_title(f"MX{machine} · M{module}   |   {int(part.windows.sum()):,} qualified windows",
                     loc="left", fontsize=11, color=colors["ink"], weight="bold")
        ax.grid(axis="y", color=colors["grid"], linewidth=.8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xticks(pd.date_range("2026-08-04", "2026-08-26", freq="2D"))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d Aug"))
    axes[-1].set_xlim(pd.Timestamp("2026-08-03 12:00"), pd.Timestamp("2026-08-27"))
    fig.suptitle("Past-only local-profile review: daily deviation and manual-control days",
                 color=colors["ink"], fontsize=15, weight="bold")
    fig.supxlabel("Orange = share above existing |z|>8 review rule · blue tick = manual-marker day · missing days are blank · source timezone unverified")
    fig.savefig(output_dir / "past_daily_review_timeline.png", dpi=160, facecolor="white")
    plt.close(fig)

    calibration = contributors.loc[contributors.split.eq("calibration")].copy()
    calibration = calibration.sort_values("review_windows")
    display_names = {"templo": "TempLo", "lp2": "Lp_2nd", "dp1": "ΔP1 (Hp_1st − Lp_1st)",
                     "temphi": "TempHi", "hp1": "Hp_1st", "valve": "Valve",
                     "lp1": "Lp_1st", "dp2": "ΔP2 (Hp_2nd − Lp_2nd)", "hp2": "Hp_2nd"}
    fig, ax = plt.subplots(figsize=(9.5, 5.8), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.barh(calibration.dominant_feature.map(display_names), calibration.review_windows,
            color="#1e6ca8", height=.67)
    for i, value in enumerate(calibration.review_windows):
        ax.text(value + 35, i, f"{value:,}", va="center", color=colors["ink"], fontsize=9)
    ax.set_xlim(0, calibration.review_windows.max() * 1.16)
    ax.set_xlabel("Five-minute windows whose largest |robust z| exceeded 8")
    ax.set_title(f"Past calibration · largest relative deviation on {int(calibration.review_windows.sum()):,} review windows",
                 loc="left", fontsize=13, weight="bold", color=colors["ink"])
    ax.grid(axis="x", color=colors["grid"], linewidth=.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output_dir / "past_calibration_contributors.png", dpi=160, facecolor="white")
    plt.close(fig)


def run(project_root: Path, output_dir: Path) -> dict:
    candidate_dir = project_root / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_qa, contexts, contributors, daily, context_contributors = _past_profile_diagnostics(project_root, candidate_dir)
    ledger, manual_qa = _manual_event_ledger(project_root, candidate_dir)
    contexts.to_csv(output_dir / "past_context_rates.csv", index=False)
    daily.to_csv(output_dir / "past_daily_context_rates.csv", index=False)
    contributors.to_csv(output_dir / "past_flag_contributors.csv", index=False)
    context_contributors.to_csv(output_dir / "past_context_flag_contributors.csv", index=False)
    ledger.to_csv(output_dir / "pre_outer_manual_review_ledger.csv", index=False)
    _make_review_figures(daily, ledger, contributors, output_dir)
    result = {"profile_qa": profile_qa, "manual_qa": manual_qa,
              "top_calibration_contexts": contexts.loc[contexts.split.eq("calibration")]
              .sort_values("review_pct", ascending=False).head(12).to_dict(orient="records"),
              "calibration_contributors": contributors.loc[contributors.split.eq("calibration")].to_dict(orient="records"),
              "decision": "REVIEW_ONLY_NO_MODEL_OR_PROFILE_ACTIVATION"}
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--figures-only", action="store_true", help="Render reviewed CSV outputs without rescanning source")
    args = parser.parse_args()
    root = args.project_root.resolve()
    target = args.output_dir or root / "notebooks/outputs/ht9046mx_cold_past_profile_audit_v1"
    if args.figures_only:
        _make_review_figures(
            pd.read_csv(target / "past_daily_context_rates.csv", dtype={"machine_number": str}),
            pd.read_csv(target / "pre_outer_manual_review_ledger.csv", dtype={"machine_number": str}),
            pd.read_csv(target / "past_flag_contributors.csv"), target,
        )
        print(json.dumps({"figures_rebuilt_from": str(target)}))
    else:
        print(json.dumps(run(root, target), indent=2, default=str))
