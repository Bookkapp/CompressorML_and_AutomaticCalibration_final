# HT9046MX Analytics Web App

**1 Oct workflow:** Daily work reports/Service Logs belong to the separate Compressor Dashboard. Operation manages Profile/shadow/approval/recalibration and shows local read-only Episode QA. New archive persistence and Dashboard incident-time snapshots are tested locally, not connected to the live Alert bridge. Setup/QA: [Episode/Dashboard workflow](../deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md).

โค้ดในโฟลเดอร์นี้เป็น Web App สำหรับนำผลวิเคราะห์แบบ Shadow ไปใช้งานบน Server โดยไม่เขียนคำสั่งกลับ PLC ตัวหน้าจอเป็น React/Vite ที่สามารถนำไปแก้ต่อใน Lovable ได้ และ Backend เป็น FastAPI ซึ่งอ่านผลจาก MySQL analytics database และรับผลตรวจจากช่างแบบ append-only

**สถานะล่าสุด 2026-09-25:** Auto-Calibration ใช้ raw วินาทีจริงสร้าง completed 1-minute Cold candidate และกราฟ Shadow 3 วันได้; Dashboard refresh ทุก 5 นาที. Live inference ยังเป็น read-only preview เท่านั้น จึงยังไม่มี 1-minute Health/alert writer ที่อนุญาตให้ใช้จริง และ Active Profile เก่าใช้กับเวอร์ชันใหม่นี้ไม่ได้. ดู `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

## สิ่งที่ระบบนี้ทำ

- Dashboard refresh ทุก 5 นาที; หน้าต่าง candidate/scoring ที่เลือกใหม่คือ 1 นาทีจาก raw-second Cold ที่ผ่าน quality gate. release `phase07-shadow-replay-v2-hp180` เป็น historical-only และไม่มี live writer ที่อนุมัติแล้ว
- แสดงกราฟ Pressure, Temperature, Valve และ Anomaly บนแกนเวลาเดียวกัน
- Highlight ช่วง Persistent anomaly โดยระบุชัดว่าไม่ใช่ confirmed fault
- ให้ช่างดูกราฟของ alert ใหม่ แล้วตอบเพียงว่าพบความผิดปกติของเครื่องจริงหรือไม่
- เก็บคำตอบแบบ binary เป็น `PENDING_QA` ก่อนอนุญาตให้ใช้เป็น label สำหรับ retraining
- สร้าง Profile candidate รายวัน และ Model candidate รายสัปดาห์ แต่ไม่ Activate อัตโนมัติ
- สร้าง calibration candidate จาก historical raw MySQL แบบ read-only แยก Machine–Module–SV–qualified state แล้ว shadow ช่วง 3 วันล่าสุด พร้อมกราฟ review สีเขียว/แดง ปัจจุบันรับ baseline อัตโนมัติเฉพาะ Compressor ON + `Status_n=On` + `Busy=0` + `SV=Off` (Cold); `Busy=1` และ `SV=On` ถูกกันออกจนกว่าจะมี state rule รองรับ
- ก่อน aggregate ทุก candidate cycle จะตรวจ duplicate key `machine_number × recorded_at`; หากพบแม้หนึ่ง key ให้หยุดแบบ fail-closed แทนการเฉลี่ยแถวที่ขัดกัน และ watermark จะรวม batch ที่ `PARTIALLY_REVIEWED` เพื่อไม่สร้าง candidate ซ้ำจาก snapshot เดิม

Health Score และ cause percentage ยังไม่เปิดใช้ เพราะยังไม่มี calibration/technician labels เพียงพอ หน้าจอไม่แสดงหรือเก็บสาเหตุใน Phase 8 นี้; จุดมุ่งหมายคือสร้าง binary anomaly-confirmation labels ที่ตรวจสอบย้อนกลับได้

## โครงสร้าง

```text
apps/
├── api/                 FastAPI, MySQL repository และ scheduler
│   ├── app/main.py      API endpoints
│   ├── app/worker.py    รอบ scoring/profile/model candidate
│   ├── app/demo.py      Preview จาก verified offline artifacts
│   └── tests/           API และ contract tests
└── web/                 React/Vite frontend สำหรับ Lovable handoff
    └── src/App.tsx      Dashboard, timeline และ technician review
