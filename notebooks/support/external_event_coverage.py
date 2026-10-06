"""Read-only clean ChangeValve coverage scan for external canonical one-second data.

This is a coverage audit, not response profiling, model fitting, baseline approval,
or fault detection.  It deliberately reuses the clean-window semantics from the
existing one-second notebook so the primary and external evidence are comparable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

PRE_SECONDS, POST_SECONDS, MIN_VALVE_STEP = 30, 120, 3


def scan_event_coverage(input_root: Path, output_root: Path) -> dict:
    input_root, output_root = Path(input_root), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    files = sorted(input_root.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No canonical Parquet files under {input_root}")

    selected = ["machine_number", "recorded_at", "Status"]
    for module in range(1, 9):
        selected += [f"Valve_{module}", f"Status_{module}", f"SV_{module}"]
    rows, cadence = [], {"positive_intervals": 0, "exact_1s": 0, "two_seconds": 0, "gt_2s": 0,
                          "candidate_starts": 0, "boundary_rejected": 0}

    for file_index, path in enumerate(files, 1):
        raw = pl.read_parquet(path, columns=selected).sort("recorded_at")
        if raw.is_empty():
            continue
        machine = str(raw["machine_number"][0]).zfill(3)
        timestamps = raw["recorded_at"].to_numpy()
        deltas = (np.diff(timestamps) / np.timedelta64(1, "s")).astype(float)
        positive = deltas[deltas > 0]
        cadence["positive_intervals"] += len(positive)
        cadence["exact_1s"] += int(np.isclose(positive, 1.0).sum())
        cadence["two_seconds"] += int(np.isclose(positive, 2.0).sum())
        cadence["gt_2s"] += int((positive > 2.0).sum())
        global_run = raw["Status"].to_numpy() == "Run"

        for module in range(1, 9):
            state = raw[f"Status_{module}"].to_numpy()
            sv = raw[f"SV_{module}"].to_numpy()
            valve = raw[f"Valve_{module}"].to_numpy().astype(float)
            starts = np.flatnonzero((state == "ChangeValve") & np.r_[True, state[1:] != state[:-1]])
            cadence["candidate_starts"] += len(starts)
            for index in starts:
                if index < PRE_SECONDS or index + POST_SECONDS >= raw.height:
                    cadence["boundary_rejected"] += 1
                    continue
                window = slice(index - PRE_SECONDS, index + POST_SECONDS + 1)
                relative = ((timestamps[window] - timestamps[index]) / np.timedelta64(1, "s")).astype(float)
                if relative[0] > -27 or relative[-1] < 115 or global_run[window].mean() < .98:
                    continue
                if len(set(sv[window])) != 1 or np.any(np.isin(state[window], ["MValveHome", "Off"])):
                    continue
                if (state[index - 20:index] == "On").mean() < .90 or np.nanmin(valve[window]) < 0:
                    continue
                pre = float(np.nanmedian(valve[index - 20:index - 5]))
                post = float(np.nanmedian(valve[index + 10:index + 31]))
                step = post - pre
                if abs(step) < MIN_VALVE_STEP:
                    continue
                repeated = np.any((state[index + 1:index + POST_SECONDS + 1] == "ChangeValve") &
                                  (state[index:index + POST_SECONDS] != "ChangeValve"))
                if repeated:
                    continue
                rows.append({"machine_number": machine, "module": module, "sv": str(sv[index]),
                             "direction": "Opening" if step > 0 else "Closing", "event_at": timestamps[index],
                             "event_date": str(pd.Timestamp(timestamps[index]).date()), "valve_step": step,
                             "source_partition": path.name})
        if file_index % 50 == 0 or file_index == len(files):
            print(f"Coverage scan: {file_index}/{len(files)} partitions; clean events={len(rows):,}")

    events = pd.DataFrame(rows, columns=["machine_number", "module", "sv", "direction", "event_at", "event_date", "valve_step", "source_partition"])
    events.to_parquet(output_root / "external_clean_events.parquet", index=False)
    by_context = (events.groupby(["machine_number", "module", "sv", "direction"], dropna=False)
                  .agg(clean_events=("event_at", "size"), event_days=("event_date", "nunique"),
                       start=("event_at", "min"), end=("event_at", "max"))
                  .reset_index()) if len(events) else pd.DataFrame(columns=["machine_number", "module", "sv", "direction", "clean_events", "event_days", "start", "end"])
    grid = pd.MultiIndex.from_product([sorted({str(pl.read_parquet(f, columns=["machine_number"])["machine_number"][0]).zfill(3) for f in files}),
                                       range(1, 9), ["Off", "On"], ["Closing", "Opening"]],
                                      names=["machine_number", "module", "sv", "direction"]).to_frame(index=False)
    by_context = grid.merge(by_context, how="left").fillna({"clean_events": 0, "event_days": 0})
    by_context[["clean_events", "event_days"]] = by_context[["clean_events", "event_days"]].astype(int)
    by_context["coverage_status"] = np.where((by_context.clean_events >= 30) & (by_context.event_days >= 3),
                                               "COVERAGE_MET_NOT_APPROVED", "INSUFFICIENT_COVERAGE")
    by_context.to_csv(output_root / "external_event_coverage_by_context.csv", index=False)
    summary = {"source": "external canonical novel rows only", "partitions_scanned": len(files), **cadence,
               "clean_events": int(len(events)), "machines_with_clean_events": int(events.machine_number.nunique()) if len(events) else 0,
               "clean_events_by_direction": events.direction.value_counts().to_dict() if len(events) else {},
               "contexts": int(len(by_context)), "contexts_coverage_met": int((by_context.coverage_status == "COVERAGE_MET_NOT_APPROVED").sum()),
               "limits": ["External canonical novel rows only; primary data not reprocessed", "Source timezone and pressure units unconfirmed",
                           "No service/refill epoch, recipe/load, facility-water or technician labels", "Coverage met is not candidate-profile or production approval"]}
    (output_root / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(scan_event_coverage(Path(args.input), Path(args.output)), indent=2))
