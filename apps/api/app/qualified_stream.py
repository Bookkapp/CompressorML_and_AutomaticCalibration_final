"""Bounded raw-second delivery rehearsal for completed one-minute windows.

Deliver non-overlapping source slices. A retried slice uses the same batch ID;
source duplicate seconds inside a slice are preserved for the data-quality gate.
No database or profile activation is performed here.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

from .qualified_windows import WINDOW_VERSION, WindowPolicy, build_completed_windows


class CompletedMinuteStream:
    def __init__(self, policy: WindowPolicy, modules: tuple[int, ...], *, receipt_limit: int = 32):
        if not modules or len(set(modules)) != len(modules) or any(m not in range(1, 9) for m in modules):
            raise ValueError("modules must be unique values 1..8")
        if receipt_limit < 1:
            raise ValueError("receipt_limit must be positive")
        self.policy = policy
        self.modules = tuple(modules)
        self.receipt_limit = receipt_limit
        self.pending: list[dict] = []
        self.closed_before: datetime | None = None
        self.last_as_of: datetime | None = None
        self.receipts: OrderedDict[str, str] = OrderedDict()

    def _local(self, stamp: datetime) -> datetime:
        if not isinstance(stamp, datetime):
            raise ValueError("timestamp must be datetime")
        return stamp.astimezone(ZoneInfo(self.policy.source_timezone)).replace(tzinfo=None) if stamp.tzinfo else stamp

    def consume(self, rows: Iterable[Mapping], *, as_of: datetime, batch_id: str):
        if as_of.tzinfo is None or not batch_id:
            raise ValueError("aware as_of and a batch ID are required")
        local_now = self._local(as_of)
        normalized = []
        for item in rows:
            row = {key: str(value) if isinstance(value, Decimal) else value for key, value in item.items()}
            row["recorded_at"] = self._local(row["recorded_at"])
            if row["recorded_at"] >= local_now:
                raise ValueError("delivery contains a sample at or after as_of")
            normalized.append(row)
        digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, default=str).encode()).hexdigest()
        if batch_id in self.receipts:
            if self.receipts[batch_id] != digest:
                raise ValueError("retried batch payload changed")
            return [], {"duplicate_batch": True, "late_rows_dropped": 0, "pending_rows": len(self.pending)}
        if self.last_as_of is not None and local_now < self.last_as_of:
            raise ValueError("as_of moved backwards")
        late = [row for row in normalized if self.closed_before is not None and row["recorded_at"] < self.closed_before]
        accepted = [row for row in normalized if self.closed_before is None or row["recorded_at"] >= self.closed_before]
        from datetime import timedelta
        cutoff = (local_now - timedelta(seconds=self.policy.late_arrival_seconds)).replace(second=0, microsecond=0)
        combined = self.pending + accepted
        complete = [row for row in combined if row["recorded_at"] < cutoff]
        pending = [row for row in combined if row["recorded_at"] >= cutoff]
        windows = build_completed_windows(complete, as_of=as_of, policy=self.policy, modules=self.modules)
        self.pending = pending
        self.closed_before = cutoff
        self.last_as_of = local_now
        self.receipts[batch_id] = digest
        while len(self.receipts) > self.receipt_limit:
            self.receipts.popitem(last=False)
        return windows, {"duplicate_batch": False, "late_rows_dropped": len(late),
                         "pending_rows": len(pending), "accepted_rows": len(accepted)}

    def checkpoint(self) -> dict:
        return {"schema_version": 1, "feature_version": WINDOW_VERSION,
                "policy": asdict(self.policy), "modules": list(self.modules),
                "receipt_limit": self.receipt_limit, "receipts": list(self.receipts.items()),
                "closed_before": self.closed_before.isoformat() if self.closed_before else None,
                "last_as_of": self.last_as_of.isoformat() if self.last_as_of else None,
                "pending": [{**row, "recorded_at": row["recorded_at"].isoformat()} for row in self.pending]}

    @classmethod
    def from_checkpoint(cls, state: Mapping) -> "CompletedMinuteStream":
        if state.get("schema_version") != 1 or state.get("feature_version") != WINDOW_VERSION:
            raise ValueError("incompatible stream checkpoint")
        policy = dict(state["policy"])
        for key in ("busy_normal", "sv_off"):
            policy[key] = tuple(policy[key])
        stream = cls(WindowPolicy(**policy), tuple(state["modules"]), receipt_limit=int(state["receipt_limit"]))
        stream.closed_before = datetime.fromisoformat(state["closed_before"]) if state.get("closed_before") else None
        stream.last_as_of = datetime.fromisoformat(state["last_as_of"]) if state.get("last_as_of") else None
        stream.pending = [{**row, "recorded_at": datetime.fromisoformat(row["recorded_at"])} for row in state["pending"]]
        stream.receipts = OrderedDict(state["receipts"])
        if len(stream.receipts) > stream.receipt_limit or any(
                row["recorded_at"].tzinfo is not None or
                (stream.closed_before is not None and row["recorded_at"] < stream.closed_before)
                for row in stream.pending):
            raise ValueError("invalid stream checkpoint")
        return stream
