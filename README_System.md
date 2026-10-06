> **Final private Server release — 6 Oct 2026:** On “Set up ระบบนี้ให้หน่อย”, read `HANDOFF_SERVER.md` first. Owner explicitly authorized real deploy secrets/config in this PRIVATE `_final` repository. This supersedes older secret-exclusion instructions for this release. Server .69 Dashboard / .73 Operation; no Server installation or Profile approval has occurred in packaging.

# HONTECH HT9046-MX — System README

**6 Oct — separate technician queue UI removed at owner request:** Removed menu/page, confirmation drawer/form and 10-second incident polling plus unused frontend calls/styles. Four workflow menus remain. TypeScript/build and 12 API regressions pass; actual web shows zero queue buttons/no console errors. Existing historical records/server compatibility and manual Profile/Engineer gates remain. Evidence: deployment/TECHNICIAN_QUEUE_REMOVAL_20261006.md. No source/Profile/Active or Server change.


**6 Oct — latest owner instruction: insert Normal source data for 7–9 Oct:** MX058/M1 now has 86,400 unique raw seconds per requested day (259,200 rows), Run/On/Busy0/SVOff. Frozen Reference probe: 4,320 minutes, zero flags. Profile/Active registries unchanged. Future dates are explicitly requested fixtures; the real clock gate still blocks their current-day validation. Receipt: notebooks/outputs/normal_days_7_8_9_20261006/receipt.json. No new UI or approval action. Earlier elapsed-only checkpoint below is historical.

**6 Oct — owner correction: standard manual workflow restored; elapsed Normal SQL fixture only:** Removed the added Mock UI/API/feature flag/approval exception/virtual clock and the exact test Active/Profile. Backed up and removed259,260 future rows; archived obsolete Mock inspection. MX058/M1 now has21,540 elapsed Normal fixture seconds (08:05–14:03:59 today; Run/On/Busy0/SVOff), with synthetic provenance in the batch ledger and no generated M2–M8 values. Original207/46legacy and110/0Context registry hashes restored exactly;567import receipts unchanged.27focused regressions/TypeScript/Vitebuild pass. Standard manual web restored and inspection/approval left to owner. Reference frozen today08:04:35 means real prospective days remain0/3, first eligible7Oct; no contracts/Engineer/scope invented. Source/worker/Server limitations and reversible backups: `deployment/NORMAL_MANUAL_FIXTURE_20261006.md`. Earlier source-marker/trial checkpoints are historical.

**6 Oct — owner-requested Normal values inserted into the current local source table:** MX058/M1 only,15,420 second rows (08:05–12:21:59 today), marked `Status=MOCK_NORMAL`; numerical probe257/257 within frozen Reference. Exact batch receipt is durable in `ht9046mx_local_mock_batch`; no overwrite/future clock or Mock UI. Actual web inspection/day graphs succeed;254 inspected minutes under the existing open-day cutoff. Mock stays visible but cannot vote, fit Reference or provide real Active evidence; mixed validation receipts carry Mock/nonapproval provenance. Closed days remain0/3; original contracts/ON Reference/real future gates stay open. Profile/Active hashes unchanged.16 initial targeted tests plus12 final provenance/followup regressions and web build pass. Evidence: `deployment/NORMAL_TABLE_MOCK_UAT_20261006.md`. Earlier no-source-write checkpoints below are historical.

**6 Oct — post-freeze progress and interim inspection delivered (no Mock UI):** Calibration step 3 shows frozen time/source latest, received closed days versus inspected supported days, daily categories/missingness and saved day/Raw evidence. Same-day inspection begins at the first full minute after review; it never counts as an approval day. Bounded 4-day inventory/shared 30s reads, durable coalesced jobs, immutable 5-minute partial snapshots and future-clock guards preserve frozen Profiles and the real 3-day prospective gate. Full 256 tests before final refinements plus 9 final followup tests/TypeScript/Vite build pass; actual 017/058 two-tab QA/no Mock/no errors and 10 clients/120 metadata GETs all succeed (warm p95 68.54 ms, cold capture/scoring/render excluded). MX058 source 5 Oct 14:45 precedes freeze 6 Oct 08:04, so 0/3 and no actual post-freeze inspection yet. Legacy 207 Profiles/46 Active, Context 110 Profiles/0 Active and 567 import receipts unchanged in read-only QA. Actual future/Engineer/contracts/Active/Server acceptance remains open. Evidence: `deployment/CONTEXT_FOLLOWUP_PROGRESS_UAT_20261006.md`. Earlier checkpoints below are historical.

**6 Oct — original items 3–6 implemented and locally tested:** Added reference-only Fleet Transition catalog, independent event-response admission, frozen-review source/version guard and actual source graphs; saved real Shadow report with flagged episodes → Raw; pinned Fleet Shadow producer in the common Event/checkpoint transaction; durable isolated retraining and Fleet Models compare/Shadow approval/rollback. Six-machine manual web training completed in203s; actual4machines×8modules SQL restart/retry rehearsal and120/120preparedGETs/10clients passed (warm p95173ms).248full API tests before final refinements plus25final targeted tests/TypeScript/build; executedNotebook14. All43steady model values and207legacy/46Active snapshots preserved,ContextActive0.144Transition groups/512Reference events/114holdout; zero donor groups pass independent screening (1929/2356minutes outside), so unsafe transfer remains unavailable. Normal/configuration/untouchedfuture and actualServer acceptance remain open. Owner requested Markdown setup handoff for10.195.17.73, with trigger “Set up ระบบนี้ให้หน่อย”. See `deployment/FLEET_WORKFLOW_UAT_20261006.md` and `deployment/SERVER_WORKER_HANDOFF_20261006.md`. Older checkpoints below are historical.


**6 Oct — Mock UI removed at owner request:** Calibration step 3 now contains real frozen-Reference validation and Active readiness only. Removed the Mock component/client/type/styles; actual MX058 UI shows zero Mock buttons, no browser errors, and final TypeScript/Vite build passes. Internal QA evidence/provenance guard is retained; no source/model/review/Active state was changed. Continue original items3–6: reviewed SV ON/Transition Reference for included states; real healthy/frozen-future validation; target Server worker/common Event History; Fleet Model Management. Missing intentionally excluded SV ON is not a prerequisite. See `deployment/MX058_NORMAL_MOCK_UAT_20261006.md` (removal checkpoint).

**6 Oct — MX058 frozen normal Mock:** Added an explicit synthetic three-day Steady test in Operation step 3 using saved MX058/M1 Profile `2a7990dd1d81…`; virtual7–9Oct/4,320minutes/Flag0%. Read-only mock receipts cannot satisfy prospective/Active approval. Included ON still has no accepted Reference; real contracts/future gates remain.20 targeted tests, TypeScript/build, all3day UI charts and48/48preparedGETs pass; frozen/legacy/import hashes and ContextActive0 unchanged. Fleet Stable v1 helps Steady/correlation shape; Transition statistics do not yet transfer approved response envelopes to Local automatically. Evidence: `deployment/MX058_NORMAL_MOCK_UAT_20261006.md`. Older entries are historical.

**6 Oct — explicit SV evaluation scope and Coverage implemented:** Owner-authorized per-Profile OFF/ON scope allows approval with Reference for included states only; explicitly excluded states are NOT_EVALUATED with no model score, while Raw/control/events remain available. Returning to included state checks frozen Local Reference immediately without a cooldown. Immutable scope/validation fingerprints, included-state evidence gates, revision CAS, reviewer-specific draft hydration and M1–M8 Coverage UI are implemented; legacy unscoped semantics and Fleet frozen bundle remain unchanged. Full API237 tests and final web build pass; actual manual save/reload/stale-tab/Raw/reviewer and017/024 multi-tab QA pass.10clients/120preparedGETs allsuccess, warm p95680.1ms (cold source/render excluded).207legacyProfiles/46legacyActive hashes unchanged,ContextActive0. Technical QA review is not Engineer-certified; contracts/Engineer/new prospective validation/real Server/live producer acceptance remain open. Runbook: `deployment/CONTEXT_SCOPE_AND_COVERAGE_UAT_20261006.md`. Earlier checkpoints are historical.

**6 Oct — Fleet Stable v1 portable Shadow Candidate:** Frozen `fleet-stable-v1-2f656893533033ab994e3713`, 43 calibrated SV-context profiles/70 donor summaries from017/024/041/058/080/081, all8modules considered.555preparedday hashes/46,616,484raw-row receipts verified. Local absolute levels/scales retained; compatible correlation-shape EB-style sharing only. Fit-only Q90 trailing five-minute movement bounds replace the over-tight0.35-only phase screen for this separate Candidate; no legacy/Active Gate changes. MX080/M6 proposed Fit27–30Aug/calibration3–6Sep; owner-described, not Engineer-certified health. Known7–8Sepcase2089/2089eligible flags/2079persistent; pre-case480minutes2raw/0persistent; acquisition-suspect34minutesDATA_QUALITY/0physical flags.12SepnewValve/level remains unreviewed. JSON/checksum ZIP, configurable portable loader, atomic Shadow CAS/rollback, later explicit retraining plan, version-pinned calibration evidence UI and common-ledger adapter delivered.43,227point score parity exact; prepared10clients/120GETs allsuccess, warmp95201.5ms (coldSQL/UIexcluded). Actual3tab/manualmodule/date/missingday QA; chartcards358px/noLoadingtext. Local Shadow pointer only;207Profile/46Active canonical hashes unchanged,ContextActive0,no source import/Server/livevotes. ReviewedNormal/sourcecontracts/independenthealthy/untouchedfuture/verifiedproducer/targetServer acceptance remain open. Report: `deployment/FLEET_STABLE_V1_RUNBOOK_20261006.md`; executed Notebook13. Earlier checkpoints are historical.


**5 Oct — Fleet Reference / selective transfer delivered:** Owner-authorized041/058/080/081 plus017/024 studied from555committed dynamic ZIP days /46,616,484rows (Jul1–Oct1; three missingJul1files). Source SHA/row counts reconciled; no stopped import resume. Selected Reference proposal freezes Local absolute means/scales and selectively shares covariance shape:76/101 evaluated sparse scenarios compatible, versus0/101 mean+covariance; compatibility is not accuracy or Active acceptance. SV-conditioned groups are unverified research strata, not a completed Cold/Room/Hot hierarchy or exact iid NIW. All-state/day/event evidence retained; transition observations do not impose cut/suppression timers. Calibration Fleet Reference UI, machine/module/day graph isolation, source alias dedup and128wireviews under the same32MB cap delivered.225full tests plus7/13focused final regressions/build; three-browser-tab QA;10clients/120preparedGETs all200, warm p95≈109ms (cold SQL preparation excluded). Known080/M6case retains643/643 evaluable minute flags. Profiles207/Active46 canonical hashes unchanged, ContextActive0. Fleet is nonvoting/Reference-only; reviewed normal regimes, verified contracts, independent healthy/case/future validation and worker/Active/Server integration remain required. Report: `deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md`; executed Notebook11. Older checkpoints below are historical. Final research steady-screen uses five-point physical max–min over contiguous supported minutes (limit0.35); adjacent-change-only results are superseded.

