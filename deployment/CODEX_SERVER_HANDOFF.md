# OPERATION_P — Codex Server Deployment Handoff

## Latest entry point — 6 October 2026

When the owner says **“Set up ระบบนี้ให้หน่อย”** on Server **10.195.17.73**, use [SERVER_WORKER_HANDOFF_20261006.md](SERVER_WORKER_HANDOFF_20261006.md) after the repository's required reading order. It covers the shipped durable observation/Fleet Shadow worker, explicit additive migration, frozen package installation, authenticated management, restart/retry/multi-tab acceptance and rollback. Earlier plans below are historical context. No remote installation was performed from the development PC.

## Latest feature handoff — 2 October 2026

**Storage repair checkpoint:** Existing Reference job migration has now been applied to normal localhost analytics (not the target Server). Include the updated `reference_jobs.py`/`main.py`/ReferenceReview frontend together: normal polling is read-only, expiration is primary-key scoped, and missing-table/schema/busy/connection errors are distinct. CREATE IF NOT EXISTS will not repair incompatible existing columns. Read `deployment/REFERENCE_STORAGE_REPAIR_20261002.md` for147tests/build/100concurrent-local-poll evidence and Server acceptance limits. Local Preview success is not Active approval or Server migration completion.

Before enabling the new Operation Reference-review UI, read `deployment/REFERENCE_REVIEW_WORKFLOW.md` and apply `deployment/mysql_reference_review.sql` explicitly to analytics after the existing registry schema. Configure the observed 1m source contract/timezone and 3-day Shadow; bind `X-Approver-Id` to an authenticated role rather than trusting a typed header. Test real source clock/late commits, retries/restart/rollback and selected-batch Approval on Server separately. The UI uses historical complete-day Shadow and reviewed fit dates/exclusions; old scheduled/legacy rolling calibration remains a different route. Primary scorer/threshold/Active approval are unchanged. Local 106-test/build/archived-MX080 QA is not Server acceptance; local QA script/harness must not be used as production data adapter. No Server installation/activation or Git push was performed in this implementation work.

**Updated:** 2026-09-14, Asia/Bangkok
**Target:** Codex session running on the Server that hosts or can reach the production-like MySQL source
**Starting mode:** Read-only shadow integration
**Activation state:** `SHADOW_ONLY_NOT_AUTHORIZED`


## 1. Prompt สำหรับส่งให้ Codex บน Server

คัดลอกข้อความด้านล่างเป็นข้อความแรกของงานบน Server:

```text
รับช่วงโปรเจกต์ OPERATION_P สำหรับ HONTECH HT9046-MX จาก repository นี้


ก่อนทำงานให้อ่านไฟล์ตามลำดับ:
1. README_System.md
2. SOT.md
3. HANDOFF.md
4. Project.md
5. Roadmap.md
6. AGENTS.md
7. deployment/SYSTEM_DEPLOYMENT_FLOW.md
8. deployment/README_Server_Shadow.md
9. deployment/CODEX_SERVER_HANDOFF.md
10. deployment/mysql_shadow_schema.sql
11. deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md
12. notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/shadow_release_manifest.json


จากนั้น implement ระบบเป็นส่วนแยก: ingestion, canonical mapping, data/state gate, one-second ring buffer, minute features, version/checksum guard, ARX-Ridge shadow scoring, persistence, append-only MySQL writes, read-only API, monitoring และ tests




ก่อนเริ่ม service ให้รัน offline parity และ MX-080 fixture. หลังเชื่อม MySQL ให้รัน shadow เท่านั้น เก็บ score/alert/audit แบบ append-only และรายงาน latency, restart parity, duplicate prevention, data-quality rate และ alert burden แยกแต่ละเครื่อง

```

## 2. ข้อเท็จจริงที่ล็อกไว้ก่อนเริ่มงาน

ค่าต่อไปนี้ต้องอ่านยืนยันจาก `shadow_release_manifest.json` อีกครั้งเมื่ออยู่บน Server:

