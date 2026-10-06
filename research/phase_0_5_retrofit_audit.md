# Phase 0–5 Research Retrofit Audit

**Reviewed:** 2026-09-08
**Purpose:** ตรวจว่างาน Phase 0–5 ที่ทำก่อน Thesis v1.1 สอดคล้องกับ research-informed contract ใหม่เพียงใด

## Audit by phase

| Phase | สิ่งที่ทำแล้วและยังใช้ได้ | สิ่งที่ต้อง retrofit ก่อน production claim | สถานะ |
|---:|---|---|---|
| 0 | Data Contract, CP1/CP2, SV และกติกา `Hp_2nd` ถูกบันทึก | ยืนยัน pressure unit, timezone, P&ID และ controller codebook | Pass with caveats |
| 1 | inventory, cadence, coverage และ baseline eligibility มีหลักฐาน | แยก recipe/load/facility-water และ service windows เมื่อมีข้อมูล | Pass with caveats |
| 2 | baseline แยก machine–module–SV และใช้ robust statistics | Operating-state interpretation ยังเป็น working logic; ต้องยืนยัน `Busy/Status` | Pass with caveats |
| 3 | relative features, chronological temporal split และ LOMO มีผลแล้ว | เพิ่ม inner HPO, calibration block, multiple seeds, ARX/PCA/ECOD/COPOD/CUSUM baseline ภายใต้ outer test เดียวกัน | Exploratory only |
| 4 | event-aligned one-second response และ coverage audit มีผลแล้ว | เพิ่ม purge/group isolation ระดับ cycle, opening/SV On coverage และ service-epoch test | Coverage limited |
| 5 | เปรียบเทียบ minute-only, 30 s และ 120 s ด้วยข้อมูลเดียวกัน | ลด feature-to-event ratio, matched search budget, multiple seeds และ threshold calibration ที่ไม่แตะ outer test | Exploratory only |

## สิ่งที่ถูกนำไปใช้แล้วใน Phase 06

- readiness แยก steady profile ออกจาก event-response profile
- past-only calibration และ future-only shadow replay ต่อ profile
- robust two-pass contamination quarantine
- profile half-stability และ day-block bootstrap uncertainty
- threshold มาจาก retained calibration เท่านั้น
- candidate artifact มี profile/feature version, source dates, reason codes และ approval fields
- ไม่มี code path ที่พา profile เข้า `ACTIVE_FROZEN` อัตโนมัติ


- ไม่เปลี่ยน `Busy/Status` state mapping จนกว่าจะมี controller codebook
- ไม่สร้าง service epoch จาก pressure jump โดยอนุมานว่าเป็นการเติมน้ำยา
- ไม่เติม opening หรือ SV On events ด้วยข้อมูลสังเคราะห์เพื่อให้ coverage ดูครบ
- ไม่ใช้ alert rate เดิมเป็น accuracy และไม่เลือก parameter จาก LOMO/sparse outer result

## Acceptance implication

Phase 0–2 ยังถือว่าเสร็จแบบมี caveat ส่วน Phase 3–5 เป็นหลักฐาน exploratory ที่ต้องถูกเปรียบเทียบใหม่ใน matched benchmark ระยะถัดไป Phase 06 implementation รอบปัจจุบันแก้ช่องว่างด้าน lifecycle และ uncertainty บางส่วนแล้ว แต่ไม่แทน matched model benchmark, server replay หรือ technician label loop

## Change log

- 2026-09-08 — Initial retrospective audit against README sections 17–21 and Thesis v1.1
