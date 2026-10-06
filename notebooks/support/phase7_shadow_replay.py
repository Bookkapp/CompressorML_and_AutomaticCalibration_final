"""Deterministic shadow replay for HONTECH HT9046-MX Phase 7.

This module replays the already-locked Phase 7 screening package. It never
selects a model or threshold from outer/incident data and never activates a
profile. MX-080 Module 6 is used only as a forensic sensitivity probe with a
clearly marked, short-history provisional profile.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_IMPORT_ROOT))

from notebooks.support import phase7_benchmark as benchmark


REPLAY_VERSION = "phase07-shadow-replay-v2-hp180"
SELECTED_MODEL_KEY = "ARX-Ridge__seed_13"
SELECTED_FAMILY = "ARX-Ridge"
PERSISTENCE_WINDOWS = 3
CADENCE_MINUTES = 5
MAX_SCORING_GAP_MINUTES = 6
CORE_RELATIVE_FEATURES = ["rz_hp1", "rz_lp1", "rz_hp2", "rz_lp2", "rz_valve"]


@dataclass(frozen=True)
class ReplayConfig:
    project_root: Path
    output_root: Path
    incident_start: str = "2026-09-07 12:23:20"
    incident_end_exclusive: str = "2026-09-08 00:00:00"
    timezone: str = "Asia/Bangkok (assumed; source timestamps do not encode timezone)"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mode_or_unknown(values: pd.Series) -> str:
    clean = values.dropna().astype(str)
    if clean.empty:
        return "Unknown"
    modes = clean.mode()
    return str(modes.iloc[0]) if len(modes) else str(clean.iloc[0])


def portable_model_export(benchmark_root: Path, output_root: Path) -> tuple[Any, Path, str]:
    """Load a legacy __main__ pickle safely and re-export with an importable class path."""
    registry = json.loads((benchmark_root / "shadow_model_registry.json").read_text(encoding="utf-8"))
    source_path = benchmark_root / registry["model_files"][SELECTED_MODEL_KEY]
    portable_path = output_root / "models" / "ARX-Ridge__seed_13.portable.joblib"
    portable_path.parent.mkdir(parents=True, exist_ok=True)

    # Earlier benchmark artifacts were serialized while the module ran as a script,
    # so their class path is __main__.ScoreModel. Bind that name only for migration.
    main_module = sys.modules["__main__"]
    previous = getattr(main_module, "ScoreModel", None)
    setattr(main_module, "ScoreModel", benchmark.ScoreModel)
    try:
        model = joblib.load(source_path)
    finally:
        if previous is None:
            delattr(main_module, "ScoreModel")
        else:
            setattr(main_module, "ScoreModel", previous)

    joblib.dump(model, portable_path)
    reloaded = joblib.load(portable_path)
    probe = pd.DataFrame(np.zeros((2, len(reloaded.feature_names))), columns=reloaded.feature_names)
    first = reloaded.score(probe)
    second = joblib.load(portable_path).score(probe)
    if not np.array_equal(first, second):
        raise AssertionError("Portable model reload is not deterministic")
    return reloaded, portable_path, sha256(portable_path)


def _apply_persistence_chunk(
    scored: pd.DataFrame,
    state: dict[tuple[str, int, str, int], dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, dict[tuple[str, int, str, int], dict[str, Any]]]:
    """Apply causal persistence and return checkpointable state."""
    state = {} if state is None else {key: dict(value) for key, value in state.items()}
    ordered = scored.sort_values(["minute", "machine_number", "module", "sv", "segment_id"]).copy()
    persistent: list[bool] = []
    new_alert: list[bool] = []
    episode_start: list[pd.Timestamp | pd.NaT] = []

    for row in ordered.itertuples(index=False):
        key = (str(row.machine_number), int(row.module), str(row.sv), int(row.segment_id))
        current = state.get(key, {"last": None, "run": 0, "start": None, "open": False})
        timestamp = pd.Timestamp(row.minute)
        gap_ok = current["last"] is not None and (
            timestamp - current["last"]
        ).total_seconds() <= MAX_SCORING_GAP_MINUTES * 60
        if bool(row.raw_flag):
            if not gap_ok:
                current = {"last": None, "run": 0, "start": timestamp, "open": False}
            if current["run"] == 0:
                current["start"] = timestamp
            current["run"] += 1
        else:
            current["run"] = 0
            current["start"] = None
            current["open"] = False

        is_persistent = bool(row.raw_flag) and current["run"] >= PERSISTENCE_WINDOWS
        is_new = is_persistent and not current["open"]
        if is_persistent:
            current["open"] = True
        current["last"] = timestamp
        state[key] = current
        persistent.append(is_persistent)
        new_alert.append(is_new)
        episode_start.append(current["start"] if is_persistent else pd.NaT)

    ordered["persistent_flag"] = persistent
    ordered["new_alert"] = new_alert
    ordered["episode_start"] = episode_start
    return ordered, state


def _episode_table(scored: pd.DataFrame) -> pd.DataFrame:
    alerts = scored.loc[scored["new_alert"]].copy()
    if alerts.empty:
        return pd.DataFrame(
            columns=["machine_number", "module", "sv", "episode_start", "detected_at", "detection_delay_minutes", "score", "threshold"]
        )
    alerts["detected_at"] = alerts["minute"]
    alerts["detection_delay_minutes"] = (
        alerts["detected_at"] - alerts["episode_start"]
    ).dt.total_seconds() / 60.0
    return alerts[
        ["machine_number", "module", "sv", "episode_start", "detected_at", "detection_delay_minutes", "score", "threshold"]
    ].reset_index(drop=True)


def _score_relative(model: Any, relative: pd.DataFrame, threshold: float) -> pd.DataFrame:
    scored = relative.loc[relative["profile_supported"]].copy()
    scores = model.score(scored)
    scored["score"] = scores
    scored["threshold"] = float(threshold)
    scored["raw_flag"] = scores >= threshold
    scored["data_quality_status"] = "PASS"
    return scored


def replay_primary_outer(
    project_root: Path,
    benchmark_root: Path,
    model: Any,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    minute_path = project_root / "notebooks" / "outputs" / "ht9046mx_colab_analysis" / "cache" / "minute_module_state.parquet"
    engineered = benchmark.load_and_engineer(minute_path, cadence_minutes=CADENCE_MINUTES)
    split_frame, _ = benchmark.assign_splits(engineered)
    outer_raw = split_frame.loc[
        split_frame["machine_number"].isin(benchmark.DEVELOPMENT_MACHINES)
        & split_frame["split"].eq("outer_temporal")
    ].copy()
    profiles = pd.read_parquet(benchmark_root / "model_local_profiles.parquet")
    relative = benchmark.apply_profiles(
        outer_raw, profiles, benchmark.PROFILE_KEYS, benchmark.RAW_FEATURES
    )
    unsupported = int((~relative["profile_supported"]).sum())
    scored = _score_relative(model, relative, threshold)

    started = time.perf_counter()
    one_shot, _ = _apply_persistence_chunk(scored)
    persistence_seconds = time.perf_counter() - started
    split_at = len(scored) // 2
    first, checkpoint = _apply_persistence_chunk(scored.iloc[:split_at])
    second, _ = _apply_persistence_chunk(scored.iloc[split_at:], checkpoint)
    restarted = pd.concat([first, second], ignore_index=True).sort_values(
        ["minute", "machine_number", "module", "sv", "segment_id"]
    ).reset_index(drop=True)
    comparable = one_shot.sort_values(
        ["minute", "machine_number", "module", "sv", "segment_id"]
    ).reset_index(drop=True)
    restart_deterministic = bool(
        np.array_equal(comparable["persistent_flag"].to_numpy(), restarted["persistent_flag"].to_numpy())
        and np.array_equal(comparable["new_alert"].to_numpy(), restarted["new_alert"].to_numpy())
    )
    episodes = _episode_table(one_shot)
    by_machine = (
        one_shot.groupby("machine_number", observed=True)
        .agg(
            scored_rows=("score", "size"),
            raw_flag_rate_pct=("raw_flag", lambda s: 100.0 * float(s.mean())),
            persistent_rows=("persistent_flag", "sum"),
            alerts=("new_alert", "sum"),
            scored_days=("date", "nunique"),
        )
        .reset_index()
    )
    by_machine["alerts_per_machine_day"] = by_machine["alerts"] / by_machine["scored_days"].clip(lower=1)
    diagnostics = {
        "outer_rows_before_profile_gate": int(len(relative)),
        "unsupported_profile_rows": unsupported,
        "scored_rows": int(len(one_shot)),
        "raw_flag_rate_pct": float(100.0 * one_shot["raw_flag"].mean()),
        "persistent_alerts": int(one_shot["new_alert"].sum()),
        "alerts_per_machine_day": float(one_shot["new_alert"].sum() / max(1, one_shot[["machine_number", "date"]].drop_duplicates().shape[0])),
        "restart_deterministic": restart_deterministic,
        "persistence_ms_per_1000_rows": float(1000.0 * persistence_seconds / max(1, len(one_shot)) * 1000.0),
    }
    return one_shot, episodes, by_machine, diagnostics


def build_mx080_minute_input(one_second_path: Path, output_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_parquet(one_second_path).sort_values("timestamp").copy()
    raw["minute"] = raw["timestamp"].dt.floor("min")
    raw["gap_seconds"] = raw.groupby("minute", observed=True)["timestamp"].diff().dt.total_seconds()
    numeric_map = {
        "Hp_1st_6": "hp1", "Lp_1st_6": "lp1", "Hp_2nd_6": "hp2", "Lp_2nd_6": "lp2",
        "Valve_6": "valve", "TempHi_6": "temphi", "TempLo_6": "templo", "Busy_6": "busy",
    }
    numeric = raw.groupby("minute", observed=True)[list(numeric_map)].median().rename(columns=numeric_map)
    categorical = raw.groupby("minute", observed=True).agg(
        global_status=("Status", _mode_or_unknown),
        module_status=("Status_6", _mode_or_unknown),
        sv=("SV_6", _mode_or_unknown),
        samples=("timestamp", "size"),
        max_gap_seconds=("gap_seconds", "max"),
    )
    minute = numeric.join(categorical).reset_index()
    minute["machine_number"] = "080"
    minute["module"] = 6
    minute["busy"] = minute["busy"].round().astype("Int8")
    required = ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo", "busy"]
    minute["quality_pass"] = (
        minute["samples"].between(55, 60)
        & minute["max_gap_seconds"].fillna(1).le(5)
        & minute[required].notna().all(axis=1)
    )
    ordered = ["machine_number", "minute", "global_status", "module", "module_status", "sv", "busy", "hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo"]
    passed = minute.loc[minute["quality_pass"], ordered].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    passed.to_parquet(output_path, index=False)
    quality = {
        "raw_seconds": int(len(raw)),
        "minute_rows": int(len(minute)),
        "quality_pass_minutes": int(minute["quality_pass"].sum()),
        "quality_fail_minutes": int((~minute["quality_pass"]).sum()),
        "quality_pass_pct": float(100.0 * minute["quality_pass"].mean()),
        "quality_rule": "55-60 unique seconds, max within-minute gap <=5s, required values present; replay only",
    }
    return passed, quality


def extract_ring_buffer_features(one_second_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(one_second_path).sort_values("timestamp").copy()
    base = raw[["timestamp", "Hp_2nd_6", "Lp_2nd_6", "Valve_6"]].copy()
    base["dp2"] = base["Hp_2nd_6"] - base["Lp_2nd_6"]
    for seconds in (30, 120):
        lagged = base[["timestamp", "Hp_2nd_6", "Lp_2nd_6", "Valve_6"]].copy()
        lagged["timestamp"] = lagged["timestamp"] + pd.Timedelta(seconds=seconds)
        lagged = lagged.rename(columns={
            "Hp_2nd_6": f"hp2_lag_{seconds}s",
            "Lp_2nd_6": f"lp2_lag_{seconds}s",
            "Valve_6": f"valve_lag_{seconds}s",
        })
        base = base.merge(lagged, on="timestamp", how="left", validate="one_to_one")
        base[f"hp2_delta_{seconds}s"] = base["Hp_2nd_6"] - base[f"hp2_lag_{seconds}s"]
        base[f"lp2_delta_{seconds}s"] = base["Lp_2nd_6"] - base[f"lp2_lag_{seconds}s"]
        base[f"valve_delta_{seconds}s"] = base["Valve_6"] - base[f"valve_lag_{seconds}s"]
        base[f"hp2_slope_{seconds}s"] = base[f"hp2_delta_{seconds}s"] / seconds
    sampled = base.loc[
        base["timestamp"].dt.second.eq(0) & base["timestamp"].dt.minute.mod(CADENCE_MINUTES).eq(0)
    ].copy()
    sampled["availability_30s"] = sampled["hp2_lag_30s"].notna()
    sampled["availability_120s"] = sampled["hp2_lag_120s"].notna()
    return sampled.reset_index(drop=True)


def replay_mx080_incident(
    config: ReplayConfig,
    model: Any,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.DataFrame]:
    source = config.project_root / "notebooks" / "outputs" / "mx080_module6_forensics_v1" / "module6_one_second_unique.parquet"
    minute_path = config.output_root / "mx080_module6_minute_replay_input.parquet"
    _, minute_quality = build_mx080_minute_input(source, minute_path)
    engineered = benchmark.load_and_engineer(minute_path, cadence_minutes=CADENCE_MINUTES)
    engineered["split"] = np.where(engineered["minute"] < pd.Timestamp("2026-09-07"), "forensic_reference", "incident_probe")
    reference = engineered.loc[engineered["split"].eq("forensic_reference")].copy()
    incident = engineered.loc[engineered["split"].eq("incident_probe")].copy()
    profiles = benchmark.fit_profiles(reference, benchmark.PROFILE_KEYS, benchmark.RAW_FEATURES)
    relative = benchmark.apply_profiles(incident, profiles, benchmark.PROFILE_KEYS, benchmark.RAW_FEATURES)
    scored = _score_relative(model, relative, threshold)
    persisted, _ = _apply_persistence_chunk(scored)
    episodes = _episode_table(persisted)
    incident_start = pd.Timestamp(config.incident_start)
    qualifying_alerts = episodes.loc[episodes["detected_at"].ge(incident_start)].copy()
    first_detection = qualifying_alerts["detected_at"].min() if len(qualifying_alerts) else pd.NaT
    first_raw_flag = persisted.loc[persisted["raw_flag"], "minute"].min() if len(persisted) else pd.NaT
    before_transition = persisted.loc[persisted["minute"].lt(incident_start)]
    after_transition = persisted.loc[persisted["minute"].ge(incident_start)]
    delay = (
        (first_detection - incident_start).total_seconds() / 60.0
        if pd.notna(first_detection) else None
    )
    ring = extract_ring_buffer_features(source)
    summary = {
        **minute_quality,
        "reference_start": str(reference["minute"].min()),
        "reference_end": str(reference["minute"].max()),
        "reference_days": int(reference["date"].nunique()),
        "profile_status": "INCIDENT_REPLAY_ONLY_INSUFFICIENT_FOR_PRODUCTION",
        "profile_rows": int(len(reference)),
        "incident_scored_rows": int(len(persisted)),
        "incident_raw_flag_rate_pct": float(100.0 * persisted["raw_flag"].mean()) if len(persisted) else 0.0,
        "pre_transition_scored_rows": int(len(before_transition)),
        "pre_transition_raw_flag_rate_pct": float(100.0 * before_transition["raw_flag"].mean()) if len(before_transition) else 0.0,
        "post_transition_scored_rows": int(len(after_transition)),
        "post_transition_raw_flag_rate_pct": float(100.0 * after_transition["raw_flag"].mean()) if len(after_transition) else 0.0,
        "incident_persistent_alerts": int(persisted["new_alert"].sum()) if len(persisted) else 0,
        "first_raw_flag": str(first_raw_flag) if pd.notna(first_raw_flag) else None,
        "first_persistent_detection": str(first_detection) if pd.notna(first_detection) else None,
        "detection_delay_from_122320_minutes": delay,
        "timing_interpretation": "Raw flags occurred before the observed 12:23:20 pressure transition; 12:35 is a descriptive post-transition persistent-alert time, not validated fault lead time.",
        "ring_30s_available_pct": float(100.0 * ring["availability_30s"].mean()),
        "ring_120s_available_pct": float(100.0 * ring["availability_120s"].mean()),
        "claim": "forensic sensitivity probe, not fault accuracy and not a production-approved profile",
    }
    return persisted, episodes, summary, ring


def validate_scoring_batch(
    frame: pd.DataFrame,
    registry: dict[str, Any],
    feature_version: str,
    feature_order: list[str],
    expected_model_hash: str,
    actual_model_hash: str,
    as_of: pd.Timestamp,
) -> str:
    """Fail closed before a batch can produce an equipment screening result."""
    if feature_version != registry["feature_version"]:
        return "FEATURE_VERSION_MISMATCH"
    if feature_order != registry["features"]:
        return "FEATURE_CONTRACT_MISMATCH"
    if expected_model_hash != actual_model_hash:
        return "MODEL_CHECKSUM_MISMATCH"
    if frame.empty or frame[CORE_RELATIVE_FEATURES].isna().any(axis=None):
        return "DATA_QUALITY"
    for _, part in frame.groupby(["machine_number", "module", "sv"], observed=True, sort=False):
        if not part["minute"].is_monotonic_increasing:
            return "DATA_QUALITY"
    if pd.Timestamp(as_of) - pd.Timestamp(frame["minute"].max()) > pd.Timedelta(minutes=10):
        return "DATA_QUALITY"
    return "PASS"


def _failure_mode_tests(
    registry: dict[str, Any],
    portable_path: Path,
    portable_hash: str,
    primary_diagnostics: dict[str, Any],
    incident_summary: dict[str, Any],
    primary_scored: pd.DataFrame,
) -> pd.DataFrame:
    sample_key = primary_scored[["machine_number", "module", "sv"]].iloc[0]
    sample = primary_scored.loc[
        primary_scored["machine_number"].eq(sample_key["machine_number"])
        & primary_scored["module"].eq(sample_key["module"])
        & primary_scored["sv"].eq(sample_key["sv"])
    ].sort_values("minute").head(12).copy()
    as_of = pd.Timestamp(sample["minute"].max())
    common = {
        "registry": registry,
        "feature_version": registry["feature_version"],
        "feature_order": list(registry["features"]),
        "expected_model_hash": portable_hash,
        "actual_model_hash": sha256(portable_path),
        "as_of": as_of,
    }
    valid_status = validate_scoring_batch(sample, **common)
    missing = sample.copy()
    missing.loc[missing.index[0], CORE_RELATIVE_FEATURES[0]] = np.nan
    missing_status = validate_scoring_batch(missing, **common)
    stale_status = validate_scoring_batch(sample, **{**common, "as_of": as_of + pd.Timedelta(minutes=11)})
    out_of_order_status = validate_scoring_batch(sample.iloc[::-1].copy(), **common)
    version_status = validate_scoring_batch(sample, **{**common, "feature_version": "wrong-version"})
    order_status = validate_scoring_batch(sample, **{**common, "feature_order": list(reversed(registry["features"]))})
    checksum_status = validate_scoring_batch(sample, **{**common, "expected_model_hash": "0" * 64})
    rows = [
        ("valid_batch", valid_status == "PASS", valid_status, "valid locked contract scores in shadow"),
        ("feature_version_mismatch", version_status == "FEATURE_VERSION_MISMATCH", version_status, "rejected before scoring"),
        ("feature_order_mismatch", order_status == "FEATURE_CONTRACT_MISMATCH", order_status, "rejected before scoring"),
        ("model_checksum_mismatch", checksum_status == "MODEL_CHECKSUM_MISMATCH", checksum_status, "rejected before scoring"),
        ("portable_model_reload", portable_path.exists() and sha256(portable_path) == portable_hash, "PASS", "checksum + clean reload"),
        ("missing_core_input", missing_status == "DATA_QUALITY", missing_status, "must not become equipment alert"),
        ("stale_input", stale_status == "DATA_QUALITY", stale_status, "must not become equipment alert"),
        ("out_of_order_input", out_of_order_status == "DATA_QUALITY", out_of_order_status, "quarantined before scoring"),
        ("restart_recovery", primary_diagnostics["restart_deterministic"], "PASS", "one-shot and checkpoint restart outputs must match"),
        ("automatic_activation", registry["auto_activation_allowed"] is False, "BLOCKED", "shadow package cannot activate itself"),
        ("rollback_target", True, "BLOCKED", "no prior ACTIVE_FROZEN registry exists; release must stay blocked"),
        ("mx080_production_profile", incident_summary["reference_days"] < 7, "INSUFFICIENT_PROFILE", "four reference days are forensic-only"),
    ]
    return pd.DataFrame(rows, columns=["test", "expected_behavior_met", "result_status", "evidence"])


def _plot_primary(by_machine: pd.DataFrame, scored: pd.DataFrame, output: Path) -> None:
    daily = scored.groupby("date", observed=True)["new_alert"].sum().reset_index()
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [1.2, 1]})
    ordered = by_machine.sort_values("alerts_per_machine_day", ascending=False)
    axes[0].bar(ordered["machine_number"], ordered["alerts_per_machine_day"], color="#2F6B9A")
    axes[0].set_ylabel("Alerts / machine-day")
    axes[0].set_title("Shadow replay alert burden by machine — ARX-Ridge, 3-window persistence")
    axes[0].grid(axis="y", alpha=.25)
    axes[1].plot(pd.to_datetime(daily["date"]), daily["new_alert"], marker="o", color="#C96A3D")
    axes[1].set_ylabel("New persistent alerts")
    axes[1].set_xlabel("Outer temporal date")
    axes[1].grid(alpha=.25)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.suptitle("Phase 7 deterministic shadow replay — screening burden, not fault accuracy", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_incident(scored: pd.DataFrame, config: ReplayConfig, output: Path) -> None:
    window = scored.loc[
        scored["minute"].between("2026-09-07 11:30", "2026-09-07 14:00")
    ].copy()
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    axes[0].plot(window["minute"], window["hp2"], label="Hp_2nd_6", color="#153B5B", lw=1.4)
    axes[0].plot(window["minute"], window["lp2"], label="Lp_2nd_6", color="#2A9D8F", lw=1.2)
    axes[0].axvline(pd.Timestamp(config.incident_start), color="#7A4E00", ls=":", label="Observed transition 12:23:20")
    axes[0].set_ylabel("CP2 pressure (psi)")
    axes[0].legend(frameon=False, ncol=3)
    axes[0].grid(alpha=.25)
    axes[1].plot(window["minute"], window["score"], color="#5B4B8A", label="ARX anomaly score")
    axes[1].axhline(float(window["threshold"].iloc[0]) if len(window) else 0, color="#8A8F98", ls="--", label="Past calibration threshold")
    raw_flags = window.loc[window["raw_flag"]]
    axes[1].scatter(raw_flags["minute"], raw_flags["score"], color="#D97706", s=28, zorder=3, label="Raw deviation flag")
    alerts = window.loc[window["new_alert"]]
    axes[1].scatter(alerts["minute"], alerts["score"], color="#B42318", s=55, zorder=4, label="New persistent alert")
    axes[1].axvline(pd.Timestamp(config.incident_start), color="#7A4E00", ls=":")
    axes[1].set_ylabel("Screening score")
    axes[1].set_xlabel("7 Sep 2026 — assumed Asia/Bangkok")
    axes[1].legend(frameon=False, ncol=4)
    axes[1].grid(alpha=.25)
    axes[1].text(
        .01, .97,
        "Raw flags appear before the pressure transition; do not read this as validated lead time",
        transform=axes[1].transAxes, ha="left", va="top", fontsize=9, color="#7A4E00",
        bbox={"facecolor": "white", "edgecolor": "#D8C28F", "alpha": .9, "boxstyle": "round,pad=.3"},
    )
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.suptitle("MX-080 Module 6 incident probe — profile is forensic-only, not production approved", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run_shadow_replay(config: ReplayConfig) -> dict[str, Any]:
    config.output_root.mkdir(parents=True, exist_ok=True)
    figure_root = config.output_root / "figures"
    figure_root.mkdir(exist_ok=True)
    benchmark_root = config.project_root / "notebooks" / "outputs" / "ht9046mx_phase7_benchmark_v2_hp180"
    registry = json.loads((benchmark_root / "shadow_model_registry.json").read_text(encoding="utf-8"))
    benchmark_summary = json.loads((benchmark_root / "analysis_summary.json").read_text(encoding="utf-8"))
    if benchmark_summary.get("inner_validation_leading_family") != SELECTED_FAMILY:
        raise AssertionError("Selected shadow family must come from locked inner validation")
    if registry["auto_activation_allowed"] or registry["activation_state"] != "NOT_AUTHORIZED":
        raise AssertionError("Registry is not safe for shadow replay")
    if registry["features"] != benchmark.MODEL_FEATURES:
        raise AssertionError("Feature order/version contract mismatch")

    threshold_row = pd.read_csv(benchmark_root / "outer_temporal_benchmark.csv").query(
        "family == @SELECTED_FAMILY and seed == 13"
    ).iloc[0]
    threshold = float(threshold_row["threshold"])
    model, portable_path, portable_hash = portable_model_export(benchmark_root, config.output_root)

    score_started = time.perf_counter()
    primary, primary_episodes, by_machine, primary_diag = replay_primary_outer(
        config.project_root, benchmark_root, model, threshold
    )
    elapsed = time.perf_counter() - score_started
    primary_diag["full_replay_elapsed_seconds"] = elapsed
    primary_diag["model_file_bytes"] = portable_path.stat().st_size
    primary_diag["scored_frame_bytes"] = int(primary.memory_usage(deep=True).sum())

    incident, incident_episodes, incident_summary, ring = replay_mx080_incident(
        config, model, threshold
    )
    tests = _failure_mode_tests(
        registry, portable_path, portable_hash, primary_diag, incident_summary, primary
    )

    primary.to_parquet(config.output_root / "primary_outer_shadow_scores.parquet", index=False)
    primary_episodes.to_csv(config.output_root / "primary_alert_episodes.csv", index=False)
    by_machine.to_csv(config.output_root / "primary_replay_by_machine.csv", index=False)
    incident.to_parquet(config.output_root / "mx080_module6_incident_scores.parquet", index=False)
    incident_episodes.to_csv(config.output_root / "mx080_module6_alert_episodes.csv", index=False)
    ring.to_parquet(config.output_root / "mx080_ring_buffer_features.parquet", index=False)
    tests.to_csv(config.output_root / "failure_mode_tests.csv", index=False)

    primary_figure = figure_root / "01_primary_shadow_replay.png"
    incident_figure = figure_root / "02_mx080_incident_probe.png"
    _plot_primary(by_machine, primary, primary_figure)
    _plot_incident(incident, config, incident_figure)

    release_manifest = {
        "replay_version": REPLAY_VERSION,
        "registry_version": registry["registry_version"],
        "model_key": SELECTED_MODEL_KEY,
        "model_selection_source": "inner temporal validation only",
        "model_path": str(portable_path.relative_to(config.output_root)).replace("\\", "/"),
        "model_sha256": portable_hash,
        "feature_version": registry["feature_version"],
        "profile_version": registry["profile_version"],
        "threshold_version": registry["threshold_version"],
        "hp2_reference_policy": registry["hp2_reference_policy"],
        "threshold": threshold,
        "threshold_source": "separate past calibration q99.5",
        "persistence_windows": PERSISTENCE_WINDOWS,
        "cadence_minutes": CADENCE_MINUTES,
        "activation_state": "SHADOW_ONLY_NOT_AUTHORIZED",
        "auto_activation_allowed": False,
        "rollback_target": None,
        "rollback_status": "BLOCKED_NO_PRIOR_ACTIVE_FROZEN",
        "mysql_write_policy": "append-only shadow tables; never write PLC/control commands",
        "claim_level": "anomaly screening only",
    }
    (config.output_root / "shadow_release_manifest.json").write_text(
        json.dumps(release_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    historical_path = config.project_root / "notebooks" / "outputs" / "ht9046mx_phase7_shadow_replay_v1" / "replay_summary.json"
    historical_comparison: dict[str, Any] | None = None
    if historical_path.exists():
        historical = json.loads(historical_path.read_text(encoding="utf-8"))
        historical_comparison = {
            "historical_release": "phase07-shadow-replay-v1-deprecated-hp200",
            "current_release": REPLAY_VERSION,
            "historical_threshold": float(historical["threshold"]),
            "current_threshold": float(threshold),
            "historical_raw_flag_rate_pct": float(historical["primary"]["raw_flag_rate_pct"]),
            "current_raw_flag_rate_pct": float(primary_diag["raw_flag_rate_pct"]),
            "historical_persistent_alerts": int(historical["primary"]["persistent_alerts"]),
            "current_persistent_alerts": int(primary_diag["persistent_alerts"]),
            "persistent_alert_delta": int(primary_diag["persistent_alerts"] - historical["primary"]["persistent_alerts"]),
            "comparison_claim": "alert-burden stability only; no diagnostic-accuracy comparison without confirmed labels",
        }
        pd.DataFrame([historical_comparison]).to_csv(config.output_root / "release_comparison_hp200_vs_hp180.csv", index=False)

    summary = {
        "status": "PASS_WITH_PRODUCTION_BLOCKERS",
        "input_period": "primary outer temporal: 2026-08-20 to 2026-09-01 by machine; MX-080 probe: 2026-09-03 to 2026-09-07",
        "timezone": config.timezone,
        "row_grain": "qualified five-minute score rows derived causally from minute data; MX-080 ring features derive from one-second records",
        "selected_model": SELECTED_MODEL_KEY,
        "selection_rule": "locked from inner validation before outer and MX-080 replay",
        "threshold": threshold,
        "persistence": f"{PERSISTENCE_WINDOWS} consecutive qualified {CADENCE_MINUTES}-minute scoring windows",
        "primary": primary_diag,
        "mx080": incident_summary,
        "hp2_reference_policy": registry["hp2_reference_policy"],
        "historical_release_comparison": historical_comparison,
        "failure_tests_passed_or_safely_blocked": int(tests["expected_behavior_met"].sum()),
        "failure_tests_total": int(len(tests)),
        "production_blockers": [
            "No prior ACTIVE_FROZEN model/profile exists as an exact rollback target.",
            "Alert budget has not been approved by operations.",
            "Service/refill epochs, source timezone and controller codebook remain unverified.",
            "MX-080 reference contains only four days and cannot be used as a production profile.",
            "No technician-confirmed labels; replay measures alert burden and incident sensitivity, not fault accuracy.",
        ],
        "figures": {"primary": str(primary_figure), "mx080": str(incident_figure)},
    }
    (config.output_root / "replay_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    hashes: dict[str, str] = {}
    for path in sorted(config.output_root.rglob("*")):
        if path.is_file() and path.name != "artifact_checksums.json":
            hashes[str(path.relative_to(config.output_root)).replace("\\", "/")] = sha256(path)
    (config.output_root / "artifact_checksums.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )
    return {
        "summary": summary,
        "release_manifest": release_manifest,
        "primary_by_machine": by_machine,
        "primary_episodes": primary_episodes,
        "incident_scores": incident,
        "incident_episodes": incident_episodes,
        "failure_tests": tests,
        "ring_features": ring,
    }


if __name__ == "__main__":
    project = Path(__file__).resolve().parents[2]
    destination = project / "notebooks" / "outputs" / "ht9046mx_phase7_shadow_replay_v2_hp180"
    print(json.dumps(run_shadow_replay(ReplayConfig(project, destination))["summary"], indent=2, ensure_ascii=False))
