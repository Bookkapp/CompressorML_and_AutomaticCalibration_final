> **7 Oct 2026 ? actual .73 Server setup, PARTIAL:** `th1pmdbdev1w` / Windows Server 2022. Dedicated venv (existing Python3.13; Python3.12 installer blocked1625), authenticated Git/LFS/checksums, metadata backup, least-privilege source/analytics accounts, additive schemas and Fleet Shadow revision1 installed. Actual6machine?8module cycle:6,816source rows/968module-minutes. Fixed MySQL checkpoint TEXT overflow with LONGTEXT;262API tests/build pass; isolated actualMySQL rollback/reconnect/retry pass. Temporary loopback API/frontend and detector-only Worker work; persistent task registration denied (non-elevated token), authenticated LAN/roles and .69bridge remain pending. Cold inventory65.905s;60/60warmGETs/10clients p95257.96ms exclude browser/cold work. Existing15Profiles/0Active registry hashes unchanged; no source writes or approval. Source lag/late quarantine remains unresolved. Evidence: `deployment/SERVER_ACCEPTANCE.md`.

# Graft — Code, Data, and Model Connection Map

**6 Oct — separate technician queue UI removed at owner request:** Removed menu/page, confirmation drawer/form and 10-second incident polling plus unused frontend calls/styles. Four workflow menus remain. TypeScript/build and 12 API regressions pass; actual web shows zero queue buttons/no console errors. Existing historical records/server compatibility and manual Profile/Engineer gates remain. Evidence: deployment/TECHNICIAN_QUEUE_REMOVAL_20261006.md. No source/Profile/Active or Server change.


**6 Oct — latest owner instruction: insert Normal source data for 7–9 Oct:** MX058/M1 now has 86,400 unique raw seconds per requested day (259,200 rows), Run/On/Busy0/SVOff. Frozen Reference probe: 4,320 minutes, zero flags. Profile/Active registries unchanged. Future dates are explicitly requested fixtures; the real clock gate still blocks their current-day validation. Receipt: notebooks/outputs/normal_days_7_8_9_20261006/receipt.json. No new UI or approval action. Earlier elapsed-only checkpoint below is historical.

**6 Oct — owner correction: standard manual workflow restored; elapsed Normal SQL fixture only:** Removed the added Mock UI/API/feature flag/approval exception/virtual clock and the exact test Active/Profile. Backed up and removed259,260 future rows; archived obsolete Mock inspection. MX058/M1 now has21,540 elapsed Normal fixture seconds (08:05–14:03:59 today; Run/On/Busy0/SVOff), with synthetic provenance in the batch ledger and no generated M2–M8 values. Original207/46legacy and110/0Context registry hashes restored exactly;567import receipts unchanged.27focused regressions/TypeScript/Vitebuild pass. Standard manual web restored and inspection/approval left to owner. Reference frozen today08:04:35 means real prospective days remain0/3, first eligible7Oct; no contracts/Engineer/scope invented. Source/worker/Server limitations and reversible backups: `deployment/NORMAL_MANUAL_FIXTURE_20261006.md`. Earlier source-marker/trial checkpoints are historical.

**6 Oct — owner-requested Normal values inserted into the current local source table:** MX058/M1 only,15,420 second rows (08:05–12:21:59 today), marked `Status=MOCK_NORMAL`; numerical probe257/257 within frozen Reference. Exact batch receipt is durable in `ht9046mx_local_mock_batch`; no overwrite/future clock or Mock UI. Actual web inspection/day graphs succeed;254 inspected minutes under the existing open-day cutoff. Mock stays visible but cannot vote, fit Reference or provide real Active evidence; mixed validation receipts carry Mock/nonapproval provenance. Closed days remain0/3; original contracts/ON Reference/real future gates stay open. Profile/Active hashes unchanged.16 initial targeted tests plus12 final provenance/followup regressions and web build pass. Evidence: `deployment/NORMAL_TABLE_MOCK_UAT_20261006.md`. Earlier no-source-write checkpoints below are historical.

**6 Oct — owner-requested isolated scenario QA:** 17 synthetic cases / 73,260 observed minutes against actual frozen MX058/M1 and MX017/M1 OFF-only Profiles. Four accepted Normal modes have 17,280 within-Reference minutes/0 flags. Raised stable CP2 remains unresolved (12 deviation + 1,068 new-level minutes across three six-hour intervals); Valve alone does not flag; delayed response stays unsupported without accepted templates; first OFF after excluded ON is evaluated immediately. Short spikes can remain below the 1% aggregate threshold despite per-minute detection. Missing/quality/manual minutes are unevaluated, not healthy. All behavioral assertions and executed Notebook rerun parity pass; registry/source heads unchanged, no Mock UI or runtime/source/Profile/Active writes. Evidence: `deployment/FROZEN_CONTEXT_SCENARIOS_UAT_20261006.md`; Notebook15. Real future/engineering/Server gates remain open.

**6 Oct — post-freeze progress and interim inspection delivered (no Mock UI):** Calibration step 3 shows frozen time/source latest, received closed days versus inspected supported days, daily categories/missingness and saved day/Raw evidence. Same-day inspection begins at the first full minute after review; it never counts as an approval day. Bounded 4-day inventory/shared 30s reads, durable coalesced jobs, immutable 5-minute partial snapshots and future-clock guards preserve frozen Profiles and the real 3-day prospective gate. Full 256 tests before final refinements plus 9 final followup tests/TypeScript/Vite build pass; actual 017/058 two-tab QA/no Mock/no errors and 10 clients/120 metadata GETs all succeed (warm p95 68.54 ms, cold capture/scoring/render excluded). MX058 source 5 Oct 14:45 precedes freeze 6 Oct 08:04, so 0/3 and no actual post-freeze inspection yet. Legacy 207 Profiles/46 Active, Context 110 Profiles/0 Active and 567 import receipts unchanged in read-only QA. Actual future/Engineer/contracts/Active/Server acceptance remains open. Evidence: `deployment/CONTEXT_FOLLOWUP_PROGRESS_UAT_20261006.md`. Earlier checkpoints below are historical.

Followup edge: `context_api` → indexed `context_followup.progress` shared reads → existing `automatic_reference`/`reference_jobs` queue → observed snapshots + frozen `assess_context` → job result/common Event → `ContextFollowupProgress`/saved day/Raw. It does not write Profile/future-validation/Active receipts. Source SELECT-only; partial snapshots never replace complete-day pointers.

**6 Oct — original items 3–6 implemented and locally tested:** Added reference-only Fleet Transition catalog, independent event-response admission, frozen-review source/version guard and actual source graphs; saved real Shadow report with flagged episodes → Raw; pinned Fleet Shadow producer in the common Event/checkpoint transaction; durable isolated retraining and Fleet Models compare/Shadow approval/rollback. Six-machine manual web training completed in203s; actual4machines×8modules SQL restart/retry rehearsal and120/120preparedGETs/10clients passed (warm p95173ms).248full API tests before final refinements plus25final targeted tests/TypeScript/build; executedNotebook14. All43steady model values and207legacy/46Active snapshots preserved,ContextActive0.144Transition groups/512Reference events/114holdout; zero donor groups pass independent screening (1929/2356minutes outside), so unsafe transfer remains unavailable. Normal/configuration/untouchedfuture and actualServer acceptance remain open. Owner requested Markdown setup handoff for10.195.17.73, with trigger “Set up ระบบนี้ให้หน่อย”. See `deployment/FLEET_WORKFLOW_UAT_20261006.md` and `deployment/SERVER_WORKER_HANDOFF_20261006.md`. Older checkpoints below are historical.


