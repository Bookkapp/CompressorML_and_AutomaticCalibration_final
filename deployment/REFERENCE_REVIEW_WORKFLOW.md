# เลือกช่วง Reference ก่อนสร้าง Calibration Profile

**3 Oct update:** Automatic preparation now uses the same completed-day selection/fit as this Manual workflow. The main UI prepares allM1–M8, then opens saved reviewer-owned graph evidence for per-module exceptions. Source-day availability is optional; one-hour CLOSED-day snapshots speed Preview/detail, while Manual Build rereads current raw seconds and checks SHA256. Read `AUTOMATIC_CALIBRATION_UAT_20261003.md`; prior descriptions requiring inventory before every Preview are superseded. No automatic Active approval or healthy-reference certification is added.

**Local storage repair — 2 Oct:** Normal API8000 analytics lacked the job migration; installed existing18-column table and fixed polling range-UPDATE1213 contention. Storage errors now distinguish missing table/schema mismatch/transient busy/connection.147tests/build and100concurrent actual-MySQL polls pass without Profile/Active change. Details/recovery/Server caveats: `REFERENCE_STORAGE_REPAIR_20261002.md`. CREATE IF NOT EXISTS does not repair incompatible existing columns.

**Latest amendment — 2 Oct:** Workflow now uses `manual-reference-complete-day-shadow-v2`. Read `REFERENCE_AVAILABILITY_V2.md`: per-machine/module source-day inventory before Preview; coverage-only suggestions chosen explicitly with historical cutoff/reason; Build requires retained Reference AND all3 qualified Shadow days/minimum minutes. Source_latest stays actual; old pending v1 jobs require re-preview. The original v1 checkpoint below describes initial implementation; default cutoff/formulas/Active approval remain unchanged. GET availability adds no migration or source write.

เริ่มพัฒนา 1 ตุลาคม 2026 · ตรวจ QA/เอกสารล่าสุด 2 ตุลาคม 2026 · รุ่นวิธีเลือกข้อมูล `manual-reference-complete-day-shadow-v1`

## สิ่งที่เพิ่ม และสิ่งที่ยังเหมือนเดิม

เพิ่มขั้นตอนให้ผู้ดูแล **เห็นข้อมูลและยืนยันช่วงอ้างอิงก่อนคำนวณ Candidate** ในหน้า Calibration ของ Operation เดิม ไม่เพิ่มระบบให้ช่างต้องใช้อีกชุด ไม่เปลี่ยน scorer, Active Profile, Alert หรือ Dashboard งานประจำวัน

ลำดับการใช้งาน:

```text
เลือกเครื่อง → เลือกโมดูล → ระบบเสนอ Reference
                         ↓
ดูกราฟ / ความครอบคลุม / ปรับวันหรือยกเว้นช่วงพร้อมเหตุผล
                         ↓
ยืนยันช่วงและบันทึกการทบทวน
                         ↓
ตรวจ source-feature digest และ policy ซ้ำ
                         ↓
สร้าง Candidate + Shadow ย้อนหลังสามวันเต็ม (ไม่ใช้ Fit)
                         ↓
อ่านผลและ reason codes → ผ่านเกณฑ์จึงอนุมัติ Active แยกอีกครั้ง
```

การยืนยัน Reference ไม่ใช่การยืนยันว่าเครื่องไม่เสีย และไม่ใช่ Approval ของ Active Profile. ระบบไม่เปลี่ยนช่วงที่ผิดปกติให้เป็น normal เพราะผู้ใช้พิมพ์หมายเหตุ ไม่มีการ retrain ARX/IF/LSTM หรือเพิ่มคะแนนความมั่นใจในรอบนี้

## วิธีใช้สำหรับผู้ดูแล

