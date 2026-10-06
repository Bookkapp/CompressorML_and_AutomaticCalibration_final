"""Reference-only event-response catalog from checksum-verified minute evidence.

No MySQL/source mutation; enrich a new immutable Fleet package. Processing is
bounded to three module days. Old selected package never changes.
"""
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
import json,hashlib,time
import pandas as pd
from apps.api.app.fleet_bundle import read_package,load_package,write_package,canonical,digest
from apps.api.app.fleet_transitions import fit_catalog,eight,signature
from apps.api.app.fleet_stable import semantic_quality
from apps.api.app.context_profiles import phase_entries
from apps.api.app.observed_context import ObservedMinute,PHYSICAL
from apps.api.app.unified_events import fingerprint


def file_sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def observed(frame,machine,module):
    valid=semantic_quality(frame[['hp1','lp1','hp2','lp2','temphi','templo']].to_numpy())
    out=[]
    for row,ok in zip(frame.itertuples(),valid):
        features={f:float(getattr(row,f)) for f in PHYSICAL if f not in ('dp1','dp2')} if row.quality and ok else None
        if features:features.update(dp1=features['hp1']-features['lp1'],dp2=features['hp2']-features['lp2'])
        context=f'{row.compressor}|{row.module_state}|{row.busy}|{row.sv}' if row.stable_control else None
        t=row.time.to_pydatetime()
        out.append(ObservedMinute('MX'+machine,module,t,t+timedelta(minutes=1),int(row.samples),float(row.coverage),1.,
            'PASS' if features else 'DATA_QUALITY','' if features else 'PREPARED_QUALITY_OR_ACQUISITION',features,
            {},context,{'valve_mean':float(row.valve) if pd.notna(row.valve) else None}))
    return out


def controls(frame,machine,module):
    result=[]
    for e in frame.itertuples():
        kind='VALVE_COMMAND_CHANGED' if e.event_type=='VALVE_CHANGED' else e.event_type
        before,after=(float(e.before),float(e.after)) if kind=='VALVE_COMMAND_CHANGED' else (e.before,e.after)
        at=e.time.to_pydatetime().isoformat()
        result.append({'event_id':fingerprint(['fleet-events',machine,module,at,kind,before,after]),
            'machine_number':'MX'+machine,'module':module,'occurred_at':at,'event_type':kind,
            'payload':{'details':{'before':before,'after':after,'witness_usable':bool(e.witness_usable)}}})
    return result


