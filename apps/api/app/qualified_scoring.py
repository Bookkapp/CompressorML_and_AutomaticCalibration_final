"""Deterministic one-minute primary and shadow temporal scoring.

No database writes, PM alerts, fault classes or automatic profile promotion are
possible from this module. Its callers must provide a reviewed, version-matched
profile and completed qualified windows.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Mapping

from .qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, QualifiedWindow
from .qualified_policy import THRESHOLD_VERSION, LEGACY_THRESHOLD_VERSION, score_features, crosses


PRIMARY_VERSION = "robust-z-qualified-1m-v1"
TEMPORAL_VERSION = "ewma-cusum-shadow-1m-v1"


@dataclass(frozen=True)
class ApprovedProfile:
    profile_id: int
    profile_version: str
    feature_version: str
    machine_number: str
    module: int
    sv_state: str
    state_code: str
    medians: Mapping[str, float]
    scales: Mapping[str, float]
    threshold: float
    threshold_version: str
    profile_fit_end: datetime | None = None


@dataclass(frozen=True)
class TemporalParameters:
    parameter_version: str = "temporal-research-1m-seed-v1"
    ewma_lambda: float = 0.20
    cusum_k: float = 0.50
    warmup_windows: int = 3
    # None means numeric evidence only; no empirically calibrated flags.
    ewma_limits: Mapping[str, float] | None = None
    cusum_limits: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if (not math.isfinite(self.ewma_lambda) or not 0 < self.ewma_lambda <= 1
                or not math.isfinite(self.cusum_k) or self.cusum_k < 0 or self.warmup_windows < 1):
            raise ValueError("invalid temporal parameters")
        for limits in (self.ewma_limits, self.cusum_limits):
            if limits is not None and (set(limits) != set(FEATURES) or any(
                not math.isfinite(float(value)) or float(value) <= 0 for value in limits.values()
            )):
                raise ValueError("temporal limits must be positive, finite and complete")


@dataclass(frozen=True)
class ScoreEvidence:
    machine_number: str
    module: int
    window_start: datetime
    window_end: datetime
    status: str
    reason: str
    profile_id: int | None
    profile_version: str | None
    primary_score: float | None = None
    primary_threshold: float | None = None
    primary_raw_flag: bool | None = None
    primary_persistent_flag: bool | None = None
    primary_run_windows: int = 0
    dominant_feature: str | None = None
    dominant_z: float | None = None
    robust_z: dict[str, float] | None = None
    ewma: dict[str, float] | None = None
    cusum_positive: dict[str, float] | None = None
    cusum_negative: dict[str, float] | None = None
    ewma_flags: dict[str, bool] | None = None
    cusum_flags: dict[str, bool] | None = None
    temporal_ready: bool = False
    temporal_mode: str = "SHADOW"
    primary_version: str = PRIMARY_VERSION
    temporal_version: str = TEMPORAL_VERSION
    parameter_version: str | None = None
    primary_features: tuple[str, ...] = FEATURES
    control_z: float | None = None


@dataclass
class _ContextState:
    context: tuple[int, str, str, str, str, str]
    last_end: datetime
    run_windows: int = 0
    seen_windows: int = 0
    ewma: dict[str, float] = field(default_factory=dict)
    cusum_positive: dict[str, float] = field(default_factory=dict)
    cusum_negative: dict[str, float] = field(default_factory=dict)
    last_result: ScoreEvidence | None = None
    last_features: dict[str, float] | None = None


def _validated_z(window: QualifiedWindow, profile: ApprovedProfile) -> dict[str, float]:
    if not window.eligible or window.features is None:
        raise ValueError("window is not qualified")
    if (window.window_start.tzinfo is not None or window.window_end.tzinfo is not None
            or window.window_end - window.window_start != timedelta(minutes=1)
            or window.window_start.second or window.window_start.microsecond
            or window.expected_samples != 60 or window.sample_count < 57
            or window.coverage < .95 or window.maximum_observed_gap_seconds > 5):
        raise ValueError("window violates qualified one-minute v1 policy")
    if not math.isfinite(profile.threshold) or profile.threshold <= 0:
        raise ValueError("profile threshold must be positive and finite")
    if set(profile.medians) != set(FEATURES) or set(profile.scales) != set(FEATURES):
        raise ValueError("profile must contain all nine features")
    result: dict[str, float] = {}
    for feature in FEATURES:
        value = float(window.features[feature])
        median = float(profile.medians[feature])
        scale = float(profile.scales[feature])
        if not all(math.isfinite(v) for v in (value, median, scale)) or scale <= 0:
            raise ValueError(f"invalid {feature} value or profile scale")
        result[feature] = (value - median) / scale
    return result


class QualifiedShadowScorer:
    """Stateful replay engine; same input order yields the same evidence.

    It intentionally has no side-effect methods. For a restart, replay from a
    stored bounded history; if context/order cannot be proven, reset/warm up.
    """

    def __init__(self, parameters: TemporalParameters | None = None) -> None:
        self.parameters = parameters or TemporalParameters()
        self._state: dict[tuple[str, int], _ContextState] = {}

    def reset(self, machine_number: str, module: int) -> None:
        self._state.pop((machine_number, module), None)

    def checkpoint(self) -> dict:
        """JSON-compatible state for atomic storage beside evidence rows."""
        states = []
        for (machine, module), state in sorted(self._state.items()):
            last_result = asdict(state.last_result) if state.last_result else None
            if last_result:
                last_result["window_start"] = state.last_result.window_start.isoformat()
                last_result["window_end"] = state.last_result.window_end.isoformat()
            states.append({
                "machine_number": machine, "module": module,
                "context": list(state.context), "last_end": state.last_end.isoformat(),
                "run_windows": state.run_windows, "seen_windows": state.seen_windows,
                "ewma": dict(state.ewma),
                "cusum_positive": dict(state.cusum_positive),
                "cusum_negative": dict(state.cusum_negative),
                "last_features": dict(state.last_features) if state.last_features else None,
                "last_result": last_result,
            })
        return {
            "schema_version": 1, "primary_version": PRIMARY_VERSION,
            "temporal_version": TEMPORAL_VERSION,
            "parameter_version": self.parameters.parameter_version,
            "states": states,
        }

    @classmethod
    def from_checkpoint(cls, checkpoint: Mapping, parameters: TemporalParameters) -> "QualifiedShadowScorer":
        """Reject incompatible/corrupt checkpoints instead of carrying stale drift."""
        if (checkpoint.get("schema_version") != 1
                or checkpoint.get("primary_version") != PRIMARY_VERSION
                or checkpoint.get("temporal_version") != TEMPORAL_VERSION
                or checkpoint.get("parameter_version") != parameters.parameter_version):
            raise ValueError("checkpoint algorithm or parameter version mismatch")
        scorer = cls(parameters)
        for item in checkpoint.get("states", []):
            context = tuple(item["context"])
            if len(context) != 6 or context[4] != parameters.parameter_version:
                raise ValueError("invalid checkpoint context")
            for name in ("ewma", "cusum_positive", "cusum_negative"):
                values = item[name]
                if set(values) != set(FEATURES) or any(not math.isfinite(float(v)) for v in values.values()):
                    raise ValueError("invalid temporal checkpoint vector")
            last_result = item.get("last_result")
            if last_result is not None:
                last_result = dict(last_result)
                last_result["window_start"] = datetime.fromisoformat(last_result["window_start"])
                last_result["window_end"] = datetime.fromisoformat(last_result["window_end"])
                if 'primary_features' in last_result:
                    last_result['primary_features']=tuple(last_result['primary_features'])
                last_result = ScoreEvidence(**last_result)
            key = (str(item["machine_number"]), int(item["module"]))
            if key in scorer._state:
                raise ValueError("duplicate checkpoint state key")
            scorer._state[key] = _ContextState(
                context=context, last_end=datetime.fromisoformat(item["last_end"]),
                run_windows=int(item["run_windows"]), seen_windows=int(item["seen_windows"]),
                ewma={f: float(item["ewma"][f]) for f in FEATURES},
                cusum_positive={f: float(item["cusum_positive"][f]) for f in FEATURES},
                cusum_negative={f: float(item["cusum_negative"][f]) for f in FEATURES},
                last_features=dict(item["last_features"]) if item.get("last_features") else None,
                last_result=last_result,
            )
        return scorer

    def score(self, window: QualifiedWindow, profile: ApprovedProfile | None) -> ScoreEvidence:
        key = (window.machine_number, window.module)
        previous = self._state.get(key)
        if previous is not None and window.window_end < previous.last_end:
            return self._not_scored(window, profile, "OUT_OF_ORDER_WINDOW")
        if not window.eligible:
            self.reset(*key)
            return self._not_scored(window, profile, window.reason or window.data_quality_status)
        if profile is None:
            self.reset(*key)
            return self._not_scored(window, None, "NO_ACTIVE_PROFILE")
        if profile.profile_fit_end is not None:
            if profile.profile_fit_end.tzinfo is not None or window.window_start < profile.profile_fit_end:
                self.reset(*key)
                return self._not_scored(window, profile, "BEFORE_PROFILE_FIT_END")
        if (
            window.feature_version != WINDOW_VERSION
            or profile.feature_version != WINDOW_VERSION
            or profile.machine_number != window.machine_number
            or profile.module != window.module
            or profile.sv_state != window.sv_state
            or profile.state_code != window.state_code
            or profile.state_code != STATE_CODE
            or profile.profile_id <= 0
        ):
            self.reset(*key)
            return self._not_scored(window, profile, "PROFILE_OR_FEATURE_MISMATCH")
        try:
            voting_features = score_features(profile.threshold_version)
            z = _validated_z(window, profile)
        except (KeyError, TypeError, ValueError, OverflowError):
            self.reset(*key)
            return self._not_scored(window, profile, "INVALID_PROFILE_OR_FEATURE")

        context = (profile.profile_id, profile.profile_version, profile.feature_version,
                   profile.threshold_version, self.parameters.parameter_version, window.state_code)
        if previous is not None and window.window_end == previous.last_end:
            if (previous.context == context and previous.last_features == window.features
                    and previous.last_result is not None):
                return previous.last_result
            return self._not_scored(window, profile, "WINDOW_REVISION_REQUIRES_REPLAY")
        if previous is None or previous.context != context or previous.last_end != window.window_start:
            previous = _ContextState(context=context, last_end=window.window_start)
            self._state[key] = previous

        dominant = max(voting_features, key=lambda feature: abs(z[feature]))
        deviation = abs(z[dominant])
        raw_flag = crosses(deviation, profile.threshold, profile.threshold_version)
        previous.run_windows = previous.run_windows + 1 if raw_flag else 0
        previous.seen_windows += 1
        p = self.parameters
        ewma: dict[str, float] = {}
        positive: dict[str, float] = {}
        negative: dict[str, float] = {}
        for feature in FEATURES:
            signed = z[feature]
            ewma[feature] = p.ewma_lambda * signed + (1 - p.ewma_lambda) * previous.ewma.get(feature, 0.0)
            positive[feature] = max(0.0, previous.cusum_positive.get(feature, 0.0) + signed - p.cusum_k)
            negative[feature] = max(0.0, previous.cusum_negative.get(feature, 0.0) - signed - p.cusum_k)
        previous.ewma, previous.cusum_positive, previous.cusum_negative = ewma, positive, negative
        ready = previous.seen_windows >= p.warmup_windows
        ewma_flags = (
            {feature: abs(ewma[feature]) >= float(p.ewma_limits[feature]) for feature in FEATURES}
            if ready and p.ewma_limits is not None else None
        )
        cusum_flags = (
            {feature: max(positive[feature], negative[feature]) >= float(p.cusum_limits[feature])
             for feature in FEATURES}
            if ready and p.cusum_limits is not None else None
        )
        evidence = ScoreEvidence(
            machine_number=window.machine_number, module=window.module,
            window_start=window.window_start, window_end=window.window_end,
            status="SCORED", reason="", profile_id=profile.profile_id,
            profile_version=profile.profile_version, primary_score=deviation,
            primary_threshold=profile.threshold, primary_raw_flag=raw_flag,
            primary_persistent_flag=previous.run_windows >= 3,
            primary_run_windows=previous.run_windows,
            dominant_feature=dominant, dominant_z=z[dominant], robust_z=z,
            ewma=ewma.copy(), cusum_positive=positive.copy(), cusum_negative=negative.copy(),
            ewma_flags=ewma_flags, cusum_flags=cusum_flags,
            temporal_ready=ready,
            parameter_version=p.parameter_version,
            primary_version="physical-robust-z-control-context-1m-v2" if profile.threshold_version == THRESHOLD_VERSION else PRIMARY_VERSION,
            primary_features=voting_features, control_z=z["valve"] if profile.threshold_version == THRESHOLD_VERSION else None,
        )
        previous.last_end = window.window_end
        previous.last_result = evidence
        previous.last_features = dict(window.features or {})
        return evidence

    def _not_scored(self, window: QualifiedWindow, profile: ApprovedProfile | None, reason: str) -> ScoreEvidence:
        return ScoreEvidence(
            machine_number=window.machine_number, module=window.module,
            window_start=window.window_start, window_end=window.window_end,
            status="NOT_SCORED", reason=reason,
            profile_id=profile.profile_id if profile else None,
            profile_version=profile.profile_version if profile else None,
            parameter_version=self.parameters.parameter_version,
        )
