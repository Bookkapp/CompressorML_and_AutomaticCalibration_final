"""Leakage-safe Phase 07 benchmark utilities for HT9046MX.

The module is intentionally importable from both a Colab notebook and local QA.
It trains screening models only; no result produced here is a confirmed fault.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import polars as pl
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import RobustScaler, StandardScaler


SEEDS = (13, 29, 47)
DEVELOPMENT_MACHINES = ("017", "022", "024", "029", "041", "057", "058", "070", "072", "081", "082", "083")
EXTERNAL_MACHINES = ("056", "063", "071", "115", "118", "119", "124")
PROFILE_KEYS = ["machine_number", "module", "sv"]
BASE_FEATURES = ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo"]
DERIVED_FEATURES = ["dp1", "dp2", "hp_stage_gap", "lp_stage_gap"]
SLOPE_FEATURES = [f"{name}_slope_15m" for name in BASE_FEATURES]
LAG_FEATURES: list[str] = []
for _lag in (1, 5):
    LAG_FEATURES.append(f"valve_change_{_lag}m")
    for _target in ("hp2", "lp2", "templo"):
        LAG_FEATURES.extend([f"{_target}_response_{_lag}m", f"valve_to_{_target}_gain_{_lag}m"])
RAW_FEATURES = BASE_FEATURES + DERIVED_FEATURES + SLOPE_FEATURES + LAG_FEATURES
RELATIVE_FEATURES = [f"rz_{name}" for name in RAW_FEATURES]
HP2_NORMAL_LOWER_PSI = 180.0
HP2_NORMAL_UPPER_PSI = 230.0
HP2_LOW_FEATURE = "hp2_low_deficit_below_180_10psi"
MODEL_FEATURES = RELATIVE_FEATURES + [HP2_LOW_FEATURE]
CONTEXT_FEATURES = ["sv_binary", "valve", "hp1", "lp1", "temphi", "templo", "valve_slope_15m"]


def _safe_scale(values: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return 0.05
    median = float(values.median())
    mad = float((values - median).abs().median())
    scale = 1.4826 * mad
    return scale if np.isfinite(scale) and scale > 1e-6 else 0.05


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bounded(frame: pd.DataFrame, maximum: int) -> pd.DataFrame:
    if len(frame) <= maximum:
        return frame.copy()
    positions = np.linspace(0, len(frame) - 1, maximum, dtype=int)
    return frame.iloc[positions].copy()


def load_and_engineer(minute_path: Path, cadence_minutes: int = 5, settle_minutes: int = 3) -> pd.DataFrame:
    """Load the minute cache, apply state gates, then build causal features."""
    minute = pl.read_parquet(minute_path).sort(["machine_number", "module", "minute"])
    state = (
        pl.when(
            pl.col("module_status").is_in(["ChangeValve", "MValveHome", "AdjustValve"])
            | (pl.col("busy") == 1)
            | (pl.col("valve") < 0)
        )
        .then(pl.lit("CONTROL_SEQUENCE"))
        .when(
            (pl.col("global_status") == "Run")
            & (pl.col("module_status") == "On")
            & (pl.col("busy") == 0)
            & (pl.col("valve") >= 0)
            & (pl.col("sv") == "Off")
        )
        .then(pl.lit("RUN_ON_SV_OFF"))
        .when(
            (pl.col("global_status") == "Run")
            & (pl.col("module_status") == "On")
            & (pl.col("busy") == 0)
            & (pl.col("valve") >= 0)
            & (pl.col("sv") == "On")
        )
        .then(pl.lit("RUN_ON_SV_ON"))
        .otherwise(pl.lit("UNCLASSIFIED"))
        .alias("state")
    )
    minute = minute.with_columns(state)
    minute = minute.with_columns(
        (
            (pl.col("state") != pl.col("state").shift(1).over(["machine_number", "module"]))
            | (pl.col("minute").diff().over(["machine_number", "module"]).dt.total_minutes() > 2)
        ).alias("segment_start")
    ).with_columns(
        pl.col("segment_start").cast(pl.Int64).cum_sum().over(["machine_number", "module"]).alias("segment_id")
    ).with_columns(
        pl.col("minute").cum_count().over(["machine_number", "module", "segment_id"]).alias("minutes_in_state")
    )
    eligible = minute.filter(
        pl.col("state").is_in(["RUN_ON_SV_OFF", "RUN_ON_SV_ON"])
        & (pl.col("minutes_in_state") >= settle_minutes)
    )
    groups = ["machine_number", "module", "segment_id"]
    eligible = eligible.with_columns(
        (pl.col("hp1") - pl.col("lp1")).alias("dp1"),
        (pl.col("hp2") - pl.col("lp2")).alias("dp2"),
        (pl.col("hp2") - pl.col("hp1")).alias("hp_stage_gap"),
        (pl.col("lp2") - pl.col("lp1")).alias("lp_stage_gap"),
    )
    feature_exprs: list[pl.Expr] = []
    for name in BASE_FEATURES:
        feature_exprs.append((pl.col(name) - pl.col(name).shift(15).over(groups)).alias(f"{name}_slope_15m"))
    for lag in (1, 5):
        valve_change = pl.col("valve") - pl.col("valve").shift(lag).over(groups)
        feature_exprs.append(valve_change.alias(f"valve_change_{lag}m"))
        for target in ("hp2", "lp2", "templo"):
            response = pl.col(target) - pl.col(target).shift(lag).over(groups)
            feature_exprs.append(response.alias(f"{target}_response_{lag}m"))
            feature_exprs.append(
                (response / (valve_change.abs() + 1.0)).alias(f"valve_to_{target}_gain_{lag}m")
            )
    eligible = eligible.with_columns(feature_exprs).filter(pl.col("minute").dt.minute().mod(cadence_minutes) == 0)
    selected = eligible.select(
        "machine_number", "module", "sv", "state", "minute", "segment_id", *RAW_FEATURES
    ).with_columns(
        pl.col("machine_number").cast(pl.Utf8),
        pl.col("minute").dt.date().alias("date"),
        (pl.col("sv") == "On").cast(pl.Int8).alias("sv_binary"),
    )
    return selected.to_pandas()


def assign_splits(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create nested day-level temporal splits before fitting any transform."""
    result = frame.copy()
    result["split"] = "external"
    records: list[dict[str, Any]] = []
    for machine in DEVELOPMENT_MACHINES:
        days = sorted(result.loc[result.machine_number == machine, "date"].unique())
        if len(days) < 5:
            continue
        outer_index = min(len(days) - 1, max(3, int(math.ceil(0.70 * len(days)))))
        early = days[:outer_index]
        outer = days[outer_index:]
        train_end = max(1, int(math.floor(0.60 * len(early))))
        val_end = max(train_end + 1, int(math.floor(0.80 * len(early))))
        val_end = min(val_end, len(early) - 1)
        labels: dict[Any, str] = {}
        labels.update({day: "inner_train" for day in early[:train_end]})
        labels.update({day: "inner_validation" for day in early[train_end:val_end]})
        labels.update({day: "calibration" for day in early[val_end:]})
        labels.update({day: "outer_temporal" for day in outer})
        mask = result.machine_number == machine
        result.loc[mask, "split"] = result.loc[mask, "date"].map(labels)
        records.append(
            {
                "machine_number": machine,
                "source_days": len(days),
                "inner_train_days": train_end,
                "inner_validation_days": val_end - train_end,
                "calibration_days": len(early) - val_end,
                "outer_temporal_days": len(outer),
                "outer_start": str(outer[0]) if outer else "",
            }
        )
    return result, pd.DataFrame(records)


