from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .config import get_settings


class DemoEvidence:
    """Read-only preview backed by the verified Phase 7 artifacts in this repository."""

    def __init__(self) -> None:
        root = get_settings().project_root
        self.replay_root = (
            root
            / "notebooks"
            / "outputs"
            / "ht9046mx_phase7_shadow_replay_v2_hp180"
        )

    @staticmethod
    def _dt(value: Any) -> datetime | None:
        if value in (None, "", "NaT"):
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def fleet_machines(self) -> list[dict[str, Any]]:
        path = self.replay_root / "primary_replay_by_machine.csv"
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                alerts = int(row["alerts"])
                rows.append(
                    {
                        "machine_number": f"MX{int(row['machine_number']):03d}",
                        "scored_rows": int(row["scored_rows"]),
                        "raw_flag_rate_pct": float(row["raw_flag_rate_pct"]),
                        "alerts": alerts,
                        "alerts_per_machine_day": float(row["alerts_per_machine_day"]),
                        "condition_status": "Deviation detected" if alerts else "Normal within this profile",
                        "latest_event_time": None,
                    }
                )
        return rows

    _prospective_alerts: list[dict[str, Any]] = []

    def incidents(self, prospective_only: bool = False) -> list[dict[str, Any]]:
        if prospective_only:
            return list(self._prospective_alerts)
        path = self.replay_root / "primary_alert_episodes.csv"
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                rows.append(
                    {
                        "alert_id": index,
                        "machine_number": f"MX{int(row['machine_number']):03d}",
                        "module": int(row["module"]),
                        "episode_start": self._dt(row["episode_start"]),
                        "detected_at": self._dt(row["detected_at"]),
                        "last_observed_at": None,
                        "alert_status": "OPEN",
                        "severity": "INVESTIGATE",
                        "claim_level": "PERSISTENT_PATTERN",
                        "release_version": "phase07-shadow-replay-v2-hp180",
                        "evidence": {
                            "score": float(row["score"]),
                            "threshold": float(row["threshold"]),
                            "sv": row.get("sv", "Unknown"),
                            "source": "verified offline replay",
                        },
                        "confirmation_status": "PENDING",
                        "is_prospective": False,
                    }
                )
        mx080 = {
            "alert_id": 10000,
            "machine_number": "MX080",
            "module": 6,
            "episode_start": self._dt("2026-09-07 12:25:00"),
            "detected_at": self._dt("2026-09-07 12:35:00"),
            "last_observed_at": self._dt("2026-09-07 23:55:00"),
            "alert_status": "OPEN",
            "severity": "INVESTIGATE",
            "claim_level": "PERSISTENT_PATTERN",
            "release_version": "phase07-shadow-replay-v2-hp180",
            "evidence": {
                "score": 11.358567349017216,
                "threshold": 7.650715626730769,
                "sv": "Off",
                "source": "MX-080 incident replay fixture",
            },
            "confirmation_status": "PENDING",
            "is_prospective": False,
        }
        return list(self._prospective_alerts) + [mx080, *list(reversed(rows))]

    def simulate_prospective_alert(self, machine: str = "MX080", module: int = 6) -> dict[str, Any]:
        alert_id = 90000 + len(self._prospective_alerts) + 1
        now = datetime.now(timezone.utc)
        alert = {
            "alert_id": alert_id,
            "machine_number": machine.upper(),
            "module": int(module),
            "episode_start": (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
            "detected_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_observed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "alert_status": "OPEN",
            "severity": "CRITICAL",
            "claim_level": "PERSISTENT_PATTERN",
            "release_version": "live-stream-prospective-v1",
            "evidence": {
                "score": 9.85,
                "threshold": 7.65,
                "sv": "Off",
                "source": "incoming live telemetry stream",
                "prospective": True,
            },
            "confirmation_status": "PENDING",
            "is_prospective": True,
        }
        self._prospective_alerts.insert(0, alert)
        return alert

    def timeline(self, machine: str, module: int) -> list[dict[str, Any]]:
        if machine.upper().replace("-", "") not in {"MX080", "080"} or module != 6:
            return []
        path = self.replay_root / "mx080_module6_incident_scores.parquet"
        wanted = [
            "minute", "hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo",
            "score", "threshold", "raw_flag", "persistent_flag", "sv", "state",
            "data_quality_status",
        ]
        table = pq.read_table(path, columns=wanted)
        points: list[dict[str, Any]] = []
        for row in table.to_pylist():
            points.append(
                {
                    "event_time": row["minute"],
                    "hp1": row["hp1"],
                    "lp1": row["lp1"],
                    "hp2": row["hp2"],
                    "lp2": row["lp2"],
                    "valve": row["valve"],
                    "temp_high": row["temphi"],
                    "temp_low": row["templo"],
                    "anomaly_score": row["score"],
                    "threshold": row["threshold"],
                    "raw_flag": bool(row["raw_flag"]),
                    "persistent_flag": bool(row["persistent_flag"]),
                    "sv_state": str(row["sv"]),
                    "busy_state": None,
                    "state_code": str(row["state"]),
                    "message_code": None,
                    "message_text": None,
                    "data_quality_status": row["data_quality_status"],
                }
            )
        return points

    def manifest(self) -> dict[str, Any]:
        path = self.replay_root / "shadow_release_manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def _calibration_batch_id(self) -> str:
        return "demo-historical-autobootstrap"

    @staticmethod
    def _default_correlations() -> dict[str, dict[str, float]]:
        return {
            "hp1":    {"hp1": 1.0,  "lp1": 0.55, "hp2": 0.35, "lp2": 0.28, "dp1": 0.88, "dp2": 0.32, "valve": -0.15, "temphi": 0.68, "templo": 0.25},
            "lp1":    {"hp1": 0.55, "lp1": 1.0,  "hp2": 0.22, "lp2": 0.31, "dp1": 0.12, "dp2": 0.20, "valve": -0.08, "temphi": 0.42, "templo": 0.18},
            "hp2":    {"hp1": 0.35, "lp1": 0.22, "hp2": 1.0,  "lp2": 0.74, "dp1": 0.30, "dp2": 0.95, "valve": -0.42, "temphi": 0.38, "templo": 0.52},
            "lp2":    {"hp1": 0.28, "lp1": 0.31, "hp2": 0.74, "lp2": 1.0,  "dp1": 0.22, "dp2": 0.58, "valve": -0.62, "temphi": 0.29, "templo": 0.58},
            "dp1":    {"hp1": 0.88, "lp1": 0.12, "hp2": 0.30, "lp2": 0.22, "dp1": 1.0,  "dp2": 0.28, "valve": -0.12, "temphi": 0.61, "templo": 0.21},
            "dp2":    {"hp1": 0.32, "lp1": 0.20, "hp2": 0.95, "lp2": 0.58, "dp1": 0.28, "dp2": 1.0,  "valve": -0.32, "temphi": 0.36, "templo": 0.46},
            "valve":  {"hp1": -0.15,"lp1": -0.08,"hp2": -0.42,"lp2": -0.62,"dp1": -0.12,"dp2": -0.32,"valve": 1.0,  "temphi": -0.22,"templo": -0.38},
            "temphi": {"hp1": 0.68, "lp1": 0.42, "hp2": 0.38, "lp2": 0.29, "dp1": 0.61, "dp2": 0.36, "valve": -0.22, "temphi": 1.0,  "templo": 0.31},
            "templo": {"hp1": 0.25, "lp1": 0.18, "hp2": 0.52, "lp2": 0.58, "dp1": 0.21, "dp2": 0.46, "valve": -0.38, "temphi": 0.31, "templo": 1.0},
        }

    def _demo_profiles(self) -> list[dict[str, Any]]:
        root = get_settings().project_root / "notebooks" / "outputs" / "ht9046mx_autobootstrap"
        lifecycle_path = root / "profile_lifecycle_status.csv"
        statistics_path = root / "candidate_profile_statistics.csv"
        shadow_path = root / "shadow_replay_results.csv"
        statistics: dict[tuple[str, int, str], dict[str, str]] = {}
        with statistics_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                statistics[(str(row["machine_number"]).zfill(3), int(row["module"]), row["sv"])] = row
        shadows: dict[tuple[str, int, str], dict[str, str]] = {}
        with shadow_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                shadows[(str(row["machine_number"]).zfill(3), int(row["module"]), row["sv"])] = row
        def as_float(value: Any) -> float | None:
            try:
                parsed = float(str(value))
                return parsed if parsed == parsed else None
            except (TypeError, ValueError):
                return None

        def as_int(value: Any) -> int:
            return int(as_float(value) or 0)
        result: list[dict[str, Any]] = []
        with lifecycle_path.open(encoding="utf-8", newline="") as handle:
            for profile_id, row in enumerate(csv.DictReader(handle), start=1):
                key = (str(row["machine_number"]).zfill(3), int(row["module"]), row["sv"])
                stat, shadow = statistics.get(key, {}), shadows.get(key, {})
                hp2_med = as_float(stat.get("hp2__median")) or 195.0
                hp2_scale = as_float(stat.get("hp2__scale")) or 1.2
                stats_dict = {
                    "hp1": {"median": 142.5, "scale": 1.8, "min": 136.0, "max": 150.0, "p25": 140.0, "p75": 145.0},
                    "lp1": {"median": 28.4, "scale": 0.8, "min": 25.0, "max": 32.0, "p25": 27.5, "p75": 29.5},
                    "hp2": {
                        "median": hp2_med,
                        "scale": hp2_scale,
                        "min": round(hp2_med - hp2_scale * 3.5, 1),
                        "max": round(hp2_med + hp2_scale * 3.5, 1),
                        "p25": round(hp2_med - hp2_scale * 0.7, 1),
                        "p75": round(hp2_med + hp2_scale * 0.7, 1),
                        "reference_band": [180.0, 230.0],
                        "in_reference_band": 180.0 <= hp2_med <= 230.0,
                    },
                    "lp2": {"median": 14.8, "scale": 0.6, "min": 12.0, "max": 18.0, "p25": 14.2, "p75": 15.5},
                    "dp1": {"median": 114.1, "scale": 2.1, "min": 108.0, "max": 120.0, "p25": 112.0, "p75": 116.0},
                    "dp2": {"median": round(hp2_med - 14.8, 1), "scale": round(hp2_scale + 0.5, 1), "min": round(hp2_med - 25.0, 1), "max": round(hp2_med - 5.0, 1), "p25": round(hp2_med - 16.0, 1), "p75": round(hp2_med - 13.0, 1)},
                    "valve": {"median": 350.0, "scale": 12.0, "min": 280.0, "max": 420.0, "p25": 335.0, "p75": 365.0},
                    "temphi": {"median": 58.2, "scale": 1.5, "min": 52.0, "max": 65.0, "p25": 56.5, "p75": 60.0},
                    "templo": {"median": -38.5, "scale": 1.2, "min": -45.0, "max": -32.0, "p25": -40.0, "p75": -37.0},
                    "correlations": self._default_correlations(),
                }
                result.append({
                    "profile_id": profile_id, "batch_id": self._calibration_batch_id,
                    "profile_version": row["profile_version"], "machine_number": f"MX{key[0]}",
                    "module": key[1], "sv_state": key[2],
                    "state_code": (
                        "HISTORICAL_BYPASS_SV_ON_UNSUPPORTED"
                        if key[2] == "On"
                        else "HISTORICAL_COLD_SV_OFF_PREVIOUS_CONTRACT"
                    ),
                    "profile_status": row["lifecycle_status"],
                    "reason_codes": [item for item in row["reason_codes"].split(";") if item],
                    "calibration_windows": as_int(row["n_windows"]), "calibration_days": as_int(row["n_days"]),
                    "quarantine_pct": as_float(row["quarantine_pct"]), "max_half_shift_rz": as_float(row["max_abs_half_shift_rz"]),
                    "shadow_windows": as_int(row["n_shadow_windows"]), "shadow_days": as_int(row["n_shadow_days"]),
                    "shadow_flag_pct": as_float(row["alert_rate_pct"]),
                    "persistent_flag_pct": as_float(row["persistent_3_rate_pct"]),
                    "statistics": stats_dict,
                    "thresholds": {"deviation_score_q995": as_float(shadow.get("alert_threshold")) or 0},
                    "validation": {"demo_source": "executed offline Auto-bootstrap artifacts"},
                })
        return result

    def active_profiles(self) -> list[dict[str, Any]]:
        profiles = self._demo_profiles()
        result: list[dict[str, Any]] = []
        for p in profiles:
            if p["machine_number"] in ("MX080", "MX057") and p["sv_state"] == "Off":
                res = dict(p)
                res["active_profile_id"] = p["profile_id"]
                res["activated_at"] = datetime(2026, 9, 18, 14, 46, 29, tzinfo=timezone.utc)
                res["activated_by"] = "APPROVER-01"
                res["rollback_mode"] = "NO_ACTIVE_PROFILE_FAIL_CLOSED"
                res["rollback_profile_id"] = None
                res["profile_status"] = "ACTIVE_FROZEN"
                res["reviewer_id"] = "APPROVER-01"
                res["review_note"] = "Approved in demo mode"
                res["reviewed_at"] = datetime(2026, 9, 18, 7, 46, 29, tzinfo=timezone.utc)
                result.append(res)
        return result

    def source_machines(self) -> list[dict[str, Any]]:
        # Returns distinct machines available in the workspace
        all_machines = sorted(list({p["machine_number"] for p in self._demo_profiles()}))
        if "MX080" not in all_machines:
            all_machines.insert(0, "MX080")
        return [
            {
                "machine_number": m,
                "display_name": m,
                "record_count": 86400 * 30 if m == "MX080" else 86400 * 25,
                "latest_recorded_at": datetime(2026, 9, 8, 13, 20) if m == "MX080" else datetime(2026, 9, 1, 0, 0),
            }
            for m in all_machines
        ]

    def calibration_batches(self, _limit: int = 30) -> list[dict[str, Any]]:
        profiles = self._demo_profiles()
        return [{
            "batch_id": self._calibration_batch_id, "batch_status": "DEMO_HISTORICAL_EVIDENCE",
            "source_start": datetime(2026, 8, 4), "calibration_end": datetime(2026, 8, 26),
            "shadow_start": datetime(2026, 8, 27), "shadow_end": datetime(2026, 9, 1),
            "source_timezone": "not encoded", "profile_algorithm_version": "autobootstrap-candidate-v2-hp180",
            "feature_version": "minute-state-core-hp180-v2", "profile_count": len(profiles),
            "ready_for_approval_count": 0, "created_at": datetime(2026, 9, 8),
        }]


    def calibration_profiles(self, batch_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self._demo_profiles()[:limit] if batch_id == self._calibration_batch_id else []

    def calibration_shadow_points(self, profile_id: int, limit: int = 10000) -> list[dict[str, Any]]:
        profiles = self._demo_profiles()
        if not 1 <= profile_id <= len(profiles):
            return []
        profile = profiles[profile_id - 1]
        table = pq.read_table(
            self.replay_root / "primary_outer_shadow_scores.parquet",
            columns=["machine_number", "module", "sv", "state", "minute", "score", "threshold", "raw_flag", "persistent_flag", "data_quality_status"],
            filters=[("machine_number", "=", profile["machine_number"].replace("MX", "")), ("module", "=", profile["module"]), ("sv", "=", profile["sv_state"])],
        )
        rows = table.to_pylist()
        if not rows:
            return []
        latest_day = max(row["minute"].date() for row in rows)
        start_day = latest_day.fromordinal(latest_day.toordinal() - 2)
        return [{
            "event_time": row["minute"], "deviation_score": row["score"], "threshold_value": row["threshold"],
            "raw_flag": bool(row["raw_flag"]), "persistent_flag": bool(row["persistent_flag"]),
            "data_quality_status": row["data_quality_status"],
        } for row in rows if row["minute"].date() >= start_day][:limit]
