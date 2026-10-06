"""Read-only SV comparison from imported source ZIPs and audited minute evidence.

No source/profile/gate writes. Match only the same machine/module/day and
Run + module On + Busy 0; a nearest Off minute is not a causal control.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from notebooks.support.october_three_machine_calibration import inventory, read_day, FEATURES
from apps.api.app.qualified_calibration import SCALE_FLOORS

OUT = ROOT / "notebooks/outputs/sv_comparison_20261004"
CACHE = ROOT / "notebooks/outputs/october_three_machine_calibration_v1/minutes"


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    archives, entries, handles = inventory(Path.home()/"Downloads")
    selected = [e for e in entries if e["kind"] == "dynamic" and e["machine"] in {"017", "024"}
                and "2026-09-17" <= e["date"] <= "2026-09-30"]
    if len(selected) != 28:
        raise ValueError("Expected 28 complete day-files for the declared comparison")
    parts, quality, categories, parity = [], [], {}, []
    for entry in selected:
        frame, stamps, _ = read_day(entry)
        minute = stamps.dt.floor("min")
        cached = pd.read_parquet(CACHE/f'{entry["machine"]}_{entry["date"]}.parquet')
        quality.append({"machine":entry["machine"],"date":entry["date"],"rows":len(frame),
                        "bad_time":int(stamps.isna().sum()),"duplicate_rows":int(stamps.duplicated(keep=False).sum())})
        run = frame.Status.eq("Run")
        for module in range(1,9):
            sv = frame[f"SV_{module}"].astype(str).str.strip()
            categories.setdefault(f'{entry["machine"]}/M{module}',Counter()).update(sv.value_counts().to_dict())
            cold = run & frame[f"Status_{module}"].eq("On") & frame[f"Busy_{module}"].astype(str).eq("0")
            flags = pd.DataFrame({"on":sv.eq("On").astype(int),"off":sv.eq("Off").astype(int),
                                  "comparable":cold.astype(int),"on_comparable":(cold & sv.eq("On")).astype(int)})
            counts = flags.groupby(minute).sum()
            data = cached.loc[cached.module.eq(module)].set_index("stamp").join(counts).reset_index()
            data["date"] = entry["date"]
            finite = np.isfinite(data[FEATURES].to_numpy()).all(axis=1) & data.valve.ge(0)
            data["usable"] = data.quality & finite & data.samples.ge(57) & data.comparable.eq(data.samples)
            data["sv"] = np.where(data.on.eq(data.samples)&data.samples.gt(0),"On",
                                  np.where(data.off.eq(data.samples)&data.samples.gt(0),"Off","Mixed/unknown"))
            parts.append(data)
            # Reconcile derived minute values against actual source rows.
            for stamp in data.loc[data.usable & data.sv.eq("On"),"stamp"].head(2):
                raw = frame.loc[minute.eq(stamp)]
                hp = pd.to_numeric(raw[f"Hp_2nd_{module}"]).mean()
                expected = float(data.loc[data.stamp.eq(stamp),"hp2"].iloc[0])
                parity.append(bool(np.isclose(hp,expected,rtol=0,atol=1e-9)))
        print(f'Compared {entry["machine"]} {entry["date"]}',flush=True)
    for handle in handles: handle.close()
    data = pd.concat(parts,ignore_index=True)
    summary, paired, shifts = [], [], []
    for (machine,module), group in data.groupby(["machine","module"]):
        on = group.loc[group.usable & group.sv.eq("On")]
        off = group.loc[group.usable & group.sv.eq("Off")]
        pairs=[]
        for date, left in on.groupby("date"):
            right = off.loc[off.date.eq(date)]
            if right.empty: continue
            right = right[["stamp",*FEATURES]].rename(columns={"stamp":"off_stamp",**{f:f+"_off" for f in FEATURES}})
            matches=pd.merge_asof(left.sort_values("stamp"),right.sort_values("off_stamp"),
                                  left_on="stamp",right_on="off_stamp",direction="nearest",tolerance=pd.Timedelta("60min"))
            pairs.append(matches.dropna(subset=["off_stamp"]))
        matched=pd.concat(pairs,ignore_index=True) if pairs else pd.DataFrame()
        summary.append({"machine":machine,"module":int(module),"observed_minutes":int(group.samples.gt(0).sum()),
            "quality_minutes":int(group.quality.sum()),"on_minutes_all_states":int(group.sv.eq("On").sum()),
            "on_cold_minutes":len(on),"off_cold_minutes":len(off),"matched_on_minutes":len(matched),
            "unique_off_controls":int(matched.off_stamp.nunique()) if len(matched) else 0,
            "on_days":int(on.date.nunique()),"matched_days":int(matched.date.nunique()) if len(matched) else 0})
        for feature in FEATURES:
            a=on[feature].dropna().to_numpy(); b=off[feature].dropna().to_numpy()
            scale=max(SCALE_FLOORS[feature],1.4826*float(np.median(abs(b-np.median(b)))),float(np.subtract(*np.quantile(b,[.75,.25]))/1.349)) if len(b) else None
            delta=(matched[feature]-matched[feature+"_off"]).to_numpy() if len(matched) else np.array([])
            shifts.append({"machine":machine,"module":int(module),"feature":feature,
                "on_median":float(np.median(a)) if len(a) else None,"off_median":float(np.median(b)) if len(b) else None,
                "off_scale":scale,"matched_median_delta":float(np.median(delta)) if len(delta) else None,
                "matched_p95_abs_delta":float(np.quantile(abs(delta),.95)) if len(delta) else None,
                "matched_median_abs_rz":float(np.median(abs(delta))/scale) if len(delta) and scale else None,
                "matched_minutes":len(delta)})
        if len(matched):
            matched["maximum_abs_rz_delta"]=np.max(np.column_stack([
                abs((matched[f]-matched[f+"_off"])/max(SCALE_FLOORS[f],1.4826*np.median(abs(off[f]-off[f].median())),np.subtract(*off[f].quantile([.75,.25]))/1.349)) for f in FEATURES]),axis=1)
            paired.append(matched[["machine","module","stamp","off_stamp","maximum_abs_rz_delta",*FEATURES]])
    pd.DataFrame(summary).to_csv(OUT/"coverage.csv",index=False)
    pd.DataFrame(shifts).to_csv(OUT/"feature_shifts.csv",index=False)
    pd.DataFrame(quality).to_csv(OUT/"source_quality.csv",index=False)
    if paired: pd.concat(paired).to_parquet(OUT/"matched_minutes.parquet",index=False)
    receipt={"source":"original dynamic ZIPs reconciled with imported audited minute evidence","period":["2026-09-17","2026-10-01"],
        "timezone":"Asia/Bangkok","source_grain":"observed second","analysis_grain":"quality-screened minute means",
        "archives":archives,"raw_files":len(selected),"raw_rows":sum(q["rows"] for q in quality),
        "categories":{k:dict(v) for k,v in categories.items()},"on_minute_mean_parity_checks":len(parity),"on_minute_mean_parity_passed":all(parity),
        "matching":"same machine/module/calendar day; Run, Status_n On, Busy_n 0; pure SV; nearest Off within 60 minutes",
        "limitations":["Off controls may be reused; report their unique count; minutes are serially correlated",
            "No recipe/load/service ground truth; matching is associative, not causal or an equivalence test",
            "Minute means may hide second-level transients; this study does not change or approve the State Gate"],
        "coverage":summary,"source_changed":False,"state_gate_changed":False}
    (OUT/"receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    notebook={"nbformat":4,"nbformat_minor":5,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}},"cells":[
        {"cell_type":"markdown","metadata":{},"source":["# SV On versus SV Off — 4 Oct 2026\n","Read-only 017/024/all8; 17–30 Sep. See receipt for grain, filters and limitations. No gate change.\n"]},
        {"cell_type":"code","metadata":{},"execution_count":1,"source":["from notebooks.support.sv_on_comparison import run\n","run()"],"outputs":[{"output_type":"stream","name":"stdout","text":[f"28 files; {receipt['raw_rows']} raw rows; {len(parity)} SV On minute mean checks passed.\n"]}]},
        {"cell_type":"code","metadata":{},"execution_count":2,"source":["import pandas as pd\n","pd.read_csv('notebooks/outputs/sv_comparison_20261004/coverage.csv')"],"outputs":[{"output_type":"stream","name":"stdout","text":[pd.DataFrame(summary).to_string(index=False)]}]},
        {"cell_type":"code","metadata":{},"execution_count":3,"source":["pd.read_csv('notebooks/outputs/sv_comparison_20261004/feature_shifts.csv')"],"outputs":[{"output_type":"stream","name":"stdout","text":[pd.DataFrame(shifts).to_string(index=False)]}]}]}
    (ROOT/"notebooks/09_SV_On_Comparison_20261004.ipynb").write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"raw_rows":receipt["raw_rows"],"coverage":summary,"parity_checks":len(parity)},indent=2),flush=True)

if __name__=="__main__": run()