1. เปิด **Calibration** เลือกเครื่องจากรายการข้อมูลต้นทาง แล้วเลือก Module ที่ต้องการ ระบบทำทีละเครื่อง–โมดูล เพราะแต่ละโมดูลอาจต้องใช้คนละช่วงอ้างอิง
2. ใส่รหัสผู้ทบทวน แล้วกด **ดูกราฟและตรวจช่วงข้อมูล**. เว้นวันที่ทั้งสองช่องให้ระบบเสนอ 28 วันก่อน Shadow หรือกรอกวันเริ่มและวันสิ้นสุดเอง วันสิ้นสุดเป็นวันแรกที่ *ไม่ใช้* เช่น ต้องการใช้ถึง 4 ก.ย. ให้ใส่วันสิ้นสุด 5 ก.ย.
3. อ่านบัตร Reference และ Shadow ก่อน กราฟ Hp/Lp ใช้คนละสเกล; สลับดู CP1, CP2, temperature, Valve และ pressure differential ได้ ภาพรวมใช้มัธยฐานรายชั่วโมงและช่วง min–max ของค่าเฉลี่ยนาทีจริง ไม่ใช่ค่าดิบรายวินาที
4. เลือก **ความละเอียดกราฟ → วันที่ที่ต้องการ / ราย 1 นาที** เมื่อเห็นช่วงเปลี่ยนแปลง ระบบอ่านเพียงวันนั้น ตรวจ digest ของวันนั้นก่อนแสดงผล ไม่เติมช่องว่างและไม่ให้ค่าปกติแทนช่วง Manual/State/Gap ที่ไม่มี feature ผ่าน Gate
5. เปิดตารางรายวัน ตรวจนาทีที่มีข้อมูล นาทีที่ผ่าน Gate นาทีที่ใช้ Reference และนาทีที่ขาดหาย. `qualified` แปลว่าประเมินในบริบท Cold ได้ ไม่ใช่ healthy label
6. หากทราบว่าบางช่วงไม่ควรใช้ Fit ให้เพิ่ม **ช่วงยกเว้น** พร้อมเวลาเริ่ม–จบและเหตุผล หรือกดย้อนกลับปรับวัน. ข้อมูลต้นทางไม่ถูกลบ ช่วงยกเว้นมีผลกับ Reference เท่านั้น ห้ามใช้ช่วงยกเว้นเปลี่ยนชุด Shadow
7. ยืนยันว่าอ่านกราฟแล้วและกรอกบันทึกการทบทวน จากนั้นกด **ยืนยันช่วงและสร้าง Candidate + Shadow**. หากข้อมูลไม่พอหลังยกเว้น/Quarantine ปุ่มจะไม่เปิดให้สร้าง
8. เมื่อเสร็จ ดู Candidate ในรอบที่สร้าง กราฟ Shadow และ reason codes. `REVIEW_REQUIRED` ต้องทบทวน ไม่ใช่กดอนุมัติด้วยการเติมหมายเหตุ. `INSUFFICIENT_DATA` ต้องหา Reference ที่มีข้อมูลเพียงพอ. เฉพาะ Candidate ที่ผ่าน Approval gate เดิมเท่านั้นจึงเปิดใช้ได้

สีในกราฟ Reference มีความหมายเฉพาะ: **เทา = ไม่ใช้ Fit; ม่วง = Shadow** ไม่ใช่สีปกติ/เสีย. การอนุมัติทั้งเครื่องยังใช้ได้เฉพาะรอบเดิมที่มีแปดโมดูลผ่านเกณฑ์พร้อมกัน; รอบทบทวนใหม่มีหนึ่งโมดูล ให้ตรวจและอนุมัติเป็นรายโมดูล

## การแบ่งเวลาและ Data Gate

Timestamp ที่เลือกเป็น source-local ตาม `HT9046MX_SOURCE_TIMEZONE`; job timestamps เก็บเป็น UTC. ขอบเขตเป็น `[start,end)` ทั้งหมด ช่วงยกเว้นต้องตรงนาที อยู่ภายใน Reference มีเหตุผล และไม่ทับกัน

```text
latest source time ของเครื่องนั้น − late-arrival grace
       ↓ ปัดลงเที่ยงคืนตาม source timezone
Shadow end (exclusive)
Shadow start = Shadow end − 3 วัน
Reference default = [Shadow start − 28 วัน, Shadow start)
```

ตัวอย่างข้อมูลล่าสุด 8 ก.ย. เวลา 12:00: Shadow คือ 5–7 ก.ย. ไม่ใช้ 8 ก.ย.; Reference เริ่ม 8 ส.ค. และจบก่อน 5 ก.ย. ผู้ใช้เลือก Reference ให้จบเร็วกว่านั้นได้ ช่องว่างระหว่าง Reference end กับ Shadow start ไม่ใช้ Fit. Lookback จำกัดไม่เกิน 90 วันก่อน Shadow. ใกล้เที่ยงคืน grace อาจเลื่อน cutoff อีกหนึ่งวันเพื่อไม่รับวันซึ่งยังไม่ปิดครบ

