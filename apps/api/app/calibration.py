"""Automatic candidate-calibration pipeline for the Server shadow service.

The pipeline reads raw telemetry with a read-only connection, builds profiles
per machine/module/SV/qualified-state from past data, and scores the final
three calendar days as a forward-only shadow window. It only creates immutable
candidates. Promotion requires a separate authenticated human approval call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, create_engine, text

from .config import Settings, get_settings
from .db import connection, source_connection


# Absolute sensor levels catch local drift; pressure differentials preserve a
# relationship feature so a coupled pressure shift is not reduced to seven
# unrelated univariate checks. A profile remains machine/module/state-specific.
FEATURES = ("hp1", "lp1", "hp2", "lp2", "dp1", "dp2", "valve", "temphi", "templo")
SCALE_FLOORS = {"hp1": 0.10, "lp1": 0.10, "hp2": 0.10, "lp2": 0.10, "dp1": 0.10, "dp2": 0.10, "valve": 1.0, "temphi": 0.10, "templo": 0.10}
# The only currently confirmed normal-calibration state is Cold operation:
# compressor ON, expansion valve ON, no manual Busy flag, and bypass SV OFF.
# SV ON belongs to a non-running/hot/post-cold context and needs its own
# source-backed qualification rule before it can form a baseline.
QUALIFIED_STATES = {"COMPRESSOR_ON_COLD_SV_OFF"}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote(identifier: str, *, allow_dots: bool = False) -> str:
    parts = identifier.split(".") if allow_dots else [identifier]
    if not parts or any(not IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return ".".join(f"`{part}`" for part in parts)


def _template(value: str, module: int) -> str:
    try:
        column = value.format(module=module)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid module-column template: {value!r}") from exc
    _quote(column)
    return column


def _values(value: str) -> set[str]:
    return {part.strip().casefold() for part in value.split(",") if part.strip()}


def _stable(minimum: Any, maximum: Any) -> bool:
    return pd.notna(minimum) and pd.notna(maximum) and str(minimum) == str(maximum)


def _state_records(frame: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Expand wide one-minute source rows to qualified long module rows."""
    records: list[dict[str, Any]] = []
    sv_off = _values(settings.source_sv_off_values)
    busy_normal = _values(settings.source_busy_normal_values)
    expected_compressor_on = settings.source_compressor_on_status.casefold()
    expected_on = _values(settings.source_module_on_status)
    for row in frame.itertuples(index=False):
        raw = row._asdict()
        if not _stable(raw["global_status_min"], raw["global_status_max"]):
            continue
        if str(raw["global_status_min"]).casefold() != expected_compressor_on:
            continue
        for module in range(1, 9):
            prefix = f"m{module}_"
            if not all(_stable(raw[f"{prefix}{field}_min"], raw[f"{prefix}{field}_max"])
                       for field in ("status", "busy", "sv")):
                continue
            module_status = str(raw[f"{prefix}status_min"]).casefold()
            busy = str(raw[f"{prefix}busy_min"]).casefold()
            sv_value = str(raw[f"{prefix}sv_min"]).casefold()
            if module_status in {"changevalve", "mvalvehome", "adjustvalve"} or busy not in busy_normal:
                continue
            if (expected_on and module_status not in expected_on) or sv_value not in sv_off:
                continue
            values = {feature: raw[f"{prefix}{feature}"] for feature in ("hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo")}
            if not all(pd.notna(value) and np.isfinite(float(value)) for value in values.values()):
                continue
            if float(values["valve"]) < 0:
                continue
            values["dp1"] = float(values["hp1"]) - float(values["lp1"])
            values["dp2"] = float(values["hp2"]) - float(values["lp2"])
            records.append(
                {
                    "minute": pd.Timestamp(raw["minute"]),
                    "machine_number": str(raw["machine_number"]),
                    "module": module,
                    "sv_state": "Off",
                    "state_code": "COMPRESSOR_ON_COLD_SV_OFF",
                    **{name: float(value) for name, value in values.items()},
                }
            )
    if not records:
        return pd.DataFrame(columns=["minute", "machine_number", "module", "sv_state", "state_code", *FEATURES])
    result = pd.DataFrame.from_records(records).sort_values(["machine_number", "module", "minute"])
    result["previous_minute"] = result.groupby(["machine_number", "module"])["minute"].shift()
    result["previous_state"] = result.groupby(["machine_number", "module"])["state_code"].shift()
    result["new_segment"] = (
        result["previous_minute"].isna()
        | (result["state_code"] != result["previous_state"])
        | ((result["minute"] - result["previous_minute"]).dt.total_seconds() > 120)
    )
    result["segment_id"] = result.groupby(["machine_number", "module"])["new_segment"].cumsum()
    result["minutes_in_state"] = result.groupby(["machine_number", "module", "segment_id"]).cumcount() + 1
    result = result.loc[result["minutes_in_state"] >= settings.profile_settle_minutes].copy()
    result["day"] = result["minute"].dt.date
    return result.drop(columns=["previous_minute", "previous_state", "new_segment"])


