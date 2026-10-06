from __future__ import annotations

from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HT9046MX_", env_file=".env", extra="ignore"
    )

    app_mode: str = "demo"
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    api_cors_origins: str = "http://localhost:5173"
    # Portable model repository and optional historical evidence location.
    # Server inference needs only the model store, never notebook outputs.
    fleet_stable_store: Path | None = None
    fleet_reference_root: Path | None = None

    analytics_db_host: str = "10.195.17.73"
    analytics_db_port: int = 3306
    analytics_db_name: str = "ht9046mx_analytics"
    analytics_db_user: str = ""
    analytics_db_password: str = ""

    # Raw telemetry is a separate, read-only connection. These values must be
    # confirmed on the Server; there is deliberately no implicit fallback to
    # the analytics database.
    source_db_host: str = ""
    source_db_port: int = 3306
    source_db_name: str = ""
    source_db_user: str = ""
    source_db_password: str = ""
    source_table: str = ""
    source_timestamp_column: str = "recorded_at"
    source_machine_column: str = "machine_number"
    source_global_status_column: str = "Status"
    source_hp1_template: str = "Hp_1st_{module}"
    source_lp1_template: str = "Lp_1st_{module}"
    source_hp2_template: str = "Hp_2nd_{module}"
    source_lp2_template: str = "Lp_2nd_{module}"
    source_valve_template: str = "Valve_{module}"
    source_temp_high_template: str = "TempHi_{module}"
    source_temp_low_template: str = "TempLo_{module}"
    source_module_status_template: str = "Status_{module}"
    source_busy_template: str = "Busy_{module}"
    source_sv_template: str = "SV_{module}"
    source_timezone: str = ""
    source_pressure_unit: str = ""  # owner-confirmed psi; psig/psia basis required for Active
    # The source value denoting Compressor ON.  "Run" is the currently
    # configured controller spelling, not an inference from a pressure tag.
    source_compressor_on_status: str = "Run"
    source_module_on_status: str = "On,Run,Off"
    source_sv_on_values: str = "On,1,True"
    source_sv_off_values: str = "Off,0,False"
    # Busy=1 is a manual/service-operation flag (for example MValveHome or
    # ChangeValve) and is excluded.  These are the normal, non-manual values.
    source_busy_normal_values: str = "0,False,Off"

    # Observed-second → completed one-minute contract is opt-in and read-only.
    # Historical minute-snapshot and five-minute profiles are incompatible.
    qualified_1m_preview_enabled: bool = False
    local_rehearsal_dashboard_enabled: bool = False
    # Owner-authorized local UI rehearsal; no production Active pointers.
    # Explicit durable worker opt-in. Shadow persists evidence but never sends PM alerts.
    detector_worker_enabled: bool = False
    detector_fleet_shadow_enabled: bool = False
    detector_cron: str = "*/5 * * * *"
    detector_shadow_only: bool = True
    detector_machines: str = ""
    detector_source_id_column: str = "id"
    detector_overlap_minutes: int = Field(default=30, ge=10, le=1440)
    detector_max_source_rows: int = Field(default=10000, ge=60, le=1000000)
    detector_bridge_enabled: bool = False
    detector_alerts_enabled: bool = False
    detector_critical_score_ratio: float = Field(default=2.0, gt=1)
    detector_pm_db_host: str = ""
    detector_pm_db_port: int = 3306
    detector_pm_db_name: str = "predictive_maintenance"
    detector_pm_db_user: str = ""
    detector_pm_db_password: str = ""
    source_expected_cadence_seconds: float = Field(default=1.0, gt=0, le=300)
    qualified_1m_minimum_coverage: float = Field(default=0.95, gt=0, le=1)
    qualified_1m_maximum_gap_seconds: float = Field(default=5.0, gt=0, le=300)
    qualified_1m_late_arrival_seconds: float = Field(default=30.0, ge=0, le=300)

    dashboard_refresh_minutes: int = 5
    scoring_interval_minutes: int = 1
    technician_feedback_start_at: datetime | None = None
    alert_datetime_timezone: str = ""

    profile_candidate_enabled: bool = False
    profile_window_contract: str = "qualified_observed_1m"
    profile_history_days: int = Field(default=28, ge=7, le=90)
    profile_shadow_days: int = Field(default=3, ge=3, le=30)
    profile_min_calibration_days: int = Field(default=7, ge=3, le=90)
    profile_min_calibration_windows: int = Field(default=200, ge=50, le=100000)
    profile_min_shadow_windows: int = Field(default=200, ge=50, le=100000)
    profile_settle_minutes: int = Field(default=3, ge=1, le=60)
    profile_quarantine_z: float = Field(default=8.0, ge=3.0, le=25.0)
    profile_max_quarantine_pct: float = Field(default=5.0, ge=0.0, le=50.0)
    profile_max_half_shift_rz: float = Field(default=1.5, ge=0.1, le=10.0)
    profile_max_shadow_flag_pct: float = Field(default=1.0, ge=0.0, le=100.0)
    profile_retry_min_new_days: int = Field(default=3, ge=1, le=30)
    profile_state_contract_version: str = ""
    profile_controller_codebook_version: str = ""
    profile_service_epoch_version: str = ""

    profile_candidate_cron: str = "0 2 * * *"
    model_candidate_cron: str = "0 3 * * 0"
    shadow_score_cron: str = "* * * * *"
    profile_candidate_command: str = ""
    model_candidate_command: str = ""
    shadow_score_command: str = ""

    @field_validator("technician_feedback_start_at")
    @classmethod
    def validate_feedback_start(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("HT9046MX_TECHNICIAN_FEEDBACK_START_AT must include a timezone offset")
        return value.astimezone(timezone.utc)

    @field_validator("alert_datetime_timezone")
    @classmethod
    def validate_alert_datetime_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("HT9046MX_ALERT_DATETIME_TIMEZONE must be a valid IANA timezone") from exc
        return normalized

    @field_validator("source_timezone")
    @classmethod
    def validate_source_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("HT9046MX_SOURCE_TIMEZONE must be a valid IANA timezone") from exc
        return normalized

    @field_validator("source_pressure_unit")
    @classmethod
    def validate_source_pressure_unit(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and normalized not in {"psi", "psig", "psia"}:
            raise ValueError("HT9046MX_SOURCE_PRESSURE_UNIT must be psi, psig or psia after source-owner verification")
        return normalized

    @property
    def alert_timezone(self) -> ZoneInfo | None:
        return ZoneInfo(self.alert_datetime_timezone) if self.alert_datetime_timezone else None

    @property
    def source_database_url(self) -> str | None:
        if not all((self.source_db_host, self.source_db_name, self.source_db_user, self.source_db_password)):
            return None
        from urllib.parse import quote_plus

        return (
            f"mysql+pymysql://{quote_plus(self.source_db_user)}:{quote_plus(self.source_db_password)}"
            f"@{self.source_db_host}:{self.source_db_port}/{self.source_db_name}?charset=utf8mb4"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.api_cors_origins.split(",") if item.strip()]

    @property
    def database_url(self) -> str | None:
        if not self.analytics_db_user or not self.analytics_db_password:
            return None
        from urllib.parse import quote_plus

        user = quote_plus(self.analytics_db_user)
        password = quote_plus(self.analytics_db_password)
        return (
            f"mysql+pymysql://{user}:{password}@{self.analytics_db_host}:"
            f"{self.analytics_db_port}/{self.analytics_db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
