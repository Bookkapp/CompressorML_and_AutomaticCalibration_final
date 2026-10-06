# Calibration: ความคืบหน้าหลังตรึง Reference

Updated: 6 October 2026 · Asia/Bangkok · Operation localhost API 8000 / web 5176.

## งานที่ส่งมอบ

เพิ่มการติดตามข้อมูลจริงในขั้นตอน **3. ตรวจข้อมูลใหม่และเปิด Active** โดยแยกการรับข้อมูล การตรวจระหว่างรอ และการตรวจรับครบ 3 วัน ไม่มีปุ่ม Mock หรือการสร้างข้อมูลจำลองในหน้าเว็บ

- แสดงเวลาตรึง Reference วันแรกที่นับเป็นวันเต็ม และ timestamp ล่าสุดจาก source
- แยก **วันปิดที่พบข้อมูล** กับ **วันปิดที่ตรวจได้อย่างน้อย 60 นาที** การมีข้อมูลไม่ใช่การผ่านเกณฑ์
- แสดงรายวัน: นาทีในกรอบ นาทีเบี่ยงเบน/อัตราเบี่ยงเบน สภาวะที่ต้องทบทวน State Gate สภาวะควบคุมไม่รองรับ คุณภาพไม่ผ่าน และข้อมูลขาด
- ตรวจข้อมูลที่เข้ามาแล้วได้ก่อนครบ 3 วัน รวมวันเดียวกับที่ตรึง Reference โดยเริ่มจากนาทีเต็มแรกหลังบันทึก วันตรึงยังไม่นับเป็นวันเต็มสำหรับอนุมัติ
- เปิดกราฟรายวันหรือ Raw รอบช่วงที่ควรตรวจ จากผลตรวจที่บันทึกไว้และผูกกับ Profile นั้น
- แจ้งเมื่อ source หยุดหรือผลตรวจเก่ากว่าข้อมูลล่าสุด งานตรวจดำเนินต่อได้หลังปิดแท็บหรือ lease หมดอายุ

## วิธีใช้งาน

1. เปิด Calibration เลือกเครื่องและโมดูล แล้วใช้ผู้ทบทวนที่มี Reference บันทึกไว้
2. ไปขั้นตอน 3 ดูเวลา **ตรึง Reference** และ **ข้อมูลต้นทางล่าสุด** หากต้นทางยังเก่ากว่าเวลาตรึง ให้ตรวจระบบรับข้อมูลก่อน
3. เมื่อมีข้อมูลหลังตรึง กด **ตรวจข้อมูลที่มีแล้ว** ติดตามงานในกรอบเดิม ไม่ต้องสร้าง Profile ใหม่
4. ตรวจตารางรายวัน โดยเฉพาะช่วงเบี่ยงเบน สภาวะ/Transition ที่ยังไม่รองรับ และคุณภาพข้อมูล กด **ดูกราฟรายวัน** หรือขยายช่วงที่ควรตรวจแล้วกด **ดู Raw**
5. หากยังไม่ครบวันเต็ม ให้รอข้อมูลจริง ระบบอัปเดต metadata ทุก 30 วินาทีในแท็บที่เปิดอยู่; ขณะมีงานตรวจจะติดตามทุก 3 วินาที
6. เมื่อช่วงตรวจรับมีข้อมูลจริงครบ 3 วันเต็ม กด **ตรวจข้อมูลใหม่ครบ 3 วันด้วย Reference ที่ตรึง** ผลตรวจระหว่างรอไม่แทนผลตรวจรับรอบนี้
7. ตรวจ blockers/หลักฐาน Engineer/สภาวะที่เลือกและผล prospective validation ก่อน Approve การแก้ Reference สร้างเวอร์ชันใหม่และเริ่มเวลาตรวจรับของเวอร์ชันนั้นใหม่

## ความหมายของข้อมูลและขอบเขต