**5 Oct — Local conditional Profiles and unified Events implemented:** New versioned all-state measurements, Reference-only steady-regime/transition Candidates, immutable reviews/CAS, frozen prospective validation, separate Active/rollback pointers and common `ht9046mx_events` history are implemented in Operation. Historical source-second capture/backfill and six additive analytics tables applied locally. Final v4 retains control context for delayed physical response without suppressing deviations. Actual017/024/all8 minute graphs, Reference exclusion/rebuild/reload, stale-tab conflict and common SV Raw investigation verified.199APItests/build;320exact minute-module comparisons;10clients/120warmGETs all200, p95≈87ms (bounded first reads≈3.77s; cold preparation≈8–15min). Existing46Active hash unchanged; ContextActive0. Real PM ACK/work/service producer connection, live worker, real conditional known-case/healthy-cycle acceptance, four verified contracts/Engineer/future3days and Server release remain open. This supersedes earlier plan-only statements about local context/event implementation; older checkpoints remain historical. Evidence/runbook: `deployment/COMPRESSOR_CONTEXT_PROFILE_UAT_20261005.md`.

**5 Oct — three-month intake stopped at owner request (working date assumption):** The shared analysis window is **1 Jul–1 Oct 2026**. The import stopped at **369/372** target daily files: MX041 92/93, MX058 92/93, MX081 93/93, MX080 92/93; the three missing files are 1 Jul for MX041/058/080. The window currently has31,042,099 raw rows. The ledger has381 receipts/31,963,964 rows including12 Oct2–5 files outside the shared interval. At stop C: had24.80GiB free; MySQL remains on C:, no move/config/profile/Active/scoring/alert/Server changes. Do not resume unless requested. Aug12 is partial-day for all four; MX080 Jul13 is also low coverage. Details: `deployment/DOWNLOADS_HISTORY_CAPACITY_REVIEW_20261005.md`.

**4 Oct — Physical/control policy and manual regression:** New qualified Candidates use physical P/T scores, nonvoting Valve context and strict Q99.5 `>` comparisons; legacy stored nine-feature `>=` semantics remain. Current-cutoff Reference alternatives are automatic, older stable regimes require review. Reference-only recovery evidence opens Raw before/after SV/unknown boundaries and never suppresses flags. Sixteen actual-cache contexts/14 scorer comparisons have zero differences; known057/M1 and080/M6 case detections retained. Actual GUI checked all 16 modules and completed MX017/M1 exclusion → Preview → Build (SHADOW_VALIDATION; four source prerequisites still block approval). Backend174 tests/build passed; cached Raw40/40 GETs, p95≈539ms. MX024 cold preparation11m33s; reviewer editing after reload remains an unresolved browser UAT path. Active hash unchanged. Manual GUI UAT and limitations: `deployment/PHYSICAL_CONTROL_CALIBRATION_UAT_20261004.md`. Four verified source contracts, prospective healthy/recovery evidence and target-Server Active-success remain open. Older checkpoints below are historical.


**4 Oct — Calibration evidence and SV review:** Readable per-check values/actions, contributor intervals → minute/Raw charts, all-state bounded Raw GET, and bounded past-only per-module Reference proposal implemented. Owner-confirmed psi recorded; pressure basis + state/controller/service versions remain explicit prerequisites. Actual017/024each7Candidates/M7insufficient; no passing stable proposal in current search. 167 API tests plus saved-policy regression/build; exact four-context selector parity, actual browser interval/Raw/invalid-range/M7 and40GET/10client QA. SV study28files/2,385,588rows/196raw-minute checks finds material pressure/thermal differences: retainSVOff Cold gate, preserveSVOn Raw. Active46hash unchanged; no Server/push. Cold preparation remains≈10–12min on local machine; graph reads are bounded/on demand. Evidence: `deployment/CALIBRATION_EVIDENCE_AND_SV_REVIEW_20261004.md`.

**Implementation checkpoint — 3 Oct 2026:** Operation automatic preparation now shares Manual's strict observed-second/completed-day method (28Reference/3Shadow). M1–M8 Candidate preparation is durable and atomic, with per-module evidence, one-hour closed-day analytics cache and fresh Manual Build SHA verification. Graph review remains explicit; `qualified` is not `healthy`, and human Active approval/frozen parameters/rollback are unchanged. Source unit/state/codebook/service prerequisites remain unverified. Local QA and operational limits: `deployment/AUTOMATIC_CALIBRATION_UAT_20261003.md`.

**Manual Calibration UX/UAT — 2026-10-02:** Actual browser tests for017/024 M1–M8 completed:16Preview/graph reviews,14Candidate builds/reviews, bothM7 blocked by zero qualified minutes. Fixed exclusion chart/job loss, dirty-preview validation/reload/recovery, refreshed/translated approval blockers and overflowing status text; empty graphs explain failed qualification. Two-tab resume and Reject checked; Active UI remains46without017/024. Active-success remains untested pending4verified source contracts and statistical gates. Local source-read latency remains open. No source DML/Server/gate bypass. Build/evidence: `deployment/MANUAL_CALIBRATION_UAT_20261002.md`.


> เอกสารสรุประบบสำหรับการวิเคราะห์ข้อมูล การติดตามสภาพ และการสร้างโมเดล Predictive Maintenance
>

## สรุปย่อ

**Local history intake — 2026-10-02:** Owner-authorized Downloads dynamic logs017/024 (July1–Oct1,186files) imported as15,574,385raw-secondwide rows into actuallocalhostsource. Static/080excluded; source duplicates/manualcontexts kept and existing480rows/เครื่องไม่เขียนทับ.204all-columnsample/120exact1mparity/retry/API/UI/158tests pass; existingMX080/Profile/Activehashunchanged. Rawingestion/observedcoverageไม่ใช่healthylabelหรือActiveapproval. Source-day preflightchanged to bounded dailyindexedqueries without Gate/scoring changes, but017/M6still~120s; performanceacceptanceยังเปิด. ไม่มีServer/Profileactivation/retrain/push. Evidence: `deployment/DOWNLOADS_HISTORY_IMPORT_20261002.md`.

**Normal local Reference storage — 2026-10-02:** ติดตั้ง existing job migration ใน actual localhost analytics แล้ว (18columns; รันซ้ำได้). แก้1213 deadlockจาก range UPDATEทุกpoll เป็น read-only live polling/scoped conditional expiry พร้อมแยก missing/schema/busy/connection errors.147tests/buildและ100concurrent actualSQL pollsผ่าน;119Profiles/46Active hashเดิม. TechnicalPreview2งานเท่านั้น ไม่Build/approve/sourceDML/Server/ML change. READYไม่ใช่approval readiness;MX080ข้อมูลqualifiedยังไม่พอ. หลักฐาน: `deployment/REFERENCE_STORAGE_REPAIR_20261002.md`.

**Reference availability v2 — 2026-10-02:** ก่อน Preview ตรวจวันข้อมูลจริงรายเครื่อง–โมดูลรวม Reference/Shadow: แยกแถวล่าสุด, วันที่ไม่มี log, sensor ไม่ครบ และ qualified minutes. ช่วงเสนออิง coverage เท่านั้น ผู้ใช้กดเลือกย้อนหลังพร้อมเหตุผล ไม่เลือกจากอัตราเตือน. Build ต้องมี retained Reference ถึงขั้นต่ำและ Shadow qualified ครบ 3 วัน/จำนวนขั้นต่ำด้วย. Default cutoff เดิมยังอยู่; selection v2/digest รักษา source_latest จริงและวันย้อนหลังที่เลือก. งาน v1 ที่ยังไม่สร้างต้อง Preview ใหม่. Scorer/Active/ML/Server ไม่เปลี่ยน. รายละเอียด/QA: `deployment/REFERENCE_AVAILABILITY_V2.md`. Checkpoint v1 ด้านล่างเป็นประวัติก่อนเพิ่ม preflight นี้.

**Manual-reviewed Reference workflow — 2026-10-02:** หน้า Calibration ของ Operation เพิ่มขั้นตอนเลือกเครื่อง–โมดูล → ดูกราฟและความครอบคลุม → ยืนยัน Reference → สร้าง Candidate + historical Shadow → ตรวจผล/Approval แยกอีกครั้ง. Reference เริ่มต้น 28 วันก่อน Shadow; Shadow ใช้ 3 วันเต็มตามเวลาข้อมูลล่าสุดของเครื่องนั้น ละวันล่าสุดและไม่ซ้ำ Fit. ผู้ดูแลปรับวันหรือยกเว้นช่วงพร้อมเหตุผลได้ โดยไม่ลบ raw/manual logs. กราฟภาพรวมรายชั่วโมงมี min–max ของค่านาที และเปิดรายวัน 1 นาทีได้; ช่องว่าง/หน่วยไม่ยืนยันแสดงตรงตามข้อมูล. งานมี durable SQL job, progress, retry idempotency และตรวจ source-input digest ก่อน atomic Candidate commit. เพิ่มเฉพาะ workflow/UI/analytics job migration และ retained-reference coverage gate; สูตร z/threshold/persistence และ Active เดิมไม่เปลี่ยน ไม่มี learned startup suppression/ML promotion. ทดสอบ MX080/M6 ใน localhost QA schema แยกได้ `REVIEW_REQUIRED` ไม่ Active; 106 API tests/build ผ่าน. ยังไม่ติดตั้ง Server/Push. รายละเอียดและข้อจำกัด: `deployment/REFERENCE_REVIEW_WORKFLOW.md`. บันทึก research ก่อนหน้าที่ระบุว่า UI ยังไม่ทำเป็นสถานะก่อน checkpoint นี้; CLI/legacy calibration route ยังเป็น rolling-window workflow เดิม ไม่ถูกย้ายมาใช้หน้าทบทวนอัตโนมัติ.

**Latest historical-shadow / reference-phase experiment — 2026-10-01:** Implemented local-only 4-way reference ablation in Notebook 08M using raw-second-derived 1m caches for nine machines/all modules. Complete-day historical splits use actual machine inventory (017/024/080 shadow28–30Sep; 029/041/057/070 shadow29–31Aug; 118/119 shadow17–19Aug with no past reference). On 37 matched latest contexts/123,658 minutes, state-only/steady/segment/combined persistent burdens are 11.72/12.85/27.96/33.80%; these are workload, not FPR. State/steady retain MX080 case99.13% and MX057100%; segment abstains for MX080/M6. The pre-case MX080 band still flags11/13 qualified minutes (lp1 under the new offline reference), so startup specificity is unresolved. Causal S/V phase and segment selectors now exist as research, not runtime gates; no phase suppresses scores. Selected runtime remains frozen local z/persistence, no ML retraining/Active/DB/Server/Git changes. Numerical historical shadow is not registry approval/production acceptance. Details: `deployment/HISTORICAL_SHADOW_REFERENCE_PHASE_EXPERIMENT_20261001.md`.

