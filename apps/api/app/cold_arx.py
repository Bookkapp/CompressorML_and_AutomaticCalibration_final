"""Importable, portable ARX-Ridge residual model for qualified Cold windows."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


# Targets are present only for residual calculation, never as current-time
# predictors. Lagged target values must be from the same uninterrupted Cold
# segment and exactly 5/10 minutes before the scored row.
PREDICTORS = (
    "rz_hp1", "rz_lp1", "rz_dp1", "rz_valve",
    "lag1_rz_hp2", "lag1_rz_lp2", "lag1_rz_valve",
    "lag1_rz_temphi", "lag1_rz_templo",
    "lag2_rz_hp2", "lag2_rz_lp2",
)
TARGETS = ("rz_hp2", "rz_lp2")
FEATURE_VERSION = "cold-arx-causal-5m-v1"
PROFILE_VERSION = "cold-machine-module-sv-state-train-only-v1"
QUANTIZED_FEATURE_VERSION = "cold-arx-causal-5m-valve-quantized-v2"
QUANTIZED_PROFILE_VERSION = "cold-machine-module-sv-state-valve-quantized-v2"


@dataclass
class ColdArxRidge:
    alpha: float
    predictor_names: tuple[str, ...] = PREDICTORS
    target_names: tuple[str, ...] = TARGETS
    scaler: StandardScaler | None = None
    estimator: Ridge | None = None

    def fit(self, predictors: np.ndarray, targets: np.ndarray) -> "ColdArxRidge":
        predictors = np.asarray(predictors, dtype=float)
        targets = np.asarray(targets, dtype=float)
        if predictors.ndim != 2 or predictors.shape[1] != len(self.predictor_names):
            raise ValueError("Predictor order/width differs from the Cold ARX contract")
        if targets.ndim != 2 or targets.shape != (len(predictors), len(self.target_names)):
            raise ValueError("Target shape differs from the Cold ARX contract")
        if not np.isfinite(predictors).all() or not np.isfinite(targets).all():
            raise ValueError("Cold ARX refuses missing or non-finite training features")
        self.scaler = StandardScaler().fit(predictors)
        self.estimator = Ridge(alpha=self.alpha).fit(self.scaler.transform(predictors), targets)
        return self

    def score(self, predictors: np.ndarray, targets: np.ndarray) -> np.ndarray:
        if self.scaler is None or self.estimator is None:
            raise ValueError("Cold ARX model is not fitted")
        predictors = np.asarray(predictors, dtype=float)
        targets = np.asarray(targets, dtype=float)
        if predictors.ndim != 2 or predictors.shape[1] != len(self.predictor_names):
            raise ValueError("Predictor order/width differs from the Cold ARX contract")
        if targets.ndim != 2 or targets.shape != (len(predictors), len(self.target_names)):
            raise ValueError("Target shape differs from the Cold ARX contract")
        if not np.isfinite(predictors).all() or not np.isfinite(targets).all():
            raise ValueError("Cold ARX refuses missing or non-finite scoring features")
        predicted = self.estimator.predict(self.scaler.transform(predictors))
        return np.max(np.abs(targets - predicted), axis=1)
