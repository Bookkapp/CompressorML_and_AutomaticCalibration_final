from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
import json
import zipfile

import numpy as np
import pytest

from apps.api.app.fleet_assistance import fit_local
from apps.api.app.fleet_stable import FrozenFleet,semantic_quality
from apps.api.app import fleet_bundle as bundle


def profile(offset=0):
    x=np.random.default_rng(17).normal(size=(300,6))+[150,28,190+offset,19,80,-20]
    local=fit_local(x,machine='080',module=6,context='SV_OFF',reference_end='2026-08-01')
    return {**local,'reference_start':'2026-07-01','threshold':50.,'absolute_threshold':4.,
            'threshold_period':['2026-08-01','2026-08-05'],'local_absolute_reference':local,
            'fleet_weight':0.,'donor_machines':[],'activation_eligible':False}


def package(tmp_path,offset=0):
    return bundle.write_package(tmp_path,{'models.json':[profile(offset)],'priors.json':{},'curation.json':{},
        'provenance.json':{},'validation.json':{},'README.md':b'Shadow'},
        metadata={'source_machines':['080'],'blockers':['REVIEW']})


def rows(n=8):
    return [{'time':(datetime(2026,9,7,13)+timedelta(minutes=i)).isoformat(),'quality':True,'context':'SV_OFF',
             'stable_control':True,'compressor':'run','module_state':'on','busy':'0','sv':'off','valve':94.,
             **dict(zip(('hp1','lp1','hp2','lp2','temphi','templo'),[150.,28.,335.,27.,80.,-20.]))} for i in range(n)]


def test_flat_high_pressure_remains_flagged_and_local_frozen(tmp_path):
    fleet=bundle.load_package(package(tmp_path));result=fleet.evaluate('080',6,rows())
    assert all(p['raw_flag'] and p['cp2_level_flag'] for p in result['points'])
    assert result['points'][-1]['phase']=='STEADY_OBSERVATION'
    assert result['points'][-1]['persistent_flag']
    assert result['alert_vote'] is False


def test_bad_acquisition_is_quality_not_high_pressure_fault(tmp_path):
    fleet=bundle.load_package(package(tmp_path));data=rows()
    for i in range(2,5):
        data[i].update(hp1=580.2,lp1=580.2,hp2=580.2,lp2=580.2,temphi=-200.,templo=-200.)
    result=fleet.evaluate('080',6,data)
    assert result['counts']['DATA_QUALITY']==3
    assert all(not p['raw_flag'] and p['absolute_score'] is None for p in result['points'][2:5])
    assert not result['points'][5]['persistent_flag']
    assert semantic_quality([[150,28,335,27,80,-20]]).all()


def test_gap_context_and_explicit_bad_raw_minute_reset_persistence(tmp_path):
    fleet=bundle.load_package(package(tmp_path));data=rows()
    data[2]['semantic_bad']=True
    data[5]['context']='UNSUPPORTED'
    data[6]['time']='2026-09-07T13:07:00';data[7]['time']='2026-09-07T13:08:00'
    result=fleet.evaluate('080',6,data)['points']
    assert not any(p['persistent_flag'] for p in result)
    assert result[5]['assessment']=='NOT_EVALUATED'
    assert fleet.evaluate('080',7,rows())['counts']=={'NOT_EVALUATED':8}
    with pytest.raises(ValueError):fleet.evaluate('080',6,list(reversed(data)))


def test_tamper_rejected_after_warm_cached_load(tmp_path):
    pkg=package(tmp_path/'packages');store=tmp_path/'store';identity=bundle.install(store,pkg)
    bundle.switch(store,identity,expected_revision=0,actor='QA',reason='test')
    bundle.current_snapshot(store)
    target=store/identity/'models.json';target.write_text('[]')
    with pytest.raises(ValueError,match='checksum'):bundle.current_snapshot(store)


def test_atomic_revision_conflict_and_real_version_rollback(tmp_path):
    store=tmp_path/'store';a=package(tmp_path/'packages');b=package(tmp_path/'packages',offset=2)
    first=bundle.install(store,a);second=bundle.install(store,b)
    assert bundle.pointer(store)['bundle_id'] is None
    bundle.switch(store,first,expected_revision=0,actor='QA',reason='first')
    bundle.switch(store,second,expected_revision=1,actor='QA',reason='second')
    with pytest.raises(ValueError,match='stale'):bundle.switch(store,first,expected_revision=1,actor='QA',reason='stale')
    bundle.switch(store,first,expected_revision=2,actor='QA',reason='rollback')
    assert bundle.current_snapshot(store)[1].bundle_id==first
    assert len(bundle.pointer(store)['history'])==3


def test_zip_traversal_duplicate_or_incompatible_feature_rejected(tmp_path):
    pkg=package(tmp_path/'packages');file=tmp_path/'valid.zip';bundle.export_zip(pkg,file)
    assert bundle.load_package(file).bundle_id==pkg.name
    with zipfile.ZipFile(file,'a') as archive:archive.writestr('../outside.json','{}')
    with pytest.raises(ValueError):bundle.install(tmp_path/'store',file)
    model=profile();model['center'][2]=500
    # local reference shares a Python list in this synthetic fixture; sever it.
    model['local_absolute_reference']=profile()['local_absolute_reference']
    with pytest.raises(ValueError,match='preserve'):FrozenFleet({'bundle_id':'test','source_machines':[],'blockers':[]},[model],{})


