"""Coverage inventory is not profile readiness or a normal-label selector."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

from fastapi.testclient import TestClient
import pytest

from apps.api.app import reference_availability as availability
from apps.api.app.config import Settings
from apps.api.app.main import app
from apps.api.app.reference_review import ReferencePreviewRequest


def settings():
    return Settings(app_mode="live",source_timezone="Asia/Bangkok",profile_shadow_days=3,
        profile_min_calibration_days=3,profile_min_calibration_windows=50,profile_min_shadow_windows=50,
        qualified_1m_late_arrival_seconds=0)


def payload(**extra):
    return ReferencePreviewRequest(machine_number="MX080",module=6,history_days=7,
        idempotency_key="availability-test",**extra)


def daily(start, days):
    return [{"date":(start+timedelta(days=i)).date().isoformat(),"raw_rows":100,
        "module_rows":100,"observed_minutes":100,"module_minutes":100} for i in range(days)]


def summarize(rows, latest=datetime(2026,10,1,12)):
    return availability.summarize_availability(payload(),latest,rows,settings(),now=datetime(2026,10,2,tzinfo=timezone.utc))


def test_latest_sparse_row_does_not_hide_recent_gap():
    rows=daily(datetime(2026,9,10),10)+daily(datetime(2026,10,1),1)
    value=summarize(rows)
    assert value["default_period"]["shadow_observed_days"] == 0
    assert value["default_period"]["shadow_raw_days"] == 0
    assert value["default_period"]["shadow_no_log_dates"] == ["2026-09-28","2026-09-29","2026-09-30"]
    assert value["default_period"]["shadow_missing_sensor_dates"] == []
    assert value["default_period"]["shadow_missing_dates"] == ["2026-09-28","2026-09-29","2026-09-30"]
    assert value["suggested_period"]["shadow_end"] == "2026-09-20"
    assert value["suggested_period"]["backtrack_days"] == 11
    assert value["source_latest"] == "2026-10-01T12:00:00"  # no silent rewind


def test_shadow_must_be_adjacent_calendar_days_not_last_three_observed_dates():
    rows=daily(datetime(2026,9,21),7)+daily(datetime(2026,9,28),3)
    rows=[r for r in rows if r["date"] != "2026-09-29"]
    value=summarize(rows)
    assert value["default_period"]["shadow_observed_days"] == 2
    assert value["suggested_period"]["shadow_end"] == "2026-09-29"
    assert value["suggested_period"]["shadow_start"] == "2026-09-26"


def test_full_closed_block_prefers_latest_and_keeps_latest_day_out():
    value=summarize(daily(datetime(2026,9,21),11))
    assert value["suggested_period"]["backtrack_days"] == 0
    assert value["suggested_period"]["reference_end"] == "2026-09-28"
    assert value["daily"][-1]["complete_day"] is False


def test_module_missing_sensors_not_counted_as_data_for_suggestion():
    rows=daily(datetime(2026,9,21),11)
    for r in rows: r.update(module_rows=0,module_minutes=0)
    value=summarize(rows)
    assert value["suggested_period"] is None and value["module_latest_date"] is None
    assert value["default_period"]["shadow_observed_days"] == 0
    assert value["default_period"]["shadow_raw_days"] == 3
    assert value["default_period"]["shadow_no_log_dates"] == []
    assert value["default_period"]["shadow_missing_sensor_dates"] == ["2026-09-28","2026-09-29","2026-09-30"]


def test_enough_shadow_without_reference_does_not_offer_ready_period():
    assert summarize(daily(datetime(2026,9,28),3))["suggested_period"] is None


def test_empty_days_are_zero_and_inventory_bounds_are_explicit():
    value=summarize([])
    assert len(value["daily"]) == 94 and value["checked_start"] == "2026-06-30"
    assert value["suggested_period"] is None
    assert all(r["raw_rows"]==0 for r in value["daily"])


def test_near_midnight_grace_is_applied_to_inventory():
    value=availability.summarize_availability(payload(),datetime(2026,10,1,17,0,10,tzinfo=timezone.utc),[],
        settings().model_copy(update={"qualified_1m_late_arrival_seconds":30}))
    assert value["latest_complete_end"] == "2026-10-01"
    assert value["source_latest"] == "2026-10-02T00:00:10"


def test_no_source_is_read_only_explicit_empty_response(monkeypatch):
    monkeypatch.setattr(availability,"_latest_source_time",lambda *a:None)
    def no_db(): raise AssertionError("No extra source scan when source is empty")
    monkeypatch.setattr(availability,"source_connection",no_db)
    value=availability.source_availability(settings(),machine_number="MX999",module=6)
    assert value["source_latest"] is None and value["reason"] == "NO_SOURCE_DATA"


def test_source_age_is_labeled_separately_from_period_availability():
    assert summarize([])["source_age_days"] == pytest.approx(19/24)  # UTC midnight = Bangkok 07:00


def test_inventory_api_validates_scope_and_does_not_need_job_storage(monkeypatch):
    from apps.api.app import main
    monkeypatch.setattr(main,"is_demo",lambda:False)
    calls=[]
    monkeypatch.setattr(main,"source_availability",lambda *a,**k:calls.append(k) or {"source_latest":None})
    client=TestClient(app)
    assert client.get("/api/v1/calibration/reference/availability?machine_number=MX080&module=6").status_code == 200
    assert calls == [{"machine_number":"MX080","module":6,"history_days":28}]
    assert client.get("/api/v1/calibration/reference/availability?machine_number=MX080&module=9").status_code == 422
    assert client.get("/api/v1/calibration/reference/availability?machine_number=MX080&module=6&history_days=91").status_code == 422
    monkeypatch.setattr(main,"is_demo",lambda:True)
    assert client.get("/api/v1/calibration/reference/availability?machine_number=MX080&module=6").status_code == 409


def test_daily_sql_bounds_aliases_nulls_duplicates_and_inclusive_latest(monkeypatch):
    latest = datetime(2026,10,1,12)
    # Same source minute may have duplicate seconds and incomplete sensor rows.
    samples = [(datetime(2026,9,30,23,59),True), (datetime(2026,9,30,23,59),True),
        (datetime(2026,9,30,23,59,1),False), (latest,True), (latest+timedelta(seconds=1),True)]
    calls=[]; connections=[]
    class Result:
        def __init__(self,row):self.row=row
        def mappings(self):return self
        def one(self):return self.row
    class Conn:
        def execute(self,query,params):
            sql=str(query)
            assert "HOUR(" in sql and "GROUP BY" not in sql and "COALESCE" in sql
            assert params["day_end"]-params["start"]==timedelta(days=1)
            assert params["end"]==latest and "017" in params["machines"]
            calls.append(params)
            rows=[(t,p) for t,p in samples if params["start"]<=t<params["day_end"] and t<=params["end"]]
            return Result({"raw_rows":len(rows),"module_rows":sum(p for _,p in rows),
                "observed_minutes":len({t.replace(second=0) for t,_ in rows}),
                "module_minutes":len({t.replace(second=0) for t,p in rows if p})})
    @contextmanager
    def conn():
        connections.append(True);yield Conn()
    monkeypatch.setattr(availability,"_latest_source_time",lambda *a:latest)
    monkeypatch.setattr(availability,"source_connection",conn)
    cfg=settings().model_copy(update={"source_db_name":"ht9046mx_iot","source_table":"ht9046mx_readings"})
    value=availability.source_availability(cfg,machine_number="017",module=6)
    assert len(calls)==94 and connections==[True]
    by_date={r["date"]:r for r in value["daily"]}
    assert by_date["2026-09-30"]["raw_rows"]==3
    assert by_date["2026-09-30"]["module_rows"]==2
    assert by_date["2026-09-30"]["observed_minutes"]==1
    assert by_date["2026-09-30"]["module_minutes"]==1
    assert by_date["2026-10-01"]["raw_rows"]==1
    assert not by_date["2026-10-01"]["complete_day"]
    assert by_date["2026-07-01"]["raw_rows"]==0
