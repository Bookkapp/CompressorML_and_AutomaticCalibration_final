# แผนเพิ่ม EWMA/CUSUM เป็นหลักฐานแนวโน้มของ HT9046MX

> **Cadence update 2026-09-25:** Signed robust-z EWMA/CUSUM is a shadow-only one-minute research lane after the new qualified 1m window contract; this plan's 5m references are historical. It does not vote on current alerts, change Health, classify causes, or authorize production. See `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.

**สถานะ:** P0/P1 แกน pure/read-only เริ่มทำแล้ว · 2026-09-25 Asia/Bangkok · ยังไม่มี registry/profile 5 นาทีที่อนุมัติ, schema persistence, UI, Server shadow หรือ alert vote. ผลและไฟล์จริงอยู่ใน `deployment/QUALIFIED_5M_SHADOW_IMPLEMENTATION.md`.

## 1. ข้อตกลงของงานนี้


ข้อความแนบฉบับที่สองเป็นภาพระยะยาวของ evidence platform ไม่ใช่สิ่งที่ต้องเปิดใช้พร้อมกันในรอบนี้ โดยเฉพาะ PCA/T²/SPE, ARX, supervised model และการรวมคะแนนยังเป็นงานวิจัยแยกต่างหาก ข้อเสนอเพิ่มช่อง root cause/action/refill ใน Technician UI **ขัดกับ Phase 8 contract ปัจจุบัน** ซึ่งรับเพียง `EQUIPMENT_ANOMALY`, `NO_EQUIPMENT_ANOMALY`, `UNRESOLVED` และหมายเหตุสำหรับ alert ใหม่เท่านั้น จึงไม่รวมในงานนี้ หากมี maintenance record จากระบบอื่นในอนาคตต้องออกแบบแหล่งข้อมูลและ governance แยก ไม่เปลี่ยนข้อความอิสระให้เป็น label โดยอัตโนมัติ

เครื่องหมาย `:chatgpt-content-reference{...}` ในข้อความแนบฉบับที่สองเป็น placeholder ไม่ใช่บรรณานุกรมที่ตรวจตามได้ จึงไม่ใช้เป็นหลักฐานว่าวิธี PCA/ARX หรือผลประโยชน์เชิง detection ได้รับการพิสูจน์กับข้อมูลโครงการนี้

```text
  → ตรวจเวลา/หน่วย/duplicate/ความครบ/Cold state
  → หน้าต่าง 5 นาทีที่ปิดครบและมี provenance
  → Active Profile ที่ตรง Machine × Module × SV × State และ version
  → signed robust z ทั้ง 9 feature
       ├─ Primary: max |z| → local threshold → 3 หน้าต่างติดกัน → alert (หลัง release gate)
       └─ Shadow: EWMA + CUSUM ต่อ feature → temporal evidence/episode เท่านั้น
  → Analytics MySQL → Dashboard (แสดงหลักฐานแยก) → prospective technician feedback ของ primary alert
```

## 2. สิ่งที่ตรวจพบจริงก่อนวางแผน

อ่าน `README_System.md`, `SOT.md`, `HANDOFF.md`, `Project.md`, `Roadmap.md` ตามลำดับ และเทียบกับ `calibration.py`, `inference.py`, `config.py`, `worker.py` และ schema ใน `deployment/` แล้ว:

| เรื่อง | สถานะจริง 2026-09-25 | ผลต่อแผน |
|---|---|---|
| Failure behavior | Inference ยอมเติม missing sensor/stat เป็น z=0, ยอม default module state และให้ non-Cold เป็น `NORMAL`/Health 90; source read ยังผ่าน analytics connection | แก้ fail-closed และแยก source read-only connection ก่อนเพิ่ม temporal state |
| MySQL ที่ตรวจ | `.env` ของ workspace ชี้ source และ analytics ไปที่ **127.0.0.1**; read-only query สำเร็จทั้งสองฝั่ง ไม่ใช่การยืนยัน Server `10.195.17.73` | ใช้ local DB ทดสอบ schema/logic ได้ แต่ Server acceptance ต้องทำใหม่บน target |
| Local Active pointers | `ht9046mx_active_calibration_profile` มี 46 keys: 38 `SV=Off`/Cold และ 8 legacy `RUN`/`QUALIFIED`; มี MX777 test-only 8 keys | Active pointer ไม่เท่ากับ production-approved reference; strict exact-key, approval/version และ test-profile exclusion จำเป็น |

ข้อมูลในตารางเป็น bounded read-only checks ของ **local** MySQL ณ วันที่ระบุ; ไม่ได้เขียนข้อมูล ไม่ได้ตรวจทุกเครื่อง/ทุกวัน และ timezone ของ `DATETIME` ยังต้องยืนยันกับ source owner แม้ config ระบุ `Asia/Bangkok`.