| Item | Locked value |
|---|---|
| Replay release | `phase07-shadow-replay-v2-hp180` |
| Registry | `phase07-shadow-registry-v2-hp180` |
| Model | `ARX-Ridge__seed_13` |
| Model selection | Inner temporal validation only |
| Feature version | `minute-relative-regime-hp180-v3` |
| Profile version | `machine-module-sv-train-only-hp180-v3` |
| Threshold version | `past-calibration-q995-hp180-v2` |
| Threshold | `7.650715626730769` |
| Scoring cadence | 5 minutes |
| Persistence | 3 consecutive qualified windows |
| Claim level | Anomaly screening only |
| Auto activation | `false` |
| Rollback | Blocked: no prior `ACTIVE_FROZEN` release |

The release manifest and model checksum are authoritative. If this table and the manifest disagree, stop and use the manifest only after reviewing the repository history and recording the discrepancy.

## 3. Repository และ Git LFS

บน Server ให้ตรวจว่า Git LFS พร้อมก่อนเริ่มงาน:

```bash
git lfs install
git clone https://github.com/Bookkapp/CompressorML_and_AutomaticCalibration.git
cd OPERATION_P
git lfs pull
git lfs ls-files
git status --short
```

ตรวจเพิ่มเติมว่าไฟล์ต่อไปนี้เป็นไฟล์จริง ไม่ใช่ LFS pointer:

```text
HT9046MX-20260902T013607Z-1-001/.../*.parquet
notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet
notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/models/ARX-Ridge__seed_13.portable.joblib
```


## 4. สิ่งที่มีอยู่แล้วใน Repository

### พร้อมใช้เป็นหลักฐานและ reference implementation

- System/Data Contract: `README_System.md`
- ข้อเท็จจริงล่าสุด: `SOT.md`
- Logical deployment flow: `deployment/SYSTEM_DEPLOYMENT_FLOW.md`
- Server contract: `deployment/README_Server_Shadow.md`
- Append-only database schema: `deployment/mysql_shadow_schema.sql`
- Owner-specific analytics database guide: `deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md`
- Portable model, release manifest, replay scores และ failure tests:
  `notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/`
- Current local-profile artifact และ model registry:
  `notebooks/outputs/ht9046mx_phase7_benchmark_v2_hp180/model_local_profiles.parquet` และ `shadow_model_registry.json`
- Executed replay notebook:
  `notebooks/07_HT9046MX_Server_Shadow_Replay_Colab.ipynb`
- Feature/model builder reference:
  `notebooks/support/phase7_benchmark.py`
- Deterministic replay reference:
  `notebooks/support/phase7_shadow_replay.py`
- Auto-bootstrap candidate lifecycle:
  `notebooks/06_HT9046MX_AutoBootstrap_Profile_Lifecycle_Colab.ipynb`

### ยังไม่มีและต้องสร้างบน Server

- Long-running MySQL ingestion worker
- Canonical source-column mapper ของ database จริง
- Live one-second ring buffer และ minute feature worker
- Model/profile/threshold registry service
- Persistent scoring service และ checkpoint store
- Read-only API และ Web App integration
- Runtime monitoring, alerting, retention และ backup policy
- Deployment service definition เช่น systemd, Docker Compose หรือ platform-native equivalent
- Exact rollback release และ rollback drill


### สิ่งที่ตั้งใจไม่ส่งขึ้น GitHub

- raw Parquet telemetry ทั้งชุด
- external intake canonical partitions
- historical/deprecated model releases
- intermediate feature matrices และ scored frames ที่สร้างซ้ำได้
- Python/Jupyter caches และ local editor files
- `.env`, credentials, tokens, private keys และ connection strings

รายการที่ไม่อยู่ใน Git ไม่ได้ถูกลบจากเครื่องวิเคราะห์เดิม Server Codex ต้องใช้ MySQL จริงสำหรับ live integration และขอ controlled data fixture เพิ่มเฉพาะเมื่อ parity test ที่มีอยู่ไม่พอ

## 5. Environment Variables


