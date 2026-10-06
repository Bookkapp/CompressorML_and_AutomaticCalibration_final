"""Isolated fixtures; these tests never approve a real machine profile."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,date
import json
import time
import pytest
from sqlalchemy import create_engine,select,func
from apps.api.app.fleet_transitions import fit_catalog,attach_holdout,propose,apply_selection
from apps.api.app.context_profiles import fit_context_candidate,assess_context
from apps.api.tests.test_context_profiles import reference,minute
from apps.api.tests.test_fleet_stable import package
from apps.api.app.fleet_bundle import load_package,switch
from apps.api.app.context_validation import report
from apps.api.app.qualified_detector import DurableDetector
from apps.api.app.qualified_windows import WindowPolicy
from apps.api.tests.test_qualified_detector import raw
from apps.api.tests.test_qualified_stream import clock
from apps.api.app.unified_events import events
from apps.api.app import fleet_management as management


def proposals():
    model=fit_context_candidate(reference(),[],machine='MX017',module=1,shadow_start=datetime(2026,9,8),shadow_end=datetime(2026,9,11))
    model['profile_id']='a'*64;r=model['regimes'][0]
    key=f"SV_off_TO_on|FROM_{r['regime_id']}|RUN_MODULE_ON_BUSY0_SV_ON"
    model['transition_templates']=[{'template_id':'local','key':key,'events':1,'days':1,'curve':{},'coverage_supported':False,'examples':[]}]
    examples=[]
    for machine in ['024','041']:
        for d in range(3):
            examples.append({'split':'reference','machine':machine,'module':1,'direction':'sv_off_to_on',
                'origin_context':r['context'],'context':'RUN_MODULE_ON_BUSY0_SV_ON','at':f'2026-08-{d+1:02}T12:00:00',
                'event_id':f'{machine}/{d}','source_digest':'source','observed_minutes':20,
                'origin_center':r['center'],'origin_scale':r['scale'],
                'points':{str(m):r['center'] for m in range(1,21)}})
    catalog=fit_catalog(examples,source_bundle_id='base',provenance={})
    holdout={'events':[{'group_id':g['group_id'],'at':f'2026-08-{d+10:02}T12:00:00','evaluated_minutes':20,'outside_minutes':0}
        for g in catalog['groups'] for d in range(3)]}
    attach_holdout(catalog,holdout)
    return model,catalog


def test_independent_donor_gate_relative_pooling_and_unknown_origin():
    model,catalog=proposals();original=deepcopy(model)
    result=propose(model,catalog,'test-version')
    assert len(result['templates'])==1
    t=result['templates'][0]
    assert t['fleet_assistance']['donor_machines']==['024','041']
    assert model==original and t['curve']['1']['fleet_weight']==1
    model['transition_templates'][0]['curve']={'1':{'center':model['regimes'][0]['center'],'radius':[1]*8,'events':6}}
    assert propose(model,catalog,'test-version')['templates'][0]['curve']['1']['fleet_weight']==pytest.approx(1/3)
    model['transition_templates'][0]['key']=model['transition_templates'][0]['key'].replace('FROM_'+model['regimes'][0]['regime_id'],'FROM_UNKNOWN')
    assert not propose(model,catalog,'test-version')['templates']
    assert propose(model,catalog,'test-version')['rejected'][0]['reason']=='OBSERVED_ORIGIN_REFERENCE_REQUIRED'


def test_failed_or_unvalidated_holdout_cannot_be_selected():
    model,catalog=proposals()
    for g in catalog['groups']:g['holdout']['passed']=False
    assert not propose(model,catalog,'v')['templates']
    class Fleet:
        bundle_id='v'
        def priors(self):return {'transition_catalog':catalog}
    with pytest.raises(ValueError,match='UNSUPPORTED'):apply_selection(model,Fleet(),['forged-template'])
    # Calibration examples cannot train a response, even if passed accidentally.
    assert not fit_catalog([{'split':'calibration'}],source_bundle_id='v',provenance={})['groups']


def test_fleet_curve_never_certifies_unknown_flat_absolute_level():
    model,catalog=proposals();r=model['regimes'][0];key=model['transition_templates'][0]['key']
    points=[minute(datetime(2026,9,8)+timedelta(minutes=i),hp2=500) for i in range(45)]
    points=[replace(w,context_key='run|on|0|on') for w in points]
    curve={str(i):{'center':list(points[0].features.values()),'radius':[10000]*8,'events':10} for i in range(1,45)}
    # Use the physical field order, not dict insertion order.
    from apps.api.app.observed_context import PHYSICAL
    for p in curve.values():p['center']=[points[0].features[f] for f in PHYSICAL]
    model['transition_templates']=[{'template_id':'fleet','key':key,'curve':curve,'coverage_supported':True,'fleet_assistance':{}}]
    # Truthy provenance identifies a Fleet alternative.
    model['transition_templates'][0]['fleet_assistance']={'bundle_id':'v'}
    before=[minute(datetime(2026,9,7,23,30)+timedelta(minutes=i),hp2=r['center'][2],temphi=r['center'][6]) for i in range(30)]
    control=[{'event_id':'e','occurred_at':'2026-09-08T00:00:00','module':1,'event_type':'SV_CHANGED',
              'payload_json':json.dumps({'details':{'before':'off','after':'on','witness_usable':True}})}]
    result=assess_context(before+points,control,model)
    assert result[-1]['category']!='WITHIN_PROPOSED_TRANSITION'


def test_saved_validation_no_leakage_and_separate_denominators():
    model={'profile_id':'p','shadow_start':'2026-09-08T00:00:00','shadow_end':'2026-09-09T00:00:00',
           'reference_review':{'at':'2026-10-06T01:00:00+00:00'}}
    def day(_):return {'chart':[{'time':f'2026-09-08T00:0{i}:00','category':c,'coverage':1}
        for i,c in enumerate(['WITHIN_PROPOSED_STEADY','STEADY_DEVIATION','STATE_GATE_EXCLUDED','INSUFFICIENT_REFERENCE','DATA_UNAVAILABLE'])]}
    value=report(model,date(2026,9,8),date(2026,9,9),day)
    assert value['supported_minutes']==2 and value['flag_burden_pct']==50
    assert value['excluded_state_minutes']==1 and value['unsupported_minutes']==1 and value['quality_minutes']==1
    assert value['false_alert_rate'] is None and value['fault_detection_delay'] is None
    assert value['earliest_prospective_day']=='2026-10-07' and not value['prospective_verified']
    with pytest.raises(ValueError,match='saved Shadow'):report(model,date(2026,9,1),date(2026,9,9),day)


def test_worker_fleet_restart_retry_and_atomic_unified_events(tmp_path):
    fleet=load_package(package(tmp_path))
    e=create_engine('sqlite://');policy=WindowPolicy('UTC',late_arrival_seconds=30)
    worker=DurableDetector(e,policy,fleet=fleet);worker.create_tables()
    run=worker.initialize('MX080',(6,),{})
    data=raw(range(300),shifted=True)
    def crash():raise RuntimeError('injected failure')
    with pytest.raises(RuntimeError):worker.cycle(run,data,as_of=clock(300),profiles={},before_commit=crash)
    with e.connect() as c:assert c.execute(select(func.count()).select_from(events)).scalar()==0
    worker.cycle(run,data,as_of=clock(300),profiles={})
    restored=DurableDetector(e,policy,fleet=fleet)
    restored.cycle(run,data+raw(range(300,600),shifted=True),as_of=clock(600),profiles={})
    with e.connect() as c:
        rows=c.execute(select(events).where(events.c.event_type=='FLEET_PERSISTENT_EVIDENCE')).mappings().all()
        assert len(rows)==1 and rows[0]['mode']=='SHADOW'
        count=c.execute(select(func.count()).select_from(events)).scalar()
    restored.cycle(run,data+raw(range(300,600),shifted=True),as_of=clock(600),profiles={})
    with e.connect() as c:assert c.execute(select(func.count()).select_from(events)).scalar()==count
    different=DurableDetector(e,policy,fleet=load_package(package(tmp_path,offset=3)))
    assert different.initialize('MX080',(6,),{})!=run
    with pytest.raises(ValueError,match='Fleet version changed'):
        different.cycle(run,raw(range(600,660)),as_of=clock(690),profiles={})


def test_kernel_lease_recovery_and_plan_quarantine(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir()
    (source/'summary.json').write_text(json.dumps({'source_machine_order':['080'],'source_days':[{'machine':'080','date':'2026-07-05'},{'machine':'080','date':'2026-08-16'}]}))
    req=management.TrainRequest(fit=['2026-07-02','2026-08-15'],calibration=['2026-08-15','2026-08-22'],machines=['080'],reason='Fixture training only')
    plan=management.validate_plan(req,source)
    assert plan['overrides'][0]['fit']==['2026-08-27','2026-08-31']
    monkeypatch.setattr(management,'paths',lambda:(tmp_path/'store',source))
    job=management.create_job(req,'QA',launch=False)
    with pytest.raises(ValueError,match='running'):management.create_job(req,'QA',launch=False)
    file=tmp_path/'store/training'/job['job_id']/'job.json';v=json.loads(file.read_bytes());v.update(status='RUNNING',updated_epoch=time.time()-120);management.save(file,v)
    with management.lease(tmp_path/'store/training/worker.lock'):
        assert management.jobs(tmp_path/'store')[0]['status']=='RUNNING'
    assert management.jobs(tmp_path/'store')[0]['status']=='INTERRUPTED'


def test_fleet_worker_excludes_state_before_scoring_and_preserves_midnight():
    from apps.api.app.context_scope import make_scope
    from apps.api.app.fleet_worker import score_observed
    at=datetime(2026,9,8,23,58)
    off=[minute(at+timedelta(minutes=i)) for i in range(4)]
    on=replace(off[-1],window_start=at+timedelta(minutes=4),window_end=at+timedelta(minutes=5),
               context_key='run|on|0|on',state_counts={**off[-1].state_counts,'sv':{'on':60}})
    class Fleet:
        bundle_id='v'
        def evaluate(self,machine,module,rows,*,allow_day_boundary=False):
            assert allow_day_boundary and len(rows)==5
            assert rows[-1]['context']=='UNSUPPORTED'
            return {'points':[{'time':r['time'],'assessment':'REVIEW','phase':'STEADY_OBSERVATION',
                'persistent_flag':True,'raw_flag':True,'cp2_level_flag':True,'absolute_score':100,'relationship_score':100} for r in rows]}
    model={'reference_review':{'evaluation_scope':make_scope(['OFF'],'No validated ON reference')}}
    result=score_observed(Fleet(),'MX017',1,off+[on],off[2:]+[on],model)
    assert len(result['points'])==3 and result['points'][0]['persistent_flag']
    assert result['points'][-1]['absolute_score'] is None
    assert result['points'][-1]['phase']=='STATE_GATE_EXCLUDED'
