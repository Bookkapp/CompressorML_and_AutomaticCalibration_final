"""Append-only Compressor event ledger with deterministic producer identities.

Observed transitions are recorded before eligibility/scoring. A source gap or
duplicate is evidence of uncertainty, not a manufactured exact transition.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import BigInteger, Column, Index, Integer, MetaData, String, Table, Text, and_, or_, select
from .qualified_windows import _safe_number

EVENT_VERSION = "compressor-unified-events-v1"
metadata = MetaData()

# Allocated under one row lock in the producer transaction, not AUTO_INCREMENT:
# readers may advance through seq without skipping a later committed lower ID.
dashboard_sequence = Table("ht9046mx_dashboard_sequence", metadata,
    Column("id", Integer, primary_key=True), Column("last_seq", BigInteger, nullable=False))
dashboard_identity = Table("ht9046mx_dashboard_identity", metadata,
    Column("id", Integer, primary_key=True), Column("stream_id", String(64), nullable=False))
dashboard_feed = Table("ht9046mx_dashboard_feed", metadata,
    Column("seq", BigInteger, primary_key=True), Column("event_id", String(64), nullable=False, unique=True),
    Column("kind", String(16), nullable=False), Column("machine_number", String(64), nullable=False),
    Column("module", Integer), Column("occurred_at", String(32), nullable=False),
    Column("payload_json", Text, nullable=False))
dashboard_latest = Table("ht9046mx_dashboard_latest", metadata,
    Column("machine_number", String(64), primary_key=True), Column("module", Integer, primary_key=True),
    Column("occurred_at", String(32), nullable=False), Column("exported_at", String(32), nullable=False),
    Column("state_key", String(64), nullable=False), Column("payload_json", Text, nullable=False))
events = Table("ht9046mx_events", metadata,
    Column("event_id", String(64), primary_key=True),
    Column("source_event_key", String(64), nullable=False),
    Column("machine_number", String(64), nullable=False),
    Column("module", Integer),
    Column("occurred_at", String(32), nullable=False),
    Column("source_timezone", String(64), nullable=False),
    Column("recorded_at", String(32), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("family", String(32), nullable=False),
    Column("assessment", String(32), nullable=False),
    Column("mode", String(32), nullable=False),
    Column("correlation_id", String(64)),
    Column("run_id", String(64)),
    Column("policy_version", String(64), nullable=False),
    Column("payload_json", Text, nullable=False))
Index("idx_events_machine_time", events.c.machine_number, events.c.occurred_at, events.c.event_id)
Index("idx_events_module_time", events.c.machine_number, events.c.module, events.c.occurred_at, events.c.event_id)
Index("idx_events_family_time", events.c.family, events.c.occurred_at, events.c.event_id)
Index("idx_events_correlation", events.c.correlation_id, events.c.occurred_at)


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, default=lambda x: x.isoformat()
                      if isinstance(x, datetime) else str(x), separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def make_event(*, source_key, machine, module, occurred_at, timezone_name, event_type, family,
               details, mode="HISTORICAL", assessment="UNASSESSED", correlation_id=None,
               run_id=None, policy_version=EVENT_VERSION, recorded_at=None):
    if mode not in {"HISTORICAL", "SHADOW", "LIVE", "LOCAL_REHEARSAL", "DETECTOR_SHADOW", "DETECTOR_LIVE"}:
        raise ValueError("explicit event mode required")
    if module is not None and module not in range(1, 9):
        raise ValueError("module must be 1..8 or machine scope")
    ZoneInfo(timezone_name)
    if isinstance(occurred_at, datetime):
        if occurred_at.tzinfo:
            occurred_at = occurred_at.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
        occurred_at = occurred_at.isoformat()
    stamp = datetime.fromisoformat(occurred_at)
    if stamp.tzinfo:
        raise ValueError("occurrence must use declared source-local clock")
    payload = {"schema_version": 1, "details": details,
               "occurrence_clock": "SOURCE_LOCAL_DECLARED", "claim": "EVENT_EVIDENCE_NOT_FAULT_DIAGNOSIS"}
    source_id = fingerprint(source_key)
    identity = fingerprint({"source": source_id, "mode": mode, "policy": policy_version,
                            "machine": machine, "module": module, "at": occurred_at,
                            "family": family, "assessment": assessment, "run": run_id,
                            "type": event_type, "payload": payload, "correlation": correlation_id})
    return dict(event_id=identity, source_event_key=source_id, machine_number=machine,
                module=module, occurred_at=occurred_at, source_timezone=timezone_name,
                recorded_at=(recorded_at or datetime.now(timezone.utc)).isoformat(),
                event_type=event_type, family=family, assessment=assessment, mode=mode,
                correlation_id=correlation_id, run_id=run_id, policy_version=policy_version,
                payload_json=encode(payload))


def append_events(conn, rows):
    """Caller controls transaction/checkpoint. Retry never updates old evidence."""
    from .dashboard_export import publish
    publish(conn, [{"event_id":r["event_id"], "kind":"EVENT", "machine_number":r["machine_number"],
                   "module":r["module"], "occurred_at":r["occurred_at"], "payload":r} for r in rows])
    for offset in range(0, len(rows), 500):
        batch = rows[offset:offset+500]
        if conn.dialect.name == "mysql":
            from sqlalchemy.dialects.mysql import insert
            stmt = insert(events).values(batch)
            conn.execute(stmt.on_duplicate_key_update(event_id=events.c.event_id))
        elif conn.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
            conn.execute(insert(events).values(batch).on_conflict_do_nothing(index_elements=["event_id"]))
        else:
            raise ValueError("event store supports mysql/sqlite")


def list_events(conn, *, machine=None, module=None, start=None, end=None, family=None,
                mode=None, correlation=None, assessment=None,event_type=None,after=None, limit=100):
    if not 1 <= limit <= 500:
        raise ValueError("event page limit must be 1..500")
    query = select(events)
    for column, value in ((events.c.machine_number, machine),
                           (events.c.family, family), (events.c.mode, mode),
                           (events.c.correlation_id, correlation),
                           (events.c.assessment,assessment),(events.c.event_type,event_type)):
        if value is not None:
            query = query.where(column == value)
    if module is not None:
        # Machine-wide controls also affect an investigation of one module.
        query = query.where(or_(events.c.module == module, events.c.module.is_(None)))
    if start:
        query = query.where(events.c.occurred_at >= start)
    if end:
        query = query.where(events.c.occurred_at < end)
    if after:
        query = query.where(or_(events.c.occurred_at < after[0], and_(
            events.c.occurred_at == after[0], events.c.event_id < after[1])))
    records = [dict(r) for r in conn.execute(query.order_by(events.c.occurred_at.desc(),
                events.c.event_id.desc()).limit(limit+1)).mappings()]
    more = len(records) > limit
    records = records[:limit]
    for row in records:
        row["payload"] = json.loads(row.pop("payload_json"))
    return {"items": records, "next": [records[-1]["occurred_at"], records[-1]["event_id"]]
            if more else None}


def _control(value, *, numeric=False):
    if numeric:
        return _safe_number(value)
    return str(value).strip() if value is not None else None


class TransitionTracker:
    """Consume complete observed-second groups, including ineligible states.

    checkpoint preserves the last unambiguous observation across days/batches.
    Duplicate seconds invalidate that witness, irrespective of duplicate content.
    """
    def __init__(self, namespace, timezone_name, *, modules=range(1, 9), mode="HISTORICAL", checkpoint=None):
        self.namespace, self.timezone_name, self.mode = namespace, timezone_name, mode
        self.modules = tuple(modules)
        if not self.modules or len(set(self.modules)) != len(self.modules) or any(m not in range(1,9) for m in self.modules):
            raise ValueError("unique modules 1..8 required")
        self.previous = json.loads(encode(checkpoint or {}))

    def checkpoint(self):
        return json.loads(encode(self.previous))

    def consume(self, rows):
        groups = defaultdict(list)
        for row in rows:
            stamp = row["recorded_at"]
            if not isinstance(stamp, datetime) or stamp.tzinfo:
                raise ValueError("tracker requires source-local DATETIME")
            groups[str(row["machine_number"]), stamp.replace(microsecond=0)].append(row)
        result = []
        for (machine, second), samples in sorted(groups.items()):
            stamp = samples[0]["recorded_at"]
            prev = self.previous.get(machine)
            if prev and stamp <= datetime.fromisoformat(prev["at"]):
                raise ValueError("out-of-order transition input requires replay")
            def add(kind, family, module, details, key_extra=None):
                result.append(make_event(source_key=[self.namespace, machine, module, stamp, kind, key_extra],
                    machine=machine, module=module, occurred_at=stamp, timezone_name=self.timezone_name,
                    event_type=kind, family=family, mode=self.mode, details=details,
                    correlation_id=fingerprint([self.namespace, machine, stamp])))
            if len(samples) != 1:
                add("DUPLICATE_SECOND", "DATA_QUALITY", None,
                    {"samples": len(samples), "second": second.isoformat(),
                     "witness_usable": False, "observation_hashes": sorted(fingerprint(r) for r in samples)})
                self.previous[machine] = {"at": max(r["recorded_at"] for r in samples).isoformat(), "values": None}
                continue
            row = samples[0]
            values = {"Status": _control(row.get("Status"))}
            for module in self.modules:
                for field in ("Status", "Busy", "SV", "Valve"):
                    col = f"{field}_{module}"
                    values[col] = _control(row.get(col), numeric=field == "Valve")
            physical = {str(m): {field: _safe_number(row.get(f"{field}_{m}")) for field in
                       ("Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "TempHi", "TempLo")} for m in self.modules}
            if not prev or prev["values"] is None:
                add("OBSERVATION_START" if not prev else "OBSERVATION_RESUMED", "DATA_QUALITY", None,
                    {"state": values, "boundary": "LEFT_CENSORED" if not prev else "DUPLICATE_INTERRUPTION"})
            else:
                elapsed = (stamp-datetime.fromisoformat(prev["at"])).total_seconds()
                exact = elapsed == 1
                if not exact:
                    add("SOURCE_GAP", "DATA_QUALITY", None,
                        {"before_at": prev["at"], "after_at": stamp.isoformat(), "elapsed_seconds": elapsed,
                         "before": prev["values"], "after": values, "witness_usable": False})
                for col, value in values.items():
                    before = prev["values"].get(col)
                    if before == value:
                        continue
                    field, module = (col.rsplit("_", 1)[0], int(col.rsplit("_", 1)[1])) if "_" in col else (col, None)
                    kind = {"Valve": "VALVE_COMMAND_CHANGED", "SV": "SV_CHANGED", "Busy": "BUSY_CHANGED",
                            "Status": "MODULE_STATE_CHANGED" if module else "COMPRESSOR_STATE_CHANGED"}[field]
                    details = {"field": col, "before": before, "after": value, "before_at": prev["at"],
                               "after_at": stamp.isoformat(), "boundary": "OBSERVED_ADJACENT_SECONDS" if exact else "GAP_BRACKETED",
                               "witness_usable": exact and before is not None and value is not None,
                               "physical_after": physical.get(str(module)) if module else None}
                    add(kind, "CONTROL", module, details, [prev["at"], before, value])
            self.previous[machine] = {"at": stamp.isoformat(), "values": values}
        return result
