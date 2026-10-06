"""Read-only validation and loading of a versioned Phase 7 shadow model.

Loading an artifact is deliberately separate from authorizing live inference.
Only trusted, project-controlled manifests may be passed to joblib.load because
the joblib/pickle format can execute code during deserialization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelBundleError(ValueError):
    """The artifact does not satisfy the recorded shadow feature contract."""


@dataclass(frozen=True)
class ShadowModelBundle:
    model: Any
    model_key: str
    model_sha256: str
    feature_names: tuple[str, ...]
    feature_version: str
    profile_version: str
    threshold_version: str
    threshold: float
    persistence_windows: int
    cadence_minutes: int
    activation_state: str

    @property
    def live_eligible(self) -> bool:
        # This historical artifact predates the current Cold-only/dp1/dp2
        # contract. A new release needs separate validation and approval.
        return False


@dataclass(frozen=True)
class ColdCandidateBundle:
    model: Any
    profiles: Any
    release_version: str
    model_sha256: str
    profiles_sha256: str
    dynamic_threshold: float
    self_threshold: float
    activation_state: str

    @property
    def live_eligible(self) -> bool:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelBundleError(f"Cannot read model metadata: {path}") from exc
    if not isinstance(value, dict):
        raise ModelBundleError(f"Model metadata must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_shadow_bundle(manifest_path: Path, registry_path: Path) -> ShadowModelBundle:
    """Verify manifest, registry, checksum and feature order, then load only.

    The returned object has no API for activation or MySQL writes. The
    historical Phase 7 bundle is always shadow-only, even when it loads.
    """
    manifest_path = Path(manifest_path).resolve(strict=True)
    registry_path = Path(registry_path).resolve(strict=True)
    manifest = _read_json(manifest_path)
    registry = _read_json(registry_path)

    for key in ("registry_version", "feature_version", "profile_version", "threshold_version"):
        if manifest.get(key) != registry.get(key) or not manifest.get(key):
            raise ModelBundleError(f"Manifest/registry {key} mismatch")
    if manifest.get("activation_state") != "SHADOW_ONLY_NOT_AUTHORIZED":
        raise ModelBundleError("This loader accepts only the historical shadow-only release")
    if manifest.get("auto_activation_allowed") is not False:
        raise ModelBundleError("Auto-activation must be explicitly disabled")
    if registry.get("activation_state") != "NOT_AUTHORIZED" or registry.get("auto_activation_allowed") is not False:
        raise ModelBundleError("Registry does not authorize shadow-only loading")
    model_key = manifest.get("model_key")
    if model_key != "ARX-Ridge__seed_13" or model_key not in registry.get("model_files", {}):
        raise ModelBundleError("Unexpected or unregistered model key")
    relative_path = manifest.get("model_path")
    if not isinstance(relative_path, str) or not relative_path:
        raise ModelBundleError("Missing model path")
    root = manifest_path.parent
    model_path = (root / relative_path).resolve(strict=True)
    if not model_path.is_relative_to(root) or model_path.suffix != ".joblib":
        raise ModelBundleError("Model path escapes the release directory")
    expected_hash = manifest.get("model_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ModelBundleError("Missing model SHA-256")
    if _sha256(model_path) != expected_hash:
        raise ModelBundleError("Model SHA-256 mismatch")

    features = registry.get("features")
    if not isinstance(features, list) or not features or not all(isinstance(x, str) for x in features):
        raise ModelBundleError("Missing ordered feature contract")
    if len(features) != len(set(features)):
        raise ModelBundleError("Duplicate feature names")
    threshold = float(manifest.get("threshold", float("nan")))
    if not math.isfinite(threshold) or threshold <= 0:
        raise ModelBundleError("Invalid threshold")
    if manifest.get("cadence_minutes") != 5 or manifest.get("persistence_windows") != 3:
        raise ModelBundleError("Unexpected cadence or persistence contract")

    # Import the original, importable class before deserializing. A passing
    # checksum only proves consistency with the trusted local manifest.
    from notebooks.support.phase7_benchmark import ScoreModel  # noqa: F401
    import joblib

    model = joblib.load(model_path)
    if not isinstance(model, ScoreModel) or model.family != "ARX-Ridge":
        raise ModelBundleError("Artifact is not the expected ARX-Ridge ScoreModel")
    if list(model.feature_names) != features:
        raise ModelBundleError("Artifact feature order differs from registry")
    if model.imputer is None or model.scaler is None or model.estimator is None:
        raise ModelBundleError("Model preprocessing/estimator is incomplete")
    return ShadowModelBundle(
        model=model,
        model_key=model_key,
        model_sha256=expected_hash,
        feature_names=tuple(features),
        feature_version=manifest["feature_version"],
        profile_version=manifest["profile_version"],
        threshold_version=manifest["threshold_version"],
        threshold=threshold,
        persistence_windows=3,
        cadence_minutes=5,
        activation_state=manifest["activation_state"],
    )


def load_cold_candidate(manifest_path: Path) -> ColdCandidateBundle:
    """Load the new Cold candidate with immutable manifest/profile/model checks.

    This does not qualify it for live use. Score generation additionally needs
    the exact causal five-minute feature adapter and approved local profiles.
    """
    from apps.api.app.cold_arx import (
        FEATURE_VERSION, PREDICTORS, PROFILE_VERSION, QUANTIZED_FEATURE_VERSION,
        QUANTIZED_PROFILE_VERSION, TARGETS, ColdArxRidge,
    )
    import joblib
    import pandas as pd

    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = _read_json(manifest_path)
    contracts = {
        "phase07-cold-relationship-candidate-v1": (FEATURE_VERSION, PROFILE_VERSION, "cold-past-calibration-q995-v1"),
        "phase07-cold-relationship-candidate-v2-valve-quantized": (
            QUANTIZED_FEATURE_VERSION, QUANTIZED_PROFILE_VERSION,
            "cold-past-calibration-q995-valve-quantized-v2",
        ),
    }
    release = manifest.get("release_version")
    if release not in contracts:
        raise ModelBundleError("Unexpected Cold release version")
    if manifest.get("activation_state") != "SHADOW_ONLY_NOT_AUTHORIZED" or manifest.get("auto_activation_allowed") is not False:
        raise ModelBundleError("Cold candidate must remain shadow-only")
    if tuple(manifest.get(name) for name in ("feature_version", "profile_version", "threshold_version")) != contracts[release]:
        raise ModelBundleError("Cold feature/profile version mismatch")
    if release.endswith("valve-quantized"):
        if manifest.get("valve_scale_policy") != "integer-command-floor-one-source-unit-v2" or manifest.get("valve_quantization_unit") != 1.0:
            raise ModelBundleError("Cold Valve quantization policy mismatch")
    if manifest.get("predictors") != list(PREDICTORS) or manifest.get("targets") != list(TARGETS):
        raise ModelBundleError("Cold predictor/target order mismatch")
    if manifest.get("cadence_minutes") != 5 or manifest.get("persistence_windows") != 3:
        raise ModelBundleError("Cold cadence/persistence mismatch")
    if manifest.get("source_timezone") != "NOT_ENCODED_UNVERIFIED":
        raise ModelBundleError("Historical source timezone status was changed")
    if manifest.get("profile_source") != "OFFLINE_TRAIN_ONLY_NOT_MYSQL_ACTIVE_PROFILE":
        raise ModelBundleError("Cold candidate profile source must remain offline train-only")
    for name in ("dynamic_threshold", "self_threshold"):
        value = float(manifest.get(name, float("nan")))
        if not math.isfinite(value) or value <= 0:
            raise ModelBundleError(f"Invalid {name}")
    root = manifest_path.parent
    checked_paths = []
    for path_field, hash_field, suffix in (
        ("model_path", "model_sha256", ".joblib"),
        ("profiles_path", "profiles_sha256", ".csv"),
    ):
        relative = manifest.get(path_field)
        expected = manifest.get(hash_field)
        if not isinstance(relative, str) or not isinstance(expected, str) or len(expected) != 64:
            raise ModelBundleError(f"Missing {path_field}/{hash_field}")
        actual = (root / relative).resolve(strict=True)
        if not actual.is_relative_to(root) or actual.suffix != suffix:
            raise ModelBundleError(f"{path_field} escapes the candidate directory")
        if _sha256(actual) != expected:
            raise ModelBundleError(f"{hash_field} mismatch")
        checked_paths.append(actual)
    model = joblib.load(checked_paths[0])
    if not isinstance(model, ColdArxRidge) or model.scaler is None or model.estimator is None:
        raise ModelBundleError("Cold artifact class or fit state mismatch")
    if model.predictor_names != PREDICTORS or model.target_names != TARGETS or model.alpha != manifest.get("alpha"):
        raise ModelBundleError("Cold artifact parameter/feature contract mismatch")
    profiles = pd.read_csv(checked_paths[1], dtype={"machine_number": str, "sv": str, "state": str})
    keys = ["machine_number", "module", "sv", "state"]
    if not set(keys + ["profile_days", "profile_rows"]).issubset(profiles.columns):
        raise ModelBundleError("Cold profile keys/coverage missing")
    if profiles.duplicated(keys).any() or profiles.profile_days.lt(7).any() or profiles.profile_rows.lt(200).any():
        raise ModelBundleError("Cold profile uniqueness/coverage failed")
    if not profiles.state.eq("RUN_ON_SV_OFF").all() or not profiles.sv.eq("Off").all():
        raise ModelBundleError("Cold profile state/SV mismatch")
    if release.endswith("valve-quantized") and ("valve__scale" not in profiles or profiles["valve__scale"].lt(1.0).any()):
        raise ModelBundleError("Quantized-Valve profile scale is below one source unit")
    return ColdCandidateBundle(
        model=model,
        profiles=profiles,
        release_version=manifest["release_version"],
        model_sha256=manifest["model_sha256"],
        profiles_sha256=manifest["profiles_sha256"],
        dynamic_threshold=float(manifest["dynamic_threshold"]),
        self_threshold=float(manifest["self_threshold"]),
        activation_state=manifest["activation_state"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load a shadow-only ARX-Ridge bundle")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--cold-candidate-manifest", type=Path)
    args = parser.parse_args()
    if args.cold_candidate_manifest:
        if args.manifest or args.registry:
            parser.error("Use either historical --manifest/--registry or --cold-candidate-manifest")
        cold = load_cold_candidate(args.cold_candidate_manifest)
        print(json.dumps({
            "status": "LOADED_COLD_CANDIDATE_REVIEW_REQUIRED",
            "release_version": cold.release_version,
            "model_sha256": cold.model_sha256,
            "profiles_sha256": cold.profiles_sha256,
            "profile_count": len(cold.profiles),
            "activation_state": cold.activation_state,
            "live_eligible": cold.live_eligible,
        }, ensure_ascii=False))
        return
    if not args.manifest or not args.registry:
        parser.error("Historical loading requires --manifest and --registry")
    bundle = load_shadow_bundle(args.manifest, args.registry)
    print(json.dumps({
        "status": "LOADED_SHADOW_ONLY",
        "model_key": bundle.model_key,
        "model_sha256": bundle.model_sha256,
        "feature_count": len(bundle.feature_names),
        "feature_version": bundle.feature_version,
        "profile_version": bundle.profile_version,
        "threshold_version": bundle.threshold_version,
        "activation_state": bundle.activation_state,
        "live_eligible": bundle.live_eligible,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
