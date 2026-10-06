from dataclasses import replace
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import math
import json
from types import SimpleNamespace

import pytest

from apps.api.app.qualified_scoring import ApprovedProfile, QualifiedShadowScorer, TemporalParameters
from apps.api.app.qualified_calibration import fit_one_minute_candidate
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows
from apps.api.app.config import Settings
from apps.api.app.qualified_temporal_fit import fit_shadow_temporal_limits
from apps.api.app.qualified_windows import (
    FEATURES, STATE_CODE, WINDOW_VERSION, QualifiedWindow, WindowPolicy, build_completed_windows,
)
from notebooks.support.qualified_1m_parquet_replay import _machine_code, _replay_candidate


BASE = {"hp1": 100.0, "lp1": 20.0, "hp2": 210.0, "lp2": 30.0,
        "dp1": 80.0, "dp2": 180.0, "valve": 40.0, "temphi": 50.0, "templo": 60.0}
START = datetime(2026, 9, 1)


def test_local_parquet_machine_alias_validation():
    assert [_machine_code(value) for value in ("57", "057", "MX057", "HT9046MX-057")] == ["057"] * 4
    for value in (None, "MX057A", "MX9999"):
        with pytest.raises(ValueError):
            _machine_code(value)


def _window(index=0, *, machine="MX080", module=6, hp2_shift=0.0):
    start = START + timedelta(minutes=index)
    features = dict(BASE)
    features["hp2"] += hp2_shift
    features["dp2"] += hp2_shift
    return QualifiedWindow(machine, module, start, start + timedelta(minutes=1),
                           "Off", STATE_CODE, 60, 60, 1.0, 1.0, "PASS", "", features)


def _profile(*, machine="MX080", module=6, profile_id=42, threshold=4.0):
    return ApprovedProfile(profile_id, "qualified-1m-test-v1", WINDOW_VERSION,
                           machine, module, "Off", STATE_CODE,
                           {feature: BASE[feature] for feature in FEATURES},
                           {feature: 1.0 for feature in FEATURES}, threshold,
                           "qualified-1m-retained-q995-v1")


def _raw(stamp, *, machine="MX080", busy="0", sv="Off", hp2=210.0):
    row = {"machine_number": machine, "recorded_at": stamp, "Status": "Run"}
    for module in range(1, 9):
        row.update({f"Status_{module}": "On", f"Busy_{module}": busy,
                    f"SV_{module}": sv, f"Hp_1st_{module}": 100.0,
                    f"Lp_1st_{module}": 20.0, f"Hp_2nd_{module}": hp2,
                    f"Lp_2nd_{module}": 30.0, f"Valve_{module}": 40.0,
                    f"TempHi_{module}": 50.0, f"TempLo_{module}": 60.0})
    return row


def test_completed_window_uses_observed_seconds_and_nine_features():
    rows = [_raw(START + timedelta(seconds=second)) for second in range(60)]
    windows = build_completed_windows(rows, as_of=(START + timedelta(minutes=1)).replace(tzinfo=timezone.utc),
                                      policy=WindowPolicy("UTC"), modules=[6])
    assert len(windows) == 1
    assert windows[0].eligible
    assert windows[0].sample_count == 60
    assert windows[0].features == BASE


def test_incomplete_duplicate_manual_and_missing_source_fail_closed():
    policy = WindowPolicy("UTC")
    as_of = (START + timedelta(minutes=1)).replace(tzinfo=timezone.utc)
    rows = [_raw(START + timedelta(seconds=second)) for second in range(60)]
    assert build_completed_windows(rows[:20], as_of=as_of, policy=policy, modules=[6])[0].reason == "LOW_SAMPLE_COVERAGE"
    assert build_completed_windows(rows + [rows[0]], as_of=as_of, policy=policy, modules=[6])[0].reason == "DUPLICATE_MACHINE_SECOND"
    same_second = _raw(START + timedelta(microseconds=500000))
    assert build_completed_windows(rows + [same_second], as_of=as_of, policy=policy, modules=[6])[0].reason == "DUPLICATE_MACHINE_SECOND"
    manual = list(rows)
    manual[30] = {**manual[30], "Busy_6": "1"}
    assert build_completed_windows(manual, as_of=as_of, policy=policy, modules=[6])[0].data_quality_status == "STATE_NOT_ELIGIBLE"
    missing = list(rows)
    missing[30] = {**missing[30], "Hp_2nd_6": None}
    assert build_completed_windows(missing, as_of=as_of, policy=policy, modules=[6])[0].reason == "MISSING_OR_NONFINITE_HP2"


