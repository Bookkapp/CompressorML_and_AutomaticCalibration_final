"""Measured SQL minutes -> pinned Fleet Shadow; preserves active State Gate."""
from collections import defaultdict
from .inference import clean_machine_code
from .fleet_stable import FEATURES


def score_observed(fleet,machine,module,combined,current,active_model=None):
    from .context_scope import scope_of
    groups=defaultdict(list)
    for w in combined:
        control=w.control or {};counts=w.state_counts or {}
        states={key:next(iter(counts.get(name,{})),'') if len(counts.get(name,{}))==1 else ''
                for key,name in (('compressor','compressor'),('module_state','module'),('busy','busy'),('sv','sv'))}
        row={'time':w.window_start.isoformat(),'quality':w.measurement_quality=='PASS',
             'context':'SV_ON' if states['sv']=='on' else 'SV_OFF' if states['sv']=='off' else 'UNSUPPORTED',
             'stable_control':bool(w.context_key),**states,
             'valve':control.get('valve_mean'),**{f:(w.features or {}).get(f,float('nan')) for f in FEATURES}}
        groups['bounded_history'].append(row)
    scope=scope_of(active_model) if active_model else None
    points=[];included=scope['included_sv_states'] if scope else ['OFF','ON']
    lower=current[0].window_start.isoformat() if current else '9999'
    for _,rows in sorted(groups.items()):
        for row in rows:
            sv=str(row.get('sv','')).upper()
            if sv in {'OFF','ON'} and sv not in included:
                row['context']='UNSUPPORTED'  # Gate before model matrix scoring.
        result=fleet.evaluate(clean_machine_code(machine).removeprefix('MX'),module,rows,allow_day_boundary=True)
        for row,p in zip(rows,result['points']):
            if str(row.get('sv','')).upper() in {'OFF','ON'} and str(row['sv']).upper() not in included:
                p.update(assessment='NOT_EVALUATED',phase='STATE_GATE_EXCLUDED',reason='ACTIVE_PROFILE_STATE_EXCLUDED',
                         absolute_score=None,relationship_score=None,raw_flag=False,cp2_level_flag=False,persistent_flag=False)
            if p['time']>=lower:points.append(p)
    return {'bundle_id':fleet.bundle_id,'machine':machine,'module':module,'points':points,'alert_vote':False}
