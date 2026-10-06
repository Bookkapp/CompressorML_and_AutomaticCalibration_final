"""Read-only, no-alert preview of the qualified one-minute scorer.

This command intentionally does not write analytics/PM/source tables. A legacy
minute-snapshot or five-minute profile cannot substitute for this exact
observed-second → one-minute feature contract, even if ACTIVE_FROZEN.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text

from .config import Settings, get_settings
from .db import get_engine
from .inference import clean_machine_code, get_machine_candidates
from .qualified_calibration import THRESHOLD_VERSION, load_observed_one_minute_windows
from .qualified_policy import LEGACY_THRESHOLD_VERSION, manifest
from .qualified_scoring import ApprovedProfile, QualifiedShadowScorer, ScoreEvidence
from .qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION


def load_matching_active_profiles(settings: Settings, machine_number: str, *, engine=None) -> dict[tuple[str, int], ApprovedProfile]:
    """Load only exact-version, human-reviewed one-minute Cold profiles."""
    engine = engine if engine is not None else get_engine()
    if engine is None:
        return {}
    query = text("""
        SELECT a.machine_number, a.module, a.sv_state, a.state_code, a.active_profile_id,
               p.profile_version, p.statistics_json, p.threshold_json,
               p.profile_status, p.reviewed_at, p.reviewer_id, p.calibration_end,
               p.calibration_days, p.calibration_windows, p.shadow_days, p.shadow_windows,
               p.shadow_flag_pct, p.reason_codes, p.validation_json,
               b.feature_version, b.source_timezone
        FROM ht9046mx_active_calibration_profile a
        JOIN ht9046mx_calibration_profile p ON p.profile_id = a.active_profile_id
        JOIN ht9046mx_calibration_batch b ON b.batch_id = p.batch_id
        WHERE a.machine_number IN :machines AND a.sv_state = 'Off'
          AND a.state_code = :state AND p.profile_status = 'ACTIVE_FROZEN'
          AND p.reviewed_at IS NOT NULL AND p.reviewer_id IS NOT NULL
          AND b.feature_version = :feature_version
    """).bindparams(bindparam("machines", expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(query, {"machines": get_machine_candidates(machine_number),
                                    "state": STATE_CODE, "feature_version": WINDOW_VERSION}).mappings().all()
    result: dict[tuple[str, int], ApprovedProfile] = {}
    ambiguous: set[tuple[str, int]] = set()
    for row in rows:
        try:
            stats = json.loads(row["statistics_json"])
            threshold_json = json.loads(row["threshold_json"])
            validation = json.loads(row["validation_json"])
            reasons = json.loads(row["reason_codes"])
            calibration_days = int(row["calibration_days"] or 0)
            calibration_windows = int(row["calibration_windows"] or 0)
            shadow_days = int(row["shadow_days"] or 0)
            shadow_windows = int(row["shadow_windows"] or 0)
            shadow_flag_pct = float(row["shadow_flag_pct"]) if row["shadow_flag_pct"] is not None else float("nan")
        except (ValueError, TypeError):
            continue
        if not all(isinstance(x, dict) for x in (stats, threshold_json, validation)):
            continue
        try:
            if (float(validation.get("shadow_elapsed_hours", 0)) < 71.95
                    or int(validation.get("expected_shadow_minutes", 0)) < 4320
                    or not .95 <= float(validation.get("observed_shadow_coverage", 0)) <= 1.):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        if (reasons != [] or not str(row["reviewer_id"]).strip() or row["calibration_end"] is None
                or row["source_timezone"] != settings.source_timezone or not settings.source_timezone
                or calibration_days < settings.profile_min_calibration_days
                or calibration_windows < settings.profile_min_calibration_windows
                or shadow_days < 3
                or shadow_windows < settings.profile_min_shadow_windows
                or not math.isfinite(shadow_flag_pct) or shadow_flag_pct < 0
                or shadow_flag_pct > settings.profile_max_shadow_flag_pct
                or validation.get("source_pressure_unit") != settings.source_pressure_unit
                or not settings.source_pressure_unit):
            continue
        exact = stats.get("exact_baseline")
        if not isinstance(exact, dict) or set(exact) != set(FEATURES):
            continue
        if (threshold_json.get("method") != "qualified_1m_retained_calibration_q995"
                or threshold_json.get("threshold_version") not in (LEGACY_THRESHOLD_VERSION, THRESHOLD_VERSION)):
            continue
        if threshold_json.get("threshold_version") == THRESHOLD_VERSION and (
                threshold_json.get("scoring_policy") != manifest() or stats.get("scoring_policy") != manifest()):
            continue
        try:
            numeric = [float(exact[f]["median"]) for f in FEATURES]
            scales = [float(exact[f]["scale"]) for f in FEATURES]
            threshold = float(threshold_json["deviation_score_q995"])
            if not all(math.isfinite(x) for x in numeric+scales+[threshold]) or min(scales+[threshold]) <= 0:
                continue
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        canonical = clean_machine_code(row["machine_number"])
        if canonical == "MX777" or str(row["reviewer_id"]).upper().startswith("MOCK"):
            continue  # localhost transport fixture is never a real approval
        key = (canonical, int(row["module"]))
        if key in result:
            ambiguous.add(key)
            continue
        result[key] = ApprovedProfile(
            profile_id=int(row["active_profile_id"]), profile_version=str(row["profile_version"]),
            feature_version=str(row["feature_version"]), machine_number=canonical,
            module=int(row["module"]), sv_state=str(row["sv_state"]), state_code=str(row["state_code"]),
            medians={f: float(exact[f]["median"]) for f in FEATURES},
            scales={f: float(exact[f]["scale"]) for f in FEATURES},
            threshold=float(threshold_json["deviation_score_q995"]),
            threshold_version=str(threshold_json["threshold_version"]),
            profile_fit_end=row["calibration_end"],
        )
    for key in ambiguous:
        result.pop(key, None)
    return result


def run_read_only_preview(settings: Settings, *, machine_number: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Report eligibility/score counts; never create a primary or temporal alert."""
    windows = load_observed_one_minute_windows(settings, machine_number=machine_number, start=start, end=end)
    profiles = load_matching_active_profiles(settings, machine_number)
    scorer = QualifiedShadowScorer()
    evidence: list[ScoreEvidence] = [
        scorer.score(window, profiles.get((window.machine_number, window.module)))
        for window in sorted(windows, key=lambda w: (w.window_start, w.machine_number, w.module))
    ]
    reasons = Counter(item.reason for item in evidence if item.status != "SCORED")
    return {
        "mode": "READ_ONLY_SHADOW_PREVIEW", "machine_number": machine_number,
        "input_start": start.isoformat(), "input_end": end.isoformat(),
        "source_timezone_config": settings.source_timezone,
        "feature_version": WINDOW_VERSION,
        "observed_module_windows": len(windows),
        "qualified_module_windows": sum(window.eligible for window in windows),
        "matching_active_1m_profiles": len(profiles),
        "scored_module_windows": sum(item.status == "SCORED" for item in evidence),
        "primary_raw_flags": sum(item.primary_raw_flag is True for item in evidence),
        "primary_persistent_windows": sum(item.primary_persistent_flag is True for item in evidence),
        "not_scored_reasons": dict(sorted(reasons.items())),
        "temporal_flags_calibrated": False,
        "database_writes": 0, "pm_alerts_created": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only qualified one-minute shadow preview")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--start", required=True, help="ISO 8601 with timezone offset")
    parser.add_argument("--end", required=True, help="ISO 8601 with timezone offset")
    args = parser.parse_args()
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    result = run_read_only_preview(get_settings(), machine_number=args.machine, start=start, end=end)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
