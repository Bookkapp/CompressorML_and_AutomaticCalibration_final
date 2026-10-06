> **Final private Server release — 6 Oct 2026:** On “Set up ระบบนี้ให้หน่อย”, read `HANDOFF_SERVER.md` first. Owner explicitly authorized real deploy secrets/config in this PRIVATE `_final` repository. This supersedes older secret-exclusion instructions for this release. Server .69 Dashboard / .73 Operation; no Server installation or Profile approval has occurred in packaging.

# 6 Oct — Calibration Fleet Stable

**6 Oct — separate technician queue UI removed at owner request:** Removed menu/page, confirmation drawer/form and 10-second incident polling plus unused frontend calls/styles. Four workflow menus remain. TypeScript/build and 12 API regressions pass; actual web shows zero queue buttons/no console errors. Existing historical records/server compatibility and manual Profile/Engineer gates remain. Evidence: deployment/TECHNICIAN_QUEUE_REMOVAL_20261006.md. No source/Profile/Active or Server change.


**6 Oct — latest owner instruction: insert Normal source data for 7–9 Oct:** MX058/M1 now has 86,400 unique raw seconds per requested day (259,200 rows), Run/On/Busy0/SVOff. Frozen Reference probe: 4,320 minutes, zero flags. Profile/Active registries unchanged. Future dates are explicitly requested fixtures; the real clock gate still blocks their current-day validation. Receipt: notebooks/outputs/normal_days_7_8_9_20261006/receipt.json. No new UI or approval action. Earlier elapsed-only checkpoint below is historical.

**6 Oct — owner correction: standard manual workflow restored; elapsed Normal SQL fixture only:** Removed the added Mock UI/API/feature flag/approval exception/virtual clock and the exact test Active/Profile. Backed up and removed259,260 future rows; archived obsolete Mock inspection. MX058/M1 now has21,540 elapsed Normal fixture seconds (08:05–14:03:59 today; Run/On/Busy0/SVOff), with synthetic provenance in the batch ledger and no generated M2–M8 values. Original207/46legacy and110/0Context registry hashes restored exactly;567import receipts unchanged.27focused regressions/TypeScript/Vitebuild pass. Standard manual web restored and inspection/approval left to owner. Reference frozen today08:04:35 means real prospective days remain0/3, first eligible7Oct; no contracts/Engineer/scope invented. Source/worker/Server limitations and reversible backups: `deployment/NORMAL_MANUAL_FIXTURE_20261006.md`. Earlier source-marker/trial checkpoints are historical.

**6 Oct — owner-requested Normal values inserted into the current local source table:** MX058/M1 only,15,420 second rows (08:05–12:21:59 today), marked `Status=MOCK_NORMAL`; numerical probe257/257 within frozen Reference. Exact batch receipt is durable in `ht9046mx_local_mock_batch`; no overwrite/future clock or Mock UI. Actual web inspection/day graphs succeed;254 inspected minutes under the existing open-day cutoff. Mock stays visible but cannot vote, fit Reference or provide real Active evidence; mixed validation receipts carry Mock/nonapproval provenance. Closed days remain0/3; original contracts/ON Reference/real future gates stay open. Profile/Active hashes unchanged.16 initial targeted tests plus12 final provenance/followup regressions and web build pass. Evidence: `deployment/NORMAL_TABLE_MOCK_UAT_20261006.md`. Earlier no-source-write checkpoints below are historical.

**6 Oct — post-freeze progress and interim inspection delivered (no Mock UI):** Calibration step 3 shows frozen time/source latest, received closed days versus inspected supported days, daily categories/missingness and saved day/Raw evidence. Same-day inspection begins at the first full minute after review; it never counts as an approval day. Bounded 4-day inventory/shared 30s reads, durable coalesced jobs, immutable 5-minute partial snapshots and future-clock guards preserve frozen Profiles and the real 3-day prospective gate. Full 256 tests before final refinements plus 9 final followup tests/TypeScript/Vite build pass; actual 017/058 two-tab QA/no Mock/no errors and 10 clients/120 metadata GETs all succeed (warm p95 68.54 ms, cold capture/scoring/render excluded). MX058 source 5 Oct 14:45 precedes freeze 6 Oct 08:04, so 0/3 and no actual post-freeze inspection yet. Legacy 207 Profiles/46 Active, Context 110 Profiles/0 Active and 567 import receipts unchanged in read-only QA. Actual future/Engineer/contracts/Active/Server acceptance remains open. Evidence: `deployment/CONTEXT_FOLLOWUP_PROGRESS_UAT_20261006.md`. Earlier checkpoints below are historical.

