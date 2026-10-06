from datetime import datetime,timedelta,timezone,date
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep
from sqlalchemy import create_engine,select
from apps.api.app.config import Settings
from apps.api.app import context_storage as storage
from apps.api.app import context_reads as reads
from apps.api.app.unified_events import events,metadata as event_meta
from apps.api.tests.test_context_events import sample,BASE
from apps.api.app.observed_context import build_observed_minutes
from apps.api.app.qualified_calibration import policy_from_settings


def test_frozen_day_survives_source_correction_and_module_filter(monkeypatch,tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"observed.sqlite"))
    for m in (storage.metadata,event_meta):m.create_all(engine)
    s=Settings(_env_file=None,source_timezone="UTC",source_db_name="fixture",source_table="raw")
    value={"hp2":200.,"revision":1,"reads":0}
    def read(settings,**kwargs):
        value["reads"]+=1
        rows=[sample(BASE+timedelta(seconds=i),Hp_2nd_1=value["hp2"]) for i in range(60)]
        kwargs["on_raw_batch"](rows)
        kwargs["revision_out"][BASE.date().isoformat()]=f'60:{value["revision"]}:1'
        return build_observed_minutes(rows,as_of=kwargs["as_of"],policy=policy_from_settings(settings),modules=range(1,9))
    monkeypatch.setattr(storage,"load_observed_one_minute_windows",read)
    monkeypatch.setattr(storage,"source_revision",lambda *a:f'60:{value["revision"]}:1')
    day=BASE.date();asof=(BASE+timedelta(days=2)).replace(tzinfo=timezone.utc)
    first,receipt=storage.load_day(s,engine,"MX017",day,as_of=asof)
    old_key=receipt["snapshot_key"]
    storage.load_day(s,engine,"MX017",day,as_of=asof)
    assert value["reads"]==1
    value.update(hp2=240.,revision=2)
    monkeypatch.setattr(storage,"TTL",timedelta(0))
    second,new=storage.load_day(s,engine,"MX017",day,as_of=asof)
    old=storage.read_day(engine,old_key,modules=(1,))
    assert old[0][0].features["hp2"]==200
    assert next(w for w in second if w.module==1).features["hp2"]==240
    assert receipt["source_digest"]!=new["source_digest"]
    with engine.connect() as conn:
        assert len(conn.execute(select(events).where(events.c.event_type=="SOURCE_REVISION_CHANGED")).all())==1


def test_inspection_reads_coalesce_ten_tabs_without_shared_mutable_results():
    calls=0;lock=Lock()
    def fetch():
        nonlocal calls
        with lock:calls+=1
        sleep(.1)
        return {"chart":[{"value":7}]}
    key=("fixture-ten-tabs",datetime.now().isoformat())
    with ThreadPoolExecutor(max_workers=10) as pool:
        values=list(pool.map(lambda _:reads.shared_read(key,fetch),range(10)))
    assert calls==1
    values[0]["chart"][0]["value"]=99
    assert values[1]["chart"][0]["value"]==7


def test_wire_inspections_share_immutable_compressed_bytes_and_preserve_values():
    import gzip,json
    calls=0;lock=Lock()
    def fetch():
        nonlocal calls
        with lock:calls+=1
        sleep(.05)
        return {"chart":[{"time":"2026-09-30T08:00:00","hp2":223.123456789}],"label":"ข้อมูลจริง"}
    key=("fixture-wire",datetime.now().isoformat())
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses=list(pool.map(lambda _:reads.inspection_response(key,fetch,accept_encoding="gzip;q=0.5"),range(10)))
    assert calls==1
    assert all(r.headers["content-encoding"]=="gzip" for r in responses)
    content=json.loads(gzip.decompress(responses[0].body))
    plain=reads.inspection_response(key,fetch,accept_encoding="gzip;q=0")
    assert "content-encoding" not in plain.headers and json.loads(plain.body)==content
    assert content["chart"][0]["hp2"]==223.123456789 and content["label"]=="ข้อมูลจริง"
