from datetime import timedelta

import pandas as pd
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from apps.api.app.main import app
from apps.api.app import calibration
from apps.api.app.calibration import _state_records, build_candidate_profiles
from apps.api.app.config import Settings, get_settings
from apps.api.app.schemas import TechnicianConfirmationCreate


client = TestClient(app)


@pytest.fixture(autouse=True)
def enforce_test_settings(monkeypatch):
    monkeypatch.setenv("HT9046MX_APP_MODE", "demo")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_is_shadow_and_has_no_plc_path():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["release_state"] == "SHADOW_ONLY_NOT_AUTHORIZED"
    assert body["plc_write_path"] is False


def test_fleet_summary_exposes_cadence_gate():
    response = client.get("/api/v1/fleet/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["dashboard_refresh_minutes"] == 5
    assert body["scoring_interval_minutes"] == 1
    assert body["cadence_gate"] == "RECALIBRATION_REQUIRED"
    assert body["condition_index_available"] is False


def test_demo_confirmation_is_read_only():
    response = client.post(
        "/api/v1/incidents/1/confirmations",
        headers={"X-Technician-Id": "tech-01"},
        json={
            "idempotency_key": "test-review-0001",
            "confirmation_status": "UNRESOLVED",
            "technician_note": "preview only",
        },
    )
    assert response.status_code == 409


def test_binary_confirmation_accepts_anomaly_without_cause():
    confirmation = TechnicianConfirmationCreate.model_validate(
        {
            "idempotency_key": "binary-confirmation-01",
            "confirmation_status": "EQUIPMENT_ANOMALY",
        }
    )
    assert confirmation.confirmation_status == "EQUIPMENT_ANOMALY"


def test_confirmation_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TechnicianConfirmationCreate.model_validate(
            {
                "idempotency_key": "invalid-confirmation-01",
                "confirmation_status": "LEAK_CONFIRMED",
            }
        )


def test_feedback_start_requires_timezone_and_normalizes_to_utc():
    settings = Settings(
        technician_feedback_start_at="2026-09-15T00:00:00+07:00",
        alert_datetime_timezone="UTC",
    )
    assert settings.technician_feedback_start_at is not None
    assert settings.technician_feedback_start_at.isoformat() == "2026-09-14T17:00:00+00:00"
    assert settings.alert_timezone is not None
    assert settings.alert_timezone.key == "UTC"

    with pytest.raises(ValidationError):
        Settings(technician_feedback_start_at="2026-09-15T00:00:00")

    with pytest.raises(ValidationError):
        Settings(alert_datetime_timezone="not-a-timezone")


def test_demo_calibration_evidence_exposes_profiles_and_three_day_graph():
    batches = client.get("/api/v1/calibration/batches")
    assert batches.status_code == 200
    batch = batches.json()[0]
    assert batch["batch_status"] == "DEMO_HISTORICAL_EVIDENCE"

    profiles = client.get(f"/api/v1/calibration/batches/{batch['batch_id']}/profiles")
    assert profiles.status_code == 200
    profile = profiles.json()[0]
    assert profile["reason_codes"]

    shadow = client.get(f"/api/v1/calibration/profiles/{profile['profile_id']}/shadow")
    assert shadow.status_code == 200
    assert shadow.json()

    review = client.post(
        f"/api/v1/calibration/profiles/{profile['profile_id']}/review",
        headers={"X-Approver-Id": "approver-01"},
        json={"idempotency_key": "demo-profile-review-01", "decision": "APPROVE"},
    )
    assert review.status_code == 409


def test_candidate_profile_requires_forward_shadow_and_can_reach_review_ready():
    minute = pd.date_range("2026-01-01", periods=480, freq="30min")
    frame = pd.DataFrame({
        "minute": minute,
        "machine_number": "MX999",
        "module": 1,
        "sv_state": "Off",
        "state_code": "COMPRESSOR_ON_COLD_SV_OFF",
    })
    for index, feature in enumerate(("hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo")):
        frame[feature] = 100.0 + index * 10 + (frame.index % 5) * 0.02
    frame["dp1"] = frame["hp1"] - frame["lp1"]
    frame["dp2"] = frame["hp2"] - frame["lp2"]
    frame["day"] = frame["minute"].dt.date
    settings = Settings(
        source_timezone="Asia/Bangkok",
        profile_state_contract_version="state-v1",
        profile_controller_codebook_version="controller-v1",
        profile_service_epoch_version="service-v1",
        profile_max_shadow_flag_pct=25.0,
        profile_min_shadow_windows=100,
    )
    shadow_start = frame["minute"].max().to_pydatetime() - timedelta(days=3)
    profile = build_candidate_profiles(frame, settings, shadow_start)[0]
    assert profile["status"] == "READY_FOR_APPROVAL"
    assert profile["shadow"]["day"].nunique() >= 3
    assert profile["threshold"]["deviation_score_q995"] is not None


def test_state_gate_excludes_manual_busy_and_sv_on_from_cold_baseline():
    """Only confirmed compressor-on + SV-off non-manual windows are eligible."""
    row: dict[str, object] = {
        "minute": pd.Timestamp("2026-01-01T00:00:00"),
        "machine_number": "MX999",
        "global_status_min": "Run",
        "global_status_max": "Run",
    }
    for module in range(1, 9):
        prefix = f"m{module}_"
        for feature, value in {"hp1": 100, "lp1": 20, "hp2": 210, "lp2": 30, "valve": 40, "temphi": 50, "templo": 60}.items():
            row[f"{prefix}{feature}"] = value
        row.update({
            f"{prefix}status_min": "On", f"{prefix}status_max": "On",
            f"{prefix}busy_min": "0", f"{prefix}busy_max": "0",
            f"{prefix}sv_min": "Off", f"{prefix}sv_max": "Off",
        })
    row["m2_busy_min"] = row["m2_busy_max"] = "1"  # manual/service flag
    row["m3_sv_min"] = row["m3_sv_max"] = "On"      # bypass/non-cold context
    result = _state_records(pd.DataFrame([row]), Settings(profile_settle_minutes=1))
    assert set(result["module"]) == {1, 4, 5, 6, 7, 8}
    assert set(result["state_code"]) == {"COMPRESSOR_ON_COLD_SV_OFF"}


def test_reviewed_batch_remains_in_calibration_retry_watermark(monkeypatch):
    captured: list[str] = []

    class Result:
        @staticmethod
        def scalar_one_or_none():
            return "2026-08-09 23:55:00"

    class Connection:
        def execute(self, statement):
            captured.append(str(statement))
            return Result()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(calibration, "connection", lambda: Connection())
    assert calibration._last_shadow_end() is not None
    assert "PARTIALLY_REVIEWED" in captured[0]


def test_source_machines_and_manual_calibration_trigger():
    # Test GET source machines
    response = client.get("/api/v1/source/machines")
    assert response.status_code == 200
    machines = response.json()
    assert len(machines) > 0
    assert any(m["machine_number"] == "MX080" for m in machines)

    # Test POST manual calibration run in demo mode
    cal_response = client.post(
        "/api/v1/calibration/run",
        json={"machine_number": "MX080", "history_days": 14, "shadow_days": 3},
    )
    assert cal_response.status_code == 200
    res_body = cal_response.json()
    assert res_body["target_machine"] == "MX080"
    assert "Demo mode" in res_body["message"] or res_body["status"] == "COMPLETED"


def test_candidate_profile_contains_correlations_and_detailed_baseline():
    batches = client.get("/api/v1/calibration/batches")
    assert batches.status_code == 200
    batch_id = batches.json()[0]["batch_id"]
    profiles = client.get(f"/api/v1/calibration/batches/{batch_id}/profiles")
    assert profiles.status_code == 200
    profile = profiles.json()[0]
    stats = profile["statistics"]
    assert "hp2" in stats
    assert "median" in stats["hp2"]
    assert "correlations" in stats
    assert "hp2" in stats["correlations"]
