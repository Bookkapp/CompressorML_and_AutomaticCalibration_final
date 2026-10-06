from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.api.app.inference import _qualified_source_table, sync_pm_alert
from apps.api.app.repository import profile_is_approval_eligible


def test_configured_source_table_is_quoted_and_schema_bound():
    assert _qualified_source_table("ht_mock777_source", "ht9046mx_readings") == "`ht_mock777_source`.`ht9046mx_readings`"
    assert _qualified_source_table("ht_mock777_source", "ht_mock777_source.ht9046mx_readings") == "`ht_mock777_source`.`ht9046mx_readings`"
    import pytest
    with pytest.raises(ValueError):
        _qualified_source_table("ht_mock777_source", "ht9046mx_iot.ht9046mx_readings")


def test_empty_or_unverified_profile_cannot_be_approved():
    ready = {"profile_status": "READY_FOR_APPROVAL", "calibration_windows": 240,
             "calibration_days": 8, "shadow_windows": 240, "shadow_days": 3,
             "reason_codes": "[]"}
    assert profile_is_approval_eligible(ready)
    assert not profile_is_approval_eligible({**ready, "profile_status": "FLEET_PROVISIONAL"})
    assert not profile_is_approval_eligible({**ready, "calibration_windows": 0})
    assert not profile_is_approval_eligible({**ready, "shadow_days": 0})
    assert not profile_is_approval_eligible({**ready, "reason_codes": '["STATE_CONTRACT_VERSION_UNVERIFIED"]'})


class _Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, today=None, acknowledged=None):
        self.today = today
        self.acknowledged = acknowledged
        self.statements = []

    def execute(self, statement, params):
        sql = " ".join(str(statement).split())
        self.statements.append((sql, params))
        if "recorded_at >= :start" in sql:
            return _Result(self.today)
        if "suppressed_until > :now" in sql:
            return _Result(self.acknowledged)
        return _Result()


def _sync(conn, *, severity="warning", source_timezone="Asia/Bangkok"):
    now = datetime.now(ZoneInfo("Asia/Bangkok")).replace(tzinfo=None)
    with patch("apps.api.app.inference.get_settings", return_value=SimpleNamespace(source_timezone=source_timezone)):
        return sync_pm_alert(conn, 3, 5, severity, "Compressor condition", "ML evidence", now)


def test_missing_source_timezone_fails_closed():
    conn = _Connection()
    assert _sync(conn, source_timezone="") is False
    assert conn.statements == []


def test_historical_replay_cannot_emit_live_alert():
    conn = _Connection()
    old = datetime.now(ZoneInfo("Asia/Bangkok")).replace(tzinfo=None) - timedelta(days=1)
    with patch("apps.api.app.inference.get_settings", return_value=SimpleNamespace(source_timezone="Asia/Bangkok")):
        assert sync_pm_alert(conn, 3, 5, "warning", "Old result", "Historical replay", old) is False
    assert conn.statements == []


def test_same_issue_once_per_day_without_deleting_history():
    conn = _Connection(today={"severity": "warning"})
    assert _sync(conn) is False
    assert not any("DELETE FROM" in sql for sql, _ in conn.statements)


def test_acknowledged_issue_is_suppressed():
    conn = _Connection(acknowledged={"severity": "critical"})
    assert _sync(conn) is False
    assert not any("INSERT INTO" in sql for sql, _ in conn.statements)


def test_escalation_can_emit_and_keeps_prior_alert():
    conn = _Connection(today={"severity": "warning"}, acknowledged={"severity": "warning"})
    assert _sync(conn, severity="critical") is True
    assert sum("INSERT INTO" in sql for sql, _ in conn.statements) == 1
    assert not any("DELETE FROM" in sql for sql, _ in conn.statements)
