# Empty feed: Server diagnostic handoff — 9 October 2026

## ตรวจที่ไหน และเป้าหมาย

เริ่มที่ **Operation Server 10.195.17.73** ซึ่งอ่าน Raw, สร้าง observed minutes และเขียน feed จากนั้นตรวจ **Dashboard Server 10.195.17.69** ซึ่งเริ่มการเชื่อมต่อ SELECT ไป .73:3306 เท่านั้น ไม่ต้องเปิดเส้นทางย้อนกลับจาก .73 ไป .69

คำสั่งสำหรับ Codex บน .73: “อ่าน deployment/EMPTY_FEED_SERVER_DIAGNOSTIC_20261009.md ตรวจสาเหตุ feed ว่างด้วยข้อมูลจริงแบบ read-only แล้วรายงานหลักฐานและแนวทางแก้ก่อนเปลี่ยน runtime หรือ checkpoint”

เอกสารนี้เป็นรายการตรวจสอบที่เตรียมจาก checkout ไม่ใช่ผลตรวจ Server ใหม่ รายงานเดิมเป็นภาพ ณ 8 October; สถานะปัจจุบันต้องอ่านใหม่ ตรวจ HANDOFF_SERVER.md, AGENTS.md และ Server Acceptance ก่อนเริ่ม ใช้ private config ของ installation จริง ห้ามนำ .env ของเครื่องอื่นมาทับ ห้ามพิมพ์ password/token ลงหลักฐาน

## ไม่มี Active ไม่ใช่เงื่อนไขให้ feed ว่าง

อ้างอิง release 090c9d6: qualified_detector เปิด unified events และ initialize ได้แม้ไม่มี legacy Active; context_monitor สร้าง NO_ACTIVE_CONTEXT_PROFILE เมื่อไม่มี approved Context model และยังเรียก dashboard_export.publish_points จากนั้น status_for คืน NOT_EVALUATED สำหรับไม่มี approval หรือ DETECTOR_SHADOW เมื่อ receiver รับได้ UI แสดง Pending ไม่ใช่ Normal

การมี Active และ DETECTOR_LIVE จำเป็นสำหรับการให้สถานะ NORMAL/WARNING จาก Context ที่รองรับ แต่ไม่จำเป็นสำหรับส่ง STATUS แบบ NOT_EVALUATED หรือเก็บ control EVENT การ export ยังต้องมี minute/event ใหม่ ผ่านทางเดินจริงและ transaction commit สำเร็จ; latest timestamp/state/heartbeat อาจทำให้ไม่ส่งซ้ำทุก minute

รายงาน 8 October พบ finalized cutoff 09:29 แต่ source ล่าสุด MX017 09:25 และ AFTER_FINALIZATION quarantine จึงมีเหตุให้สงสัย source lag/finalization อย่างไรก็ตามต้องตรวจ actual installation และรอบใหม่ก่อนสรุปว่าเป็นสาเหตุทั้งหมด first_cycle.json เป็นหลักฐานเก่า 7 October ไม่ใช่หลักฐานส่ง feed ใน release ปัจจุบัน

## A. ตรวจ .73 แบบ read-only ก่อน

1. ยืนยัน code ที่ process ใช้จริง: working directory, entrypoint, supervisor PID/child PID, source/config paths และ revision/checksums Installation เดิมเป็น ZIP; runtime/release_git เป็น reference checkout การ pull checkout อย่างเดียวไม่ยืนยันว่า service ใช้โค้ดใหม่
2. ยืนยันมี detector scheduler เดียว ตรวจ parsed settings โดยไม่เปิดเผย secrets: worker enabled, shadow_only, cron, source timezone/unit, source schema/table, analytics schema, overlap minutes, qualified_1m_late_arrival_seconds, selected Fleet bundle และ modules ห้ามเปิด Live หรือ activate Profile เพื่อทำให้ feed มีข้อมูล
3. อ่าน log อย่างน้อย 3 รอบ เก็บเวลา/เครื่อง/run_id, COMPLETED หรือ exception, accepted_rows, windows_written, quarantined_rows, scan_start/end, revision, source_cursor และ mode ตรวจ transaction rollback, LONGTEXT overflow, permission errors และ scheduler ที่หยุดทำงาน
4. วัด source lag แยกรายเครื่องและตามเวลาหลายรอบ อย่าดู global MAX อย่างเดียว เปรียบเทียบ source-local clock กับ source recorded_at, stream.closed_before และ last_as_of ตรวจ timezone/clock และ telemetry writer/buffer; recorded_at ไม่ใช่ arrival/commit time หากไม่มี ingest timestamp ต้องระบุว่ายังวัด arrival latency โดยตรงไม่ได้
5. อ่าน current run และ checkpoint แบบเลือก field เท่านั้น ตรวจ source receipt กับ quarantine การพบ source rows เพิ่มแต่ accepted_rows/windows_written=0 พร้อม AFTER_FINALIZATION คือหลักฐานที่ต้องตามต่อ ตรวจ per-machine scan bounds/row budget/overlap ด้วย
6. ยืนยัน checkpoint_json ในตาราง detector_stream จริงเป็น LONGTEXT ตรวจ table engine ทั้ง feed/sequence/identity/latest เป็น InnoDB การเปลี่ยน SQLAlchemy type ไม่ได้ ALTER ตารางเก่าโดยอัตโนมัติ
7. ตรวจเส้นทาง consume_observed -> publish_points -> publish และ append_events บน code ที่ติดตั้งจริง รวมถึง unified_events_enabled, observed-minute quality/grouping และ transaction commit ตรวจ latest ว่าเกิดจากรอบไหน หาก latest มีข้อมูลแต่ feed/identity/sequence ว่าง ต้องตรวจ provenance/restore/manual mutation โดยไม่สมมติว่าไม่มี Active เป็นสาเหตุ
8. หากมีข้อมูลใหม่ที่อยู่ในช่วงรับจริง แต่ยังไม่ส่ง ให้ระบุตำแหน่งที่หยุดด้วย log/DB evidence ไม่ reset watermark เพื่อทดลอง

