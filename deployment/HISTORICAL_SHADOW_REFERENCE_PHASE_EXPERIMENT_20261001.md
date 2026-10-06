# ทดลองเลือก Reference และ Shadow ย้อนหลัง — 1 ตุลาคม 2026

## ข้อสรุปก่อนอ่านรายละเอียด

**Shadow ย้อนหลัง 3 วันเต็มที่แยกจากวันสร้าง Profile ทำได้ และไม่ต้องรออีก 3 วันในอนาคต** แต่การเลือกช่วงอ้างอิงอัตโนมัติยังมีข้อจำกัด: รอบนี้การคัดช่วงนิ่งไม่ได้ลดภาระการเตือน และกติกาแบ่ง segment ย่อยเกินไปจนหลายบริบทไม่มี reference รองรับ โดยเฉพาะ MX080/M6

จึงยังคง frozen local robust-z + 3 adjacent minutes เป็น primary เดิม ไม่เปลี่ยน Active Profile หรือเปิด phase suppression. สิ่งที่ควรเพิ่มถัดไปคือ **หน้าทบทวนช่วง Reference ที่เลือก/วันที่ตัดออก/phase และ contributor** ให้ผู้ใช้ตัดสินก่อนสร้าง candidate ไม่ใช่เปลี่ยนค่าผิดปกติให้เป็น normal อัตโนมัติ

Notebook ที่ execute แล้ว: `notebooks/08M_Historical_Shadow_Reference_and_Phase_Comparison_Colab.ipynb` — 11 code cells, 9 กราฟพร้อมสมการและคำอธิบายภาษาไทย

สถานะ: **LOCAL RETROSPECTIVE EXPERIMENT**. รันคำนวณบนคอมเครื่องนี้ ไม่เรียก SQL, ไม่ทำ registry/Approval จริง, ไม่แก้ worker/Dashboard/scorer, ไม่ติดตั้ง Server และไม่ Push Git. ไม่มี ML model retraining รอบนี้

## 1. ข้อมูลจริงและวันตัดรายเครื่อง

ใช้ caches ที่สร้างจาก raw observed seconds และ QA แล้วใน 08K/08L ไม่สร้างข้อมูลวินาทีขึ้นจาก minute snapshots และไม่อ่าน `_Static.txt`

| เครื่อง / ทุก M1–M8 | ที่มาข้อมูล | Fit interval ที่ขอ [start,end) | Shadow [start,end) | หมายเหตุ |
|---|---|---|---|---|
| MX017, MX024, MX080 | Downloads dynamic ZIPs ที่อ่านใน 08K | 31 Aug–28 Sep | 28 Sep–1 Oct | ไม่ใช้ 1 Oct ซึ่งเป็น partial day |
| MX029, MX041, MX057, MX070 | original raw Parquet ที่อ่านใน 08L | 1–29 Aug | 29 Aug–1 Sep | ข้อมูลจริงเริ่ม 4 Aug; 1 Sep จบกลางวันและถูกตัดออก |
| MX118, MX119 | raw Parquet; archive มีเพียง 17–20 Aug | 20 Jul–17 Aug | 17–20 Aug | ไม่มีอดีตใน Fit; ทุกวิธี unsupported ไม่ใช่ Normal |
| MX080/M6 case regression | แหล่งเดิม + raw-second forensic archive | 8 Aug–5 Sep | 5–8 Sep | ประเมิน known case 7 Sep 12:24–24:00 |
| MX057/M1 case regression | raw Parquet + archived raw case | 30 Jul–27 Aug | 27–30 Aug | ประเมิน known case 29 Aug 04:06–22:51 |

เวลาเป็น local archive convention `Asia/Bangkok`; ยังไม่ได้ตรวจ timezone ของ Server จริง. `[start,end)` หมายถึงรวมจุดเริ่มแต่ไม่รวมจุดจบ. Shadow วันที่ 28–30 Sep จึงเขียน end=1 Oct. Calendar interval ไม่ได้แปลว่ามี sensor coverage ครบทุกนาที

