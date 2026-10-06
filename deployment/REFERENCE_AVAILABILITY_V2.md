# ตรวจวันข้อมูลให้ครบทั้ง Reference และ Shadow

Checkpoint: 2 October 2026 · selection version `manual-reference-complete-day-shadow-v2`

## ปัญหาที่แก้

**Storage checkpoint 2 Oct:** Availability SELECT could work even when normal analytics had no job table. Existing `mysql_reference_review.sql` is now installed in localhost normal analytics; Preview/poll lease contention and misleading SQL errors are also repaired.147tests/build and100concurrent polls pass; qualified coverage gates are unchanged. See `REFERENCE_STORAGE_REPAIR_20261002.md`. This supersedes earlier normal-local no-job-write status only; target Server remains untouched.

เวลาของแถวล่าสุด (`MAX(recorded_at)`) ไม่ได้บอกว่าวันก่อนหน้ามีข้อมูลครบ แถวใหม่ไม่กี่แถวหลัง log ขาดอาจทำให้ Shadow ย้ายไปอยู่ในวันว่างได้ อีกกรณีหนึ่งคือ schema แบบ wide มีแถวของเครื่อง แต่ sensor ของโมดูลที่เลือกเป็น NULL จึงต้องตรวจ Machine × Module และทั้ง Reference + Shadow ไม่ใช่ตรวจเพียงวันล่าสุดของ fleet

ตัวอย่างจริงจาก localhost `ht9046mx_iot.ht9046mx_readings`: MX080/M6 มีแถวล่าสุด **21 Sep 2026 03:13:28** ตาม config `Asia/Bangkok`. Shadow เริ่มต้น 18–20 Sep มี log/sensor ครบเพียง 19 Sep (30 observed minutes); 18 และ 20 Sep ไม่มี log. Reference เริ่มต้น 21 Aug–ก่อน 18 Sep มี sensor ครบ 5 วัน/7,178 observed minutes. ห้าวันนี้ไม่พอแบ่ง Reference อย่างน้อย 3 วันและ Shadow อีก 3 วันโดยไม่ซ้ำกัน จึงยังเสนอช่วงที่พร้อมไม่ได้

เป็นข้อมูล MySQL บนคอมเครื่องนี้ ไม่ใช่ ZIP/archive ทั้งหมดหรือ Server 10.195.17.73. ตารางมีข้อมูลย้อนหลัง/import และการทดลองเดิมปะปนกัน; เวลา หน่วย และ healthy provenance ยังไม่ผ่าน production acceptance

## ขั้นตอนใหม่

1. เลือกเครื่อง–โมดูล → UI เรียก **GET availability** ทันที ไม่ต้องสร้าง job/Profile ก่อน แสดงแถวล่าสุด วันล่าสุดที่โมดูลมี sensor ครบ 7 ช่อง timezone และอายุข้อมูล
2. ตรวจ 93 วันปฏิทินที่ปิดแล้ว พร้อมวันล่าสุด/วันใน grace ที่ยังไม่ปิด: daily raw rows, distinct occupied minutes และ rows/minutes ที่ Hp1/Lp1/Hp2/Lp2/Valve/TempHi/TempLo ไม่เป็น NULL. SQL จำกัด machine aliases และ timestamp range; API รับผลสรุปรายวัน ไม่โหลด raw ทุกแถวมาที่หน้าเว็บ
3. แสดง Reference/Shadow ตาม cutoff เดิม แยก **ไม่มี log** กับ **มี log แต่ไม่มีแถว sensor ครบ**. จำนวนที่พบยังไม่ใช่จำนวน qualified Cold minutes
4. หาช่วงเสนอที่ใหม่ที่สุดในขอบเขตที่ตรวจ: Shadow 3 วันปฏิทินติดกันมี sensor ครบบางนาทีทุกวันและจำนวน observed minutes ถึงขั้นต่ำ; Reference 28 วันก่อนนั้นมีวัน/observed minutes ถึงขั้นต่ำด้วย. ไม่ใช้ค่าตัวแปร คะแนน หรืออัตรา flag เลือกวัน ไม่ต่อสามวันห่างกันเป็น Shadow และไม่ให้ทับ Reference
5. ผู้ใช้กด **ใช้ช่วงเสนอ แล้วตรวจ Gate ใน Preview** เพื่อเลือกย้อนหลังอย่างเปิดเผย ระบบไม่ย้อนวันให้เงียบ ๆ. กรอก cutoff เองได้พร้อมเหตุผล; ไม่เกิน latest closed cutoff และย้อนหลังไม่เกิน 90 วัน. Reference ยังปรับ/ยกเว้นช่วงได้เหมือนเดิม
6. Preview อ่าน source ทีละวันและใช้ Gate เดิม: occupied seconds ≥57/60, duplicates/gaps/state/finite sensors/Valve. Inventory เป็นเพียง necessary coverage check ไม่รับประกันจำนวนที่ผ่าน Gate
7. Build เปิดเมื่อ **retained Reference** ถึงขั้นต่ำหลัง quarantine **และ Shadow มี qualified Cold minutes ครบทุกวันทั้ง 3 วันและจำนวนรวมถึงขั้นต่ำ**. ถ้า Shadow ไม่พอจะไม่สร้าง Candidate แม้ Reference พอ แต่ยังดู Preview/กราฟได้ ไม่มีการเติมข้อมูลให้ปกติ
8. เก็บ source_latest จริง, latest_complete_end, chosen shadow_end และเหตุผลใน selection/digest. ตรวจ input/policy ซ้ำก่อน commit. เปลี่ยนวัน/เหตุผลต้อง Preview ใหม่; งาน v1 ที่ยังไม่ Build ต้องทบทวนใหม่ UI แจ้งและปิด Build ไม่ลบงานเก่าหรือเปลี่ยน Active