def _source_sql(settings: Settings, start: datetime, end: datetime, target_machine: str | None = None) -> tuple[str, dict[str, Any]]:
    table = _quote(settings.source_table, allow_dots=True)
    timestamp = _quote(settings.source_timestamp_column)
    machine = _quote(settings.source_machine_column)
    global_status = _quote(settings.source_global_status_column)
    select = [
        f"CAST(DATE_FORMAT({timestamp}, '%Y-%m-%d %H:%i:00') AS DATETIME) AS minute",
        f"{machine} AS machine_number",
        f"MIN({global_status}) AS global_status_min",
        f"MAX({global_status}) AS global_status_max",
    ]
    fields = {
        "hp1": settings.source_hp1_template, "lp1": settings.source_lp1_template,
        "hp2": settings.source_hp2_template, "lp2": settings.source_lp2_template,
        "valve": settings.source_valve_template, "temphi": settings.source_temp_high_template,
        "templo": settings.source_temp_low_template, "status": settings.source_module_status_template,
        "busy": settings.source_busy_template, "sv": settings.source_sv_template,
    }
    for module in range(1, 9):
        for name, template in fields.items():
            column = _quote(_template(template, module))
            alias = f"m{module}_{name}"
            if name in FEATURES:
                select.append(f"AVG({column}) AS {alias}")
            else:
                select.extend((f"MIN({column}) AS {alias}_min", f"MAX({column}) AS {alias}_max"))
    params: dict[str, Any] = {"start": start, "end": end}
    machine_clause = ""
    if target_machine:
        from .inference import get_machine_candidates
        cands = get_machine_candidates(target_machine)
        machine_clause = f" AND {machine} IN :cands"
        params["cands"] = tuple(cands)
    sql = f"""
        SELECT {', '.join(select)}
        FROM {table}
        WHERE {timestamp} >= :start AND {timestamp} < :end{machine_clause}
        GROUP BY CAST(DATE_FORMAT({timestamp}, '%Y-%m-%d %H:%i:00') AS DATETIME), {machine}
        ORDER BY minute, machine_number
    """
    return sql, params


def _latest_source_time(settings: Settings, target_machine: str | None = None) -> datetime | None:
    table = _quote(settings.source_table, allow_dots=True)
    timestamp = _quote(settings.source_timestamp_column)
    machine = _quote(settings.source_machine_column)
    params: dict[str, Any] = {}
    machine_clause = ""
    if target_machine:
        from .inference import get_machine_candidates
        cands = get_machine_candidates(target_machine)
        machine_clause = f" WHERE {machine} IN :cands"
        params["cands"] = tuple(cands)
    with source_connection() as conn:
        value = conn.execute(text(f"SELECT MAX({timestamp}) AS latest_time FROM {table}{machine_clause}"), params).scalar_one_or_none()
    return pd.Timestamp(value).to_pydatetime() if value is not None else None


def discover_source_machines(settings: Settings | str | None = None) -> list[dict[str, Any]]:
    """Discover distinct machines present in the raw telemetry source table."""
    source_url = None
    table_name = "ht9046mx_readings"
    ts_col = "recorded_at"
    mach_col = "machine_number"

    if isinstance(settings, str):
        source_url = settings
    elif isinstance(settings, Settings):
        if not settings.source_db_host or not settings.source_table:
            return []
        source_url = settings.source_database_url
        table_name = settings.source_table
        ts_col = settings.source_timestamp_column
        mach_col = settings.source_machine_column
    else:
        st = get_settings()
        if not st.source_db_host or not st.source_table:
            return []
        source_url = st.source_database_url
        table_name = st.source_table
        ts_col = st.source_timestamp_column
        mach_col = st.source_machine_column

    table = _quote(table_name, allow_dots=True)
    timestamp = _quote(ts_col)
    machine = _quote(mach_col)
    query = text(f"""
        SELECT {machine} AS machine_number,
               COUNT(*) AS record_count,
               MIN({timestamp}) AS first_event,
               MAX({timestamp}) AS latest_recorded_at
        FROM {table}
        GROUP BY {machine}
        ORDER BY {machine}
    """)
    try:
        if source_url:
            eng = create_engine(source_url)
            with eng.connect() as conn:
                rows = conn.execute(query).mappings().all()
            eng.dispose()
        else:
            with source_connection() as conn:
                rows = conn.execute(query).mappings().all()

        result = []
        for row in rows:
            raw_m = str(row["machine_number"])
            digits = raw_m.upper().replace("MX", "").strip()
            display = f"MX{digits.zfill(3)}" if digits.isdigit() else raw_m
            result.append({
                "machine_number": display,
                "display_name": display,
                "row_count": int(row["record_count"]),
                "record_count": int(row["record_count"]),
                "first_event": str(row["first_event"]) if row["first_event"] else None,
                "last_event": str(row["latest_recorded_at"]) if row["latest_recorded_at"] else None,
                "latest_recorded_at": row["latest_recorded_at"],
            })
        return result
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("discover_source_machines failed: %s", exc)
        return []


