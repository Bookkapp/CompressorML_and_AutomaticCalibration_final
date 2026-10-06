from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
import pytest
from sqlalchemy import create_engine,select,func
from apps.api.app.config import Settings
from apps.api.app.context_profiles import fit_context_candidate,assess_context
from apps.api.app.context_reference import profiles,metadata as profile_meta,contract_versions,get_profile
from apps.api.app.context_storage import source_namespace,pack
from apps.api.app.context_review import metadata as review_meta,ReviewRequest,record_review,state,gate,DecisionRequest,approve,rollback
from apps.api.app.unified_events import metadata as event_meta,events
from apps.api.app.operational_inbox import metadata as inbox_meta,OperationalEvent,receive
from apps.api.app.reference_jobs import ReviewConflict
from apps.api.tests.test_context_profiles import minute,reference


def fixture_model(engine,settings):
    start=datetime(2026,9,8)
    model=fit_context_candidate(reference(),[],machine="MX017",module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    model.update(profile_id="a"*64,source_digest="b"*64,source_namespace=source_namespace(settings),contracts=contract_versions(settings),reference_start="2026-09-01T00:00:00",day_receipts={},exclusions=[])
    with engine.begin() as conn: conn.execute(profiles.insert().values(profile_id=model["profile_id"],job_id="fixture",machine_number="MX017",module=1,status=model["status"],version=model["version"],source_digest=model["source_digest"],created_at=datetime.now(timezone.utc).isoformat(),payload=pack(model)))
    return model


@pytest.fixture
def store():
    e=create_engine("sqlite://")
    for meta in (profile_meta,review_meta,event_meta,inbox_meta): meta.create_all(e)
    return e


def test_review_versions_retry_actor_isolation_and_stale_tabs(store):
    settings=Settings(_env_file=None,source_timezone="Asia/Bangkok")
    model=fixture_model(store,settings)
    r=ReviewRequest(expected_revision=0,source_digest=model["source_digest"],accepted_regime_ids=[model["regimes"][0]["regime_id"]],note="Fixture review only; no real Engineer certification")
    a=record_review(store,model["profile_id"],"QA-A",r,settings)
    assert record_review(store,model["profile_id"],"QA-A",r,settings)==a
    assert get_profile(store,model["profile_id"])==model
    child=get_profile(store,a["reviewed_profile_id"])
    assert child["reference_review"]["actor"]=="QA-A"
    assert "PROSPECTIVE_VALIDATION_REQUIRED" in gate(child,settings)["blockers"]
    with pytest.raises(ReviewConflict,match="ANOTHER_TAB"):
        record_review(store,model["profile_id"],"QA-A",r.model_copy(update={"note":"Changed review from stale tab"}),settings)
    assert state(store,model["profile_id"],"QA-B")["revision"]==0
    with store.connect() as conn:
        assert conn.execute(select(func.count()).select_from(events)).scalar()==1


def test_no_gate_bypass_from_note_and_actual_approved_fixture_rollback(store):
    settings=Settings(_env_file=None,source_timezone="Asia/Bangkok",source_pressure_unit="psig",profile_state_contract_version="TEST-STATE",profile_controller_codebook_version="TEST-CODE",profile_service_epoch_version="TEST-EPOCH")
    model=fixture_model(store,settings)
    request=ReviewRequest(expected_revision=0,source_digest=model["source_digest"],accepted_regime_ids=[r["regime_id"] for r in model["regimes"]],note="Synthetic SQL fixture; never a real machine activation",engineer_evidence_ref="ISOLATED_TEST_ONLY")
    reviewed=record_review(store,model["profile_id"],"QA",request,settings)
    child=get_profile(store,reviewed["reviewed_profile_id"])
    decision=DecisionRequest(expected_revision=0,source_digest=child["source_digest"],note="Attempt without future evidence")
    with pytest.raises(ReviewConflict,match="PROSPECTIVE_VALIDATION"):
        approve(store,child["profile_id"],"QA",decision,settings)
    # Internal future-validation receipt fixture, not client-supplied metrics.
    child["future_validation"]={"prospective":True,"supported_days":3,"supported_minutes":1000,"unresolved_minutes":0,"flag_pct":0.}
    child["parent_profile_id"]=reviewed["reviewed_profile_id"]
    for letter in ("c","d"):
        child["profile_id"]=letter*64
        with store.begin() as conn: conn.execute(profiles.insert().values(profile_id=child["profile_id"],job_id="future-fixture",machine_number="MX017",module=1,status="FUTURE_VALIDATED",version=child["version"],source_digest=child["source_digest"],created_at="2026-10-10",payload=pack(child)))
    assert approve(store,"c"*64,"QA",decision,settings)["revision"]==1
    assert approve(store,"c"*64,"QA",decision,settings)["revision"]==1
    assert approve(store,"d"*64,"QA",decision.model_copy(update={"expected_revision":1}),settings)["revision"]==2
    assert rollback(store,"MX017",1,"QA",decision.model_copy(update={"expected_revision":2}),settings)["profile_id"]=="c"*64
    with pytest.raises(ReviewConflict,match="ACTIVE_CHANGED"):
        rollback(store,"MX017",1,"QA",decision.model_copy(update={"expected_revision":2}),settings)


def test_transition_templates_use_reference_only_and_unknown_flat_is_not_normal():
    base=datetime(2026,9,1)
    windows=[];controls=[]
    for d in range(7):
        day=base+timedelta(days=d)
        for i in range(150):
            w=minute(day+timedelta(minutes=i),200+(i-89)*.8 if 90<=i<130 else 200)
            if 90<=i<130: w=replace(w,context_key="run|on|0|on")
            windows.append(w)
        controls.append({"machine_number":"MX017","module":1,"occurred_at":(day+timedelta(minutes=90,seconds=-1)).isoformat(),"event_id":str(d)*64,"event_type":"SV_CHANGED","payload":{"details":{"before":"off","after":"on","witness_usable":True}}})
    shadow=base+timedelta(days=7)
    model=fit_context_candidate(windows,controls,machine="MX017",module=1,shadow_start=shadow,shadow_end=shadow+timedelta(days=3))
    assert any(t["coverage_supported"] for t in model["transition_templates"])
    new=[minute(shadow+timedelta(minutes=i),200) for i in range(90)]
    new.extend(replace(minute(shadow+timedelta(minutes=90+i),300),context_key="run|on|0|on") for i in range(40))
    event={**controls[0],"occurred_at":(shadow+timedelta(minutes=90,seconds=-1)).isoformat(),"event_id":"f"*64}
    points=assess_context(new,[event],model)
    assert points[90]["category"]=="UNEXPECTED_TRANSITION"
    assert points[100]["category"]=="UNEXPECTED_TRANSITION"
    altered=fit_context_candidate(windows+new,controls+[event],machine="MX017",module=1,shadow_start=shadow,shadow_end=shadow+timedelta(days=3))
    assert altered["regimes"]==model["regimes"] and altered["transition_templates"]==model["transition_templates"]


def test_operational_receipt_rollback_retry_scoped_identity_and_correction(store):
    e=OperationalEvent(producer="PM-QA",external_event_id="ACK-1",machine_number="MX017",module=1,occurred_at=datetime(2026,9,1,12),source_timezone="Asia/Bangkok",source_database="isolated-test/pm",source_record_type="alert",source_record_id="7",event_type="ALERT_ACKNOWLEDGED",correlation_id="episode-qa",after={"acknowledged":True})
    def crash(): raise RuntimeError("before commit")
    with pytest.raises(RuntimeError): receive(store,e,before_commit=crash)
    with store.connect() as conn: assert conn.execute(select(func.count()).select_from(events)).scalar()==0
    first=receive(store,e)
    assert receive(store,e)["duplicate"]
    with pytest.raises(ReviewConflict,match="REUSED"):
        receive(store,e.model_copy(update={"after":{"acknowledged":False}}))
    corrected=e.model_copy(update={"external_event_id":"CORRECTION-1","event_type":"OPERATIONAL_EVENT_CORRECTED","supersedes_event_id":first["event_id"],"reason":"QA correction keeps original receipt"})
    receive(store,corrected)
    with store.connect() as conn: assert conn.execute(select(func.count()).select_from(events)).scalar()==2


def test_prospective_single_module_result_keeps_frozen_sibling_navigation(store):
    from apps.api.app.context_reference import retain_module_navigation
    def insert(model,job):
        with store.begin() as conn:conn.execute(profiles.insert().values(profile_id=model["profile_id"],job_id=job,
            machine_number="MX017",module=model["module"],status="QA",version="QA",source_digest="b"*64,created_at="2026-10-05",payload=pack(model)))
    for m in range(1,9):insert({"profile_id":str(m)*64,"module":m,"summary":{"module":m,"status":"unchanged"}},"all-eight")
    parent={"profile_id":"c"*64,"module":1,"parent_profile_id":"1"*64}
    insert(parent,"review-child")
    updated={"module":1,"profile_id":"d"*64,"status":"FUTURE_VALIDATED"}
    result=retain_module_navigation(store,parent,updated)
    assert len(result)==8 and result[0]==updated
    assert result[5]["profile_id"]=="6"*64 and result[5]["status"]=="unchanged"


def test_delayed_response_is_still_assessed_against_reference_transition():
    base=datetime(2026,9,1);windows=[];controls=[]
    for day in range(8):
        at=base+timedelta(days=day)
        for i in range(150):
            hp=200.+(i-99)*2 if 100<=i<110 else 200.
            windows.append(minute(at+timedelta(minutes=i),hp))
        controls.append({"event_id":str(day)*64,"machine_number":"MX017","module":1,"event_type":"VALVE_COMMAND_CHANGED",
            "occurred_at":(at+timedelta(minutes=90)).isoformat(),"payload":{"details":{"before":100.,"after":110.,"witness_usable":True}}})
    split=base+timedelta(days=7)
    model=fit_context_candidate(windows,controls,machine="MX017",module=1,shadow_start=split,shadow_end=split+timedelta(days=3))
    result=assess_context(windows,controls,model)
    earlier=next(p for p in result if p["time"]==(split+timedelta(minutes=95)).isoformat())
    delayed=next(p for p in result if p["time"]==(split+timedelta(minutes=105)).isoformat())
    assert earlier["category"]=="WITHIN_PROPOSED_STEADY"
    assert delayed["category"]=="WITHIN_PROPOSED_TRANSITION" and delayed["transition_elapsed_minutes"]==15
    assert delayed["transition_event_id"]==controls[-1]["event_id"]
