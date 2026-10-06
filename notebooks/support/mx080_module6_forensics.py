"""One-second forensic analysis for HONTECH HT9046-MX machine MX-080, Module 6.

The module deliberately keeps equipment diagnosis separate from observed evidence.
It removes ambiguous duplicate timestamps, never interpolates across missing seconds,
and uses MessageLogs only as timestamped context.
"""

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PRESSURE_FIELDS = [
    "Hp_1st_6",
    "Lp_1st_6",
    "Hp_2nd_6",
    "Lp_2nd_6",
    "Valve_6",
    "Status_6",
    "TempHi_6",
    "TempLo_6",
    "SV_6",
    "Busy_6",
]
NUMERIC_FIELDS = [field for field in PRESSURE_FIELDS if field not in {"Status_6", "SV_6"}]
HP2_REFERENCE_LOWER_PSI = 180.0
HP2_REFERENCE_UPPER_PSI = 230.0
WATER_KEYWORDS = r"water|tank|level|flow|inlet|outlet"
COLORS = {
    "hp": "#153B5B",
    "lp": "#2A9D8F",
    "delta": "#D97706",
    "temp_hi": "#A23B3B",
    "temp_lo": "#457B9D",
    "valve": "#5B4B8A",
    "alarm": "#B42318",
    "event": "#60646C",
    "reference": "#8A8F98",
    "shade": "#E8EEF3",
}


@dataclass(frozen=True)
class AnalysisConfig:
    pressure_root: Path
    message_file: Path
    output_root: Path
    analysis_start: str = "2026-09-03"
    analysis_end_exclusive: str = "2026-09-08"
    followup_end_exclusive: str = "2026-09-09"
    timezone: str = "Asia/Bangkok (assumed from project context; source files have no timezone)"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _trim_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.select_dtypes(include="object").columns:
        frame[column] = frame[column].astype("string").str.strip()
    return frame


def read_pressure_day(path: Path, day: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    wanted = {"Time", "Status", *PRESSURE_FIELDS}
    raw = pd.read_csv(
        path,
        skiprows=2,
        skipinitialspace=True,
        usecols=lambda column: str(column).strip() in wanted,
        index_col=False,
    )
    raw = _trim_columns(raw)
    raw["timestamp"] = pd.to_datetime(
        day.strftime("%Y-%m-%d") + " " + raw["Time"].astype(str),
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )
    for field in NUMERIC_FIELDS:
        raw[field] = pd.to_numeric(raw[field], errors="coerce")

    valid = raw.loc[raw["timestamp"].notna()].copy()
    duplicate_mask = valid["timestamp"].duplicated(keep=False)
    duplicate_rows = valid.loc[duplicate_mask]
    conflicting_timestamps = 0
    for _, group in duplicate_rows.groupby("timestamp", sort=False):
        if len(group[["Status", *PRESSURE_FIELDS]].drop_duplicates()) > 1:
            conflicting_timestamps += 1

    # Ambiguous duplicate seconds are excluded instead of choosing a row arbitrarily.
    clean = valid.loc[~duplicate_mask].sort_values("timestamp").reset_index(drop=True)
    unique_seconds = int(clean["timestamp"].nunique())
    expected_seconds = 86_400
    quality = {
        "date": day.date().isoformat(),
        "source_file": str(path),
        "source_sha256": sha256(path),
        "raw_rows": int(len(raw)),
        "invalid_timestamp_rows": int(raw["timestamp"].isna().sum()),
        "duplicate_rows_excluded": int(duplicate_mask.sum()),
        "duplicate_timestamps_excluded": int(duplicate_rows["timestamp"].nunique()),
        "conflicting_duplicate_timestamps": int(conflicting_timestamps),
        "usable_unique_seconds": unique_seconds,
        "expected_seconds": expected_seconds,
        "coverage_pct": 100.0 * unique_seconds / expected_seconds,
        "missing_expected_seconds": expected_seconds - unique_seconds,
    }
    return clean, quality


def read_pressure_period(config: AnalysisConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(config.analysis_start)
    end = pd.Timestamp(config.followup_end_exclusive)
    frames: list[pd.DataFrame] = []
    quality_rows: list[dict] = []
    for day in pd.date_range(start, end - pd.Timedelta(days=1), freq="D"):
        path = config.pressure_root / f"{day:%Y_%m_%d}.txt"
        if not path.exists():
            quality_rows.append(
                {
                    "date": day.date().isoformat(),
                    "source_file": str(path),
                    "raw_rows": 0,
                    "usable_unique_seconds": 0,
                    "expected_seconds": 86_400,
                    "coverage_pct": 0.0,
                    "missing_expected_seconds": 86_400,
                    "file_missing": True,
                }
            )
            continue
        frame, quality = read_pressure_day(path, day)
        frames.append(frame)
        quality_rows.append(quality)
    if not frames:
        raise FileNotFoundError(f"No daily pressure files found in {config.pressure_root}")
    pressure = pd.concat(frames, ignore_index=True).sort_values("timestamp")
    pressure["dp_1st_6"] = pressure["Hp_1st_6"] - pressure["Lp_1st_6"]
    pressure["dp_2nd_6"] = pressure["Hp_2nd_6"] - pressure["Lp_2nd_6"]
    return pressure.reset_index(drop=True), pd.DataFrame(quality_rows)


MESSAGE_PATTERN = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M),(.*)$"
)