**Latest local method selection — 2026-10-01:** Owner authorized additional-machine analysis while preserving machine-specific calibration. Notebook 08L audits nine machines and fits local references only on 4–17 Aug; 9/72 contexts pass reference screening, 41 require review, 22 are insufficient. Shared ARX/DPCA/IF were trained on 22,500 rows from 5 machines; matched comparison uses 375,857 future minutes. MX057/M1 persistent case coverage: Self 99.82%, ARX 8.27%, DPCA 99.56%, IF 99.82%; these are known-case regression, not accuracy. MX080 ML lanes abstain because their past threshold block has only two qualified days. Selected primary remains frozen local robust-z + 3 adjacent minutes; improve reference/phase qualification before ML promotion. New code/artifacts are local research only, not registry/runtime/Active/DB/Server changes. Evidence: `deployment/LOCAL_PROFILE_MODEL_SELECTION_20261001.md`.

**Control-state research — 2026-10-01 (proposal only):** `ChangeValve/MValveHome/Busy/SV` should remain in observed-second evidence even when ineligible for steady Cold fit/scoring. Existing `qualified_windows.py` excludes these from steady features; it does not delete source rows. Proposed separate quality/context/fit/score gates and event-response ARX/DPCA challengers are not implemented or activated. Falling Hp2 is screening evidence, not confirmed leak; flatness alone is not health. New attached Busy/SV explanations conflict with earlier owner definitions, so tag semantics stay unchanged pending clarification. Research/access limits and evaluation plan: `research/HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md`.

**Evidence update — 2026-10-01:** New raw-second ZIP review of MX017/MX024/MX080 (279 dynamic files/23.35M rows; Static excluded) supports local profile keys, explicit transition/steady review and stable-reference-period selection. Low flag rate from a broad mixed-regime fit is not evidence of health or approval. The proposed phase gate has not been implemented/fitted; numerical lookback experiments do not replace the full registry lifecycle. Data Contract, selected z/persistence, Active Profiles and Server state remain unchanged. Details: `deployment/THREE_MACHINE_AUTOCALIBRATION_REVIEW.md`, Notebook 08K.

**Presentation update — 2026-10-01:** Red sensor-panel overlays now name only that panel's stored features satisfying `|z_j| >= threshold` while the existing global persistent flag is true; global score remains visible separately. This is score attribution, not physical cause or a new per-feature persistence rule. Dashboard and Operation local replay changed presentation only; primary scores/flags/thresholds/Profile remain frozen. The multi-start settling investigation is a proposal in `deployment/STARTUP_SETTLING_VALIDATION_PLAN.md`, not a live regime gate. The global-on-every-panel descriptions in older checkpoints below are historical.

**Local integration / interpretation — 2026-10-01:** เพิ่ม durable worker และ Dashboard evidence bridge แบบ opt-in (default disabled/shadow); การทดสอบจริงใช้ archived MX080 ใน schema QA localhost แยก ไม่ใช่ Active promotion/Server launch. Red overlay ปัจจุบันคือ global persistent max-robust-z จึงเกิดบน pressure panel ได้แม้ dominant feature เป็น temperature. First-band owner review พบ possible normal startup ถูกเทียบ narrow steady candidate; data gate ตอนนี้ตรวจสถานะภายในหนึ่งนาที ยังไม่มี multi-minute thermal settling. บันทึกเป็น limitation ที่ต้องตรวจหลาย starts/regimes ก่อน production specificity ไม่เปลี่ยน tag/threshold หรือเรียกเป็น fault. รายงาน/คู่มือ: `deployment/DURABLE_DETECTOR_LOCAL_QA.md`, `SERVER_DETECTOR_RUNBOOK.md`.

**Workflow update — 2026-10-01:** งานประจำวันของช่างอยู่ที่ `Compressor_and_VacuumPump` Dashboard: Alert → Assigned Work → Service Log หรือ Admin เปิด Assign Work เองเมื่อพบอาการโดยไม่มี Alert. Operation ดูแล calibration/3-day shadow/Active Profile และ recalibration ของเครื่องเดิม พร้อมงานเบื้องหลัง. Episode จาก detector เก็บแยกจาก notification/ใบงาน; Description และ DONE ไม่ใช่ cause label หรือหลักฐาน recovery. รอบนี้เพิ่ม local Episode archive และ reported occurrence-time/frozen report snapshot ใน Dashboard โดยไม่เปลี่ยน tag, primary detector, threshold หรือ Active Profile. Bridge ของ scorer 1 นาทีใหม่ทำและทดสอบใน localhost QA แล้ว แต่ real Active qualification และ live Server acceptance ยังรอตรวจ. รายละเอียด: [Episode/Dashboard workflow](deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md), [local integration QA](deployment/DURABLE_DETECTOR_LOCAL_QA.md).

HONTECH HT9046-MX เป็นชื่อรุ่นที่เจ้าของโครงการยืนยัน; เอกสารและชื่อไฟล์เดิมอาจใช้ alias `HT-9046MX`. เครื่องเป็น Tri-Temperature Test Handler สำหรับควบคุมสภาวะความร้อนของ DUT ในโหมด Cold, Room และ Hot ผ่านระบบ ATC (Active Temperature Control) และ thermal mechanism หลายตำแหน่งในเครื่อง

ระบบมี **8 Compressor Modules** ซึ่งควรวิเคราะห์เป็นระบบกายภาพและระบบควบคุมที่มีสถานะตามเวลา (stateful system) แยกตาม module ไม่ใช่ตีความ pressure, valve และ temperature เป็น sensor อิสระจากกัน

แต่ละ module ใช้ระบบ cascade refrigeration สองวงจรที่แยกกัน:

- **CP1 / first stage:** refrigerant **R507A** — high-temperature circuit และระบายความร้อนออกผ่าน condenser/facility water
- **CP2 / second stage:** refrigerant **R23** — low-temperature circuit ที่สร้างความเย็นให้ thermal load
- ทั้งสองวงจรแลกเปลี่ยนเฉพาะ **ความร้อน** กันผ่าน Cascade Heat Exchanger; refrigerant R507A และ R23 **ไม่ไหลรวมกันในวงจรเดียว**

การวิเคราะห์ที่ถูกต้องต้องเทียบข้อมูลใน operating state, module, recipe, load, valve state, SV state และสภาพ facility water ที่ใกล้เคียงกันเสมอ

---

## 1. Data Contract (Source of Truth)

คำนิยามต่อไปนี้เป็นมาตรฐานที่ต้องใช้ใน dashboard, query, feature engineering, model และเอกสารต่อจากนี้

| Tag | ความหมาย | ข้อควรใช้ในการวิเคราะห์ |
|---|---|---|
| `Hp_1st` | High Pressure ของ **CP1** | ตัวแทนฝั่ง high pressure ของวงจร R507A/CP1; อ่อนไหวต่อ heat rejection และ facility water |
| `Lp_1st` | Low Pressure ของ **CP1** | ตัวแทนฝั่ง low pressure ของวงจร R507A/CP1 |
| `Hp_2nd` | High Pressure ของ **CP2** | ตัวแทนฝั่ง high pressure ของวงจร R23/CP2 |
| `Lp_2nd` | Low Pressure ของ **CP2** | ตัวแทนฝั่ง low/suction pressure ของวงจร R23/CP2 |
| `Status` | Compressor ON/OFF ของเครื่อง | ใช้เป็น state gate ของ compressor; ค่า literal จาก controller (เช่น `Run`) ต้อง map ใน Server configuration ก่อนใช้งาน |
| `Status_n` | Status of Expansion Valve ของ module `n` | เก็บเป็นสถานะควบคุม; ต้องทำ codebook จาก log/controller ก่อนตีความค่าแต่ละ code |
| `Busy_n` | Manual/service-operation flag ของ module `n` | `Busy=1` ใช้ระบุช่วง manual เช่น `MValveHome` หรือ `ChangeValve`; ไม่ใช่หลักฐานว่า motor/compressor หมุนหรือหยุด. `Busy=1` ต้อง exclude จาก normal baseline และ anomaly scoring |
| `TempHigh_n` | Compressor Temperature ของ module `n` | ใช้ติดตาม thermal stress ของ compressor และตรวจความสัมพันธ์กับ pressure/load |
| `TempLow_n` | Discharge Pipe Temperature ของ module `n` | ใช้เป็นอุณหภูมิท่อ discharge ตาม Data Contract นี้; ควรเทียบกับ pressure และ `SV_n` แบบมีเวลาเหลื่อม |
| `SV_n` | Bypass Valve ON/OFF ของ module `n` | `ON` = เปิดใช้งาน Bypass Valve, `OFF` = ปิด Bypass Valve |

`n` คือหมายเลข module 1–8 เช่น `Valve_3`, `Busy_7`, `SV_2`.


### กติกาการตั้งชื่อ

- เอกสารนี้ใช้คำว่า `CP1` และ `CP2` เท่านั้น; หาก log เก่าใช้ `COM1`/`COM2` ให้ map เป็น `CP1`/`CP2` ก่อนรวมข้อมูล
- `Status_n` และ `SV_n` เป็น discrete control signals ต้องเก็บ timestamp เดียวกันกับ pressure/temperature เพื่อวิเคราะห์ event response ได้ถูกต้อง
- Candidate calibration ปัจจุบันรับเฉพาะ `Status=Compressor ON` + `Status_n=On` + `Busy_n=0` + `SV_n=Off` หลังผ่าน quality และ state-stability ในหนึ่งนาที (ยังไม่มี learned thermal-settling gate). `SV_n=On` ระบุ Bypass เปิด; ผลข้อมูลจริง 017/024 วันที่17–30Sepพบร่วมกับ Run/moduleOn/Busy0 จึงไม่ควรสรุป non-running/Hot จาก SV เพียงตัวเดียว. Pressure/thermal differencesยังมากในหลายโมดูล จึงคงแยก SVOn ออกจาก Cold baseline เดิมจนมี mode/recipe qualification เฉพาะ; source rowsยังคงอยู่และเปิดดู Raw ได้.

---

## 2. โครงสร้าง 8 Modules

| Module | การใช้งานตาม configuration ปัจจุบัน | กลุ่ม |
|---:|---|---|
| 1 | Index L Arm1 | Index |
| 2 | Index R Arm1 | Index |
| 3 | Index L Arm2 | Index |
| 4 | Index R Arm2 | Index |
| 5 | SH1 | Shuttle |
| 6 | SH2 | Shuttle |
| 7 | Hot1 | Hot |
| 8 | Hot2 | Hot |

