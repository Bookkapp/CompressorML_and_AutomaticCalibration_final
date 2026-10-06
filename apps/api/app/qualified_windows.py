"""Pure, fail-closed one-minute Cold window contract.

The caller must fetch *all* raw rows covering each requested window. This
module never reads MySQL, interpolates seconds, or activates a profile.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


FEATURES = ("hp1", "lp1", "hp2", "lp2", "dp1", "dp2", "valve", "temphi", "templo")
SOURCE_FIELDS = {
    "hp1": "Hp_1st_{module}",
    "lp1": "Lp_1st_{module}",
    "hp2": "Hp_2nd_{module}",
    "lp2": "Lp_2nd_{module}",
    "valve": "Valve_{module}",
    "temphi": "TempHi_{module}",
    "templo": "TempLo_{module}",
}
STATE_CODE = "COMPRESSOR_ON_COLD_SV_OFF"
WINDOW_VERSION = "qualified-cold-observed-1m-v1"


@dataclass(frozen=True)
class WindowPolicy:
    source_timezone: str
    expected_cadence_seconds: float = 1.0
    minimum_coverage: float = 0.95
    maximum_gap_seconds: float = 5.0
    late_arrival_seconds: float = 0.0
    window_minutes: int = 1
    compressor_on: str = "Run"
    module_on: str = "On"
    busy_normal: tuple[str, ...] = ("0", "False", "Off")
    sv_off: tuple[str, ...] = ("Off", "0", "False")

    def __post_init__(self) -> None:
        if not self.source_timezone:
            raise ValueError("source_timezone must be confirmed before window construction")
        ZoneInfo(self.source_timezone)
        if self.window_minutes != 1:
            raise ValueError("this feature contract is versioned for one-minute windows")
        if self.expected_cadence_seconds <= 0 or not 0 < self.minimum_coverage <= 1:
            raise ValueError("invalid cadence or coverage policy")
        if self.maximum_gap_seconds <= 0 or self.late_arrival_seconds < 0:
            raise ValueError("invalid gap or lateness policy")


@dataclass(frozen=True)
class QualifiedWindow:
    machine_number: str
    module: int
    window_start: datetime
    window_end: datetime
    sv_state: str
    state_code: str
    sample_count: int
    expected_samples: int
    coverage: float
    maximum_observed_gap_seconds: float
    data_quality_status: str
    reason: str
    features: dict[str, float] | None
    feature_version: str = WINDOW_VERSION

    @property
    def eligible(self) -> bool:
        return self.data_quality_status == "PASS" and self.features is not None


def _source_local(value: datetime, zone: ZoneInfo) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("recorded_at must be a datetime")
    # A source DATETIME has no timezone. The operator must confirm its meaning.
    return value.astimezone(zone).replace(tzinfo=None) if value.tzinfo else value


def _window_start(value: datetime, minutes: int) -> datetime:
    return value.replace(minute=(value.minute // minutes) * minutes, second=0, microsecond=0)


def _state(value: Any) -> str:
    return str(value).strip().casefold() if value is not None else ""


def _safe_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_completed_windows(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: datetime,
    policy: WindowPolicy,
    modules: Iterable[int] = range(1, 9),
    source_fields: Mapping[str, str] = SOURCE_FIELDS,
    module_status_template: str = "Status_{module}",
    busy_template: str = "Busy_{module}",
    sv_template: str = "SV_{module}",
) -> list[QualifiedWindow]:
    """Aggregate observed source rows; emit only closed windows with explicit QA.

    `rows` must include every source sample for each window being assessed. A
    low count/large gap fails closed. No missing second is synthesized.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must include a timezone")
    zone = ZoneInfo(policy.source_timezone)
    cutoff = _source_local(as_of, zone) - timedelta(seconds=policy.late_arrival_seconds)
    selected_modules = tuple(modules)
    if set(source_fields) != set(SOURCE_FIELDS):
        raise ValueError("all seven physical sensor mappings are required")
    if any(module < 1 or module > 8 for module in selected_modules):
        raise ValueError("module numbers must be 1..8")
    groups: dict[tuple[str, datetime], list[tuple[datetime, Mapping[str, Any]]]] = defaultdict(list)
    for row in rows:
        machine = str(row.get("machine_number") or "").strip()
        if not machine:
            raise ValueError("machine_number is required")
        stamp = _source_local(row.get("recorded_at"), zone)
        groups[(machine, _window_start(stamp, policy.window_minutes))].append((stamp, row))

    duration = timedelta(minutes=policy.window_minutes)
    expected = math.ceil(duration.total_seconds() / policy.expected_cadence_seconds)
    minimum = math.ceil(expected * policy.minimum_coverage)
    result: list[QualifiedWindow] = []
    expected_run, expected_on = _state(policy.compressor_on), _state(policy.module_on)
    normal_busy, off_sv = {_state(x) for x in policy.busy_normal}, {_state(x) for x in policy.sv_off}
    module_columns = {m:(module_status_template.format(module=m),busy_template.format(module=m),
        sv_template.format(module=m),{name:template.format(module=m) for name,template in source_fields.items()}) for m in selected_modules}
    for (machine, start), samples in sorted(groups.items()):
        end = start + duration
        if end > cutoff:
            continue
        samples.sort(key=lambda item: item[0])
        stamps = [item[0] for item in samples]
        # One-second coverage counts occupied second bins, not distinct
        # microsecond timestamps. Two samples in one second cannot replace a
        # missing second elsewhere and are treated as a source duplicate.
        unique_count = len({stamp.replace(microsecond=0) for stamp in stamps})
        gaps = [(stamps[0] - start).total_seconds(), (end - stamps[-1]).total_seconds()]
        gaps.extend((later - earlier).total_seconds() for earlier, later in zip(stamps, stamps[1:]))
        maximum_gap = max(gaps)
        coverage = min(1.0, unique_count / expected)
        common_status = "PASS"
        common_reason = ""
        if unique_count != len(samples):
            common_status, common_reason = "DATA_QUALITY", "DUPLICATE_MACHINE_SECOND"
        elif unique_count < minimum:
            common_status, common_reason = "INSUFFICIENT_DATA", "LOW_SAMPLE_COVERAGE"
        elif maximum_gap > policy.maximum_gap_seconds:
            common_status, common_reason = "DATA_QUALITY", "SOURCE_GAP"

        for module in selected_modules:
            status_col,busy_col,sv_col,sensor_cols = module_columns[module]
            status, reason = common_status, common_reason
            values: dict[str, float] | None = None
            if status == "PASS":
                if any(_state(row.get("Status")) != expected_run for _, row in samples):
                    status, reason = "STATE_NOT_ELIGIBLE", "COMPRESSOR_NOT_STABLE_RUN"
                elif any(_state(row.get(status_col)) != expected_on for _, row in samples):
                    status, reason = "STATE_NOT_ELIGIBLE", "MODULE_NOT_STABLE_ON"
                elif any(_state(row.get(busy_col)) not in normal_busy for _, row in samples):
                    status, reason = "STATE_NOT_ELIGIBLE", "MANUAL_OR_UNKNOWN_BUSY"
                elif any(_state(row.get(sv_col)) not in off_sv for _, row in samples):
                    status, reason = "STATE_NOT_ELIGIBLE", "BYPASS_OR_UNKNOWN_SV"
                else:
                    observed: dict[str, list[float]] = {}
                    for name, column in sensor_cols.items():
                        numbers = [_safe_number(row.get(column)) for _, row in samples]
                        if any(number is None for number in numbers):
                            status, reason = "DATA_QUALITY", f"MISSING_OR_NONFINITE_{name.upper()}"
                            break
                        observed[name] = [float(number) for number in numbers if number is not None]
                    if status == "PASS":
                        if any(value < 0 for value in observed["valve"]):
                            status, reason = "STATE_NOT_ELIGIBLE", "NEGATIVE_VALVE_COMMAND"
                        else:
                            values = {name: sum(numbers) / len(numbers) for name, numbers in observed.items()}
                            values["dp1"] = values["hp1"] - values["lp1"]
                            values["dp2"] = values["hp2"] - values["lp2"]
            result.append(QualifiedWindow(
                machine_number=machine, module=module, window_start=start, window_end=end,
                sv_state="Off" if status == "PASS" else "UNKNOWN",
                state_code=STATE_CODE if status == "PASS" else "NOT_SCORED",
                sample_count=len(samples), expected_samples=expected, coverage=coverage,
                maximum_observed_gap_seconds=maximum_gap, data_quality_status=status,
                reason=reason, features=values,
            ))
    return result
