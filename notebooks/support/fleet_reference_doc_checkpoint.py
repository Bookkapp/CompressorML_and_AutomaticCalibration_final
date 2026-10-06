from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REPORT='deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md'
NOTEBOOK='notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb'


def prepend(name,text):
    path=ROOT/name;old=path.read_text(encoding='utf-8')
    if '**5 Oct — Fleet Reference / selective transfer delivered:**' in old:return
    head,rest=old.split('\n',1)
    path.write_text(head+'\n\n'+text.strip()+'\n'+rest,encoding='utf-8')


common=f'''**5 Oct — Fleet Reference / selective transfer delivered:** Owner-authorized041/058/080/081 plus017/024 studied from555committed dynamic ZIP days /46,616,484rows (Jul1–Oct1; three missingJul1files). Source SHA/row counts reconciled; no stopped import resume. Selected Reference proposal freezes Local absolute means/scales and selectively shares covariance shape:76/101 evaluated sparse scenarios compatible, versus0/101 mean+covariance; compatibility is not accuracy or Active acceptance. SV-conditioned groups are unverified research strata, not a completed Cold/Room/Hot hierarchy or exact iid NIW. All-state/day/event evidence retained; transition observations do not impose cut/suppression timers. Calibration Fleet Reference UI, machine/module/day graph isolation, source alias dedup and128wireviews under the same32MB cap delivered.225full tests plus7/13focused final regressions/build; three-browser-tab QA;10clients/120preparedGETs all200, warm p95≈109ms (cold SQL preparation excluded). Known080/M6case retains643/643 evaluable minute flags. Profiles207/Active46 canonical hashes unchanged, ContextActive0. Fleet is nonvoting/Reference-only; reviewed normal regimes, verified contracts, independent healthy/case/future validation and worker/Active/Server integration remain required. Report: `{REPORT}`; executed Notebook11. Older checkpoints below are historical.'''
for name in ('README_System.md','SOT.md','AGENTS.md','HANDOFF.md','Project.md'):
    prepend(name,common)

prepend('Roadmap.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:**

- [x] Checksum-reconcile555committed dynamic files for017/024/041/058/080/081; all8module observed minutes and within-day control events retained.
- [x] Asset-held-out/time-separated sparse Fit comparison, frozen Local absolute lane and selective covariance-shape EB-style proposals; no exact NIW/accuracy claim.
- [x] Calibration Fleet Reference UI; manual three-tab/machine/module/date/empty-data QA; prepared10client/120GET performance;128wireviews with unchanged32MB cap; source alias selector merge.
- [x] Executed Notebook11, quality/source/protocol/environment/known-case/load receipts, unchanged207Profile/46Active hashes and ContextActive0.
- [ ] Verify hardware/module role/configuration/controller/pressure basis/service epochs and review normal regimes; sameM/SV grouping is research-only.
- [ ] Evaluate independent healthy cycles, untouched cases and frozen prospective target days before operational Fleet votes/compatible registry and rollback integration. Current Fleet proposals remain nonvoting; no Active/Server/live worker changes.

Evidence: `{REPORT}` · `{NOTEBOOK}`. Compatibility76/101 vs0/101 is not diagnostic accuracy; sparse Fit arms also require7target calibration days. Previous intake remains stopped.''')

prepend('UX.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:** Calibration machine first→Fleet Reference→M1–M8→Local Fit1/3/7/14days→independent source machine/date→explicit graph. Defaultcollapsed transition/method details; numerical sharing is marked waiting for review. Previous-module numbers are hidden during request changes while graph cards reserve space. Date input handles input/change; out-of-range graph action disabled, missing committed days shows clear empty-data message; no“Loading chart data”. Real three-tab041/058/081 and080/M6graph checks show4pressure/2temperature curves,358px cards, no horizontal overflow. Source080/MX080 aliases now appear once, without source-row rewriting. This UI presents unreviewed minute evidence, not Raw seconds or Normal certification. Evidence: `{REPORT}`.''')