Shadow เป็น **retrospective holdout** ที่ไม่ซ้ำ Reference ไม่ใช่ blind test และไม่พิสูจน์ความแม่นยำหากเคยสำรวจช่วงนั้นแล้ว. การปรับ Reference หลังเห็น Shadow ต้องบันทึกเป็นการทบทวนย้อนหลัง ไม่อ้างผลเป็น validation อิสระ ไม่ใช้ shadow flag rate เป็น FPR เมื่อไม่มี confirmed healthy negatives

Server reader เดิมอ่าน source MySQL ทีละวันด้วย SELECT และสร้าง completed minute จากวินาทีจริง: ≥57 occupied second bins/60, ไม่มี duplicate second, gap ≤5 s; global Run, module On, Busy ปกติ, SV Off, sensor finite, Valve ≥0. Control/manual rows ยังอยู่ใน source แม้ไม่ใช้ Fit steady Cold. Busy ไม่ถูกเปลี่ยนเป็นหลักฐานไฟฟ้า compressor-run และ SV ไม่ใช้สรุป Hot/Room

## วิธีคำนวณ Candidate

ใช้ estimator และ threshold policy เดิมจาก `qualified_calibration.py` / `qualified_candidate_registry.py`:

\[
m_j=\mathrm{median}(x_j),\quad s_j=\max(1.4826\,MAD_j,IQR_j/1.349,f_j)
\]

\[
A_t=\max_j|(x_{tj}-m_j)/s_j|,\qquad \tau=Q_{0.995}(A_t\text{ จาก retained Reference})
\]

Features: Hp1/Lp1/Hp2/Lp2/Valve/TempHi/TempLo และ Hp1−Lp1, Hp2−Lp2. Floor Valve=1 count; อื่น .1 source unit. Fit รอบแรก → quarantine `A>8` → Fit รอบสอง → Q99.5 ของ retained fit. Shadow ไม่มีส่วนในการ Fit median/scale/threshold. หลักฐาน persistence ยังเป็น `A≥τ` สามนาที qualified ที่ติดกันจริง; นาทีที่ขาด/ไม่ผ่านจะตัดความต่อเนื่อง

ค่าขั้นต่ำมาจาก config (ค่าแนะนำ/ค่า QA: Reference ≥7 วัน/200 นาที, Shadow ≥3 วัน/200 นาที); เพิ่มตรวจจำนวน retained Reference หลัง quarantine ใน workflow นี้ หากไม่พอให้ `INSUFFICIENT_RETAINED_REFERENCE_COVERAGE` ไม่เปลี่ยนสูตรคะแนน. Drift/quarantine/shadow/observed-coverage และ source-unit/codebook/service-context gates เดิมยังอยู่. รหัสวิธีเลือกข้อมูลใหม่ไม่ใช่ algorithm/threshold รุ่นใหม่

## โค้ด / ตาราง / API

| ส่วน | ที่อยู่ / หน้าที่ |
|---|---|
| Selection / preview / digest / minute detail | `apps/api/app/reference_review.py` |
| Durable queue / lease / idempotency / atomic completion | `apps/api/app/reference_jobs.py` |
| อ่าน source seconds ทีละวัน | `qualified_calibration.py::load_observed_one_minute_windows` เพิ่ม progress callback แบบ optional; caller เดิมเหมือนเดิม |
| Candidate / Shadow | `qualified_candidate_registry.py` เดิม ผ่าน selection wrapper |
| Atomic registry write | `calibration.py::persist_batch(transaction=...,reference_review=...)`; caller เดิมยังทำ transaction ของตัวเอง |
| UI | `apps/web/src/components/ReferenceReview.tsx`, CSS, `styles.css` responsive layout และหน้า Calibration ใน `App.tsx` |
| Migration | `deployment/mysql_reference_review.sql` เพิ่มเฉพาะ analytics job table |
| Local rehearsal | `notebooks/support/reference_review_local_qa.py`, development-only `reference-review-qa.html` |

