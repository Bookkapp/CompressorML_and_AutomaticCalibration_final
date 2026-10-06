# Episode archive และงานช่างผ่าน Dashboard

วันที่ 1 ตุลาคม 2026 · สถานะ: implementation และ QA บนคอมเครื่องนี้ ยังไม่ได้เปิด live bridge บน Server

## 1. ข้อตกลงการใช้งาน

ผู้ใช้หน้างานใช้ **Compressor_and_VacuumPump Dashboard** เป็นจุดเดียวสำหรับ Alerts, Assigned Work และ Service Logs ไม่ต้องเขียนรายงานซ้ำใน Operation

**Operation** เป็นระบบดูแลข้อมูลและการวิเคราะห์: ค้นพบเครื่องใหม่, สร้าง calibration candidate, แสดง Shadow Validation 3 วัน, อนุมัติ/ทบทวน `ACTIVE_FROZEN`, ดูแลเวอร์ชันและการ recalibrate เครื่องเดิมเมื่อจำเป็น งานเบื้องหลังทำงานตาม scheduler; ผู้ใช้ไม่ต้องเปิดหน้า Operation ค้างไว้ ทั้งนี้ worker รุ่นหนึ่งนาทีใหม่ยังต้องเชื่อม production persistence/Alert ให้ครบก่อนเปิดใช้งานจริง

## 2. ทางเดินสองกรณี

```text
กรณี detector พบความเบี่ยงเบน                 กรณีช่างพบปัญหาเอง ไม่มี Alert
Qualified data + matching Active Profile        Admin เปิด Assign Work ใน Dashboard
                 ↓                                        ↓
          Score + persistence                  ระบุเครื่อง/โมดูล/อาการ/ช่วงเวลาที่พบ
                 ↓                                        ↓
             Episode archive                              │
                 ↓                                        │
        Alert notification [bridge ยังรอเชื่อม]            │
                 ↓                                        │
  Dashboard: Critical Acknowledge → Work Order              │
                 └─────────── Assigned Work ────────────────┘
                                  ↓
                ช่างเริ่มงาน → เขียน Service Log → ปิดใบงาน
                                  ↓
                MySQL: รายงาน + snapshot บริบทเดิม + ผลทำงาน
                                  ↓
                  จับคู่กราฟ/ช่วงเวลา → Label QA → dataset ในอนาคต
```

โค้ด Dashboard ปัจจุบันสร้าง Work Order อัตโนมัติเมื่อ **รับทราบ Critical Alert** ไม่ใช่ทันทีที่ detector ส่ง Alert ส่วน Warning Acknowledge บันทึก suppression 7 วันโดยไม่สร้างใบงาน และ Admin ยังเปิดใบงานเองได้

Episode, Alert, Work Order และ Service Log เป็นคนละสิ่ง:

| สิ่งที่เก็บ | ใช้ตอบคำถาม | อะไรไม่ควรอนุมานจากสิ่งนั้น |
|---|---|---|
| Episode | กราฟเบี่ยงเบนช่วงไหน ภายใต้ Profile/version ใด | ยังไม่ใช่สาเหตุหรือ fault label |
| Alert | แจ้งใคร/เวลาไหน/รับทราบหรือยัง | Notification cooldown ไม่ใช่ขอบเขต Episode |
| Work Order | ใครต้องตรวจเครื่อง อาการและเวลาที่รายงาน | เปิดใบงานไม่ใช่หลักฐานว่า detector ตรวจพลาด |
| Service Log | ช่างทำอะไร มีค่าใช้จ่ายอะไร และจบงานเมื่อใด | DONE ไม่ใช่หลักฐานว่ากราฟฟื้นตัวหรือ baseline ใหม่ปกติ |

## 3. สิ่งที่เพิ่มใน Dashboard แล้ว

เพิ่ม nullable metadata ใน `predictive_maintenance`:

| Table | Column | ความหมาย |
|---|---|---|
| `pm_work_orders` | `report_origin` | `ADMIN_WORK_ORDER` เมื่อ Admin เปิดเอง; `ALERT_LINKED` เมื่อ Critical ACK สร้างใบงาน |
| `pm_work_orders` | `event_started_at`, `event_ended_at` (`DATETIME(6)`) | ช่วงที่รายงานว่าพบอาการ ไม่ใช่เวลาเปิดใบงาน; end ว่างได้ |
| `pm_work_orders` | `event_timezone` | IANA timezone ของเวลาข้างต้น; ฟอร์มปัจจุบันระบุ `Asia/Bangkok` ชัดเจน |
| `pm_work_orders` | `event_time_precision` | SECOND / MINUTE / APPROXIMATE / UNKNOWN |
| `pm_maintenance_logs` | `incident_context_json` (`JSON`) | snapshot รายละเอียดใบงาน ณ ตอนส่ง Service Log |

