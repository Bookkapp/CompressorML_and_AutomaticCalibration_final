# HT9046MX — ML Analytics Database Deployment

> **2026-09-25 one-minute amendment:** The selected Cold feature/profile contract is now `qualified-cold-observed-1m-v1` from actual observed seconds. The existing registry can receive candidates and future three-day shadow points, but the inference worker is only a read-only preview; do **not** enable score/Health/PM alert writes on `10.195.17.73` from this code. Previous five-minute setup instructions below are historical. Verify raw-second cadence, source clock/unit/codebook/service provenance, independently reviewed approval, rollback and fresh Server shadow first. See `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

**Target Analytics MySQL host:** `10.195.17.73`  
**Deployment mode:** Phase 7 read-only shadow screening  
**Status:** Server setup guide prepared. The owner-selected scoring path is now **Active-Profile robust-z rule only**, not a `cold-state-relationship-v2`/ARX release; see `deployment/RULE_ONLY_ACTIVE_PROFILE_PIPELINE.md`. Five-minute inference parity, source/time/unit, secure approval, fresh shadow, alert budget and rollback acceptance remain open. No connection, schema creation, model activation or machine-control action has been performed from this workspace.


อ่านร่วมกับ:

1. `README_System.md` — Data Contract และขอบเขตผลลัพธ์
2. `SOT.md` — สถานะและ blocker ล่าสุด
3. `deployment/README_Server_Shadow.md` — release/model contract
4. `deployment/mysql_shadow_schema.sql` — ตาราง output ปัจจุบัน
5. `deployment/CODEX_SERVER_HANDOFF.md` — งานที่ Codex บน Server ต้องทำ

## 1. เป้าหมายของฐานข้อมูลนี้

```text
Raw telemetry source (read-only)
        ↓
Analytics worker: validate → state gate → feature → score → persistence
        ↓
10.195.17.73 / dedicated analytics schema (append-only)
        ↓
Read-only Web App + technician review
```

ฐานนี้เก็บเฉพาะผลวิเคราะห์และหลักฐานที่อธิบายผล ไม่เก็บคำสั่งควบคุมเครื่อง ไม่มี worker ใดเขียนกลับ PLC หรือแก้ข้อมูลต้นทาง

ตารางที่มีใน Phase 7:

| Table | เก็บอะไร | ใช้ทำอะไร |
|---|---|---|
| `ht9046mx_shadow_score` | score ทุกจุด scoring, gate/status, version, evidence | ดู trend และตรวจ reproducibility |
| `ht9046mx_shadow_alert_episode` | ช่วง persistent pattern ที่เปิดเป็น alert | จัดลำดับให้ช่างตรวจ |
| `ht9046mx_shadow_audit_event` | contract failure, restart, late-data, checksum และ audit | QA/monitoring และสืบค้นปัญหาระบบ |
| `ht9046mx_maintenance_outcome` | ผลตรวจ/ซ่อมแบบ legacy | ไม่ใช้เป็น source ของ prospective binary label |
| `ht9046mx_calibration_batch` | ขอบเขต historical calibration และ shadow 3 วันของแต่ละรอบ | audit/reproduce candidate run |
| `ht9046mx_calibration_profile` | robust profile ต่อ machine/module/SV/state พร้อม gate/reason/statistics | Review ก่อนเปลี่ยน active pointer |
| `ht9046mx_calibration_shadow_point` | local-deviation score และ threshold ทุก qualified shadow window | กราฟ review เขียว/แดง 3 วัน |
| `ht9046mx_active_calibration_profile` | active pointer และ exact rollback mode/profile | shadow scorer อ่าน profile ที่อนุมัติ |
| `ht9046mx_calibration_review` | append-only approve/reject audit | governance และ retrain/profile lineage |


## 2. สิทธิ์และการแยกฐานข้อมูล


- **Source database user:** `SELECT` เท่านั้นบน telemetry table/view ที่ owner อนุมัติ
- **Analytics database user:** สิทธิ์เฉพาะ schema analytics สำหรับ `SELECT`, `INSERT`, `UPDATE` ที่จำเป็นต่อ idempotent upsert และการอ่านผ่าน Web App
- ให้ DBA เป็นผู้สร้าง database, user, network rule, backup policy และ TLS policy ตามมาตรฐานหน้างาน

ชื่อ schema แนะนำ: `ht9046mx_analytics` แต่ DBA เปลี่ยนชื่อได้หากใส่ค่าเดียวกันใน environment configuration

## 3. Environment configuration


```dotenv
# Raw telemetry source: read-only. เติมค่าจริงบน Server
HT9046MX_SOURCE_DB_HOST=
HT9046MX_SOURCE_DB_PORT=3306
HT9046MX_SOURCE_DB_NAME=
HT9046MX_SOURCE_DB_USER=
HT9046MX_SOURCE_DB_PASSWORD=
HT9046MX_SOURCE_TABLE=
HT9046MX_SOURCE_TIMESTAMP_COLUMN=recorded_at
HT9046MX_SOURCE_MACHINE_COLUMN=machine_number
HT9046MX_SOURCE_TIMEZONE=