- `POST /api/v1/calibration/reference/preview` → HTTP 202, durable job ID
- `GET /api/v1/calibration/reference/jobs/{id}` → progress / preview / result / error
- `GET /api/v1/calibration/reference/jobs/{id}/day?day=YYYY-MM-DD` → bounded one-day minute-detail read
- `POST /api/v1/calibration/reference/jobs/{id}/build` → HTTP 202, Candidate + stored Shadow (ไม่ Active)

ทั้งหมดใช้ `X-Approver-Id` สำหรับ reviewer identity ตามสัญญาเดิม. Header ที่พิมพ์เอง **ไม่ใช่ authentication**: ก่อนใช้งานจริงให้ผูก identity/role จาก authenticated reverse proxy หรือระบบ login และป้องกันการปลอม header. API schema ปฏิเสธ fields ที่ไม่รองรับ. ไม่มี endpoint อนุมัติใหม่ ไม่มี source write

Job เก็บ request, selection/policy version, reviewer, exclusions/reasons, source-feature digest, preview, result/batch ID, error และ UTC timestamps ใน `ht9046mx_reference_review_job`. Selection/notes/digest อยู่ใน batch manifest และ profile validation JSON ด้วย ไม่ต้องเพิ่มคอลัมน์ในตาราง Profile เดิม. Digest ครอบคลุม **model-input minute features และ quality/state/window metadata** ไม่ใช่ hash ของ raw source ทุก byte

## เสถียรภาพ / การกดซ้ำ / การหยุดกลางทาง

- Queue จำกัดสี่งานที่ยังรัน; หนึ่ง source-reading worker ต่อ API process. MySQL admission lock ป้องกัน admission race ข้าม process และถือจน transaction commit จึงปล่อย
- คำขอ Preview มี idempotency key. Key เดิมกับ actor/input เดิมได้ job เดิม; key เดิมแต่ input ต่างตอบ 409. UI disable ระหว่างงานและรอผลผ่าน polling ไม่ค้าง HTTP อ่าน telemetry หนึ่งเดือน
- Build ใช้ job/digest/note เดิมกดซ้ำได้ แต่เปลี่ยน note หลัง submit ต้องเป็นการทบทวนรอบใหม่. Candidate และ job COMPLETED commit ใน transaction เดียวกัน ไม่มี completed job ที่ไม่มี Candidate และไม่มี Candidate ซ้ำจาก retry ของ job เดิม
- Lease ต่ออายุเมื่ออ่านวันใหม่ (15 นาที); queue deadline สองชั่วโมง. ถ้าหยุด process/restart งาน RUNNING ที่ lease หมดจะเป็น FAILED ให้เริ่ม Preview ใหม่ ไม่อนุมัติหรือ retry build แบบเงียบ ๆ. QUEUED dispatch ต่อเมื่อ poll ได้
- UI เก็บ job ID/reviewer/draft ใน localStorage เพื่อกลับมาติดตามหลัง refresh; ไม่มี credential/token ในค่าที่เพิ่มนี้. ล้าง/ปรับ draft แล้วต้อง Preview ใหม่ ห้ามนำผลกราฟเก่ามายืนยันช่วงใหม่
- ก่อน Build อ่านชุดเดิมซ้ำแล้วตรวจ digest และ policy. ข้อมูลเพิ่ม/แก้ในอดีตที่เปลี่ยน input → `SOURCE_CHANGED_REVIEW_AGAIN`; policy เปลี่ยน → `POLICY_CHANGED_REVIEW_AGAIN`. ข้อมูลสดหลัง cutoff ไม่มีผลกับ frozen selection นี้
- Preview หมดอายุ 24 ชั่วโมงเมื่อ submit Build; กราฟวันเดียวต้องตรง digest ที่ทบทวนไว้ด้วย. Data missing/unknown คงเป็น null ไม่ Normal/0

Idempotency อยู่ในระดับ *job* ไม่ใช่ deduplicate ทุก Candidate ที่ผู้ใช้ตั้งใจสร้างคนละรอบ. ระบบยังไม่ใช่ distributed task broker และไม่ควรอ้างว่าไม่มีปัญหาเมื่อ deploy จนผ่าน Server acceptance