**6 Oct — Mock UI removed at owner request:** Calibration step 3 now contains real frozen-Reference validation and Active readiness only. Removed the Mock component/client/type/styles; actual MX058 UI shows zero Mock buttons, no browser errors, and final TypeScript/Vite build passes. Internal QA evidence/provenance guard is retained; no source/model/review/Active state was changed. Continue original items3–6: reviewed SV ON/Transition Reference for included states; real healthy/frozen-future validation; target Server worker/common Event History; Fleet Model Management. Missing intentionally excluded SV ON is not a prerequisite. See `deployment/MX058_NORMAL_MOCK_UAT_20261006.md` (removal checkpoint).

**6 Oct — MX058 frozen normal Mock:** Added an explicit synthetic three-day Steady test in Operation step 3 using saved MX058/M1 Profile `2a7990dd1d81…`; virtual7–9Oct/4,320minutes/Flag0%. Read-only mock receipts cannot satisfy prospective/Active approval. Included ON still has no accepted Reference; real contracts/future gates remain.20 targeted tests, TypeScript/build, all3day UI charts and48/48preparedGETs pass; frozen/legacy/import hashes and ContextActive0 unchanged. Fleet Stable v1 helps Steady/correlation shape; Transition statistics do not yet transfer approved response envelopes to Local automatically. Evidence: `deployment/MX058_NORMAL_MOCK_UAT_20261006.md`. Older entries are historical.

**6 Oct — explicit SV evaluation scope and Coverage implemented:** Owner-authorized per-Profile OFF/ON scope allows approval with Reference for included states only; explicitly excluded states are NOT_EVALUATED with no model score, while Raw/control/events remain available. Returning to included state checks frozen Local Reference immediately without a cooldown. Immutable scope/validation fingerprints, included-state evidence gates, revision CAS, reviewer-specific draft hydration and M1–M8 Coverage UI are implemented; legacy unscoped semantics and Fleet frozen bundle remain unchanged. Full API237 tests and final web build pass; actual manual save/reload/stale-tab/Raw/reviewer and017/024 multi-tab QA pass.10clients/120preparedGETs allsuccess, warm p95680.1ms (cold source/render excluded).207legacyProfiles/46legacyActive hashes unchanged,ContextActive0. Technical QA review is not Engineer-certified; contracts/Engineer/new prospective validation/real Server/live producer acceptance remain open. Runbook: `deployment/CONTEXT_SCOPE_AND_COVERAGE_UAT_20261006.md`. Earlier checkpoints are historical.

**6 Oct — Fleet Stable v1 portable Shadow Candidate:** Frozen `fleet-stable-v1-2f656893533033ab994e3713`, 43 calibrated SV-context profiles/70 donor summaries from017/024/041/058/080/081, all8modules considered.555preparedday hashes/46,616,484raw-row receipts verified. Local absolute levels/scales retained; compatible correlation-shape EB-style sharing only. Fit-only Q90 trailing five-minute movement bounds replace the over-tight0.35-only phase screen for this separate Candidate; no legacy/Active Gate changes. MX080/M6 proposed Fit27–30Aug/calibration3–6Sep; owner-described, not Engineer-certified health. Known7–8Sepcase2089/2089eligible flags/2079persistent; pre-case480minutes2raw/0persistent; acquisition-suspect34minutesDATA_QUALITY/0physical flags.12SepnewValve/level remains unreviewed. JSON/checksum ZIP, configurable portable loader, atomic Shadow CAS/rollback, later explicit retraining plan, version-pinned calibration evidence UI and common-ledger adapter delivered.43,227point score parity exact; prepared10clients/120GETs allsuccess, warmp95201.5ms (coldSQL/UIexcluded). Actual3tab/manualmodule/date/missingday QA; chartcards358px/noLoadingtext. Local Shadow pointer only;207Profile/46Active canonical hashes unchanged,ContextActive0,no source import/Server/livevotes. ReviewedNormal/sourcecontracts/independenthealthy/untouchedfuture/verifiedproducer/targetServer acceptance remain open. Report: `deployment/FLEET_STABLE_V1_RUNBOOK_20261006.md`; executed Notebook13. Earlier checkpoints are historical.


**5 Oct — MX080/M6 CP2 episode review (analysis only):** Owner supplied Aug23/24/26/31 and Sep1/2/7/8/10 hypotheses; HP2/LP2 are primary.24 source days/10 raw rereads851,177rows and30 raw-minute parity checks. Off/Valve0 pressure equalization is distinct from reviewed Run. Sep7–8 supported HP2/LP2/delta medians334.9/27.1/308.5 vs190.5/18.8/171.7; stable abnormal plateau retained. Sep7 M6 four pressures580.2+both temperatures-200 for1896observed rows suggests acquisition/default-value issue, not filling. Sep10 remainsStatus_6Off/Valve0; supported On resumesSep12 afterChangeValve withValve100/new level. Refrigerant filling/leak remains unconfirmed; proposed healthy/exclusion/service epochs require review. No retrain/source/model/Active/SQL/Server changes. Evidence: `deployment/MX080_M6_CP2_EPISODE_REVIEW_20261005.md`, executed Notebook12. Fleet Stable deployment remains a planned next task.


**5 Oct — Fleet Reference / selective transfer delivered:**

Committed import receipts + local dynamic ZIP SHA/row count → `notebooks/support/fleet_reference_study.py` → bounded all-state1m-v3 per-day Parquet + original within-day state/command events → `fleet_reference_benchmark.py` → time/asset-separated proposals and diagnostics. `apps/api/app/fleet_assistance.py` performs bounded robust-moment selective pooling; frozen Local absolute evidence remains. `fleet_reference_api.py` reads only frozen prepared evidence with source/derivative checks → `FleetReferencePanel.tsx` in Calibration. No edge from these research proposals to Context runtime votes, registry/Active writes or SQL event backfill. `context_reads.py` raises only immutable wire entry cap to128;32MB and mutable Raw24 remain. `repository.py` merges source selector aliases after cache reads. Notebook11/report/technical and browser QA receipts document this edge. `deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md`.

## 5 Oct — additional local raw history intake

Downloads/MX041, MX058, MX081 plus selected MX080 archives → `notebooks.support.import_requested_machine_history` → exact82-column normalization and daily SHA receipt check → `LOAD DATA INFILE` append into `ht9046mx_iot.ht9046mx_readings` + same-transaction receipt in `ht9046mx_analytics.ht9046mx_history_import_file`. Owner stopped the shared1Jul–1Oct2026 intake at369/372 files:04192,05892,08193,08092; missing only1Jul for041/058/080. Target has31,042,099 rows; total ledger381 files/31,963,964 rows includes12 extra Oct2–5 receipts. C: had24.80GiB free; MySQL stayed on C: and no storage/config/Profile/Active/model/alert change occurred. See `../deployment/DOWNLOADS_HISTORY_CAPACITY_REVIEW_20261005.md`. No analysis/Profile/Active/model/alert records are created automatically.

## 5 Oct — conditional Profile and unified event connections

