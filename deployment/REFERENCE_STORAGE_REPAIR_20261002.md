# Reference Review storage — local repair and QA, 2 October 2026

## ผลและสาเหตุ

ข้อความ `Reference review storage unavailable; apply mysql_reference_review.sql to the analytics schema` เกิดขึ้นจริง เพราะหน้า Operation ปกติใช้ API8000 กับ `127.0.0.1 / ht9046mx_analytics` ซึ่งยังไม่มีตาราง job. ก่อนหน้านี้ทดสอบ Preview ใน schema ทดลองแยก จึงไม่ได้ติดตั้งตารางให้ schema ปกติด้วย

ใช้ **migration เดิม** `deployment/mysql_reference_review.sql` ใน analytics schema บนคอมเครื่องนี้ และรันซ้ำเพื่อตรวจ idempotency. เพิ่ม `ht9046mx_reference_review_job` แบบ InnoDB มี **18 columns** กับ index ตามไฟล์; ไม่แก้ source/registry/Profile/Active/PM tables. MySQL DDL autocommit; นี่คือ additive installation ไม่ใช่ rollback experiment

ทดสอบ Preview รอบแรกพบปัญหาอีกข้อ: `get_job → _expire` ทำ range UPDATE ทุกครั้งที่ poll แม้ไม่มี lease หมดอายุ เกิด MySQL **1213 deadlock** พร้อม worker ที่กำลัง update lease/status. ตัว job จบ READY แต่ poll บางครั้งตอบ503 และ error handler เหมารวมว่า missing migration ทำให้แก้ผิดสาเหตุได้

## โค้ดที่ปรับ

- `reference_jobs.py`: poll ปกติอ่านสถานะอย่างเดียว; ตรวจ reviewer ก่อนหมดอายุงาน. งานหมดอายุจะ update เฉพาะ primary key ที่ร้องขอ พร้อมตรวจ status/lease ซ้ำ. Cleanup ตอน admission SELECT เฉพาะ expired IDs แล้ว update ตาม primary-key order ไม่ใช้ global range UPDATE. Worker ตรวจเฉพาะงานของตัวเอง. ใช้ current locking read หลัง expiry เฉพาะกรณีจำเป็น เพื่อไม่ใช้ snapshot เก่าเมื่อ lease ถูกต่อพร้อมกัน
- `main.py`: 1146 ที่ job table → แจ้ง migration; 1054 → schema mismatch; 1205/1213 → temporary storage busy/retry; connection/permission/other SQL errors → ข้อความตรวจ connection/permission ไม่อ้างว่าแก้ด้วย migration ทุกครั้ง. ไม่ส่งรายละเอียด connection/password/SQL parameters ไปใน HTTP error
- `ReferenceReview.tsx`: ข้อความไทยบอก next action ตามสาเหตุ. ใช้การ reconnect/poll/retry งานเดิม ไม่ auto-build/approve. การเริ่ม Preview ซ้ำใน draft เดิมใช้ idempotency key เดิมอยู่แล้ว
- Tests ครอบคลุม no-write live polling/empty cleanup, reviewer-before-expiry, scoped expiration, renewed-lease compare-and-set และ error classification

`CREATE TABLE IF NOT EXISTS` เพิ่มตารางที่หายได้ แต่ **ไม่ซ่อม columns ของตารางเก่าที่ไม่ตรงกัน**. หากเจอ `REFERENCE_STORAGE_SCHEMA_MISMATCH` ให้เทียบ schema กับ migration และทำ reviewed additive migration โดยรักษางานเก่า ไม่ drop/recreate เพื่อให้ error หาย

## การตรวจจริงบนคอมเครื่องนี้

หน้า `http://127.0.0.1:5176/` → API8000 หลัง restart โค้ดใหม่. ใช้ actual local source `ht9046mx_iot.ht9046mx_readings`, MX080/M6, cutoff ตามแถวล่าสุดของเครื่อง **21 Sep 2026 03:13:28**, config Asia/Bangkok. Reference **21 Aug–ก่อน18Sep**; Shadow **18–ก่อน21Sep**. Source อิมพอร์ตนี้มี minute-grain/gaps และ fixture เดิม ไม่ใช่ traceable production-normal raw-second cohort

ไม่มีการเปลี่ยน occupied-second/state/finite-sensor gate, quarantine, fit, Q99.5 หรือ3-adjacent-minute persistence. งานเทคนิคสองงานใช้ reviewer `local-storage-repair-qa`: รอบแรกยืนยัน migration/พบ deadlock และรอบสอง concurrency QA. เป็น Preview เท่านั้น ไม่มี Candidate Build/Approval

