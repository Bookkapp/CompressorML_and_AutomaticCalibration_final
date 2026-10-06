# Local MySQL incremental scoring QA

วันที่ตรวจ: 1 ตุลาคม 2026 · เวลาอ้างอิง Asia/Bangkok

## ผลที่ทำได้

Raw-second delivery → completed one-minute window → robust-z/persistence → MySQL → read-only API → Dashboard ทำงานบนคอมเครื่องนี้แล้วในโหมด **LOCAL_REHEARSAL_NOT_ACTIVE** ไม่ใช่ live worker หรือการอนุมัติ Profile

ทดสอบข้อมูลจริงจาก archived MX080/M6 วันที่ 7 กันยายน 2026 เวลา 11:45–13:00 (ปลายช่วงไม่รวม) จำนวน 4,438 แถว รับจำลองทุก 5 นาที และ flush นาทีสุดท้ายหลัง grace 30 วินาที ได้ 75 หน้าต่าง รวมหน้าต่างที่ไม่ผ่าน qualification ด้วย

| การตรวจ | ผล |
|---|---:|
| ผล window และ score เทียบ whole-data replay | 0 differences |
| ส่ง batch เดิมซ้ำ | 15 ครั้ง ไม่มีผลซ้ำ |
| Dispose/reconnect และ restore จาก DB | 15 รอบ ผลตรงเดิม |
| Crash ก่อน commit | 1 รอบ ผล/receipt/cursor rollback พร้อมกัน |
| Checkpoint revision หลัง final flush | 16 |
| P95 ต่อรอบ | 56.60 ms |
| Targeted unit/API tests | 27 passed |
| Full API test suite | 58 passed (19.52 s) |

Latency ครอบคลุม fetch จากตารางสำเนาทดสอบ, scoring, DB writes, retry/reconnect และ crash probe ใน 15 รอบเล็ก ไม่รวม calibration fit/การนำ raw ลงตารางสำเนา ไม่ใช่ benchmark fleet หรือ latency บน Server

Run ที่ตรวจ: `mx080-m6-6c490e47a956`.

## โครงสร้างข้อมูลและ transaction

เขียนเพิ่มเฉพาะตารางต่อไปนี้ใน localhost `ht9046mx_analytics`:

- `ht9046mx_rehearsal_input`: สำเนา source ของช่วงทดสอบ; `(run_id, ingestion_id)` และ JSON payload
- `ht9046mx_rehearsal_stream`: cursor, revision, frozen run contract และ stream/scorer checkpoint
- `ht9046mx_rehearsal_batch`: durable receipt พร้อม payload/as_of/cursor digest
- `ht9046mx_rehearsal_evidence`: window, score, reason, version และ `available_at`; unique run × machine × module × minute

ไม่มีการเขียน source table `ht9046mx_iot.ht9046mx_readings`, Active Profile, PM Alert หรือ technician feedback ตารางเดิม ข้อมูลทดสอบคงอยู่สำหรับเปิดกราฟ/ตรวจซ้ำ ไม่ได้ลบข้อมูลเดิม

```text
Archived MX080 second-level Parquet
        ↓ explicit local-only copy
rehearsal_input (monotonic ingestion_id)
        ↓ fetch complete ID slice per simulated 5-minute delivery
lock rehearsal_stream row
        ↓ restore stream + scorer
qualified 1-minute windows → unchanged primary scorer
        ↓ ONE TRANSACTION
evidence + batch receipt + source cursor + both checkpoints
        ↓ GET /api/v1/rehearsal/{run_id}/points
local Dashboard: pressure / differential / temperature / valve / score
```

Crash ก่อน commit จะไม่เหลือผลบางส่วน; retry หลัง commit ตรวจ durable receipt ก่อนประมวลผล ไม่อาศัย memory receipt 32 รายการเพียงอย่างเดียว หาก batch เดิมเปลี่ยน payload/cursor/as_of จะถูกปฏิเสธ Profile/parameter/policy เปลี่ยนต้องเริ่ม run ใหม่

## Profile และความหมายของกราฟ

อ้างอิง candidate fitted จาก 3–6 กันยายนก่อนช่วงตรวจ มีเพียง **4 วัน** จึงยังไม่ผ่าน minimum 7 วันสำหรับ Active Profile ใหม่ ไม่ได้ใช้การ replay นี้ bypass approval หรือเรียกข้อมูลหลังเกิดปัญหาว่าปกติ