“สามวันเต็ม” หมายถึงขอบเขตปฏิทินปิดแล้ว ไม่ได้รับรองว่ามี log ครบ 1,440 นาที/วัน. Observed coverage และ Approval gates เดิมยังต้องตรวจ. Shadow ย้อนหลังไม่ซ้ำ Fit แต่ **ไม่ใช่ blind test**; การเลือกช่วงที่เคยดูแล้วเป็น retrospective review ไม่ใช่หลักฐานความแม่นยำหรือ healthy label

## API / โค้ด / Server handoff

- `GET /api/v1/calibration/reference/availability?machine_number=MX080&module=6&history_days=28`: SELECT-only เช่นเดียวกับ source inventory เดิม ไม่ต้องมี job storage/reviewer ก่อนอ่าน. ผลมี default/suggested periods, daily counts และข้อจำกัด. UI cache 60 วินาทีและมีปุ่มตรวจล่าสุด
- Preview เพิ่ม `shadow_end` (วัน exclusive) และ `shadow_selection_reason`. เว้น cutoff ให้ใช้วันปิดล่าสุดตามแถวจริง; ใส่ cutoff ต้องมีเหตุผล. ใช้ selection เดียวกันทั้ง Preview/detail/Build/retry
- `reference_availability.py` อ่าน/summarize inventory; `reference_review.py` ตรวจวันและ Shadow; `main.py` เพิ่ม GET; `ReferenceReview.tsx`, `api.ts`, CSS แสดง/เลือกวันและแจ้ง Preview รุ่นเก่า
- ไม่เพิ่ม DB column/migration: selection/เหตุผล/summary เก็บใน JSON เดิม. Server ต้องมี registry และ `mysql_reference_review.sql` ตาม runbook เดิม และ deploy backend/frontend ด้วยกัน
- ไม่เปลี่ยน legacy rolling route/scheduler, Data Contract, robust-z/scale floor/Q99.5/3-minute persistence, Active Profiles, workers หรือ Alerts; **ไม่ต้อง retrain ML สำหรับการแก้วันข้อมูลนี้**
- หน้า actual Operation บนคอมเครื่องนี้ `http://127.0.0.1:5176/` → normal API8000; 5175/API8178 เป็น experimental isolation. Archive QA 5174/API8177 เดิมเป็น checkpoint v1 คนละ input lane ไม่ใช่ source SQL inventory หรือหลักฐาน UI v2. ไม่รัน Server/Push รอบนี้

## QA และข้อจำกัด

`python -m pytest apps/api/tests -q` → **137 passed**, รวม 45 reference/availability tests: empty/partial days, timezone/grace, sensor-null vs no-log, adjacent days, Reference/Shadow minima, explicit cutoff/reason/bounds, policy/digest changes, idempotency/atomic rollback และ Shadow ไม่เข้า Fit. Tiny unit fixtures กำหนด Shadow 50 สำหรับ transaction tests ไม่ใช่เปลี่ยน production config

`npm run build` ผ่าน มี large-bundle warning เดิม. ตรวจ browser บน actual Operation MX080/M6: แถวล่าสุด/Reference/Shadow/วันที่ไม่มี log แสดงตรงกับ API; Preview ยัง disabled เมื่อไม่ใส่ reviewer; มีช่อง cutoff/เหตุผล ไม่มี Candidate/Approval บน normal schema จาก UI QA

`python -m notebooks.support.reference_availability_qa` อ่าน actual SQL ของ MX080/M6, MX057/M1+M6 และ MX017/M6 แล้วสร้าง **Preview job เท่านั้น** ใน `ht9046mx_reference_mysql_experiment_20261002`. Explicit Shadow 5–7 Sep พบ log ครบ 3 วัน แต่ **0 qualified minutes/0 qualified days**; Reference 0; can_build=false. Build ตอบ 409 `REFERENCE_NOT_READY`. Experimental Profile/Active เป็น 0 ก่อนและหลัง ไม่ insert source/activate Profile. Receipt/screenshot อยู่ใน ignored `notebooks/outputs/reference_availability_v2/`

Availability requests สองรอบที่ตรวจใช้ประมาณ 0.03–7.30 วินาที ขึ้นกับเครื่อง/จำนวนแถว ไม่ใช่ Server SLA หรือ fleet load test. Query 93 วันบน raw-second Server อาจหนักกว่านี้ ต้องวัด index/query plan/latency/auth/load จริง; incremental daily coverage สำหรับการตรวจบ่อยเป็นงานต่อยอด ไม่ใช่ลด Gate หรือเติมวินาทีจากข้อมูลนาที

### QA loop

- [x] System/data: README/SOT, Machine×Module, source-local closed days, counts/null/gaps และ retrospective scope
- [x] Model/evidence: ไม่มี retrain/HPO/threshold tuning; Shadow ไม่ Fit; source_latest จริงไม่ถูกซ่อน; coverage ไม่ใช่ healthy label
- [x] Presentation: แยก log/sensor ครบ/qualified, วันขาด/next action, cutoff พร้อมเหตุผล และ Build/version/busy controls
- [x] Local persistence: isolated Preview/refused Build, Profile/Active คงเดิม; retry/rollback tests ผ่าน
- [x] Governance: README_System/SOT/HANDOFF/Project/Roadmap/UX/AGENTS/graft และ workflow อัปเดต
- [ ] Production: ยังไม่ติดตั้ง/ตรวจ Server, live clock/codebook, large-history concurrency, authenticated Approval หรือ healthy specificity

Change log: 2026-10-02 — เพิ่ม source-day preflight และ explicit historical cutoff v2; ตรวจ Shadow ก่อน Build. เป็นการปรับ calibration administration ไม่ใช่ detector/ML release
