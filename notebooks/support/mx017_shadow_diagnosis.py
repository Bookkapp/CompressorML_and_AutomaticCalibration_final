"""Read-only diagnosis of saved MX017 candidate evidence; no model changes."""
import sys,json,csv
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
import numpy as np
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from apps.api.app.config import get_settings
from apps.api.app.db import connection
from apps.api.app.qualified_cache import day_key,unpack
from apps.api.app.qualified_windows import FEATURES
from apps.api.app.reference_review import bounds,snapshot_digest
OUT=ROOT/'notebooks/outputs/mx017_shadow_diagnosis_20261004'

def quantiles(values):
    return {key:float(v) for key,v in zip(('p01','p10','median','p90','p99'),np.quantile(values,[.01,.1,.5,.9,.99]))} if len(values) else None

def main():
    OUT.mkdir(parents=True,exist_ok=True);settings=get_settings()
    with connection() as c:
        parent=c.execute(text("SELECT job_id,created_at,result_json FROM ht9046mx_reference_review_job WHERE machine_number='MX017' AND module=0 AND status='COMPLETED' ORDER BY created_at DESC LIMIT 1")).mappings().one()
        result=json.loads(parent['result_json']);previews=[]
        for m in result['modules']:
            row=c.execute(text('SELECT preview_json FROM ht9046mx_reference_review_job WHERE job_id=:job'),{'job':m['job_id']}).scalar()
            previews.append((m,json.loads(row)))
    receipt={'parent_id':parent['job_id'],'parent_created_utc':str(parent['created_at']),'timezone':'Asia/Bangkok','snapshot':'Saved candidate + analytics cached exact minute windows; cache SHA256 must match saved source_digest','source_read_only':True,'production_model_changed':False,'modules':[]}
    distributions=[];episodes=[];minute_points=[]
    for m,p in previews:
        module=m['module'];s=p['selection'];start,ref_end,shadow_start,end=bounds(s);windows=[];day=start
        with connection() as c:
            while day<end:
                payload=c.execute(text('SELECT payload FROM ht9046mx_qualified_day_cache WHERE day_key=:key AND module=:module'),{'key':day_key(settings,'MX017',day.date()),'module':module}).scalar()
                if payload is None:raise RuntimeError(f'Missing frozen-source cache M{module} {day}')
                windows.extend(unpack(payload));day+=timedelta(days=1)
        assert snapshot_digest(windows,s)==p['source_digest'],f'M{module} current cache differs from frozen review'
        record={'module':module,'job_id':m['job_id'],'status':m['status'],'summary':p['summary'],'reason_codes':p['reason_codes'],'source_digest_match':True,'baseline':p['baseline'],'threshold':p['diagnostics']['threshold'],'drift':p['diagnostics']['drift'],'proposal':p.get('reference_proposal'),'feature_crossings':{},'dominant_feature_minutes':{},'episodes':[]}
        ref=[w for w in windows if w.eligible and start<=w.window_start<ref_end]
        shadow=[w for w in windows if w.eligible and shadow_start<=w.window_start<end]
        initial=p['diagnostics'].get('initial_reference_baseline',{})
        if ref and initial:
            rv=np.asarray([[w.features[f] for f in FEATURES] for w in ref]);rz=np.max(abs((rv-np.asarray([initial[f]['median'] for f in FEATURES]))/np.asarray([initial[f]['scale'] for f in FEATURES])),axis=1)
            retained=rv[rz<=s['policy']['profile_quarantine_z']]
            for i,f in enumerate(FEATURES):
                for phase,values in [('reference_all',rv[:,i]),('reference_retained',retained[:,i]),('shadow',np.asarray([w.features[f] for w in shadow]))]:
                    q=quantiles(values)
                    if q:distributions.append({'module':module,'feature':f,'phase':phase,'minutes':len(values),**q})
        if p['baseline'] and shadow:
            base=p['baseline'];th=p['diagnostics']['threshold'];sv=np.asarray([[w.features[f] for f in FEATURES] for w in shadow])
            z=abs((sv-np.asarray([base[f]['median'] for f in FEATURES]))/np.asarray([base[f]['scale'] for f in FEATURES]));scores=z.max(axis=1);dominant=z.argmax(axis=1);flags=scores>=th
            ref_scores=np.max(abs((retained-np.asarray([base[f]['median'] for f in FEATURES]))/np.asarray([base[f]['scale'] for f in FEATURES])),axis=1)
            record['threshold_comparator_audit']={'comparison':'Diagnostic only; runtime remains >=; threshold unchanged','reference_retained_ge':int(np.sum(ref_scores>=th)),'reference_retained_gt':int(np.sum(ref_scores>th)),'reference_retained_equal':int(np.sum(ref_scores==th)),'reference_retained_minutes':len(retained),'shadow_ge':int(flags.sum()),'shadow_gt':int(np.sum(scores>th)),'shadow_equal':int(np.sum(scores==th)),'shadow_minutes':len(shadow),'shadow_gt_pct':100*int(np.sum(scores>th))/len(shadow)}
            record['reference_quarantine_dominant']=dict(Counter(FEATURES[int(i)] for i in np.argmax(abs((rv-np.asarray([initial[f]['median'] for f in FEATURES]))/np.asarray([initial[f]['scale'] for f in FEATURES])),axis=1)[rz>s['policy']['profile_quarantine_z']]))
            record['feature_crossings']={f:int(np.sum(z[:,i]>=th)) for i,f in enumerate(FEATURES)}
            valve_index=FEATURES.index('valve');other=[i for i,f in enumerate(FEATURES) if f!='valve']
            record['valve_only_minutes']=int(np.sum((z[:,valve_index]>=th)&(np.max(z[:,other],axis=1)<th)))
            record['any_non_valve_crossing_minutes']=int(np.sum(np.max(z[:,other],axis=1)>=th))
            record['dominant_feature_minutes']=dict(Counter(FEATURES[int(dominant[i])] for i in np.where(flags)[0]))
            by_time={w.window_start:w for w in windows};scored={w.window_start:(float(scores[i]),bool(flags[i]),FEATURES[int(dominant[i])]) for i,w in enumerate(shadow)}
            runs=[];current=None
            for i,w in enumerate(shadow):
                t=w.window_start
                if flags[i]:
                    if current is not None and current['end']==t.isoformat():
                        current['end']=w.window_end.isoformat();current['minutes']+=1
                        current['features'][FEATURES[int(dominant[i])]]+=1
                        if scores[i]>current['peak_score']:current.update(peak_score=float(scores[i]),peak_time=t.isoformat(),peak_feature=FEATURES[int(dominant[i])])
                    else:
                        prev=by_time.get(t-timedelta(minutes=1))
                        current={'module':module,'start':t.isoformat(),'end':w.window_end.isoformat(),'minutes':1,'peak_score':float(scores[i]),'peak_time':t.isoformat(),'peak_feature':FEATURES[int(dominant[i])],'features':Counter({FEATURES[int(dominant[i])]:1}),'preceding_minute_reason':prev.reason or prev.data_quality_status if prev else 'NO_SOURCE_ROWS'}
                        runs.append(current)
                else:current=None
            for run in runs:
                t=datetime.fromisoformat(run['end']);after=scored.get(t);run['return_to_below_threshold_next_minute']=bool(after and not after[1]);run['ended_at_state_or_gap']=after is None
                stable_after=[]
                for step in range(15):
                    v=scored.get(t+timedelta(minutes=step))
                    if v is None:break
                    stable_after.append(not v[1])
                run['next_15_qualified_minutes']=len(stable_after);run['next_15_below_threshold_minutes']=sum(stable_after)
                run['features']=dict(run['features'])
            lengths=np.asarray([r['minutes'] for r in runs]);record['episode_summary']={'count':len(runs),'flagged_minutes':int(flags.sum()),'single_minute_runs':int(sum(lengths==1)),'runs_le_5min':int(sum(lengths<=5)),'minutes_in_runs_le_5min':int(sum(lengths[lengths<=5])),'runs_ge_30min':int(sum(lengths>=30)),'minutes_in_runs_ge_30min':int(sum(lengths[lengths>=30])),'longest_minutes':int(max(lengths)) if len(lengths) else 0,'median_minutes':float(np.median(lengths)) if len(lengths) else 0,'returned_to_below_threshold':sum(r['return_to_below_threshold_next_minute'] for r in runs),'ended_at_state_or_gap':sum(r['ended_at_state_or_gap'] for r in runs)}
            record['episodes']=sorted(runs,key=lambda r:-r['minutes'])[:15];episodes+=runs
            for i,w in enumerate(shadow):minute_points.append({'module':module,'time':w.window_start.isoformat(),'score':float(scores[i]),'threshold':th,'flag':bool(flags[i]),'dominant':FEATURES[int(dominant[i])],**w.features})
            assert abs(int(flags.sum())/len(shadow)*100-p['summary']['shadow_flag_pct'])<1e-12
            record['daily_shadow']=[{'date':str(day),'qualified_minutes':sum(w.window_start.date()==day for w in shadow),'flagged_minutes':sum(bool(flags[i]) for i,w in enumerate(shadow) if w.window_start.date()==day)} for day in sorted({w.window_start.date() for w in shadow})]
        receipt['modules'].append(record)
        print(json.dumps({k:record[k] for k in ['module','dominant_feature_minutes','episode_summary'] if k in record}),flush=True)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'episodes.json').write_text(json.dumps(episodes,indent=2),encoding='utf-8')
    for name,rows in [('distributions.csv',distributions),('shadow_minutes.csv',minute_points)]:
        with (OUT/name).open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

if __name__=='__main__':main()