มี 11 experiment runs × 8 modules = **88 บริบท** และ 4 วิธี = **352 reference comparisons**. Latest fleet มี 72 บริบท แยก case replays อีก 16 บริบท; ไม่รวม case replay ซ้ำใน headline latest rates. ข้อมูลทั้งหมดเป็น retrospective ที่เคยตรวจแล้ว ไม่เรียกว่า untouched blind outer test

### การแก้ที่ QA พบ

รอบเริ่มต้นใช้ 9 Sep เป็น cutoff ของอีก 6 เครื่องตามวันปลายสุดของ fleet ซึ่งผิด: source inventory ยืนยัน 029/041/057/070 จบ 1 Sep กลางวัน และ 118/119 จบ 20 Aug กลางวัน. แก้เฉพาะ cutoff ให้ตรงแหล่งข้อมูลจริง; parameters/methods เดิมทั้งหมด. ไม่ใช้ตัวเลขรอบที่ Shadow ว่างมาสรุปผลหรือเลือกวิธี. บันทึกใน protocol revision `historical-reference-phase-v1.1-inventory-cutoff`

## 2. สิ่งที่สืบทอดจาก Data Gate

แต่ละ completed minute ต้องมี ≥57 unique observed seconds, ไม่มี duplicate timestamp, maximum gap ≤5 seconds และทุกแถวเป็น `Status=Run`, module `Status_n=On`, `Busy_n=0`, `SV_n=Off`; sensor finite และ Valve ไม่ติดลบ. ไม่ interpolate gaps

ใช้ 9 features: Hp1, Lp1, Hp2, Lp2, Valve, TempHi, TempLo, `dp1=Hp1-Lp1`, `dp2=Hp2-Lp2`. Control/manual records ยังอยู่ใน raw archive; การไม่ใช้ fit steady Cold ไม่ใช่การลบ log. Busy ไม่ถูกเปลี่ยนเป็น electrical compressor-run signal; ไม่ตี SV เป็น Hot/Room และไม่ตี manual marker เป็น refill/service

หลักฐาน input: 229 source-second-derived minute files พร้อม SHA256 ใน `input_receipt.json`; provenance ย้อนกลับ ZIP/raw Parquet/08K window QA ใน `inherited_source_receipt.json`. รอบนี้ reuse caches ไม่อ้างว่า reingest raw ทุกไฟล์ใหม่

## 3. เปรียบเทียบอะไร — ล็อกวิธีก่อนรันผล

| วิธี | แถว Fit ที่ใช้ | สิ่งที่ทำเมื่อ score Shadow |
|---|---|---|
| State only | ทุกนาทีอดีตที่ผ่าน state/quality gate | score ทุก qualified minute |
| Steady reference | นาทีอดีตที่ low dynamics ต่อเนื่อง | score ทุก qualified minute รวมช่วงเปลี่ยนผ่าน |
| Segment reference | supported segment ที่มีนาทีมากที่สุด; เสมอเลือกก่อน | score ทุก qualified minute ถ้ามี reference พอ |
| Segment + steady | intersection ของสอง selector | score ทุก qualified minute ถ้ามี reference พอ |

**Phase ไม่ใช้ปิด alert.** ช่วงที่ไม่มี reference แสดง `unsupported` และ score ว่าง ไม่ให้ Normal/0-score แทน. แสดง score/phase/contributor แยกกัน; `STEADY_CANDIDATE` ไม่ใช่ healthy label

ไม่มี HPO/parameter search ในงานนี้ จึงไม่มีการเลือกจาก inner หรือ outer ผลที่ดูแล้ว. จำนวน 5 trailing minutes และ 3 stable windows เป็นค่า exploratory ที่ล็อกไว้ก่อน ไม่ได้พิสูจน์ว่า optimal. หากทดลอง grid ภายหลังต้องแยก inner และ fresh/independent outer ใหม่

### สูตร Profile และ detector ที่ใช้ร่วมกัน

