from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "HT9046MX_ML_Calibration_LOMO.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "colab": {"name": OUTPUT.name, "provenance": []},
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.x"},
}

nb["cells"] = [
    md(
        """
# HT-9046MX — ML Calibration Profiles, Temporal Validation & Leave-One-Machine-Out

Notebook นี้ต่อจาก `HT9046MX_State_Aware_Baseline_Analysis.ipynb` และใช้ผล `baseline_stats.csv` เพื่อ:

- เลือกเครื่อง/โมดูล/SV ที่ข้อมูลเพียงพอ
- สร้าง calibration profile จากช่วงต้น 70% ของเวลาเท่านั้น
- สร้าง relative features: robust z-score, pressure differential, rolling slope และ lag response
- ทำ temporal validation บนช่วงท้าย 30%
- ทำ Leave-One-Machine-Out (LOMO) บนเครื่องที่ข้อมูลเพียงพอ
- กันเครื่องประวัติสั้น/ข้อมูลไม่พอออกเป็น external test โดยไม่ใช้ฝึกหรือ calibrate

ไม่มี failure label ที่ยืนยันแล้ว ผล validation จึงวัด **transferability และ calibration stability** ไม่ใช่ precision/recall ของการตรวจ leak
"""
    ),
    md("## 1. Setup"),
    code(
        r"""
import importlib.util
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

required = {
    "polars": "polars>=1.20", "pandas": "pandas>=2", "numpy": "numpy>=1.26",
    "sklearn": "scikit-learn>=1.4", "matplotlib": "matplotlib>=3.8", "joblib": "joblib>=1.3",
}
missing = [pkg for module, pkg in required.items() if importlib.util.find_spec(module) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore", category=RuntimeWarning)
plt.style.use("seaborn-v0_8-whitegrid")

start = Path(os.environ.get("HT9046MX_PROJECT_ROOT", Path.cwd())).resolve()
PROJECT_ROOT = next(
    (p for p in [start, start.parent] if (p / "README_System.md").exists()),
    start,
)
ANALYSIS_ROOT = PROJECT_ROOT / "notebooks" / "outputs" / "ht9046mx_colab_analysis"
if not ANALYSIS_ROOT.exists():
    ANALYSIS_ROOT = PROJECT_ROOT / "outputs" / "ht9046mx_colab_analysis"
OUTPUT_ROOT = PROJECT_ROOT / "notebooks" / "outputs" / "ht9046mx_ml_calibration"
PROFILE_ROOT = OUTPUT_ROOT / "calibration_profiles"
FIGURE_ROOT = OUTPUT_ROOT / "figures"
for folder in [OUTPUT_ROOT, PROFILE_ROOT, FIGURE_ROOT]:
    folder.mkdir(parents=True, exist_ok=True)

BASELINE_FILE = ANALYSIS_ROOT / "baseline_stats.csv"
READINESS_FILE = ANALYSIS_ROOT / "machine_ml_readiness.csv"
MINUTE_CACHE = ANALYSIS_ROOT / "cache" / "minute_module_state.parquet"
for required_file in [BASELINE_FILE, READINESS_FILE, MINUTE_CACHE]:
    if not required_file.exists():
        raise FileNotFoundError(f"Missing {required_file}. Run the state-aware baseline notebook first.")

RANDOM_STATE = 9046
TIME_TRAIN_FRACTION = 0.70
MIN_READY_MODULES_PER_MACHINE = 6
SETTLE_MINUTES = 3
MODEL_SAMPLE_PER_MACHINE = 12_000
EVAL_SAMPLE_PER_MACHINE = 25_000
MAX_SAMPLES_PER_TREE = 2048
N_TREES = 120

BASE_FEATURES = ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo"]
DERIVED_FEATURES = ["dp1", "dp2", "hp_stage_gap", "lp_stage_gap"]
SLOPE_FEATURES = [f"{name}_slope_15m" for name in BASE_FEATURES]
RESPONSE_TARGETS = ["hp2", "lp2", "templo"]
LAG_FEATURES = []
for lag in [1, 5]:
    LAG_FEATURES.append(f"valve_change_{lag}m")
    for target in RESPONSE_TARGETS:
        LAG_FEATURES += [f"{target}_response_{lag}m", f"valve_to_{target}_gain_{lag}m"]
RAW_FEATURES = BASE_FEATURES + DERIVED_FEATURES + SLOPE_FEATURES + LAG_FEATURES
MODEL_FEATURES = [f"rz_{feature}" for feature in RAW_FEATURES]

print("PROJECT_ROOT:", PROJECT_ROOT)
print("ANALYSIS_ROOT:", ANALYSIS_ROOT)
print("OUTPUT_ROOT:", OUTPUT_ROOT)
print("Model features:", len(MODEL_FEATURES))
"""
    ),
    md(
        """
## 2. Split policy

- **Development machines:** อย่างน้อย 6 modules ผ่านเกณฑ์ candidate ในผล readiness เดิม
- **External test machines:** เครื่องอื่นทั้งหมด รวมเครื่องวันน้อยและข้อมูลไม่พอ
- **Profile window:** 70% แรกของวันใน development machine
- **Temporal validation:** 30% หลังของเครื่องเดียวกัน
- **LOMO:** ฝึก shared model จาก development machines อื่น แล้วทดสอบช่วงท้ายของเครื่องที่กันออก
- External test ใช้ fleet cold-start profile ที่สร้างจาก development train window เท่านั้น
"""
    ),
    code(
        r"""
baseline_audit = pl.read_csv(BASELINE_FILE, schema_overrides={"machine_number": pl.Utf8})
readiness = pl.read_csv(READINESS_FILE, schema_overrides={"machine_number": pl.Utf8})

development_machines = sorted(
    readiness.filter(pl.col("candidate_modules") >= MIN_READY_MODULES_PER_MACHINE)
    .get_column("machine_number").cast(pl.Utf8).to_list()
)
all_machines = sorted(readiness.get_column("machine_number").cast(pl.Utf8).to_list())
external_test_machines = sorted(set(all_machines) - set(development_machines))

split_manifest = pd.DataFrame({
    "machine_number": all_machines,
    "role": ["development_temporal_lomo" if m in development_machines else "external_test" for m in all_machines],
})
split_manifest.to_csv(OUTPUT_ROOT / "machine_split_manifest.csv", index=False)

print("Development machines:", development_machines)
print("External test machines:", external_test_machines)
display(split_manifest)
"""
    ),
    md("## 3. Rebuild evidence-safe operating rows from the minute cache"),
    code(
        r"""
minute = pl.read_parquet(MINUTE_CACHE).sort(["machine_number", "module", "minute"])
minute = minute.with_columns(pl.col("machine_number").cast(pl.Utf8))
control_states = ["ChangeValve", "MValveHome", "AdjustValve"]

minute = minute.with_columns(
    pl.when(pl.col("global_status") == "Stop").then(pl.lit("GLOBAL_STOP"))
    .when(
        pl.col("module_status").is_in(control_states)
        | (pl.col("busy") == 1)
        | (pl.col("valve") < 0)
    ).then(pl.lit("CONTROL_SEQUENCE"))
    .when(pl.col("module_status") == "Off").then(pl.lit("RUN_MODULE_OFF"))
    .when(
        (pl.col("global_status") == "Run") & (pl.col("module_status") == "On")
        & (pl.col("busy") == 0) & (pl.col("valve") >= 0) & (pl.col("sv") == "Off")
    ).then(pl.lit("COMPRESSOR_ON_COLD_SV_OFF"))
    .when(
        (pl.col("global_status") == "Run") & (pl.col("module_status") == "On")
        & (pl.col("busy") == 0) & (pl.col("valve") >= 0) & (pl.col("sv") == "On")
    ).then(pl.lit("BYPASS_NONRUN_SV_ON_UNSUPPORTED"))
    .otherwise(pl.lit("UNCLASSIFIED")).alias("state")
)

minute = minute.with_columns(
    (
        (pl.col("state") != pl.col("state").shift(1).over(["machine_number", "module"]))
        | (pl.col("minute").diff().over(["machine_number", "module"]).dt.total_minutes() > 2)
    ).fill_null(True).alias("segment_start")
).with_columns(
    pl.col("segment_start").cast(pl.Int64).cum_sum().over(["machine_number", "module"]).alias("segment_id")
).with_columns(
    pl.col("minute").cum_count().over(["machine_number", "module", "segment_id"]).alias("minutes_in_state")
)

eligible = minute.filter(
    pl.col("state").is_in(["COMPRESSOR_ON_COLD_SV_OFF"])
    & (pl.col("minutes_in_state") >= SETTLE_MINUTES)
)

# baseline_stats.csv controls which development machine-module-SV groups are trusted enough.
ready_profile_keys = (
    baseline_audit.filter(pl.col("sufficient_baseline"))
    .with_columns(pl.col("machine_number").cast(pl.Utf8))
    .filter(pl.col("machine_number").is_in(development_machines))
    .select(["machine_number", "module", "sv"]).unique()
)
development_rows = eligible.join(ready_profile_keys, on=["machine_number", "module", "sv"], how="inner")
external_rows = eligible.filter(pl.col("machine_number").is_in(external_test_machines))

print(f"Eligible development rows: {development_rows.height:,}")
print(f"Eligible external-test rows: {external_rows.height:,}")
"""
    ),
    md("## 4. Temporal split — determine cutoffs before profile calculation"),
    code(
        r"""
cutoff_rows = []
for machine in development_machines:
    dates = (
        development_rows.filter(pl.col("machine_number") == machine)
        .select(pl.col("minute").dt.date().unique().sort())
        .to_series().to_list()
    )
    if len(dates) < 2:
        continue
    split_index = min(len(dates) - 2, max(0, int(np.ceil(len(dates) * TIME_TRAIN_FRACTION)) - 1))
    cutoff_rows.append({
        "machine_number": machine,
        "cutoff_date": dates[split_index],
        "total_days": len(dates),
        "train_days": split_index + 1,
        "validation_days": len(dates) - split_index - 1,
    })

cutoffs = pl.from_pandas(pd.DataFrame(cutoff_rows)).with_columns(pl.col("machine_number").cast(pl.Utf8))
cutoffs.write_csv(OUTPUT_ROOT / "temporal_cutoffs.csv")
development_rows = development_rows.join(cutoffs.select(["machine_number", "cutoff_date"]), on="machine_number")
development_rows = development_rows.with_columns(
    (pl.col("minute").dt.date() <= pl.col("cutoff_date")).alias("is_profile_train")
)
display(cutoffs.to_pandas())
"""
    ),
    md("## 5. Feature engineering — only present and past observations"),
    code(
        r"""
def add_raw_features(frame: pl.DataFrame) -> pl.DataFrame:
    frame = frame.sort(["machine_number", "module", "sv", "segment_id", "minute"])
    groups = ["machine_number", "module", "sv", "segment_id"]
    frame = frame.with_columns(
        (pl.col("hp1") - pl.col("lp1")).alias("dp1"),
        (pl.col("hp2") - pl.col("lp2")).alias("dp2"),
        (pl.col("hp2") - pl.col("hp1")).alias("hp_stage_gap"),
        (pl.col("lp2") - pl.col("lp1")).alias("lp_stage_gap"),
    )

    lag15_time = pl.col("minute").shift(15).over(groups)
    gap15 = (pl.col("minute") - lag15_time).dt.total_minutes()
    slope_exprs = []
    for feature in BASE_FEATURES:
        slope_exprs.append(
            pl.when(gap15 == 15)
            .then((pl.col(feature) - pl.col(feature).shift(15).over(groups)) / 15.0)
            .otherwise(None).alias(f"{feature}_slope_15m")
        )
    frame = frame.with_columns(*slope_exprs)

    for lag in [1, 5]:
        lag_time = pl.col("minute").shift(lag).over(groups)
        gap = (pl.col("minute") - lag_time).dt.total_minutes()
        valve_change = pl.when(gap == lag).then(
            pl.col("valve") - pl.col("valve").shift(lag).over(groups)
        ).otherwise(None)
        expressions = [valve_change.alias(f"valve_change_{lag}m")]
        for target in RESPONSE_TARGETS:
            response = pl.when(gap == lag).then(
                pl.col(target) - pl.col(target).shift(lag).over(groups)
            ).otherwise(None)
            expressions += [
                response.alias(f"{target}_response_{lag}m"),
                (response / (valve_change.abs() + 1.0)).alias(f"valve_to_{target}_gain_{lag}m"),
            ]
        frame = frame.with_columns(*expressions)
    return frame

development_features = add_raw_features(development_rows)
external_features = add_raw_features(external_rows)
print("Raw engineered features:", len(RAW_FEATURES))
display(development_features.select(["machine_number", "module", "sv", "minute", *RAW_FEATURES[:12]]).head(8).to_pandas())
"""
    ),
    md("## 6. Build leakage-safe calibration profiles from the early window"),
    code(
        r"""
PROFILE_KEYS = ["machine_number", "module", "sv"]
profile_train = development_features.filter(pl.col("is_profile_train"))

summary_exprs = [pl.len().alias("n_minutes"), pl.col("minute").dt.date().n_unique().alias("n_days")]
for feature in RAW_FEATURES:
    summary_exprs += [
        pl.col(feature).median().alias(f"{feature}__median"),
        pl.col(feature).quantile(0.25).alias(f"{feature}__q25"),
        pl.col(feature).quantile(0.75).alias(f"{feature}__q75"),
        pl.col(feature).quantile(0.05).alias(f"{feature}__q05"),
        pl.col(feature).quantile(0.95).alias(f"{feature}__q95"),
    ]

profile_summary = profile_train.group_by(PROFILE_KEYS).agg(*summary_exprs)
center_cols = PROFILE_KEYS + [f"{feature}__median" for feature in RAW_FEATURES]
with_centers = profile_train.join(profile_summary.select(center_cols), on=PROFILE_KEYS)
mad_exprs = [
    (pl.col(feature) - pl.col(f"{feature}__median")).abs().median().alias(f"{feature}__mad")
    for feature in RAW_FEATURES
]
profile_mad = with_centers.group_by(PROFILE_KEYS).agg(*mad_exprs)
profiles = profile_summary.join(profile_mad, on=PROFILE_KEYS).sort(PROFILE_KEYS)
profiles.write_csv(OUTPUT_ROOT / "machine_module_sv_calibration_profiles.csv")

# Fleet profile is learned only from development training rows and is used for cold-start external tests.
FLEET_KEYS = ["module", "sv"]
fleet_exprs = []
for feature in RAW_FEATURES:
    fleet_exprs += [
        pl.col(feature).median().alias(f"{feature}__median"),
        pl.col(feature).quantile(0.25).alias(f"{feature}__q25"),
        pl.col(feature).quantile(0.75).alias(f"{feature}__q75"),
        pl.col(feature).quantile(0.05).alias(f"{feature}__q05"),
        pl.col(feature).quantile(0.95).alias(f"{feature}__q95"),
    ]
fleet_summary = profile_train.group_by(FLEET_KEYS).agg(pl.len().alias("n_minutes"), *fleet_exprs)
fleet_centers = FLEET_KEYS + [f"{feature}__median" for feature in RAW_FEATURES]
fleet_with_centers = profile_train.join(fleet_summary.select(fleet_centers), on=FLEET_KEYS)
fleet_mad = fleet_with_centers.group_by(FLEET_KEYS).agg(*[
    (pl.col(feature) - pl.col(f"{feature}__median")).abs().median().alias(f"{feature}__mad")
    for feature in RAW_FEATURES
])
fleet_profiles = fleet_summary.join(fleet_mad, on=FLEET_KEYS).sort(FLEET_KEYS)
fleet_profiles.write_csv(OUTPUT_ROOT / "fleet_cold_start_profiles.csv")

display(profiles.select([*PROFILE_KEYS, "n_minutes", "n_days", "hp2__median", "hp2__mad", "valve__median", "valve__mad"]).head(24).to_pandas())
"""
    ),
    md("## 7. Save one JSON calibration profile per development machine"),
    code(
        r"""
profiles_pdf = profiles.to_pandas()
cutoffs_pdf = cutoffs.to_pandas().set_index("machine_number")

for machine in development_machines:
    rows = profiles_pdf[profiles_pdf["machine_number"] == machine]
    payload = {
        "machine_number": machine,
        "source": "baseline_stats.csv eligibility + first 70% temporal profile window",
        "cutoff_date": str(cutoffs_pdf.loc[machine, "cutoff_date"]),
        "profile_version": "cold-state-relationship-v2",
        "features": RAW_FEATURES,
        "profiles": [],
    }
    for row in rows.to_dict(orient="records"):
        profile = {
            "module": int(row["module"]), "sv": row["sv"],
            "n_minutes": int(row["n_minutes"]), "n_days": int(row["n_days"]),
            "statistics": {},
        }
        for feature in RAW_FEATURES:
            profile["statistics"][feature] = {
                key: (None if pd.isna(row[f"{feature}__{key}"]) else float(row[f"{feature}__{key}"]))
                for key in ["median", "mad", "q25", "q75", "q05", "q95"]
            }
        payload["profiles"].append(profile)
    (PROFILE_ROOT / f"machine_{machine}_calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

print(f"Saved {len(list(PROFILE_ROOT.glob('machine_*_calibration.json')))} machine profiles")
"""
    ),
    md("## 8. Convert raw features to robust relative features"),
    code(
        r"""
def apply_profiles(frame: pl.DataFrame, profile_table: pl.DataFrame, keys, profile_source: str) -> pl.DataFrame:
    needed = list(keys)
    for feature in RAW_FEATURES:
        needed += [f"{feature}__median", f"{feature}__mad", f"{feature}__q25", f"{feature}__q75"]
    result = frame.join(profile_table.select(needed), on=list(keys), how="inner")
    expressions = []
    for feature in RAW_FEATURES:
        iqr_scale = (pl.col(f"{feature}__q75") - pl.col(f"{feature}__q25")) / 1.349
        scale = (
            pl.when(pl.col(f"{feature}__mad") > 1e-9).then(pl.col(f"{feature}__mad") / 0.67448975)
            .when(iqr_scale > 1e-9).then(iqr_scale)
            .otherwise(1.0)
        )
        expressions.append(
            ((pl.col(feature) - pl.col(f"{feature}__median")) / scale)
            .clip(-12, 12).alias(f"rz_{feature}")
        )
    return result.with_columns(*expressions, pl.lit(profile_source).alias("profile_source"))

development_relative = apply_profiles(development_features, profiles, PROFILE_KEYS, "machine_early_window")
external_relative = apply_profiles(external_features, fleet_profiles, FLEET_KEYS, "fleet_cold_start")

model_rows = pl.concat([
    development_relative.select(["machine_number", "module", "sv", "minute", "is_profile_train", "profile_source", *MODEL_FEATURES]),
    external_relative.with_columns(pl.lit(False).alias("is_profile_train")).select(
        ["machine_number", "module", "sv", "minute", "is_profile_train", "profile_source", *MODEL_FEATURES]
    ),
], how="vertical")
model_rows.write_parquet(OUTPUT_ROOT / "ml_relative_features.parquet", compression="zstd")

print(f"Development relative rows: {development_relative.height:,}")
print(f"External relative rows: {external_relative.height:,}")
"""
    ),
    md("## 9. Shared anomaly model and evaluation helpers"),
    code(
        r"""
def to_model_frame(frame: pl.DataFrame) -> pd.DataFrame:
    return frame.select(["machine_number", "module", "sv", "minute", *MODEL_FEATURES]).to_pandas()

def balanced_sample(pdf: pd.DataFrame, machines, per_machine, seed):
    parts = []
    for machine in machines:
        part = pdf[pdf["machine_number"] == machine]
        if part.empty:
            continue
        parts.append(part.sample(n=min(per_machine, len(part)), random_state=seed))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=pdf.columns)

def fit_detector(train_pdf: pd.DataFrame, seed=RANDOM_STATE):
    imputer = SimpleImputer(strategy="median")
    x = imputer.fit_transform(train_pdf[MODEL_FEATURES])
    detector = IsolationForest(
        n_estimators=N_TREES, max_samples=min(MAX_SAMPLES_PER_TREE, len(x)),
        contamination="auto", random_state=seed, n_jobs=-1,
    )
    detector.fit(x)
    train_scores = detector.decision_function(x)
    thresholds = {
        "watch": float(np.quantile(train_scores, 0.025)),
        "alert": float(np.quantile(train_scores, 0.010)),
    }
    return imputer, detector, thresholds

def score_frame(pdf, imputer, detector, thresholds):
    if pdf.empty:
        return pdf.assign(anomaly_score=np.nan, watch=False, alert=False)
    scores = detector.decision_function(imputer.transform(pdf[MODEL_FEATURES]))
    result = pdf.copy()
    result["anomaly_score"] = scores
    result["watch"] = scores <= thresholds["watch"]
    result["alert"] = scores <= thresholds["alert"]
    return result

development_pdf = to_model_frame(development_relative)
development_pdf["is_profile_train"] = development_relative.get_column("is_profile_train").to_numpy()
external_pdf = to_model_frame(external_relative)

global_train = balanced_sample(
    development_pdf[development_pdf["is_profile_train"]], development_machines,
    MODEL_SAMPLE_PER_MACHINE, RANDOM_STATE,
)
imputer, detector, thresholds = fit_detector(global_train)

model_bundle = {
    "imputer": imputer, "detector": detector, "thresholds": thresholds,
    "model_features": MODEL_FEATURES, "raw_features": RAW_FEATURES,
    "development_machines": development_machines,
    "external_test_machines": external_test_machines,
    "validation_design": "70/30 temporal + leave-one-machine-out + external cold-start test",
}
joblib.dump(model_bundle, OUTPUT_ROOT / "shared_relative_isolation_forest.joblib")
print("Thresholds:", thresholds)
"""
    ),
    md("## 10. Temporal validation on the final 30% of each development machine"),
    code(
        r"""
temporal_rows = []
for machine in development_machines:
    late = development_pdf[
        (development_pdf["machine_number"] == machine) & (~development_pdf["is_profile_train"])
    ]
    late = late.sample(n=min(EVAL_SAMPLE_PER_MACHINE, len(late)), random_state=RANDOM_STATE)
    scored = score_frame(late, imputer, detector, thresholds)
    temporal_rows.append({
        "machine_number": machine, "n_scored": len(scored),
        "watch_rate_pct": 100 * scored["watch"].mean(),
        "alert_rate_pct": 100 * scored["alert"].mean(),
        "median_score": scored["anomaly_score"].median(),
    })

temporal_validation = pd.DataFrame(temporal_rows)
temporal_validation.to_csv(OUTPUT_ROOT / "temporal_validation.csv", index=False)
display(temporal_validation.sort_values("alert_rate_pct", ascending=False))
"""
    ),
    md("## 11. Leave-One-Machine-Out validation"),
    code(
        r"""
lomo_rows = []
for fold, held_out in enumerate(development_machines, start=1):
    fold_train_machines = [m for m in development_machines if m != held_out]
    fold_train = balanced_sample(
        development_pdf[development_pdf["is_profile_train"]], fold_train_machines,
        MODEL_SAMPLE_PER_MACHINE, RANDOM_STATE + fold,
    )
    fold_imputer, fold_detector, fold_thresholds = fit_detector(fold_train, RANDOM_STATE + fold)
    held_out_late = development_pdf[
        (development_pdf["machine_number"] == held_out) & (~development_pdf["is_profile_train"])
    ]
    held_out_late = held_out_late.sample(
        n=min(EVAL_SAMPLE_PER_MACHINE, len(held_out_late)), random_state=RANDOM_STATE + fold
    )
    scored = score_frame(held_out_late, fold_imputer, fold_detector, fold_thresholds)
    lomo_rows.append({
        "held_out_machine": held_out, "train_machines": len(fold_train_machines),
        "n_scored": len(scored),
        "watch_rate_pct": 100 * scored["watch"].mean(),
        "alert_rate_pct": 100 * scored["alert"].mean(),
        "median_score": scored["anomaly_score"].median(),
        "watch_threshold": fold_thresholds["watch"],
        "alert_threshold": fold_thresholds["alert"],
    })
    print(f"LOMO {fold:02d}/{len(development_machines)}: held out {held_out}")

lomo_validation = pd.DataFrame(lomo_rows)
lomo_validation.to_csv(OUTPUT_ROOT / "lomo_validation.csv", index=False)
display(lomo_validation.sort_values("alert_rate_pct", ascending=False))
"""
    ),
    md("## 12. External test — short-history and insufficient-data machines"),
    code(
        r"""
external_rows_summary = []
for machine in external_test_machines:
    test = external_pdf[external_pdf["machine_number"] == machine]
    test = test.sample(n=min(EVAL_SAMPLE_PER_MACHINE, len(test)), random_state=RANDOM_STATE)
    scored = score_frame(test, imputer, detector, thresholds)
    external_rows_summary.append({
        "machine_number": machine, "n_scored": len(scored),
        "profile_source": "fleet_cold_start",
        "watch_rate_pct": 100 * scored["watch"].mean(),
        "alert_rate_pct": 100 * scored["alert"].mean(),
        "median_score": scored["anomaly_score"].median(),
    })

external_test = pd.DataFrame(external_rows_summary)
external_test.to_csv(OUTPUT_ROOT / "external_test_results.csv", index=False)
display(external_test.sort_values("alert_rate_pct", ascending=False))
"""
    ),
    md("## 13. Validation charts"),
    code(
        r"""
fig, axes = plt.subplots(3, 1, figsize=(13, 12), constrained_layout=True)

for ax, table, label_col, title in [
    (axes[0], temporal_validation, "machine_number", "Temporal validation — late 30%"),
    (axes[1], lomo_validation, "held_out_machine", "Leave-One-Machine-Out — held-out late window"),
    (axes[2], external_test, "machine_number", "External cold-start test — short/insufficient history"),
]:
    ordered = table.sort_values("alert_rate_pct", ascending=False)
    x = np.arange(len(ordered))
    ax.bar(x - 0.18, ordered["watch_rate_pct"], width=0.36, label="Watch")
    ax.bar(x + 0.18, ordered["alert_rate_pct"], width=0.36, label="Alert")
    ax.axhline(2.5, color="#6b7280", ls="--", lw=1, label="Train watch reference 2.5%")
    ax.axhline(1.0, color="#111827", ls=":", lw=1, label="Train alert reference 1.0%")
    ax.set_xticks(x, ordered[label_col].astype(str))
    ax.set_ylabel("flag rate (%)")
    ax.set_title(title)
    ax.legend(ncol=4, fontsize=8)

fig.savefig(FIGURE_ROOT / "01_validation_flag_rates.png", dpi=170, bbox_inches="tight")
plt.show()
"""
    ),
    md("## 14. Feature-family portability"),
    code(
        r"""
family_map = {}
for feature in MODEL_FEATURES:
    raw = feature.removeprefix("rz_")
    if raw in BASE_FEATURES:
        family_map[feature] = "robust level"
    elif raw in DERIVED_FEATURES:
        family_map[feature] = "pressure differential"
    elif "slope" in raw:
        family_map[feature] = "rolling slope"
    else:
        family_map[feature] = "lag response"

late_all = development_pdf[~development_pdf["is_profile_train"]]
portability_rows = []
for feature in MODEL_FEATURES:
    machine_medians = late_all.groupby("machine_number")[feature].median()
    portability_rows.append({
        "feature": feature,
        "family": family_map[feature],
        "between_machine_iqr_of_late_medians": machine_medians.quantile(0.75) - machine_medians.quantile(0.25),
        "median_abs_late_value": late_all[feature].abs().median(),
        "missing_pct": 100 * late_all[feature].isna().mean(),
    })

feature_portability = pd.DataFrame(portability_rows).sort_values("between_machine_iqr_of_late_medians")
feature_portability.to_csv(OUTPUT_ROOT / "feature_portability.csv", index=False)
display(feature_portability)

family_summary = feature_portability.groupby("family", as_index=False).agg(
    median_between_machine_iqr=("between_machine_iqr_of_late_medians", "median"),
    median_abs_value=("median_abs_late_value", "median"),
    median_missing_pct=("missing_pct", "median"),
)
display(family_summary.sort_values("median_between_machine_iqr"))
"""
    ),
    md("## 15. Final summary and handoff"),
    code(
        r"""
summary = {
    "development_machines": development_machines,
    "external_test_machines": external_test_machines,
    "development_machine_count": len(development_machines),
    "external_test_machine_count": len(external_test_machines),
    "calibration_profile_files": len(list(PROFILE_ROOT.glob("machine_*_calibration.json"))),
    "raw_feature_count": len(RAW_FEATURES),
    "model_feature_count": len(MODEL_FEATURES),
    "temporal_validation_median_alert_pct": float(temporal_validation.alert_rate_pct.median()),
    "lomo_median_alert_pct": float(lomo_validation.alert_rate_pct.median()),
    "external_test_median_alert_pct": float(external_test.alert_rate_pct.median()),
    "important_limit": "No confirmed failure labels; flag rates measure calibration/transfer, not diagnostic accuracy.",
}
(OUTPUT_ROOT / "ml_validation_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nArtifacts:")
print("- calibration_profiles/*.json")
print("- machine_module_sv_calibration_profiles.csv")
print("- ml_relative_features.parquet")
print("- shared_relative_isolation_forest.joblib")
print("- temporal_validation.csv / lomo_validation.csv / external_test_results.csv")
"""
    ),
    md(
        """
## Interpretation guardrails

- External-test flag rate สูงไม่ได้แปลว่าเครื่องเสีย เพราะเครื่องกลุ่มนี้ไม่มี profile ของตัวเองและใช้ fleet cold-start profile
- LOMO ทดสอบการย้าย shared model ข้ามเครื่อง แต่ held-out machine ยังใช้ early-window profile ของตัวเองตาม deployment design
- Relative feature ลด absolute offset แต่ไม่ทดแทน recipe, actual controlled temperature, facility water หรือ maintenance label
- ก่อนใช้งานจริงควรรัน shadow mode และให้ช่างยืนยันเหตุการณ์ที่ถูก flag
"""
    ),
]

nbf.write(nb, OUTPUT)
print(OUTPUT)
