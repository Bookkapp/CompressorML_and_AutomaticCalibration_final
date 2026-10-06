"""Synthetic flow checks; no real source insertion or machine approval."""
from copy import deepcopy
from datetime import date,datetime
from concurrent.futures import ThreadPoolExecutor
import pytest

from apps.api.app.context_mock import normal_mock
from apps.api.app.context_review import gate
from apps.api.tests.test_context_scope import review
from apps.api.tests.test_context_workflow import store


def test_mock_is_normal_deterministic_physical_and_never_refits(store):
    settings,_,model,_=review(store)
    before=deepcopy(model)
    first=normal_mock(model,settings,58)
    assert first==normal_mock(model,settings,58) and model==before
    assert first["normal_test_passed"] and first["receipt"]["supported_minutes"]==4320
    assert first["receipt"]["supported_days"]==3 and first["receipt"]["flag_pct"]==0
    assert first["source_kind"]=="MOCK" and not first["receipt"]["prospective"]
    assert not first["receipt"]["approval_eligible"] and first["steady_only"]
    assert len(first["chart"])==1440
    for p in first["chart"]:
        f=p["features"]
        assert f["dp1"]==f["hp1"]-f["lp1"] and f["dp2"]==f["hp2"]-f["lp2"]
        assert p["category"]=="WITHIN_PROPOSED_STEADY"


def test_virtual_dates_after_review_and_day_range_is_bounded(store):
    settings,_,model,_=review(store)
    model["reference_review"]["at"]="2026-10-06T18:30:00+00:00"
    data=normal_mock(model,settings)
    assert data["days"]==["2026-10-08","2026-10-09","2026-10-10"]
    second=normal_mock(model,settings,day=date(2026,10,9))
    assert second["mock_id"]==data["mock_id"] and second["selected_day"]=="2026-10-09"
    assert all(p["time"].startswith("2026-10-09") for p in second["chart"])
    with pytest.raises(ValueError,match="OUTSIDE_SIMULATED_PERIOD"):
        normal_mock(model,settings,day=date(2026,10,11))


def test_no_reference_is_invented_for_on_or_unreviewed_model(store):
    settings,base,model,_=review(store)
    with pytest.raises(ValueError,match="REVIEW_FROZEN_REFERENCE"):
        normal_mock(base,settings)
    model["reference_review"]["evaluation_scope"]["included_sv_states"]=["OFF","ON"]
    model["reference_review"]["evaluation_scope"]["excluded_sv_states"]=[]
    data=normal_mock(model,settings)
    assert data["missing_reference_states"]==["ON"] and data["sv"]=="OFF"
    assert "INCLUDED_STATE_REFERENCE_REQUIRED" in data["actual_readiness"]["blockers"]
    model["reference_review"]["accepted_regime_ids"]=[]
    with pytest.raises(ValueError,match="NO_ACCEPTED_REFERENCE"):
        normal_mock(model,settings)


def test_mock_receipt_cannot_promote_active_even_if_prospective_bit_changes(store):
    settings,_,model,_=review(store)
    data=normal_mock(model,settings)
    model["future_validation"]={**data["receipt"],"prospective":True}
    readiness=gate(model,settings)
    assert not readiness["ready"] and "MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE" in readiness["blockers"]


def test_parallel_mock_profiles_are_isolated(store):
    settings,_,model,_=review(store)
    before=deepcopy(model)
    with ThreadPoolExecutor(max_workers=4) as pool:
        result=list(pool.map(lambda seed:normal_mock(model,settings,seed),[58,58,24,24]))
    assert result[0]==result[1] and result[2]==result[3]
    assert result[0]["mock_id"]!=result[2]["mock_id"] and model==before