```


## ทดลองดูบนเครื่องโดยไม่ต่อ Database

Demo mode อ่าน verified Phase 7 artifacts ที่มีใน repository และไม่ยอมบันทึกข้อมูลช่าง

```bash
python -m venv .venv
.venv/Scripts/pip install -r apps/api/requirements.txt
.venv/Scripts/uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

เปิดอีก Terminal:

```bash
cd apps/web
npm install
npm run dev
```

จากนั้นเปิด `http://localhost:5173`

## ตั้งค่าบน Server

1. ให้ DBA ตรวจและ apply schema เดิม `deployment/mysql_shadow_schema.sql`
2. ให้ DBA ตรวจและ apply `deployment/mysql_phase6_calibration_registry.sql`
3. ให้ DBA ตรวจและ apply `deployment/mysql_phase8_confirmation_only.sql`
4. คัดลอก `apps/api/.env.example` เป็นไฟล์ secret ของ Server แล้วใส่ credential จริงนอก Git
5. ตั้ง `HT9046MX_APP_MODE=live`
6. ตั้ง host analytics database เป็น `10.195.17.73`
7. ยืนยัน source timezone, pressure unit, wide-column mapping และ service epoch ก่อนเปิด built-in calibration worker
8. ตั้ง `HT9046MX_PROFILE_CANDIDATE_ENABLED=true` หลัง schema/mapping ผ่าน staging; worker จะใช้ historical 30 วันและ shadow 3 วันโดยค่าเริ่มต้น โดยรับเฉพาะ Cold-qualified windows
9. ใช้ historical source สร้าง `cold-state-relationship-v2`: refit profile ที่มี `dp1/dp2`, retrain/recalibrate ภายใน temporal development split, รัน LOMO และ shadow สามวัน; บันทึก manifest/checksum/threshold/persistence ที่ได้
10. รัน API, Web และ worker ด้วย Docker Compose หรือ service manager ของ Server

คำสั่งตัวอย่าง:

```bash
docker compose -f deployment/docker-compose.analytics.yml --env-file deployment/.env.analytics up -d --build
```


```dotenv
HT9046MX_APP_MODE=live
HT9046MX_ANALYTICS_DB_HOST=10.195.17.73
HT9046MX_ANALYTICS_DB_PORT=3306
HT9046MX_ANALYTICS_DB_NAME=ht9046mx_analytics
HT9046MX_ANALYTICS_DB_USER=REPLACE_ON_SERVER
HT9046MX_ANALYTICS_DB_PASSWORD=REPLACE_ON_SERVER
HT9046MX_DASHBOARD_REFRESH_MINUTES=5
HT9046MX_SCORING_INTERVAL_MINUTES=1
# HT9046MX_TECHNICIAN_FEEDBACK_START_AT=<APPROVED_ISO8601_WITH_OFFSET>
# Confirmed timezone semantics of ht9046mx_shadow_alert_episode.detected_at.
HT9046MX_ALERT_DATETIME_TIMEZONE=
HT9046MX_SOURCE_DB_HOST=REPLACE_READ_ONLY_SOURCE_HOST
HT9046MX_SOURCE_DB_NAME=ht9046mx_iot
HT9046MX_SOURCE_DB_USER=REPLACE_READ_ONLY_SOURCE_USER
HT9046MX_SOURCE_DB_PASSWORD=REPLACE_ON_SERVER
HT9046MX_SOURCE_TABLE=ht9046mx_readings
HT9046MX_SOURCE_TIMEZONE=REPLACE_CONFIRMED_IANA_TIMEZONE
HT9046MX_SOURCE_PRESSURE_UNIT=REPLACE_CONFIRMED_PSIG_OR_PSIA
HT9046MX_PROFILE_WINDOW_CONTRACT=qualified_observed_1m
HT9046MX_QUALIFIED_1M_PREVIEW_ENABLED=false
HT9046MX_PROFILE_CANDIDATE_ENABLED=true
HT9046MX_PROFILE_STATE_CONTRACT_VERSION=REPLACE_VERIFIED_VERSION
HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION=REPLACE_VERIFIED_VERSION
HT9046MX_PROFILE_SERVICE_EPOCH_VERSION=REPLACE_VERIFIED_VERSION
HT9046MX_SHADOW_SCORE_CRON=* * * * *
HT9046MX_PROFILE_CANDIDATE_CRON=0 2 * * *
HT9046MX_MODEL_CANDIDATE_CRON=0 3 * * 0
```

