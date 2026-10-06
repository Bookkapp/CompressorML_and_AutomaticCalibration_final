"""Context candidates and one common event history, with bounded inspection."""
from datetime import date, datetime, timedelta, timezone
import base64
import json

from fastapi import APIRouter, Header, HTTPException, Query,Response
from sqlalchemy import select

from .config import get_settings
from .db import get_engine
from . import reference_jobs as jobs
from .automatic_reference import create_preparation
from .context_request import ContextPreparationRequest
from .context_reference import MODE, latest_preparation, get_profile, controls_from_ids
from .context_storage import read_day, day_key, source_namespace
from .context_profiles import assess_context,VERSION
from .context_reads import shared_read,cached_raw,inspection_response
from . import context_review as review
from .unified_events import events, list_events, fingerprint
from .inference import clean_machine_code
from .reference_raw import read_raw, READERS, validate_period

router = APIRouter(prefix="/api/v1", tags=["Context profiles and event history"])


def actor(value):
    if not value or not 2<=len(value.strip())<=100:
        raise HTTPException(422,"กรอกชื่อหรือรหัสผู้ทบทวนอย่างน้อย 2 ตัวอักษร")
    return value.strip()


def engine():
    value=get_engine()
    if value is None: raise HTTPException(503,"Analytics database is not configured")
    return value


def call(fn):
    try: return fn()
    except jobs.ReviewConflict as exc: raise HTTPException(409,str(exc)) from exc
    except KeyError as exc: raise HTTPException(404,str(exc)) from exc
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc


def model_for(profile_id):
    model=call(lambda:shared_read(("model",profile_id),lambda:get_profile(engine(),profile_id),ttl=300))
    if model["source_namespace"]!=source_namespace(get_settings()):
        raise HTTPException(409,"Source mapping changed; prepare a new context candidate")
    return model


@router.post("/calibration/context/prepare",status_code=202)
def prepare(payload:ContextPreparationRequest,x_approver_id:str|None=Header(default=None)):
    if get_settings().app_mode=="demo": raise HTTPException(409,"Demo mode is read-only")
    who=actor(x_approver_id)
    if payload.validation_only:
        from .calibration import _latest_source_time
        from zoneinfo import ZoneInfo
        frozen=model_for(payload.parent_profile_id)
        if not frozen.get("reference_review"): raise HTTPException(409,"REVIEW_FROZEN_REFERENCE_BEFORE_FUTURE_VALIDATION")
        latest_at=call(lambda:_latest_source_time(get_settings(),payload.machine_number))
        if latest_at is None: raise HTTPException(409,"NO_SOURCE_DATA")
        from .context_followup import assert_source_clock
        call(lambda:assert_source_clock(latest_at,get_settings()))
        zone=ZoneInfo(get_settings().source_timezone)
        if latest_at.tzinfo is None: latest_at=latest_at.replace(tzinfo=zone)
        latest_at=min(latest_at,datetime.now(timezone.utc).astimezone(zone))
        future_start=latest_at.astimezone(zone).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=3)
        if future_start<=datetime.fromisoformat(frozen["reference_review"]["at"]).astimezone(zone):
            raise HTTPException(409,"FUTURE_SOURCE_REQUIRED_AFTER_REFERENCE_REVIEW")
    job=call(lambda:create_preparation(payload,who,mode=MODE))
    jobs.dispatch(job)
    return call(lambda:jobs.get_job(job,who))


@router.get("/calibration/context/latest")
def latest(machine_number:str,completed_only:bool=False,x_approver_id:str|None=Header(default=None)):
    actor(x_approver_id)
    job=call(lambda:latest_preparation(clean_machine_code(machine_number),completed_only))
    if job and job["status"]=="PREVIEW_QUEUED": jobs.dispatch(job["job_id"])
    return job


