# Fleet Reference / Selective Transfer — local UAT, 5 October 2026

## Decision and delivered scope

Selected **frozen Local absolute evidence + selective correlation-shape partial pooling + observed transition evidence**. Fleet donor means never move the default Local baseline or per-channel robust scales. Full mean/covariance pooling remains a comparison arm. ARX is not required by this implementation; existing offline ARX challengers remain available. Context v4 stays the main runtime model; this Fleet proposal does **not** vote, write Candidate/Active pointers or replace it.

The code implements a bounded **Empirical-Bayes-style robust moment approximation**, not exact iid NIW inference, full hierarchical posterior sampling or calibrated Student-t fault probabilities. Mahalanobis scores use Cholesky; thresholds are target-specific disjoint empirical Q99.5. Six physical coordinates omit exact redundant DP coordinates; DP remains display evidence. Research group membership is same module index + supported SV context, not verified hardware role or a completed Cold/Room/Hot regime hierarchy. Source contracts/healthy Reference reviews are still needed before real transfer eligibility.

## Actual data and quality audit

Frozen study `d907db2e9e283e7183d252b3`, derived `all-state-study-1m-v3`. **555 committed dynamic files / 46,616,484 raw-second rows**, July 1–October 1 inclusive; Static excluded. 041/058/080 July 1 are absent from the committed scope. Oct2–5 receipts and older SQL fixtures are outside this experiment. Source CSV SHA and raw row counts match the local import ledger; this canonical ZIP corpus is not an exact live SQL snapshot. Import receipts remain567; no stopped import was resumed.

| Machine | Source day files | Raw rows | Evaluated sparse scenarios | Compatible covariance-sharing scenarios |
| --- | ---: | ---: | ---: | ---: |
| MX017 | 93 | 7,772,969 | 6 | 3 |
| MX024 | 93 | 7,801,416 | 5 | 3 |
| MX041 | 92 | 7,758,001 | 19 | 14 |
| MX058 | 92 | 7,751,066 | 24 | 13 |
| MX080 | 92 | 7,687,891 | 24 | 22 |
| MX081 | 93 | 7,845,141 | 23 | 21 |

Across all files: **105,926 rows participating in duplicate seconds**, not distinct duplicate keys. All duplicates/source gaps/manual states stay in evidence. Quality needs ≥57 occupied seconds, no duplicates, gaps≤5 seconds and six finite physical fields. A passing minute is not proof of health. Missing Valve cannot become supported context through averaging valid remaining samples. The final full555file Valve audit found **0 invalid Valve observations**. Partial days include Aug12 across assets, MX080 Jul13 and the October1 tails; exact per-file counts and hashes are inspectable in Notebook11/intake manifest.

Actual production-builder adapter comparison: **160 minute-module pairs**, physical means within1e−10 and quality parity. Ten additional synthetic quality/control tests cover57/56samples, duplicate/gap/mixedSV/missingphysical/missingorInfiniteValve and invalid transition witnesses. Source schema has82 columns and no independently verified ATC mode code; pressure is owner-confirmed psi, psig/psia basis remains unverified. All-state graph temperatures must not be read as a certified Cold regime.

## Experiment boundaries and results

Reference Jul2–Aug14; calibration Aug15–21; diagnostic Sep1–30; all endpoint dates in the protocol are exclusive. Sparse Fit arms1/3/7/14days additionally use seven target calibration days, so this is **not a pure one-day cold-start test**. Threshold needs≥200 points and≥3 days. Donors are asset-balanced, one summary per machine; the entire target machine is excluded. Prior strength capped20; at least two compatible donors and20 thinned target points are required. Parameters and gates use Reference only, threshold block is separate; diagnostic data do not tune them.

384 scenario receipts: {'INSUFFICIENT_FIT': 242, 'RESEARCH_PROPOSAL': 101, 'INSUFFICIENT_DISJOINT_CALIBRATION': 41}. **0/101** evaluated scenarios accepted mean+covariance sharing; **76/101** accepted shape-only sharing. These count compatibility under the fixed research gate, **not accuracy, healthy acceptance or Active Profiles**. Regime multimodality and serial dependence are still review limitations; 15-minute thinning is not an iid/effective-sample-size proof. Final steady screening uses physical max-minus-min over five contiguous supported minutes, normalized by Reference scale, with limit0.35; adjacent-change-only screening was superseded because it can miss cumulative drift. Both precision and cumulative-drift regression tests pass. The first draft's nanosecond-assumption sampler was corrected to calendar-minute sampling; only final study results are used here.

SV/Module/Busy/Valve changes are retained in all555 daily event partitions. First-row/day-boundary events are censored rather than invented. SV examples use every usable observed change; Valve examples use steps≥3 units and a deterministic≥2hour spacing. All source events remain stored, even when examples are thinned. Observed delay/overshoot/terminal shift/settling/censoring are available. Five-minute stability is sought after material response, with up to120 observed minutes. These are confounded observational features, not causal Valve tests, normal labels, suppression or an exclusion timer. Curves use only Reference observations before its cutoff; split labels use the same disjoint protocol. This task adds file-backed research evidence; it does not backfill the common SQL event ledger or label events as anomalies. Existing Context event capture remains unchanged.

