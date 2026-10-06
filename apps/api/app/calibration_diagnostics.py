"""Explain immutable candidate checks and locate evidence; never change scores."""
from __future__ import annotations
from datetime import datetime, timedelta
from collections import Counter
import numpy as np
from .qualified_windows import FEATURES
from .qualified_calibration import _fit_features
from .reference_review import bounds, is_excluded
from .qualified_policy import LEGACY_THRESHOLD_VERSION, THRESHOLD_VERSION, score_features, crosses, manifest

VERSION = "candidate-review-evidence-v2-physical-control-recovery"


def _runs(points, kind, phase):
    result, current = [], None
    for stamp, feature, score, value, median in points:
        if current and current["end"] == stamp.isoformat() and current["feature"] == feature:
            current["end"] = (stamp+timedelta(minutes=1)).isoformat()
            current["minutes"] += 1
            if score is not None and score > (current["peak_score"] or 0):
                current.update(peak_score=score, peak_value=value, baseline_median=median, peak_time=stamp.isoformat())
        else:
            current = {"kind":kind,"phase":phase,"start":stamp.isoformat(),"end":(stamp+timedelta(minutes=1)).isoformat(),
                "feature":feature,"minutes":1,"peak_score":score,"peak_value":value,"baseline_median":median,"peak_time":stamp.isoformat()}
            result.append(current)
    return result


