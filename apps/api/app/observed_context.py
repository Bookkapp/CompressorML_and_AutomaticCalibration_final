"""Observed minute measurements for every control state; quality is not health.

The legacy Cold-only feature contract remains unchanged. This separate version
retains homing, manual and bypass observations without making them fit-eligible.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .qualified_windows import SOURCE_FIELDS, WindowPolicy, _safe_number, _source_local, _state

VERSION = "observed-all-state-1m-v2"
PHYSICAL = ("hp1", "lp1", "hp2", "lp2", "dp1", "dp2", "temphi", "templo")


@dataclass(frozen=True)
class ObservedMinute:
    machine_number: str
    module: int
    window_start: datetime
    window_end: datetime
    sample_count: int
    coverage: float
    maximum_observed_gap_seconds: float
    measurement_quality: str
    reason: str
    features: dict | None
    state_counts: dict
    context_key: str | None
    control: dict
    feature_version: str = VERSION

    @property
    def measured(self):
        return self.measurement_quality == "PASS" and self.features is not None


def build_observed_minutes(rows, *, as_of, policy: WindowPolicy, modules=range(1, 9),
                           source_fields=SOURCE_FIELDS, module_status_template="Status_{module}",
                           busy_template="Busy_{module}", sv_template="SV_{module}"):
    if as_of.tzinfo is None:
        raise ValueError("aware as_of is required")
    modules = tuple(modules)
    if not modules or len(set(modules)) != len(modules) or any(m not in range(1, 9) for m in modules):
        raise ValueError("unique modules 1..8 required")
    if set(source_fields) != set(SOURCE_FIELDS):
        raise ValueError("complete sensor mapping required")
    zone = ZoneInfo(policy.source_timezone)
    cutoff = _source_local(as_of, zone) - timedelta(seconds=policy.late_arrival_seconds)
    groups = defaultdict(list)
    for row in rows:
        machine = str(row.get("machine_number") or "").strip()
        if not machine:
            raise ValueError("machine_number required")
        stamp = _source_local(row.get("recorded_at"), zone)
        groups[machine, stamp.replace(second=0, microsecond=0)].append((stamp, row))
    result = []
    expected = math.ceil(60 / policy.expected_cadence_seconds)
    for (machine, start), samples in sorted(groups.items()):
        end = start + timedelta(minutes=1)
        if end > cutoff:
            continue
        samples.sort(key=lambda x: x[0])
        stamps = [x[0] for x in samples]
        occupied = len({x.replace(microsecond=0) for x in stamps})
        gap = max([(stamps[0]-start).total_seconds(), (end-stamps[-1]).total_seconds(),
                   *((b-a).total_seconds() for a, b in zip(stamps, stamps[1:]))])
        common, reason = "PASS", ""
        if occupied != len(samples):
            common, reason = "DATA_QUALITY", "DUPLICATE_MACHINE_SECOND"
        elif occupied < math.ceil(expected * policy.minimum_coverage):
            common, reason = "INSUFFICIENT_DATA", "LOW_SAMPLE_COVERAGE"
        elif gap > policy.maximum_gap_seconds:
            common, reason = "DATA_QUALITY", "SOURCE_GAP"
        for module in modules:
            counts = {name: dict(Counter(_state(r.get(col)) for _, r in samples)) for name, col in (
                ("compressor", "Status"), ("module", module_status_template.format(module=module)),
                ("busy", busy_template.format(module=module)), ("sv", sv_template.format(module=module)))}
            # A stable source code is context, never proof of a healthy regime.
            stable = all(len(c) == 1 and "" not in c for c in counts.values())
            context = "|".join(next(iter(counts[n])) for n in ("compressor", "module", "busy", "sv")) if stable else None
            quality, why, values = common, reason, None
            valve = [_safe_number(r.get(source_fields["valve"].format(module=module))) for _, r in samples]
            valid_valve = [v for v in valve if v is not None]
            control = {"valve_min": min(valid_valve) if valid_valve else None,
                       "valve_max": max(valid_valve) if valid_valve else None,
                       "valve_mean": sum(valid_valve)/len(valve) if len(valid_valve) == len(valve) else None,
                       "valve_samples": len(valid_valve)}
            if quality == "PASS":
                measured = {}
                for name, template in source_fields.items():
                    if name == "valve":
                        continue
                    numbers = [_safe_number(r.get(template.format(module=module))) for _, r in samples]
                    if any(n is None for n in numbers):
                        quality, why = "DATA_QUALITY", f"MISSING_OR_NONFINITE_{name.upper()}"
                        break
                    measured[name] = sum(numbers)/len(numbers)
                if quality == "PASS":
                    measured.update(dp1=measured["hp1"]-measured["lp1"], dp2=measured["hp2"]-measured["lp2"])
                    values = measured
            # Explicit local test provenance stays visible beside numeric Raw.
            # MOCK_NORMAL is never an eligible Run/controller state.
            if "mock_normal" in counts["compressor"]:
                why = "MOCK_SOURCE_DATA"
            result.append(ObservedMinute(machine, module, start, end, len(samples), min(1, occupied/expected),
                                         gap, quality, why, values, counts, context, control))
    return result
