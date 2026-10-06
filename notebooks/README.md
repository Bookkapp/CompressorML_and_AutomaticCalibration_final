## Notebook13 — Fleet Stable v1 portable Shadow

`15_Frozen_Context_Scenarios_20261006.ipynb`: executed17case synthetic diagnostic companion using saved frozen MX058/M1 and MX017/M1 inputs. Category/receipt rerun parity, visual comparison and approval-provenance rejection. No source insertion or new Mock UI. Evidence `deployment/FROZEN_CONTEXT_SCENARIOS_UAT_20261006.md`.

6Oct software QA companion: `support/context_followup_qa.py` checks actual localhost metadata concurrency and frozen registry invariance; outputs in `outputs/context_followup_20261006/`. This is workflow QA, not a new model-fitting research study. Runbook: `deployment/CONTEXT_FOLLOWUP_PROGRESS_UAT_20261006.md`.

`13_Fleet_Stable_v1_Portable_Shadow_20261006.ipynb`: executed frozen-package/curation/coverage/CP2-case/portability/performance companion. Builders accept explicit future training plans and produce new immutable versions. Private raw/evidence/model output stays in controlled local storage. Installation and open gates: `deployment/FLEET_STABLE_V1_RUNBOOK_20261006.md`.

# HT9046MX Notebook Guide

**5 Oct — Fleet Reference / selective transfer delivered:** Executed `11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb` (six code cells/one source-backed case figure) audits555committed dynamic day files for017/024/041/058/080/081, observed quality/control coverage, held-out sparse transfer, SV/Valve censoring and080/M6frozen-level regression. Companion support commands are read-only for source/registry and create only local derivative/research outputs. Private ZIP/receipts/day partitions are needed and not published; the notebook does not silently refit on open. Report: `../deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md`.

**Latest — Notebook 08M:** `08M_Historical_Shadow_Reference_and_Phase_Comparison_Colab.ipynb` compares4past-reference selectors and3complete historical shadow days across9machines/all8modules. Executed11cells/9figures: splits, reference support, burden+coverage, MX080 mixed baseline, phase attribution, actual-second observed starts and two known-case panels. All-supported rows still scored; no startup suppression/Active/runtime/Server change. Full cached-input rebuild is optional `RUN_EXPERIMENT=True`; private08K/08Lcaches/supports required on Colab. See `../deployment/HISTORICAL_SHADOW_REFERENCE_PHASE_EXPERIMENT_20261001.md` for findings, actual per-machine cutoffs, failed segment support and unresolved early warning.

**Latest — Notebook 08L:** `08L_Local_Calibration_and_Model_Selection_Colab.ipynb` is an executed companion to the nine-machine local trial: local reference/readiness, baseline/correlation, Self vs ARX/DPCA/IF, adapted LOMO, known-case regression and actual-second contributor/control panels. 11 code cells, 8 figures; model training was executed separately by the reproducible support command, not automatically rerun on every notebook open. Local results/support files are required on Colab; raw/model/cache outputs are not assumed to be in Git. Primary remains frozen Self/persistence; no Active/Server change. Read `../deployment/LOCAL_PROFILE_MODEL_SELECTION_20261001.md` for exact sources, model-fit machines, splits and limitations.

**1 Oct — Notebook 08K:** `08K_Three_Machine_Raw_Second_AutoCalibration_Review.ipynb` reviews the new MX017/024/080 July–October ZIPs: quality, local baseline, daily level shifts, conditional correlations, raw-second Run trajectories and causal 3-day lookback sensitivity. Static excluded; seven saved figures, 23,347,480 raw rows; no Active/DB/Server mutation or healthy-label/accuracy claim. Requires the two `support/october_*` scripts plus local outputs or original ZIPs for rerun. Detailed recommendation: `../deployment/THREE_MACHINE_AUTOCALIBRATION_REVIEW.md`.

**Updated:** 2026-09-16
**Recommended entry point:** `00_HT9046MX_Notebook_Navigator_Colab.ipynb`

