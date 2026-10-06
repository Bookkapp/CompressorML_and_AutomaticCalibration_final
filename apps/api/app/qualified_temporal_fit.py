"""Past-only research calibration for shadow EWMA/CUSUM limits.

Point quantiles are candidate screening limits, *not* a validated live alert
budget. The future/outer block remains untouched until parameters are frozen.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import numpy as np

from .qualified_scoring import ApprovedProfile, QualifiedShadowScorer, TemporalParameters
from .qualified_windows import FEATURES, QualifiedWindow


@dataclass(frozen=True)
class TemporalCalibrationCandidate:
    status: str
    reason_codes: tuple[str, ...]
    parameter_version: str | None
    calibration_start: datetime
    calibration_end: datetime
    qualified_windows: int
    qualified_days: int
    ewma_lambda: float
    cusum_k: float
    ewma_family_limit: float | None
    cusum_family_limit: float | None
    observed_ewma_flag_pct: float | None
    observed_cusum_flag_pct: float | None
    auto_activation_allowed: bool = False
    primary_excluded_windows: int = 0

    def to_parameters(self) -> TemporalParameters:
        if not self.parameter_version or self.ewma_family_limit is None or self.cusum_family_limit is None:
            raise ValueError("temporal calibration is incomplete")
        return TemporalParameters(
            parameter_version=self.parameter_version,
            ewma_lambda=self.ewma_lambda, cusum_k=self.cusum_k,
            ewma_limits={feature: self.ewma_family_limit for feature in FEATURES},
            cusum_limits={feature: self.cusum_family_limit for feature in FEATURES},
        )


def fit_shadow_temporal_limits(
    windows: Iterable[QualifiedWindow],
    *,
    profile: ApprovedProfile,
    calibration_start: datetime,
    calibration_end: datetime,
    untouched_test_start: datetime,
    ewma_lambda: float = .20,
    cusum_k: float = .50,
    family_quantile: float = .995,
    min_windows: int = 200,
    min_days: int = 3,
) -> TemporalCalibrationCandidate:
    """Fit only on a separate later block; never select from an outer test."""
    if any(value.tzinfo is not None for value in (calibration_start, calibration_end, untouched_test_start)):
        raise ValueError("split boundaries must be source-local naive DATETIME")
    if profile.profile_fit_end is None or profile.profile_fit_end > calibration_start:
        raise ValueError("profile fit must end before temporal calibration begins")
    if not calibration_start < calibration_end <= untouched_test_start:
        raise ValueError("temporal calibration must end before untouched future test")
    if not 0 < family_quantile < 1:
        raise ValueError("family_quantile must be in (0, 1)")
    selected = sorted((window for window in windows
                       if window.machine_number == profile.machine_number
                       and window.module == profile.module
                       and calibration_start <= window.window_start < calibration_end),
                      key=lambda window: window.window_start)
    if len({window.window_start for window in selected}) != len(selected):
        raise ValueError("duplicate machine/module/window start in temporal calibration")
    scorer = QualifiedShadowScorer(TemporalParameters(
        parameter_version="research-selection-only", ewma_lambda=ewma_lambda,
        cusum_k=cusum_k,
    ))
    results = []
    primary_excluded = 0
    for window in selected:
        evidence = scorer.score(window, profile)
        if evidence.status == "SCORED" and evidence.primary_raw_flag:
            # An already-deviant primary window must not enlarge the proposed
            # shadow limits. Reset both temporal directions before continuing.
            primary_excluded += 1
            scorer.reset(window.machine_number, window.module)
            continue
        results.append(evidence)
    qualified = [result for result in results if result.status == "SCORED"]
    days = len({result.window_start.date() for result in qualified})
    reasons = []
    if len(qualified) < min_windows or days < min_days:
        reasons.append("INSUFFICIENT_TEMPORAL_CALIBRATION_COVERAGE")
    # Ignore the first warm-up windows of each valid segment. Their state
    # begins at zero by definition and does not represent steady run length.
    steady = [result for result in qualified if result.temporal_ready and result.ewma is not None
              and result.cusum_positive is not None and result.cusum_negative is not None]
    if len(steady) < min_windows:
        reasons.append("INSUFFICIENT_STEADY_TEMPORAL_WINDOWS")
    if reasons:
        return TemporalCalibrationCandidate(
            "INSUFFICIENT_DATA", tuple(sorted(set(reasons))), None,
            calibration_start, calibration_end, len(qualified), days,
            ewma_lambda, cusum_k, None, None, None, None,
            primary_excluded_windows=primary_excluded,
        )
    ewma_scores = np.asarray([max(abs(result.ewma[feature]) for feature in FEATURES) for result in steady])
    cusum_scores = np.asarray([max(max(result.cusum_positive[feature], result.cusum_negative[feature])
                                   for feature in FEATURES) for result in steady])
    ewma_limit = float(np.quantile(ewma_scores, family_quantile))
    cusum_limit = float(np.quantile(cusum_scores, family_quantile))
    if ewma_limit <= 0 or cusum_limit <= 0:
        reasons.append("NONPOSITIVE_TEMPORAL_LIMIT")
    manifest = {
        "profile_id": profile.profile_id, "profile_version": profile.profile_version,
        "feature_version": profile.feature_version, "start": calibration_start.isoformat(),
        "end": calibration_end.isoformat(), "lambda": ewma_lambda, "k": cusum_k,
        "quantile": family_quantile, "ewma_limit": ewma_limit, "cusum_limit": cusum_limit,
    }
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    return TemporalCalibrationCandidate(
        "REVIEW_REQUIRED", tuple(reasons), f"temporal-shadow-candidate-{digest}",
        calibration_start, calibration_end, len(qualified), days,
        ewma_lambda, cusum_k, ewma_limit, cusum_limit,
        float(100 * np.mean(ewma_scores >= ewma_limit)),
        float(100 * np.mean(cusum_scores >= cusum_limit)),
        primary_excluded_windows=primary_excluded,
    )
