"""Transactional minute/score/Episode/checkpoint storage with versioned scope.

Default namespace remains local rehearsal. The opt-in qualified detector uses
a separate prefix and its own overlap/source-ID receipt adapter. Its cursor is
an accepted-row counter, not a claim about MySQL commit-order IDs.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (BigInteger, Column, Index, Integer, MetaData, String, Table,
                        Text, select, update)

from .qualified_scoring import QualifiedShadowScorer, TemporalParameters
from .qualified_stream import CompletedMinuteStream
from .qualified_episodes import EpisodeArchive, EpisodePolicy
from .qualified_evidence import minute_evidence


metadata = MetaData()
runs = Table("ht9046mx_rehearsal_stream", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("source_cursor", BigInteger, nullable=False),
    Column("contract_json", Text, nullable=False),
    Column("checkpoint_json", Text, nullable=False))
batches = Table("ht9046mx_rehearsal_batch", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("batch_id", String(64), primary_key=True),
    Column("digest", String(64), nullable=False),
    Column("result_json", Text, nullable=False))
evidence = Table("ht9046mx_rehearsal_evidence", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("machine_number", String(64), primary_key=True),
    Column("module", Integer, primary_key=True),
    Column("window_start", String(32), primary_key=True),
    Column("payload_json", Text, nullable=False))

episodes = Table("ht9046mx_rehearsal_episode", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("episode_id", String(36), primary_key=True),
    Column("payload_json", Text, nullable=False))
raw_evidence = Table("ht9046mx_rehearsal_raw_evidence", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("batch_id", String(64), primary_key=True),
    Column("row_index", Integer, primary_key=True),
    Column("machine_number", String(64), nullable=False),
    Column("recorded_at", String(32), nullable=False),
    Column("payload_json", Text, nullable=False))
Index("ix_rehearsal_raw_range", raw_evidence.c.run_id,
      raw_evidence.c.machine_number, raw_evidence.c.recorded_at)


def _encode(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported checkpoint value {type(value).__name__}")


def canonical(value):
    return json.dumps(value, sort_keys=True, default=_encode, allow_nan=False,
                      separators=(",", ":"))


class PersistentRehearsal:
    def __init__(self, engine, *, table_prefix="ht9046mx_rehearsal", mode="LOCAL_REHEARSAL", unified_events_enabled=False, source_namespace="detector-source", fleet=None):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", table_prefix):
            raise ValueError("invalid evidence table prefix")
        if mode not in {"LOCAL_REHEARSAL", "DETECTOR_SHADOW", "DETECTOR_LIVE"}:
            raise ValueError("invalid evidence mode")
        self.engine = engine
        self.mode = mode
        self.unified_events_enabled=unified_events_enabled
        self.source_namespace=source_namespace
        self.fleet=fleet
        self.metadata = MetaData()
        for name, original in (("runs", runs), ("batches", batches), ("evidence", evidence),
                               ("episodes", episodes), ("raw_evidence", raw_evidence)):
            suffix = original.name.removeprefix("ht9046mx_rehearsal_")
            setattr(self, name, original.to_metadata(self.metadata, name=f"{table_prefix}_{suffix}"))

    def create_tables(self):
        # Explicit invocation only; never an API startup migration.
        self.metadata.create_all(self.engine)
        if self.unified_events_enabled:
            from .unified_events import metadata as event_meta
            from .context_review import metadata as context_meta
            event_meta.create_all(self.engine)
            context_meta.create_all(self.engine)

    def initialize(self, run_id, stream, profiles, parameters=None, episode_policy=None):
        runs = self.runs
        if not run_id or len(run_id) > 64:
            raise ValueError("run_id must contain 1..64 characters")
        parameters = parameters or TemporalParameters()
        episode_policy = episode_policy or EpisodePolicy()
        contract = canonical({"mode": self.mode,"unified_events_enabled":self.unified_events_enabled,
            **({'fleet_shadow_bundle_id':self.fleet.bundle_id} if self.fleet else {}),
            "event_namespace":self.source_namespace,"profiles": [
            asdict(profiles[k]) for k in sorted(profiles)],
            "parameters": asdict(parameters), "policy": asdict(stream.policy),
            "modules": stream.modules, "episode_policy": asdict(episode_policy)})
        state = canonical({"stream": stream.checkpoint(),
                           "scorer": QualifiedShadowScorer(parameters).checkpoint(),
                           "episodes": EpisodeArchive(run_id, episode_policy).checkpoint()})
        with self.engine.begin() as conn:
            existing = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
            if existing:
                if existing["contract_json"] != contract:
                    raise ValueError("run contract changed; create a new run")
                return
            conn.execute(runs.insert().values(run_id=run_id, revision=0,
                         source_cursor=0, contract_json=contract, checkpoint_json=state))

    def consume(self, run_id, batch_id, rows, *, as_of, next_cursor,
                profiles, parameters=None, before_commit=None, transaction_hook=None, expected_revision=None):
        """Restore each cycle; commit cursor + checkpoint + evidence together.

        before_commit is a failure-injection hook for rollback testing only.
        Durable batch receipts preserve retry identity beyond the memory ring.
        """
        if not batch_id or len(batch_id) > 64 or not isinstance(next_cursor, int):
            raise ValueError("valid batch ID and integer ingestion cursor required")
        parameters = parameters or TemporalParameters()
        runs, batches, evidence = self.runs, self.batches, self.evidence
        episodes, raw_evidence = self.episodes, self.raw_evidence
        rows = list(rows)
        digest = hashlib.sha256(canonical({"rows": rows, "as_of": as_of,
                                          "next_cursor": next_cursor}).encode()).hexdigest()
        with self.engine.begin() as conn:
            saved = conn.execute(select(runs).where(runs.c.run_id == run_id)
                                 .with_for_update()).mappings().one()
            if expected_revision is not None and saved["revision"] != expected_revision:
                raise RuntimeError("concurrent checkpoint update; reload and retry")
            contract = json.loads(saved["contract_json"])
            if contract.get('fleet_shadow_bundle_id')!=(self.fleet.bundle_id if self.fleet else None):
                raise ValueError('Fleet version changed; create a new run before advancing the checkpoint')
            if (canonical(contract["profiles"]) != canonical([asdict(profiles[k]) for k in sorted(profiles)])
                    or canonical(contract["parameters"]) != canonical(asdict(parameters))):
                raise ValueError("profile/parameter contract changed")
            receipt = conn.execute(select(batches).where(
                batches.c.run_id == run_id, batches.c.batch_id == batch_id)).mappings().first()
            if receipt:
                if receipt["digest"] != digest:
                    raise ValueError("retried batch payload or cursor changed")
                return {**json.loads(receipt["result_json"]), "duplicate_batch": True}
            if next_cursor < saved["source_cursor"] or (rows and next_cursor == saved["source_cursor"]):
                raise ValueError("source ingestion cursor did not advance")
            checkpoint = json.loads(saved["checkpoint_json"])
            stream = CompletedMinuteStream.from_checkpoint(checkpoint["stream"])
            scorer = QualifiedShadowScorer.from_checkpoint(checkpoint["scorer"], parameters)
            archive = (EpisodeArchive.from_checkpoint(checkpoint["episodes"])
                       if "episodes" in checkpoint else EpisodeArchive(run_id))
            if asdict(archive.policy) != contract.get("episode_policy", asdict(EpisodePolicy())):
                raise ValueError("episode policy contract changed")
            evidence_rows = stream.pending + rows
            windows, info = stream.consume(rows, as_of=as_of, batch_id=batch_id)
            secondary = minute_evidence(evidence_rows, windows, stream._local)
            context_checkpoint=checkpoint.get("context",{})
            if self.unified_events_enabled:
                from .context_monitor import consume_observed
                complete=[r for r in evidence_rows if stream._local(r["recorded_at"])<stream.closed_before]
                context_checkpoint=consume_observed(conn,complete,as_of,stream,context_checkpoint,
                    source_namespace=self.source_namespace,mode=self.mode,run_id=run_id,fleet=self.fleet)
            output = []
            changed_episodes = {}
            for window in windows:
                score = scorer.score(window, profiles.get((window.machine_number, window.module)))
                for item in archive.consume(score, available_at=as_of.isoformat()):
                    changed_episodes[item["episode_id"]] = item
                payload = {"window": asdict(window), "score": asdict(score),
                           "second_statistics": secondary[(window.machine_number, window.module, window.window_start)],
                           "available_at": as_of, "mode": self.mode}
                output.append({"run_id": run_id, "machine_number": window.machine_number,
                    "module": window.module, "window_start": window.window_start.isoformat(),
                    "payload_json": canonical(payload)})
            if output:
                conn.execute(evidence.insert(), output)
            for item in archive.mark_stale(stream.closed_before):
                changed_episodes[item["episode_id"]] = item
            for eid, item in changed_episodes.items():
                query = select(episodes.c.episode_id).where(episodes.c.run_id == run_id, episodes.c.episode_id == eid)
                item.update(mode="LOCAL_REHEARSAL_NOT_ACTIVE" if self.mode == "LOCAL_REHEARSAL" else self.mode,
                            source_timezone=stream.policy.source_timezone)
                if conn.execute(query).first():
                    conn.execute(episodes.update().where(episodes.c.run_id == run_id,
                        episodes.c.episode_id == eid).values(payload_json=canonical(item)))
                else:
                    conn.execute(episodes.insert().values(run_id=run_id, episode_id=eid, payload_json=canonical(item)))
                if self.unified_events_enabled:
                    from .unified_events import make_event,append_events
                    at=item.get("last_observed_at") or item["first_deviation_at"]
                    append_events(conn,[make_event(source_key=[run_id,eid,item],machine=item["machine_number"],module=item["module"],
                        occurred_at=at,timezone_name=stream.policy.source_timezone,event_type="ANOMALY_EPISODE_UPDATED",
                        family="ANOMALY",mode=self.mode,assessment=item["status"],correlation_id=eid,run_id=run_id,
                        details={"episode":item,"profile_version":item.get("profile_version"),
                                 "claim":"Persistent deviation evidence; cause requires inspection"})])
            if rows:
                conn.execute(raw_evidence.insert(), [{"run_id": run_id, "batch_id": batch_id,
                    "row_index": i, "machine_number": str(row["machine_number"]),
                    "recorded_at": stream._local(row["recorded_at"]).isoformat(),
                    "payload_json": canonical(row)} for i, row in enumerate(rows)])
            result = {**info, "windows_written": len(output), "source_cursor": next_cursor,
                      "revision": saved["revision"] + 1, "episodes_updated": len(changed_episodes)}
            conn.execute(batches.insert().values(run_id=run_id, batch_id=batch_id,
                         digest=digest, result_json=canonical(result)))
            updated = conn.execute(update(runs).where(runs.c.run_id == run_id,
                runs.c.revision == saved["revision"]).values(revision=saved["revision"]+1,
                source_cursor=next_cursor, checkpoint_json=canonical({
                    "stream": stream.checkpoint(), "scorer": scorer.checkpoint(),
                    "episodes": archive.checkpoint(),"context":context_checkpoint})))
            if updated.rowcount != 1:
                raise RuntimeError("concurrent checkpoint update; retry transaction")
            if transaction_hook:
                transaction_hook(conn, output, list(changed_episodes.values()), result)
                conn.execute(batches.update().where(batches.c.run_id == run_id,
                    batches.c.batch_id == batch_id).values(result_json=canonical(result)))
            if before_commit:
                before_commit()
            return result

    def points(self, run_id, *, machine_number=None, module=None, limit=10000):
        evidence = self.evidence
        query = select(evidence.c.payload_json).where(evidence.c.run_id == run_id)
        if machine_number is not None:
            query = query.where(evidence.c.machine_number == machine_number)
        if module is not None:
            query = query.where(evidence.c.module == module)
        with self.engine.connect() as conn:
            return [json.loads(row[0]) for row in conn.execute(query.order_by(
                evidence.c.window_start, evidence.c.machine_number, evidence.c.module).limit(limit))]

    def episode_summaries(self, run_id):
        episodes = self.episodes
        with self.engine.connect() as conn:
            items = [json.loads(row[0]) for row in conn.execute(select(episodes.c.payload_json)
                .where(episodes.c.run_id == run_id))]
        return sorted(items, key=lambda item: (item["first_deviation_at"], item["episode_id"]))

    def episode_raw(self, run_id, episode_id, *, limit=20000, start=None, end=None):
        raw_evidence = self.raw_evidence
        """Bounded raw evidence; requested range is NOT a completeness claim."""
        item = next((x for x in self.episode_summaries(run_id) if x["episode_id"] == episode_id), None)
        if item is None:
            return None
        requested_end = item["requested_evidence_end"] or item["last_observed_at"]
        if any(x is not None and (not isinstance(x, datetime) or x.tzinfo) for x in (start, end)):
            raise ValueError("raw slices must use source-local naive datetimes")
        start = max(start.isoformat() if start else item["requested_evidence_start"], item["requested_evidence_start"])
        end = min(end.isoformat() if end else requested_end, requested_end)
        if end <= start:
            raise ValueError("raw slice must have end after start")
        query = select(raw_evidence.c.payload_json).where(raw_evidence.c.run_id == run_id,
            raw_evidence.c.machine_number == item["machine_number"],
            raw_evidence.c.recorded_at >= start, raw_evidence.c.recorded_at < end)
        limit = max(1, min(limit, 20000))
        with self.engine.connect() as conn:
            rows = [json.loads(x[0]) for x in conn.execute(query.order_by(raw_evidence.c.recorded_at,
                raw_evidence.c.batch_id, raw_evidence.c.row_index).limit(limit + 1))]
        return {"episode": item, "rows": rows[:limit], "truncated": len(rows) > limit,
                "coverage_verified": False, "slice_start": start, "slice_end_exclusive": end}