def test_partial_window_is_not_scored_even_with_samples():
    rows = [_raw(START + timedelta(seconds=second)) for second in range(60)]
    assert build_completed_windows(rows, as_of=(START + timedelta(seconds=30)).replace(tzinfo=timezone.utc),
                                   policy=WindowPolicy("UTC"), modules=[6]) == []


def test_window_builder_honors_configured_source_mapping():
    rows = [_raw(START + timedelta(seconds=second)) for second in range(60)]
    for row in rows:
        row["HighPressure_6"] = row.pop("Hp_2nd_6")
        row["CoolingSV_6"] = row.pop("SV_6")
    fields = {"hp1": "Hp_1st_{module}", "lp1": "Lp_1st_{module}",
              "hp2": "HighPressure_{module}", "lp2": "Lp_2nd_{module}",
              "valve": "Valve_{module}", "temphi": "TempHi_{module}",
              "templo": "TempLo_{module}"}
    windows = build_completed_windows(
        rows, as_of=(START + timedelta(minutes=1)).replace(tzinfo=timezone.utc),
        policy=WindowPolicy("UTC"), modules=[6], source_fields=fields,
        sv_template="CoolingSV_{module}",
    )
    assert windows[0].eligible and windows[0].features == BASE


def test_primary_requires_three_adjacent_one_minute_windows_and_duplicate_is_idempotent():
    scorer = QualifiedShadowScorer()
    profile = _profile()
    results = [scorer.score(_window(index, hp2_shift=5), profile) for index in range(3)]
    assert [r.primary_run_windows for r in results] == [1, 2, 3]
    assert [r.primary_persistent_flag for r in results] == [False, False, True]
    assert scorer.score(_window(2, hp2_shift=5), profile) == results[-1]
    assert scorer.score(_window(2, hp2_shift=6), profile).reason == "WINDOW_REVISION_REQUIRES_REPLAY"


def test_gap_state_change_and_profile_change_reset_temporal_and_primary():
    scorer = QualifiedShadowScorer()
    profile = _profile()
    scorer.score(_window(0, hp2_shift=5), profile)
    second = scorer.score(_window(1, hp2_shift=5), profile)
    assert second.primary_run_windows == 2
    gap = scorer.score(_window(3, hp2_shift=5), profile)
    assert gap.primary_run_windows == 1
    invalid = replace(_window(4), features=None, data_quality_status="STATE_NOT_ELIGIBLE", reason="MANUAL")
    assert scorer.score(invalid, profile).status == "NOT_SCORED"
    after_invalid = scorer.score(_window(5, hp2_shift=5), profile)
    assert after_invalid.primary_run_windows == 1
    changed = scorer.score(_window(6, hp2_shift=5), replace(profile, profile_id=43))
    assert changed.primary_run_windows == 1
    assert changed.cusum_positive["hp2"] == pytest.approx(4.5)


def test_signed_cusum_and_ewma_detect_gradual_drift_without_primary_flag():
    parameters = TemporalParameters(ewma_limits={feature: 0.2 for feature in FEATURES},
                                    cusum_limits={feature: 0.5 for feature in FEATURES})
    scorer = QualifiedShadowScorer(parameters)
    profile = _profile(threshold=10)
    down = [scorer.score(_window(index, hp2_shift=-index * 0.5), profile) for index in range(6)]
    assert all(r.primary_raw_flag is False for r in down)
    assert down[-1].cusum_negative["hp2"] > 0.5
    assert down[-1].cusum_positive["hp2"] == 0.0
    assert down[-1].ewma["hp2"] < 0
    assert down[-1].cusum_flags["hp2"] is True
    assert down[-1].temporal_mode == "SHADOW"
    up_scorer = QualifiedShadowScorer(parameters)
    up = [up_scorer.score(_window(index, hp2_shift=index * 0.5), profile) for index in range(6)]
    assert up[-1].cusum_positive["hp2"] > 0.5
    assert up[-1].cusum_negative["hp2"] == 0.0


def test_unfitted_temporal_limits_emit_values_but_no_flags():
    scorer = QualifiedShadowScorer()
    result = scorer.score(_window(hp2_shift=2), _profile())
    assert result.status == "SCORED"
    assert result.ewma_flags is None and result.cusum_flags is None
    assert result.ewma["hp2"] > 0