```text
HT9046MX_DB_HOST=
HT9046MX_DB_PORT=3306
HT9046MX_DB_NAME=
HT9046MX_DB_USER=
HT9046MX_DB_PASSWORD=
HT9046MX_SOURCE_TABLE=
HT9046MX_TIMESTAMP_COLUMN=
HT9046MX_MACHINE_COLUMN=
HT9046MX_SHADOW_OUTPUT_SCHEMA=
HT9046MX_PROJECT_ROOT=
HT9046MX_RELEASE_MANIFEST=notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/shadow_release_manifest.json
HT9046MX_SOURCE_TIMEZONE=
HT9046MX_PRESSURE_UNIT=
```


## 6. Canonical Source Contract

ทุก source row ต้องถูก map เป็น:

```text
machine_number, timestamp, global_status,
module, module_status, sv, busy,
hp1, lp1, hp2, lp2, valve, temphi, templo
```

ก่อนยอมรับ mapping ต้องตรวจ:

- source table และ primary/revision key
- timestamp resolution, timezone และ daylight-saving behavior ถ้ามี
- pressure unit ว่าเป็น psig/psia หรือหน่วยอื่น
- tag mapping ของ 8 modules
- duplicate timestamp และ late-arrival behavior
- null/sentinel values และ stale interval
- semantics ของ `Status_n`, `SV_n` และ `Busy_n`


## 7. Runtime Components ที่ต้อง Implement


```text
src/
  config/       environment validation and secret-safe settings
  ingest/       MySQL polling, watermark, late data and idempotency
  contract/     canonical mapping, schema, units and timestamps
  state/        qualification and transient exclusions
  features/     minute features and one-second ring summaries
  registry/     immutable release/profile/model metadata
  scoring/      model loading, checksum, threshold and persistence
  evidence/     explanation payload and alternative-cause categories
  storage/      append-only MySQL repositories
  api/          read-only Web App endpoints
  monitoring/   health, latency, drift and audit metrics
tests/
  unit/
  integration/
  replay/
  failure_modes/
```

### Runtime order

```text
MySQL source
→ read-only ingest + watermark
→ data contract validation
→ state qualification
→ 1-second ring + minute base
→ local Machine/Module/SV/State profile
→ relative/residual feature vector
→ checksum/version guard
→ cross-machine ARX-Ridge score
→ calibrated threshold
→ 3-window persistence
→ provisional condition/health view
→ append-only score/alert/audit
→ read-only API/Web App
→ technician outcome
```

## 8. Data-quality และ State Gate


- missing, stale, duplicate-conflict หรือ out-of-order input
- unknown unit/timezone
- Emergency Down
- MValveHome และ negative valve command
- pump-down/equalization
- start/stop transient
- ChangeValve หรือ SV/Status เปลี่ยนกลาง steady window
- profile ที่ไม่ตรง Machine + Module + SV + qualified state

ผลที่ถูกต้องคือ `DATA_QUALITY`, exclusion reason หรือ `INSUFFICIENT_PROFILE` ไม่ใช่ equipment fault

## 9. Dual-rate Feature Contract

- Minute stream เป็น durable operational base สำหรับ trend และ steady profile
- คำนวณ response 5/15/30/60/120 วินาที เช่น delta, slope, lag, gain และ settling
- บันทึก `available_at` ตามเวลาที่ feature พร้อมจริง
- Feature/scaler/profile ทุกตัว fit จาก training/calibration period เท่านั้น

Pressure rule ปัจจุบัน:

```text
Hp_2nd 180–230 psi = qualified field-reference band
Hp_2nd < 180 psi   = one-sided undercharge/leak screening evidence only
Hp_2nd > 230 psi   = separate high-side/local-deviation evidence
```

ไม่มีค่า pressure ใดยืนยัน leak, water-pipe problem หรือ tank-level cause เพียงลำพัง

## 10. Database Setup

ใช้ dedicated analytics schema และให้ Server/DB owner ตรวจ SQL ก่อน apply:

