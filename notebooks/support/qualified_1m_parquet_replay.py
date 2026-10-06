"""Read-only raw-Parquet exercise of the production candidate's 1-minute contract.

Example:
python -m notebooks.support.qualified_1m_parquet_replay --raw-root PATH \
  --machine 057 --module 6 --start-date 2026-08-20 --days 10

The last three calendar days are shadow-only. This script neither writes a
database nor approves a profile. Source timestamps are interpreted in the
explicitly supplied timezone; that assumption is not source-owner verification.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from apps.api.app.config import Settings
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows
from apps.api.app.qualified_policy import LEGACY_THRESHOLD_VERSION
from apps.api.app.qualified_scoring import ApprovedProfile, QualifiedShadowScorer
from apps.api.app.qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, build_completed_windows, WindowPolicy


SOURCE_TAGS = ("Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "Valve",
               "Status", "Busy", "SV", "TempHi", "TempLo")


def _machine_code(value: object) -> str:
    token = str(value).strip().upper()
    if token.startswith("HT9046MX-"):
        token = token.removeprefix("HT9046MX-")
    elif token.startswith("MX"):
        token = token.removeprefix("MX")
    if not token.isdecimal() or not 1 <= int(token) <= 999:
        raise ValueError(f"invalid machine_number: {value!r}")
    return token.zfill(3)


def _peak_memory_mb() -> float | None:
    try:
        import psutil
        info = psutil.Process().memory_info()
        return round(getattr(info, "peak_wset", info.rss) / 1024**2, 1)
    except ImportError:
        return None


def _replay_candidate(windows, candidate, shadow_start: datetime) -> dict:
    """Local-only shadow/scorer parity check with a synthetic in-memory ID."""
    exact = candidate["statistics"].get("exact_baseline", {})
    threshold = candidate["threshold"].get("deviation_score_q995")
    if set(exact) != set(FEATURES) or threshold is None or threshold <= 0:
        return {"status": "NOT_RUN_NO_VALID_CANDIDATE", "scored_windows": 0}
    key = candidate["key"]
    profile = ApprovedProfile(
        profile_id=1, profile_version="LOCAL_REHEARSAL_IN_MEMORY",
        feature_version=WINDOW_VERSION, machine_number=key["machine_number"],
        module=key["module"], sv_state="Off", state_code=STATE_CODE,
        medians={feature: exact[feature]["median"] for feature in FEATURES},
        scales={feature: exact[feature]["scale"] for feature in FEATURES},
        threshold=float(threshold), threshold_version=candidate["threshold"].get("threshold_version", LEGACY_THRESHOLD_VERSION),
        profile_fit_end=shadow_start,
    )
    expected = {row.minute: row for row in candidate["shadow"].itertuples()}
    expected_scored = {minute for minute, row in expected.items()
                       if row.data_quality_status == "PASS"}
    shadow_windows = sorted((w for w in windows if w.window_start >= shadow_start),
                            key=lambda w: w.window_start)
    scorer = QualifiedShadowScorer()
    scored = raw_flags = persistent = mismatches = 0
    actual_scored = set()
    abstentions = Counter()
    dominant_flag_features = Counter()
    one_shot_evidence = []
    for window in shadow_windows:
        evidence = scorer.score(window, profile)
        one_shot_evidence.append(evidence)
        if evidence.status != "SCORED":
            abstentions[evidence.reason] += 1
            continue
        scored += 1
        actual_scored.add(window.window_start)
        raw_flags += int(evidence.primary_raw_flag is True)
        persistent += int(evidence.primary_persistent_flag is True)
        if evidence.primary_raw_flag and evidence.dominant_feature:
            dominant_flag_features[evidence.dominant_feature] += 1
        point = expected.get(window.window_start)
        if (point is None or point.data_quality_status != "PASS"
                or abs(evidence.primary_score - point.deviation_score) > 1e-8
                or evidence.primary_raw_flag != point.raw_flag
                or evidence.primary_persistent_flag != point.persistent_flag):
            mismatches += 1
    missing_scored = len(expected_scored - actual_scored)
    unexpected_scored = len(actual_scored - expected_scored)
    mismatches += missing_scored + unexpected_scored
    restarted = QualifiedShadowScorer()
    restart_mismatches = 0
    midpoint = len(shadow_windows) // 2
    for index, (window, reference) in enumerate(zip(shadow_windows, one_shot_evidence)):
        if index == midpoint:
            checkpoint = json.loads(json.dumps(restarted.checkpoint()))
            restarted = QualifiedShadowScorer.from_checkpoint(checkpoint, restarted.parameters)
        restart_mismatches += int(restarted.score(window, profile) != reference)
    return {
        "status": "PARITY_PASS" if mismatches == 0 and restart_mismatches == 0 else "PARITY_MISMATCH",
        "profile_source": "LOCAL_CANDIDATE_IN_MEMORY_NOT_ACTIVE",
        "scored_windows": scored, "raw_flags": raw_flags,
        "persistent_minutes": persistent, "mismatched_windows": mismatches,
        "expected_scored_windows": len(expected_scored),
        "missing_scored_windows": missing_scored,
        "unexpected_scored_windows": unexpected_scored,
        "restart_checkpoint_mismatches": restart_mismatches,
        "dominant_features_on_raw_flags": dict(sorted(dominant_flag_features.items())),
        "not_scored_reasons": dict(sorted(abstentions.items())),
    }


def run(raw_root: Path, machine: str, module: int, start_date: date,
        days: int, source_timezone: str, score_rehearsal: bool = False) -> dict:
    batch = run_many(raw_root, machine, (module,), start_date, days,
                     source_timezone, score_rehearsal=score_rehearsal)
    item = batch.pop("module_results")[0]
    batch.pop("modules")
    return {**batch, **item}


def run_many(raw_root: Path, machine: str, modules: tuple[int, ...], start_date: date,
             days: int, source_timezone: str, *, score_rehearsal: bool = False) -> dict:
    if days < 10 or not modules or len(set(modules)) != len(modules) or any(m not in range(1, 9) for m in modules):
        raise ValueError("require at least 7 calibration + 3 shadow days and unique modules 1..8")
    started = perf_counter()
    zone = ZoneInfo(source_timezone)
    machine = _machine_code(machine)
    canonical = f"MX{machine}"
    fields = ["recorded_at", "machine_number", "Status"]
    fields.extend(f"{tag}_{module}" for module in modules for tag in SOURCE_TAGS)
    windows = []
    raw_rows = 0
    source_files = []
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        folder = (raw_root / f"machine={machine}" / f"year={current.year}"
                  / f"month={current.month:02d}" / f"day={current.day:02d}")
        paths = sorted(folder.glob("*.parquet"))
        if not paths:
            raise FileNotFoundError(f"no raw day partition: {folder}")
        def rows_for_day():
            nonlocal raw_rows
            for path in paths:
                source_files.append(str(path))
                parquet = pq.ParquetFile(path)
                for batch in parquet.iter_batches(batch_size=8192, columns=fields):
                    raw_rows += batch.num_rows
                    for row in batch.to_pylist():
                        if _machine_code(row.get("machine_number")) != machine:
                            raise ValueError(f"source machine does not match partition: {path}")
                        row["machine_number"] = canonical
                        yield row
        day_end = datetime.combine(current + timedelta(days=1), time(), tzinfo=zone)
        windows.extend(build_completed_windows(
            rows_for_day(), as_of=day_end, policy=WindowPolicy(source_timezone), modules=modules,
        ))
    intake_seconds = perf_counter() - started
    start = datetime.combine(start_date, time())
    end = start + timedelta(days=days)
    shadow_start = end - timedelta(days=3)
    # Leave all operational prerequisites unverified in this offline exercise.
    settings = Settings(source_timezone=source_timezone, source_pressure_unit="",
                        profile_state_contract_version="",
                        profile_controller_codebook_version="",
                        profile_service_epoch_version="")
    module_results = []
    for module in modules:
        selected = [window for window in windows if window.module == module]
        candidate = registry_candidate_from_windows(
            selected, settings=settings, machine_number=canonical, module=module,
            calibration_start=start, shadow_start=shadow_start, shadow_end=end,
        )
        validation = candidate["validation"]
        shadow = candidate["shadow"]
        shadow_daily = []
        for day, points in shadow.groupby(shadow["minute"].dt.date, sort=True):
            eligible = int((points["data_quality_status"] == "PASS").sum())
            flagged = int(points["raw_flag"].sum())
            shadow_daily.append({
                "date": day.isoformat(), "eligible_minutes": eligible,
                "raw_flags": flagged,
                "persistent_minutes": int(points["persistent_flag"].sum()),
                "flag_pct_eligible": round(100 * flagged / eligible, 3) if eligible else None,
            })
        module_result = {
            "module": module,
            "observed_windows": len(selected),
            "qualified_windows": sum(window.eligible for window in selected),
            "not_qualified_reasons": dict(sorted(Counter(w.reason for w in selected if not w.eligible).items())),
            "feature_version": candidate["feature_version"],
            "candidate_status": candidate["status"], "reason_codes": candidate["reasons"],
            "calibration_windows": len(candidate["calibration"]),
            "calibration_days": int(candidate["calibration"]["day"].nunique()),
            "shadow_observed_windows": validation["observed_shadow_windows"],
            "shadow_missing_source_minutes": int((shadow["data_quality_status"] == "NO_SOURCE_ROWS").sum()),
            "shadow_qualified_windows": validation["eligible_shadow_windows"],
            "shadow_raw_flags": int(shadow["raw_flag"].sum()) if len(shadow) else 0,
            "shadow_persistent_minutes": int(shadow["persistent_flag"].sum()) if len(shadow) else 0,
            "shadow_flag_pct_qualified": validation["shadow_flag_pct"],
            "shadow_daily": shadow_daily,
            "threshold": candidate["threshold"]["deviation_score_q995"],
            "exact_hp2_median": candidate["statistics"].get("exact_baseline", {}).get("hp2", {}).get("median"),
            "exact_hp2_scale": candidate["statistics"].get("exact_baseline", {}).get("hp2", {}).get("scale"),
            "active_profile_created": False, "database_writes": 0, "alerts_created": 0,
        }
        if score_rehearsal:
            module_result["local_score_rehearsal"] = _replay_candidate(selected, candidate, shadow_start)
        module_results.append(module_result)
    return {
        "machine_number": canonical, "modules": list(modules),
        "source_files": len(source_files), "raw_rows": raw_rows,
        "input_start": start.isoformat(), "input_end_exclusive": end.isoformat(),
        "source_timezone_assumption": source_timezone,
        "timing_seconds": {"intake_and_windows": round(intake_seconds, 3),
                           "candidate_and_replay": round(perf_counter() - started - intake_seconds, 3),
                           "total": round(perf_counter() - started, 3)},
        "peak_working_set_mb": _peak_memory_mb(),
        "module_results": module_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--machine", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--module", type=int)
    group.add_argument("--modules", help="comma-separated module numbers; reads each raw day once")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--source-timezone", default="Asia/Bangkok")
    parser.add_argument("--score-rehearsal", action="store_true",
                        help="score the candidate's future shadow in memory and check flag parity")
    args = parser.parse_args()
    modules = tuple(int(value.strip()) for value in args.modules.split(",")) if args.modules else (args.module,)
    result = (run(args.raw_root, args.machine, modules[0], args.start_date,
                  args.days, args.source_timezone, args.score_rehearsal)
              if len(modules) == 1 else
              run_many(args.raw_root, args.machine, modules, args.start_date,
                       args.days, args.source_timezone, score_rehearsal=args.score_rehearsal))
    print(json.dumps(result,
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
