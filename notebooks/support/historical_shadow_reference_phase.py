"""Pure-local, past-only reference/phase ablation; never calls SQL or approval.

Inputs are the source-second-derived, strict 1m caches from 08K and 08L.
Dynamic phase is causal review evidence, NOT a rule to suppress alerts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from notebooks.support.october_three_machine_calibration import FEATURES, fit_array, persistent_flags

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'notebooks/outputs/historical_shadow_reference_phase_v1'
PROTOCOL = ROOT / 'research/historical_shadow_reference_phase_protocol_v1.json'
CACHE_ROOTS = [ROOT / 'notebooks/outputs/october_three_machine_calibration_v1',
               ROOT / 'notebooks/outputs/local_profile_model_selection_v1']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def complete_day_bounds(as_of, history_days=28, shadow_days=3):
    """Local midnight boundaries, fit [a,b), shadow [b,c); today excluded."""
    end = pd.Timestamp(as_of).normalize()
    shadow_start = end - pd.Timedelta(days=shadow_days)
    return shadow_start - pd.Timedelta(days=history_days), shadow_start, end


def trailing_dynamics(data, window=5):
    """Five observed contiguous minute means; robust pairwise slope + MAD.

    No resampling, filling or future rows. Every window must be state-qualified.
    Missing minute/invalid state restarts history. Slope unit is source-unit/min.
    """
    n = len(data)
    values = data[FEATURES].to_numpy(float)
    slopes = np.full_like(values, np.nan)
    variation = np.full_like(values, np.nan)
    complete = np.zeros(n, bool)
    if n < window:
        return slopes, variation, complete
    windows = np.lib.stride_tricks.sliding_window_view(values, window, axis=0)
    valid = data.eligible.to_numpy(bool)
    stamp = data.stamp.to_numpy(dtype='datetime64[ns]').astype('int64')
    vw = np.lib.stride_tricks.sliding_window_view(valid, window)
    tw = np.lib.stride_tricks.sliding_window_view(stamp, window)
    ok = vw.all(axis=1) & (np.diff(tw, axis=1) == 60_000_000_000).all(axis=1)
    # Ten pairwise slopes for W=5; median guards a single endpoint jump.
    pairs = [(windows[:, :, b] - windows[:, :, a]) / (b-a)
             for a in range(window) for b in range(a+1, window)]
    s = np.median(np.stack(pairs, axis=2), axis=2)
    med = np.median(windows, axis=2)
    v = 1.4826 * np.median(np.abs(windows - med[:, :, None]), axis=2)
    slopes[window-1:] = np.where(ok[:, None], np.abs(s), np.nan)
    variation[window-1:] = np.where(ok[:, None], v, np.nan)
    complete[window-1:] = ok
    return slopes, variation, complete


def dynamic_limits(data, fit_mask, protocol):
    slope, variation, complete = trailing_dynamics(data, protocol['trailing_minutes'])
    past = np.asarray(fit_mask) & complete
    if past.sum() < protocol['minimum_minutes']:
        return None, slope, variation, complete
    floors_s = np.array([.1, .1, .1, .1, .25, .01, .01, .1, .1])
    floors_v = np.array([.1, .1, .1, .1, 1., .05, .05, .1, .1])
    q = protocol['dynamic_limit_quantile']
    return (np.maximum(np.quantile(slope[past], q, axis=0), floors_s),
            np.maximum(np.quantile(variation[past], q, axis=0), floors_v)), slope, variation, complete


def classify_phase(data, limits, slope, variation, complete, protocol):
    n = len(data)
    eligible = data.eligible.to_numpy(bool)
    labels = np.full(n, 'INELIGIBLE', dtype=object)
    labels[eligible] = 'UNKNOWN_HISTORY'
    stable = np.zeros(n, bool)
    if limits is not None:
        within = complete & (slope <= limits[0]).all(axis=1) & (variation <= limits[1]).all(axis=1)
        adjacent = data.stamp.diff().eq(pd.Timedelta(minutes=1)).to_numpy()
        k = protocol['stable_consecutive_minutes']
        for i in range(k-1, n):
            stable[i] = within[i-k+1:i+1].all() and adjacent[i-k+2:i+1].all()
        labels[complete] = 'CHANGING_OR_SETTLING'
        labels[stable] = 'STEADY_CANDIDATE'
    return labels, stable


def select_segment(data, fit_mask, protocol):
    """Level discontinuities from past day medians, scaled WITHIN days.

    Flatness never establishes health. Multiple supported epochs => review.
    No shadow data may choose the segment. Longest, earliest on ties, fixed rule.
    """
    fields = protocol['segment_features']
    train = data.loc[np.asarray(fit_mask) & data.eligible].copy()
    train['day'] = train.stamp.dt.normalize()
    day_rows = []
    for day, group in train.groupby('day', sort=True):
        if len(group) < protocol['minimum_day_minutes_for_segment']:
            continue
        values = group[fields].to_numpy(float)
        med = np.median(values, axis=0)
        scale = np.maximum(1.4826*np.median(np.abs(values-med), axis=0), [.1,.1,.05,.05])
        day_rows.append(dict(day=day, minutes=len(group), **{f:med[j] for j,f in enumerate(fields)},
                             **{f+'_scale':scale[j] for j,f in enumerate(fields)}))
    day_table = pd.DataFrame(day_rows)
    result = np.zeros(len(data), bool)
    if day_table.empty:
        return result, day_table, dict(supported_segments=0, selected_days=0, selected_minutes=0)
    within_scale = np.median(day_table[[f+'_scale' for f in fields]].to_numpy(), axis=0)
    shifts = np.max(np.abs(np.diff(day_table[fields].to_numpy(), axis=0))/within_scale, axis=1)
    breaks = np.r_[True, (shifts > protocol['segment_jump_z']) |
                   day_table.day.diff().iloc[1:].gt(pd.Timedelta(days=1)).to_numpy()]
    day_table['segment'] = np.cumsum(breaks)-1
    day_table['jump_z'] = np.r_[0., shifts]
    candidates = day_table.groupby('segment').agg(days=('day','size'),minutes=('minutes','sum'),start=('day','min'))
    supported = candidates.loc[(candidates.days >= protocol['minimum_days']) &
                               (candidates.minutes >= protocol['minimum_minutes'])]
    if len(supported):
        selected = supported.sort_values(['minutes','start'], ascending=[False,True],kind='stable').index[0]
        selected_days = day_table.loc[day_table.segment.eq(selected),'day']
        result = data.stamp.dt.normalize().isin(selected_days).to_numpy() & np.asarray(fit_mask)
        day_table['selected'] = day_table.segment.eq(selected)
        info = dict(supported_segments=len(supported), selected_days=len(selected_days),
                    selected_minutes=int(supported.loc[selected,'minutes']), selected_start=str(selected_days.min()),
                    selected_end_exclusive=str(selected_days.max()+pd.Timedelta(days=1)))
    else:
        day_table['selected'] = False
        info = dict(supported_segments=0, selected_days=0, selected_minutes=0)
    return result, day_table, info


def fit_reference(data, mask, protocol):
    train = data.loc[np.asarray(mask) & data.eligible]
    info = dict(fit_minutes=len(train), fit_days=train.stamp.dt.normalize().nunique(),
                supported=False, status='INSUFFICIENT_REFERENCE')
    if len(train) < protocol['minimum_minutes'] or info['fit_days'] < protocol['minimum_days']:
        return None, info
    med, scale, threshold, quarantine = fit_array(train)
    values = train[FEATURES].to_numpy(float)
    initial_med = np.median(values,axis=0)
    initial_scale = np.maximum.reduce([1.4826*np.median(np.abs(values-initial_med),axis=0),
        (np.quantile(values,.75,axis=0)-np.quantile(values,.25,axis=0))/1.349,
        np.array([1. if f=='valve' else .1 for f in FEATURES])])
    keep = np.max(np.abs((values-initial_med)/initial_scale),axis=1) <= protocol['quarantine_z']
    retained = train.loc[keep]
    info.update(retained_minutes=len(retained),retained_days=retained.stamp.dt.normalize().nunique(),
                quarantine_percent=quarantine,threshold=threshold)
    if len(retained) < protocol['minimum_minutes'] or info['retained_days'] < protocol['minimum_days']:
        return None,info
    midpoint = retained.stamp.min()+(retained.stamp.max()-retained.stamp.min())/2
    left=retained.loc[retained.stamp.lt(midpoint),FEATURES].to_numpy(float)
    right=retained.loc[retained.stamp.ge(midpoint),FEATURES].to_numpy(float)
    half_shift = float(np.max(np.abs(np.median(left,axis=0)-np.median(right,axis=0))/scale)) if len(left) and len(right) else None
    review = quarantine > protocol['quarantine_review_percent'] or half_shift is None or half_shift > protocol['half_shift_review_z']
    info.update(supported=True,half_shift_z=half_shift,
                status='REFERENCE_REVIEW_REQUIRED' if review else 'SCREENED_NOT_APPROVED',
                hp2_median=float(med[2]),hp2_scale=float(scale[2]),lp2_median=float(med[3]),lp2_scale=float(scale[3]))
    return (med,scale,threshold),info


def load_machine(machine, start, end, receipt):
    paths=[]
    for root in CACHE_ROOTS:
        for path in sorted((root/'minutes').glob(machine+'_*.parquet')):
            day=pd.Timestamp(path.stem.split('_')[1])
            if start-pd.Timedelta(days=1) <= day < end:
                paths.append(path)
    if not paths:
        raise FileNotFoundError(f'No 08K/08L source-second cache for {machine}')
    frames=[]
    for path in paths:
        receipt[str(path.relative_to(ROOT))]=dict(sha256=sha(path),bytes=path.stat().st_size)
        frames.append(pd.read_parquet(path))
    data=pd.concat(frames,ignore_index=True)
    if data.duplicated(['machine','module','stamp']).any():
        raise ValueError('Overlapping source caches: deduplication must not be guessed')
    return data.sort_values(['module','stamp']).reset_index(drop=True)


def run(output=OUTPUT):
    start_clock=time.perf_counter()
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=True)
    # Pin the reused estimator contract; never silently claim configurable HPO.
    if protocol['quarantine_z'] != 8 or protocol['threshold_quantile'] != .995 or protocol['persistence_minutes'] != 3:
        raise ValueError('08K/08L estimator contract changed; version the helper and tests first')
    receipts={};profiles=[];burdens=[];scores=[];day_evidence=[];limits_evidence=[];cases=[];frozen_references=[]
    experiments=[dict(id='latest_mx'+m,machine=m,shadow_end=end) for m,end in protocol['latest_complete_day_exclusive'].items()]
    experiments+=protocol['case_runs']
    for spec in experiments:
        fit_start,shadow_start,shadow_end=complete_day_bounds(spec['shadow_end'],protocol['history_days'],protocol['shadow_days'])
        machine=spec['machine']
        data=load_machine(machine,fit_start,shadow_end,receipts)
        print(f"{spec['id']}: fit {fit_start.date()} to {shadow_start.date()} (exclusive), shadow to {shadow_end.date()} (exclusive)",flush=True)
        for module, group in data.groupby('module',sort=True):
            g=group.reset_index(drop=True)
            fit_mask=(g.stamp.ge(fit_start)&g.stamp.lt(shadow_start)).to_numpy()
            shadow_mask=(g.stamp.ge(shadow_start)&g.stamp.lt(shadow_end)).to_numpy()
            limits,slopes,variation,complete=dynamic_limits(g,fit_mask,protocol)
            phase,steady=classify_phase(g,limits,slopes,variation,complete,protocol)
            segment,days,seginfo=select_segment(g,fit_mask,protocol)
            if len(days):
                days['experiment']=spec['id'];days['machine']=machine;days['module']=module
                day_evidence.append(days)
            if limits is not None:
                for j,f in enumerate(FEATURES):
                    limits_evidence.append(dict(experiment=spec['id'],machine=machine,module=module,feature=f,
                        absolute_slope_limit=float(limits[0][j]),variation_limit=float(limits[1][j])))
            masks={'state_only':fit_mask, 'steady_reference':fit_mask & steady,
                   'segment_reference':segment,'segment_steady_reference':segment & steady}
            shadow=g.loc[shadow_mask].copy().reset_index(drop=True)
            shadow['phase']=phase[shadow_mask]
            known=(shadow.elapsed_known_seconds.eq(shadow.samples)&shadow.samples.gt(0))
            shadow['onset_observed']=known
            for variant,mask in masks.items():
                profile,info=fit_reference(g,mask,protocol)
                base=dict(experiment=spec['id'],machine=machine,module=int(module),variant=variant,
                          fit_start=str(fit_start),shadow_start=str(shadow_start),shadow_end=str(shadow_end),**seginfo)
                if 'segment' in variant and seginfo['supported_segments']>1 and info['supported']:
                    info['status']='MULTIPLE_REFERENCE_SEGMENTS_REVIEW'
                profiles.append({**base,**info})
                if profile is not None:
                    frozen_references.append(dict(experiment=spec['id'],machine=machine,module=int(module),variant=variant,
                        median=profile[0].tolist(),scale=profile[1].tolist(),threshold=profile[2],
                        fit_start=str(fit_start),fit_end_exclusive=str(shadow_start),status=info['status'],
                        namespace='LOCAL_EXPERIMENT_NOT_ACTIVE'))
                s=shadow[['stamp','eligible','phase','onset_observed','elapsed_min_seconds',*FEATURES]].copy()
                s['score']=np.nan;s['raw_flag']=False;s['persistent']=False;s['dominant']=''
                if profile is not None:
                    values=s[FEATURES].to_numpy(float)
                    z=np.abs((values-profile[0])/profile[1]);valid=s.eligible.to_numpy(bool)
                    s.loc[valid,'score']=np.max(z[valid],axis=1)
                    s.loc[valid,'dominant']=np.array(FEATURES)[np.argmax(z[valid],axis=1)]
                    s['raw_flag']=s.eligible & s.score.ge(profile[2])
                    s['persistent']=persistent_flags(s,s.raw_flag.to_numpy())
                eligible=int(s.eligible.sum());evaluated=int(s.score.notna().sum());persistent=int(s.persistent.sum())
                openings=int((s.persistent & ~s.persistent.shift(fill_value=False)).sum())
                transient=int((s.persistent & s.phase.eq('CHANGING_OR_SETTLING')).sum())
                unknown=int((s.persistent & s.phase.eq('UNKNOWN_HISTORY')).sum())
                raw_percent=100*int(s.raw_flag.sum())/evaluated if evaluated else None
                shadow_days=s.loc[s.score.notna(),'stamp'].dt.normalize().nunique()
                candidate_screen=(info['supported'] and info['status']=='SCREENED_NOT_APPROVED' and
                    shadow_days>=3 and evaluated>=200 and raw_percent is not None and raw_percent<=1)
                burdens.append({**base, 'reference_status':info['status'],'calendar_minutes':len(s),
                    'qualified_minutes':eligible,'evaluated_minutes':evaluated,'unsupported_qualified':eligible-evaluated,
                    'persistent_minutes':persistent,'openings':openings,'raw_flag_percent':raw_percent,
                    'persistent_percent':100*persistent/evaluated if evaluated else None,
                    'changing_persistent':transient,'unknown_history_persistent':unknown,
                    'steady_persistent':int((s.persistent & s.phase.eq('STEADY_CANDIDATE')).sum()),
                    'known_onset_qualified':int((s.eligible & known).sum()),'shadow_days_with_evaluation':shadow_days,
                    'candidate_screen_pass_not_approval':bool(candidate_screen)})
                s['experiment']=spec['id'];s['machine']=machine;s['module']=module;s['variant']=variant
                scores.append(s)
                if 'case_start' in spec and module==spec['module']:
                    cm=s.stamp.ge(spec['case_start']) & s.stamp.lt(spec['case_end']) & s.eligible
                    selected=s.loc[cm];hits=selected.loc[selected.persistent]
                    cases.append(dict(experiment=spec['id'],machine=machine,module=module,variant=variant,
                        case_start=spec['case_start'],case_end=spec['case_end'],qualified_minutes=len(selected),
                        evaluated_minutes=int(selected.score.notna().sum()),persistent_minutes=int(selected.persistent.sum()),
                        persistent_coverage_percent=100*selected.persistent.sum()/len(selected) if len(selected) else None,
                        first_persistent=str(hits.stamp.min()) if len(hits) else None,
                        changing_hits=int((selected.persistent & selected.phase.eq('CHANGING_OR_SETTLING')).sum()),
                        steady_hits=int((selected.persistent & selected.phase.eq('STEADY_CANDIDATE')).sum()),
                        reference_status=info['status']))
    p=pd.DataFrame(profiles);b=pd.DataFrame(burdens);s=pd.concat(scores,ignore_index=True)
    p.to_csv(output/'reference_readiness.csv',index=False);b.to_csv(output/'shadow_burden.csv',index=False)
    pd.DataFrame(cases).to_csv(output/'known_case_regression.csv',index=False)
    pd.concat(day_evidence,ignore_index=True).to_csv(output/'past_day_segment_evidence.csv',index=False)
    pd.DataFrame(limits_evidence).to_csv(output/'past_dynamic_limits.csv',index=False)
    s.to_parquet(output/'shadow_scores.parquet',index=False)
    # Same row cohort only: every variant must have a supported profile for the context.
    cohort=b.pivot(index=['experiment','machine','module'],columns='variant',values='evaluated_minutes')
    comparable=cohort.index[cohort.gt(0).all(axis=1)&cohort.nunique(axis=1).eq(1)]
    common=b.set_index(['experiment','machine','module']).loc[comparable].reset_index()
    totals=common.groupby('variant').agg(evaluated_minutes=('evaluated_minutes','sum'),
        persistent_minutes=('persistent_minutes','sum'),openings=('openings','sum'),
        changing_persistent=('changing_persistent','sum'),steady_persistent=('steady_persistent','sum'),
        unknown_history_persistent=('unknown_history_persistent','sum')).reset_index()
    totals['persistent_percent']=100*totals.persistent_minutes/totals.evaluated_minutes
    totals.to_csv(output/'matched_context_totals.csv',index=False)
    # Latest fleet only avoids double-counting case replays in headline rates.
    latest=common.loc[common.experiment.str.startswith('latest_')]
    latest_totals=latest.groupby('variant').agg(evaluated_minutes=('evaluated_minutes','sum'),
        persistent_minutes=('persistent_minutes','sum'),openings=('openings','sum')).reset_index()
    latest_totals['persistent_percent']=100*latest_totals.persistent_minutes/latest_totals.evaluated_minutes
    latest_totals.to_csv(output/'latest_matched_totals.csv',index=False)
    status=p.groupby(['variant','status']).size().rename('contexts').reset_index()
    status.to_csv(output/'reference_status_counts.csv',index=False)
    write_json(output/'input_receipt.json',receipts)
    write_json(output/'offline_reference_profiles.json',frozen_references)
    inherited={}
    for root,names in [(CACHE_ROOTS[0],['file_inventory.csv','ingestion_manifest.json','source_parity_qa.json']),
                       (CACHE_ROOTS[1],['additional_raw_inventory.csv','intake_manifest.json'])]:
        for name in names:
            path=root/name
            inherited[str(path.relative_to(ROOT))]=dict(sha256=sha(path),role='source-second provenance inherited from executed 08K/08L')
    write_json(output/'inherited_source_receipt.json',inherited)
    summary=dict(version=protocol['version'],protocol=protocol,experiment_count=len(experiments),
        contexts=len(p)//len(protocol['variants']),matched_contexts=len(comparable),
        latest_matched_contexts=latest[['experiment','machine','module']].drop_duplicates().shape[0],
        cache_files=len(receipts),raw_seconds_reused_not_reingested=True,source_grain='observed seconds -> qualified completed 1m',
        runtime_seconds=time.perf_counter()-start_clock,python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
        protocol_sha256=sha(PROTOCOL),score_sha256=sha(output/'shadow_scores.parquet'),
        offline_reference_sha256=sha(output/'offline_reference_profiles.json'),
        latest_matched=latest_totals.to_dict('records'),runtime_changed=False,active_changed=False,db_writes=False,server_access=False,
        warnings=['Retrospective inspected data, not a blind outer test','Unknown normal negatives: workload is not false-positive rate',
                  'Every qualified minute is still scored when a reference is supported; no startup suppression',
                  'No technician approval or Active profile registry lifecycle exercised',
                  '28-day fit includes source gaps; calendar days alone do not establish coverage',
                  protocol['cutoff_qa_correction']])
    write_json(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUTPUT)
    run(parser.parse_args().output)