def test_parallel_requests_are_isolated_and_public_results_cannot_mutate_model(tmp_path):
    fleet=bundle.load_package(package(tmp_path));original=fleet.evaluate('080',6,rows())
    fleet.models()[0]['center'][2]=9999
    with ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(lambda _:fleet.evaluate('080',6,rows()),range(40)))
    assert all(r==original for r in results)
    assert not fleet._compiled[('080',6,'SV_OFF')].center.flags.writeable


def test_context_label_cannot_bypass_manual_off_or_missing_valve_controls(tmp_path):
    fleet=bundle.load_package(package(tmp_path));data=rows(4)
    data[0]['busy']='1';data[1]['module_state']='off';data[2]['stable_control']=False;data[3]['valve']=float('nan')
    assert fleet.evaluate('080',6,data)['counts']=={'NOT_EVALUATED':4}


def test_derived_normal_transitions_and_quality_share_idempotent_common_ledger(tmp_path):
    from apps.api.app.fleet_stable_events import evidence_events
    from apps.api.app.unified_events import metadata,events,append_events
    from sqlalchemy import create_engine,select,func
    fleet=bundle.load_package(package(tmp_path));data=rows();data[4]['semantic_bad']=True
    result=fleet.evaluate('080',6,data);records=evidence_events(result,source_digest='a'*64)
    assert all(r['machine_number']=='MX080' for r in records)
    assert {r['family'] for r in records}=={'TRANSITION','ANOMALY','DATA_QUALITY'}
    engine=create_engine('sqlite:///:memory:');metadata.create_all(engine)
    with engine.begin() as connection:
        append_events(connection,records);append_events(connection,evidence_events(result,source_digest='a'*64))
        assert connection.execute(select(func.count()).select_from(events)).scalar()==len(records)


def test_retraining_plan_rejects_overlap_and_ambiguous_dates(monkeypatch):
    from notebooks.support import fleet_stable_build as build
    for name in ('BASE_FIT','BASE_CAL','MACHINES','OVERRIDES'):
        monkeypatch.setattr(build,name,getattr(build,name))
    plan={'fit':['2026-07-02','2026-08-15'],'calibration':['2026-08-15','2026-08-22'],
          'machines':['017','080'],'overrides':[{'machine':'080','module':6,'fit':['2026-08-27','2026-08-31'],
                                              'calibration':['2026-09-03','2026-09-07']}]}
    build.configure_plan(plan);assert build.OVERRIDES['080:6']['fit']==('2026-08-27','2026-08-31')
    with pytest.raises(ValueError,match='overlap'):build.configure_plan({**plan,'calibration':['2026-08-10','2026-08-22']})
    with pytest.raises(ValueError,match='ISO'):build.configure_plan({**plan,'fit':['20260702','2026-08-15']})


def test_fleet_raw_link_requires_verified_matching_source(tmp_path,monkeypatch):
    from apps.api.app.fleet_stable_events import evidence_events
    from apps.api.app import context_api
    from apps.api.app.context_storage import source_namespace
    from apps.api.app.config import Settings
    from fastapi import HTTPException
    settings=Settings(_env_file=None,source_timezone='Asia/Bangkok',source_db_name='QA-SOURCE')
    monkeypatch.setattr(context_api,'get_settings',lambda:settings)
    result=bundle.load_package(package(tmp_path)).evaluate('080',6,rows())
    unverified=evidence_events(result,source_digest='a'*64)[0]
    with pytest.raises(HTTPException,match='UNVERIFIED'):context_api.verify_event_source(unverified)
    valid=evidence_events(result,source_digest='a'*64,source_namespace=source_namespace(settings),verified_source_mapping=True)[0]
    context_api.verify_event_source(valid)
    settings2=settings.model_copy(update={'source_db_name':'OTHER-SOURCE'})
    monkeypatch.setattr(context_api,'get_settings',lambda:settings2)
    with pytest.raises(HTTPException,match='UNVERIFIED'):context_api.verify_event_source(valid)


def test_temporary_windows_rename_denial_preserves_atomic_old_pointer(tmp_path,monkeypatch):
    old=tmp_path/'shadow.json';old.write_text('old');new=tmp_path/'shadow.json.tmp';new.write_text('new')
    original=bundle.os.replace;calls=[]
    def temporarily_locked(source,target):
        calls.append(1)
        if len(calls)==1:
            assert old.read_text()=='old';raise PermissionError('temporary scanner/read lock')
        return original(source,target)
    monkeypatch.setattr(bundle.os,'replace',temporarily_locked);monkeypatch.setattr(bundle.time,'sleep',lambda _:None)
    bundle.atomic_replace(new,old)
    assert old.read_text()=='new' and len(calls)==2
