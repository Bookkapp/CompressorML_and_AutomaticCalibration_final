"""MX057/M1 local, read-only shadow diagnostic with source-second zoom.

Uses the exact qualified one-minute window/candidate contract. It does not
approve a profile, write MySQL, or assign a fault label.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.parquet as pq

from apps.api.app.config import Settings
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows
from notebooks.support.qualified_1m_parquet_replay import SOURCE_TAGS, _machine_code


BLUE = "#1769aa"
NAVY = "#19354c"
RED = "#bf3d39"
TEAL = "#16847a"
AMBER = "#d79437"
GRAY = "#6b7885"


def _source_files(raw_root: Path, day: date) -> list[Path]:
    folder = raw_root / "machine=057" / f"year={day.year}" / f"month={day.month:02d}" / f"day={day.day:02d}"
    paths = sorted(folder.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(folder)
    return paths


def _windows(raw_root: Path) -> tuple[list, int]:
    fields = ["recorded_at", "machine_number", "Status"]
    fields += [f"{tag}_{module}" for module in (1, 6) for tag in SOURCE_TAGS]
    all_windows = []
    raw_rows = 0
    for offset in range(10):
        day = date(2026, 8, 20) + timedelta(days=offset)

        def source_rows():
            nonlocal raw_rows
            for path in _source_files(raw_root, day):
                for batch in pq.ParquetFile(path).iter_batches(batch_size=8192, columns=fields):
                    raw_rows += batch.num_rows
                    for row in batch.to_pylist():
                        if _machine_code(row["machine_number"]) != "057":
                            raise ValueError(f"wrong machine in {path}")
                        row["machine_number"] = "MX057"
                        yield row

        day_end = datetime.combine(day + timedelta(days=1), time(), tzinfo=ZoneInfo("Asia/Bangkok"))
        all_windows += build_completed_windows(source_rows(), as_of=day_end,
                                               policy=WindowPolicy("Asia/Bangkok"), modules=(1, 6))
    return all_windows, raw_rows


def _candidate(windows: list, module: int) -> tuple[dict, pd.DataFrame]:
    selected = [w for w in windows if w.module == module]
    candidate = registry_candidate_from_windows(
        selected,
        settings=Settings(source_timezone="Asia/Bangkok", source_pressure_unit="",
                          profile_state_contract_version="", profile_controller_codebook_version="",
                          profile_service_epoch_version=""),
        machine_number="MX057", module=module,
        calibration_start=datetime(2026, 8, 20),
        shadow_start=datetime(2026, 8, 27), shadow_end=datetime(2026, 8, 30),
    )
    feature_rows = [{"minute": w.window_start, "coverage": w.coverage, "window_status": w.data_quality_status,
                     **(w.features or {})} for w in selected if w.window_start >= datetime(2026, 8, 27)]
    frame = candidate["shadow"].merge(pd.DataFrame(feature_rows), on="minute", how="left", validate="one_to_one")
    return candidate, frame


def _runs(frame: pd.DataFrame, column: str, day: date | None = None) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    selected = frame if day is None else frame[frame.minute.dt.date == day]
    result = []
    beginning = None
    previous = None
    for row in selected.itertuples():
        if bool(getattr(row, column)):
            if beginning is None or previous is None or row.minute - previous != pd.Timedelta(minutes=1):
                if beginning is not None:
                    result.append((beginning, previous + pd.Timedelta(minutes=1),
                                   int((previous - beginning).total_seconds() / 60) + 1))
                beginning = row.minute
            previous = row.minute
        elif beginning is not None:
            result.append((beginning, previous + pd.Timedelta(minutes=1),
                           int((previous - beginning).total_seconds() / 60) + 1))
            beginning = previous = None
    if beginning is not None:
        result.append((beginning, previous + pd.Timedelta(minutes=1),
                       int((previous - beginning).total_seconds() / 60) + 1))
    return result


def _shade(ax, runs, alpha=0.10):
    for start, end, _ in runs:
        ax.axvspan(start, end, color=RED, alpha=alpha, linewidth=0)


def _style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12,
                         "figure.facecolor": "white", "axes.facecolor": "white",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#bac6cf", "grid.color": "#e6ecef",
                         "grid.linewidth": .7, "savefig.dpi": 170})


def _daily(frame: pd.DataFrame) -> list[dict]:
    out = []
    for day, group in frame.groupby(frame.minute.dt.date):
        good = group[group.data_quality_status == "PASS"]
        out.append({"date": str(day), "qualified_minutes": len(good),
                    "raw_flags": int(group.raw_flag.sum()), "persistent_minutes": int(group.persistent_flag.sum()),
                    "lp2_median": round(float(good.lp2.median()), 3) if len(good) else None,
                    "hp2_median": round(float(good.hp2.median()), 3) if len(good) else None,
                    "valve_median": round(float(good.valve.median()), 3) if len(good) else None,
                    "templo_median": round(float(good.templo.median()), 3) if len(good) else None})
    return out


def _overview(m1: pd.DataFrame, m6: pd.DataFrame, c1: dict, c6: dict, output: Path):
    exact = c1["statistics"]["exact_baseline"]
    base = exact["lp2"]["median"]
    scale = exact["lp2"]["scale"]
    runs = _runs(m1, "persistent_flag")
    fig, axes = plt.subplots(3, 1, figsize=(15, 9.4), sharex=True,
                             gridspec_kw={"height_ratios": [1.25, 1, .9]}, layout="constrained")
    fig.suptitle("MX057 | M1 abnormal shadow period (27–29 Aug 2026)", fontsize=17, color=NAVY,
                 fontweight="bold")
    axes[0].plot(m1.minute, m1.lp2, color=BLUE, lw=1.15, label="M1 Lp_2nd • qualified 1-min mean")
    axes[0].axhline(base, color=TEAL, lw=1.3, ls="--", label=f"M1 calibration median {base:.1f}")
    axes[0].fill_between(m1.minute, base-3*scale, base+3*scale, color=TEAL, alpha=.12,
                         label="median ±3 robust scales (reference, not alert rule)")
    _shade(axes[0], runs)
    axes[0].set_ylabel("Lp_2nd (source unit*)")
    axes[0].legend(loc="upper left", ncol=2, fontsize=8.5, frameon=False)
    axes[1].plot(m1.minute, m1.deviation_score / c1["threshold"]["deviation_score_q995"], color=BLUE,
                 lw=1, label="M1 score / own threshold")
    axes[1].plot(m6.minute, m6.deviation_score / c6["threshold"]["deviation_score_q995"], color=AMBER,
                 lw=.9, alpha=.78, label="M6 score / own threshold (context only)")
    axes[1].axhline(1, color=RED, lw=1, ls="--", label="raw-flag boundary")
    _shade(axes[1], runs)
    axes[1].set_ylabel("Relative score")
    axes[1].legend(loc="upper left", ncol=3, fontsize=8.5, frameon=False)
    axes[2].step(m1.minute, m1.raw_flag.astype(int), color=AMBER, lw=1, where="post", label="M1 raw flag")
    axes[2].step(m1.minute, m1.persistent_flag.astype(int), color=RED, lw=1.1, where="post",
                 label="M1 persistent ≥3 consecutive qualified min")
    _shade(axes[2], runs)
    axes[2].set_ylim(-.1, 1.3)
    axes[2].set_yticks([0, 1], ["No", "Yes"])
    axes[2].set_ylabel("Flag")
    axes[2].legend(loc="upper left", ncol=2, fontsize=8.5, frameon=False)
    for ax in axes:
        ax.grid(axis="y")
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=6))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d Aug\n%H:%M"))
    axes[-1].set_xlabel("recorded_at • Asia/Bangkok assumed")
    fig.text(.01, -.027, "* Source pressure unit and timestamp semantics not independently confirmed. Blank = not scored; red bands = persistent deviation, not confirmed equipment fault.",
             fontsize=8, color=GRAY)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _relationship(m1: pd.DataFrame, c1: dict, output: Path):
    day = m1[m1.minute.dt.date == date(2026, 8, 29)]
    exact = c1["statistics"]["exact_baseline"]
    runs = _runs(day, "persistent_flag")
    features = [("lp2", "Lp_2nd (CP2 suction)", BLUE),
                ("hp2", "Hp_2nd (CP2 high)", RED),
                ("valve", "Expansion valve", TEAL),
                ("templo", "TempLo (discharge pipe)", AMBER)]
    fig, axes = plt.subplots(4, 1, figsize=(15, 10), sharex=True, layout="constrained")
    fig.suptitle("MX057 / M1 | 29 Aug: do pressure, valve and temperature move together?",
                 fontsize=16, fontweight="bold", color=NAVY)
    for ax, (feature, label, color) in zip(axes, features):
        ax.plot(day.minute, day[feature], color=color, lw=1.25, label="qualified 1-min mean")
        ax.axhline(exact[feature]["median"], color=NAVY, ls="--", lw=1,
                   label=f"20–26 Aug calibration median {exact[feature]['median']:.1f}")
        _shade(ax, runs)
        ax.set_ylabel(label + "\n(source unit*)")
        ax.grid(axis="y")
        ax.legend(loc="upper left", ncol=2, fontsize=8.3, frameon=False)
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[-1].set_xlabel("29 Aug 2026 • recorded_at, Asia/Bangkok assumed")
    fig.text(.01, -.027, "Red shading = M1 persistent deviation. Separate scales prevent unlike sensors from being overlaid as though values were comparable. * Engineering units unverified.",
             fontsize=8, color=GRAY)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _second_rows(raw_root: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    fields = ["recorded_at", "Status", "Lp_2nd_1", "Hp_2nd_1", "Valve_1", "TempLo_1",
              "Status_1", "Busy_1", "SV_1", "Lp_2nd_6"]
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    parts = []
    for day in days:
        for path in _source_files(raw_root, day.date()):
            parts.append(pq.read_table(path, columns=fields).to_pandas())
    raw = pd.concat(parts, ignore_index=True)
    raw["recorded_at"] = pd.to_datetime(raw.recorded_at)
    raw = raw[(raw.recorded_at >= start) & (raw.recorded_at < end)].sort_values("recorded_at")
    for col in ("Lp_2nd_1", "Hp_2nd_1", "Valve_1", "TempLo_1", "Lp_2nd_6"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    return raw


def _seconds(raw: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, output: Path):
    # Reindex only for drawing. Missing source seconds remain NaN, so the line
    # visibly breaks instead of implying uninterrupted measurement.
    visible = raw.set_index("recorded_at").reindex(pd.date_range(start, end - pd.Timedelta(seconds=1), freq="s"))
    fig, axes = plt.subplots(4, 1, figsize=(15, 9.5), sharex=True, layout="constrained")
    fig.suptitle(f"MX057 / M1 | source-second view • {start:%d Aug %H:%M}–{end:%H:%M}",
                 fontsize=16, fontweight="bold", color=NAVY)
    manual = raw[raw.Status_1.astype(str).eq("ChangeValve") | raw.Busy_1.astype(str).eq("1")]
    for ax, col, name, color in zip(axes,
                                     ("Lp_2nd_1", "Hp_2nd_1", "Valve_1", "TempLo_1"),
                                     ("Lp_2nd", "Hp_2nd", "Valve", "TempLo"),
                                     (BLUE, RED, TEAL, AMBER)):
        ax.plot(visible.index, visible[col], color=color, lw=.8)
        if not manual.empty:
            ax.axvspan(manual.recorded_at.min(), manual.recorded_at.max() + pd.Timedelta(seconds=1),
                       color="#9a77b7", alpha=.20, linewidth=0)
        ax.set_ylabel(name + "\n(source unit*)")
        ax.grid(axis="y")
    axes[-1].xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[-1].set_xlabel("recorded_at • source seconds, no interpolation • Asia/Bangkok assumed")
    footer = ("Purple = ChangeValve / Busy=1 manual-state interval. " if not manual.empty else "")
    fig.text(.01, -.027, footer + "Physical cause cannot be inferred from these tags alone. Missing seconds remain gaps.",
             fontsize=8, color=GRAY)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def run(raw_root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    _style()
    windows, raw_rows = _windows(raw_root)
    c1, m1 = _candidate(windows, 1)
    c6, m6 = _candidate(windows, 6)
    runs29 = _runs(m1, "persistent_flag", date(2026, 8, 29))
    if not runs29:
        raise ValueError("expected diagnostic period did not produce persistent flags")
    longest = max(runs29, key=lambda item: item[2])
    # Show an observed-second interval inside the longest scored episode.
    midpoint = longest[0] + (longest[1] - longest[0]) / 2
    start = max(pd.Timestamp("2026-08-29"), midpoint - pd.Timedelta(minutes=30)).floor("min")
    end = min(pd.Timestamp("2026-08-30"), start + pd.Timedelta(hours=1))
    raw = _second_rows(raw_root, start, end)
    onset_start = pd.Timestamp("2026-08-29 03:45:00")
    onset_end = pd.Timestamp("2026-08-29 04:45:00")
    onset_raw = _second_rows(raw_root, onset_start, onset_end)
    _overview(m1, m6, c1, c6, output / "01_mx057_shadow_overview.png")
    _relationship(m1, c1, output / "02_mx057_m1_relationship_29aug.png")
    _seconds(raw, start, end, output / "03_mx057_m1_source_seconds.png")
    _seconds(onset_raw, onset_start, onset_end, output / "04_mx057_m1_onset_source_seconds.png")
    good29 = m1[(m1.minute.dt.date == date(2026, 8, 29)) & (m1.data_quality_status == "PASS")]
    exact = c1["statistics"]["exact_baseline"]
    dominant = Counter()
    for row in good29[good29.raw_flag].itertuples():
        dominant[max(exact, key=lambda f: abs((getattr(row, f) - exact[f]["median"]) / exact[f]["scale"]))] += 1
    seconds = raw.recorded_at.dt.floor("s")
    manual = onset_raw[onset_raw.Status_1.astype(str).eq("ChangeValve") |
                       onset_raw.Busy_1.astype(str).eq("1")]
    pre = onset_raw[(onset_raw.recorded_at >= pd.Timestamp("2026-08-29 03:45")) &
                    (onset_raw.recorded_at < pd.Timestamp("2026-08-29 04:00"))]
    post = onset_raw[(onset_raw.recorded_at >= pd.Timestamp("2026-08-29 04:10")) &
                     (onset_raw.recorded_at < pd.Timestamp("2026-08-29 04:45"))]
    def medians(frame):
        return {name: round(float(frame[col].median()), 3) for name, col in
                (("lp2", "Lp_2nd_1"), ("hp2", "Hp_2nd_1"),
                 ("valve", "Valve_1"), ("templo", "TempLo_1"))}
    result = {
        "machine": "MX057", "module": 1, "source_period": "2026-08-20 through 2026-08-29",
        "calibration_period": "2026-08-20 through 2026-08-26",
        "shadow_period": "2026-08-27 through 2026-08-29",
        "source_timezone_assumption": "Asia/Bangkok", "source_pressure_unit_verified": False,
        "raw_rows_all_ten_days": raw_rows,
        "candidate_status_m1": c1["status"], "candidate_status_m6": c6["status"],
        "active_profile_used": False, "database_writes": 0,
        "m1_threshold": c1["threshold"]["deviation_score_q995"],
        "m6_threshold": c6["threshold"]["deviation_score_q995"],
        "m1_calibration_exact": exact,
        "m1_daily": _daily(m1), "m6_daily": _daily(m6),
        "m1_dominant_features_on_29aug_raw_flags": dict(dominant),
        "m1_29aug_persistent_runs": [{"start": str(a), "end_exclusive": str(b), "minutes": n} for a,b,n in runs29],
        "longest_29aug_persistent_run": {"start": str(longest[0]), "end_exclusive": str(longest[1]), "minutes": longest[2]},
        "source_second_zoom": {"start": str(start), "end_exclusive": str(end),
                               "rows": len(raw), "unique_seconds": seconds.nunique(),
                               "duplicate_seconds": int(seconds.duplicated().sum()),
                               "expected_seconds": int((end-start).total_seconds()),
                               "compressor_status": dict(Counter(raw.Status.astype(str))),
                               "module_status": dict(Counter(raw.Status_1.astype(str))),
                               "busy": dict(Counter(raw.Busy_1.astype(str))),
                               "sv": dict(Counter(raw.SV_1.astype(str))),
                               "lp2_m1_median": round(float(raw.Lp_2nd_1.median()), 3),
                               "lp2_m6_median": round(float(raw.Lp_2nd_6.median()), 3)},
        "onset_source_second_zoom": {"start": str(onset_start), "end_exclusive": str(onset_end),
                                     "rows": len(onset_raw),
                                     "unique_seconds": onset_raw.recorded_at.dt.floor("s").nunique(),
                                     "expected_seconds": int((onset_end-onset_start).total_seconds()),
                                     "compressor_status": dict(Counter(onset_raw.Status.astype(str))),
                                     "module_status": dict(Counter(onset_raw.Status_1.astype(str))),
                                     "busy": dict(Counter(onset_raw.Busy_1.astype(str))),
                                     "sv": dict(Counter(onset_raw.SV_1.astype(str))),
                                     "manual_state_start": str(manual.recorded_at.min()),
                                     "manual_state_end_inclusive": str(manual.recorded_at.max()),
                                     "manual_state_rows": len(manual),
                                     "before_manual_median": medians(pre),
                                     "after_manual_median": medians(post)},
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.raw_root, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