`observed_context` separates measured all-state minutes from legacy eligibility. `context_storage` shares streamed source-day intake/all8 snapshots with `unified_events.TransitionTracker` before gating. `context_reference` + durable `reference_jobs` produce immutable `context_profiles` v4 Reference regimes/templates and diagnostic Shadow boundaries. `context_review` maintains actor versions, frozen reviewed children, prospective gates and separate Active/rollback pointers. `context_reads` bounds/coalesces graph/Raw reads and encoded gzip caching; `context_api` serves review/investigation and verifies retained source mapping.

`ContextCalibrationWorkspace`/`ContextChart` display reviewed module/day/raw evidence. `EventHistory`/`EventEvidence` query common `ht9046mx_events`. Opt-in `context_monitor`/qualified detector-persistence and bridge hooks connect measured transitions, phase/episode and delivery events transactionally. `operational_inbox` supplies a private receipt boundary, but the actual PM ACK/work/service producer is not yet wired; no live worker was started. Local migration already created six analytics tables; source/legacy46Active unchanged. Code paths, QA and remaining release gates: `deployment/COMPRESSOR_CONTEXT_PROFILE_UAT_20261005.md`.

**4 Oct — Physical/control policy and manual regression:** New qualified Candidates use physical P/T scores, nonvoting Valve context and strict Q99.5 `>` comparisons; legacy stored nine-feature `>=` semantics remain. Current-cutoff Reference alternatives are automatic, older stable regimes require review. Reference-only recovery evidence opens Raw before/after SV/unknown boundaries and never suppresses flags. Sixteen actual-cache contexts/14 scorer comparisons have zero differences; known057/M1 and080/M6 case detections retained. Actual GUI checked all 16 modules and completed MX017/M1 exclusion → Preview → Build (SHADOW_VALIDATION; four source prerequisites still block approval). Backend174 tests/build passed; cached Raw40/40 GETs, p95≈539ms. MX024 cold preparation11m33s; reviewer editing after reload remains an unresolved browser UAT path. Active hash unchanged. Manual GUI UAT and limitations: `deployment/PHYSICAL_CONTROL_CALIBRATION_UAT_20261004.md`. Four verified source contracts, prospective healthy/recovery evidence and target-Server Active-success remain open. Older checkpoints below are historical.


**4 Oct — Calibration evidence and SV review:** Readable per-check values/actions, contributor intervals → minute/Raw charts, all-state bounded Raw GET, and bounded past-only per-module Reference proposal implemented. Owner-confirmed psi recorded; pressure basis + state/controller/service versions remain explicit prerequisites. Actual017/024each7Candidates/M7insufficient; no passing stable proposal in current search. 167 API tests plus saved-policy regression/build; exact four-context selector parity, actual browser interval/Raw/invalid-range/M7 and40GET/10client QA. SV study28files/2,385,588rows/196raw-minute checks finds material pressure/thermal differences: retainSVOff Cold gate, preserveSVOn Raw. Active46hash unchanged; no Server/push. Cold preparation remains≈10–12min on local machine; graph reads are bounded/on demand. Evidence: `../deployment/CALIBRATION_EVIDENCE_AND_SV_REVIEW_20261004.md`.

**3 Oct auto/manual edge:** source SELECT → exact observed-second streaming (`qualified_calibration.py`/`qualified_windows.py`) → analytics closed-day snapshots (`qualified_cache.py`; new `mysql_qualified_day_cache.sql`) → shared complete-day fit/review (`reference_review.py`) → durable module0parent/modulechildren (`automatic_reference.py`/`reference_jobs.py`) → immutable Candidate registry → manual Active approval. Web `AutomaticCalibration.tsx` opens reviewer-owned copies into `ReferenceReview.tsx`. Manual Build bypasses cache and checks exact SHA; no source/PM/Active writes in QA. Scoped worker shares the same edge. Evidence: `deployment/AUTOMATIC_CALIBRATION_UAT_20261003.md`.

**2 Oct — Manual Calibration UI repair:** `ReferenceReview.tsx` + `calibration-review.ts` handle validation/dirty-preview retention/reviewer recovery/cache freshness/empty graphs. Read-only `GET /api/v1/calibration/reference/jobs` lists12recent jobs for actor+machine+module; existing ownership checks remain. `App.tsx` resolves current profile by ID after refetch and resets decisions across contexts; CSS wraps Matrix/profile text. No feature/scorer/approval gate semantics changed. Build and actual16module Preview/graph/14Candidate reviews completed; Active-success and performance remain open: `../deployment/MANUAL_CALIBRATION_UAT_20261002.md`.

## Owner-authorized local raw history edge — 2 Oct 2026

Downloads fiveZIPparts → `october_three_machine_calibration.py::inventory/read_day` → `import_downloads_history.py` (017/024dynamic only,82mappedcolumns, full-rowmultisetreuse, namedmachinelock, fileSHA/version) → per-dayatomic`LOADDATAINFILE` append intoactual `ht9046mx_iot.ht9046mx_readings` + receipt into`ht9046mx_analytics.ht9046mx_history_import_file` → existing sourcediscovery/observed1mloader/ReferenceReview. Noedge toCandidateBuild/Activeapproval/scoreractivation/Server. `verify_downloads_history_import.py`: count/hash/204rawsamples/120exact1mwindows/APIchecks. Newdaily sourceavailabilityranges useexistingmachine/timeindex andoneconnection without changingquality/stateGates; latencystill~120s. MainUI5176verified. Evidence: `deployment/DOWNLOADS_HISTORY_IMPORT_20261002.md`.

## Normal local job storage repair — 2 Oct 2026

`mysql_reference_review.sql` → normal localhost analytics job table(18columns); `ReferenceReview.tsx` poll → `main.py::reference_call` classified SQL errors → `reference_jobs.py::get_job` reviewer-first read → only expired requested PK gets conditional expiry/current read. Admission cleanup SELECTs expiredIDs then PK updates; no global range UPDATE during poll. Regression: `test_reference_review.py`; actual SQL10-client/100polls plus same-key retry: `notebooks/support/reference_storage_repair_qa.py`. No edge to source DML/Active promotion/worker activation. Evidence: `deployment/REFERENCE_STORAGE_REPAIR_20261002.md`.

## Source-day preflight edge — 2 Oct 2026

`ReferenceReview.tsx` → `api.ts::referenceAvailability` → `main.py GET /calibration/reference/availability` → `reference_availability.py` → bounded source SQL daily counts → coverage-only suggested disjoint Reference/Shadow. Explicit `shadow_end`/reason goes through the existing Preview job/digest/detail/atomic Build flow. `reference_review.py` v2 also checks qualified Shadow days/minutes before Build. Tests: `test_reference_availability.py`, `test_reference_review.py`; actual SQL isolation receipt: `notebooks/support/reference_availability_qa.py`. No source writes or Active/scorer changes; no new DDL. Evidence: `deployment/REFERENCE_AVAILABILITY_V2.md`.

## Actual MySQL experiment edge — 2 October 2026