ฟอร์ม manual Assign Work ให้กรอก Description, เวลาเริ่ม–จบอาการ และเลือกเวลาประมาณได้ หากไม่ทราบเวลาก็เว้นไว้ ระบบไม่ใช้ `created_at` แทน onset โดยอัตโนมัติ Assigned Work แสดงช่วงอาการแยกจากเวลา Alert/เปิดงาน ส่วน Service Logs มีรายละเอียดขยายดู **Original incident report**

การส่ง Service Log ที่ผูกใบงานใช้ transaction เดียวสำหรับ snapshot, insert log และปิดใบงาน การแก้ Description ของใบงานภายหลังไม่เปลี่ยน snapshot เดิม การแก้ Service Log ยังทำได้ตามสิทธิ์ Admin เดิม แต่ไม่ได้แก้ frozen incident context ไม่มีการเปลี่ยน Description เป็น cause/probability หรือ training label อัตโนมัติ (`UNREVIEWED`, cause `UNKNOWN`)

ตรวจว่า module อยู่ใน device ที่เลือกก่อนสร้าง manual ใบงาน API กำหนด origin เอง ไม่รับ origin/source Alert ที่ client พยายามปลอม Work Order และ Log เก่ายังแสดงได้โดยไม่มี onset/snapshot; ไม่เติมข้อมูลย้อนหลังขึ้นเอง

**Identity:** `pm_work_orders.source_alert_id` อ้าง `pm_alerts.id` เท่านั้น ไม่ใช่ UUID ของ analytics Episode ปัจจุบันยังไม่มี Episode → PM Alert → Work Order foreign-key mapping สำหรับ scorer หนึ่งนาทีใหม่ ต้องเพิ่ม bridge/mapping ที่ชัดเจนในขั้นต่อไป ไม่จับคู่ด้วยเลข ID ที่บังเอิญเหมือนกัน

## 4. Episode policy ที่ลงมือทำแล้วใน local rehearsal

เก็บ downstream จาก `QualifiedShadowScorer` เดิม ไม่เพิ่มโมเดลหรือเปลี่ยน threshold/Active Profile

| Parameter | ค่าเริ่มต้น | หน้าที่ |
|---|---:|---|
| Primary opening persistence | 3 qualified consecutive 1m flags (กฎเดิม) | เปิด Episode จากหลักฐานเดิม ไม่ใช่ spike นาทีเดียว |
| `recovery_windows` | 5 | ปิดเป็น RECOVERED เมื่อ 5 นาที qualified ต่อกันไม่เกิน threshold |
| `merge_gap_minutes` | 5 | recurrence สั้นใน context เดิมเชื่อม group ID; ยังเก็บ Episode segment/time แยก |
| `unknown_gap_minutes` | 5 | ไม่มี window ใหม่ใน empty delivery → UNKNOWN ไม่ใช่หายผิดปกติ |
| `pre_event_minutes`, `post_event_minutes` | 30 / 30 | requested raw evidence รอบ onset/recovery; ต้องเช็ค coverage จริง |
| `top_contributors` | 3 | ตัวแปรที่ |z| สูงสุด ณ peak พร้อมทิศ HIGH/LOW ไม่ใช่สาเหตุ |
| `chunk_hours` | 6 | metadata สำหรับแผน export chunk; ยังไม่ได้สร้าง automatic chunk/export worker |
| Policy version | `qualified-1m-episode-archive-v1` | แยกนโยบาย archive จาก feature/Profile/score versions |

```text
persistent deviation → OPEN → qualified non-flag → RECOVERING (1…5) → RECOVERED
                            ↖ flag กลับมา: reset recovery → OPEN
missing / manual / non-Cold / unsupported Profile → UNKNOWN (ไม่ยืนยัน recovery)
Profile/parameter เปลี่ยน → ENDED_UNKNOWN + เริ่ม segment ใหม่ภายใต้ context ใหม่
```

เก็บ onset ของ flag แรกใน run, เวลาที่ครบ persistence และเวลาผลพร้อมใช้งานแยกกัน ผู้ใช้จึงเห็น latency จาก delivery 5 นาทีได้ Policy นี้เป็นค่าเริ่มต้นเพื่อทดสอบ lifecycle ยังไม่ใช่ optimum ที่พิสูจน์จาก labeled fleet ไม่มี threshold tuning, HPO, retraining หรือการเพิ่มเสียงโหวต EWMA/CUSUM ในรอบนี้

เพิ่มสถิติเพื่อ **review** จาก raw seconds ต่อ minute/channel: finite sample count, min, max, p05, p95, IQR (7 physical channels) ช่วยเห็น spike ที่ค่าเฉลี่ยกลบ สถิติเหล่านี้ไม่ได้เพิ่มเข้า 9-feature mean scorer หรือ profile fit; score เดิมคงเดิม