def _source_duplicate_key_count(settings: Settings, start: datetime, end: datetime, target_machine: str | None = None) -> int:
    """Fail closed when a wide telemetry row is not unique per machine/timestamp."""
    table = _quote(settings.source_table, allow_dots=True)
    timestamp = _quote(settings.source_timestamp_column)
    machine = _quote(settings.source_machine_column)
    params: dict[str, Any] = {"start": start, "end": end}
    machine_clause = ""
    if target_machine:
        from .inference import get_machine_candidates
        machine_clause = f" AND {machine} IN :machines"
        params["machines"] = get_machine_candidates(target_machine)
    query = text(f"""
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM {table}
            WHERE {timestamp} >= :start AND {timestamp} < :end{machine_clause}
            GROUP BY {machine}, {timestamp}
            HAVING COUNT(*) > 1
        ) AS duplicate_source_keys
    """)
    if target_machine:
        query = query.bindparams(bindparam("machines", expanding=True))
    with source_connection() as conn:
        return int(conn.execute(query, params).scalar_one())


def load_qualified_windows(settings: Settings, start: datetime, end: datetime, target_machine: str | None = None) -> pd.DataFrame:
    sql, params = _source_sql(settings, start, end, target_machine=target_machine)
    with source_connection() as conn:
        minute_frame = pd.read_sql_query(text(sql), conn, params=params)
    return _state_records(minute_frame, settings)



