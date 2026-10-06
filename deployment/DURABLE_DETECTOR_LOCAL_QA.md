# Durable detector → Dashboard: local QA checkpoint

วันที่ 1 ตุลาคม 2026 · Server `10.195.17.73` ไม่ได้ถูกเชื่อมต่อในรอบนี้

## ผลและขอบเขต

เพิ่ม worker แบบ opt-in, strict Active loader, source-ID/digest overlap receipts, atomic checkpoint/window/Episode/outbox, idempotent PM bridge, authenticated evidence API และ Dashboard review จาก Alert/Work/Service Log พร้อม export/inventory โดยไม่เปลี่ยน primary rule/threshold/Active Profile หรือ train model

ทดสอบ archived MX080/M6 7 Sep 2026 11:45–13:00 ไม่รวมปลายช่วง; source clock Asia/Bangkok; raw observed seconds 4,438 แถว → 75 module-minute windows มี qualification failures อยู่ในผลด้วย ไม่เติมวินาทีที่ขาด Fit reference 3–6 Sep มีเพียงสี่วัน Candidate จึงเป็น INSUFFICIENT_DATA และไม่ได้ใช้ real Active Profile

| การตรวจ | ผล |
|---|---:|
| Operation full Python suite | 80 passed (36.04 s; prior repeat 18.07 s) |
| Dashboard full Python suite | 69 passed |
| Dashboard Node/chart contracts | 8 passed |
| Full replay vs durable minute/window/score | 0 mismatches |
| Analytics windows → PM evidence | 75 → 75 |
| Episode ที่เก็บจาก replay | 1 |
| Retry / reconnect | 15 / 15 |
| Crash ก่อน commit | 1; rollback ผ่าน |
| Source-ID low-ID late commit, changed/finalized row | unit tests ผ่าน; DATA_ISSUE แทน rewrite |
| PM commit → ก่อน analytics ACK crash | unit tests ผ่าน; receipt กัน Alert ซ้ำ |
| Obsolete Profile context → pending Alert | unit test ผ่าน; suppressed |
| Local authenticated-fixture evidence requests พร้อมกัน | 10/10 HTTP 200; 75 points/request; 0 writes |
| Local API latency avg / max | 716.83 / 898.01 ms รวม TestClient/thread/DB |
| MySQL poll/retry/bridge cycle P95 | 850.14 ms บน 15 รอบเล็ก |
| Export | 4,438 archived rows; 2 JSONL files; checksum/count verified |
| Production/source/Profile/actual Alert/work/log mutations | 0 |

ตัวเลข runtime นี้ไม่ใช่ calibration fitting cost, fleet benchmark หรือ Server network latency ค่า P95 ระหว่างสอง local runs (668.49/850.14 ms) แสดงความแปรปรวน จึงไม่ใช้รับประกัน Server SLA

Actual local QA schema: `ht9046mx_detector_qa_20261001` มี source clone `qa_source_4349047bfd1a`, detector/PM derived tables และ fixture identity/work reference สำหรับ API test เป็น schema แยกจาก source/analytics/PM ที่ใช้งานอยู่ เก็บไว้ reproduce ไม่มีการลบ

Run: `detector-83831094e0a13dbb7276484862be9f49b26caf6de62df406`.
Report: `notebooks/outputs/durable_detector_qa_v1/4349047bfd1a/qa.json`; evidence/export manifest อยู่ใน folder เดียวกัน

## สิ่งที่เพิ่มในระบบ

- `qualified_detector.py`: bounded SELECT; overlap; source receipts/issues; revision fencing; catch-up; opt-in CLI
- `qualified_persistence.py`: reusable namespace, transaction hook และ accepted-row counter สำหรับ detector; default rehearsal เดิมยังอยู่
- `qualified_shadow_preview.py`: exact Active/feature/threshold/units/timezone/approval/evidence gate; `qualified_scoring.py` ไม่ score ก่อน fit-end
- `qualified_bridge.py`: separate PM receipt transaction, UTC indexing, Alert/Episode identity, freshness/suppression และ no-new-Alert สำหรับ historical/shadow/superseded
- `qualified_archive.py`: immutable export, hashes และ retention inventory; ไม่มี purge
- Dashboard `detector_evidence.py`/API: report-time/source-time distinction, bounded 7d query, context isolation, manual module/time selection, no invented Health
- `DetectorEvidence.jsx`/`detector-chart.mjs`: pressure/differential/temp/valve/score panels, shared zoom, source units, exact packet baseline, null gaps, report/data-issue/persistent highlights และ paged evidence table
- Dashboard `source_recorded_at`: Fleet Trend ยึด source event-time; legacy unknown clock ไม่ backfill เป็นวันนี้

