"""Retrospective recovery evidence, fitted on Reference only; never suppress flags.

The cache reports SV On OR unknown; that boundary is not a confirmed startup.
No healthy envelope, safety limit, automatic rebase or live phase vote is inferred.
"""
from datetime import datetime, timedelta
import numpy as np
from .qualified_policy import PHYSICAL_FEATURES, THRESHOLD_VERSION, crosses

VERSION = "reference-recovery-evidence-v1"


def review(windows, selection, baseline, threshold):
    if not baseline or not threshold:
        return {"version":VERSION,"reference_events":0,"supported":False,"events":[],"suppresses_flags":False}
    ref_end=datetime.fromisoformat(selection['reference_end'])
    shadow_start=datetime.fromisoformat(selection['shadow_start'])
    start=datetime.fromisoformat(selection['reference_start'])
    rows=sorted(windows,key=lambda w:w.window_start)
    by_time={w.window_start:w for w in rows}
    excluded=[(datetime.fromisoformat(x['start']),datetime.fromisoformat(x['end'])) for x in selection['exclusions']]
    def score(w):
        return max(abs((w.features[f]-baseline[f]['median'])/baseline[f]['scale']) for f in PHYSICAL_FEATURES)
    # Events stop at gaps/manual/state boundaries. A 120m scan cap bounds work,
    # not a grace period; all original flags remain counted and visible.
    events=[]
    for w in rows:
        if not w.eligible or w.window_start<start: continue
        prev=by_time.get(w.window_start-timedelta(minutes=1))
        if not prev or prev.eligible or prev.reason!='BYPASS_OR_UNKNOWN_SV': continue
        phase='reference' if w.window_start<ref_end else 'shadow' if w.window_start>=shadow_start else 'unused'
        if phase=='unused': continue
        boundary=ref_end if phase=='reference' else datetime.fromisoformat(selection['shadow_end'])
        samples=[]; below=0; returned=False
        for step in range(120):
            item=by_time.get(w.window_start+timedelta(minutes=step))
            if item is None or not item.eligible or item.window_start>=boundary: break
            if phase=='reference' and any(a<item.window_end and item.window_start<b for a,b in excluded): break
            value=score(item); samples.append(value)
            below=below+1 if not crosses(value,threshold,THRESHOLD_VERSION) else 0
            if below==3:
                returned=True;break
        if samples:
            events.append({'start':w.window_start.isoformat(),'end':(w.window_start+timedelta(minutes=len(samples))).isoformat(),
                'phase':phase,'returned':returned,'observed_minutes':len(samples),
                'recovery_minutes':len(samples)-3 if returned else None,
                'peak_score':max(samples),'scores':samples,'boundary':'SV_ON_OR_UNKNOWN_TO_QUALIFIED_OFF'})
    reference=[e for e in events if e['phase']=='reference' and e['returned'] and e['recovery_minutes']>0]
    supported=len(reference)>=3 and len({e['start'][:10] for e in reference})>=3
    duration=float(np.quantile([e['recovery_minutes'] for e in reference],.95)) if reference else None
    trajectory=[]
    if supported:
        for step in range(120):
            values=[e['scores'][step] for e in reference if len(e['scores'])>step]
            if len(values)>=3:
                trajectory.append({'elapsed_minute':step,'events':len(values),'p50_score':float(np.quantile(values,.5)),
                    'p95_score':float(np.quantile(values,.95))})
    for e in events:
        if e['phase']=='shadow':
            e['assessment']='not_returned_in_observed_run' if not e['returned'] else 'reference_examples_insufficient'
            if e['returned'] and supported:
                limits={p['elapsed_minute']:p['p95_score'] for p in trajectory}
                comparable=[i for i in range(min(e['recovery_minutes'],len(e['scores']))) if i in limits]
                similar=bool(comparable) and e['recovery_minutes']<=duration and all(e['scores'][i]<=limits[i] for i in comparable)
                e['assessment']='recovery_similar_to_reference' if similar else 'recovery_differs_from_reference'
        e.pop('scores')
    return {'version':VERSION,'reference_events':len(reference),'reference_event_days':len({e['start'][:10] for e in reference}),
        'supported':supported,'reference_recovery_p95_minutes':duration,'reference_trajectory':trajectory,
        'events':[e for e in events if e['phase']=='shadow'][:100],
        'suppresses_flags':False,'healthy_confirmed':False,'shadow_used_for_fit':False,
        'boundary_verified':False,'note':'SV On / unknown boundary needs Raw review. Three below-threshold minutes mark observed recovery, not healthy certification.'}
