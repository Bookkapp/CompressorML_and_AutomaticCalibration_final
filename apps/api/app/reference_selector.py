"""Bounded, past-only reference proposal. Never rank using Shadow results.

Stable does not mean healthy. No automatic exclusions, gate relaxation,
service epoch invention or Active promotion. Search only already-read days.
"""
from datetime import timedelta
import numpy as np
from .qualified_calibration import SCALE_FLOORS
from .qualified_windows import FEATURES
from .reference_review import bounds
from .qualified_policy import PHYSICAL_FEATURES, THRESHOLD_VERSION

VERSION = "past-only-physical-current-reference-proposal-v3"


def fit_matrix(values):
    medians=np.median(values,axis=0)
    scales=np.maximum(np.asarray([SCALE_FLOORS[f] for f in FEATURES]),np.maximum(
        1.4826*np.median(abs(values-medians),axis=0),np.subtract(*np.quantile(values,[.75,.25],axis=0))/1.349))
    return medians,scales


def propose(windows, selection, settings):
    start,end,shadow_start,_ = bounds(selection)
    past=[w for w in windows if w.eligible and start<=w.window_start<end]
    matrix=np.asarray([[w.features[f] for f in FEATURES] for w in past],dtype=float).reshape(-1,len(FEATURES))
    stamps=np.asarray([w.window_start for w in past],dtype="datetime64[m]")
    calendar=stamps.astype("datetime64[D]")
    daily={}
    for day in np.unique(calendar):
        daily[day]=fit_matrix(matrix[calendar==day])
    lengths=sorted({int((end-start).days),7,14,21},reverse=True)
    candidates=[]
    for shift in (0,7,14,21):
        finish=end-timedelta(days=shift)
        for length in lengths:
            begin=finish-timedelta(days=length)
            if begin<start or begin>=finish or finish>shadow_start: continue
            mask=(stamps>=np.datetime64(begin))&(stamps<np.datetime64(finish))
            rows=matrix[mask];dates=calendar[mask]
            if len(rows)<settings.profile_min_calibration_windows or len(np.unique(dates))<settings.profile_min_calibration_days: continue
            physical=[FEATURES.index(f) for f in PHYSICAL_FEATURES]
            medians,scales=fit_matrix(rows); scores=np.max(abs((rows-medians)/scales)[:,physical],axis=1)
            keep=scores<=settings.profile_quarantine_z
            retained=rows[keep];retained_dates=dates[keep]
            days=np.unique(retained_dates)
            quarantine=100*(1-len(retained)/len(rows))
            drift=None
            if len(days)>=2:
                midpoint=days[len(days)//2]; a=retained[retained_dates<midpoint]; b=retained[retained_dates>=midpoint]
                retained_medians,fit_scales=fit_matrix(retained)
                drift=float(np.max((abs(np.median(a,axis=0)-np.median(b,axis=0))/fit_scales)[physical]))
            observed_days=np.unique(dates)
            gaps=length-len(observed_days)
            dvalues=np.asarray([daily[d][0] for d in observed_days])
            dscales=np.median(np.asarray([daily[d][1] for d in observed_days]),axis=0)
            # Whole-period scale can hide two plateaus. This proposal-only
            # screen compares daily levels against within-day variation.
            spans=np.subtract(*np.quantile(dvalues,[.90,.10],axis=0))/dscales
            daily_span=float(np.max(spans[physical]))
            daily_feature=PHYSICAL_FEATURES[int(np.argmax(spans[physical]))]
            passes=(len(retained)>=settings.profile_min_calibration_windows and len(days)>=settings.profile_min_calibration_days
                    and quarantine<=settings.profile_max_quarantine_pct and drift is not None and drift<=settings.profile_max_half_shift_rz
                    and daily_span<=2.0 and float(np.quantile(np.max(abs((retained-retained_medians)/fit_scales)[:,physical],axis=1),.995))>0)
            # Coverage/continuity first; prefer more evidence and recency among
            # passing blocks. No flag-rate or threshold feedback from Shadow.
            candidates.append({"start":begin.isoformat(),"end":finish.isoformat(),"days":length,"qualified_days":len(days),
                "qualified_minutes":len(rows),"retained_minutes":len(retained),"quarantine_pct":quarantine,
                "drift_rz":drift,"daily_level_span_rz":daily_span,"daily_level_feature":daily_feature,
                "daily_feature_spans":{f:float(spans[FEATURES.index(f)]) for f in PHYSICAL_FEATURES},
                "control_daily_span_rz":float(spans[FEATURES.index('valve')]),
                "missing_days":gaps,"reference_checks_pass":bool(passes),"age_days":shift})
    ranked=sorted(candidates,key=lambda x:(not x["reference_checks_pass"],x["missing_days"],-x["qualified_days"],x["age_days"],x["quarantine_pct"]))
    # A stable older regime is evidence to inspect, not an automatically valid
    # baseline for today's operating regime. Without a dated verified service
    # epoch, only blocks ending at the current Reference cutoff are proposed.
    choice=next((x for x in ranked if x["reference_checks_pass"] and x['age_days']==0),None)
    default={"start":start.isoformat(),"end":end.isoformat()}
    return {"version":VERSION,"selected":choice or default,"changed":bool(choice and (choice["start"]!=default["start"] or choice["end"]!=default["end"])),
        "candidates_checked":len(candidates),"alternatives":ranked[:3],"shadow_used_for_selection":False,
        "search_start":start.isoformat(),"search_end":end.isoformat(),"service_epoch_verified":bool(settings.profile_service_epoch_version),
        "reason":"เลือกช่วงที่สิ้นสุดตรง Reference ล่าสุด จากความครอบคลุม ความต่อเนื่อง และความคงที่เท่านั้น" if choice else "ยังไม่พบช่วงปัจจุบันที่ผ่านครบ ช่วงเก่าที่คงที่ต้องให้ผู้ดูแลตรวจบริบทก่อนใช้แทนสภาวะล่าสุด",
        "healthy_confirmed":False,"automatic_exclusions":[],"needs_review":choice is None,
        "proposal_policy":{"threshold_version":THRESHOLD_VERSION,"physical_features":list(PHYSICAL_FEATURES),"valve_is_control_context":True,"automatic_end_backtrack_days":0,
            "daily_level_span_rz_max":2.0,"period_lengths_days":lengths,"end_backtracks_days":[0,7,14,21],"maximum_candidates":16}}
