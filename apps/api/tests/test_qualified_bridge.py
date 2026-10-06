"""Isolated SQLite transport fixtures; no real Profile approval or Server access."""
from datetime import timedelta
import json

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, select

from apps.api.app.qualified_bridge import DashboardBridge, episodes, windows, receipts
from apps.api.app.qualified_detector import DurableDetector, outbox
from apps.api.app.qualified_windows import WindowPolicy
from apps.api.tests.test_qualified_detector import profiles, raw
from apps.api.tests.test_qualified_stream import clock


@pytest.fixture
def pair():
    analytics, pm = create_engine("sqlite://"), create_engine("sqlite://")
    m = MetaData()
    devices = Table("pm_devices", m, Column("id", Integer, primary_key=True),
        Column("machine_code", String), Column("device_uid", String))
    modules = Table("pm_modules", m, Column("id", Integer, primary_key=True),
        Column("device_id", Integer), Column("module_code", String))
    alerts = Table("pm_alerts", m, Column("id", Integer, primary_key=True),
        Column("device_id", Integer), Column("module_id", Integer), Column("issue_key", String),
        Column("severity", String), Column("title", String), Column("message", Text),
        Column("acknowledged", Integer), Column("recorded_at", DateTime), Column("suppressed_until", DateTime))
    m.create_all(pm)
    with pm.begin() as c:
        c.execute(devices.insert().values(id=10, machine_code="MX080", device_uid="HT9046MX-080"))
        c.execute(modules.insert().values(id=60, device_id=10, module_code="compressor-m6"))
    detector = DurableDetector(analytics, WindowPolicy("UTC", late_arrival_seconds=30), mode="DETECTOR_LIVE")
    detector.create_tables()
    bridge = DashboardBridge(analytics, pm, alerts_enabled=True)
    bridge.create_tables()
    return detector, bridge, alerts


def test_fixture_active_to_episode_pm_alert_and_crash_safe_receipt(pair):
    detector, bridge, alerts = pair
    p = profiles(); run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(300), shifted=True), as_of=clock(300), profiles=p)
    def crash():
        raise RuntimeError("after PM commit")
    with pytest.raises(RuntimeError):
        bridge.deliver(now=clock(300), before_ack=crash)
    bridge.deliver(now=clock(300))
    bridge.deliver(now=clock(300))
    with bridge.pm.connect() as c:
        assert len(c.execute(select(windows)).all()) == 4
        assert len(c.execute(select(alerts)).all()) == 1
        episode = c.execute(select(episodes)).mappings().one()
        assert episode["pm_alert_id"] == 1
        assert "cause requires inspection" in c.execute(select(alerts.c.message)).scalar_one()
    with detector.engine.connect() as c:
        assert not c.execute(select(outbox).where(outbox.c.delivered == 0)).first()


def test_shadow_historical_and_recovered_backlog_do_not_alert(pair):
    detector, bridge, alerts = pair
    p = profiles(); run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(300), shifted=True), as_of=clock(300), profiles=p)
    # Recovery is delivered first; earlier OPEN updates must not notify afterward.
    detector.cycle(run, raw(range(300, 660)), as_of=clock(690), profiles=p)
    bridge.deliver(now=clock(690))
    with bridge.pm.connect() as c:
        assert not c.execute(select(alerts)).first()
        item = json.loads(c.execute(select(episodes.c.payload_json)).scalar_one())
        assert item["data"]["status"] == "RECOVERED"
    shadow = DurableDetector(detector.engine, detector.policy, mode="DETECTOR_SHADOW")
    shadow_run = shadow.initialize("MX080", (6,), p)
    shadow.cycle(shadow_run, raw(range(300), shifted=True), as_of=clock(300), profiles=p)
    bridge.deliver(now=clock(300))
    with bridge.pm.connect() as c:
        assert not c.execute(select(alerts)).first()


def test_stale_episode_stored_without_live_notification(pair):
    detector, bridge, alerts = pair
    p = profiles(); run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(300), shifted=True), as_of=clock(300), profiles=p)
    bridge.deliver(now=clock(300)+timedelta(days=1))
    with bridge.pm.connect() as c:
        assert not c.execute(select(alerts)).first()
        assert c.execute(select(episodes.c.notification_status)).scalar_one() == "HISTORICAL_OR_FUTURE_EVIDENCE"
def test_profile_supersession_prevents_pending_old_context_alert(pair):
    detector, bridge, alerts = pair
    p = profiles()
    run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(300), shifted=True), as_of=clock(300), profiles=p)
    detector.set_current("MX080")
    bridge.deliver(now=clock(300))
    with bridge.pm.connect() as c:
        assert not c.execute(select(alerts)).first()
        result = c.execute(select(episodes.c.notification_status)).scalar_one()
        assert result == "SUPERSEDED_OR_UNAVAILABLE_PROFILE_CONTEXT"
