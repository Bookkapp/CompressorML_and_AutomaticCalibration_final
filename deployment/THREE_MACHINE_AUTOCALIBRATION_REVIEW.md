# ทบทวน Auto-Calibration จาก MX017, MX024 และ MX080

วันที่ 1 ตุลาคม 2026 · วิเคราะห์บนคอมเครื่องนี้ · ยังไม่ได้เปลี่ยนระบบที่ใช้จริง

## คำตอบหลัก

ควรพัฒนา Auto-Calibration ไปทาง **แยกช่วงการทำงาน และเลือกช่วงอ้างอิงที่คงที่ก่อน fit** มากกว่าการเพิ่มจำนวนวันย้อนหลังหรือขยาย threshold อย่างเดียว เครื่องรุ่นเดียวกันและสถานะ Cold เดียวกันยังมี baseline และความสัมพันธ์ต่างกัน ขณะเดียวกัน โมดูลเดียวก็เปลี่ยนระดับได้ตามเวลา

ข้อมูลชุดนี้สนับสนุนการใช้ robust profile รายเครื่อง–รายโมดูลต่อไป ยังไม่ให้เหตุผลเพียงพอที่จะเปลี่ยนไป LSTM หรือกล่าวว่าโมเดลใหม่จะตรวจ fault ได้แม่นกว่าเดิม ปัญหาที่เห็นชัดในรอบนี้คือ **คุณภาพและความหมายของข้อมูลที่นำไปสร้าง profile**

## 1. ข้อมูลที่ใช้จริง

อ่าน ZIP ทั้ง 5 ส่วน `HT9046MX-Compressor-Data-20261001T095156Z-1-001..005.zip` ใน `C:/Users/Book/Downloads` รวม ZIP เดือนกรกฎาคมของ MX080 ที่ซ้อนอยู่ภายใน ส่วน `_Static.txt` ไม่ได้อ่านหรือวิเคราะห์ตามคำขอของเจ้าของโครงการ

| เครื่อง | Daily raw files | แถวต้นทาง | ช่วงเวลา |
|---|---:|---:|---|
| MX017 | 93 | 7,772,969 | 1 Jul 00:00:00 – 1 Oct 15:55:01 |
| MX024 | 93 | 7,801,416 | 1 Jul 00:00:00 – 1 Oct 15:45:00 |
| MX080 | 93 | 7,773,095 | 1 Jul 00:00:00 – 1 Oct 15:34:59 |
| รวม | 279 | 23,347,480 | วันที่ 1 Oct เป็นวันไม่เต็ม |

ไฟล์มี 82 คอลัมน์: Time, Status และ 10 tags × 8 modules. Timestamp ประกอบจากวันที่ในชื่อไฟล์กับ Time; ไม่มี timezone offset จึงคงนาฬิกาต้นทางไว้ การตีความเป็นเวลาไทยเป็นสมมติฐานสำหรับงาน local นี้ ไม่ใช่การยืนยัน clock ของ Server. Pressure คาดว่าเป็น psi, temperature เป็น °C และ Valve เป็น command count ตาม contract แต่ไม่ได้ตรวจ calibration certificate

ตัวอย่าง interval ที่ห่างกัน 1 วินาทีคิดเป็น 98.5268% ของ adjacent source rows. ไม่ได้หมายความว่าทุกนาทีมีข้อมูลครบ และไม่ใช่จำนวน sample อิสระทางสถิติ

### คุณภาพข้อมูลก่อนสร้าง profile

| เครื่อง | แถวที่อยู่ใน timestamp ซ้ำ* | ก้าวเวลาที่เรียงย้อน | Missing cells |
|---|---:|---:|---:|
| MX017 | 40,617 | 700 | 0 |
| MX024 | 13,143 | 220 | 0 |
| MX080 | 4,380 | 18 | 0 |

