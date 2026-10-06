"""Shared all-module daily measurements and observed events, source SELECT-only.

Events are flushed in bounded transactions during intake. The completed-day
receipt is published only after its events and all eight measurement snapshots
are durable. Interrupted fills are safe to retry using deterministic event IDs.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, LargeBinary, MetaData, String, Table, select, delete
from sqlalchemy.dialects.mysql import MEDIUMBLOB

from .observed_context import VERSION, ObservedMinute, build_observed_minutes
from .qualified_calibration import load_observed_one_minute_windows, policy_from_settings
from .qualified_cache import fill_lock, source_revision, TTL
from .unified_events import TransitionTracker, append_events, fingerprint

metadata = MetaData()
days = Table("ht9046mx_observed_day", metadata,
    Column("day_key", String(64), primary_key=True),
    Column("module", Integer, primary_key=True),
    Column("machine_number", String(64), nullable=False),
    Column("source_day", String(10), nullable=False),
    Column("checked_at", String(32), nullable=False),
    Column("source_revision", String(96), nullable=False),
    Column("payload", LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), nullable=False))


def source_namespace(settings):
    names = ("source_db_host", "source_db_name", "source_table", "source_machine_column",
             "source_timestamp_column", "source_global_status_column", "source_timezone",
             "source_hp1_template", "source_lp1_template", "source_hp2_template", "source_lp2_template",
             "source_valve_template", "source_temp_high_template", "source_temp_low_template",
             "source_module_status_template", "source_busy_template", "source_sv_template")
    return fingerprint({name: getattr(settings, name) for name in names})


def day_key(settings, machine, day):
    return fingerprint([source_namespace(settings), machine, day.isoformat(), VERSION,
                        asdict(policy_from_settings(settings))])


def pack(value):
    return gzip.compress(json.dumps(value, default=lambda x:x.isoformat(), allow_nan=False,
                                  separators=(",", ":")).encode(), compresslevel=1)


def unpack(value):
    return json.loads(gzip.decompress(value))


def decode_minutes(value):
    result = []
    payload = unpack(value)
    for row in payload["windows"]:
        for key in ("window_start", "window_end"):
            row[key] = datetime.fromisoformat(row[key])
        result.append(ObservedMinute(**row))
    return result


def read_day(engine, key, modules=range(1,9)):
    wanted = (0, *tuple(modules))
    with engine.connect() as conn:
        rows = list(conn.execute(select(days).where(days.c.day_key == key,
                                                  days.c.module.in_(wanted))).mappings())
    pointer = next((unpack(r["payload"]) for r in rows if r["module"]==0),None)
    if pointer and pointer.get("snapshot_key") and pointer["snapshot_key"] != key:
        return read_day(engine,pointer["snapshot_key"],modules)
    if {r["module"] for r in rows} != set(wanted) or len({r["source_revision"] for r in rows}) != 1:
        return None
    receipt = unpack(next(r["payload"] for r in rows if r["module"] == 0))
    result = [w for r in rows if r["module"] != 0 for w in decode_minutes(r["payload"])]
    receipt["event_ids"] = [eid for r in rows for eid in unpack(r["payload"]).get("event_ids",[])]
    return result, receipt, rows[0]["checked_at"], rows[0]["source_revision"]


def freeze_previous(engine,key,previous):
    """Upgrade an existing complete cache without rereading the source."""
    snapshot=fingerprint([key,previous[1]["source_digest"]])
    with engine.begin() as conn:
        rows=list(conn.execute(select(days).where(days.c.day_key==key)).mappings())
        if {r["module"] for r in rows}!=set(range(9)): raise ValueError("Incomplete day cannot be frozen")
        conn.execute(delete(days).where(days.c.day_key==snapshot))
        for r in rows:
            values=dict(r);values["day_key"]=snapshot
            if r["module"]==0:
                receipt=unpack(r["payload"]);receipt["snapshot_key"]=snapshot
                values["payload"]=pack(receipt)
            conn.execute(days.insert().values(**values))
        pointer={**previous[1],"snapshot_key":snapshot}
        pointer.pop("event_ids",None)
        conn.execute(delete(days).where(days.c.day_key==key))
        conn.execute(days.insert().values(day_key=key,module=0,machine_number=rows[0]["machine_number"],
            source_day=rows[0]["source_day"],source_revision=rows[0]["source_revision"],
            checked_at=rows[0]["checked_at"],payload=pack(pointer)))
    return read_day(engine,key)


def load_day(settings, engine, machine, day, *, as_of, refresh=False, progress=None):
    zone = ZoneInfo(settings.source_timezone)
    start = datetime.combine(day, datetime.min.time(), zone)
    end = start + timedelta(days=1)
    if as_of.tzinfo is None or end > as_of.astimezone(zone)-timedelta(seconds=settings.qualified_1m_late_arrival_seconds):
        raise ValueError("only complete observed days can be cached")
    key = day_key(settings, machine, day)
    previous = read_day(engine, key)
    now = datetime.now(timezone.utc)
    if not refresh and previous and previous[1].get("snapshot_key") and datetime.fromisoformat(previous[2]) >= now-TTL:
        return previous[0], previous[1]
    with fill_lock("observed-" + key[:55], engine_override=engine):
        previous = read_day(engine, key)
        if previous and not previous[1].get("snapshot_key"):
            previous=freeze_previous(engine,key,previous)
        if not refresh and previous and datetime.fromisoformat(previous[2]) >= datetime.now(timezone.utc)-TTL:
            return previous[0], previous[1]
        # One extra observed second carries the true boundary over midnight.
        source_start = start-timedelta(seconds=1)
        if previous and source_revision(settings, machine, source_start, end) == previous[3]:
            with engine.begin() as conn:
                conn.execute(days.update().where(days.c.day_key.in_((key,previous[1].get("snapshot_key",key)))).values(checked_at=now.isoformat()))
            return previous[0], previous[1]
        tracker = TransitionTracker(source_namespace(settings), settings.source_timezone)
        counts, revision, pending_events = {}, {}, []
        event_ids = {m:[] for m in range(9)}
        def flush():
            if pending_events:
                with engine.begin() as conn:
                    append_events(conn, pending_events)
                pending_events.clear()
        def consume(batch):
            records = [r for r in tracker.consume(batch) if r["occurred_at"] >= start.replace(tzinfo=None).isoformat()]
            if records:
                pending_events.extend(records)
                for record in records:
                    counts[record["event_type"]] = counts.get(record["event_type"], 0)+1
                    event_ids[record["module"] or 0].append(record["event_id"])
                if len(pending_events) >= 1000:
                    flush()
        windows = load_observed_one_minute_windows(settings, machine_number=machine,
            start=source_start, end=end, as_of=as_of, modules=range(1,9), compact_json=True,
            window_builder=build_observed_minutes, on_raw_batch=consume, revision_out=revision,
            progress=progress)
        flush()
        windows = [w for w in windows if w.window_start >= start.replace(tzinfo=None)]
        # The extra second may create two source-day revision entries.
        combined_revision = fingerprint(revision)
        # CRC receipt for later change detection covers the identical source slice.
        values = [str(v).split(":") for v in revision.values()]
        raw_count = sum(int(v[0]) for v in values)
        crc_total = sum(int(v[1]) for v in values)
        crc_xor = 0
        for v in values: crc_xor ^= int(v[2])
        revision_value = f"{raw_count}:{crc_total}:{crc_xor}"
        receipt = {"version": VERSION, "machine_number": machine, "day": day.isoformat(),
                   "raw_rows": raw_count, "includes_boundary_second": True,
                   "event_counts": counts, "source_digest": combined_revision,
                   "measurement_minutes": len(windows), "completed": True,
                   "event_policy": "compressor-unified-events-v1"}
        snapshot_key = fingerprint([key,combined_revision])
        receipt["snapshot_key"] = snapshot_key
        with engine.begin() as conn:
            # Immutable snapshots retain evidence for old/reviewed models.
            # The small current-day pointer publishes only after all eight rows.
            if previous and previous[1]["source_digest"] != combined_revision:
                from .unified_events import make_event
                correction=make_event(source_key=[key,"revision",combined_revision],machine=machine,
                    module=None,occurred_at=start,timezone_name=settings.source_timezone,
                    event_type="SOURCE_REVISION_CHANGED",family="DATA_QUALITY",
                    details={"before":previous[1]["source_digest"],"after":combined_revision,
                             "previous_snapshot_key":previous[1].get("snapshot_key",key),
                             "current_snapshot_key":snapshot_key,"source_day":day.isoformat(),
                             "interpretation":"Correction detected; original recorded events retained"})
                append_events(conn,[correction])
            conn.execute(delete(days).where(days.c.day_key == snapshot_key))
            for module in range(9):
                payload = {**receipt,"event_ids":event_ids[0]} if module == 0 else {
                    "windows":[asdict(w) for w in windows if w.module == module],"event_ids":event_ids[module]}
                conn.execute(days.insert().values(day_key=snapshot_key, module=module, machine_number=machine,
                    source_day=day.isoformat(), checked_at=now.isoformat(), source_revision=revision_value,
                    payload=pack(payload)))
            conn.execute(delete(days).where(days.c.day_key == key))
            conn.execute(days.insert().values(day_key=key,module=0,machine_number=machine,
                source_day=day.isoformat(),checked_at=now.isoformat(),source_revision=revision_value,payload=pack(receipt)))
        receipt["event_ids"] = [eid for ids in event_ids.values() for eid in ids]
        return windows, receipt