Known inspected case **MX080/M6,7Sep12:24–24:00**:643 control-supported/quality/steady incident minutes,643 Local absolute flags and643 combined flags,629 persistent minutes after continuity resets. Frozen Local mean and scale equal the selected covariance-sharing proposal; Fleet weight≈2.30%. Nonsteady/unsupported minutes abstain; this is a known-case regression, not prospective recall/whole-episode sensitivity. No new fault cause is assigned.

## Web and performance

Calibration→select machine→**Fleet Reference**→M1–M8→Fit1/3/7/14days. Independent on-demand machine/day graphs show observed **minute averages**, not Raw seconds; pressure psi, temperature°C. Transition tables and method notes collapse by default. Query keys include complete machine/module/day; prior-module numbers are hidden during placeholder loading. Graph cards stay358px in the tested viewport, no “Loading chart data” text. Date input handles input/change; days outside the corpus disable the graph action, missing committed days show a readable error and empty reserved charts. The source selector now merges080/MX080 aliases into one entry, summing stored row counts and taking outer observed coverage; raw alias rows are untouched.

Actual browser UI: three concurrent tabs041/M1,058/M2andM7,081/M8; switching Fit1day; missing041Jul1; out-of-rangeOct5; source-machine switch to080/M6andSep7 case graph. See `browser-qa.json`/screenshots in local outputs. This is manual UI action QA through the browser, separate from HTTP automation. It does not claim Manual Build→review→prospective→Active-success for Fleet.

Prepared reads:64firstGETs across four assets/all8modules (Reference+day), then10clients/120GETs all200. Warm p50 **53.1ms**, p95 **109.0ms**, max **121.0ms**; bounded first-read p95 **224.5ms**. The original24wire-entry cache churned on64views (warm p95≈402ms);128 immutable views with the same32MB byte cap improved measured p95≈204ms. Mutable Raw cache remains24. Cache coalescing is per API process; frozen file partitions are shared inputs. Fresh-process/cold SQL source inventory and full source preparation are not covered by the warm read claim.

Actual1361point Local+relationship batch scoring p50 **0.142ms**, p95 **0.243ms** (no IO/fit/UI). Offline full benchmark **172.7s**; full raw SHA/Valve audit≈590s. Derived study≈228MB; reads are bounded by day/module, no request-time fitting. Frozen version/hash checks reject source/derived revisions even after a cached read.

## Verification and remaining gates

Full suite before final small cache/selector patches: **225passed**,450 existing SQLite adapter deprecation warnings. Focused final cache/source/API regressions: **7passed +13passed**, and final benchmark precision/drift/split regressions **3passed**. TypeScript and Vite production build pass; existing large bundle warning remains. Actual execution: Python3.12.10, NumPy2.2.1, pandas2.2.3; direct SciPy dependency1.16.2 recorded. Requirements pins differ from the existing local NumPy/pandas environment; no environment reinstall was performed.

Canonical sorted-JSON-line hashes (same helper as pre-work snapshot): Profiles207, `04c30ac95a435e3345041f5015518624d7c3075112c9708b7d8689fa6d28e5d5`; Active46, `7f05d8a04d3c01a3f0a4513592d1200c8d2096449187ce38ed866ba51f377be1` — both unchanged. ContextActive0, import receipts567 unchanged. No source DML, Candidate/Active promotion, worker launch, Server deployment or Git push. API8000 and Vite5176 remain running locally; service PIDs are in `services.json`.

To progress to operational Fleet use: verified hardware/role/configuration/controller/pressure basis/service epoch per asset; Engineer-reviewed normal regime references; independent healthy cycles and known cases; frozen prospective target validation; explicit compatible Profile version/rollback integration. The algorithm can assist sparse but comparable Local evidence; when similarity cannot be established or a regime is unreviewed, it abstains. Zero Local evidence is not certified normal using unrelated Fleet data.

## Sources and reproduction

Dhada et al.[2020](https://doi.org/10.1017/dce.2020.19) motivate collaboration within similar-asset clusters; their Gaussian/NIW model and synthetic experimental results do not certify these machines. Bull et al.[2022 preprint](https://arxiv.org/abs/2204.12404) motivate hierarchical sharing across subgroup effects; its fleet tasks differ from HT9046MX anomaly detection. Ghauch et al.[2025](https://doi.org/10.1017/dce.2025.3) motivate operating-segment matching to limit negative transfer; predictive MSE gains are not fault-detection accuracy here. Our bounded correlation-only update is an engineering adaptation, not a replication of those papers.

Read executed `notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb`. Reproduce from workspace root: `python -m notebooks.support.fleet_reference_study --intake`, `python -m notebooks.support.fleet_reference_benchmark`, then with localAPI8000 `python notebooks/support/fleet_reference_qa.py`. The private ZIP/receipts/day partitions are required; they are not published. Source hashes, adapter/core/implementation hashes, protocol, environment, model proposals, transition metrics and QA receipts are in the ignored local output directory.