@router.get("/calibration/context/jobs/{job_id}")
def shared_job(job_id:str,x_approver_id:str|None=Header(default=None)):
    actor(x_approver_id)
    from .db import connection
    with connection() as conn:
        row=call(lambda:jobs._row(conn,job_id))
    if json.loads(row["request_json"]).get("mode")!=MODE: raise HTTPException(404,"Context preparation not found")
    return call(lambda:jobs.get_job(job_id,row["actor_id"]))


@router.get("/calibration/context/jobs/{job_id}/coverage")
def coverage(job_id:str,x_approver_id:str|None=Header(default=None)):
    who=actor(x_approver_id)
    from .context_coverage import job_coverage
    from .db import connection
    with connection() as conn: row=call(lambda:jobs._row(conn,job_id))
    if json.loads(row["request_json"]).get("mode")!=MODE: raise HTTPException(404,"Context preparation not found")
    job=call(lambda:jobs.get_job(job_id,row["actor_id"]))
    return call(lambda:job_coverage(engine(),job,who,get_settings()))


@router.get("/calibration/context/profiles/{profile_id}")
def profile(profile_id:str,accept_encoding:str=Header(default="")):
    return call(lambda:inspection_response(("context-model",profile_id,source_namespace(get_settings())),lambda:model_for(profile_id),accept_encoding=accept_encoding))


@router.get("/calibration/context/profiles/{profile_id}/day")
def profile_day(profile_id:str,day:date,accept_encoding:str=Header(default="")):
    return call(lambda:inspection_response(("context-day",profile_id,day,source_namespace(get_settings()),VERSION,
                                   get_settings().source_pressure_unit),lambda:_profile_day(profile_id,day),accept_encoding=accept_encoding))


@router.get("/calibration/context/profiles/{profile_id}/mock-validation")
def mock_validation(profile_id:str,seed:int=Query(default=58,ge=0,le=2**31-1),day:date|None=None,
                    x_approver_id:str|None=Header(default=None),accept_encoding:str=Header(default="")):
    actor(x_approver_id)
    from .context_mock import normal_mock,VERSION as MOCK_VERSION
    frozen=model_for(profile_id)
    settings=get_settings()
    return call(lambda:inspection_response(("context-mock",profile_id,seed,day,source_namespace(settings),MOCK_VERSION,
                          settings.profile_min_shadow_windows,settings.profile_max_shadow_flag_pct),
        lambda:normal_mock(frozen,settings,seed,day),accept_encoding=accept_encoding))


@router.get('/calibration/context/profiles/{profile_id}/fleet-transitions')
def fleet_transitions(profile_id:str,accept_encoding:str=Header(default='')):
    from .fleet_reference_api import stable_snapshot
    from .fleet_transitions import propose
    _,fleet=stable_snapshot();catalog=fleet.priors().get('transition_catalog')
    if not catalog:return {'bundle_id':fleet.bundle_id,'profile_id':profile_id,'templates':[],
        'rejected':[],'status':'CATALOG_NOT_PREPARED'}
    def payload():
        result=propose(model_for(profile_id),catalog,fleet.bundle_id)
        # Frozen curves are reconstructed server-side at review commit. HTTP
        # sends source receipts and counts, not hundreds of repeated matrices.
        for t in result['templates']:t.pop('curve',None)
        return result
    return call(lambda:inspection_response(('fleet-transition',profile_id,fleet.bundle_id),payload,accept_encoding=accept_encoding))


@router.get('/calibration/context/profiles/{profile_id}/validation-report')
def validation_report(profile_id:str,start:date,end:date,accept_encoding:str=Header(default='')):
    from .context_validation import report
    settings=get_settings()
    return call(lambda:inspection_response(('context-validation-report',profile_id,start,end,source_namespace(settings)),
        lambda:report(model_for(profile_id),start,end,lambda day:shared_read(
            ('context-assessment',profile_id,day,source_namespace(settings)),lambda:_profile_day(profile_id,day),ttl=300),
            source_timezone=settings.source_timezone),accept_encoding=accept_encoding))