# ML analytics output: owner-confirmed target host
HT9046MX_ANALYTICS_DB_HOST=10.195.17.73
HT9046MX_ANALYTICS_DB_PORT=3306
HT9046MX_ANALYTICS_DB_NAME=ht9046mx_analytics
HT9046MX_ANALYTICS_DB_USER=
HT9046MX_ANALYTICS_DB_PASSWORD=
HT9046MX_ANALYTICS_DB_TLS_MODE=
HT9046MX_TECHNICIAN_FEEDBACK_START_AT=2026-09-15T00:00:00+07:00
HT9046MX_ALERT_DATETIME_TIMEZONE=UTC

# Server has trained/recalibrated and versioned cold-state-relationship-v2.
HT9046MX_PROJECT_ROOT=/opt/OPERATION_P
HT9046MX_RELEASE_MANIFEST=
HT9046MX_PROFILE_CANDIDATE_ENABLED=true
HT9046MX_PROFILE_HISTORY_DAYS=30
HT9046MX_PROFILE_SHADOW_DAYS=3
HT9046MX_PROFILE_RETRY_MIN_NEW_DAYS=3
HT9046MX_PROFILE_STATE_CONTRACT_VERSION=
HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION=
HT9046MX_PROFILE_SERVICE_EPOCH_VERSION=
```

ถ้า telemetry และ analytics อยู่ host เดียวกัน ให้ใส่ host เดียวกันได้ แต่ต้องใช้ account และสิทธิ์แยกกันอยู่ดี

## 4. ขั้นตอนสำหรับ DBA

1. ยืนยันว่า `10.195.17.73` เป็น MySQL endpoint ที่อนุญาตให้ Server worker เชื่อมต่อได้
2. สร้าง schema analytics และ user เฉพาะงานตามมาตรฐานขององค์กร
3. เปิด firewall เฉพาะจาก analytics worker ไปยัง port MySQL ที่ DBA กำหนด
4. ใช้ TLS หาก infrastructure รองรับ/บังคับ
5. ตั้ง backup, restore test และ retention สำหรับ analytics schema
6. บันทึกชื่อ schema, timezone policy และ DBA owner ใน deployment record

ตัวอย่างคำสั่งด้านล่างเป็น **template สำหรับ DBA** เท่านั้น ต้องแทน placeholder และตรวจ security policy ก่อนรัน:

```sql
CREATE DATABASE IF NOT EXISTS ht9046mx_analytics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- GRANT SELECT, INSERT, UPDATE ON ht9046mx_analytics.* TO 'ht9046mx_analytics'@'<worker-host>';
```

จากนั้นเลือก schema และ apply ตาราง output ที่ versioned ใน repository:

```bash
mysql --host=10.195.17.73 --port=3306 --user="$HT9046MX_ANALYTICS_DB_USER" --password \
  --database="$HT9046MX_ANALYTICS_DB_NAME" \
  < deployment/mysql_shadow_schema.sql
```

หลังจากนั้นให้ DBA review/apply registry และ technician confirmation schema ตามลำดับ:

```bash
mysql --host=10.195.17.73 --port=3306 --user="$HT9046MX_ANALYTICS_DB_USER" --password \
  --database="$HT9046MX_ANALYTICS_DB_NAME" \
  < deployment/mysql_phase6_calibration_registry.sql
