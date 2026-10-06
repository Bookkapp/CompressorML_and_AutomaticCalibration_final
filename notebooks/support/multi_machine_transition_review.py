"""Offline, past-only multi-machine phase evidence. No runtime/profile/DB writes.

Uses previously audited source-second event ledgers and minute archives. Returned
Reference events are unverified transient examples, not confirmed healthy labels.
"""
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import sys,json,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from notebooks.support.sv_settling_diagnostic import profiles,F
from apps.api.app.qualified_calibration import fit_one_minute_candidate
from apps.api.app.qualified_windows import QualifiedWindow,FEATURES,STATE_CODE

OUT=ROOT/'notebooks/outputs/sv_settling_diagnostic_20261005'
ORIG=ROOT/'notebooks/outputs/october_three_machine_calibration_v1'
EXTRA=ROOT/'notebooks/outputs/local_profile_model_selection_v1'

def candidate(frame,machine,module,ref_start,ref_end,end):
    windows=[]
    for r in frame.itertuples():
        t=r.stamp.to_pydatetime();ok=bool(r.eligible)
        windows.append(QualifiedWindow('MX'+machine,module,t,t+timedelta(minutes=1),'Off' if ok else 'UNKNOWN',STATE_CODE if ok else 'NOT_SCORED',int(r.samples),60,min(1.,r.samples/60),float(r.gap),'PASS' if ok else 'ARCHIVE_NOT_QUALIFIED','',
          {f:float(getattr(r,f)) for f in FEATURES} if ok else None))
    return fit_one_minute_candidate(windows,machine_number='MX'+machine,module=module,calibration_start=ref_start.to_pydatetime(),shadow_start=ref_end.to_pydatetime(),shadow_end=end.to_pydatetime())