```bash
mysql --host "$HT9046MX_DB_HOST" \
      --port "$HT9046MX_DB_PORT" \
      --user "$HT9046MX_DB_USER" \
      --password \
      "$HT9046MX_DB_NAME" \
      < deployment/mysql_shadow_schema.sql
```

ก่อนเปิด prospective technician feedback ให้ DBA review และ apply เพิ่ม:

```bash
mysql --host "$HT9046MX_DB_HOST" \
      --port "$HT9046MX_DB_PORT" \
      --user "$HT9046MX_DB_USER" \
      --password \
      "$HT9046MX_DB_NAME" \
      < deployment/mysql_phase8_confirmation_only.sql
```

ก่อนเปิด built-in Auto-bootstrap worker ให้ DBA review และ apply เพิ่ม:

```bash
mysql --host="$HT9046MX_ANALYTICS_DB_HOST" --port="$HT9046MX_ANALYTICS_DB_PORT" \
  --user="$HT9046MX_ANALYTICS_DB_USER" --password \
  --database="$HT9046MX_ANALYTICS_DB_NAME" \
  < deployment/mysql_phase6_calibration_registry.sql
```

ตั้ง source MySQL credentials แบบ `SELECT` เท่านั้น และยืนยัน `HT9046MX_SOURCE_TIMEZONE`, column templates, `HT9046MX_PROFILE_STATE_CONTRACT_VERSION`, `HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION` และ `HT9046MX_PROFILE_SERVICE_EPOCH_VERSION` ก่อนตั้ง `HT9046MX_PROFILE_CANDIDATE_ENABLED=true`. Worker จะใช้ source history 30 วันและกัน 3 วันท้ายเป็น future-only shadow; ไม่เชื่อมต่อหรือเดา mapping หาก config เหล่านี้ไม่ครบ.

ตารางหลัก:

- `ht9046mx_shadow_score`
- `ht9046mx_shadow_alert_episode`
- `ht9046mx_shadow_audit_event`
- `ht9046mx_maintenance_outcome` (legacy service evidence; not a binary target)
- `ht9046mx_technician_confirmation` (prospective binary confirmation after Phase 8 migration)


## 11. Implementation Phases บน Server

### S0 — Environment audit

- ตรวจ OS, CPU, RAM, disk, Python และ process/container platform
- ตรวจ Git LFS object completeness
- ตรวจ network path ไป MySQL โดยไม่แสดง secret
- บันทึก source schema, timezone, unit และ row cadence
- ยังไม่สร้าง service ที่รันต่อเนื่อง

### S1 — Offline parity

- ติดตั้ง dependencies แบบ versioned และ reproducible
- โหลด release manifest และตรวจ model SHA-256
- รัน failure-mode tests เดิม
- รัน replay แบบ one-shot และ restart/checkpoint
- ยืนยัน MX-080 fixture ตามค่าที่บันทึกไว้

Acceptance: output ตรงกับ artifact เดิมภายใต้ tolerance ที่ประกาศ และ version mismatch ต้อง fail closed

### S2 — Read-only MySQL intake

- map source schema เป็น canonical contract
- implement watermark, overlap/backfill และ late-arrival policy
- เก็บ source-row identity เพื่อป้องกันประมวลผลซ้ำ

Acceptance: rerun ช่วงเดิมแล้วไม่เกิด duplicate score/alert และ source table ไม่ถูกแก้ไข

### S3 — Live feature and shadow scoring

- implement one-second ring buffer และ minute stream
- ตรวจ feature availability time/order/version
- ใช้ profile/model/threshold จาก release manifest เท่านั้น
- เขียน score, alert และ audit แบบ append-only

Acceptance: restart parity, stale-data behavior และ contract-failure behavior ผ่านบน Server จริง

### S4 — API, Web App and monitoring

- API เป็น read-only สำหรับ score/alert/evidence/version
- แยก DATA_QUALITY จาก equipment screening
- Dashboard แสดง local profile, persistence และ alternative explanations
- monitor lag, CPU, RAM, disk, DB errors, feature drift และ alert burden ต่อเครื่อง