Current step3: **ความคืบหน้าหลังตรึง Reference** → source/freeze timestamps → received/evaluable day counts → daily results → saved day graph/Raw. **ตรวจข้อมูลที่มีแล้ว** accepts real same-day data afterfreeze without waiting3days; **ตรวจข้อมูลใหม่ครบ3วัน** remains the separate approval-evidence action. Preserve graph space, label interim/nonapproval and disabled missing-data actions. No Mock UI. ActualMX0580/3 screenshot in `notebooks/outputs/context_followup_20261006/mx058-progress.png`.

**6 Oct — original items 3–6 implemented and locally tested:** Added reference-only Fleet Transition catalog, independent event-response admission, frozen-review source/version guard and actual source graphs; saved real Shadow report with flagged episodes → Raw; pinned Fleet Shadow producer in the common Event/checkpoint transaction; durable isolated retraining and Fleet Models compare/Shadow approval/rollback. Six-machine manual web training completed in203s; actual4machines×8modules SQL restart/retry rehearsal and120/120preparedGETs/10clients passed (warm p95173ms).248full API tests before final refinements plus25final targeted tests/TypeScript/build; executedNotebook14. All43steady model values and207legacy/46Active snapshots preserved,ContextActive0.144Transition groups/512Reference events/114holdout; zero donor groups pass independent screening (1929/2356minutes outside), so unsafe transfer remains unavailable. Normal/configuration/untouchedfuture and actualServer acceptance remain open. Owner requested Markdown setup handoff for10.195.17.73, with trigger “Set up ระบบนี้ให้หน่อย”. See `deployment/FLEET_WORKFLOW_UAT_20261006.md` and `deployment/SERVER_WORKER_HANDOFF_20261006.md`. Older checkpoints below are historical.


**Current UI, later owner correction on6Oct:** Removed the entire Mock action/result/day selector/charts from step3 and removed its frontend component/API wrapper/type/CSS. Frozen real-data validation/readiness/Approve now follow the step description directly. Actual MX058 saved review remained unchanged; zeroMockbuttons/noerrors and finalbuild pass. The Mock UI description immediately below is historical. Screenshot: `notebooks/outputs/mx058_normal_mock_20261006/mx058-mock-removed.png`.

Step 3 now offers an explicit **จำลองข้อมูล Normal 3 วัน (Mock)** for a saved reviewed Profile. Label virtual dates, machine/module/SV/frozen version and all results as MOCK; show missing included-state Reference separately. Three-day selector and fixed280px pressure/temperature panels retain their view during day fetch. Actual MX058/M1 shows4,320simulatedminutes/Flag0%; real validation/Active remain unchanged. Fleet Stable text explains that Transition events/statistics do not yet fill Local Transition envelopes. Evidence: `deployment/MX058_NORMAL_MOCK_UAT_20261006.md`.

Fleet Reference now opens the frozen installed model first; older Fit-day/transition experiments are collapsed. Select a machine in the existing page, then M1–M8/date and open the actual minute graph. Display model version and separate Reference/calibration periods; load no graphs before the button. Graph cache pins bundle/machine/module/day and rejects changed versions. A latest-version button refreshes the review.

Within Reference is not Healthy; Review is not a cause diagnosis. Explain unsupported controls separately from an insufficient Local profile. Acquisition-suspect/incomplete minutes create chart gaps while originals remain stored. Four fixed result badges reserve space while loading; graphcards remain358px and omit Loading chart data. Normal/post-intervention acceptance is still a reviewed workflow. Actual 080/M6,041/M3,081/M8 three-tab isolation, M7 insufficiency, invaliddate disabled and missingJuly1 graceful-empty tested.

# HT9046MX Analysis and Monitoring UX

**5 Oct — Fleet Reference / selective transfer delivered:** Calibration machine first→Fleet Reference→M1–M8→Local Fit1/3/7/14days→independent source machine/date→explicit graph. Defaultcollapsed transition/method details; numerical sharing is marked waiting for review. Previous-module numbers are hidden during request changes while graph cards reserve space. Date input handles input/change; out-of-range graph action disabled, missing committed days shows clear empty-data message; no“Loading chart data”. Real three-tab041/058/081 and080/M6graph checks show4pressure/2temperature curves,358px cards, no horizontal overflow. Source080/MX080 aliases now appear once, without source-row rewriting. This UI presents unreviewed minute evidence, not Raw seconds or Normal certification. Evidence: `deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md`.

