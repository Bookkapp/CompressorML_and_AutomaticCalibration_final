"""Immutable reviewed model versions; SQL compare-and-swap reviewer state.

Approval never accepts client-supplied contracts or validation metrics. A
prospective validation receipt must be computed from a frozen reviewed model.
"""
from copy import deepcopy
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from .context_scope import make_scope,scope_of,scope_hash,state_of
from sqlalchemy import Column,Integer,MetaData,String,Table,select,update
from .context_reference import profiles,get_profile,contract_versions
from .context_storage import pack,source_namespace
from .context_profiles import VERSION
from .unified_events import append_events,make_event,fingerprint
from .reference_jobs import ReviewConflict

metadata=MetaData()
review_state=Table("ht9046mx_context_review_state",metadata,
    Column("base_profile_id",String(64),primary_key=True),Column("actor_id",String(100),primary_key=True),
    Column("revision",Integer,nullable=False),Column("reviewed_profile_id",String(64),nullable=False))
active=Table("ht9046mx_context_active",metadata,
    Column("machine_number",String(64),primary_key=True),Column("module",Integer,primary_key=True),
    Column("profile_id",String(64),nullable=False),Column("previous_profile_id",String(64)),
    Column("revision",Integer,nullable=False))


class ReviewRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expected_revision:int=Field(ge=0)
    source_digest:str=Field(min_length=64,max_length=64)
    accepted_regime_ids:list[str]=Field(default_factory=list,max_length=12)
    accepted_template_ids:list[str]=Field(default_factory=list,max_length=100)
    accepted_fleet_template_ids:list[str]=Field(default_factory=list,max_length=100)
    fleet_bundle_id:str|None=Field(default=None,max_length=64)
    note:str=Field(min_length=8,max_length=2000)
    engineer_evidence_ref:str=Field(default="",max_length=1000)
    included_sv_states:list[Literal["OFF","ON"]]|None=Field(default=None,min_length=1,max_length=2)
    excluded_sv_reason:str=Field(default="",max_length=1000)

    @model_validator(mode="after")
    def scope_valid(self):
        if self.included_sv_states is not None: make_scope(self.included_sv_states,self.excluded_sv_reason)
        return self


class DecisionRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expected_revision:int=Field(ge=0)
    source_digest:str=Field(min_length=64,max_length=64)
    note:str=Field(min_length=8,max_length=2000)


def state(engine,base_id,who):
    with engine.connect() as conn:
        row=conn.execute(select(review_state).where(review_state.c.base_profile_id==base_id,
                                                    review_state.c.actor_id==who)).mappings().first()
    return dict(row) if row else {"base_profile_id":base_id,"actor_id":who,"revision":0,"reviewed_profile_id":None}


def gate(model,settings):
    reasons=[]
    current=contract_versions(settings)
    for key in ("state_contract","controller_codebook","service_epoch"):
        if not current[key].strip(): reasons.append(key.upper()+"_UNVERIFIED")
    if current["pressure_basis"] not in {"psig","psia"}: reasons.append("PRESSURE_BASIS_UNVERIFIED")
    if model.get("contracts")!=current: reasons.append("CONTRACT_CHANGED_PREPARE_AGAIN")
    if model.get("version")!=VERSION or model.get("source_namespace")!=source_namespace(settings):
        reasons.append("MODEL_OR_SOURCE_VERSION_CHANGED")
    review=model.get("reference_review")
    if not review or not review["accepted_regime_ids"]: reasons.append("REFERENCE_ACCEPTANCE_REQUIRED")
    if not review or not review["engineer_evidence_ref"].strip(): reasons.append("ENGINEER_EVIDENCE_REQUIRED")
    try:
        scope=scope_of(model)
        if scope:
            accepted={state_of(r["context"]) for r in model["regimes"] if r["coverage_supported"] and r["regime_id"] in review["accepted_regime_ids"]}
            if not set(scope["included_sv_states"])<=accepted: reasons.append("INCLUDED_STATE_REFERENCE_REQUIRED")
    except (ValueError,TypeError):
        scope=None; reasons.append("EVALUATION_SCOPE_INVALID")
    v=model.get("future_validation")
    if v and (v.get("source_kind")=="MOCK" or v.get("approval_eligible") is False):
        reasons.append("MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE")
    if not v or not v.get("prospective"): reasons.append("PROSPECTIVE_VALIDATION_REQUIRED")
    else:
        if scope and v.get("evaluation_scope_fingerprint")!=scope_hash(model): reasons.append("VALIDATION_SCOPE_CHANGED")
        if v["supported_days"]<3 or v["supported_minutes"]<settings.profile_min_shadow_windows:
            reasons.append("VALIDATION_COVERAGE_INSUFFICIENT")
        if v["unresolved_minutes"]>0: reasons.append("VALIDATION_UNSUPPORTED_PERIODS_REQUIRE_REVIEW")
        if v["flag_pct"]>settings.profile_max_shadow_flag_pct: reasons.append("VALIDATION_FLAG_RATE_EXCEEDED")
    return {"ready":not reasons,"blockers":reasons,"auto_activation_allowed":False}