`HT9046MX_SHADOW_SCORE_COMMAND` ต้องเว้นว่างจนกว่า one-minute live writer จะผ่าน Server staging/approval; ตารางทุกหนึ่งนาทีไม่ได้ทำให้ read-only preview กลายเป็น live scorer. เมื่อเปิด `HT9046MX_PROFILE_CANDIDATE_ENABLED=true` จะใช้ built-in calibration worker แทนคำสั่ง candidate ภายนอก. รายละเอียด gate อยู่ใน `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

เมื่อ `HT9046MX_PROFILE_CANDIDATE_ENABLED=true` profile worker จะใช้ built-in pipeline แทน `HT9046MX_PROFILE_CANDIDATE_COMMAND`: อ่าน source MySQL แบบ `SELECT` เท่านั้น, fit retained-calibration profile, แล้วเก็บ shadow 3 วันลง registry. กราฟสีเขียวแปลว่า score ต่ำกว่า candidate threshold และสีแดงแปลว่าเกิน threshold; ไม่ใช่เปอร์เซ็นต์หรือคำยืนยันว่าเครื่องเสีย. ปุ่ม Approve ต้องมี authenticated production approver และทำงานได้เมื่อ profile ที่เลือกเป็น `READY_FOR_APPROVAL` เท่านั้น.

## Technician feedback loop

1. ระบบสร้าง alert episode หลังผ่าน data/state/profile gate และ persistence 3 รอบ
2. API รับเฉพาะ alert ที่ `detected_at` อยู่หลัง `HT9046MX_TECHNICIAN_FEEDBACK_START_AT`; alert เก่าจะถูกปฏิเสธ โดยต้องตั้ง `HT9046MX_ALERT_DATETIME_TIMEZONE` ให้ตรงกับ semantic ของ MySQL `DATETIME(6)` ก่อน มิฉะนั้น API จะ fail closed
3. หน้า Incident แสดงกราฟและเวลาที่ระบบพบ pattern แล้วช่างเลือกเพียง `EQUIPMENT_ANOMALY`, `NO_EQUIPMENT_ANOMALY` หรือ `UNRESOLVED`
4. API เก็บ record ใหม่แบบ append-only พร้อม policy version และสถานะ `PENDING_QA`; ไม่มี cause, action หรือ refrigerant field
5. Reviewer ตรวจเวลา, identity, หลักฐาน และความสอดคล้องของคำตอบ
6. เฉพาะ `EQUIPMENT_ANOMALY` และ `NO_EQUIPMENT_ANOMALY` ที่ผ่าน QA จึงเข้าสู่ dataset version ใหม่สำหรับ temporal + leave-one-machine-out binary supervised validation; `UNRESOLVED` และ free-text note ไม่เป็น target

การพบ pattern คล้ายกันในเครื่องอื่นเป็นเพียง suspect evidence ไม่ใช่การยืนยัน fault. Phase 8 นี้ไม่สร้าง cause taxonomy, cause classifier หรือ cause percentage


## Production boundary

- ไม่มี endpoint สำหรับ PLC write หรือ machine control
- การเปลี่ยน profile/model/threshold ต้องมี version, shadow validation, approval และ rollback target
- Server ต้องมี SSO หรือ reverse-proxy authentication, TLS, role-based authorization และ audit log ก่อนให้ช่างใช้งานจริง
- Demo mode เป็น read-only; Live mode ที่ไม่มี MySQL credential จะ fail closed ด้วย HTTP 503
- Live mode ที่ไม่ตั้ง `HT9046MX_TECHNICIAN_FEEDBACK_START_AT` จะปฏิเสธ technician confirmation เพื่อไม่ให้ historical alert กลายเป็น prospective label
- Live mode ที่ไม่ยืนยัน `HT9046MX_ALERT_DATETIME_TIMEZONE` จะปฏิเสธ technician confirmation เพราะ `detected_at` เป็น `DATETIME(6)` ที่ไม่พก timezone
