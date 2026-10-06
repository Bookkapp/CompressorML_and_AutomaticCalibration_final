"""Publish the executed companion and source-backed local method decision."""
from pathlib import Path
import json
from collections import Counter

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notebooks/outputs/fleet_reference_study_20261005'


def run():
    import nbformat
    from nbclient import NotebookClient
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    qa=json.loads((OUT/'technical-qa.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'intake_manifest.json').read_text(encoding='utf-8'))
    case=qa['known_case']['results'][0]
    notebook=nbformat.v4.new_notebook()
    notebook.metadata.kernelspec={'name':'python3','display_name':'Python 3','language':'python'}
    notebook.cells=[
      nbformat.v4.new_markdown_cell('''# Fleet Reference: selective transfer, 5 October 2026

Actual checksum-reconciled **017, 024, 041, 058, 080, 081**, all eight Compressor modules.
This is an inspectable historical experiment, not a healthy-label dataset or Active model.
Private day partitions and output receipts must be supplied locally; they are excluded from Git.

The selected proposal freezes Local means/scales and borrows compatible **correlation shape**.
The fitted moments are a bounded Empirical-Bayes-style approximation; this notebook does not claim exact iid NIW, calibrated fault probability, or independent accuracy.'''),
      nbformat.v4.new_code_cell('''from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'apps/api').is_dir())
out = root / 'notebooks/outputs/fleet_reference_study_20261005'
summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
manifest = json.loads((out/'intake_manifest.json').read_text(encoding='utf-8'))
qa = json.loads((out/'technical-qa.json').read_text(encoding='utf-8'))
assert summary['study_id'] == qa['study_id']
print('Frozen study:', summary['study_id'])
print('Protocol:', json.dumps(summary['protocol'], indent=2))'''),
      nbformat.v4.new_markdown_cell('''## Source quality and coverage

555 committed dynamic files, July 1–October 1 inclusive. July 1 is absent from the imported scope for 041/058/080. October 2–5 files and older SQL fixtures are outside the corpus. Duplicate counts below count rows participating in duplicated timestamps, not distinct duplicate keys. A passing minute is a complete observation, not a normal/healthy label. No missing seconds are interpolated.'''),
      nbformat.v4.new_code_cell('''files = pd.DataFrame(manifest['files'])
display(files.groupby('machine').agg(files=('date','count'), raw_rows=('raw_rows','sum'),
    duplicate_occurrence_rows=('duplicate_rows','sum'), invalid_valves=('invalid_valve_observations','sum')))
display(pd.DataFrame(summary['coverage'])[['machine','module','source_days','quality_minutes','sv_off_minutes','sv_on_minutes']])
print('Partial files below 80,000 rows (screen only):')
display(files.loc[files.raw_rows.lt(80000), ['machine','date','raw_rows','source_sha256']])'''),
      nbformat.v4.new_markdown_cell('''## Time and asset separation

Reference: July 2–August 14. Threshold calibration: August 15–21. Historical diagnostics: September 1–30. Endpoints in the protocol are exclusive. Sparse arms vary **Fit** history (1/3/7/14 days) and additionally need seven target calibration days: this is not a pure one-day cold start.

The entire target machine is excluded from its donors. Same M index is an unverified research stratum; source logs do not contain an independently verified ATC mode/hardware/configuration contract. SV-conditioned stable segments can still contain multiple operating regimes and require review.'''),
      nbformat.v4.new_code_cell('''variants = pd.DataFrame(summary['variants'])
display(variants.groupby(['machine','status']).size().unstack(fill_value=0))
completed = variants[variants.status.eq('RESEARCH_PROPOSAL')].copy()
display(completed.groupby('machine').agg(scenarios=('module','count'),
    full_pool_compatible=('fleet_weight',lambda s: s.gt(0).sum()),
    shape_pool_compatible=('relationship_fleet_weight',lambda s:s.gt(0).sum())))
display(completed[completed.fit_days_requested.eq(14)][['machine','module','context','fit_points',
    'fit_days_observed','relationship_donor_machines','relationship_fleet_weight']])
print('Compatibility counts are NOT detection accuracy or accepted Active Profiles.')'''),
      nbformat.v4.new_markdown_cell('''## Observed SV / Valve response

Every within-day observed command/state change is retained in the day event partitions. First rows have no invented preceding-day witness. Diagnostics use all usable SV changes and a deterministic subset of Valve steps ≥3 units, separated by two hours. These examples may have concurrent controls; settling is not proven health or causal response. Censored/unsettled/no-response events remain in the denominator. Five-minute stable observation is sought only after material response; no fixed exclusion timer is deployed.'''),
      nbformat.v4.new_code_cell('''events = pd.read_parquet(out/'transition_metrics.parquet')
display(events.groupby(['event_type','split','status']).size().rename('events').reset_index())
phase = pd.DataFrame(summary['transition_summary'])
display(phase[(phase.machine.isin(['041','058','080','081'])) & phase.direction.isin(['OFF_TO_ON','ON_TO_OFF'])])'''),
      nbformat.v4.new_markdown_cell('''## Previously inspected MX080/M6 case

The owner-confirmed interval begins September 7 at 12:23:28. Complete incident minutes start 12:24. All-state observed minute averages below are not raw seconds. The frozen Local candidate baseline stays visible when a shifted level later becomes flat. This regression uses qualified/control-supported/steady minutes only, so it is not a claim of full-episode coverage or prospective recall.'''),
      nbformat.v4.new_code_cell('''models=json.loads((out/'model_proposals.json').read_text(encoding='utf-8'))['models']
model=next(m for m in models if m['machine']=='080' and m['module']==6 and m['context']=='SV_OFF')
data=pd.read_parquet(out/'minutes/080_2026-09-07.parquet',filters=[('module','==',6)]).sort_values('time')
fig,axes=plt.subplots(3,1,figsize=(12,7),sharex=True,layout='constrained')
for ax,feature,label,index in [(axes[0],'hp2','HP2 (psi)',2),(axes[1],'lp2','LP2 (psi)',3)]:
    observed=data[feature].where(data.quality)
    # Add NaN breakpoints for gaps, rather than drawing across absent minutes.
    observed=pd.Series(observed.to_numpy(),index=data.time).reindex(pd.date_range(data.time.min(),data.time.max(),freq='min'))
    ax.plot(observed.index,observed.values,color='#216f99',lw=1,label='Observed minute average')
    ax.axhline(model['center'][index],color='#9c6a17',ls='--',label='Frozen Local Reference median')
    ax.axvspan(pd.Timestamp('2026-09-07 12:23:28'),pd.Timestamp('2026-09-08'),color='#cc6d54',alpha=.12)
    ax.set_ylabel(label);ax.grid(alpha=.18);ax.legend(loc='upper left',fontsize=8)
axes[2].step(data.time,data.valve,where='post',color='#7159b7',lw=1)
axes[2].set_ylabel('Valve command');axes[2].set_xlabel('Source clock: Asia/Bangkok assumption')
fig.suptitle('MX080/M6 · frozen Local levels with selective Fleet relationship assistance')
fig.savefig(out/'known-case-local-levels.png',dpi=150)
plt.show()
display(pd.DataFrame(qa['known_case']['results']))'''),
      nbformat.v4.new_markdown_cell('''## Performance, mutation boundary and reproduction

HTTP measurements are bounded prepared-artifact reads, not live SQL intake or browser rendering. Batch-score time excludes IO, fit and approval. Wire cache now retains 128 immutable views with the same 32 MB cap; mutable Raw cache remains 24 entries. API requests never trigger model fitting. Model proposals are nonvoting and not auto-activated.

Reproduce from the workspace root with the existing local environment:
```text
python -m notebooks.support.fleet_reference_study --intake
python -m notebooks.support.fleet_reference_benchmark
python notebooks/support/fleet_reference_qa.py
```
Intake validates committed SHA/row-count receipts; it does not resume the stopped source import. The QA command needs the local API at port 8000. See deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md for real-browser results and activation prerequisites.'''),
      nbformat.v4.new_code_cell('''display(pd.DataFrame([qa['scoring']]))
display(pd.DataFrame([{k:v for k,v in qa['http'].items() if k not in ['first_reads','responses']}]))
print('Actual execution environment:',qa['environment'])
print('Registry receipts:',json.dumps(qa['registry'],indent=2))
assert all(qa['registry'][table]['unchanged'] for table in ['ht9046mx_calibration_profile','ht9046mx_active_calibration_profile'])
assert summary['activation_eligible'] is False
print('Independent healthy-cycle/future validation, verified contracts and reviewed regime references remain required.')''')]
    path=ROOT/'notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb'
    NotebookClient(notebook,timeout=90,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.write(notebook,path)
    completed=[r for r in summary['variants'] if r['status']=='RESEARCH_PROPOSAL']
    table='\n'.join(f"| MX{m} | {len([r for r in manifest['files'] if r['machine']==m])} | {sum(r['raw_rows'] for r in manifest['files'] if r['machine']==m):,} | {sum(r['machine']==m for r in completed)} | {sum(r['machine']==m and bool(r['relationship_fleet_weight']) for r in completed)} |" for m in summary['source_machine_order'])
    report=f'''# Fleet Reference / Selective Transfer — local UAT, 5 October 2026

## Decision and delivered scope

Selected **frozen Local absolute evidence + selective correlation-shape partial pooling + observed transition evidence**. Fleet donor means never move the default Local baseline or per-channel robust scales. Full mean/covariance pooling remains a comparison arm. ARX is not required by this implementation; existing offline ARX challengers remain available. Context v4 stays the main runtime model; this Fleet proposal does **not** vote, write Candidate/Active pointers or replace it.

The code implements a bounded **Empirical-Bayes-style robust moment approximation**, not exact iid NIW inference, full hierarchical posterior sampling or calibrated Student-t fault probabilities. Mahalanobis scores use Cholesky; thresholds are target-specific disjoint empirical Q99.5. Six physical coordinates omit exact redundant DP coordinates; DP remains display evidence. Research group membership is same module index + supported SV context, not verified hardware role or a completed Cold/Room/Hot regime hierarchy. Source contracts/healthy Reference reviews are still needed before real transfer eligibility.

## Actual data and quality audit

Frozen study `{summary['study_id']}`, derived `{manifest['version']}`. **555 committed dynamic files / {manifest['raw_rows']:,} raw-second rows**, July 1–October 1 inclusive; Static excluded. 041/058/080 July 1 are absent from the committed scope. Oct2–5 receipts and older SQL fixtures are outside this experiment. Source CSV SHA and raw row counts match the local import ledger; this canonical ZIP corpus is not an exact live SQL snapshot. Import receipts remain567; no stopped import was resumed.

| Machine | Source day files | Raw rows | Evaluated sparse scenarios | Compatible covariance-sharing scenarios |
| --- | ---: | ---: | ---: | ---: |
{table}

Across all files: **{qa['quality']['duplicate_timestamp_occurrence_rows']:,} rows participating in duplicate seconds**, not distinct duplicate keys. All duplicates/source gaps/manual states stay in evidence. Quality needs ≥57 occupied seconds, no duplicates, gaps≤5 seconds and six finite physical fields. A passing minute is not proof of health. Missing Valve cannot become supported context through averaging valid remaining samples. The final full555file Valve audit found **0 invalid Valve observations**. Partial days include Aug12 across assets, MX080 Jul13 and the October1 tails; exact per-file counts and hashes are inspectable in Notebook11/intake manifest.

Actual production-builder adapter comparison: **160 minute-module pairs**, physical means within1e−10 and quality parity. Ten additional synthetic quality/control tests cover57/56samples, duplicate/gap/mixedSV/missingphysical/missingorInfiniteValve and invalid transition witnesses. Source schema has82 columns and no independently verified ATC mode code; pressure is owner-confirmed psi, psig/psia basis remains unverified. All-state graph temperatures must not be read as a certified Cold regime.

## Experiment boundaries and results

Reference Jul2–Aug14; calibration Aug15–21; diagnostic Sep1–30; all endpoint dates in the protocol are exclusive. Sparse Fit arms1/3/7/14days additionally use seven target calibration days, so this is **not a pure one-day cold-start test**. Threshold needs≥200 points and≥3 days. Donors are asset-balanced, one summary per machine; the entire target machine is excluded. Prior strength capped20; at least two compatible donors and20 thinned target points are required. Parameters and gates use Reference only, threshold block is separate; diagnostic data do not tune them.

384 scenario receipts: {dict(Counter(r['status'] for r in summary['variants']))}. **{summary['fleet_assisted_variants']}/{summary['completed_variants']}** evaluated scenarios accepted mean+covariance sharing; **{summary['relationship_assisted_variants']}/{summary['completed_variants']}** accepted shape-only sharing. These count compatibility under the fixed research gate, **not accuracy, healthy acceptance or Active Profiles**. Regime multimodality and serial dependence are still review limitations; 15-minute thinning is not an iid/effective-sample-size proof. Final steady screening uses physical max-minus-min over five contiguous supported minutes, normalized by Reference scale, with limit0.35; adjacent-change-only screening was superseded because it can miss cumulative drift. Both precision and cumulative-drift regression tests pass. The first draft's nanosecond-assumption sampler was corrected to calendar-minute sampling; only final study results are used here.

SV/Module/Busy/Valve changes are retained in all555 daily event partitions. First-row/day-boundary events are censored rather than invented. SV examples use every usable observed change; Valve examples use steps≥3 units and a deterministic≥2hour spacing. All source events remain stored, even when examples are thinned. Observed delay/overshoot/terminal shift/settling/censoring are available. Five-minute stability is sought after material response, with up to120 observed minutes. These are confounded observational features, not causal Valve tests, normal labels, suppression or an exclusion timer. Curves use only Reference observations before its cutoff; split labels use the same disjoint protocol. This task adds file-backed research evidence; it does not backfill the common SQL event ledger or label events as anomalies. Existing Context event capture remains unchanged.

Known inspected case **MX080/M6,7Sep12:24–24:00**:{case['quality_supported_steady_minutes']} control-supported/quality/steady incident minutes,{case['absolute_flags']} Local absolute flags and{case['combined_flags']} combined flags,{case['combined_persistent_minutes']} persistent minutes after continuity resets. Frozen Local mean and scale equal the selected covariance-sharing proposal; Fleet weight≈{case['fleet_weight']*100:.2f}%. Nonsteady/unsupported minutes abstain; this is a known-case regression, not prospective recall/whole-episode sensitivity. No new fault cause is assigned.

## Web and performance

Calibration→select machine→**Fleet Reference**→M1–M8→Fit1/3/7/14days. Independent on-demand machine/day graphs show observed **minute averages**, not Raw seconds; pressure psi, temperature°C. Transition tables and method notes collapse by default. Query keys include complete machine/module/day; prior-module numbers are hidden during placeholder loading. Graph cards stay358px in the tested viewport, no “Loading chart data” text. Date input handles input/change; days outside the corpus disable the graph action, missing committed days show a readable error and empty reserved charts. The source selector now merges080/MX080 aliases into one entry, summing stored row counts and taking outer observed coverage; raw alias rows are untouched.

Actual browser UI: three concurrent tabs041/M1,058/M2andM7,081/M8; switching Fit1day; missing041Jul1; out-of-rangeOct5; source-machine switch to080/M6andSep7 case graph. See `browser-qa.json`/screenshots in local outputs. This is manual UI action QA through the browser, separate from HTTP automation. It does not claim Manual Build→review→prospective→Active-success for Fleet.

Prepared reads:64firstGETs across four assets/all8modules (Reference+day), then10clients/120GETs all200. Warm p50 **{qa['http']['p50_ms']:.1f}ms**, p95 **{qa['http']['p95_ms']:.1f}ms**, max **{qa['http']['max_ms']:.1f}ms**; bounded first-read p95 **{qa['http']['first_p95_ms']:.1f}ms**. The original24wire-entry cache churned on64views (warm p95≈402ms);128 immutable views with the same32MB byte cap improved measured p95≈204ms. Mutable Raw cache remains24. Cache coalescing is per API process; frozen file partitions are shared inputs. Fresh-process/cold SQL source inventory and full source preparation are not covered by the warm read claim.

Actual1361point Local+relationship batch scoring p50 **{qa['scoring']['p50_ms']:.3f}ms**, p95 **{qa['scoring']['p95_ms']:.3f}ms** (no IO/fit/UI). Offline full benchmark **{summary['elapsed_seconds']:.1f}s**; full raw SHA/Valve audit≈590s. Derived study≈228MB; reads are bounded by day/module, no request-time fitting. Frozen version/hash checks reject source/derived revisions even after a cached read.

## Verification and remaining gates

Full suite before final small cache/selector patches: **225passed**,450 existing SQLite adapter deprecation warnings. Focused final cache/source/API regressions: **7passed +13passed**, and final benchmark precision/drift/split regressions **3passed**. TypeScript and Vite production build pass; existing large bundle warning remains. Actual execution: Python{qa['environment']['python']}, NumPy{qa['environment']['numpy']}, pandas{qa['environment']['pandas']}; direct SciPy dependency1.16.2 recorded. Requirements pins differ from the existing local NumPy/pandas environment; no environment reinstall was performed.

Canonical sorted-JSON-line hashes (same helper as pre-work snapshot): Profiles207, `{qa['registry']['ht9046mx_calibration_profile']['sha256']}`; Active46, `{qa['registry']['ht9046mx_active_calibration_profile']['sha256']}` — both unchanged. ContextActive0, import receipts567 unchanged. No source DML, Candidate/Active promotion, worker launch, Server deployment or Git push. API8000 and Vite5176 remain running locally; service PIDs are in `services.json`.

To progress to operational Fleet use: verified hardware/role/configuration/controller/pressure basis/service epoch per asset; Engineer-reviewed normal regime references; independent healthy cycles and known cases; frozen prospective target validation; explicit compatible Profile version/rollback integration. The algorithm can assist sparse but comparable Local evidence; when similarity cannot be established or a regime is unreviewed, it abstains. Zero Local evidence is not certified normal using unrelated Fleet data.

## Sources and reproduction

Dhada et al.[2020](https://doi.org/10.1017/dce.2020.19) motivate collaboration within similar-asset clusters; their Gaussian/NIW model and synthetic experimental results do not certify these machines. Bull et al.[2022 preprint](https://arxiv.org/abs/2204.12404) motivate hierarchical sharing across subgroup effects; its fleet tasks differ from HT9046MX anomaly detection. Ghauch et al.[2025](https://doi.org/10.1017/dce.2025.3) motivate operating-segment matching to limit negative transfer; predictive MSE gains are not fault-detection accuracy here. Our bounded correlation-only update is an engineering adaptation, not a replication of those papers.

Read executed `notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb`. Reproduce from workspace root: `python -m notebooks.support.fleet_reference_study --intake`, `python -m notebooks.support.fleet_reference_benchmark`, then with localAPI8000 `python notebooks/support/fleet_reference_qa.py`. The private ZIP/receipts/day partitions are required; they are not published. Source hashes, adapter/core/implementation hashes, protocol, environment, model proposals, transition metrics and QA receipts are in the ignored local output directory.
'''
    (ROOT/'deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md').write_text(report,encoding='utf-8')
    print(json.dumps({'notebook':str(path),'code_cells':sum(c.cell_type=='code' for c in notebook.cells),'study_id':summary['study_id']}))


if __name__=='__main__':run()
