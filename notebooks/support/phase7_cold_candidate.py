"""Build a non-deployable Cold-only ARX-Ridge shadow candidate from the minute cache.

All profiles and model transforms are fitted on past development data. Inner
validation chooses alpha; a separate past block sets thresholds; future and
leave-one-machine-out rows are descriptive tests, never tuning inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import polars as pl
import sklearn

from apps.api.app.cold_arx import (
    FEATURE_VERSION, PREDICTORS, PROFILE_VERSION, QUANTIZED_FEATURE_VERSION,
    QUANTIZED_PROFILE_VERSION, TARGETS, ColdArxRidge,
)
from notebooks.support.phase7_benchmark import (
    DEVELOPMENT_MACHINES, EXTERNAL_MACHINES, apply_profiles, assign_splits,
    fit_profiles, load_and_engineer,
)


RELEASE_VERSION = "phase07-cold-relationship-candidate-v1"
QUANTIZED_RELEASE_VERSION = "phase07-cold-relationship-candidate-v2-valve-quantized"
STATE = "RUN_ON_SV_OFF"
PROFILE_KEYS = ["machine_number", "module", "sv", "state"]
PROFILE_FEATURES = ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo", "dp1", "dp2"]
SELF_FEATURES = [f"rz_{name}" for name in PROFILE_FEATURES]
INCIDENT_EXCLUSION_DATES = {pd.Timestamp("2026-08-18")}
ALPHAS = (0.1, 1.0, 10.0)
QUARANTINE_SELF_Z = 8.0
PROFILE_MIN_DAYS = 7
PROFILE_MIN_WINDOWS = 200
PERSISTENCE_WINDOWS = 3
VALVE_QUANTIZATION_UNIT = 1.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_qa(path: Path) -> dict:
    scan = pl.scan_parquet(path)
    duplicate_keys = scan.group_by("machine_number", "module", "minute").len().filter(pl.col("len") > 1).select(pl.len()).collect().item()
    if duplicate_keys:
        raise ValueError(f"Source has {duplicate_keys} duplicate machine/module/minute keys")
    summary = scan.select(
        pl.len().alias("source_rows"),
        pl.col("minute").min().alias("source_start"),
        pl.col("minute").max().alias("source_end"),
        pl.col("machine_number").n_unique().alias("source_machines"),
    ).collect().to_dicts()[0]
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in summary.items()} | {"duplicate_keys": 0}


def _self_score(frame: pd.DataFrame) -> pd.Series:
    return frame[SELF_FEATURES].abs().max(axis=1, skipna=False)


def _is_incident_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values).dt.normalize().isin(INCIDENT_EXCLUSION_DATES)


def _fit_local_profiles(raw: pd.DataFrame, quantized_valve: bool) -> pd.DataFrame:
    profiles = fit_profiles(raw, PROFILE_KEYS, PROFILE_FEATURES)
    if quantized_valve:
        valve = pd.to_numeric(raw.valve, errors="coerce").dropna().to_numpy(dtype=float)
        if valve.size == 0 or not np.isfinite(valve).all() or not np.allclose(valve, np.round(valve), rtol=0, atol=1e-8):
            raise ValueError("Quantized-Valve candidate requires integer command values in past fit data")
        # A one-count command shift must not be divided by the generic 0.05
        # zero-MAD fallback. The floor is source resolution, not a test-tuned
        # alarm threshold. It is fitted/applied only inside past profile blocks.
        profiles["valve__scale"] = profiles["valve__scale"].clip(lower=VALVE_QUANTIZATION_UNIT)
    return profiles


def _profiles_from_past(raw: pd.DataFrame, quantized_valve: bool = False) -> tuple[pd.DataFrame, dict]:
    raw = raw.loc[~_is_incident_date(raw.date)].copy()
    preliminary = _fit_local_profiles(raw, quantized_valve)
    first_pass = apply_profiles(raw, preliminary, PROFILE_KEYS, PROFILE_FEATURES)
    first_pass["quarantined"] = _self_score(first_pass).gt(QUARANTINE_SELF_Z)
    group_rates = first_pass.groupby(PROFILE_KEYS, observed=True).quarantined.mean()
    clean = first_pass.loc[~first_pass.quarantined].copy()
    if clean.empty:
        raise ValueError("No past windows survive robust quarantine")
    second = _fit_local_profiles(clean, quantized_valve)
    second = second.loc[
        second.profile_rows.ge(PROFILE_MIN_WINDOWS) & second.profile_days.ge(PROFILE_MIN_DAYS)
    ].copy()
    if second.empty:
        raise ValueError("No local profile meets candidate training coverage")
    return second, {
        "past_rows": int(len(raw)),
        "first_pass_quarantined": int(len(raw) - len(clean)),
        "first_pass_quarantine_pct": float(100 * (len(raw) - len(clean)) / len(raw)),
        "supported_profiles": int(len(second)),
        "profiles_over_5pct_quarantine": int(group_rates.gt(0.05).sum()),
        "worst_profile_quarantine_pct": float(100 * group_rates.max()),
        "valve_scale_floor_source_units": VALVE_QUANTIZATION_UNIT if quantized_valve else None,
        "profiles_using_valve_floor": int(second["valve__scale"].eq(VALVE_QUANTIZATION_UNIT).sum()) if quantized_valve else None,
    }


def _relative_with_lags(raw: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    frame = apply_profiles(raw, profiles, PROFILE_KEYS, PROFILE_FEATURES)
    frame = frame.loc[frame.profile_supported].sort_values(
        ["machine_number", "module", "segment_id", "minute"]
    ).copy()
    frame["self_score"] = _self_score(frame)
    groups = frame.groupby(["machine_number", "module", "segment_id"], sort=False, observed=True)
    for lag in (1, 2):
        earlier_time = groups["minute"].shift(lag)
        elapsed = (frame["minute"] - earlier_time).dt.total_seconds().div(60)
        frame[f"lag{lag}_date"] = groups["date"].shift(lag)
        for name in (("rz_hp2", "rz_lp2", "rz_valve", "rz_temphi", "rz_templo") if lag == 1 else ("rz_hp2", "rz_lp2")):
            value = groups[name].shift(lag)
            frame[f"lag{lag}_{name}"] = value.where(elapsed.eq(5 * lag))
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame.dropna(subset=list(PREDICTORS) + list(TARGETS) + ["self_score"]).copy()


def _fit_rows(frame: pd.DataFrame, splits: tuple[str, ...]) -> pd.DataFrame:
    eligible = frame.loc[frame.split.isin(splits) & ~_is_incident_date(frame.date)].copy()
    eligible = eligible.loc[
        eligible.self_score.le(QUARANTINE_SELF_Z)
        & ~_is_incident_date(eligible.lag1_date)
        & ~_is_incident_date(eligible.lag2_date)
    ]
    return eligible


def _matrices(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return frame.loc[:, PREDICTORS].to_numpy(dtype=float), frame.loc[:, TARGETS].to_numpy(dtype=float)


def _fit_model(train: pd.DataFrame, alpha: float) -> ColdArxRidge:
    if train.empty:
        raise ValueError("No qualified model-fit rows")
    predictors, targets = _matrices(train)
    return ColdArxRidge(alpha=alpha).fit(predictors, targets)


def _scores(model: ColdArxRidge, frame: pd.DataFrame) -> np.ndarray:
    predictors, targets = _matrices(frame)
    return model.score(predictors, targets)


def _select_alpha(train: pd.DataFrame, validation: pd.DataFrame) -> tuple[float, list[dict]]:
    if train.empty or validation.empty:
        raise ValueError("Inner train/validation has insufficient Cold windows")
    results = []
    for alpha in ALPHAS:
        model = _fit_model(train, alpha)
        scores = _scores(model, validation)
        machine_p95 = pd.DataFrame({"machine": validation.machine_number.to_numpy(), "score": scores}).groupby("machine").score.quantile(0.95)
        results.append({
            "alpha": alpha,
            "inner_validation_rows": int(len(scores)),
            "median_abs_residual": float(np.median(scores)),
            "p95_residual": float(np.quantile(scores, 0.95)),
            "worst_machine_p95": float(machine_p95.max()),
        })
    selected = min(results, key=lambda item: (item["worst_machine_p95"], item["p95_residual"], item["alpha"]))
    return float(selected["alpha"]), results


def _persistence(scored: pd.DataFrame, raw_column: str) -> tuple[int, int]:
    episodes = 0
    persistent_windows = 0
    for _, part in scored.sort_values("minute").groupby(["machine_number", "module"], observed=True):
        prior = None
        run = 0
        for when, flag in zip(part.minute, part[raw_column], strict=True):
            contiguous = prior is not None and (when - prior).total_seconds() == 300
            run = run + 1 if bool(flag) and contiguous else (1 if bool(flag) else 0)
            if run == PERSISTENCE_WINDOWS:
                episodes += 1
            if run >= PERSISTENCE_WINDOWS:
                persistent_windows += 1
            prior = when
    return episodes, persistent_windows


def _evaluate(model: ColdArxRidge, threshold: float, self_threshold: float, test: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    scored = test[["machine_number", "module", "minute", "date", "self_score"]].copy()
    scored["dynamic_score"] = _scores(model, test)
    scored["dynamic_flag"] = scored.dynamic_score.ge(threshold)
    scored["self_flag"] = scored.self_score.ge(self_threshold)
    scored["any_flag"] = scored.dynamic_flag | scored.self_flag
    dynamic_episodes, _ = _persistence(scored, "dynamic_flag")
    self_episodes, _ = _persistence(scored, "self_flag")
    or_episodes, or_persistent_windows = _persistence(scored, "any_flag")
    machine = scored.groupby("machine_number", observed=True).agg(
        scored_windows=("any_flag", "size"),
        scored_days=("date", "nunique"),
        dynamic_flags=("dynamic_flag", "sum"),
        self_flags=("self_flag", "sum"),
        any_flags=("any_flag", "sum"),
    ).reset_index()
    machine["any_flag_pct"] = 100 * machine.any_flags / machine.scored_windows
    machine["dynamic_flag_pct"] = 100 * machine.dynamic_flags / machine.scored_windows
    machine["self_flag_pct"] = 100 * machine.self_flags / machine.scored_windows
    metrics = {
        "scored_windows": int(len(scored)),
        "dynamic_flag_pct": float(100 * scored.dynamic_flag.mean()) if len(scored) else None,
        "self_flag_pct": float(100 * scored.self_flag.mean()) if len(scored) else None,
        "any_flag_pct": float(100 * scored.any_flag.mean()) if len(scored) else None,
        "dynamic_persistence_episodes": int(dynamic_episodes),
        "self_persistence_episodes": int(self_episodes),
        "diagnostic_or_persistence_episodes": int(or_episodes),
        "diagnostic_or_persistent_windows": int(or_persistent_windows),
        "worst_machine_any_flag_pct": float(machine.any_flag_pct.max()) if len(machine) else None,
        "worst_machine_dynamic_flag_pct": float(machine.dynamic_flag_pct.max()) if len(machine) else None,
    }
    return metrics, machine


def run(project_root: Path, output_dir: Path, quantized_valve: bool = False) -> dict:
    minute_path = project_root / "notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_qa = _source_qa(minute_path)
    print("Qualifying Cold-only minute windows", flush=True)
    engineered = load_and_engineer(minute_path)
    cold = engineered.loc[(engineered.state == STATE) & (engineered.sv == "Off")].copy()
    split, split_manifest = assign_splits(cold)
    split_manifest.to_csv(output_dir / "split_manifest.csv", index=False)
    development = split.loc[split.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    if development.empty:
        raise ValueError("No development-machine Cold windows")

    inner_train_raw = development.loc[development.split == "inner_train"]
    inner_profiles, inner_profile_qa = _profiles_from_past(inner_train_raw, quantized_valve)
    inner_relative = _relative_with_lags(development.loc[development.split.isin(["inner_train", "inner_validation"])], inner_profiles)
    inner_train = _fit_rows(inner_relative, ("inner_train",))
    inner_validation = _fit_rows(inner_relative, ("inner_validation",))
    alpha, hpo = _select_alpha(inner_train, inner_validation)

    print(f"Fitting Cold ARX (alpha={alpha}) and calibrating on past-only block", flush=True)
    fit_raw = development.loc[development.split.isin(["inner_train", "inner_validation"])]
    profiles, profile_qa = _profiles_from_past(fit_raw, quantized_valve)
    relative = _relative_with_lags(development, profiles)
    fit = _fit_rows(relative, ("inner_train", "inner_validation"))
    calibration = _fit_rows(relative, ("calibration",))
    outer = relative.loc[relative.split == "outer_temporal"].copy()
    if calibration.empty or outer.empty:
        raise ValueError("Calibration or future test has no qualified rows")
    model = _fit_model(fit, alpha)
    dynamic_threshold = float(np.quantile(_scores(model, calibration), 0.995))
    self_threshold = float(np.quantile(calibration.self_score, 0.995))
    if not np.isfinite(dynamic_threshold) or dynamic_threshold <= 0 or not np.isfinite(self_threshold) or self_threshold <= 0:
        raise ValueError("Calibration thresholds are invalid")

    # No threshold, alpha or feature is chosen from the following held-out data.
    temporal_metrics, temporal_machine = _evaluate(model, dynamic_threshold, self_threshold, outer)
    temporal_machine.to_csv(output_dir / "temporal_machine_rates.csv", index=False)
    self_flagged = outer.loc[outer.self_score.ge(self_threshold), ["machine_number", *SELF_FEATURES]].copy()
    self_flagged["dominant_feature"] = self_flagged[SELF_FEATURES].abs().idxmax(axis=1)
    contributors = self_flagged.groupby(["machine_number", "dominant_feature"], observed=True).size().reset_index(name="flagged_windows")
    contributors.to_csv(output_dir / "self_flag_contributors.csv", index=False)
    lomo_rows = []
    for machine in DEVELOPMENT_MACHINES:
        heldout = outer.loc[outer.machine_number == machine]
        if heldout.empty:
            continue
        source_fit = fit.loc[fit.machine_number != machine]
        source_cal = calibration.loc[calibration.machine_number != machine]
        if source_fit.empty or source_cal.empty:
            continue
        source_model = _fit_model(source_fit, alpha)
        source_threshold = float(np.quantile(_scores(source_model, source_cal), 0.995))
        source_self_threshold = float(np.quantile(source_cal.self_score, 0.995))
        result, _ = _evaluate(source_model, source_threshold, source_self_threshold, heldout)
        lomo_rows.append({"held_out_machine": machine, "target_profile_source": "target_inner_train_and_validation_only", "model_source": "other_development_machines", "threshold_source": "other_development_machines_past_calibration", **result})
    pd.DataFrame(lomo_rows).to_csv(output_dir / "lomo_machine_rates.csv", index=False)

    profile_columns = PROFILE_KEYS + ["profile_rows", "profile_days"] + [f"{name}__{suffix}" for name in PROFILE_FEATURES for suffix in ("median", "scale")]
    profiles_path = output_dir / "local_profiles.csv"
    profiles[profile_columns].to_csv(profiles_path, index=False)
    model_path = output_dir / "cold_arx_ridge.joblib"
    joblib.dump(model, model_path)
    reloaded = joblib.load(model_path)
    probe_x, probe_y = _matrices(outer.head(3))
    if not np.allclose(model.score(probe_x, probe_y), reloaded.score(probe_x, probe_y), rtol=0, atol=0):
        raise AssertionError("Portable model reload parity failed")
    release_version = QUANTIZED_RELEASE_VERSION if quantized_valve else RELEASE_VERSION
    manifest = {
        "release_version": release_version,
        "activation_state": "SHADOW_ONLY_NOT_AUTHORIZED",
        "auto_activation_allowed": False,
        "model_family": "ColdARXRidge",
        "model_path": model_path.name,
        "model_sha256": _sha256(model_path),
        "profiles_path": profiles_path.name,
        "profiles_sha256": _sha256(profiles_path),
        "feature_version": QUANTIZED_FEATURE_VERSION if quantized_valve else FEATURE_VERSION,
        "profile_version": QUANTIZED_PROFILE_VERSION if quantized_valve else PROFILE_VERSION,
        "threshold_version": "cold-past-calibration-q995-valve-quantized-v2" if quantized_valve else "cold-past-calibration-q995-v1",
        "valve_scale_policy": "integer-command-floor-one-source-unit-v2" if quantized_valve else "generic-zero-mad-fallback-v1",
        "valve_quantization_unit": VALVE_QUANTIZATION_UNIT if quantized_valve else None,
        "predictors": list(PREDICTORS),
        "targets": list(TARGETS),
        "alpha": alpha,
        "dynamic_threshold": dynamic_threshold,
        "self_threshold": self_threshold,
        "persistence_windows": PERSISTENCE_WINDOWS,
        "cadence_minutes": 5,
        "qualified_state": "Compressor Run + module On + Busy 0 + SV Off + nonnegative Valve + settled",
        "profile_keys": PROFILE_KEYS,
        "profile_source": "OFFLINE_TRAIN_ONLY_NOT_MYSQL_ACTIVE_PROFILE",
        "source_cache_sha256": _sha256(minute_path),
        "source_timezone": "NOT_ENCODED_UNVERIFIED",
        "excluded_fit_dates": [day.date().isoformat() for day in sorted(INCIDENT_EXCLUSION_DATES)],
        "selection_policy": "alpha from inner temporal validation; thresholds from separate past calibration; outer/LOMO descriptive only",
        "runtime_versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "polars": pl.__version__, "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
        "claim_level": "anomaly_screening_only_not_fault_accuracy",
        "production_blockers": ["source timezone and units", "service/refill epochs", "independent prospective holdout", "alert budget", "approved profile and rollback target", "server shadow parity"],
    }
    (output_dir / "candidate_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary = {
        "release_version": release_version,
        "source_qa": source_qa,
        "cold_qualified_5minute_rows": int(len(cold)),
        "development_machines": list(DEVELOPMENT_MACHINES),
        "external_sparse_machines_not_scored": list(EXTERNAL_MACHINES),
        "split_rows": {str(k): int(v) for k, v in development.split.value_counts().items()},
        "inner_profile_qa": inner_profile_qa,
        "final_profile_qa": profile_qa,
        "inner_hpo": hpo,
        "selected_alpha": alpha,
        "fit_windows": int(len(fit)),
        "calibration_windows": int(len(calibration)),
        "dynamic_threshold": dynamic_threshold,
        "self_threshold": self_threshold,
        "temporal": temporal_metrics,
        "top_self_flag_contributors": contributors.groupby("dominant_feature", observed=True).flagged_windows.sum().sort_values(ascending=False).head(6).to_dict(),
        "lomo_machines": len(lomo_rows),
        "lomo_worst_dynamic_flag_pct": max((row["dynamic_flag_pct"] for row in lomo_rows), default=None),
        "status": "SHADOW_CANDIDATE_REVIEW_REQUIRED",
        "review_reasons": ["PROFILE_QUARANTINE_EXCEEDS_5PCT", "SELF_LANE_FUTURE_FLAG_BURDEN", "NO_ACTIVE_PROFILE_OR_APPROVED_MODEL", "SOURCE_TIME_AND_SERVICE_CONTEXT_UNVERIFIED"],
        "limits": ["No confirmed fault labels; rates are not accuracy", "Source timezone and service epochs unverified", "The previously inspected historical outer period is not a fresh unbiased release test", "Conditional peer lane and server scoring are not integrated"],
    }
    (output_dir / "candidate_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--quantized-valve", action="store_true", help="Train the separate v2 one-count Valve-scale-floor candidate")
    args = parser.parse_args()
    root = args.project_root.resolve()
    directory = "ht9046mx_phase7_cold_candidate_v2_valve_quantized" if args.quantized_valve else "ht9046mx_phase7_cold_candidate_v1"
    output = args.output or (root / "notebooks/outputs" / directory)
    print(json.dumps(run(root, output, quantized_valve=args.quantized_valve), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