$$m_j=\mathrm{median}(x_j),\qquad s_j=\max(1.4826\,MAD_j, IQR_j/1.349, f_j)$$

$$z_j(t)=\frac{x_j(t)-m_j}{s_j},\qquad A_t=\max_j|z_j(t)|$$

Floor `Valve=1 count`; อื่น `.1 source unit`. คัด quarantine initial `A>8`, fit รอบสองจาก retained rows และ `threshold=Q99.5(A retained fit)`. Flag ใช้ `A>=threshold`; persistence ต้อง flag 3 นาทีที่ติดกันจริง

นี่คือ scale ของ **research 08K/08L** เพื่อให้เปรียบเทียบ selector บน estimator เดียวกัน ไม่ใช่การรับรองว่า scale/threshold เท่ากับ registry/Active Profile ทุกเวอร์ชัน. State-only คือ comparator ของ local research ไม่ใช่นำ Active จริงมาเปลี่ยนหรือ fit ทับ

### Causal phase

บน 5 qualified adjacent minute means ที่สิ้นสุด ณ ตอนประเมิน:

$$S_j(t)=\left|\mathrm{median}_{a<b}\frac{x_j(t-4+b)-x_j(t-4+a)}{b-a}\right|$$

$$V_j(t)=1.4826\,\mathrm{median}_{u=t-4}^{t}|x_j(u)-\mathrm{median}(x_j(t-4:t))|$$

Learn Q90 limits จาก **Fit เท่านั้น**, แล้วใช้คงที่กับ Shadow. Slope units = source-unit/min. Limit floors ตาม feature order: slope `[.1,.1,.1,.1,.25,.01,.01,.1,.1]`, variation `[.1,.1,.1,.1,1,.05,.05,.1,.1]`. Floor เป็น numerical/instrument-resolution guard ในการทดลอง ไม่ใช่ขีดจำกัดความปลอดภัยที่ช่างยืนยัน

ต้องต่ำกว่า S/V limits ทุก feature ต่อเนื่อง 3 windows จึงเป็น steady candidate. Gap/control ineligibility ทำให้เริ่มนับประวัติใหม่. ข้อมูลครบแต่ยังไม่นิ่ง = changing/settling; history ไม่ครบ = unknown history. Unknown actual onset ยังมีคอลัมน์แยก ไม่เดาว่า compressor เพิ่งเริ่มจากขอบไฟล์. นี่เป็น statistical steady selector ไม่ใช่ fitted healthy startup envelope

### Past segment selection

ใช้ day medians ของ hp2/lp2/TempHi/TempLo; scale สำหรับ level jump เป็น median within-day `1.4826 MAD` พร้อม floor pressure `.1`, temperature `.05`. วันมี ≥60 qualified minutes. ระหว่างวันติดกัน max normalized jump >6 หรือวันขาด ให้แบ่ง segment ใหม่. Segment ต้องมี ≥7 วัน/≥200 นาที; เลือกจำนวน qualified minutes มากที่สุด เสมอเลือกก่อน. หลาย supported segments = review ไม่ autoเลือกเป็น service epoch

กติกานี้เลือกจากอดีตเท่านั้น แต่ **การไม่รั่วข้อมูลไม่ได้แปลว่า selector เหมาะสม**: ผลจริงแสดงว่าการหารด้วย within-day scale เล็กและใช้ max ทุก feature ทำให้ sensitivity ต่อ day-level drift สูงเกินไปในหลายโมดูล

## 4. ผลล่าสุดบนแถวเดียวกัน

ทั้ง 4 วิธีมี supported reference ร่วมกัน **37 machine×module contexts / 123,658 qualified minutes**. ไม่มีการรวมเคส replay เพิ่มใน denominator นี้

| วิธี | Persistent flagged minutes | สัดส่วน | Episode openings ใน replay |
|---|---:|---:|---:|
| State only | 14,492 | 11.7194% | 334 |
| Steady reference | 15,895 | 12.8540% | 599 |
| Segment reference | 34,572 | 27.9578% | 773 |
| Segment + steady | 41,792 | 33.7964% | 1,027 |

