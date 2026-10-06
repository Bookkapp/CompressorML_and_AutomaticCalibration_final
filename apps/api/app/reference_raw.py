"""Bounded, read-only raw review of a saved job. Not approval evidence fitting."""
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
from threading import Lock, BoundedSemaphore, Event
from time import monotonic
from sqlalchemy import bindparam, text
from . import reference_jobs as jobs
from .config import get_settings
from .db import source_connection
from .inference import _qualified_source_table, get_machine_candidates
from .qualified_calibration import IDENTIFIER

CACHE = OrderedDict()
LOCK = Lock()
READERS = BoundedSemaphore(2)
INFLIGHT = {}


def validate_period(selection, start, end):
    if start.tzinfo or end.tzinfo or start.second or end.second or start.microsecond or end.microsecond:
        raise jobs.ReviewConflict("RAW_USE_LOCAL_MINUTE_BOUNDARIES")
    if not timedelta(0)<end-start<=timedelta(minutes=30):
        raise jobs.ReviewConflict("RAW_PERIOD_MAX_30_MINUTES")
    if not datetime.fromisoformat(selection["reference_start"])<=start<end<=datetime.fromisoformat(selection["shadow_end"]):
        raise jobs.ReviewConflict("DETAIL_DAY_OUTSIDE_REFERENCE")


def read_raw(settings, machine, module, start, end):
    templates={"hp1":settings.source_hp1_template,"lp1":settings.source_lp1_template,
        "hp2":settings.source_hp2_template,"lp2":settings.source_lp2_template,"valve":settings.source_valve_template,
        "temphi":settings.source_temp_high_template,"templo":settings.source_temp_low_template,
        "module_state":settings.source_module_status_template,"busy":settings.source_busy_template,"sv":settings.source_sv_template}
    columns={name:template.format(module=module) for name,template in templates.items()}
    columns.update(time=settings.source_timestamp_column,machine=settings.source_machine_column,global_state=settings.source_global_status_column)
    if any(not IDENTIFIER.fullmatch(c) for c in columns.values()): raise ValueError("Invalid source identifier")
    table=_qualified_source_table(settings.source_db_name,settings.source_table)
    query=text(f"SELECT {','.join(f'`{column}` AS `{name}`' for name,column in columns.items())} FROM {table} "
        f"WHERE `{columns['machine']}` IN :machines AND `{columns['time']}`>=:start AND `{columns['time']}`<:end "
        f"ORDER BY `{columns['time']}`,`{columns['machine']}` LIMIT 6001").bindparams(bindparam("machines",expanding=True))
    with source_connection() as conn:
        rows=[dict(row) for row in conn.execute(query,{"machines":get_machine_candidates(machine),"start":start,"end":end}).mappings()]
    if len(rows)>6000: raise jobs.ReviewConflict("RAW_TOO_MANY_ROWS_REDUCE_PERIOD")
    seconds=Counter(row["time"].replace(microsecond=0) for row in rows)
    def number(value):
        if isinstance(value,bool): return None
        try: result=float(value)
        except (TypeError,ValueError): return None
        return result if math.isfinite(result) else None
    points=[]
    for row in rows:
        point={key:number(row[key]) for key in ("hp1","lp1","hp2","lp2","valve","temphi","templo")}
        state=lambda name:"" if row[name] is None else str(row[name])
        point.update(time=row["time"].isoformat(),global_state=state("global_state"),
            module_state=state("module_state"),busy=state("busy"),sv=state("sv"),
            source_alias=str(row["machine"]),duplicate_second=seconds[row["time"].replace(microsecond=0)]>1)
        point["dp1"]=point["hp1"]-point["lp1"] if point["hp1"] is not None and point["lp1"] is not None else None
        point["dp2"]=point["hp2"]-point["lp2"] if point["hp2"] is not None and point["lp2"] is not None else None
        points.append(point)
    return {"machine_number":machine,"module":module,"start":start.isoformat(),"end":end.isoformat(),"chart":points,
        "grain":"observed second; no interpolation or state filtering","source_timezone":settings.source_timezone,
        "pressure_unit":settings.source_pressure_unit or "unverified","observed_rows":len(rows),"unique_seconds":len(seconds),
        "expected_seconds":int((end-start).total_seconds()),"duplicate_rows":sum(v for v in seconds.values() if v>1),
        "sv_counts":dict(Counter(p["sv"] for p in points)),"read_at":datetime.now(timezone.utc).isoformat(),
        "review_only":True,"cache_seconds":60,"source_written":False}


def get_raw(job_id, actor, start, end):
    # Authorization is checked before cache access on every request.
    with jobs.connection() as conn:
        row=conn.execute(text(f"SELECT actor_id,machine_number,module,status,selection_json FROM {jobs.TABLE} WHERE job_id=:job"),{"job":job_id}).mappings().first()
    if row is None: raise KeyError("Reference review job not found")
    job=dict(row)
    if job["actor_id"]!=actor: raise PermissionError("Reference review belongs to another reviewer")
    if job["module"]==0 or not job["selection_json"]: raise jobs.ReviewConflict("REFERENCE_NOT_READY")
    selection=json.loads(job["selection_json"])
    validate_period(selection,start,end)
    settings=get_settings()
    mapping_keys=[k for k in selection["policy"] if k.startswith("source_") and (k.endswith("template") or k.endswith("column") or k in {"source_db_name","source_table"})]
    if any(selection["policy"][k]!=getattr(settings,k) for k in mapping_keys): raise jobs.ReviewConflict("POLICY_CHANGED_REVIEW_AGAIN")
    key=(job_id,actor,start.isoformat(),end.isoformat(),settings.source_pressure_unit)
    # Coalesce duplicate GETs, bounded to 8 short slices. Source
    # statements are indexed narrow ranges, with a hard row cap and two readers.
    with LOCK:
        cached=CACHE.get(key)
        if cached and cached[0]>monotonic(): return deepcopy(cached[1])
        flight=INFLIGHT.get(key)
        leader=flight is None
        if leader:
            flight=Event();INFLIGHT[key]=flight
    if not leader:
        if not flight.wait(10): raise jobs.ReviewConflict("RAW_READER_BUSY_RETRY")
        with LOCK:
            cached=CACHE.get(key)
            if cached and cached[0]>monotonic(): return deepcopy(cached[1])
        raise jobs.ReviewConflict("RAW_READER_BUSY_RETRY")
    acquired=False
    try:
        acquired=READERS.acquire(timeout=3)
        if not acquired: raise jobs.ReviewConflict("RAW_READER_BUSY_RETRY")
        result=read_raw(settings,job["machine_number"],job["module"],start,end)
        with LOCK:
            CACHE[key]=(monotonic()+60,result); CACHE.move_to_end(key)
            while len(CACHE)>8: CACHE.popitem(last=False)
        return deepcopy(result)
    finally:
        if acquired: READERS.release()
        with LOCK: INFLIGHT.pop(key,None);flight.set()
