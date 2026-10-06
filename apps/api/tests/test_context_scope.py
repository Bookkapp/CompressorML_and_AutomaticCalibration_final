"""Synthetic isolated SQL fixtures; never real machine approval evidence."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from apps.api.app import context_profiles as scorer
from apps.api.app.context_scope import make_scope,scope_hash,validation_receipt,coverage_rows
from apps.api.app.context_review import ReviewRequest,record_review,gate,approve,DecisionRequest
from apps.api.app.context_reference import get_profile,profiles
from apps.api.app.context_storage import pack
from apps.api.app.reference_jobs import ReviewConflict
from apps.api.app.config import Settings
from apps.api.tests.test_context_workflow import store,fixture_model
from apps.api.tests.test_context_profiles import minute


def settings():
    return Settings(_env_file=None,source_timezone="Asia/Bangkok",source_pressure_unit="psig",
        profile_state_contract_version="ISOLATED_TEST_STATE",profile_controller_codebook_version="ISOLATED_TEST_CODE",
        profile_service_epoch_version="ISOLATED_TEST_EPOCH",profile_min_shadow_windows=60)


def review(store):
    config=settings();base=fixture_model(store,config)
    request=ReviewRequest(expected_revision=0,source_digest=base["source_digest"],
        accepted_regime_ids=[r["regime_id"] for r in base["regimes"]],included_sv_states=["OFF"],
        excluded_sv_reason="ISOLATED TEST: no accepted ON reference",note="Synthetic review only, never healthy certification",
        engineer_evidence_ref="ISOLATED TEST ONLY")
    saved=record_review(store,base["profile_id"],"SCOPE-QA",request,config)
    return config,base,get_profile(store,saved["reviewed_profile_id"]),request


def test_excluded_on_never_calls_physical_model_and_raw_is_retained(store,monkeypatch):
    _,base,model,_=review(store);at=datetime(2026,10,10)
    rows=[replace(minute(at+timedelta(minutes=i),2000),context_key="run|on|0|on") for i in range(20)]
    def forbidden(w): raise AssertionError("Excluded ON must not use model features")
    monkeypatch.setattr(scorer,"vector",forbidden)
    points=scorer.assess_context(rows,[],model)
    assert all(p["category"]=="STATE_GATE_EXCLUDED" and not p["model_evaluated"] for p in points)
    assert all(p["steady_score"] is None and p["transition_score"] is None and p["main_evidence"] is None for p in points)
    assert points[-1]["features"]["hp2"]==2000 and points[-1]["control"]["valve_mean"]==100
    assert "evaluation_scope" not in base.get("reference_review",{})


def test_return_to_off_scores_immediately_and_does_not_hide_abnormal_level(store):
    _,_,model,_=review(store);at=datetime(2026,10,10)
    before=[replace(minute(at+timedelta(minutes=i),2000),context_key="run|on|0|on") for i in range(5)]
    event={"machine_number":"MX017","module":1,"occurred_at":(at+timedelta(minutes=5)).isoformat(),
        "event_id":"e"*64,"event_type":"SV_CHANGED","payload":{"details":{"before":"on","after":"off","witness_usable":True}}}
    healthy=[minute(at+timedelta(minutes=5+i),200) for i in range(12)]
    normal=scorer.assess_context(before+healthy,[event],model)
    assert all(p["category"]=="WITHIN_PROPOSED_STEADY" and p["model_evaluated"] for p in normal[5:])
    high=[minute(at+timedelta(minutes=5+i),600) for i in range(12)]
    abnormal=scorer.assess_context(before+high,[event],model)
    assert abnormal[5]["steady_score"]>abnormal[5]["steady_threshold"]
    assert all(p["category"] in {"STEADY_DEVIATION","NEW_STEADY_LEVEL"} for p in abnormal[5:])
    assert abnormal[-1]["stable"] and abnormal[-1]["category"]=="NEW_STEADY_LEVEL"


def test_validation_only_exempts_declared_states_and_still_needs_supported_future(store):
    config,_,model,_=review(store);at=datetime(2026,10,10)
    rows=[]
    for d in range(3):
        rows.extend(minute(at+timedelta(days=d,minutes=i)) for i in range(100))
        rows.extend(replace(minute(at+timedelta(days=d,minutes=100+i),2000),context_key="run|on|0|on") for i in range(10))
    points=scorer.assess_context(rows,[],model)
    receipt=validation_receipt(points,model)
    assert receipt["supported_minutes"]==300 and receipt["excluded_state_minutes"]==30
    assert receipt["supported_days"]==3 and receipt["unresolved_minutes"]==0 and receipt["flag_pct"]==0
    model["future_validation"]={"prospective":True,**receipt}
    assert gate(model,config)["ready"]
    changed=deepcopy(model);changed["future_validation"]["evaluation_scope_fingerprint"]="wrong"
    assert "VALIDATION_SCOPE_CHANGED" in gate(changed,config)["blockers"]
    bad=points+[dict(points[0],category="NEW_STEADY_LEVEL")]
    assert validation_receipt(bad,model)["unresolved_minutes"]==1
    model["future_validation"]={"prospective":True,**validation_receipt([p for p in points if p["category"]=="STATE_GATE_EXCLUDED"],model)}
    assert "VALIDATION_COVERAGE_INSUFFICIENT" in gate(model,config)["blockers"]


def test_scope_reason_uniqueness_and_no_reference_or_contract_bypass(store):
    config,_,model,request=review(store)
    for change in ({"included_sv_states":[]},{"included_sv_states":["OFF","OFF"]},{"excluded_sv_reason":"short"}):
        with pytest.raises(ValidationError): ReviewRequest.model_validate({**request.model_dump(),**change})
    assert "PROSPECTIVE_VALIDATION_REQUIRED" in gate(model,config)["blockers"]
    model["reference_review"]["evaluation_scope"]=make_scope(["OFF","ON"],"")
    assert "INCLUDED_STATE_REFERENCE_REQUIRED" in gate(model,config)["blockers"]
    config.profile_state_contract_version=""
    assert "STATE_CONTRACT_UNVERIFIED" in gate(model,config)["blockers"]


def test_quality_and_unknown_control_are_not_claimed_as_excluded_normal(store):
    _,_,model,_=review(store);at=datetime(2026,10,10)
    rows=[replace(minute(at),measurement_quality="DATA_QUALITY",features=None,context_key="run|on|0|on"),
          replace(minute(at+timedelta(minutes=1)),context_key=None)]
    p=scorer.assess_context(rows,[],model)
    assert [r["category"] for r in p]==["DATA_UNAVAILABLE","UNSUPPORTED_CONTROL_CONTEXT"]
    assert all(not r["model_evaluated"] for r in p)


def test_scope_change_invalidates_receipt_and_old_validation_cannot_be_reused(store):
    config,base,model,request=review(store)
    next_request=request.model_copy(update={"expected_revision":1,"excluded_sv_reason":"Updated isolated coverage decision"})
    second=record_review(store,base["profile_id"],"SCOPE-QA",next_request,config)
    next_model=get_profile(store,second["reviewed_profile_id"])
    assert next_model["profile_id"]!=model["profile_id"] and next_model["future_validation"] is None
    assert scope_hash(next_model)!=scope_hash(model)
    with pytest.raises(ReviewConflict,match="ANOTHER_TAB"):
        record_review(store,base["profile_id"],"SCOPE-QA",request.model_copy(update={"note":"Stale second tab request"}),config)


def test_legacy_scoring_is_unchanged_and_parallel_scope_reads_are_isolated(store):
    _,base,model,_=review(store);at=datetime(2026,10,10)
    rows=[minute(at+timedelta(minutes=i),600) for i in range(20)]
    before=deepcopy(model)
    with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(lambda _:scorer.assess_context(rows,[],model),range(16)))
    assert all(r==results[0] for r in results) and model==before
    assert scorer.assess_context(rows,[],base)[-1]["category"]=="NEW_STEADY_LEVEL"
    coverage=coverage_rows(model)
    assert coverage[1]["status"]=="STATE_GATE_EXCLUDED" and coverage[0]["accepted_regimes"]==2


def test_scoped_active_requires_matching_frozen_validation_and_ledger_is_unassessed(store,monkeypatch):
    from types import SimpleNamespace
    from apps.api.app import context_monitor
    from apps.api.app.context_review import active
    from apps.api.app.unified_events import events
    from apps.api.app.qualified_windows import WindowPolicy
    config,_,model,_=review(store)
    at=datetime(2026,10,10)
    reference_points=[dict(time=(at+timedelta(days=d,minutes=i)).isoformat(),category="WITHIN_PROPOSED_STEADY") for d in range(3) for i in range(100)]
    model["future_validation"]={"prospective":True,**validation_receipt(reference_points,model)}
    model["profile_id"]="f"*64
    with store.begin() as conn:
        conn.execute(profiles.insert().values(profile_id=model["profile_id"],job_id="SYNTHETIC-FUTURE-ONLY",machine_number="MX017",module=1,status="FUTURE_VALIDATED",version=model["version"],source_digest=model["source_digest"],created_at="2026-10-13",payload=pack(model)))
    pointer=approve(store,model["profile_id"],"ISOLATED-QA",DecisionRequest(expected_revision=0,source_digest=model["source_digest"],note="Synthetic isolated approval only"),config)
    assert pointer["profile_id"]==model["profile_id"]
    observed=[replace(minute(at+timedelta(minutes=i),900),context_key="run|on|0|on") for i in range(3)]
    monkeypatch.setattr(context_monitor,"build_observed_minutes",lambda *a,**k:observed)
    monkeypatch.setattr("apps.api.app.config.get_settings",lambda:config)
    stream=SimpleNamespace(policy=WindowPolicy(source_timezone="Asia/Bangkok"),modules=(1,),closed_before=at+timedelta(minutes=3))
    with store.begin() as conn:
        checkpoint=context_monitor.consume_observed(conn,[],None,stream,{},source_namespace="ISOLATED-QA",mode="SHADOW",run_id="fixture-scope-runtime")
    with store.connect() as conn:
        row=conn.execute(select(events).where(events.c.event_type=="CONTEXT_ASSESSMENT_CHANGED")).mappings().one()
        assert row["assessment"]=="NOT_EVALUATED" and row["family"]!="ANOMALY"
        assert "STATE_GATE_EXCLUDED" in row["payload_json"]
    assert checkpoint["categories"]["MX017/M1"][0]=="STATE_GATE_EXCLUDED"


def test_bulk_coverage_actor_isolation_and_no_raw_read(store):
    from apps.api.app.context_coverage import job_coverage
    config,base,model,_=review(store)
    job={"job_id":"isolated-job","machine_number":"MX017","result":{"modules":[{"module":1,"profile_id":base["profile_id"]}]}}
    mine=job_coverage(store,job,"SCOPE-QA",config)
    other=job_coverage(store,job,"OTHER-QA",config)
    assert mine["modules"][0]["profile_id"]==model["profile_id"]
    assert mine["modules"][0]["states"][1]["status"]=="STATE_GATE_EXCLUDED"
    assert other["modules"][0]["profile_id"]==base["profile_id"]
    assert other["modules"][0]["states"][1]["status"]=="INSUFFICIENT_REFERENCE"