@router.get('/calibration/context/profiles/{profile_id}/followup')
def followup_progress(profile_id:str,x_approver_id:str|None=Header(default=None)):
    from .context_followup import reviewed_model,progress
    actor(x_approver_id);settings=get_settings()
    model=call(lambda:reviewed_model(engine(),profile_id,settings))
    value=call(lambda:progress(engine(),model,settings))
    if value.get('job') and value['job']['status']=='PREVIEW_QUEUED':jobs.dispatch(value['job']['job_id'])
    return value


@router.post('/calibration/context/profiles/{profile_id}/followup',status_code=202)
def inspect_followup(profile_id:str,payload:dict,x_approver_id:str|None=Header(default=None)):
    from .context_followup import reviewed_model,FollowupRequest,MODE as FOLLOWUP_MODE
    if get_settings().app_mode=='demo':raise HTTPException(409,'Demo mode is read-only')
    who=actor(x_approver_id);model=call(lambda:reviewed_model(engine(),profile_id,get_settings()))
    # All source/Reference identity comes from the saved immutable Profile.
    request=call(lambda:FollowupRequest.model_validate({**payload,'parent_profile_id':profile_id,'machine_number':model['machine_number']}))
    job=call(lambda:create_preparation(request,who,mode=FOLLOWUP_MODE))
    jobs.dispatch(job)
    return call(lambda:jobs.get_job(job,who))


@router.get('/calibration/context/profiles/{profile_id}/followup/{job_id}/day')
def followup_day(profile_id:str,job_id:str,day:date,accept_encoding:str=Header(default='')):
    from .context_followup import reviewed_model,result_for,inspection_day
    settings=get_settings();model=call(lambda:reviewed_model(engine(),profile_id,settings))
    result=call(lambda:result_for(engine(),job_id,profile_id))
    return call(lambda:inspection_response(('followup-day',profile_id,job_id,day,source_namespace(settings)),
        lambda:inspection_day(engine(),model,result,day,settings),accept_encoding=accept_encoding))


@router.get('/calibration/context/profiles/{profile_id}/followup/{job_id}/raw')
def followup_raw(profile_id:str,job_id:str,start:datetime,end:datetime,accept_encoding:str=Header(default='')):
    from .context_followup import reviewed_model,result_for
    settings=get_settings();model=call(lambda:reviewed_model(engine(),profile_id,settings))
    result=call(lambda:result_for(engine(),job_id,profile_id))
    call(lambda:validate_period({'reference_start':result['start'],'shadow_end':result['end']},start,end))
    return call(lambda:inspection_response(('followup-raw',profile_id,job_id,start,end,source_namespace(settings)),
        lambda:cached_raw(settings,model['machine_number'],model['module'],start,end),accept_encoding=accept_encoding,ttl=60))


def _profile_day(profile_id,day):
    model=model_for(profile_id)
    if day.isoformat() not in model["day_receipts"]:
        raise HTTPException(422,"Choose a day within the saved Reference/Shadow period")
    settings=get_settings()
    data, ids=[],[]
    for selected in (day-timedelta(days=1),day):
        if selected.isoformat() not in model["day_receipts"]: continue
        key=model.get("day_snapshot_keys",{}).get(selected.isoformat(),day_key(settings,model["machine_number"],selected))
        value=read_day(engine(),key,modules=(model["module"],))
        if value is None: raise HTTPException(409,"Measurements unavailable; prepare again")
        if value[1]["source_digest"] != model["day_receipts"][selected.isoformat()]:
            raise HTTPException(409,"Source snapshot changed; inspect the previous profile evidence and prepare a new candidate")
        data.extend(value[0])
        ids.extend(value[1]["event_ids"])
    controls=controls_from_ids(engine(),ids)
    if model["version"]==VERSION:
        scored=call(lambda:assess_context(sorted(data,key=lambda w:w.window_start),controls,model))
    else:
        # Old frozen evidence remains inspectable without silently rescoring it
        # under a new algorithm or displaying another version's envelope.
        scored=[{"time":w.window_start.isoformat(),"module":w.module,"features":w.features,
            "control":w.control,"state_counts":w.state_counts,"quality":w.measurement_quality,
            "quality_reason":w.reason,"coverage":w.coverage,"category":"ARCHIVED_MODEL_VERSION",
            "steady_score":None,"steady_threshold":None,"transition_score":None,"transition_elapsed_minutes":None,
            "transition_event_id":None,"transition_envelope":None,"steady_envelope":None,"stable":False} for w in data]
    return {"day":day.isoformat(),"profile_id":profile_id,"source_timezone":settings.source_timezone,
            "pressure_unit":settings.source_pressure_unit,"chart":[p for p in scored if p["time"].startswith(day.isoformat())],
            "reference_review_required":not bool(model.get("reference_review")),"grain":"observed minute; no interpolation",
            "regimes":model["regimes"],"transition_templates":model["transition_templates"],"exclusions":model.get("exclusions",[])}