เอกสารนี้เป็นสารบัญสำหรับเปิด notebook ให้ถูกลำดับ โดยไม่ต้องเดาจากชื่อไฟล์ ทุกเล่มถูกบันทึกพร้อมผลการรันแล้ว และยังสามารถรันใหม่บน Google Colab จากต้นจนจบได้

## เส้นเรื่องสำหรับอ่านและพรีเซนต์

| ลำดับ | คำถามที่ตอบ | Notebook |
|---:|---|---|
| 00 | มี notebook อะไรบ้าง และควรเริ่มตรงไหน | `00_HT9046MX_Notebook_Navigator_Colab.ipynb` |
| 00A | สรุปสถานะและหลักฐานทั้งโปรเจกต์ในเล่มเดียว | `00A_HT9046MX_Project_Master_Summary_Colab.ipynb` |
| 00B | อธิบายที่มาของเครื่อง, split, baseline, สมการ, model, calibration และ Server workflow ตั้งแต่ระดับเริ่มต้นถึงเชิงเทคนิค | `00B_HT9046MX_System_Story_Colab.ipynb` |
| 01 | ข้อมูลครอบคลุมกี่เครื่อง กี่วัน และเชื่อถือได้แค่ไหน | `HT9046MX_State_Aware_Baseline_Analysis.ipynb` |
| 02 | baseline ของแต่ละเครื่อง–โมดูล–SV เท่ากันหรือไม่ | `HT9046MX_Visual_Analysis_Colab.ipynb` |
| 03 | เมื่อแปลงเป็น relative features แล้ว transfer ข้ามเครื่องได้แค่ไหน | `HT9046MX_ML_Calibration_LOMO.ipynb` |
| Story | เล่า Data Analysis ถึง ML เป็นขั้นตอนสำหรับพรีเซนต์ | `HT9046MX_Data_Analysis_to_ML_Phased_Colab.ipynb` |
| 07C checkpoint | ข้อมูลเพิ่มเติมช่วย coverage ของ one-second opening/closing ได้แค่ไหน | `07C_HT9046MX_External_OneSecond_Coverage_Colab.ipynb` |

## วิธีใช้แบบสั้น

1. เปิด Navigator ก่อน เพื่อเลือกเส้นเรื่องตามผู้ฟัง
2. สำหรับพรีเซนต์ภาพรวม ใช้ Story notebook แล้วเปิด Phase 06 เป็นภาคต่อด้าน calibration lifecycle
3. สำหรับตรวจวิธีคำนวณ ให้เปิด notebook ของ phase นั้นโดยตรง
4. ทุกครั้งที่พูดถึง alert rate ต้องพูด denominator, state coverage และข้อจำกัดว่าไม่มี confirmed fault labels
5. `Hp_2nd = 180–230 psi` เป็น qualified field reference; `<180 psi` เป็นหลักฐานคัดกรองด้านต่ำ และ `>230 psi` เป็น high-side investigation แยกกัน โดยไม่มีค่าใดยืนยันสาเหตุเพียงลำพัง

## สถานะ notebook

- Notebook หลัก 8 เล่มผ่าน execution QA เดิม และ Notebook checkpoint 07B/07C/07D ถูกบันทึกพร้อมผลการรัน; inventory ล่าสุดตรวจทุก `.ipynb` ในโฟลเดอร์
- Phase 06 สร้าง candidate profile 262 รายการ: 39 อยู่ `SHADOW_VALIDATION`, 3 อยู่ `CANDIDATE_PROFILE`, 66 ต้อง `REVIEW_REQUIRED` และ 154 เป็น `INSUFFICIENT_DATA`; ไม่มีรายการใดเปิดใช้เอง
- ผลสูงสุดของ Phase 06 ในรอบนี้คือ `SHADOW_VALIDATION`; ยังไม่มี `READY_FOR_APPROVAL` หรือ `ACTIVE_FROZEN`
- Event-response ทั้ง 524 strata ยังเป็น `INSUFFICIENT_COVERAGE` เมื่อแยก machine–module–SV–direction ตาม provisional gate
- Notebook 07D v2/hp180 รันครบ 11/11 code cells ไม่มี error; เพิ่ม 180–230 psi band และ water-keyword audit โดยไม่เปลี่ยน training/approval state
- Notebook 07 รัน deterministic shadow replay รุ่น hp180 ด้วย ARX-Ridge ที่ล็อกจาก inner validation; production status ยังเป็น `SHADOW_ONLY_NOT_AUTHORIZED`