def run():
    started=time.perf_counter();saved=profiles();records=[];supports=[];context_rows=[];trajectories=[];source_files=[];fit_receipts=[]
    ledgers=pd.concat([pd.read_parquet(ORIG/'events.parquet'),pd.read_parquet(EXTRA/'additional_cold_entry_events.parquet')],ignore_index=True)
    # Source witnesses, not gap-generated artificial start IDs.
    ledgers=ledgers[~ledgers.kind.eq('UNKNOWN_GAP_OR_LEFT_CENSORED')]
    for machine in ['017','024','080','029','041','057','070','118','119']:
        folder=ORIG if machine in ['017','024','080'] else EXTRA
        a,b,end=map(pd.Timestamp,('2026-08-31','2026-09-28','2026-10-01') if machine in ['017','024'] else ('2026-08-04','2026-08-18','2026-09-09'))
        paths=sorted(p for p in (folder/'minutes').glob(machine+'_*.parquet') if str(a.date())<=p.stem[4:]<str(end.date()))
        if not paths:continue
        data=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
        source_files.extend({'machine':machine,'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size} for p in paths)
        for module in range(1,9):
            d=data[data.module.eq(module)].sort_values('stamp').reset_index(drop=True)
            chosen=ledgers[ledgers.machine.eq(machine)&ledgers.module.eq(module)&ledgers.start.ge(a)&ledgers.start.lt(end)]
            if (machine,module) in saved:
                c=saved[machine,module];med=np.array([c['baseline'][f]['median'] for f in F]);scale=np.array([c['baseline'][f]['scale'] for f in F]);threshold=c['threshold']
                fit_n=int(d[d.stamp.lt(b)&d.eligible].shape[0]);fit_days=d.loc[d.stamp.lt(b)&d.eligible,'stamp'].dt.date.nunique();status=c['status']
            else:
                eligible_ref=d[d.stamp.lt(b)&d.eligible]
                if len(eligible_ref)<200 or eligible_ref.stamp.dt.date.nunique()<7:
                    context_rows.append({'machine':machine,'module':module,'supported':False,'reason':'INSUFFICIENT_PAST_REFERENCE','witnessed_starts':len(chosen)});continue
                c=candidate(d,machine,module,a,b,end)
                med=np.array([c['medians'][f] for f in F]);scale=np.array([c['scales'][f] for f in F]);threshold=c['threshold'];fit_n=c['calibration_windows'];fit_days=c['calibration_days'];status=c['status']
            if threshold<=0:continue
            fit_receipts.append({'machine':machine,'module':module,'reference_start':a.isoformat(),'reference_end':b.isoformat(),
                'medians':dict(zip(F,map(float,med))),'scales':dict(zip(F,map(float,scale))),'threshold':float(threshold),'status':status,
                'reference_minutes':fit_n,'reference_days':int(fit_days),'saved_profile_id':saved.get((machine,module),{}).get('profile_id')})
            times=d.stamp.to_numpy(dtype='datetime64[ns]');eligible=d.eligible.to_numpy(bool);vals=d[F].to_numpy(float);signed=(vals-med)/scale;scores=abs(signed).max(axis=1)
            group_records=[];tracks={}
            for event in chosen.itertuples():
                phase='reference' if event.start<b else 'evaluation';limit=b if phase=='reference' else end
                idx=int(np.searchsorted(times,np.datetime64(event.start.ceil('min'))));stop=idx
                while stop<len(d) and eligible[stop] and d.stamp.iloc[stop]<limit and d.stamp.iloc[stop]<event.start+pd.Timedelta('120min'):
                    if stop>idx and (d.stamp.iloc[stop]-d.stamp.iloc[stop-1]).total_seconds()!=60:break
                    stop+=1
                count=0;returned=None
                for k in range(idx,stop):
                    count=count+1 if scores[k]<=threshold else 0
                    if count==3:returned=(d.stamp.iloc[k]+pd.Timedelta('1min')-event.start).total_seconds()/60;break
                r={'machine':machine,'module':module,'event_id':event.event_id,'kind':event.kind,'start':event.start,'phase':phase,'reference_end':b,
                   'qualified_minutes':stop-idx,'returned_confirm_min':returned,'flagged_minutes':int((scores[idx:stop]>threshold).sum()),
                   'not_returned_after_30min':bool(stop-idx>=30 and returned is None),'source_duration_seconds':event.observed_duration_seconds,
                   'censored':bool(returned is None),'threshold':threshold,'initial_hp2':event.initial_hp2,'initial_templo':event.initial_templo}
                elapsed=(times[idx:stop]-np.datetime64(event.start))/np.timedelta64(1,'m')
                r['early30_flagged_minutes']=int(((scores[idx:stop]>threshold)&(elapsed<30)).sum())
                r['pre_return_flagged_minutes']=int(((scores[idx:stop]>threshold)&(elapsed<returned)).sum()) if returned is not None else None
                records.append(r);group_records.append(r)
                tracks[event.event_id]=(idx,stop,event.start)
            frame=pd.DataFrame(group_records)
            if frame.empty:context_rows.append({'machine':machine,'module':module,'supported':True,'witnessed_starts':0,'fit_minutes':fit_n,'fit_days':fit_days});continue
            for kind,g in frame[frame.phase.eq('reference')&frame.returned_confirm_min.notna()].groupby('kind'):
                days=pd.to_datetime(g.start).dt.date.nunique();supported=len(g)>=3 and days>=3
                supports.append({'machine':machine,'module':module,'kind':kind,'returned_reference_events':len(g),'reference_event_days':days,
                    'envelope_example_support':supported,'reference_p50_confirm_min':float(g.returned_confirm_min.median()),'reference_p95_confirm_min':float(g.returned_confirm_min.quantile(.95)),
                    'healthy_confirmed':False})
                # Event-weighted descriptive trajectory, no minute-count weighting.
                for lo,hi in [(0,3),(3,6),(6,11),(11,21),(21,31),(31,61),(61,121)]:
                    vectors=[]
                    for ev in g.itertuples():
                        idx,stop,t0=tracks[ev.event_id];elapsed=(times[idx:stop]-np.datetime64(t0))/np.timedelta64(1,'m')
                        mask=(elapsed>=lo)&(elapsed<hi)
                        if mask.any():vectors.append(np.median(signed[idx:stop][mask],axis=0))
                    if not vectors:continue
                    x=np.array(vectors)
                    for j,f in enumerate(F):trajectories.append({'machine':machine,'module':module,'kind':kind,'elapsed_start':lo,'elapsed_end':hi,'feature':f,
                        'events_with_data':len(vectors),'event_median_signed_z':float(np.median(x[:,j])),'event_q10_signed_z':float(np.quantile(x[:,j],.1)),
                        'event_q90_signed_z':float(np.quantile(x[:,j],.9)),'supported_context':supported,'healthy_confirmed':False})
            ref=frame[frame.phase.eq('reference')];future=frame[frame.phase.eq('evaluation')]
            context_rows.append({'machine':machine,'module':module,'supported':True,'fit_minutes':fit_n,'fit_days':fit_days,'fit_status':status,
                'witnessed_starts':len(frame),'reference_starts':len(ref),'evaluation_starts':len(future),
                'reference_tracks_at_least_3min':int(ref.qualified_minutes.ge(3).sum()),'evaluation_tracks_at_least_3min':int(future.qualified_minutes.ge(3).sum()),
                'reference_returns':int(ref.returned_confirm_min.notna().sum()),'evaluation_returns':int(future.returned_confirm_min.notna().sum()),
                'reference_return_p50':float(ref.returned_confirm_min.median()) if ref.returned_confirm_min.notna().any() else None,
                'evaluation_return_p50':float(future.returned_confirm_min.median()) if future.returned_confirm_min.notna().any() else None,
                'reference_return_p95':float(ref.returned_confirm_min.quantile(.95)) if ref.returned_confirm_min.notna().any() else None,
                'evaluation_return_p95':float(future.returned_confirm_min.quantile(.95)) if future.returned_confirm_min.notna().any() else None,
                'reference_no_return_30min':int(ref.not_returned_after_30min.sum()),'evaluation_no_return_30min':int(future.not_returned_after_30min.sum())})
        print('Reviewed multi-machine '+machine,flush=True)
    for name,items in [('multi_events',records),('multi_contexts',context_rows),('multi_support',supports),('reference_trajectories',trajectories),('multi_source_files',source_files)]:pd.DataFrame(items).to_csv(OUT/f'{name}.csv',index=False)
    (OUT/'offline_physical_profiles.json').write_text(json.dumps(fit_receipts,indent=2),encoding='utf-8')
    receipt={'executed_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),'source':'Previously audited observed-second source event ledgers and per-minute Parquet archives; 017/024 retain exact saved SQL Candidates',
      'machines':['017','024','080','029','041','057','070','118','119'],'contexts':len(context_rows),'supported_contexts':sum(r['supported'] for r in context_rows),
      'witnessed_starts_with_supported_baseline':len(records),'reference_envelopes_with_at_least_3_events_3_days':sum(s['envelope_example_support'] for s in supports),
      'reference_policy':'017/024 saved physical-v2 31Aug-before28Sep; others physical-v2 pure fit 4Aug-before18Aug. Different dates retained; no pooled absolute levels.',
      'future_period':'017/024 28Sep-before1Oct; others18Aug-before9Sep, as available. Previously inspected historical periods, not fresh holdout.',
      'known_case_policy':'Owner-confirmed 057/1 29Aug and080/6 7Sep are outside their fits; existing fixed-case replay is separate evidence, not policy tuning.',
      'limitations':['Event kind COLD_CONTROL_ENTRY is a shared qualification boundary; this archive ledger does not distinguish SVOff from moduleOn entry. Exact 017/024 SV witnesses are in the separate Raw study.',
        'Only observed events enter; gap/left-censored events are excluded and not relabelled as starts.',
        'Returned Reference examples are outcome-conditioned unverified candidates; healthy technician labels and independent normal/fault phase validation are absent.',
        'Three events on three days is evidence sufficiency for exploratory comparison only, not certified Q95 coverage or approval.',
        'Some fit contexts remain REVIEW_REQUIRED; their descriptive trajectories are not production profiles.'],
      'source_written':False,'runtime_changed':False,'profile_changed':False,'elapsed_seconds':time.perf_counter()-started}
    (OUT/'multi_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt),flush=True)

if __name__=='__main__':run()