### SQL ตรวจ .73 (SELECT เท่านั้น)

ใช้บัญชี source SELECT-only สำหรับ Raw และบัญชีที่อ่าน analytics ได้สำหรับข้อมูลผล เก็บผลจำกัดแถว ใช้ EXPLAIN ก่อน query ใหญ่บน Raw

```sql
SELECT NOW(6), UTC_TIMESTAMP(6), @@session.time_zone, @@global.time_zone;
SELECT machine_number, MAX(recorded_at) AS latest_recorded_at
FROM ht9046mx_iot.ht9046mx_readings
WHERE recorded_at >= NOW() - INTERVAL 1 HOUR
GROUP BY machine_number;

SELECT machine_number, run_id, reason FROM ht9046mx_analytics.ht9046mx_detector_current;
SELECT run_id, revision, source_cursor,
 JSON_UNQUOTE(JSON_EXTRACT(checkpoint_json,'$.stream.closed_before')) AS closed_before,
 JSON_UNQUOTE(JSON_EXTRACT(checkpoint_json,'$.stream.last_as_of')) AS last_as_of
FROM ht9046mx_analytics.ht9046mx_detector_stream;
SELECT run_id, JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.reason')) AS reason,
 JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.recorded_at')) AS recorded_at,
 JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.observed_at')) AS observed_at
FROM ht9046mx_analytics.ht9046mx_detector_data_issue LIMIT 30;

SELECT COLUMN_TYPE FROM information_schema.columns
WHERE table_schema='ht9046mx_analytics' AND table_name='ht9046mx_detector_stream'
 AND column_name='checkpoint_json';
SELECT table_name, engine FROM information_schema.tables
WHERE table_schema='ht9046mx_analytics' AND table_name IN
 ('ht9046mx_dashboard_feed','ht9046mx_dashboard_sequence',
  'ht9046mx_dashboard_identity','ht9046mx_dashboard_latest');
SELECT COUNT(*) AS feed_count, MIN(seq), MAX(seq), MAX(occurred_at)
FROM ht9046mx_analytics.ht9046mx_dashboard_feed;
SELECT id,last_seq FROM ht9046mx_analytics.ht9046mx_dashboard_sequence;
SELECT id,stream_id FROM ht9046mx_analytics.ht9046mx_dashboard_identity;
SELECT machine_number,module,occurred_at,exported_at
FROM ht9046mx_analytics.ht9046mx_dashboard_latest LIMIT 48;
SELECT seq,event_id,kind,machine_number,module,occurred_at,
 JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.status')) AS status,
 JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.category')) AS category
FROM ht9046mx_analytics.ht9046mx_dashboard_feed ORDER BY seq DESC LIMIT 20;
```

Raw query ใช้ clock assumption Asia/Bangkok ที่ต้องยืนยันก่อน NOW(); window 1 ชั่วโมงไม่พบเครื่องที่หยุดนาน จึงไม่ใช่ machine inventory ครบทุกเครื่อง SQL issue LIMIT เป็น sample ไม่ได้แปลว่าเป็น 30 issue ล่าสุด หลีกเลี่ยง GROUP BY/count/full scan บน telemetry/history ใหญ่ซ้ำถี่โดยไม่มี index/query plan

## B. แนวทางแก้หลังมีหลักฐาน — ยังไม่ให้ดำเนินการอัตโนมัติ