Openings คือเริ่มช่วง persistent ใน offline replay ไม่ใช่จำนวน PM Alerts/ใบงานที่สร้างจริง. ตัวเลขข้างต้นคือ workload ไม่ใช่ FPR/precision/accuracy; ไม่มี healthy-negative truth ที่ครบ

### ดูทุกบริบท ไม่ซ่อนบริบทที่ unsupported

Latest ทั้ง fleet มี **213,086 qualified minutes**:

- State-only/steady ประเมินได้ 157,683 นาที; อีก 55,403 ไม่มี reference รองรับ
- Segment/combined ประเมินได้ 123,658 นาที; อีก 89,428 ไม่มี reference รองรับ
- Fit-only screen ของ State-only: 29 screened-not-approved, 21 review, 22 insufficient จาก 72 contexts
- Steady: 27 screened, 23 review, 22 insufficient
- Segment: 19 screened, 18 review (รวมหลาย segments), 35 insufficient
- Combined: 17 screened, 20 review, 35 insufficient

บริบทที่ครบเพียง **numerical** fit/shadow screen มี 8/3/3/1 ตามสี่วิธี แต่ไม่ผ่าน human/codebook/unit/source/registry production gates โดยอัตโนมัติ และ **ไม่มี Profile ใดถูก Approval**

### ตัวอย่าง MX080/M6 — เหตุใด reference กว้างเป็นปัญหา

ใน Fit 31 Aug–27 Sep มี day median Hp2 ประมาณ 180–190 และ plateau สูงประมาณ 300–340 ปนกัน:

- State-only: Hp2 median 190.64, scale 89.00 psi; quarantine 21.60% → review
- Steady: Hp2 median 184.16, scale 8.92 psi; quarantine 18.33% → review
- Segment/combined: ไม่มี segment ครบขั้นต่ำ 7 วัน → unsupported

Scale ที่แคบลงยังไม่พิสูจน์ว่า baseline ถูก: การคัด steady ยังเหลือ contamination/review และ threshold เทียบทุก sensor. รูปกราฟนิ่งที่ระดับสูงไม่ถูกเรียก Normal. รอบนี้ไม่เปลี่ยน reference เป็น plateau ล่าสุดและไม่ปรับ Active จากผลเหล่านี้

## 5. Known-case regression และช่วงก่อนเกิดเคส

| เคส | State-only | Steady | Segment / combined |
|---|---|---|---|
| MX080/M6, 7 Sep 12:24–24:00 | 686/692 = 99.13% | 686/692 = 99.13% | Unsupported: ไม่มี reference พอ |
| MX057/M1, 29 Aug 04:06–22:51 | 1,124/1,124 = 100% | 1,124/1,124 = 100% | ทั้งคู่ 1,124/1,124 = 100% |

นี่คือ coverage ของ qualified minutes ใน owner-confirmed behavioral case ไม่ใช่ detector accuracy หรือ fault/cause label. First persistent ของ case replay เป็น 12:24 และ 04:06 ตามลำดับ; MX080 มี warning ก่อน pressure shift จึงไม่ได้แปลว่า first episode ถูกระบุตรง physical onset หรือมี latency เท่านี้ทุกครั้ง

**ปัญหาช่วงต้นยังไม่หาย:** MX080 7 Sep 11:45–12:20 มี 13 qualified minutes; State-only และ Steady เตือน persistent 11 นาที โดย dominant เป็น `lp1` จาก **reference ทดลองใหม่**. ไม่ใช้ช่วงนี้ fit/tune และยังไม่ adjudicate เป็น healthy negative. ข้อนี้ไม่ขัดกับ checkpoint เดิมที่ Active/candidate อีกชุดมี dominant TempLo/TempHi: โปรไฟล์/fit periods ต่างกัน. ห้ามนำ contributor ของคนละ profile มาอ้างเป็น score เดียวกัน