`POST /calibration/run` และ CLI/scheduler ของ rolling calibration เดิมยังอยู่ และไม่ได้รับ date/exclusion review จาก UI ใหม่นี้โดยอัตโนมัติ. ระบบใหม่เป็นช่องทาง manual administration รายโมดูล ไม่เปลี่ยนทุก background route หรือเปิด auto-approval. หากต้องการให้ทุก Candidate ใช้ Reference ที่คนเลือก ต้องออกแบบการใช้ approved selection กับ scheduler เป็นงานแยก

## เตรียมใช้งานบน Server (ยังไม่ได้รันจริงในรอบนี้)

1. สำรอง analytics metadata; source credential ต้องเป็น SELECT role แยกจาก analytics write role. ตรวจ timezone, pressure units, controller/state/service context version และ index `(machine_number, recorded_at)` ของ source
2. ใช้ registry schema เดิมให้พร้อมก่อน แล้ว apply `deployment/mysql_reference_review.sql` ใน **analytics schema เท่านั้น**. Application ไม่ auto-create table; migration หายจะตอบข้อความแก้ไขได้ ไม่ fallback เป็น normal
3. ใช้ `HT9046MX_PROFILE_WINDOW_CONTRACT=qualified_observed_1m`, `HT9046MX_PROFILE_SHADOW_DAYS=3`, config ของ observed-second gates/versions เดิม. ไม่มี cron/scheduler/automatic activation ที่เพิ่มจาก workflow นี้
4. Deploy backend + frontend build ตาม runbook เดิม. Worker scoring เดิมเป็นคนละ process/หน้าที่. ห้ามใช้ QA script เป็น source adapter ของ production: script นั้นอ่าน cache และบล็อก Approval/Alert ทั้งหมด
5. ตรวจหน้า Calibration: ข้อมูลไม่พอ, มี gaps, ปรับช่วง/เหตุผล, refresh กลางงาน, network retry, late source commit, rollback เมื่อ persistence ล้ม, identity/authorization และ worker capacity
6. ผู้มีสิทธิ์ค่อยทบทวน/Approval จริงผ่าน gate เดิม แล้วตรวจ Active loader และ source→scoring parity บน Server แยกอีกครั้ง. รอบนี้ไม่ติดตั้ง Server, ไม่แตะ Active registry จริง, ไม่ส่ง Alert และไม่ Push Git

## หลักฐาน QA บนคอมเครื่องนี้

