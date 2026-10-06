"""Frozen event-response proposals. No fitting/scoring of future inputs here.

Fleet transfers relative response, never donor absolute levels. Every proposal
retains source examples and still requires local reference review/validation.
"""
from collections import defaultdict
from copy import deepcopy
import math
import numpy as np
from .observed_context import PHYSICAL
from .unified_events import fingerprint

VERSION = 'fleet-relative-transition-v1'
MIN_DONORS = 2
MIN_EVENTS = 6
MIN_DAYS = 3
PRIOR_EVENTS = 3


def eight(center, scale):
    c=list(map(float,center));s=list(map(float,scale))
    return [*c[:4],c[0]-c[1],c[2]-c[3],*c[4:]], [*s[:4],math.hypot(s[0],s[1]),math.hypot(s[2],s[3]),*s[4:]]


def signature(key):
    parts=key.split('|')
    if len(parts)!=3 or not parts[1].startswith('FROM_'):raise ValueError('invalid transition key')
    return parts[0].casefold(),parts[1][5:],parts[2]


def validate_catalog(catalog):
    if catalog.get('version')!=VERSION or catalog.get('automatic_normal_acceptance') is not False:
        raise ValueError('incompatible transition catalog')
    groups=catalog.get('groups',[])
    if len(groups)>500:raise ValueError('transition group budget exceeded')
    for g in groups:
        if not 1<=g['module']<=8 or len(g['examples'])>250 or len(g['curve'])>120:
            raise ValueError('transition evidence budget exceeded')
        for p in g['curve'].values():
            for name in ('center','radius'):
                a=np.asarray(p[name],float)
                if a.shape!=(8,) or not np.isfinite(a).all() or (name=='radius' and (a<=0).any()):
                    raise ValueError('invalid frozen transition curve')
    return catalog


def fit_catalog(examples, *, source_bundle_id, provenance):
    """One example is a source event, not 120 independent minute samples.

    Caller supplies only declared Reference events; holdout events are never
    admitted to the envelope fit. Context and direction remain separate.
    """
    grouped=defaultdict(list)
    for e in examples:
        if e['split']!='reference':continue
        grouped[(e['machine'],e['module'],e['direction'],e['origin_context'],e['context'])].append(e)
    groups=[]
    for key,values in sorted(grouped.items()):
        values=sorted(values,key=lambda x:(x['at'],x['event_id']))[:60]
        bins=defaultdict(list)
        for e in values:
            c=np.asarray(e['origin_center']);s=np.asarray(e['origin_scale'])
            for elapsed,p in e['points'].items():
                if 1<=int(elapsed)<=120:bins[elapsed].append((np.asarray(p)-c)/s)
        curve={}
        for minute,points in sorted(bins.items(),key=lambda x:int(x[0])):
            if len(points)<3:continue
            low,c,hi=np.quantile(points,[.05,.5,.95],axis=0)
            curve[minute]={'center':c.tolist(),'radius':np.maximum(.25,np.maximum(c-low,hi-c)).tolist(),'events':len(points)}
        days=len({e['at'][:10] for e in values})
        groups.append({'group_id':fingerprint([VERSION,key,curve]),'machine':key[0],'module':key[1],
            'direction':key[2],'origin_context':key[3],'context':key[4],
            'origin_center':values[0]['origin_center'],'origin_scale':values[0]['origin_scale'],
            'curve':curve,'events':len(values),'days':days,
            'examples':[{k:e[k] for k in ('event_id','at','machine','module','source_digest','observed_minutes')} for e in values],
            'reference_review_required':True})
    return validate_catalog({'version':VERSION,'source_bundle_id':source_bundle_id,'groups':groups,
        'automatic_normal_acceptance':False,'provenance':provenance,
        'method':'Reference-only robust relative event curves; capped event-count partial pooling',
        'grouping':'Module index and observed contexts are research strata; hardware/configuration equivalence still needs review'})


def compatible(origin, donor):
    # Similarity screen, not certified engineering limits. Absolute comparison
    # uses explicit relative-coordinate floors, not tiny sensor noise scales.
    c=np.asarray(origin['center']);d=np.asarray(donor['origin_center'])
    tolerance=np.maximum(5.,.15*np.maximum(np.abs(c[:6]),np.abs(d[:6])))
    scale=np.r_[tolerance,[15.,15.]]
    distance=float(np.sqrt(np.mean(((c-d)/scale)**2)))
    return distance<=1.5,distance


def attach_holdout(catalog,validation):
    """Independent event coverage screens proposals; stability is not health."""
    by_group=defaultdict(list)
    for e in validation['events']:
        if e.get('group_id') and e['evaluated_minutes']:by_group[e['group_id']].append(e)
    for g in catalog['groups']:
        events=by_group[g['group_id']];minutes=sum(e['evaluated_minutes'] for e in events)
        outside=sum(e['outside_minutes'] for e in events);days=len({e['at'][:10] for e in events})
        passed=len(events)>=3 and days>=3 and minutes>=30 and outside/minutes<=.1
        g['holdout']={'events':len(events),'days':days,'evaluated_minutes':minutes,'outside_minutes':outside,
            'passed':passed,'normal_review':'PENDING','max_outside_fraction':.1,
            'reason':'HISTORICAL_RESPONSE_SCREEN_PASSED' if passed else 'INDEPENDENT_RESPONSE_VALIDATION_REQUIRED'}
    return catalog