Module แต่ละตัวต้องมี baseline ของตนเอง แม้จะอยู่ในเครื่องเดียวกัน: ความยาวท่อ, thermal load, อายุอุปกรณ์, valve calibration, sensor offset และ recipe ที่ใช้งาน อาจทำให้ normal pressure/valve ต่างกันได้

> ตารางนี้เป็น working mapping จากข้อมูลสนทนาปัจจุบัน หากชื่อจริงจาก HMI, configuration file หรือ service manual แตกต่าง ให้ข้อมูลจากเครื่องจริงเป็น source of truth และแก้ mapping นี้ก่อน train model

---

## 3. Architecture ของ Cascade Refrigeration

```text
                         HEAT / ENERGY PATH

DUT / Thermal Load
        │
        ▼
CP2 low-temperature circuit (R23)
        │
        ▼
Cascade Heat Exchanger
        │
        ▼
CP1 high-temperature circuit (R507A)
        │
        ▼
Water-cooled condenser
        │
        ▼
Facility water / plant heat rejection
```

```text
CP1 — R507A (วงจรที่ 1, แยกจาก CP2)
Compressor → water-cooled condenser → expansion device
          → cascade heat exchanger (R507A evaporates) → compressor

CP2 — R23 (วงจรที่ 2, แยกจาก CP1)
Compressor → cascade heat exchanger (R23 condenses) → expansion valve
          → thermal-load evaporator → compressor
```


1. `CP1` และ `CP2` เป็น **คนละ refrigerant circuit** ไม่ใช่ท่อ refrigerant เดียวกันที่ไหลต่อกัน
2. Cascade Heat Exchanger ส่งผ่าน **ความร้อน** จาก R23 ไปสู่ R507A ไม่ใช่การผสมน้ำยาทั้งสองชนิด
3. CP1 เป็น high-temperature/base stage แต่ `Hp_1st` และ `Lp_1st` **ไม่ใช่ fixed pressure**: ค่าเปลี่ยนตาม heat load, condensing condition, facility water, charge, fouling และ operating state
4. CP2 ต้องอาศัย CP1 เพื่อ condense R23 ได้ดี ดังนั้นปัญหา CP1 หรือ facility water สามารถสะท้อนเป็น cooling performance ของ CP2 ได้ โดยไม่จำเป็นต้องเป็นปัญหา R23

---

## 4. หน้าที่และความสัมพันธ์ของ CP1 / CP2

### CP1: R507A high-temperature stage

CP1 รับความร้อนจาก CP2 ผ่าน Cascade Heat Exchanger แล้วถ่ายเทความร้อนออกสู่ facility water ที่ condenser เป็นหลัก

**สัญญาณสำคัญ**

- `Hp_1st` สูงกว่าปกติอาจสัมพันธ์กับ condenser water ร้อน, flow น้ำต่ำ, condenser fouling, heat load สูง หรือปัญหาใน CP1
- `TempHigh_n` สูงร่วมกับ high pressure/running time สูง เพิ่มน้ำหนักความเสี่ยง thermal stress แต่ต้องเทียบ operating state

### CP2: R23 low-temperature stage

CP2 สร้าง cooling capacity ให้ thermal load โดย R23 ถูกควบคุมผ่าน expansion valve และระบายความร้อนเข้าสู่ CP1 ที่ Cascade Heat Exchanger

**สัญญาณสำคัญ**

- `Valve_n`, `Lp_2nd`, `Hp_2nd` และผลลัพธ์การ pull-down ต้องอ่านเป็นชุดเดียวกัน
- `Valve_n` เพิ่มอาจเป็นการตอบสนองของ ATC ต่อ load; ไม่ใช่หลักฐานว่าน้ำยาน้อยด้วยตัวมันเอง
- ความสัมพันธ์ valve → pressure → cooling มี time delay และเปลี่ยนตาม load, compressor capacity, charge, restriction และสภาวะ condensing

---

## 5. ผลของ Facility Water และสาเหตุร่วม (Common Cause)

Facility water เป็นส่วนหนึ่งของ heat-rejection path ของ CP1 ไม่ใช่ตัวแปรภายนอกที่ละเลยได้

| เหตุการณ์ที่เป็นไปได้ | สัญญาณที่อาจเห็น | วิธีแยกจากปัญหาเฉพาะ module |
|---|---|---|
| Water inlet อุ่นขึ้น / water flow ลดลง | `Hp_1st` สูงขึ้น, CP1 temperature/running time อาจสูงขึ้น, CP2 performance อาจแย่ลงตามมา | เกิดคล้ายกันหลาย module หรือสัมพันธ์กับ water/plant telemetry |
| Condenser fouling | head pressure หรือ temperature drift ช้า ๆ ของ module ที่ได้รับผล | ดู trend ระยะยาวและตรวจ maintenance history |
| Thermal load ของ DUT/recipe เปลี่ยน | pressure/valve/cooling rate เปลี่ยนเฉพาะช่วงงานหรือ recipe | เทียบเฉพาะ recipe, load และ phase เดียวกัน |
| ปัญหา local เช่น R23, EEV, sensor หรือ compressor | ความผิดปกติเด่นที่ module เดียว | เปรียบเทียบ peer modules ภายใต้ state/recipe เดียวกัน |

**กฎใช้งาน:** หากหลาย module มี `Hp_1st` หรือ cooling degradation เปลี่ยนไปในช่วงเดียวกัน ให้ตรวจ facility water, ambient, recipe mix และ common infrastructure ก่อนสรุปว่าแต่ละ module รั่วพร้อมกัน

---

## 6. ATC, Expansion Valve และ Bypass Valve (SV)

ATC เป็น control loop ที่พยายามทำให้อุณหภูมิของ thermal target เข้าใกล้ recipe โดยอาศัย cooling, heating และตำแหน่ง expansion valve ตาม state ของระบบ

### Expansion valve

`Valve_n` เป็น output/control demand ของ ATC สำหรับการป้อน refrigerant ใน module นั้น ผลที่คาดหวังโดยทั่วไปของการเปิดเพิ่มคือ refrigerant feed เปลี่ยน และต่อมาค่า `Lp_2nd`/cooling response เปลี่ยน แต่ทิศทางหรือขนาดของผลตอบสนอง **ไม่ตายตัว** ในทุก sample เพราะขึ้นกับ load, CP2 pumping capacity, CP1 condensing condition, charge และ transient/hunting ของ controller

ให้วิเคราะห์แบบ event response:

```text
ΔValve_n → response delay → ΔLp_2nd / ΔHp_2nd → cooling-rate response → temperature settling
```

### Bypass valve (`SV_n`)

- `SV_n = ON`: Bypass Valve เปิดใช้งาน
- `SV_n = OFF`: Bypass Valve ปิด
- หน้าที่/เส้นทาง piping ที่แน่นอนของ bypass ต้องยึด P&ID หรือ service documentation ของ HT-9046MX; ใน data model ให้ถือ `SV_n` เป็น state boundary ที่ต้อง split dataset เสมอ

---

## 7. Operating Modes และพฤติกรรมที่คาดหวัง

| Mode / phase | เจตนาของระบบ | แนวทางอ่านข้อมูล |
|---|---|---|
| Cold / Pull-down | ดึงอุณหภูมิลงสู่ cold recipe | `Status=Compressor ON`, `Busy=0`, `SV=OFF`; ประเมิน cooling rate, valve demand, CP2 pressures, time-to-target และ CP1/facility condition ร่วมกัน |
| Cold / Regulation | รักษาอุณหภูมิที่ target | วิเคราะห์ stability, valve movement, hunting, SV state, pressure band และ overshoot |
| Room | เข้า/รักษาอุณหภูมิใกล้ ambient/room recipe | thermal load และ control strategy ต่างจาก Cold; สร้าง baseline แยก |
| Start-up | เริ่ม compressor/control sequence | มี transient สูง ไม่เหมาะกับ steady-state baseline |
| Shut-down / Idle | compressor หยุดหรือรอ | pressure อาจ equalize ตามเวลาและ valve/SV state; ไม่ใช่ cooling-health baseline |


---


หลัง compressor หยุด ความต่างของ high/low pressure **อาจ** ค่อย ๆ ลดลง (`HP` ลด, `LP` เพิ่ม และเข้าใกล้กัน) ตามเวลาที่หยุด, อุณหภูมิ refrigerant, expansion valve, solenoid/bypass state และโครงสร้างของวงจร

ดังนั้น:

- ค่า static/idle pressure ต้องพิจารณาเป็น function ของ **module + refrigerant temperature + elapsed OFF time + valve/SV state + หน่วย pressure**
- การที่ HP และ LP ยังไม่ equalize ไม่ได้แปลว่าผิดปกติโดยอัตโนมัติ เพราะวาล์วอาจกัก differential pressure ไว้

---

## 9. Emergency Down และ MValveHome

### Emergency Down

Emergency Down เป็น event/sequence ด้านความปลอดภัยและการหยุดระบบ จึงต้อง tag แยกจาก normal stop และ exclude จากการสร้าง normal cooling baseline


- timestamp ของ Emergency Down
- `Busy_n`, `Valve_n`, `Status_n`, `SV_n` ก่อนและหลัง event
- pressure/temperature trajectory ของ CP1 และ CP2
- fault/alarm code และ operator action

### MValveHome

MValveHome คือ sequence เพื่อหา/ตั้ง reference ของ expansion valve ใหม่ โดยทั่วไป stepper EEV สามารถมี closing overdrive เพื่อสร้าง mechanical closed reference

- `Valve_n < 0` ระหว่าง MValveHome ให้ตีความเป็น **controller command/reference ของ homing/closing direction** ไม่ใช่ physical valve opening ติดลบ
- หลัง homing ให้รอ transition สู่ stable operating state ก่อนนำข้อมูลกลับเข้า feature window

---

## 10. การตีความ Leak / Undercharge ของ R23

### กติกาหน้างานที่ยืนยันสำหรับชุดข้อมูลนี้

- ในข้อมูลที่ผ่าน qualification และเทียบภายใต้ `machine × module × SV × operating state` เดียวกัน ให้ใช้ `Hp_2nd = 180–230 psi` เป็น **ช่วงอ้างอิงหน้างานของ charge ปกติ** ไม่ใช่ช่วง safety certification และไม่แทน local calibration
- เมื่อ `Hp_2nd < 180 psi` ให้เพิ่ม **one-sided undercharge/leak screening evidence** เท่านั้น ต้องดู persistence, trend, `Lp_2nd`, valve demand, cooling performance และผลตรวจจากช่างร่วมกันก่อนสรุป

### สมมติฐานหน้างานเรื่องแรงดันสูงและระบบน้ำ