def explain(windows, selection, candidate):
    start, ref_end, shadow_start, shadow_end = bounds(selection)
    ref = [w for w in windows if w.eligible and start <= w.window_start < ref_end and not is_excluded(w,selection)]
    baseline = candidate["statistics"].get("exact_baseline",{})
    threshold = candidate["threshold"].get("deviation_score_q995")
    version=candidate['threshold'].get('threshold_version',LEGACY_THRESHOLD_VERSION)
    voting=score_features(version); indices=[FEATURES.index(f) for f in voting]
    control={}
    intervals, initial, marks = [], {}, {}
    if ref:
        medians, scales = _fit_features(ref)
        initial = {f:{"median":medians[f],"scale":scales[f]} for f in FEATURES}
        values = np.asarray([[w.features[f] for f in FEATURES] for w in ref])
        z = abs((values-np.asarray([medians[f] for f in FEATURES]))/np.asarray([scales[f] for f in FEATURES]))
        peaks=np.asarray(indices)[z[:,indices].argmax(axis=1)]
        flagged=[(w.window_start,FEATURES[int(peaks[i])],float(z[i,peaks[i]]),float(values[i,peaks[i]]),medians[FEATURES[int(peaks[i])]])
                 for i,w in enumerate(ref) if z[i,peaks[i]] > selection["policy"]["profile_quarantine_z"]]
        intervals += _runs(flagged,"reference_outlier","reference")
    usable = [w for w in windows if w.eligible and shadow_start <= w.window_start < shadow_end]
    if baseline and threshold:
        medians=np.asarray([baseline[f]["median"] for f in FEATURES]); scales=np.asarray([baseline[f]["scale"] for f in FEATURES])
        if usable:
            values=np.asarray([[w.features[f] for f in FEATURES] for w in usable])
            z=abs((values-medians)/scales); peaks=np.asarray(indices)[z[:,indices].argmax(axis=1)]
            for i,w in enumerate(usable):
                hour=w.window_start.replace(minute=0).isoformat()
                mark=marks.setdefault(hour,{"score_max":0.0,"threshold":threshold,"flagged_minutes":0,"contributor":""})
                if z[i,peaks[i]]>mark["score_max"]:
                    mark.update(score_max=float(z[i,peaks[i]]),contributor=FEATURES[int(peaks[i])])
                mark["flagged_minutes"]+=int(crosses(z[i,peaks[i]],threshold,version))
            flagged=[(w.window_start,FEATURES[int(peaks[i])],float(z[i,peaks[i]]),float(values[i,peaks[i]]),float(medians[peaks[i]]))
                     for i,w in enumerate(usable) if crosses(z[i,peaks[i]],threshold,version)]
            intervals += _runs(flagged,"shadow_deviation","shadow")
            if version==THRESHOLD_VERSION:
                vi=FEATURES.index('valve');physical_flags=crosses(z[np.arange(len(usable)),peaks],threshold,version)
                adjusted=(z[:,vi]>=1)&~physical_flags
                controls=[(w.window_start,'valve',float(z[i,vi]),float(values[i,vi]),float(medians[vi])) for i,w in enumerate(usable) if adjusted[i]]
                intervals += _runs(controls,'control_context','shadow')
                retained=candidate['retained']
                control={'votes':False,'physical_flagged_minutes':int(physical_flags.sum()),
                    'control_changed_physical_below_minutes':int(adjusted.sum()),
                    'reference_valve_median':float(medians[vi]),
                    'reference_valve_range':[float(retained.valve.min()),float(retained.valve.max())] if not retained.empty else None,
                    'description':'Valve differs from Reference median by at least one source count while physical score is below or equal cutoff; not a fault/healthy label.'}
    intervals.sort(key=lambda x: (x["kind"]!="shadow_deviation",-(x["peak_score"] or 0),-x["minutes"],x["start"]))
    for i,item in enumerate(intervals): item["id"]=f"{item['kind']}-{i}-{item['start']}"
    reasons = candidate["reasons"]
    checks = [
        {"key":"reference","state":"review" if any(r in reasons for r in ("REFERENCE_SELECTION_NEEDS_REVIEW","QUARANTINE_RATE_EXCEEDED","CALIBRATION_DRIFT_EXCEEDED","ALL_WINDOWS_QUARANTINED","NONPOSITIVE_THRESHOLD")) else "waiting" if any(r.startswith("INSUFFICIENT") and "SHADOW" not in r for r in reasons) else "pass", "value":candidate["quarantine_pct"],"limit":selection["policy"]["profile_max_quarantine_pct"],"unit":"%"},
        {"key":"shadow","state":"review" if "SHADOW_FLAG_RATE_EXCEEDED" in reasons else "waiting" if any("SHADOW" in r and r!="SHADOW_FLAG_RATE_EXCEEDED" for r in reasons) else "pass", "value":candidate["validation"].get("shadow_flag_pct"),"limit":selection["policy"]["profile_max_shadow_flag_pct"],"unit":"%"},
        {"key":"contracts","state":"waiting" if any(r.endswith("_UNVERIFIED") for r in reasons) else "pass", "reasons":[r for r in reasons if r.endswith("_UNVERIFIED")]},
    ]
    drift={"rz":candidate["validation"].get("max_half_shift_rz"),"limit":selection["policy"]["profile_max_half_shift_rz"]}
    retained=candidate["retained"]
    days=sorted(retained.day.unique()) if not retained.empty else []
    if len(days)>=2 and baseline:
        midpoint=days[len(days)//2]; early=retained.loc[retained.day<midpoint,list(FEATURES)].median(); late=retained.loc[retained.day>=midpoint,list(FEATURES)].median()
        feature=max(voting,key=lambda f:abs(float(late[f]-early[f]))/baseline[f]["scale"])
        drift.update(feature=feature,early_median=float(early[feature]),late_median=float(late[feature]),split_day=str(midpoint))
    gate_counts=Counter(w.reason or w.data_quality_status for w in windows if not w.eligible)
    missing=max(0,int((shadow_end-start).total_seconds()/60)-len(windows))
    if missing:gate_counts["NO_SOURCE_ROWS"]=missing
    from .calibration_recovery import review as recovery_review
    recovery=recovery_review(windows,selection,baseline,threshold) if version==THRESHOLD_VERSION else None
    return {"version":VERSION,"scoring_policy":manifest(version),"control":control,"recovery":recovery,
        "checks":checks,"threshold":threshold,"quarantine_threshold":selection["policy"]["profile_quarantine_z"],"initial_reference_baseline":initial,
        "quality":{"observed_minutes":len(windows),"qualified_minutes":sum(w.eligible for w in windows),"gate_counts":dict(gate_counts)},
        "drift":drift,"intervals":intervals[:200],"total_intervals":len(intervals),"intervals_limited":len(intervals)>200,
        "hourly_marks":marks,"qualified_is_healthy":False,"raw_grain":"observed second",
        "interpretation":"Feature contribution is a score explanation, not a confirmed physical cause"}


def annotate_points(points, evidence, baseline):
    """For daily minute charts; use the exact frozen preview baseline/threshold."""
    threshold=evidence.get("threshold")
    version=evidence.get('scoring_policy',{}).get('threshold_version',LEGACY_THRESHOLD_VERSION)
    voting=score_features(version)
    for point in points:
        if point.get("phase")=="shadow" and point.get("qualified") and baseline and threshold:
            z={f:abs((point[f]-baseline[f]["median"])/baseline[f]["scale"]) for f in FEATURES}
            feature=max(voting,key=z.get)
            point.update(score=z[feature],threshold=threshold,flagged=bool(crosses(z[feature],threshold,version)),contributor=feature)
            if version==THRESHOLD_VERSION:
                point.update(control_z=z['valve'],control_only=not point['flagged'] and z['valve']>=1)
        elif point.get("phase")=="reference" and point.get("qualified") and evidence.get("initial_reference_baseline"):
            initial=evidence["initial_reference_baseline"]
            z={f:abs((point[f]-initial[f]["median"])/initial[f]["scale"]) for f in FEATURES}
            point["reference_outlier"]=max(z[f] for f in voting)>evidence.get("quarantine_threshold",8.0)
            point["reference_contributor"]=max(voting,key=z.get)
    return points
