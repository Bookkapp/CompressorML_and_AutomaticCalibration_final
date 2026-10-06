"""Portable frozen Fleet inference. No SQL, fitting, adaptation or alert writes.

Local absolute levels remain fixed. Fleet shares compatible correlation shape
only. These robust empirical moments are not an exact Bayesian posterior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
import json
import math

import numpy as np
from scipy.linalg import solve_triangular

from .fleet_assistance import FEATURES, VERSION, pool

SCHEMA = "ht9046mx-fleet-stable-bundle-v1"
SEMANTICS = "fleet-stable-shadow-inference-v1"
CONTEXTS = ("SV_OFF", "SV_ON")


def semantic_quality(values):
    """Suspected acquired defaults, not certified transducer range limits.

    Minute averages can hide a short invalid burst. Producers must also supply
    semantic_bad from the observed-second adapter; known audited intervals are
    marked separately by the historical adapter.
    """
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != 6:
        raise ValueError("six physical coordinates required")
    finite = np.isfinite(x).all(axis=1)
    # -200 observed on both temperature channels during the MX080 acquisition
    # incident. Conservatively quarantine either exact temperature default.
    temperature_default = np.any(np.isclose(x[:, 4:], -200., atol=1e-6, rtol=0), axis=1)
    simultaneous_rail = np.all(np.isclose(x[:, :4], 580.2, atol=1e-6, rtol=0), axis=1)
    return finite & ~temperature_default & ~simultaneous_rail


def assist_local(local, donor_summaries, *, research=False):
    """Frozen, past-only extension point for a later new-machine build.

    A target without sufficient local similarity evidence remains local-only;
    no Fleet-only absolute profile is invented for zero-data machines.
    """
    return pool(local, donor_summaries, research=research, parameter="relationship")


def validate_model(model):
    if model.get("version") != VERSION or tuple(model.get("features", [])) != FEATURES:
        raise ValueError("incompatible Fleet feature/model version")
    if model.get("context") not in CONTEXTS or not 1 <= model.get("module", 0) <= 8:
        raise ValueError("unsupported module/control context")
    local = model["local_absolute_reference"]
    for key in ("center", "scale"):
        x = np.asarray(model[key], float)
        if x.shape != (6,) or not np.isfinite(x).all():
            raise ValueError("invalid local scaler")
        if not np.array_equal(x, np.asarray(local[key], float)):
            raise ValueError("Fleet must preserve frozen Local levels and scales")
    if np.any(np.asarray(model["scale"]) <= 0):
        raise ValueError("positive scales required")
    covariance = np.asarray(model["covariance"], float)
    if covariance.shape != (6, 6) or not np.isfinite(covariance).all() or not np.allclose(covariance, covariance.T):
        raise ValueError("invalid covariance")
    np.linalg.cholesky(covariance)
    for key in ("threshold", "absolute_threshold"):
        if not math.isfinite(model[key]) or model[key] <= 0:
            raise ValueError("invalid frozen threshold")
    reference_end = datetime.fromisoformat(model["reference_end"])
    start, end = map(datetime.fromisoformat, model["threshold_period"])
    if start < reference_end or end <= start:
        raise ValueError("overlapping Reference and threshold calibration")
    donors = model.get("donor_machines", [])
    if model["machine"] in donors or len(donors) != len(set(donors)):
        raise ValueError("target/duplicate donor leakage")
    if model.get("activation_eligible") is not False:
        raise ValueError("v1 package is Shadow only")


@dataclass(frozen=True)
class CompiledModel:
    center: np.ndarray
    scale: np.ndarray
    cholesky: np.ndarray
    absolute_threshold: float
    relationship_threshold: float
    fleet_weight: float
    stability_bounds: np.ndarray


class FrozenFleet:
    """Per-version read-only matrices; requests never mutate shared state."""

    def __init__(self, manifest, models, priors, curation=None):
        self.bundle_id = manifest["bundle_id"]
        self._manifest_json = json.dumps(manifest, allow_nan=False)
        self._models_json = json.dumps(models, allow_nan=False)
        self._priors_json = json.dumps(priors, allow_nan=False)
        if priors.get('transition_catalog'):
            from .fleet_transitions import validate_catalog
            validate_catalog(priors['transition_catalog'])
        intervals=[]
        for r in (curation or {}).get('semantic_quarantine_intervals',[]):
            start,end=map(datetime.fromisoformat,(r['start'],r['end']))
            if start.tzinfo or end.tzinfo or end<=start or not 1<=r['module']<=8:
                raise ValueError('invalid semantic quarantine interval')
            intervals.append((r['machine'],r['module'],start,end))
        self._quality_intervals=tuple(intervals)
        compiled = {}
        for model in models:
            validate_model(model)
            key = (model["machine"], model["module"], model["context"])
            if key in compiled:
                raise ValueError("duplicate target profile")
            matrices = [np.asarray(model["center"], float), np.asarray(model["scale"], float),
                        np.linalg.cholesky(np.asarray(model["covariance"], float))]
            bounds=np.asarray(model.get('stability_bounds',np.asarray(model['scale'])*.35),float)
            if bounds.shape!=(6,) or not np.isfinite(bounds).all() or np.any(bounds<=0):
                raise ValueError('positive frozen train-only phase bounds required')
            bounds.setflags(write=False)
            for matrix in matrices:
                matrix.setflags(write=False)
            compiled[key] = CompiledModel(*matrices, model["absolute_threshold"], model["threshold"], model["fleet_weight"],bounds)
        self._compiled = MappingProxyType(compiled)

    def models(self):
        return json.loads(self._models_json)

    def priors(self):
        return json.loads(self._priors_json)

    def status(self, machine=None, module=None):
        all_models=self.models()
        models = [m for m in all_models if (machine is None or m["machine"] == machine)
                  and (module is None or m["module"] == module)]
        manifest = json.loads(self._manifest_json)
        return {"bundle_id": self.bundle_id, "release_state": "FROZEN_SHADOW_CANDIDATE", "alert_vote": False,
                "schema": SCHEMA, "semantics": SEMANTICS, "source_timezone": "Asia/Bangkok",
                "pressure_unit": "psi", "pressure_basis": "UNVERIFIED", "models_total": len(self._compiled),
                "source_machines": manifest["source_machines"], "blockers": manifest["blockers"],
                "evidence_dates":manifest.get('evidence_dates',['2026-07-01','2026-10-01']),
                "module_coverage":[{"module":i,"states":[{"sv":sv.removeprefix("SV_"),
                    "status":"FROZEN_SHADOW_REFERENCE" if any(m["machine"]==machine and m["module"]==i and m["context"]==sv for m in all_models) else "INSUFFICIENT_REFERENCE"}
                    for sv in CONTEXTS]} for i in range(1,9)] if machine is not None else [],
                "profiles": [{k: m[k] for k in ("machine", "module", "context", "reference_start", "reference_end",
                    "threshold_period", "n", "fleet_weight", "donor_machines", "absolute_threshold", "threshold")}
                    for m in models],
                "method": "Frozen Local levels + selective Fleet correlation shape; bounded robust empirical moments"}

    def evaluate(self, machine, module, rows, *, allow_day_boundary=False):
        """At most one observed module-day. All gaps/context changes reset runs.

        Scores remain visible during delayed physical response. 'Steady' is a
        trailing descriptive phase, not health and not a suppression timer.
        """
        if len(rows) > 1440:
            raise ValueError("one observed module-day maximum")
        n = len(rows)
        if not n:
            return {"bundle_id": self.bundle_id, "machine": machine, "module": module, "points": [], "counts": {}}
        times = [datetime.fromisoformat(r["time"]) for r in rows]
        if any(t.tzinfo for t in times) or any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("strict increasing naive source-local minute timestamps required")
        if any(t.second or t.microsecond for t in times) or (not allow_day_boundary and times[0].date() != times[-1].date()):
            raise ValueError("one completed source-local minute day required")
        x = np.asarray([[r.get(f, np.nan) for f in FEATURES] for r in rows], float)
        numeric_quality = semantic_quality(x)
        valid = numeric_quality & np.asarray([r.get("quality") is True and not r.get("semantic_bad", False) for r in rows])
        quarantined=np.zeros(n,bool)
        for i,at in enumerate(times):
            if any(m==machine and mod==module and start<=at<end for m,mod,start,end in self._quality_intervals):
                valid[i]=False;quarantined[i]=True
        contexts=[]
        for r in rows:
            sv=str(r.get('sv','')).lower()
            try:valve_ok=math.isfinite(float(r.get('valve',float('nan')))) and float(r.get('valve'))>=0
            except (TypeError,ValueError):valve_ok=False
            supported=(r.get('stable_control') is True and str(r.get('compressor','')).lower()=='run'
                       and str(r.get('module_state','')).lower()=='on' and str(r.get('busy','')).lower()=='0'
                       and sv in {'on','off'} and valve_ok)
            derived='SV_ON' if sv=='on' else 'SV_OFF'
            contexts.append(derived if supported and r.get('context')==derived else 'UNSUPPORTED')
        absolute = np.full(n, np.nan); relationship = np.full(n, np.nan)
        flag = np.zeros(n, bool); cp2 = np.zeros(n, bool)
        for context in CONTEXTS:
            model = self._compiled.get((machine, module, context))
            if model is None:
                continue
            idx = np.flatnonzero(valid & np.asarray([c == context for c in contexts]))
            if not len(idx):
                continue
            z = np.abs((x[idx] - model.center) / model.scale)
            a = z.max(axis=1)
            delta = (x[idx] - model.center).T
            distance = np.sum(solve_triangular(model.cholesky, delta, lower=True, check_finite=False)**2, axis=0)
            absolute[idx] = a; relationship[idx] = distance
            cp2[idx] = z[:, 2:4].max(axis=1) > model.absolute_threshold
            flag[idx] = (a > model.absolute_threshold) | (distance > model.relationship_threshold)
        points = []; counts = {}; run = 0
        for i, row in enumerate(rows):
            model = self._compiled.get((machine, module, contexts[i]))
            evaluated = bool(valid[i] and model is not None and contexts[i] in CONTEXTS)
            continuous = i > 0 and times[i]-times[i-1] == timedelta(minutes=1) and contexts[i] == contexts[i-1]
            # A rolling window cannot cross missing/bad/unsupported observations.
            steady = bool(evaluated and i >= 4 and all(valid[i-4:i+1])
                          and len(set(contexts[i-4:i+1])) == 1
                          and times[i]-times[i-4] == timedelta(minutes=4)
                          and np.all(np.ptp(x[i-4:i+1], axis=0)<=model.stability_bounds))
            phase = "STEADY_OBSERVATION" if steady else "RESPONSE_OR_CHANGING"
            if not valid[i]:
                assessment = "DATA_QUALITY"; phase = "DATA_QUALITY"
                reason='ACQUISITION_SUSPECT' if (quarantined[i] or row.get('semantic_bad') or
                        (np.isfinite(x[i]).all() and not numeric_quality[i])) else 'INCOMPLETE_MEASUREMENTS'
            elif not evaluated:
                assessment = "NOT_EVALUATED"; phase = "UNSUPPORTED_CONTEXT"
                reason='CONTROL_CONTEXT_UNSUPPORTED' if contexts[i]=='UNSUPPORTED' else 'NO_LOCAL_PROFILE'
            else:
                assessment = "REVIEW" if flag[i] else "WITHIN_REFERENCE"
                reason='REFERENCE_DEVIATION' if flag[i] else 'WITHIN_REFERENCE'
            # A descriptive response/steady boundary must not erase sustained
            # absolute evidence; missing/invalid/control context still resets.
            run = (run+1 if continuous else 1) if evaluated and flag[i] else 0
            counts[assessment] = counts.get(assessment, 0)+1
            points.append({"time": row["time"], "assessment": assessment, "phase": phase,'reason':reason,
                           "absolute_score": float(absolute[i]) if evaluated else None,
                           "relationship_score": float(relationship[i]) if evaluated else None,
                           "cp2_level_flag": bool(cp2[i]), "raw_flag": bool(evaluated and flag[i]),
                           "persistent_flag": run >= 3, "fleet_weight": model.fleet_weight if evaluated else None})
        return {"bundle_id": self.bundle_id, "machine": machine, "module": module, "points": points, "counts": counts,
                "alert_vote": False, "interpretation": "Shadow evidence; WITHIN_REFERENCE is not confirmed healthy. Response scores are never hidden."}