@router.get("/calibration/context/profiles/{profile_id}/raw")
def profile_raw(profile_id:str,start:datetime,end:datetime,accept_encoding:str=Header(default="")):
    model=model_for(profile_id)
    call(lambda:validate_period(model,start,end))
    return call(lambda:inspection_response(("context-raw",profile_id,start,end,source_namespace(get_settings()),get_settings().source_pressure_unit),lambda:cached_raw(get_settings(),model["machine_number"],model["module"],start,end),accept_encoding=accept_encoding,ttl=60))


@router.get("/calibration/context/profiles/{profile_id}/review")
def review_state(profile_id:str,x_approver_id:str|None=Header(default=None)):
    model_for(profile_id)
    value=call(lambda:review.state(engine(),profile_id,actor(x_approver_id)))
    selected=model_for(value["reviewed_profile_id"] or profile_id)
    return {**value,"readiness":review.gate(selected,get_settings())}


@router.post("/calibration/context/profiles/{profile_id}/review")
def save_review(profile_id:str,payload:review.ReviewRequest,x_approver_id:str|None=Header(default=None)):
    if get_settings().app_mode=="demo": raise HTTPException(409,"Demo mode is read-only")
    model_for(profile_id)
    return call(lambda:review.record_review(engine(),profile_id,actor(x_approver_id),payload,get_settings()))


@router.get("/calibration/context/profiles/{profile_id}/readiness")
def readiness(profile_id:str):
    return review.gate(model_for(profile_id),get_settings())


@router.post("/calibration/context/profiles/{profile_id}/approve")
def approve(profile_id:str,payload:review.DecisionRequest,x_approver_id:str|None=Header(default=None)):
    if get_settings().app_mode=="demo": raise HTTPException(409,"Demo mode is read-only")
    model_for(profile_id)
    return call(lambda:review.approve(engine(),profile_id,actor(x_approver_id),payload,get_settings()))


@router.get("/calibration/context/active")
def active_profiles(machine_number:str):
    with engine().connect() as conn:
        rows=[dict(r) for r in conn.execute(select(review.active).where(review.active.c.machine_number==clean_machine_code(machine_number))).mappings()]
    return rows


@router.post("/calibration/context/active/{machine_number}/{module}/rollback")
def rollback(machine_number:str,module:int,payload:review.DecisionRequest,x_approver_id:str|None=Header(default=None)):
    if get_settings().app_mode=="demo": raise HTTPException(409,"Demo mode is read-only")
    if module not in range(1,9): raise HTTPException(422,"Module must be 1..8")
    return call(lambda:review.rollback(engine(),clean_machine_code(machine_number),module,actor(x_approver_id),payload,get_settings()))