## 3. สัญญาข้อมูลร่วมที่ต้องสร้างก่อน

หน่วยคะแนนใหม่เป็น `[window_start, window_end)` ระยะ 5 นาทีที่ปิดครบแล้ว โดยมี `machine_number`, `module`, `sv_state`, `state_code`, `profile_id`, `sample_count`, expected/observed cadence, coverage, duplicate count, missingness, source timezone, feature version, quality reason และ watermark. เครื่องหนึ่งมีได้แปด module records ต่อหน้าต่าง source. ต้องกำหนด timestamp alignment, late-arrival grace และ cutoff จากข้อมูลจริงก่อน; cron firing ไม่ทำให้หน้าต่างสมบูรณ์เอง



Primary score ยังคงเป็น `D_t=max_j |z_{j,t}|` บน 9 feature: `hp1, lp1, hp2, lp2, dp1=hp1−lp1, dp2=hp2−lp2, valve, temphi, templo`. เก็บ signed `z` ทุกตัวก่อนหา max เพื่อบอกทิศทาง. Threshold ต้องเป็น positive finite local value จาก **profile version เดียวกัน** และ comparison operator ต้องล็อกใน manifest. Primary persistence นับ 3 **qualified 5-minute windows ที่ต่อกันตามเวลา** ภายใต้ key/version เดียวกัน; invalid/missing, state/SV/Profile เปลี่ยน หรือ gap ต้องตัด run. สามธงหมายถึงการเบี่ยงเบนในสามช่วงต่อเนื่อง รวม 15 นาทีของหน้าต่างที่สังเกต; ไม่ใช่การยืนยัน fault.

## 4. นิยาม Temporal lane รุ่นแรก

ใช้ signed local residual `z_{j,t}=(x_{j,t}-m_j)/s_j` ไม่ใช้ `D_t` เพราะ `D_t` ทิ้งทิศทาง. สำหรับแต่ละ feature `j` และ context key เดียวกัน:

\[
E_{j,t}=\lambda z_{j,t}+(1-\lambda)E_{j,t-1},\qquad
C^+_{j,t}=\max(0,C^+_{j,t-1}+z_{j,t}-k),\qquad
C^-_{j,t}=\max(0,C^-_{j,t-1}-z_{j,t}-k).
\]





`Hp_2nd` ด้านลงเป็น use case นำร่อง แต่ผลที่อนุญาตคือ `SUSTAINED_HP2_DOWNWARD_DEVIATION` พร้อมค่า raw/z/EWMA/CUSUM และ LP2/DP2/Valve/temperature context ไม่ใช่ `LEAK`, `UNDERCHARGE_CONFIRMED`, cause percentage หรือ failure probability. ช่วง 180–230 psi เป็น qualified field reference เท่านั้น ไม่แทน local profile.

## 5. แผนลงมือทำและ acceptance ของแต่ละช่วง

| ลำดับ | งาน | สิ่งส่งมอบ/เกณฑ์ผ่าน |
|---|---|---|
| P0 | ตรึง input contract และแก้ shared completed-window builder, exact Active-key/profile stats, source read-only path, missing/state/threshold fail-closed | Candidate/replay/inference ให้ feature และ score ตรงกันบน fixture เดียว; 3×5 นาทีจริง; gap/restart/late/duplicate tests; profile version ใหม่ผ่าน shadow และ human approval ก่อนใช้งานจริง |
| P1 | สร้าง pure EWMA/CUSUM engine และ versioned config โดยยังไม่แตะ live vote | unit tests ทิศทางขึ้น/ลง, stable, isolated spike, gradual drift, warm-up/reset, cross-machine isolation; output reproducible จาก fixed input/seed/version |
| P2 | ออกแบบ analytics migration + atomic checkpoint/score/episode persistence | unique idempotency key มี window, full context, detector/parameter version; transaction/restart replay ให้ผลเท่า one-shot; migration/rollback ผ่าน staging; ไม่เขียน raw/PLC |
| P3 | Offline matched replay กับ frozen primary บน eligible 5-minute rows เดียวกัน | inner-only parameter selection; future untouched temporal shadow; report EWMA-only/CUSUM-only/primary-only/overlap, flags/episodes per machine-day, worst module, lead time **เทียบ primary** และจำนวน temporal-only ที่ primary ไม่เคยตามมา; ไม่มี fault precision/recall claim |
| P4 | Shadow worker + Dashboard detail | Temporal score/episode บันทึกแยกจาก primary; UI มี time-aligned raw pressure, signed z, EWMA, CUSUM, local limits, status `SHADOW`; Overview ไม่แสดง fault/cause; temporal-only episode ไม่เข้า technician confirmation queue ของ primary โดยอัตโนมัติ |
| P6 | ขออนุมัติ evidence-only deployment แยกต่างหาก | แสดงประโยชน์เพิ่มเมื่อเทียบ frozen primary และต้นทุนเตือนที่ยอมรับได้; production approver อนุมัติพร้อม version/audit/rollback. `live_vote` เป็น proposal รุ่นถัดไปเท่านั้น |


