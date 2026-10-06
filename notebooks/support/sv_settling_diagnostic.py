"""Read-only transition diagnosis; writes local receipts, never changes gates/jobs/profiles.

Raw ZIP state witnesses + archived minute means, frozen saved Candidate baselines.
Bounded actual SQL Raw checks reconcile event witnesses/means against current source.
"""
from __future__ import annotations
import csv, hashlib, json, sys, time, zipfile
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from apps.api.app.db import connection
from apps.api.app.config import get_settings
from apps.api.app.reference_raw import read_raw

BASE=ROOT/'notebooks/outputs/october_three_machine_calibration_v1'
OUT=ROOT/'notebooks/outputs/sv_settling_diagnostic_20261005'
F=['hp1','lp1','hp2','lp2','dp1','dp2','temphi','templo']
REF_END=pd.Timestamp('2026-09-28');END=pd.Timestamp('2026-10-01')
BATCHES={'017':'272a5438-b021-4056-90fb-ad03188830a9'}

def serialize(v):
    if isinstance(v,(datetime,pd.Timestamp)): return v.isoformat()
    if isinstance(v,np.generic): return v.item()
    raise TypeError(type(v).__name__)

def profiles():
    audit=json.loads((ROOT/'notebooks/outputs/physical_control_qa_20261004/final-audit.json').read_text())
    parent=next(j for j in audit['jobs'] if j['job_id']=='0fca7c97-8b66-4f82-a92e-3933afbb2a39')
    BATCHES['024']=parent['result']['batch_id']
    result={}
    with connection() as c:
        for machine,batch in BATCHES.items():
            for r in c.execute(text('SELECT * FROM ht9046mx_calibration_profile WHERE batch_id=:b AND machine_number=:m ORDER BY module'),{'b':batch,'m':'MX'+machine}).mappings():
                stats=json.loads(r['statistics_json']);th=json.loads(r['threshold_json'])
                assert th['threshold_version']=='qualified-1m-physical-retained-q995-strict-v2'
                result[machine,int(r['module'])]={'profile_id':r['profile_id'],'batch':batch,'baseline':stats['exact_baseline'],
                    'threshold':th['deviation_score_q995'],'shadow_flag_pct':r['shadow_flag_pct'],
                    'reasons':json.loads(r['reason_codes']),'status':r['profile_status']}
    return result