- Source: localhost `ht9046mx_iot.ht9046mx_readings`; analytics: `ht9046mx_analytics`; timezone `Asia/Bangkok` แรงดัน psi ความเป็น psig/psia ยังต้องยืนยัน
- กราฟ/ผลตรวจเป็น observed minutes จาก Raw วินาที ใช้คุณภาพและ State Gate เดิม ไม่เติมนาทีที่ขาด
- ตรวจด้วย frozen model เท่านั้น ไม่มี fitting ปรับ baseline หรือเปลี่ยน thresholds จากข้อมูลหลังตรึง
- ตรวจระหว่างรอมี `approval_eligible=false`, `prospective=false` และไม่เขียน `future_validation`/Profile/Active
- วันปิดที่มีข้อมูลอย่างน้อยหนึ่งแถวเป็นเพียง inventory; ต้องตรวจ observed coverage และ supported minutes เพิ่ม
- เกณฑ์ตรวจรับเดิม: 3 วันเต็มล่าสุดหลังวันทบทวน วันละ supported ≥60 นาที รวม ≥ค่าที่ตั้งไว้ และ flag ≤ค่าที่ตั้งไว้ ปัจจุบัน local ตั้ง total minimum 50 นาที/flag 1%; ข้อกำหนดรายวันทำให้รวมอย่างน้อย180นาทีอยู่แล้ว
- การรับรอง included states/Reference และ source contracts ยังเป็น prerequisites เดิม SV ที่ระบุ excluded เป็น NOT_EVALUATED พร้อมเก็บ Raw/เหตุการณ์
- Source timestamp อนาคตเกิน60วินาทีหรือเวลาทบทวนอนาคตบล็อกการตรวจ; final validation ตรวจ clock ทั้งตอนรับคำขอและตอน execute
- กราฟแสดง telemetry deviation ไม่ใช่การยืนยัน leak/charge/ความเสียหายทางกายภาพ

## เสถียรภาพและการดึงข้อมูล

- GET progress ใช้ indexed timestamp/presence seeks ตาม alias รายเครื่อง จำกัดไม่เกิน4วัน มี coalesced cache30วินาที ไม่มี scan ประวัติหลายเดือนหรือ fitting ผ่าน GET
- ใช้ durable leased SQL queue เดิม จำกัด admission4งานและ serialize งานของเครื่องเดียวกัน งานซ้ำจากหลายแท็บ reuse งานที่รับไว้
- Partial snapshot ตรึงเป็นช่วง5นาที อ่านข้อมูลร่วมทั้ง8โมดูล ใช้ SQL fill lock และไม่เขียนทับ pointer ของ complete-day snapshot
- การตรวจจำกัด4วันพร้อมวันก่อนหน้าสำหรับ delayed transition context ข้อมูลก่อนเวลา freeze ใช้ประกอบบริบทได้ แต่ไม่รวมในผลตรวจหลังfreeze
- Raw จำกัดช่วงที่อยู่ใน saved inspection และไม่เกิน30นาที กราฟผูก exact job/Profile/snapshot digest
- Event เก็บใน ledger เดิม `PROFILE_FOLLOWUP_INSPECTED` ใช้ job identity ป้องกันรายการซ้ำ flush control events เป็น batch และจำกัด event budget
- ไม่มี schema migration เพิ่ม ไม่มี background synthetic producer หรือ worker production เปิดใหม่ในงานนี้

## QA ที่ตรวจแล้ว

