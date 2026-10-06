"""Operation-owned derived-evidence bridge; Dashboard owns all technician work.

Analytics outbox and PM receipt use at-least-once transport/exact event identity.
PM transaction commits before analytics acknowledgement. A crash between them
retries the same receipt, not the same alert. Historical/shadow data never alert.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, Text, and_, or_, select, update

from .qualified_detector import outbox, current
from .qualified_persistence import canonical
from .inference import get_machine_candidates


meta = MetaData()
receipts = Table("pm_detector_delivery_receipts", meta,
    Column("event_id", String(64), primary_key=True),
    Column("received_at", String(32), nullable=False))
windows = Table("pm_detector_windows", meta,
    Column("run_id", String(64), primary_key=True),
    Column("machine_number", String(64), primary_key=True),
    Column("module", Integer, primary_key=True),
    Column("window_start", String(32), primary_key=True),
    Column("payload_json", Text, nullable=False))
episodes = Table("pm_detector_episodes", meta,
    Column("run_id", String(64), primary_key=True),
    Column("episode_id", String(36), primary_key=True),
    Column("pm_alert_id", Integer),
    Column("notification_status", String(64), nullable=False),
    Column("payload_json", Text, nullable=False))
data_issues = Table("pm_detector_data_issues", meta,
    Column("event_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("machine_number", String(64), nullable=False),
    Column("recorded_at", String(32), nullable=False),
    Column("payload_json", Text, nullable=False))
Index("idx_pm_detector_window_time", windows.c.machine_number, windows.c.module, windows.c.window_start)
Index("idx_pm_detector_episode_alert", episodes.c.pm_alert_id)
Index("idx_pm_detector_issue_time", data_issues.c.run_id, data_issues.c.machine_number, data_issues.c.recorded_at)


class DashboardBridge:
    def __init__(self, analytics_engine, pm_engine, *, alerts_enabled=False, critical_ratio=2.,
                 fresh_seconds=900):
        if critical_ratio <= 1 or fresh_seconds < 60:
            raise ValueError("invalid alert policy")
        self.analytics, self.pm = analytics_engine, pm_engine
        self.alerts_enabled, self.critical_ratio, self.fresh_seconds = alerts_enabled, critical_ratio, fresh_seconds

    def create_tables(self):
        # Additive derived metadata only; no source or Profile tables are changed.
        meta.create_all(self.pm)

    def _alert(self, conn, payload, item, now):
        if not self.alerts_enabled or payload["mode"] != "DETECTOR_LIVE":
            return None, "SHADOW_OR_DISABLED"
        with self.analytics.connect() as source:
            active_run = source.execute(select(current.c.run_id).where(
                current.c.machine_number == item["machine_number"])).scalar_one_or_none()
        if active_run != payload["run_id"]:
            return None, "SUPERSEDED_OR_UNAVAILABLE_PROFILE_CONTEXT"
        if item["status"] not in {"OPEN", "RECOVERING"}:
            return None, "NO_NEW_PERSISTENT_DEVIATION"
        observed = datetime.fromisoformat(item["last_deviation_at"])
        observed = observed.replace(tzinfo=ZoneInfo(payload["source_timezone"]))
        if not -120 <= (now.astimezone(timezone.utc)-observed.astimezone(timezone.utc)).total_seconds() <= self.fresh_seconds:
            return None, "HISTORICAL_OR_FUTURE_EVIDENCE"
        reflected = MetaData()
        devices = Table("pm_devices", reflected, autoload_with=conn)
        modules = Table("pm_modules", reflected, autoload_with=conn)
        alerts = Table("pm_alerts", reflected, autoload_with=conn)
        aliases = get_machine_candidates(item["machine_number"])
        matches = conn.execute(select(devices.c.id).where(or_(devices.c.machine_code.in_(aliases),
                                               devices.c.device_uid.in_(aliases)))).scalars().all()
        if len(matches) != 1:
            raise ValueError("PM_DEVICE_IDENTITY_NOT_UNIQUE_OR_NOT_DISCOVERED")
        device_id = matches[0]
        module_ids = conn.execute(select(modules.c.id).where(modules.c.device_id == device_id,
            modules.c.module_code == f"compressor-m{item['module']}").with_for_update()).scalars().all()
        if len(module_ids) != 1:
            raise ValueError("PM_MODULE_IDENTITY_NOT_UNIQUE_OR_NOT_DISCOVERED")
        module_id = module_ids[0]
        severity = "critical" if item["peak_score_ratio"] >= self.critical_ratio else "warning"
        ranks = dict(info=0, warning=1, critical=2)
        local_now = now.astimezone(ZoneInfo("Asia/Bangkok")).replace(tzinfo=None)
        common = (alerts.c.device_id == device_id, alerts.c.module_id == module_id,
                  alerts.c.issue_key.in_(["compressor_ml_condition", "diagnostic_alert"]))
        day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        same_day = conn.execute(select(alerts).where(*common, alerts.c.recorded_at >= day,
            alerts.c.recorded_at < day+timedelta(days=1)).order_by(alerts.c.recorded_at.desc(), alerts.c.id.desc())
            .limit(1).with_for_update()).mappings().first()
        acknowledged = conn.execute(select(alerts).where(*common, alerts.c.acknowledged == 1,
            alerts.c.suppressed_until > local_now).order_by(alerts.c.id.desc()).limit(1).with_for_update()).mappings().first()
        for prior, reason in ((same_day, "DAILY_LIMIT"), (acknowledged, "ACKNOWLEDGED_SUPPRESSION")):
            if prior and ranks[severity] <= ranks.get(str(prior["severity"]).lower(), 0):
                return int(prior["id"]), reason
        message = (f"{item['machine_number']} M{item['module']} · score {item['peak_score']:.2f} / "
            f"threshold {item['threshold']:.2f} · profile {item['profile_version']} · "
            f"observed from {item['first_deviation_at']} ({payload['source_timezone']}). "
            "Persistent telemetry deviation; cause requires inspection.")
        result = conn.execute(alerts.insert().values(device_id=device_id, module_id=module_id,
            issue_key="compressor_ml_condition", severity=severity, title="Persistent compressor deviation",
            message=message, acknowledged=0, recorded_at=local_now))
        return int(result.inserted_primary_key[0]), "ALERT_CREATED"

    def deliver(self, *, now=None, limit=500, before_ack=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or not 1 <= limit <= 10000:
            raise ValueError("aware clock and bounded batch required")
        with self.analytics.connect() as conn:
            events = conn.execute(select(outbox).where(outbox.c.delivered == 0)
                .order_by(outbox.c.revision.desc(), outbox.c.run_id, outbox.c.event_id).limit(limit)).mappings().all()
        delivered = 0
        for event in events:
            payload = json.loads(event["payload_json"])
            item = payload["data"]
            with self.pm.begin() as conn:
                exists = conn.execute(select(receipts).where(receipts.c.event_id == event["event_id"])
                                      .with_for_update()).first()
                if not exists:
                    if event["kind"] == "WINDOW":
                        w = item["window"]
                        utc_start = datetime.fromisoformat(w["window_start"]).replace(
                            tzinfo=ZoneInfo(payload["source_timezone"])).astimezone(timezone.utc).isoformat()
                        conn.execute(windows.insert().values(run_id=payload["run_id"],
                            machine_number=w["machine_number"], module=w["module"],
                            window_start=utc_start, payload_json=canonical(payload)))
                    elif event["kind"] == "EPISODE":
                        key = and_(episodes.c.run_id == payload["run_id"], episodes.c.episode_id == item["episode_id"])
                        old = conn.execute(select(episodes).where(key).with_for_update()).mappings().first()
                        # Keep newest source observation even when outbox event ordering is arbitrary.
                        old_item = json.loads(old["payload_json"])["data"] if old else None
                        if not old_item or json.loads(old["payload_json"]).get("revision", -1) < payload["revision"]:
                            alert_id, status = self._alert(conn, payload, item, now)
                            values = dict(pm_alert_id=alert_id or (old["pm_alert_id"] if old else None),
                                          notification_status=status, payload_json=canonical(payload))
                            if old:
                                conn.execute(episodes.update().where(key).values(**values))
                            else:
                                conn.execute(episodes.insert().values(run_id=payload["run_id"],
                                    episode_id=item["episode_id"], **values))
                    elif event["kind"] == "DATA_ISSUE":
                        conn.execute(data_issues.insert().values(event_id=event["event_id"], run_id=payload["run_id"],
                            machine_number=item["machine_number"], recorded_at=datetime.fromisoformat(item["recorded_at"])
                                .replace(tzinfo=ZoneInfo(payload["source_timezone"])).astimezone(timezone.utc).isoformat(),
                            payload_json=canonical(payload)))
                    else:
                        raise ValueError("unknown bridge event kind")
                    conn.execute(receipts.insert().values(event_id=event["event_id"], received_at=now.isoformat()))
            if before_ack:
                before_ack()  # crash test: PM already committed, analytics event remains pending
            # Read the committed receipt/status again on retry. This records the
            # actual delivery time and PM identity, including a crash after PM commit.
            notification=None
            if event["kind"]=="EPISODE":
                with self.pm.connect() as target:
                    received=target.execute(select(receipts.c.received_at).where(receipts.c.event_id==event["event_id"])).scalar_one()
                    reflected=target.execute(select(episodes).where(episodes.c.run_id==payload["run_id"],episodes.c.episode_id==item["episode_id"])).mappings().one()
                from .unified_events import make_event
                notification=make_event(source_key=["pm-delivery",event["event_id"]],machine=item["machine_number"],module=item["module"],
                    occurred_at=datetime.fromisoformat(received),timezone_name=payload["source_timezone"],
                    event_type="NOTIFICATION_DELIVERY_RECORDED",family="NOTIFICATION",mode=payload["mode"],
                    assessment=reflected["notification_status"][:32],correlation_id=item["episode_id"],run_id=payload["run_id"],
                    details={"episode_id":item["episode_id"],"outbox_event_id":event["event_id"],
                        "pm_alert_id":reflected["pm_alert_id"],"pm_schema":self.pm.url.database or "isolated-sqlite-fixture",
                        "delivery_status":reflected["notification_status"],"received_at":received,
                        "original_observation_at":item["last_observed_at"],"clock":"PM_DELIVERY_RECEIPT_UTC"})
            with self.analytics.begin() as conn:
                if notification:
                    from .unified_events import append_events
                    append_events(conn,[notification])
                conn.execute(outbox.update().where(outbox.c.event_id == event["event_id"]).values(delivered=1))
            delivered += 1
        return {"delivered_events": delivered, "alerts_enabled": self.alerts_enabled}


def run_configured_bridge(settings, *, migrate=False, migrate_only=False):
    if not settings.detector_bridge_enabled and not migrate_only:
        return {"status": "BRIDGE_DISABLED", "database_writes": 0}
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from .db import get_engine
    if not all((settings.detector_pm_db_host, settings.detector_pm_db_user, settings.detector_pm_db_password)):
        raise ValueError("explicit PM metadata connection required")
    pm = create_engine(URL.create("mysql+pymysql", host=settings.detector_pm_db_host,
        port=settings.detector_pm_db_port, username=settings.detector_pm_db_user,
        password=settings.detector_pm_db_password, database=settings.detector_pm_db_name), pool_pre_ping=True)
    try:
        bridge = DashboardBridge(get_engine(), pm, alerts_enabled=settings.detector_alerts_enabled,
                                 critical_ratio=settings.detector_critical_score_ratio)
        if migrate or migrate_only:
            bridge.create_tables()
        if migrate_only:
            return {"status":"PM_EVIDENCE_TABLES_CREATED","events_delivered":0,"alerts_created":0}
        return bridge.deliver()
    finally:
        pm.dispose()


def main():
    import argparse
    from .config import get_settings
    parser = argparse.ArgumentParser(description="Deliver derived detector evidence to Dashboard metadata")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_remote and any(host not in {"localhost", "127.0.0.1", "::1"}
            for host in (settings.analytics_db_host, settings.detector_pm_db_host)):
        parser.error("local command requires localhost analytics and PM metadata")
    print(json.dumps(run_configured_bridge(settings, migrate=args.migrate,migrate_only=args.migrate_only), indent=2))


if __name__ == "__main__":
    main()
