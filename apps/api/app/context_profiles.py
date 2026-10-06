"""Past-only proposed regimes and observed transition templates.

Models describe reference data, not certified healthy operation. A supported
proposal is still subject to reference review and independent validation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from bisect import bisect_left
from dataclasses import replace
import json

import numpy as np

from .observed_context import PHYSICAL, VERSION as FEATURE_VERSION
from .unified_events import fingerprint
from .context_scope import scope_of,state_of

VERSION = "conditional-steady-transition-candidate-v4"
STABLE_MINUTES = 5
MAX_PHASE_MINUTES = 120
MIN_REGIME_DAYS = 7
MIN_REGIME_MINUTES = 200
MIN_PHASE_EVENTS = 3
MIN_PHASE_DAYS = 3


def vector(w):
    return np.asarray([w.features[f] for f in PHYSICAL], dtype=float)


def robust(values):
    values = np.asarray(values)
    center = np.median(values, axis=0)
    scale = np.maximum(.1, np.maximum(1.4826*np.median(np.abs(values-center),axis=0),
                                     (np.quantile(values,.75,axis=0)-np.quantile(values,.25,axis=0))/1.349))
    return center, scale


def supported_context(w):
    """Owner codebook remains authoritative; manual/unknown is not auto normal."""
    if not w.measured or not w.context_key:
        return None
    run, module, busy, sv = w.context_key.split("|")
    if run != "run" or module != "on" or busy not in {"0","false","off"}:
        return None
    if w.control.get("valve_mean") is None or w.control["valve_mean"] < 0:
        return None
    sv = "off" if sv in {"off","0","false"} else "on" if sv in {"on","1","true"} else None
    return f"RUN_MODULE_ON_BUSY0_SV_{sv.upper()}" if sv else None


def trailing_stability(windows, scale, limit):
    result, trail = {}, []
    for w in windows:
        context = supported_context(w)
        if (not context or (trail and (trail[-1].window_end != w.window_start
                                     or supported_context(trail[-1]) != context))):
            trail = []
        if context:
            trail.append(w)
            trail = trail[-STABLE_MINUTES:]
        if len(trail) == STABLE_MINUTES:
            a = np.asarray([vector(x) for x in trail])
            movement = float(np.max(np.ptp(a,axis=0)/scale))
            result[w.window_start.isoformat()] = (movement <= limit, movement)
        else:
            result[w.window_start.isoformat()] = (False, None)
    return result


def fit_regimes(reference):
    eligible = [w for w in reference if supported_context(w)]
    if not eligible:
        return {"regimes": [], "stability_scale": None, "stability_limit": None}
    differences = [vector(b)-vector(a) for a,b in zip(reference,reference[1:])
                   if supported_context(a) and supported_context(a)==supported_context(b)
                   and a.window_end==b.window_start]
    _, stability_scale = robust(differences) if differences else robust([vector(w) for w in eligible])
    stability_scale = np.maximum(.1,stability_scale/np.sqrt(2))
    # Learn a descriptive low-movement criterion from Reference only. It is
    # not a healthy label and never uses Shadow to select stable intervals.
    movement = trailing_stability(reference, stability_scale, float("inf"))
    values = [x[1] for x in movement.values() if x[1] is not None]
    limit = max(.25, float(np.quantile(values,.5))) if values else .25
    flags = trailing_stability(reference, stability_scale, limit)
    blocks, current = [], []
    for w in reference:
        context = supported_context(w)
        stable = flags[w.window_start.isoformat()][0]
        if current and (not stable or current[-1].window_end != w.window_start
                        or supported_context(current[-1]) != context):
            if len(current) >= 10: blocks.append(current)
            current = []
        if stable: current.append(w)
    if len(current) >= 10: blocks.append(current)
    groups = []
    by_context=defaultdict(list)
    for block in blocks: by_context[supported_context(block[0])].extend(block)
    from sklearn.mixture import GaussianMixture
    from threadpoolctl import threadpool_limits
    for context,records in by_context.items():
        matrix=np.asarray([vector(w) for w in records])
        center,scale=robust(matrix)
        normalized=(matrix-center)/scale
        sample=normalized[np.linspace(0,len(normalized)-1,min(5000,len(normalized)),dtype=int)]
        if len(sample)<30:
            groups.append({"context":context,"windows":records})
            continue
        # Descriptive Reference-only mode selection. Slow long-term variation
        # within a repeated mode is not split into dozens of ten-minute bins.
        # BIC separates repeated levels; no Shadow labels/metrics choose k.
        choices=[]
        with threadpool_limits(limits=1):
            for k in range(1,min(4,len(sample)//30,len(np.unique(sample,axis=0)))+1):
                fit=GaussianMixture(n_components=k,covariance_type="diag",reg_covar=.01,
                                    random_state=17,n_init=2,max_iter=100).fit(sample)
                choices.append((fit.bic(sample),fit))
            selected=min(choices,key=lambda x:x[0])[1]
            labels=selected.predict(normalized)
        for label in sorted(set(labels)):
            members=[w for w,assigned in zip(records,labels) if assigned==label]
            groups.append({"context":context,"windows":members})
    # Rank all Reference modes before applying the display/model budget. A
    # chronological budget would let the first day's startup plateaus crowd
    # out repeated steady operation across later days.
    groups.sort(key=lambda g:(len({w.window_start.date() for w in g["windows"]}),len(g["windows"])),reverse=True)
    groups=groups[:12]
    regimes = []
    for group in groups:
        records = group["windows"]
        matrix = np.asarray([vector(w) for w in records])
        center, scale = robust(matrix)
        score = np.max(np.abs(matrix-center)/scale,axis=1)
        threshold = max(1.0, float(np.quantile(score,.995)))
        days = len({w.window_start.date() for w in records})
        enough = days >= MIN_REGIME_DAYS and len(records) >= MIN_REGIME_MINUTES
        midpoint = sorted({w.window_start.date() for w in records})[days//2]
        first = [vector(w) for w in records if w.window_start.date()<midpoint]
        last = [vector(w) for w in records if w.window_start.date()>=midpoint]
        half_shift = float(np.max(np.abs(np.median(first,axis=0)-np.median(last,axis=0))/scale)) if first and last else None
        regimes.append({"regime_id":fingerprint([group["context"], records[0].window_start, center.tolist()])[:20],
            "context":group["context"], "center":center.tolist(), "scale":scale.tolist(), "threshold":threshold,
            "minutes":len(records), "days":days, "start":records[0].window_start.isoformat(),
            "end":records[-1].window_end.isoformat(), "coverage_supported":enough,
            "half_shift":half_shift, "reference_review_required":True,
            "status":"PROPOSED_REGIME" if enough else "INSUFFICIENT_REGIME_COVERAGE"})
    return {"regimes":regimes, "stability_scale":stability_scale.tolist(), "stability_limit":limit}


def phase_entries(windows, control_events, valve_step_limit, regimes=(),lookback_minutes=30):
    stamps = [w.window_start for w in windows]
    entries = []
    for event in sorted(control_events,key=lambda e:(e["occurred_at"],e["event_id"])):
        d = event.get("payload", {}).get("details") or json.loads(event["payload_json"])["details"]
        if not d.get("witness_usable"):
            continue
        kind = event["event_type"]
        if kind == "VALVE_COMMAND_CHANGED":
            step=abs(d["after"]-d["before"])
            if step < valve_step_limit or step<=1: continue
            subtype = "VALVE_INCREASE" if d["after"] > d["before"] else "VALVE_DECREASE"
        elif kind == "SV_CHANGED": subtype = f"SV_{str(d['before']).casefold()}_TO_{str(d['after']).casefold()}"
        elif kind == "BUSY_CHANGED": subtype = f"BUSY_{d['before']}_TO_{d['after']}"
        elif kind in {"MODULE_STATE_CHANGED","COMPRESSOR_STATE_CHANGED"}: subtype = f"{kind}_{d['before']}_TO_{d['after']}"
        else: continue
        at = datetime.fromisoformat(event["occurred_at"])
        i = bisect_left(stamps, at.replace(second=0,microsecond=0)+timedelta(minutes=1))
        if i >= len(windows) or windows[i].window_start-at > timedelta(minutes=3): continue
        context = supported_context(windows[i])
        if not context: continue
        before_index=bisect_left(stamps,at.replace(second=0,microsecond=0))-1
        origin_id="UNKNOWN"
        # Anchor to an observed recognized starting regime across the complete
        # short control trajectory. An SV On period can be too brief for its
        # own steady model while its preceding Off regime is well supported.
        # Any missing/invalid minute breaks that witness chain.
        for j in range(before_index,max(-1,before_index-lookback_minutes),-1):
            before=windows[j]
            if not before.measured or at-before.window_end>timedelta(minutes=lookback_minutes): break
            if j<before_index and before.window_end!=windows[j+1].window_start: break
            matches=[(float(np.max(np.abs(vector(before)-r["center"])/r["scale"])),r) for r in regimes
                     if r["coverage_supported"] and r["context"]==supported_context(before)]
            distance,origin=min(matches,key=lambda x:x[0]) if matches else (None,None)
            if origin and distance<=origin["threshold"]:
                origin_id=origin["regime_id"];break
        priority={"SV_CHANGED":4,"MODULE_STATE_CHANGED":3,"COMPRESSOR_STATE_CHANGED":3,"BUSY_CHANGED":2,"VALVE_COMMAND_CHANGED":1}[kind]
        entry = {"at":at,"cluster_start":at,"index":i,"key":f"{subtype}|FROM_{origin_id}|{context}",
                 "event_id":event["event_id"],"context":context,"priority":priority,"origin_regime_id":origin_id,
                 "witness_event_ids":[event["event_id"]]}
        # Correlated actions within two minutes are one model example, while
        # every original control event remains separately retained in SQL.
        if entries and entry["context"]==entries[-1]["context"] and at-entries[-1]["cluster_start"] <= timedelta(minutes=2):
            old=entries[-1]
            if entry["priority"]>old["priority"]:
                entry["cluster_start"]=old["cluster_start"]
                entry["witness_event_ids"]=old["witness_event_ids"]+entry["witness_event_ids"]
                entries[-1]=entry
            else:
                old["witness_event_ids"].extend(entry["witness_event_ids"])
        else: entries.append(entry)
    return entries


def fit_templates(reference, entries, stability_scale):
    groups = defaultdict(list)
    for n, entry in enumerate(entries):
        stop = entries[n+1]["at"] if n+1<len(entries) else datetime.max
        points = []
        previous = None
        for w in reference[entry["index"]:entry["index"]+MAX_PHASE_MINUTES]:
            elapsed = int((w.window_start-entry["at"]).total_seconds()//60)
            if w.window_start >= stop or elapsed > MAX_PHASE_MINUTES or not w.measured or supported_context(w) != entry["context"]:
                break
            if previous and previous.window_end != w.window_start: break
            points.append((elapsed, vector(w)))
            previous = w
        if points: groups[entry["key"]].append((entry, points))
    templates = []
    for key, examples in groups.items():
        day_count = len({e[0]["at"].date() for e in examples})
        bins = defaultdict(list)
        for _, points in examples:
            for elapsed, values in points: bins[elapsed].append(values)
        curve = {}
        for elapsed, observations in sorted(bins.items()):
            if len(observations) < MIN_PHASE_EVENTS: continue
            matrix = np.asarray(observations)
            low, center, high = np.quantile(matrix,[.05,.5,.95],axis=0)
            radius = np.maximum(np.maximum(center-low,high-center), np.maximum(.1,np.asarray(stability_scale)*.5))
            curve[str(elapsed)] = {"center":center.tolist(),"radius":radius.tolist(),"events":len(observations)}
        templates.append({"template_id":fingerprint(key)[:20],"key":key,"events":len(examples),"days":day_count,
            "coverage_supported":len(examples)>=MIN_PHASE_EVENTS and day_count>=MIN_PHASE_DAYS and bool(curve) and "FROM_UNKNOWN" not in key,
            "reference_review_required":True,"curve":curve,
            "examples":[{"event_id":e["event_id"],"at":e["at"].isoformat(),"observed_minutes":len(p)} for e,p in examples]})
    return templates


def fit_context_candidate(windows, control_events, *, machine, module, shadow_start, shadow_end):
    if shadow_start.tzinfo or shadow_end.tzinfo or not shadow_start < shadow_end:
        raise ValueError("ordered source-local split required")
    selected = sorted([w for w in windows if w.machine_number==machine and w.module==module],key=lambda w:w.window_start)
    if len({w.window_start for w in selected}) != len(selected) or any(w.feature_version != FEATURE_VERSION for w in selected):
        raise ValueError("incompatible or duplicate minute input")
    ref = [w for w in selected if w.window_start<shadow_start
           and "mock_normal" not in w.state_counts.get("compressor",{})]
    controls = [e for e in control_events if e["module"] in (None,module) and e["machine_number"]==machine]
    ref_events = [e for e in controls if datetime.fromisoformat(e["occurred_at"])<shadow_start]
    steps=[]
    for e in ref_events:
        d = e.get("payload",{}).get("details") or json.loads(e["payload_json"])["details"]
        if e["event_type"]=="VALVE_COMMAND_CHANGED" and d.get("witness_usable"):
            steps.append(abs(d["after"]-d["before"]))
    valve_limit = max(1.,float(np.quantile(steps,.95))) if steps else 1.
    model = fit_regimes(ref)
    entries = phase_entries(ref,ref_events,valve_limit,model["regimes"])
    model.update(version=VERSION, feature_version=FEATURE_VERSION, physical_features=list(PHYSICAL),
                 machine_number=machine,module=module,shadow_start=shadow_start.isoformat(),shadow_end=shadow_end.isoformat(),
                 valve_step_limit=valve_limit, transition_templates=fit_templates(ref,entries,model["stability_scale"] or [.1]*8),
                 phase_origin_lookback_minutes=30,maximum_phase_minutes=MAX_PHASE_MINUTES,
                 response_tracking="retain_control_context_for_delayed_physical_response",
                 auto_activation_allowed=False, reference_review_required=True,
                 regime_selector={"method":"Reference-only diagonal mixture BIC","minimum_components_per_context":1,"maximum_components_per_context":4,
                                  "seed":17,"sample_budget":5000,"covariance_floor":.01,"stability_quantile":.5},
                 status="REVIEW_REQUIRED" if any(r["coverage_supported"] for r in model["regimes"]) else "INSUFFICIENT_DATA",
                 minimum_support={"regime_days":MIN_REGIME_DAYS,"regime_minutes":MIN_REGIME_MINUTES,
                                  "transition_events":MIN_PHASE_EVENTS,"transition_days":MIN_PHASE_DAYS},
                 data_quality_counts=dict(Counter(w.measurement_quality for w in selected)))
    model["context_coverage"]={sv:{"minutes":sum(state_of(supported_context(w))==sv for w in ref),
        "days":len({w.window_start.date() for w in ref if state_of(supported_context(w))==sv})} for sv in ("OFF","ON")}
    return model


def assess_context(windows, control_events, model):
    if model["version"] != VERSION: raise ValueError("unsupported context model")
    ordered = sorted(windows,key=lambda w:w.window_start)
    scope=scope_of(model)
    eligible=[bool(supported_context(w)) and (scope is None or state_of(supported_context(w)) in scope["included_sv_states"]) for w in ordered]
    analysis=[w if ok or scope is None else replace(w,features=None,context_key=None) for w,ok in zip(ordered,eligible)]
    stability = trailing_stability(analysis,np.asarray(model["stability_scale"] or [.1]*8),model["stability_limit"] or .25)
    entries = phase_entries(analysis,control_events,model["valve_step_limit"],model["regimes"],model.get("phase_origin_lookback_minutes",1))
    if scope:
        stamps=[w.window_start for w in ordered]
        for entry in entries:
            at=entry["at"]
            prior=bisect_left(stamps,at.replace(second=0,microsecond=0))-1
            # Returning from an excluded state uses the accepted steady model
            # immediately, without inventing a Transition envelope or timer.
            entry["origin_excluded"]=any(state_of(supported_context(w)) in scope["excluded_sv_states"]
                for w in ordered[max(0,prior-2):prior+1] if timedelta(0)<=at-w.window_end<=timedelta(minutes=3))
    by_index = {e["index"]:e for e in entries}
    review=model.get("reference_review")
    templates = {t["key"]:t for t in model["transition_templates"] if t["coverage_supported"] and
                 (not review or t["template_id"] in review["accepted_template_ids"])}
    active, output = None, []
    for i,w in enumerate(ordered):
        if i in by_index: active=by_index[i]
        context=supported_context(w)
        stable,movement=stability[w.window_start.isoformat()]
        excluded=scope is not None and context is not None and state_of(context) not in scope["included_sv_states"]
        candidates=[r for r in model["regimes"] if eligible[i] and r["context"]==context and r["coverage_supported"] and
                    (not review or r["regime_id"] in review["accepted_regime_ids"])]
        matches=[(float(np.max(np.abs(vector(w)-np.asarray(r["center"]))/r["scale"])),r) for r in candidates] if w.measured else []
        score,regime=min(matches,key=lambda x:x[0]) if matches else (None,None)
        within = regime is not None and score <= regime["threshold"]
        elapsed=int((w.window_start-active["at"]).total_seconds()//60) if active else None
        template=templates.get(active["key"]) if active and (eligible[i] or scope is None) else None
        envelope=template["curve"].get(str(elapsed)) if template and elapsed is not None else None
        transition_score=float(np.max(np.abs(vector(w)-envelope["center"])/envelope["radius"])) if w.measured and envelope else None
        if "mock_normal" in w.state_counts.get("compressor",{}): category="MOCK_DATA"; active=None
        elif not w.measured: category="DATA_UNAVAILABLE"; active=None
        elif excluded: category="STATE_GATE_EXCLUDED"; active=None
        elif context is None: category="UNSUPPORTED_CONTROL_CONTEXT"; active=None
        elif stable and within:
            category="WITHIN_PROPOSED_STEADY"
            # A control command can precede the thermal/pressure response by
            # several minutes. Initial steady values do not end its evidence
            # context; retain it until the bounded horizon/new event/gap.
            if elapsed is None or elapsed>MAX_PHASE_MINUTES:active=None
        elif stable and template and template.get('fleet_assistance'):
            # Relative Fleet response cannot certify an unfamiliar persistent
            # absolute plateau. Accepted Local steady evidence remains required.
            category="NEW_STEADY_LEVEL"
        elif active and elapsed is not None and elapsed<=MAX_PHASE_MINUTES and envelope:
            category="WITHIN_PROPOSED_TRANSITION" if transition_score<=1 else "UNEXPECTED_TRANSITION"
        elif stable: category="NEW_STEADY_LEVEL"
        elif active and elapsed is not None and elapsed<=MAX_PHASE_MINUTES and not active.get("origin_excluded"): category="UNSUPPORTED_TRANSITION"
        elif within: category="WITHIN_PROPOSED_STEADY"
        else: category="STEADY_DEVIATION" if regime else "INSUFFICIENT_REFERENCE"
        phase_envelope=envelope if category in {"WITHIN_PROPOSED_TRANSITION","UNEXPECTED_TRANSITION"} else None
        diagnostic=phase_envelope or ({"center":regime["center"],"radius":(np.asarray(regime["scale"])*regime["threshold"]).tolist()} if regime else None)
        main=None
        if w.measured and diagnostic:
            delta=vector(w)-diagnostic["center"]
            contributor=int(np.argmax(np.abs(delta)/np.maximum(.1,diagnostic["radius"])))
            main={"feature":PHYSICAL[contributor],"value":float(vector(w)[contributor]),
                  "lower":diagnostic["center"][contributor]-diagnostic["radius"][contributor],
                  "upper":diagnostic["center"][contributor]+diagnostic["radius"][contributor],
                  "delta":float(delta[contributor]),"unit":"source temperature unit" if contributor>=6 else "psi"}
        output.append({"time":w.window_start.isoformat(),"module":w.module,"category":category,"context":context,
            "features":w.features,"control":w.control,"state_counts":w.state_counts,"quality":w.measurement_quality,
            "quality_reason":w.reason,"coverage":w.coverage,"movement":movement,"stable":stable,
            "regime_id":regime["regime_id"] if regime else None,"steady_score":score,
            "steady_threshold":regime["threshold"] if regime else None,"transition_score":transition_score,
            "transition_elapsed_minutes":elapsed,"transition_event_id":active["event_id"] if active else None,
            "transition_envelope":phase_envelope,"steady_envelope":{"center":regime["center"],"radius":(np.asarray(regime["scale"])*regime["threshold"]).tolist()} if regime else None,"main_evidence":main,
            "reference_review_required":not bool(review)})
        output[-1].update(model_evaluated=bool(regime or phase_envelope),
                         transition_template_id=template['template_id'] if template else None,
                         transition_source="FLEET_ASSISTED" if template and template.get('fleet_assistance') else "LOCAL" if template else None,
                         state_gate_reason=scope["excluded_reason"] if excluded else None,
                         transition_steady_fallback=bool(active and active.get("origin_excluded") and not phase_envelope))
    return output
