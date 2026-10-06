"""Review explanations, raw intake and past-only selection regression."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta
import json
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from apps.api.tests.test_reference_review import store,config,selection,windows,request,ready
from apps.api.app import reference_jobs as jobs, reference_raw as raw
from apps.api.app.reference_review import make_preview,selected_candidate,ReferencePreviewRequest,resolve_selection,bounds
from apps.api.app.reference_selector import propose
from apps.api.app.qualified_windows import FEATURES
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows


def test_shadow_locations_exact_threshold_contributor_and_no_fit_changes():
    s=selection();rows=windows(s);_,_,shadow_start,shadow_end=bounds(s)
    rows=[replace(w,features={**w.features,"hp2":w.features["hp2"]+10}) if w.window_start>=shadow_start else w for w in rows]
    candidate=selected_candidate(rows,s,config())
    before=json.dumps(candidate["statistics"]["exact_baseline"],sort_keys=True)
    preview=make_preview(rows,s,config(),candidate=candidate)
    assert json.dumps(candidate["statistics"]["exact_baseline"],sort_keys=True)==before
    evidence=preview["diagnostics"]
    assert evidence["checks"][1]["state"]=="review"
    assert evidence["threshold"]==candidate["threshold"]["deviation_score_q995"]
    items=[x for x in evidence["intervals"] if x["kind"]=="shadow_deviation"]
    assert items and all(x["feature"]=="hp2" for x in items)
    assert all(shadow_start<=datetime.fromisoformat(x["start"])<datetime.fromisoformat(x["end"])<=shadow_end for x in items)
    assert sum(x["minutes"] for x in items)==preview["summary"]["shadow_minutes"]
    assert any(p.get("flagged_minutes",0)>0 for p in preview["chart"])


def test_ineligible_sv_does_not_enter_candidate_or_raw_filter():
    s=selection();rows=windows(s);w=rows[0]
    excluded=replace(w,data_quality_status="STATE_NOT_ELIGIBLE",reason="BYPASS_OR_UNKNOWN_SV",features=None,sv_state="On")
    preview=make_preview([excluded,*rows[1:]],s,config())
    assert preview["summary"]["reference_minutes"]==216
    assert preview["daily"][0]["reasons"]["BYPASS_OR_UNKNOWN_SV"]==1


def test_minute_reference_marks_use_saved_quarantine_policy():
    from apps.api.app.calibration_diagnostics import annotate_points
    point={"phase":"reference","qualified":1,**{f:0.0 for f in FEATURES},"hp2":7.0}
    evidence={"quarantine_threshold":6.0,"initial_reference_baseline":{f:{"median":0.0,"scale":1.0} for f in FEATURES}}
    annotated=annotate_points([point],evidence,{})[0]
    assert annotated["reference_outlier"] and annotated["reference_contributor"]=="hp2"


def proposal_rows():
    settings=config();s=resolve_selection(ReferencePreviewRequest(idempotency_key="selection-test",machine_number="MX080",module=6,history_days=28),datetime(2026,10,1,12),settings)
    rows=windows(s)
    start,_,_,_=bounds(s)
    # Two narrow regimes that a whole-period IQR could disguise.
    changed=[replace(w,features={**w.features,"hp2":w.features["hp2"]+20}) if w.window_start<start+timedelta(days=14) else w for w in rows]
    return settings,s,changed


def test_proposal_ignores_every_shadow_value_and_flags():
    settings,s,rows=proposal_rows();_,_,shadow_start,_=bounds(s)
    original=propose(rows,s,settings)
    future=[replace(w,features={f:1e9 for f in FEATURES}) if w.window_start>=shadow_start else w for w in rows]
    assert propose(future,s,settings)==original
    assert original["shadow_used_for_selection"] is False
    assert original["changed"] and original["selected"]["days"]==14
    assert original["healthy_confirmed"] is False
    assert original["candidates_checked"]<=16
    assert original["selected"]["end"]<=s["shadow_start"]
    assert original["automatic_exclusions"]==[]


def test_proposal_missing_data_never_invents_reference():
    settings,s,rows=proposal_rows()
    proposal=propose([],s,settings)
    assert proposal["needs_review"] and not proposal["changed"] and not proposal["alternatives"]


def test_raw_scope_rejects_shadow_escape_timezone_and_large_period():
    s=selection();start,_,_,end=bounds(s)
    for a,b in [(start-timedelta(minutes=1),start+timedelta(minutes=1)),(start,start+timedelta(minutes=31)),(end-timedelta(minutes=1),end+timedelta(minutes=1)),(start.replace(second=1),start+timedelta(minutes=1))]:
        with pytest.raises(jobs.ReviewConflict):raw.validate_period(s,a,b)
    raw.validate_period(s,start,start+timedelta(minutes=30))


def test_raw_reads_all_states_numeric_zero_and_duplicate_seconds(monkeypatch):
    stamp=datetime(2026,9,21,12)
    rows=[dict(time=stamp,machine="MX080",global_state="Run",module_state="On",busy=0,sv="On",hp1=200.,lp1=20.,hp2=220.,lp2=30.,valve=4,temphi=10.,templo=20.),
          dict(time=stamp,machine="080",global_state="Run",module_state="Off",busy=1,sv="Off",hp1=201.,lp1=21.,hp2=221.,lp2=31.,valve=5,temphi=11.,templo=21.)]
    class Conn:
        def execute(self,query,params):
            assert "SELECT" in str(query) and "LIMIT 6001" in str(query)
            assert "SV" not in str(query).split("WHERE")[1]
            assert params["start"]==stamp
            return self
        def mappings(self):return rows
    @contextmanager
    def source():yield Conn()
    monkeypatch.setattr(raw,"source_connection",source)
    result=raw.read_raw(config(),"MX080",6,stamp,stamp+timedelta(minutes=1))
    assert result["observed_rows"]==2 and result["duplicate_rows"]==2
    assert result["sv_counts"]=={"On":1,"Off":1}
    assert result["chart"][0]["busy"]=="0"
    assert result["chart"][0]["dp2"]==190
    assert result["expected_seconds"]==60 and not result["source_written"]


def test_raw_coalesces_gets_and_checks_owner_before_cache(store,monkeypatch):
    job,_=ready(store);value=jobs.get_job(job,"reviewer-qa")
    s=value["preview"]["selection"];start=datetime.fromisoformat(s["reference_start"]);end=start+timedelta(minutes=5)
    monkeypatch.setattr(raw,"get_settings",config);raw.CACHE.clear();raw.INFLIGHT.clear()
    calls=[]
    def read(*args):calls.append(1);time.sleep(.1);return {"chart":[],"marker":"unchanged"}
    monkeypatch.setattr(raw,"read_raw",read)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _:raw.get_raw(job,"reviewer-qa",start,end),range(6)))
    assert len(calls)==1 and all(x==results[0] for x in results)
    results[0]["chart"].append("mutate client")
    assert raw.get_raw(job,"reviewer-qa",start,end)["chart"]==[]
    with pytest.raises(PermissionError):raw.get_raw(job,"another-reviewer",start,end)


def test_psi_confirmation_keeps_pressure_basis_explicit():
    settings=config().model_copy(update={"source_pressure_unit":"psi"});s=selection();rows=windows(s)
    start,_,shadow_start,end=bounds(s)
    candidate=registry_candidate_from_windows(rows,settings=settings,machine_number="MX080",module=6,calibration_start=start,shadow_start=shadow_start,shadow_end=end)
    assert "SOURCE_PRESSURE_UNIT_UNVERIFIED" not in candidate["reasons"]
    assert "SOURCE_PRESSURE_BASIS_UNVERIFIED" in candidate["reasons"]
    assert candidate["status"]!="READY_FOR_APPROVAL"


def test_raw_http_ownership_period_and_no_activation(store,monkeypatch):
    from apps.api.app.main import app
    job,_=ready(store);value=jobs.get_job(job,"reviewer-qa");stamp=value["preview"]["selection"]["reference_start"]
    monkeypatch.setattr(raw,"get_settings",config);monkeypatch.setattr(raw,"read_raw",lambda *a:{"chart":[],"source_written":False})
    with TestClient(app) as client:
        endpoint=f"/api/v1/calibration/reference/jobs/{job}/raw"
        params={"start":stamp,"end":(datetime.fromisoformat(stamp)+timedelta(minutes=5)).isoformat()}
        assert client.get(endpoint,params=params).status_code==401
        assert client.get(endpoint,params=params,headers={"X-Approver-Id":"wrong-owner"}).status_code==403
        result=client.get(endpoint,params=params,headers={"X-Approver-Id":"reviewer-qa"})
        assert result.status_code==200 and not result.json()["source_written"]
        assert client.get(endpoint,params={**params,"end":"2026-10-02T00:00:00"},headers={"X-Approver-Id":"reviewer-qa"}).status_code==409
    with store[0].connect() as conn:assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==0


def test_each_profile_persists_its_reviewed_reference_bounds():
    from apps.api.app.calibration import persist_batch
    s=selection();rows=windows(s);candidate=selected_candidate(rows,s,config())
    chosen={**s,"reference_end":"2026-09-27T00:00:00"}
    candidate["validation"]["reference_review"]=chosen
    inserted=[]
    class Result:lastrowid=123
    class Conn:
        def execute(self,query,params):
            if "INSERT INTO ht9046mx_calibration_profile" in str(query):inserted.append(params)
            return Result()
    start,_,shadow_start,end=bounds(s)
    persist_batch(config(),start,shadow_start,shadow_start,end,[candidate],transaction=Conn())
    assert inserted[0]["calibration_end"]==datetime(2026,9,27)
    assert inserted[0]["source_start"]==datetime.fromisoformat(chosen["reference_start"])
    assert inserted[0]["shadow_start"]==shadow_start