MX057 03:45–04:06 ก่อน case มี 17 qualified minutes และ 0 persistent ในทั้ง 4 วิธี. เป็น pre-case diagnostic เฉพาะช่วง ไม่ใช่ชุด healthy validation ที่ยืนยันแล้ว

### หลายรอบเริ่มเครื่อง

กราฟ raw observed Run-entry trajectories ของ M6 ใน Fit 31 Aug–27 Sep แสดง earliest 18 sampled starts ต่อเครื่องจาก archive เดิม: MX017 กระจาย 6 วัน, MX024/MX080 เพียง 2 วัน. Initial levels/thermal responses แตกต่างกันชัดเจน แต่เป็น unreviewed runs ไม่มี healthy labels และไม่ได้ fit normal envelope. 18 รอบที่มาจาก 2 วันไม่ถือว่าครอบคลุม operating conditions เพียงพอ

Observed compressor start, Cold entry และ post-manual ต้องแยกชนิดก่อนทำ start-response model. รอบนี้ใช้ raw start graphs เป็นบริบท ไม่ใช้ normal-startup suppression คงที่ 20 นาที และไม่เปิด EWMA/CUSUM/ARX/DPCA/IF เป็น primary vote

## 6. แนวทางที่เลือกหลังทดลอง

1. **คง primary เดิม** ขณะเพิ่ม diagnostics ไม่ย้ายไป segment-auto-adoption หรือ LSTM เพียงเพราะอยากได้ alert น้อย
2. เพิ่มตัวเลือก **historical complete-day shadow** ใน manual calibration workflow โดยใช้ cutoff รายเครื่อง ไม่ใช่ fleet-wide latest date. Backend ปัจจุบันมี historical trailing-72h shadow อยู่แล้ว; ยังไม่ได้แก้ runtime เป็น complete-calendar-day option ในรอบนี้
3. เพิ่ม reference review package: daily level/scale, control/manual boundaries, requested/actual coverage, proposed segments และวันถูกตัดออก. ผู้ใช้เลือกช่วงที่มีหลักฐานเหมาะสมก่อน Candidate; เปลี่ยน selection แล้วต้องสร้างเวอร์ชัน/Shadow ใหม่
4. ให้ causal phase เป็น **review evidence** ก่อน ไม่ปิด score ที่ changing/unknown. ช่วงใหม่ที่นิ่งผิดระดับยังวัด deviation จาก frozen reference ได้
5. หาก candidate review/ไม่อนุมัติ: ใช้ Active เดิมต่อหากยังเข้ากันได้; ผู้ใช้เปลี่ยน reference dates/context หรือเก็บ normal-reference evidence เพิ่ม แล้วสร้าง candidate ใหม่. เครื่องใหม่ที่ยังไม่มี Active ให้แสดง calibration/insufficient ไม่สร้าง Normal score ทดแทน
6. ถ้าจะปรับ segment detector ให้ลอง sustained daily change + absolute engineering floors + event context บน **inner split ใหม่** และเทียบ unseen starts/days/healthy reviewed intervals. ตัวเลขรอบนี้ไม่ถูกใช้เลือก jump threshold ใหม่ย้อนหลังแล้วประกาศผ่าน

## 7. QA / วิธีรันซ้ำ

Support files:

- `research/historical_shadow_reference_phase_protocol_v1.json` — ทุก parameters / cutoff correction / scope
- `notebooks/support/historical_shadow_reference_phase.py` — selectors, past-only fit และ minute replay
- `notebooks/support/historical_shadow_reference_phase_presentation.py` — figures + notebook execute/export
- `notebooks/support/audit_historical_shadow_reference_phase.py` — score/raw/persistence/aggregate/input audit
- `notebooks/support/test_historical_shadow_reference_phase.py` — 13 focused tests

Private local outputs อยู่ที่ `notebooks/outputs/historical_shadow_reference_phase_v1/`: CSVs, frozen offline-reference JSON, per-minute Parquet, source receipts/hashes, nine PNG/SVGs, notebook preview HTML และ QA JSON. ไม่ต้องเข้าถึง MySQL หรือ target IP เพื่อรัน

