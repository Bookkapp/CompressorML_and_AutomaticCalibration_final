"""Matched-row retrospective comparison of two shadow-only Cold candidates.

Neither the inspected outer period nor these descriptive results may be used
to select another threshold, feature, model, or production release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apps.api.app.model_bundle import load_cold_candidate
from notebooks.support.phase7_benchmark import DEVELOPMENT_MACHINES, assign_splits, load_and_engineer
from notebooks.support.phase7_cold_candidate import STATE, _persistence, _relative_with_lags, _scores


KEY = ["machine_number", "module", "minute"]


def _score_candidate(raw: pd.DataFrame, manifest_path: Path, suffix: str) -> pd.DataFrame:
    bundle = load_cold_candidate(manifest_path)
    relative = _relative_with_lags(raw, bundle.profiles)
    outer = relative.loc[relative.split.eq("outer_temporal")].copy()
    if outer.duplicated(KEY).any():
        raise ValueError(f"Duplicate scored {suffix} outer keys")
    if outer.empty:
        raise ValueError(f"No scored {suffix} outer rows")
    result = outer[KEY].copy()
    result[f"self_score_{suffix}"] = outer.self_score.to_numpy(dtype=float)
    result[f"dynamic_score_{suffix}"] = _scores(bundle.model, outer)
    result[f"self_flag_{suffix}"] = result[f"self_score_{suffix}"].ge(bundle.self_threshold)
    result[f"dynamic_flag_{suffix}"] = result[f"dynamic_score_{suffix}"].ge(bundle.dynamic_threshold)
    result[f"any_flag_{suffix}"] = result[f"self_flag_{suffix}"] | result[f"dynamic_flag_{suffix}"]
    return result


def run(root: Path, output_dir: Path) -> dict:
    artifact_root = root / "notebooks/outputs"
    cache = artifact_root / "ht9046mx_colab_analysis/cache/minute_module_state.parquet"
    v1 = artifact_root / "ht9046mx_phase7_cold_candidate_v1/candidate_manifest.json"
    v2 = artifact_root / "ht9046mx_phase7_cold_candidate_v2_valve_quantized/candidate_manifest.json"
    engineered = load_and_engineer(cache)
    cold = engineered.loc[(engineered.state.eq(STATE)) & engineered.sv.eq("Off")]
    split, _ = assign_splits(cold)
    development = split.loc[split.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    old = _score_candidate(development, v1, "v1")
    new = _score_candidate(development, v2, "v2")
    matched = old.merge(new, on=KEY, how="inner", validate="one_to_one")
    if matched.empty:
        raise ValueError("No matched scored rows")
    fields = ("self_flag", "dynamic_flag", "any_flag")
    overall = {}
    for field in fields:
        a = matched[f"{field}_v1"]
        b = matched[f"{field}_v2"]
        overall[field] = {
            "v1_pct": float(100 * a.mean()), "v2_pct": float(100 * b.mean()),
            "v1_only_rows": int((a & ~b).sum()), "v2_only_rows": int((~a & b).sum()),
            "both_rows": int((a & b).sum()), "neither_rows": int((~a & ~b).sum()),
            "v1_three_window_episodes": int(_persistence(matched, f"{field}_v1")[0]),
            "v2_three_window_episodes": int(_persistence(matched, f"{field}_v2")[0]),
        }
    machine = matched.groupby("machine_number", observed=True).agg(
        matched_rows=("module", "size"),
        v1_self_pct=("self_flag_v1", lambda x: 100 * x.mean()),
        v2_self_pct=("self_flag_v2", lambda x: 100 * x.mean()),
        v1_dynamic_pct=("dynamic_flag_v1", lambda x: 100 * x.mean()),
        v2_dynamic_pct=("dynamic_flag_v2", lambda x: 100 * x.mean()),
        v1_any_pct=("any_flag_v1", lambda x: 100 * x.mean()),
        v2_any_pct=("any_flag_v2", lambda x: 100 * x.mean()),
    ).reset_index()
    output_dir.mkdir(parents=True, exist_ok=True)
    machine.to_csv(output_dir / "matched_machine_rates.csv", index=False)
    categories = ("Self", "Dynamic", "Either")
    lookup = ("self_flag", "dynamic_flag", "any_flag")
    positions = np.arange(3)
    width = .34
    fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    old_values = [overall[name]["v1_pct"] for name in lookup]
    new_values = [overall[name]["v2_pct"] for name in lookup]
    for shift, values, label, color in ((-width / 2, old_values, "v1 generic 0.05 fallback", "#8798aa"), (width / 2, new_values, "v2 one-count Valve floor", "#1769a8")):
        bars = ax.bar(positions + shift, values, width, label=label, color=color)
        ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=10)
    ax.set_xticks(positions, categories)
    ax.set_ylim(0, max(old_values) * 1.25)
    ax.set_ylabel("Flagged windows (% of matched scored windows)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.18)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right")
    fig.suptitle(f"Cold candidate screening comparison | {len(matched):,} identical windows", fontsize=14, fontweight="bold")
    period = f"{matched.minute.min():%Y-%m-%d} to {matched.minute.max():%Y-%m-%d}"
    fig.supxlabel(f"Retrospective {period} · no fault labels · lower flag rate is not proof of better detection", fontsize=9)
    fig.savefig(output_dir / "matched_flag_rates.png", dpi=180, facecolor="white")
    plt.close(fig)
    summary = {
        "status": "RETROSPECTIVE_DIAGNOSTIC_ONLY_NOT_RELEASE_SELECTION",
        "row_grain": "machine x module x five-minute qualified Cold window",
        "source_timezone": "NOT_ENCODED_UNVERIFIED",
        "matched_start": str(matched.minute.min()),
        "matched_end": str(matched.minute.max()),
        "v1_scored_rows": len(old), "v2_scored_rows": len(new),
        "matched_rows": len(matched),
        "v1_only_rows": len(old) - len(matched),
        "v2_only_rows": len(new) - len(matched),
        "matched_rates": overall,
        "limits": [
            "Historical outer test was inspected before designing the v2 Valve floor",
            "This comparison cannot select features/thresholds or establish fault accuracy",
            "Different profile coverage produces unmatched rows; headline full-sample rates are not a matched comparison",
            "No approved MySQL Active Profiles, source timezone/units, service epochs, or prospective holdout",
        ],
    }
    (output_dir / "matched_comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output or root / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized"
    print(json.dumps(run(root, output), indent=2))


if __name__ == "__main__":
    main()
