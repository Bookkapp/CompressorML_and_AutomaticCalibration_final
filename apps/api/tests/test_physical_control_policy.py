"""Version compatibility, quantile ties, control separation and leakage checks."""
from dataclasses import replace
from datetime import timedelta
import json
from sqlalchemy import text
from apps.api.app.qualified_policy import THRESHOLD_VERSION, LEGACY_THRESHOLD_VERSION, manifest
from apps.api.app.qualified_scoring import QualifiedShadowScorer, TemporalParameters
from apps.api.tests.test_qualified_temporal import _window, _profile
from apps.api.tests.test_reference_review import config, selection, windows
from apps.api.app.reference_review import selected_candidate, make_preview, bounds
from apps.api.app.reference_selector import propose
from apps.api.app.calibration_recovery import review


def test_frozen_v1_ties_preserved_v2_strict_and_control_not_voting():
    old=_profile(threshold=5)
    new=replace(old,threshold_version=THRESHOLD_VERSION)
    valve=replace(_window(),features={**_window().features,'valve':old.medians['valve']-5})
    assert QualifiedShadowScorer().score(valve,old).primary_raw_flag is True
    physical=QualifiedShadowScorer().score(valve,new)
    assert physical.primary_raw_flag is False and physical.control_z==-5
    assert 'valve' not in physical.primary_features
    assert QualifiedShadowScorer().score(_window(hp2_shift=5),new).primary_raw_flag is False
    assert QualifiedShadowScorer().score(_window(hp2_shift=5.01),new).primary_raw_flag is True
    assert QualifiedShadowScorer().score(_window(),replace(new,threshold_version='unknown')).status=='NOT_SCORED'


def test_v2_pressure_persistence_and_checkpoint_exact():
    profile=replace(_profile(),threshold_version=THRESHOLD_VERSION)
    scorer=QualifiedShadowScorer()
    for i in range(3):result=scorer.score(_window(i,hp2_shift=10),profile)
    assert result.primary_persistent_flag and result.dominant_feature=='hp2'
    restored=QualifiedShadowScorer.from_checkpoint(json.loads(json.dumps(scorer.checkpoint())),TemporalParameters())
    assert restored.score(_window(3,hp2_shift=10),profile)==scorer.score(_window(3,hp2_shift=10),profile)


def test_control_cannot_quarantine_drift_or_select_reference_and_shadow_never_fits():
    s=selection();rows=windows(s);_,_,shadow_start,_=bounds(s)
    original=selected_candidate(rows,s,config())
    # Extreme actuator values do not broaden physical scales or alter selection.
    controls=[replace(w,features={**w.features,'valve':1e6 if w.window_start<shadow_start else 1e8}) for w in rows]
    changed=selected_candidate(controls,s,config())
    assert changed['threshold']==original['threshold']
    assert changed['quarantine_pct']==original['quarantine_pct']
    assert changed['validation']['shadow_flag_pct']==original['validation']['shadow_flag_pct']
    a=propose(controls,s,config())['selected'];b=propose(rows,s,config())['selected']
    assert {k:v for k,v in a.items() if k!='control_daily_span_rz'}=={k:v for k,v in b.items() if k!='control_daily_span_rz'}
    future=[replace(w,features={f:1e9 for f in w.features}) if w.window_start>=shadow_start else w for w in rows]
    new=selected_candidate(future,s,config())
    assert new['statistics']==original['statistics'] and new['threshold']==original['threshold']
    evidence=make_preview(controls,s,config(),candidate=changed)['diagnostics']
    assert evidence['scoring_policy']==manifest() and evidence['control']['votes'] is False


def test_loader_accepts_complete_v2_and_keeps_v1_without_reinterpretation():
    from apps.api.tests.test_qualified_active_loader import registry,load
    engine=registry()
    assert list(load(engine).values())[0].threshold_version==LEGACY_THRESHOLD_VERSION
    with engine.begin() as c:
        row=c.execute(text('SELECT statistics_json,threshold_json FROM ht9046mx_calibration_profile')).mappings().one()
        stats=json.loads(row['statistics_json']);th=json.loads(row['threshold_json'])
        stats['scoring_policy']=manifest();th.update(threshold_version=THRESHOLD_VERSION,scoring_policy=manifest())
        c.execute(text('UPDATE ht9046mx_calibration_profile SET statistics_json=:s,threshold_json=:t'),{'s':json.dumps(stats),'t':json.dumps(th)})
    assert list(load(engine).values())[0].threshold_version==THRESHOLD_VERSION
    with engine.begin() as c:
        th['scoring_policy']['control_votes']=True
        c.execute(text('UPDATE ht9046mx_calibration_profile SET threshold_json=:t'),{'t':json.dumps(th)})
    assert load(engine)=={}


def test_recovery_has_no_shadow_fit_no_suppression_and_gap_not_recovered():
    s=selection();start,_,shadow_start,_=bounds(s)
    base={f:{'median':100.,'scale':1.} for f in _window().features}
    events=[]
    for day in [start,start+timedelta(days=1),start+timedelta(days=2),shadow_start]:
        onset=replace(_window(),machine_number=s['machine_number'],module=s['module'],window_start=day,window_end=day+timedelta(minutes=1),features=None,data_quality_status='STATE_NOT_ELIGIBLE',reason='BYPASS_OR_UNKNOWN_SV')
        events.append(onset)
        for i in range(1,9):
            t=day+timedelta(minutes=i);features={f:100. for f in base};features['hp2']=100.+(10 if i<4 else 0)
            events.append(replace(_window(),machine_number=s['machine_number'],module=s['module'],window_start=t,window_end=t+timedelta(minutes=1),features=features))
    r=review(events,s,base,5.)
    assert r['supported'] and r['reference_events']==3 and r['events'][0]['assessment']=='recovery_similar_to_reference'
    assert not r['suppresses_flags'] and not r['healthy_confirmed'] and not r['shadow_used_for_fit']
    changed=[replace(w,features={f:1e9 for f in base}) if w.eligible and w.window_start>=shadow_start else w for w in events]
    other=review(changed,s,base,5.)
    assert other['reference_trajectory']==r['reference_trajectory']
    assert not other['events'][0]['returned']
    gap=[w for w in events if w.window_start!=shadow_start+timedelta(minutes=4)]
    assert not review(gap,s,base,5.)['events'][0]['returned']


def test_old_stable_regime_requires_human_reference_selection():
    from apps.api.tests.test_calibration_evidence import proposal_rows
    settings,s,rows=proposal_rows()
    # Make the most recent fortnight alternate operating levels daily while
    # the older fortnight is stable. The old block must not auto-replace it.
    start=bounds(s)[0]
    altered=[replace(w,features={**w.features,'hp2':w.features['hp2']+20*((w.window_start-start).days%2)})
        if w.window_start>=start+timedelta(days=14) else w for w in rows]
    p=propose(altered,s,settings)
    assert p['needs_review'] and not p['changed']
    assert p['selected']['end']==s['reference_end']
