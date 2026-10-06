"""Opt-in durable 1m detector. SELECT-only source; no profile fitting/activation.

Time-overlap rescans + durable source-ID receipts replace a MAX(id) cursor.
Lateness outside the declared overlap cannot be proven complete without CDC.
Changed/too-late rows are quarantined, never silently turned into new normal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, Text, bindparam, select, text, update

from .qualified_calibration import policy_from_settings
from .qualified_persistence import PersistentRehearsal, canonical
from .qualified_shadow_preview import load_matching_active_profiles
from .qualified_stream import CompletedMinuteStream
from .context_storage import source_namespace
from .inference import clean_machine_code, get_machine_candidates


meta = MetaData()
seen = Table("ht9046mx_detector_source_receipt", meta,
    Column("run_id", String(64), primary_key=True),
    Column("source_id", String(64), primary_key=True),
    Column("digest", String(64), nullable=False),
    Column("recorded_at", String(32), nullable=False))
issues = Table("ht9046mx_detector_data_issue", meta,
    Column("issue_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("payload_json", Text, nullable=False))
outbox = Table("ht9046mx_detector_outbox", meta,
    Column("event_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("revision", Integer, nullable=False, default=0),
    Column("delivered", Integer, nullable=False, default=0),
    Column("payload_json", Text, nullable=False))
current = Table("ht9046mx_detector_current", meta,
    Column("machine_number", String(64), primary_key=True),
    Column("run_id", String(64)),
    Column("reason", String(64), nullable=False))
Index("idx_detector_outbox_pending", outbox.c.delivered, outbox.c.revision)
Index("idx_detector_receipt_time", seen.c.run_id, seen.c.recorded_at)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("unsafe SQL identifier")
    return f"`{value}`"


class ObservedSourceReader:
    """Bounded, complete overlap slice; overflow aborts before any watermark moves."""
    def __init__(self, engine, settings, *, maximum_rows=10000):
        self.engine, self.settings, self.maximum_rows = engine, settings, maximum_rows
        if maximum_rows < 60 or not settings.source_table:
            raise ValueError("source table and positive slice budget required")

    def read(self, machine, start, end, modules):
        s = self.settings
        # No source mutation or SELECT *; validate aliases/templates before SQL.
        table = ".".join(identifier(part) for part in s.source_table.split("."))
        templates = (s.source_hp1_template, s.source_lp1_template, s.source_hp2_template,
                     s.source_lp2_template, s.source_valve_template, s.source_temp_high_template,
                     s.source_temp_low_template, s.source_module_status_template,
                     s.source_busy_template, s.source_sv_template)
        canonical_templates = ("Hp_1st_{module}", "Lp_1st_{module}", "Hp_2nd_{module}",
            "Lp_2nd_{module}", "Valve_{module}", "TempHi_{module}", "TempLo_{module}",
            "Status_{module}", "Busy_{module}", "SV_{module}")
        columns = [f"{identifier(s.detector_source_id_column)} AS source_id",
            f"{identifier(s.source_timestamp_column)} AS recorded_at",
            f"{identifier(s.source_machine_column)} AS machine_number",
            f"{identifier(s.source_global_status_column)} AS Status"]
        for module in modules:
            columns += [f"{identifier(a.format(module=module))} AS {identifier(b.format(module=module))}"
                        for a, b in zip(templates, canonical_templates)]
        query = text(f"SELECT {', '.join(columns)} FROM {table} WHERE "
            f"{identifier(s.source_machine_column)} IN :aliases AND "
            f"{identifier(s.source_timestamp_column)} >= :start AND "
            f"{identifier(s.source_timestamp_column)} < :end ORDER BY "
            f"{identifier(s.source_timestamp_column)}, {identifier(s.detector_source_id_column)} "
            "LIMIT :budget").bindparams(bindparam("aliases", expanding=True))
        with self.engine.connect() as conn:
            rows = conn.execute(query, dict(aliases=get_machine_candidates(machine), start=start,
                                end=end, budget=self.maximum_rows + 1)).mappings().all()
        if len(rows) > self.maximum_rows:
            raise RuntimeError("SOURCE_SLICE_OVERFLOW: increase declared budget; no partial slice scored")
        return [{**dict(row), "machine_number": clean_machine_code(row["machine_number"])} for row in rows]


class DurableDetector:
    def __init__(self, engine, policy, *, mode="DETECTOR_SHADOW", overlap_minutes=30, pressure_unit="", source_namespace="detector-source",fleet=None):
        if overlap_minutes < 10 or overlap_minutes * 60 <= policy.late_arrival_seconds:
            raise ValueError("overlap must exceed finalization grace and span at least ten minutes")
        self.engine, self.policy, self.mode = engine, policy, mode
        self.overlap_minutes = overlap_minutes
        if pressure_unit not in {"", "psi", "psig", "psia"}:
            raise ValueError("declared source pressure unit must be psi, psig or psia")
        self.pressure_unit = pressure_unit
        self.store = PersistentRehearsal(engine, table_prefix="ht9046mx_detector", mode=mode,
            unified_events_enabled=True,source_namespace=source_namespace,fleet=fleet)

    def create_tables(self):
        self.store.create_tables()
        meta.create_all(self.engine)

    def initialize(self, machine, modules, profiles):
        signature = digest({"machine": machine, "modules": modules,
            "profiles": [asdict(profiles[k]) for k in sorted(profiles)],
            "policy": asdict(self.policy), "mode": self.mode, "overlap_minutes": self.overlap_minutes,
            "pressure_unit": self.pressure_unit})
        signature=digest([signature,"unified-events-v1",self.store.source_namespace])
        if self.store.fleet:signature=digest([signature,self.store.fleet.bundle_id])
        run_id = "detector-" + signature[:48]
        self.store.initialize(run_id, CompletedMinuteStream(self.policy, tuple(modules)), profiles)
        self.set_current(machine, run_id,reason="MATCHING_PROFILE" if profiles else "OBSERVING_WITHOUT_LEGACY_ACTIVE")
        return run_id

    def set_current(self, machine, run_id=None,reason=None):
        with self.engine.begin() as conn:
            existing = conn.execute(select(current).where(current.c.machine_number == machine)
                                    .with_for_update()).first()
            values = dict(run_id=run_id, reason=reason or ("MATCHING_PROFILE" if run_id else "NO_MATCHING_ACTIVE_PROFILE"))
            if existing:
                conn.execute(current.update().where(current.c.machine_number == machine).values(**values))
            else:
                conn.execute(current.insert().values(machine_number=machine, **values))

    def cycle(self, run_id, rows, *, as_of, profiles, before_commit=None):
        """One serialized transaction for source receipts, scores, Episodes and outbox."""
        with self.engine.connect() as conn:
            state = conn.execute(select(self.store.runs).where(self.store.runs.c.run_id == run_id)).mappings().one()
        checkpoint = json.loads(state["checkpoint_json"])
        closed = checkpoint["stream"]["closed_before"]
        last_as_of = checkpoint["stream"]["last_as_of"]
        local_now = as_of.astimezone(ZoneInfo(self.policy.source_timezone)).replace(tzinfo=None)
        if last_as_of and local_now < datetime.fromisoformat(last_as_of):
            raise ValueError("worker clock moved backwards")
        incoming, receipt_rows, problems = [], [], []
        ids = [str(row["source_id"]) for row in rows]
        if len(ids) != len(set(ids)) or any(not value or len(value) > 64 for value in ids):
            raise ValueError("source IDs must be unique, nonempty and bounded")
        with self.engine.connect() as conn:
            previous = {}
            for offset in range(0, len(ids), 500):
                previous.update({r["source_id"]: r["digest"] for r in conn.execute(select(seen).where(
                    seen.c.run_id == run_id, seen.c.source_id.in_(ids[offset:offset+500]))).mappings()})
        for raw in rows:
            row = dict(raw)
            source_id = str(row.pop("source_id"))
            stamp = row["recorded_at"]
            if not isinstance(stamp, datetime) or stamp.tzinfo:
                raise ValueError("source reader must return source-local DATETIME")
            value_digest = digest(row)
            changed = source_id in previous and previous[source_id] != value_digest
            late = closed is not None and stamp < datetime.fromisoformat(closed)
            if source_id in previous and not changed:
                continue
            if changed or late:
                problem = dict(source_id=source_id, recorded_at=stamp,
                    reason="SOURCE_ROW_CHANGED" if changed else "AFTER_FINALIZATION",
                    observed_at=as_of, source_digest=value_digest, machine_number=row["machine_number"])
                problems.append(problem)
            else:
                incoming.append(row)
            if source_id not in previous:
                receipt_rows.append(dict(run_id=run_id, source_id=source_id,
                    digest=value_digest, recorded_at=stamp.isoformat()))
        batch_id = digest(dict(revision=state["revision"], as_of=as_of, rows=rows))
        def commit_hook(conn, output, changed_episodes, result):
            if receipt_rows:
                conn.execute(seen.insert(), receipt_rows)
            for problem in problems:
                problem_id = digest({"run_id": run_id, **{k: v for k, v in problem.items() if k != "observed_at"}})
                if conn.execute(select(issues.c.issue_id).where(issues.c.issue_id == problem_id)).first() is None:
                    conn.execute(issues.insert().values(issue_id=problem_id, run_id=run_id,
                                                       payload_json=canonical(problem)))
                    payload = dict(run_id=run_id, mode=self.mode, source_timezone=self.policy.source_timezone,
                                   source_pressure_unit=self.pressure_unit,
                                   revision=result["revision"], data=problem)
                    conn.execute(outbox.insert().values(event_id=problem_id, run_id=run_id,
                        kind="DATA_ISSUE", revision=result["revision"], delivered=0, payload_json=canonical(payload)))
            for kind, values in (("WINDOW", [json.loads(x["payload_json"]) for x in output]),
                                 ("EPISODE", changed_episodes)):
                for value in values:
                    if kind == "WINDOW":
                        w = value["window"]
                        profile = profiles.get((w["machine_number"], w["module"]))
                        value["baseline"] = asdict(profile) if profile else None
                    payload = {"run_id": run_id, "mode": self.mode,
                               "source_pressure_unit": self.pressure_unit,
                               "source_timezone": self.policy.source_timezone,
                               "revision": result["revision"], "data": value}
                    event_id = digest(payload)
                    if conn.execute(select(outbox.c.event_id).where(outbox.c.event_id == event_id)).first() is None:
                        conn.execute(outbox.insert().values(event_id=event_id, run_id=run_id,
                            kind=kind, revision=result["revision"], delivered=0, payload_json=canonical(payload)))
            result.update(source_rows_scanned=len(rows), new_source_rows=len(receipt_rows),
                          quarantined_rows=len(problems), mode=self.mode)
        result = self.store.consume(run_id, batch_id, incoming, as_of=as_of,
            next_cursor=state["source_cursor"] + len(incoming), profiles=profiles,
            expected_revision=state["revision"], before_commit=before_commit, transaction_hook=commit_hook)
        return result

    def poll(self, reader, machine, *, as_of, profiles):
        modules = tuple(range(1, 9))
        run_id = self.initialize(machine, modules, profiles)
        local_now = as_of.astimezone(ZoneInfo(self.policy.source_timezone)).replace(tzinfo=None)
        with self.engine.connect() as conn:
            saved = conn.execute(select(self.store.runs.c.checkpoint_json).where(
                self.store.runs.c.run_id == run_id)).scalar_one()
        stream = json.loads(saved)["stream"]
        # Catch up after a downtime; never jump the lower bound straight to now.
        anchor = datetime.fromisoformat(stream["last_as_of"]) if stream["last_as_of"] else local_now
        cycle_end = min(local_now, anchor + timedelta(minutes=5)) if stream["last_as_of"] else local_now
        cycle_as_of = cycle_end.replace(tzinfo=ZoneInfo(self.policy.source_timezone))
        start = (anchor - timedelta(minutes=self.overlap_minutes)).replace(second=0, microsecond=0)
        rows = reader.read(machine, start, cycle_end, modules)
        result = self.cycle(run_id, rows, as_of=cycle_as_of, profiles=profiles)
        return {**result, "run_id": run_id, "matching_active_profiles": len(profiles),
                "scan_start": start.isoformat(), "scan_end": cycle_end.isoformat(),
                "catchup_remaining": cycle_end < local_now}


def run_configured_cycle(settings, *, as_of=None, migrate=False):
    """Server-portable entry point; disabled until explicitly configured."""
    if not settings.detector_worker_enabled:
        return {"status": "DETECTOR_DISABLED", "database_writes": 0}
    if not settings.source_timezone or not settings.source_pressure_unit:
        raise ValueError("confirmed source timezone and pressure unit required")
    from .db import get_engine, get_source_engine
    engine, source_engine = get_engine(), get_source_engine()
    if engine is None or source_engine is None:
        raise ValueError("separate analytics and SELECT-only source connections required")
    fleet=None
    if settings.detector_fleet_shadow_enabled:
        from .fleet_bundle import current_snapshot
        _,fleet=current_snapshot(settings.fleet_stable_store or settings.project_root/'artifacts/fleet-stable')
        if settings.source_pressure_unit!='psi' or settings.source_timezone!='Asia/Bangkok':
            raise ValueError('Fleet package requires the declared psi / Asia Bangkok source semantics')
    detector = DurableDetector(engine, policy_from_settings(settings),
        mode="DETECTOR_SHADOW" if settings.detector_shadow_only else "DETECTOR_LIVE",
        overlap_minutes=settings.detector_overlap_minutes, pressure_unit=settings.source_pressure_unit,
        source_namespace=source_namespace(settings),fleet=fleet)
    if migrate:
        detector.create_tables()
    reader = ObservedSourceReader(source_engine, settings, maximum_rows=settings.detector_max_source_rows)
    now = as_of or datetime.now(timezone.utc)
    result = []
    for machine in settings.detector_machines.split(","):
        if not machine.strip():
            continue
        machine = clean_machine_code(machine)
        profiles = load_matching_active_profiles(settings, machine, engine=engine)
        # Observe all controls even without Active. Scoring remains NOT_SCORED.
        # Bounded fast catch-up instead of advancing one delivery per scheduler tick.
        for _ in range(12):
            item = detector.poll(reader, machine, as_of=now, profiles=profiles)
            result.append(item)
            if not item["catchup_remaining"]:
                break
    return {"status": "COMPLETED", "machines": result}


def main():
    parser = argparse.ArgumentParser(description="Opt-in durable qualified-minute detector")
    parser.add_argument("--migrate", action="store_true", help="Create ONLY new analytics detector tables")
    parser.add_argument("--migrate-only", action="store_true", help="Add detector tables without fetching/scoring source")
    parser.add_argument("--allow-remote", action="store_true", help="Explicit deployment opt-in; not used in local QA")
    args = parser.parse_args()
    from .config import get_settings
    settings = get_settings()
    if not args.allow_remote and any(host not in {"localhost", "127.0.0.1", "::1"}
            for host in (settings.source_db_host, settings.analytics_db_host)):
        parser.error("local command requires localhost source and analytics; remote deployment is separate")
    if args.migrate_only:
        from .db import get_engine
        engine = get_engine()
        if engine is None:
            parser.error("analytics connection required for additive DDL")
        PersistentRehearsal(engine,table_prefix="ht9046mx_detector",mode="DETECTOR_SHADOW",unified_events_enabled=True).create_tables()
        meta.create_all(engine)
        result = {"status":"DETECTOR_TABLES_CREATED","source_rows_read":0,"profiles_activated":0}
    else:
        result = run_configured_cycle(settings, migrate=args.migrate)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