def propose(model, catalog, bundle_id):
    validate_catalog(catalog)
    target=model['machine_number'].removeprefix('MX')
    origins={r['regime_id']:r for r in model['regimes'] if r['coverage_supported']}
    proposals=[];rejected=[]
    for local in model['transition_templates']:
        direction,rid,context=signature(local['key']);origin=origins.get(rid)
        if not origin:
            rejected.append({'key':local['key'],'reason':'OBSERVED_ORIGIN_REFERENCE_REQUIRED'});continue
        candidates=[g for g in catalog['groups'] if g['machine']!=target and g['module']==model['module']
            and g['direction']==direction and g['context']==context and g['origin_context']==origin['context']]
        admitted=[];receipts=[]
        for donor in candidates:
            ok,distance=compatible(origin,donor)
            tested=donor.get('holdout',{}).get('passed') is True
            receipts.append({'machine':donor['machine'],'group_id':donor['group_id'],'eligible':ok and tested,'distance':distance,'holdout':donor.get('holdout'),
                             'reason':'INDEPENDENT_RESPONSE_VALIDATION_REQUIRED' if not tested else 'ORIGIN_INCOMPATIBLE' if not ok else 'ELIGIBLE_FOR_REVIEW',
                             'examples':donor['examples'][:3]})
            ok=ok and tested
            if ok:admitted.append(donor)
        machines=sorted({g['machine'] for g in admitted});events=sum(g['events'] for g in admitted)
        days=len({e['at'][:10] for g in admitted for e in g['examples']})
        if len(machines)<MIN_DONORS or events<MIN_EVENTS or days<MIN_DAYS:
            rejected.append({'key':local['key'],'reason':'COMPATIBLE_FLEET_EVENT_COVERAGE_INSUFFICIENT',
                             'donor_machines':machines,'events':events,'days':days,'transfer_receipts':receipts});continue
        c=np.asarray(origin['center']);s=np.asarray(origin['scale']);curve={}
        for minute in sorted({m for g in admitted for m in g['curve']},key=int):
            votes=[g['curve'][minute] for g in admitted if minute in g['curve']]
            # Machines vote equally; one high-rate donor cannot overwhelm peers.
            if len(votes)<MIN_DONORS:continue
            nc=np.median([v['center'] for v in votes],axis=0)
            nr=np.maximum.reduce([np.asarray(v['radius'])+np.abs(np.asarray(v['center'])-nc) for v in votes])
            fleet_c=c+nc*s;fleet_r=np.maximum(.1,nr*s)
            own=local['curve'].get(minute);n=int(own['events']) if own else 0
            weight=PRIOR_EVENTS/(PRIOR_EVENTS+n)
            pc=weight*fleet_c+(1-weight)*np.asarray(own['center']) if own else fleet_c
            pr=(weight*fleet_r+(1-weight)*np.asarray(own['radius'])+weight*(1-weight)*np.abs(fleet_c-np.asarray(own['center']))) if own else fleet_r
            # Delta channels follow the transferred physical pressures.
            pc[4]=pc[0]-pc[1];pc[5]=pc[2]-pc[3]
            pr[4]=pr[0]+pr[1];pr[5]=pr[2]+pr[3]
            curve[minute]={'center':pc.tolist(),'radius':pr.tolist(),'events':events+n,'local_events':n,'fleet_weight':weight}
        if not curve:continue
        provenance={'version':VERSION,'bundle_id':bundle_id,'catalog_source_bundle_id':catalog['source_bundle_id'],
            'donor_machines':machines,'source_group_ids':[g['group_id'] for g in admitted],
            'transfer_receipts':receipts,'prior_events':PRIOR_EVENTS,'local_events':local['events'],
            'automatic_normal_acceptance':False,'local_absolute_reference_preserved':True,
            'examples':[e for g in admitted for e in g['examples']][:250]}
        template={'key':local['key'],'curve':curve,'events':events+local['events'],'days':days,
            'coverage_supported':True,'reference_review_required':True,'examples':local['examples'],
            'fleet_assistance':provenance}
        template['template_id']=fingerprint([model['profile_id'],VERSION,template])[:20]
        proposals.append(template)
    return {'bundle_id':bundle_id,'profile_id':model['profile_id'],'version':VERSION,'templates':proposals,'rejected':rejected,
            'interpretation':'Proposed relative responses only; accept local origin and review source/configuration and Normal evidence before freezing'}


def apply_selection(base, fleet, selected_ids):
    catalog=fleet.priors().get('transition_catalog')
    if not catalog:raise ValueError('FLEET_TRANSITION_CATALOG_NOT_PREPARED')
    result=propose(base,catalog,fleet.bundle_id)
    selected=set(selected_ids);allowed={t['template_id']:t for t in result['templates']}
    if not selected<=allowed.keys():raise ValueError('FLEET_TEMPLATE_CHANGED_OR_UNSUPPORTED')
    model=deepcopy(base)
    # A reviewed Fleet alternative replaces an unaccepted local proposal for
    # that key, rather than silently shadowing an accepted Local template.
    keys={allowed[t]['key'] for t in selected}
    model['transition_templates']=[t for t in model['transition_templates'] if t['key'] not in keys]+[allowed[t] for t in sorted(selected)]
    model['fleet_transition_bundle_id']=fleet.bundle_id
    return model