`source-mysql-experiment.html` → `source-mysql-experiment.tsx` (dev-only graphs/ReferenceReview) → API8178 `reference_review_mysql_experiment.py` → guarded read-only localhost `ht9046mx_iot.ht9046mx_readings`. Real latest query/observed-second loader retained; no cache adapter. Reference jobs/batch/profile/shadow write only `ht9046mx_reference_mysql_experiment_20261002`; Approval/Alert/feedback/legacy rolling blocked. `reference_mysql_experiment_check.py` creates ignored reconciliation receipt; boundary tests in `apps/api/tests/test_mysql_experiment_boundary.py`. Production Vite entry and sibling Dashboard unchanged. Actual source minute-grain limitations and launch commands: `deployment/LOCAL_MYSQL_REFERENCE_EXPERIMENT.md`.

## Reviewed Reference edge — 2 October 2026

```text
App.tsx Calibration → ReferenceReview.tsx → api.ts
  → main.py reference preview/job/day/build endpoints
  → reference_jobs.py (SQL queue/lease/idempotency, background day reads)
  → qualified_calibration.py observed-second SELECT → qualified 1m windows
  → reference_review.py date/exclusion selection + input digest + review graphs
  → unchanged qualified_candidate_registry.py (fit/quarantine/Q99.5/Shadow)
  → calibration.py::persist_batch(transaction=..., reference_review=...)
  → Candidate + Shadow tables AND job COMPLETED in one analytics transaction
  → App.tsx exact selected batch → existing human Approval gate
```

`deployment/mysql_reference_review.sql` adds `ht9046mx_reference_review_job`; no source/PM/Active table change. Retained-reference coverage is checked after quarantine; scorer and Active loader are not rewritten. `notebooks/support/reference_review_local_qa.py` replaces only the source reader with actual archived-minute caches and points persistence to isolated localhost QA schema, blocking Approval/Alert POSTs. It is not a production ingestion adapter. `reference-review-qa.html` is a development-only component harness, not a second deployed app. Tests: `apps/api/tests/test_reference_review.py`. Runbook/API/identity limits: `deployment/REFERENCE_REVIEW_WORKFLOW.md`. Legacy rolling route/CLI is still independent; offline phase selectors are not connected to this workflow.

**New local reference/phase edge — 1 Oct:** private strict observed-second-derived08K/08Lminute caches → `research/historical_shadow_reference_phase_protocol_v1.json` → `notebooks/support/historical_shadow_reference_phase.py` (per-machine complete-day cut, causal S/V, fit-only segment/steady selectors, frozen offline-reference JSON, unchanged 3-minute rule replay) → ignored `notebooks/outputs/historical_shadow_reference_phase_v1/` → `audit_historical_shadow_reference_phase.py` / `historical_shadow_reference_phase_presentation.py` → executed Notebook08M/9figures/HTML. Focused tests `test_historical_shadow_reference_phase.py`. No edge to runtime candidate registry, Active loader, worker, Dashboard, SQL or Server. Integration recommendation/negative result in `deployment/HISTORICAL_SHADOW_REFERENCE_PHASE_EXPERIMENT_20261001.md`.

**New local experiment edge — 1 Oct:** original raw-second Parquet029/041/057/070/118/119 + October017/024/080 strict minute cache → `notebooks/support/local_profile_model_selection.py` (identity/precision adapter, train-only local reference screen, causal1m lags, shared ARX/DPCA/IF, past-local cuts, adapted LOMO) → ignored `notebooks/outputs/local_profile_model_selection_v1/` (frozen shadow joblib, minute scores, inventories, tables) → `local_profile_model_selection_presentation.py` / `execute_local_model_selection_notebook.py` → executed Notebook08L + PNG/SVG/HTML. Protocol under `research/local_profile_model_selection_protocol_v1.json`; tests in `test_local_profile_model_selection.py`. `qualified_windows.py` is imported only for actual-source parity. **No edge to candidate registry, Active loader, live worker, PM Alert, Dashboard or MySQL.** Selection/QA: `deployment/LOCAL_PROFILE_MODEL_SELECTION_20261001.md`.

**Research-only edge — 1 Oct:** `qualified_windows.py`/`qualified_calibration.py`/`qualified_candidate_registry.py`/`qualified_scoring.py` + Notebook 08K evidence + primary papers → `research/HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md`. Proposed raw event inventory → event response/reference → ARX/DPCA shadow edges do not exist as new implemented modules in this checkpoint. Source-state exclusion in the steady builder is not source deletion; raw retention is a separate archive concern. No detector/Profile/DB/Server connection added.

**Contributor presentation (1 Oct):** `apps/web/src/components/RehearsalDashboard.tsx` filters panel shading through stored z/threshold, without recalculating scores. Dashboard sibling `frontend/src/detector-chart.mjs` owns contributor grouping/tooltip and `DetectorEvidence.jsx` responsive summaries/table. Design-only multi-start method: `deployment/STARTUP_SETTLING_VALIDATION_PLAN.md`; no runtime settling module or fitted parameter added.

**Durable integration — 1 Oct:** `qualified_detector.py` source reader/receipts → `qualified_persistence.py` namespace/checkpoint → existing `qualified_windows.py`/`qualified_scoring.py`/`qualified_episodes.py` → outbox → `qualified_bridge.py` PM receipts/evidence/Alert → sibling Dashboard `app/detector_evidence.py`, `app/main.py` route and `frontend/src/DetectorEvidence.jsx`/`detector-chart.mjs`. `qualified_archive.py` exports observed raw/windows/contract; purge off. QA: `notebooks/support/durable_detector_qa.py` and sibling `scripts/qa_detector_database.py`, targeted unit tests. Migration: `deployment/mysql_detector_worker_audit.sql` + explicit detector/bridge migrate-only. Runbook/limitations: `deployment/SERVER_DETECTOR_RUNBOOK.md`, `DURABLE_DETECTOR_LOCAL_QA.md`.

**Dashboard rollback (2026-10-01):** Removed the last-turn custom build-version → static-page-reload edge from the sibling Dashboard. The incident-report edge below remains; no Operation scoring or live bridge connection changed. QA: `../Compressor_and_VacuumPump/graft/CHANGE_CHECKLIST.md`.

**Episode/report edge (2026-10-01):** unchanged `qualified_scoring.py` → `qualified_episodes.py::EpisodeArchive` + raw review statistics from `qualified_evidence.py` → atomic `qualified_persistence.py` rehearsal Episode/raw/checkpoint tables → GET rehearsal points/raw → `RehearsalDashboard.tsx`. Separately, sibling Dashboard `maintenance_evidence.py` + `services.py` → `pm_work_orders` reported interval/origin → linked `pm_maintenance_logs.incident_context_json` frozen snapshot → Assigned Work/Service Logs UI. `pm_work_orders.source_alert_id` is PM Alert ID, not analytics Episode UUID. New live scorer→PM Alert mapping is still absent; no automatic dataset label or Profile activation edge. Full map/QA: `deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md`.

**Incremental-case edge (2026-09-30):** MX057 raw daily Parquet and MX080/M6 observed-second forensic Parquet → `notebooks/support/case_incremental_replay.py` → `apps/api/app/qualified_stream.py::CompletedMinuteStream` (five-minute delivery, open-minute buffer, 30-second grace, batch retry ledger, JSON checkpoint) → shared `qualified_windows.py` → `QualifiedShadowScorer` → local case report/figure and ignored per-minute evidence. Candidate profiles are fitted on earlier days only. This edge has no MySQL persistence or worker/UI connection yet. Tests: `apps/api/tests/test_qualified_stream.py`.

