"""Execute the portable model handoff companion and generate its runbook."""
from pathlib import Path
import json
import nbformat
from nbclient import NotebookClient

from notebooks.support.fleet_stable_build import ROOT,OUT


def run():
    qa=json.loads((OUT/'qa.json').read_text(encoding='utf-8'))
    build=json.loads((OUT/'build-summary.json').read_text(encoding='utf-8'))
    notebook=nbformat.v4.new_notebook();notebook.metadata.kernelspec={'name':'python3','display_name':'Python 3','language':'python'}
    notebook.cells=[
      nbformat.v4.new_markdown_cell('''# Fleet Stable v1 — portable frozen Shadow Candidate
## tl;dr
Six real source machines (017/024/041/058/080/081), all eight modules considered. Unsupported data remain unsupported.
Local absolute levels/scales stay frozen; compatible donor correlation shapes assist them. This is a bounded robust empirical-moment approximation, not exact hierarchical posterior inference.
The bundle loads without notebook inputs or SQL. It does not certify healthy references, automatically activate, or vote in alerts.
## Context & Methods
### Key Assumptions
Naive source clock is treated as Asia/Bangkok. Pressure is owner-confirmed psi; psig/psia and configuration/state/controller/service contracts remain unverified. Same module index is a research stratum.
Reference and threshold periods are disjoint. Phase bounds use Fit-only Q90 of five contiguous minute coordinate ranges, floored at max(0.35 Local robust scale, 0.1 physical units). The previous 0.35-only phase rule could reject normal sensor movement. A stable phase is not a healthy label; response scores are never suppressed.
MX080/M6 proposed Fit is Aug27–30; threshold is Sep3–6. These intervals require engineering health review. The previously inspected Sep7–8 case is a regression, not prospective recall; the pre-case holdout is owner-proposed stable, not independently healthy.'''),
      nbformat.v4.new_code_cell('''from pathlib import Path
import json,sys
import numpy as np,pandas as pd,matplotlib.pyplot as plt
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'apps/api').is_dir())
sys.path.insert(0,str(root))
from apps.api.app.fleet_bundle import load_package
from notebooks.support.fleet_stable_qa import day_rows
out=root/'notebooks/outputs/fleet_stable_v1_20261006'
build=json.loads((out/'build-summary.json').read_text(encoding='utf-8'))
qa=json.loads((out/'qa.json').read_text(encoding='utf-8'))
fleet=load_package(build['packages']['cp2_candidate'])
assert fleet.bundle_id==qa['bundle_id']
print('Frozen bundle:',fleet.bundle_id)
display(pd.DataFrame([qa['portable'],qa['parity']]))'''),
      nbformat.v4.new_markdown_cell('''## Data
All source-day derivative SHA values reconcile to the frozen import/ZIP receipt corpus; this is not an exact current SQL snapshot. The original seconds and control events remain in their source stores. The package contains summary parameters, provenance and curation, not 46 million raw records.
Observed default-like temperatures -200 or all four module pressures 580.2 are acquisition review evidence. Audited Sep7 10:55:59–11:28:01 seconds quarantine outward-rounded 10:55–11:28 minute rows, including boundary mixtures. Future source adapters must report invalid-second membership; an average can hide a short bad burst.'''),
      nbformat.v4.new_code_cell('''receipts=pd.DataFrame(build['calibration_receipts'])
display(receipts.groupby(['machine','status']).size().unstack(fill_value=0))
print('Verified days:',build['source_days_verified'],'raw receipt rows:',build['raw_rows'])
models=pd.DataFrame(fleet.models())
display(models[['machine','module','context','n','fleet_weight','donor_machines']])
fig,ax=plt.subplots(figsize=(10,3.6),layout='constrained')
counts=models.groupby('machine').size().reindex(['017','024','041','058','080','081'],fill_value=0)
ax.bar(['MX'+m for m in counts.index],counts.values,color='#2c78b8')
ax.set_ylim(0,16);ax.set_yticks(range(0,17,2));ax.set_ylabel('Calibrated SV-context profiles / 16')
ax.set_title('Candidate coverage · not healthy acceptance')
for i,n in enumerate(counts):ax.text(i,n+.25,str(n),ha='center')
fig.savefig(out/'profile-coverage.png',dpi=150);plt.show()'''),
      nbformat.v4.new_markdown_cell('''## Results
The case and acquisition incident have different meanings. Flat high CP2 remains outside the Local baseline; acquired defaults do not count as physical pressure anomalies. A descriptive response/steady boundary does not reset persistent raw evidence; bad data, gaps and control changes do. The day interface resets persistence at midnight, so counts are retrospective daily replay rather than streaming-episode duration.
After Sep12, Valve100/new levels are compared for review against Valve94 Reference. Flags there do not prove fault or leak; a reviewed new regime is needed.'''),
      nbformat.v4.new_code_cell('''cases=pd.DataFrame({k:qa[k] for k in ['proposed_normal_holdout','known_case','suspected_acquisition','post_intervention_unreviewed']}).T
display(cases)
model=next(m for m in fleet.models() if m['machine']=='080' and m['module']==6 and m['context']=='SV_OFF')
views=[('2026-09-07','00:00','08:00','Proposed pre-case holdout'),('2026-09-08','00:00','23:50','Known persistent CP2 problem'),('2026-09-12','04:00','23:59','Post-intervention · unreviewed')]
fig,axes=plt.subplots(2,3,figsize=(14,6.4),sharey='row',layout='constrained')
for col,(day,start,end,label) in enumerate(views):
    rows=day_rows('080',day,6);points=fleet.evaluate('080',6,rows)['points']
    data=pd.DataFrame(rows);data['assessment']=[p['assessment'] for p in points]
    data=data[data.time.ge(day+'T'+start)&data.time.lt(day+'T'+end)]
    stamp=pd.to_datetime(data.time)
    for ax,feature,index in [(axes[0,col],'hp2',2),(axes[1,col],'lp2',3)]:
        values=pd.Series(data[feature].where(data.assessment.ne('DATA_QUALITY')).to_numpy(),index=stamp)
        values=values.reindex(pd.date_range(stamp.min(),stamp.max(),freq='min'))
        ax.plot(values.index,values.values,color='#216f99',lw=1)
        limits=(160,360) if index==2 else (10,32)
        outside=values[(values<limits[0])|(values>limits[1])].dropna()
        if len(outside):
            ax.scatter(outside.index,outside.clip(*limits),marker='^',s=14,color='#be7a34',zorder=4)
            ax.text(.02,.92,f'{len(outside)} observations outside zoom; max {outside.max():.1f} psi',transform=ax.transAxes,fontsize=7,color='#82561e')
        ax.set_xlim(stamp.min(),stamp.max())
        center=model['center'][index];radius=model['absolute_threshold']*model['scale'][index]
        ax.axhspan(center-radius,center+radius,color='#9ebfaf',alpha=.3,label='Frozen Local single-coordinate envelope')
        ax.axhline(center,color='#537766',ls='--',lw=1)
        ax.grid(alpha=.15)
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'));ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    axes[0,col].set_title(label+'\\n'+day,fontsize=10)
    axes[1,col].set_xlabel('Asia/Bangkok source-clock assumption')
axes[0,0].set_ylabel('HP2 (psi) · level zoom');axes[1,0].set_ylabel('LP2 (psi) · level zoom')
axes[0,0].set_ylim(160,360);axes[1,0].set_ylim(10,32)
axes[0,0].legend(fontsize=7,loc='upper left')
fig.suptitle('MX080/M6 · stable pressure level is not automatically Normal')
fig.savefig(out/'cp2-shadow-regression.png',dpi=150);plt.show()'''),
      nbformat.v4.new_code_cell('''display(pd.DataFrame([qa['inference'],qa.get('http',{})]))
display(pd.DataFrame(qa['local_shadow_switch']['switches']))
assert qa['local_shadow_switch']['stale_revision_rejected']
assert all(qa['registry'][t]['unchanged'] for t in ['ht9046mx_calibration_profile','ht9046mx_active_calibration_profile'])
print('Healthy FPR verified:',qa['healthy_fpr_verified'],'Prospective verified:',qa['prospective_verified'])'''),
      nbformat.v4.new_markdown_cell('''## Takeaways
This handoff establishes portable frozen inference, checksum validation, local Shadow selection/rollback, stale-revision rejection and prepared graph reads. It does not establish independent healthy false-alert rates, production hardware/regime eligibility or target-Server/live worker acceptance. ARX is not needed in this runtime; offline challengers remain available.
### Reproduce and retrain
Run `python -m notebooks.support.fleet_stable_build`, then `python -m notebooks.support.fleet_stable_qa --http` with the local API running. Retraining accepts `--source-root`, `--plan` and `--output-root`; every build produces a new immutable package and does not change the Shadow pointer.
The Server runbook is deployment/FLEET_STABLE_V1_RUNBOOK_20261006.md. Common ledger adapters are in fleet_stable_events.py; the producer must append them atomically with its checkpoint. Existing source-second transitions stay in their original common-event capture. There is no GET-triggered event write or new source/backfill import in this task.''')]
    path=ROOT/'notebooks/13_Fleet_Stable_v1_Portable_Shadow_20261006.ipynb'
    NotebookClient(notebook,timeout=90,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.write(notebook,path)
    candidate=Path(build['packages']['cp2_candidate']);archive=OUT/(candidate.name+'.zip')
    report=f'''# Fleet Stable v1 — portable Shadow handoff, 6 October 2026

## Delivered

- Frozen Candidate `{qa['bundle_id']}`: **{build['models']} calibrated profiles**, {build['fleet_assisted_models']} with compatible correlation assistance, {build['donor_summaries']} donor summaries. All six machines/eight modules/SV contexts considered; missing calibration contexts remain unsupported. Numerical support is not reviewed health.
- 555 prepared source days /46,616,484 original-row receipts rechecked; canonical ZIP corpus, not exact current SQL. No source DML/import resume. Existing207Profile/46Active hashes unchanged and ContextActive0.
- Portable ZIP **{qa['portable']['zip_bytes']:,} bytes** with JSON models/scalers/covariance/thresholds, priors, curation, provenance, validation, README and manifest checksums. SHA256 `{qa['portable']['zip_sha256']}`. Only JSON loading, no pickle/joblib. Copied outside repo and loaded with exact prediction parity without SQL/notebook inputs; this is not a target-Server test.
- Local Shadow repository installed; actual base→Candidate→base rollback→Candidate tested. CAS rejects stale revision. Each request pins one immutable version; malformed/tampered package fails closed. Checksum guards accidental changes; no cryptographic publisher authentication is claimed. Store permissions must be restricted to the deploying operator.
- Calibration Fleet Stable UI shows version, per-module supported contexts, separate fit/calibration periods and on-demand actual minute graphs. Prepared graph requests never fit models or rewrite shared Profiles.
- Common `ht9046mx_events` adapter covers derived phase changes, persistent evidence and acquisition review idempotently. Original observed-second SV/Valve capture remains responsible for every control command. This task adds no live producer/worker, no new SQL Fleet-event backfill and no production Alert votes; version deployment history is an atomic file document.

## Method and curation

Frozen Local median and MAD/IQR scales; selective compatible donor correlation shapes, asset-balanced with capped prior strength20, same target machine excluded, source cutoff before target Reference end. Robust empirical moments are an EB-style approximation, not exact NIW/Student-t probabilities. Same M/SV is an unverified research stratum, not a verified hardware/ATC/recipe hierarchy. ARX is absent from this runtime; previous offline challengers remain.

Default Reference2Jul–14Aug; separate threshold15–21Aug. MX080/M6 Candidate uses owner-proposed Reference27–30Aug and threshold3–6Sep. These are NOT Engineer-certified healthy intervals. Old0.35×scale-only stability left156threshold minutes and no M6 Candidate. Frozen Fit-only Q90 five-minute coordinate ranges, max with0.35robust scale/0.1physical units, tolerate ordinary sensor variation; actual Candidate n/model phase bounds are serialized. Calibration/case/future never fit phase bounds. Statistical stability does not admit unreviewed new levels as healthy.

All-state data and transitions retained. -200 temperature defaults/all four pressures580.2 are conservative acquisition-suspect evidence; hardware sentinel codes remain unverified. The independently audited7Sep10:55:59–11:28:01 interval rounds outward to34minute rows, so mixed boundary averages cannot slip through. Live source adapters must set invalid-second `semantic_bad`; minute averages alone cannot prove all underlying seconds valid. This does not modify legacy ingestion/Data Gate.

Scores are visible during physical response, without an exclusion timer. Raw persistence is3adjacent same-context valid minutes; response/steady descriptors never clear an ongoing flag. This batch day adapter resets at midnight; a streaming producer must retain continuity/checkpoint across days. WITHIN_REFERENCE is not a health label. Post12Sep/newValve100 remains a regime/epoch review.

## Actual regression and performance

| Check | Observed result | Interpretation |
|---|---|---|
|Owner-confirmed7Sep12:30–8Sep23:50|{qa['known_case']['raw_flags']}/{qa['known_case']['evaluated_minutes']} eligible minute flags;{qa['known_case']['persistent_minutes']} persistent;{qa['known_case']['steady_flags']} stable flags|Retrospective previously inspected case; unsupported/bad minutes excluded|
|7Sep00:00–08:00 proposed stable holdout|{qa['proposed_normal_holdout']['raw_flags']}/480 raw;0persistent;0/395stable flags|Owner-proposed, not independently healthy FPR|
|Suspect acquisition interval|34DATA_QUALITY;0physical anomaly flags|Separate sensor/data investigation|
|12Sep04:00–midnight|1200/1200raw flags|Different control level, unreviewed regime; NOT proof of fault|
|Compiled/fitting-function parity|{qa['parity']['actual_points']:,} actual points;0score error|Numerical parity, not independent accuracy|
|Full1430minute-module-day inference|p50{qa['inference']['p50_ms']:.1f}ms /p95{qa['inference']['p95_ms']:.1f}ms|Excludes IO, fitting and UI|
|Prepared HTTP10clients/120GETs|120success;warm p95{qa.get('http',{}).get('warm_p95_ms',0):.1f}ms|Not cold source SQL or browser-render latency|

Backend/API package, mutation, isolation and event tests; TSC/Vite and actual manual browser evidence are recorded in the companion QA receipts. Existing Vite large-bundle and SQLite datetime warnings remain. Figures and all exact per-context receipts are in executed Notebook13/local outputs.

## Installation on Server

Copy this ZIP and the reviewed Operation API code to a controlled Server directory. Inference requiresPython>=3.11/NumPy2.x/SciPy>=1.13,<2; actual local tested environment isPython3.12.10/NumPy2.2.1/SciPy1.16.2. Keep API dependencies as declared by Operation. The model loader itself does not need SQL or notebook raw data.

```powershell
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" install "D:/Release/{archive.name}"
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" status
```

For an empty store, `status` has no selected model until switching. Read `shadow.json` revision (0when absent), then:

```powershell
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" switch {qa['bundle_id']} --expected-revision 0 --actor "ServerOwner" --reason "Approved Shadow installation"
```

Set `HT9046MX_FLEET_STABLE_STORE` to that directory. Model status isGET`/api/v1/calibration/fleet/stable/reference?machine_number=080&module=6`. Historical day charts optionally need an independently installed prepared evidence store via`HT9046MX_FLEET_REFERENCE_ROOT`; inference itself takes observed rows and needs no notebook folder. No fitting occurs in HTTP. The target source-minute adapter must match clock/controls/coverage/quality contract; do not send legacy snapshot/five-minute rows as observed completed minutes.

Producer integration:

```python
from apps.api.app.fleet_bundle import current_snapshot
from apps.api.app.fleet_stable_events import evidence_events
from apps.api.app.unified_events import append_events
pointer, fleet = current_snapshot(model_store)
result = fleet.evaluate("080", 6, observed_module_day_rows)
records = evidence_events(result, source_digest=verified_source_digest,
    source_namespace=verified_source_namespace, verified_source_mapping=True)
# producer-owned transaction: append_events(conn, records), then checkpoint
```

Live worker/outbox, authentication, clock/service recovery and production activation are not enabled by these instructions. Target-Server acceptance remains unperformed. The package only permitsShadow; it cannot becomeActive by editing a pointer mode.

## Retraining and rollback

Add new data to a new checksum-reconciled prepared evidence inventory. Copy `build-plan.json`, set explicit fit/calibration periods, machines and optional machine/module overrides. Keep disjoint periods and review contamination/service epochs. Run:

```powershell
python -m notebooks.support.fleet_stable_build --source-root "D:/Evidence/new_snapshot" --plan "D:/Plans/fleet_v2.json" --output-root "D:/Candidates/fleet_v2"
```

Plan periods3–90days, machine count1–32; calibrated Reference coverage still needs>=3days,>=20spacedpoints,>=200separate threshold points/3days. Unreviewed references remainShadow-only. Refit/validate writes a new immutable version and does not change deployed pointers. Install new version, validate before switching, and use the current expected revision.

Rollback by switching to `previous_bundle_id` with the current revision; no deletion or in-place model mutation. Cross-process file lock fails promptly on competing deployers. If a deploying process crashes with `.shadow-pointer.lock` remaining, an operator must verify that PID is gone before removing only that stale lock. Missing/corrupt files block inference; do not silently train or choose a different model.

## Remaining acceptance

Engineer-reviewed Normal intervals and hardware/role/configuration/recipe/state/controller/service/pressure-basis contracts; independent healthy-cycle alert burden; truly untouched future validation after this frozen version; authenticated source producer/worker/common-event checkpoint; real target-Server Shadow/approval/rollback/live votes. AllSource rows and known anomalies remain retained. NoActive was promoted, no Server deployed and no Gitpush occurred in this local task.
'''
    (ROOT/'deployment/FLEET_STABLE_V1_RUNBOOK_20261006.md').write_text(report,encoding='utf-8')
    print(path);print('Notebook executed and runbook saved')


if __name__=='__main__':run()
