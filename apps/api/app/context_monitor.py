"""All-state controls and approved frozen context inference in one transaction."""
from dataclasses import asdict
from datetime import datetime,timedelta
from collections import defaultdict
from sqlalchemy import select
from .observed_context import build_observed_minutes,ObservedMinute
from .unified_events import TransitionTracker,append_events,make_event
from .context_review import active,gate
from .context_reference import get_profile
from .context_profiles import assess_context


def consume_observed(conn,rows,as_of,stream,checkpoint,*,source_namespace,mode,run_id,fleet=None):
    from .config import get_settings
    tracker=TransitionTracker(source_namespace,stream.policy.source_timezone,modules=stream.modules,
                              mode=mode,checkpoint=checkpoint.get("tracker"))
    observed=tracker.consume(rows)
    append_events(conn,observed)
    minutes=build_observed_minutes(rows,as_of=as_of,policy=stream.policy,modules=stream.modules)
    grouped=defaultdict(list)
    for w in minutes: grouped[w.machine_number,w.module].append(w)
    history=checkpoint.get("history",{})
    controls=checkpoint.get("controls",[])
    # Ledger keeps every command. Inference needs only potentially relevant
    # boundaries, with bounded metadata rather than repeated physical payloads.
    controls.extend({"event_id":e["event_id"],"occurred_at":e["occurred_at"],"module":e["module"],
        "machine_number":e["machine_number"],"event_type":e["event_type"],"payload_json":e["payload_json"]}
        for e in observed if e["family"]=="CONTROL")
    cutoff=stream.closed_before-timedelta(minutes=125)
    controls=[e for e in controls if datetime.fromisoformat(e["occurred_at"])>=cutoff]
    if len(controls)>100000: raise ValueError("Context control history budget exceeded; no checkpoint advanced")
    previous=checkpoint.get("categories",{})
    fleet_previous=checkpoint.get('fleet_previous',{})
    settings=get_settings()
    for (machine,module),current in grouped.items():
        key=f"{machine}/M{module}"
        old=[]
        for item in history.get(key,[]):
            item=dict(item)
            for f in ("window_start","window_end"): item[f]=datetime.fromisoformat(item[f])
            old.append(ObservedMinute(**item))
        combined=old+current
        pointer=conn.execute(select(active).where(active.c.machine_number==machine,active.c.module==module).with_for_update()).mappings().first()
        model=get_profile(conn.engine,pointer["profile_id"]) if pointer else None
        ready=model is not None and gate(model,settings)["ready"]
        if ready:
            relevant=[e for e in controls if e["machine_number"]==machine and e["module"] in (None,module)]
            points=assess_context(combined,relevant,model)[len(old):]
        else:
            points=[{"time":w.window_start.isoformat(),"category":"NO_ACTIVE_CONTEXT_PROFILE",
                     "features":w.features,"quality":w.measurement_quality} for w in current]
        for p in points:
            identity=[p["category"],model["profile_id"] if ready else None,p.get("quality")]
            if previous.get(key)!=identity:
                abnormal=p["category"] in {"UNEXPECTED_TRANSITION","STEADY_DEVIATION"}
                append_events(conn,[make_event(source_key=[run_id,key,p["time"],identity],machine=machine,module=module,
                    occurred_at=p["time"],timezone_name=stream.policy.source_timezone,family="ANOMALY" if abnormal else "PHASE",
                    event_type="CONTEXT_ASSESSMENT_CHANGED",mode=mode,assessment="NOT_EVALUATED" if p["category"]=="STATE_GATE_EXCLUDED" else "ASSESSED" if ready else "NOT_SCORED",
                    run_id=run_id,details={"before":previous.get(key),"after":p["category"],"point":p,
                        "profile_id":model["profile_id"] if ready else None,"control_events_retained":True})])
                previous[key]=identity
        history[key]=[asdict(w) for w in combined if w.window_start>=cutoff]
        if fleet:
            from .fleet_worker import score_observed
            from .fleet_stable_events import evidence_events
            result=score_observed(fleet,machine,module,combined,current,model)
            last=fleet_previous.get(key)
            append_events(conn,evidence_events(result,source_digest=f'{run_id}:{source_namespace}',
                source_namespace=source_namespace,verified_source_mapping=True,previous_point=last))
            if result['points']:fleet_previous[key]=result['points'][-1]
    # Normalize to JSON-compatible checkpoint with declared source-local times.
    from .qualified_persistence import canonical
    import json
    return json.loads(canonical({"tracker":tracker.checkpoint(),"history":history,"controls":controls,"categories":previous,'fleet_previous':fleet_previous}))
