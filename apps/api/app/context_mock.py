"""Deterministic mock future observations. Never a source/approval receipt.

This exercises the frozen physical evaluator without updating Reference,
source clocks, jobs, reviewer state, events, or Active pointers.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math

from .observed_context import ObservedMinute, PHYSICAL
from .context_profiles import assess_context
from .context_scope import scope_of, state_of, validation_receipt
from .context_review import gate
from .unified_events import fingerprint

VERSION = "frozen-reference-normal-mock-v1"


def normal_mock(model, settings, seed=58, day=None):
    review = model.get("reference_review")
    if not review:
        raise ValueError("REVIEW_FROZEN_REFERENCE_BEFORE_MOCK")
    scope = scope_of(model)
    accepted = set(review["accepted_regime_ids"])
    eligible = [r for r in model["regimes"] if r["coverage_supported"] and r["regime_id"] in accepted
                and (not scope or state_of(r["context"]) in scope["included_sv_states"])]
    if not eligible:
        raise ValueError("NO_ACCEPTED_REFERENCE_FOR_NORMAL_MOCK")
    # One reviewed steady regime for this smoke test; it does not invent a
    # healthy transition trajectory between independently reviewed levels.
    regime = max(eligible, key=lambda r:(r["days"], r["minutes"], r["regime_id"]))
    sv = state_of(regime["context"])
    zone = ZoneInfo(settings.source_timezone)
    reviewed_at = datetime.fromisoformat(review["at"]).astimezone(zone).replace(tzinfo=None)
    start = max(reviewed_at, datetime.fromisoformat(model["shadow_end"]))
    start = start.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    dates = [(start+timedelta(days=i)).date().isoformat() for i in range(3)]
    selected = day.isoformat() if day is not None else dates[0]
    if selected not in dates:
        raise ValueError("MOCK_DAY_OUTSIDE_SIMULATED_PERIOD")
    # Six physical channels; delta pressures are derived, never independently
    # randomized. The small correlated variation is fixed by seed, not tuned
    # against score outcomes. No parameters are fitted from these samples.
    rows = []
    for i in range(3*1440):
        t = start+timedelta(minutes=i)
        phase = seed*.137+i*.045
        values = {name: float(regime["center"][j]+.04*regime["scale"][j]*
                     (math.sin(phase+j*.21)+.2*math.sin(i*.19+j)))
                  for j,name in enumerate(PHYSICAL) if name not in {"dp1","dp2"}}
        values.update(dp1=values["hp1"]-values["lp1"],dp2=values["hp2"]-values["lp2"])
        rows.append(ObservedMinute(model["machine_number"],model["module"],t,t+timedelta(minutes=1),
            60,1.,1.,"PASS","SYNTHETIC_MOCK_NOT_SENSOR_DATA",values,
            {"compressor":{"run":60},"module":{"on":60},"busy":{"0":60},"sv":{sv.lower():60}},
            f"run|on|0|{sv.lower()}",{"valve_mean":100.,"valve_min":100.,"valve_max":100.,"valve_samples":60}))
    points = assess_context(rows,[],model)
    receipt = {**validation_receipt(points,model),"prospective":False,"source_kind":"MOCK",
               "approval_eligible":False,"frozen_reviewed_profile_id":model["profile_id"]}
    passed = receipt["supported_days"]>=3 and receipt["supported_minutes"]>=settings.profile_min_shadow_windows \
             and receipt["unresolved_minutes"]==0 and receipt["flag_pct"]<=settings.profile_max_shadow_flag_pct
    included = scope["included_sv_states"] if scope else ["OFF","ON"]
    have = {state_of(r["context"]) for r in eligible}
    return {"mock_id":fingerprint([VERSION,model["profile_id"],seed]),"version":VERSION,
            "source_kind":"MOCK","machine_number":model["machine_number"],"module":model["module"],
            "profile_id":model["profile_id"],"seed":seed,"days":dates,"selected_day":selected,
            "start":start.isoformat(),"end":(start+timedelta(days=3)).isoformat(),
            "source_timezone":settings.source_timezone,"pressure_unit":"psi",
            "sv":sv,"regime_id":regime["regime_id"],"steady_only":True,
            "missing_reference_states":sorted(set(included)-have),
            "normal_test_passed":passed,"receipt":receipt,"actual_readiness":gate(model,settings),
            "chart":[p for p in points if p["time"][:10]==selected],
            "interpretation":"Synthetic virtual dates after frozen review; tests software behavior only. No source insertion, retraining or Active approval evidence."}
