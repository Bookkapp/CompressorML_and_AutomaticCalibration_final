import json
import math
import shutil
from pathlib import Path

import pandas as pd
import pytest

from apps.api.app.model_bundle import ModelBundleError, load_shadow_bundle
from apps.api.app.inference import RUNTIME_SCORER_VERSION


ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180"
MANIFEST = RELEASE / "shadow_release_manifest.json"
REGISTRY = ROOT / "notebooks/outputs/ht9046mx_phase7_benchmark_v2_hp180/shadow_model_registry.json"


def test_historical_arx_artifact_loads_but_cannot_be_live() -> None:
    bundle = load_shadow_bundle(MANIFEST, REGISTRY)
    assert bundle.model_key == "ARX-Ridge__seed_13"
    assert len(bundle.feature_names) == 33
    assert bundle.activation_state == "SHADOW_ONLY_NOT_AUTHORIZED"
    assert bundle.live_eligible is False
    assert RUNTIME_SCORER_VERSION != bundle.model_key
    probe = pd.DataFrame([[0.0] * len(bundle.feature_names)], columns=bundle.feature_names)
    assert math.isfinite(float(bundle.model.score(probe)[0]))


@pytest.fixture
def copied_release(tmp_path: Path) -> tuple[Path, Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    model_path = tmp_path / manifest["model_path"]
    model_path.parent.mkdir(parents=True)
    shutil.copyfile(RELEASE / manifest["model_path"], model_path)
    manifest_path = tmp_path / "manifest.json"
    registry_path = tmp_path / "registry.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return manifest_path, registry_path


def test_checksum_mismatch_fails_closed(copied_release: tuple[Path, Path]) -> None:
    manifest_path, registry_path = copied_release
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="SHA-256 mismatch"):
        load_shadow_bundle(manifest_path, registry_path)


def test_feature_contract_mismatch_fails_closed(copied_release: tuple[Path, Path]) -> None:
    manifest_path, registry_path = copied_release
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["features"][:2] = registry["features"][1::-1]
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="feature order"):
        load_shadow_bundle(manifest_path, registry_path)


def test_activation_state_cannot_be_promoted_by_manifest(copied_release: tuple[Path, Path]) -> None:
    manifest_path, registry_path = copied_release
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["activation_state"] = "ACTIVE_FROZEN"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="shadow-only"):
        load_shadow_bundle(manifest_path, registry_path)
