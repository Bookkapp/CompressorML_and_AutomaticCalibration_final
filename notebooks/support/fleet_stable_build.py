"""Bounded, source-verified build of portable Fleet Stable Shadow Candidates.

No SQL writes, no source import, no automatic healthy labels. The MX080/M6
owner-proposed intervals remain visibly unreviewed until engineering review.
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import gc
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from apps.api.app.fleet_assistance import FEATURES, fit_local, robust_location, calibrate, self_scores
from apps.api.app.fleet_stable import assist_local, semantic_quality
from apps.api.app.fleet_bundle import write_package, export_zip, digest
from notebooks.support.fleet_reference_study import OUT as SOURCE, MACHINES, write_json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"notebooks/outputs/fleet_stable_v1_20261006"
BASE_FIT = ("2026-07-02", "2026-08-15")
BASE_CAL = ("2026-08-15", "2026-08-22")
CP2_FIT = ("2026-08-27", "2026-08-31")
CP2_CAL = ("2026-09-03", "2026-09-07")
KNOWN_BAD = ("2026-09-07T10:55:00", "2026-09-07T11:29:00")
OVERRIDES = {"080:6":{"fit":CP2_FIT,"calibration":CP2_CAL}}


def configure_plan(plan):
    """Later retraining stays explicit, bounded and produces a new version."""
    global BASE_FIT,BASE_CAL,MACHINES,OVERRIDES
    from datetime import date
    def period(value):
        if len(value)!=2:raise ValueError('two exclusive period endpoints required')
        start,end=map(date.fromisoformat,value)
        if [start.isoformat(),end.isoformat()]!=list(value):raise ValueError('ISO YYYY-MM-DD endpoints required')
        if not 3<=(end-start).days<=90:raise ValueError('period must contain 3–90 days')
        return tuple(value)
    BASE_FIT=period(plan['fit']);BASE_CAL=period(plan['calibration'])
    if BASE_FIT[1]>BASE_CAL[0]:raise ValueError('fit/calibration overlap')
    machines=plan['machines']
    if not 1<=len(machines)<=32 or len(set(machines))!=len(machines) or any(len(m)!=3 or not m.isdigit() for m in machines):
        raise ValueError('1–32 unique canonical three-digit machine identifiers required')
    MACHINES=tuple(machines);OVERRIDES={}
    for row in plan.get('overrides',[]):
        if row['machine'] not in MACHINES or not 1<=row['module']<=8:raise ValueError('invalid override target')
        fit,cal=period(row['fit']),period(row['calibration'])
        if fit[1]>cal[0]:raise ValueError('override fit/calibration overlap')
        key=f"{row['machine']}:{row['module']}"
        if key in OVERRIDES:raise ValueError('duplicate module override')
        OVERRIDES[key]={'fit':fit,'calibration':cal}


def hash_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def semantic_admit(frame):
    x = frame[list(FEATURES)].to_numpy()
    good = semantic_quality(x)
    known = frame.machine.eq("080") & frame.module.eq(6) & frame.time.ge(KNOWN_BAD[0]) & frame.time.lt(KNOWN_BAD[1])
    frame = frame.copy()
    frame["semantic_bad"] = ~good | known
    frame["quality"] = frame.quality & ~frame.semantic_bad
    return frame


def frozen_sources():
    manifest = json.loads((SOURCE/"intake_manifest.json").read_text(encoding="utf-8"))
    study = json.loads((SOURCE/"summary.json").read_text(encoding="utf-8"))
    lookup = {(r["machine"], r["date"]): r for r in study["source_days"]}
    verified = []
    for r in manifest["files"]:
        key = r["machine"], r["date"]
        if lookup[key]["minute_parquet_sha256"] != r["minute_parquet_sha256"] or lookup[key]["source_sha256"] != r["source_sha256"]:
            raise ValueError("source receipts conflict")
        path = SOURCE/"minutes"/f"{key[0]}_{key[1]}.parquet"
        if hash_file(path) != r["minute_parquet_sha256"]:
            raise ValueError(f"changed prepared day: {path.name}")
        verified.append({k: r[k] for k in ("machine", "date", "source_sha256", "minute_parquet_sha256", "raw_rows")})
    if not verified or len(verified)!=len(lookup) or not set(MACHINES).issubset({r['machine'] for r in verified}):
        raise ValueError("complete planned frozen source receipts required")
    return study, verified


def read_period(machine, period, sources,module=None):
    start, end = period
    days = [r["date"] for r in sources if r["machine"] == machine and start <= r["date"] < end]
    if not days:raise ValueError(f'No committed source days for {machine} in {period}')
    columns = ["time", "machine", "module", "quality", "context", "valve", *FEATURES]
    frame = pd.concat([pd.read_parquet(SOURCE/"minutes"/f"{machine}_{d}.parquet", columns=columns,
                      filters=[('module','==',module)] if module else None) for d in days], ignore_index=True)
    return semantic_admit(frame).sort_values(["module", "time"]).reset_index(drop=True)


def phase_movement(frame,context):
    valid=frame.quality & frame.context.eq(context)
    valid &= frame.time.diff().dt.total_seconds().eq(60) & frame.context.eq(frame.context.shift())
    contiguous=valid.astype(int).rolling(4,min_periods=4).sum().eq(4) & frame.quality.shift(4,fill_value=False)
    movement=frame[list(FEATURES)].rolling(5,min_periods=5).max()-frame[list(FEATURES)].rolling(5,min_periods=5).min()
    return movement,contiguous


def phase_select(frame,context,bounds):
    movement,contiguous=phase_movement(frame,context)
    return contiguous & movement.le(bounds).all(axis=1) & frame.context.eq(context)


def references(sources, override, machines=None, modules=range(1, 9)):
    models = []; receipts = []
    for machine in machines or MACHINES:
        data = read_period(machine, BASE_FIT, sources)
        for module in modules:
            period=OVERRIDES.get(f'{machine}:{module}',{}).get('fit',BASE_FIT) if override else BASE_FIT
            frame = read_period(machine,period,sources,module=module) if period!=BASE_FIT else data
            frame = frame[frame.module.eq(module)].copy()
            for context in ("SV_OFF", "SV_ON"):
                eligible = frame.quality & frame.context.eq(context)
                rows = frame[eligible]
                receipt = {"machine": machine, "module": module, "context": context, "fit_period": period,
                           "qualified_points": len(rows), "suspect_quality_minutes": int(frame.semantic_bad.sum())}
                if len(rows) < 20:
                    receipts.append({**receipt, "status": "INSUFFICIENT_LOCAL_REFERENCE"}); continue
                _, scale = robust_location(rows[list(FEATURES)])
                movement,contiguous=phase_movement(frame,context)
                if contiguous.sum()<20:
                    receipts.append({**receipt,"status":"INSUFFICIENT_CONTIGUOUS_REFERENCE"});continue
                # Model phase tolerates observed normal sensor variation, rather
                # than requiring almost zero movement relative to narrow MAD.
                # Bounds use Fit ONLY; no calibration/case/future flag tuning.
                bounds=np.maximum(.35*scale,movement.loc[contiguous].quantile(.90).to_numpy())
                bounds=np.maximum(bounds,.1)
                chosen = frame[phase_select(frame,context,bounds)]
                sampled = chosen[chosen.time.dt.minute.mod(15).eq(0)]
                if len(sampled) < 20 or chosen.time.dt.normalize().nunique() < 3:
                    receipts.append({**receipt, "status": "INSUFFICIENT_STEADY_REFERENCE"}); continue
                model = fit_local(sampled[list(FEATURES)], machine=machine, module=module, context=context,
                                  reference_end=period[1], evidence_status="OWNER_PROPOSED_NOT_HEALTH_REVIEWED" if period != BASE_FIT else "UNREVIEWED_OPERATING_DATA")
                model.update(stability_bounds=bounds.tolist(),phase_method='Fit-only Q90 five-minute coordinate range, max(.35 robust scale,.1 physical units); phase is not health',
                             reference_start=period[0], reference_days=int(chosen.time.dt.normalize().nunique()),
                             reference_minutes=len(chosen), valve_p05=float(chosen.valve.quantile(.05)),
                             valve_p95=float(chosen.valve.quantile(.95)), service_epoch="UNVERIFIED",
                             regime_scope="SV-conditioned supported control; verified ATC/recipe/config not available")
                models.append(model)
                receipts.append({**receipt, "status": "REFERENCE_PROPOSAL", "thinned_points": len(sampled), "steady_minutes": len(chosen)})
        del data; gc.collect()
    return models, receipts


def candidates(local_references, donor_references, sources, override, machines=None):
    models = []; receipts = []
    for machine in machines or MACHINES:
        calibration = read_period(machine, BASE_CAL, sources)
        for local in [r for r in local_references if r["machine"] == machine]:
            module = local["module"]; context = local["context"]
            period=OVERRIDES.get(f'{machine}:{module}',{}).get('calibration',BASE_CAL) if override else BASE_CAL
            frame = read_period(machine,period,sources,module=module) if period!=BASE_CAL else calibration
            frame = frame[frame.module.eq(module)].copy()
            # Independent threshold block, with frozen fit scales/phase screen.
            eligible = phase_select(frame,context,local['stability_bounds'])
            selected = frame[eligible]
            receipt = {"machine": machine, "module": module, "context": context, "calibration_period": period,
                       "calibration_minutes": len(selected), "calibration_days": int(selected.time.dt.normalize().nunique())}
            if len(selected) < 200 or receipt["calibration_days"] < 3:
                receipts.append({**receipt, "status": "INSUFFICIENT_THRESHOLD_CALIBRATION"}); continue
            assisted = assist_local(local, [r for r in donor_references if r["module"] == module and r["context"] == context], research=True)
            model = calibrate(selected[list(FEATURES)], assisted, start=period[0], end=period[1])
            model.update(absolute_threshold=float(max(1., np.quantile(self_scores(selected[list(FEATURES)], local), .995))),
                         local_absolute_reference=local, calibration_days=receipt["calibration_days"])
            models.append(model)
            receipts.append({**receipt, "status": "FROZEN_SHADOW_CANDIDATE", "fleet_weight": model["fleet_weight"],
                             "donor_machines": model["donor_machines"]})
        del calibration; gc.collect()
    return models, receipts


def run():
    started = time.perf_counter(); OUT.mkdir(parents=True, exist_ok=True)
    study, sources = frozen_sources()
    print(f"Verified all {len(sources)} prepared source-day checksums", flush=True)
    donors, base_receipts = references(sources, False)
    base_models, base_cal = candidates(donors, donors, sources, False)
    print(f"Base: {len(donors)} references / {len(base_models)} calibrated profiles", flush=True)
    changed=[];changed_receipts=[];changed_models=[];changed_cal=[]
    for key in OVERRIDES:
        machine,module=key.split(':');module=int(module)
        refs,receipt=references(sources,True,machines=(machine,),modules=(module,))
        calibrated,cal_receipt=candidates(refs,donors,sources,True,machines=(machine,))
        changed.extend(refs);changed_receipts.extend(receipt);changed_models.extend(calibrated);changed_cal.extend(cal_receipt)
    is_changed=lambda m:f"{m['machine']}:{m['module']}" in OVERRIDES
    updated_receipts=[r for r in base_receipts if not is_changed(r)]+changed_receipts
    models=[m for m in base_models if not is_changed(m)]+changed_models
    cal_receipts=[r for r in base_cal if not is_changed(r)]+changed_cal
    curves = SOURCE/"transition_metrics.parquet"
    transition = pd.read_parquet(curves)
    transition = transition[transition.split.eq("reference")]
    transition_summary = transition.groupby(["machine", "module", "direction", "status"]).size().rename("events").reset_index().to_dict("records")
    plan={'fit':BASE_FIT,'calibration':BASE_CAL,'machines':MACHINES,'overrides':[
        {'machine':k.split(':')[0],'module':int(k.split(':')[1]),**v} for k,v in OVERRIDES.items()]}
    write_json(OUT/'build-plan.json',plan)
    curation = {"version": "explicit-reference-periods-v1", "healthy_review": "PENDING",'build_plan':plan,
                "semantic_quarantine_intervals":[{"machine":"080","module":6,"start":KNOWN_BAD[0],"end":KNOWN_BAD[1],
                    "reason":"Observed-second M6 rail/default acquisition evidence; outward minute rounding"}],
                "default_fit": BASE_FIT, "default_calibration": BASE_CAL,
                "MX080_M6": {"proposed_fit": CP2_FIT, "proposed_calibration": CP2_CAL,
                    "interpretation": "Owner-described stable run; not independently certified healthy",
                    "quarantine_from_normal": [["2026-08-23T15:09:00", "2026-08-27"], ["2026-08-31T15:59:00", "2026-09-03"], ["2026-09-07", "2026-10-02"]],
                    "acquisition_suspect_minute_interval": KNOWN_BAD,
                    "post_2026_09_12": "NEW_CONTROL_LEVEL_REQUIRES_EPOCH_REVIEW"},
                "raw_and_events_deleted": False, "quarantine_is_fault_label": False,
                "admission": "complete observed minute + semantic screen + supported context + five trailing ranges inside frozen Fit-only Q90 bounds; stability is not health"}
    provenance = {"study_id": study["study_id"], "derived_version": study["derived_version"], "sources": sources,
                  "timezone": "Asia/Bangkok assumed from naive logs", "pressure_unit": "owner-confirmed psi", "pressure_basis": "UNVERIFIED",
                  "source_snapshot": "canonical ZIP/import receipts, not exact current SQL snapshot",
                  "transition_metrics_sha256": hash_file(curves),
                  "episode_review": "deployment/MX080_M6_CP2_EPISODE_REVIEW_20261005.md",
                  "code_sha256": {p.name: hash_file(p) for p in [Path(__file__), ROOT/"apps/api/app/fleet_stable.py", ROOT/"apps/api/app/fleet_assistance.py"]}}
    blockers = ["ENGINEER_REVIEWED_HEALTHY_REFERENCES", "VERIFIED_HARDWARE_ROLE_CONFIGURATION",
                "PRESSURE_BASIS_STATE_CONTROLLER_SERVICE_CONTRACTS", "INDEPENDENT_HEALTHY_CYCLES",
                "FROZEN_PROSPECTIVE_VALIDATION", "TARGET_SERVER_PRODUCER_AUTH_AND_LIFECYCLE_ACCEPTANCE"]
    paths = {}
    for variant, chosen, fit_receipts, threshold_receipts in [("base", base_models, base_receipts, base_cal), ("cp2_candidate", models, updated_receipts, cal_receipts)]:
        current_curation = {**curation, "variant": variant, "fit_receipts": fit_receipts, "threshold_receipts": threshold_receipts}
        if variant == "base":
            current_curation["MX080_M6"] = {**curation["MX080_M6"], "actual_fit": BASE_FIT, "actual_calibration": BASE_CAL}
        elif '080:6' in OVERRIDES:
            current_curation["MX080_M6"] = {**curation["MX080_M6"], "actual_fit": OVERRIDES['080:6']['fit'], "actual_calibration": OVERRIDES['080:6']['calibration']}
        payloads = {"models.json": chosen, "priors.json": {"steady_donor_summaries": donors, "transition_counts": transition_summary,
                    "transitions_voting": False, "transition_interpretation": "Unreviewed observed source events, not accepted normal response envelopes"},
                    "curation.json": current_curation, "provenance.json": provenance,
                    "validation.json": {"release_gate": "SHADOW_ONLY", "prospective_verified": False,
                        "healthy_fpr_verified": False, "protocol": "Separate fit/calibration; whole target machine excluded from donors; known-case regression is retrospective"},
                    "README.md": b"# Fleet Stable v1\n\nFrozen portable Shadow Candidate. Six physical coordinates, psi (basis unverified). Local absolute median/MAD-IQR scales are frozen; Fleet shares compatible correlation shape only. JSON/scalers/covariance/target thresholds are checksum verified. No live fitting, adaptation, PLC write or alert vote.\n\nInstall with apps.api.app.fleet_bundle; select a Shadow pointer with expected revision. New training produces a new immutable version. Production needs reviewed healthy references, verified contracts, independent/future validation and target-server lifecycle acceptance.\n"}
        path = write_package(OUT/"bundles", payloads, metadata={"source_machines": list(MACHINES), "blockers": blockers,
            'evidence_dates':[min(r['date'] for r in sources),max(r['date'] for r in sources)],
            "method_version": "selective-fleet-empirical-bayes-v1", "variant": variant,
            "runtime_dependencies": {"python": ">=3.11", "numpy": ">=2.0,<3", "scipy": ">=1.13,<2"}})
        export_zip(path, OUT/(path.name+".zip")); paths[variant] = str(path)
    summary = {"packages": paths, "models": len(models), "base_models": len(base_models), "donor_summaries": len(donors),
               "source_days_verified": len(sources), "raw_rows": sum(r["raw_rows"] for r in sources),
               "fleet_assisted_models": sum(m["fleet_weight"] > 0 for m in models), "elapsed_seconds": time.perf_counter()-started,
               "fit_receipts": updated_receipts, "calibration_receipts": cal_receipts}
    write_json(OUT/"build-summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("receipts")}, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path);parser.add_argument('--source-root',type=Path)
    parser.add_argument('--output-root',type=Path);args=parser.parse_args()
    if args.plan:configure_plan(json.loads(args.plan.read_text(encoding='utf-8')))
    if args.source_root:SOURCE=args.source_root.resolve()
    if args.output_root:OUT=args.output_root.resolve()
    run()