```

Worker calibration ใช้ source MySQL account แบบ `SELECT` เท่านั้น, หา latest timestamp ของ source, ใช้ย้อนหลัง 30 วันและแยกสามวันท้ายเป็น future-only shadow. `HT9046MX_SOURCE_TIMEZONE`, state-contract/codebook/service-epoch version ต้องถูกยืนยันก่อน profile จะเป็น `READY_FOR_APPROVAL`. สีเขียว/แดงใน Web App คือ score ต่ำกว่า/เกิน candidate threshold ไม่ใช่ health percentage หรือ fault probability.

การกด Approve เป็น human-gated transaction ต่อ profile เท่านั้น: profile ที่เลือกต้อง ready, audit review ถูก append, active pointer ของ key นั้นเปลี่ยนพร้อม rollback. รอบแรก rollback mode คือ `NO_ACTIVE_PROFILE_FAIL_CLOSED`; รอบถัดไปชี้ไป previous active profile. Reject ไม่แก้ active pointer ของ key นั้น และ worker จะรอจำนวนวันข้อมูลใหม่ตาม `HT9046MX_PROFILE_RETRY_MIN_NEW_DAYS` ก่อนสร้าง batch ใหม่.

`mysql_shadow_schema.sql` ใช้ `CREATE TABLE IF NOT EXISTS` จึงรันซ้ำได้สำหรับ schema ที่ว่างหรือมีตารางรุ่นเดิม แต่ DBA ต้อง review migration ที่เปลี่ยน schema ในอนาคตก่อนเสมอ

## 5. สิ่งที่ worker ต้องทำก่อนเขียนข้อมูล

1. อ่าน `shadow_release_manifest.json` และตรวจ checksum ของ model
2. map source columns ไป canonical contract และยืนยัน unit/timezone
3. ใช้ watermark + deterministic source key เพื่อรองรับ restart/late arrival โดยไม่สร้าง score ซ้ำ
4. gate ข้อมูลที่ missing, stale, out-of-order, unit/timezone unknown หรือ state ไม่เทียบเคียงเป็น `DATA_QUALITY` / `INSUFFICIENT_PROFILE`
5. score เฉพาะ manifest ของ `cold-state-relationship-v2` ที่ผ่าน temporal/LOMO/shadow validation แล้ว: cadence 5 นาที, threshold จาก manifest และ persistence ที่ versioned พร้อม release


## 6. การใช้ผลใน Web App

Web App มีสิทธิ์อ่าน analytics schema และต้องแสดง:

- Machine, Module, state/SV, score, persistence และ evidence
- `DATA_QUALITY` / `INSUFFICIENT_PROFILE` แยกจาก equipment alert
- `Normal within this profile` เฉพาะเมื่อ data/profile gate ผ่านและไม่พบ persistent anomaly; ไม่ใช่คำรับรองว่าเครื่องปกติทุกด้าน
- ข้อความ `Shadow screening — not confirmed diagnosis`

Phase 8/9 ของระบบปัจจุบันรองรับเฉพาะ prospective binary anomaly confirmation และ supervised binary anomaly model ในอนาคต. ไม่มีแผนเพิ่ม cause candidates หรือเปอร์เซ็นต์จาก technician note/binary label; ความสามารถนั้นต้องเริ่ม contract ใหม่หากมีความจำเป็นจริง

## 7. Data retention และการป้องกันข้อมูล

- `shadow_alert_episode` และ `shadow_audit_event`: เก็บนานพอสำหรับ rollback/replay investigation
- `technician_confirmation`: จำกัดสิทธิ์อ่าน/แก้ตาม role เพราะเป็น prospective label ที่ต้องผ่าน QA
- เก็บ release, feature, profile และ threshold version ทุก score เพื่อ replay ได้

## 8. Acceptance checklist ก่อนเปิด worker แบบ Shadow

- [ ] DBA ยืนยัน host `10.195.17.73`, schema, network path, backup และ restore owner
- [ ] สร้าง Cold-only release จาก source history: `Status=Compressor ON`, `Status_n=On`, `Busy=0`, `SV=Off`; verify `dp1=Hp_1st−Lp_1st` และ `dp2=Hp_2nd−Lp_2nd` ใน feature contract
- [ ] Rerun temporal and leave-one-machine-out validation without tuning on those outer tests; record release manifest, threshold and persistence
- [ ] Source telemetry mapping ได้รับการยืนยัน; source worker เป็น read-only
- [ ] Analytics user มีสิทธิ์ขั้นต่ำและไม่มี PLC/source write permission
- [ ] Unit pressure, timezone, unique key และ late-arrival policy ผ่านการตรวจ
- [ ] Schema apply สำเร็จบน staging และ worker สามารถเขียน idempotently
- [ ] Offline parity + restart checkpoint + MX-080 fixture ผ่านบน Server
- [ ] Missing/stale/out-of-order input สร้าง `DATA_QUALITY` โดยไม่สร้าง equipment alert
- [ ] Alert budget แยกต่อ machine/day ได้รับการอนุมัติ โดย review MX058/MX082 แล้ว
- [ ] Exact rollback release ได้ถูกลงทะเบียน
- [ ] Web App เป็น read-only และมีข้อความ capability boundary ชัดเจน
- [ ] ไม่มี route หรือ database privilege ที่ใช้ส่งคำสั่งกลับ PLC/safety control

จนกว่ารายการข้างต้นจะครบ สถานะ deployment คือ `SHADOW_ONLY_NOT_AUTHORIZED` แม้ตารางถูกสร้างเรียบร้อยแล้ว



## Change log

- 2026-09-25 — Updated the selected scoring path to Active-Profile robust-z only and linked its current-versus-target pipeline; no DB setup or Server acceptance was performed.

- 2026-09-15 — Replaced the future cause-taxonomy proposal with a prospective binary technician-confirmation contract. The new Phase 8 migration is `mysql_phase8_confirmation_only.sql`; no database was connected or changed.

- 2026-09-14 — Created deployment guide for the owner-specified analytics MySQL target `10.195.17.73`. The guide separates raw telemetry read access from append-only analytics writes; no connectivity, database mutation or deployment was performed.
