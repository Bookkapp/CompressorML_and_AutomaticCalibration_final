"""Matched, descriptive replay of the frozen robust-z rule and Cold ARX v2.

Both lanes use the same offline profile, qualified five-minute rows and locked
thresholds. MX080/M6 is a separate four-day-profile forensic transfer probe.
No model or threshold is selected from the inspected outer/incident periods.
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

from apps.api.app.model_bundle import load_cold_candidate
from notebooks.support.phase7_benchmark import DEVELOPMENT_MACHINES, assign_splits, load_and_engineer
from notebooks.support.phase7_cold_candidate import (
    PROFILE_KEYS, STATE, _fit_local_profiles, _relative_with_lags, _sha256,
)
from notebooks.support.phase7_shadow_replay import build_mx080_minute_input


TRANSITION = pd.Timestamp("2026-09-07 12:23:20")
PERSISTENCE = 3
COLORS = {"self": "#1e6ca8", "dynamic": "#c65d47", "both": "#625187", "neutral": "#66798c"}


def _add_persistence(frame: pd.DataFrame) -> pd.DataFrame:
    """Causal three-window persistence, resetting on a non-five-minute gap."""
    result = frame.sort_values(["machine_number", "module", "minute"]).copy()
    for lane in ("self", "dynamic", "either"):
        result[f"{lane}_persistent"] = False
        result[f"{lane}_opening"] = False
    for _, group in result.groupby(["machine_number", "module"], observed=True, sort=False):
        previous = None
        runs = {lane: 0 for lane in ("self", "dynamic", "either")}
        for idx, row in group.iterrows():
            contiguous = previous is not None and row.minute - previous == pd.Timedelta(minutes=5)
            for lane in runs:
                runs[lane] = (runs[lane] + 1 if contiguous else 1) if bool(row[f"{lane}_flag"]) else 0
                result.at[idx, f"{lane}_persistent"] = runs[lane] >= PERSISTENCE
                result.at[idx, f"{lane}_opening"] = runs[lane] == PERSISTENCE
            previous = row.minute
    return result


def _score_same_rows(relative: pd.DataFrame, bundle) -> pd.DataFrame:
    keys = ["machine_number", "module", "minute", "date", "hp2", "lp2", "self_score"]
    scored = relative[keys].copy()
    scored["dynamic_score"] = bundle.model.score(
        relative.loc[:, bundle.model.predictor_names].to_numpy(dtype=float),
        relative.loc[:, bundle.model.target_names].to_numpy(dtype=float),
    )
    scored["self_flag"] = scored.self_score.ge(bundle.self_threshold)
    scored["dynamic_flag"] = scored.dynamic_score.ge(bundle.dynamic_threshold)
    scored["either_flag"] = scored.self_flag | scored.dynamic_flag
    if scored.duplicated(["machine_number", "module", "minute"]).any():
        raise AssertionError("Duplicate score grain")
    return _add_persistence(scored)


def _lane_summary(scored: pd.DataFrame) -> dict:
    total = len(scored)
    machine_days = scored[["machine_number", "date"]].drop_duplicates().shape[0]
    self_only = scored.self_flag & ~scored.dynamic_flag
    dynamic_only = scored.dynamic_flag & ~scored.self_flag
    both = scored.self_flag & scored.dynamic_flag
    neither = ~scored.either_flag
    return {
        "matched_windows": total,
        "machine_days": machine_days,
        "self_flag_windows": int(scored.self_flag.sum()),
        "dynamic_flag_windows": int(scored.dynamic_flag.sum()),
        "either_flag_windows": int(scored.either_flag.sum()),
        "neither_windows": int(neither.sum()),
        "self_only_windows": int(self_only.sum()),
        "dynamic_only_windows": int(dynamic_only.sum()),
        "both_windows": int(both.sum()),
        "self_flag_pct": float(100 * scored.self_flag.mean()) if total else None,
        "dynamic_flag_pct": float(100 * scored.dynamic_flag.mean()) if total else None,
        "either_flag_pct": float(100 * scored.either_flag.mean()) if total else None,
        "self_episode_openings": int(scored.self_opening.sum()),
        "dynamic_episode_openings": int(scored.dynamic_opening.sum()),
        "either_episode_openings": int(scored.either_opening.sum()),
        "either_openings_without_same_lane_persistence": int((scored.either_opening & ~scored.self_persistent & ~scored.dynamic_persistent).sum()),
        "self_openings_per_machine_day": float(scored.self_opening.sum() / machine_days) if machine_days else None,
        "either_openings_per_machine_day": float(scored.either_opening.sum() / machine_days) if machine_days else None,
    }


def _machine_table(scored: pd.DataFrame) -> pd.DataFrame:
    table = scored.groupby("machine_number", observed=True).agg(
        windows=("self_flag", "size"), days=("date", "nunique"),
        self_flags=("self_flag", "sum"), dynamic_flags=("dynamic_flag", "sum"),
        either_flags=("either_flag", "sum"), self_episodes=("self_opening", "sum"),
        dynamic_episodes=("dynamic_opening", "sum"), either_episodes=("either_opening", "sum"),
    ).reset_index()
    table["dynamic_only_flags"] = table.either_flags - table.self_flags
    for lane in ("self", "dynamic", "either"):
        table[f"{lane}_flag_pct"] = 100 * table[f"{lane}_flags"] / table.windows
        table[f"{lane}_episodes_per_day"] = table[f"{lane}_episodes"] / table.days
    return table


def _development_replay(project_root: Path, bundle, candidate_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cache = project_root / "notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet"
    manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    if _sha256(cache) != manifest["source_cache_sha256"]:
        raise AssertionError("Minute cache differs from frozen candidate source")
    source_splits = pd.read_csv(candidate_dir / "split_manifest.csv", dtype={"machine_number": str})
    engineered = load_and_engineer(cache)
    cold = engineered.loc[(engineered.state == STATE) & (engineered.sv == "Off")].copy()
    split, actual_splits = assign_splits(cold)
    if not source_splits.equals(actual_splits):
        raise AssertionError("Split manifest mismatch")
    development = split.loc[split.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    relative = _relative_with_lags(development, bundle.profiles)
    outer = relative.loc[relative.split.eq("outer_temporal")].copy()
    if outer.empty or not (outer.minute >= outer.machine_number.map(pd.to_datetime(source_splits.set_index("machine_number").outer_start))).all():
        raise AssertionError("Outer comparison boundary mismatch")
    scored = _score_same_rows(outer, bundle)
    existing = json.loads((candidate_dir / "candidate_summary.json").read_text(encoding="utf-8"))["temporal"]
    lane = _lane_summary(scored)
    if lane["matched_windows"] != existing["scored_windows"] or lane["self_episode_openings"] != existing["self_persistence_episodes"] or lane["dynamic_episode_openings"] != existing["dynamic_persistence_episodes"] or lane["either_episode_openings"] != existing["diagnostic_or_persistence_episodes"]:
        raise AssertionError("Frozen v2 replay does not reproduce candidate episode counts")
    return scored, _machine_table(scored), lane | {
        "source": str(cache.relative_to(project_root)),
        "source_sha256": manifest["source_cache_sha256"],
        "period_start": str(scored.minute.min()), "period_end": str(scored.minute.max()),
        "source_timezone": "NOT_ENCODED_UNVERIFIED",
        "grain": "machine x module x matched qualified five-minute Cold window",
        "profile_source": "frozen v2 offline train-only profiles, not MySQL ACTIVE_FROZEN",
        "outer_used_for_model_or_threshold_selection": False,
    }


def _mx080_replay(project_root: Path, output_dir: Path, bundle) -> tuple[pd.DataFrame, dict]:
    source = project_root / "notebooks/outputs/mx080_module6_forensics_v1/module6_one_second_unique.parquet"
    minute_path = output_dir / "mx080_module6_quality_minutes.parquet"
    _, quality = build_mx080_minute_input(source, minute_path)
    engineered = load_and_engineer(minute_path)
    cold = engineered.loc[(engineered.state == STATE) & (engineered.sv == "Off")].copy()
    reference = cold.loc[cold.minute.lt(pd.Timestamp("2026-09-07"))]
    if reference.date.nunique() != 4 or reference.module.nunique() != 1 or not reference.module.eq(6).all():
        raise AssertionError("MX080 forensic reference is not the expected M6 four-day source")
    # Deliberately bypass the seven-day production readiness threshold. This
    # single-pass profile is a short-history forensic comparator only; both
    # lanes use the exact same local medians/scales and locked fleet thresholds.
    short_profile = _fit_local_profiles(reference, quantized_valve=True)
    if len(short_profile) != 1 or int(short_profile.iloc[0].profile_days) != 4:
        raise AssertionError("MX080 short profile unexpectedly changed")
    relative = _relative_with_lags(cold, short_profile)
    scored = _score_same_rows(relative, bundle)
    probe = scored.loc[scored.minute.dt.date.eq(pd.Timestamp("2026-09-07").date())].copy()
    before = probe.loc[probe.minute.lt(TRANSITION)]
    after = probe.loc[probe.minute.ge(TRANSITION)]
    result = {
        "source": str(source.relative_to(project_root)),
        "raw_seconds": quality["raw_seconds"],
        "quality_pass_minutes": quality["quality_pass_minutes"],
        "quality_fail_minutes": quality["quality_fail_minutes"],
        "source_timezone": "NOT_ENCODED_UNVERIFIED",
        "profile_source": "MX080/M6 single-pass 4-day forensic reference, not ACTIVE_FROZEN or production-ready",
        "reference_days": int(reference.date.nunique()),
        "reference_cold_windows": int(len(reference)),
        "reference_scored_windows": int(scored.minute.lt(pd.Timestamp("2026-09-07")).sum()),
        "incident_probe_windows": int(len(probe)),
        "probe_pre_observed_transition_windows": int(len(before)),
        "probe_post_observed_transition_windows": int(len(after)),
        "observed_pressure_transition": str(TRANSITION),
        "locked_fleet_self_threshold": bundle.self_threshold,
        "locked_fleet_dynamic_threshold": bundle.dynamic_threshold,
        "reference_lanes": _lane_summary(scored.loc[scored.minute.lt(pd.Timestamp("2026-09-07"))]),
        "probe_pre_lanes": _lane_summary(before),
        "probe_post_lanes": _lane_summary(after),
        "probe_all_lanes": _lane_summary(probe),
        "first_probe_flags": {}, "first_probe_persistent_openings_after_transition": {},
    }
    for lane in ("self", "dynamic", "either"):
        flagged = probe.loc[probe[f"{lane}_flag"], "minute"]
        opening = after.loc[after[f"{lane}_opening"], "minute"]
        result["first_probe_flags"][lane] = str(flagged.min()) if len(flagged) else None
        result["first_probe_persistent_openings_after_transition"][lane] = str(opening.min()) if len(opening) else None
    return scored, result


def _figures(machine: pd.DataFrame, outer: pd.DataFrame, mx: pd.DataFrame, bundle, output_dir: Path) -> None:
    order = machine.sort_values("self_flag_pct", ascending=True)
    names = [f"MX{name}" for name in order.machine_number]
    self_pct = order.self_flag_pct.to_numpy()
    incremental = 100 * order.dynamic_only_flags.to_numpy() / order.windows.to_numpy()
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    fig.patch.set_facecolor("white")
    bars = ax.barh(names, self_pct, color=COLORS["self"], label="Robust-z rule flags")
    ax.barh(names, incremental, left=self_pct, color=COLORS["dynamic"],
            label="Additional ARX-only flags")
    for bar, self_value, extra in zip(bars, self_pct, incremental, strict=True):
        ax.text(self_value + extra + .5, bar.get_y() + bar.get_height()/2,
                f"{self_value:.1f}% + {extra:.1f}%", va="center", fontsize=8.5, color="#263747")
    ax.set_xlim(0, max(100, float((self_pct + incremental).max() + 13)))
    ax.set_xlabel("Share of matched qualified five-minute windows (%)")
    ax.set_title("Frozen v2 profiles · rule-only burden and ARX-only increment", loc="left", weight="bold")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="x", alpha=.17)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output_dir / "development_matched_flag_burden.png", dpi=170, facecolor="white")
    plt.close(fig)

    labels = ["Neither", "Rule only", "ARX only", "Both"]
    counts = [int((~outer.either_flag).sum()), int((outer.self_flag & ~outer.dynamic_flag).sum()),
              int((outer.dynamic_flag & ~outer.self_flag).sum()), int((outer.self_flag & outer.dynamic_flag).sum())]
    palette = ["#a3b0bb", COLORS["self"], COLORS["dynamic"], COLORS["both"]]
    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    fig.patch.set_facecolor("white")
    bars = ax.barh(labels[::-1], counts[::-1], color=palette[::-1], height=.62)
    for bar, count in zip(bars, counts[::-1], strict=True):
        ax.text(count + max(counts)*.008, bar.get_y()+bar.get_height()/2,
                f"{count:,}  ({100*count/len(outer):.2f}%)", va="center", fontsize=9, color="#263747")
    ax.set_xlim(0, max(counts)*1.2)
    ax.set_xlabel(f"Windows · common denominator {len(outer):,}")
    ax.set_title("Where the two screening lanes agree and disagree", loc="left", weight="bold")
    ax.grid(axis="x", alpha=.17)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output_dir / "development_lane_agreement.png", dpi=170, facecolor="white")
    plt.close(fig)

    day = mx.loc[mx.minute.dt.date.eq(pd.Timestamp("2026-09-07").date())].sort_values("minute")
    fig, axes = plt.subplots(3, 1, figsize=(13, 8.8), sharex=True, constrained_layout=True)
    fig.patch.set_facecolor("white")
    gap = day.minute.diff().gt(pd.Timedelta(minutes=5))
    segments = list(day.groupby(gap.cumsum(), sort=False))
    for ax in axes:
        ax.axvline(TRANSITION, color="#394b5c", linestyle="--", linewidth=1.1)
        ax.grid(axis="y", alpha=.17)
        ax.spines[["top", "right"]].set_visible(False)
        for i in np.flatnonzero(gap.to_numpy()):
            left = day.minute.iloc[i-1] + pd.Timedelta(minutes=5)
            right = day.minute.iloc[i]
            ax.axvspan(left, right, color="#e9edf1", alpha=.7, linewidth=0)
    for _, part in segments:
        axes[0].plot(part.minute, part.hp2, color="#6b7c88", linewidth=1.35)
        axes[1].plot(part.minute, part.self_score, color=COLORS["self"], linewidth=1.35)
        axes[2].plot(part.minute, part.dynamic_score, color=COLORS["dynamic"], linewidth=1.35)
    axes[0].set_ylabel("Hp_2nd · source units")
    axes[1].axhline(bundle.self_threshold, color=COLORS["self"], linestyle=":", linewidth=1)
    axes[1].scatter(day.loc[day.self_opening, "minute"], day.loc[day.self_opening, "self_score"],
                    color=COLORS["self"], s=32, marker="D", label="3-window opening")
    axes[1].set_ylabel("Rule |z| max (capped 25)")
    axes[2].axhline(bundle.dynamic_threshold, color=COLORS["dynamic"], linestyle=":", linewidth=1)
    axes[2].scatter(day.loc[day.dynamic_opening, "minute"], day.loc[day.dynamic_opening, "dynamic_score"],
                    color=COLORS["dynamic"], s=32, marker="D")
    axes[2].set_ylabel("ARX residual score")
    axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[2].set_xlim(pd.Timestamp("2026-09-07 00:00"), pd.Timestamp("2026-09-08 00:00"))
    fig.suptitle("MX080 · M6 · 7 Sep 2026 | same qualified five-minute windows", fontsize=15, weight="bold")
    fig.supxlabel("Grey: no qualified Cold windows · dashed: observed pressure transition 12:23:20\nDotted: locked threshold · diamond: 3-window episode opening", fontsize=9)
    fig.savefig(output_dir / "mx080_m6_matched_timeline.png", dpi=170, facecolor="white")
    plt.close(fig)


def run(project_root: Path, output_dir: Path) -> dict:
    candidate_dir = project_root / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized"
    bundle = load_cold_candidate(candidate_dir / "candidate_manifest.json")
    if bundle.live_eligible or bundle.activation_state != "SHADOW_ONLY_NOT_AUTHORIZED":
        raise AssertionError("Only a shadow-only frozen candidate may be compared")
    output_dir.mkdir(parents=True, exist_ok=True)
    outer, machine, outer_summary = _development_replay(project_root, bundle, candidate_dir)
    mx, mx_summary = _mx080_replay(project_root, output_dir, bundle)
    machine.to_csv(output_dir / "development_matched_machine_rates.csv", index=False)
    # Row-level scores and the forensic minute aggregate stay local; the Git
    # handoff contains only bounded aggregates, method and figures.
    outer.to_parquet(output_dir / "development_matched_window_scores.parquet", index=False)
    mx.to_parquet(output_dir / "mx080_m6_forensic_window_scores.parquet", index=False)
    _figures(machine, outer, mx, bundle, output_dir)
    result = {
        "status": "DESCRIPTIVE_MATCHED_REPLAY_NOT_RELEASE_SELECTION",
        "candidate_release": bundle.release_version,
        "candidate_model_sha256": bundle.model_sha256,
        "candidate_profiles_sha256": bundle.profiles_sha256,
        "comparison": "same frozen local profile/rows; rule-only=max absolute robust z, ARX=dynamic residual, either=OR",
        "thresholds": {"self": bundle.self_threshold, "dynamic": bundle.dynamic_threshold,
                       "persistence_qualified_5minute_windows": PERSISTENCE},
        "development_outer": outer_summary,
        "mx080_forensic": mx_summary,
        "limits": [
            "No production ACTIVE_FROZEN profiles were read; the server's rule-only threshold/profile may differ",
            "The historical outer block and MX080 incident were previously inspected; use descriptively, never tune or select release from them",
            "MX080 profile has only four reference days and is a single-pass forensic approximation",
            "No confirmed fault labels; counts and timing are screening behavior, not accuracy, recall or proven lead time",
            "Source timezone and pressure units are unverified; no Server/MySQL connection or alert activation",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--figures-only", action="store_true", help="Render already-reviewed replay rows")
    args = parser.parse_args()
    root = args.project_root.resolve()
    target = args.output_dir or root / "notebooks/outputs/ht9046mx_rule_arx_matched_v1"
    if args.figures_only:
        frozen = root / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized/candidate_manifest.json"
        bundle = load_cold_candidate(frozen)
        _figures(
            pd.read_csv(target / "development_matched_machine_rates.csv", dtype={"machine_number": str}),
            pd.read_parquet(target / "development_matched_window_scores.parquet"),
            pd.read_parquet(target / "mx080_m6_forensic_window_scores.parquet"), bundle, target,
        )
        print(json.dumps({"figures_rebuilt_from": str(target)}))
    else:
        print(json.dumps(run(root, target), indent=2, default=str))