def enrich(package,source_root,output_root,progress=None):
    started=time.perf_counter();package=Path(package);source_root=Path(source_root)
    fleet=load_package(package);study=json.loads((source_root/'summary.json').read_bytes())
    receipts={(r['machine'],r['date']):r for r in study['source_days']}
    verified={};events_verified={};examples=[];holdout=[];counts=Counter()
    progress=progress or (lambda x:None)
    for model in fleet.models():
        machine,module=model['machine'],model['module']
        start=model['reference_start'][:10];end=model['threshold_period'][1][:10]
        dates=sorted(d for m,d in receipts if m==machine and start<=d<end)
        center,scale=eight(model['center'],model['scale'])
        regime={'regime_id':fingerprint([machine,module,model['context'],center])[:20],
            'center':center,'scale':scale,'threshold':model['absolute_threshold'],
            'context':'RUN_MODULE_ON_BUSY0_'+model['context'],'coverage_supported':True}
        # Only source-derived known origin, consecutive valid minutes and exact
        # event direction. Event examples never cross fit/calibration boundary.
        for day in dates:
            progress(f'Transition {machine}/M{module} {day}')
            frame_parts=[];event_parts=[]
            date=datetime.fromisoformat(day)
            split='reference' if day<model['reference_end'][:10] else 'calibration'
            lo=start if split=='reference' else model['threshold_period'][0][:10]
            hi=model['reference_end'][:10] if split=='reference' else end
            for offset in (-1,0,1):
                selected=(date+timedelta(days=offset)).date().isoformat()
                if not lo<=selected<hi or (machine,selected) not in receipts:continue
                p=source_root/'minutes'/f'{machine}_{selected}.parquet'
                if (machine,selected) not in verified:
                    actual=file_sha(p)
                    if actual!=receipts[machine,selected]['minute_parquet_sha256']:raise ValueError('PREPARED_SOURCE_CHECKSUM_CHANGED')
                    verified[machine,selected]=actual
                f=pd.read_parquet(p,filters=[('module','==',module)])
                # Read only a short neighbor margin; missing witnesses stay censored.
                if offset<0:f=f[f.time.ge(date-pd.Timedelta(minutes=125))]
                if offset>0:f=f[f.time.lt(date+pd.Timedelta(days=1,minutes=125))]
                frame_parts.append(f)
                ep=source_root/'events'/f'{machine}_{selected}.parquet'
                if ep.exists():
                    events_verified[ep.name]=file_sha(ep)
                    e=pd.read_parquet(ep,filters=[('module','==',module)]);event_parts.append(e)
            if not frame_parts:continue
            windows=observed(pd.concat(frame_parts).sort_values('time'),machine,module)
            events=controls(pd.concat(event_parts).sort_values('time'),machine,module) if event_parts else []
            entries=phase_entries(windows,events,1.,[regime],30)
            for n,e in enumerate(entries):
                if e['at'].date().isoformat()!=day:continue
                direction,rid,context=signature(e['key'])
                if rid=='UNKNOWN':counts['unknown_origin']+=1;continue
                stop=entries[n+1]['at'] if n+1<len(entries) else datetime.max
                points={};previous=None
                for w in windows[e['index']:e['index']+120]:
                    elapsed=int((w.window_start-e['at']).total_seconds()//60)
                    if w.window_start>=stop or not w.measured or (previous and previous.window_end!=w.window_start):break
                    from apps.api.app.context_profiles import supported_context
                    if supported_context(w)!=context:break
                    if 1<=elapsed<=120:points[str(elapsed)]=[w.features[f] for f in PHYSICAL]
                    previous=w
                if len(points)<5:counts['censored_short_response']+=1;continue
                example={'event_id':e['event_id'],'machine':machine,'module':module,'at':e['at'].isoformat(),
                    'direction':direction,'origin_context':regime['context'],'context':context,'points':points,
                    'origin_center':center,'origin_scale':scale,'split':split,'observed_minutes':len(points),
                    'source_digest':receipts[machine,day]['source_sha256']}
                (examples if split=='reference' else holdout).append(example);counts[split]+=1
    provenance={'study_id':study['study_id'],'source_timezone':'Asia/Bangkok','pressure_unit':'psi',
        'minute_files':[{'machine':m,'day':d,'sha256':h} for (m,d),h in sorted(verified.items())],
        'event_files':events_verified,'split':'per-parent-model disjoint Reference and threshold-calibration days',
        'healthy_review':'PENDING','counts':dict(counts),'max_event_minutes':120}
    catalog=fit_catalog(examples,source_bundle_id=fleet.bundle_id,provenance=provenance)
    validation=validate_holdout(catalog,holdout)
    from apps.api.app.fleet_transitions import attach_holdout
    attach_holdout(catalog,validation)
    data=read_package(package);payloads={k:json.loads(v) if k.endswith('.json') else v for k,v in data.items() if k!='manifest.json'}
    payloads['priors.json']['transition_catalog']=catalog
    payloads['validation.json']['transition_event_holdout']=validation
    payloads['curation.json']['transition_reference']={'version':catalog['version'],'healthy_review':'PENDING','parent_bundle_id':fleet.bundle_id}
    payloads['provenance.json']['transition_sources']=provenance
    metadata={k:v for k,v in json.loads(data['manifest.json']).items() if k not in ('schema','semantics','bundle_id','files','release_state','alert_vote')}
    metadata.update(parent_bundle_id=fleet.bundle_id,transition_version=catalog['version'])
    path=write_package(output_root,payloads,metadata=metadata)
    progress(f'Frozen {path.name}')
    return {'bundle_id':path.name,'path':str(path),'groups':len(catalog['groups']),'reference_events':len(examples),
            'validation':validation,'elapsed_seconds':time.perf_counter()-started}


def validate_holdout(catalog,examples):
    groups={(g['machine'],g['module'],g['direction'],g['origin_context'],g['context']):g for g in catalog['groups']}
    events=[]
    for e in examples:
        g=groups.get((e['machine'],e['module'],e['direction'],e['origin_context'],e['context']))
        evaluated=outside=0
        if g:
            import numpy as np
            for minute,p in e['points'].items():
                envelope=g['curve'].get(minute)
                if not envelope:continue
                x=(np.asarray(p)-e['origin_center'])/e['origin_scale']
                evaluated+=1;outside+=int(np.max(np.abs(x-envelope['center'])/envelope['radius'])>1)
        events.append({k:e[k] for k in ('event_id','machine','module','at','direction','observed_minutes')}|{'evaluated_minutes':evaluated,'outside_minutes':outside,'group_id':g['group_id'] if g else None})
    return {'version':'whole-event-heldout-v1','fitted_events':sum(g['events'] for g in catalog['groups']),
        'heldout_events':len(events),'evaluated_events':sum(e['evaluated_minutes']>0 for e in events),
        'evaluated_minutes':sum(e['evaluated_minutes'] for e in events),'outside_minutes':sum(e['outside_minutes'] for e in events),
        'events':events,'healthy_review':'PENDING','prospective':False,
        'interpretation':'Independent historical event-response coverage, not healthy false-positive accuracy or untouched future acceptance'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True)
    a=p.parse_args();result=enrich(a.package,a.source_root,a.output_root,lambda x:print(x,flush=True));print(json.dumps(result,ensure_ascii=False,indent=2))