| การตรวจ | ผลและขอบเขต |
|---|---|
| Full API suite ก่อนการปรับรายละเอียดวันตรึง/flush สุดท้าย | 256 passed |
| Final followup regression | 9 passed ครอบคลุม0–3วัน/missing/future clock/same-day/retry/restart/coalescing/Raw bounds/frozen invariance |
| Final TypeScript + Vite production build | ผ่าน รวมการปรับตัวเลือกวันของ partial inspection; existing bundle-size warning ยังคงมี |
| Actual localhost concurrency | 10 clients /120 GETs สำเร็จ120; warm p50 55.82ms /p95 68.54ms /max85.18ms |
| Manual actual browser | MX058/017สองแท็บ Profile/วันที่/ผู้ทบทวนไม่ปะปน; refresh/disabled gate ถูกต้อง; Mock buttons0 /console errors0 |
| Registry comparison | legacy Profiles207/Active46, ContextProfiles110/ContextActive0 และ import receipts567 เหมือนเดิมก่อน–หลัง read-only QA |

HTTP timings วัดเฉพาะ progress metadata ที่ warm แล้ว ไม่ครอบคลุม cold source capture/scoring หรือเวลาวาดกราฟ ไม่ใช่ Server SLA กรณี restart และ partial/day/Raw success ใช้ isolated SQLite fixtures ไม่ใช่การกดตรวจข้อมูลจริง3วันในเว็บ

### สถานะข้อมูลจริง ณ การตรวจ

- MX058/M1 Profile `2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e` ตรึง6Oct08:04:35 ต้นทางล่าสุด5Oct14:45:05 จึง0/3วัน ไม่มีข้อมูลหลังfreezeสำหรับการตรวจจริง วันเต็มแรก7Oct
- MX017/M1 Profile `65a3e0210722f339c00ee6fc8118e4f7c093e5f7a158a679150aec6526a61416` ตรึง6Oct07:10:47 ต้นทางล่าสุด1Oct15:55:01 จึง0/3วัน
- ไม่เปิด Active ไม่แก้ Reference/ข้อรับรอง ไม่เติม source ไม่ตั้งค่า Server10.195.17.73 ข้อความ Engineer ที่มีอยู่เดิมไม่ถูกนำมายืนยันว่าเป็นผลตรวจจริง
- Actual interim/day/Raw manual success และ actual 3-day Active-success ต้องตรวจอีกครั้งเมื่อมี source หลังfreezeจริง ขณะนี้ทดสอบเส้นทางเหล่านั้นด้วย isolated fixtures

### บันทึกการแยกฐานข้อมูลทดสอบ

การรันครั้งแรกพบ fixture admission ใช้ engine ของlocalแทนSQLite จึงมี queued technical jobหนึ่งรายการ `eb9b08b7-eb14-42c1-89f8-9d957255a9f4` (`followup-test-job`, parent=`a`×64) งานไม่เคยdispatch หลังตรวจidentityยกเลิกแบบคงaudit rowเป็นFAILED/`ISOLATED_FIXTURE_ADMISSION_CANCELLED` แล้วแก้fixtureให้patchทั้งconnectionและget_engine ไม่มีsource/Profile/Active mutationจากงานนี้ การทดสอบfinal9กรณีแยกSQLiteแล้ว

## หลักฐานและไฟล์

- `notebooks/outputs/context_followup_20261006/{actual-progress,http-load,registry-before,registry-after}.json`
- `notebooks/outputs/context_followup_20261006/mx058-progress.png`
- `notebooks/support/context_followup_qa.py` — actual read-only local QA
- `apps/api/app/context_followup.py`, `context_api.py`, `context_reference.py`, `automatic_reference.py`, `reference_jobs.py`
- `apps/api/tests/test_context_followup.py`
- `apps/web/src/components/ContextFollowupProgress.tsx`, `ContextCalibrationWorkspace.tsx`, `context-calibration.css`, `context-types.ts`, `api.ts`

### Reproduce

```powershell
python -m pytest apps/api/tests/test_context_followup.py -q
python -m notebooks.support.context_followup_qa
```

## Change log

- 2026-10-06 — Owner authorized post-freeze actual-data progress and interim inspection with no Mock button. Added bounded source inventory, exact frozen-profile saved inspection/day/Raw, restart/idempotency/clock guards and manual UI/local load evidence. Real data afterfreeze/Server/Active acceptance remains open.
