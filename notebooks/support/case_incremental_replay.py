"""Confirmed-case regression and five-minute delivery rehearsal, without DB writes."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from apps.api.app.config import Settings
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows
from apps.api.app.qualified_calibration import THRESHOLD_VERSION
from apps.api.app.qualified_scoring import ApprovedProfile, QualifiedShadowScorer
from apps.api.app.qualified_stream import CompletedMinuteStream
from apps.api.app.qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, WindowPolicy, build_completed_windows
from notebooks.support.mx057_m1_shadow_diagnostic import _windows, _source_files
from notebooks.support.qualified_1m_parquet_replay import SOURCE_TAGS, _machine_code


ZONE = ZoneInfo("Asia/Bangkok")
MX080_SOURCE = Path("notebooks/outputs/mx080_module6_forensics_v1/module6_one_second_unique.parquet")


def rows057(root, start, end):
    fields = ["recorded_at", "machine_number", "Status"] + [f"{tag}_{m}" for m in (1, 6) for tag in SOURCE_TAGS]
    for day in pd.date_range(start.date(), (end-timedelta(seconds=1)).date()):
        for path in _source_files(root, day.date()):
            for batch in pq.ParquetFile(path).iter_batches(batch_size=8192, columns=fields):
                for row in batch.to_pylist():
                    if _machine_code(row["machine_number"]) != "057":
                        raise ValueError("mixed machine source")
                    row["machine_number"] = "MX057"
                    if start <= row["recorded_at"] < end:
                        yield row


def rows080(start, end):
    fields = ["timestamp", "Status"] + [f"{tag}_6" for tag in SOURCE_TAGS]
    for batch in pq.ParquetFile(MX080_SOURCE).iter_batches(batch_size=8192, columns=fields):
        for row in batch.to_pylist():
            stamp = row.pop("timestamp")
            if start <= stamp < end:
                yield {**row, "recorded_at": stamp.to_pydatetime() if isinstance(stamp, pd.Timestamp) else stamp,
                       "machine_number": "MX080"}


def candidate(windows, machine, module, start, shadow, end):
    c = registry_candidate_from_windows(windows, settings=Settings(source_timezone="Asia/Bangkok",
        source_pressure_unit="", profile_state_contract_version="", profile_controller_codebook_version="",
        profile_service_epoch_version="", profile_min_calibration_days=7,
        profile_min_calibration_windows=200, profile_shadow_days=3, profile_min_shadow_windows=200,
        profile_quarantine_z=8.0, profile_max_quarantine_pct=5.0,
        profile_max_half_shift_rz=1.5, profile_max_shadow_flag_pct=1.0), machine_number=machine, module=module,
        calibration_start=start, shadow_start=shadow, shadow_end=end)
    exact = c["statistics"]["exact_baseline"]
    p = ApprovedProfile(1, "CASE_REPLAY_IN_MEMORY", WINDOW_VERSION, machine, module, "Off", STATE_CODE,
        {f: exact[f]["median"] for f in FEATURES}, {f: exact[f]["scale"] for f in FEATURES},
        c["threshold"]["deviation_score_q995"], THRESHOLD_VERSION, shadow)
    return c, p


def audit(rows, windows, profile, start, end, case_start, case_end, output):
    expected_windows = {(w.module, w.window_start): w for w in windows if start <= w.window_start < end}
    reference_scorer = QualifiedShadowScorer()
    expected = {key: reference_scorer.score(w, profile) for key,w in sorted(expected_windows.items(), key=lambda x:x[0][1])}
    stream = CompletedMinuteStream(WindowPolicy("Asia/Bangkok", late_arrival_seconds=30), (profile.module,))
    scorer = QualifiedShadowScorer()
    actual = {}
    times = []
    arrivals = {}
    window_errors = score_errors = duplicate_errors = 0
    restarts = duplicate_batches = late_dropped = peak_pending = 0
    rows_seen = 0
    iterator = iter(rows)
    next_row = next(iterator, None)
    previous_stamp = None
    cycle_end = start + timedelta(minutes=5)
    cycles = 0
    def apply(batch, clock, token):
        nonlocal stream, scorer, window_errors, score_errors, duplicate_errors, duplicate_batches, restarts, peak_pending, late_dropped
        before = perf_counter()
        emitted, info = stream.consume(batch, as_of=clock.replace(tzinfo=ZONE), batch_id=token)
        peak_pending = max(peak_pending, len(stream.pending))
        for w in emitted:
            key = (w.module, w.window_start)
            window_errors += int(expected_windows.get(key) != w)
            result = scorer.score(w, profile)
            score_errors += int(expected.get(key) != result)
            if key in actual:
                duplicate_errors += 1
            actual[key] = result
            arrivals[key] = clock
            duplicate_errors += int(scorer.score(w, profile) != result)
        if cycles % 17 == 0:
            again, retry = stream.consume(batch, as_of=clock.replace(tzinfo=ZONE), batch_id=token)
            duplicate_errors += int(bool(again) or not retry["duplicate_batch"])
            duplicate_batches += 1
        if cycles % 25 == 0:
            stream = CompletedMinuteStream.from_checkpoint(json.loads(json.dumps(stream.checkpoint())))
            scorer = QualifiedShadowScorer.from_checkpoint(json.loads(json.dumps(scorer.checkpoint())), scorer.parameters)
            restarts += 1
        if batch and cycles == 3:
            stale, late = stream.consume([batch[0]], as_of=clock.replace(tzinfo=ZONE), batch_id=token+"-late-probe")
            late_dropped += late["late_rows_dropped"]
            duplicate_errors += int(bool(stale))
        times.append(perf_counter()-before)
    while cycle_end <= end:
        batch = []
        while next_row is not None and next_row["recorded_at"] < cycle_end:
            stamp = next_row["recorded_at"]
            if previous_stamp is not None and stamp < previous_stamp:
                raise ValueError("raw source is not chronologically ordered")
            previous_stamp = stamp
            batch.append(next_row)
            rows_seen += 1
            next_row = next(iterator, None)
        apply(batch, cycle_end, f"batch-{cycles}")
        cycles += 1
        cycle_end += timedelta(minutes=5)
    if next_row is not None:
        raise ValueError("source replay has unexpected remaining rows")
    apply([], end+timedelta(seconds=30), "final-grace-flush")
    missing = len(expected.keys()-actual.keys())
    unexpected = len(actual.keys()-expected.keys())
    records = []
    for key,result in sorted(actual.items(), key=lambda x:x[0][1]):
        records.append({"minute": result.window_start, "status": result.status, "reason": result.reason,
                        "score": result.primary_score, "threshold": profile.threshold,
                        "raw_flag": result.primary_raw_flag, "persistent_flag": result.primary_persistent_flag,
                        "dominant_feature": result.dominant_feature, "available_at": arrivals[key]})
    frame = pd.DataFrame(records)
    positive = frame[(frame.minute >= case_start) & (frame.minute < case_end)]
    qualified_positive = positive[positive.status.eq("SCORED")]
    pre_case = frame[(frame.minute < case_start) & frame.status.eq("SCORED")]
    detected = qualified_positive[qualified_positive.persistent_flag.eq(True)]
    first = detected.iloc[0] if len(detected) else None
    daily = []
    for day,g in frame.groupby(frame.minute.dt.date):
        good=g[g.status.eq("SCORED")]
        daily.append({"date":str(day), "scored_minutes":len(good),
            "raw_flags":int(good.raw_flag.eq(True).sum()), "persistent_minutes":int(good.persistent_flag.eq(True).sum())})
    frame.to_csv(output / f"{profile.machine_number}_m{profile.module}_minute_evidence.csv", index=False)
    summary = {"machine":profile.machine_number, "module":profile.module,
        "evaluation_start":str(start), "evaluation_end_exclusive":str(end),
        "profile_source":"PAST_ONLY_CANDIDATE_IN_MEMORY_NOT_ACTIVE", "raw_rows_replayed":rows_seen,
        "five_minute_cycles":cycles, "grace_seconds":30, "observed_windows":len(actual),
        "window_mismatches":window_errors, "score_evidence_mismatches":score_errors,
        "missing_windows":missing, "unexpected_windows":unexpected, "duplicate_errors":duplicate_errors,
        "duplicate_batches_tested":duplicate_batches, "checkpoint_restarts":restarts,
        "late_after_close_rows_dropped":late_dropped, "peak_pending_source_rows":peak_pending,
        "cycle_processing_ms":{"p50":round(float(np.quantile(times,.5))*1000,3),
                               "p95":round(float(np.quantile(times,.95))*1000,3),
                               "max":round(max(times)*1000,3)},
        "timing_scope":"window construction + scoring + retry/checkpoint probes; source decoding excluded",
        "scored_minutes":int(frame.status.eq("SCORED").sum()), "daily":daily,
        "before_confirmed_interval":{"scored_minutes":len(pre_case),
            "raw_flags":int(pre_case.raw_flag.eq(True).sum()),
            "persistent_minutes":int(pre_case.persistent_flag.eq(True).sum()),
            "label_status":"not assumed normal or false-positive; interval labels are separate"},
        "not_scored_reasons":dict(Counter(frame.loc[~frame.status.eq("SCORED"),"reason"])),
        "confirmed_case":{"start":str(case_start), "end_exclusive":str(case_end),
            "qualified_minutes":len(qualified_positive), "raw_flags":int(qualified_positive.raw_flag.eq(True).sum()),
            "persistent_minutes":len(detected),
            "first_persistent_window":str(first.minute) if first is not None else None,
            "first_persistent_available_at":str(first.available_at) if first is not None else None},
        "parity_pass":not any((window_errors,score_errors,missing,unexpected,duplicate_errors)),
        "database_writes":0}
    return summary,frame


def plot(frames, output):
    fig, axes = plt.subplots(2,1,figsize=(14,8),layout="constrained")
    for ax,(summary,frame) in zip(axes,frames):
        day=pd.Timestamp(summary["confirmed_case"]["start"]).normalize()
        g=frame[(frame.minute>=day)&(frame.minute<day+pd.Timedelta(days=1))].set_index("minute")
        g=g.reindex(pd.date_range(day,day+pd.Timedelta(days=1)-pd.Timedelta(minutes=1),freq="min"))
        ax.plot(g.index,g.score/g.threshold,color="#1769aa",lw=1.2,label="5-minute delivery • 1-minute scores")
        ax.axhline(1,color="#bf3d39",ls="--",lw=1,label="flag boundary")
        ax.axvspan(pd.Timestamp(summary["confirmed_case"]["start"]),pd.Timestamp(summary["confirmed_case"]["end_exclusive"]),color="#bf3d39",alpha=.09,label="owner-confirmed case")
        first=summary["confirmed_case"]["first_persistent_window"]
        if first:
            ax.axvline(pd.Timestamp(first),color="#16847a",ls=":",label="first persistent window in case")
        ax.set_title(f"{summary['machine']} / M{summary['module']} | {day:%d %b %Y} | batch/restart parity: {'PASS' if summary['parity_pass'] else 'FAIL'}",loc="left")
        ax.set_ylabel("score / own threshold")
        ax.grid(axis="y",alpha=.2)
        ax.legend(loc="upper left",fontsize=8,ncol=2,frameon=False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.suptitle("Confirmed cases | qualified 1-minute scoring in 5-minute delivery cycles",fontsize=15,weight="bold")
    fig.supxlabel("Source clock • Asia/Bangkok assumed; profiles are offline candidates, not Active")
    fig.savefig(output / "case_incremental_timeline.png",dpi=170,bbox_inches="tight")
    plt.close(fig)


def verify_report(results):
    for item in results["runs"]:
        if not item["parity_pass"]:
            raise AssertionError(f"incremental parity failed for {item['machine']}")
        case=item["confirmed_case"]
        if not case["qualified_minutes"] or case["raw_flags"] != case["qualified_minutes"] or not case["persistent_minutes"]:
            raise AssertionError(f"confirmed case regression failed for {item['machine']}")
    mx57=next(r for r in results["runs"] if r["machine"]=="MX057")
    aug27=next(d for d in mx57["daily"] if d["date"]=="2026-08-27")
    if aug27["raw_flags"] != 0:
        raise AssertionError("MX057/M1 27 Aug historical zero-flag regression changed")
    return "CASE_AND_INCREMENTAL_REGRESSION_PASS"


def run(root, output):
    output.mkdir(parents=True, exist_ok=True)
    began=perf_counter()
    w57,total57=_windows(root)
    c57,p57=candidate(w57,"MX057",1,datetime(2026,8,20),datetime(2026,8,27),datetime(2026,8,30))
    s57,f57=audit(rows057(root,datetime(2026,8,27),datetime(2026,8,30)),[w for w in w57 if w.module==1],p57,
        datetime(2026,8,27),datetime(2026,8,30),datetime(2026,8,29,4,6),datetime(2026,8,29,22,50),output)
    w80=[]
    for day in pd.date_range("2026-09-03","2026-09-07"):
        start=day.to_pydatetime(); end=start+timedelta(days=1)
        w80+=build_completed_windows(rows080(start,end),as_of=end.replace(tzinfo=ZONE),policy=WindowPolicy("Asia/Bangkok"),modules=(6,))
    c80,p80=candidate(w80,"MX080",6,datetime(2026,9,3),datetime(2026,9,7),datetime(2026,9,8))
    s80,f80=audit(rows080(datetime(2026,9,7),datetime(2026,9,8)),w80,p80,
        datetime(2026,9,7),datetime(2026,9,8),datetime(2026,9,7,12,23,28),datetime(2026,9,8),output)
    for summary,c in ((s57,c57),(s80,c80)):
        summary.update({"candidate_status":c["status"],"candidate_reasons":c["reasons"],
            "calibration_days":int(c["calibration"].day.nunique()),
            "threshold":c["threshold"]["deviation_score_q995"]})
    plot([(s57,f57),(s80,f80)],output)
    results={"source_timezone_assumption":"Asia/Bangkok", "source_pressure_unit_verified":False,
        "runs":[s57,s80], "total_seconds":round(perf_counter()-began,3),
        "mx080_reference_limitation":"Only four past days and one evaluation day; not a seven-day calibration / three-day shadow or an Active Profile",
        "database_writes":0}
    results["regression_status"]=verify_report(results)
    (output/"summary.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(results,indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--raw-root",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("notebooks/outputs/case_incremental_replay_v1"))
    a=p.parse_args(); run(a.raw_root,a.output)
