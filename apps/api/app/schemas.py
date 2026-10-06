from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FleetMachine(BaseModel):
    machine_number: str
    scored_rows: int
    raw_flag_rate_pct: float
    alerts: int
    alerts_per_machine_day: float
    condition_status: str
    latest_event_time: datetime | None = None


class FleetSummary(BaseModel):
    mode: str
    release_state: str
    configured_machines: int
    scored_machines: int
    open_incidents: int
    data_quality_issues: int
    condition_index_available: bool
    dashboard_refresh_minutes: int
    scoring_interval_minutes: int
    cadence_gate: str
    machines: list[FleetMachine]


class TimelinePoint(BaseModel):
    event_time: datetime
    hp1: float | None = None
    lp1: float | None = None
    hp2: float | None = None
    lp2: float | None = None
    valve: float | None = None
    temp_high: float | None = None
    temp_low: float | None = None
    anomaly_score: float | None = None
    threshold: float | None = None
    raw_flag: bool = False
    persistent_flag: bool = False
    sv_state: str | None = None
    busy_state: str | None = None
    state_code: str | None = None
    message_code: str | None = None
    message_text: str | None = None
    data_quality_status: str = "PASS"


class TimelineResponse(BaseModel):
    machine_number: str
    module: int
    source_grain: str
    source_timezone: str
    condition_index_available: bool
    points: list[TimelinePoint]


class Incident(BaseModel):
    alert_id: int
    machine_number: str
    module: int
    episode_start: datetime
    detected_at: datetime
    last_observed_at: datetime | None = None
    alert_status: str
    severity: str
    claim_level: str
    release_version: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confirmation_status: str = "PENDING"
    is_prospective: bool | None = None


class TechnicianConfirmationCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    confirmation_status: Literal[
        "EQUIPMENT_ANOMALY", "NO_EQUIPMENT_ANOMALY", "UNRESOLVED"
    ]
    technician_note: str = Field(default="", max_length=4000)


class TechnicianConfirmationCreated(BaseModel):
    confirmation_id: int
    alert_id: int
    label_status: str
    message: str


class CalibrationBatch(BaseModel):
    batch_id: str
    batch_status: str
    source_start: datetime
    calibration_end: datetime
    shadow_start: datetime
    shadow_end: datetime
    source_timezone: str
    profile_algorithm_version: str
    feature_version: str
    profile_count: int = 0
    ready_for_approval_count: int = 0
    created_at: datetime | None = None


class CalibrationProfile(BaseModel):
    profile_id: int
    batch_id: str
    profile_version: str
    machine_number: str
    module: int
    sv_state: str
    state_code: str
    profile_status: str
    reason_codes: list[str] = Field(default_factory=list)
    calibration_windows: int
    calibration_days: int
    quarantine_pct: float | None = None
    max_half_shift_rz: float | None = None
    shadow_windows: int
    shadow_days: int
    shadow_flag_pct: float | None = None
    persistent_flag_pct: float | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)


class CalibrationShadowPoint(BaseModel):
    event_time: datetime
    deviation_score: float | None = None
    threshold_value: float | None = None
    raw_flag: bool
    persistent_flag: bool
    data_quality_status: str


class CalibrationReviewCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    decision: Literal["APPROVE", "REJECT"]
    review_note: str = Field(default="", max_length=1000)


class CalibrationReviewResult(BaseModel):
    batch_id: str
    profile_id: int
    batch_status: str
    review_id: int
    message: str


class AutomationStatus(BaseModel):
    dashboard_refresh_minutes: int
    desired_scoring_interval_minutes: int
    locked_release_interval_minutes: int
    cadence_gate: str
    profile_schedule: str
    model_schedule: str
    scoring_schedule: str
    profile_activation: str
    model_activation: str
    latest_runs: list[dict[str, Any]] = Field(default_factory=list)


class SourceMachine(BaseModel):
    machine_number: str
    display_name: str
    record_count: int | None = None
    row_count: int | None = None
    latest_recorded_at: datetime | None = None
    first_event: datetime | None = None



class ManualCalibrationRequest(BaseModel):
    machine_number: str | None = None
    target_machine: str | None = None
    history_days: int = Field(default=28, ge=7, le=90)
    shadow_days: int = Field(default=3, ge=1, le=14)
    force: bool = False


class ManualCalibrationResult(BaseModel):
    status: str
    batch_id: str | None = None
    target_machine: str | None = None
    profile_count: int = 0
    ready_count: int = 0
    message: str


class MachineApprovalRequest(BaseModel):
    approver_id: str | None = None
    batch_id: str | None = None
    review_note: str | None = None


class MachineApprovalResult(BaseModel):
    approved_count: int
    profile_ids: list[int]
    message: str