ใช้กฎ/threshold เดิม: nine-feature qualified mean, max absolute robust-z, persistence 3 qualified consecutive minutes; EWMA/CUSUM ยังคง numeric shadow evidence ไม่ส่ง Alert เพิ่ม การ replay รอบนี้ไม่ทำ HPO หรือเปลี่ยน threshold จาก case ที่ตรวจ

กราฟแยกหน่วย pressure, differential, temperature และ valve ออกจากกัน หน่วยแสดงเป็น source units เพราะ metadata ของไฟล์ยังไม่ใช่การยืนยัน calibration หน้างาน Score ratio = primary score / profile threshold; ≥1 หมายถึงเกิน threshold ไม่ใช่ probability หรือ Health Score

แดง = persistent deviation ตามกฎ; พื้นขาวไม่ยืนยันเครื่องปกติ เส้นขาด = unavailable/unqualified minute ไม่ได้ interpolate ตารางล่างแสดง `window_start`, `available_at`, status และ reason ช่วงก่อน case ที่ถูก flag ไม่ได้ถูกยืนยันว่าเป็น false positive

ตรวจ rendered Desktop view ครบทั้ง 5 กราฟและตาราง เห็น pressure shift, ช่องว่างและแถบแดงจริง; narrow/mobile viewport ยังไม่ได้ตรวจ Build ผ่าน มี bundle-size warning ที่มีอยู่ใน build

## เปิดหรือรันซ้ำ

จาก project root:

```powershell
python -m notebooks.support.mysql_incremental_rehearsal
python -m pytest apps/api/tests/test_qualified_persistence.py apps/api/tests/test_qualified_stream.py apps/api/tests/test_qualified_temporal.py -q
```

สคริปต์อ่าน credentials จาก `apps/api/.env` โดยไม่แสดง secrets ตรวจ target ต้องเป็น localhost สร้าง run ID ใหม่แต่ละครั้งและเก็บหลักฐานรอบก่อน

API จาก `apps/api` (flag นี้ตั้งเฉพาะ process ทดสอบ ไม่ได้แก้ `.env`):

```powershell
$env:HT9046MX_LOCAL_REHEARSAL_DASHBOARD_ENABLED='true'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend จาก `apps/web`:

```powershell
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

เปิด `http://127.0.0.1:5174/?rehearsal=mx080-m6-6c490e47a956` หรือเปลี่ยน run ID ตามผลสคริปต์ API view disabled โดย default และปฏิเสธ remote analytics host ไม่แทรก run นี้เข้า operational Alert queue

## สิ่งที่ยังไม่พิสูจน์ / ขั้นถัดไป

1. Source table ปัจจุบันมี `id` primary key แต่ cursor ของการทดลองเป็น ingestion ID ของสำเนาทดสอบ ไม่ใช่การยืนยัน exactly-once จาก source จริง MySQL auto-increment ID อาจ commit ไม่เรียง ID; production ต้องตรวจ ingestion contract หรือใช้ overlap/dedup/CDC ไม่เพียงเอา `MAX(id)` แล้วถือว่าไม่มีแถวตกหล่น
2. ยังไม่ได้เชื่อม worker รับข้อมูลใหม่อัตโนมัติ หรือตรวจ concurrent multi-process/writer, multi-machine load, network failure และ Server clock
3. ยังไม่มี matching reviewed one-minute Active Profile ในการทดสอบนี้ ขั้นถัดไปคือต่อ read-only source ingestion ที่จัดการ late commit ได้ และ replay ผ่าน strict Active loader; ถ้า Profile ไม่ผ่านต้องแสดง `NO_ACTIVE_PROFILE` ไม่ใช้ candidate แทนเงียบ ๆ
4. การทดลองนี้พิสูจน์ persistence/transport ของช่วงข้อมูลที่ระบุ ไม่ยืนยัน specificity ของ detector, fault accuracy, cause หรือ production readiness

ไฟล์หลัก: `qualified_persistence.py`, `mysql_incremental_rehearsal.py`, `test_qualified_persistence.py`, `RehearsalDashboard.tsx` และ local-only endpoint ใน `main.py`.