def record_review(engine,base_id,who,payload,settings):
    base=get_profile(engine,base_id)
    if base["source_digest"]!=payload.source_digest: raise ReviewConflict("SOURCE_DIGEST_CHANGED")
    if base["version"]!=VERSION or base["source_namespace"]!=source_namespace(settings):
        raise ReviewConflict("MODEL_OR_SOURCE_VERSION_CHANGED")
    accepted_r=set(payload.accepted_regime_ids);accepted_t=set(payload.accepted_template_ids)
    if payload.accepted_fleet_template_ids:
        from .fleet_bundle import current_snapshot
        from .fleet_transitions import apply_selection
        _,fleet=current_snapshot(settings.fleet_stable_store or settings.project_root/'artifacts/fleet-stable')
        if fleet.bundle_id!=payload.fleet_bundle_id:raise ReviewConflict('FLEET_VERSION_CHANGED_REFRESH_BEFORE_REVIEW')
        base=apply_selection(base,fleet,payload.accepted_fleet_template_ids)
        accepted_t.update(payload.accepted_fleet_template_ids)
    scope=make_scope(payload.included_sv_states,payload.excluded_sv_reason) if payload.included_sv_states is not None else None
    allowed_r={r["regime_id"] for r in base["regimes"] if r["coverage_supported"]}
    allowed_t={t["template_id"] for t in base["transition_templates"] if t["coverage_supported"]}
    if not accepted_r<=allowed_r or not accepted_t<=allowed_t:
        raise ReviewConflict("INSUFFICIENT_SUPPORT_CANNOT_BE_ACCEPTED")
    if scope and any(r["regime_id"] in accepted_r and state_of(r["context"]) not in scope["included_sv_states"] for r in base["regimes"]):
        raise ReviewConflict("ACCEPTED_REGIME_OUTSIDE_EVALUATION_SCOPE")
    for t in base["transition_templates"]:
        if scope and t["template_id"] in accepted_t and state_of(t["key"].split("|")[-1]) not in scope["included_sv_states"]:
            raise ReviewConflict("ACCEPTED_TRANSITION_OUTSIDE_EVALUATION_SCOPE")
        if t["template_id"] in accepted_t and not any("FROM_"+rid+"|" in t["key"] for rid in accepted_r):
            raise ReviewConflict("TRANSITION_ORIGIN_REGIME_MUST_BE_ACCEPTED")
    request=payload.model_dump()
    if len(payload.note.strip())<8: raise ValueError("Explain the review")
    new_id=fingerprint([base_id,who,request])
    with engine.begin() as conn:
        # Existing immutable parent provides a lock even before reviewer state
        # exists, so two first saves cannot both claim revision zero.
        conn.execute(select(profiles.c.profile_id).where(profiles.c.profile_id==base_id).with_for_update()).scalar_one()
        saved=conn.execute(select(review_state).where(review_state.c.base_profile_id==base_id,
                                                     review_state.c.actor_id==who).with_for_update()).mappings().first()
        if saved and saved["reviewed_profile_id"]==new_id: return dict(saved)
        if (saved["revision"] if saved else 0)!=payload.expected_revision:
            raise ReviewConflict("REVIEW_CHANGED_IN_ANOTHER_TAB_RELOAD")
        version=payload.expected_revision+1
        stamp=datetime.now(timezone.utc)
        model=deepcopy(base)
        model.update(profile_id=new_id,parent_profile_id=base_id,status="REFERENCE_REVIEWED",
                     reference_review_required=False,
                     reference_review={"actor":who,"at":stamp.isoformat(),"revision":version,
                                       "accepted_regime_ids":sorted(accepted_r),"accepted_template_ids":sorted(accepted_t),
                                       "note":payload.note.strip(),"engineer_evidence_ref":payload.engineer_evidence_ref.strip()},
                     future_validation=None)
        if scope: model["reference_review"]["evaluation_scope"]=scope
        conn.execute(profiles.insert().values(profile_id=new_id,job_id=f"review-{new_id[:28]}",
            machine_number=model["machine_number"],module=model["module"],status=model["status"],version=model["version"],
            source_digest=model["source_digest"],created_at=stamp.isoformat(),payload=pack(model)))
        values={"revision":version,"reviewed_profile_id":new_id}
        if saved: conn.execute(review_state.update().where(review_state.c.base_profile_id==base_id,review_state.c.actor_id==who).values(**values))
        else: conn.execute(review_state.insert().values(base_profile_id=base_id,actor_id=who,**values))
        append_events(conn,[make_event(source_key=[base_id,who,version,"review"],machine=model["machine_number"],
            module=model["module"],occurred_at=stamp,timezone_name=settings.source_timezone,family="PROFILE",
            event_type="PROFILE_REFERENCE_REVIEWED",mode="SHADOW",assessment="REVIEWED",
            details={"base_profile_id":base_id,"profile_id":new_id,"actor":who,"revision":version,**request})])
    return {"base_profile_id":base_id,"actor_id":who,**values}