**5 Oct — Conditional Calibration and EventHistory UI implemented:** Machine-first → all8 preparation → module/day → minute or bounded Raw graphs → Reference-only dates/exclusions → immutable reviewed regimes/templates → prospective check/Active blockers. Fixed280px panels remain during loading; memoized charts do not redraw on every progress poll. Category-specific counts and actual feature values/bands use readable Thai; original Candidate counts are labelled separately from reviewed graph assessments. Drafts survive reload; old graphs remain while inputs are dirty; stale-tab save rejects and refresh recovers. Raw invalid-range/same-range retry and event/source mapping failures explain the next action. Common history filters reset old details/graphs and retain source time/before-after; Alerts/Maintenance/Logs layouts are not changed. Actual017/024all16 minuteviews, two/three-tab review and exactSVRaw tested. Live operational event capture and real eligible Active/rollback remain open. Evidence/screenshots: `deployment/COMPRESSOR_CONTEXT_PROFILE_UAT_20261005.md`.

**4 Oct — Physical/control policy and manual regression:** New qualified Candidates use physical P/T scores, nonvoting Valve context and strict Q99.5 `>` comparisons; legacy stored nine-feature `>=` semantics remain. Current-cutoff Reference alternatives are automatic, older stable regimes require review. Reference-only recovery evidence opens Raw before/after SV/unknown boundaries and never suppresses flags. Sixteen actual-cache contexts/14 scorer comparisons have zero differences; known057/M1 and080/M6 case detections retained. Actual GUI checked all 16 modules and completed MX017/M1 exclusion → Preview → Build (SHADOW_VALIDATION; four source prerequisites still block approval). Backend174 tests/build passed; cached Raw40/40 GETs, p95≈539ms. MX024 cold preparation11m33s; reviewer editing after reload remains an unresolved browser UAT path. Active hash unchanged. Manual GUI UAT and limitations: `deployment/PHYSICAL_CONTROL_CALIBRATION_UAT_20261004.md`. Four verified source contracts, prospective healthy/recovery evidence and target-Server Active-success remain open. Older checkpoints below are historical.


**4 Oct — Calibration evidence and SV review:** Readable per-check values/actions, contributor intervals → minute/Raw charts, all-state bounded Raw GET, and bounded past-only per-module Reference proposal implemented. Owner-confirmed psi recorded; pressure basis + state/controller/service versions remain explicit prerequisites. Actual017/024each7Candidates/M7insufficient; no passing stable proposal in current search. 167 API tests plus saved-policy regression/build; exact four-context selector parity, actual browser interval/Raw/invalid-range/M7 and40GET/10client QA. SV study28files/2,385,588rows/196raw-minute checks finds material pressure/thermal differences: retainSVOff Cold gate, preserveSVOn Raw. Active46hash unchanged; no Server/push. Cold preparation remains≈10–12min on local machine; graph reads are bounded/on demand. Evidence: `deployment/CALIBRATION_EVIDENCE_AND_SV_REVIEW_20261004.md`.

**3 Oct Calibration flow:** Compact machine select → reviewer → prepare all8 → module cards with coverage, status/reasons → saved graph / optional Manual dates and exclusions → Candidate review → human Active approval if eligible. Extended source-day inventory starts only when expanded. Graphs stay during draft edits/re-preview and unreviewed edits disable Build. Closed-day graph freshness is disclosed as≤1hour; Manual Build checks current raw evidence. Background jobs survive tab closure and automatic expired leases can resume. Missing M7 does not hide other results. Screens/QA/limitations: `deployment/AUTOMATIC_CALIBRATION_UAT_20261003.md`.

**2 Oct — Manual Reference review repair:** Editing an exclusion keeps the old chart and selected minute day visible; label old counts clearly and disable Build until a new Preview completes. Validate complete/nonoverlapping Reference-only intervals with readable messages. Reopen the current reviewer's latest12machine/module jobs without recomputing. Minute loading/error/empty placeholders keep230px chart space; no qualified minutes means unavailable Quarantine, not0%. Approval explains missing verification/exceeded gates, uses refreshed status and resets decisions across contexts. Availability shows its check time, stays cached30minutes/fresh5minutes, and background refresh does not block inventory-backed Preview. Wrap Matrix status/parameter/profile text to prevent overflow. Actual16module Preview/graph UAT and14Candidate reviews completed; Active-success remains blocked. Evidence: `deployment/MANUAL_CALIBRATION_UAT_20261002.md`.

**2 Oct — imported history visible:** MainOperation5176 now showsMX0177,773,449rows/latest1Oct15:55 andMX0247,801,896rows/latest15:45, both `Needs Calib`. This means data intake is complete, not that reference is healthy or Active. Latest1Octispartial; defaultclosed Shadow28–30Sep andReference31Aug–27Sep require separateobserved-secondPreview/review. NoautoPreview/Build/Approve oruserformoverwrite. Inventory93dayscan take~120s; do notpresentit as instant/productionSLA. UIcountproof and limitations: `deployment/DOWNLOADS_HISTORY_IMPORT_20261002.md`.

