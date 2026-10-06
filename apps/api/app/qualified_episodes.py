"""Episode archive policy downstream of the unchanged one-minute detector.

No alert emission, health mapping, labels, profile fitting or automatic approval.
Work orders and technician reports remain owned by the operational Dashboard.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
import copy
import math

from .qualified_scoring import ScoreEvidence


@dataclass(frozen=True)
class EpisodePolicy:
    version: str = "qualified-1m-episode-archive-v1"
    recovery_windows: int = 5
    merge_gap_minutes: int = 5
    unknown_gap_minutes: int = 5
    pre_event_minutes: int = 30
    post_event_minutes: int = 30
    chunk_hours: int = 6
    top_contributors: int = 3

    def __post_init__(self):
        numbers = (self.recovery_windows, self.merge_gap_minutes,
                   self.unknown_gap_minutes, self.pre_event_minutes,
                   self.post_event_minutes, self.chunk_hours, self.top_contributors)
        if not self.version or any(type(n) is not int or n < 1 for n in numbers):
            raise ValueError("episode parameters must be positive integers")
        if self.top_contributors > 9:
            raise ValueError("at most nine contributors")


class EpisodeArchive:
    """JSON-checkpointable, deterministic episode segments, not fault diagnoses.

    Recovery needs qualified observations. Missing/manual/non-Cold observations
    interrupt recovery and grouping, never imply recovery. Close and link new
    segments instead of erasing their original boundaries during grouping.
    """
    def __init__(self, scope: str, policy: EpisodePolicy | None = None):
        if not scope:
            raise ValueError("episode scope is required")
        self.scope = scope
        self.policy = policy or EpisodePolicy()
        self.states = {}
        self.records = {}

    def checkpoint(self):
        needed = {s[name] for s in self.states.values() for name in ("active", "last_closed") if s[name]}
        self.records = {key: value for key, value in self.records.items() if key in needed}
        return copy.deepcopy({"schema_version": 1, "scope": self.scope,
                              "policy": asdict(self.policy), "states": self.states,
                              "records": self.records})

    @classmethod
    def from_checkpoint(cls, saved):
        if saved.get("schema_version") != 1:
            raise ValueError("incompatible episode checkpoint")
        obj = cls(saved["scope"], EpisodePolicy(**saved["policy"]))
        obj.states = copy.deepcopy(saved["states"])
        obj.records = copy.deepcopy(saved["records"])
        return obj

    def consume(self, score: ScoreEvidence, *, available_at: str):
        # Window clocks are naive source-local, as in the qualified scorer.
        start, end = score.window_start, score.window_end
        if start.tzinfo or end.tzinfo or end - start != timedelta(minutes=1):
            raise ValueError("episode requires source-local one-minute windows")
        key = f"{score.machine_number}:{score.module}"
        identity = [score.profile_id, score.profile_version, score.primary_version,
                    score.parameter_version, score.primary_threshold]
        state = self.states.setdefault(key, {"last_end": None, "context": None,
            "pending": [], "active": None, "last_closed": None,
            "grouping_safe": True, "last_input": None})
        fingerprint = asdict(score)
        fingerprint["window_start"], fingerprint["window_end"] = start.isoformat(), end.isoformat()
        if state["last_end"] and end <= datetime.fromisoformat(state["last_end"]):
            if end.isoformat() == state["last_end"] and state["last_input"] == fingerprint:
                return []
            raise ValueError("episode window revision/out-of-order requires replay")
        changed = set()
        contiguous = state["last_end"] == start.isoformat()
        if not contiguous:
            state["pending"] = []
            state["grouping_safe"] = False
            if state["active"]:
                item = self.records[state["active"]]
                item.update(status="UNKNOWN", recovery_run=0, recovery_started_at=None,
                            interruption_reason="MISSING_WINDOWS")
                changed.add(item["episode_id"])
        valid = (score.status == "SCORED" and score.primary_score is not None
                 and score.primary_threshold is not None and score.primary_threshold > 0
                 and math.isfinite(score.primary_score) and math.isfinite(score.primary_threshold))
        if valid and state["context"] is not None and state["context"] != identity:
            if state["active"]:
                item = self.records[state["active"]]
                item.update(status="ENDED_UNKNOWN", close_reason="PROFILE_OR_PARAMETER_CHANGED",
                            closed_at=start.isoformat(), recovery_run=0)
                changed.add(item["episode_id"])
            state.update(active=None, pending=[], last_closed=None, grouping_safe=False)
        if not valid:
            state.update(pending=[], grouping_safe=False)
            if state["active"]:
                item = self.records[state["active"]]
                item.update(status="UNKNOWN", recovery_run=0, recovery_started_at=None,
                            interruption_reason=score.reason or "NOT_SCORED")
                item["unavailable_windows"] += 1
                item["last_observed_at"] = end.isoformat()
                changed.add(item["episode_id"])
        else:
            state["context"] = identity
            flagged = bool(score.primary_raw_flag)
            if not state["active"]:
                if flagged:
                    state["pending"].append({"start": start.isoformat(),
                        "end": end.isoformat(), "score": score.primary_score,
                        "z": score.robust_z or {}})
                    state["pending"] = state["pending"][-3:]
                else:
                    state["pending"] = []
                if flagged and score.primary_persistent_flag and len(state["pending"]) == 3:
                    onset = state["pending"][0]["start"]
                    eid = str(uuid5(NAMESPACE_URL, f"{self.scope}|{key}|{identity}|{onset}"))
                    previous = self.records.get(state["last_closed"])
                    can_group = (previous and state["grouping_safe"]
                        and previous["context"] == identity
                        and timedelta(0) <= datetime.fromisoformat(onset) -
                        datetime.fromisoformat(previous["closed_at"]) <=
                        timedelta(minutes=self.policy.merge_gap_minutes))
                    self.records[eid] = {
                        "episode_id": eid, "episode_group_id": previous["episode_group_id"] if can_group else eid,
                        "machine_number": score.machine_number, "module": score.module,
                        "origin": "DETECTOR", "label_status": "UNREVIEWED",
                        "claim_level": "PERSISTENT_DEVIATION", "policy_version": self.policy.version,
                        "context": identity, "profile_id": score.profile_id,
                        "profile_version": score.profile_version, "primary_version": score.primary_version,
                        "status": "OPEN", "first_deviation_at": onset,
                        "detected_window_end": end.isoformat(), "detected_at": available_at,
                        "last_deviation_at": end.isoformat(), "last_observed_at": end.isoformat(),
                        "closed_at": None, "close_reason": None, "recovery_started_at": None,
                        "recovery_run": 0, "qualified_windows": 2, "flagged_windows": 2,
                        "unavailable_windows": 0, "interruption_reason": None,
                        "peak_score": max(x["score"] for x in state["pending"]),
                        "threshold": score.primary_threshold,
                        "peak_score_ratio": max(x["score"] for x in state["pending"]) / score.primary_threshold,
                        "top_contributors": [{"feature": name, "signed_z": value,
                            "direction": "HIGH" if value >= 0 else "LOW"} for name, value in sorted(
                                max(state["pending"], key=lambda x: x["score"])["z"].items(),
                                key=lambda x: abs(x[1]), reverse=True)[:self.policy.top_contributors]],
                        "requested_evidence_start": (datetime.fromisoformat(onset) -
                            timedelta(minutes=self.policy.pre_event_minutes)).isoformat(),
                        "requested_evidence_end": None,
                        "evidence_status": "QUERY_AVAILABLE_RAW_CHECK_COVERAGE",
                        "chunk_hours": self.policy.chunk_hours,
                    }
                    state.update(active=eid, pending=[])
            if state["active"]:
                item = self.records[state["active"]]
                item["qualified_windows"] += 1
                item["last_observed_at"] = end.isoformat()
                item["interruption_reason"] = None
                if flagged:
                    item.update(status="OPEN", recovery_run=0, recovery_started_at=None,
                                last_deviation_at=end.isoformat())
                    item["flagged_windows"] += 1
                else:
                    item["recovery_run"] += 1
                    item["recovery_started_at"] = item["recovery_started_at"] or start.isoformat()
                    item["status"] = "RECOVERING"
                    if item["recovery_run"] >= self.policy.recovery_windows:
                        item.update(status="RECOVERED", closed_at=end.isoformat(),
                            close_reason="RECOVERED_WITHIN_PROFILE",
                            requested_evidence_end=(end + timedelta(minutes=self.policy.post_event_minutes)).isoformat())
                        state.update(active=None, last_closed=item["episode_id"], grouping_safe=True)
                if score.primary_score >= item["peak_score"]:
                    item["peak_score"] = score.primary_score
                    item["peak_score_ratio"] = score.primary_score / score.primary_threshold
                    item["top_contributors"] = [{"feature": name, "signed_z": value,
                        "direction": "HIGH" if value >= 0 else "LOW"} for name, value in sorted(
                            ((name,value) for name,value in (score.robust_z or {}).items() if name in score.primary_features), key=lambda x: abs(x[1]), reverse=True
                        )[:self.policy.top_contributors]]
                changed.add(item["episode_id"])
        state.update(last_end=end.isoformat(), last_input=fingerprint)
        return [copy.deepcopy(self.records[eid]) for eid in sorted(changed)]

    def mark_stale(self, through: datetime):
        """Called on empty deliveries too; absence is never recovery."""
        changed = []
        for state in self.states.values():
            if state["active"] and state["last_end"] and through - datetime.fromisoformat(state["last_end"]) >= timedelta(minutes=self.policy.unknown_gap_minutes):
                item = self.records[state["active"]]
                item.update(status="UNKNOWN", interruption_reason="SOURCE_GAP",
                            recovery_run=0, recovery_started_at=None)
                state.update(grouping_safe=False, pending=[])
                changed.append(copy.deepcopy(item))
        return changed