def test_temporal_flags_require_warmup_again_after_gap():
    parameters = TemporalParameters(
        ewma_limits={feature: 0.01 for feature in FEATURES},
        cusum_limits={feature: 0.01 for feature in FEATURES},
    )
    scorer = QualifiedShadowScorer(parameters)
    first = scorer.score(_window(0, hp2_shift=2), _profile())
    assert not first.temporal_ready and first.ewma_flags is None
    scorer.score(_window(1, hp2_shift=2), _profile())
    third = scorer.score(_window(2, hp2_shift=2), _profile())
    assert third.temporal_ready and third.ewma_flags["hp2"]
    after_gap = scorer.score(_window(4, hp2_shift=2), _profile())
    assert not after_gap.temporal_ready and after_gap.ewma_flags is None


def test_cross_machine_state_is_isolated_and_mismatched_profile_abstains():
    scorer = QualifiedShadowScorer()
    scorer.score(_window(hp2_shift=5), _profile())
    other = scorer.score(_window(machine="MX057", hp2_shift=5), _profile(machine="MX057"))
    assert other.primary_run_windows == 1
    assert scorer.score(_window(1, hp2_shift=5), _profile(machine="MX057")).reason == "PROFILE_OR_FEATURE_MISMATCH"


def test_out_of_order_cannot_corrupt_state_and_threshold_must_be_positive():
    scorer = QualifiedShadowScorer()
    profile = _profile()
    scorer.score(_window(1, hp2_shift=5), profile)
    assert scorer.score(_window(0, hp2_shift=5), profile).reason == "OUT_OF_ORDER_WINDOW"
    assert scorer.score(_window(2, hp2_shift=5), profile).primary_run_windows == 2
    assert scorer.score(_window(3), _profile(threshold=0)).reason == "INVALID_PROFILE_OR_FEATURE"
    malformed = replace(_window(4), sample_count=3, coverage=.01)
    assert scorer.score(malformed, profile).reason == "INVALID_PROFILE_OR_FEATURE"


def test_candidate_uses_past_only_fit_and_future_shadow_can_block():
    windows = [_window(index, hp2_shift=math.sin(index * 0.37) * 0.35)
               for index in range(10 * 1440)]
    split = START + timedelta(days=7)
    reference = fit_one_minute_candidate(windows, machine_number="MX080", module=6,
                                          calibration_start=START, shadow_start=split,
                                          shadow_end=START + timedelta(days=10))
    changed = [replace(window, features={**window.features,
                                         "hp2": window.features["hp2"] + 30,
                                         "dp2": window.features["dp2"] + 30})
               if window.window_start >= split else window for window in windows]
    shifted = fit_one_minute_candidate(changed, machine_number="MX080", module=6,
                                        calibration_start=START, shadow_start=split,
                                        shadow_end=START + timedelta(days=10))
    assert reference["algorithm_version"] == shifted["algorithm_version"]
    assert reference["medians"] == shifted["medians"]
    assert reference["threshold"] == shifted["threshold"]
    assert shifted["status"] == "REVIEW_REQUIRED"
    assert "SHADOW_FLAG_RATE_EXCEEDED" in shifted["reason_codes"]
    assert shifted["auto_activation_allowed"] is False
    outside = fit_one_minute_candidate(
        windows + [_window(10 * 1440, hp2_shift=100)], machine_number="MX080", module=6,
        calibration_start=START, shadow_start=split, shadow_end=START + timedelta(days=10),
    )
    assert outside["threshold"] == reference["threshold"]
    assert outside["shadow_flag_pct"] == reference["shadow_flag_pct"]
    with pytest.raises(ValueError, match="duplicate"):
        fit_one_minute_candidate(windows + [windows[0]], machine_number="MX080", module=6,
                                  calibration_start=START, shadow_start=split,
                                  shadow_end=START + timedelta(days=10))