**Reviewed-case edge (2026-09-30):** `notebooks/support/mx057_m1_shadow_diagnostic.py` + local raw Parquet → generated `cases/MX057_M1_2026-08-29/evidence/` figures/aggregate summary; project-owner confirmation → hand-authored `cases/MX057_M1_2026-08-29/case.json` and README. This is a historical case registry, separate from prospective `Phase 8` technician-feedback MySQL tables and absent from live inference/retraining.

**MX057 local graph edge (2026-09-30):** local raw-second Parquet (20–29 Aug) → `notebooks/support/mx057_m1_shadow_diagnostic.py` → shared `qualified_windows.py` + `qualified_candidate_registry.py` → ignored `notebooks/outputs/mx057_m1_shadow_diagnostic_v1/` (candidate-shadow summary and four PNGs, including un-interpolated source-second onset and sustained hour). Read-only diagnostic only; no connection to MySQL Active Profile or live scoring.

**30 Sep local restart edge:** `qualified_1m_parquet_replay.py::_replay_candidate` now runs the same MX057/MX070 shadow twice: one-shot, then midpoint JSON checkpoint → `QualifiedShadowScorer.from_checkpoint` → continuation. It compares each resumed result and candidate shadow point; MX070/M6 had zero mismatches on 4,256 scored minutes. These checks stay in memory and do not write MySQL or activate a profile.

**Local test edge (2026-09-25):** local raw-second Parquet → `notebooks/support/qualified_1m_parquet_replay.py::run_many` (one daily read across requested modules) → `qualified_windows.py` → `qualified_candidate_registry.py` (seven-day past fit + three-day shadow) → synthetic in-memory `ApprovedProfile` → `qualified_scoring.py::QualifiedShadowScorer` → per-minute candidate/scorer parity, runtime and memory report. This edge exercises the core rule without Server/MySQL writes or real Active-Profile promotion; M1+M6 parity passed on MX057. Further local incremental/restart tests precede Server integration.

**Current selected one-minute branch (2026-09-25):** source SELECT/raw seconds → `apps/api/app/qualified_calibration.py` (bounded read, strict 1m quality) → `qualified_windows.py` → `qualified_candidate_registry.py` (past-only fit, future three-day shadow) → `calibration.py::run_qualified_one_minute_calibration`/`persist_batch` (candidate registry + shadow graph points, **not** Active) → human review/rollback boundary. Separately, `qualified_shadow_preview.py` loads only exact-version human Active Profiles → `qualified_scoring.py` read-only robust-z + three adjacent qualified minute persistence; `inference.py` blocks legacy raw-row writes and only permits this read-only preview when opted in. `notebooks/support/qualified_1m_parquet_replay.py` exercises the pure candidate branch with local raw files and writes no database. No current edge to live score/Health/PM alerts. Historical five-minute and minute-snapshot paths below are not compatible; see `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

**Last updated:** 2026-09-25

MX080 actual-Active diagnostic branch (2026-09-25): localhost source MySQL minute rows + localhost analytics `ACTIVE_FROZEN` profile 21 and stored shadow points + existing observed-second forensic file for timestamp cross-check → `notebooks/support/mx080_active_profile_replay.py` → ignored local `notebooks/outputs/mx080_active_profile_replay_v1/` (summary, daily/episode/minute CSV, two figures, report). This is a read-only **historical one-minute** branch. It does not feed or approve `qualified-cold-observed-5m-v1`, `inference.py`, PM Alerts, Health or EWMA/CUSUM. New strict five-minute preview remains a separate abstaining branch on minute-grain MySQL.

Implemented read-only five-minute branch (2026-09-25): source SELECT connection → `apps/api/app/qualified_calibration.py::load_observed_five_minute_windows` → `qualified_windows.py::build_completed_windows` → strict Active-profile lookup in `qualified_shadow_preview.py` → pure `qualified_scoring.py` primary robust-z/persistence + EWMA/CUSUM numerical shadow → preview counts only. `qualified_temporal_fit.py` proposes separate-block candidate limits; it is not connected to the live vote. `inference.py::run_inference_and_sync` now blocks historical raw-row writes by default, and its opt-in invokes preview only. There is **no edge** from this new branch to analytics score tables, PM Alerts, Dashboard graphs or Active-Profile approval. See `deployment/QUALIFIED_5M_SHADOW_IMPLEMENTATION.md`.


Owner-selected rule-only deployment map (2026-09-25): source `ht9046mx_iot.ht9046mx_readings` → `apps/api/app/calibration.py` one-minute candidate gate/two-pass profile/three-day shadow → analytics registry tables in `deployment/mysql_phase6_calibration_registry.sql` → `apps/api/app/repository.py` human review/active pointer → `apps/api/app/inference.py` robust-z envelope → `deployment/mysql_shadow_schema.sql` score/episode and optional PM sync → Web UI/technician review. `apps/api/app/worker.py` schedules candidate and score commands; `apps/api/app/model_bundle.py`/Cold ARX artifacts are **not** on this live path. The current inference edge still fetches raw rows through analytics `connection()` and must be aligned with the intended read-only, qualified five-minute edge before release. Full contract: `deployment/RULE_ONLY_ACTIVE_PROFILE_PIPELINE.md`.



One-second diagnostic-only branch: raw daily `ht9046mx_readings` Parquet (local, excluded from Git) + the offline Cold candidate's train-only profiles/split manifest + minute cache → `notebooks/support/one_second_valve_audit.py` → `notebooks/outputs/ht9046mx_one_second_valve_audit_v1/` (CSV/JSON/figures/report). This branch only reads; it neither feeds `apps/api/app/inference.py` nor changes the candidate model/threshold/Active Profile. A server second-level ring buffer remains planned, not implemented.

Historical model-loading path: `shadow_release_manifest.json` + `shadow_model_registry.json` + portable `.joblib` → `apps/api/app/model_bundle.py` (checksum/feature-order verified, read-only, shadow-only). This is separate from `apps/api/app/inference.py`, which still computes a robust-z envelope and now records its own scorer version. No ARX artifact is used by live scoring.

New offline candidate path: local ignored `minute_module_state.parquet` → `notebooks/support/phase7_cold_candidate.py` (Cold gate, train-only local profiles, causal five-minute lags, inner alpha selection, past calibration, retrospective temporal/LOMO) → `notebooks/outputs/ht9046mx_phase7_cold_candidate_v1/` (small manifest/model/profiles/QA artifacts) → `apps/api/app/model_bundle.py::load_cold_candidate`. `apps/api/app/cold_arx.py` defines the importable model contract. This path does **not** read MySQL Active Profiles, write live scores, approve a profile or close Phase 7.
Quantization-aware comparison branch: the same past-only training script with `--quantized-valve` → separate `notebooks/outputs/ht9046mx_phase7_cold_candidate_v2_valve_quantized/` artifact and versioned scale/feature/threshold contract → `notebooks/support/compare_cold_candidates.py` matched retrospective rates and chart. Both candidate bundles load through `apps/api/app/model_bundle.py::load_cold_candidate` only as `SHADOW_ONLY_NOT_AUTHORIZED`. Neither branch connects to live inference or MySQL Active Profiles.
**Purpose:** แผนที่สำหรับดูว่าไฟล์ใดสร้างข้อมูลอะไร และผลลัพธ์ถูกส่งต่อไปใช้ที่ไหน

Private Server handoff repository: `https://github.com/Bookkapp/CompressorML_and_AutomaticCalibration`