เจ้าของโครงการให้บริบทว่า `Hp_2nd` ที่สูงมากอาจพบร่วมกับปัญหาท่อน้ำ/การเปิดน้ำแรง และอาจตามด้วยข้อความระดับน้ำใน tank ใกล้เต็ม บริบทนี้บันทึกเป็น **field hypothesis** จนกว่าจะมี P&ID, alarm codebook, water-level/flow telemetry หรือ technician record ยืนยันเส้นทางเหตุผลของเครื่องจริง

การตรวจ MessageLogs ของ MX-080 ที่มีอยู่ ณ 10 Sep 2026 พบ `ALM004 Water flow error!! [IN]` เพียงหนึ่งครั้งเมื่อ 30 Aug 2026 แต่ไม่พบข้อความ `water`, `tank` หรือ `level` ในช่วง Module 6 high-pressure episode วันที่ 3–8 Sep 2026. ใกล้เหตุการณ์ `ALM004` นั้น `Hp_2nd_6` อยู่ประมาณ 213.9 psi และระบบอยู่ในช่วง Run/Stop transition จึงยังใช้ยืนยันหรือหักล้าง causal relation ไม่ได้

เอกสาร troubleshooting ของ Danfoss สำหรับ water-cooled condenser ระบุสาเหตุทั่วไปของ condensing pressure สูง เช่น water quantity ต่ำ, cooling-water temperature สูง, fouling/blockage, pump/valve problem และ refrigerant overcharge; ส่วน pressure-regulating water valve โดยทั่วไปเพิ่ม water flow เมื่อ condensing pressure สูงเพื่อพาระบบกลับสู่สมดุล ([Danfoss Ref Tools](https://reftools.danfoss.com/tools/cooling/troubleshooter/system-areas/high-pressure/system/condensing-pressure-too-high/water-cooled-condensers/), [Danfoss WVFX/WVO/WWS](https://assets.danfoss.com/documents/latest/151244/AF189286419730en-040201.pdf)). หลักทั่วไปนี้ทำให้สมมติฐาน “เปิดน้ำมากขึ้นเป็นเหตุให้ pressure สูง” ต้องได้รับการพิสูจน์จาก piping/control logic ของ HT9046-MX โดยเฉพาะก่อนใช้เป็น diagnostic rule


### หลักฐานที่ทำให้น่าสงสัย Undercharge/Leak มากขึ้น

ให้พิจารณาเป็น evidence fusion ต่อไปนี้ใน module, recipe และ operating state เดียวกัน:

```text
Hp_2nd baseline ↓  (persistent over many comparable cycles)
Lp_2nd ↓
Valve demand ↑
Cooling rate ↓
Time-to-target ↑ หรือ target miss
Runtime ↑
CP1 / facility-water condition ไม่ได้อธิบายอาการ
```

Pattern นี้สอดคล้องกับแนวคิดว่า R23 inventory ลด → evaporator/feed ถูก starve → CP2 suction/head response ลด → ATC เรียก valve มากขึ้นแต่ cooling performance แย่ลง


> **“R23 undercharge/leak suspect — requires maintenance verification”**

ไม่ใช่ “ยืนยัน leak” จาก tag เพียงตัวเดียว

### ตัวอย่างการจัดระดับ

| หลักฐาน | การตีความที่เหมาะสม |
|---|---|
| `Hp_2nd` ลดลงครั้งเดียว | transient / load or phase difference / investigate context |
| `Hp_2nd` baseline ลดต่อเนื่อง แต่ performance ปกติ | CP2 high-pressure drift; monitor และตรวจ comparability |
| `Hp_2nd` + `Lp_2nd` ลด, valve สูง, pull-down ช้า ต่อเนื่องหลาย cycle | strong undercharge/leak suspect หลังตัด common causes |
| หลาย module มี CP1 head pressure สูงใกล้กัน | facility water / shared heat rejection suspect ก่อน |

---

## 11. Operating-State Rules สำหรับการวิเคราะห์

ก่อนเปรียบเทียบค่าใด ๆ ต้อง qualification ข้อมูลด้วยกฎต่อไปนี้

1. **เทียบเฉพาะ module เดียวกันก่อน** แล้วจึงใช้ peer module เป็น reference รอง
2. **เทียบ recipe/mode/phase เดียวกัน** เช่น Cold pull-down กับ Cold pull-down เท่านั้น
3. `Busy_n` ต้องสะท้อน run state ที่สอดคล้องกัน; แยก start-up, shutdown, idle, MValveHome และ Emergency Down ออก
4. `SV_n` ต้องเท่ากัน หรือแยก model/threshold ระหว่าง `SV=ON` และ `SV=OFF`
5. `Status_n` ต้องอยู่ใน control state ที่เทียบเคียงได้; value/code ที่ไม่รู้ความหมายต้องจัดเป็น unknown state
6. ใช้ window หลัง transient settle แล้วเมื่อสร้าง steady-state baseline
7. เก็บ facility-water condition และ thermal load/recipe context เพื่อป้องกัน confounding
8. ใช้ timestamp ที่ synchronized และลำดับเวลาเสมอ; valve response ต้องมี lag window


- sensor communication error, missing data, unit mismatch หรือ timestamp out of order
- Emergency Down, MValveHome, valve negative command และช่วง pump-down
- first minutes หลัง start/stop ที่ยังไม่ settle (กำหนด duration จาก log จริง)
- recipe/mode เปลี่ยนกลาง window
- `SV`/`Status` เปลี่ยนกลาง window โดยไม่ได้ segment event

---

## 12. แนวทาง Data Analysis

### 12.1 Minimum dataset ที่แนะนำ

นอกจาก Data Contract หลัก ควรเก็บข้อมูลต่อไปนี้ให้ครบทุก timestamp:

- machine ID, module ID, firmware/configuration version
- timestamp และ sampling interval
- recipe ID, mode, temperature setpoint, actual controlled temperature และ thermal-load/DUT context เท่าที่มี
- `Hp_1st`, `Lp_1st`, `Hp_2nd`, `Lp_2nd`, `Valve_n`, `Status_n`, `Busy_n`, `TempHigh_n`, `TempLow_n`, `SV_n`
- facility-water inlet/outlet temperature, flow/pressure (ถ้ามี), ambient condition
- compressor runtime/cycle count, alarm/fault history, service event และ refrigerant/part replacement history

### 12.2 Features ที่มีประโยชน์

| กลุ่ม | ตัวอย่าง feature |
|---|---|
| Pressure | median/mean/band ของ HP/LP ตาม state, `Hp_2nd-Lp_2nd`, slope, variance, drift ต่อวัน/ต่อ cycle, `max(0,180-Hp_2nd)` สำหรับ low-side screening และ high-side local robust deviation แยกกัน |
| Valve response | `ΔValve`, lag ถึง `ΔLp_2nd`, response gain, t90, settling time, oscillation/hunting count |
| Cooling outcome | pull-down slope, time-to-target, target miss, overshoot, temperature stability |
| Compressor/thermal | `TempHigh`/`TempLow` band, slope, time above baseline, runtime, starts per cycle |
| Cross-stage | ความสัมพันธ์ CP1↔CP2 เช่น CP1 head condition เทียบกับ CP2 pull-down performance |
| Cross-module | robust z-score ของ module เทียบ peer ภายใต้ recipe/state เดียวกัน |
| Control state | `Busy`, `Status`, `SV`, mode, recipe และ event flags เป็น feature/categorical partition |

### 12.3 Baseline ที่ควรใช้

สร้าง baseline แบบมีเงื่อนไข แทน threshold เดียวทั้งเครื่อง:

```text
baseline[module, recipe, mode/phase, Busy, Status, SV, facility-water band]
```

ใช้ robust statistics เช่น median, IQR/MAD, percentile band และ slope over time เพื่อทนต่อ outlier และ recipe mix ที่เปลี่ยนไป

---

## 13. Recommended ML Flow

```text
1. Ingest + validate units/timestamps
            ↓
2. Map tags to Data Contract และ enrich module/recipe/water context
            ↓
3. Detect operating state and segment cycles/events
            ↓
4. Exclude homing, Emergency Down, pump-down, unstable transient
            ↓
5. Build state-conditioned baseline per module
            ↓
6. Generate response, performance, trend, and peer-comparison features
            ↓
7. Detect anomaly / degradation score
            ↓
8. Fuse evidence into a non-diagnostic anomaly explanation
            ↓
9. Route alert for maintenance verification; feed confirmed outcome back as label
```

### Model strategy ตามความพร้อมของ label

| สถานะข้อมูล | แนวทางที่แนะนำ |
|---|---|
| ยังไม่มี failure label ที่เชื่อถือได้ | เริ่มจาก rule + state-conditioned baseline + anomaly detection (เช่น robust z-score, isolation forest) |
| มี prospective technician confirmations ไม่มาก | ใช้ anomaly screening + human review ก่อนสร้าง binary label final |
| มี binary confirmation ที่ผ่าน QA มากพอ | ใช้ supervised model เพื่อแยก `EQUIPMENT_ANOMALY` กับ `NO_EQUIPMENT_ANOMALY` พร้อม time-based validation |

### หลักการสำหรับ alert

- Alert ต้องระบุ **module, state/recipe, evidence, baseline ที่เปรียบเทียบ และความต่อเนื่องของอาการ**
- ใช้ persistence หลาย cycle/หลายวัน ลด false positive จาก transient เดี่ยว
- แยกผลเป็น `common-cause suspect`, `local refrigeration/control suspect`, `sensor/data-quality suspect` ก่อนลงรายละเอียดว่า leak
- ให้ maintenance technician ยืนยันเพียงว่า alert สัมพันธ์กับความผิดปกติของเครื่องจริงหรือไม่ และบันทึกกลับสู่ prospective dataset
- Integration กับ Dashboard: OPERATION เป็นผู้สร้าง Compressor Alert เพียงฝั่งเดียว (`issue_key=compressor_ml_condition`); แยกจาก Vacuum Alert ของ Dashboard. Alert ประเภทเดิมแจ้งได้ไม่เกินหนึ่งครั้งต่อวันตามเวลา Asia/Bangkok, ยกเว้น severity escalation; Acknowledge ระงับประเภทเดิม 7 วัน และไม่ลบ Alert เก่าเพื่อรักษา audit/Work Order linkage. การส่ง live Alert ต้องมี source timezone ที่ยืนยันแล้วและ sample สดเท่านั้น; historical replay ไม่ส่ง live Alert.

---

## 14. Cautions / ข้อควรระวัง

1. Pressure absolute value ไม่ใช่ health score โดยลำพัง
2. Idle 100 psi ไม่ใช่กฎ; static pressure ขึ้นกับอุณหภูมิ เวลา และ valve state
3. `Valve_n` คือคำสั่ง/position ไม่ใช่ flow meter และค่า negative ระหว่าง homing ไม่ใช่ valve opening จริง
4. SV, expansion-valve status, mode และ recipe คือ state boundary ที่ต้องแยกข้อมูล
5. ค่า “ปกติ” ของ module หนึ่งไม่จำเป็นต้องเป็นค่าปกติของ module อื่น
6. P&ID, service manual, controller codebook และ log ที่มี labelled events เป็นหลักฐานสูงสุดสำหรับยืนยัน logic machine-specific
7. `Busy_n` ไม่ใช่หลักฐานยืนยัน compressor run state จนกว่า controller codebook หรือ electrical feedback จะยืนยัน semantics

---

## 15. Checklist ก่อนใช้งานจริง

- [ ] ยืนยัน mapping ของ 8 modules จาก HMI/configuration เครื่อง
- [ ] ยืนยัน units, sampling rate, sensor calibration และ timezone ของ historian
- [ ] สร้าง codebook สำหรับ `Status_n`, `Busy_n`, `SV_n` และ alarm/event code
- [ ] เพิ่ม recipe, actual temperature, setpoint, mode/phase และ facility-water telemetry
- [ ] mark MValveHome, Emergency Down, start/stop และ maintenance windows
- [ ] สร้าง baseline แยก module + state ก่อนตั้ง threshold/ทำ ML
- [ ] ตั้ง prospective-feedback start time หลังระบบ live แล้วรับเฉพาะ alert ใหม่
- [ ] ยืนยัน timezone semantic ของ `detected_at` และตั้ง `ALERT_DATETIME_TIMEZONE` ก่อนเปิดรับ technician confirmation
- [ ] ให้ technician ยืนยันว่า alert นั้นพบความผิดปกติของเครื่องจริง, ไม่พบ, หรือยังยืนยันไม่ได้
- [ ] ทำ Label QA ก่อนนำเฉพาะคำตอบ yes/no ไปทบทวน binary anomaly model

---

## การใช้เอกสารนี้

README นี้เป็น data-and-analysis contract สำหรับ HT-9046MX ไม่ใช่คู่มือซ่อมหรือคำสั่งเปลี่ยนค่าเครื่อง การทำงานกับ refrigerant, pressure system, compressor และ Emergency Down ต้องดำเนินการโดยผู้มีอำนาจ/ผู้เชี่ยวชาญของเครื่องตาม service documentation และขั้นตอนความปลอดภัยของโรงงาน

---

## 16. Evidence Hierarchy และระดับความหมายของผลลัพธ์

README นี้สามารถปรับปรุงได้เมื่อมีหลักฐานที่ดีกว่า แต่การเปลี่ยนแปลงต้องระบุแหล่งที่มา เหตุผล วันที่ และผลกระทบต่อ feature/model/profile version

### ลำดับความน่าเชื่อถือสำหรับข้อเท็จจริงเฉพาะเครื่อง

1. P&ID, controller codebook, service manual และ configuration ของ HT-9046MX รุ่นจริง
2. Maintenance/service/refill record ที่มีเวลาและผู้ยืนยัน
3. Log ที่มี event/fault label ซึ่งช่างตรวจสอบแล้ว
4. Data Contract และกติกาหน้างานที่ผู้ใช้ยืนยัน
5. ผลวิเคราะห์เชิงสถิติจากข้อมูลที่ผ่าน qualification
6. งานวิจัยจากระบบ refrigeration หรือ industrial time-series ที่เทียบเคียงได้
7. สมมติฐานหรือ inference ที่ยังไม่มีหลักฐานยืนยัน


### ระดับผลลัพธ์ที่อนุญาต

| ระดับ | ความหมาย | หลักฐานขั้นต่ำ |
|---|---|---|
| `DATA_QUALITY` | ข้อมูลไม่พร้อมสำหรับตัดสินสภาพเครื่อง | schema/unit/time/state gate ไม่ผ่าน |
| `DEVIATION` | ค่าเบี่ยงจาก reference profile | comparable profile + calibrated deviation |
| `PERSISTENT_PATTERN` | ความเบี่ยงเบนเกิดซ้ำหรือสะสม | persistence หลาย window/cycle/day |
| `FAULT_SUSPECT` | รูปแบบเข้ากับสาเหตุหนึ่งมากขึ้นหลังพิจารณาสาเหตุอื่น | evidence fusion + alternative-cause check |
| `TECHNICIAN_CONFIRMED_ANOMALY` | ช่างยืนยันว่ามีความผิดปกติจริง แต่ยังไม่ระบุสาเหตุ | prospective confirmation + Label QA |
| `CONFIRMED_FAULT` | สาเหตุได้รับการตรวจยืนยัน | technician/service evidence เท่านั้น |


**กติกา prospective binary label:** Phase 8 รับคำยืนยันเฉพาะ alert ที่เกิดหลัง `TECHNICIAN_FEEDBACK_START_AT` และเก็บ `EQUIPMENT_ANOMALY`, `NO_EQUIPMENT_ANOMALY` หรือ `UNRESOLVED`. เนื่องจาก `detected_at` ใน analytics schema เป็น `DATETIME(6)` ที่ไม่พก timezone, live API ต้องมี `ALERT_DATETIME_TIMEZONE` ที่ผ่านการยืนยันก่อนเปรียบเทียบ boundary; หากไม่มีต้อง fail closed. เฉพาะสองสถานะแรกที่ผ่าน Label QA จึงใช้เป็น binary training evidence; `UNRESOLVED`, historical alert และ raw note ไม่เป็น target. เหตุการณ์ใหม่หรือเครื่องอื่นที่มี pattern คล้ายกันยังคงเป็น `FAULT_SUSPECT` จนกว่าจะได้รับการตรวจใหม่

---

## 17. Research-informed Hybrid Model Architecture

สถาปัตยกรรมที่ใช้ต่อจากนี้ต้องแยกหน้าที่ของแต่ละชั้นให้ชัดเจน:

```text
Data and state qualification
        ↓
State-conditioned local calibration
        ↓
Relative, trend and event-response features
        ↓
Robust/SPC + dynamic residual + multivariate anomaly detector
        ↓
Threshold calibration and evidence fusion
        ↓
Persistence and alert policy
        ↓
Maintenance verification and label feedback
```

### Four-evidence contract

**Current scoring decision (30 Sep 2026):** the selected anomaly screen uses only the `Self` lane: max-absolute robust z-score from a machine–module–SV–state profile, followed by temporal persistence. The selected feature grain is a completed qualified **one-minute** Cold window built from observed seconds; Dashboard refresh remains five minutes. `Dynamic`/ARX, `Peer`, Isolation Forest and sequence models below are research options, not current live score/alert inputs. Local candidate/scorer and checkpoint parity have passed on MX057/MX070 using candidate-derived profiles in memory. That local rehearsal does not create a real `ACTIVE_FROZEN` profile or connect the one-minute path to live scores/alerts. Details: `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

สถาปัตยกรรมเชิงวิธีการแบ่งหลักฐานก่อน persistence ออกเป็นสี่ส่วน เพื่อไม่ให้ anomaly score เดี่ยวถูกตีความเกินจริง:

| Evidence | คำถามที่ตอบ | ตัวอย่างผลลัพธ์ |
|---|---|---|
| `Self` | module นี้ต่างจาก profile ของตัวเองหรือไม่ | robust z-score, quantile distance, local residual |
| `Dynamic` | response หลัง valve/control change ต่างจากอดีตหรือไม่ | ARX residual, lag, gain, settling mismatch |
| `Peer` | module นี้ต่างจาก peer/subfleet ที่มี context เดียวกันหรือไม่ | peer residual, peer coverage, multivariate deviation |
| `Temporal` | ความเบี่ยงเบนเป็น transient หรือสะสมต่อเนื่องหรือไม่ | EWMA/CUSUM, slope, change point, persistence |


ก่อนมี labels ให้เก็บ evidence vector และ contributor แยกกัน แทนการอ้างว่า weighted score คือ failure probability. Evidence fusion มีหน้าที่จัด category เช่น `LOCAL_DEVIATION`, `DYNAMIC_RESPONSE_MISMATCH`, `PEER_MISMATCH`, `PERSISTENT_DEGRADATION`, `SENSOR_OR_DATA_QUALITY_SUSPECT` หรือ `REVIEW_REQUIRED`; persistence และ human verification ยังเป็น gate หลังจากนั้น.

### Model strategy ตาม data maturity

| Data maturity | Model ที่ควรเป็นแกน | Model challenger |
|---|---|---|
| ไม่มี confirmed fault labels | robust baseline, CUSUM/EWMA, ARX residual, Isolation Forest | PCA-SPE, ECOD/COPOD, One-Class SVM |
| มี normal sequence ครอบคลุม state/event | shallow hybrid เดิม | TCN autoencoder, LSTM encoder-decoder |
| มี confirmed labels จำนวนน้อย | anomaly screening + human review | Extra Trees/CatBoost แบบ cost-sensitive |
| มี confirmed labels และ coverage เพียงพอ | calibrated supervised tree model พร้อม anomaly fallback | physics-guided/sequence classifier |


### Dual-rate feature policy

- ข้อมูลหนึ่งนาทีเป็น durable operational stream สำหรับ steady features และ trend
- ข้อมูลหนึ่งวินาทีเก็บใน ring buffer ชั่วคราวเพื่อคำนวณ event-response features เช่น 5/15/30/60/120-second delta, lag, gain, t90 และ settling
- หลังสกัด feature แล้วจึงเชื่อมเข้ากับ minute record
- ข้อมูลหนึ่งนาทีที่ aggregate ไปแล้วไม่สามารถสร้าง trajectory หนึ่งวินาทีย้อนหลังได้ครบ

### Health view และ supervised anomaly confirmation


เมื่อผ่าน data/profile gate และไม่มี persistent anomaly ระบบสามารถใช้ Health/Condition Score เพื่อแสดง `Normal within this profile` ได้ แต่เป็นเพียงสถานะที่สัมพันธ์กับ reference profile ไม่ใช่การรับรองว่าเครื่องไม่มีความเสียหายทุกชนิด

Phase 8 เก็บเพียง binary confirmation ว่า `EQUIPMENT_ANOMALY` หรือ `NO_EQUIPMENT_ANOMALY`; ไม่เก็บ cause code, action, refrigerant amount หรือ note เพื่อสร้าง class. ดังนั้น supervised model รุ่นแรกมีขอบเขตแค่คัดกรอง anomaly ที่มีผลตรวจจริง ไม่ใช่ทำนายสาเหตุ และต้องผ่าน temporal + leave-one-machine-out validation, probability calibration, data/profile/OOD gates และ human approval ก่อนใช้ advisory ใด ๆ.


---

## 18. Auto-bootstrap Profile Lifecycle


### Server candidate workflow

**Reference UI v2:** ขั้นเลือกวันตรวจ source-day inventory รวม Reference และ Shadow ก่อนเริ่มงาน. ผู้ดูแลเลือก cutoff ย้อนหลังพร้อมเหตุผลได้เมื่อช่วงล่าสุดขาดข้อมูล; ยังคง Shadow 3 วันปฏิทินติดกันหลัง Reference ไม่ทับ Fit และเก็บเวลาของแถวล่าสุดจริงไว้. Build ตรวจทั้ง retained Reference และ qualified Shadow coverage. การเลือกจาก coverage ไม่ยืนยัน healthy และไม่เลือกวันจากผล anomaly. Legacy rolling workflow ไม่เปลี่ยน. รายละเอียด: `deployment/REFERENCE_AVAILABILITY_V2.md`.

เมื่อ Server ได้รับ source mapping, unit และ IANA timezone ที่ยืนยันแล้ว ขั้นคำนวณทำงานแบบ read-only ต่อ telemetry: ดึง raw ย้อนหลัง → aggregate เป็น machine–module–SV–qualified-state minute windows → รับ baseline ปัจจุบันเฉพาะ `Status=Compressor ON` + `Status_n=On` + `Busy=0` + `SV=Off` → two-pass robust quarantine → fit median/scale → ตั้ง candidate threshold จาก retained calibration เท่านั้น → score Shadow ที่อยู่หลัง Reference และไม่ซ้ำ Fit → เขียน candidate, reason codes และ shadow points ลง analytics registry. `Busy=1` และ `SV=On` ไม่ใช้ steady Fit/score แต่ไม่ลบ source log; ไม่ใช่ data-quality fault.

**ช่องทาง manual review ปัจจุบัน (2 Oct):** ผู้ดูแลเลือกเครื่อง–โมดูลและทบทวน Reference บน Operation ก่อนกดสร้าง Candidate. Shadow เป็น 3 วันย้อนหลังที่ครบวันตามเวลาข้อมูลล่าสุดของเครื่องนั้น ไม่ต้องรอ 3 วันถัดจากวันที่กด; default Reference28d อยู่ก่อน Shadow และปรับวัน/ยกเว้นช่วง Reference พร้อมเหตุผลได้. บันทึกวัน reviewer เหตุผลและ input digest; ตรวจจำนวนข้อมูลหลัง quarantine และอ่าน source ซ้ำก่อน atomic commit. หมายเหตุ/การยืนยัน Reference ไม่ใช่ healthy label หรือ Active approval. การทบทวนย้อนหลังแล้วเลือก Reference ใหม่ไม่ใช่ blind test และไม่ใช้ flag rate เป็น FPR. Legacy rolling route/CLI/scheduler เดิมยังเป็นอีกช่องทาง ไม่ถูกเปลี่ยนเป็น workflow นี้เอง. ขั้นอนุมัติ Active ยังคงเป็นการตัดสินใจแยกของผู้มีสิทธิ์. รายละเอียด: `deployment/REFERENCE_REVIEW_WORKFLOW.md`.

กราฟ review ต้องใช้แกนเวลา 3 วันเดียวกัน: **เขียว** คือ window ที่ผ่าน gate และต่ำกว่า candidate threshold, **แดง** คือ local robust-deviation score ที่เกิน threshold. Score นี้เป็น calibration/anomaly evidence ไม่ใช่ failure probability, Health Score หรือ fault confirmation.


คำว่า bootstrap ในโปรเจกต์นี้ต้องแยกชัดเจน:

- **Auto-bootstrap profile:** lifecycle สำหรับสร้าง candidate profile
- **Block/stationary bootstrap:** resampling block ตามเวลาเพื่อประมาณ uncertainty
- **Model bootstrap/bagging:** sampling with replacement ภายใน ensemble
- **AutoML/HPO:** การค้นหา model/parameter ภายใน development split

สี่คำนี้ไม่สามารถใช้แทนกันได้ และ `bootstrap=True` ของ model ใดไม่ได้หมายความว่า Auto-bootstrap profile ถูก implement แล้ว

```text
UNSEEN
→ COLLECTING
→ DATA_QUALITY_PASSED
→ STATE_COVERAGE_CHECKED
→ FLEET_SCREENING_PASSED
→ CANDIDATE_PROFILE
→ SHADOW_VALIDATION
→ READY_FOR_APPROVAL
→ ACTIVE_FROZEN
```

สถานะที่ต้องรองรับเพิ่มเติม ได้แก่ `INSUFFICIENT_DATA`, `INSUFFICIENT_COVERAGE`, `REVIEW_REQUIRED`, `REJECTED`, `SUPERSEDED` และ `ROLLBACK_ACTIVE`

### Readiness ต้องแยกสองส่วน


ค่า minimum days/windows/events เป็น provisional operating policy ต้องทบทวนด้วย profile-stability curve, block-bootstrap uncertainty และ shadow false-alert evidence

### Contamination protection

- Candidate baseline รับเฉพาะ window ที่ผ่าน Data/State Gate
- Quarantine window ที่มี extreme robust residual, persistent anomaly evidence หรืออยู่ใกล้ service transition
- หากข้อมูลที่ถูก quarantine สูงผิดปกติหรือกระจุกต่อเนื่อง ให้หยุดที่ `REVIEW_REQUIRED`

### Service/refill epoch


ทุก profile ต้องบันทึก machine, module, SV/state key, source dates, eligible counts, feature version, uncertainty, quarantine reasons, shadow result, approver และ rollback version

---

## 19. Validation, Threshold และ Uncertainty Contract

### Required validation hierarchy

```text
Past-only temporal validation
→ Leave-one-machine-out validation
→ Sparse/new-machine external test
→ Service-epoch holdout
→ Shadow production replay
```

- Overlapping windows จาก event/cycle เดียวกันต้องอยู่ใน split เดียวกัน
- Baseline, scaler, imputer, feature selection, model และ threshold ต้อง fit จาก training period เท่านั้น
- Feature ที่ใช้ข้อมูลอนาคต 30/120 วินาทีต้องระบุ availability time และมี purge gap ที่เหมาะสม

### Hyperparameter-selection policy

```text
Outer test: future time / held-out machine / sparse external machine
Inner train: fit profile, scaler, imputer, feature selector and model
Inner validation: select model hyperparameters
Calibration block: select threshold and persistence
```

- Random search เป็น baseline สำหรับทุก HPO study; ใช้ Optuna/Hyperband/SMAC ได้เมื่อ search budget และ split เท่ากัน
- ต้องรันหลาย seed และรายงานทั้ง median กับ worst-machine result

### Threshold policy

- แยก anomaly model score ออกจาก operating threshold
- `contamination` ของ model ไม่ใช่อัตราความเสียหายจริง
- Threshold ต้อง calibrate จาก past-only clean candidate data และ alert budget
- ใช้ persistence หลาย window/cycle ลด false positive จาก transient เดี่ยว
- หากใช้ conformal calibration ต้องตรวจ time dependence/distribution drift และรายงาน realized false alerts ต่อ machine-day ควบคู่กัน

### Uncertainty

- Time-series uncertainty ใช้ block/cluster bootstrap ระดับ cycle หรือ machine-day ไม่สุ่มรายวินาที
- รายงาน sample count และ confidence interval โดยเฉพาะเครื่องที่มีข้อมูลน้อย

### Metrics

ก่อนมี confirmed labels ให้รายงาน flag rate, alerts per machine-day, persistence, score drift, seed stability, LOMO dispersion และ worst-machine behavior หลังมี labels ให้เพิ่ม precision, recall, PR-AUC, false alerts per machine-day, missed faults, lead time, cause confusion และ probability calibration

---

## 20. Production Change Control

Feature, model, threshold และ calibration profile ต้องมี version แยกกัน การเปลี่ยนค่าใดค่าหนึ่งถือเป็น production change แม้ไม่ได้เปลี่ยนชนิด model


ก่อนเปลี่ยน `ACTIVE_FROZEN` ต้องมี:

- reproducible training/calibration inputs
- temporal และ cross-machine validation
- shadow evidence
- technician-facing explanation example
- approver record
- exact rollback target
- server latency, missing-data และ restart tests


### สถานะความพร้อมปัจจุบัน

- พร้อมพัฒนาต่อเป็น **shadow/anomaly-screening service** หลัง Auto-bootstrap และ replay gates ผ่าน
- Deterministic offline shadow replay ผ่านด้าน model portability, checksum, restart parity และ fail-closed contract แล้ว แต่ live MySQL/server replay, alert budget และ exact rollback target ยังไม่ผ่าน
- ยังไม่พร้อมอ้าง **automatic leak diagnosis** เพราะไม่มี technician-confirmed labels และ operating context ยังไม่ครบ
- การใช้กับช่างต้องอยู่ในรูป Watch/Investigate พร้อมหลักฐานและคำอธิบายอื่นที่เป็นไปได้

---

## 21. QA Loop Contract

“Loop Check” ในโครงการนี้หมายถึงการวนตรวจ QA ของระบบวิเคราะห์ เอกสาร และหลักฐานซ้ำ ไม่ใช่ชื่อ algorithm หรือข้อกำหนดให้สร้าง duplicate-detection subsystem ใหม่

ก่อนยืนยันผลหรือเลื่อน phase ต้องตรวจตามลำดับ:

1. **System QA:** อ่าน README และ SOT ใหม่ ตรวจ tag, CP1/CP2, SV/state และกติกา `Hp_2nd`
2. **Data QA:** reconcile source period, row/event grain, filters, counts, timezone, missingness และ exclusions กับ output จริง
3. **Model QA:** ตรวจ train-only fitting, time/group split, purge gap, HPO isolation, seed stability และ threshold calibration
4. **Evidence QA:** ทุก claim มี source/internal artifact แยก fact, inference และ provisional policy
5. **Presentation QA:** กราฟมีหน่วย จำนวนตัวอย่าง denominator uncertainty และ caveat; ไม่ใช้ correlation แทน cause
6. **Production QA:** shadow, latency, missing-data, restart, version mismatch, monitoring และ rollback
7. **Governance QA:** อัปเดต Project, AGENTS, SOT, Roadmap, UX, graft และ change log


---

## เอกสารหลักฐานและสถานะที่เกี่ยวข้อง

- [THESIS.md](THESIS.md) — เหตุผลเชิงวิจัย ผลวิเคราะห์ภายใน สมการ การเลือกโมเดล และแผนการทดลอง
- [HANDOFF.md](HANDOFF.md) — context snapshot สำหรับส่งต่อไปยัง Chat ใหม่; หากขัดกันให้ยึด README และ SOT
- [research/claim-to-source-ledger.md](research/claim-to-source-ledger.md) — แผนที่จากข้ออ้างสำคัญไปยังแหล่งอ้างอิง
- [SOT.md](SOT.md) — ตัวเลขที่ตรวจยืนยันแล้ว สถานะล่าสุด และข้อจำกัดของข้อมูล
- [Roadmap.md](Roadmap.md) — ลำดับการนำข้อกำหนดนี้ไปพัฒนาและทดสอบ
- [deployment/SYSTEM_DEPLOYMENT_FLOW.md](deployment/SYSTEM_DEPLOYMENT_FLOW.md) — Flowchart และคำอธิบายระบบ Shadow ที่จะนำไปติดตั้งบน Server
- [deployment/CODEX_SERVER_HANDOFF.md](deployment/CODEX_SERVER_HANDOFF.md) — คำสั่งรับช่วงสำหรับ Codex บน Server และ acceptance checklist
- [deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md](deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md) — ขอบเขตฐานข้อมูล Analytics แบบ append-only สำหรับ target Server ที่ระบุ; ไม่ใช่หลักฐานว่าเชื่อมต่อหรือ deploy แล้ว

หากเอกสารขัดกัน ให้ใช้ evidence hierarchy ในหัวข้อ 16 และบันทึกการแก้ไขใน Change Log ของเอกสารที่ได้รับผลกระทบ

---

## Change Log

- 2026-10-02 — Installed existing Reference job table in normal local analytics and fixed polling lease contention/error diagnosis. Detector/Data Contract/Active unchanged. Evidence: `deployment/REFERENCE_STORAGE_REPAIR_20261002.md`.

- 2026-10-02 — Added per-machine/module source-day preflight, explicit historical Shadow cutoff/reason and combined retained-Reference/qualified-Shadow Build readiness. Selection v2 only; no scorer/ML/Active/Server change. Evidence: `deployment/REFERENCE_AVAILABILITY_V2.md`.

- 2026-10-02 — Added manually reviewed Reference selection and complete-day historical Shadow to Operation Calibration, with durable job/source digest/atomic Candidate workflow, honest graph units and retained-coverage check. Local QA only; source semantics, selected scorer and Active approval unchanged. Evidence: `deployment/REFERENCE_REVIEW_WORKFLOW.md`.

- 2026-10-01 — Added Dashboard-owned manual incident/work reporting and downstream local Episode archive. Five qualified non-flag minutes confirm archive recovery; missing/manual/non-Cold context is UNKNOWN. Primary robust-z/persistence, physics semantics and Active Profiles are unchanged. Evidence: `deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md`.

- 2026-09-30 — Replayed the selected one-minute candidate/scorer on MX070/M6 and verified exact midpoint-checkpoint restart parity as local QA. This adds cross-machine testing evidence, not a new tag meaning, pressure threshold or Active Profile. Evidence: `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

- 2026-09-25 — Owner-directed documentation cleanup removed prescriptive restriction text from Markdown files. Technical definitions, measured results, code behavior and profile approval state were not changed by this edit.

- 2026-09-25 — Added a local-first rehearsal of the selected one-minute candidate and scorer on MX057/M1+M6 raw-second data. Both modules matched their future shadow graph point by point; M1's high flag burden remains for review. This changes testing workflow, not tag semantics, thresholds or Active Profiles. Evidence: `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.
- 2026-09-25 — Changed the selected candidate and shadow feature contract from five-minute to qualified observed-second/completed one-minute Cold windows at the owner's request. The existing Auto-Calibration lifecycle now creates versioned candidates and three-day graphs with explicit missing-minute gaps; old Active Profiles are incompatible. MX057/M6 local replay stayed `REVIEW_REQUIRED`, and live inference remains read-only preview. This is a methodology/cadence change, not a new tag fact or Server approval. Evidence: `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

- 2026-09-25 — Added a separate fail-closed observed-second → completed five-minute Cold window and strict-profile robust-z/persistence path with shadow-only EWMA/CUSUM research evidence. The historical raw-row mutating inference entry point is blocked by default; opt-in is read-only preview. This does not change tag semantics, establish an approved five-minute Active Profile, or authorize Server scoring/alerts. Contract and limitations: `deployment/QUALIFIED_5M_SHADOW_IMPLEMENTATION.md`.

- 2026-09-25 — Recorded owner selection of Active-Profile Self/robust-z plus persistence as the sole current anomaly-scoring method. ARX/peer/other detectors remain research-only, and current raw-row runtime gaps prevent a five-minute production claim. No tag semantics, pressure rule, profile approval or Server activation changed. See `deployment/RULE_ONLY_ACTIVE_PROFILE_PIPELINE.md`.

- 2026-09-25 — Reviewed the matched frozen Self/robust-z versus Cold ARX v2 replay under this Data Contract. It changes no tag, state, pressure, model or approval semantics; inspected outer/MX080 evidence remains descriptive and cannot select a release. See `notebooks/outputs/ht9046mx_rule_arx_matched_v1/README.md`.

- 2026-09-24 — A past-only Cold profile QA found persistent local Self deviations and original-second manual markers. This does not alter tag semantics, prove intervention/causality or authorize automatic profile re-basing; the existing approval and fresh-holdout gates remain in force. See `notebooks/outputs/ht9046mx_cold_past_profile_audit_v1/README.md`.


- 2026-09-15 — Added pressure-differential relationship evidence (`dp1=Hp_1st−Lp_1st`, `dp2=Hp_2nd−Lp_2nd`) to the next candidate-calibration/model contract. A persistent within-state relationship shift is an `ANOMALOUS_OPERATING_PATTERN` and must be excluded from normal baseline; it may open an anomaly review, but it does not name a root cause. This invalidates reuse of the hp180 threshold/model for the new contract and requires retraining/recalibration plus temporal/LOMO/shadow validation.
- 2026-09-15 — Owner confirmed `Status` as Compressor ON/OFF, `Busy=1` as manual/service operation (including MValveHome/ChangeValve), and `SV=ON` as Compressor-not-running Hot/post-Cold bypass context. The candidate worker now admits only Compressor-ON, Busy=0, SV=OFF Cold windows; SV-ON baseline creation is intentionally unsupported pending a dedicated state rule. This is a state-contract/version change, not a model retrain, profile approval, diagnosis or deployment result.
- 2026-09-15 — Added the Server-ready automatic calibration candidate contract: read-only historical MySQL intake, machine–module–SV–state robust profile, future-only 3-day shadow graph and transactional human approval. Approval remains human-gated; no live Server/database run, model retrain or fault claim occurred.
- 2026-09-15 — Live prospective confirmation now fails closed until the IANA timezone for the `DATETIME(6)` alert timestamp is explicitly configured; this prevents an unverified clock policy from admitting historical labels. No score, percentage, cause output or release state changed.
- 2026-09-15 — Replaced the Phase 8 cause-capture proposal with a prospective binary technician-confirmation contract. Only new alerts after a configured boundary may receive `EQUIPMENT_ANOMALY`, `NO_EQUIPMENT_ANOMALY` or `UNRESOLVED`; no cause is collected or modeled. No current release, profile, threshold or deployment state changed.

- 2026-09-15 — Added the methodology-only Four-evidence contract (`Self`, `Dynamic`, `Peer`, `Temporal`) and independent peer-screening rules from the improved system architecture. No data split, profile, model, threshold, deployment status or diagnostic claim changed.

- 2026-09-14 — Updated the repository handoff reference to `Bookkapp/CompressorML_and_AutomaticCalibration`. No system semantics, pressure rule, model, threshold or deployment authorization changed.

- 2026-09-14 — Reviewed after implementing the five-minute FastAPI/React shadow application and technician-review contract. No tag semantics, pressure rule, model, threshold, Health Score or production authorization changed.

- 2026-09-14 — Added the owner-specified `10.195.17.73` append-only analytics-database deployment guide as a companion to the Server handoff. No system semantics, model, profile activation or live deployment status changed.

- 2026-09-11 — Added the curated Codex Server handoff and repository boundary. Raw telemetry/intermediate artifacts remain outside GitHub; the current model/profile/parity package is retained without changing system semantics.

- 2026-09-11 — Clarified the intended local-calibration → relative features → cross-machine Fleet model → anomaly/persistence → provisional health view → technician-label → future classification architecture. No Health Score or cause classifier is claimed as currently validated.

- 2026-09-11 — Added the logical Server deployment flow as an explanatory companion. System semantics, model/threshold versions and the no-PLC-write/no-auto-activation boundaries remain unchanged.


- 2026-09-10 — Recorded Phase 7 offline shadow-replay evidence and retained the production boundary: live MySQL/server, approved alert budget and exact rollback target are still required; no system tag or diagnostic rule changed.

- 2026-09-10 — ยืนยันชื่อรุ่นเป็น HONTECH HT9046-MX (คง `HT-9046MX` เป็น legacy/file alias) และเพิ่ม evidence-controlled caveat ว่า `Busy_n` ยังใช้ยืนยัน compressor run state ไม่ได้ จาก MX-080 Module 6 one-second forensic; ไม่ได้เปลี่ยน tag mapping หรือกฎ alarm

- 2026-09-10 — Reviewed after external one-second coverage checkpoint; response-coverage insufficiency does not alter tag semantics, system rules, pressure screening or activation guardrails.

- 2026-09-10 — Reviewed after executed external intake v2. The relaxed 55–60 sample, ≤5-second-gap rule is explicitly EDA-only; no system tag semantics, pressure rule, baseline approval or ML threshold changed.

- 2026-09-09 — Reviewed external MX intake: source pressure scale, timezone uncertainty, machine/module/SV boundaries and service-epoch rules retained; no tag semantics or 200 psi rule changed

- 2026-09-08 — Reviewed against executed Phase 06 Auto-bootstrap notebook; no tag, pressure rule or system semantics changed, and the 3-day shadow gate remains an implementation policy below this system contract
- 2026-09-08 — แยกความหมาย Auto-bootstrap, block bootstrap, model bagging และ AutoML/HPO; เพิ่ม nested selection policy, production-readiness verdict และ QA Loop Contract จาก Deep Research ฉบับขยาย
- 2026-09-08 — ยืนยันว่า Loop Check ในบริบทโครงการหมายถึง repeated QA review ไม่ใช่ระบบตรวจ duplicate ใหม่
- 2026-09-08 — เพิ่ม evidence hierarchy, result semantics, hybrid model architecture, dual-rate features, Auto-bootstrap lifecycle, contamination protection, validation/uncertainty contract, production change control และทางเชื่อมไปยังเอกสารหลักฐานจากผล Deep Research และผลวิเคราะห์ภายในโปรเจกต์
- 2026-09-08 — เชื่อม `HANDOFF.md` สำหรับส่งต่อบริบท โดยคง README และ SOT เป็น Source of Truth

- 2026-09-24 — Prepared the separate `_v1` repository snapshot and documented the exact schema ownership, five-minute data flow, approval/rollback boundary and current live runtime provenance mismatch. No tag semantics, profile activation, production deployment or model approval changed.
