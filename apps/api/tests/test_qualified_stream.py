import json
from datetime import datetime, timedelta, timezone

import pytest

from apps.api.app.qualified_stream import CompletedMinuteStream
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows


START = datetime(2026, 9, 1)


def row(second):
    return {"recorded_at": START+timedelta(seconds=second), "machine_number":"MX080", "Status":"Run",
            "Status_6":"On", "Busy_6":"0", "SV_6":"Off", "Hp_1st_6":150., "Lp_1st_6":25.,
            "Hp_2nd_6":210., "Lp_2nd_6":20., "Valve_6":90., "TempHi_6":80., "TempLo_6":-10.}


def clock(seconds):
    return (START+timedelta(seconds=seconds)).replace(tzinfo=timezone.utc)


def test_five_minute_restart_and_retry_match_complete_raw_replay():
    policy=WindowPolicy("UTC",late_arrival_seconds=30)
    raw=[row(s) for s in range(600)]
    reference=build_completed_windows(raw,as_of=clock(630),policy=policy,modules=(6,))
    stream=CompletedMinuteStream(policy,(6,))
    first, _=stream.consume(raw[:300],as_of=clock(300),batch_id="first")
    assert len(first)==4 and len(stream.pending)==60
    stream=CompletedMinuteStream.from_checkpoint(json.loads(json.dumps(stream.checkpoint())))
    retry, info=stream.consume(raw[:300],as_of=clock(300),batch_id="first")
    assert retry==[] and info["duplicate_batch"]
    middle,_=stream.consume(raw[300:],as_of=clock(600),batch_id="second")
    last,_=stream.consume([],as_of=clock(630),batch_id="flush")
    assert first+middle+last==reference
    assert not stream.pending


def test_source_duplicates_are_not_mistaken_for_delivery_retries():
    stream=CompletedMinuteStream(WindowPolicy("UTC",late_arrival_seconds=30),(6,))
    raw=[row(s) for s in range(60)]
    result,_=stream.consume(raw+[raw[0]],as_of=clock(90),batch_id="source-duplicate")
    assert result[0].reason=="DUPLICATE_MACHINE_SECOND"
    changed=list(raw); changed[0]={**raw[0],"Hp_2nd_6":400.}
    with pytest.raises(ValueError,match="payload changed"):
        stream.consume(changed,as_of=clock(90),batch_id="source-duplicate")


def test_late_sample_inside_grace_completes_window_but_closed_window_is_not_rewritten():
    stream=CompletedMinuteStream(WindowPolicy("UTC",late_arrival_seconds=30),(6,))
    assert stream.consume([row(s) for s in range(59)],as_of=clock(60),batch_id="partial")[0]==[]
    assert stream.consume([row(59)],as_of=clock(80),batch_id="late-in-grace")[0]==[]
    result,_=stream.consume([],as_of=clock(90),batch_id="close")
    assert result[0].eligible and result[0].sample_count==60
    again,info=stream.consume([row(20)],as_of=clock(100),batch_id="too-late")
    assert not again and info["late_rows_dropped"]==1


def test_backwards_clock_future_sample_and_wrong_checkpoint_are_rejected():
    stream=CompletedMinuteStream(WindowPolicy("UTC"),(6,))
    with pytest.raises(ValueError,match="at or after as_of"):
        stream.consume([row(60)],as_of=clock(60),batch_id="future")
    stream.consume([],as_of=clock(120),batch_id="empty")
    with pytest.raises(ValueError,match="backwards"):
        stream.consume([],as_of=clock(60),batch_id="backwards")
    state=stream.checkpoint(); state["feature_version"]="old-snapshot"
    with pytest.raises(ValueError,match="incompatible"):
        CompletedMinuteStream.from_checkpoint(state)