*นับทุกแถวที่อยู่ใน duplicated timestamp ด้วย `keep=False` ไม่ใช่จำนวนแถวเกินที่ควรลบทิ้ง. ไม่เลือกค่าใดค่าหนึ่งแทนโดยอัตโนมัติ; นาทีที่มี duplicate ถูกตัดจาก qualification ทั้งนาทีตามกฎเดิม และยังเก็บหลักฐานไว้. ข้อมูลถูกเรียงเวลาเพื่อคำนวณ แต่บันทึก out-of-order ของต้นทางก่อนเรียงไว้แล้ว

คำนวณครบ 3,214,080 calendar module-minute slots. มี source อยู่ 3,156,896 slots, ผ่าน quality 3,084,896 slots และผ่านทั้ง quality กับ Cold state 2,036,991 slots. ตัวเลขเหล่านี้ไม่ใช่จำนวน normal labels

## 2. Baseline ไม่เท่ากันจริง แต่ยังไม่รู้สาเหตุครบ

ตัวอย่าง median จาก **ทุก qualified Cold minute** ในชุดนี้:

| ตัวแปร/โมดูล | MX017 | MX024 | MX080 |
|---|---:|---:|---:|
| Hp_2nd M1 (source psi) | 194.87 | 205.27 | 181.93 |
| TempLo M1 (source °C) | -66.28 | -22.33 | -12.10 |
| Valve M1 (command) | 102 | 81 | 80 |
| Hp_2nd M6 (source psi) | 202.92 | 194.31 | 191.05 |

ค่ารวมหลายเดือนใช้บอกว่า distribution ต่างกัน ไม่ใช่ประกาศว่าเป็นค่าปกติของเครื่องนั้น โดยเฉพาะ M6/MX080 ซึ่งมีช่วงปัญหารวมอยู่ด้วย

แม้หัก median รายวันออกก่อนคำนวณ Spearman ความสัมพันธ์ `Lp_2nd ↔ TempLo` ของ M1 ยังเป็น +0.57, -0.49 และ -0.27 ตามลำดับ จึงไม่ควรนำ regression หรือ relationship rule เดียวกันไปใช้กับทุกเครื่องทันที ไม่มี recipe/setpoint/load/water telemetry ที่ครบเพื่อพิสูจน์ว่าบริบทเหมือนกัน; ค่า correlation เป็นเพียงความสัมพันธ์ ไม่ใช่สาเหตุทางกายภาพ

M7 มี qualified Cold เพียง 0, 102 และ 36 นาทีตามลำดับ ไม่เพียงพอสำหรับ profile จึงแสดง unsupported ไม่ใช่ baseline=0

## 3. MX080/M6 แสดงว่าการรวมประวัติอาจกลบปัญหา

Daily median ของ qualified-minute `Hp_2nd_6`:

| ช่วง | พฤติกรรมที่สังเกต |
|---|---|
| 3–6 Sep | ประมาณ 190 psi |
| 7–8 Sep | ประมาณ 332–340 psi; เชื่อมกับ case ที่เจ้าของยืนยันไว้แล้ว |
| 18–21 Sep | อีกช่วงสูงประมาณ 298–314 psi; เป็นช่วงให้ review เพิ่ม ไม่ใช่ fault label ใหม่ |
| ปลาย Sep | ลงมาแถว 176–180 psi และ TempLo/Valve ต่างจากก่อนหน้า |

ไม่มีหลักฐานพอจะบอกว่าการลดลงเกิดจาก leak, การเติมน้ำยา, การซ่อม หรือ recipe change. ต่ำกว่า 180 เป็น field screening evidence ตาม contract; ไม่ใช่ diagnosis

กราฟรายวินาที 7 Sep แยกได้สองเรื่อง: thermal transition ช่วงแรก กับแรงดันที่ขึ้นไปค้างระดับสูงหลังประมาณ 12:23. **“กราฟนิ่ง” ไม่เท่ากับ “ระดับปกติ”** การคัด steady ด้วย slope ต่ำอย่างเดียวจะรับ plateau ที่ผิดปกติเข้า profile ได้

## 4. ทดลอง lookback แล้วพบอะไร

