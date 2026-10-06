"""Adapt strict one-minute candidates to the existing calibration review registry.

No profile is approved here. The three-day shadow uses the candidate fitted on
earlier windows and preserves unscored minutes as gaps in the review graph.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from typing import Any, Iterable

import pandas as pd

from .config import Settings
from .qualified_calibration import (
    CANDIDATE_VERSION, THRESHOLD_VERSION, _fit_features, _scores,
    fit_one_minute_candidate,
)
from .qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, QualifiedWindow
from .qualified_policy import score_features, crosses, manifest


def _frame(windows: list[QualifiedWindow]) -> pd.DataFrame:
    rows = [{"minute": window.window_start, "machine_number": window.machine_number,
             "module": window.module, "sv_state": window.sv_state,
             "state_code": window.state_code, "day": window.window_start.date(),
             **(window.features or {})}
            for window in windows if window.eligible]
    return pd.DataFrame(rows, columns=["minute", "machine_number", "module", "sv_state",
                                       "state_code", "day", *FEATURES])


def registry_candidate_from_windows(
    windows: Iterable[QualifiedWindow], *, settings: Settings, machine_number: str,
    module: int, calibration_start: datetime, shadow_start: datetime, shadow_end: datetime,
) -> dict[str, Any]:
    """Build one candidate for the existing review graph; never an Active Profile."""
    # These values are part of the v1 algorithm contract. A changed policy
    # needs an explicit new algorithm/threshold version, not silent reuse.
    if settings.profile_quarantine_z != 8.0 or settings.profile_max_half_shift_rz != 1.5:
        raise ValueError("qualified 1m v1 requires quarantine z=8 and half-shift rz=1.5")
    selected = sorted((w for w in windows if w.machine_number == machine_number
                       and w.module == module and calibration_start <= w.window_start < shadow_end),
                      key=lambda w: w.window_start)
    candidate = fit_one_minute_candidate(
        selected, machine_number=machine_number, module=module,
        calibration_start=calibration_start, shadow_start=shadow_start, shadow_end=shadow_end,
        min_calibration_days=settings.profile_min_calibration_days,
        min_calibration_windows=settings.profile_min_calibration_windows,
        min_shadow_days=settings.profile_shadow_days,
        min_shadow_windows=settings.profile_min_shadow_windows,
        max_quarantine_pct=settings.profile_max_quarantine_pct,
        max_shadow_flag_pct=settings.profile_max_shadow_flag_pct,
    )
    calibration_windows = [w for w in selected if w.eligible and w.window_start < shadow_start]
    shadow_windows = [w for w in selected if w.window_start >= shadow_start]
    calibration = _frame(calibration_windows)
    retained_windows: list[QualifiedWindow] = []
    if calibration_windows:
        initial_medians, initial_scales = _fit_features(calibration_windows)
        retained_windows = [w for w, score in zip(calibration_windows,
                            _scores(calibration_windows, initial_medians, initial_scales))
                            if score <= 8.0]
        if not retained_windows:
            retained_windows = calibration_windows
    retained = _frame(retained_windows)

    threshold_value = candidate.get("threshold")
    threshold = (float(threshold_value) if threshold_value is not None
                 and math.isfinite(float(threshold_value)) and float(threshold_value) > 0 else None)
    medians = candidate.get("medians", {})
    scales = candidate.get("scales", {})
    shadow_rows = []
    run = 0
    previous_end: datetime | None = None
    by_minute = {window.window_start: window for window in shadow_windows}
    minute = shadow_start
    while minute < shadow_end:
        window = by_minute.get(minute)
        score = None
        raw_flag = False
        if window is not None and window.eligible and threshold is not None and set(medians) == set(FEATURES):
            score = max(abs((float(window.features[f]) - float(medians[f])) / float(scales[f]))
                        for f in score_features(THRESHOLD_VERSION))
            raw_flag = crosses(score, threshold, THRESHOLD_VERSION)
        run = run + 1 if raw_flag and previous_end == minute else int(raw_flag)
        shadow_rows.append({
            "minute": minute, "day": minute.date(),
            "deviation_score": score, "threshold_value": threshold,
            "raw_flag": raw_flag, "persistent_flag": run >= 3,
            "data_quality_status": ("NO_SOURCE_ROWS" if window is None else
                                    "PASS" if window.eligible else window.reason or window.data_quality_status),
        })
        previous_end = window.window_end if window is not None and window.eligible else None
        minute += timedelta(minutes=1)
    shadow = pd.DataFrame(shadow_rows, columns=["minute", "day", "deviation_score",
                                                "threshold_value", "raw_flag", "persistent_flag",
                                                "data_quality_status"])

    prerequisites = {
        "SOURCE_TIMEZONE": settings.source_timezone,
        "SOURCE_PRESSURE_UNIT": settings.source_pressure_unit,
        "STATE_CONTRACT_VERSION": settings.profile_state_contract_version,
        "CONTROLLER_CODEBOOK_VERSION": settings.profile_controller_codebook_version,
        "SERVICE_EPOCH_VERSION": settings.profile_service_epoch_version,
    }
    reasons = list(candidate["reason_codes"])
    expected_shadow_minutes = int((shadow_end - shadow_start).total_seconds() // 60)
    if expected_shadow_minutes and len(shadow_windows) / expected_shadow_minutes < .95:
        reasons.append("SHADOW_SOURCE_COVERAGE_LT_95")
    reasons.extend(f"{key}_UNVERIFIED" for key, value in prerequisites.items() if not str(value).strip())
    if settings.source_pressure_unit=="psi":
        reasons.append("SOURCE_PRESSURE_BASIS_UNVERIFIED")
    status = candidate["status"]
    if status == "SHADOW_VALIDATION" and "SHADOW_SOURCE_COVERAGE_LT_95" in reasons:
        status = "REVIEW_REQUIRED"
    if status == "SHADOW_VALIDATION" and not reasons:
        status = "READY_FOR_APPROVAL"
    eligible_shadow = sum(w.eligible for w in shadow_windows)
    persistent_pct = (100.0 * sum(row["persistent_flag"] for row in shadow_rows) / eligible_shadow
                      if eligible_shadow else None)
    exact = {feature: {"median": float(medians[feature]), "scale": float(scales[feature])}
             for feature in FEATURES} if set(medians) == set(FEATURES) else {}
    # The old rounded cards remain presentation-only. Scoring loads exact_baseline.
    from .calibration import _detailed_stats
    statistics = _detailed_stats(retained, medians, scales) if exact and not retained.empty else {}
    statistics["exact_baseline"] = exact
    statistics["window_contract"] = WINDOW_VERSION
    statistics["scoring_policy"] = manifest()
    payload = {
        "key": [machine_number, module, "Off", STATE_CODE],
        "feature_version": WINDOW_VERSION,
        "calibration_start": calibration_start.isoformat(),
        "shadow_start": shadow_start.isoformat(), "shadow_end": shadow_end.isoformat(),
        "samples": [(w.window_start.isoformat(), w.sample_count, w.data_quality_status,
                     [w.features[f] for f in FEATURES] if w.features else None) for w in selected],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "key": {"machine_number": machine_number, "module": module,
                "sv_state": "Off", "state_code": STATE_CODE},
        "status": status, "reasons": sorted(set(reasons)),
        "feature_version": WINDOW_VERSION, "algorithm_version": CANDIDATE_VERSION,
        "calibration": calibration, "retained": retained, "shadow": shadow,
        "statistics": statistics,
        "threshold": {"deviation_score_q995": threshold,
                      "method": "qualified_1m_retained_calibration_q995",
                      "threshold_version": THRESHOLD_VERSION,
                      "scoring_policy": manifest()},
        "validation": {"shadow_flag_pct": candidate.get("shadow_flag_pct"),
                       "scoring_policy": manifest(),
                       "persistent_flag_pct": persistent_pct,
                       "max_half_shift_rz": candidate.get("max_half_shift_rz"),
                       "shadow_elapsed_hours": (shadow_windows[-1].window_end - shadow_windows[0].window_start).total_seconds() / 3600
                       if shadow_windows else 0.0,
                       "eligible_shadow_windows": eligible_shadow,
                       "observed_shadow_windows": len(shadow_windows),
                       "expected_shadow_minutes": expected_shadow_minutes,
                       "observed_shadow_coverage": len(shadow_windows) / expected_shadow_minutes if expected_shadow_minutes else None,
                       "reason_codes": sorted(set(reasons)),
                       "source_pressure_unit": settings.source_pressure_unit},
        "quarantine_pct": candidate.get("quarantine_pct", 0.0),
        "source_digest": digest,
    }
