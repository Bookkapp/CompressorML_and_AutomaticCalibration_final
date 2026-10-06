# Operation — เว็บทดลองที่อ่าน MySQL จริง

**หน้า Operation หลักที่เปิดตามคำขอถัดมา:** `http://127.0.0.1:5176/` ใช้ main production source entry กับ normal API8000/ฐาน local เดิม ไม่ใช่หน้าทดลองด้านล่าง. เปิด backend ด้วย `python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000`; frontendใช้ Vite5176 โดยเว้น `VITE_API_BASE_URL` ให้ใช้ same-origin proxy8000ตาม `vite.config.ts`. ไม่ใช้ experimental adapter และไม่ได้กดเปลี่ยน Profile/เปิด worker. เป็น deployable UI รัน local ไม่ใช่ Server10.195.17.73.

ตรวจล่าสุด 2 ตุลาคม 2026 · ใช้บนคอมเครื่องนี้ ไม่ใช่การ Deploy/เชื่อม Server เป้าหมาย

## เปิดดู

หน้าเว็บ: `http://127.0.0.1:5175/source-mysql-experiment.html` · API: `http://127.0.0.1:8178`.

เริ่มที่ MX080 / Module 6 / วันที่ 7 ก.ย. 2026. เปลี่ยนเครื่อง โมดูล วันที่ หรือกด **อ่านใหม่** เพื่อ SELECT จาก MySQL. แยก High/Low pressure, temperature และ Valve เป็นสี่กราฟ; เปิดแถวต้นทาง 10 แถวแรกและเหตุผล Gate ได้. **ทดลอง Calibration** ใช้ ReferenceReview component ตัวเดียวกับ Operation เดิม แต่เขียน job/Candidate ได้เฉพาะ schema ทดลอง.

| หน้าที่ | Host / Schema / Table |
|---|---|
| Source telemetry ที่ตั้งค่าและอ่านจริง | `127.0.0.1` → `ht9046mx_iot.ht9046mx_readings` |
| การค้นหาเครื่อง | `machine_number`, จำนวนแถว, เวลาต้น–ปลายจาก source table |
| Tag ที่อ่าน | `recorded_at`, `Status`, Hp/Lp1/2, Valve, TempHi/TempLo, Status/Busy/SV ของโมดูลที่เลือก |
| ผลทดลอง | `ht9046mx_reference_mysql_experiment_20261002` → `ht9046mx_reference_review_job`, ตาราง batch/profile/shadow/active ของ registry |
| Analytics เดิม | `ht9046mx_analytics` — ไม่ใช้เก็บผลทดลอง ไม่แก้ Active เดิม |
| Server เป้าหมาย | `10.195.17.73` — ไม่ติดต่อในรอบนี้ |

## สิ่งที่พบจริง

Source มี 24 machine IDs รวมข้อมูลย้อนหลังและ fixtures จาก QA ก่อนหน้า. รหัส `001`, `100`, `111`, `777` ติดป้าย **MOCK** ตามประวัติในเอกสาร; รหัสอื่นไม่ได้ถูกยืนยันว่าแต่ละแถวเป็น telemetry เครื่องจริง จึงระบุ historical/imported หรือ additions ที่ provenance ยังไม่ยืนยัน. MAX timestamp ไม่ใช่หลักฐานว่า feed สด. MX080 มี 8,582 แถว ตั้งแต่ 3 ก.ย. ถึง 21 ก.ย. 03:13:28 ตาม config Asia/Bangkok; config ไม่ได้ยืนยัน pressure unit.

วันที่เลือกใช้ช่วง `[2026-09-07 00:00,2026-09-08 00:00)` ตาม source-local time. MX080/M6 มี **1,418 แถว, timestamp ซ้ำ 0 แถว, median positive interval 60 วินาที**. กราฟเป็นค่าเฉลี่ยของแถว SQL ที่มีจริงต่อนาที มีช่องว่าง 22 นาที ไม่ interpolate. ไม่ใช่ raw-second trajectory, anomaly score หรือ Active-based normal band. Manual/state rows ถูกแสดงและเก็บไว้ ไม่แปลงเป็น healthy label.

เมื่อผ่าน strict observed-second 1m builder ตัวเดิม ได้ **0 qualified minutes** ของวันนี้: LOW_SAMPLE_COVERAGE 1,418 windows. ไม่ผ่อน ≥57 occupied seconds/95%/gap≤5s หรือสร้างวินาทีเทียม. ต้องมี raw-second intake จริงก่อนทดสอบ lifecycle นี้ได้ครบ; ไฟล์ archived QA ก่อนหน้านี้กับ MySQL local ไม่ใช่ dataset/grain เดียวกัน.