รัน numerical fit/scoring 1,059 ชุด: fit จากอดีตย้อนหลังสูงสุด 7/14/30/60 วัน แล้ว score 3 calendar days ถัดไป ณ weekly cuts ตั้งแต่ 1 Aug. ก่อน Sep ประวัติยังไม่ครบ 60 วัน จึงเก็บ actual fit days แยกไว้. เปรียบเทียบกราฟ lookback เฉพาะ September machine–module–cut ที่ fit ได้ครบทั้ง 4 แบบ เพื่อใช้ shadow denominator เดียวกัน

วิธี fit เหมือนส่วน numerical ของ candidate เดิม:

\[
m_j=\operatorname{median}(x_j),\qquad
s_j=\max\{1.4826\operatorname{MAD}(x_j),\operatorname{IQR}(x_j)/1.349,f_j\}
\]
\[
z_j=\frac{x_j-m_j}{s_j},\qquad S=\max_j|z_j|.
\]

9 features: `hp1`, `lp1`, `hp2`, `lp2`, `valve`, `temphi`, `templo`, `dp1=hp1-lp1`, `dp2=hp2-lp2`. Floor เป็น 1 command สำหรับ Valve และ 0.1 source unit สำหรับ feature อื่น. First-pass retain เมื่อ S≤8 แล้ว refit; threshold เป็น retained training-score Q99.5. Raw flagใช้ S≥threshold และ persistence ต้อง raw-flag 3 qualified นาทีที่ติดกันจริง

ตัวอย่าง cut 26 Sep ของ MX080/M6:

| Fit lookback | Hp_2nd robust scale (psi) | First-pass quarantine | Raw flags / shadow minutes |
|---:|---:|---:|---:|
| 7 วัน | 97.79 | 7.48% | 0 / 3,420 |
| 14 วัน | 87.34 | 0.54% | 0 / 3,420 |
| 30 วัน | 2.98 | 32.11% | 0 / 3,420 |
| 60 วัน | 6.31 | 19.90% | 2,822 / 3,420 |

ผล 0 flags ไม่ได้แปลว่าดีกว่า: scale ที่กว้างจากการรวมระดับต่างกัน หรือการเลือก retained tail/threshold หลัง quarantine มาก อาจทำให้ sensitivity ลดลง. 209/665 state-only fits มี quarantine เกิน 5%; มีเหตุผลให้ review ไม่ใช่ approve ตาม flag rateต่ำ

**ขอบเขตสำคัญ:** ไม่ได้สร้าง candidate ใน MySQL registry และไม่ได้รัน approval lifecycle ครบทุก gate. ตัวเลขนี้ตรวจเฉพาะ fit/threshold/score; half-shift, retained coverage, units/timezone/codebook/service prerequisites, shadow duration/coverage และ human review ยังต้องตรวจแยก. ไม่รายงาน false-positive/recall เพราะไม่มี labels ครบชุด และไม่ได้เลือก parameter/release ที่ดีที่สุดจาก test ที่ตรวจแล้ว

## 5. ทำไมไม่เลือก timer 20 นาทีไปเลย

1,654,644/2,036,991 qualified minutes (81.23%) ไม่มี Cold onset ที่ยืนยันได้จาก observed boundary ตาม continuity criterion 2 วินาทีของการตรวจ event นี้ สาเหตุรวมถึงเริ่มไฟล์กลาง run และ source gaps; นี่ไม่ใช่จำนวน physical restarts. กฎ quality ของ minute ที่ยอม gap≤5s เป็นอีกเรื่องหนึ่ง

ทดลอง age≥20min ได้เพียง 357,440 นาที และเป็น subset ที่ source continuityดีกว่า การเลือก subsetนี้อาจเปลี่ยนบริบทด้วย จึงไม่ใช้ผลเป็นเหตุผลตั้ง blanket startup suppression 20 นาที

Raw Run entry กับ Cold-ready entry เป็นคนละ event: กราฟ Run จึงตรวจใหม่จาก actual raw boundary และเก็บสถานะโมดูลที่ตามมา แม้ยังไม่ผ่าน Cold. Cold/post-manual ledger แยกเก็บไว้. การไม่รู้ onset ไม่จำเป็นต้องทำให้ steady detectorใช้งานไม่ได้ตลอดไป; ในอนาคตสามารถสะสม trailing quality/state historyแล้วตรวจความนิ่งจากระดับปัจจุบันได้ โดยไม่แต่งเวลา startย้อนหลัง