def witnesses():
    entries=list(csv.DictReader((BASE/'file_inventory.csv').open(encoding='utf-8')))
    entries=sorted([e for e in entries if e['machine'] in {'017','024'} and e['kind']=='dynamic' and '2026-08-31'<=e['date']<='2026-09-30'],key=lambda e:(e['machine'],e['date']))
    assert len(entries)==62
    wanted={'Time','Status',*(f'{tag}_{m}' for m in range(1,9) for tag in ['Status','Busy','SV','Valve'])}
    prior={};events=[];quality=[]
    for n,e in enumerate(entries):
        with zipfile.ZipFile(Path.home()/'Downloads'/e['archive']) as z:
            assert z.getinfo(e['member']).CRC==int(e['crc32'])
            with z.open(e['member']) as f:
                d=pd.read_csv(f,skiprows=1,skipinitialspace=True,usecols=lambda col:col.strip() in wanted,low_memory=False)
        d.columns=d.columns.str.strip()
        for col in d.select_dtypes('object'):d[col]=d[col].str.strip()
        stamps=pd.to_datetime(e['date']+' '+d.Time,errors='coerce')
        bad_time=int(stamps.isna().sum());nonmonotonic=int(stamps.diff().dt.total_seconds().lt(0).sum())
        d=d.loc[stamps.notna()].assign(_stamp=stamps.loc[stamps.notna()]).sort_values('_stamp',kind='stable').reset_index(drop=True)
        stamps=d._stamp
        seconds=stamps.astype('int64').to_numpy()//10**9
        duplicates=stamps.duplicated(keep=False).to_numpy()
        quality.append({'machine':e['machine'],'date':e['date'],'rows':len(d),'bad_time':bad_time,'nonmonotonic':nonmonotonic,'duplicate_rows':int(duplicates.sum()),'crc32':e['crc32']})
        for m in range(1,9):
            key=(e['machine'],m);p=prior.get(key)
            sv=d[f'SV_{m}'].to_numpy();status=d[f'Status_{m}'].to_numpy();busy=d[f'Busy_{m}'].astype(str).to_numpy();valve=d[f'Valve_{m}'].to_numpy();run=d.Status.to_numpy()
            prev_sv=np.concatenate(([p['sv'] if p else ''],sv[:-1]));prev_st=np.concatenate(([p['status'] if p else ''],status[:-1]))
            prev_busy=np.concatenate(([p['busy'] if p else ''],busy[:-1]));prev_s=np.r_[p['second'] if p else -99999999999,seconds[:-1]]
            prev_duplicate=np.r_[p['duplicate'] if p else True,duplicates[:-1]]
            continuous=(seconds-prev_s>0)&(seconds-prev_s<=2)&~duplicates&~prev_duplicate
            sv_off=continuous&(prev_sv=='On')&(sv=='Off')
            manual_end=continuous&(prev_st=='ChangeValve')&(status=='On')&(busy=='0')
            for kind,mask in [('SV_OFF',sv_off),('CHANGE_VALVE_END',manual_end)]:
                for i in np.flatnonzero(mask):
                    events.append({'machine':e['machine'],'module':m,'kind':kind,'start':stamps.iloc[i],
                        'previous_time':pd.Timestamp(prev_s[i],unit='s'),'previous_sv':str(prev_sv[i]),'previous_state':str(prev_st[i]),
                        'previous_busy':str(prev_busy[i]),'sv':str(sv[i]),'state':str(status[i]),'busy':str(busy[i]),'global_state':str(run[i]),
                        'valve_at_start':float(valve[i]),'qualified_state_at_start':bool(run[i]=='Run' and status[i]=='On' and busy[i]=='0' and sv[i]=='Off')})
            prior[key]={'sv':sv[-1],'status':status[-1],'busy':busy[-1],'second':seconds[-1],'duplicate':bool(duplicates[-1])}
        if (n+1)%8==0:print(f'Raw witnesses {n+1}/62',flush=True)
    pd.DataFrame(quality).to_csv(OUT/'raw_quality.csv',index=False)
    pd.DataFrame(events).to_parquet(OUT/'raw_transition_witnesses.parquet',index=False)
    return events,quality

def load_minutes(machine):
    return pd.concat([pd.read_parquet(BASE/'minutes'/f'{machine}_{day.date()}.parquet') for day in pd.date_range('2026-08-31','2026-09-30')],ignore_index=True)