def test_one_minute_auto_calibration_builds_candidate_shadow_without_active_profile():
    windows = []
    for day in range(10):
        for minute in range(20):
            index = day * 1440 + minute
            windows.append(_window(index, hp2_shift=math.sin(minute * .4) * .3))
    windows.append(_window(10 * 1440 - 1, hp2_shift=.1))
    settings = Settings(
        source_timezone="Asia/Bangkok", source_pressure_unit="psig",
        profile_state_contract_version="cold-v1", profile_controller_codebook_version="controller-v1",
        profile_service_epoch_version="epoch-reviewed-v1", profile_min_calibration_windows=50,
        profile_min_shadow_windows=50, profile_max_shadow_flag_pct=100,
    )
    candidate = registry_candidate_from_windows(
        windows, settings=settings, machine_number="MX080", module=6,
        calibration_start=START, shadow_start=START + timedelta(days=7),
        shadow_end=START + timedelta(days=10),
    )
    assert candidate["status"] == "REVIEW_REQUIRED"
    assert "SHADOW_SOURCE_COVERAGE_LT_95" in candidate["reasons"]
    assert candidate["feature_version"] == WINDOW_VERSION
    assert candidate["threshold"]["method"] == "qualified_1m_retained_calibration_q995"
    assert candidate["statistics"]["exact_baseline"]["hp2"]["scale"] > 0
    assert candidate["validation"]["eligible_shadow_windows"] == 61
    assert len(candidate["shadow"]) == 3 * 1440
    assert (candidate["shadow"]["data_quality_status"] == "NO_SOURCE_ROWS").sum() == 3 * 1440 - 61
    assert candidate["status"] != "ACTIVE_FROZEN"
    replay = _replay_candidate(windows, candidate, START + timedelta(days=7))
    assert replay["status"] == "PARITY_PASS"
    assert replay["scored_windows"] == replay["expected_scored_windows"] == 61
    assert replay["mismatched_windows"] == 0
    assert replay["restart_checkpoint_mismatches"] == 0
    changed_shadow = candidate["shadow"].copy()
    passing_index = changed_shadow.index[changed_shadow["data_quality_status"] == "PASS"][0]
    changed_shadow.loc[passing_index, "raw_flag"] = not bool(changed_shadow.loc[passing_index, "raw_flag"])
    corrupted = {**candidate, "shadow": changed_shadow}
    assert _replay_candidate(windows, corrupted, START + timedelta(days=7))["status"] == "PARITY_MISMATCH"
    unverified = registry_candidate_from_windows(
        windows, settings=Settings(source_pressure_unit="", profile_min_calibration_windows=50,
                                   profile_min_shadow_windows=50,
                                   profile_max_shadow_flag_pct=100),
        machine_number="MX080", module=6,
        calibration_start=START, shadow_start=START + timedelta(days=7),
        shadow_end=START + timedelta(days=10),
    )
    assert unverified["status"] == "REVIEW_REQUIRED"
    assert "SOURCE_PRESSURE_UNIT_UNVERIFIED" in unverified["reasons"]
    with pytest.raises(ValueError, match="requires quarantine"):
        registry_candidate_from_windows(
            windows, settings=Settings(profile_quarantine_z=9), machine_number="MX080", module=6,
            calibration_start=START, shadow_start=START + timedelta(days=7),
            shadow_end=START + timedelta(days=10),
        )


def test_one_minute_candidate_registry_writes_only_versioned_candidate_and_shadow(monkeypatch):
    from apps.api.app import calibration

    windows = [_window(day * 1440 + minute, hp2_shift=math.sin(minute * .4) * .3)
               for day in range(10) for minute in range(20)]
    windows.append(_window(10 * 1440 - 1, hp2_shift=.1))
    settings = Settings(source_timezone="Asia/Bangkok", source_pressure_unit="",
                        profile_min_calibration_windows=50,
                        profile_min_shadow_windows=50, profile_max_shadow_flag_pct=100)
    candidate = registry_candidate_from_windows(
        windows, settings=settings, machine_number="MX080", module=6,
        calibration_start=START, shadow_start=START + timedelta(days=7),
        shadow_end=START + timedelta(days=10),
    )
    calls = []

    class FakeConnection:
        def execute(self, query, parameters):
            calls.append((str(query), parameters))
            return SimpleNamespace(lastrowid=501)

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(calibration, "connection", fake_connection)
    result = calibration.persist_batch(
        settings, START, START + timedelta(days=7),
        START + timedelta(days=7), START + timedelta(days=10), [candidate],
    )
    assert result["profiles"] == 1
    assert result["profile_version"].startswith("autocalibration-1m-v1-")
    assert calls[0][1]["feature_version"] == WINDOW_VERSION
    assert calls[0][1]["algorithm_version"] == candidate["algorithm_version"]
    assert calls[1][1]["profile_status"] == "REVIEW_REQUIRED"
    assert calls[1][1]["shadow_windows"] == 61
    assert calls[2][1][0]["data_quality_status"] == "PASS"
    assert all("ACTIVE_FROZEN" not in sql for sql, _ in calls)