## 5. Persistence/API ที่ทำแล้ว

`apps/api/app/qualified_persistence.py` commit cursor, checkpoint ของ stream/scorer/archive, batch receipt, minute evidence, Episode upsert และ received raw rows ใน transaction เดียว บนตาราง local `ht9046mx_rehearsal_*`:

- `ht9046mx_rehearsal_episode`: `run_id + episode_id` เป็น identity, payload มี machine/module/versions/status/group/times/evidence request
- `ht9046mx_rehearsal_raw_evidence`: `run_id + batch_id + row_index`, machine/source-local timestamp และ raw JSON
- ตาราง stream/batch/evidence เดิมยังใช้ร่วมกัน retry batch เดิมไม่ insert ซ้ำ และ rollback ไม่เลื่อน cursor

GET `/api/v1/rehearsal/{run_id}/points` คืนกราฟรายนาทีและ Episode summaries

GET `/api/v1/rehearsal/{run_id}/episodes/{episode_id}/raw?start=...&end=...&limit=20000` คืน available received raw แบบช่วง **[start,end)**, naive source-local clock พร้อม timezone ใน Episode ขอบเขต `start/end` ถูก clip ให้อยู่ใน requested evidence range และ end ต้องหลัง start `truncated=true` หมายถึงต้องแบ่งช่วงเวลาให้เล็กลง; ไม่มีการอ้างว่าส่งออกครบเมื่อชน limit `coverage_verified=false` ยังต้อง reconcile กับ source

QA UI ของ Operation อ่านอย่างเดียว: Episode + ห้ากราฟ + raw JSON link ไม่ใช่หน้ารายงานงานช่าง ไม่มี production API/Alert writer เพิ่มจาก endpoint นี้ เรียกได้เมื่อ process เปิด local rehearsal flag และ analytics host เป็น localhost เท่านั้น

ต้นแบบปัจจุบันเก็บ **received raw ทั้ง run** เพื่อ parity/rollback test ไม่ใช่ retention design ของ production ระยะยาว ต้องเพิ่ม bounded pre-event buffer, post-event completion, indexing/retention/export และการตรวจ completeness ก่อนขยายทั้ง fleet

## 6. ผล QA ที่รันจริง

- Operation: full `python -m pytest apps/api/tests -q` **67 passed** (12.93 s); web TypeScript/Vite production build ผ่าน (717.01 kB JS chunk warning)
- Dashboard: full `python -m pytest -q` **63 passed** (final repeat 2.25 s); production frontend build ผ่านใน temporary output ไม่ทับ user-edited `public/` (ECharts chunk warning)
- Dashboard local MySQL metadata migration เรียกซ้ำ 2 รอบผ่าน เพิ่มเฉพาะ columns ข้างต้น ไม่มี Work Order/Service Log row ถูกสร้างหรือแก้โดย QA นี้
- MX080/M6 source-second archive: **7 Sep 2026 11:45–13:00 exclusive**, Asia/Bangkok, 4,438 received raw rows, 75 minute/module windows; calibration ใช้ 3–6 Sep **4 วันก่อน replay**, ไม่ใช่ Active Profile และยังไม่พอ policy 7 วัน
- Run `mx080-m6-68767020a8ce`: whole-batch vs five-minute delivery **0 window/score differences**, 15 duplicate-batch retries, 15 reconnect cycles, 1 pre-commit crash rollback ผ่าน; p95 ต่อ cycle 199.1 ms จาก sample สั้น 15 cycles ไม่ใช่ fleet throughput claim
- เก็บ 1 Episode UUID `3671b995-7ba2-5833-a10d-a2f2dca6c73f`, first deviation **12:06**, persistence window end **12:09**, result available **12:10+07:00**, status OPEN ณ 13:00; peak ratio 58.36, top `dp2`, `hp2`, `templo`
- Episode นี้เริ่มก่อน owner-confirmed high-pressure interval ใน case registry ไม่ใช่การพิสูจน์ว่า fault เริ่ม 12:06 หรือยืนยัน sensitivity/specificity Profile สั้นยังต้องตรวจ early flags; onset ไม่ได้ปรับให้ตรง case ที่ทราบแล้ว
- Requested pre-context เริ่ม 11:36 แต่ input เริ่ม 11:45 และ Episode ยัง OPEN จึง **ไม่มีหลักฐานครบก่อน/หลัง 30 นาที**; raw query คืน 4,438 แถว ไม่ได้ invent rows
- Read-only Operation Episode/graph UI ตรวจใน browser บน localhost:5175/API:8011; Dashboard ฟอร์ม/Service Log ใหม่ build/test ผ่าน แต่ browser UAT ของ workflow จริงยังรอทำ ไม่มี Server acceptance/production writes

