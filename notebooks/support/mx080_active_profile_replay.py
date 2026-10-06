"""Read-only retrospective replay of MX080's existing one-minute Active profiles.

This does not fit, approve, modify, or deploy a profile. It deliberately uses
the historical minute-state-core-hp180-v2 contract, not qualified five-minute v1.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import text

from apps.api.app.calibration import FEATURES, _deviation, load_qualified_windows
from apps.api.app.config import get_settings
from apps.api.app.db import get_engine, get_source_engine
from apps.api.app.inference import get_machine_candidates


START = datetime(2026, 9, 3)
END = datetime(2026, 9, 8)
INCIDENT = pd.Timestamp("2026-09-07 12:23:28")  # first >300 psi in observed-second forensic file; not a fault label
OUT = Path(__file__).resolve().parents[1] / "outputs" / "mx080_active_profile_replay_v1"


def _decode(value):
    return json.loads(value) if isinstance(value, str) else value


def _profile_rows() -> dict[int, dict]:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Analytics MySQL is not configured")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT a.module, a.active_profile_id, a.activated_at, a.activated_by,
                   p.profile_version, p.profile_status, p.reason_codes,
                   p.statistics_json, p.threshold_json, p.calibration_days,
                   p.shadow_flag_pct, p.persistent_flag_pct,
                   b.feature_version, b.source_timezone
            FROM ht9046mx_active_calibration_profile a
            JOIN ht9046mx_calibration_profile p ON p.profile_id = a.active_profile_id
            JOIN ht9046mx_calibration_batch b ON b.batch_id = p.batch_id
            WHERE a.machine_number = 'MX080'
              AND a.sv_state = 'Off'
              AND a.state_code = 'COMPRESSOR_ON_COLD_SV_OFF'
            ORDER BY a.module
        """)).mappings().all()
    profiles = {int(r["module"]): dict(r) for r in rows}
    if set(profiles) != set(range(1, 9)):
        raise RuntimeError("MX080 must have exactly eight exact-key Active profiles")
    for row in profiles.values():
        if row["profile_status"] != "ACTIVE_FROZEN" or row["feature_version"] != "minute-state-core-hp180-v2":
            raise RuntimeError("Active profile/feature contract mismatch")
        row["statistics_json"] = _decode(row["statistics_json"])
        row["threshold_json"] = _decode(row["threshold_json"])
        row["reason_codes"] = _decode(row["reason_codes"])
    return profiles


def _score(frame: pd.DataFrame, profiles: dict[int, dict]) -> pd.DataFrame:
    scored = []
    for module, group in frame.groupby("module", sort=True):
        group = group.sort_values("minute").copy()
        profile = profiles[int(module)]
        medians = {name: float(profile["statistics_json"][name]["median"]) for name in FEATURES}
        scales = {name: float(profile["statistics_json"][name]["scale"]) for name in FEATURES}
        z = pd.DataFrame({name: ((group[name] - medians[name]) / scales[name]).abs() for name in FEATURES}, index=group.index)
        group["score"] = _deviation(group, medians, scales)
        group["dominant_feature"] = z.idxmax(axis=1)
        group["threshold"] = float(profile["threshold_json"]["deviation_score_q995"])
        group["raw_flag"] = group["score"].ge(group["threshold"])
        gap1 = group["minute"].diff().dt.total_seconds().eq(60)
        gap2 = group["minute"].sub(group["minute"].shift(2)).dt.total_seconds().eq(120)
        group["persistent_flag"] = group["raw_flag"] & group["raw_flag"].shift(1).eq(True) & group["raw_flag"].shift(2).eq(True) & gap1 & gap2
        group["profile_id"] = int(profile["active_profile_id"])
        scored.append(group)
    return pd.concat(scored, ignore_index=True).sort_values(["module", "minute"])


def _summarize(frame: pd.DataFrame) -> list[dict]:
    out = []
    for (module, day), group in frame.groupby(["module", frame["minute"].dt.date], sort=True):
        out.append({
            "module": int(module), "date": str(day), "eligible_minutes": int(len(group)),
            "raw_flag_minutes": int(group["raw_flag"].sum()),
            "persistent_flag_minutes": int(group["persistent_flag"].sum()),
            "flag_pct_eligible": round(float(group["raw_flag"].mean() * 100), 2),
            "hp2_median_psi": round(float(group["hp2"].median()), 2),
            "score_median": round(float(group["score"].median()), 2),
            "score_p95": round(float(group["score"].quantile(.95)), 2),
        })
    return out


def _episodes(group: pd.DataFrame) -> list[dict]:
    group = group.sort_values("minute").copy()
    # An episode begins with a persistent flag and ends at the last contiguous
    # flagged minute. The first two raw-flag minutes precede persistence.
    mask = group["persistent_flag"]
    selected = group.loc[mask].copy()
    if selected.empty:
        return []
    selected["episode"] = selected["minute"].diff().dt.total_seconds().ne(60).cumsum()
    episodes = []
    for _, part in selected.groupby("episode"):
        episodes.append({
            "start_persistent": part["minute"].iloc[0].isoformat(),
            "end": part["minute"].iloc[-1].isoformat(),
            "persistent_minutes": int(len(part)),
            "hp2_median_psi": round(float(part["hp2"].median()), 2),
            "score_median": round(float(part["score"].median()), 2),
            "dominant_feature": part["dominant_feature"].mode().iloc[0],
        })
    return episodes