@router.get("/events")
def history(machine_number:str|None=None,module:int|None=Query(default=None,ge=1,le=8),
            start:datetime|None=None,end:datetime|None=None,family:str|None=None,mode:str|None=None,
            assessment:str|None=Query(default=None,max_length=32),event_type:str|None=Query(default=None,max_length=64),
            correlation_id:str|None=None,cursor:str|None=Query(default=None,max_length=300),limit:int=Query(default=100,ge=1,le=500)):
    if any(d and d.tzinfo for d in (start,end)): raise HTTPException(422,"Use source-local times")
    if start and end and end<=start: raise HTTPException(422,"End must follow start")
    after=None
    if cursor:
        try:
            after=json.loads(base64.urlsafe_b64decode(cursor).decode())
            if not isinstance(after,list) or len(after)!=2 or not all(isinstance(v,str) for v in after): raise ValueError()
            datetime.fromisoformat(after[0])
            if len(after[1])!=64: raise ValueError()
        except Exception as exc: raise HTTPException(422,"Invalid history cursor") from exc
    with engine().connect() as conn:
        result=list_events(conn,machine=clean_machine_code(machine_number) if machine_number else None,
            module=module,start=start.isoformat() if start else None,end=end.isoformat() if end else None,
            family=family,mode=mode,correlation=correlation_id,assessment=assessment,event_type=event_type,after=after,limit=limit)
    next_pair=result.pop("next")
    result["next_cursor"]=base64.urlsafe_b64encode(json.dumps(next_pair).encode()).decode() if next_pair else None
    return Response(json.dumps(result,ensure_ascii=False,separators=(",",":")),media_type="application/json")


@router.get("/events/{event_id}")
def event_detail(event_id:str):
    with engine().connect() as conn:
        row=conn.execute(select(events).where(events.c.event_id==event_id)).mappings().first()
        if row is None: raise HTTPException(404,"Event not found")
        value=dict(row)
        value["payload"]=json.loads(value.pop("payload_json"))
        related=list_events(conn,correlation=value["correlation_id"],limit=100) if value["correlation_id"] else {"items":[]}
    return {"event":value,"related":related["items"],"related_next":related.get("next")}


@router.get("/events/{event_id}/raw")
def event_raw(event_id:str,module:int=Query(ge=1,le=8),start:datetime=Query(),end:datetime=Query()):
    with engine().connect() as conn:
        row=conn.execute(select(events).where(events.c.event_id==event_id)).mappings().first()
    if row is None: raise HTTPException(404,"Event not found")
    if row["module"] not in (None,module): raise HTTPException(422,"Choose the event's Module")
    verify_event_source(row)
    at=datetime.fromisoformat(row["occurred_at"]).replace(second=0,microsecond=0)
    call(lambda:validate_period({"reference_start":(at-timedelta(hours=2)).isoformat(),
                               "shadow_end":(at+timedelta(hours=2)).isoformat()},start,end))
    return call(lambda:cached_raw(get_settings(),row["machine_number"],module,start,end))


def verify_event_source(row):
    """Do not substitute a newly configured source for retained event evidence.

    Earlier control records retain the namespace in their deterministic source
    identity. Verify it without rewriting the append-only event ledger.
    Operational producers must establish their telemetry mapping explicitly.
    """
    settings=get_settings()
    namespace=source_namespace(settings)
    details=json.loads(row["payload_json"])["details"]
    if row['event_type'].startswith('FLEET_'):
        # Derived Fleet evidence cannot substitute canonical ZIP telemetry for
        # the configured SQL source. Only a producer with verified mapping may
        # link this event into the existing bounded Raw endpoint.
        valid=(details.get('source_namespace')==namespace and details.get('source_mapping_status')=='VERIFIED_SQL_SOURCE')
    elif details.get("profile_id"):
        model=model_for(details["profile_id"])
        valid=model["machine_number"]==row["machine_number"] and model["module"]==row["module"]
    elif row["family"] in {"CONTROL","DATA_QUALITY"} and row["event_type"]!="SOURCE_REVISION_CHANGED":
        extra=[details.get("before_at"),details.get("before"),details.get("after")] if row["family"]=="CONTROL" else None
        valid=fingerprint([namespace,row["machine_number"],row["module"],
            datetime.fromisoformat(row["occurred_at"]),row["event_type"],extra])==row["source_event_key"]
    else:
        valid=details.get("source_namespace")==namespace
    if not valid or row["source_timezone"]!=settings.source_timezone:
        raise HTTPException(409,"EVENT_RAW_SOURCE_MAPPING_UNVERIFIED")
