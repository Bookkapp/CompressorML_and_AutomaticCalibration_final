"""Bounded post-review progress and durable interim inspections, never fitting.

Interim results do not write a Profile or an approval receipt. Source reads run
in the existing leased job queue; GETs use small indexed inventory/saved results.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from pydantic import Field
from sqlalchemy import text

from . import reference_jobs as jobs
from .automatic_reference import PreparationRequest
from .config import get_settings
from .context_profiles import VERSION as MODEL_VERSION, assess_context
from .context_reads import shared_read
from .context_reference import get_profile, controls_from_ids
from .context_scope import validation_receipt, scope_hash
from .context_storage import days, day_key, read_day, pack, source_namespace
from .db import get_engine, source_connection
from .inference import _qualified_source_table, get_machine_candidates
from .observed_context import build_observed_minutes
from .qualified_cache import fill_lock
from .qualified_calibration import IDENTIFIER, load_observed_one_minute_windows
from .unified_events import TransitionTracker, append_events, fingerprint, make_event

MODE = "context-followup-v1"


def result_provenance(result):
    """Read older immutable inspection receipts without losing daily provenance."""
    if any(r.get("source_kind")=="MOCK" or r.get("categories",{}).get("MOCK_DATA",0)
           for r in result.get("daily",[])):
        return {**result,"source_kind":"MOCK","approval_eligible":False}
    return result


class FollowupRequest(PreparationRequest):
    parent_profile_id: str = Field(min_length=64, max_length=64)


def local_time(value, settings):
    zone = ZoneInfo(settings.source_timezone)
    return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)


def assert_source_clock(latest, settings, *, now=None):
    if latest is not None and local_time(latest, settings) > local_time(now or datetime.now(timezone.utc), settings) + timedelta(seconds=60):
        raise jobs.ReviewConflict("FUTURE_SOURCE_TIMESTAMP_CHECK_CLOCK")


def reviewed_model(engine, profile_id, settings):
    model = get_profile(engine, profile_id)
    if not model.get("reference_review"):
        raise jobs.ReviewConflict("REVIEW_FROZEN_REFERENCE_BEFORE_FUTURE_VALIDATION")
    if model["version"] != MODEL_VERSION or model["source_namespace"] != source_namespace(settings):
        raise jobs.ReviewConflict("MODEL_OR_SOURCE_VERSION_CHANGED")
    return model


def source_head(settings, machine, *, now=None):
    """Index seeks per alias, including a separate trustworthy clock boundary."""
    current = local_time(now or datetime.now(timezone.utc), settings).replace(tzinfo=None)
    table = _qualified_source_table(settings.source_db_name, settings.source_table)
    mc, tc = settings.source_machine_column, settings.source_timestamp_column
    if not all(IDENTIFIER.fullmatch(c) for c in (mc, tc)):
        raise ValueError("Unsafe source mapping")
    latest, valid = [], []
    query = f"SELECT `{tc}` FROM {table} WHERE `{mc}`=:machine {{bound}} ORDER BY `{tc}` DESC LIMIT 1"
    with source_connection() as conn:
        for alias in dict.fromkeys(get_machine_candidates(machine)):
            at = conn.execute(text(query.format(bound="")), {"machine":alias}).scalar()
            if at is None:
                continue
            at = local_time(at, settings).replace(tzinfo=None)
            latest.append(at)
            if at <= current:
                valid.append(at)
            else:
                previous = conn.execute(text(query.format(bound=f"AND `{tc}`<=:now")), {"machine":alias,"now":current}).scalar()
                if previous is not None:
                    valid.append(local_time(previous, settings).replace(tzinfo=None))
    return {"latest":max(latest) if latest else None, "valid_latest":max(valid) if valid else None}


def calendar(model, head, settings, *, now=None):
    current = local_time(now or datetime.now(timezone.utc), settings)
    reviewed = local_time(datetime.fromisoformat(model["reference_review"]["at"]), settings)
    first = reviewed.date() + timedelta(days=1)
    latest = head["valid_latest"]
    source_day = local_time(latest, settings).date() if latest else first - timedelta(days=1)
    start = max(reviewed.date(), source_day - timedelta(days=3))
    # At most four dates: the latest three calendar days and the open source day.
    stop = max(first + timedelta(days=3), source_day + timedelta(days=1))
    stop = min(stop,start+timedelta(days=4))
    after_review=reviewed.replace(tzinfo=None,second=0,microsecond=0)+timedelta(minutes=1)
    inspection_start=max(datetime.combine(start,datetime.min.time()),after_review)
    end = datetime.combine(source_day, datetime.min.time())
    ready = latest is not None and end - timedelta(days=3) > reviewed.replace(tzinfo=None)
    clock_error = reviewed > current or (head["latest"] is not None and local_time(head["latest"], settings) > current + timedelta(seconds=60))
    return {"first_day":first.isoformat(),"window_start":start.isoformat(),"window_end":stop.isoformat(),
        "available_start":inspection_start.isoformat(),
        "validation_start":(end - timedelta(days=3)).date().isoformat() if ready else None,
        "validation_end":end.date().isoformat() if ready else None,
        "calendar_ready":ready and not clock_error,"clock_error":clock_error,
        "reviewed_at":reviewed.isoformat(),"source_latest":head["latest"].isoformat() if head["latest"] else None,
        "valid_latest":latest.isoformat() if latest else None,"checked_at":current.isoformat(),
        "source_age_seconds":max(0,(current-local_time(latest,settings)).total_seconds()) if latest else None}


def inventory(settings, machine, start, end, head, *, now=None, not_before=None):
    """Presence seeks only; raw-row counts/health are never guessed from dates."""
    table = _qualified_source_table(settings.source_db_name, settings.source_table)
    mc, tc = settings.source_machine_column, settings.source_timestamp_column
    if not all(IDENTIFIER.fullmatch(c) for c in (mc,tc)):
        raise ValueError("Unsafe source mapping")
    query = f"SELECT `{tc}` FROM {table} WHERE `{mc}`=:machine AND `{tc}`>=:start AND `{tc}`<:end AND `{tc}`<=:latest ORDER BY `{tc}` {{order}} LIMIT 1"
    latest = head["valid_latest"]
    current = local_time(now or datetime.now(timezone.utc),settings).replace(tzinfo=None)
    rows = []
    with source_connection() as conn:
        for offset in range((end-start).days):
            day = start + timedelta(days=offset)
            lo = datetime.combine(day,datetime.min.time()); hi=lo+timedelta(days=1)
            if not_before:lo=max(lo,datetime.fromisoformat(not_before))
            first_at = last_at = None
            if latest and lo <= latest and lo <= current:
                firsts=[];lasts=[]
                for alias in dict.fromkeys(get_machine_candidates(machine)):
                    params={"machine":alias,"start":lo,"end":hi,"latest":latest}
                    for order in ("ASC","DESC"):
                        at=conn.execute(text(query.format(order=order)),params).scalar()
                        if at is not None:(firsts if order=="ASC" else lasts).append(at)
                first_at=min(firsts) if firsts else None;last_at=max(lasts) if lasts else None
            closed=hi<=current and latest is not None and hi<=latest-timedelta(seconds=settings.qualified_1m_late_arrival_seconds)
            rows.append({"day":day.isoformat(),"has_data":first_at is not None,"closed":closed,
                "first_at":first_at.isoformat() if first_at else None,"last_at":last_at.isoformat() if last_at else None})
    return rows


def latest_job(engine, model, *, completed=False):
    predicate=" AND status='COMPLETED'" if completed else ""
    with engine.connect() as conn:
        row=conn.execute(text(f"SELECT job_id,actor_id,request_json FROM {jobs.TABLE} WHERE machine_number=:machine AND module=0{predicate} AND request_json LIKE :parent ORDER BY created_at DESC,job_id DESC LIMIT 30"),
            {"machine":model["machine_number"],"parent":"%"+model["profile_id"]+"%"}).mappings().all()
    match=next((r for r in row if json.loads(r["request_json"]).get("mode")==MODE and json.loads(r["request_json"]).get("parent_profile_id")==model["profile_id"]),None)
    return jobs.get_job(match["job_id"],match["actor_id"]) if match else None


def progress(engine, model, settings, *, now=None):
    now=now or datetime.now(timezone.utc)
    head=shared_read(("followup-head",source_namespace(settings),model["machine_number"]),lambda:source_head(settings,model["machine_number"],now=now),ttl=30)
    plan=calendar(model,head,settings,now=now)
    start,end=date.fromisoformat(plan["window_start"]),date.fromisoformat(plan["window_end"])
    observed=shared_read(("followup-inventory",source_namespace(settings),model["machine_number"],start,end,plan["valid_latest"],plan["available_start"]),
        lambda:inventory(settings,model["machine_number"],start,end,head,now=now,not_before=plan["available_start"]),ttl=30)
    job=latest_job(engine,model); saved=job if job and job["status"]=="COMPLETED" else latest_job(engine,model,completed=True)
    result=result_provenance((saved or {}).get("result") or {})
    if job and job.get("result"):job={**job,"result":result_provenance(job["result"])}
    summaries={r["day"]:r for r in result.get("daily",[])}
    daily=[{**r,"inspection":summaries.get(r["day"])} for r in observed]
    closed=sum(r["closed"] and r["has_data"] and r["day"]>=plan["first_day"] for r in daily)
    validated={r["day"] for r in result.get("daily",[]) if r["supported_minutes"]>=60 and r["closed"] and r["day"]>=plan["first_day"]}
    selected=[r for r in daily if plan["validation_start"] and plan["validation_start"]<=r["day"]<plan["validation_end"]]
    return {"profile_id":model["profile_id"],"machine_number":model["machine_number"],"module":model["module"],**plan,
        "daily":daily,"received_closed_days":closed,"inspected_supported_days":sum(r["day"] in validated for r in daily),
        "can_inspect":not plan["clock_error"] and any(r["has_data"] for r in daily),
        "can_validate":plan["calendar_ready"] and len(selected)==3 and all(r["closed"] and r["has_data"] for r in selected),
        "job":job,"saved_job_id":saved["job_id"] if saved else None,
        "inspection_start":result.get("start"),"inspection_end":result.get("end"),
        "inspection_stale":bool(result) and result.get("source_latest")!=plan["valid_latest"],
        "minimum_daily_minutes":60,"minimum_total_minutes":settings.profile_min_shadow_windows,
        "maximum_flag_pct":settings.profile_max_shadow_flag_pct,"approval_eligible":False,
        "reason":"FUTURE_SOURCE_TIMESTAMP_CHECK_CLOCK" if plan["clock_error"] else "NO_SOURCE_DATA" if not head["latest"] else "SOURCE_NOT_AFTER_REVIEW" if not any(r["has_data"] for r in daily) else "WAITING_FOR_COMPLETE_DAYS" if not plan["calendar_ready"] else "SOURCE_DAY_MISSING" if len(selected)!=3 or not all(r["closed"] and r["has_data"] for r in selected) else "READY_FOR_FULL_VALIDATION"}


def partial_day(settings, engine, machine, day, *, as_of, progress=None):
    """Immutable five-minute inspection snapshots shared by all eight modules."""
    from .context_storage import load_day
    current=local_time(as_of,settings)
    lo=datetime.combine(day,datetime.min.time(),ZoneInfo(settings.source_timezone));hi=lo+timedelta(days=1)
    if hi<=current-timedelta(seconds=settings.qualified_1m_late_arrival_seconds):
        return load_day(settings,engine,machine,day,as_of=current,progress=progress)
    # An open-day snapshot never replaces a complete-day cache pointer.
    cutoff=current.replace(minute=(current.minute//5)*5,second=0,microsecond=0)
    key=fingerprint([day_key(settings,machine,day),MODE,cutoff.isoformat()])
    with fill_lock("followup-"+key[:55],engine_override=engine):
        previous=read_day(engine,key)
        if previous:return previous[0],previous[1]
        tracker=TransitionTracker(source_namespace(settings),settings.source_timezone)
        event_ids=[];pending=[]
        def flush():
            if pending:
                with engine.begin() as conn:append_events(conn,pending)
                pending.clear()
        def consume(batch):
            records=[e for e in tracker.consume(batch) if e["occurred_at"]>=lo.replace(tzinfo=None).isoformat()]
            event_ids.extend(e["event_id"] for e in records)
            if len(event_ids)>100000:raise jobs.ReviewConflict("FOLLOWUP_CONTROL_EVENT_BUDGET_EXCEEDED")
            pending.extend(records)
            if len(pending)>=1000:flush()
        revision={}
        windows=load_observed_one_minute_windows(settings,machine_number=machine,start=lo-timedelta(seconds=1),end=cutoff,
            as_of=cutoff,modules=range(1,9),compact_json=True,window_builder=build_observed_minutes,
            on_raw_batch=consume,revision_out=revision,progress=progress) if cutoff>lo else []
        windows=[w for w in windows if w.window_start>=lo.replace(tzinfo=None)]
        flush()
        digest=fingerprint([cutoff.isoformat(),revision]);stamp=datetime.now(timezone.utc).isoformat()
        receipt={"day":day.isoformat(),"source_digest":digest,"snapshot_key":key,"completed":False,
            "inspected_until":max(lo,(cutoff-timedelta(seconds=settings.qualified_1m_late_arrival_seconds)).replace(second=0,microsecond=0)).isoformat(),
            "event_ids":event_ids,"source_kind":"OBSERVED_SOURCE","approval_eligible":False}
        with engine.begin() as conn:
            for module in range(9):
                payload=receipt if module==0 else {"windows":[asdict(w) for w in windows if w.module==module],"event_ids":[]}
                conn.execute(days.insert().values(day_key=key,module=module,machine_number=machine,source_day=day.isoformat(),
                    checked_at=stamp,source_revision=digest,payload=pack(payload)))
        return windows,receipt


def summarize_day(points, day, *, closed, inspected_until, not_before=None):
    rows=[p for p in points if p["time"][:10]==day.isoformat() and (not not_before or p["time"]>=not_before)]
    receipt=validation_receipt(rows,{"reference_review":{}})
    episodes=[];current=None;previous=None
    for p in rows:
        at=datetime.fromisoformat(p["time"])
        issue=p["category"] in {"UNEXPECTED_TRANSITION","STEADY_DEVIATION","NEW_STEADY_LEVEL","UNSUPPORTED_TRANSITION","INSUFFICIENT_REFERENCE","UNSUPPORTED_CONTROL_CONTEXT","DATA_UNAVAILABLE"}
        if issue and (current is None or previous is None or at-previous!=timedelta(minutes=1) or current["category"]!=p["category"]):
            current={"start":p["time"],"end":p["time"],"minutes":0,"category":p["category"],"evidence":p.get("main_evidence")};episodes.append(current)
        if issue:current["end"]=p["time"];current["minutes"]+=1
        else:current=None
        previous=at
    flagged=sum(p["category"] in {"UNEXPECTED_TRANSITION","STEADY_DEVIATION"} for p in rows)
    lower=max(datetime.combine(day,datetime.min.time()),datetime.fromisoformat(not_before)) if not_before else datetime.combine(day,datetime.min.time())
    upper=max(lower,datetime.fromisoformat(inspected_until).replace(tzinfo=None))
    expected=max(0,min(1440,int((upper-lower).total_seconds()/60)))
    return {"day":day.isoformat(),"closed":closed,"inspected_until":upper.isoformat(),**receipt,
        "flagged_minutes":flagged,"within_minutes":receipt["supported_minutes"]-flagged,
        "unsupported_control_minutes":sum(p["category"]=="UNSUPPORTED_CONTROL_CONTEXT" for p in rows),
        "missing_minutes":max(0,expected-len(rows)),"expected_minutes":expected,
        "episodes":episodes[:80],"episodes_total":len(episodes)}


def execute_preparation(job_id,row,owner,phase,progress):
    settings,engine=get_settings(),get_engine()
    request=FollowupRequest.model_validate({k:v for k,v in json.loads(row["request_json"]).items() if k!="mode"})
    model=reviewed_model(engine,request.parent_profile_id,settings)
    if request.machine_number!=model["machine_number"]:raise jobs.ReviewConflict("PARENT_SOURCE_CONTEXT_CHANGED")
    now=datetime.now(timezone.utc);head=source_head(settings,request.machine_number,now=now)
    assert_source_clock(head["latest"],settings,now=now)
    plan=calendar(model,head,settings,now=now)
    if plan["clock_error"]:raise jobs.ReviewConflict("FUTURE_SOURCE_TIMESTAMP_CHECK_CLOCK")
    start=date.fromisoformat(plan["window_start"]);latest=head["valid_latest"]
    if latest is None or latest.isoformat()<plan["available_start"]:raise jobs.ReviewConflict("NO_OBSERVATIONS_AFTER_FROZEN_REVIEW")
    end=min(date.fromisoformat(plan["window_end"]),latest.date()+timedelta(days=1))
    snapshots={};all_windows=[];all_ids=[];receipts={}
    # One previous day carries delayed event context across the first midnight.
    for offset in range(-1,(end-start).days):
        day=start+timedelta(days=offset);progress(day.isoformat())
        windows,receipt=partial_day(settings,engine,request.machine_number,day,as_of=local_time(latest,settings),progress=progress)
        snapshots[day.isoformat()]=receipt["snapshot_key"];receipts[day.isoformat()]=receipt
        all_windows.extend(w for w in windows if w.module==model["module"] and (offset>=0 or w.window_start>=datetime.combine(start,datetime.min.time())-timedelta(minutes=125)))
        all_ids.extend(receipt["event_ids"])
    points=assess_context(sorted(all_windows,key=lambda w:w.window_start),controls_from_ids(engine,all_ids),deepcopy(model))
    daily=[]
    for offset in range((end-start).days):
        day=start+timedelta(days=offset);receipt=receipts[day.isoformat()]
        until=receipt.get("inspected_until",datetime.combine(day+timedelta(days=1),datetime.min.time()).isoformat())
        daily.append(summarize_day(points,day,closed=receipt["completed"],inspected_until=until,not_before=plan["available_start"]))
    high=max(r["inspected_until"][:19] for r in daily)
    result=result_provenance({"mode":MODE,"profile_id":model["profile_id"],"module":model["module"],"daily":daily,
        "start":plan["available_start"],"end":high,"source_latest":latest.isoformat(),"source_kind":"OBSERVED_SOURCE",
        "approval_eligible":False,"prospective":False,"evaluation_scope_fingerprint":scope_hash(model),
        "snapshot_keys":snapshots,"source_digests":{d:r["source_digest"] for d,r in receipts.items()},"completed_at":now.isoformat()})
    progress("Saving frozen Reference inspection")
    with jobs.connection() as conn:
        current=jobs._row(conn,job_id,lock=True)
        if current["status"]!=phase or current["lease_owner"]!=owner or current["lease_until"]<jobs.utcnow():raise jobs.ReviewConflict("JOB_LEASE_LOST")
        append_events(conn,[make_event(source_key=[job_id,"followup"],machine=model["machine_number"],module=model["module"],occurred_at=now,
            timezone_name=settings.source_timezone,family="PROFILE",event_type="PROFILE_FOLLOWUP_INSPECTED",mode="SHADOW",assessment="UNASSESSED",
            details={"profile_id":model["profile_id"],"job_id":job_id,"start":result["start"],"end":high,"approval_eligible":False})])
        conn.execute(text(f"UPDATE {jobs.TABLE} SET status='COMPLETED',result_json=:result,lease_until=NULL,updated_at=:stamp WHERE job_id=:job"),
            {"job":job_id,"result":jobs.encode(result),"stamp":jobs.utcnow()})


def result_for(engine,job_id,profile_id):
    with engine.connect() as conn:row=jobs._row(conn,job_id)
    request=json.loads(row["request_json"])
    if request.get("mode")!=MODE or request.get("parent_profile_id")!=profile_id:raise jobs.ReviewConflict("FOLLOWUP_PROFILE_CHANGED_REFRESH")
    if row["status"]!="COMPLETED":raise jobs.ReviewConflict("FOLLOWUP_INSPECTION_NOT_READY")
    return result_provenance(json.loads(row["result_json"]))


def inspection_day(engine,model,result,day,settings):
    if not any(r["day"]==day.isoformat() for r in result["daily"]):raise ValueError("Choose an inspected post-review day")
    windows=[];ids=[]
    for d in (day-timedelta(days=1),day):
        key=result["snapshot_keys"].get(d.isoformat())
        if not key:continue
        value=read_day(engine,key,modules=(model["module"],))
        if value is None or value[1]["source_digest"]!=result["source_digests"][d.isoformat()]:raise jobs.ReviewConflict("FOLLOWUP_SNAPSHOT_UNAVAILABLE")
        windows.extend(value[0]);ids.extend(value[1]["event_ids"])
    points=assess_context(sorted(windows,key=lambda w:w.window_start),controls_from_ids(engine,ids),model)
    return {"profile_id":model["profile_id"],"chart":[p for p in points if p["time"][:10]==day.isoformat() and p["time"]>=result["start"]],
        "source_timezone":settings.source_timezone,"pressure_unit":settings.source_pressure_unit or "psi","approval_eligible":False}
