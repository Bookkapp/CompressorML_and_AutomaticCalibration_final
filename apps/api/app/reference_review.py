"""Human-selected fit interval; untouched historical shadow; no activation.

All timestamps in the selection are source-local, minute-aligned [start, end).
The immutable digest includes ineligible windows: late commits cannot silently
change a reviewed selection. UI aggregation is presentation-only.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import Settings
from .inference import clean_machine_code
from .qualified_candidate_registry import registry_candidate_from_windows
from .qualified_windows import FEATURES, QualifiedWindow
from .qualified_policy import manifest

REVIEW_VERSION = "manual-reference-complete-day-shadow-v3-physical"


class ExcludedPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: datetime
    end: datetime
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def valid(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3 or self.start >= self.end:
            raise ValueError("Exclusion needs an ordered interval and a written reason")
        for value in (self.start, self.end):
            if value.tzinfo or value.second or value.microsecond:
                raise ValueError("Use minute-aligned source-local exclusion times")
        return self


class ReferencePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=100)
    machine_number: str = Field(min_length=1, max_length=40)
    module: int = Field(ge=1, le=8)
    history_days: int = Field(default=28, ge=7, le=90)
    reference_start: date | None = None
    reference_end: date | None = None  # exclusive, displayed as such
    shadow_end: date | None = None  # explicit historical cutoff, never future
    shadow_selection_reason: str = Field(default="", max_length=500)
    exclusions: list[ExcludedPeriod] = Field(default_factory=list, max_length=30)
    review_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def valid(self):
        self.machine_number = clean_machine_code(self.machine_number)
        if not self.machine_number or not any(c.isdigit() for c in self.machine_number):
            raise ValueError("Choose one discovered machine, not ALL")
        if bool(self.reference_start) != bool(self.reference_end):
            raise ValueError("Provide both reference start and exclusive end")
        if self.reference_start and self.reference_start >= self.reference_end:
            raise ValueError("Reference end must follow start")
        self.shadow_selection_reason = self.shadow_selection_reason.strip()
        if self.shadow_end and len(self.shadow_selection_reason) < 3:
            raise ValueError("Write a reason for selecting a historical Shadow cutoff")
        return self


class ReferenceBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledge_reference: bool
    review_note: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def valid(self):
        self.review_note = self.review_note.strip()
        if not self.acknowledge_reference or len(self.review_note) < 3:
            raise ValueError("Acknowledge the reference and write a review note")
        return self


def resolve_selection(request: ReferencePreviewRequest, latest: datetime, settings: Settings) -> dict[str, Any]:
    if settings.profile_shadow_days != 3:
        raise ValueError("Manual historical reference review requires profile_shadow_days=3")
    zone = ZoneInfo(settings.source_timezone)
    local = latest.astimezone(zone).replace(tzinfo=None) if latest.tzinfo else latest
    # Grace also applies near midnight: do not include a day not fully closed.
    latest_complete_end = (local - timedelta(seconds=settings.qualified_1m_late_arrival_seconds)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    shadow_end = datetime.combine(request.shadow_end, datetime.min.time()) if request.shadow_end else latest_complete_end
    if not latest_complete_end - timedelta(days=90) <= shadow_end <= latest_complete_end:
        raise ValueError("Shadow cutoff must be a closed historical date within the latest 90 days")
    shadow_start = shadow_end - timedelta(days=3)
    earliest = shadow_start - timedelta(days=90)
    start = datetime.combine(request.reference_start, datetime.min.time()) if request.reference_start else shadow_start - timedelta(days=request.history_days)
    end = datetime.combine(request.reference_end, datetime.min.time()) if request.reference_end else shadow_start
    if not earliest <= start < end <= shadow_start:
        raise ValueError("Reference must be before Shadow and within its preceding 90 days")
    exclusions = sorted(request.exclusions, key=lambda x: x.start)
    previous_end = start
    for interval in exclusions:
        if not start <= interval.start < interval.end <= end or interval.start < previous_end:
            raise ValueError("Exclusions must be inside Reference and must not overlap")
        previous_end = interval.end
    return {"version": REVIEW_VERSION, "machine_number": request.machine_number,
            "scoring_policy": manifest(),
            "module": request.module, "source_timezone": settings.source_timezone,
            "source_latest": local.isoformat(), "reference_start": start.isoformat(),
            "latest_complete_end": latest_complete_end.isoformat(),
            "shadow_selection_reason": request.shadow_selection_reason,
            "reference_end": end.isoformat(), "shadow_start": shadow_start.isoformat(),
            "shadow_end": shadow_end.isoformat(), "exclusions": [x.model_dump(mode="json") for x in exclusions],
            "review_note": request.review_note,
            "policy": {key: getattr(settings, key) for key in (
                "source_db_name", "source_table", "source_machine_column", "source_timestamp_column",
                "source_global_status_column", "source_compressor_on_status", "source_module_status_template",
                "source_busy_template", "source_busy_normal_values", "source_sv_template", "source_sv_off_values",
                "source_hp1_template", "source_lp1_template", "source_hp2_template", "source_lp2_template",
                "source_valve_template", "source_temp_high_template", "source_temp_low_template",
                "source_expected_cadence_seconds", "qualified_1m_minimum_coverage",
                "qualified_1m_maximum_gap_seconds", "qualified_1m_late_arrival_seconds",
                "profile_window_contract", "profile_shadow_days", "profile_min_calibration_days", "profile_min_calibration_windows", "profile_min_shadow_windows",
                "profile_quarantine_z", "profile_max_quarantine_pct", "profile_max_half_shift_rz",
                "profile_max_shadow_flag_pct", "source_pressure_unit", "profile_state_contract_version",
                "profile_controller_codebook_version", "profile_service_epoch_version")}}


def bounds(selection: dict):
    return tuple(datetime.fromisoformat(selection[key]) for key in (
        "reference_start", "reference_end", "shadow_start", "shadow_end"))


def is_excluded(window: QualifiedWindow, selection: dict) -> bool:
    return any(datetime.fromisoformat(x["start"]) < window.window_end
               and window.window_start < datetime.fromisoformat(x["end"])
               for x in selection["exclusions"])


def checked_windows(windows: list[QualifiedWindow], selection: dict) -> list[QualifiedWindow]:
    start, _, _, end = bounds(selection)
    rows = sorted(windows, key=lambda w: w.window_start)
    if any(w.machine_number != selection["machine_number"] or w.module != selection["module"]
           or not start <= w.window_start < w.window_end <= end for w in rows):
        raise ValueError("Source windows do not match the reviewed machine/module/period")
    if len({w.window_start for w in rows}) != len(rows):
        raise ValueError("Duplicate minute in source snapshot")
    return rows


def snapshot_digest(windows: list[QualifiedWindow], selection: dict) -> str:
    digest = hashlib.sha256(json.dumps(selection, sort_keys=True, allow_nan=False).encode())
    for w in checked_windows(windows, selection):
        digest.update(json.dumps([w.window_start.isoformat(), w.window_end.isoformat(), w.sv_state,
            w.state_code, w.sample_count, w.expected_samples, w.coverage,
            w.maximum_observed_gap_seconds, w.data_quality_status, w.reason, w.features,
            w.feature_version], sort_keys=True, allow_nan=False).encode())
    return digest.hexdigest()


def selected_candidate(windows: list[QualifiedWindow], selection: dict, settings: Settings) -> dict:
    start, ref_end, shadow_start, shadow_end = bounds(selection)
    selected = [w for w in checked_windows(windows, selection)
                if (start <= w.window_start < ref_end and not is_excluded(w, selection))
                or shadow_start <= w.window_start < shadow_end]
    # Fix the historical holdout at three complete days, irrespective of a
    # scheduler's separate default. Estimator and acceptance limits stay the same.
    candidate = registry_candidate_from_windows(selected, settings=settings.model_copy(update={"profile_shadow_days": 3}),
        machine_number=selection["machine_number"], module=selection["module"],
        calibration_start=start, shadow_start=shadow_start, shadow_end=shadow_end)
    candidate["validation"]["reference_review"] = selection
    retained = candidate["retained"]
    retained_days = int(retained["day"].nunique()) if not retained.empty else 0
    candidate["validation"].update(retained_reference_windows=len(retained), retained_reference_days=retained_days)
    if len(retained) < settings.profile_min_calibration_windows or retained_days < settings.profile_min_calibration_days:
        candidate["reasons"] = sorted(set([*candidate["reasons"], "INSUFFICIENT_RETAINED_REFERENCE_COVERAGE"]))
        candidate["validation"]["reason_codes"] = candidate["reasons"]
        candidate["status"] = "INSUFFICIENT_DATA"
    candidate["source_digest"] = snapshot_digest(windows, selection)
    return candidate


def make_preview(windows: list[QualifiedWindow], selection: dict, settings: Settings, *, candidate: dict | None = None) -> dict:
    rows = checked_windows(windows, selection)
    candidate = candidate if candidate is not None else selected_candidate(rows, selection, settings)
    start, ref_end, shadow_start, shadow_end = bounds(selection)
    days, charts = [], []
    cursor = start
    by_day, by_hour = {}, {}
    for w in rows:
        by_day.setdefault(w.window_start.date(), []).append(w)
        by_hour.setdefault(w.window_start.replace(minute=0), []).append(w)
    while cursor < shadow_end:
        items = by_day.get(cursor.date(), [])
        reference = [w for w in items if w.window_start < ref_end]
        usable = [w for w in reference if w.eligible and not is_excluded(w, selection)]
        days.append({"date": cursor.date().isoformat(), "phase": "reference" if cursor < ref_end else "shadow" if cursor >= shadow_start else "unused",
            "observed": len(items), "qualified": sum(w.eligible for w in items),
            "selected": len(usable), "excluded": sum(is_excluded(w, selection) for w in reference),
            "missing": 1440 - len(items),
            "source_digest": snapshot_digest(items, selection),
            "reasons": dict(Counter(w.reason or w.data_quality_status for w in items if not w.eligible))})
        cursor += timedelta(days=1)
    cursor = start
    while cursor < shadow_end:
        items = by_hour.get(cursor, [])
        qualified = [w for w in items if w.eligible]
        # Each feature shows median and actual extrema of the eligible minute
        # means. Null buckets stay null; no line crosses a missing hour.
        values = {f: [float(w.features[f]) for w in qualified] for f in FEATURES}
        charts.append({"time": cursor.isoformat(), "phase": "reference" if cursor < ref_end else "shadow" if cursor >= shadow_start else "unused",
            "qualified": len(qualified), "observed": len(items),
            **{f: float(np.median(v)) if v else None for f, v in values.items()},
            **{f + "_range": [min(v), max(v)] if v else None for f, v in values.items()}})
        cursor += timedelta(hours=1)
    fit_days = candidate["calibration"]["day"].nunique() if not candidate["calibration"].empty else 0
    can_build = (len(candidate["calibration"]) >= settings.profile_min_calibration_windows
                 and fit_days >= settings.profile_min_calibration_days
                 and "INSUFFICIENT_RETAINED_REFERENCE_COVERAGE" not in candidate["reasons"])
    shadow_daily = [d for d in days if d["phase"] == "shadow"]
    qualified_shadow_days = sum(d["qualified"] > 0 for d in shadow_daily)
    shadow_ready = (qualified_shadow_days == 3
                    and candidate["validation"]["eligible_shadow_windows"] >= settings.profile_min_shadow_windows)
    can_build = can_build and shadow_ready
    from .calibration_diagnostics import explain
    evidence = explain(rows,selection,candidate)
    for point in charts:
        point.update(evidence["hourly_marks"].get(point["time"],{}))
    evidence.pop("hourly_marks")
    return {"selection": selection, "source_digest": candidate["source_digest"], "diagnostics":evidence,
        "daily": days, "chart": charts, "chart_grain": "1-hour median and min/max of qualified observed-second-derived 1-minute means",
        "can_build": bool(can_build), "candidate_status": candidate["status"], "reason_codes": candidate["reasons"],
        "coverage_issues": [*[f"SHADOW_NO_SOURCE:{d['date']}" for d in shadow_daily if not d["observed"]],
            *[f"SHADOW_NO_QUALIFIED_MINUTES:{d['date']}" for d in shadow_daily if d["observed"] and not d["qualified"]],
            *(["INSUFFICIENT_SHADOW_COVERAGE"] if not shadow_ready else [])],
        "summary": {"reference_minutes": len(candidate["calibration"]), "reference_days": int(fit_days),
            "retained_reference_minutes": candidate["validation"]["retained_reference_windows"],
            "retained_reference_days": candidate["validation"]["retained_reference_days"],
            "quarantine_pct": candidate["quarantine_pct"], "max_half_shift_rz":candidate["validation"].get("max_half_shift_rz"), "shadow_minutes": candidate["validation"]["eligible_shadow_windows"],
            "shadow_days": qualified_shadow_days, "min_shadow_days": 3,
            "min_shadow_minutes": settings.profile_min_shadow_windows, "shadow_ready": shadow_ready,
            "shadow_flag_pct": candidate["validation"]["shadow_flag_pct"],
            "min_reference_days": settings.profile_min_calibration_days,
            "min_reference_minutes": settings.profile_min_calibration_windows},
        "baseline": candidate["statistics"].get("exact_baseline", {}),
        "limitations": ["Selected / qualified does not certify healthy equipment",
            "Historical Shadow is retrospective, not a blind or prospective test",
            "Only qualified Cold minute means are graphed; manual/state/gap counts are retained below",
            "Hourly review cannot resolve every second-level transient; use raw case evidence for diagnosis"]}


def minute_detail(windows: list[QualifiedWindow], selection: dict, day: date, expected_digest: str) -> dict:
    start, _, _, end = bounds(selection)
    cursor = datetime.combine(day, datetime.min.time())
    if not start <= cursor < end:
        raise ValueError("Detail day is outside the reviewed source period")
    rows = checked_windows(windows, selection)
    if any(w.window_start.date() != day for w in rows):
        raise ValueError("Detail input mixes source days")
    if snapshot_digest(rows, selection) != expected_digest:
        raise ValueError("SOURCE_CHANGED_REVIEW_AGAIN")
    by_minute = {w.window_start:w for w in rows}
    points=[]
    while cursor < datetime.combine(day,datetime.min.time())+timedelta(days=1):
        w=by_minute.get(cursor)
        points.append({"time":cursor.isoformat(), "phase":"reference" if cursor<datetime.fromisoformat(selection["reference_end"]) else "shadow" if cursor>=datetime.fromisoformat(selection["shadow_start"]) else "unused", "observed": int(w is not None),
            "qualified":int(w is not None and w.eligible),
            "quality": w.reason or w.data_quality_status if w else "NO_SOURCE_ROWS",
            "samples":w.sample_count if w else 0, "maximum_gap_seconds":w.maximum_observed_gap_seconds if w else None,
            **{f:float(w.features[f]) if w and w.eligible else None for f in FEATURES}})
        cursor+=timedelta(minutes=1)
    return {"day":day.isoformat(),"source_timezone":selection["source_timezone"],"grain":"observed-second-derived 1-minute mean","chart":points}