def _plot(m6: pd.DataFrame) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(16, 8), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})
    blue, red, amber, gray = "#0072B2", "#C74440", "#D79621", "#66778A"
    # Reindex to every minute so unqualified/missing periods remain visible as
    # gaps; connecting across a state transition would imply invented data.
    timeline = m6.set_index("minute").reindex(pd.date_range(m6["minute"].min(), m6["minute"].max(), freq="min"))
    x = timeline.index
    axes[0].plot(x, timeline["hp2"], color=blue, linewidth=.9, label="Hp_2nd (psi)")
    axes[0].axhspan(180, 230, color="#DAF0E6", alpha=.7, label="180–230 psi: field reference only")
    axes[0].axvline(INCIDENT, color=red, linewidth=1.5, linestyle="--", label="First observed >300 psi: 7 Sep 12:23:28")
    axes[0].set_ylabel("Hp_2nd (psi)")
    axes[0].legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    axes[1].plot(x, timeline["score"], color=gray, linewidth=.7, label="Max |robust z| (capped at 25)")
    axes[1].axhline(float(m6["threshold"].iloc[0]), color=amber, linestyle="--", linewidth=1.4, label="Active threshold = 3.5")
    flagged = m6.loc[m6["persistent_flag"]]
    axes[1].scatter(flagged["minute"], flagged["score"], color=red, s=7, label="3-minute persistent flag", zorder=3)
    axes[1].set_ylabel("Deviation score")
    axes[1].legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    axes[1].xaxis.set_major_locator(mdates.DayLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    axes[1].set_xlabel("Source time: Asia/Bangkok | one-minute qualified rows")
    for ax in axes:
        ax.grid(color="#DDE4E9", linewidth=.5)
    fig.suptitle("MX080 · Module 6 | historical Active-profile replay (not production validation)", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "mx080_m6_active_profile_replay.png", dpi=180)
    plt.close(fig)

    zoom = m6.loc[m6["minute"].between("2026-09-07 11:45", "2026-09-07 14:00")]
    zoom_line = timeline.loc["2026-09-07 11:45":"2026-09-07 14:00"]
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1]})
    axes[0].plot(zoom_line.index, zoom_line["hp2"], color=blue, linewidth=1.6, label="Hp_2nd")
    axes[0].axhspan(180, 230, color="#DAF0E6", alpha=.7)
    axes[0].set_ylabel("CP2 high pressure (psi)")
    axes[1].plot(zoom_line.index, zoom_line["temphi"], color="#6D4C8F", linewidth=1.3, label="TempHi")
    axes[1].plot(zoom_line.index, zoom_line["templo"], color="#009C9C", linewidth=1.3, label="TempLo")
    axes[1].set_ylabel("Temperature (source units)")
    axes[1].legend(loc="upper left", ncol=2, frameon=False)
    axes[2].plot(zoom_line.index, zoom_line["score"], color=gray, linewidth=1, label="Max |robust z|")
    axes[2].scatter(zoom.loc[zoom["persistent_flag"], "minute"], zoom.loc[zoom["persistent_flag"], "score"],
                    color=red, s=16, label="Persistent flag")
    axes[2].axhline(float(m6["threshold"].iloc[0]), color=amber, linestyle="--", label="Threshold 3.5")
    axes[2].set_ylabel("Deviation score")
    axes[2].legend(loc="upper left", ncol=3, frameon=False)
    axes[2].set_xlabel("7 Sep 2026 · Asia/Bangkok | gaps are unqualified or missing minutes")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for ax in axes:
        ax.axvline(INCIDENT, color=red, linewidth=1.1, linestyle="--")
        ax.grid(color="#DDE4E9", linewidth=.5)
    fig.suptitle("MX080 · Module 6 | transition detail around 12:23", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "mx080_m6_sep7_transition.png", dpi=180)
    plt.close(fig)


