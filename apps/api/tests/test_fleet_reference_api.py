from datetime import datetime
import json
import hashlib
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.api.app import fleet_reference_api as api


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'ROOT',tmp_path)
    (tmp_path/'minutes').mkdir()
    study={'study_id':str(tmp_path),'derived_version':'test-v1','source_machine_order':['041','058'],
           'source_days':[{'machine':'041','date':'2026-09-15','source_sha256':'a'*64}],
           'variants':[{'machine':'041','module':1},{'machine':'058','module':2}],
           'coverage':[{'machine':'041','module':1}], 'transition_summary':[], 'activation_eligible':False}
    (tmp_path/'summary.json').write_text(json.dumps(study),encoding='utf-8')
    rows=[]
    for module in (1,2):
        rows.append(dict(time=datetime(2026,9,15),module=module,quality=True,context='SV_OFF',coverage=1,
                         stable_control=True,compressor='run',module_state='on',busy='0',sv='off',valve=94.,
                         hp1=module,lp1=2.,hp2=220.,lp2=20.,temphi=30.,templo=40.))
    pd.DataFrame(rows).to_parquet(tmp_path/'minutes/041_2026-09-15.parquet',index=False)
    study['source_days'][0]['minute_parquet_sha256']=hashlib.sha256((tmp_path/'minutes/041_2026-09-15.parquet').read_bytes()).hexdigest()
    (tmp_path/'summary.json').write_text(json.dumps(study),encoding='utf-8')
    (tmp_path/'minutes/041_2026-09-15.json').write_text(json.dumps({'source_sha256':'a'*64,'derived_version':'test-v1'}),encoding='utf-8')
    app=FastAPI();app.include_router(api.router)
    return TestClient(app),tmp_path


def test_filter_machine_module_and_bound_invalid_inputs(client):
    c,_=client
    response=c.get('/api/v1/calibration/fleet/reference?machine_number=HT9046MX-041&module=1')
    assert response.status_code==200
    body=response.json();assert body['machine']=='041' and len(body['variants'])==1
    assert body['mode']=='RESEARCH_REFERENCE_NOT_ACTIVE' and not body['activation_eligible']
    assert c.get('/api/v1/calibration/fleet/reference?machine_number=MX080').status_code==404
    assert c.get('/api/v1/calibration/fleet/reference?machine_number=041&module=9').status_code==422
    assert c.get('/api/v1/calibration/fleet/day?machine_number=041&day=2026-07-01').status_code==422
    assert c.get('/api/v1/calibration/fleet/day?machine_number=../../secret&day=2026-09-15').status_code==422


def test_chart_reads_only_selected_module_and_rejects_source_revision(client):
    c,path=client
    first=c.get('/api/v1/calibration/fleet/day?machine_number=041&module=1&day=2026-09-15').json()
    second=c.get('/api/v1/calibration/fleet/day?machine_number=041&module=2&day=2026-09-15').json()
    assert first['chart'][0]['features']['hp1']==1 and second['chart'][0]['features']['hp1']==2
    assert first['chart'][0]['features']['dp2']==200
    (path/'minutes/041_2026-09-15.json').write_text(json.dumps({'source_sha256':'b'*64,'derived_version':'test-v1'}),encoding='utf-8')
    assert c.get('/api/v1/calibration/fleet/day?machine_number=041&module=1&day=2026-09-15').status_code==409


def test_changed_derivative_rejected_even_after_cached_read(client):
    c,path=client;url='/api/v1/calibration/fleet/day?machine_number=041&module=1&day=2026-09-15'
    assert c.get(url).status_code==200
    file=path/'minutes/041_2026-09-15.parquet'
    data=pd.read_parquet(file);data['hp1']=999.;data.to_parquet(file,index=False)
    assert c.get(url).status_code==409


def test_many_machine_module_views_remain_cached_and_isolated(monkeypatch):
    from apps.api.app import context_reads as reads
    from collections import OrderedDict
    import gzip
    monkeypatch.setattr(reads,'_wire_cache',OrderedDict())
    monkeypatch.setattr(reads,'_wire_bytes',0)
    monkeypatch.setattr(reads,'_cache',OrderedDict())
    built=[]
    for _ in range(2):
        for machine in ('017','041','058','080','081'):
            for module in range(1,9):
                for view in ('reference','day'):
                    key=('fleet-cache-regression',machine,module,view)
                    def build(key=key):
                        built.append(key)
                        return {'machine':key[1],'module':key[2],'view':key[3]}
                    response=reads.inspection_response(key,build,accept_encoding='gzip')
                    assert json.loads(gzip.decompress(response.body))=={'machine':machine,'module':module,'view':view}
    assert len(built)==80


def test_stable_version_pin_isolation_and_bad_package_cannot_fall_back(client,monkeypatch):
    from types import SimpleNamespace
    from apps.api.app import fleet_bundle as bundle
    from apps.api.tests.test_fleet_stable import profile
    c,path=client
    model=profile();model['machine']='041';model['local_absolute_reference']['machine']='041'
    package=bundle.write_package(path/'packages',{'models.json':[model],'priors.json':{},'curation.json':{},
        'provenance.json':{},'validation.json':{},'README.md':b'Shadow'},
        metadata={'source_machines':['041'],'blockers':['NORMAL_REVIEW']})
    store=path/'store';identity=bundle.install(store,package)
    bundle.switch(store,identity,expected_revision=0,actor='QA',reason='reference')
    monkeypatch.setattr(api,'get_settings',lambda:SimpleNamespace(fleet_stable_store=store,fleet_reference_root=None,project_root=path))
    response=c.get('/api/v1/calibration/fleet/stable/reference?machine_number=041&module=1')
    assert response.status_code==200 and response.json()['alert_vote'] is False
    url='/api/v1/calibration/fleet/stable/day?machine_number=041&module=1&day=2026-09-15'
    assert c.get(url+'&bundle_id=stale').status_code==409
    assert c.get(url+'&bundle_id='+identity).json()['counts']=={'NOT_EVALUATED':1}
    assert c.get(url+'&module=9').status_code==422
    (store/identity/'models.json').write_text('[]')
    assert c.get(url).status_code==409
    assert c.get('/api/v1/calibration/fleet/stable/reference?machine_number=041').status_code==409
