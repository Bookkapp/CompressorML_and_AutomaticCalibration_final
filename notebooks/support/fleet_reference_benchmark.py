"""Asset-held-out, time-separated historical Fleet diagnostics, not accuracy.

Sparse scenarios vary FIT history only. All require a separate seven-day target
threshold period, explicitly NOT a pure one-day cold-start experiment.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import gc
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from notebooks.support.fleet_reference_study import OUT,PROTOCOL,MACHINES,write_json
from apps.api.app.fleet_assistance import FEATURES,VERSION,fit_local,pool,scores,self_scores,calibrate,robust_location


def dataset(machine):
    paths=sorted((OUT/'minutes').glob(machine+'_*.parquet'))
    if not paths:raise ValueError('Run checksum-reconciled intake before benchmark')
    columns=['time','module','quality','context',*FEATURES]
    data=pd.concat([pd.read_parquet(p,columns=columns) for p in paths],ignore_index=True).sort_values(['module','time']).reset_index(drop=True)
    data['context']=data.context.astype('category')
    return data


def steady(frame,scale):
    valid=frame.quality&frame.context.ne('UNSUPPORTED')&frame.time.diff().dt.total_seconds().eq(60)&frame.context.eq(frame.context.shift())
    physical=frame[list(FEATURES)]
    movement=(physical.rolling(5,min_periods=5).max()-physical.rolling(5,min_periods=5).min()).div(scale).max(axis=1)
    continuous=valid.astype(int).rolling(4,min_periods=4).sum().eq(4)
    return movement.le(PROTOCOL['stability_limit'])&continuous&frame.quality


def fit(frame,machine,module,context,start,end):
    selected=frame[(frame.time>=start)&(frame.time<end)&frame.quality&frame.context.eq(context)]
    if len(selected)<8:return None
    _,scale=robust_location(selected[list(FEATURES)])
    eligible=steady(frame,scale)&frame.context.eq(context)&frame.time.ge(start)&frame.time.lt(end)
    rows=frame[eligible]
    # Parquet datetime may be microseconds or nanoseconds. Use calendar minutes
    # rather than assuming integer timestamp units when selecting spaced points.
    sampled=rows[rows.time.dt.minute.mod(15).eq(0)]
    if len(sampled)<8:return None
    model=fit_local(sampled[list(FEATURES)],machine=machine,module=module,context=context,reference_end=end)
    model.update(reference_start=start,reference_days=int(rows.time.dt.normalize().nunique()),
                 reference_minutes=len(rows),raw_fit_points=len(sampled),source_family='checksum-reconciled canonical ZIP',
                 reference_health='UNREVIEWED_OPERATING_DATA',regime_scope='SV-conditioned stable proposal; multimodality requires review')
    return model


def persistence(flags,times):
    flags=np.asarray(flags,bool);times=np.asarray(times,dtype='datetime64[ns]')
    continuity=np.r_[False,np.diff(times)==np.timedelta64(1,'m')]
    consecutive=np.zeros(len(flags),int)
    for i,flag in enumerate(flags):
        if flag:consecutive[i]=1+(consecutive[i-1] if i and continuity[i] else 0)
    confirmed=consecutive>=3
    onsets=confirmed&~np.r_[False,confirmed[:-1]&continuity[1:]]
    return int(confirmed.sum()),int(onsets.sum())


def event_split(at):
    for name in ('reference','calibration','diagnostic'):
        start,end=PROTOCOL[name]
        if pd.Timestamp(start)<=at<pd.Timestamp(end):return name
    return 'outside_evaluation'


def transitions(frame,events,models,machine):
    """No recovery-conditioned filtering: keep censored/unsettled transitions."""
    metrics=[];curves=[];points=(0,1,2,5,10,20,30,60,90,120)
    if not len(events):return metrics,curves
    for module in range(1,9):
        data=frame[frame.module.eq(module)].set_index('time').sort_index()
        module_events=events[events.module.eq(module)&events.witness_usable].sort_values('time')
        sv=module_events[module_events.event_type.eq('SV_CHANGED')].copy()
        valve=module_events[module_events.event_type.eq('VALVE_CHANGED')].copy()
        if len(valve):
            step=pd.to_numeric(valve.after,errors='coerce')-pd.to_numeric(valve.before,errors='coerce')
            valve=valve[step.abs().ge(3)].copy()
            # Fixed bounded, non-overlapping research examples. Every original
            # command remains in the day partitions; no operational suppression.
            valve=valve.drop_duplicates(subset=['module','event_type','time'])
            keep=[];last=None
            for row in valve.itertuples():
                if last is None or row.time-last>=pd.Timedelta(hours=2):keep.append(row.Index);last=row.time
            valve=valve.loc[keep]
        choices=pd.concat([sv,valve],ignore_index=True).sort_values('time')
        for n,event in enumerate(choices.itertuples()):
            at=event.time.ceil('min');stop=choices.iloc[n+1].time if n+1<len(choices) else at+pd.Timedelta(minutes=121)
            before=data.loc[at-pd.Timedelta(minutes=6):event.time.floor('min')-pd.Timedelta(minutes=1)]
            after=data.loc[at:min(at+pd.Timedelta(minutes=120),stop.ceil('min')-pd.Timedelta(minutes=1))].copy()
            valve_event=event.event_type=='VALVE_CHANGED'
            step=float(event.after)-float(event.before) if valve_event else None
            band='3_9' if valve_event and abs(step)<10 else '10_29' if valve_event and abs(step)<30 else '30_PLUS'
            direction=(f'VALVE_{"UP" if step>0 else "DOWN"}_STEP_{band}' if valve_event else f'{event.before.upper()}_TO_{event.after.upper()}')
            record={'machine':machine,'module':module,'time':event.time.isoformat(),'direction':direction,
                    'split':event_split(event.time),
                    'settling_minutes':None,'response_delay_minutes':None,'duration_minutes':0,
                    'status':'INSUFFICIENT_PRE_EVENT','terminal_local_z':None,'health_label':'UNREVIEWED',
                    'event_type':event.event_type,'valve_step':step,'causal_interpretation':False}
            if len(before)<5 or not before.quality.all() or before.context.eq('UNSUPPORTED').any():
                metrics.append(record);continue
            baseline=before[list(FEATURES)].median().to_numpy()
            context=str(before.context.iloc[-1]) if valve_event else 'SV_ON' if event.after in ('on','1','true') else 'SV_OFF'
            if valve_event:direction=context+'_'+direction;record['direction']=direction
            model=models.get((machine,module,context))
            scale=np.asarray(model['scale']) if model else np.maximum(.1,before[list(FEATURES)].std().fillna(.1).to_numpy())
            # End at the first missing minute, bad quality or incompatible controls.
            contiguous=after.quality&after.context.eq(context)
            contiguous &= pd.Series(after.index,index=after.index).diff().dt.total_seconds().fillna(60).eq(60)
            bad=np.flatnonzero(~contiguous.to_numpy())
            if len(bad):after=after.iloc[:bad[0]]
            record['duration_minutes']=len(after)
            if not len(after):record['status']='NO_COMPLETE_POST_EVENT';metrics.append(record);continue
            delta=(after[list(FEATURES)].to_numpy()-baseline)
            response=np.flatnonzero(np.max(np.abs(delta)/scale,axis=1)>=.5)
            if len(response):
                response_at=int(response[0]);record['response_delay_minutes']=response_at
                for j in range(max(4,response_at+4),len(after)):
                    if np.max(np.ptp(after[list(FEATURES)].iloc[j-4:j+1].to_numpy(),axis=0)/scale)<=.35:
                        record['settling_minutes']=j;break
            record['status']='SETTLED_OBSERVATION' if record['settling_minutes'] is not None else (
                'NO_MATERIAL_RESPONSE_OBSERVED' if not len(response) else 'CENSORED_OR_UNSETTLED')
            last=after[list(FEATURES)].iloc[-5:].median().to_numpy()
            record.update(terminal_delta_hp2=float(last[2]-baseline[2]),terminal_delta_lp2=float(last[3]-baseline[3]),
                          overshoot_hp2=float(np.max(np.abs(delta[:,2]))),overshoot_lp2=float(np.max(np.abs(delta[:,3]))))
            if model:record['terminal_local_z']=float(self_scores([last],model)[0])
            metrics.append(record)
            # Fit-time curves exclusively use Reference events and observed data.
            if record['split']=='reference' and before.index.min()>=pd.Timestamp(PROTOCOL['reference'][0]):
                for elapsed in points:
                    if elapsed>=len(delta):continue
                    if after.index[elapsed]>=pd.Timestamp(PROTOCOL['reference'][1]):continue
                    curves.append({'machine':machine,'module':module,'direction':direction,'elapsed':elapsed,
                                  'time':event.time.isoformat(),**dict(zip(FEATURES,delta[elapsed]))})
    return metrics,curves


def run():
    started=time.perf_counter();manifest=json.loads((OUT/'intake_manifest.json').read_text(encoding='utf-8'))
    if len(manifest['files'])<555:raise ValueError('The full 555 committed-file intake must finish first')
    source_hashes=sorted((r['machine'],r['date'],r['source_sha256']) for r in manifest['files'])
    import hashlib
    core_hash=hashlib.sha256(Path(fit_local.__code__.co_filename).read_bytes()).hexdigest()
    benchmark_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    study_id=hashlib.sha256(json.dumps([PROTOCOL,source_hashes,core_hash,benchmark_hash,
                                      manifest['version'],manifest['code_sha256'],
                                      [r['minute_parquet_sha256'] for r in manifest['files']]],sort_keys=True).encode()).hexdigest()[:24]
    models={};coverage=[]
    for machine in MACHINES:
        data=dataset(machine)
        for module in range(1,9):
            frame=data[data.module.eq(module)]
            row={'machine':machine,'module':module,'source_days':int(frame.time.dt.normalize().nunique()),
                 'observed_minutes':len(frame),'quality_minutes':int(frame.quality.sum()),
                 'supported_control_minutes':int((frame.quality&frame.context.ne('UNSUPPORTED')).sum()),
                 'sv_on_minutes':int((frame.quality&frame.context.eq('SV_ON')).sum()),
                 'sv_off_minutes':int((frame.quality&frame.context.eq('SV_OFF')).sum())}
            coverage.append(row)
            for context in ('SV_OFF','SV_ON'):
                model=fit(frame,machine,module,context,*PROTOCOL['reference'])
                if model:models[machine,module,context]=model
        del data;gc.collect()
        print(json.dumps({'phase':'reference_fit','machine':machine,'models':len(models)}),flush=True)
    variants=[];daily=[];candidate_models=[];metrics=[];curves=[]
    for machine in MACHINES:
        data=dataset(machine)
        event_paths=sorted((OUT/'events').glob(machine+'_*.parquet'))
        events=pd.concat([pd.read_parquet(p,filters=[('event_type','in',['SV_CHANGED','VALVE_CHANGED'])]) for p in event_paths],ignore_index=True)
        machine_metrics,machine_curves=transitions(data,events,models,machine);metrics.extend(machine_metrics);curves.extend(machine_curves)
        for module in range(1,9):
            frame=data[data.module.eq(module)].reset_index(drop=True)
            for context in ('SV_OFF','SV_ON'):
                for days in PROTOCOL['sparse_days']:
                    start=(pd.Timestamp(PROTOCOL['reference'][1])-pd.Timedelta(days=days)).isoformat()[:10]
                    local=fit(frame,machine,module,context,start,PROTOCOL['reference'][1])
                    receipt={'machine':machine,'module':module,'context':context,'fit_days_requested':days,
                             'status':'INSUFFICIENT_FIT','source_role_verified':False,'activation_eligible':False}
                    if not local:variants.append(receipt);continue
                    eligibility=steady(frame,np.asarray(local['scale']))&frame.context.eq(context)
                    calibration=frame[eligibility&frame.time.ge(PROTOCOL['calibration'][0])&frame.time.lt(PROTOCOL['calibration'][1])]
                    donors=[v for (m,mod,c),v in models.items() if m!=machine and mod==module and c==context]
                    assisted=pool(local,donors,research=True)
                    relationship=pool(local,donors,research=True,parameter='relationship')
                    receipt.update(fit_points=local['n'],fit_days_observed=local['reference_days'],
                        donor_machines=assisted['donor_machines'],fleet_weight=assisted['fleet_weight'],
                        transfer_receipts=assisted['transfer_receipts'],calibration_points=len(calibration),
                        relationship_donor_machines=relationship['donor_machines'],
                        relationship_fleet_weight=relationship['fleet_weight'],
                        relationship_transfer_receipts=relationship['transfer_receipts'],
                        calibration_days=int(calibration.time.dt.normalize().nunique()),
                        calibration_period=PROTOCOL['calibration'],pure_cold_start=False)
                    if len(calibration)<200 or receipt['calibration_days']<3:
                        receipt['status']='INSUFFICIENT_DISJOINT_CALIBRATION';variants.append(receipt);continue
                    xcal=calibration[list(FEATURES)].to_numpy()
                    local=calibrate(xcal,local,start=PROTOCOL['calibration'][0],end=PROTOCOL['calibration'][1])
                    assisted=calibrate(xcal,assisted,start=PROTOCOL['calibration'][0],end=PROTOCOL['calibration'][1])
                    relationship=calibrate(xcal,relationship,start=PROTOCOL['calibration'][0],end=PROTOCOL['calibration'][1])
                    absolute_threshold=float(max(1.,np.quantile(self_scores(xcal,local),.995)))
                    future=frame[eligibility&frame.time.ge(PROTOCOL['diagnostic'][0])&frame.time.lt(PROTOCOL['diagnostic'][1])]
                    if len(future)==0:receipt['status']='NO_DIAGNOSTIC_STEADY_POINTS';variants.append(receipt);continue
                    values=future[list(FEATURES)].to_numpy();s=self_scores(values,local)>absolute_threshold
                    j=scores(values,local)>local['threshold'];f=scores(values,assisted)>assisted['threshold']
                    rel=scores(values,relationship)>relationship['threshold']
                    lanes={'local_absolute':s,'local_joint':j,'fleet_joint':f,'local_plus_fleet':s|f,
                           'fleet_relationship_only':rel,'local_plus_relationship':s|rel}
                    receipt.update(status='RESEARCH_PROPOSAL',diagnostic_points=len(future),
                                   diagnostic_period=PROTOCOL['diagnostic'],lanes={})
                    for lane,flags in lanes.items():
                        persisted,episodes=persistence(flags,future.time)
                        receipt['lanes'][lane]={'flagged_minutes':int(flags.sum()),'flag_rate':float(flags.mean()),
                                              'persisted_minutes':persisted,'episodes':episodes}
                        daily_frame=pd.DataFrame({'day':future.time.dt.strftime('%Y-%m-%d'),'flag':flags})
                        for day,day_frame in daily_frame.groupby('day'):
                            daily.append({'machine':machine,'module':module,'context':context,'fit_days':days,
                                          'lane':lane,'day':day,'evaluated_minutes':len(day_frame),
                                          'flagged_minutes':int(day_frame.flag.sum())})
                    variants.append(receipt)
                    if days==14:
                        candidate_models.append({**relationship,'absolute_threshold':absolute_threshold,
                                                 'study_id':study_id,'local_absolute_reference':local})
        del data,events;gc.collect()
        print(json.dumps({'phase':'diagnostic','machine':machine,'variants':len(variants),
                          'elapsed_seconds':round(time.perf_counter()-started,1)}),flush=True)
    pd.DataFrame(metrics).to_parquet(OUT/'transition_metrics.parquet',index=False)
    pd.DataFrame(curves).to_parquet(OUT/'reference_transition_curves.parquet',index=False)
    pd.DataFrame(daily).to_parquet(OUT/'daily_lane_diagnostics.parquet',index=False)
    write_json(OUT/'model_proposals.json',{'study_id':study_id,'models':candidate_models})
    phase_summary=[]
    metric_frame=pd.DataFrame(metrics)
    for (machine,module,direction,split),group in metric_frame.groupby(['machine','module','direction','split']):
        settled=group.settling_minutes.dropna();responded=group.response_delay_minutes.dropna()
        phase_summary.append({'machine':machine,'module':int(module),'direction':direction,'split':split,
          'events':len(group),'settled_observations':len(settled),'censored_or_insufficient':int(group.settling_minutes.isna().sum()),
          'settling_p50_minutes':float(settled.median()) if len(settled) else None,
          'settling_p90_minutes':float(settled.quantile(.9)) if len(settled) else None,
          'response_delay_p50_minutes':float(responded.median()) if len(responded) else None,
          'healthy_label_verified':False})
    completed=[r for r in variants if r['status']=='RESEARCH_PROPOSAL']
    summary={'study_id':study_id,'version':VERSION,'status':'RESEARCH_REFERENCE_READY',
        'activation_eligible':False,'auto_activation_allowed':False,'source_machine_order':list(MACHINES),
        'new_machines':['041','058','080','081'],'source_files':len(manifest['files']),'raw_rows':manifest['raw_rows'],
        'protocol':PROTOCOL,'coverage':coverage,'variants':variants,'transition_summary':phase_summary,
        'completed_variants':len(completed),'fleet_assisted_variants':sum(bool(r['fleet_weight']) for r in completed),
        'relationship_assisted_variants':sum(bool(r['relationship_fleet_weight']) for r in completed),
        'selection':'Frozen Local absolute + parameter-specific selective Fleet covariance shape + event response evidence; donor means never move the default Local baseline; ARX not required',
        'quality_claim':'Flag burden is not false-alarm rate; historical inspected data are not prospective accuracy.',
        'production_blockers':['Reviewed healthy donor/target references','Verified hardware/role/configuration/control/pressure-basis contracts',
                               'Independent known-case and healthy-cycle acceptance','Prospective target validation after frozen review'],
        'elapsed_seconds':round(time.perf_counter()-started,3),'source_namespace':None,
        'derived_version':manifest['version'],'adapter_sha256':manifest['code_sha256'],
        'source_days':[{k:r[k] for k in ('machine','date','source_sha256','minute_parquet_sha256')} for r in manifest['files']],
        'core_sha256':core_hash,'implementation_sha256':benchmark_hash}
    # Atomic publication after all evidence is complete. API only reads artifacts.
    write_json(OUT/'summary.json',summary)
    print(json.dumps({'phase':'complete','study_id':study_id,'variants':len(completed),
                      'fleet_assisted':summary['fleet_assisted_variants'],'seconds':summary['elapsed_seconds']}),flush=True)


if __name__=='__main__':run()