def _source_daily_quality() -> list[dict]:
    engine = get_source_engine()
    if engine is None:
        raise RuntimeError("Source MySQL is not configured")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DATE(recorded_at) AS day, COUNT(*) AS rows_count,
                   COUNT(DISTINCT recorded_at) AS distinct_timestamps,
                   MIN(recorded_at) AS first_at, MAX(recorded_at) AS last_at
            FROM ht9046mx_iot.ht9046mx_readings
            WHERE machine_number IN :aliases
              AND recorded_at >= :start AND recorded_at < :end
            GROUP BY DATE(recorded_at) ORDER BY day
        """), {"aliases": tuple(get_machine_candidates("MX080")), "start": START, "end": END}).mappings().all()
    return [{key: str(value) if isinstance(value, (datetime, pd.Timestamp)) else value for key, value in row.items()} for row in rows]


def _stored_shadow_parity(m6: pd.DataFrame) -> dict:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Analytics MySQL is not configured")
    with engine.connect() as conn:
        stored = pd.read_sql_query(text("""
            SELECT event_time, deviation_score, raw_flag, persistent_flag
            FROM ht9046mx_calibration_shadow_point
            WHERE profile_id = 21 ORDER BY event_time
        """), conn)
    matched = m6.merge(stored, left_on="minute", right_on="event_time")
    return {
        "stored_shadow_points": len(stored), "matched_points": len(matched),
        "raw_flag_disagreements": int((matched["raw_flag_x"] != matched["raw_flag_y"]).sum()),
        "persistent_flag_disagreements": int((matched["persistent_flag_x"] != matched["persistent_flag_y"]).sum()),
        "max_score_difference_due_to_persisted_rounding": round(float((matched["score"] - matched["deviation_score"]).abs().max()), 4),
    }


def main() -> None:
    settings = get_settings()
    if settings.source_timezone != "Asia/Bangkok":
        raise RuntimeError("Source timezone must be explicitly Asia/Bangkok")
    profiles = _profile_rows()
    qualified = load_qualified_windows(settings, START, END, "MX080")
    if qualified.empty:
        raise RuntimeError("No qualified MX080 rows in requested interval")
    scored = _score(qualified, profiles)
    m6 = scored.loc[scored["module"].eq(6)].copy()
    periods = {
        "comparison_sep5_6_unlabeled": m6.loc[m6["minute"].between("2026-09-05", "2026-09-06 23:59:59")],
        "sep7_pre_shift": m6.loc[m6["minute"].lt(INCIDENT) & m6["minute"].ge("2026-09-07")],
        "sep7_post_shift": m6.loc[m6["minute"].ge(INCIDENT)],
    }
    period_summary = {}
    for name, group in periods.items():
        period_summary[name] = {
            "eligible_minutes": len(group), "raw_flags": int(group["raw_flag"].sum()),
            "persistent_flags": int(group["persistent_flag"].sum()),
            "flag_pct_eligible": round(float(group["raw_flag"].mean() * 100), 2) if len(group) else None,
            "hp2_median_psi": round(float(group["hp2"].median()), 2) if len(group) else None,
            "score_median": round(float(group["score"].median()), 2) if len(group) else None,
            "first_raw_flag": group.loc[group["raw_flag"], "minute"].min().isoformat() if group["raw_flag"].any() else None,
            "first_persistent_flag": group.loc[group["persistent_flag"], "minute"].min().isoformat() if group["persistent_flag"].any() else None,
            "dominant_feature_counts": group.loc[group["raw_flag"], "dominant_feature"].value_counts().to_dict(),
        }
    summary = {
        "run_scope": "read-only retrospective; no fit or profile promotion",
        "source": "local MySQL ht9046mx_iot.ht9046mx_readings; analytics local MySQL Active pointers",
        "input_interval": "2026-09-03 00:00:00 through 2026-09-07 23:59:59 Asia/Bangkok",
        "grain": "source one-minute rows; qualified one-minute module rows",
        "feature_version": "minute-state-core-hp180-v2",
        "five_minute_v1_active_compatible": False,
        "profiles": {str(k): {"profile_id": int(v["active_profile_id"]), "profile_version": v["profile_version"],
                                "threshold": v["threshold_json"], "calibration_days": int(v["calibration_days"]),
                                "approval_reason_codes": v["reason_codes"]} for k, v in profiles.items()},
        "qualified_rows": len(scored), "m6_qualified_rows": len(m6),
        "source_daily_quality": _source_daily_quality(),
        "stored_shadow_parity": _stored_shadow_parity(m6),
        "m6_periods": period_summary,
        "m6_episodes": _episodes(m6),
        "daily_module_summary": _summarize(scored),
        "limitations": [
            "Active pointer was activated after the inspected dates; replay is not prospective validation.",
            "MX080 M6 has only two calibration days and a pre-approval ~49.5% shadow flag rate.",
            "The v1 five-minute scorer cannot consume this minute-profile feature version.",
            "No technician-confirmed fault label or independent cause evidence is available.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(summary["daily_module_summary"]).to_csv(OUT / "daily_module_summary.csv", index=False)
    pd.DataFrame(summary["m6_episodes"]).to_csv(OUT / "m6_persistent_episodes.csv", index=False)
    m6[["minute", "hp1", "lp1", "hp2", "lp2", "dp1", "dp2", "valve", "temphi", "templo", "score", "threshold", "dominant_feature", "raw_flag", "persistent_flag"]].to_csv(OUT / "m6_minute_replay.csv", index=False)
    _plot(m6)
    print(json.dumps({"m6_periods": period_summary, "m6_episodes_top10": sorted(summary["m6_episodes"], key=lambda r: r["persistent_minutes"], reverse=True)[:10], "output": str(OUT)}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