```powershell
python -X utf8 -m pytest notebooks/support/test_historical_shadow_reference_phase.py notebooks/support/test_october_three_machine_calibration.py notebooks/support/test_local_profile_model_selection.py -q
python -X utf8 -m notebooks.support.historical_shadow_reference_phase
python -X utf8 -m notebooks.support.audit_historical_shadow_reference_phase
python -X utf8 -m notebooks.support.historical_shadow_reference_phase_presentation
```

ใช้ Python 3.12.10, NumPy 2.2.1, Pandas 2.2.3 พร้อม PyArrow, matplotlib, nbformat, nbclient, nbconvert และ project support dependencies ที่ใช้ใน 08K/08L. บน Colab mount/upload caches ส่วนตัวพร้อม project files; ตั้ง `PROJECT_ROOT` และ `RUN_EXPERIMENT=True` หากต้อง rebuild numerical fit. ค่า False อ่านผลที่คำนวณแล้วและตรวจ hashes ไม่แอบ retrain เมื่อเปิดกราฟ

33 tests รวมใหม่และ regressions เดิมผ่าน. Notebook 11 code cells/9 figures execute แล้ว ไม่มี error; raw-second mean เทียบ strict minute cache exact 205 นาที MX080/M6 และ 245 นาที MX057/M1. Whole-evidence audit ตรวจ1,520,640minute records/352reference comparisons ไม่ใช่เฉพาะ sampled plots. CSV threshold อ่านด้วย `float_precision='round_trip'`; frozen references เก็บ JSON float ตรงต้นทางเพื่อรักษา `>=` ที่ขอบ cutoff ไม่แก้ด้วย tolerance. Numerical rerun ได้ score Parquet SHA256 เดิม `ff09fa7e082f35cbe6e97b5b34c8db42867a007f438ede5bf6e248b7e8733da6`

เวลาคำนวณจาก cached minutes ประมาณ 78–80 วินาทีต่อ run บนคอมเครื่องนี้ ไม่รวม raw ingestion/DB/Server latency และไม่ใช่ fleet Server benchmark. คะแนนจาก numerical rerun ต้องตรง artifact hashes; runtime seconds ไม่จำเป็นต้องเท่าเดิม

Presentation QA ตรวจแยกหน่วย, denominator, unsupported labels, actual-second gaps, contributor strip และ absence-of-data. แก้กราฟ control ให้เป็นแถบ active states ไม่ใช่ offset lines ที่ดูเหมือน On ตลอด; ใส่ `Not evaluated` เมื่อไม่มี segment ไม่ปล่อยแถวว่างให้ดูเหมือนไม่พบ anomaly

### Checklist

- [x] อ่านระบบ/SOT/hand-off และไม่เปลี่ยน tag semantics
- [x] ระบุ source-time/grain/period/filter และ source inventory รายเครื่อง
- [x] Fit/limits/segment/cut ใช้อดีตเท่านั้น; ไม่มี HPO/known-case tuning
- [x] Candidate support/retained days/quarantine/half-shift/unknown coverage แสดงครบ
- [x] Test causality, gap reset, persistence, min-days และ flat abnormal plateau
- [x] Execute notebook, inspect/revise figures, raw-minute parity และ exact artifact reload
- [x] อัปเดต SOT/Project/Roadmap/HANDOFF/README_System/UX/AGENTS/graft/notebook guide
- [ ] Reviewed healthy startups/negative intervals และ fresh independent holdout
- [ ] Versioned registry/UI integration ของ complete-day shadow/reference selection
- [ ] Actual Server timezone/late-commit/Active loading/approval/rollback acceptance

รายละเอียดที่ยังพิสูจน์ไม่ได้: fault cause, sensitivity ทุก failure, false-positive rate, unseen startup specificity, calibrated probabilities, production availability และผลเมื่อ source latency/recipe/load/water ไม่เหมือน archive. งานนี้ไม่ทำ DB/Server writes และไม่สร้าง supervised labels