Acceptance: Web App แสดง `Shadow screening — not confirmed diagnosis` และไม่มี endpoint เปลี่ยน PLC/model/profile/threshold

### S5 — Shadow observation and approval package

- รัน shadow ตามช่วงที่ Project owner กำหนด
- รายงาน alerts per machine-day ทั้ง median และ worst machines
- ตรวจ MX058/MX082 แยก ไม่ใช้ค่าเฉลี่ย fleet ปิดบัง outlier
- ให้ technician review ตัวอย่าง alert และบันทึก outcome
- สร้าง exact rollback release และทดสอบ rollback

Acceptance: alert budget, rollback, security/safety review และผู้รับผิดชอบลงนามครบก่อนพิจารณา Technician Advisory

## 12. Required Failure Behavior

| Failure | Required result |
|---|---|
| Missing/stale/out-of-order input | `DATA_QUALITY`; no equipment alert |
| Unknown source mapping/unit/timezone | Block scoring |
| Missing/unsupported local profile | `INSUFFICIENT_PROFILE`; no silent fleet fallback |
| Feature version/order mismatch | Reject batch and write audit event |
| Model checksum mismatch | Refuse model load |
| Worker restart | Restore checkpoint and reproduce persistence state |
| Missing rollback target | Keep release blocked |
| Web App unavailable | Machine/PLC operation remains unaffected |

## 13. Offline Parity Reference

ค่าที่ต้อง reproduce ก่อนเชื่อม live stream:

- Primary outer replay: 131,853 scored rows
- Raw flag rate: approximately 0.3936%
- Persistent alerts: 36
- Alert burden: approximately 0.456 alerts per machine-day
- Restart deterministic: true
- Failure-mode tests: 12/12 safe behavior
- MX-080 reference status: `INCIDENT_REPLAY_ONLY_INSUFFICIENT_FOR_PRODUCTION`
- MX-080 pre-transition raw flag rate: 3.0% across 100 scored rows
- MX-080 post-transition raw flag rate: 100% across 139 scored rows
- MX-080 descriptive persistent detection: 2026-09-07 12:35:00

MX-080 เป็น sensitivity/parity fixture เพียงเหตุการณ์เดียว ไม่ใช่ recall, accuracy หรือ validated lead time

## 14. Web App Minimum Contract

หน้าใช้งานต้องตอบตามลำดับ:

1. ระบบและข้อมูลพร้อมหรือไม่
2. Machine/Module ใดมี persistent pattern
3. เปรียบเทียบกับ profile ใดและอยู่ใน state ใด
4. หลักฐาน pressure/valve/temperature/lag ใดเด่น
5. มี common-cause หรือ sensor/data-quality explanation หรือไม่
6. ช่างควรตรวจอะไรต่อ
7. ใช้ model/profile/feature/threshold version ใด
8. ผลนี้ยังพิสูจน์อะไรไม่ได้

หากเพิ่ม Health Score 0–100 ในรอบ Server:

- ต้องคำนวณหลัง Data-quality/Profile-readiness gates
- หาก gate ไม่ผ่าน ให้แสดง `Not available` แทนคะแนน
- ต้องแสดง deviation, persistence, trend และ profile confidence ที่ประกอบเป็นคะแนน
- Phase 8 เก็บเพียง prospective binary confirmation ของ alert ใหม่: anomaly found, no anomaly found หรือ unresolved. ก่อนเปิดรับ ต้องตั้ง `HT9046MX_ALERT_DATETIME_TIMEZONE` เป็น IANA timezone ที่ยืนยันแล้วของ alert `detected_at` (`DATETIME(6)`); หากไม่มี API จะ fail closed. เมื่อ Label QA และ temporal/LOMO validation ผ่าน จึงพิจารณา supervised binary anomaly model ได้; cause classification ไม่อยู่ใน scope นี้


## 15. Security and Safety Boundary