- Operation Python suite **106 tests pass** รวม 26 reference tests: split/timezone/grace, leakage, original estimator parity, exclusion/retained minima, null gaps, digest, access, queue, duplicate retry, transaction rollback, policy-change conflict และ minute detail. SQLite test adapter มี Python3.12 deprecation warnings 200 รายการ ไม่ใช่ failure; MySQL rehearsal ใช้ driver จริง
- `npm run build` ผ่าน. ยังมี warning bundle ขนาด >500 KB ของ app เดิม ไม่ได้อ้างว่าลด bundle หรือผ่านโหลด Server แล้ว
- ใช้ archived MX080/M6 ที่ derived จากวินาทีจริง: cut 8 ก.ย. เที่ยง, Reference 8 ส.ค.–ก่อน 5 ก.ย., Shadow 5–7 ก.ย. พบ fit 22,367 นาที/21 observed qualified days; เหลือ 21,767 นาที/21 วันหลัง quarantine; Shadow 3,994 eligible minutes/3 วันจาก 4,320 calendar slots
- Local MySQL 8.0.46 schema แยก `ht9046mx_reference_review_qa_20261001`: concurrent Preview retries 16 ครั้งได้ job เดียว และ Build retries 16 ครั้งได้ Candidate เดียว/4,320 Shadow points. Inject failure หลัง insert registry จริงแต่ก่อน completion commit แล้วจำนวน batch/profile/shadow กลับเท่าเดิม และ job FAILED. สถานะ Candidate ที่สำเร็จ `REVIEW_REQUIRED`, Active count=0. เวลารอบ smoke รวม rollback rehearsal 23.74 s บน archived-cache adapter ไม่ใช่ throughput benchmark ของ Server SELECT หรือการ kill process จริง
- Receipt พร้อม source-cache SHA256: ignored `notebooks/outputs/reference_review_local_qa_v1/qa_receipt.json`; command `python -m notebooks.support.reference_review_local_qa`. ไม่มี synthetic source เข้าตาราง telemetry จริง
- UI ใช้ component เดียวกับหน้า Operation และทดสอบทั้ง component harness กับหน้า Calibration จริงผ่าน QA backend/archived features ไม่ใช่ fake API. ตรวจการ disable/confirm/build, กราฟ 7 ก.ย. ราย 1 นาที, ย้อนกลับแล้วล้าง Preview เก่า, Reference 4 calendar days ที่มีข้อมูล qualified 3 วันไม่เปิด Build และ refresh คืน job/reviewer/date เดิม. จอกว้างและ Operation 390×844 ผ่าน visual QA; แก้ grid/header/Approval ที่เดิมล้นมือถือ วัด document scrollWidth=clientWidth=375px (viewport390 ลบ scrollbar). Grids/ปุ่มไม่เลื่อนออกนอกจอ กราฟไม่รวม Hp/Lp บนสเกลเดียว และชื่อเครื่อง–โมดูลติดอยู่ในชื่อกราฟ
- Preview ปัจจุบันบนเครื่องนี้แยก Operation `http://127.0.0.1:5174/` / API8177 จาก Dashboard ที่ผู้ใช้รันบน5173. สี/ข้อมูลเป็น LOCAL_ARCHIVE_REFERENCE_QA เท่านั้น ไม่ใช่ live feed หรือ Server. ตัว harness ไม่รวมใน production Vite build
- ภาพหน้าทบทวนจาก browser จริง: ignored `notebooks/outputs/reference_review_local_qa_v1/ui_reference_wizard.jpg`. ตรวจ console ไม่พบ error/warn ในช่วง QA สุดท้าย; ไม่เท่ากับ load test หรือ production uptime guarantee. พารามิเตอร์ใน foldout อ่านจาก policy ที่ทบทวน และหาก browser storage ใช้ไม่ได้ UI แจ้งว่าหลัง refresh อาจต้องทบทวนใหม่ แทนการทำให้หน้า crash

## QA checklist สำหรับ change นี้

- [x] System: อ่าน README/SOT และไม่เปลี่ยน Busy/SV/Temp/CP semantics
- [x] Data: ระบุ source-local cutoff/period, source-second-derived 1m grain, Gate/exclusions/counts/null gaps/digests
- [x] Model: fit median/scale/threshold เฉพาะ Reference; exclusion ไม่แตะ Shadow; original estimator parity test ผ่าน ไม่มี HPO/ML retrain ในรอบนี้
- [x] Evidence: QA receipt/source SHA256; REVIEW_REQUIRED ไม่ถูกเรียก healthy/Active/FPR
- [x] Presentation: Hp/Lp คนละสเกล, gray/purple มีคำอธิบาย, verified units เท่านั้น, missing correlation ไม่แทน0; busy/insufficient/back/refresh ผ่าน local UI
- [x] Local persistence: concurrent retry/atomic normal commit และ injected rollback ตาม receipt; lease/changed-source/policy unit tests
- [x] Governance: อัปเดต README_System/SOT/HANDOFF/Project/Roadmap/UX/AGENTS/graft/schema/handoff
- [ ] Production: authenticated identity, real source late-commit/timezone/load, restart/persistence/approval/rollback และ live UI/alerts บน Server — ยังไม่ได้ติดตั้งจริง
- [ ] Detection validity: healthy-start specificity/fresh negative cases — workflow ใหม่นี้ไม่ได้แก้ startup suppression หรือพิสูจน์ว่าทุก Reference ปกติ

ข้อจำกัด: local cache adapter ใช้ aggregated Gate reasons ไม่ใช่ raw-second controller event timeline; ไม่พิสูจน์ healthy startup, fault cause, FPR, Server clock, late-commit semantics จริง หรือ authorization จาก proxy. การดูกราฟรายนาทีไม่สร้างรายละเอียดวินาทีขึ้นมาใหม่. สิ่งเหล่านี้แยกจากงานเพิ่ม manual-reviewed Reference และยังต้องทดสอบตาม Roadmap