**2 Oct — storage error recovery:** Reference UI distinguishes missing job table (apply analytics migration), incompatible columns (review additive schema repair; CREATE IF NOT EXISTS does not fix old columns), temporary lock contention (retry/reconnect same job) and connection/permission errors. A technical Preview READY is not approval readiness; insufficient coverage remains visible/Build blocked. No automatic rebuild/Active promotion. Normal local storage/poll repair QA: `deployment/REFERENCE_STORAGE_REPAIR_20261002.md`.

**2 Oct — Reference availability v2:** Before Preview show latest machine row, latest module sensor-complete date, data age/TZ, Reference dates/counts and Shadow dates/counts. Distinguish no-log dates from populated dates with incomplete sensors and from final qualified minutes. Coverage-supported suggestions require a clear “use suggested period” action; preserve actual latest timestamp when backtracking. Show editable exclusive Shadow cutoff/reason; changing inputs clears old preview. Block Build for insufficient Shadow even if Reference suffices; pending v1 results explain re-preview. Main Operation5176/MX080/M6 inspected; source inventory not healthy/Active readiness. Details: `deployment/REFERENCE_AVAILABILITY_V2.md`.

**2 Oct source-backed experiment:** Development-only SQL page5175 exposes host/schema/table, isolated-output schema, source period and known mock IDs. Select machine/module/day; separate HP/LP/temperature/Valve charts and expandable raw rows/Gate reasons. State chart grain and unknown units; preserve missing minutes. Actual SQL-grain insufficiency is not Normal and Preview READY is not approvable. Reuse ReferenceReview for experiments; no operational technician queue added. Desktop four-chart/selector/Preview checks passed; production UI unchanged. Evidence: `deployment/LOCAL_MYSQL_REFERENCE_EXPERIMENT.md`.

## Calibration Reference review — 2 October 2026

Use the existing Operation UI for Profile administration; technicians continue using the Compressor Dashboard for work/reporting. Present four steps: **เลือกช่วงข้อมูล → ทบทวนกราฟ → สร้าง Candidate + Shadow → ตรวจผลและอนุมัติ**. Machine and Module must remain visible. Default dates can be automatic, but actual Reference/Shadow boundaries, source timezone and exclusive end are shown before confirmation. Reference confirmation and Active approval are distinct actions; a prior Active badge is not attached to a new Candidate.

Overview graphs show hourly median with actual min–max of qualified minute means, then offer one-day 1m detail. Hp and Lp use separate aligned panels, not a common scale. Gray means excluded/unused for fit; purple means Shadow, neither is a fault/healthy label. Null gaps stay gaps. Unverified pressure units do not display psi or a green 180–230 check; Valve is count, TempHi compressor and TempLo discharge pipe. Correlation tooltip describes direction, not physical cause; missing r is not zero.

Keep counts/retained coverage and next action above the technical details. Busy actions are disabled with progress; insufficient Reference explains required days/minutes after exclusions and quarantine. Back/edit clears stale preview; refresh restores the durable job when browser storage is available. A reviewed note and explicit checkbox precede Build. Failures explain whether to retry, reconnect or re-review; Candidate creation cannot activate a profile. Minimum 42px controls, visible focus, readable wrapping and narrow single-column forms; detailed tables scroll inside their panel. Verified wide and 390px layouts on the actual Operation page against isolated archived-data QA; fixed parent grid/header/Approval overflow, with pageWidth equal to clientWidth. Chart titles retain machine/module and minute axes use familiar 00/06/12/18-hour labels. Full authenticated production UAT remains a separate check. Details: `deployment/REFERENCE_REVIEW_WORKFLOW.md`.

**Notebook08M presentation — 1 Oct:** Historical-shadow comparison now shows actual source cutoff per machine, nominal-vs-observed fit coverage, 4-method reference support, matched burden paired with all-context unsupported counts, phase attribution and raw-second control/decision strips. Controls are active-state bands; absent supported segment says `Not evaluated`, not a blank normal-looking row. Steady/flat is not a healthy label; unknown onset and 18startsfrom2days limitations remain visible. New panels are notebook/local artifacts only, no Dashboard/OperationUI runtime change. Outcome and next reference-selection review UX: `deployment/HISTORICAL_SHADOW_REFERENCE_PHASE_EXPERIMENT_20261001.md`.

**Notebook 08L — 1 Oct:** Local model-selection presentation adds source/reference readiness, baseline/within-day correlations, same-row burden, known-case comparison and actual-second/control-state case panels. Separate Hp2/Lp2 scales, panel-specific stored-z contributors and named red features; explicitly label ML abstention on MX080, not zero/normal. Raw gaps remain gaps; future/Active target flow is distinct from the offline experiment. Eight PNG/SVG figures inspected; no Dashboard UI/runtime change. Evidence: `deployment/LOCAL_PROFILE_MODEL_SELECTION_20261001.md`.