คำสั่ง QA: `python -m notebooks.support.reference_storage_repair_qa`. **คำสั่งนี้สร้าง technical Preview job หนึ่งรายการใน normal localhost analytics schema** จึงรันเมื่อต้องการทดสอบจริงเท่านั้น ไม่ใช่ read-only diagnostic. Script มี local-host/schema guard, ไม่ apply DDL, ไม่เรียก Build/Approval/worker activation และไม่ insert telemetry

ผลรอบทดสอบ:

| ตรวจ | ผล |
|---|---|
| 10 concurrent HTTP clients ×10 polls | 100/100 HTTP200; ทุกครั้งเห็น PREVIEW_RUNNING |
| เวลาสูงสุดของ100 polls | 0.1183s ในรอบทดสอบนี้ ไม่ใช่ Server SLA |
| Final job | READY; can_build=false |
| Retry POST keyเดิม | jobเดิม; unique keyมี1row |
| Normal frontend Vite proxy → job | HTTP200, READY |
| Profile registry | 119rows; SHA256ของทุก row เหมือนเดิม |
| Active pointers | 46rows; SHA256ของทุก row เหมือนเดิม |
| Source sanity | 322,200rows/MAX timestampเหมือนเดิม; ไม่เรียก source DML |
| Full API tests | 147passed; SQLite/Python3.12 datetime adapter deprecation warnings |
| Frontend build | ผ่าน; existing large-JS-bundle warning |

Ignored receipt: `notebooks/outputs/reference_storage_repair_qa/receipt.json`. Normal-schema Preview job `f26f67ee-84f7-4249-a5dc-39a072e2fdc9`; first smoke job `bfca8d1f-418a-449c-9fb1-d779b6199962`. เก็บเป็น technical audit ไม่ลบทิ้ง

READY หมายถึงอ่าน/คำนวณ Preview จบ **ไม่ใช่ Profile พร้อมอนุมัติ**: retained Reference0days/0minutes; Shadow1qualified day/13minutes, ยังไม่ถึง3days/50minutes. ให้ทบทวนข้อมูลต้นทาง/เลือกช่วงที่มีข้อมูลเหมาะสม ไม่ลด Gate เพื่อให้ Build ผ่าน. Active46รายการเดิมรวม historical local test states ไม่ใช่46 production-approved profiles

## Server handoff และข้อจำกัด

บน Server ต้องติดตั้ง registry ก่อน แล้ว applyไฟล์เดิมใน **analytics schema ที่ API ใช้จริง** ด้วย DBA account ที่มีสิทธิ์สร้างตาราง. Restart backend และ deploy frontend จาก revisionเดียวกัน แล้วตรวจ Preview/poll โดยไม่ approve จากผล technical QA. อย่า apply migration ใน source telemetry schema. รอบนี้ไม่ได้เชื่อม/ติดตั้ง/ตรวจ Server10.195.17.73 และไม่ได้ push Git

100 concurrent reads ที่ผ่านพิสูจน์เฉพาะรอบ localhost นี้ ไม่รับรองว่าไม่มี deadlockจาก workloadทุกชนิด. ยังต้องตรวจ large raw-second load, multiple API processes, actual reviewer authentication, permissions, restart/late commits และ production approval ตาม runbook. ไม่มี model retraining, score/threshold/Active promotion หรือ Alert enablementจากงานนี้

## QA loop

- [x] System: อ่าน README/SOT/ลำดับ context; tag/scorer/approval semantics ไม่เปลี่ยน
- [x] Data: ระบุ schema/Machine×Module/period/timezone/minute-grain/gaps; sourceใช้ SELECT เท่านั้น
- [x] Model: ไม่ fit/train/HPO/retune; split/Gateเดิม
- [x] Evidence: SQL missing-table และ1213stack, scoped/CAS tests, receipt/hash/idempotency/concurrent polls
- [x] Presentation: แยก missing/schema/busy/connection error; READY ไม่แสดงเป็น approval readiness
- [x] Local production-path QA: normal API/proxy/storage, concurrent Preview polling; Profile/Active unchanged
- [x] Governance: SOT/HANDOFF/Project/Roadmap/UX/AGENTS/graft/README และ runbook update
- [ ] Target-Server acceptance/auth/load/clock: ยังไม่ดำเนินการ

Change log: 2026-10-02 — ติดตั้ง existing Reference job migration ใน normal local analytics และแก้ poll-expiration locking/error diagnosis; ไม่มี source/Profile/Active/Server change