def approve(engine,profile_id,who,payload,settings):
    model=get_profile(engine,profile_id)
    if model["source_digest"]!=payload.source_digest: raise ReviewConflict("SOURCE_DIGEST_CHANGED")
    readiness=gate(model,settings)
    if not readiness["ready"]: raise ReviewConflict("; ".join(readiness["blockers"]))
    with engine.begin() as conn:
        saved=conn.execute(select(active).where(active.c.machine_number==model["machine_number"],
                                                 active.c.module==model["module"]).with_for_update()).mappings().first()
        if saved and saved["profile_id"]==profile_id: return dict(saved)
        if (saved["revision"] if saved else 0)!=payload.expected_revision: raise ReviewConflict("ACTIVE_CHANGED_RELOAD")
        values={"profile_id":profile_id,"previous_profile_id":saved["profile_id"] if saved else None,
                "revision":payload.expected_revision+1}
        if saved: conn.execute(update(active).where(active.c.machine_number==model["machine_number"],active.c.module==model["module"]).values(**values))
        else: conn.execute(active.insert().values(machine_number=model["machine_number"],module=model["module"],**values))
        append_events(conn,[make_event(source_key=[profile_id,"activate",values["revision"]],machine=model["machine_number"],
            module=model["module"],occurred_at=datetime.now(timezone.utc),timezone_name=settings.source_timezone,
            family="PROFILE",event_type="PROFILE_ACTIVATED",mode="LIVE",assessment="APPROVED",
            details={"actor":who,"note":payload.note,"before":values["previous_profile_id"],"after":profile_id,
                     "revision":values["revision"],"frozen_source_digest":model["source_digest"]})])
    return values


def rollback(engine,machine,module,who,payload,settings):
    with engine.begin() as conn:
        saved=conn.execute(select(active).where(active.c.machine_number==machine,active.c.module==module).with_for_update()).mappings().first()
        if not saved or not saved["previous_profile_id"]: raise ReviewConflict("NO_PREVIOUS_CONTEXT_PROFILE")
        if saved["revision"]!=payload.expected_revision: raise ReviewConflict("ACTIVE_CHANGED_RELOAD")
        target=get_profile(engine,saved["previous_profile_id"])
        if target["source_digest"]!=payload.source_digest: raise ReviewConflict("ROLLBACK_DIGEST_CHANGED")
        if not gate(target,settings)["ready"]: raise ReviewConflict("ROLLBACK_TARGET_CONTRACT_OR_VALIDATION_CHANGED")
        values={"profile_id":saved["previous_profile_id"],"previous_profile_id":saved["profile_id"],"revision":saved["revision"]+1}
        conn.execute(active.update().where(active.c.machine_number==machine,active.c.module==module).values(**values))
        append_events(conn,[make_event(source_key=[machine,module,"rollback",values["revision"]],machine=machine,module=module,
            occurred_at=datetime.now(timezone.utc),timezone_name=settings.source_timezone,family="PROFILE",
            event_type="PROFILE_ROLLED_BACK",mode="LIVE",assessment="APPROVED",
            details={"actor":who,"note":payload.note,"before":saved["profile_id"],"after":values["profile_id"],"revision":values["revision"]})])
    return values
