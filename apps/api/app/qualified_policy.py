"""Explicit, immutable score semantics; feature transport remains unchanged."""
from .qualified_windows import FEATURES

LEGACY_THRESHOLD_VERSION = "qualified-1m-retained-q995-v1"
LEGACY_CANDIDATE_VERSION = "two-pass-robust-z-qualified-1m-v1"
THRESHOLD_VERSION = "qualified-1m-physical-retained-q995-strict-v2"
CANDIDATE_VERSION = "two-pass-physical-robust-z-control-context-1m-v2"
PHYSICAL_FEATURES = tuple(f for f in FEATURES if f != "valve")


def score_features(version):
    if version == LEGACY_THRESHOLD_VERSION:
        return FEATURES
    if version == THRESHOLD_VERSION:
        return PHYSICAL_FEATURES
    raise ValueError("unsupported qualified score policy")


def crosses(score, threshold, version):
    # Ties at a discrete empirical quantile do not exceed that quantile.
    if version == LEGACY_THRESHOLD_VERSION:
        return score >= threshold
    if version == THRESHOLD_VERSION:
        return score > threshold
    raise ValueError("unsupported qualified threshold policy")


def manifest(version=THRESHOLD_VERSION):
    return {"threshold_version": version, "primary_features": list(score_features(version)),
            "comparison": ">=" if version == LEGACY_THRESHOLD_VERSION else ">",
            "control_features": [] if version == LEGACY_THRESHOLD_VERSION else ["valve"],
            "control_votes": version == LEGACY_THRESHOLD_VERSION,
            "recovery_suppression": False}