Planned append-only ML analytics database target: `10.195.17.73`; deployment contract is `deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md`. The raw telemetry source remains a separately configured read-only dependency.

Dashboard bridge (code-level, not production-approved): `apps/api/app/inference.py::sync_pm_alert` → `predictive_maintenance.pm_alerts` (Compressor issue only) → Dashboard Acknowledge → `pm_work_orders.source_alert_id` → linked Service Log. Inference also writes `ht9046mx_iot.compressor_health_scores` for Dashboard read-only display. `HT9046MX_SOURCE_TIMEZONE` and accepted profile/release gates must be verified before live emission.

Local isolated mock path (2026-09-23): `ht_mock777_source.ht9046mx_readings` → `apps/api/app/calibration.py` → `ht_mock777_analytics.ht9046mx_calibration_profile` (`SHADOW_VALIDATION`, not active) → `scripts/score_mock777.py` injects profile in memory only → `apps/api/app/inference.py` → `ht_mock777_source.compressor_health_scores` → Dashboard `ReadOnlyTelemetrySources` → M1/M2 Health Score UI. `scripts/mock777_env.py` and `run_mock777_api.py` keep the OPERATION process on localhost mock schemas. No profile was approved and no non-mock source table was written.

## Repository map


`HT9046MX_Improved_Data_Pipeline_and_Architecture_Summary.md`
→ system-only architecture contract for data/state gates, local profile, `Self + Dynamic + Peer + Temporal` evidence, persistence, Server shadow monitoring and technician feedback.
→ The document is methodology/design only; it does not represent an implemented live worker or a trained new model.

Additional input: external `Data Analysis` MX folders and MX057 ZIP members
→ `notebooks/support/external_dataset_intake.py`
→ `notebooks/outputs/ht9046mx_external_intake_v2/{source_manifest.csv,canonical_novel/,external_minute_module_state.parquet,partition_qa.json}`
→ `notebooks/07B_HT9046MX_External_Dataset_Intake_Colab.ipynb`.
The current daily pressure summary is regenerated from 354 raw daily files and exposes `hp2_below_180_pct`; `train_enabled=false` remains mandatory.
→ `notebooks/support/external_event_coverage.py`
→ `notebooks/outputs/ht9046mx_external_event_coverage_v1/{external_clean_events.parquet,external_event_coverage_by_context.csv}`
→ `notebooks/07C_HT9046MX_External_OneSecond_Coverage_Colab.ipynb`.
See `notebooks/EXTERNAL_DATASET_INTAKE.md` for provenance, gates and rerun instructions.

MX-080 incident input: Desktop `Pressure - Copy/2026_09` + `MessageLogs - Copy/2026_09_01.csv`
→ `notebooks/support/mx080_module6_forensics.py`
→ `notebooks/outputs/mx080_module6_forensics_v2_hp180/{module6_one_second_unique.parquet,message_events_parsed.csv,water_message_keyword_evidence.csv,water_message_prior_pressure_snapshot.csv,module6_event_snapshots.csv,module6_period_summary.csv,analysis_summary.json,figures/}`
→ `notebooks/07D_MX080_Module6_OneSecond_Forensics_Colab.ipynb`.
The separate Temperature log is deliberately not joined until a channel-to-module mapping is verified.

Primary minute cache → `notebooks/support/phase7_benchmark.py`
→ `notebooks/outputs/ht9046mx_phase7_benchmark_v2_hp180/` with the versioned 180–230 psi field-reference contract
→ locked ARX lane selected from inner validation.

Locked Phase 7 hp180 benchmark + primary minute cache + MX-080 one-second fixture
→ `notebooks/support/phase7_shadow_replay.py`
→ `notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/`
→ `notebooks/07_HT9046MX_Server_Shadow_Replay_Colab.ipynb`
→ `deployment/README_Server_Shadow.md` + `deployment/mysql_shadow_schema.sql`.
→ `deployment/SYSTEM_DEPLOYMENT_FLOW.md` documents the intended Server topology, decision path, human feedback loop and acceptance gates; it is not an implemented service.
→ `deployment/CODEX_SERVER_HANDOFF.md` packages the implementation prompt, environment audit, runtime components, parity values and Definition of Done for Server Codex.
→ `deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md` defines the database host role, append-only storage boundary, environment split and DBA/worker acceptance checks.
→ `apps/api/` exposes Fleet/Incident/Timeline/Prospective-Confirmation/Automation APIs and a candidate-only scheduler.
→ `apps/web/` provides the React/Vite Lovable-compatible Dashboard and technician workflow.
→ `deployment/mysql_phase8_confirmation_only.sql` adds append-only prospective binary confirmations; the former cause-taxonomy migration is legacy-only.
→ `deployment/docker-compose.analytics.yml` connects API, scheduler and Web containers; production secrets remain outside Git.

```text
README_System.md
│  system semantics, tag contract, operating rules
│
├─ HT9046MX-20260902T013607Z-1-001/
│  └─ raw parquet data by machine/date
│
├─ notebooks/
│  ├─ README.md
│  ├─ 00_HT9046MX_Notebook_Navigator_Colab.ipynb
│  ├─ 00A_HT9046MX_Project_Master_Summary_Colab.ipynb
│  ├─ 00B_HT9046MX_System_Story_Colab.ipynb
│  ├─ 06_HT9046MX_AutoBootstrap_Profile_Lifecycle_Colab.ipynb
│  ├─ 07D_MX080_Module6_OneSecond_Forensics_Colab.ipynb
│  ├─ 07_HT9046MX_Server_Shadow_Replay_Colab.ipynb
│  ├─ HT9046MX_Visual_Analysis_Colab.ipynb
│  ├─ HT9046MX_State_Aware_Baseline_Analysis.ipynb
│  ├─ HT9046MX_ML_Calibration_LOMO.ipynb
│  ├─ HT9046MX_1Second_Window_Response_Analysis_Colab.ipynb
│  ├─ HT9046MX_ML_Minute_vs_SecondDerived_Comparison_Colab.ipynb
│  ├─ HT9046MX_Data_Analysis_to_ML_Phased_Colab.ipynb
│  ├─ build_ht9046mx_*.py
│  └─ outputs/
│     ├─ ht9046mx_colab_analysis/
│     ├─ ht9046mx_ml_calibration/
│     ├─ ht9046mx_1s_window_analysis/
│     ├─ ht9046mx_ml_second_comparison/
│     ├─ ht9046mx_visual_story/
│     ├─ ht9046mx_presentation_v2/
│     ├─ ht9046mx_autobootstrap/
│     ├─ ht9046mx_navigator/
│     ├─ mx080_module6_forensics_v2_hp180/
│     ├─ ht9046mx_phase7_benchmark_v2_hp180/
│     ├─ ht9046mx_phase7_shadow_replay_v2_hp180/
│     └─ notebook_qa/
│
├─ THESIS.md
│  └─ research synthesis, equations, model/HPO choices, Auto-bootstrap and Production QA design
├─ HT9046MX_Improved_Data_Pipeline_and_Architecture_Summary.md
│  └─ four-evidence system architecture; no executed intake/model result
├─ Project.md
├─ AGENTS.md
├─ SOT.md
├─ Roadmap.md
├─ UX.md
└─ research/
   ├─ report-source.md
   └─ claim-to-source-ledger.md
```