Raw-boundary QA เปิดซ้ำ115candidate day-files แล้วตรวจได้550 within-day Run entries: MX017=287, MX024=129, MX080=134; ไม่บังคับColdทันที. ก่อนหน้านั้นตัวนับจากCold ledgerมี45/4/16unique startsเฉพาะที่เข้าColdพร้อมRun จึงไม่ใช่จำนวนRunentriesทั้งหมด. กราฟM6แสดง287/129/134cycles แต่มีsampleที่elapsed20minเพียง79/50/47cycles; runสั้น/หยุด/gap/ท้ายวันทำให้denominatorลดลง. เก็บrawstateและpartialcycles ไม่สร้างhealthylabelจากcurveเฉลี่ย และไม่ตีความทุกcontrollerRunentryเป็นindependent mechanicalrestartที่ตรวจยืนยันแล้ว

## 6. แนวทางที่แนะนำให้พัฒนาต่อ

```text
Raw seconds + source/event receipts
  → Data quality: units, time, duplicates, observed-second coverage
  → State boundaries: Run / Cold entry / Manual / SV / Unknown
  → Phase qualification: transition vs steady vs stable-but-different level
  → Stable reference-period selection + known-case/shift review
  → Machine × Module × qualified context numerical profile
  → Past-only threshold + baseline/relationship stability report
  → Future 3-day shadow: gaps, eligible time, contributors, episodes
  → Human approval → ACTIVE_FROZEN
  → Existing robust-z + persistence detector / Episode evidence
```

### A. เพิ่ม causal settling แต่คง level detector ไว้

ใช้ trailing slope/variation ของ pressure และ temperature, control continuity, recent manual boundary และ comparable level/differential. เริ่มตรวจ W=2/3/5 นาทีและ L=2/3/5 windows ใน inner developmentตามแผนเดิม ไม่ประกาศค่าใดเป็น defaultใหม่จากชุดที่ inspectแล้ว. ช่วงที่นิ่งแต่ต่างจาก frozen reference เป็น `SETTLED_REVIEW` ไม่ auto-normalize. ถ้าเป็น transitionให้เก็บ measurementsและshadow evidenceต่อ ไม่ปิดการตรวจทุกอย่าง

### B. ประวัติยาวเป็น evidence bank; profileเป็น stable reference

ไม่ hard-code ว่า 7,14,30หรือ60วันดีที่สุด. ตรวจ daily/cycle baseline, spread, level shifts และความสัมพันธ์ก่อนเลือกช่วง. หลาย distributionในColdเดียวกันอาจมาจากrecipe/load/Valve/serviceที่ไม่มีtag ต้อง reviewแยก. วันที่เลือกเป็น referenceต้องมีเหตุผลและ provenance ไม่ใช่เลือกเพราะทำให้shadowเตือนน้อย

### C. ป้องกัน profile “เรียนรู้ปัญหาเป็นปกติ”

Exclude owner-confirmed abnormal case จากnormal candidate; reviewช่วงเปลี่ยนระดับต่อเนื่องแม้ slopeต่ำ. `ChangeValve/Busy=1` เป็นmanual markerไม่ใช่refill/serviceที่ยืนยัน. ถ้ามีActiveเดิมให้freezeไว้ระหว่างshiftreview; candidateใหม่เก็บแยกพร้อมเหตุผล ไม่เขียนทับpointerเพื่อให้กราฟกลับมาเขียว

### D. แยก coverage ออกจาก health

Shadow3วันรายงาน source-observed coverage, source-quality coverage, Cold duty/eligible coverage, startup/unknown coverage และflag burdenคนละ denominator. กฎregistryปัจจุบันใช้observed source-minute coverageสำหรับ95% ไม่ใช่บังคับเครื่องCold95%ของเวลา. OFF/Manualเป็นบริบทไม่ถูกscore ไม่เรียกว่าsensorเสียหรือNormal