def read_messages(path: Path) -> pd.DataFrame:
    parsed: list[list[object]] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = MESSAGE_PATTERN.match(line)
        if match:
            fields = next(csv.reader([match.group(2)]))
            code = fields[0].strip() if fields else ""
            message = ",".join(fields[1:]).strip() if len(fields) > 1 else ""
            parsed.append(
                [
                    datetime.strptime(match.group(1), "%m/%d/%Y %I:%M:%S %p"),
                    code,
                    message,
                ]
            )
        elif parsed and line.strip():
            parsed[-1][2] = f"{parsed[-1][2]} {line.strip()}"
    messages = pd.DataFrame(parsed, columns=["timestamp", "code", "message"])
    messages["is_module6"] = messages["message"].str.contains(
        r"\[Model06\]", case=False, regex=True, na=False
    )
    messages["is_alarm"] = messages["code"].str.startswith("ALM", na=False)
    messages["is_data_or_network"] = messages["message"].str.contains(
        "APAX_DAQ|Network disconnect|Pressure rebooting",
        case=False,
        regex=True,
        na=False,
    )
    return messages.sort_values("timestamp").reset_index(drop=True)


def collect_water_message_evidence(message_folder: Path) -> pd.DataFrame:
    """Search every provided MessageLog file; keyword hits are context, not causal proof."""
    frames: list[pd.DataFrame] = []
    for path in sorted(message_folder.glob("*.csv")):
        messages = read_messages(path)
        hits = messages.loc[messages["message"].str.contains(WATER_KEYWORDS, case=False, regex=True, na=False)].copy()
        if not hits.empty:
            hits.insert(0, "source_file", str(path))
            frames.append(hits)
    columns = ["source_file", "timestamp", "code", "message", "is_module6", "is_alarm", "is_data_or_network"]
    return pd.concat(frames, ignore_index=True).reindex(columns=columns) if frames else pd.DataFrame(columns=columns)