## Evidence-to-implementation lineage

`notebooks/00A_HT9046MX_Project_Master_Summary_Colab.ipynb` is the one-file, executed presentation companion. It reads the committed Auto-bootstrap, calibration and Phase 7 replay summaries/figures; it produces no profile, model, threshold or deployment mutation.

`notebooks/00B_HT9046MX_System_Story_Colab.ipynb` is the deep teaching/presentation companion. `notebooks/build_00B_presentation_notebook.py` reads machine split, nested temporal split, baseline, correlation, model benchmark and profile-lifecycle artefacts and writes slide-ready figures to `notebooks/outputs/presentation_system_story/`; it does not fit or activate a model.

```text
Primary research / official technical documentation
        ↓
research/report-source.md
        ↓
research/claim-to-source-ledger.md
        ↓
THESIS.md (synthesis, equations, model and experiment choices)
        ↓
README_System.md (approved system/data/model/QA contract)
        ↓
Roadmap.md + implementation notebooks/modules
        ↓
SOT.md (only results that have actually been verified)
```


## Data lineage

```text
Raw parquet
  │
  ├─ minute aggregation + state qualification
  │    ├─ machine_inventory.csv
  │    ├─ baseline_stats.csv
  │    ├─ baseline_comparability.csv
  │    └─ daily_baseline_trends.csv
  │
  ├─ calibration and relative features
  │    ├─ machine_module_sv_calibration_profiles.csv
  │    ├─ ml_relative_features.parquet
  │    ├─ temporal_validation.csv
  │    ├─ lomo_validation.csv
  │    └─ calibration_profiles/*.json
  │
  └─ one-second event extraction
       ├─ clean_event_summary.csv
       ├─ event trajectories cache
       ├─ minute_response_features.parquet
       └─ relationship_retention.csv
              │
              └─ minute vs 30 s vs 120 s model comparison
                   ├─ model bundles/*.joblib
                   ├─ temporal_model_comparison.csv
                   ├─ lomo_model_comparison.csv
                   ├─ deployment_benchmark.csv
                   └─ scored_temporal_events.parquet

State-qualified minute cache + clean event summary
  │
  └─ Phase 06 Auto-bootstrap candidate lifecycle
       ├─ temporal_profile_splits.csv
       ├─ candidate_profile_statistics.csv
       ├─ block_bootstrap_uncertainty.csv
       ├─ profile_lifecycle_status.csv
       ├─ event_profile_readiness.csv
       ├─ shadow_replay_results.csv
       ├─ approval_package.csv
       ├─ run_manifest.json
       └─ candidate_profiles/machine_*_candidate.json

Deployment decision path:

```text
Auto-bootstrap / local calibration profiles
→ relative and residual feature vector
→ cross-machine ARX-Ridge Fleet model
→ anomaly score and persistence
→ gated provisional Health/Condition view (`Normal within this profile` is profile-relative)
→ prospective binary technician-confirmation store for new alerts only
→ future supervised binary anomaly model after Label QA
```

The first four stages have offline evidence. The Health view is not calibrated, the prospective label store is not live and the supervised binary model is not implemented.
```

## Connection contracts

| Producer | Contract/output | Consumer | Risk if changed |
|---|---|---|---|
| Raw loader | normalized tag names and timestamp order | every notebook | silent semantic or time leakage |
| State-aware analysis | `baseline_stats.csv` | calibration profile builder | wrong profile key or contaminated baseline |
| Calibration notebook | profile JSON + relative features | shared Isolation Forest and future server | feature order/version mismatch |
| One-second notebook | event summary and response features | hybrid event models | window leakage or unsupported state inference |
| MX-080 Module 6 forensic producer | exact-second pressure/message snapshots + four figures + water-keyword audit | technician review and future provisional incident table | mistaking event alignment/keyword timing for causal proof, or joining ambiguous duplicate seconds |
| Phase 7 hp180 benchmark | `max(0,180-Hp_2nd)/10`, local-relative features, nested split and versioned registry | shadow replay | mixing the deprecated 200-psi model/threshold with current feature semantics |
| Phase 7 shadow replay | portable model + locked hp180 manifest + scores/episodes/failure tests | server/MySQL staging and Web App | selecting from outer/incident data, silent fallback, non-idempotent alerts or activation without rollback |
| FastAPI application | verified artifacts in demo or analytics MySQL in live mode | React/Lovable-compatible Dashboard | silent demo fallback, missing auth, schema mismatch or unsupported diagnostic claims |
| Technician confirmation API/UI | incident graph + new-alert boundary + declared `DATETIME(6)` timezone + binary status + technician ID | append-only `PENDING_QA` label store | historical-label leakage, accepting an alert before the boundary, unverified clock semantics or using raw notes as classes |
| Candidate-only scheduler | 5-minute shadow command + daily profile + weekly model commands | automation audit and approval packages | accidental activation, overlapping jobs or commands without QA/versioning |
| Model comparison | model bundle and threshold evidence | future shadow server | treating flag rate as accuracy |
| Phase 06 Auto-bootstrap candidate builder | versioned candidate package + lifecycle/reason codes | future registry and server shadow validator | service-epoch ambiguity, overwrite risk before immutable registry, or silent activation |
| Technician confirmation loop, planned | prospective binary status + raw audit note | future supervised binary anomaly model | label leakage, hindsight bias or treating similar future patterns as confirmed |
| Built-in calibration worker | raw source MySQL (read-only) → duplicate-key gate → state-qualified minute windows → two-pass robust candidate + 3-day shadow points | immutable calibration registry and Review UI | unverified mapping/timezone, mixed state/service data, retrying same reviewed snapshot or auto-approval |
| Calibration Review UI/API | candidate batch/profile/3-day green-red deviation chart + human decision | active-profile pointer or rejected batch audit | treating colours as diagnosis, activating partial batches or silently replacing rollback target |
| HPO runner, planned | inner-validation study + search manifest | model-selection report | tuning on outer test or non-reproducible search |
| Threshold calibrator, planned | threshold/persistence version | shadow scorer | treating model contamination as fault prevalence |
| QA Loop, required | signed data/model/evidence/presentation/production checks | phase gate and release review | advancing a phase from a good average metric while a critical check fails |

`README_System.md` now also owns the evidence hierarchy, result-level vocabulary, Auto-bootstrap lifecycle and production change-control contract. Implementations must reference a README revision/date in generated profile and model metadata.

## Planned production modules

```text
ingest/
  schema validation, units, timestamp, tag mapping
state/
  Compressor Status / Status_n / SV segmentation; Busy=1 manual-service exclusion flags
features/
  minute features, robust residuals, one-second ring-buffer response
profiles/
  candidate/frozen profile store and service epochs
models/
  shallow anomaly detector, drift detector, future supervised/sequence challengers
bootstrap/
  readiness, contamination screening, candidate creation, shadow evidence
scoring/
  evidence fusion, persistence and alert-budget policy
api/
  score response and explanation contract
monitoring/
  data drift, feature drift, model/profile version and server health
qa/
  system, data, model, evidence, presentation, production and governance gates
tests/
  unit, replay, leakage, cross-machine and rollback tests
```


## Update checklist