### E. ใช้ความสัมพันธ์ช่วย review profile ก่อนเพิ่ม model

เก็บ local correlation/differential/Valve contextรายช่วง พร้อมจำนวนวัน/cycles และconstant-featureข้อจำกัด. ถ้าบริบทไม่เทียบกันได้ไม่เอาpeer distributionมาบังคับlocal. รอบนี้ยังไม่เพิ่มcorrelation voter, ARX, EWMA/CUSUM live voteหรือLSTMเข้าscore

### F. เมื่อ implement ต้องทำเป็น candidate version ใหม่

การเปลี่ยนphase/fit-period filteringทำให้referenceเปลี่ยน แม้ยังใช้สูตรเดิม จึงต้องversion candidate/state policyและตรวจscorer-parityใหม่ → untouched future starts/steady periods + known-case regression → shadow3วัน → approval/rollback. ชุดนี้ถูกinspectแล้วใช้วางแผน/diagnostic ไม่ใช่freshaccuracytestหลังปรับparameter

## 7. หลักฐานและการรันซ้ำ

- Notebookรันเรียงทุกcell: `notebooks/08K_Three_Machine_Raw_Second_AutoCalibration_Review.ipynb`
- Data preparation: `notebooks/support/october_three_machine_calibration.py`
- Plot/notebook scaffold: `notebooks/support/october_calibration_presentation.py`
- Local derived outputs/ZIP hashes: `notebooks/outputs/october_three_machine_calibration_v1/`
- Tests: `notebooks/support/test_october_three_machine_calibration.py` — 10 testsผ่าน ทั้งquality/state gates, unknown onset, continuing history, candidate numerical-fit parityและgap persistence
- Actual raw-prefix QA: 9 boundedช่วง / 360 windows, gate mismatches0, maximumfeatureerror5.68e-14. เป็นsampled parity ไม่ใช่full-seriesruntime replay

```powershell
python notebooks/support/october_three_machine_calibration.py --stage all
python notebooks/support/october_calibration_presentation.py
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/08K_Three_Machine_Raw_Second_AutoCalibration_Review.ipynb --ExecutePreprocessor.timeout=600
python -m pytest notebooks/support/test_october_three_machine_calibration.py -q
```

Colab: อัปโหลดสองsupport scriptsกับNotebook และmount ZIP/derived outputsจากDrive; ปรับSOURCE_DIR/OUTPUT. ค่าเริ่มต้นอ่านcacheพร้อมmanifest; `REBUILD_RAW=True`คำนวณจากrawใหม่. Notebookบันทึกกราฟไว้ให้เปิดอ่านได้โดยไม่ต้องมีZIP แต่rerunต้องมีinputs/support scripts. Raw/cacheไม่ถูกpushGitHubในงานนี้

## 8. แหล่งอ้างอิงและข้อจำกัด

[NIST process stability](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm) สนับสนุนการตรวจmean/variance/distributionตามเวลา; [NIST standard control runs](https://www.itl.nist.gov/div898/handbook/pri/section2/pri22.htm) สนับสนุนการเทียบบริบท/recipe; [Zhang/NIST autocorrelated process data](https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data) อธิบายว่าตัวอย่างตามเวลาไม่จำเป็นต้องindependent. Sourcesเหล่านี้ไม่ได้กำหนด20min/lookbackที่เหมาะกับHT9046MX

ยังไม่มีrecipe/load/water/serviceและhealthy-startlabelsที่ครบ จึงยังfit/validatehealthy startup envelopeหรือsettling timeoutไม่ได้. Full-seriesMySQLActive integration/Serverlatency/restartไม่ได้ทดสอบจากงานนี้. ไม่ได้เชื่อมTargetServer เปลี่ยนActiveProfile/model/threshold/alerts หรือปรับdata contractของtags

## Change log

- 2026-10-01 — วิเคราะห์ZIPรายวินาทีสามเครื่อง, source QA, numerical causal-shadow sensitivityและpresentation Notebook; Staticexcluded. เสนอphase/stable-reference-aware calibration ไม่ได้implementหรือactivatepolicyใหม่