**Metric ที่ต้องนิยามก่อนรัน:** episode opening/ending และ merge gap, windows and episodes per machine-day, coverage-adjusted denominator, worst machine/module, temporal-only review burden, lead time ต่อ *primary alert* (ไม่ใช่ lead time ต่อ fault), latency ต่อรอบ, p95 DB/UI load, storage growth, restart/replay parity. Synthetic gradual-drift injection ใช้ตรวจกลไกได้ แต่ไม่แทนความไวต่อ fault จริง. `UNREVIEWED` และ `UNRESOLVED` ไม่ใช่ normal/negative labels

## 6. โค้ดและฐานข้อมูลที่จะเปลี่ยนเมื่อเริ่ม implementation

- `apps/api/app/window_builder.py` (ใหม่) และ `calibration.py`/`inference.py`: ใช้ qualified-window contract เดียวกัน; การเปลี่ยน profile grain ต้อง version ใหม่
- `apps/api/app/scoring/ewma.py`, `cusum.py`, `temporal_state.py` (ใหม่): pure, deterministic, signed residual, explicit warm-up/reset
- `apps/api/app/config.py` และ release manifest: `TEMPORAL_MODE=shadow` default, per-version `λ/k/threshold/warm-up`; ไม่เปิด `live_vote` ใน release นี้
- `apps/web/` Module Detail/Overview: วาดเส้นค่า raw และ threshold บนแกนที่ถูกหน่วย แยก z/EWMA/CUSUM อีกแกน/กราฟ; ไม่เอา psi กับ standardized score มาซ้อนแกนเดียวโดยไม่ระบุ

**Storage decision ก่อน migration:** ข้อมูล 19 เครื่อง × 8 โมดูล × 288 หน้าต่าง/วัน ≈ **43,776 module-windows/วัน** หากครบทั้งวัน; การสร้าง 9 feature rows ต่อ window ≈ **393,984 rows/วัน** ก่อน episode/index. ควรวัด active Cold coverage และ DB storage จริงก่อนเลือกหนึ่งแถวต่อ window พร้อม versioned feature/evidence JSON + indexed flags หรือ normalized per-feature rows. นี่เป็น capacity estimate ไม่ใช่จำนวนข้อมูลที่สังเกตแล้ว


PCA/T²/SPE เป็นคำถามเชิง multivariate ที่น่าสนใจ แต่ `dp1=hp1−lp1` และ `dp2=hp2−lp2` ทำให้ 9-vector มี dependence เชิงพีชคณิต; การ fit covariance/PCA แบบไม่ตรวจ rank และอ้าง contributor เป็นเปอร์เซ็นต์สาเหตุจะชวนเข้าใจผิด. ให้วิจัยแยกด้วย base sensors หรือ rank-aware design, fit/train-only, temporal/LOMO และ fresh shadow แล้วเปรียบเทียบกับ rule-only baseline. ARX ยังคงเป็น non-voting research artifact ตาม SOT. ไม่มี weighted fusion, fault classifier, cause fields หรือ auto-retraining จาก note ในการเปลี่ยนแปลงนี้

## 8. Definition of Done และสิทธิ์อนุมัติ

P0–P4 ผ่านใน local/staging ไม่ได้แปลว่า production-ready. ก่อนเปิด primary บน Server ต้องมี source-owner timezone/unit/codebook, approved 5-minute Active Profile และ rollback target, authenticated reviewer, fresh shadow, accepted alert budget, operational monitoring, security and `README_System.md` §21 QA. EWMA/CUSUM เริ่มได้เพียง shadow; evidence-only หรือ alert vote ต้องขอ release decision ใหม่พร้อม version และ rollback. ไม่มีขั้นตอนไหนอนุญาต Auto-bootstrap เขียนทับ `ACTIVE_FROZEN` หรือให้ technician note เปลี่ยน class/threshold เอง

**Change log:** 2026-09-25 — เพิ่ม completed-window builder, pure scorer, EWMA/CUSUM research engine, candidate temporal-limit fitter, read-only preview และ block เส้นทาง raw-row ที่เขียนข้อมูลเดิมโดย default. P2–P6 ยังไม่เสร็จ; ไม่มี migration, profile activation, Server deployment หรือ alert write. รายละเอียด QA/ข้อจำกัด: `deployment/QUALIFIED_5M_SHADOW_IMPLEMENTATION.md`.