**Control-event view proposal — 1 Oct (not implemented):** Retain observed-second ChangeValve/Homing/startup/Busy/SV state strips and before/during/after trajectories. Manual/unknown contexts show control event/not assessed, not green Normal; keep frozen-level reference and abnormal post-event plateau visible. Contributor red remains primary-only; proposed response envelopes/ARX/DPCA are labelled research/shadow. Details: `research/HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md`. No UI/runtime changed in this research checkpoint.

**Three-machine presentation — 1 Oct:** Notebook 08K separates source inventory, supported local baseline distributions/daily trends, conditional correlations, actual-second transition review, paired lookback shadow burden and registered case evidence. Qualified is not healthy; M7/unknown onset/gaps are explicit, empirical bands are not confidence intervals, and correlation is not cause. Numerical-fit diagnostics do not show an approved Active lifecycle. Static excluded. Existing Dashboard presentation remains unchanged.

**1 Oct contributor review:** Daily review lives in Dashboard: Alert/Work/Log → bounded five-panel graph. Red sensor panels require their own stored feature z meeting >= the packet threshold during global persistence; global result is on the score panel. Display names/signed z/baseline in tooltip/table and an accessible contributor summary above each chart. Narrow layouts hide overlapping in-band labels, not attribution/evidence. Yellow data review, blue report periods and null gaps retain separate meaning. Contributor is not equipment cause, per-feature persistence or Health probability. Multi-start/settling validation remains proposed in `deployment/STARTUP_SETTLING_VALIDATION_PLAN.md`.


**Last updated:** 2026-10-02
**Audience:** Project owner, refrigeration technician, data/ML reviewer and operations

## Daily work vs Profile administration (2026-10-01)

Technicians use the Compressor Dashboard for Alerts → Assigned Work → Service Log. Admin can create a work order with Description and a reported occurrence interval when there is no Alert. Show UNKNOWN onset honestly and explicit Asia/Bangkok clock; keep reported onset, Alert timestamp, work creation and service recording times distinct. Original report expands in Service Logs from a frozen snapshot. OPEN/RECOVERING/RECOVERED/UNKNOWN Episode state is independent of Work Order status; DONE is not detector recovery or a cause label.

Operation is for candidate/3-day-shadow/Active approval and later recalibration, not a duplicate manual-incident entry screen. Its local rehearsal view displays Episode identity, versions, onset/availability, recovery and raw JSON next to the five graphs. This QA view was inspected on localhost; daily Dashboard workflow UAT and integrated evidence-graph links/highlights remain pending. Missing context stays blank/UNKNOWN, not green Normal. See `deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md`.

**MX080 replay figure QA (2026-09-25):** The read-only historical Active-profile figures place `Hp_2nd` and max absolute robust-z on separate axes, print the one-minute grain and Asia/Bangkok assumption, and leave unqualified/missing minutes blank. The vertical 7 Sep marker is an observed-second pressure transition, not a verified fault onset. The 5 Sep temperature flags must remain visible in the overview; hiding them would overstate specificity. This is a forensic report, not the future live five-minute Dashboard view. Evidence: `notebooks/outputs/mx080_active_profile_replay_v1/`.


**Planned temporal-evidence view (re-scoped 2026-09-30; not implemented):** After the selected one-minute/profile path is integrated, Module Detail may show signed robust z, EWMA and CUSUM beside the raw sensor timeline, each with its own unit/axis and versioned threshold. Label the lane `SHADOW` until separately reviewed; a temporal-only episode is not a fault, does not change primary Health/Condition and does not enter the current Technician confirmation queue automatically. Use `Sustained downward deviation`, not `Leak`, cause percentage or failure probability. The earlier five-minute design in `deployment/EWMA_CUSUM_TEMPORAL_DRIFT_PLAN.md` is historical and must be re-validated for one-minute windows.


**Past-only QA figure rule (2026-09-24):** Present daily Self review *share* as separate bars per machine–module with qualified-window denominator, leaving missing days blank. A manual-status day is a distinct tick, not a red fault annotation or a service/refill label. Rank dominant features by count of review windows, not by causal importance. State source timezone uncertainty and that the existing `|z|>8` review rule is not a fault probability.




## UX principle

ผลลัพธ์ต้องช่วยให้ผู้ใช้ตอบได้ตามลำดับว่า “ข้อมูลเชื่อถือได้หรือไม่ → เครื่องกำลังอยู่ใน state ใด → อะไรเปลี่ยนไปจากค่าปกติของเครื่องนี้ → เปลี่ยนนานแค่ไหน → มีคำอธิบายอื่นหรือไม่ → ควรตรวจอะไรต่อ” โดยไม่บังคับให้ผู้ใช้ตีความ anomaly score เพียงตัวเดียว

## Required presentation flow


