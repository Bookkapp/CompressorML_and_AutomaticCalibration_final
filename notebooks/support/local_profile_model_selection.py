"""Local-only, source-second intake and matched 1m challenger experiment.

No SQL, approval, worker or machine-control calls. Profiles are offline train-only
references, not copies of ACTIVE_FROZEN. Every model learns a predictive/normality
task without technician fault labels. The inspected future is diagnostic only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import polars as pl
import sklearn
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from notebooks.support.october_three_machine_calibration import (
    FEATURES, TAGS, fit_array, minute_day, persistent_flags,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'notebooks/outputs/local_profile_model_selection_v1'
PROTOCOL = ROOT / 'research/local_profile_model_selection_protocol_v1.json'
OCTOBER = ROOT / 'notebooks/outputs/october_three_machine_calibration_v1'
RAW = Path('C:/Users/Book/OneDrive/เดสก์ท็อป/HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings')
BASE = FEATURES[:7]
TARGETS = ['hp2', 'lp2', 'temphi', 'templo']
LANES = ['self_legacy', 'self_separate', 'arx', 'dpca', 'iforest']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def split_masks(stamps, protocol):
    return {name: stamps.ge(pd.Timestamp(protocol[key][0])) & stamps.lt(pd.Timestamp(protocol[key][1]))
            for name, key in [('fit', 'fit'), ('inner', 'inner_validation'),
                              ('calibration', 'threshold_calibration'), ('future', 'diagnostic_future')]}


def raw_day(path, machine):
    scan = pl.scan_parquet(path)
    columns = ['recorded_at', 'machine_number', 'Status'] + [
        f'{tag}_{m}' for m in range(1, 9) for tag in ['Hp_1st', 'Lp_1st', 'Hp_2nd', 'Lp_2nd',
                                                    'Valve', 'TempHi', 'TempLo', 'Status', 'Busy', 'SV']]
    df = scan.select(columns).collect()
    identities = df.get_column('machine_number').unique().to_list()
    if df.height and identities != [machine]:
        raise ValueError(f'Machine identity mismatch in {path}: {identities}, expected {machine}')
    numeric = [f'{tag}_{m}' for m in range(1, 9) for tag in TAGS.values()]
    df = df.with_columns(pl.col(numeric).cast(pl.Float64))
    frame = df.to_pandas()
    # Parquet stores datetime64[us], whereas the shared TXT adapter's elapsed
    # arithmetic expects nanoseconds. Normalize precision, not timestamp values.
    frame['recorded_at'] = frame.recorded_at.astype('datetime64[ns]')
    stamps = frame.recorded_at
    if stamps.isna().any() or not stamps.eq(stamps.dt.floor('s')).all():
        raise ValueError('This fast adapter requires valid whole-second source timestamps')
    return frame, stamps


def ingest(raw_root=RAW, output=OUTPUT):
    protocol = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'minutes').mkdir(exist_ok=True)
    (output / 'raw_cases').mkdir(exist_ok=True)
    records, tails, events = [], {}, []
    start = time.perf_counter()
    for machine in protocol['raw_additional_machines']:
        paths = sorted((raw_root / f'machine={machine}').glob('year=*/month=*/day=*/*.parquet'))
        for path in paths:
            date = '-'.join([path.parts[-4].split('=')[1], path.parts[-3].split('=')[1], path.parts[-2].split('=')[1]])
            if not protocol['period'][0] <= date < protocol['period'][1]:
                continue
            frame, stamps = raw_day(path, machine)
            # Event metadata retained; the benchmark does not need sampled onset trajectories.
            if len(frame):
                result = minute_day(frame, stamps, machine, tails, events, [])
                result.to_parquet(output / 'minutes' / f'{machine}_{date}.parquet', index=False)
            record = dict(machine=machine, date=date, file=str(path), sha256=sha(path),
                          rows=len(frame), first=str(stamps.min()), last=str(stamps.max()),
                          duplicate_rows=int(stamps.duplicated(keep=False).sum()),
                          nonmonotonic=int(stamps.diff().dt.total_seconds().lt(0).sum()))
            records.append(record)
            if machine == '057' and date == '2026-08-29':
                save_raw_module(frame, stamps, machine, 1, output / 'raw_cases/MX057_M1_20260829.parquet')
            if len(records) % 10 == 0:
                print(f'Additional raw files {len(records)} | {machine} {date} | {time.perf_counter()-start:.1f}s', flush=True)
    pd.DataFrame(records).to_csv(output / 'additional_raw_inventory.csv', index=False)
    pd.DataFrame(events).to_parquet(output / 'additional_cold_entry_events.parquet', index=False)
    json_write(output / 'intake_manifest.json', dict(source_root=str(raw_root), files=len(records),
               raw_rows=sum(r['rows'] for r in records), elapsed_seconds=time.perf_counter()-start,
               source_clock=protocol['clock'], code_sha256=sha(__file__), protocol_sha256=sha(PROTOCOL),
               strict_seconds=True, changed_source=False))
    print(f'Intake complete: {len(records)} day-files', flush=True)


def save_raw_module(frame, stamps, machine, module, path):
    out = pd.DataFrame({f: pd.to_numeric(frame[f'{tag}_{module}'], errors='coerce') for f, tag in TAGS.items()})
    out['stamp'] = stamps
    for tag in ['Status', 'Busy', 'SV']:
        out[tag.lower()] = frame[f'{tag}_{module}']
    out['compressor_status'] = frame.Status
    out['machine'], out['module'] = machine, module
    out.to_parquet(path, index=False)


def load_dataset(output=OUTPUT):
    protocol = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    paths = list((output / 'minutes').glob('*.parquet'))
    paths += [p for p in (OCTOBER / 'minutes').glob('*.parquet')
              if protocol['period'][0] <= p.stem.split('_', 1)[1] < protocol['period'][1]]
    frames = [pd.read_parquet(p) for p in paths]
    data = pd.concat(frames, ignore_index=True)
    data['machine'] = data.machine.astype(str).str.zfill(3)
    data['module'] = data.module.astype('int8')
    data = data.sort_values(['machine', 'module', 'stamp']).reset_index(drop=True)
    if data.duplicated(['machine', 'module', 'stamp']).any():
        raise ValueError('Duplicate source families / machine-module-minute keys')
    return data


def fit_profiles(data, protocol):
    rows, profiles, fit_keep = [], {}, pd.Series(False, index=data.index)
    masks = split_masks(data.stamp, protocol)
    for key, group in data.groupby(['machine', 'module'], sort=True):
        train = group.loc[masks['fit'] & data.eligible]
        info = dict(machine=key[0], module=int(key[1]), fit_rows=len(train),
                    fit_days=train.stamp.dt.normalize().nunique(),
                    first=str(group.stamp.min()), last=str(group.stamp.max()))
        if len(train) < protocol['minimum_fit_minutes'] or info['fit_days'] < protocol['minimum_fit_days']:
            rows.append(info | dict(status='INSUFFICIENT_FIT'))
            continue
        med, scale, threshold, quarantine = fit_array(train)
        values = train[FEATURES].to_numpy(float)
        first_med = np.median(values, axis=0)
        first_scale = np.maximum.reduce([1.4826*np.median(abs(values-first_med), axis=0),
                      (np.quantile(values,.75,axis=0)-np.quantile(values,.25,axis=0))/1.349,
                      np.array([1 if f=='valve' else .1 for f in FEATURES])])
        keep = np.max(abs((values-first_med)/first_scale),axis=1) <= protocol['quarantine_z']
        retained = train.loc[keep]
        if len(retained) < protocol['minimum_fit_minutes'] or retained.stamp.dt.normalize().nunique() < protocol['minimum_fit_days']:
            rows.append(info | dict(status='INSUFFICIENT_AFTER_QUARANTINE', quarantine_pct=quarantine))
            continue
        half_cut = pd.Timestamp(protocol['fit'][0]) + (pd.Timestamp(protocol['fit'][1])-pd.Timestamp(protocol['fit'][0]))/2
        halves = [retained.loc[retained.stamp.lt(half_cut), FEATURES], retained.loc[retained.stamp.ge(half_cut), FEATURES]]
        half_shift = np.max(abs((halves[1].median().to_numpy()-halves[0].median().to_numpy())/scale)) if all(len(x) for x in halves) else np.inf
        review = quarantine > 100*protocol['profile_review_quarantine_fraction'] or half_shift > protocol['profile_review_half_shift_z']
        status = 'REFERENCE_REVIEW_REQUIRED' if review else 'SCREENED_CANDIDATE_NOT_APPROVED'
        profiles[key] = dict(median=med, scale=scale, threshold=threshold, status=status)
        fit_keep.loc[retained.index] = True
        for f, center, spread in zip(FEATURES, med, scale):
            info[f'{f}_median'], info[f'{f}_scale'] = float(center), float(spread)
        rows.append(info | dict(status=status, retained_rows=len(retained), retained_days=retained.stamp.dt.normalize().nunique(),
                     quarantine_pct=quarantine, max_half_shift_z=float(half_shift), legacy_threshold=threshold))
    return profiles, pd.DataFrame(rows), fit_keep


def relative_lags(data, profiles, fit_keep):
    result = data.copy()
    for f in FEATURES:
        result[f'z_{f}'] = np.nan
    result['profile_status'] = 'INSUFFICIENT_FIT'
    result['legacy_threshold'] = np.nan
    result['fit_keep'] = fit_keep
    for key, indexes in result.groupby(['machine', 'module']).groups.items():
        if key not in profiles:
            continue
        p = profiles[key]
        result.loc[indexes, [f'z_{f}' for f in FEATURES]] = (result.loc[indexes, FEATURES].to_numpy(float)-p['median'])/p['scale']
        result.loc[indexes, 'profile_status'] = p['status']
        result.loc[indexes, 'legacy_threshold'] = p['threshold']
    result['self_score'] = result[[f'z_{f}' for f in FEATURES]].abs().max(axis=1, skipna=False)
    result['dominant_feature'] = result[[f'z_{f}' for f in FEATURES]].abs().fillna(-1).idxmax(axis=1).str.removeprefix('z_')
    # Do not bridge manual, bypass, missing windows or machine/module boundaries.
    g = result.groupby(['machine', 'module'], sort=False)
    previous_time = g.stamp.shift(1)
    contiguous = result.eligible & g.eligible.shift(1, fill_value=False) & result.stamp.sub(previous_time).eq(pd.Timedelta(minutes=1))
    boundary = ~contiguous
    result['segment'] = boundary.cumsum()
    g = result.groupby('segment', sort=False)
    lag_cols = []
    for lag in (1, 2):
        result[f'lag{lag}_fit_keep'] = g.fit_keep.shift(lag, fill_value=False)
        for f in BASE:
            name = f'lag{lag}_z_{f}'
            result[name] = g[f'z_{f}'].shift(lag)
            lag_cols.append(name)
    result['matched'] = result.eligible & result[lag_cols].notna().all(axis=1) & result.self_score.notna()
    return result, lag_cols


def balanced_indices(frame, mask, maximum, seed):
    rng = np.random.default_rng(seed)
    indexes = []
    for _, group in frame.loc[mask].groupby(['machine', 'module'], sort=True):
        indexes.extend(rng.choice(group.index, min(maximum, len(group)), replace=False))
    return np.sort(indexes)


def train_models(frame, lag_cols, protocol, exclude_machine=None):
    masks = split_masks(frame.stamp, protocol)
    fit_mask = masks['fit'] & frame.matched & frame.fit_keep & frame.lag1_fit_keep & frame.lag2_fit_keep
    inner_mask = masks['inner'] & frame.matched
    # Review-marked references stay visible in diagnostics, not silently treated as healthy training.
    fit_mask &= frame.profile_status.eq('SCREENED_CANDIDATE_NOT_APPROVED')
    inner_mask &= frame.profile_status.eq('SCREENED_CANDIDATE_NOT_APPROVED')
    if exclude_machine is not None:
        fit_mask &= frame.machine.ne(exclude_machine)
        inner_mask &= frame.machine.ne(exclude_machine)
    fit_ids = balanced_indices(frame, fit_mask, protocol['maximum_shared_fit_rows_per_profile'], protocol['seed'])
    val_ids = balanced_indices(frame, inner_mask, 1000, protocol['seed'])
    if len(fit_ids) < 200 or len(val_ids) < 200:
        raise ValueError('Insufficient screened fit/inner rows for shared candidate')
    x = frame.loc[fit_ids, lag_cols].to_numpy(float)
    y = frame.loc[fit_ids, [f'z_{f}' for f in TARGETS]].to_numpy(float)
    scaler = StandardScaler().fit(x)
    xt = scaler.transform(x)
    xv = scaler.transform(frame.loc[val_ids, lag_cols].to_numpy(float))
    yv = frame.loc[val_ids, [f'z_{f}' for f in TARGETS]].to_numpy(float)
    trials = []
    for alpha in protocol['ridge_alphas_inner_only']:
        model = Ridge(alpha=alpha).fit(xt, y)
        error = np.square(model.predict(xv)-yv).mean(axis=1)
        # Equal profile weights prevent a long-history module dominating alpha selection.
        row_errors = frame.loc[val_ids, ['machine', 'module']].copy()
        row_errors['mse'] = error
        trials.append(dict(alpha=alpha, mean_profile_inner_mse=float(row_errors.groupby(['machine','module']).mse.mean().mean())))
    alpha = min(trials, key=lambda t:t['mean_profile_inner_mse'])['alpha']
    arx = Ridge(alpha=alpha).fit(xt,y)
    residual = arx.predict(xt)-y
    residual_med = np.median(residual, axis=0)
    residual_scale = np.maximum(1.4826*np.median(abs(residual-residual_med), axis=0), .1)
    dpca_cols = [f'z_{f}' for f in BASE] + lag_cols
    dpca_scaler = StandardScaler().fit(frame.loc[fit_ids, dpca_cols])
    xp = dpca_scaler.transform(frame.loc[fit_ids, dpca_cols])
    dpca = PCA(n_components=protocol['dpca_variance_fraction'], svd_solver='full').fit(xp)
    isolation = IsolationForest(n_estimators=protocol['iforest']['n_estimators'],
                    max_samples=min(protocol['iforest']['max_samples'],len(fit_ids)),
                    contamination='auto', random_state=protocol['iforest']['seed'], n_jobs=1).fit(xp)
    bundle = dict(arx=arx, arx_scaler=scaler, residual_median=residual_med, residual_scale=residual_scale,
                  dpca=dpca, dpca_scaler=dpca_scaler, iforest=isolation,
                  lag_columns=lag_cols, dpca_columns=dpca_cols, targets=TARGETS,
                  status='SHADOW_ONLY_NOT_ACTIVE', excluded_machine=exclude_machine)
    return bundle, dict(fit_rows=len(fit_ids), inner_rows=len(val_ids), ridge_alpha=alpha,
                       ridge_trials=trials, dpca_components=int(dpca.n_components_),
                       dpca_explained_variance=float(dpca.explained_variance_ratio_.sum()),
                       fit_machines=sorted(frame.loc[fit_ids,'machine'].unique().tolist()),
                       fit_profiles=int(frame.loc[fit_ids,['machine','module']].drop_duplicates().shape[0]))


def score_models(bundle, frame):
    x = frame[bundle['lag_columns']].to_numpy(float)
    y = frame[[f'z_{f}' for f in bundle['targets']]].to_numpy(float)
    residual = bundle['arx'].predict(bundle['arx_scaler'].transform(x))-y
    arx = np.max(abs((residual-bundle['residual_median'])/bundle['residual_scale']),axis=1)
    xp = bundle['dpca_scaler'].transform(frame[bundle['dpca_columns']])
    reconstruction = bundle['dpca'].inverse_transform(bundle['dpca'].transform(xp))
    dpca = np.square(xp-reconstruction).sum(axis=1)  # Q/SPE, not label probability
    iforest = -bundle['iforest'].score_samples(xp)  # Ignore its generic contamination cut.
    return dict(arx=arx, dpca=dpca, iforest=iforest)


def apply_thresholds(frame, protocol):
    threshold_rows = []
    cal_mask = split_masks(frame.stamp, protocol)['calibration']
    for key, group in frame.groupby(['machine','module']):
        cal = group.loc[cal_mask & frame.matched]
        row = dict(machine=key[0], module=int(key[1]), calibration_rows=len(cal),
                   calibration_days=cal.stamp.dt.normalize().nunique())
        sufficient = len(cal) >= protocol['minimum_threshold_minutes'] and row['calibration_days'] >= 3
        for lane in LANES:
            if lane == 'self_legacy':
                cut = group.legacy_threshold.iloc[0]
            elif sufficient:
                score_name = 'self_score' if lane == 'self_separate' else lane+'_score'
                cut = float(cal[score_name].quantile(protocol['threshold_quantile']))
            else:
                cut = np.nan
            row[lane+'_threshold'] = cut
            frame.loc[group.index, lane+'_threshold'] = cut
        row['status'] = 'CALIBRATED_SHADOW_ONLY' if sufficient else 'INSUFFICIENT_PAST_THRESHOLD_BLOCK'
        threshold_rows.append(row)
    return frame, pd.DataFrame(threshold_rows)


def flag_results(frame):
    out = frame.copy()
    for lane in LANES:
        name = 'self_score' if lane.startswith('self_') else lane+'_score'
        out[lane+'_raw_flag'] = out[name].ge(out[lane+'_threshold']) & out[lane+'_threshold'].notna()
        out[lane+'_persistent'] = False
        for _, indexes in out.groupby(['machine','module']).groups.items():
            block = out.loc[indexes]
            out.loc[indexes,lane+'_persistent'] = persistent_flags(block, block[lane+'_raw_flag'].to_numpy())
    return out


def summary_rows(scored, protocol):
    future = scored.loc[split_masks(scored.stamp, protocol)['future']]
    rows = []
    for (machine,module), g in future.groupby(['machine','module']):
        for lane in LANES:
            supported = g[lane+'_threshold'].notna()
            b = g.loc[supported]
            flags = b[lane+'_persistent']
            opening = flags & (~flags.shift(1,fill_value=False) | b.stamp.diff().ne(pd.Timedelta(minutes=1)))
            rows.append(dict(machine=machine, module=int(module), lane=lane, rows=len(b),
                        raw_flags=int(b[lane+'_raw_flag'].sum()), persistent_flags=int(flags.sum()),
                        persistent_pct=float(flags.mean()*100) if len(b) else np.nan,
                        openings=int(opening.sum()), qualified_days=b.stamp.dt.normalize().nunique()))
    return pd.DataFrame(rows)


def case_regression(scored):
    cases = [('057',1,'2026-08-29 04:06','2026-08-29 22:50'),
             ('080',6,'2026-09-07 12:23:28','2026-09-08 00:00')]
    rows=[]
    for machine,module,start,end in cases:
        start,end=pd.Timestamp(start),pd.Timestamp(end)
        b=scored.loc[scored.machine.eq(machine)&scored.module.eq(module)&scored.stamp.ge(start.ceil('min'))&scored.stamp.lt(end)]
        for lane in LANES:
            supported=b.loc[b[lane+'_threshold'].notna()]
            flagged=supported.loc[supported[lane+'_persistent']]
            first=flagged.stamp.min() if len(flagged) else pd.NaT
            # Score available only once the one-minute window is complete.
            decision=first+pd.Timedelta(minutes=1) if pd.notna(first) else pd.NaT
            rows.append(dict(machine=machine,module=module,lane=lane,case_start=str(start),case_end=str(end),
                        matched_case_rows=len(b),supported_rows=len(supported),persistent_rows=len(flagged),
                        coverage_pct=float(len(flagged)/len(supported)*100) if len(supported) else None,
                        first_flag_window=str(first),decision_time=str(decision),
                        diagnostic_delay_minutes=(decision-start).total_seconds()/60 if pd.notna(decision) else None))
    return pd.DataFrame(rows)


def parity_samples(raw_root=RAW, output=OUTPUT):
    from datetime import datetime, timezone
    from apps.api.app.qualified_windows import build_completed_windows, WindowPolicy
    comparisons=0
    for machine in ['029','041','057','070','118','119']:
        path=next(iter(sorted((raw_root/f'machine={machine}').glob('year=*/month=*/day=*/*.parquet'))),None)
        if path is None: continue
        frame,stamps=raw_day(path,machine)
        if not len(frame): continue
        # Include beginnings and actual manual/quality boundaries, not clean points only.
        indexes={0, len(frame)//2, max(0,len(frame)-120)}
        manual=frame[[f'Busy_{m}' for m in range(1,9)]].eq(1).any(axis=1)
        if manual.any(): indexes.add(int(np.flatnonzero(manual)[0]))
        for pos in sorted(indexes):
            minute=stamps.iloc[pos].floor('min')
            pick=stamps.ge(minute)&stamps.lt(minute+pd.Timedelta(minutes=2))
            chunk=frame.loc[pick].copy()
            expected=build_completed_windows(chunk.to_dict('records'),as_of=datetime(2026,10,2,tzinfo=timezone.utc),policy=WindowPolicy('Asia/Bangkok'))
            actual=minute_day(chunk,chunk.recorded_at,machine,{},[],[])
            for w in expected:
                point=actual.loc[actual.module.eq(w.module)&actual.stamp.eq(w.window_start)].iloc[0]
                if bool(point.eligible)!=w.eligible: raise AssertionError('Window eligibility parity failed')
                if w.eligible:
                    if not np.allclose([point[f] for f in FEATURES],[w.features[f] for f in FEATURES],atol=1e-8,rtol=1e-10):
                        raise AssertionError('Feature parity failed')
                comparisons+=1
    return comparisons


def benchmark(output=OUTPUT, raw_root=RAW):
    started=time.perf_counter()
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=True)
    data=load_dataset(output)
    print(f'Loaded {len(data):,} calendar module-minute slots',flush=True)
    profiles, profile_table, fit_keep=fit_profiles(data,protocol)
    profile_table.to_csv(output/'profile_readiness.csv',index=False)
    frame,lag_cols=relative_lags(data,profiles,fit_keep)
    frame=frame.loc[frame.matched].copy()
    # Frozen profiles are inspectable in a non-Active artifact.
    bundle, model_info=train_models(frame,lag_cols,protocol)
    print(f'Shared models trained on {model_info["fit_rows"]:,} rows, {model_info["fit_profiles"]} screened references',flush=True)
    t=time.perf_counter()
    for lane,values in score_models(bundle,frame).items(): frame[lane+'_score']=values
    score_seconds=time.perf_counter()-t
    frame,thresholds=apply_thresholds(frame,protocol)
    scored=flag_results(frame)
    burden=summary_rows(scored,protocol)
    cases=case_regression(scored)
    lomo_rows=[]
    for held in model_info['fit_machines']:
        sub=scored.loc[scored.machine.eq(held)].copy()
        other_bundle,other_info=train_models(frame,lag_cols,protocol,exclude_machine=held)
        for lane,values in score_models(other_bundle,sub).items(): sub[lane+'_score']=values
        sub,_=apply_thresholds(sub,protocol)
        lomo_rows.append(summary_rows(flag_results(sub),protocol).assign(excluded_machine=held))
        print(f'Adapted LOMO {held}: shared fit excludes held machine; local past reference/calibration permitted',flush=True)
    joblib.dump(bundle,output/'shadow_model_bundle.joblib')
    joblib.dump(profiles,output/'offline_reference_profiles.joblib')
    check=joblib.load(output/'shadow_model_bundle.joblib')
    sample=frame.head(1000)
    before,after=score_models(bundle,sample),score_models(check,sample)
    reload_error=max(float(np.max(abs(before[l]-after[l]))) for l in before)
    if reload_error!=0: raise AssertionError('Artifact score parity failed')
    thresholds.to_csv(output/'thresholds.csv',index=False)
    burden.to_csv(output/'future_burden_by_context.csv',index=False)
    cases.to_csv(output/'case_regression.csv',index=False)
    pd.concat(lomo_rows,ignore_index=True).to_csv(output/'adapted_lomo_burden.csv',index=False)
    scored.to_parquet(output/'matched_scores.parquet',index=False)
    source_summary=data.groupby('machine').agg(calendar_slots=('stamp','size'),observed_minutes=('samples',lambda s:int(s.gt(0).sum())),
                        qualified_minutes=('eligible','sum'),first=('stamp','min'),last=('stamp','max')).reset_index()
    source_summary.to_csv(output/'machine_coverage.csv',index=False)
    # Within-context, demean by daily median: correlation still association, not causal proof.
    corr_rows=[]
    for (machine,module),g in data.loc[data.eligible].groupby(['machine','module']):
        train=g.loc[split_masks(g.stamp,protocol)['fit']]
        if len(train)<200:continue
        centered=train[BASE]-train.groupby(train.stamp.dt.normalize())[BASE].transform('median')
        matrix=centered.corr(method='spearman')
        for a,b in [('hp2','lp2'),('lp2','templo'),('valve','lp2'),('hp1','hp2')]:
            corr_rows.append(dict(machine=machine,module=int(module),pair=f'{a}/{b}',rho=matrix.loc[a,b],n=len(train)))
    pd.DataFrame(corr_rows).to_csv(output/'train_within_day_correlations.csv',index=False)
    parity=parity_samples(raw_root,output)
    artifacts=['shadow_model_bundle.joblib','offline_reference_profiles.joblib','profile_readiness.csv','thresholds.csv',
               'future_burden_by_context.csv','case_regression.csv','adapted_lomo_burden.csv','machine_coverage.csv','train_within_day_correlations.csv']
    manifest=dict(version=protocol['version'],status='SHADOW_ONLY_NOT_ACTIVE',protocol=protocol,
                protocol_sha256=sha(PROTOCOL),code_sha256=sha(__file__),
                python=platform.python_version(),sklearn=sklearn.__version__,pandas=pd.__version__,
                source_clock=protocol['clock'],derived_minutes=len(data),matched_rows=len(scored),
                offline_supported_profiles=len(profiles),profile_status_counts=profile_table.status.value_counts().to_dict(),
                models=model_info,model_score_seconds=score_seconds,
                seconds_per_1000_matched_rows=score_seconds*1000/len(frame),
                strict_actual_source_window_comparisons=parity,artifact_reload_max_abs_error=reload_error,
                total_runtime_seconds=time.perf_counter()-started,
                source_families=['October ZIP raw-second strict minute cache (017/024/080)',
                                 'Original raw-second Parquet (029/041/057/070/118/119)'],
                zip_intake_manifest_sha256=sha(OCTOBER/'ingestion_manifest.json'),
                additional_intake_manifest_sha256=sha(output/'intake_manifest.json'),
                hashes={name:sha(output/name) for name in artifacts},
                decision='Keep local frozen robust-z + 3-adjacent-minute primary. ARX/DPCA/IF are non-voting comparison artifacts; improve reference qualification before any ML promotion.',
                limits=['No verified healthy negative set: flag burden is not false-positive rate.',
                        'Previously inspected cases and history: diagnostic regression, not independent model accuracy.',
                        'Self legacy and separate-calibration policies are intentionally distinct.',
                        'Adapted LOMO allows held-unit past profiles and calibration, not zero-shot generalization.',
                        'No transition-response model fitted; manual evidence retained, steady models abstain there.',
                        'No genuine Active or three-day registry lifecycle was executed; no approval/DB/Server writes.',
                        'One-minute means do not preserve all second-level transients; source-second evidence is separate.'])
    json_write(output/'summary.json',manifest)
    print(json.dumps({k:manifest[k] for k in ['matched_rows','profile_status_counts','models','strict_actual_source_window_comparisons','total_runtime_seconds']},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['ingest','benchmark'])
    parser.add_argument('--raw-root',type=Path,default=RAW)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.action=='ingest':ingest(args.raw_root,args.output)
    else:benchmark(args.output,args.raw_root)