def run():
    OUT.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    p=profiles();events,quality=witnesses();results=[];summaries=[];cuts=[];parity=[];limits=[];feature_samples=[]
    for machine in ['017','024']:
        all_minutes=load_minutes(machine)
        for m in range(1,9):
            context=all_minutes.loc[all_minutes.module.eq(m)].sort_values('stamp').reset_index(drop=True)
            raw_events=[e for e in events if e['machine']==machine and e['module']==m]
            if (machine,m) not in p:
                summaries.append({'machine':machine,'module':m,'status':'NO_CANDIDATE','events':len(raw_events),'qualified_shadow':int(context.loc[context.stamp.ge(REF_END),'eligible'].sum())});continue
            profile=p[machine,m];b=profile['baseline'];threshold=profile['threshold']
            vals=context[F].to_numpy(float);med=np.array([b[f]['median'] for f in F]);scale=np.array([b[f]['scale'] for f in F])
            z=abs((vals-med)/scale);score=z.max(axis=1);eligible=context.eligible.to_numpy(bool)
            context['score']=score;context['flag']=eligible&(score>threshold)
            # Exploratory stability limits use only past, below-threshold Reference,
            # with no witnessed transition in the preceding hour. Not healthy labels.
            since=np.full(len(context),np.inf)
            times=context.stamp.to_numpy(dtype='datetime64[ns]')
            starts=sorted(e['start'] for e in raw_events)
            if starts:
                arr=np.array(starts,dtype='datetime64[ns]');idx=np.searchsorted(arr,times,side='right')-1;valid=idx>=0
                since[valid]=(times[valid]-arr[idx[valid]])/np.timedelta64(1,'m')
            stats_by_w={}
            for w in [3,5]:
                frame=pd.DataFrame(vals,columns=F)
                variation=(frame.rolling(w).max()-frame.rolling(w).min()).to_numpy()/scale
                slope=abs(frame.diff(w-1).to_numpy())/((w-1)*scale)
                uninterrupted=pd.Series(eligible).rolling(w).sum().eq(w).to_numpy()
                ref=(context.stamp.lt(REF_END).to_numpy())&eligible&(score<=threshold)&(since>=60)&uninterrupted
                for offset in range(1,w):ref&=np.r_[np.zeros(offset,dtype=bool),(score[:-offset]<=threshold)]
                if ref.sum()<50:continue
                range_limit=np.quantile(variation[ref],.99,axis=0);slope_limit=np.quantile(slope[ref],.99,axis=0)
                # Zero variation limits remain zero; no empirically invented epsilon.
                stable=uninterrupted & np.all(variation<=range_limit+1e-12,axis=1)&np.all(slope<=slope_limit+1e-12,axis=1)
                stats_by_w[w]={'stable':stable,'range':range_limit,'slope':slope_limit,'ref_minutes':int(ref.sum())}
                for j,f in enumerate(F):limits.append({'machine':machine,'module':m,'window':w,'feature':f,'reference_minutes':int(ref.sum()),'range_q99_source_units':float(range_limit[j]*scale[j]),'slope_q99_units_per_min':float(slope_limit[j]*scale[j])})
            phase_shadow=context.stamp.ge(REF_END).to_numpy();shadow_n=int((eligible&phase_shadow).sum());shadow_flags=int((context.flag.to_numpy()&phase_shadow).sum())
            assert np.isclose(shadow_flags/shadow_n*100,profile['shadow_flag_pct'],rtol=0,atol=1e-8),(machine,m,shadow_flags,shadow_n,profile['shadow_flag_pct'])
            valid_events=[]
            for e in raw_events:
                e=dict(e);e['phase']='reference' if e['start']<REF_END else 'shadow'
                idx=int(np.searchsorted(times,np.datetime64(e['start'].ceil('min'))));stop=idx
                boundary=REF_END if e['phase']=='reference' else END
                while stop<len(context) and eligible[stop] and context.stamp.iloc[stop]<boundary and context.stamp.iloc[stop]<e['start']+pd.Timedelta('120min'):
                    stop+=1
                track=context.iloc[idx:stop];below=0;e['returned_entry_min']=None;e['returned_confirm_min']=None
                for j,row in enumerate(track.itertuples()):
                    below=below+1 if row.score<=threshold else 0
                    if below==3:
                        e['returned_entry_min']=round((row.stamp-pd.Timedelta('2min')-e['start']).total_seconds()/60,3)
                        e['returned_confirm_min']=round((row.stamp+pd.Timedelta('1min')-e['start']).total_seconds()/60,3);break
                e.update(observed_qualified_minutes=len(track),observed_until=context.stamp.iloc[stop] if stop<len(context) else END,
                    flagged_minutes=int(track.flag.sum()),peak_score=float(track.score.max()) if len(track) else None,
                    reference_profile_id=profile['profile_id'],threshold=threshold)
                for w,stats in stats_by_w.items():
                    cnt=cnt_level=0;e[f'stable_confirm_{w}m']=None;e[f'level_and_stable_confirm_{w}m']=None
                    for k in range(idx,stop):
                        # A trailing window must be fully after this observed event.
                        ok=k-w+1>=idx and stats['stable'][k]
                        cnt=cnt+1 if ok else 0;cnt_level=cnt_level+1 if ok and score[k]<=threshold else 0
                        elapsed=(context.stamp.iloc[k]+pd.Timedelta('1min')-e['start']).total_seconds()/60
                        if cnt==3 and e[f'stable_confirm_{w}m'] is None:e[f'stable_confirm_{w}m']=round(elapsed,3)
                        if cnt_level==3 and e[f'level_and_stable_confirm_{w}m'] is None:e[f'level_and_stable_confirm_{w}m']=round(elapsed,3)
                if len(track):
                    e['dominant_feature']=F[int(z[idx:stop].max(axis=0).argmax())]
                    e['start_value']=float(track[e['dominant_feature']].iloc[0]);e['baseline_median']=b[e['dominant_feature']]['median']
                e['last_qualified_index']=stop;e['first_qualified_index']=idx
                valid_events.append(e);results.append(e)
                for minute in [0,5,10,15,20,25,30,60,90]:
                    k=int(np.searchsorted(times,np.datetime64(e['start']+pd.Timedelta(minutes=minute))))
                    if idx<=k<stop:
                        feature_samples.append({'machine':machine,'module':m,'kind':e['kind'],'start':e['start'],'phase':e['phase'],'elapsed_sample_min':minute,
                          'stamp':context.stamp.iloc[k],'score':float(score[k]),'threshold':threshold,**{f:float(vals[k,j]) for j,f in enumerate(F)},'valve':float(context.valve.iloc[k])})
            # Counterfactual masks on frozen scores, NOT a newly fitted Profile.
            for duration in [0,5,10,15,20,25,30,45,60]:
                masks={kind:np.zeros(len(context),bool) for kind in ['SV_OFF','CHANGE_VALVE_END']}
                for e in valid_events:
                    a=e['first_qualified_index'];stop=e['last_qualified_index']
                    masks[e['kind']][a:stop]|=times[a:stop]<np.datetime64(e['start']+pd.Timedelta(minutes=duration))
                union=masks['SV_OFF']|masks['CHANGE_VALVE_END'];kept=eligible&phase_shadow&~union
                cuts.append({'machine':machine,'module':m,'cut_minutes':duration,'original_qualified':shadow_n,'original_flags':shadow_flags,
                    'excluded_qualified':int((eligible&phase_shadow&union).sum()),'excluded_flags':int((context.flag.to_numpy()&phase_shadow&union).sum()),
                    'sv_excluded_flags':int((context.flag.to_numpy()&phase_shadow&masks['SV_OFF']).sum()),
                    'manual_only_excluded_flags':int((context.flag.to_numpy()&phase_shadow&~masks['SV_OFF']&masks['CHANGE_VALVE_END']).sum()),
                    'remaining_flags':int((context.flag.to_numpy()&kept).sum()),'remaining_qualified':int(kept.sum()),
                    'remaining_flag_pct':float(context.flag.to_numpy()[kept].sum()/kept.sum()*100) if kept.sum() else None,
                    'reference_excluded_qualified':int((eligible&~phase_shadow&union).sum())})
            # Bounded source validation: every Shadow SV witness, selected manual,
            # one Reference SV witness per context; raw range includes both states.
            selected=[e for e in valid_events if e['phase']=='shadow' and e['kind']=='SV_OFF']
            selected += [e for e in valid_events if e['kind']=='CHANGE_VALVE_END'][:1]
            selected += [e for e in valid_events if e['phase']=='reference' and e['kind']=='SV_OFF'][:1]
            for e in selected:
                start=e['start'].floor('min')-pd.Timedelta('1min');end=start+pd.Timedelta('30min')
                raw=read_raw(get_settings(),'MX'+machine,m,start.to_pydatetime(),end.to_pydatetime())
                d=pd.DataFrame(raw['chart']);d['stamp']=pd.to_datetime(d.time);at=d.loc[d.stamp.eq(e['start'])];prev=d.loc[d.stamp.eq(e['previous_time'])]
                witness_ok=len(at)==len(prev)==1 and at.iloc[0].sv==e['sv'] and prev.iloc[0].sv==e['previous_sv'] and at.iloc[0].module_state==e['state'] and prev.iloc[0].module_state==e['previous_state']
                means=d.groupby(d.stamp.dt.floor('min'))[F].mean();joined=context.set_index('stamp')[F].join(means,rsuffix='_raw',how='inner')
                err=float(np.nanmax(abs(joined[F].to_numpy()-joined[[f+'_raw' for f in F]].to_numpy())))
                parity.append({'machine':machine,'module':m,'kind':e['kind'],'event':e['start'],'observed_rows':raw['observed_rows'],'duplicate_rows':raw['duplicate_rows'],
                    'sv_counts':raw['sv_counts'],'witness_equal':bool(witness_ok),'mean_absolute_error':err,'matched_minutes':len(joined)})
                assert witness_ok and err<1e-8,(e,parity[-1])
                if machine=='017' and m==1 and e['phase']=='shadow':(OUT/f'raw_017_M1_{e["start"].strftime("%Y%m%d_%H%M%S")}.json').write_text(json.dumps(raw,indent=2),encoding='utf-8')
            summaries.append({'machine':machine,'module':m,'status':profile['status'],'profile_id':profile['profile_id'],
                'reference_sv_events':sum(e['phase']=='reference' and e['kind']=='SV_OFF' for e in valid_events),
                'shadow_sv_events':sum(e['phase']=='shadow' and e['kind']=='SV_OFF' for e in valid_events),
                'manual_events':sum(e['kind']=='CHANGE_VALVE_END' for e in valid_events),'qualified_shadow':shadow_n,'flagged_shadow':shadow_flags,'shadow_flag_pct':shadow_flags/shadow_n*100})
            print(json.dumps(summaries[-1]),flush=True)
    for name,data in [('events',results),('contexts',summaries),('cut_sensitivity',cuts),('source_parity',parity),('stability_limits',limits),('feature_samples',feature_samples)]:
        pd.DataFrame(data).to_csv(OUT/f'{name}.csv',index=False)
    receipt={'executed_at':datetime.now().isoformat(),'timezone':'Asia/Bangkok','source':'original dynamic source ZIPs, saved minute archive and exact physical-v2 SQL Candidates; bounded SELECT-only source checks',
      'period':['2026-08-31','2026-10-01'],'reference_end':REF_END,'batches':BATCHES,'raw_files':len(quality),'raw_rows':sum(q['rows'] for q in quality),
      'raw_duplicate_rows':sum(q['duplicate_rows'] for q in quality),'source_checks':len(parity),'source_witnesses_equal':all(q['witness_equal'] for q in parity),
      'maximum_source_mean_error':max(q['mean_absolute_error'] for q in parity),'events':len(events),'contexts':summaries,
      'stability_definition':'3 consecutive trailing3/5minute windows; per-feature endpoint slope and range within Reference Q99; Reference below-threshold and >=60min from observed transition. Exploratory, no healthy label.',
      'return_definition':'3 consecutive qualified physical scores <= frozen threshold; entry and confirmation times distinct',
      'censoring':'stop at first unqualified minute, next state/quality discontinuity, 120min, or phase boundary; no inferred return across missing evidence',
      'cut_sensitivity':'frozen score what-if; excludes only witnessed continuous event run. No threshold refit and no Shadow-based policy selection.',
      'source_written':False,'runtime_changed':False,'profile_changed':False,'elapsed_seconds':time.perf_counter()-started}
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2,default=serialize),encoding='utf-8')
    print(json.dumps({'events':len(events),'source_checks':len(parity),'elapsed_seconds':receipt['elapsed_seconds']}),flush=True)

if __name__=='__main__':run()