External intake companion (07B) adds a date-coverage strip, novel/overlap row bars,
daily Hp_2nd reference heatmap with day counts, all-module time plots and per-SV
Valve/Lp_2nd correlation matrices. Quality/reference values must be labelled
as historical evidence, not approved healthy baselines. Missing days remain visible.


Phase 7 shadow replay adds two decision views: alerts per machine-day plus daily alert count, and an MX-080 pressure/score timeline. Raw deviation points and persistent-alert openings use different marks; any pre-transition raw flag must be stated so the reader cannot mistake descriptive timing for validated lead time.

1. Coverage and data quality
2. Current operating-state composition
3. Baseline by machine/module/SV
4. Deviation and drift over time
5. One-second event response where coverage permits
6. Model agreement/disagreement
7. Technician confirmation of whether a real equipment anomaly was found
8. Recommended human verification
9. Profile/model version and confidence limitations

## Alert card contract

ทุก alert ต้องแสดง:

| Field | Example |
|---|---|
| Machine / module | MX017 / Module 4 |
| State | Compressor ON, Busy normal, SV Off, Cold-qualified state |
| Data quality | Passed / Limited / Failed |
| Main observation | CP2 high-pressure baseline is persistently lower than its frozen profile |
| Comparison basis | Same machine, module, SV and qualified operating state |
| Evidence | Hp2 deficit, Lp2 residual, valve demand, response lag, persistence |
| Alternative explanations | load/recipe, CP1, facility water, sensor drift, restriction |
| Severity | Watch / Investigate / Urgent review |
| Condition status | Normal within this profile / Deviation detected / Not available |
| Technician feedback | `EQUIPMENT_ANOMALY`, `NO_EQUIPMENT_ANOMALY` or `UNRESOLVED`; no cause field |
| Required action | Maintenance verification; not an automatic diagnosis |
| Model/profile version | feature vX, model vY, profile epoch Z |
| Capability boundary | Screening/advisory only; diagnosis not confirmed |

## Health view contract

- คำนวณหลัง Data-quality และ Profile-readiness gate เท่านั้น; หากไม่ผ่านให้แสดง `Not available`
- แสดงองค์ประกอบของ condition index ได้แก่ profile confidence, deviation, persistence และ trend
- `Normal within this profile` หมายถึงผ่าน gate และไม่พบ persistent anomaly เมื่อเทียบ profile นี้เท่านั้น; ไม่ใช่คำรับรองว่าไม่มี fault ทุกชนิด
- Cause classification ระยะปัจจุบันแสดงได้เพียง evidence category พร้อม alternative explanations

## Prospective binary-confirmation contract

- เปิด form เฉพาะ alert ที่เกิดหลังวันเริ่ม Prospective Feedback ที่ Server กำหนด; historical alert แสดงได้แต่กดบันทึก label ไม่ได้
- Drawer แสดงกราฟและ context ของ alert ก่อน แล้วช่างเลือกเพียงพบ anomaly จริง, ไม่พบ anomaly จริง หรือยังยืนยันไม่ได้
- `UNRESOLVED` และ optional raw note เก็บเพื่อ audit เท่านั้น; ไม่เป็น target และไม่มี free-text cause class

## Visualization rules

- Use small multiples per machine/module instead of overlaying dozens of lines
- Show median and uncertainty band rather than mean alone
- Use consistent units and scales when comparisons are intended
- Shade `Hp_2nd = 180–230 psi` as a qualified field-reference band; use `<180 psi` only for low-side screening and show `>230 psi` as a separate high-side investigation region
- Use event-aligned plots with `t=0` at valve change and show sample count
- Separate SV On/Off and opening/closing; unsupported groups show “insufficient coverage”
- Use timelines for drift and service/refill epochs
- Titles should state the supported finding, not a causal diagnosis
- Place caveats adjacent to the chart they qualify
- Model-comparison chart ต้องแสดง simple/statistical baseline, validation level, machine count, event count และ search budget เดียวกัน
- Deep-model chart ต้องแสดง parameter count, latency/memory และ unsupported state coverage ไม่ใช่แสดง F1 เพียงค่าเดียว
- Shadow flag-rate chart ต้องแสดง denominator ต่อ profile และแยกค่า 0%/100% ที่มาจากกลุ่มตัวอย่างน้อยออกจากกลุ่มที่ผ่าน minimum coverage
- Uncertainty chart ที่มี outlier บีบสเกลต้องแสดงทั้งภาพเต็มและ focused view พร้อมบอกจำนวนจุดที่อยู่นอกช่วง focus
- Profile-stability curve ต้องแสดงจำนวน profile ที่เหลือในแต่ละ horizon และเตือนเมื่อ cohort ไม่ใช่ชุดเดิม
- A descriptive pressure reference line such as 300 psi must be labelled as a visual aid, not an alarm or safety threshold