หาก lag มาจาก writer/buffering ให้แก้ ingestion latency/clock ที่ต้นเหตุ หาก late-arrival policy ไม่รองรับ observed delay ให้เสนอ policy/version ที่ใช้ข้อมูลวัดจริงและทดสอบ isolated replay ก่อน โดยคง closed-minute coverage/duplicates/finite/control contract; overlap สำหรับ rescan กับ lateness ก่อน finalization เป็นคนละเรื่อง การเพิ่ม overlap อย่างเดียวไม่ได้เปิด minute ที่ finalized ไปแล้ว

ห้าม reset/delete receipts, stream, latest, identity, sequence หรือ cursor; ห้าม fabricate feed, mock timestamps, เปลี่ยน Raw, ฝืน Active, เปลี่ยน Shadow เป็น Live หรือผ่อน data-quality เพื่อให้ดูผ่าน Historical backfill ต้องมีแผนแยก/version/namespace และไม่ย้อนหลังสร้าง production alerts แบบเงียบ ๆ การเพิ่ม lateness มี trade-off กับเวลาที่ Dashboard ได้ผล ต้องวัด throughput/lag และออกแบบ bounded catch-up สำหรับหลายเครื่องก่อน

## C. ตรวจ .69 เมื่อ .73 มี export จริง

1. อ่าน /api/db/status สองครั้งและหลังมี export โดย authenticated Admin; operation_pull connected=true/error_type=null เป็น connectivity เท่านั้น ไม่ใช่ delivery acceptance
2. ใช้ installed read-only reader SELECT feed/sequence/identity ที่ .73:3306 เทียบ last_seq/backlog กับ producer บันทึก effective CURRENT_USER โดยไม่เปิดเผย password
3. อ่าน local metadata pm_operation_cursor, pm_operation_source_identity, pm_operation_receipts, pm_operation_latest และ pm_operation_unmapped แบบ bounded SELECT ตรวจ cursor เดินตาม producer, stream_id ตรง, payload ถูก map machine/module และ backlog drain
4. ไม่มี Active/Shadow ต้องแสดง Pending/NOT_EVALUATED โดย health_score=null ไม่สร้าง Good/Warning/Critical หรือ Work Order จากหลักฐาน Shadow ตรวจ freshness/Offline แยกจาก evaluation
5. เมื่อได้รับอนุญาต restart จริงและมี metadata backup แล้ว ทดสอบ restart receiver ขณะมี feed ไม่ว่าง: identity/cursor/receipts ไม่หาย ไม่เพิ่ม duplicate Alerts และไม่ reapply event เก่า การ restart ที่ feed ว่างพิสูจน์ข้อนี้ไม่ได้ Outage/replay/load ให้ใช้ isolated QA ก่อน
6. เก็บเวลา producer export -> receiver receipt -> UI พร้อมระบุ clock basis/browser rendering แยกจาก warm HTTP p95; source lag กับ model lag ต้องแยกกัน

## สิ่งที่ต้องส่งมอบหลังตรวจ

สร้างรายงานใหม่ชื่อ deployment/EMPTY_FEED_SERVER_FINDINGS_<date>.md พร้อม .73/.69 revisions/processes, settings ที่ไม่เป็น secret, clock/source lag หลายรอบ, counts/cursors/categories, stage ที่หยุด, root cause ที่มีหลักฐานหรือข้อที่ยังไม่ทราบ และ proposed fix/rollback/tests/latency impact แยก confirmed facts จาก hypotheses

เกณฑ์สำเร็จ: export จริงไม่ว่าง, sequence/identity เริ่มและคงอยู่, receiver รับ payload/cursor ก้าวหน้าและ backlog drain, no-Active/Shadow คง NOT_EVALUATED/Pending, source/Profile/Active ไม่ถูกเปลี่ยน และ restart/replay acceptance บนข้อมูลไม่ว่างผ่านตามขอบเขตที่ได้รับอนุญาต ไม่จำเป็นต้องสร้าง Active Profile เพื่อพิสูจน์การส่ง feed

## Evidence / source pointers

- deployment/ONE_WAY_SERVER_ACCEPTANCE_20261008.md (historical Server observations)
- apps/api/app/qualified_detector.py (no-Active observation, receipts/finalization)
- apps/api/app/qualified_persistence.py (atomic checkpoint/context transaction)
- apps/api/app/context_monitor.py (NO_ACTIVE_CONTEXT_PROFILE still publishes)
- apps/api/app/dashboard_export.py (NOT_EVALUATED mapping, latest/heartbeat)
- apps/api/app/unified_events.py (common events and export tables)
- Companion Dashboard: app/operation_pull.py and deployment/SERVER_ACCEPTANCE.md