def fit_profiles(frame: pd.DataFrame, keys: list[str], features: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key_values, part in frame.groupby(keys, observed=True, sort=False):
        if not isinstance(key_values, tuple):
            key_values = (key_values,)
        row = dict(zip(keys, key_values))
        row["profile_rows"] = int(len(part))
        row["profile_days"] = int(part["date"].nunique())
        for feature in features:
            values = pd.to_numeric(part[feature], errors="coerce").dropna()
            row[f"{feature}__median"] = float(values.median()) if not values.empty else np.nan
            row[f"{feature}__scale"] = _safe_scale(values)
        rows.append(row)
    return pd.DataFrame(rows)


def apply_profiles(frame: pd.DataFrame, profiles: pd.DataFrame, keys: list[str], features: list[str]) -> pd.DataFrame:
    joined = frame.merge(profiles, on=keys, how="left", validate="many_to_one")
    for feature in features:
        joined[f"rz_{feature}"] = np.clip(
            (joined[feature] - joined[f"{feature}__median"]) / joined[f"{feature}__scale"], -25, 25
        )
    # Field-owner rule v2: 180–230 psi is the qualified reference band.
    # Only the lower boundary contributes to undercharge screening. Values
    # above 230 psi remain visible to the multivariate/local-deviation lanes;
    # they are not interpreted as undercharge.
    joined[HP2_LOW_FEATURE] = np.maximum(0.0, HP2_NORMAL_LOWER_PSI - joined["hp2"]) / 10.0
    joined["profile_supported"] = joined[f"{features[0]}__median"].notna()
    return joined


@dataclass
class ScoreModel:
    family: str
    params: dict[str, Any]
    feature_names: list[str]
    imputer: Any = None
    scaler: Any = None
    estimator: Any = None
    train_sorted: Any = None

    def fit(self, frame: pd.DataFrame) -> "ScoreModel":
        matrix = frame[self.feature_names].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        matrix = self.imputer.fit_transform(matrix)
        if self.family == "Robust-MAD":
            return self
        if self.family == "PCA-SPE":
            self.scaler = StandardScaler().fit(matrix)
            scaled = self.scaler.transform(matrix)
            self.estimator = PCA(n_components=self.params["variance"], svd_solver="full").fit(scaled)
        elif self.family == "IsolationForest":
            self.estimator = IsolationForest(
                n_estimators=self.params["n_estimators"],
                max_samples=self.params["max_samples"],
                max_features=self.params["max_features"],
                contamination="auto",
                random_state=self.params["seed"],
                n_jobs=-1,
            ).fit(matrix)
        elif self.family in {"ECOD", "COPOD"}:
            self.train_sorted = np.sort(matrix, axis=0)
        elif self.family == "ARX-Ridge":
            target_names = ["rz_hp2", "rz_lp2"]
            predictor_names = [name for name in self.feature_names if name not in target_names]
            target_positions = [self.feature_names.index(name) for name in target_names]
            predictor_positions = [self.feature_names.index(name) for name in predictor_names]
            self.params["target_positions"] = target_positions
            self.params["predictor_positions"] = predictor_positions
            self.scaler = StandardScaler().fit(matrix[:, predictor_positions])
            predictors = self.scaler.transform(matrix[:, predictor_positions])
            self.estimator = Ridge(alpha=self.params["alpha"]).fit(predictors, matrix[:, target_positions])
        else:
            raise ValueError(f"Unknown family: {self.family}")
        return self

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        matrix = frame[self.feature_names].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        matrix = self.imputer.transform(matrix)
        if self.family == "Robust-MAD":
            return np.quantile(np.abs(matrix), self.params["feature_quantile"], axis=1)
        if self.family == "PCA-SPE":
            scaled = self.scaler.transform(matrix)
            reconstructed = self.estimator.inverse_transform(self.estimator.transform(scaled))
            return np.mean((scaled - reconstructed) ** 2, axis=1)
        if self.family == "IsolationForest":
            return -self.estimator.score_samples(matrix)
        if self.family in {"ECOD", "COPOD"}:
            n_train = self.train_sorted.shape[0]
            probabilities = np.empty_like(matrix, dtype=float)
            for column in range(matrix.shape[1]):
                ranks = np.searchsorted(self.train_sorted[:, column], matrix[:, column], side="right")
                cdf = (ranks + 0.5) / (n_train + 1.0)
                probabilities[:, column] = np.minimum(cdf, 1.0 - cdf)
            surprise = -np.log(np.clip(probabilities, 1.0 / (n_train + 1.0), 0.5))
            if self.family == "ECOD":
                return np.quantile(surprise, self.params["feature_quantile"], axis=1)
            top_k = min(self.params["top_k"], surprise.shape[1])
            return np.partition(surprise, -top_k, axis=1)[:, -top_k:].sum(axis=1)
        if self.family == "ARX-Ridge":
            p = self.params["predictor_positions"]
            t = self.params["target_positions"]
            prediction = self.estimator.predict(self.scaler.transform(matrix[:, p]))
            return np.max(np.abs(matrix[:, t] - prediction), axis=1)
        raise ValueError(self.family)


def parameter_grid() -> dict[str, list[dict[str, Any]]]:
    return {
        "Robust-MAD": [{"feature_quantile": q} for q in (0.80, 0.90, 1.0)],
        "PCA-SPE": [{"variance": v} for v in (0.80, 0.90, 0.95)],
        "ECOD": [{"feature_quantile": q} for q in (0.90, 1.0)],
        "COPOD": [{"top_k": k} for k in (3, 5)],
        "ARX-Ridge": [{"alpha": a} for a in (0.1, 1.0, 10.0)],
        "IsolationForest": [
            {"n_estimators": 200, "max_samples": 256, "max_features": 0.7},
            {"n_estimators": 300, "max_samples": 1024, "max_features": 0.7},
            {"n_estimators": 300, "max_samples": 1024, "max_features": 1.0},
        ],
    }


def _rate_by_machine(frame: pd.DataFrame, flagged: np.ndarray) -> tuple[float, float, float]:
    scored = frame[["machine_number"]].copy()
    scored["flag"] = flagged.astype(float)
    rates = 100.0 * scored.groupby("machine_number", observed=True)["flag"].mean()
    return float(scored.flag.mean() * 100.0), float(rates.max()), float(rates.quantile(0.75) - rates.quantile(0.25))


def tune_families(inner_train: pd.DataFrame, inner_validation: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    train = _bounded(inner_train.sort_values("minute"), 60_000)
    validation = _bounded(inner_validation.sort_values("minute"), 50_000)
    rows: list[dict[str, Any]] = []
    for family, configurations in parameter_grid().items():
        for configuration in configurations:
            seeds = SEEDS if family == "IsolationForest" else (SEEDS[0],)
            for seed in seeds:
                params = dict(configuration)
                if family == "IsolationForest":
                    params["seed"] = seed
                started = time.perf_counter()
                model = ScoreModel(family, params, MODEL_FEATURES).fit(train)
                train_scores = model.score(train)
                validation_scores = model.score(validation)
                threshold = float(np.quantile(train_scores, 0.995))
                overall, worst, iqr = _rate_by_machine(validation, validation_scores >= threshold)
                probe = validation.copy()
                probe["rz_hp2"] = np.clip(probe["rz_hp2"] - 3.0, -25, 25)
                probe["rz_lp2"] = np.clip(probe["rz_lp2"] - 2.0, -25, 25)
                probe["rz_valve"] = np.clip(probe["rz_valve"] + 1.5, -25, 25)
                probe[HP2_LOW_FEATURE] = probe[HP2_LOW_FEATURE] + 3.0
                probe_rate = float(100.0 * np.mean(model.score(probe) >= threshold))
                objective = abs(math.log((overall + 0.05) / 0.55)) + 0.04 * worst + 0.02 * iqr
                rows.append(
                    {
                        "family": family,
                        "params_json": json.dumps(configuration, sort_keys=True),
                        "seed": seed,
                        "inner_validation_flag_pct": overall,
                        "inner_validation_worst_machine_pct": worst,
                        "inner_validation_machine_iqr_pct": iqr,
                        "synthetic_low_pressure_probe_pct": probe_rate,
                        "selection_objective": objective,
                        "fit_score_seconds": time.perf_counter() - started,
                        "threshold_source": "inner_train_q99.5",
                    }
                )
    search = pd.DataFrame(rows)
    selected: dict[str, dict[str, Any]] = {}
    for family, part in search.groupby("family", sort=False):
        grouped = part.groupby("params_json", as_index=False).agg(
            selection_objective=("selection_objective", "median"),
            inner_validation_flag_pct=("inner_validation_flag_pct", "median"),
            inner_validation_worst_machine_pct=("inner_validation_worst_machine_pct", "max"),
        )
        best = grouped.sort_values(["selection_objective", "inner_validation_worst_machine_pct"]).iloc[0]
        selected[family] = json.loads(best.params_json)
    return search, selected


def _score_final_family(
    family: str,
    params: dict[str, Any],
    fit_frame: pd.DataFrame,
    calibration: pd.DataFrame,
    test: pd.DataFrame,
    seed: int,
) -> tuple[dict[str, Any], ScoreModel, pd.DataFrame]:
    configured = dict(params)
    if family == "IsolationForest":
        configured["seed"] = seed
    fit_sample = _bounded(fit_frame.sort_values("minute"), 80_000)
    calibration_sample = _bounded(calibration.sort_values("minute"), 60_000)
    started = time.perf_counter()
    model = ScoreModel(family, configured, MODEL_FEATURES).fit(fit_sample)
    calibration_scores = model.score(calibration_sample)
    threshold = float(np.quantile(calibration_scores, 0.995))
    score_started = time.perf_counter()
    test_scores = model.score(test)
    score_seconds = time.perf_counter() - score_started
    flagged = test_scores >= threshold
    overall, worst, iqr = _rate_by_machine(test, flagged)
    scored = test[["machine_number", "module", "sv", "minute", "date", "hp2", HP2_LOW_FEATURE]].copy()
    scored["family"] = family
    scored["seed"] = seed
    scored["anomaly_score"] = test_scores
    scored["threshold"] = threshold
    scored["flag"] = flagged
    row = {
        "family": family,
        "seed": seed,
        "n_fit": len(fit_sample),
        "n_calibration": len(calibration_sample),
        "n_test": len(test),
        "flag_rate_pct": overall,
        "worst_machine_flag_pct": worst,
        "machine_iqr_pct": iqr,
        "threshold": threshold,
        "fit_seconds": time.perf_counter() - started,
        "score_ms_per_1000_rows": 1000.0 * score_seconds / max(1, len(test)) * 1000.0,
        "threshold_source": "separate_past_calibration_q99.5",
        "claim_level": "screening_stability_not_fault_accuracy",
    }
    return row, model, scored


def benchmark_models(
    relative: pd.DataFrame,
    selected: dict[str, dict[str, Any]],
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, ScoreModel]]:
    fit_frame = relative[relative.split.isin(["inner_train", "inner_validation"]) & relative.profile_supported]
    calibration = relative[(relative.split == "calibration") & relative.profile_supported]
    outer = relative[(relative.split == "outer_temporal") & relative.profile_supported]
    temporal_rows: list[dict[str, Any]] = []
    score_frames: list[pd.DataFrame] = []
    exported_models: dict[str, ScoreModel] = {}
    for family, params in selected.items():
        print(f"Temporal benchmark: {family}", flush=True)
        seeds = SEEDS if family == "IsolationForest" else (SEEDS[0],)
        for seed in seeds:
            row, model, scores = _score_final_family(family, params, fit_frame, calibration, outer, seed)
            temporal_rows.append(row)
            score_frames.append(scores)
            exported_models[f"{family}__seed_{seed}"] = model
    temporal = pd.DataFrame(temporal_rows)
    all_scores = pd.concat(score_frames, ignore_index=True)

    lomo_rows: list[dict[str, Any]] = []
    for held_out in DEVELOPMENT_MACHINES:
        test = outer[outer.machine_number == held_out]
        if test.empty:
            continue
        for family, params in selected.items():
            # Multi-seed robustness is measured on the untouched temporal test.
            # LOMO uses one locked seed to keep the matched 12-fold run practical.
            seeds = (SEEDS[0],)
            for seed in seeds:
                print(f"LOMO {held_out}: {family}", flush=True)
                train_fold = fit_frame[fit_frame.machine_number != held_out]
                calibration_fold = calibration[calibration.machine_number != held_out]
                row, _, _ = _score_final_family(family, params, train_fold, calibration_fold, test, seed)
                row["held_out_machine"] = held_out
                lomo_rows.append(row)
    lomo = pd.DataFrame(lomo_rows)
    all_scores.to_parquet(output_dir / "scored_outer_temporal.parquet", index=False)
    return temporal, lomo, all_scores, exported_models


def benchmark_external(
    external_relative: pd.DataFrame,
    selected: dict[str, dict[str, Any]],
    fitted_models: dict[str, ScoreModel],
    calibration_relative: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    calibration_sample = _bounded(calibration_relative.sort_values("minute"), 60_000)
    for family, params in selected.items():
        seeds = SEEDS if family == "IsolationForest" else (SEEDS[0],)
        for seed in seeds:
            key = f"{family}__seed_{seed}"
            model = fitted_models[key]
            threshold = float(np.quantile(model.score(calibration_sample), 0.995))
            for machine, test in external_relative.groupby("machine_number", observed=True):
                if test.empty:
                    continue
                scores = model.score(test)
                rows.append(
                    {
                        "family": family,
                        "seed": seed,
                        "machine_number": machine,
                        "n_scored": len(test),
                        "flag_rate_pct": float(100.0 * np.mean(scores >= threshold)),
                        "threshold_source": "development_calibration_q99.5",
                        "profile_source": "development_fleet_module_sv",
                    }
                )
    return pd.DataFrame(rows)


def _fit_regime_models(fit_frame: pd.DataFrame, n_clusters: int = 3) -> dict[tuple[str, int], dict[str, Any]]:
    models: dict[tuple[str, int], dict[str, Any]] = {}
    for (machine, module), part in fit_frame.groupby(["machine_number", "module"], observed=True):
        clean = part.dropna(subset=CONTEXT_FEATURES)
        if len(clean) < 150:
            continue
        sample = _bounded(clean.sort_values("minute"), 10_000)
        scaler = RobustScaler().fit(sample[CONTEXT_FEATURES])
        matrix = scaler.transform(sample[CONTEXT_FEATURES])
        k = min(n_clusters, max(2, len(sample) // 75))
        clusterer = KMeans(n_clusters=k, random_state=SEEDS[0], n_init=10).fit(matrix)
        models[(str(machine), int(module))] = {"scaler": scaler, "clusterer": clusterer, "n_fit": len(sample)}
    return models


def _assign_regime(frame: pd.DataFrame, models: dict[tuple[str, int], dict[str, Any]]) -> pd.DataFrame:
    assigned_parts: list[pd.DataFrame] = []
    for (machine, module), part in frame.groupby(["machine_number", "module"], observed=True):
        item = models.get((str(machine), int(module)))
        current = part.copy()
        current["regime"] = np.nan
        if item is not None:
            valid = current[CONTEXT_FEATURES].notna().all(axis=1)
            current.loc[valid, "regime"] = item["clusterer"].predict(
                item["scaler"].transform(current.loc[valid, CONTEXT_FEATURES])
            )
        assigned_parts.append(current)
    return pd.concat(assigned_parts, ignore_index=True) if assigned_parts else frame.assign(regime=np.nan)


def compare_profile_strategies(split_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare MM, MM+SV, and MM+learned-regime on untouched future rows."""
    fit_frame = split_frame[split_frame.split.isin(["inner_train", "inner_validation"]) & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    calibration = split_frame[(split_frame.split == "calibration") & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    outer = split_frame[(split_frame.split == "outer_temporal") & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)].copy()
    regime_models = _fit_regime_models(fit_frame)
    fit_regime = _assign_regime(fit_frame, regime_models)
    calibration_regime = _assign_regime(calibration, regime_models)
    outer_regime = _assign_regime(outer, regime_models)

    strategies = {
        "Machine+Module": (["machine_number", "module"], fit_frame, calibration, outer),
        "Machine+Module+SV": (["machine_number", "module", "sv"], fit_frame, calibration, outer),
        "Machine+Module+LearnedRegime": (["machine_number", "module", "regime"], fit_regime, calibration_regime, outer_regime),
    }
    comparison_rows: list[dict[str, Any]] = []
    assignment_rows: list[pd.DataFrame] = []
    example_rows: list[dict[str, Any]] = []
    for name, (keys, train, cal, test) in strategies.items():
        train = train.dropna(subset=keys + ["hp2"])
        cal = cal.dropna(subset=keys + ["hp2"])
        test = test.dropna(subset=keys + ["hp2"])
        profile = fit_profiles(train, keys, ["hp2"])
        profile = profile[profile.profile_rows >= 50]
        # Keep this one-variable diagnostic unbounded. Clipping is useful for
        # multivariate model stability but would hide an under-supported regime
        # by forcing both its threshold and extreme residuals to the same cap.
        cal_scored = cal.merge(profile, on=keys, how="left", validate="many_to_one")
        cal_scored["profile_supported"] = cal_scored["hp2__median"].notna()
        cal_scored["rz_hp2"] = (cal_scored.hp2 - cal_scored.hp2__median) / cal_scored.hp2__scale
        cal_scored = cal_scored[cal_scored.profile_supported]
        test_scored = test.merge(profile, on=keys, how="left", validate="many_to_one")
        test_scored["profile_supported"] = test_scored["hp2__median"].notna()
        test_scored["rz_hp2"] = (test_scored.hp2 - test_scored.hp2__median) / test_scored.hp2__scale
        supported = test_scored[test_scored.profile_supported].copy()
        threshold = float(np.quantile(np.abs(cal_scored.rz_hp2), 0.995)) if len(cal_scored) else np.nan
        supported["flag"] = np.abs(supported.rz_hp2) >= threshold
        machine_rates = 100 * supported.groupby("machine_number", observed=True).flag.mean()
        comparison_rows.append(
            {
                "strategy": name,
                "profile_count": len(profile),
                "outer_rows": len(test_scored),
                "supported_outer_rows": len(supported),
                "support_pct": 100.0 * len(supported) / max(1, len(test_scored)),
                "median_abs_hp2_rz": float(np.median(np.abs(supported.rz_hp2))) if len(supported) else np.nan,
                "outer_flag_rate_pct": float(100.0 * supported.flag.mean()) if len(supported) else np.nan,
                "worst_machine_flag_pct": float(machine_rates.max()) if len(machine_rates) else np.nan,
                "threshold": threshold,
                "threshold_source": "separate_past_calibration_q99.5",
            }
        )
        if name == "Machine+Module+LearnedRegime":
            assignment = (
                pd.concat([fit_regime.assign(period="fit"), outer_regime.assign(period="outer")])
                .dropna(subset=["regime"])
                .groupby(["machine_number", "module", "regime", "sv", "period"], observed=True)
                .agg(rows=("hp2", "size"), hp2_median=("hp2", "median"), valve_median=("valve", "median"))
                .reset_index()
            )
            assignment_rows.append(assignment)
            for (machine, module), part in assignment[assignment.period == "fit"].groupby(["machine_number", "module"], observed=True):
                if part.regime.nunique() >= 2:
                    spread = part.hp2_median.max() - part.hp2_median.min()
                    example_rows.append({"machine_number": machine, "module": module, "regime_hp2_median_spread_psi": spread, "regimes": int(part.regime.nunique()), "rows": int(part.rows.sum())})
    assignments = pd.concat(assignment_rows, ignore_index=True) if assignment_rows else pd.DataFrame()
    examples = pd.DataFrame(example_rows).sort_values("regime_hp2_median_spread_psi", ascending=False) if example_rows else pd.DataFrame()
    return pd.DataFrame(comparison_rows), assignments, examples


def _sequence_detector_scores(frame: pd.DataFrame, detector: str, parameter: float) -> np.ndarray:
    """Causal one-sided scores reset at every qualified state segment."""
    scored = pd.Series(index=frame.index, dtype=float)
    grouping = ["machine_number", "module", "sv", "segment_id"]
    for _, part in frame.sort_values(grouping + ["minute"]).groupby(grouping, observed=True, sort=False):
        signal = np.maximum(0.0, -part.rz_hp2.fillna(0.0).to_numpy(dtype=float))
        output = np.zeros(len(part), dtype=float)
        if detector == "EWMA":
            level = 0.0
            for i, value in enumerate(signal):
                level = parameter * value + (1.0 - parameter) * level
                output[i] = level
        elif detector == "CUSUM":
            cumulative = 0.0
            for i, value in enumerate(signal):
                cumulative = max(0.0, cumulative + value - parameter)
                output[i] = cumulative
        elif detector == "Page-Hinkley":
            mean = 0.0
            cumulative = 0.0
            minimum = 0.0
            for i, value in enumerate(signal, start=1):
                mean += (value - mean) / i
                cumulative += value - mean - parameter
                minimum = min(minimum, cumulative)
                output[i - 1] = cumulative - minimum
        else:
            raise ValueError(detector)
        scored.loc[part.index] = output
    return scored.loc[frame.index].to_numpy(dtype=float)


def benchmark_streaming_detectors(relative: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inner_train = relative[(relative.split == "inner_train") & relative.profile_supported].copy()
    inner_validation = relative[(relative.split == "inner_validation") & relative.profile_supported].copy()
    calibration = relative[(relative.split == "calibration") & relative.profile_supported].copy()
    outer = relative[(relative.split == "outer_temporal") & relative.profile_supported].copy()
    grids = {"EWMA": (0.05, 0.10, 0.20), "CUSUM": (0.25, 0.50, 0.75), "Page-Hinkley": (0.05, 0.10, 0.25)}
    search_rows: list[dict[str, Any]] = []
    selected: dict[str, float] = {}
    bounded_train = _bounded(inner_train.sort_values("minute"), 80_000)
    bounded_validation = _bounded(inner_validation.sort_values("minute"), 60_000)
    for detector, values in grids.items():
        for parameter in values:
            train_score = _sequence_detector_scores(bounded_train, detector, parameter)
            validation_score = _sequence_detector_scores(bounded_validation, detector, parameter)
            threshold = float(np.quantile(train_score, 0.995))
            overall, worst, iqr = _rate_by_machine(bounded_validation, validation_score >= threshold)
            objective = abs(math.log((overall + 0.05) / 0.55)) + 0.04 * worst + 0.02 * iqr
            search_rows.append({"detector": detector, "parameter": parameter, "inner_validation_flag_pct": overall, "inner_validation_worst_machine_pct": worst, "selection_objective": objective, "threshold_source": "inner_train_q99.5"})
        candidate = pd.DataFrame([row for row in search_rows if row["detector"] == detector]).sort_values("selection_objective").iloc[0]
        selected[detector] = float(candidate.parameter)
    result_rows: list[dict[str, Any]] = []
    for detector, parameter in selected.items():
        calibration_score = _sequence_detector_scores(calibration, detector, parameter)
        threshold = float(np.quantile(calibration_score, 0.995))
        started = time.perf_counter()
        outer_score = _sequence_detector_scores(outer, detector, parameter)
        elapsed = time.perf_counter() - started
        overall, worst, iqr = _rate_by_machine(outer, outer_score >= threshold)
        result_rows.append({"family": detector, "parameter": parameter, "n_calibration": len(calibration), "n_test": len(outer), "flag_rate_pct": overall, "worst_machine_flag_pct": worst, "machine_iqr_pct": iqr, "threshold": threshold, "score_ms_per_1000_rows": 1000.0 * elapsed / max(1, len(outer)) * 1000.0, "threshold_source": "separate_past_calibration_q99.5", "signal": "one_sided_negative_rz_hp2", "claim_level": "screening_stability_not_fault_accuracy"})
    return pd.DataFrame(search_rows), pd.DataFrame(result_rows)


def benchmark_feature_ablation(relative: pd.DataFrame, selected_iforest: dict[str, Any]) -> pd.DataFrame:
    fit_frame = relative[relative.split.isin(["inner_train", "inner_validation"]) & relative.profile_supported]
    calibration = relative[(relative.split == "calibration") & relative.profile_supported]
    outer = relative[(relative.split == "outer_temporal") & relative.profile_supported]
    stages = {
        "A_absolute_core": BASE_FEATURES,
        "B_relative_core": [f"rz_{name}" for name in BASE_FEATURES] + [HP2_LOW_FEATURE],
        "C_relative_differential_slope": [f"rz_{name}" for name in BASE_FEATURES + DERIVED_FEATURES + SLOPE_FEATURES] + [HP2_LOW_FEATURE],
        "D_plus_1minute_response": [name for name in MODEL_FEATURES if not ("_5m" in name)],
        "E_plus_5minute_response": MODEL_FEATURES,
    }
    rows: list[dict[str, Any]] = []
    for stage, features in stages.items():
        params = dict(selected_iforest)
        params["seed"] = SEEDS[0]
        fit_sample = _bounded(fit_frame.sort_values("minute"), 80_000)
        calibration_sample = _bounded(calibration.sort_values("minute"), 60_000)
        model = ScoreModel("IsolationForest", params, list(features)).fit(fit_sample)
        threshold = float(np.quantile(model.score(calibration_sample), 0.995))
        started = time.perf_counter()
        scores = model.score(outer)
        elapsed = time.perf_counter() - started
        overall, worst, iqr = _rate_by_machine(outer, scores >= threshold)
        rows.append({"feature_stage": stage, "feature_count": len(features), "outer_flag_rate_pct": overall, "outer_worst_machine_pct": worst, "outer_machine_iqr_pct": iqr, "threshold": threshold, "score_ms_per_1000_rows": 1000.0 * elapsed / max(1, len(outer)) * 1000.0, "selection_status": "predeclared_ablation_not_selected_from_outer"})
    return pd.DataFrame(rows)


def run_postprocess(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Rebuild corrected regime, streaming and ablation evidence without retraining all LOMO folds."""
    minute_path = project_root / "notebooks" / "outputs" / "ht9046mx_colab_analysis" / "cache" / "minute_module_state.parquet"
    engineered = load_and_engineer(minute_path)
    split_frame, _ = assign_splits(engineered)
    regime_comparison, regime_assignments, regime_examples = compare_profile_strategies(split_frame)
    regime_comparison.to_csv(output_dir / "regime_strategy_comparison.csv", index=False)
    regime_assignments.to_csv(output_dir / "regime_assignment_summary.csv", index=False)
    regime_examples.head(50).to_csv(output_dir / "regime_examples.csv", index=False)

    fit_raw = split_frame[split_frame.split.isin(["inner_train", "inner_validation"]) & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    local_profiles = fit_profiles(fit_raw, PROFILE_KEYS, RAW_FEATURES)
    dev_raw = split_frame[split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    dev_relative = apply_profiles(dev_raw, local_profiles, PROFILE_KEYS, RAW_FEATURES)
    stream_search, stream_result = benchmark_streaming_detectors(dev_relative)
    stream_search.to_csv(output_dir / "streaming_inner_hpo_search.csv", index=False)
    stream_result.to_csv(output_dir / "streaming_detector_benchmark.csv", index=False)
    selected = json.loads((output_dir / "selected_hyperparameters.json").read_text(encoding="utf-8"))
    ablation = benchmark_feature_ablation(dev_relative, selected["IsolationForest"])
    ablation.to_csv(output_dir / "feature_ablation_temporal.csv", index=False)

    summary_path = output_dir / "analysis_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["regime_strategies"] = regime_comparison.to_dict(orient="records")
    summary.pop("best_stability_family", None)
    summary["family_selection_status"] = "NOT_SELECTED_FROM_OUTER_TESTS"
    summary["inner_validation_leading_family"] = str(
        pd.read_csv(output_dir / "inner_hpo_search.csv").sort_values("selection_objective").iloc[0].family
    )
    summary["streaming_detectors"] = stream_result.to_dict(orient="records")
    summary["feature_ablation_status"] = "reported_for_diagnostics_only_not_used_for_post_outer_selection"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    hashes = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_checksums.json":
            hashes[str(path.relative_to(output_dir)).replace("\\", "/")] = _sha256(path)
    (output_dir / "artifact_checksums.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return summary


def run_benchmark(project_root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    minute_path = project_root / "notebooks" / "outputs" / "ht9046mx_colab_analysis" / "cache" / "minute_module_state.parquet"
    started = time.perf_counter()
    print("Phase 07: load, qualify and engineer", flush=True)
    engineered = load_and_engineer(minute_path)
    split_frame, split_manifest = assign_splits(engineered)
    split_manifest.to_csv(output_dir / "nested_temporal_split_manifest.csv", index=False)
    split_counts = split_frame.groupby(["split", "machine_number"], observed=True).size().reset_index(name="rows")
    split_counts.to_csv(output_dir / "split_row_counts.csv", index=False)

    print("Phase 07: compare profile key strategies", flush=True)
    regime_comparison, regime_assignments, regime_examples = compare_profile_strategies(split_frame)
    regime_comparison.to_csv(output_dir / "regime_strategy_comparison.csv", index=False)
    regime_assignments.to_csv(output_dir / "regime_assignment_summary.csv", index=False)
    regime_examples.head(50).to_csv(output_dir / "regime_examples.csv", index=False)

    inner_train_raw = split_frame[(split_frame.split == "inner_train") & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    inner_val_raw = split_frame[(split_frame.split == "inner_validation") & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    hpo_profiles = fit_profiles(inner_train_raw, PROFILE_KEYS, RAW_FEATURES)
    inner_train_relative = apply_profiles(inner_train_raw, hpo_profiles, PROFILE_KEYS, RAW_FEATURES)
    inner_val_relative = apply_profiles(inner_val_raw, hpo_profiles, PROFILE_KEYS, RAW_FEATURES)
    print("Phase 07: inner temporal HPO", flush=True)
    search, selected = tune_families(
        inner_train_relative[inner_train_relative.profile_supported],
        inner_val_relative[inner_val_relative.profile_supported],
    )
    search.to_csv(output_dir / "inner_hpo_search.csv", index=False)
    (output_dir / "selected_hyperparameters.json").write_text(json.dumps(selected, indent=2, sort_keys=True), encoding="utf-8")

    fit_raw = split_frame[split_frame.split.isin(["inner_train", "inner_validation"]) & split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    local_profiles = fit_profiles(fit_raw, PROFILE_KEYS, RAW_FEATURES)
    dev_raw = split_frame[split_frame.machine_number.isin(DEVELOPMENT_MACHINES)]
    dev_relative = apply_profiles(dev_raw, local_profiles, PROFILE_KEYS, RAW_FEATURES)
    local_profiles.to_parquet(output_dir / "model_local_profiles.parquet", index=False)

    print("Phase 07: untouched temporal and LOMO evaluation", flush=True)
    temporal, lomo, outer_scores, fitted_models = benchmark_models(dev_relative, selected, output_dir)
    temporal.to_csv(output_dir / "outer_temporal_benchmark.csv", index=False)
    lomo.to_csv(output_dir / "lomo_benchmark.csv", index=False)

    fleet_profiles = fit_profiles(fit_raw, ["module", "sv"], RAW_FEATURES)
    external_raw = split_frame[split_frame.machine_number.isin(EXTERNAL_MACHINES)]
    external_relative = apply_profiles(external_raw, fleet_profiles, ["module", "sv"], RAW_FEATURES)
    external_relative = external_relative[external_relative.profile_supported]
    calibration_relative = dev_relative[(dev_relative.split == "calibration") & dev_relative.profile_supported]
    print("Phase 07: sparse external challenge", flush=True)
    external = benchmark_external(external_relative, selected, fitted_models, calibration_relative)
    external.to_csv(output_dir / "external_sparse_benchmark.csv", index=False)

    aggregate = temporal.groupby("family", as_index=False).agg(
        seeds=("seed", "nunique"),
        temporal_flag_pct_median=("flag_rate_pct", "median"),
        temporal_flag_pct_worst_seed=("flag_rate_pct", "max"),
        temporal_worst_machine_pct=("worst_machine_flag_pct", "max"),
        score_ms_per_1000_rows_median=("score_ms_per_1000_rows", "median"),
    )
    lomo_aggregate = lomo.groupby("family", as_index=False).agg(
        lomo_flag_pct_median=("flag_rate_pct", "median"),
        lomo_worst_fold_pct=("flag_rate_pct", "max"),
    )
    external_aggregate = external.groupby("family", as_index=False).agg(
        external_flag_pct_median=("flag_rate_pct", "median"),
        external_worst_machine_pct=("flag_rate_pct", "max"),
    )
    summary_table = aggregate.merge(lomo_aggregate, on="family", how="left").merge(external_aggregate, on="family", how="left")
    summary_table.to_csv(output_dir / "model_benchmark_summary.csv", index=False)

    # Export every fitted lane as a shadow-only registry package; activation stays forbidden.
    model_paths: dict[str, str] = {}
    model_dir = output_dir / "models"
    model_dir.mkdir(exist_ok=True)
    for key, model in fitted_models.items():
        path = model_dir / f"{key.replace(' ', '_').replace('/', '_')}.joblib"
        joblib.dump(model, path)
        model_paths[key] = str(path.relative_to(output_dir)).replace("\\", "/")
    registry = {
        "registry_version": "phase07-shadow-registry-v2-hp180",
        "feature_version": "minute-relative-regime-hp180-v3",
        "profile_version": "machine-module-sv-train-only-hp180-v3",
        "threshold_version": "past-calibration-q995-hp180-v2",
        "hp2_reference_policy": {
            "qualified_reference_band_psi": [HP2_NORMAL_LOWER_PSI, HP2_NORMAL_UPPER_PSI],
            "undercharge_screening_boundary_psi": HP2_NORMAL_LOWER_PSI,
            "feature": HP2_LOW_FEATURE,
            "high_side_interpretation": "separate local/multivariate deviation evidence; not undercharge and not a water-cause label",
        },
        "activation_state": "NOT_AUTHORIZED",
        "auto_activation_allowed": False,
        "model_files": model_paths,
        "features": MODEL_FEATURES,
        "source_period": {"start": str(split_frame.minute.min()), "end": str(split_frame.minute.max()), "timezone": "not encoded"},
        "split_contract": "day-level nested temporal; inner HPO then separate calibration; outer temporal/LOMO/sparse untouched",
        "claim_level": "anomaly_screening_only",
    }
    (output_dir / "shadow_model_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")

    artifact_hashes = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_checksums.json":
            artifact_hashes[str(path.relative_to(output_dir)).replace("\\", "/")] = _sha256(path)
    (output_dir / "artifact_checksums.json").write_text(json.dumps(artifact_hashes, indent=2), encoding="utf-8")

    summary = {
        "status": "PASS_WITH_CAVEATS",
        "analysis_grain": f"qualified minute features scored every 5 minutes",
        "engineered_rows": int(len(split_frame)),
        "development_machines": len(DEVELOPMENT_MACHINES),
        "external_machines": len(EXTERNAL_MACHINES),
        "model_families": int(summary_table.family.nunique()),
        "model_feature_count": len(MODEL_FEATURES),
        "hp2_reference_policy": {
            "qualified_reference_band_psi": [HP2_NORMAL_LOWER_PSI, HP2_NORMAL_UPPER_PSI],
            "undercharge_screening_boundary_psi": HP2_NORMAL_LOWER_PSI,
            "low_feature": HP2_LOW_FEATURE,
        },
        "regime_strategies": regime_comparison.to_dict(orient="records"),
        "best_stability_family": str(summary_table.sort_values(["temporal_worst_machine_pct", "temporal_flag_pct_median"]).iloc[0].family),
        "elapsed_seconds": time.perf_counter() - started,
        "limits": [
            "No technician-confirmed fault labels; no precision/recall or diagnostic accuracy is reported.",
            "Learned regimes are statistical context clusters, not physical mode labels.",
            "Recipe, target temperature, facility water, service epochs and source timezone remain unavailable.",
            "ECOD/COPOD lanes are transparent empirical-tail implementations and must be revalidated if replaced with another library implementation.",
        ],
    }
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    destination = root / "notebooks" / "outputs" / "ht9046mx_phase7_benchmark_v2_hp180"
    print(json.dumps(run_benchmark(root, destination), indent=2, ensure_ascii=False))