prepend('graft/README.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:**

Committed import receipts + local dynamic ZIP SHA/row count → `notebooks/support/fleet_reference_study.py` → bounded all-state1m-v3 per-day Parquet + original within-day state/command events → `fleet_reference_benchmark.py` → time/asset-separated proposals and diagnostics. `apps/api/app/fleet_assistance.py` performs bounded robust-moment selective pooling; frozen Local absolute evidence remains. `fleet_reference_api.py` reads only frozen prepared evidence with source/derivative checks → `FleetReferencePanel.tsx` in Calibration. No edge from these research proposals to Context runtime votes, registry/Active writes or SQL event backfill. `context_reads.py` raises only immutable wire entry cap to128;32MB and mutable Raw24 remain. `repository.py` merges source selector aliases after cache reads. Notebook11/report/technical and browser QA receipts document this edge. `{REPORT}`.''')

prepend('THESIS.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:** The local implementation is a **bounded robust-moment Empirical-Bayes-style covariance-shape approximation**, with frozen Local absolute levels/scales and target-specific disjoint empirical thresholds. It is not full hierarchical posterior inference or exact iid NIW; dependence and unverified within-SV multimodality remain. On six assets/555committed files,76/101 sparse scenarios pass correlation-sharing eligibility versus0/101 mean+covariance sharing; these are compatibility counts, not accuracy. Fit1/3/7/14day arms also have7target calibration days, so no one-day cold-start claim. Dhada2020([DOI](https://doi.org/10.1017/dce.2020.19)), Bull2022([preprint](https://arxiv.org/abs/2204.12404)) and Ghauch2025([DOI](https://doi.org/10.1017/dce.2025.3)) motivate similar-asset/hierarchical/selective sharing; none validates HT9046MX healthy labels or our approximation. Current conditional Context runtime and frozen Local evidence remain primary, ARX optional offline challenger. Executed `{NOTEBOOK}` and `{REPORT}` record provenance/splits/limitations/future acceptance.''')

prepend('README.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:** [Fleet study + local UI/QA]({REPORT}) · [Executed Notebook11]({NOTEBOOK}). Calibration now shows Reference-only comparisons for041/058/080/081 and017/024 with machine/module/day graphs. Frozen Local means/scales are retained; compatible Fleet correlation sharing is an offline proposal, no Active/runtime detector replacement. Warm prepared reads p95≈109ms; cold intake/source SQL and prospective approval remain separate.''')
prepend('notebooks/README.md',f'''**5 Oct — Fleet Reference / selective transfer delivered:** Executed `11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb` (six code cells/one source-backed case figure) audits555committed dynamic day files for017/024/041/058/080/081, observed quality/control coverage, held-out sparse transfer, SV/Valve censoring and080/M6frozen-level regression. Companion support commands are read-only for source/registry and create only local derivative/research outputs. Private ZIP/receipts/day partitions are needed and not published; the notebook does not silently refit on open. Report: `../{REPORT}`.''')

path=ROOT/'Project.md';old=path.read_text(encoding='utf-8')
old=old.replace('**Current task — 5 Oct:** Owner asked to stop','**Previous intake task — 5 Oct:** Owner asked to stop',1)
path.write_text(old,encoding='utf-8')
path=ROOT/'AGENTS.md';old=path.read_text(encoding='utf-8')
entry=f'- 2026-10-05 — Added checksum-reconciled Fleet Reference study/UI and bounded selective correlation sharing while preserving frozen Local levels. Research proposals nonvoting;225full tests plus final focused7/13/build/manual3tabs/120GET QA;207Profile/46Active hashes unchanged. No source import resume/Active/worker/Server/push. `{REPORT}`.\n'
old=old.replace('## Change log\n','## Change log\n\n'+entry,1);path.write_text(old,encoding='utf-8')

path=ROOT/'research/claim-to-source-ledger.md';old=path.read_text(encoding='utf-8')
extra='''
## Fleet methodology follow-up — 5 October 2026

| Claim | Primary source | Scope checked / limit |
| --- | --- | --- |
| Hierarchical multivariate Gaussian/NIW models can share information within similar-asset clusters, with reported gains for sparse assets | Dhada, Girolami & Parlikad (2020), [Anomaly detection in a fleet of industrial assets with hierarchical statistical modeling](https://doi.org/10.1017/dce.2020.19) | Publisher full PDF checked; synthetic experiments, not HT9046MX field accuracy or a license to label all Fleet data healthy |
| Hierarchical multitask models share information among subgroup effects and allow data-poor groups to borrow strength | Bull et al. (2022 preprint), [Hierarchical Bayesian Modelling for Knowledge Transfer Across Engineering Fleets via Multitask Learning](https://arxiv.org/abs/2204.12404) | Author preprint abstract checked; truck survival/wind power examples, not our anomaly classifier |
| Our covariance-shape-only robust moment pooling is an engineering adaptation, not an exact NIW replication or a literature-proved best detector | Local executed Notebook11 / Fleet UAT20261005 | Compatibility76/101 vs0/101; extra7target calibration days, unreviewed SV strata, dependent thinned observations and nonvoting proposals; independent field validation still required |
'''
if '## Fleet methodology follow-up — 5 October 2026' not in old:path.write_text(old+'\n'+extra,encoding='utf-8')
print('Updated system, SOT, roadmap, handoff, UX, code/data map, thesis, README and source ledger checkpoints.')