## Web App UX contract

- Minimal blue/white layout with separate Fleet overview, synchronized machine timeline, Technician review queue and Automation status views
- Dashboard refresh and Model scoring must both show the locked 5-minute cadence and the cadence gate beside them
- Pressure, Temperature, Valve and Anomaly charts share one timeline; Pressure shades the qualified `Hp_2nd` 180–230 psi field-reference band
- Persistent anomaly uses a light highlight and adjacent wording that it is not a confirmed fault
- An alert may state `Anomaly detected` when a qualified Cold window has persistent local deviation or pressure-relationship shift; it is a data-derived anomaly decision. Technician feedback subsequently decides whether a real equipment anomaly was found, without requiring the system to name a cause.
- State context shows SV, Compressor `Status`, `Status_n`, Busy/manual-flag availability, Data quality and MessageLog availability without inventing missing values. `Busy=1` is shown as a manual/service-operation exclusion, not motor-run feedback.
- Demo mode must be visibly labelled and reject saves; live mode must reject alerts before the prospective-feedback boundary and fail closed until `ALERT_DATETIME_TIMEZONE` for `detected_at` is configured; Health Score remains `ยังไม่เปิดใช้`
- `Approve → Active Profile` is enabled only when the selected profile is `READY_FOR_APPROVAL`; Demo is visibly read-only. Reject requires a review note, preserves that profile key's active pointer and tells the user that the next candidate waits for new source days.

## Status language

Approved wording:

```text
Normal within this profile
Deviation detected
Persistent degradation pattern
R23 undercharge/leak suspect — requires maintenance verification
Common-cause condition suspected
Sensor/data-quality issue suspected
Insufficient data
Insufficient state coverage
Fleet-assisted provisional profile
Calibration drift — review required
Shadow screening only
Technician advisory — not a confirmed diagnosis
```


```text
Leak confirmed
Refrigerant definitely low
Machine is safe because Hp_2nd is inside or above 180–230 psi
High Hp_2nd proves a water-pipe or tank-level problem
Pressure is normal for every machine
The model proved the cause
```

## Notebook UX

Colab notebooks should use phase dividers, a concise “what this cell proves” note before each major chart, and a result/caveat block after it. The first screen must summarize data period, machines, coverage and claim limitations. The last screen must state what is ready, what is exploratory and what remains blocked. ให้เริ่มจาก `notebooks/00_HT9046MX_Notebook_Navigator_Colab.ipynb` และใช้เลข phase นำหน้าสำหรับ notebook ใหม่ที่ผูกกับ Roadmap โดยตรง

## Change log

- 2026-09-30 — Re-scoped the planned temporal-evidence view from the historical five-minute design to the selected one-minute feature grain; no UI code changed. The next graph QA should show qualified-minute denominators and separate deviation evidence from verified faults.

- 2026-09-25 — Reviewed the rule-only rationale register. Existing qualification, abstention, provenance and non-diagnostic graph wording remain unchanged; no UI behavior was changed.

- 2026-09-25 — Set the future operator wording to rule-only Active-Profile evidence and abstention for unsupported data; current raw-row runtime remains a blocker and no live UI behavior was changed.

- 2026-09-25 — Reviewed the new offline matched-lane presentation figures: the fleet chart separates rule flags from incremental ARX-only flags on a common denominator; the MX080/M6 timeline shades unqualified gaps and distinguishes raw threshold crossings from three-window episode openings. These are shadow evidence, not fault probability or a live UI change. See `notebooks/outputs/ht9046mx_rule_arx_matched_v1/README.md`.

- 2026-09-24 — Clarified daily profile QA figure semantics: qualified-window denominator, blank missing days, distinct manual-marker ticks and no causal/fault color claim.

- 2026-09-24 — Added the matched-denominator v1/v2 shadow-candidate chart rule and retrospective no-label caveat; no live UI changed.

- 2026-09-24 — Added observed-second forensic figure guidance with aligned separate CP2 pressure axes, explicit manual-state shading and source/grain caveats; no live Dashboard behavior changed.

- 2026-09-24 — Reviewed after offline Cold ARX candidate QA: no user-facing score, alert colour, Active Profile view or technician workflow changed because the candidate remains `REVIEW_REQUIRED`.

