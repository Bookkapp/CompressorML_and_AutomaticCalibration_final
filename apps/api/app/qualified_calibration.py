"""Read-only intake and pure candidate fitting for the observed-second → one-minute contract.

This is deliberately separate from the historical minute candidate registry.
It cannot write a candidate or activate an Active Profile by itself.
"""

from __future__ import annotations

import math
import json
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import bindparam, text

from .config import Settings
from .db import source_connection
from .inference import _qualified_source_table, clean_machine_code, get_machine_candidates
from .qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, QualifiedWindow, WindowPolicy, build_completed_windows
from .qualified_policy import CANDIDATE_VERSION, THRESHOLD_VERSION, LEGACY_CANDIDATE_VERSION, score_features, crosses, manifest


SCALE_FLOORS = {feature: (1.0 if feature == "valve" else 0.10) for feature in FEATURES}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def policy_from_settings(settings: Settings) -> WindowPolicy:
    # These gates are part of WINDOW_VERSION. A different policy must receive
    # a new feature/profile/threshold version before it can be scored.
    if (settings.source_expected_cadence_seconds != 1.0
            or settings.qualified_1m_minimum_coverage != .95
            or settings.qualified_1m_maximum_gap_seconds != 5.0):
        raise ValueError("qualified one-minute v1 requires 1s/.95/5s policy; version a changed policy")
    return WindowPolicy(
        source_timezone=settings.source_timezone,
        expected_cadence_seconds=settings.source_expected_cadence_seconds,
        minimum_coverage=settings.qualified_1m_minimum_coverage,
        maximum_gap_seconds=settings.qualified_1m_maximum_gap_seconds,
        late_arrival_seconds=settings.qualified_1m_late_arrival_seconds,
        compressor_on=settings.source_compressor_on_status,
        module_on="On",  # owner-confirmed Cold code; do not accept a broad default
        busy_normal=tuple(x.strip() for x in settings.source_busy_normal_values.split(",") if x.strip()),
        sv_off=tuple(x.strip() for x in settings.source_sv_off_values.split(",") if x.strip()),
    )