def prior_pressure_for_message(config: AnalysisConfig, events: pd.DataFrame) -> pd.DataFrame:
    """Attach the last recorded all-module pressure second within two seconds of each event."""
    if events.empty:
        return events.copy()
    rows: list[pd.DataFrame] = []
    wanted = {"Time", "Status", *[f"Hp_1st_{n}" for n in range(1, 9)], *[f"Hp_2nd_{n}" for n in range(1, 9)]}
    for day, day_events in events.groupby(events["timestamp"].dt.floor("D")):
        path = config.pressure_root.parent / f"{day:%Y_%m}" / f"{day:%Y_%m_%d}.txt"
        if not path.exists():
            rows.append(day_events.assign(pressure_source_file=str(path), pressure_match_status="FILE_MISSING"))
            continue
        pressure = pd.read_csv(path, skiprows=2, skipinitialspace=True, usecols=lambda c: str(c).strip() in wanted)
        pressure = _trim_columns(pressure)
        pressure["pressure_timestamp"] = pd.to_datetime(
            day.strftime("%Y-%m-%d") + " " + pressure["Time"].astype(str),
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )
        pressure = pressure.dropna(subset=["pressure_timestamp"]).sort_values("pressure_timestamp")
        merged = pd.merge_asof(
            day_events.sort_values("timestamp"),
            pressure.drop(columns=["Time"]).sort_values("pressure_timestamp"),
            left_on="timestamp",
            right_on="pressure_timestamp",
            direction="backward",
            tolerance=pd.Timedelta(seconds=2),
        )
        merged["pressure_source_file"] = str(path)
        merged["pressure_lag_seconds"] = (merged["timestamp"] - merged["pressure_timestamp"]).dt.total_seconds()
        merged["pressure_match_status"] = np.where(merged["pressure_timestamp"].notna(), "PRIOR_WITHIN_2S", "NO_MATCH")
        rows.append(merged)
    return pd.concat(rows, ignore_index=True)


def exact_event_snapshots(pressure: pd.DataFrame, messages: pd.DataFrame) -> pd.DataFrame:
    events = messages.loc[
        messages["is_module6"]
        & (messages["is_alarm"] | messages["message"].str.contains("relay timer", case=False))
    ].copy()
    snapshots = events.merge(pressure, on="timestamp", how="left", suffixes=("", "_pressure"))
    keep = [
        "timestamp",
        "code",
        "message",
        "Hp_1st_6",
        "Lp_1st_6",
        "dp_1st_6",
        "Hp_2nd_6",
        "Lp_2nd_6",
        "dp_2nd_6",
        "Valve_6",
        "Status_6",
        "TempHi_6",
        "TempLo_6",
        "SV_6",
        "Busy_6",
    ]
    return snapshots.reindex(columns=keep)


def summarize_periods(pressure: pd.DataFrame) -> pd.DataFrame:
    period_defs = [
        ("Reference: Sep 3–6", "2026-09-03", "2026-09-07"),
        ("Sep 7 before 08:00", "2026-09-07", "2026-09-07 08:00:00"),
        ("Sep 7 restart/balancing", "2026-09-07 08:00:00", "2026-09-07 10:55:58"),
        ("Sep 7 persistent high CP2", "2026-09-07 12:23:20", "2026-09-08"),
        ("Sep 8 confirmation window", "2026-09-08 12:55:00", "2026-09-08 13:20:00"),
    ]
    rows: list[dict] = []
    for label, start, end in period_defs:
        segment = pressure.loc[
            pressure["timestamp"].ge(pd.Timestamp(start))
            & pressure["timestamp"].lt(pd.Timestamp(end))
        ]
        hp2 = segment["Hp_2nd_6"]
        lp2 = segment["Lp_2nd_6"]
        dp2 = segment["dp_2nd_6"]
        rows.append(
            {
                "period": label,
                "start": start,
                "end_exclusive": end,
                "usable_seconds": int(len(segment)),
                "hp2_median_psi": hp2.median(),
                "hp2_q05_psi": hp2.quantile(0.05),
                "hp2_q95_psi": hp2.quantile(0.95),
                "hp2_max_psi": hp2.max(),
                "lp2_median_psi": lp2.median(),
                "dp2_median_psi": dp2.median(),
                "hp2_over_300_pct": 100.0 * hp2.gt(300).mean(),
                "hp2_below_180_pct": 100.0 * hp2.lt(HP2_REFERENCE_LOWER_PSI).mean(),
                "hp2_within_180_230_pct": 100.0 * hp2.between(
                    HP2_REFERENCE_LOWER_PSI, HP2_REFERENCE_UPPER_PSI, inclusive="both"
                ).mean(),
                "hp2_above_230_pct": 100.0 * hp2.gt(HP2_REFERENCE_UPPER_PSI).mean(),
            }
        )
    return pd.DataFrame(rows)


