from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from apps.api.app.observed_context import build_observed_minutes
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows
from apps.api.app.unified_events import TransitionTracker, metadata, events, append_events, list_events


def sample(stamp, **extra):
    row = {"machine_number": "MX017", "recorded_at": stamp, "Status": "Run"}
    for m in range(1,9):
        row.update({f"Status_{m}": "On", f"Busy_{m}": 0, f"SV_{m}": "Off",
                    f"Valve_{m}": 100, f"Hp_1st_{m}": 190, f"Lp_1st_{m}": 15,
                    f"Hp_2nd_{m}": 200, f"Lp_2nd_{m}": 5,
                    f"TempHi_{m}": 60, f"TempLo_{m}": -65})
    return {**row, **extra}


BASE = datetime(2026,9,29,23,59)
POLICY = WindowPolicy("Asia/Bangkok")
AS_OF = (BASE+timedelta(minutes=2)).replace(tzinfo=timezone(timedelta(hours=7)))


@pytest.mark.parametrize("context", [{"SV_1": "On"}, {"Busy_1":1, "Status_1":"ChangeValve"}, {"Valve_1":-200}])
def test_all_state_measurements_are_separate_from_legacy_eligibility(context):
    rows = [sample(BASE+timedelta(seconds=i), **context) for i in range(60)]
    new = build_observed_minutes(rows, as_of=AS_OF, policy=POLICY, modules=(1,))[0]
    old = build_completed_windows(rows, as_of=AS_OF, policy=POLICY, modules=(1,))[0]
    assert new.measured and new.features["dp2"] == 195
    assert not old.eligible and old.features is None
    assert new.feature_version != old.feature_version


@pytest.mark.parametrize("bad", ["duplicate", "gap", "nan"])
def test_measurement_quality_still_fails_closed(bad):
    rows = [sample(BASE+timedelta(seconds=i)) for i in range(60)]
    if bad == "duplicate": rows.append(rows[0])
    if bad == "gap": rows = rows[:20]+rows[35:]
    if bad == "nan": rows[5]["Hp_2nd_1"] = float("nan")
    result = build_observed_minutes(rows, as_of=AS_OF, policy=POLICY, modules=(1,))[0]
    assert not result.measured and result.features is None


def test_all_changes_within_a_minute_and_across_delivery_boundary_survive():
    rows = [sample(BASE+timedelta(seconds=i), Valve_1=i, SV_1="On" if i >= 10 else "Off") for i in range(61)]
    whole = TransitionTracker("source", "Asia/Bangkok").consume(rows)
    a = TransitionTracker("source", "Asia/Bangkok")
    first = a.consume(rows[:30])
    b = TransitionTracker("source", "Asia/Bangkok", checkpoint=a.checkpoint())
    split = first+b.consume(rows[30:])
    assert [x["event_id"] for x in whole] == [x["event_id"] for x in split]
    assert sum(x["event_type"] == "VALVE_COMMAND_CHANGED" for x in whole) == 60
    assert sum(x["event_type"] == "SV_CHANGED" for x in whole) == 1
    assert all(x["assessment"] == "UNASSESSED" for x in whole)


def test_common_raw_rejects_changed_or_unverified_source_mapping(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from apps.api.app import context_api
    monkeypatch.setattr(context_api,"get_settings",lambda:SimpleNamespace(source_timezone="Asia/Bangkok"))
    monkeypatch.setattr(context_api,"source_namespace",lambda _:"original-source")
    records=TransitionTracker("original-source","Asia/Bangkok").consume(
        [sample(BASE),sample(BASE+timedelta(seconds=1),SV_1="On")])
    for record in records:context_api.verify_event_source(record)
    monkeypatch.setattr(context_api,"source_namespace",lambda _:"replacement-source")
    for record in records:
        with pytest.raises(HTTPException) as error:context_api.verify_event_source(record)
        assert error.value.status_code==409
    unknown={**records[-1],"family":"OPERATIONAL","payload_json":'{"details":{"producer":"pm"}}'}
    with pytest.raises(HTTPException):context_api.verify_event_source(unknown)


def test_common_raw_profile_source_must_match_the_event_scope(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from apps.api.app import context_api
    from apps.api.app.unified_events import make_event
    monkeypatch.setattr(context_api,"get_settings",lambda:SimpleNamespace(source_timezone="Asia/Bangkok"))
    monkeypatch.setattr(context_api,"source_namespace",lambda _:"source")
    monkeypatch.setattr(context_api,"model_for",lambda _:dict(machine_number="MX017",module=1))
    record=make_event(source_key=["profile"],machine="MX017",module=1,occurred_at=BASE,
        timezone_name="Asia/Bangkok",event_type="PHASE_ASSESSMENT_CHANGED",family="PHASE",details={"profile_id":"frozen"})
    context_api.verify_event_source(record)
    with pytest.raises(HTTPException):context_api.verify_event_source({**record,"machine_number":"MX024"})


def test_gap_duplicate_and_machine_scope_are_not_exact_module_starts():
    rows = [sample(BASE), sample(BASE+timedelta(seconds=1)), sample(BASE+timedelta(seconds=1), Valve_1=105),
            sample(BASE+timedelta(seconds=2), Valve_1=110), sample(BASE+timedelta(seconds=10), Status="Stop", SV_1="On")]
    result = TransitionTracker("source", "Asia/Bangkok").consume(rows)
    assert sum(x["event_type"] == "DUPLICATE_SECOND" for x in result) == 1
    changes = [x for x in result if x["event_type"] == "VALVE_COMMAND_CHANGED"]
    assert len(changes) == 1
    assert not __import__("json").loads(changes[0]["payload_json"])["details"]["witness_usable"]
    compressor = [x for x in result if x["event_type"] == "COMPRESSOR_STATE_CHANGED"]
    assert len(compressor) == 1 and compressor[0]["module"] is None
    detail = __import__("json").loads(compressor[0]["payload_json"])["details"]
    assert not detail["witness_usable"] and detail["boundary"] == "GAP_BRACKETED"


def test_event_retry_rollback_and_keyset_history():
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    records = TransitionTracker("source", "Asia/Bangkok").consume(
        [sample(BASE+timedelta(seconds=i), Valve_1=i) for i in range(10)])
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            append_events(conn, records)
            raise RuntimeError("crash")
    with engine.connect() as conn:
        assert conn.execute(select(events)).all() == []
    with engine.begin() as conn:
        append_events(conn, records)
        append_events(conn, records)
    with engine.connect() as conn:
        page = list_events(conn, machine="MX017", limit=3)
        seen = page["items"]
        while page["next"]:
            page = list_events(conn, machine="MX017", limit=3, after=page["next"])
            seen.extend(page["items"])
        assert len(seen) == len(records) == len({r["event_id"] for r in seen})
        scoped=list_events(conn, machine="MX017", module=1)["items"]
        assert len(scoped)==10
        assert any(r["module"] is None for r in scoped)
