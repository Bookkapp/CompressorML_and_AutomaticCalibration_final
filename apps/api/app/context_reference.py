"""Durable all-module context preparation, sharing the existing job admission.

One source/day pass prepares all-state measurements AND the common event ledger.
Frozen candidate models are separate from legacy Active records.
"""
from __future__ import annotations

import json
from copy import deepcopy
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, LargeBinary, MetaData, String, Table, select, text
from sqlalchemy.dialects.mysql import MEDIUMBLOB

from . import reference_jobs as jobs
from .context_request import ContextPreparationRequest
from .calibration import _latest_source_time
from .config import get_settings
from .db import connection, get_engine
from .context_storage import load_day, pack, unpack, source_namespace
from .context_profiles import VERSION, fit_context_candidate, assess_context
from .context_scope import validation_receipt
from .unified_events import events, make_event, append_events, fingerprint

MODE = "context-reference-v1"
metadata = MetaData()
profiles = Table("ht9046mx_context_profile", metadata,
    Column("profile_id", String(64), primary_key=True),
    Column("job_id", String(36), nullable=False),
    Column("machine_number", String(64), nullable=False),
    Column("module", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("version", String(64), nullable=False),
    Column("source_digest", String(64), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("payload", LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), nullable=False))


def controls_from_ids(engine, ids):
    result = []
    with engine.connect() as conn:
        for start in range(0,len(ids),500):
            rows = conn.execute(select(events).where(events.c.event_id.in_(ids[start:start+500]),
                                                     events.c.family=="CONTROL")).mappings()
            for row in rows:
                item = dict(row)
                item["payload"] = json.loads(item.pop("payload_json"))
                result.append(item)
    return sorted(result,key=lambda e:(e["occurred_at"],e["event_id"]))


def retain_module_navigation(engine,parent,replacement):
    """A one-module prospective check keeps the other frozen modules visible."""
    current=parent
    for _ in range(20):
        with engine.connect() as conn:
            job_id=conn.execute(select(profiles.c.job_id).where(profiles.c.profile_id==current["profile_id"])).scalar_one()
            siblings=[unpack(r) for r in conn.execute(select(profiles.c.payload).where(profiles.c.job_id==job_id)).scalars()]
        if len({s["module"] for s in siblings})==8:
            values={s["module"]:{**s["summary"],"profile_id":s["profile_id"]} for s in siblings}
            values[replacement["module"]]=replacement
            return [values[m] for m in sorted(values)]
        previous=current.get("parent_profile_id")
        if not previous:break
        current=get_profile(engine,previous)
    return [replacement]


def execute_preparation(job_id, row, owner, phase, progress):
    settings, engine = get_settings(), get_engine()
    request = ContextPreparationRequest.model_validate({k:v for k,v in json.loads(row["request_json"]).items() if k != "mode"})
    latest = _latest_source_time(settings,request.machine_number)
    if latest is None: raise jobs.ReviewConflict("NO_SOURCE_DATA")
    zone = ZoneInfo(settings.source_timezone)
    latest = latest.replace(tzinfo=zone) if latest.tzinfo is None else latest.astimezone(zone)
    end = latest.replace(hour=0,minute=0,second=0,microsecond=0)
    shadow_start = end-timedelta(days=3)
    start = shadow_start-timedelta(days=request.history_days)
    parent=get_profile(engine,request.parent_profile_id) if request.parent_profile_id else None
    if parent and (parent["machine_number"]!=request.machine_number or parent["source_namespace"]!=source_namespace(settings)):
        raise jobs.ReviewConflict("PARENT_SOURCE_CONTEXT_CHANGED")
    if parent and not request.validation_only:
        if parent["machine_number"]!=request.machine_number or parent["source_namespace"]!=source_namespace(settings):
            raise jobs.ReviewConflict("PARENT_SOURCE_CONTEXT_CHANGED")
        start=datetime.fromisoformat(parent["reference_start"]).replace(tzinfo=zone)
        shadow_start=datetime.fromisoformat(parent["shadow_start"]).replace(tzinfo=zone)
        end=datetime.fromisoformat(parent["shadow_end"]).replace(tzinfo=zone)
    if request.validation_only:
        from .context_followup import assert_source_clock
        assert_source_clock(latest,settings)
        latest=min(latest,datetime.now(zone))
        end=latest.replace(hour=0,minute=0,second=0,microsecond=0)
        shadow_start=end-timedelta(days=3)
        if not parent or not parent.get("reference_review") or parent["version"]!=VERSION:
            raise jobs.ReviewConflict("REVIEW_FROZEN_REFERENCE_BEFORE_FUTURE_VALIDATION")
        start=shadow_start
        if shadow_start <= datetime.fromisoformat(parent["reference_review"]["at"]).astimezone(zone):
            raise jobs.ReviewConflict("FUTURE_SOURCE_REQUIRED_AFTER_REFERENCE_REVIEW")
    if request.reference_start:
        start=datetime.combine(request.reference_start,datetime.min.time(),zone)
        shadow_start=datetime.combine(request.shadow_start,datetime.min.time(),zone)
        end=datetime.combine(request.shadow_end,datetime.min.time(),zone)
    if end>latest.replace(hour=0,minute=0,second=0,microsecond=0):
        raise jobs.ReviewConflict("SHADOW_REQUIRES_COMPLETE_SOURCE_DAYS")
    exclusions=[e.model_dump(mode="json") for e in request.exclusions]
    if parent and not request.validation_only:
        # Preserve the other seven modules' reasoned exclusions when changing
        # one module. The shared source pass does not imply shared fit choices.
        base=parent
        for _ in range(12):
            with engine.connect() as conn:
                job_key=conn.execute(select(profiles.c.job_id).where(profiles.c.profile_id==base["profile_id"])).scalar_one()
                batch=conn.execute(text(f"SELECT result_json FROM {jobs.TABLE} WHERE job_id=:job"),{"job":job_key}).scalar()
            if batch: break
            if not base.get("parent_profile_id"): break
            base=get_profile(engine,base["parent_profile_id"])
        if batch:
            for item in json.loads(batch).get("modules",[]):
                if item["module"]==parent["module"]: continue
                sibling=get_profile(engine,item["profile_id"])
                for excluded in sibling.get("exclusions",[]):
                    if start.replace(tzinfo=None).isoformat()<=excluded["start"]<excluded["end"]<=shadow_start.replace(tzinfo=None).isoformat():
                        exclusions.append(excluded)
    for e in request.exclusions:
        if not start.replace(tzinfo=None)<=e.start<e.end<=shadow_start.replace(tzinfo=None):
            raise jobs.ReviewConflict("EXCLUDE_REFERENCE_ONLY_NOT_SHADOW")
    windows, controls, receipts = [], [], []
    cursor = start
    while cursor < end:
        progress(cursor.date().isoformat())
        data, receipt = load_day(settings,engine,request.machine_number,cursor.date(),as_of=latest)
        if parent and cursor.date().isoformat() in parent["day_receipts"] and receipt["source_digest"]!=parent["day_receipts"][cursor.date().isoformat()]:
            raise jobs.ReviewConflict("SOURCE_CHANGED_REVIEW_NEW_PROFILE")
        windows.extend(data)
        controls.extend(controls_from_ids(engine,receipt["event_ids"]))
        receipts.append({k:v for k,v in receipt.items() if k != "event_ids"})
        cursor += timedelta(days=1)
    digest = fingerprint(receipts)
    summaries, frozen, ledger = [], [], []
    for module in ((parent["module"],) if request.validation_only else range(1,9)):
        progress(f"Preparing M{module} context profiles")
        subset = [w for w in windows if w.module==module]
        relevant = [e for e in controls if e["module"] in (None,module)]
        excluded=[e for e in exclusions if e["module"]==module]
        retained=[w for w in subset if not any(datetime.fromisoformat(e["start"])<=w.window_start<datetime.fromisoformat(e["end"]) for e in excluded)]
        model = deepcopy(parent) if request.validation_only else fit_context_candidate(retained,relevant,machine=request.machine_number,module=module,
                                     shadow_start=shadow_start.replace(tzinfo=None),shadow_end=end.replace(tzinfo=None))
        if request.validation_only:
            model.update(shadow_start=shadow_start.replace(tzinfo=None).isoformat(),shadow_end=end.replace(tzinfo=None).isoformat())
        assessment = assess_context(subset,relevant,model)
        shadow = [p for p in assessment if p["time"]>=shadow_start.replace(tzinfo=None).isoformat()]
        summary = {"module":module,"status":model["status"],"regimes":len(model["regimes"]),
                   "supported_regimes":sum(r["coverage_supported"] for r in model["regimes"]),
                   "templates":len(model["transition_templates"]),
                   "supported_templates":sum(t["coverage_supported"] for t in model["transition_templates"]),
                   "shadow_categories":dict(Counter(p["category"] for p in shadow)),
                   "shadow_minutes":len(shadow),"quality_counts":model["data_quality_counts"]}
        if request.validation_only:
            model["future_validation"]={"prospective":True,"start":model["shadow_start"],"end":model["shadow_end"],
                "frozen_reviewed_profile_id":request.parent_profile_id,**validation_receipt(shadow,model),"job_id":job_id}
            model["status"]="FUTURE_VALIDATED"
        profile_id = fingerprint([job_id,module,VERSION,digest,model])
        model.update(profile_id=profile_id,source_digest=digest,reference_start=parent["reference_start"] if request.validation_only else start.replace(tzinfo=None).isoformat(),
                     reference_end=parent.get("reference_end",parent["shadow_start"]) if request.validation_only else shadow_start.replace(tzinfo=None).isoformat(),
                     source_latest=latest.isoformat(),summary=summary,source_namespace=source_namespace(settings),
                     day_receipts={**(parent["day_receipts"] if request.validation_only else {}),**{r["day"]:r["source_digest"] for r in receipts}},
                     day_snapshot_keys={**(parent.get("day_snapshot_keys",{}) if request.validation_only else {}),**{r["day"]:r["snapshot_key"] for r in receipts if r.get("snapshot_key")}},
                     exclusions=parent.get("exclusions",[]) if request.validation_only else [e for e in exclusions if e["module"]==module],parent_profile_id=request.parent_profile_id,
                     contracts=parent.get("contracts") if request.validation_only else contract_versions(settings))
        summary["profile_id"] = profile_id
        summaries.append(summary)
        frozen.append((profile_id,model))
        def add(kind, at, details, extra, correlation=None, assessment="UNASSESSED"):
            ledger.append(make_event(source_key=[job_id,module,kind,extra],machine=request.machine_number,
                module=module,occurred_at=at,timezone_name=settings.source_timezone,event_type=kind,
                family="PROFILE" if kind.startswith("PROFILE") else "PHASE" if kind.startswith("PHASE") else "ANOMALY",
                details={"profile_id":profile_id,"model_version":VERSION,**details},mode="SHADOW",
                run_id=job_id,correlation_id=correlation,assessment=assessment))
        add("PROFILE_CANDIDATE_CREATED",datetime.now(zone).replace(tzinfo=None),summary,profile_id)
        previous = None
        for p in shadow:
            # Archive every derived category boundary; original control changes
            # and all raw measurements are separately retained/inspectable.
            if previous != p["category"]:
                kind = "ANOMALY_ASSESSMENT_CHANGED" if p["category"] in {"UNEXPECTED_TRANSITION","STEADY_DEVIATION"} else "PHASE_ASSESSMENT_CHANGED"
                add(kind,p["time"],{"before":previous,"after":p["category"],"features":p["features"],
                    "steady_score":p["steady_score"],"steady_threshold":p["steady_threshold"],
                    "transition_event_id":p["transition_event_id"],"reference_review_required":True},
                    [p["time"],p["category"]],p["transition_event_id"],"PROPOSED")
                previous = p["category"]
        add("PROFILE_SHADOW_COMPLETED",datetime.now(zone).replace(tzinfo=None),summary,[profile_id,"complete"])
    progress("Saving context candidates and unified events")
    if request.validation_only:summaries=retain_module_navigation(engine,parent,summaries[0])
    result = {"mode":MODE,"version":VERSION,"modules":summaries,"profiles":len(frozen),
              "source_digest":digest,"event_counts":dict(sum((Counter(r["event_counts"]) for r in receipts),Counter())),
              "selection":{"reference_start":parent["reference_start"] if request.validation_only else start.isoformat(),
                           "reference_end":parent.get("reference_end",parent["shadow_start"]) if request.validation_only else shadow_start.isoformat(),"shadow_start":shadow_start.isoformat(),
                           "shadow_end":end.isoformat(),"source_latest":latest.isoformat()},
              "auto_activation_allowed":False,"reference_review_required":True}
    with connection() as conn:
        current = jobs._row(conn,job_id,lock=True)
        if current["status"] != phase or current["lease_owner"] != owner or current["lease_until"] < jobs.utcnow():
            raise jobs.ReviewConflict("JOB_LEASE_LOST")
        for profile_id, model in frozen:
            conn.execute(profiles.insert().values(profile_id=profile_id,job_id=job_id,machine_number=request.machine_number,
                module=model["module"],status=model["status"],version=VERSION,source_digest=digest,
                created_at=jobs.utcnow().isoformat()+"Z",payload=pack(model)))
        append_events(conn,ledger)
        conn.execute(text(f"UPDATE {jobs.TABLE} SET status='COMPLETED',result_json=:result,selection_json=:selection,lease_until=NULL,updated_at=:stamp WHERE job_id=:job"),
                     {"job":job_id,"result":jobs.encode(result),"selection":jobs.encode(result["selection"]),"stamp":jobs.utcnow()})


def latest_preparation(machine,completed_only=False):
    with connection() as conn:
        predicate=" AND status='COMPLETED'" if completed_only else ""
        rows = conn.execute(text(f"SELECT job_id,actor_id,request_json FROM {jobs.TABLE} WHERE machine_number=:machine AND module=0{predicate} ORDER BY created_at DESC LIMIT 100"),
                            {"machine":machine}).mappings().all()
    match = next((r for r in rows if json.loads(r["request_json"]).get("mode")==MODE),None)
    return jobs.get_job(match["job_id"],match["actor_id"]) if match else None


def get_profile(engine, profile_id):
    with engine.connect() as conn:
        row = conn.execute(select(profiles).where(profiles.c.profile_id==profile_id)).mappings().first()
    if row is None: raise KeyError("Context profile not found")
    return unpack(row["payload"])


def contract_versions(settings):
    return {"pressure_basis":settings.source_pressure_unit,
            "state_contract":settings.profile_state_contract_version,
            "controller_codebook":settings.profile_controller_codebook_version,
            "service_epoch":settings.profile_service_epoch_version,"timezone":settings.source_timezone}