def _prepare_plot_window(pressure: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    window = pressure.loc[
        pressure["timestamp"].ge(pd.Timestamp(start))
        & pressure["timestamp"].le(pd.Timestamp(end))
    ].copy()
    # Break lines after a missing second so the plot does not imply interpolated continuity.
    gap = window["timestamp"].diff().gt(pd.Timedelta(seconds=1))
    window.loc[gap, NUMERIC_FIELDS + ["dp_1st_6", "dp_2nd_6"]] = np.nan
    return window


def _style_axis(axis: plt.Axes) -> None:
    axis.grid(axis="y", color="#D9DEE5", linewidth=0.7, alpha=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.tick_params(labelsize=9)


def _add_figure_header(fig: plt.Figure, axis: plt.Axes, title: str, subtitle: str) -> None:
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.075, top=0.90, hspace=0.08)
    fig.suptitle(title, x=0.065, y=0.975, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.065, 0.935, subtitle, ha="left", fontsize=10, color="#555B66")
    axis.set_title("")


def _event_lines(axis: plt.Axes, events: pd.DataFrame, start: str, end: str) -> None:
    subset = events.loc[
        events["timestamp"].between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
    ]
    for timestamp in subset.loc[subset["is_alarm"] & subset["is_module6"], "timestamp"]:
        axis.axvline(timestamp, color=COLORS["alarm"], linewidth=1.0, alpha=0.78)
    for timestamp in subset.loc[subset["is_data_or_network"], "timestamp"]:
        axis.axvline(timestamp, color=COLORS["event"], linewidth=0.8, linestyle="--", alpha=0.55)


def plot_overview(pressure: pd.DataFrame, messages: pd.DataFrame, output: Path) -> None:
    window = _prepare_plot_window(pressure, "2026-09-03", "2026-09-07 23:59:59")
    fig, axes = plt.subplots(3, 1, figsize=(17, 10), sharex=True)
    axes[0].plot(window["timestamp"], window["Hp_2nd_6"], color=COLORS["hp"], lw=0.55, label="Hp_2nd_6")
    axes[0].plot(window["timestamp"], window["Lp_2nd_6"], color=COLORS["lp"], lw=0.55, label="Lp_2nd_6")
    axes[0].axhspan(
        HP2_REFERENCE_LOWER_PSI,
        HP2_REFERENCE_UPPER_PSI,
        color="#DCEFE4",
        alpha=0.55,
        label="180–230 psi qualified field reference",
    )
    axes[0].set_ylabel("CP2 pressure (psi)")
    axes[0].legend(loc="upper left", ncol=3, frameon=False)
    _add_figure_header(
        fig,
        axes[0],
        "MX-080 · Module 6 — five-day pressure history from one-second records",
        "3–7 Sep 2026 · ambiguous duplicate seconds excluded · no interpolation",
    )

    axes[1].plot(window["timestamp"], window["dp_2nd_6"], color=COLORS["delta"], lw=0.65)
    axes[1].axhline(0, color=COLORS["reference"], lw=0.8)
    axes[1].set_ylabel("CP2 ΔP (psi)")

    axes[2].plot(window["timestamp"], window["TempHi_6"], color=COLORS["temp_hi"], lw=0.55, label="TempHi_6")
    axes[2].plot(window["timestamp"], window["TempLo_6"], color=COLORS["temp_lo"], lw=0.55, label="TempLo_6")
    axes[2].set_ylabel("Logged temperature")
    axes[2].legend(loc="upper left", ncol=2, frameon=False)
    axes[2].xaxis.set_major_locator(mdates.DayLocator())
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    for axis in axes:
        _style_axis(axis)
        axis.axvspan(pd.Timestamp("2026-09-07 08:00"), pd.Timestamp("2026-09-07 10:56"), color="#F7E4E2", alpha=0.55)
        axis.axvspan(pd.Timestamp("2026-09-07 12:23:20"), pd.Timestamp("2026-09-08"), color="#F6E8C8", alpha=0.45)
        _event_lines(axis, messages, "2026-09-03", "2026-09-07 23:59:59")
        axis.set_xlim(pd.Timestamp("2026-09-03"), pd.Timestamp("2026-09-08"))
    fig.savefig(output, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_balancing_window(pressure: pd.DataFrame, messages: pd.DataFrame, output: Path) -> None:
    start, end = "2026-09-07 07:50:00", "2026-09-07 09:45:00"
    window = _prepare_plot_window(pressure, start, end)
    fig, axes = plt.subplots(4, 1, figsize=(17, 12), sharex=True)
    axes[0].plot(window["timestamp"], window["Hp_2nd_6"], color=COLORS["hp"], lw=0.85, label="Hp_2nd_6")
    axes[0].plot(window["timestamp"], window["Lp_2nd_6"], color=COLORS["lp"], lw=0.85, label="Lp_2nd_6")
    axes[0].set_ylabel("CP2 (psi)")
    axes[0].legend(loc="upper right", ncol=2, frameon=False)
    _add_figure_header(
        fig,
        axes[0],
        "Module 6 — repeated pressure-balancing attempts at one-second resolution",
        "7 Sep 2026, 07:50–09:45 · red = ALM043 · grey dashed = DAQ/network/reboot context",
    )

    axes[1].plot(window["timestamp"], window["dp_2nd_6"], color=COLORS["delta"], lw=0.85)
    axes[1].axhline(0, color=COLORS["reference"], lw=0.8)
    axes[1].set_ylabel("CP2 ΔP (psi)")

    axes[2].step(window["timestamp"], window["Valve_6"], where="post", color=COLORS["valve"], lw=0.9, label="Valve_6")
    axes[2].step(window["timestamp"], window["Busy_6"] * 100, where="post", color="#111827", lw=0.75, alpha=0.75, label="Busy_6 × 100")
    axes[2].set_ylabel("Valve / busy")
    axes[2].legend(loc="upper right", ncol=2, frameon=False)

    axes[3].plot(window["timestamp"], window["TempHi_6"], color=COLORS["temp_hi"], lw=0.8, label="TempHi_6")
    axes[3].plot(window["timestamp"], window["TempLo_6"], color=COLORS["temp_lo"], lw=0.8, label="TempLo_6")
    axes[3].set_ylabel("Logged temperature")
    axes[3].legend(loc="upper right", ncol=2, frameon=False)
    axes[3].xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for axis in axes:
        _style_axis(axis)
        _event_lines(axis, messages, start, end)
        axis.set_xlim(pd.Timestamp(start), pd.Timestamp(end))
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_high_pressure_transition(pressure: pd.DataFrame, messages: pd.DataFrame, output: Path) -> None:
    start, end = "2026-09-07 11:55:00", "2026-09-07 13:15:00"
    window = _prepare_plot_window(pressure, start, end)
    fig, axes = plt.subplots(4, 1, figsize=(17, 12), sharex=True)
    axes[0].plot(window["timestamp"], window["Hp_2nd_6"], color=COLORS["hp"], lw=0.8, label="Hp_2nd_6")
    axes[0].plot(window["timestamp"], window["Lp_2nd_6"], color=COLORS["lp"], lw=0.8, label="Lp_2nd_6")
    axes[0].axhline(HP2_REFERENCE_UPPER_PSI, color="#6B8E6E", ls="--", lw=0.9, label="230 psi upper reference")
    axes[0].axhline(300, color=COLORS["reference"], ls="--", lw=0.9, label="300 psi visual reference")
    axes[0].set_ylabel("CP2 (psi)")
    axes[0].legend(loc="upper left", ncol=3, frameon=False)
    _add_figure_header(
        fig,
        axes[0],
        "Module 6 — transition into persistent high CP2 pressure",
        "7 Sep 2026, 11:55–13:15 · exact one-second records · reference line is descriptive, not an alarm rule",
    )

    axes[1].plot(window["timestamp"], window["dp_2nd_6"], color=COLORS["delta"], lw=0.85)
    axes[1].set_ylabel("CP2 ΔP (psi)")

    axes[2].plot(window["timestamp"], window["Hp_1st_6"], color=COLORS["hp"], lw=0.75, label="Hp_1st_6")
    axes[2].plot(window["timestamp"], window["Lp_1st_6"], color=COLORS["lp"], lw=0.75, label="Lp_1st_6")
    axes[2].set_ylabel("CP1 (psi)")
    axes[2].legend(loc="upper left", ncol=2, frameon=False)

    axes[3].step(window["timestamp"], window["Valve_6"], where="post", color=COLORS["valve"], lw=0.85, label="Valve_6")
    axes[3].step(window["timestamp"], window["Busy_6"] * 100, where="post", color="#111827", lw=0.7, alpha=0.75, label="Busy_6 × 100")
    axes[3].set_ylabel("Valve / busy")
    axes[3].legend(loc="upper left", ncol=2, frameon=False)
    axes[3].xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for axis in axes:
        _style_axis(axis)
        _event_lines(axis, messages, start, end)
        axis.axvline(pd.Timestamp("2026-09-07 12:23:20"), color="#7A4E00", lw=1.1, ls=":")
        axis.set_xlim(pd.Timestamp(start), pd.Timestamp(end))
    axes[0].annotate(
        "Persistent high-ΔP segment begins\n12:23:20",
        xy=(pd.Timestamp("2026-09-07 12:23:20"), 300),
        xytext=(pd.Timestamp("2026-09-07 11:58"), 365),
        arrowprops={"arrowstyle": "->", "color": "#7A4E00"},
        color="#7A4E00",
    )
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_followup_alarm(pressure: pd.DataFrame, messages: pd.DataFrame, output: Path) -> None:
    start, end = "2026-09-08 12:55:00", "2026-09-08 13:20:00"
    window = _prepare_plot_window(pressure, start, end)
    fig, axes = plt.subplots(2, 1, figsize=(16, 7.5), sharex=True)
    axes[0].plot(window["timestamp"], window["Hp_2nd_6"], color=COLORS["hp"], lw=0.9, label="Hp_2nd_6")
    axes[0].plot(window["timestamp"], window["Lp_2nd_6"], color=COLORS["lp"], lw=0.9, label="Lp_2nd_6")
    axes[0].set_ylabel("CP2 (psi)")
    axes[0].legend(loc="upper left", ncol=2, frameon=False)
    _add_figure_header(
        fig,
        axes[0],
        "Follow-up evidence — Module 6 CP2 high-pressure alarms",
        "8 Sep 2026, 12:55–13:20 · outside the requested 3–7 Sep window, shown only as confirmation",
    )
    axes[1].plot(window["timestamp"], window["dp_2nd_6"], color=COLORS["delta"], lw=0.9)
    axes[1].set_ylabel("CP2 ΔP (psi)")
    axes[1].xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for axis in axes:
        _style_axis(axis)
        _event_lines(axis, messages, start, end)
        axis.set_xlim(pd.Timestamp(start), pd.Timestamp(end))
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run_analysis(config: AnalysisConfig) -> dict:
    config.output_root.mkdir(parents=True, exist_ok=True)
    figure_root = config.output_root / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)

    pressure, quality = read_pressure_period(config)
    messages = read_messages(config.message_file)
    water_messages = collect_water_message_evidence(config.message_file.parent)
    water_snapshots = prior_pressure_for_message(config, water_messages)
    period_summary = summarize_periods(pressure)
    snapshots = exact_event_snapshots(pressure, messages)

    analysis_pressure = pressure.loc[
        pressure["timestamp"].ge(pd.Timestamp(config.analysis_start))
        & pressure["timestamp"].lt(pd.Timestamp(config.analysis_end_exclusive))
    ].copy()
    analysis_pressure.to_parquet(config.output_root / "module6_one_second_unique.parquet", index=False)
    quality.to_csv(config.output_root / "data_quality_by_day.csv", index=False)
    period_summary.to_csv(config.output_root / "module6_period_summary.csv", index=False)
    snapshots.to_csv(config.output_root / "module6_event_snapshots.csv", index=False)
    messages.to_csv(config.output_root / "message_events_parsed.csv", index=False)
    water_messages.to_csv(config.output_root / "water_message_keyword_evidence.csv", index=False)
    water_snapshots.to_csv(config.output_root / "water_message_prior_pressure_snapshot.csv", index=False)

    figure_paths = {
        "overview": figure_root / "01_module6_five_day_overview.png",
        "balancing": figure_root / "02_module6_balancing_attempts_1s.png",
        "high_pressure": figure_root / "03_module6_high_pressure_transition_1s.png",
        "followup": figure_root / "04_module6_followup_high_pressure_alarm_1s.png",
    }
    plot_overview(pressure, messages, figure_paths["overview"])
    plot_balancing_window(pressure, messages, figure_paths["balancing"])
    plot_high_pressure_transition(pressure, messages, figure_paths["high_pressure"])
    plot_followup_alarm(pressure, messages, figure_paths["followup"])

    reference = period_summary.loc[period_summary["period"].eq("Reference: Sep 3–6")].iloc[0]
    persistent = period_summary.loc[period_summary["period"].eq("Sep 7 persistent high CP2")].iloc[0]
    summary = {
        "machine": "HONTECH HT9046-MX / MX-080",
        "module": 6,
        "input_period": "2026-09-03 through 2026-09-07; 2026-09-08 used only as follow-up confirmation",
        "timezone": config.timezone,
        "row_grain": "one recorded second; ambiguous duplicate timestamps excluded; missing seconds not interpolated",
        "usable_seconds_analysis_window": int(len(analysis_pressure)),
        "reference_hp2_median_psi": float(reference["hp2_median_psi"]),
        "reference_hp2_q05_psi": float(reference["hp2_q05_psi"]),
        "reference_hp2_q95_psi": float(reference["hp2_q95_psi"]),
        "persistent_hp2_median_psi": float(persistent["hp2_median_psi"]),
        "persistent_hp2_q05_psi": float(persistent["hp2_q05_psi"]),
        "persistent_hp2_q95_psi": float(persistent["hp2_q95_psi"]),
        "persistent_hp2_over_300_pct": float(persistent["hp2_over_300_pct"]),
        "hp2_qualified_field_reference_band_psi": [HP2_REFERENCE_LOWER_PSI, HP2_REFERENCE_UPPER_PSI],
        "undercharge_screening_boundary_psi": HP2_REFERENCE_LOWER_PSI,
        "water_keyword_messages_all_available_logs": int(len(water_messages)),
        "water_keyword_messages_sep3_to_sep8": int(
            water_messages["timestamp"].between("2026-09-03", "2026-09-08 23:59:59").sum()
        ),
        "water_log_interpretation": "No water/tank/level message corroborates the Sep 3–8 Module 6 high-pressure episode. One ALM004 Water flow error [IN] exists on Aug 30; the prior recorded second has Hp_2nd_6 about 213.9 psi during a Run/Stop transition, so water causality remains unverified.",
        "module6_alm043_sep7_count": int(
            messages["timestamp"].between("2026-09-07", "2026-09-07 23:59:59")
            .mul(messages["is_module6"])
            .mul(messages["code"].eq("ALM043"))
            .sum()
        ),
        "module6_alm041_sep8_count": int(
            messages["timestamp"].between("2026-09-08", "2026-09-08 23:59:59")
            .mul(messages["is_module6"])
            .mul(messages["code"].eq("ALM041"))
            .sum()
        ),
        "interpretation": "Observed sequence supports repeated pressure-balancing/start attempts followed by persistent CP2 high pressure; it does not identify root cause or prove refrigerant leak.",
        "temperature_log_scope": "The separate 20-channel Temperature log is not assigned to Module 6 because a channel-to-module map is unavailable.",
        "figures": {key: str(path) for key, path in figure_paths.items()},
    }
    (config.output_root / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "summary": summary,
        "quality": quality,
        "period_summary": period_summary,
        "snapshots": snapshots,
        "water_messages": water_messages,
        "water_snapshots": water_snapshots,
        "figure_paths": figure_paths,
    }


if __name__ == "__main__":
    raise SystemExit("Import this module and call run_analysis(AnalysisConfig(...)).")