กด Preview จริงจาก UI แล้ว job `b0ce8b31-09c0-4557-87ea-3c799a766a99` เป็น READY หมายถึง **อ่านและคำนวณ Preview เสร็จ** ไม่ใช่ Profile พร้อมอนุมัติ: Reference 21 ส.ค.–ก่อน18ก.ย. มี 0 eligible minutes; Shadow18–20ก.ย. มี 13 eligible minutes ซึ่ง provenance ยังไม่ยืนยัน. Reference ไม่พอจึงปิด Build. ใช้ minima/settings จาก `.env` ปัจจุบันโดยไม่เปลี่ยน: UI ที่ทดสอบแสดง 3 วัน/50 นาที; ไม่ใช่การรับรองว่า QA ค่าต่ำนี้เหมาะกับ production (แนวทางเดิมแนะนำ7วัน/200นาที). ไม่มี Candidate/Profile ใหม่; schema ทดลอง Active=0, Profile=0, job=1 ณ receipt.

## ขอบเขตทดลอง

`reference_review_mysql_experiment.py` ใช้ latest-time query และ `load_observed_one_minute_windows` ตัวจริง ไม่ override ด้วย Parquet/cache และไม่เลื่อน source cutoff ให้ช่วงที่อยากเห็นผ่านเกณฑ์. มี source connection read-only transaction session และ statement guard สำหรับ SELECT/SHOW/EXPLAIN; discovery ใน runner ใช้ engine เดียวกัน. ใช้บัญชีที่มีในเครื่องนี้; ไม่ได้พิสูจน์ว่า Server DBA สร้าง SELECT-only role แล้ว.

สร้าง schema ทดลองใหม่และ apply registry/job DDL เฉพาะ schema นั้น. API อนุญาต write เฉพาะ Preview/Build ของ Reference; Approval, legacy rolling run, technician feedback และ alert simulator ตอบ409. ไม่เริ่ม scheduler/scorer/PM bridge ไม่เพิ่ม telemetry/fixture ไม่ปรับ detector/threshold/profile/unit/state semantics. หน้า SQL นี้เป็น development entry แยก ไม่รวมใน production Vite build; ไม่แก้ Dashboard ที่ผู้ใช้เปิดบน5173หรือ archived preview5174/API8177.

## เปิดใหม่บนเครื่องนี้

จาก root โปรเจกต์ ใช้ local `.env` ที่มี source/analytics credentials อยู่แล้ว โดยไม่พิมพ์ secret ลงคำสั่งหรือ Git:

```powershell
python -m notebooks.support.reference_review_mysql_experiment --port 8178
```

อีก terminal ที่ `apps/web`:

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8178'
node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort
```

runner จำกัด localhost ทั้งสอง connections เพื่อไม่ใช้เป็น deployment launcher. `.env` ไม่ถูกแก้และ credentials ไม่แสดงในหน้าเว็บ. ปิด process ทดลองสองตัวเมื่อไม่ใช้ได้; ข้อมูล job ยังอยู่ใน schema ทดลอง ไม่ได้ลบทิ้ง. ถ้ามีโปรแกรมอื่นใช้portอยู่ให้ตรวจเจ้าของก่อน ไม่หยุด process ของผู้ใช้.

## QA และข้อจำกัด

- [x] อ่าน README/SOT และอ่าน actual schema/84 columns (81 telemetry tags + id/machine/time)/index `(machine_number,recorded_at)`
- [x] Reconcile API 1,418 rows กับ minute observation count; 1,440 chart slots/22 null gaps; empty date แสดงไม่มีข้อมูล ไม่ใช่ Normal
- [x] Actual Reference preview จบ; insufficient Reference ปิด Build; ไม่ fit/HPO/retrain/approve
- [x] 118 API tests ผ่าน รวม12 experimental boundary/SQL-guard tests; frontend `npm run build` ผ่าน (large-bundle warningเดิม)
- [x] Actual HTTP invalid module422, approval409, simulator409; Active/Profile counts0
- [x] Browser desktop: สี่กราฟ, selector/Preview, complete-day boundaries/coverage และ Build disabled; scrollWidth=clientWidth1176px
- [x] ปรับ dev HMR ให้ reuse React root หลังพบ createRoot warning ระหว่างแก้; reload ตรวจ runtime ใหม่
- [x] อัปเดต governance/status/data-code map; no Git push/Server operation
- [ ] ไม่ใช่ fault accuracy, healthy-start specificity, real source provenance/clock validation, production auth/load/restart/late-commit/Active acceptance

หลักฐาน ignored: `notebooks/outputs/reference_mysql_experiment_v1/receipt.json`, `ui_source_mysql.jpg`. ตรวจซ้ำเมื่อ API รัน: `python -m notebooks.support.reference_mysql_experiment_check`. Check นี้ผูกกับ historical sample และสถานะทดลองตอนนี้ ไม่ใช่ acceptance test ของทุก dataset; เปลี่ยนข้อมูล/สร้างงานใหม่ต้องบันทึก snapshot ใหม่.