def _scales(frame: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    medians: dict[str, float] = {}
    scales: dict[str, float] = {}
    for feature in FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").dropna()
        median = float(values.median())
        mad_scale = float((values - median).abs().median()) * 1.4826
        q_scale = float((values.quantile(.75) - values.quantile(.25)) / 1.349)
        medians[feature] = median
        scales[feature] = max(SCALE_FLOORS[feature], mad_scale, q_scale)
    return medians, scales


def _deviation(frame: pd.DataFrame, medians: dict[str, float], scales: dict[str, float]) -> pd.Series:
    z = pd.concat([((frame[name] - medians[name]) / scales[name]).abs() for name in FEATURES], axis=1)
    return z.max(axis=1).clip(upper=25.0)


def _half_shift(frame: pd.DataFrame, scales: dict[str, float]) -> float:
    if frame.empty or frame["day"].nunique() < 2:
        return float("inf")
    midpoint = sorted(frame["day"].unique())[len(frame["day"].unique()) // 2]
    first, second = frame.loc[frame["day"] < midpoint], frame.loc[frame["day"] >= midpoint]
    if first.empty or second.empty:
        return float("inf")
    return float(max(abs(first[name].median() - second[name].median()) / scales[name] for name in FEATURES))


def _detailed_stats(frame: pd.DataFrame, medians: dict[str, float], scales: dict[str, float]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for feature in FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").dropna() if not frame.empty else pd.Series(dtype=float)
        p05 = float(values.quantile(0.05)) if not values.empty else 0.0
        p25 = float(values.quantile(0.25)) if not values.empty else 0.0
        p75 = float(values.quantile(0.75)) if not values.empty else 0.0
        p95 = float(values.quantile(0.95)) if not values.empty else 0.0
        min_v = float(values.min()) if not values.empty else 0.0
        max_v = float(values.max()) if not values.empty else 0.0
        med = round(float(medians[feature]), 2)
        sc = round(float(scales[feature]), 2)
        mean_v = float(values.mean()) if not values.empty else med
        std_v = float(values.std()) if not values.empty and not pd.isna(values.std()) else sc
        p10 = float(values.quantile(0.10)) if not values.empty else p05
        p90 = float(values.quantile(0.90)) if not values.empty else p95
        stats[feature] = {
            "median": med,
            "mean": round(mean_v, 2),
            "std": round(std_v, 2),
            "scale": sc,
            "min": round(min_v, 2),
            "max": round(max_v, 2),
            "p10": round(p10, 2),
            "p90": round(p90, 2),
            "p05": round(p05, 2),
            "p25": round(p25, 2),
            "p75": round(p75, 2),
            "p95": round(p95, 2),
        }
        if feature == "hp2":
            stats[feature]["reference_band"] = [180.0, 230.0]
            stats[feature]["in_reference_band"] = 180.0 <= med <= 230.0

    # Feature correlation matrix across all 9 features
    correlations: dict[str, dict[str, float]] = {}
    cols = [col for col in FEATURES if col in frame.columns]
    if len(frame) >= 5 and len(cols) > 1:
        try:
            corr_df = frame[cols].corr().fillna(0.0).round(3)
            correlations = {
                col: {other: float(corr_df.loc[col, other]) for other in cols}
                for col in cols
            }
        except Exception:
            correlations = {}
    stats["detailed_baseline"] = {f: stats[f] for f in FEATURES if f in stats}
    stats["correlations"] = correlations
    return stats


def _extract_fleet_priors(windows: pd.DataFrame, settings: Settings, shadow_start: datetime) -> dict[int, dict[str, Any]]:
    """Extract fleet-wide reference baselines per module from sufficient windows or existing profiles in DB."""
    priors: dict[int, dict[str, Any]] = {}
    if not windows.empty:
        for (mod, sv, st_code), group in windows.groupby(["module", "sv_state", "state_code"], observed=True):
            calib = group.loc[group["minute"] < pd.Timestamp(shadow_start)]
            if len(calib) >= settings.profile_min_calibration_windows:
                meds, scs = _scales(calib)
                priors[int(mod)] = {
                    "medians": meds,
                    "scales": scs,
                    "calibration_windows": len(calib),
                    "frame": calib,
                }
    if len(priors) < 8:
        try:
            with connection() as conn:
                rows = conn.execute(text("""
                    SELECT module, statistics_json, calibration_windows
                    FROM ht9046mx_calibration_profile
                    WHERE calibration_windows >= 50
                      AND profile_status = 'ACTIVE_FROZEN'
                    ORDER BY
                      CASE WHEN machine_number IN ('MX080', '080') THEN 1 ELSE 2 END,
                      calibration_windows DESC
                """)).mappings().all()
                for r in rows:
                    m = int(r["module"])
                    if m not in priors:
                        st = json.loads(r["statistics_json"]) if isinstance(r["statistics_json"], str) else (r["statistics_json"] or {})
                        base = st.get("detailed_baseline", {})
                        if base:
                            meds = {feat: float(base[feat]["mean"]) for feat in FEATURES if feat in base and "mean" in base[feat]}
                            scs = {feat: max(float(base[feat].get("std", SCALE_FLOORS[feat])), SCALE_FLOORS[feat]) for feat in FEATURES if feat in base}
                            if len(meds) == len(FEATURES):
                                priors[m] = {
                                    "medians": meds,
                                    "scales": scs,
                                    "calibration_windows": int(r["calibration_windows"]),
                                    "frame": pd.DataFrame(),
                                }
        except Exception:
            pass
    return priors


def build_candidate_profiles(
    windows: pd.DataFrame,
    settings: Settings,
    shadow_start: datetime,
    target_machine: str | None = None,
) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    fleet_priors = _extract_fleet_priors(windows, settings, shadow_start)
    keys = ["machine_number", "module", "sv_state", "state_code"]
    for key_values, group in windows.groupby(keys, sort=True, observed=True):
        machine_num, mod_num, sv_st, st_code = key_values
        calibration = group.loc[group["minute"] < pd.Timestamp(shadow_start)].copy()
        shadow = group.loc[group["minute"] >= pd.Timestamp(shadow_start)].copy()
        reasons: list[str] = []
        is_insufficient = (
            len(calibration) < settings.profile_min_calibration_windows
            or calibration["day"].nunique() < settings.profile_min_calibration_days
        )
        fleet_prior = fleet_priors.get(int(mod_num))
        is_fleet_bootstrapped = False

        if is_insufficient:
            if fleet_prior:
                # Hierarchical Empirical Bayes (Stein Shrinkage)
                is_fleet_bootstrapped = True
                n_local = len(calibration)
                n_0 = 50.0  # shrinkage scale
                w_local = n_local / (n_local + n_0)
                w_fleet = 1.0 - w_local

                if n_local >= 5:
                    local_meds, local_scs = _scales(calibration)
                    medians = {f: w_local * local_meds[f] + w_fleet * fleet_prior["medians"][f] for f in FEATURES}
                    scales = {f: max(w_local * local_scs[f] + w_fleet * fleet_prior["scales"][f], SCALE_FLOORS[f]) for f in FEATURES}
                else:
                    medians = fleet_prior["medians"].copy()
                    scales = fleet_prior["scales"].copy()

                retained = calibration if not calibration.empty else (fleet_prior["frame"].head(50) if not fleet_prior["frame"].empty else pd.DataFrame(columns=calibration.columns))
                threshold = 3.5  # Conservative deviation threshold for fleet provisional
                quarantine_pct = 0.0
                half_shift = 0.0
                reasons.append("BOOTSTRAPPED_FROM_FLEET_PRIOR")
            else:
                reasons.append("INSUFFICIENT_CALIBRATION_COVERAGE")
                medians = {name: 0.0 for name in FEATURES}
                scales = SCALE_FLOORS.copy()
                retained = calibration
                threshold = None
                quarantine_pct = 0.0
                half_shift = float("inf")
        else:
            initial_medians, initial_scales = _scales(calibration)
            initial_score = _deviation(calibration, initial_medians, initial_scales)
            retained = calibration.loc[initial_score <= settings.profile_quarantine_z].copy()
            quarantine_pct = 100.0 * (1.0 - len(retained) / len(calibration))
            if retained.empty:
                retained = calibration.copy()
                reasons.append("ALL_WINDOWS_QUARANTINED")
            medians, scales = _scales(retained)
            train_score = _deviation(retained, medians, scales)
            threshold = float(train_score.quantile(.995))
            half_shift = _half_shift(retained, scales)
        if quarantine_pct > settings.profile_max_quarantine_pct:
            reasons.append("QUARANTINE_RATE_EXCEEDED")
        if half_shift > settings.profile_max_half_shift_rz:
            reasons.append("CALIBRATION_DRIFT_EXCEEDED")
        shadow = shadow.copy()
        if threshold is not None and not shadow.empty:
            shadow["deviation_score"] = _deviation(shadow, medians, scales)
            shadow["threshold_value"] = threshold
            shadow["raw_flag"] = shadow["deviation_score"] >= threshold
            previous = shadow.groupby(keys)["raw_flag"].shift(1).eq(True)
            previous2 = shadow.groupby(keys)["raw_flag"].shift(2).eq(True)
            minute_gap = shadow.groupby(keys)["minute"].diff().dt.total_seconds().eq(60)
            minute_gap2 = shadow["minute"].sub(shadow.groupby(keys)["minute"].shift(2)).dt.total_seconds().eq(120)
            shadow["persistent_flag"] = shadow["raw_flag"] & previous & previous2 & minute_gap & minute_gap2
        else:
            shadow = shadow.assign(deviation_score=np.nan, threshold_value=np.nan, raw_flag=False, persistent_flag=False)
        shadow_days = int(shadow["day"].nunique())
        shadow_elapsed_hours = float((shadow["minute"].max() - shadow["minute"].min()).total_seconds() / 3600.0) if len(shadow) > 1 else 0.0
        flag_pct = float(100.0 * shadow["raw_flag"].mean()) if len(shadow) else None
        persistent_pct = float(100.0 * shadow["persistent_flag"].mean()) if len(shadow) else None
        if shadow_days < settings.profile_shadow_days:
            reasons.append("SHADOW_DAYS_LT_REQUIRED")
        if len(shadow) < settings.profile_min_shadow_windows:
            reasons.append("SHADOW_WINDOWS_LT_REQUIRED")
        if shadow_elapsed_hours < settings.profile_shadow_days * 24 - 1:
            reasons.append("SHADOW_DURATION_LT_REQUIRED")
        if flag_pct is not None and flag_pct > settings.profile_max_shadow_flag_pct:
            reasons.append("SHADOW_FLAG_RATE_EXCEEDED")
        prerequisites = {
            "STATE_CONTRACT_VERSION": settings.profile_state_contract_version,
            "CONTROLLER_CODEBOOK_VERSION": settings.profile_controller_codebook_version,
            "SERVICE_EPOCH_VERSION": settings.profile_service_epoch_version,
            "SOURCE_TIMEZONE": settings.source_timezone,
        }
        reasons.extend(f"{name}_UNVERIFIED" for name, value in prerequisites.items() if not value.strip())
        if any(reason in reasons for reason in ("QUARANTINE_RATE_EXCEEDED", "CALIBRATION_DRIFT_EXCEEDED", "SHADOW_FLAG_RATE_EXCEEDED", "ALL_WINDOWS_QUARANTINED")):
            status = "REVIEW_REQUIRED"
        elif is_fleet_bootstrapped:
            status = "FLEET_PROVISIONAL"
        elif "INSUFFICIENT_CALIBRATION_COVERAGE" in reasons:
            status = "INSUFFICIENT_DATA"
        elif any(reason in reasons for reason in ("SHADOW_DAYS_LT_REQUIRED", "SHADOW_WINDOWS_LT_REQUIRED", "SHADOW_DURATION_LT_REQUIRED")):
            status = "CANDIDATE_PROFILE"
        elif any(reason.endswith("_UNVERIFIED") for reason in reasons):
            status = "SHADOW_VALIDATION"
        else:
            status = "READY_FOR_APPROVAL"
        stats = _detailed_stats(retained, medians, scales)
        digest_payload = {
            "key": [str(value) for value in key_values],
            "medians": {name: medians[name] for name in FEATURES},
            "scales": {name: scales[name] for name in FEATURES},
            "start": str(calibration.minute.min() if len(calibration) else None),
            "end": str(shadow.minute.max() if len(shadow) else None),
        }
        source_digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()
        profiles.append({
            "key": dict(zip(keys, key_values)), "status": status, "reasons": sorted(set(reasons)),
            "calibration": calibration, "retained": retained, "shadow": shadow,
            "statistics": stats, "threshold": {"deviation_score_q995": threshold, "method": "max_abs_robust_z / retained_calibration_q995"},
            "validation": {"shadow_flag_pct": flag_pct, "persistent_flag_pct": persistent_pct, "max_half_shift_rz": half_shift, "shadow_elapsed_hours": shadow_elapsed_hours},
            "quarantine_pct": quarantine_pct, "source_digest": source_digest,
        })

    # Ensure all 8 modules (1 to 8) exist for target machine or machines in windows
    existing_pairs = {(p["key"]["machine_number"], int(p["key"]["module"])) for p in profiles}
    machines = list(windows["machine_number"].unique()) if not windows.empty else []
    from .inference import clean_machine_code
    if target_machine and clean_machine_code(target_machine) not in {clean_machine_code(str(m)) for m in machines}:
        machines.append(target_machine)
    if not machines and target_machine:
        machines = [target_machine]

    for machine_num in machines:
        for mod_num in range(1, 9):
            if (machine_num, mod_num) not in existing_pairs:
                fleet_prior = fleet_priors.get(mod_num)
                if not fleet_prior:
                    continue
                medians = fleet_prior["medians"].copy()
                scales = fleet_prior["scales"].copy()
                threshold = 3.5
                detailed_baseline = {
                    feat: {
                        "mean": round(float(medians[feat]), 2),
                        "median": round(float(medians[feat]), 2),
                        "std": round(float(scales[feat]), 2),
                        "scale": round(float(scales[feat]), 2),
                        "p10": round(float(medians[feat] - 1.28 * scales[feat]), 2),
                        "p90": round(float(medians[feat] + 1.28 * scales[feat]), 2),
                        "min": round(float(medians[feat] - 2.5 * scales[feat]), 2),
                        "max": round(float(medians[feat] + 2.5 * scales[feat]), 2),
                    }
                    for feat in FEATURES
                }
                stats = {
                    "detailed_baseline": detailed_baseline,
                    "correlations": fleet_prior.get("correlations", {}),
                    "windows": int(fleet_prior.get("calibration_windows", 4255)),
                }
                key_dict = {
                    "machine_number": str(machine_num),
                    "module": int(mod_num),
                    "sv_state": "Off",
                    "state_code": "COMPRESSOR_ON_COLD_SV_OFF",
                }
                digest_payload = {
                    "key": [str(key_dict[k]) for k in keys],
                    "medians": {name: medians[name] for name in FEATURES},
                    "scales": {name: scales[name] for name in FEATURES},
                    "start": None,
                    "end": None,
                }
                source_digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()
                profiles.append({
                    "key": key_dict,
                    "status": "FLEET_PROVISIONAL",
                    "reasons": ["BOOTSTRAPPED_FROM_FLEET_PRIOR", "EXPANDED_FOR_FULL_8_MODULES"],
                    "calibration": pd.DataFrame(),
                    "retained": pd.DataFrame(),
                    "shadow": pd.DataFrame(),
                    "statistics": stats,
                    "threshold": {"deviation_score_q995": threshold, "method": "fleet_prior_robust_z_3.5"},
                    "validation": {"shadow_flag_pct": None, "persistent_flag_pct": None, "max_half_shift_rz": None, "shadow_elapsed_hours": 0.0},
                    "quarantine_pct": 0.0,
                    "source_digest": source_digest,
                })

    profiles.sort(key=lambda p: (p["key"]["machine_number"], int(p["key"]["module"])))
    return profiles


def _last_shadow_end() -> datetime | None:
    with connection() as conn:
        value = conn.execute(text("SELECT MAX(shadow_end) FROM ht9046mx_calibration_batch WHERE batch_status IN ('COMPLETED', 'PARTIALLY_REVIEWED', 'REJECTED', 'APPROVED')")).scalar_one_or_none()
    return pd.Timestamp(value).to_pydatetime() if value is not None else None


def _last_qualified_shadow_end(machine_number: str) -> datetime | None:
    """The retry watermark belongs to this machine and one-minute contract."""
    from .qualified_windows import WINDOW_VERSION
    from .inference import get_machine_candidates
    from sqlalchemy import bindparam

    query = text("""
        SELECT MAX(b.shadow_end)
        FROM ht9046mx_calibration_batch b
        JOIN ht9046mx_calibration_profile p ON p.batch_id = b.batch_id
        WHERE p.machine_number IN :machines AND b.feature_version = :feature_version
          AND b.batch_status IN ('COMPLETED', 'PARTIALLY_REVIEWED', 'REJECTED', 'APPROVED')
    """).bindparams(bindparam("machines", expanding=True))
    with connection() as conn:
        value = conn.execute(query, {"machines": get_machine_candidates(machine_number),
                                     "feature_version": WINDOW_VERSION}).scalar_one_or_none()
    return pd.Timestamp(value).to_pydatetime() if value is not None else None


def run_qualified_one_minute_calibration(
    settings: Settings, *, target_machine: str | None, history_days: int | None,
    shadow_days: int | None, force: bool, target_module: int | None = None,
) -> dict[str, Any]:
    """Scheduled/CLI calculation shares the complete-day Manual reference fit."""
    if settings.database_url is None or settings.source_database_url is None or not settings.source_table.strip():
        return {"status": "SKIPPED_NOT_CONFIGURED"}
    if not settings.source_timezone.strip():
        return {"status": "SKIPPED_SOURCE_TIMEZONE_UNVERIFIED"}
    from .automatic_reference import run_candidate_cycle
    return run_candidate_cycle(settings, target_machine=target_machine, history_days=history_days,
        shadow_days=shadow_days, force=force, target_module=target_module)


def persist_batch(settings: Settings, source_start: datetime, calibration_end: datetime, shadow_start: datetime, shadow_end: datetime, profiles: list[dict[str, Any]], *, transaction=None, reference_review: dict[str, Any] | None = None) -> dict[str, Any]:
    batch_id = str(uuid.uuid4())
    feature_versions = {item.get("feature_version", "minute-state-core-hp180-v2") for item in profiles}
    algorithm_versions = {item.get("algorithm_version", "two-pass-robust-z-v1") for item in profiles}
    if len(feature_versions) != 1 or len(algorithm_versions) != 1:
        raise ValueError("a calibration batch cannot mix feature or algorithm versions")
    feature_version = feature_versions.pop()
    algorithm_version = algorithm_versions.pop()
    version = f"autocalibration-1m-v1-{batch_id[:8]}" if feature_version == "qualified-cold-observed-1m-v1" else f"autocalibration-v1-{batch_id[:8]}"
    manifest = {
        "batch_id": batch_id, "source_timezone": settings.source_timezone,
        "source_table": settings.source_table, "history_days": settings.profile_history_days,
        "shadow_days": settings.profile_shadow_days, "profile_algorithm": algorithm_version,
        "algorithm_version": algorithm_version,
        "feature_version": feature_version,
        "activation": "human approval only", "profile_count": len(profiles),
    }
    if reference_review is not None:
        manifest["reference_review"] = reference_review
        manifest["history_days"] = (calibration_end - source_start).total_seconds() / 86400
        manifest["shadow_days"] = (shadow_end - shadow_start).total_seconds() / 86400
    with (nullcontext(transaction) if transaction is not None else connection()) as conn:
        conn.execute(text("""
            INSERT INTO ht9046mx_calibration_batch
            (batch_id, batch_status, source_start, calibration_end, shadow_start, shadow_end, source_timezone, source_table_ref, profile_algorithm_version, feature_version, manifest_json, completed_at)
            VALUES (:batch_id, 'COMPLETED', :source_start, :calibration_end, :shadow_start, :shadow_end, :source_timezone, :source_table, :algorithm_version, :feature_version, :manifest, UTC_TIMESTAMP(6))
        """), {**manifest, "source_start": source_start, "calibration_end": calibration_end, "shadow_start": shadow_start, "shadow_end": shadow_end, "manifest": json.dumps(manifest)})
        for item in profiles:
            key = item["key"]
            calibration, retained, shadow = item["calibration"], item["retained"], item["shadow"]
            calib_windows = len(calibration)
            calib_days = calibration["day"].nunique() if len(calibration) and "day" in calibration else 0
            quar_win = len(calibration) - len(retained) if len(calibration) else 0
            qualified_shadow = (shadow.loc[shadow["data_quality_status"] == "PASS"]
                                if len(shadow) and "data_quality_status" in shadow else shadow)
            shadow_win = len(qualified_shadow)
            shadow_days_val = qualified_shadow["day"].nunique() if len(qualified_shadow) and "day" in qualified_shadow else 0
            src_start = calibration.minute.min().to_pydatetime() if len(calibration) and "minute" in calibration else source_start
            reviewed=item["validation"].get("reference_review") or {}
            profile_ref_end=datetime.fromisoformat(reviewed["reference_end"]) if reviewed.get("reference_end") else calibration_end
            if reviewed.get("reference_start"):
                src_start=datetime.fromisoformat(reviewed["reference_start"])
            result = conn.execute(text("""
                INSERT INTO ht9046mx_calibration_profile
                (batch_id, profile_version, machine_number, module, sv_state, state_code, profile_status, reason_codes, source_start, calibration_end, shadow_start, shadow_end, calibration_windows, calibration_days, quarantined_windows, quarantine_pct, max_half_shift_rz, shadow_windows, shadow_days, shadow_flag_pct, persistent_flag_pct, statistics_json, threshold_json, validation_json, source_digest)
                VALUES (:batch_id, :profile_version, :machine_number, :module, :sv_state, :state_code, :profile_status, :reason_codes, :source_start, :calibration_end, :shadow_start, :shadow_end, :calibration_windows, :calibration_days, :quarantined_windows, :quarantine_pct, :max_half_shift_rz, :shadow_windows, :shadow_days, :shadow_flag_pct, :persistent_flag_pct, :statistics_json, :threshold_json, :validation_json, :source_digest)
            """), {
                "batch_id": batch_id, "profile_version": version, **key, "profile_status": item["status"], "reason_codes": json.dumps(item["reasons"]),
                "source_start": src_start,
                "calibration_end": profile_ref_end, "shadow_start": shadow_start, "shadow_end": shadow_end,
                "calibration_windows": calib_windows, "calibration_days": calib_days, "quarantined_windows": quar_win, "quarantine_pct": item["quarantine_pct"],
                "max_half_shift_rz": item["validation"]["max_half_shift_rz"] if item["validation"]["max_half_shift_rz"] is not None and np.isfinite(item["validation"]["max_half_shift_rz"]) else None,
                "shadow_windows": shadow_win, "shadow_days": shadow_days_val, "shadow_flag_pct": item["validation"]["shadow_flag_pct"],
                "persistent_flag_pct": item["validation"]["persistent_flag_pct"], "statistics_json": json.dumps(item["statistics"]),
                "threshold_json": json.dumps(item["threshold"]), "validation_json": json.dumps(item["validation"]), "source_digest": item["source_digest"],
            })
            profile_id = int(result.lastrowid)
            if not shadow.empty:
                points = [{"profile_id": profile_id, "event_time": row.minute.to_pydatetime(), "deviation_score": None if pd.isna(row.deviation_score) else float(row.deviation_score), "threshold_value": None if pd.isna(row.threshold_value) else float(row.threshold_value), "raw_flag": bool(row.raw_flag), "persistent_flag": bool(row.persistent_flag), "data_quality_status": str(getattr(row, "data_quality_status", "PASS"))} for row in shadow.itertuples()]
                conn.execute(text("""
                    INSERT INTO ht9046mx_calibration_shadow_point (profile_id, event_time, deviation_score, threshold_value, raw_flag, persistent_flag, data_quality_status)
                    VALUES (:profile_id, :event_time, :deviation_score, :threshold_value, :raw_flag, :persistent_flag, :data_quality_status)
                """), points)
    return {"batch_id": batch_id, "profile_version": version, "profiles": len(profiles), "status": "COMPLETED"}


def run_candidate_calibration(
    settings: Settings | None = None,
    target_machine: str | None = None,
    history_days: int | None = None,
    shadow_days: int | None = None,
    force: bool = False,
    target_module: int | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if settings.profile_window_contract == "qualified_observed_1m":
        return run_qualified_one_minute_calibration(
            settings, target_machine=target_machine, history_days=history_days,
            shadow_days=shadow_days, force=force, target_module=target_module,
        )
    if settings.profile_window_contract != "legacy_minute_snapshot":
        raise ValueError("unknown profile_window_contract")
    if not settings.profile_candidate_enabled and not force:
        return {"status": "SKIPPED_NOT_ENABLED"}
    if settings.database_url is None or settings.source_database_url is None or not settings.source_table.strip():
        return {"status": "SKIPPED_NOT_CONFIGURED", "detail": "Analytics/source credentials and source table are required"}
    if not settings.source_timezone.strip():
        return {"status": "SKIPPED_SOURCE_TIMEZONE_UNVERIFIED"}
    source_end = _latest_source_time(settings, target_machine=target_machine)
    if source_end is None:
        return {"status": "SKIPPED_NO_SOURCE_DATA", "target_machine": target_machine}
    if not force:
        previous_end = _last_shadow_end()
        if previous_end and source_end < previous_end + timedelta(days=settings.profile_retry_min_new_days):
            return {"status": "SKIPPED_WAITING_FOR_NEW_SOURCE_DAYS", "source_end": source_end.isoformat(), "previous_end": previous_end.isoformat()}
    eff_shadow_days = shadow_days or settings.profile_shadow_days
    eff_history_days = history_days or settings.profile_history_days
    shadow_start = source_end - timedelta(days=eff_shadow_days)
    source_start = shadow_start - timedelta(days=eff_history_days)
    duplicate_keys = _source_duplicate_key_count(settings, source_start, source_end + timedelta(minutes=1), target_machine=target_machine)
    if duplicate_keys:
        return {
            "status": "SKIPPED_SOURCE_DUPLICATE_MACHINE_TIMESTAMP",
            "duplicate_keys": duplicate_keys,
            "target_machine": target_machine,
            "source_start": source_start.isoformat(),
            "source_end": source_end.isoformat(),
        }
    windows = load_qualified_windows(settings, source_start, source_end + timedelta(minutes=1), target_machine=target_machine)
    profiles = build_candidate_profiles(windows, settings, shadow_start, target_machine=target_machine)
    if not profiles:
        return {"status": "SKIPPED_NO_QUALIFIED_WINDOWS", "target_machine": target_machine, "source_start": source_start.isoformat(), "source_end": source_end.isoformat()}
    result = persist_batch(settings, source_start, shadow_start, shadow_start, source_end, profiles)
    result["target_machine"] = target_machine
    result["qualified_windows"] = len(windows)
    result["status_counts"] = pd.Series([item["status"] for item in profiles]).value_counts().to_dict()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build immutable HT9046MX calibration-profile candidates")
    parser.add_argument("--run", action="store_true", help="run one candidate cycle")
    parser.add_argument("--machine", type=str, default=None, help="target machine (e.g. MX080)")
    parser.add_argument("--history-days", type=int, default=None, help="history days for calibration")
    parser.add_argument("--shadow-days", type=int, default=None, help="shadow days for validation")
    parser.add_argument("--module", type=int, default=None, help="one module for bounded validation")
    parser.add_argument("--force", action="store_true", help="force run without waiting for new source days")
    args = parser.parse_args()
    if not args.run:
        parser.error("pass --run")
    print(json.dumps(run_candidate_calibration(
        target_machine=args.machine,
        history_days=args.history_days,
        shadow_days=args.shadow_days,
        force=args.force,
        target_module=args.module,
    ), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