## 7. การติดตั้ง/ทดสอบต่อ

### Dashboard

1. Backup metadata database และตั้ง `.env`/APP_TIMEZONE ตาม deployment guide เดิม ไม่ต้องเปลี่ยน source telemetry accounts
2. schema ทั้ง `schema.sql` และ `app/db.py` เพิ่ม columns แล้ว startup migration เรียก targeted `migrate_incident_evidence(cur)` แบบ idempotent บัญชี migrate ต้องมี ALTER TABLE; หาก runtime account ไม่มีสิทธิ์นี้ให้ DBA apply additive migration ก่อน
3. Local targeted QA: `python -m scripts.qa_incident_context_migration` (localhost เท่านั้น) ไม่ได้เป็น migration runner ของ Server
4. `python -m pytest -q`; build frontend ตาม README เดิมและ deploy bundle พร้อม backend รุ่นเดียวกัน ในรอบนี้ build temporary output เพื่อรักษาไฟล์ public ที่มี user changes
5. UAT: Admin เปิด manual งานทั้งรู้เวลา/ไม่รู้เวลา, ตรวจ machine/module, assigned tech เริ่มงาน/ส่ง Service Log, Admin ตรวจ original report, แก้ใบงานแล้ว snapshot เดิมคงอยู่, ตรวจสิทธิ์คนอื่นและ legacy logs

### Operation local QA

จาก project root:

```powershell
python -m pytest apps/api/tests -q
python -m notebooks.support.mysql_incremental_rehearsal
```

คำสั่งหลังเขียน rehearsal tables บน localhost และสร้าง run ID ใหม่ทุกครั้ง ไม่แตะ source/Active/PM Alerts หากไม่ต้องการ run เพิ่มให้ใช้ ID QA ที่ระบุข้างต้น

API ที่ `apps/api`:

```powershell
$env:HT9046MX_LOCAL_REHEARSAL_DASHBOARD_ENABLED='true'
$env:HT9046MX_API_CORS_ORIGINS='http://127.0.0.1:5175'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Web ที่ `apps/web`:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8011'
node node_modules/vite/bin/vite.js --host=127.0.0.1 --port=5175 --strictPort
```

เปิด `http://127.0.0.1:5175/?rehearsal=mx080-m6-68767020a8ce` ไม่ใช้ Profile นี้เปิด live inference

## 8. ขั้นถัดไปที่ยังไม่เสร็จ

- [ ] Matching reviewed `qualified-cold-observed-1m-v1` Active Profile → live atomic persistence → Alert outbox/bridge → explicit Episode/PM Alert/Work Order mapping
- [ ] รับข้อมูล raw seconds จาก source จริงพร้อม late-commit-safe cursor/watermark; ingestion ID monotonic อย่างเดียวไม่พิสูจน์ commit order
- [ ] Dashboard browser UAT + role checks และ Module graph link/highlight จาก Episode/รายงาน manual; ตอนนี้มีช่วงเวลารายงานและ raw QA link แต่ยังไม่มี integrated manual evidence graph
- [ ] Production retention/export/completeness, concurrency/restart/freshness/rollback บน Server
- [ ] Dataset assembly: จับคู่ manual reports กับ scored/unsupported/missing intervals โดยเวลาและ machine/module; review label ก่อนสรุป false negative หรือใช้ Supervised learning

การมีข้อมูลไม่มี Alert อาจมาจากไม่มี Active Profile, นอก qualified state, ข้อมูลขาด, notification suppression หรือ detector ไม่ไวพอ ต้องแยกเหตุผลเหล่านี้ก่อนนับ missed detection ไม่ใช้การปิดใบงานหรือข้อความอิสระเพื่อ auto-retrain/auto-approve Profile

## Code map

- Operation: `qualified_episodes.py`, `qualified_evidence.py`, `qualified_persistence.py`, local endpoints ใน `main.py`, `RehearsalDashboard.tsx`, `test_qualified_episodes.py`
- Dashboard: `maintenance_evidence.py`, `services.py`, `db.py`, `schema.sql`, `frontend/src/main.jsx`, `i18n.js`, `test_maintenance_evidence.py`, `scripts/qa_incident_context_migration.py`

Change log — 2026-10-01: implemented local Episode archive and Dashboard-owned reported incident times/frozen service context; QA corrected the ratio chart label to strict `>1`, and made the original-report disclosure available in both Maintenance and Data → Logs with origin/precision. Read-only HTTP checks passed for 75 points/1 Episode, truncation/coverage flags and 404/400/422 responses. No detector threshold, model, Active Profile or Server release changed.