## Visual QA

ใช้ actual archived replay JSON ใน development-only test entry `/tests/evidence-qa.html` ไม่ใช้ข้อมูลจำลองที่อ้างว่าเป็นเครื่องจริง ตรวจ Desktop และ 390px viewport ครบห้ากราฟ พบและแก้:

1. ECharts MarkArea registration เพื่อให้แถบ deviation แสดงจริง
2. baseline legend color ตรงกับเส้นและ source field
3. date ticks ทับกันบนมือถือ → multiline date/time + hide overlap
4. เปลี่ยนวันที่ผ่าน controlled datetime input → รองรับ input event; 12:00–12:40 ได้ 40 points
5. shared zoom แทน independent panel sliders เพื่อเทียบเวลาเดียวกัน
6. keyboard close/focus boundary และ lazy/paged evidence table

ภาพ: `notebooks/outputs/durable_detector_qa_v1/desktop-review.jpg`, `mobile-review.jpg` ส่วน code/frontend build ทดสอบแยกออกไป temp directory จึงไม่แทน static public bundle ที่ผู้ใช้อาจกำลังเปิดอยู่

## Reproduce บนคอมนี้

```powershell
python -m pytest apps/api/tests -q
python -m notebooks.support.durable_detector_qa
```

ใน Dashboard root:

```powershell
python -m pytest tests -q
node --test frontend/tests/*.mjs
$env:DB_NAME = 'ht9046mx_detector_qa_20261001'
$env:TELEMETRY_ENABLED = 'false'
python scripts/qa_detector_database.py <new-detector-run-id>
```

QA script มี localhost/named-QA-schema check ใช้ fixture auth override เฉพาะ TestClient ไม่ใช้ login ของผู้ใช้และไม่เพิ่ม runtime auth bypass

## Limitation / งานที่ยังไม่พิสูจน์

### Contributor presentation follow-up — 1 Oct

แก้ Dashboard evidence และ Operation local replay ให้ red sensor panel ต้องมีตัวแปรในกราฟนั้นที่ stored `|z| >= threshold` ระหว่าง global persistence; score panel ยังเก็บผล global. ทุก crossers ถูกระบุ ไม่เลือกเฉพาะ dominant. Tooltip มี actual/baseline/signed z/threshold และ table มี all-contributors. Missing z ไม่เติม; แถบเหลือง/ฟ้ายังแยกความหมาย. การเปลี่ยนนี้ไม่สร้าง per-feature persistence ไม่เปลี่ยน score/flag/Profile และไม่ยืนยัน physical cause

ใช้ archived fixture75 windowsเดิม: global47/75นาที เทียบ Valve11/75; เวลา12:10 primary contributors TempLo189.25, Lp_1st−71.00, Hp_1st−30.31, TempHi−22.82, dp2+16.15, Hp_2nd+11.31, dp1−11.27, Valve−8.00. Pressure band ยังอยู่เมื่อมี pressure crossers จริง. Filter12:00–12:40ได้40points (global27/40, Valve11/40). Visual inspectionพบ narrow in-band labels/tooltipล้น จึงใช้ responsive summary และ bounded tooltip; ตรวจซ้ำแล้ว ไม่ปรับข้อมูลเพื่อให้กราฟดูดี

Latest Operation80Pythonผ่าน (16.26s), Dashboard69Pythonผ่าน (3.16s)/17Nodeผ่าน; both frontend buildsผ่าน. Dashboard buildเป็นtemp output, Operation tsc/Vite buildเป็นlocal ignored dist; ไม่มี Server deployment หรือแทน Dashboard public bundle. Screenshots: `notebooks/outputs/durable_detector_qa_v1/contributor-pressure-desktop.png`, `contributor-mobile.png`, `contributor-global-desktop.png`, `contributor-operation.png`. Dashboard Desktop/mobile/filter และ Operation local replay ตรวจ rendered แล้ว; Operation อ่านเฉพาะ existing rehearsal run ที่ไม่มี Episode archive จาก checkpoint เก่านั้น ไม่สร้าง run/score ใหม่. Reproducibility test verifies renderer does not mutate stored evidence. ไม่มี DB QA rerun/writeใน display-only task นี้