def load_observed_one_minute_windows(
    settings: Settings,
    *,
    machine_number: str,
    start: datetime,
    end: datetime,
    as_of: datetime | None = None,
    modules: Iterable[int] = range(1, 9),
    progress: Callable[[str], None] | None = None,
    revision_out: dict[str,str] | None = None,
    compact_json: bool = False,
    window_builder: Callable | None = None,
    on_raw_batch: Callable | None = None,
) -> list[QualifiedWindow]:
    """Fetch bounded raw rows by local calendar day through source SELECT role.

    The Server must confirm source DATETIME timezone and cadence first. A
    single day is the largest in-memory slice; missing seconds stay missing.
    """
    if not settings.source_database_url or not settings.source_table:
        raise RuntimeError("read-only source MySQL is not configured")
    policy = policy_from_settings(settings)
    zone = ZoneInfo(policy.source_timezone)
    if start.tzinfo is None or end.tzinfo is None or (as_of is not None and as_of.tzinfo is None):
        raise ValueError("start, end and as_of must be timezone-aware")
    local_start = start.astimezone(zone).replace(tzinfo=None)
    local_end = end.astimezone(zone).replace(tzinfo=None)
    if local_end <= local_start:
        raise ValueError("end must follow start")
    table = _qualified_source_table(settings.source_db_name, settings.source_table)
    source_fields = {
        "hp1": settings.source_hp1_template, "lp1": settings.source_lp1_template,
        "hp2": settings.source_hp2_template, "lp2": settings.source_lp2_template,
        "valve": settings.source_valve_template,
        "temphi": settings.source_temp_high_template, "templo": settings.source_temp_low_template,
    }
    state_templates = (settings.source_module_status_template, settings.source_busy_template,
                       settings.source_sv_template)
    modules = tuple(modules)
    if not modules or len(set(modules)) != len(modules) or any(module < 1 or module > 8 for module in modules):
        raise ValueError("modules must be unique numbers 1..8")
    columns = []
    for module in modules:
        columns.extend(template.format(module=module) for template in source_fields.values())
        columns.extend(template.format(module=module) for template in state_templates)
    if len(columns) != len(set(columns)):
        raise ValueError("duplicate source column mapping")
    # The templates are config, so validate every interpolated identifier.
    for column in columns:
        if not IDENTIFIER.fullmatch(column):
            raise ValueError("unsafe configured source column")
    machine_col = settings.source_machine_column
    time_col = settings.source_timestamp_column
    status_col = settings.source_global_status_column
    if not all(IDENTIFIER.fullmatch(item) for item in (machine_col, time_col, status_col)):
        raise ValueError("unsafe source identifier")
    quoted = ", ".join([
        f"`{time_col}` AS recorded_at", f"`{machine_col}` AS machine_number",
        f"`{status_col}` AS Status", *(f"`{column}`" for column in columns),
    ])
    if revision_out is not None:
        from .qualified_cache import revision_expression
        quoted += f", {revision_expression(settings)} AS _qcrc"
    query = text(f"SELECT {quoted} FROM {table} "
                 f"WHERE `{machine_col}` IN :machines AND `{time_col}` >= :start AND `{time_col}` < :end "
                 f"ORDER BY `{time_col}`").bindparams(bindparam("machines", expanding=True))
    compact_names = ["recorded_at","machine_number","Status",*columns]
    if compact_json:
        json_fields = [f"`{time_col}`",f"`{machine_col}`",f"`{status_col}`",*(f"`{c}`" for c in columns)]
        if revision_out is not None:
            compact_names.append("_qcrc")
            json_fields.append(revision_expression(settings))
        minute_key = f"DATE_FORMAT(`{time_col}`,'%Y-%m-%d %H:%i:00')"
        query = text(f"SELECT JSON_ARRAYAGG(JSON_ARRAY({','.join(json_fields)})) AS minute_payload FROM {table} "
            f"WHERE `{machine_col}` IN :machines AND `{time_col}`>=:start AND `{time_col}`<:end "
            f"GROUP BY {minute_key} ORDER BY {minute_key}").bindparams(bindparam("machines",expanding=True))
    aliases = get_machine_candidates(machine_number)
    cursor = local_start
    result: list[QualifiedWindow] = []
    while cursor < local_end:
        if progress:
            progress(cursor.date().isoformat())
        next_day = min(local_end, cursor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        # Stream bounded chunks, retaining the final minute across partitions.
        # A minute must contain ALL aliases/seconds before applying its gate.
        pending: list[dict] = []
        raw_count = crc_total = crc_xor = 0
        def append_windows(batch):
            if on_raw_batch is not None:
                from .qualified_windows import SOURCE_FIELDS
                if source_fields == SOURCE_FIELDS and state_templates == ("Status_{module}", "Busy_{module}", "SV_{module}"):
                    canonical_rows = batch
                else:
                    canonical_rows = []
                    for row in batch:
                        mapped = {"recorded_at": row["recorded_at"], "machine_number": row["machine_number"], "Status": row.get("Status")}
                        for module in modules:
                            for name, template in source_fields.items():
                                mapped[SOURCE_FIELDS[name].format(module=module)] = row.get(template.format(module=module))
                            for source_template, canonical_template in zip(state_templates, ("Status_{module}", "Busy_{module}", "SV_{module}")):
                                mapped[canonical_template.format(module=module)] = row.get(source_template.format(module=module))
                        canonical_rows.append(mapped)
                on_raw_batch(sorted(canonical_rows, key=lambda r:r["recorded_at"]))
            result.extend((window_builder or build_completed_windows)(
                batch, as_of=as_of or end, policy=policy, modules=modules,
                source_fields=source_fields, module_status_template=state_templates[0],
                busy_template=state_templates[1], sv_template=state_templates[2]))
        with source_connection() as conn:
            partition_size = 16 if compact_json else 1200
            source = conn.execution_options(stream_results=True, yield_per=partition_size).execute(
                query, {"machines": aliases, "start": cursor, "end": next_day}).mappings()
            for partition in source.partitions(partition_size):
                if compact_json:
                    for item in partition:
                        batch = [dict(zip(compact_names,values)) for values in json.loads(item["minute_payload"])]
                        for row in batch:
                            row["recorded_at"] = datetime.fromisoformat(row["recorded_at"])
                            row["machine_number"] = clean_machine_code(row["machine_number"])
                            if revision_out is not None:
                                raw_count += 1
                                crc_total += int(row["_qcrc"])
                                crc_xor ^= int(row["_qcrc"])
                        append_windows(batch)
                    continue
                if revision_out is not None:
                    for row in partition:
                        raw_count += 1
                        crc_total += int(row["_qcrc"])
                        crc_xor ^= int(row["_qcrc"])
                pending.extend({**dict(row), "machine_number": clean_machine_code(row["machine_number"])} for row in partition)
                last = pending[-1]["recorded_at"].replace(second=0, microsecond=0)
                split = len(pending)
                while split and pending[split-1]["recorded_at"].replace(second=0, microsecond=0) == last:
                    split -= 1
                if split:
                    append_windows(pending[:split])
                    pending = pending[split:]
            if pending:
                append_windows(pending)
        if revision_out is not None:
            revision_out[cursor.date().isoformat()] = f"{raw_count}:{crc_total}:{crc_xor}"
        cursor = next_day
    return sorted(result, key=lambda w: (w.machine_number, w.module, w.window_start))


def _fit_features(windows: list[QualifiedWindow]) -> tuple[dict[str, float], dict[str, float]]:
    medians: dict[str, float] = {}
    scales: dict[str, float] = {}
    for feature in FEATURES:
        values = np.asarray([float(window.features[feature]) for window in windows if window.features is not None])
        median = float(np.median(values))
        mad = 1.4826 * float(np.median(np.abs(values - median)))
        iqr = float((np.quantile(values, .75) - np.quantile(values, .25)) / 1.349)
        medians[feature] = median
        scales[feature] = max(SCALE_FLOORS[feature], mad, iqr)
    return medians, scales


def _scores(windows: list[QualifiedWindow], medians: dict[str, float], scales: dict[str, float], *, version=THRESHOLD_VERSION) -> np.ndarray:
    return np.asarray([max(abs((window.features[feature] - medians[feature]) / scales[feature])
                           for feature in score_features(version)) for window in windows])


def fit_one_minute_candidate(
    windows: Iterable[QualifiedWindow],
    *,
    machine_number: str,
    module: int,
    calibration_start: datetime,
    shadow_start: datetime,
    shadow_end: datetime,
    min_calibration_days: int = 7,
    min_calibration_windows: int = 200,
    min_shadow_days: int = 3,
    min_shadow_windows: int = 200,
    max_quarantine_pct: float = 5.0,
    max_shadow_flag_pct: float = 1.0,
    scoring_version: str = THRESHOLD_VERSION,
) -> dict[str, Any]:
    """Fit an immutable *candidate* from past windows; never an Active Profile."""
    if any(value.tzinfo is not None for value in (calibration_start, shadow_start, shadow_end)):
        raise ValueError("split boundaries must be source-local naive DATETIME")
    if not calibration_start < shadow_start < shadow_end:
        raise ValueError("calibration and shadow must be disjoint ordered blocks")
    selected = sorted(
        (window for window in windows if window.machine_number == machine_number and window.module == module
         and calibration_start <= window.window_start < shadow_end),
        key=lambda window: window.window_start,
    )
    if len({window.window_start for window in selected}) != len(selected):
        raise ValueError("duplicate machine/module/window start in candidate input")
    for window in selected:
        if window.feature_version != WINDOW_VERSION or window.window_end - window.window_start != timedelta(minutes=1):
            raise ValueError("candidate input violates the one-minute feature contract")
        if window.eligible and (window.state_code != STATE_CODE or window.sv_state != "Off"):
            raise ValueError("candidate input mixes operating states")
        if window.eligible and (window.expected_samples != 60 or window.sample_count < 57
                                or window.coverage < .95 or window.maximum_observed_gap_seconds > 5):
            raise ValueError("eligible candidate input violates the observed-second policy")
        if window.eligible and (set(window.features or {}) != set(FEATURES) or any(
            not math.isfinite(float(window.features[feature])) for feature in FEATURES
        )):
            raise ValueError("eligible candidate input has invalid features")
    eligible = [window for window in selected if window.eligible]
    calibration = [window for window in eligible if window.window_start < shadow_start]
    shadow = [window for window in eligible if window.window_start >= shadow_start]
    reasons: list[str] = []
    if len(calibration) < min_calibration_windows or len({w.window_start.date() for w in calibration}) < min_calibration_days:
        reasons.append("INSUFFICIENT_CALIBRATION_COVERAGE")
    if len(shadow) < min_shadow_windows or len({w.window_start.date() for w in shadow}) < min_shadow_days:
        reasons.append("INSUFFICIENT_SHADOW_COVERAGE")
    if not calibration:
        return {"status": "INSUFFICIENT_DATA", "reason_codes": reasons,
                "calibration_windows": 0, "shadow_windows": len(shadow), "auto_activation_allowed": False}

    initial_medians, initial_scales = _fit_features(calibration)
    initial_scores = _scores(calibration, initial_medians, initial_scales,version=scoring_version)
    retained = [window for window, score in zip(calibration, initial_scores) if score <= 8.0]
    quarantine_pct = 100.0 * (1 - len(retained) / len(calibration))
    if not retained:
        reasons.append("ALL_WINDOWS_QUARANTINED")
        retained = calibration
    medians, scales = _fit_features(retained)
    threshold = float(np.quantile(_scores(retained, medians, scales,version=scoring_version), .995))
    if not math.isfinite(threshold) or threshold <= 0:
        reasons.append("NONPOSITIVE_THRESHOLD")
    if quarantine_pct > max_quarantine_pct:
        reasons.append("QUARANTINE_RATE_EXCEEDED")
    days = sorted({w.window_start.date() for w in retained})
    if len(days) >= 2:
        midpoint = days[len(days) // 2]
        first = [w for w in retained if w.window_start.date() < midpoint]
        second = [w for w in retained if w.window_start.date() >= midpoint]
        half_shift = max(abs(float(np.median([w.features[f] for w in first])) -
                             float(np.median([w.features[f] for w in second]))) / scales[f] for f in score_features(scoring_version))
        if half_shift > 1.5:
            reasons.append("CALIBRATION_DRIFT_EXCEEDED")
    else:
        half_shift = None
    shadow_flags = [crosses(float(score), threshold, scoring_version) for score in _scores(shadow, medians, scales,version=scoring_version)] if shadow and threshold > 0 else []
    shadow_flag_pct = 100 * sum(shadow_flags) / len(shadow_flags) if shadow_flags else None
    if shadow_flag_pct is not None and shadow_flag_pct > max_shadow_flag_pct:
        reasons.append("SHADOW_FLAG_RATE_EXCEEDED")
    if len(shadow) > 1 and (shadow[-1].window_end - shadow[0].window_start).total_seconds() < min_shadow_days * 86400 - 3600:
        reasons.append("SHADOW_DURATION_LT_REQUIRED")
    if any(reason.startswith("INSUFFICIENT") for reason in reasons):
        status = "INSUFFICIENT_DATA"
    elif reasons:
        status = "REVIEW_REQUIRED"
    else:
        # Source owner and approver must separately verify codebook, units,
        # service epochs, source clock and the shadow graph before approval.
        status = "SHADOW_VALIDATION"
    return {
        "status": status, "reason_codes": sorted(set(reasons)),
        "calibration_start": calibration_start.isoformat(), "shadow_start": shadow_start.isoformat(),
        "shadow_end": shadow_end.isoformat(),
        "machine_number": machine_number, "module": module, "sv_state": "Off",
        "state_code": STATE_CODE, "feature_version": WINDOW_VERSION,
        "algorithm_version": CANDIDATE_VERSION if scoring_version==THRESHOLD_VERSION else LEGACY_CANDIDATE_VERSION, "threshold_version": scoring_version,
        "scoring_policy": manifest(scoring_version),
        "calibration_windows": len(calibration), "calibration_days": len({w.window_start.date() for w in calibration}),
        "retained_windows": len(retained), "quarantine_pct": quarantine_pct,
        "shadow_windows": len(shadow), "shadow_days": len({w.window_start.date() for w in shadow}),
        "shadow_flag_pct": shadow_flag_pct, "max_half_shift_rz": half_shift,
        "medians": medians, "scales": scales, "threshold": threshold,
        "auto_activation_allowed": False,
    }