def test_legacy_mutating_inference_is_blocked_before_database_access(monkeypatch):
    from apps.api.app import inference
    monkeypatch.setattr(inference, "get_settings", lambda: SimpleNamespace(qualified_1m_preview_enabled=False))
    monkeypatch.setattr(inference, "connection", lambda: pytest.fail("legacy inference reached the database"))
    result = inference.run_inference_and_sync(target_machines=["MX080"])
    assert result["status"] == "BLOCKED_LEGACY_RAW_ROW_SCORER"
    assert result["scored_windows"] == 0 and result["persistent_alerts"] == 0


def test_opt_in_inference_is_read_only_preview_without_alert_write(monkeypatch):
    from apps.api.app import inference, qualified_shadow_preview
    monkeypatch.setattr(inference, "get_settings", lambda: SimpleNamespace(
        qualified_1m_preview_enabled=True, source_timezone="Asia/Bangkok"))
    monkeypatch.setattr(inference, "connection", lambda: pytest.fail("analytics write connection reached"))
    monkeypatch.setattr(qualified_shadow_preview, "run_read_only_preview", lambda *args, **kwargs: {
        "scored_module_windows": 2, "primary_raw_flags": 1,
    })
    result = inference.run_inference_and_sync(target_machines=["MX080"], sync_to_pm=True)
    assert result["status"] == "READ_ONLY_QUALIFIED_1M_PREVIEW"
    assert result["scored_windows"] == 2 and result["raw_flags"] == 1
    assert result["persistent_alerts"] == 0 and result["synced_diagnostics_to_pm"] == 0


def test_checkpoint_restart_matches_one_shot_and_rejects_version_change():
    profile = _profile()
    parameters = TemporalParameters()
    one_shot = QualifiedShadowScorer(parameters)
    expected = [one_shot.score(_window(index, hp2_shift=5), profile) for index in range(4)]
    first = QualifiedShadowScorer(parameters)
    first.score(_window(0, hp2_shift=5), profile)
    first.score(_window(1, hp2_shift=5), profile)
    durable = json.loads(json.dumps(first.checkpoint()))
    resumed = QualifiedShadowScorer.from_checkpoint(durable, parameters)
    assert resumed.score(_window(1, hp2_shift=5), profile) == expected[1]
    assert resumed.score(_window(2, hp2_shift=5), profile) == expected[2]
    assert resumed.score(_window(3, hp2_shift=5), profile) == expected[3]
    with pytest.raises(ValueError):
        QualifiedShadowScorer.from_checkpoint(durable, TemporalParameters(parameter_version="new-params"))


def test_temporal_limit_fit_uses_separate_past_only_block_and_warmup():
    profile = replace(_profile(), profile_fit_end=START)
    calibration_start = START + timedelta(days=1)
    calibration_end = START + timedelta(days=4)
    windows = [_window(day * 1440 + index, hp2_shift=math.sin(index * 0.3) * 1.5)
               for day in range(1, 4) for index in range(70)]
    fit = fit_shadow_temporal_limits(
        windows, profile=profile, calibration_start=calibration_start,
        calibration_end=calibration_end, untouched_test_start=calibration_end,
    )
    future = [_window(4 * 1440 + index, hp2_shift=30) for index in range(70)]
    refit = fit_shadow_temporal_limits(
        windows + future, profile=profile, calibration_start=calibration_start,
        calibration_end=calibration_end, untouched_test_start=calibration_end,
    )
    assert fit.status == "REVIEW_REQUIRED" and fit.qualified_windows == 210
    assert fit.ewma_family_limit > 0 and fit.cusum_family_limit > 0
    assert fit.parameter_version == refit.parameter_version
    assert fit.ewma_family_limit == refit.ewma_family_limit
    assert fit.cusum_family_limit == refit.cusum_family_limit
    assert fit.auto_activation_allowed is False
    contaminated = list(windows)
    contaminated[40] = _window(1440 + 40, hp2_shift=30)
    screened = fit_shadow_temporal_limits(
        contaminated, profile=profile, calibration_start=calibration_start,
        calibration_end=calibration_end, untouched_test_start=calibration_end,
    )
    assert screened.primary_excluded_windows == 1
    assert screened.ewma_family_limit < 10
    with pytest.raises(ValueError):
        fit_shadow_temporal_limits(windows, profile=replace(profile, profile_fit_end=calibration_end),
                                   calibration_start=calibration_start, calibration_end=calibration_end,
                                   untouched_test_start=calibration_end)