Multi-start/settling ไม่ได้ implement หรือ fit ในรอบนี้; วิธีตรวจและ required validation อยู่ใน `STARTUP_SETTLING_VALIDATION_PLAN.md`. Global-on-every-panel descriptionsข้างล่างเป็นhistorical diagnosisก่อนแก้UI ไม่ใช่behaviorล่าสุด

### Owner graph review: แถบแรกไม่ใช่ high-pressure incident

เจ้าของโครงการสอบถามแถบแรกที่กราฟ pressure ยังดูทำงานปกติ ตรวจ stored evidence แล้วพบ: 12:00–12:05 NOT_SCORED/MODULE_NOT_STABLE_ON; 12:06 เริ่ม qualified scoring; 12:06/07/08 flag ต่อเนื่อง จึง highlight 12:08–12:18. Dominant feature ตลอดช่วงคือ `templo`, ไม่ใช่ Hp_2nd. เวลา 12:10 TempLo=24.2610, baseline median=−20.2034, scale=0.234951, |z|=189.2496 เทียบ threshold=7.8594. TempHi=62.7525 เทียบ baseline81.2119; Hp_2nd=196.7153 เทียบ baseline190.5881/scale0.54161 ก็เกิน local envelope แม้ยังอยู่ใน owner reference band180–230.

สาเหตุเชิงระบบ: ทุก panel ใช้ global persistent flag และ candidate ที่แคบ/อิง stable values ถูกเทียบกับ warm/transition behavior หลังกลับเป็น On. Qualification ปัจจุบันตรวจสถานะภายในหนึ่งนาที แต่ยังไม่มี cross-minute thermal settling/STARTUP-vs-STEADY regime gate. จึงเป็น sensitivity/visual interpretation limitation ไม่ใช่ fault proof. ถ้าหน้างานยืนยันว่าเป็น normal startup ต้องนับเป็น false positive ของ candidate นี้และใช้เป็น independent normal-transition validation ไม่ใช่เปลี่ยน threshold จาก inspected case แล้วยืนยันว่าผ่าน outer test.

ข้อเสนอสำหรับรอบถัดไป: แยก startup/settling จาก steady Cold โดยตรวจหลาย restart/หลาย module; แสดง dominant contributors และแยก global detector context จาก panel-specific deviation. รอบตอบคำถามนี้ **ยังไม่เปลี่ยน primary rule, profile, threshold หรือซ่อนคะแนน/แถบเดิม** เพื่อรักษาหลักฐาน reproducibility. งานนี้เพิ่มใน Roadmap ก่อนอ้างว่า production specificity ผ่าน

Real source สามารถมี late commit เกิน overlap ได้; ยังไม่มี CDC/reconciliation ครบทุกกรณี Multi-worker fencing ทดสอบ revision failure แต่ยังไม่ทำ multi-process race/load บน MySQL เต็ม fleet Graph filter/render ทดสอบแล้ว แต่ยังไม่ใช่ browser login → ACK → งาน → Service Log กับบัญชีจริงครบวงจร

Profile ใน replay มีสี่วันและ pressure units ไม่ได้ verified ในไฟล์ จึงแสดง source units ไม่อ้างว่า approved normal baseline มี flag ก่อนช่วง high-pressure case ที่ต้องแยก startup/regime/คุณภาพ profile ใน QA ไม่ retune threshold จาก case ที่ดูแล้ว การจับ case ได้ไม่ใช่หลักฐาน specificity/production approval

Qualified evidence ไม่ถูกแปลงเป็น Health % หรือแทน legacy Health overview อัตโนมัติ; pre-existing Health/table/worker paths ต้องเทียบก่อนเปิด liveจริง Episode note/Description/DONE ยังเป็น UNREVIEWED evidence ไม่ใช่ fault/cause training target

Retention inventory ยังไม่รวม manual report intervals ครบ จึงไม่มี automatic purge ไม่มี Git push/Server install/real Active promotion ในรอบนี้ คู่มือสำหรับงานภายหลัง: `SERVER_DETECTOR_RUNBOOK.md`
