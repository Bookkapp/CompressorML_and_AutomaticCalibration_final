from dataclasses import replace
from datetime import datetime, timedelta

from apps.api.app.observed_context import ObservedMinute
from apps.api.app.context_profiles import fit_context_candidate, assess_context


def minute(at, hp2=200, temphi=60):
    return ObservedMinute("MX017",1,at,at+timedelta(minutes=1),60,1.,1.,"PASS","",
        {"hp1":190.,"lp1":15.,"hp2":float(hp2),"lp2":5.,"dp1":175.,"dp2":float(hp2-5),"temphi":float(temphi),"templo":-65.},
        {"compressor":{"run":60},"module":{"on":60},"busy":{"0":60},"sv":{"off":60}},"run|on|0|off",
        {"valve_mean":100.,"valve_min":100.,"valve_max":100.,"valve_samples":60})


def reference():
    base=datetime(2026,9,1)
    return [minute(base+timedelta(days=d,minutes=i),200 if i<180 else 260)
            for d in range(7) for i in range(360)]


def test_two_reviewable_steady_levels_do_not_become_one_wide_baseline():
    start=datetime(2026,9,8)
    ref=reference()
    shadow=[minute(start+timedelta(minutes=i),260) for i in range(30)]
    model=fit_context_candidate(ref+shadow,[],machine="MX017",module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    supported=[r for r in model["regimes"] if r["coverage_supported"]]
    assert len(supported)==2
    assert sorted(r["center"][2] for r in supported)==[200,260]
    assert model["reference_review_required"] and not model["auto_activation_allowed"]
    scored=assess_context(shadow,[],model)
    assert scored[-1]["category"]=="WITHIN_PROPOSED_STEADY"


def test_flat_unknown_plateau_and_shadow_changes_do_not_refit_reference():
    start=datetime(2026,9,8)
    ref=reference()
    a=[minute(start+timedelta(minutes=i),280) for i in range(30)]
    b=[minute(start+timedelta(minutes=i),400) for i in range(30)]
    args=dict(machine="MX017",module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    first=fit_context_candidate(ref+a,[],**args)
    second=fit_context_candidate(ref+b,[],**args)
    assert first["regimes"]==second["regimes"]
    scored=assess_context(a,[],first)
    assert scored[-1]["stable"] and scored[-1]["category"]=="NEW_STEADY_LEVEL"
    assert scored[-1]["steady_score"]>scored[-1]["steady_threshold"]


def test_manual_and_bad_quality_measurements_do_not_become_normal_proposals():
    start=datetime(2026,9,8)
    ref=[replace(w,context_key="run|changevalve|1|off") for w in reference()]
    model=fit_context_candidate(ref,[],machine="MX017",module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    assert model["regimes"]==[] and model["status"]=="INSUFFICIENT_DATA"
    data=[replace(minute(start),measurement_quality="DATA_QUALITY",features=None,reason="SOURCE_GAP")]
    result=assess_context(data,[],model)
    assert result[0]["category"]=="DATA_UNAVAILABLE" and result[0]["features"] is None


def test_first_day_startup_plateaus_do_not_crowd_out_repeated_later_steady():
    base=datetime(2026,9,1)
    startup=[minute(base+timedelta(minutes=i),hp2=400+(i//30)*30,temphi=100) for i in range(450)]
    repeated=[minute(base+timedelta(days=d,minutes=i),200,60) for d in range(1,8) for i in range(180)]
    shadow=base+timedelta(days=8)
    model=fit_context_candidate(startup+repeated,[],machine="MX017",module=1,shadow_start=shadow,shadow_end=shadow+timedelta(days=3))
    assert any(r["coverage_supported"] and r["center"][2]==200 for r in model["regimes"])


def test_short_second_context_is_an_unsupported_proposal_not_a_failed_job():
    base=datetime(2026,9,1)
    brief=[replace(minute(base+timedelta(days=7,minutes=i),300),context_key="run|on|0|on") for i in range(20)]
    shadow=base+timedelta(days=8)
    model=fit_context_candidate(reference()+brief,[],machine="MX017",module=1,shadow_start=shadow,shadow_end=shadow+timedelta(days=3))
    assert any(r["coverage_supported"] for r in model["regimes"])
    assert all(not r["coverage_supported"] for r in model["regimes"] if r["context"].endswith("SV_ON"))
