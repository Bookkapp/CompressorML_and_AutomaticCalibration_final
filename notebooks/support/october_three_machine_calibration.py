"""Read-only ZIP audit and calibration diagnostics. No DB/Active/worker writes.

Raw seconds are processed one day at a time. The cache is derived local evidence,
not an approved normal dataset. Source timestamps stay naive/source-clock.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = ["hp1", "lp1", "hp2", "lp2", "valve", "temphi", "templo", "dp1", "dp2"]
TAGS = dict(zip(FEATURES[:7], ["Hp_1st", "Lp_1st", "Hp_2nd", "Lp_2nd", "Valve", "TempHi", "TempLo"]))
PATTERN = re.compile(r"(2026_\d{2}_\d{2})(_Static)?\.txt$")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "october_three_machine_calibration_v1"


def inventory(downloads: Path):
    archives = []
    entries = []
    handles = []
    for path in sorted(downloads.glob("HT9046MX-Compressor-Data-20261001*.zip")):
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        outer = zipfile.ZipFile(path)
        handles.append(outer)
        archives.append({"archive": path.name, "bytes": path.stat().st_size, "sha256": digest})
        for item in outer.infolist():
            if item.filename.endswith(".zip"):
                nested = zipfile.ZipFile(io.BytesIO(outer.read(item)))
                handles.append(nested)
                machine = item.filename.split("/")[1]
                candidates = [(nested, inner, machine, item.filename) for inner in nested.infolist()]
            else:
                candidates = [(outer, item, item.filename.split("/")[1], "")]
            for archive, inner, machine, nested_name in candidates:
                match = PATTERN.search(inner.filename)
                if not match:
                    continue
                entries.append({"archive": path.name, "nested": nested_name, "member": inner.filename,
                                "machine": machine, "date": match[1].replace("_", "-"),
                                "kind": "static" if match[2] else "dynamic", "bytes": inner.file_size,
                                "crc32": inner.CRC, "handle": archive, "info": inner})
    keys = [(e["machine"], e["date"], e["kind"]) for e in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate machine/date/kind members; reconcile before ingestion")
    return archives, sorted(entries, key=lambda e: (e["machine"], e["date"], e["kind"])), handles


def read_day(entry, nrows=None):
    with entry["handle"].open(entry["info"]) as stream:
        first = stream.readline().decode("utf-8-sig").strip()
    skip = 0 if first.startswith("Time") else 1
    with entry["handle"].open(entry["info"]) as stream:
        frame = pd.read_csv(stream, skiprows=skip, skipinitialspace=True, low_memory=False, nrows=nrows)
    frame.columns = frame.columns.str.strip()
    for column in frame.select_dtypes(include="object"):
        frame[column] = frame[column].str.strip()
    stamps = pd.to_datetime(entry["date"] + " " + frame["Time"], errors="coerce")
    return frame, stamps, first if skip else None


def minute_day(frame, stamps, machine, tails, event_rows, trajectory_parts):
    """Vectorized equivalent of the v1 1m gate, with additional audit fields."""
    valid = stamps.notna()
    frame = frame.loc[valid].copy()
    frame["stamp"] = stamps.loc[valid].values
    frame = frame.sort_values("stamp", kind="stable").reset_index(drop=True)
    stamp = frame["stamp"]
    seconds = stamp.astype("int64").to_numpy() // 10**9
    minute = stamp.dt.floor("min")
    index = pd.date_range(stamp.iloc[0].normalize(), periods=1440, freq="min")
    groups = frame.groupby(minute, sort=True)
    base = groups["stamp"].agg(["size", "min", "max", "nunique"]).reindex(index)
    base["coverage"] = base["nunique"].fillna(0) / 60
    gap = stamp.diff().dt.total_seconds().where(minute.eq(minute.shift()))
    internal = gap.groupby(minute).max().reindex(index).fillna(0)
    first_gap = (base["min"] - pd.Series(index, index=index)).dt.total_seconds()
    last_gap = (pd.Series(index + pd.Timedelta(minutes=1), index=index) - base["max"]).dt.total_seconds()
    base["gap"] = pd.concat([internal, first_gap, last_gap], axis=1).max(axis=1)
    quality = base["nunique"].ge(57) & base["size"].eq(base["nunique"]) & base["gap"].le(5)
    run = frame["Status"].eq("Run").to_numpy()
    results = []
    for module in range(1, 9):
        numeric = pd.DataFrame({f: pd.to_numeric(frame[f"{tag}_{module}"], errors="coerce") for f, tag in TAGS.items()})
        numeric["dp1"] = numeric.hp1 - numeric.lp1
        numeric["dp2"] = numeric.hp2 - numeric.lp2
        busy = frame[f"Busy_{module}"].astype(str).to_numpy()
        modstate = frame[f"Status_{module}"].astype(str).to_numpy()
        sv = frame[f"SV_{module}"].astype(str).to_numpy()
        cold = run & (modstate == "On") & (busy == "0") & (sv == "Off")
        finite = np.isfinite(numeric.to_numpy()).all(axis=1) & numeric.valve.ge(0).to_numpy()
        means = numeric.groupby(minute).mean().reindex(index)
        sd = numeric[["hp2", "temphi", "templo"]].groupby(minute).std(ddof=0).reindex(index).add_suffix("_std")
        cold_count = pd.Series(cold).groupby(minute).sum().reindex(index).fillna(0)
        finite_count = pd.Series(finite).groupby(minute).sum().reindex(index).fillna(0)
        out = pd.concat([means, sd], axis=1)
        out["eligible"] = quality & cold_count.eq(base["size"]) & finite_count.eq(base["size"])
        out["quality"] = quality
        out["samples"] = base["size"].fillna(0).astype(int)
        out["gap"] = base["gap"]
        out["cold_seconds"] = cold_count.astype(int)
        out["manual_seconds"] = pd.Series(busy == "1").groupby(minute).sum().reindex(index).fillna(0).astype(int)
        out["run_seconds"] = pd.Series(run).groupby(minute).sum().reindex(index).fillna(0).astype(int)
        out["module_on_seconds"] = pd.Series(modstate == "On").groupby(minute).sum().reindex(index).fillna(0).astype(int)
        out["sv_off_seconds"] = pd.Series(sv == "Off").groupby(minute).sum().reindex(index).fillna(0).astype(int)
        previous = tails.get((machine, module))
        prior_cold = np.r_[previous["cold"] if previous else False, cold[:-1]]
        prior_s = np.r_[previous["second"] if previous else seconds[0] - 99999, seconds[:-1]]
        continuity = (seconds - prior_s > 0) & (seconds - prior_s <= 2)
        start_mask = cold & (~prior_cold | ~continuity)
        starts = np.flatnonzero(start_mask)
        marker = np.full(len(frame), np.nan)
        if previous and previous["cold"] and continuity[0]:
            marker[0] = previous["onset"]
        marker[starts] = seconds[starts]
        onset = pd.Series(marker).ffill().to_numpy()
        onset[~cold] = np.nan
        known_marker = np.full(len(frame), np.nan)
        if previous and previous["cold"] and continuity[0]:
            known_marker[0] = int(previous["known"])
        known_marker[starts] = continuity[starts].astype(int)
        known = pd.Series(known_marker).ffill().fillna(0).to_numpy().astype(bool) & cold
        elapsed = np.where(known, seconds - onset, np.nan)
        out["elapsed_min_seconds"] = pd.Series(elapsed).groupby(minute).min().reindex(index)
        out["elapsed_known_seconds"] = pd.Series(np.isfinite(elapsed)).groupby(minute).sum().reindex(index).fillna(0).astype(int)
        # Sampling of raw trajectory storage is bounded; the event ledger is not.
        kept_by_kind = Counter()
        prior_busy = np.concatenate(([previous["busy"] if previous else ""], busy[:-1]))
        prior_run = np.r_[previous["run"] if previous else False, run[:-1]]
        for pos in starts:
            kind = "UNKNOWN_GAP_OR_LEFT_CENSORED" if not continuity[pos] else (
                "POST_MANUAL" if prior_busy[pos] == "1" else "OBSERVED_RUN_START" if not prior_run[pos] else "COLD_CONTROL_ENTRY")
            stop_candidates = np.flatnonzero(~cold[pos:] | ~np.r_[True, continuity[pos+1:]])
            stop = pos + (int(stop_candidates[0]) if len(stop_candidates) else len(frame)-pos)
            duration = int(seconds[stop-1] - seconds[pos] + 1) if stop > pos else 0
            event_id = f"{machine}-M{module}-{stamp.iloc[pos].isoformat()}"
            event_rows.append({"event_id": event_id, "machine": machine, "module": module,
                               "start": stamp.iloc[pos], "kind": kind, "observed_duration_seconds": duration,
                               "right_censored_at_day_end": bool(stop == len(frame)),
                               "initial_hp2": numeric.hp2.iloc[pos], "initial_templo": numeric.templo.iloc[pos],
                               "initial_valve": numeric.valve.iloc[pos]})
            if continuity[pos] and duration >= 120 and kept_by_kind[kind] < 5:
                end = min(stop, int(np.searchsorted(seconds, seconds[pos] + 1801)))
                tr = numeric.iloc[pos:end].copy()
                tr["elapsed"] = seconds[pos:end] - seconds[pos]
                tr["event_id"] = event_id
                tr["kind"] = kind
                tr["machine"] = machine
                tr["module"] = module
                trajectory_parts.append(tr)
                kept_by_kind[kind] += 1
        tails[(machine, module)] = {"cold": bool(cold[-1]), "second": int(seconds[-1]),
                                   "onset": float(onset[-1]), "known": bool(known[-1]),
                                   "busy": busy[-1], "run": bool(run[-1])}
        out["stamp"] = index
        out["machine"] = machine
        out["module"] = module
        results.append(out.reset_index(drop=True))
    return pd.concat(results, ignore_index=True)


def ingest(downloads: Path, output: Path, limit: int | None = None):
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    (output / "minutes").mkdir(exist_ok=True)
    (output / "trajectories").mkdir(exist_ok=True)
    archives, entries, handles = inventory(downloads)
    pd.DataFrame([{k:v for k,v in e.items() if k not in ("handle", "info")} for e in entries]).to_csv(output / "file_inventory.csv", index=False)
    quality_rows, event_rows, categories, tails = [], [], {}, {}
    dynamic_count = 0
    for entry in entries:
        if entry["kind"] == "static":
            continue  # Owner excluded static logs; inventory only, never parse/use.
        if limit is not None and entry["kind"] == "dynamic" and dynamic_count >= limit:
            continue
        frame, stamps, version = read_day(entry)
        key = f'{entry["machine"]}_{entry["date"]}'
        q = {k:entry[k] for k in ("machine", "date", "kind", "bytes")}
        q.update(rows=len(frame), columns=len(frame.columns), bad_time=int(stamps.isna().sum()),
                 duplicate_seconds=int(stamps.duplicated(keep=False).sum()), first=str(stamps.min()), last=str(stamps.max()),
                 firmware=version, missing_cells=int(frame.isna().sum().sum()),
                 nonmonotonic=int((stamps.diff().dt.total_seconds()<0).sum()),
                 one_second_intervals=int(stamps.diff().dt.total_seconds().eq(1).sum()), intervals=max(0,len(frame)-1))
        quality_rows.append(q)
        dynamic_count += 1
        for column in ["Status"] + [f"{tag}_{m}" for m in range(1,9) for tag in ("Status", "Busy", "SV")]:
            categories.setdefault(column, Counter()).update(frame[column].astype(str).value_counts().to_dict())
        trajectories = []
        minute_day(frame, stamps, entry["machine"], tails, event_rows, trajectories).to_parquet(output / "minutes" / f"{key}.parquet", index=False)
        if trajectories:
            pd.concat(trajectories, ignore_index=True).to_parquet(output / "trajectories" / f"{key}.parquet", index=False)
        if dynamic_count % 10 == 0:
            print(f"Parsed {dynamic_count} raw day-files; current {key}; elapsed {time.perf_counter()-started:.1f}s", flush=True)
    pd.DataFrame(quality_rows).to_csv(output / "quality.csv", index=False)
    pd.DataFrame(event_rows).to_parquet(output / "events.parquet", index=False)
    manifest = {"archives": archives, "machine_ids": sorted({e["machine"] for e in entries}),
                "source_clock": "naive historian clock; Asia/Bangkok interpretation assumed for local review only",
                "units": "source pressure presumed psi, temperature degC, Valve command count; no independent calibration certificate",
                "dynamic_day_files_processed": dynamic_count, "member_count": len(entries),
                "runtime_seconds": time.perf_counter()-started, "raw_inputs_changed": False,
                "trajectory_sampling": "all event metadata; first five per module/day/kind with >=120 observed consecutive Cold seconds, raw0..1800s; day-end censored",
                "window_gate": "57/60 unique seconds, gap including edges<=5s, no duplicate, all Run/On/Busy0/SVOff finite7tags, Valve>=0",
                "window_aggregation": "means over observed seconds, dp derived from means",
                "code_sha256": hashlib.file_digest(Path(__file__).open('rb'), 'sha256').hexdigest()}
    (output / "ingestion_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for h in handles:
        h.close()
    print(json.dumps(manifest, indent=2), flush=True)


def load_minutes(output: Path):
    data = pd.read_parquet(output / "minutes")
    data["machine"] = data["machine"].astype('category')
    data["module"] = data["module"].astype('int8')
    for column in ('samples','cold_seconds','manual_seconds','run_seconds','module_on_seconds','sv_off_seconds','elapsed_known_seconds'):
        data[column] = data[column].astype('int16')
    return data.sort_values(["machine", "module", "stamp"]).reset_index(drop=True)


def fit_array(data):
    values = data[FEATURES].to_numpy(dtype=float)
    med = np.median(values, axis=0)
    scale = np.maximum.reduce([1.4826*np.median(np.abs(values-med), axis=0),
                               (np.quantile(values,.75,axis=0)-np.quantile(values,.25,axis=0))/1.349,
                               np.array([1 if f=='valve' else .1 for f in FEATURES])])
    scores = np.max(np.abs((values-med)/scale),axis=1)
    keep = scores <= 8
    if keep.any():
        values = values[keep]
    med = np.median(values,axis=0)
    scale = np.maximum.reduce([1.4826*np.median(np.abs(values-med),axis=0),
                               (np.quantile(values,.75,axis=0)-np.quantile(values,.25,axis=0))/1.349,
                               np.array([1 if f=='valve' else .1 for f in FEATURES])])
    threshold = np.quantile(np.max(np.abs((values-med)/scale),axis=1),.995)
    return med, scale, float(threshold), float(100*(1-keep.mean()))


def persistent_flags(data, flags):
    adjacent = data.stamp.diff().eq(pd.Timedelta(minutes=1)).to_numpy()
    out = np.zeros(len(flags),dtype=bool)
    if len(flags) >= 3:
        out[2:] = flags[2:] & flags[1:-1] & flags[:-2] & adjacent[2:] & adjacent[1:-1]
    return out


def summarize(output: Path):
    data = load_minutes(output)
    data["date"] = data.stamp.dt.floor("D")
    data["month"] = data.stamp.dt.strftime("%Y-%m")
    # Age sensitivity only, NOT fitted settling/normal classification. Unknown onset excluded.
    data["age20"] = data.eligible & data.elapsed_known_seconds.eq(data.samples) & data.elapsed_min_seconds.ge(1200)
    context = []
    correlations = []
    daily = []
    experiments = []
    for (machine,module), group in data.groupby(["machine","module"],sort=True,observed=True):
        eligible = group[group.eligible]
        age = group[group.age20]
        context.append({"machine":machine,"module":int(module),"source_minutes":int(group.samples.gt(0).sum()),
                        "cold_minutes":len(eligible),"cold_days":eligible.date.nunique(),"age20_minutes":len(age),
                        "early20_minutes":int((group.eligible & group.elapsed_min_seconds.lt(1200)).sum()),
                        "unknown_age_minutes":int((group.eligible & group.elapsed_known_seconds.ne(group.samples)).sum()),
                        "manual_seconds":int(group.manual_seconds.sum()),
                        **{f'{f}_q{p}':float(age[f].quantile(p/100)) for f in FEATURES for p in (5,50,95)},
                        **{f'{f}_all_q{p}':float(eligible[f].quantile(p/100)) for f in FEATURES for p in (5,50,95)},
                        "hp2_below180_pct":100*age.hp2.lt(180).mean(),"hp2_above230_pct":100*age.hp2.gt(230).mean()})
        for day, block in eligible.groupby("date"):
            ageblock = block[block.age20]
            daily.append({"machine":machine,"module":int(module),"date":day,"n":len(block),
                          "age20_n":len(ageblock), "hp2_age20":float(ageblock.hp2.median()),
                          **{f:float(block[f].median()) for f in FEATURES},
                          **{f'{f}_iqr':float(block[f].quantile(.75)-block[f].quantile(.25)) for f in ("hp2","temphi","templo")}})
        for label, block in (("all_qualified",eligible),("age20",age),("within_day_age20",age),("within_day_all_qualified",eligible)):
            values = block[FEATURES]
            if label.startswith("within_day_"):
                values = values - block.groupby('date')[FEATURES].transform('median')
            corr = values.corr(method="spearman")
            for i,f in enumerate(FEATURES):
                for other in FEATURES[i+1:]:
                    correlations.append({"machine":machine,"module":int(module),"population":label,"x":f,"y":other,"rho":corr.loc[f,other],"n":len(block)})
        # Repeated causal past fit -> NEXT3calendar days, August onwards. Diagnostic not untouched accuracy test.
        last_full_end = pd.Timestamp("2026-10-01")
        for cut in pd.date_range("2026-08-01","2026-09-28",freq="7D"):
            shadow_end = min(cut+pd.Timedelta(days=3),last_full_end)
            for lookback in (7,14,30,60):
                for policy in ("current_state_only","observed_age20_sensitivity"):
                    mask = group.eligible if policy=="current_state_only" else group.age20
                    fit = group[mask & group.stamp.ge(cut-pd.Timedelta(days=lookback)) & group.stamp.lt(cut)]
                    test = group[group.eligible & group.stamp.ge(cut) & group.stamp.lt(shadow_end)].copy()
                    if len(fit)<200 or fit.date.nunique()<7 or not len(test):
                        continue
                    med,scale,threshold,quarantine = fit_array(fit)
                    if threshold<=0:
                        continue
                    z = (test[FEATURES].to_numpy()-med)/scale
                    scores = np.abs(z).max(axis=1)
                    flags = scores>=threshold
                    persistence = persistent_flags(test,flags)
                    early = (test.elapsed_known_seconds.eq(test.samples)&test.elapsed_min_seconds.lt(1200)).to_numpy()
                    late = (test.elapsed_known_seconds.eq(test.samples)&test.elapsed_min_seconds.ge(1200)).to_numpy()
                    experiments.append({"machine":machine,"module":int(module),"cut":cut,"lookback_days":lookback,
                                        "fit_policy":policy,"fit_n":len(fit),"fit_days":fit.date.nunique(),"quarantine_pct":quarantine,
                                        "threshold":threshold,"hp2_median":med[FEATURES.index("hp2")],"hp2_scale":scale[FEATURES.index("hp2")],
                                        "shadow_n":len(test),"shadow_expected_minutes":int((shadow_end-cut).total_seconds()/60),
                                        "shadow_qualified_pct":100*len(test)/((shadow_end-cut).total_seconds()/60),
                                        "raw_flag_n":int(flags.sum()),"persistent_n":int(persistence.sum()),
                                        "early_n":int(early.sum()),"early_flag_n":int(flags[early].sum()),
                                        "late_n":int(late.sum()),"late_flag_n":int(flags[late].sum()),
                                        "unknown_n":int((~(early|late)).sum()),
                                        "dominant_temporal_flags":int(np.isin(np.abs(z).argmax(axis=1),[5,6])[flags].sum())})
    pd.DataFrame(context).to_csv(output/"context_summary.csv",index=False)
    pd.DataFrame(daily).to_csv(output/"daily_baselines.csv",index=False)
    pd.DataFrame(correlations).to_csv(output/"correlations.csv",index=False)
    pd.DataFrame(experiments).to_csv(output/"causal_shadow_experiments.csv",index=False)
    events = pd.read_parquet(output/"events.parquet")
    events.groupby(["machine","module","kind"]).size().rename("events").reset_index().to_csv(output/"event_counts.csv",index=False)
    summary = {"module_minute_rows":len(data),"raw_present_minutes":int(data.samples.gt(0).sum()),
               "quality_minutes":int(data.quality.sum()),"qualified_cold_minutes":int(data.eligible.sum()),
               "age20_minutes":int(data.age20.sum()),"unknown_onset_cold_minutes":int((data.eligible & data.elapsed_known_seconds.ne(data.samples)).sum()),
               "context_count":len(context),"events":len(events),"causal_experiments":len(experiments),
               "normal_labels_available":False,"age20_is_sensitivity_not_live_gate":True,
               "active_or_database_changed":False}
    (output/"analysis_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
    return summary


def verify_source_parity(downloads: Path, output: Path):
    from apps.api.app.qualified_windows import build_completed_windows, WindowPolicy
    from datetime import timezone
    _, entries, handles = inventory(downloads)
    comparisons, maximum_error = 0, 0.0
    samples = []
    for machine in ('017','024','080'):
        for day in ('2026-07-01','2026-08-15','2026-09-07'):
            entry = next(e for e in entries if e['machine']==machine and e['date']==day and e['kind']=='dynamic')
            raw, stamps, _ = read_day(entry, nrows=900)
            start = stamps.min().ceil('min')
            end = start + pd.Timedelta(minutes=5)
            mask=stamps.ge(start)&stamps.lt(end)
            raw=raw[mask].reset_index(drop=True); stamps=stamps[mask].reset_index(drop=True)
            actual=minute_day(raw,stamps,machine,{},[],[])
            rows=raw.assign(recorded_at=stamps,machine_number=machine).to_dict('records')
            expected=build_completed_windows(rows,as_of=(end+pd.Timedelta(days=1)).to_pydatetime().replace(tzinfo=timezone.utc),policy=WindowPolicy('Asia/Bangkok'))
            for window in expected:
                point=actual[(actual.module==window.module)&actual.stamp.eq(window.window_start)].iloc[0]
                if bool(point.eligible)!=window.eligible:
                    raise AssertionError(f'Gate mismatch {machine}/{day}/M{window.module}/{window.window_start}')
                if window.eligible:
                    error=max(abs(point[f]-window.features[f]) for f in FEATURES)
                    maximum_error=max(maximum_error,float(error))
                    if error>1e-9: raise AssertionError('Feature mismatch')
                comparisons+=1
            samples.append({'machine':machine,'date':day,'raw_rows':len(raw),'windows':len(expected)})
    for handle in handles:handle.close()
    result={'sampled_raw_runtime_windows':comparisons,'gate_mismatches':0,'maximum_feature_absolute_error':maximum_error,
            'samples':samples,'scope':'9 bounded raw prefixes, not a full-series runtime replay'}
    (output/'source_parity_qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


def extract_run_trajectories(downloads: Path, output: Path):
    """Observed Run starts independent of Cold eligibility; retain manual/state context."""
    source=pd.read_parquet(output/'minutes',columns=['machine','module','stamp','run_seconds','samples'],filters=[('module','==',1)])
    source=source.sort_values(['machine','stamp']).reset_index(drop=True)
    source['previous_run']=source.groupby('machine',observed=True).run_seconds.shift()
    source['previous_samples']=source.groupby('machine',observed=True).samples.shift()
    # Candidate days only. The actual boundary is verified again from raw seconds.
    possible=((source.run_seconds>0)&(source.run_seconds<source.samples)) | ((source.run_seconds>0)&source.previous_run.eq(0)&source.previous_samples.gt(0))
    dates=set(zip(source.loc[possible,'machine'].astype(str),source.loc[possible,'stamp'].dt.strftime('%Y-%m-%d')))
    cold_events=pd.read_parquet(output/'events.parquet')
    for _,e in cold_events[cold_events.kind.eq('OBSERVED_RUN_START')].iterrows():
        dates.add((e.machine,pd.Timestamp(e.start).strftime('%Y-%m-%d')))
    del source,cold_events
    _,entries,handles=inventory(downloads)
    traces,events=[],[]
    for entry in entries:
        if entry['kind']!='dynamic' or (entry['machine'],entry['date']) not in dates:continue
        raw,stamp,_=read_day(entry)
        usable=stamp.notna()&~stamp.duplicated(keep=False)
        raw=raw[usable].copy();stamp=stamp[usable]
        order=stamp.sort_values().index;raw=raw.loc[order].reset_index(drop=True);stamp=stamp.loc[order].reset_index(drop=True)
        run=raw.Status.eq('Run')
        start=run & ~run.shift(fill_value=True) & stamp.diff().dt.total_seconds().between(1,2)
        for pos in np.flatnonzero(start.to_numpy()):
            event_id=f'{entry["machine"]}-RUN-{stamp.iloc[pos].isoformat()}'
            end=int(np.searchsorted(stamp.values,(stamp.iloc[pos]+pd.Timedelta(seconds=1801)).to_datetime64()))
            next_stop=np.flatnonzero(~run.iloc[pos:end].to_numpy())
            if len(next_stop):end=pos+int(next_stop[0])
            events.append({'event_id':event_id,'machine':entry['machine'],'start':stamp.iloc[pos],
                           'retained_rows':end-pos,'source_date':entry['date'],
                           'right_censored_at_day_end':end==len(raw)})
            for module in range(1,9):
                tr=pd.DataFrame({f:pd.to_numeric(raw[f'{tag}_{module}'].iloc[pos:end],errors='coerce').to_numpy() for f,tag in TAGS.items()})
                tr['elapsed']=(stamp.iloc[pos:end]-stamp.iloc[pos]).dt.total_seconds().to_numpy().astype(int)
                tr['cold']=raw[f'Status_{module}'].iloc[pos:end].eq('On').to_numpy() & raw[f'Busy_{module}'].iloc[pos:end].astype(str).eq('0').to_numpy() & raw[f'SV_{module}'].iloc[pos:end].eq('Off').to_numpy()
                tr['event_id']=event_id;tr['machine']=entry['machine'];tr['module']=module
                traces.append(tr)
    for handle in handles:handle.close()
    pd.DataFrame(events).to_csv(output/'raw_run_boundaries.csv',index=False)
    pd.concat(traces,ignore_index=True).to_parquet(output/'raw_run_trajectories.parquet',index=False)
    print(f'Raw Run boundary scan: {len(dates)} candidate day-files; {len(events)} within-day observed starts',flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--downloads",type=Path,default=Path("C:/Users/Book/Downloads"))
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument("--stage",choices=["ingest","summarize","runstarts","all"],default="all")
    parser.add_argument("--limit",type=int)
    args=parser.parse_args()
    if args.stage in ("ingest","all"):
        ingest(args.downloads,args.output,args.limit)
    if args.stage in ("summarize","all"):
        summarize(args.output)
    if args.stage in ("runstarts","all"):
        extract_run_trajectories(args.downloads,args.output)