- [ ] New input/tag reflected in `README_System.md`
- [ ] New feature has formula, unit, availability time and version
- [ ] New output identifies producer and consumer
- [ ] Changed notebook updates its downstream paths
- [ ] Model bundle records feature/profile versions
- [ ] Auto-bootstrap transition and rollback path remain visible
- [ ] HPO artifact records outer/inner/calibration split, search space, budget, seed and selected parameters
- [ ] Simple/statistical baseline and complex challenger use the same eligible windows and outer tests
- [ ] QA Loop records pass/fail/caveat without creating a separate duplicate-detection subsystem
- [ ] `SOT.md` and `Roadmap.md` reflect implementation status

## Change log

- 2026-09-25 — Reviewed the explanatory rationale addition; the existing source → candidate → review → rule-only scoring map and its blocked raw-row edge are unchanged.

- 2026-09-25 — Mapped the owner-selected rule-only Active-Profile path and marked the ARX loader as an offline branch; documented the raw-row/source-connection parity gap without changing an execution edge.

- 2026-09-25 — Mapped the isolated rule/ARX matched-replay branch and its aggregate-versus-local row-level artifact boundary; no edge to the production worker or Active Profile was added.

- 2026-09-24 — Mapped the past-only residual QA branch and separated aggregate Git evidence from its locally regenerated second-level event ledger.

- 2026-09-24 — Added the separate v2 train-only Valve-quantization branch and matched retrospective comparator; no live-scoring or approval edge was added.

- 2026-09-24 — Mapped the read-only second-level Valve audit branch and its derived CSV/JSON/figure outputs; no scoring or Active Profile edge was added.

- 2026-09-24 — Added the isolated Cold candidate producer, model contract, version-checked loader and QA-artifact lineage; the production Active-Profile → model edge remains unimplemented.

- 2026-09-24 — Mapped the isolated ARX bundle loader and the still-separate, truthfully labeled robust-z live scorer.

- 2026-09-16 — Added Notebook 00B lineage from the committed split/baseline/correlation/benchmark/profile artefacts through an executed notebook, HTML preview and slide-ready figures. This is a read-only presentation producer and does not alter the model/profile registry.
- 2026-09-15 — Added MX057 historical backtest lineage and a duplicate-key/reviewed-batch retry guard to the calibration worker; no live source or profile was changed.
- 2026-09-15 — Added the deployed-code map for automatic candidate calibration, 3-day shadow evidence and human-gated profile promotion. No database producer or active profile exists yet.
- 2026-09-15 — Added the explicit alert-timestamp timezone gate to the prospective-confirmation path; writes fail closed without it.
- 2026-09-15 — Replaced the cause-taxonomy label path with the prospective binary confirmation path and its dedicated migration/API. No database producer or live label exists yet.

- 2026-09-15 — Added the improved system architecture map: data/state gates, four evidence engines, persistence, Server shadow and technician feedback. No producer output or trained artifact exists yet.

- 2026-09-14 — Updated the curated handoff repository endpoint to `Bookkapp/CompressorML_and_AutomaticCalibration`; data/code lineage and production boundaries are unchanged.

- 2026-09-14 — Added the implemented Web App/API/scheduler and Phase 8 MySQL migration lineage. Demo QA is complete; live data, authentication, label-review and activation connections remain deliberately open.

- 2026-09-14 — Added the planned `10.195.17.73` append-only analytics-database documentation path; no producer/consumer service or database connection is claimed as implemented.

- 2026-09-14 — Added the planned controlled technician-label/cause-probability path. It documents the approved UI contract only; no label store, Health Score or classifier producer exists yet.

- 2026-09-11 — Connected the curated deployment lineage to the former private handoff repository.

- 2026-09-11 — Added the curated GitHub-to-Server handoff path and retained only current profile/model/parity artifacts required by the deployment lineage.

- 2026-09-11 — Clarified the local-profile-to-Fleet-model path and marked Health Score/classification as downstream planned consumers, not current validated outputs.

- 2026-09-11 — Added the logical deployment-flow document to the Phase 7 lineage; planned components remain planned and live Server/MySQL acceptance remains open.

- 2026-09-10 — Versioned the 180–230 psi field-reference migration through benchmark v2, MX-080 forensic v2 and shadow replay v2; historical 200-psi artifacts remain comparison-only.

- 2026-09-10 — Added Phase 7 shadow-replay and deployment lineage, including portable model migration, locked versions/checksum, append-only MySQL schema and safe failure outputs.

- 2026-09-10 — Added MX-080 Module 6 forensic lineage from Desktop Pressure/MessageLogs through Notebook 07D and versioned evidence outputs; Temperature remains unjoined pending channel mapping.


- 2026-09-10 — Regenerated external intake v2 lineage with `hp2_below_180_pct`; source counts, overlap equality and the EDA-only/no-training boundary are unchanged.

- 2026-09-10 — Pointed the external-data lineage at executed intake v2, including independent partition QA and EDA-only quality-minute output.

- 2026-09-08 — Added Navigator, Phase 06 Auto-bootstrap producer, candidate/profile/shadow artifacts and notebook QA outputs to the implemented lineage; immutable production registry remains planned
- 2026-09-08 — Synced Handoff documentation into the evidence lineage; no implemented producer/consumer path changed
- 2026-09-08 — Created initial repository map, data lineage and planned production component graph
- 2026-09-08 — Added README revision dependency to model/profile metadata contract
- 2026-09-08 — Reviewed after Chat handoff creation; no code or data-lineage change required
- 2026-09-08 — Added research-to-contract lineage, HPO/threshold connection contracts and the seven-part QA Loop; no new production module or data artifact is claimed as implemented
- 2026-09-08 — Clarified that “Loop Check” means repeated QA review, not a duplicate-data subsystem

- 2026-09-24 — Added `docs/V1_ARCHITECTURE_AND_DEPLOYMENT.md` as the cross-repository map for source telemetry, calibration registry, score/episode outputs, Dashboard metadata and Server topology. Existing code paths are unchanged.
# Local persistence/transport edge — 2026-10-01

`notebooks/support/mysql_incremental_rehearsal.py` → `qualified_stream.py` + `qualified_scoring.py` → `qualified_persistence.py` (atomic rehearsal-only MySQL state/evidence/receipt/cursor) → `main.py::rehearsal_points` → `components/RehearsalDashboard.tsx` via `?rehearsal=<run_id>`. This is not wired into the live worker, profile promotion or PM alerts. `test_qualified_persistence.py` covers rollback, long-lived receipts and API gating. See `deployment/LOCAL_MYSQL_INCREMENTAL_QA.md`.
# Three-machine offline analysis edge — 1 Oct 2026

Downloads five ZIP parts + nested MX080 July → `notebooks/support/october_three_machine_calibration.py` → ignored local minute/event/trajectory caches + hashes + quality/local baseline/correlation/past-fit/future-shadow tables → `october_calibration_presentation.py` → executed Notebook `08K_Three_Machine_Raw_Second_AutoCalibration_Review.ipynb` and local figures. Static is inventory-only, not parsed/analysed. No edge to MySQL registry/Active pointer/PM bridge/worker/Server. Numerical gates/fit parity tests: `notebooks/support/test_october_three_machine_calibration.py`. Method and next-version proposal: `deployment/THREE_MACHINE_AUTOCALIBRATION_REVIEW.md`.
