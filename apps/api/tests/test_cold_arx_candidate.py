import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.api.app.cold_arx import PREDICTORS, TARGETS, ColdArxRidge
from apps.api.app.calibration import SCALE_FLOORS
from apps.api.app.model_bundle import ModelBundleError, load_cold_candidate
from notebooks.support.phase7_benchmark import fit_profiles
from notebooks.support.phase7_cold_candidate import PROFILE_FEATURES, PROFILE_KEYS, _fit_local_profiles, _relative_with_lags


ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v1"
MANIFEST = CANDIDATE / "candidate_manifest.json"
QUANTIZED = ROOT / "notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized"
QUANTIZED_MANIFEST = QUANTIZED / "candidate_manifest.json"


def test_predictors_exclude_current_cp2_target_and_algebraic_leaks() -> None:
    assert set(PREDICTORS).isdisjoint(TARGETS)
    assert not any(name in PREDICTORS for name in ("rz_dp2", "rz_hp_stage_gap", "rz_lp_stage_gap", "rz_hp2_response_1m", "rz_lp2_response_1m"))
    x = np.zeros((3, len(PREDICTORS)))
    y = np.array([[0, 0], [1, 2], [2, 3]], dtype=float)
    model = ColdArxRidge(alpha=1.0).fit(x, y)
    assert len(model.score(x, y)) == 3
    with pytest.raises(ValueError, match="non-finite"):
        model.score(np.full_like(x, np.nan), y)


def test_lags_require_exact_cold_five_minute_continuity() -> None:
    times = pd.to_datetime(["2026-08-05 00:00", "2026-08-05 00:05", "2026-08-05 00:10", "2026-08-05 00:20"])
    raw = pd.DataFrame({
        "machine_number": ["017"] * 4,
        "module": [1] * 4,
        "sv": ["Off"] * 4,
        "state": ["RUN_ON_SV_OFF"] * 4,
        "minute": times,
        "date": times.normalize(),
        "segment_id": [1] * 4,
        "hp1": [190.0] * 4,
        "lp1": [20.0] * 4,
        "hp2": [190.0, 191.0, 210.0, 211.0],
        "lp2": [10.0, 11.0, 12.0, 13.0],
        "valve": [10.0, 11.0, 12.0, 13.0],
        "temphi": [70.0] * 4,
        "templo": [20.0] * 4,
    })
    raw["dp1"] = raw.hp1 - raw.lp1
    raw["dp2"] = raw.hp2 - raw.lp2
    profiles = fit_profiles(raw, PROFILE_KEYS, PROFILE_FEATURES)
    relative = _relative_with_lags(raw, profiles)
    assert relative.minute.tolist() == [times[2]]
    assert relative.iloc[0].lag1_rz_hp2 != relative.iloc[0].rz_hp2


def test_new_candidate_loads_for_review_only() -> None:
    bundle = load_cold_candidate(MANIFEST)
    assert bundle.release_version == "phase07-cold-relationship-candidate-v1"
    assert len(bundle.profiles) == 78
    assert bundle.live_eligible is False
    assert bundle.activation_state == "SHADOW_ONLY_NOT_AUTHORIZED"


def test_new_candidate_hash_tamper_fails_closed(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name in (manifest["model_path"], manifest["profiles_path"]):
        shutil.copyfile(CANDIDATE / name, tmp_path / name)
    manifest["profiles_sha256"] = "0" * 64
    manifest_path = tmp_path / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="profiles_sha256 mismatch"):
        load_cold_candidate(manifest_path)


def test_one_count_valve_floor_is_fit_only_from_passed_past_rows() -> None:
    assert SCALE_FLOORS["valve"] == 1.0
    rows = pd.DataFrame({
        "machine_number": ["017"] * 4, "module": [1] * 4,
        "sv": ["Off"] * 4, "state": ["RUN_ON_SV_OFF"] * 4,
        "date": pd.to_datetime(["2026-08-04"] * 4),
        **{name: [10.0] * 4 for name in PROFILE_FEATURES},
    })
    rows["valve"] = [88.0] * 4
    old = _fit_local_profiles(rows, quantized_valve=False)
    new = _fit_local_profiles(rows, quantized_valve=True)
    assert old.loc[0, "valve__scale"] == 0.05
    assert new.loc[0, "valve__scale"] == 1.0
    assert new.loc[0, "valve__median"] == 88.0
    rows.loc[3, "valve"] = 88.5
    with pytest.raises(ValueError, match="integer command"):
        _fit_local_profiles(rows, quantized_valve=True)


def test_quantized_candidate_loads_only_as_review() -> None:
    bundle = load_cold_candidate(QUANTIZED_MANIFEST)
    assert bundle.release_version.endswith("valve-quantized")
    assert len(bundle.profiles) == 87
    assert bundle.profiles["valve__scale"].ge(1.0).all()
    assert bundle.live_eligible is False


def test_quantized_candidate_policy_tamper_fails_closed(tmp_path: Path) -> None:
    manifest = json.loads(QUANTIZED_MANIFEST.read_text(encoding="utf-8"))
    for name in (manifest["model_path"], manifest["profiles_path"]):
        shutil.copyfile(QUANTIZED / name, tmp_path / name)
    manifest["valve_quantization_unit"] = 0.05
    manifest_path = tmp_path / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="Valve quantization policy"):
        load_cold_candidate(manifest_path)


def test_retrospective_matched_comparison_reconciles_rows() -> None:
    result = json.loads((QUANTIZED / "matched_comparison.json").read_text(encoding="utf-8"))
    assert result["status"] == "RETROSPECTIVE_DIAGNOSTIC_ONLY_NOT_RELEASE_SELECTION"
    assert result["matched_rows"] == result["v1_scored_rows"] == 110283
    assert result["v2_scored_rows"] == result["matched_rows"] + result["v2_only_rows"]
    for lane in result["matched_rates"].values():
        assert sum(lane[key] for key in ("v1_only_rows", "v2_only_rows", "both_rows", "neither_rows")) == result["matched_rows"]
        assert lane["v1_three_window_episodes"] >= 0
        assert lane["v2_three_window_episodes"] >= 0