- 2026-09-16 — Expanded Notebook 00B for a non-specialist audience with a readable 12-development/7-external machine map, annotated Hp_2nd machine×module heatmap, Thai plain-language model summaries and equations tied to their operational meaning. Alert and cause-language guardrails are unchanged.
- 2026-09-15 — Clarified that the current UI may call a persistent qualified deviation/relationship shift `Anomaly detected`; this is distinct from root-cause diagnosis and from the later technician equipment-confirmation label.
- 2026-09-15 — Added the Calibration review view: 3-day green/red local-deviation chart, gate reasons and human-gated transactional approval. It does not expose Health Score, cause or percentage.
- 2026-09-15 — Added the visible/live contract that confirmation cannot be saved until the `DATETIME(6)` alert-time timezone is configured. This does not add a score, percentage or cause output.
- 2026-09-15 — Replaced the cause-selection drawer with prospective binary anomaly confirmation for new alerts only. Cause percentages and cause fields are out of scope for the current UI.

- 2026-09-15 — Reviewed after adopting the system-only Four-evidence architecture; no visualization, status-language or alert-card contract changed. Future views must distinguish self, dynamic, peer and temporal evidence without presenting them as fault probabilities.

- 2026-09-15 — Added and visually reviewed a single master-summary notebook using existing verified figures plus concise metric charts. It distinguishes offline evidence, planned Server behavior and live blockers; no user-facing alert semantics changed.

- 2026-09-14 — Implemented and visually reviewed the minimal blue/white Web App, synchronized graphs, incident review drawer and Automation page. The UI shows matched five-minute cadence and preserves all Health/Cause abstention wording.

- 2026-09-14 — Historical cause-probability presentation proposal; superseded on 2026-09-15 by prospective binary confirmation with no cause output or percentage.

- 2026-09-11 — Reviewed for the curated GitHub/Server handoff; no material presentation contract changed.

- 2026-09-11 — Added the gated Health-view contract: no score when data/profile evidence is insufficient, no failure-probability claim, and cause output remains an evidence category pending labels.

- 2026-09-11 — Added the beginner deployment-story order and required separation between documented/offline-ready components and live-production acceptance.


- 2026-09-10 — Added Phase 7 shadow-replay visuals and wording rules: alert burden by machine, raw-vs-persistent marks, pre-transition caveat and explicit production blockers.

- 2026-09-10 — Added the Notebook 07D incident-story contract for MX-080 Module 6: exact windows, separated event semantics, preserved gaps and explicit non-causal wording.

- 2026-09-10 — Added Notebook 07C event funnel, direction-balance bar and machine-module heatmap. Each visual keeps candidate, clean and insufficient coverage distinct.

- 2026-09-10 — Verified Notebook 07B figures after execution. EDA quality minutes are explicitly separate from approved baseline data and carry the 55–60 sample, ≤5-second-gap rule.

- 2026-09-08 — Added Notebook Navigator entry point and visual QA rules for denominators, shrinking cohorts and outlier-focused uncertainty views after Phase 06 review
- 2026-09-08 — Reviewed after Handoff v1.1 sync; presentation contract remains unchanged
- 2026-09-08 — Added capability-boundary wording and matched model/HPO/worst-machine/deep-cost visualization requirements from Thesis v1.1
- 2026-09-08 — Reviewed Loop Check clarification; QA affects review workflow but does not add a new user-facing duplicate view
- 2026-09-08 — Reviewed after `README_System.md` expansion; no material UX change required
- 2026-09-08 — Reviewed after `HANDOFF.md`; no material presentation or alert UX change required
# Local persistence QA view — 2026-10-01

Separate `?rehearsal=<run_id>` view reads only explicit local rehearsal runs. Five aligned time-series charts separate pressure, pressure differential, temperature, Valve and score/threshold ratio. Persistent windows are red; white is not a verified-normal claim. Missing/unqualified minutes remain gaps. Detail table shows source-window time separately from availability time and abstention reason. Offline candidate disclosure remains visible; this view has no approval or technician-label action. Desktop rendering inspected; narrow/mobile not yet verified. Evidence: `deployment/LOCAL_MYSQL_INCREMENTAL_QA.md`.
## 6 Oct — SV scope and saved Coverage

Calibration displays a saved M1–M8 matrix before individual evidence. Each OFF/ON cell distinguishes proposed coverage, recorded Reference, insufficient Reference and explicit exclusion. Frozen Fleet Shadow availability is a separate read-only matrix. Counts describe data coverage, not a Healthy certification.

Within Module review, choose at least one SV state. Exclusion requires a reason; Reference and transition selections outside that scope are disabled. Raw/event investigation remains available during excluded periods, labeled **ไม่ได้ประเมิน**. Returning included states are checked immediately. Dirty or hydrating drafts cannot validate/approve; reviewer/model-specific initialization prevents another actor's acceptance from becoming a draft. Save uses revision CAS, with readable stale-tab recovery.

Actual narrow447px screenshot QA corrected checkbox sizing/wrapping; no horizontal page overflow and no new Loading chart data label. Manual save/reload/Raw/stale-tab/017–024 isolation checked. Runbook: `deployment/CONTEXT_SCOPE_AND_COVERAGE_UAT_20261006.md`.
