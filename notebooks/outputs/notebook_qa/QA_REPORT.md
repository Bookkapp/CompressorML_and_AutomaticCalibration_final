# HT9046MX Notebook QA Report

**Date:** 2026-09-10
**Result:** `PASS_WITH_CAVEATS` — ผ่าน 27 จาก 27 checks

## README section 21 QA Loop

| Layer | Result | Evidence / remaining condition |
|---|---|---|
| System QA | Pass | อ่าน README/SOT ซ้ำ; กติกา `Hp_2nd` เปลี่ยนเป็น qualified field-reference 180–230 psi พร้อม version migration |
| Data QA | Pass with caveats | grain/count/key ตรงกัน; timezone, service epoch และ operating context ยังขาด |
| Model QA | Pass for offline shadow scope | inner temporal HPO, separate calibration threshold, untouched outer/LOMO/sparse tests และ versioned hp180 replay ผ่าน; diagnostic accuracy ยังวัดไม่ได้ |
| Evidence QA | Pass | แยกผล readiness/deviation ออกจาก fault accuracy และบันทึก artifact/version |
| Presentation QA | Pass | ตรวจภาพจริงหลังปรับ denominator, cohort และ outlier view |
| Production QA | Partial | Offline replay, restart parity, version/order/checksum และ safe-failure tests ผ่านแล้ว; live MySQL/server, exact rollback target และ alert budget ยังไม่ผ่าน |
| Governance QA | Pass | Project, AGENTS, SOT, Roadmap, UX, graft, HANDOFF, THESIS และ README change log ถูกอัปเดต |

ดังนั้นคำว่า “ผ่าน” ในรายงานนี้หมายถึง notebook และ candidate-lifecycle implementation พร้อมใช้ทำงานวิจัยต่อ ไม่ได้หมายถึง Phase 06 ผ่าน production acceptance ทั้งหมด

## สิ่งที่ตรวจแล้ว

- Notebook ทั้ง 12 เล่มรันครบทุก code cell และไม่มี saved error output
- Navigator และ Phase 06 มีโครงสร้าง `tl;dr → Context & Methods → Data → Results → Takeaways`
- ช่วงข้อมูลและ timezone ถูกระบุ: 2026-08-04 00:00 ถึง 2026-09-01 17:10; source timezone ไม่ได้ encode
- จำนวน minute rows 3,548,928 และ eligible rows 2,667,008 ตรงกับหลักฐานเดิม
- lifecycle, approval package และ summary ตรงกันที่ 262 profiles
- สถานะตรงกัน: 39 `SHADOW_VALIDATION`, 3 `CANDIDATE_PROFILE`, 66 `REVIEW_REQUIRED`, 154 `INSUFFICIENT_DATA`
- event-response 524 strata เป็น `INSUFFICIENT_COVERAGE` ทั้งหมด ไม่มีการเติมข้อมูลในกลุ่มที่ไม่รองรับ
- candidate JSON มีครบ 19 เครื่อง
- split เป็น past calibration → future shadow ต่อ profile และไม่มี random row split
- threshold q99/q99.5 มาจาก retained calibration เท่านั้น
- ไม่มี profile ใดเปิดใช้เองหรือเข้า `READY_FOR_APPROVAL`/`ACTIVE_FROZEN`
- Phase 06 ประกาศ `profile_version=autobootstrap-candidate-v2-hp180` และ `feature_version=minute-state-core-hp180-v2` ตรงกันทั้ง run manifest และ lifecycle output
- External intake v2 ถูกสร้างซ้ำจาก raw 354 daily files; `daily_module_sv_pressure.csv` ใช้ `hp2_below_180_pct` และผล provenance/overlap เดิมไม่เปลี่ยน

## Presentation QA ที่ปรับแล้ว

- Heatmap อธิบายความหมายของช่องว่างและช่วงข้อมูล
- Stability curve แสดงจำนวน profile ในแต่ละ horizon และเตือนเรื่อง cohort ที่ลดลง
- Bootstrap uncertainty แสดงทั้ง full scale และ focused scale โดยไม่ซ่อน outlier
- Shadow exception แสดง alert rate คู่กับ denominator และไม่ตีความ 100% เป็น fault accuracy

## Caveats ที่ยังบล็อก Production

- ไม่มี technician-confirmed fault/no-fault labels
- service/refill epoch และ source timezone ยังไม่ยืนยัน
- `Busy/Status` interpretation ยังรอ controller codebook
- ไม่มี recipe, load และ facility-water context
- ยังไม่มี immutable `ACTIVE_FROZEN` registry/exact rollback target, live MySQL/server replay และ approved alert budget

## Phase 7 hp180 update — 2026-09-10

- Notebook `07_HT9046MX_Server_Shadow_Replay_Colab.ipynb` รันครบ 8/8 code cells ไม่มี saved error
- Notebook `07D_MX080_Module6_OneSecond_Forensics_Colab.ipynb` รันครบ 11/11 code cells ไม่มี saved error
- QA รวมผ่าน 27/27 checks แบบ `PASS_WITH_CAVEATS`
- Primary replay 131,853 rows, 36 persistent alerts, 0.456 alerts/machine-day
- MX-080 post-transition raw flag rate 100% แต่มี raw flags ก่อน transition จึงไม่ใช่ validated lead time
- MX-080 water-keyword audit พบ 0 ข้อความในช่วง 3–8 ก.ย.; พบ `ALM004 Water flow error [IN]` เพียง 1 ครั้งในวันที่ 30 ส.ค. จึงยังไม่ยืนยัน water/tank cause

รายละเอียดที่เครื่องอ่านได้อยู่ใน `notebook_qa_summary.json`; execution inventory อยู่ใน `notebook_execution_inventory.csv`.