- ใช้ least-privilege database users แยก source-read และ analytics-write เมื่อทำได้
- Secrets อยู่ใน Server secret store หรือ untracked `.env` เท่านั้น
- จำกัด Web/API access ตามเครือข่ายและ role ของโรงงาน
- Analytics process ต้องอยู่นอก PLC/safety-control path
- หาก analytics ล้มเหลว เครื่องต้องรักษา control/safety เดิมได้ทั้งหมด
- การทำงานกับ refrigerant และ pressure system ต้องดำเนินการโดยผู้มีอำนาจตามขั้นตอนโรงงาน

## 16. Git Workflow สำหรับ Codex บน Server

3. แยก commit ตาม component และใส่ test evidence
4. ก่อน push ให้ตรวจ secret และ LFS status
5. ทุก material change ต้องอัปเดต governance documents ตาม `AGENTS.md`
6. เปิด Pull Request พร้อมรายการ acceptance ที่ผ่าน/ไม่ผ่านและ rollback instruction

Suggested checks before push:

```bash
git status --short
git lfs status
git diff --check
git diff --cached --check
```

## 17. Definition of Done สำหรับงาน Handoff รอบ Server

- [ ] Repository และ LFS objects clone ได้ครบ
- [ ] Environment/dependency versions ถูกบันทึก
- [ ] Source-to-canonical mapping ผ่านการ review
- [ ] Unit และ timezone ยืนยันจากระบบต้นทาง
- [ ] Model checksum และ feature order/version fail closed
- [ ] Offline replay/MX-080 parity ผ่าน
- [ ] One-second ring buffer และ minute stream ทำงานตาม availability time
- [ ] Live MySQL shadow scores เขียนแบบ append-only/idempotent
- [ ] Missing/stale/out-of-order tests ผ่าน
- [ ] Restart/checkpoint parity ผ่าน
- [ ] API/Web App เป็น read-only และแสดง capability boundary
- [ ] Health view ไม่ออกคะแนนเมื่อ data/profile gate ไม่ผ่าน และไม่อ้างว่าเป็น failure probability
- [ ] Alert burden รายเครื่องอยู่ใน budget ที่อนุมัติ
- [ ] Exact rollback target และ rollback drill ผ่าน
- [ ] Security/safety review ผ่าน
- [ ] Technician, data/ML reviewer, Server owner และ production approver ลงนามตาม gate

จนกว่ารายการทั้งหมดจะผ่าน ให้สถานะเป็น `SHADOW_ONLY_NOT_AUTHORIZED`

## 18. สิ่งที่ Codex ต้องส่งกลับเมื่อจบงานแต่ละรอบ

รายงานสั้น ๆ ต้องมี:

- สิ่งที่ implement จริงและไฟล์ที่เปลี่ยน
- source period, timezone, row/event grain และ filters
- version ของ feature/profile/model/threshold/release
- test/QA ที่รันและผลลัพธ์
- latency, resource use, data-quality rate และ alert burden
- สิ่งที่ยังพิสูจน์ไม่ได้และ production blockers
- rollback target/instruction หรือเหตุผลที่ยังไม่มี
- commit/branch/PR ที่ใช้ตรวจสอบย้อนหลังได้

## Change log

- 2026-09-15 — Added Server handoff for automatic read-only calibration candidates, three-day shadow graph, append-only review and transactional active-pointer promotion. No Server was connected from this workspace.
- 2026-09-15 — Added the prospective binary technician-confirmation migration and feedback-boundary requirement. This is a Server handoff contract only; no Server/database connection or deployment occurred.

- 2026-09-14 — Added the owner-specified ML analytics database target guide and explicitly separated its append-only output role from the unknown raw telemetry source; no server access was exercised.

- 2026-09-11 — Set the former private GitHub handoff target.

- 2026-09-11 — Curated the GitHub handoff scope: retained code, notebooks, documents, current profiles/model and compact parity evidence while excluding raw telemetry, reproducible intermediates, caches and secrets.

- 2026-09-11 — Created the Server-specific Codex handoff for cloning with Git LFS, environment audit, read-only MySQL integration, dual-rate features, versioned shadow scoring, failure behavior, Web App contract, rollout gates and required return evidence. No live deployment or production activation is claimed.