ผล QA ที่อ่านโดยระบบได้อยู่ใน `outputs/notebook_qa/notebook_qa_summary.json` และ inventory อยู่ใน `outputs/notebook_qa/notebook_execution_inventory.csv`.
รอบล่าสุดวันที่ 2026-09-10 ผ่าน 27/27 checks แบบ `PASS_WITH_CAVEATS` รวม Phase 06 hp180 candidate/feature version, Phase 7 hp180 version/contract และ MX-080 water-log QA.

## Naming policy ต่อจากนี้

- Notebook ใหม่ใช้เลข phase นำหน้าเมื่อเป็นงานใน roadmap โดยตรง เช่น `07_..._Server_Replay_Colab.ipynb`
- Notebook ที่เป็นเส้นเรื่องรวมให้ใช้คำว่า `Story` หรือ `Navigator` ในชื่อ
- ไม่เปลี่ยนชื่อ notebook เดิมย้อนหลัง เพราะไฟล์เหล่านั้นเป็น evidence artifact ที่ถูกอ้างถึงในเอกสารและ output แล้ว; ใช้ Navigator เป็นชั้นจัดระเบียบแทน

## Change log

- 2026-09-16 — Added executed Notebook 00B as the detailed teaching/presentation entry point. It documents all 19 benchmark-machine roles, temporal/LOMO split mechanics, implementation-faithful equations, selected parameters and ten slide-ready figures without changing any model/profile state.
- 2026-09-10 — Regenerated external intake v2 and reran Notebook 07B so the current daily artifact uses `hp2_below_180_pct`; source/overlap counts are unchanged.

- 2026-09-10 — Rebuilt Phase 06 with explicit `autobootstrap-candidate-v2-hp180` / `minute-state-core-hp180-v2` identifiers and raised notebook-suite QA to 27/27 checks.

- 2026-09-10 — Migrated Notebook 07/07D and affected notebook builders to the 180–230 psi reference contract; hp180 outputs are versioned separately from historical 200-psi artifacts.

- 2026-09-10 — Added and executed Phase 07 server shadow replay notebook with portable model export, causal persistence, failure-mode QA, ring-buffer features and MX-080 incident probe.

- 2026-09-10 — Added and executed Notebook 07D for MX-080 Module 6 exact-second incident forensics, with four QA-reviewed figures and non-causal interpretation.

- 2026-09-10 — Added and executed Notebook 07C external one-second event-coverage checkpoint; no response context passed its coverage gate.

- 2026-09-10 — Executed Notebook 07B without cell errors against external intake v2; figures and notebook QA are available under its versioned output folder.

- 2026-09-09 — Added Notebook 07B external intake companion and `EXTERNAL_DATASET_INTAKE.md`; phase numbers in the Roadmap remain unchanged

- 2026-09-08 — เพิ่ม Navigator, Phase 06 Auto-bootstrap, naming policy และตำแหน่ง QA artifact

**Notebook12 — MX080/M6 CP2/control episode review (5Oct):** Executed `12_MX080_M6_Control_and_CP2_Episode_Review_20261005.ipynb`,24days/10raw source checks, CP2-led episode/equalization/acquisition-suspect evidence. No filling/leak label, model or Active change.

## 6 October: Fleet Transition, Worker and Management

Executed `14_Fleet_Transition_Worker_Management_20261006.ipynb` verifies event separation, frozen model values, actual-source isolated persistence, saved Shadow burden and HTTP/retraining receipts. Reproduction/evidence: `support/fleet_workflow_qa.py`, `support/fleet_workflow_delivery.py`, `outputs/fleet_workflow_20261006/`. See `deployment/FLEET_WORKFLOW_UAT_20261006.md`; historical flag burden is not certified healthy false-positive accuracy.
