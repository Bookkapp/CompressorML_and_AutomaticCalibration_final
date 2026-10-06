# กรอบการวิเคราะห์ข้อมูลและพัฒนาแบบจำลองเพื่อการติดตามสภาพระบบทำความเย็นแบบ Cascade ของเครื่อง HT-9046MX

**5 Oct — Fleet Reference / selective transfer delivered:** The local implementation is a **bounded robust-moment Empirical-Bayes-style covariance-shape approximation**, with frozen Local absolute levels/scales and target-specific disjoint empirical thresholds. It is not full hierarchical posterior inference or exact iid NIW; dependence and unverified within-SV multimodality remain. On six assets/555committed files,76/101 sparse scenarios pass correlation-sharing eligibility versus0/101 mean+covariance sharing; these are compatibility counts, not accuracy. Fit1/3/7/14day arms also have7target calibration days, so no one-day cold-start claim. Dhada2020([DOI](https://doi.org/10.1017/dce.2020.19)), Bull2022([preprint](https://arxiv.org/abs/2204.12404)) and Ghauch2025([DOI](https://doi.org/10.1017/dce.2025.3)) motivate similar-asset/hierarchical/selective sharing; none validates HT9046MX healthy labels or our approximation. Current conditional Context runtime and frozen Local evidence remain primary, ARX optional offline challenger. Executed `notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb` and `deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md` record provenance/splits/limitations/future acceptance. Final research steady-screen uses five-point physical max–min over contiguous supported minutes (limit0.35); adjacent-change-only results are superseded.

## วิทยานิพนธ์เชิงประยุกต์สำหรับการพัฒนา Predictive Maintenance, Machine Learning และ Auto-bootstrap

**Empirical local update — 2026-10-01:** Notebook08L implements a local-reference-aware 1m Self/ARX/DPCA/Isolation Forest comparison (nine machines audited, five shared-fit machines, five adapted LOMO folds). The evidence supports keeping frozen local Self primary rather than replacing it with predictive residuals: MX057/M1 known-case coverage99.82% Self versus8.27% ARX. MX080 ML abstains for insufficient declared threshold days; no transfer/fault accuracy is proved there. Reference stability/phase qualification remains the priority; event-response and LSTM remain research, not newly fitted/activated models. Full empirical methods, results and limitations: `deployment/LOCAL_PROFILE_MODEL_SELECTION_20261001.md`.

**Current-method clarification — 2026-10-01:** Earlier candidate/ensemble tables below are historical research options, not the current selected production vote. The selected detector is qualified one-minute robust-z + three adjacent qualified-minute persistence; EWMA/CUSUM remain shadow. New control-state/EEV/multimode research supports retaining manual-event raw evidence, separate phase/reference qualification and event ARX/DPCA trials before LSTM replacement. Busy/SV and Active semantics are unchanged. Detailed equations, proposed parameters, primary-source access notes and evaluation limits: [control-event research](research/HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md).

**ฉบับ:** 1.1 — Deep Research & Production Readiness Revision
**วันที่:** 8 กันยายน 2026
**สถานะ:** Research-backed design พร้อม Phase 06 candidate implementation; ยังไม่ใช่รายงานยืนยันความแม่นยำของการวินิจฉัยความเสียหาย

---

## บทคัดย่อ


ข้อมูลที่นำมาศึกษาประกอบด้วยไฟล์ Parquet 369 ไฟล์ รวม 26,159,383 แถว จาก 19 เครื่อง ครอบคลุมช่วงวันที่ 4 สิงหาคมถึง 1 กันยายน 2026 เมื่อนำข้อมูลมาจัดให้อยู่ในระดับหนึ่งนาทีและคัดเฉพาะช่วงที่เหมาะสมต่อการสร้าง baseline เหลือข้อมูล 2,667,008 แถว และสร้าง candidate profile ระดับเครื่อง–โมดูลได้ 87 profile การเปรียบเทียบความแปรปรวนพบว่า ความแตกต่างระหว่างเครื่องสูงกว่าความแปรปรวนภายใน profile เดียวกันเป็นค่ามัธยฐานประมาณ 4.64 เท่า ผลดังกล่าวยืนยันว่า threshold เดียวสำหรับทุกเครื่องไม่เหมาะสม

แม้ข้อมูลดิบเกือบทั้งหมดมี cadence ใกล้หนึ่งวินาที แต่เมื่อคัด valve event ที่มีหน้าต่างข้อมูลครบและไม่ปะปนกับ control sequence อื่น เหลือ clean event เพียง 243 เหตุการณ์ ในจำนวนนี้เป็น closing event 241 เหตุการณ์ opening event 2 เหตุการณ์ และทั้งหมดอยู่ในสถานะ SV Off ดังนั้นจำนวนแถวดิบที่สูงไม่ได้หมายความว่ามีตัวอย่างอิสระและครอบคลุมเพียงพอสำหรับ deep sequence model

จากการทบทวนงานวิจัยและผลทดลองภายใน งานนี้เสนอระบบแบบผสมที่มีความรู้ทางกายภาพและสถานะการควบคุมเป็นกรอบนำ ประกอบด้วย data/state gate, robust calibration รายเครื่อง–โมดูล–SV, relative features, dynamic-response features, one-sided CUSUM, ARX residual model, Isolation Forest และ evidence-fusion layer สำหรับสร้างคำเตือนที่อธิบายได้ ส่วน TCN และ LSTM encoder-decoder ควรเป็น challenger model เมื่อมี coverage ของ sequence และผลตรวจจริงมากพอ ขณะที่ Extra Trees, CatBoost หรือ gradient-boosted trees เหมาะกับ probable-cause classification หลังจากมี technician-confirmed labels



**คำสำคัญ:** cascade refrigeration, predictive maintenance, anomaly detection, Isolation Forest, LSTM, TCN, ARX, CUSUM, Auto-bootstrap, refrigerant undercharge, concept drift

---

## 0. คำตอบจากการทบทวนงานวิจัยฉบับขยาย

### 0.1 Thesis เดิมมีงานวิจัยที่เกี่ยวข้องหรือไม่


ฉบับ 1.1 จึงเพิ่มหลักฐานและข้อกำหนดในห้ากลุ่ม:

1. งาน FDD และ field deployment ใน vapor-compression refrigeration
2. งาน benchmark ที่เตือนว่า deep anomaly detector อาจดูดีกว่าความจริงเพราะ dataset, point adjustment และ protocol
3. classical, streaming และ sequence-model challengers พร้อม parameter/search space
4. Auto-bootstrap, statistical block bootstrap, ensemble bootstrap และ AutoML ซึ่งเดิมมักถูกเรียกปนกัน
5. production ML: data validation, model test score, hidden technical debt, registry, shadow mode, rollback และ QA Loop

### 0.2 คำตอบเชิงการตัดสินใจ

| คำถาม | คำตอบสำหรับข้อมูลปัจจุบัน | ระดับหลักฐาน |
|---|---|---|
| ใช้ ML ได้หรือไม่ | ใช้ได้สำหรับ anomaly screening, baseline drift และจัดลำดับเหตุให้ช่างตรวจ | มีผลภายในและงานวิจัยรองรับวิธี |
| ใช้ทำนายว่า leak แน่นอนได้หรือไม่ | ยังไม่ได้ เพราะไม่มี technician-confirmed fault/no-fault labels และ operating context ยังไม่ครบ | ข้อจำกัดชัดเจน |
| Model หลักควรเป็นอะไร | state-aware robust profile + EWMA/CUSUM + ARX residual + Isolation Forest | เหมาะกับ tabular features, label scarcity และต้นทุน server |
| ข้อมูล 1 นาทีพอหรือไม่ | พอสำหรับ steady drift; ไม่พอสำหรับ valve-response morphology จึงต้องสกัด 1-second features ก่อน aggregate | ยืนยันจากผลภายใน |
| พร้อม Production หรือยัง | พร้อมพัฒนาเป็น shadow/advisory screening service; ยังไม่พร้อม autonomous diagnosis หรือ control | ต้องผ่าน gate เพิ่ม |

### 0.3 ความเชื่อมโยงจากงานวิจัยสู่การออกแบบจริง

```text
Refrigeration FDD
  → ต้องหาค่า fault-free ภายใต้ driving condition ที่เทียบกันได้
  → local state-conditioned profile + residual

Time-series anomaly research
  → row count ไม่ใช่ independent-event count และ metric อาจลำเอียง
  → event/cycle split + range/event metrics + no point adjustment

Domain-shift research
  → random K-fold ให้ภาพดีเกินจริงเมื่อย้ายเครื่อง
  → temporal outer test + LOMO + sparse-machine external test

Bootstrap/Phase-I research
  → baseline ที่ปน fault ทำให้ monitoring ระยะถัดไปเสีย
  → quarantine + block-bootstrap uncertainty + shadow approval

Production ML research
  → model เป็นเพียงส่วนเล็กของระบบและ data failure ทำลายผลได้
  → data/state gate + versioned artifacts + monitoring + rollback + QA Loop
```

ผลสังเคราะห์นี้ไม่เปลี่ยน physics หรือกติกาหน้างานใน `README_System.md`; สิ่งที่เปลี่ยนคือความเข้มของวิธีเลือก model, วิธีรายงานผล และ production gate

---

## 1. ที่มาและความสำคัญของปัญหา



งานวิจัยเกี่ยวกับ refrigerant leakage ในระบบอุตสาหกรรมยังชี้ว่า การตรวจจับที่ใช้ได้จริงมักสร้างค่าคาดหมายของสภาวะ fault-free แล้วพิจารณา residual ระหว่างค่าจริงกับค่าที่คาด งานปี 2024 พบว่า Extremely Randomized Trees ให้ผลดีที่สุดในกรณีศึกษาหนึ่ง แต่ตัวแปรเป้าหมายของงานนั้นคือระดับสารทำความเย็นใน receiver ซึ่งไม่มีอยู่ในชุดข้อมูล HT9046MX ปัจจุบัน ([Mtibaa et al., 2024](https://doi.org/10.1016/j.ijrefrig.2024.02.016)) งานนี้จึงรับหลักการ residual-based monitoring มาใช้ แต่ไม่คัดลอกตัวแปรหรือผลความแม่นยำจากระบบที่มี instrumentation ต่างกัน

### 1.1 วัตถุประสงค์

1. กำหนดวิธีสร้างค่าปกติที่เหมาะสมกับเครื่อง โมดูลและสถานะเฉพาะ
2. ศึกษาความสัมพันธ์เชิงเวลาในเส้นทาง `Valve → pressure → temperature response`
3. เปรียบเทียบความเหมาะสมของ statistical monitoring, classical ML และ deep sequence models
4. กำหนด validation, deployment และ human-review process ที่ตรวจสอบย้อนหลังได้

### 1.2 คำถามวิจัย

- ค่าปกติสามารถใช้ร่วมกันทั้ง fleet ได้หรือจำเป็นต้อง calibrate รายเครื่องและโมดูล?
- ในภาวะที่ไม่มี confirmed fault labels โมเดลชนิดใดให้สมดุลระหว่างความไว ความเสถียร การอธิบาย และต้นทุน server?
- ต้องมีหลักฐานและ validation แบบใดจึงจะเปลี่ยนจาก anomaly screening ไปสู่ probable-cause diagnosis ได้?

---

## 2. ขอบเขตของข้อสรุป

ผลของระบบนี้มีสถานะเป็น condition-monitoring evidence ไม่ใช่คำวินิจฉัยทางช่าง คำว่า anomaly หมายถึง “พฤติกรรมที่ไม่สอดคล้องกับ reference profile ภายใต้เงื่อนไขที่กำหนด” ไม่ได้หมายความว่าอุปกรณ์เสียเสมอไป

ในทำนองเดียวกัน กติกาหน้างานล่าสุดกำหนด `Hp_2nd = 180–230 psi` เป็นช่วงอ้างอิงของ charge ปกติสำหรับข้อมูลที่ผ่าน qualification และเปรียบเทียบใน machine–module–SV–state เดียวกันเท่านั้น เมื่อ `Hp_2nd < 180 psi` จึงเพิ่ม one-sided undercharge/leak screening evidence; เมื่อ `Hp_2nd >= 180 psi` feature นี้ไม่เพิ่มคะแนน undercharge. ค่า `Hp_2nd > 230 psi` ต้องถูกพิจารณาเป็น high-side/local-deviation evidence แยกต่างหาก ไม่ใช่ leak score และไม่ยืนยันสาเหตุจากระบบน้ำ


สำหรับ water-cooled condenser เอกสารผู้ผลิตระบุว่า water flow ต่ำ, water inlet temperature สูง, fouling/blockage, pump/valve failure และ refrigerant overcharge เป็นคำอธิบายที่เป็นไปได้ของ condensing pressure สูง ขณะที่ water-regulating valve มักเปิดเพิ่มตาม condensing pressure เพื่อรักษาสมดุล ([Danfoss Ref Tools](https://reftools.danfoss.com/tools/cooling/troubleshooter/system-areas/high-pressure/system/condensing-pressure-too-high/water-cooled-condensers/), [Danfoss Fitters' Notes](https://assets.danfoss.com/documents/latest/50971/AX274333437010en-000101.pdf)). ดังนั้น direction ของเหตุผลต้องแยก “pressure สูงทำให้ controller เพิ่มน้ำ” ออกจาก “ปัญหาระบบน้ำทำให้ pressure สูง” และต้องมี telemetry ที่ตรงเวลาก่อนตัดสิน

---

## 3. ชุดข้อมูลและความพร้อมต่อการสร้างแบบจำลอง

### 3.1 ภาพรวมข้อมูล

| รายการ | ผลที่ตรวจสอบได้ |
|---|---:|
| จำนวนเครื่อง | 19 |
| จำนวนไฟล์ Parquet | 369 |
| จำนวนแถวดิบ | 26,159,383 |
| ช่วงข้อมูล | 2026-08-04 ถึง 2026-09-01 |
| จำนวนแถว machine–module ระดับหนึ่งนาที | 3,548,928 |
| แถวที่ผ่าน baseline eligibility | 2,667,008 |
| Candidate machine–module profile | 87 |
| Clean one-second valve event | 243 |


### 3.2 ความไม่สมดุลของ coverage

เครื่องกลุ่ม development มีข้อมูลประมาณ 17–29 วันเป็นส่วนใหญ่ ขณะที่เครื่อง 056, 063, 071, 115, 118, 119 และ 124 มีข้อมูลเพียงประมาณ 3–9 วัน จึงถูกแยกเป็น sparse external test ตามข้อตกลงของโครงการ การใช้เครื่องเหล่านี้เป็น test มีประโยชน์ต่อการวัด cold-start transfer แต่ sample size ที่เล็กทำให้อัตรา alert ต่อเครื่องผันผวนสูง ค่าที่ได้จึงต้องรายงานพร้อมจำนวนตัวอย่างเสมอ

### 3.3 หนึ่งวินาทีไม่ได้หมายความว่าครอบคลุมทุก event

Raw cadence ใกล้หนึ่งวินาทีคิดเป็น 98.55% แต่จาก candidate valve event 2,971 เหตุการณ์ มีเพียง 243 เหตุการณ์ที่ผ่านข้อกำหนดเรื่องหน้าต่างครบ ไม่อยู่ตรงขอบไฟล์ และไม่ปะปนกับ sequence ที่ต้องตัดออก ใน clean set มี closing 241 เหตุการณ์ opening 2 เหตุการณ์ และพบเฉพาะ SV Off


### 3.4 ตัวแปรบริบทที่ยังขาด

ชุดข้อมูลยังไม่มี recipe/mode/phase, temperature setpoint, actual controlled temperature, DUT load, facility-water condition และ service timeline ที่ครบถ้วน การขาดตัวแปรเหล่านี้ทำให้ความสัมพันธ์ทางสถิติอาจเกิดจาก confounding เช่น เครื่องหนึ่งมี `Hp_2nd` ต่ำกว่าอีกเครื่องเพราะทำงานคนละ phase ไม่ใช่เพราะสุขภาพต่างกัน งาน LSTM encoder-decoder เองก็ระบุว่าปัจจัยภายนอกหรือ manual control ที่ไม่ได้บันทึกทำให้ sensor series คาดเดายากและลดความน่าเชื่อถือของ prediction-error detector ([Malhotra et al., 2016](https://arxiv.org/abs/1607.00148))

---

## 4. กรอบ Data Analysis ที่เสนอ

### 4.1 Data and state qualification


1. หน่วย pressure และ tag mapping ถูกต้อง
2. timestamp เรียงลำดับและ sampling gap อยู่ในเกณฑ์
3. machine และ module ถูกระบุครบ
4. `Busy`, `Status` และ `SV` ไม่เปลี่ยนกลาง window เว้นแต่ window นั้นเป็น event ที่ตั้งใจศึกษา
5. ไม่เป็น Emergency Down, MValveHome, negative valve command, pump-down หรือช่วง start/stop ที่ยังไม่ settle
6. ไม่มี missingness ที่ทำให้ slope, lag หรือ response calculation ผิดความหมาย
7. หากไม่ทราบ recipe/phase ต้องบันทึกเป็น unknown ไม่เดาแทน

งาน FDD ใน vapor-compression system จำนวนมากอาศัย quasi-steady operation เพราะ transient และ driving conditions สามารถเลียนแบบ fault signature ได้ ([Li & Braun, 2007](https://doi.org/10.1016/j.ijrefrig.2006.07.024)) สำหรับ HT9046MX จึงควรมี analysis path สองชุดที่ไม่ปะปนกัน คือ steady/minute profile และ transient/event-response profile

### 4.2 Baseline ที่มีเงื่อนไข

ให้กำหนด profile key เป็น:

```text
machine × module × recipe/mode/phase × Busy × Status × SV × facility-water band × service epoch
```


ค่ากลางและ dispersion ควรใช้ median และ MAD:

\[
m=\operatorname{median}(x_1,\ldots,x_n)
\]

\[
MAD=\operatorname{median}(|x_i-m|)
\]

\[
z_{robust}=\frac{0.6745(x-m)}{MAD+\epsilon}
\]

การใช้ robust scale ลดอิทธิพลจาก outlier และ contaminated window ได้ดีกว่า mean/std ในระยะเริ่มต้น แนวทาง robust median/MAD ยังถูกใช้ในงาน anomaly detection ที่ต้องรับมือกับ spike และ distribution ที่ไม่สะอาด ([Hochenbaum, Vallis & Kejariwal, 2017](https://arxiv.org/abs/1704.07706))

### 4.3 Relative features

Raw pressure มีความหมายต่อช่าง แต่ model fleet ควรรับทั้ง raw context และ relative deviation โดย relative feature หลักประกอบด้วย:

\[
\Delta P_1=Hp_{1st}-Lp_{1st}, \quad
\Delta P_2=Hp_{2nd}-Lp_{2nd}
\]

\[
r_{HP2}=Hp_{2nd}-m_{HP2,profile}
\]

\[
d_{HP2-low}=\max(0, 200-Hp_{2nd})
\]


### 4.4 Trend and persistence

Slope ระยะสั้นคำนวณจาก robust linear fit ภายใน window ส่วน degradation ระยะยาวควรคำนวณจาก daily/cycle median ภายใต้ profile เดียวกัน ไม่ใช่ raw sample ที่มี recipe mix ต่างกัน

สำหรับ drift ลง ใช้ one-sided CUSUM บน standardized residual:

\[
C_t^-=\max(0,C_{t-1}^- - z_t-k)
\]

และแจ้ง drift candidate เมื่อ $C_t^- > h$ NIST ระบุว่า CUSUM มีประสิทธิภาพกว่าวิธี Shewhart ในการจับ mean shift ขนาดเล็ก โดยค่าตั้งต้นที่มักใช้คือ $k$ ประมาณครึ่งหนึ่งของ shift ที่ต้องการตรวจ และ $h$ ประมาณ 4–5 หน่วยมาตรฐาน แต่ค่าจริงต้องออกแบบจาก false-alarm budget ของระบบ ([NIST CUSUM Guidance](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm))

### 4.5 Dynamic valve response

Event window กำหนด $t=0$ ที่ valve command เปลี่ยน แล้วเปรียบเทียบ pressure และ temperature ก่อน–หลัง event ในช่วง 5, 15, 30, 60 และ 120 วินาที

\[
\tau^*=\arg\max_{\tau \in \mathcal{T}}
|\operatorname{corr}(\Delta Valve_t,\Delta y_{t+\tau})|
\]

โดย $y$ อาจเป็น `Lp_2nd`, `Hp_2nd`, `TempHigh` หรือ `TempLow` ค่า lag ที่พบเป็น temporal association ไม่ใช่เวลาตอบสนองเชิงสาเหตุที่พิสูจน์แล้ว เพราะ controller อาจปรับหลายคำสั่งพร้อมกัน

Feature response ที่ควรบันทึก ได้แก่:

- pre-event median และ post-event delta
- maximum/minimum excursion
- area under response curve
- response lag และ time-to-peak
- t50/t90 และ settling time
- response gain ต่อขนาด valve step
- oscillation/hunting count
- missing fraction และ observed seconds

### 4.6 ARX residual model

ARX ช่วยตอบคำถามว่า เมื่อทราบ pressure ก่อนหน้าและ valve command แล้ว response ปัจจุบันต่างจากสิ่งที่ควรเกิดขึ้นเพียงใด:

\[
y_t=c+\sum_{i=1}^{p}a_i y_{t-i}
+\sum_{j=0}^{q}b_j u_{t-d-j}
+\gamma^T w_t+e_t
\]



### 4.7 Effective sample size และ profile-stability curve

จำนวน 26 ล้านแถวไม่ใช่ขนาดตัวอย่างอิสระ เพราะค่าที่ติดกันหนึ่งวินาทีมี autocorrelation สูง ให้ประมาณ effective sample size ของ statistic แบบคร่าว ๆ จาก

\[
n_{eff}\approx\frac{n}{1+2\sum_{k=1}^{K}\rho_k}
\]

โดยตัดผลรวมที่ lag ซึ่ง autocorrelation ลดลงหรือเปลี่ยนเครื่องหมาย สูตรนี้ไม่ใช้แทน block bootstrap แต่ช่วยอธิบายว่าทำไม 80,000 แถวจากวันเดียวอาจให้ข้อมูลอิสระน้อยกว่าหลายร้อย cycle จากหลายวัน


\[
Stability_d = \max_f
\frac{|\hat\theta_{f,d}-\hat\theta_{f,d-1}|}
{MAD_{f,d-1}+\epsilon}
\]

ค่า gate ต้องกำหนดจากความนิ่งที่จำเป็นต่อ alert budget ไม่ใช่ใช้ 7 หรือ 14 วันเป็นกฎสากล วันที่ขั้นต่ำยังมีประโยชน์เป็น guardrail เพื่อบังคับ calendar coverage แต่ไม่ยืนยันความนิ่งด้วยตัวมันเอง

### 4.8 EWMA, CUSUM และ offline change point

EWMA เหมาะกับ drift ค่อยเป็นค่อยไปและคำนวณได้ด้วย state เดียว:

\[
Z_t=\lambda x_t+(1-\lambda)Z_{t-1}
\]

NIST แนะนำค่าเริ่มต้นของ $\lambda$ ประมาณ 0.2–0.3 และกล่าวถึง 0.15 ว่าเป็นค่าที่นิยม แต่ค่าของ HT9046MX ต้อง calibrate จาก run length และ false-alert budget ของแต่ละ profile ไม่ใช่คัดลอกตัวเลขมาใช้ตรง ๆ ([NIST EWMA guidance](https://www.itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm))

บทบาทของเครื่องมือแต่ละชนิดควรแยกกัน:

| วิธี | ใช้เมื่อ | Output ที่เหมาะสม |
|---|---|---|
| robust z-score | deviation ณ window ปัจจุบัน | local deviation evidence |
| EWMA | shift ช้าและต่อเนื่อง | smoothed drift evidence |
| one-sided CUSUM | สนใจ drift ลงด้านเดียว เช่น qualified `Hp_2nd` residual | accumulated low-side evidence |
| Page-Hinkley/ADWIN | online score distribution เปลี่ยน | drift incident; ไม่แก้ profile เอง |
| PELT | วิเคราะห์ย้อนหลังหา service/change epoch | candidate breakpoint สำหรับเทียบ service log |

PELT หา changepoint หลายจุดโดย optimize cost + penalty และมีต้นทุนใกล้เชิงเส้นภายใต้เงื่อนไขของวิธี ([Killick, Fearnhead & Eckley, 2012](https://doi.org/10.1080/01621459.2012.737745)) แต่ changepoint ไม่บอกสาเหตุ จึงต้องเชื่อมกับ refill, sensor replacement, recipe mix และ facility condition ก่อนเปิด epoch ใหม่

### 4.9 ลำดับการวิเคราะห์ความสัมพันธ์เพื่อป้องกันความเข้าใจผิด

การวิเคราะห์ “ความสัมพันธ์” ควรไล่จากคำถามง่ายไปยากและหยุดเมื่อ context ไม่พอ:

1. **Raw descriptive:** scatter/distribution และ Spearman correlation เพื่อดูรูปแบบเบื้องต้น
2. **State-stratified:** แยก machine, module, SV, Busy, Status และ phase ที่มีข้อมูล
3. **Residualized:** หัก local baseline และตัวแปรร่วมที่สังเกตได้ แล้ววิเคราะห์ residual
4. **Event-aligned:** วาง $t=0$ ที่ valve change และรายงาน pre/post delta, lag, gain, t90
5. **Dynamic model:** ARX/state-space residual บน past-only windows

Correlation หลัง aggregate หนึ่งนาทีอาจสูงขึ้นจาก smoothing ทั้งที่ response timing หายไป จึงต้องรายงานทั้ง association retention และ lag-resolution loss การเห็นเส้นสองเส้นขยับพร้อมกันไม่เพียงพอที่จะสรุปว่า valve เป็นสาเหตุ เพราะ controller อาจตอบสนองต่อ load ที่ไม่ได้บันทึก

### 4.10 Matrix Profile สำหรับ cycle morphology

Matrix Profile เป็นวิธีค้นหา subsequence ที่คล้ายกันและ discord โดยไม่ต้อง train neural network งานต้นฉบับเสนอ efficient all-pairs similarity join และแสดงการใช้กับ motif/novelty discovery ([Yeh et al., 2016](https://doi.org/10.1109/ICDM.2016.0179)) วิธีนี้มีประโยชน์เป็น **forensic/offline challenger** เมื่อสามารถ segment cold pull-down หรือ valve-response cycle ที่มีความยาวใกล้กันได้


---

## 5. ผลวิเคราะห์ภายในและความหมายต่อการออกแบบ

### 5.1 Baseline ไม่เท่ากันเป็นโครงสร้างของข้อมูล ไม่ใช่ noise เล็กน้อย

ค่ามัธยฐานของอัตราส่วนความแปรปรวนระหว่างเครื่องต่อความแปรปรวนภายใน profile เท่ากับประมาณ 4.64 และค่าสูงสุด 24.0 แปลว่า machine identity และ module identity มีผลมากพอที่ global raw threshold จะสร้างทั้ง false positive และ false negative ได้


### 5.2 ผลของ model ระดับหนึ่งนาที

Shared Isolation Forest ที่ใช้ relative features 32 ตัวให้ temporal median alert rate 0.942% และ LOMO median alert rate 0.882% แต่ sparse external-test median alert rate สูงถึง 10.344% ความต่างนี้ชี้ว่า model transfer ไปยังเครื่องข้อมูลสั้นยังไม่นิ่ง และ profile cold-start มีบทบาทสำคัญ

งาน condition monitoring ภายใต้ domain shift พบเช่นกันว่า performance จาก random cross-validation สามารถลดลงมากเมื่อย้ายไปเครื่องหรือกลุ่มที่ไม่เคยเห็น และในหลาย dataset วิธี feature-based classical model ทน domain shift ได้ดีกว่า deep learning ([Goodarzi, Schütze & Schneider, 2025](https://doi.org/10.5194/jsss-14-119-2025)) ผลนี้สนับสนุนการใช้ LOMO เป็น release gate และสนับสนุนการเก็บ machine-specific calibration ไว้ข้าง shared detector

### 5.3 ผลของหนึ่งวินาทีและ hybrid features

การเปรียบเทียบ closing event ที่ join ได้ 240 เหตุการณ์ ใช้ train 160 และ temporal test 73 ได้ผลดังนี้:

| Model | จำนวน feature | พร้อมใช้หลัง event | Temporal alert rate |
|---|---:|---:|---:|
| Minute-only | 19 | 0 วินาที | 2.74% |
| Hybrid fast | 36 | 30 วินาที | 4.11% |
| Hybrid complete | 58 | 120 วินาที | 5.48% |

Hybrid complete มี feature 58 ตัวต่อ train event เพียง 160 ตัว หรือประมาณ 2.76 แถวต่อ feature และให้ alert rate 100% บน MX081 ซึ่งมี test เพียง 3 เหตุการณ์ ผลดังกล่าวไม่พิสูจน์ว่า 120-second feature แย่ แต่ชี้ว่าความซับซ้อนสูงเกิน evidence ในปัจจุบัน การลด feature, regularization และเพิ่ม event coverage มีความสำคัญกว่าการเพิ่ม architecture ลึกขึ้น

### 5.4 การตัดสินใจจากผลปัจจุบัน

- Minute-only เป็น operational baseline ที่เสถียรกว่า
- Hybrid fast 30 วินาทีควรเป็น challenger ที่มีโอกาสเพิ่ม sensitivity โดย latency ยังยอมรับได้
- Hybrid complete 120 วินาทีเหมาะกับ post-event analysis หรือ shadow experiment จนกว่าจะมีข้อมูลเพิ่ม
- Opening และ SV On profile ต้องตอบ `INSUFFICIENT_COVERAGE`
- ไม่มี model ใดรายงาน precision, recall หรือ accuracy ของ leak ได้ในขณะนี้

---

## 6. การเลือกแบบจำลอง

### 6.1 เหตุผลที่ไม่ใช้โมเดลเดียว

ความผิดปกติที่ต้องการตรวจมีหลายมาตราส่วน: sensor glitch เกิดในวินาที, valve response ใช้หลายสิบวินาที, baseline drift ใช้หลาย cycle หรือหลายวัน และ service/refill ทำให้ distribution เปลี่ยนแบบเป็น epoch โมเดลเดียวที่รับ raw sequence ทั้งหมดจะต้องเรียนรู้ทั้ง state machine, dynamics, fleet differences และ degradation พร้อมกัน ซึ่งไม่เหมาะกับ coverage ปัจจุบัน

ระบบจึงแบ่งหน้าที่:

```text
Rule/state layer      → ป้องกันการเปรียบเทียบผิดบริบท
Robust/SPC layer      → จับ deviation และ drift ที่อธิบายได้
Dynamic layer         → จับ response ที่ผิดจาก valve-pressure model
Multivariate ML layer → จับรูปแบบร่วมที่ rule เดี่ยวมองไม่เห็น
Fusion/persistence    → ลดการเตือนจาก transient เดี่ยว
Human verification   → ยืนยันสาเหตุจริงและสร้าง label
```

### 6.2 Isolation Forest: production baseline ที่เหมาะในระยะนี้

Isolation Forest แยก anomaly ด้วยจำนวน split ที่ต้องใช้ในการ isolate จุดข้อมูล จึงไม่ต้องประมาณ density เต็มรูปแบบและรองรับ subsampling ด้วยต้นทุนหน่วยความจำต่ำ ([Liu, Ting & Zhou, 2008](https://doi.org/10.1109/ICDM.2008.17)) จุดแข็งของมันในโครงการนี้คือรองรับ tabular relative features, ไม่ต้องมี failure labels และรันบน server ได้ง่าย

ข้อจำกัดคือ Isolation Forest ไม่ทราบลำดับเวลาโดยตัวมันเอง ลำดับเวลาต้องถูกเข้ารหัสผ่าน slope, lag, response summary และ persistence policy อีกทั้ง anomaly score ไม่ได้บอกสาเหตุ จึงต้องรายงาน feature evidence แยก

Parameter search ที่เสนอ:

| Parameter | Candidate |
|---|---|
| `n_estimators` | 300, 500 |
| `max_samples` | `min(256, n)` และ 0.5–1.0 ของ clean calibration setเมื่อ set มีขนาดเล็ก |
| `max_features` | 0.5, 0.75, 1.0 |
| `bootstrap` | `False` เป็นค่าเริ่มต้น |
| `contamination` | `auto`; แยก threshold calibration ออกจาก model fit |
| threshold | calibration quantile 0.99/0.995 หรือ conformal p-value |

ควรเลือก parameter จาก median false-alert rate, LOMO dispersion, seed-rank correlation และ alert-set Jaccard ไม่ใช่จากจำนวน alert ที่ดูเหมาะด้วยสายตา

### 6.3 One-Class SVM และ LOF: benchmark รอง


LOF เหมาะกับ local-density anomaly แต่ online novelty mode มีข้อจำกัดในการใช้ score กับ training data และค่า `n_neighbors` ต้องสัมพันธ์กับขนาด cluster ในแต่ละ state เมื่อ profile บางกลุ่มมีตัวอย่างน้อยและ density ต่างกันมาก การตั้งค่าจะไม่เสถียร จึงควรใช้เพื่อเทียบผล ไม่ใช่เป็น detector หลัก

### 6.5 Extra Trees, Random Forest, CatBoost และ Gradient Boosting

โมเดลกลุ่มต้นไม้เหมาะกับ tabular feature ที่มี nonlinear interaction และ feature scale ต่างกัน งานวิเคราะห์ refrigerant-charge fault ใช้ Random-Forest recursive feature elimination ก่อนเปรียบเทียบ SVM, decision tree, Random Forest, weighted kNN และ AdaBoost ([Li et al., 2020](https://doi.org/10.1016/j.ijrefrig.2019.10.026)) ส่วนงานข้อมูล refrigeration ภาคสนามปี 2024 พบว่า Extra Trees เป็น regression model ที่ดีที่สุดในโจทย์ทำนาย receiver liquid level ภายใต้สภาวะ fault-free ([Mtibaa et al., 2024](https://doi.org/10.1016/j.ijrefrig.2024.02.016))

สำหรับ HT9046MX โมเดลกลุ่มนี้มีสองบทบาท:

1. **Fault-free expectation regression** — ทำนาย expected `Hp_2nd`, `Lp_2nd` หรือ response feature จาก state และ context แล้วใช้ residual เป็นสัญญาณ
2. **Probable-cause classification** — ใช้เมื่อมี confirmed labels เพื่อแยก undercharge, EEV/control, compressor, sensor, common cause และ no-fault



Parameter starting range สำหรับ supervised tree challenger:

| Model | Parameter ที่ควรทดลอง |
|---|---|
| Extra Trees | 300–800 trees, `min_samples_leaf` 5–30, `max_features` 0.5–1.0, class/sample weights |
| CatBoost | depth 4–8, learning rate 0.02–0.1, 300–1500 iterations, early stopping, categorical state fields |
| HistGradientBoosting | `max_leaf_nodes` 7–31, `min_samples_leaf` 20–100, learning rate 0.03–0.1, class weights |

การเลือกค่าต้องทำภายใน temporal/group split เท่านั้น และต้องปรับ threshold ตามค่าเสียหายของ false alarm กับ missed detection ไม่ใช้ threshold 0.5 โดยอัตโนมัติ

### 6.6 LSTM encoder-decoder

LSTM encoder-decoder ฝึกจาก normal sequence แล้วใช้ reconstruction error เป็น anomaly score จึงเหมาะในเชิงหลักการกับข้อมูลหลาย sensor ที่ไม่มี anomaly labels งานต้นฉบับแสดงการใช้ sequence length ตั้งแต่ 30 ถึง 500 และชี้ว่ารูปแบบ reconstruction มีประโยชน์เมื่อ series คาดเดาได้ยาก ([Malhotra et al., 2016](https://arxiv.org/abs/1607.00148))


LSTM-AE challenger ที่เหมาะสมเมื่อ data gate ผ่าน:

```text
Input              [batch, 60 or 120 seconds, 12–25 features]
Encoder            1–2 LSTM layers, hidden 32/64
Latent             8/16/32
Decoder            symmetric LSTM
Loss               Huber or masked MAE
Dropout            0.1–0.3
Optimizer          Adam, learning rate 1e-4 to 1e-3
Early stopping     patience 10–20 epochs on future validation block
Threshold          blocked calibration quantile/conformal score
```


### 6.7 Temporal Convolutional Autoencoder

TCN ใช้ causal/dilated convolution และ residual connection เพื่อครอบคลุม receptive field ตามเวลาที่ต้องการ งานเปรียบเทียบ sequence model พบว่า generic TCN เป็นจุดเริ่มต้นที่มีเหตุผลเทียบกับ recurrent network และเน้นว่าความยาว receptive field ต้องครอบคลุม context ของโจทย์ ([Bai, Kolter & Koltun, 2018](https://arxiv.org/abs/1803.01271))

สำหรับหน้าต่าง 120 วินาที สามารถเริ่มด้วย kernel size 3 และ dilation 1, 2, 4, 8, 16, 32 พร้อม channel 16–32 และ residual blocks ขนาดเล็ก แล้วตรวจว่ารับข้อมูลย้อนหลังครบช่วงที่ต้องการหรือไม่ TCN สามารถคำนวณหลาย timestep แบบขนาน จึงมีโอกาสเหมาะกับ server มากกว่า LSTM แต่ต้องพิสูจน์จาก benchmark บนเครื่องจริง ไม่ใช่อาศัยผลจาก dataset อื่น


### 6.8 Transformer-based anomaly models


Anomaly Transformer ใช้ association discrepancy เป็น anomaly criterion ([Xu et al., 2022](https://openreview.net/pdf?id=LzQQ89U1qm_)) ส่วน TranAD ใช้ transformer, self-conditioning และ adversarial training ใน multivariate time series ([Tuli et al., 2022](https://vldb.org/pvldb/vol15/p1201-tuli.pdf)) งานเหล่านี้พิสูจน์ว่า architecture มีศักยภาพบน benchmark ของตน แต่ไม่ได้แก้ปัญหา state coverage, missing operating context หรือ label truth ของ HT9046MX

นอกจากนี้ reconstruction model อาจเกิด over-generalization คือ reconstruct anomaly ได้ดีจนแยกไม่ออก งาน MEMTO ระบุปัญหานี้โดยตรงและเพิ่ม memory module เพื่อจำกัด representation ([Song et al., 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/b4c898eb1fb556b8d871fbe9ead92256-Abstract.html)) การเพิ่ม model ซับซ้อนเพื่อแก้ข้อจำกัดของ model ซับซ้อนอีกชั้นจึงต้องมี evidence gain ที่มากพอชดเชยต้นทุนและความเสี่ยง

### 6.9 ECOD, COPOD และ Robust Random Cut Forest

ECOD ประมาณ tail probability ของแต่ละ feature ผ่าน empirical CDF และรวมเป็น outlier score จุดเด่นคือแทบไม่ต้อง tune parameter และแสดงได้ว่า feature ใดอยู่ใน tail ([Li et al., 2022](https://arxiv.org/abs/2201.00382)) ส่วน COPOD ใช้ empirical copula เพื่อจับ tail dependence โดยไม่มี training loop ที่หนัก ([Li et al., 2020](https://ieeexplore.ieee.org/document/9338429)) ทั้งสองวิธีเหมาะเป็น low-complexity benchmark บน **relative feature table** ไม่ใช่ raw pressure ข้าม state

Robust Random Cut Forest (RRCF) ถูกออกแบบให้ปรับปรุง forest บน dynamic stream และวัดผลกระทบของจุดใหม่ต่อโครงสร้างข้อมูล งานต้นฉบับยังกล่าวถึง outlier masking จาก duplicate/near-duplicate records ([Guha et al., 2016](https://proceedings.mlr.press/v48/guha16.html)) RRCF จึงเป็น online challenger ที่น่าสนใจหากต้องลดรอบ batch retraining แต่ต้องตรึง state partition และป้องกัน fault ที่ค่อย ๆ เกิดถูกเรียนเป็น normal เช่นเดียวกับ Auto-bootstrap

ในข้อมูลปัจจุบันให้จัดลำดับดังนี้:

```text
ECOD/COPOD → transparent parameter-light benchmark
Isolation Forest → operational batch/shallow baseline
RRCF → streaming challenger ใน shadow mode
Matrix Profile → offline cycle/subsequence forensic
```

### 6.10 งาน benchmark สอนอะไรเกี่ยวกับการเลือก model


งาน TSB-AD ปี 2024 เปรียบเทียบ 40 algorithms บนชุดข้อมูลที่ curate ใหม่และพบว่า model ที่เรียบง่ายหรือ statistical methods มักแข่งขันหรือดีกว่า neural architecture ในหลายกรณี ([Liu & Paparrizos, 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/c3f3c690b7a99fba16d0efd35cb83b2c-Abstract-Datasets_and_Benchmarks_Track.html)) สิ่งที่นำมาใช้กับ HT9046MX ไม่ใช่อันดับชนะของ model จาก dataset อื่น แต่เป็น **กติกาให้ shallow baseline ต้องอยู่ในการแข่งขันเสมอ** และ deep model ต้องชนะภายใต้ protocol เดียวกัน

### 6.11 Model decision matrix สำหรับข้อมูล HT9046MX

| Model/Method | สิ่งที่เรียนรู้ | Data requirement | จุดแข็งกับข้อมูลนี้ | ความเสี่ยงหลัก | สถานะ |
|---|---|---|---|---|---|
| robust median/MAD | local location/scale | qualified windows ต่อ profile | อธิบายง่าย ทน outlier | state contamination | Production core candidate |
| EWMA/CUSUM | persistent mean shift | time-ordered residual | จับ drift เล็ก ต้นทุนต่ำ | parameter ผูก alert budget | Production core candidate |
| ARX/Ridge residual | expected dynamic response | clean input-output windows | ผูก Valve กับ pressure lag | omitted load/controller action | P0 challenger/core candidate |
| Isolation Forest | multivariate isolation | tabular relative features | ไม่มี label, bundle เล็ก | ไม่เข้าใจเวลา/สาเหตุ | Current shallow baseline |
| ECOD/COPOD | marginal/dependent tails | tabular relative features | parameter น้อย โปร่งใส | correlation/state nonlinear บางแบบ | P0 benchmark |
| PCA T²/SPE | linear covariance/subspace | scaled clean profile | visualize covariance drift | nonlinear response | P0 benchmark |
| OCSVM/LOF | boundary/local density | clean scaled normal set | จับ local structure | tune ยากและ scale sensitive | P1 benchmark |
| RRCF | dynamic stream externality | ordered relative features | online update ได้ | fault adaptation/contamination | P1 shadow challenger |
| Extra Trees/CatBoost | nonlinear regression/classification | fault-free target หรือ confirmed labels | tabular interaction + explainability | weak-label leakage | P1 หลังมี target/labels |
| TCN-AE | sequence morphology | balanced normal sequences | causal convolution/parallel inference | event coverage ต่ำ | P2 challenger |
| LSTM-AE | recurrent normal sequence | balanced normal sequences | flexible temporal memory | slower, overlapping-window leakage | P2 challenger |
| Transformer family | long-range/spatial association | large balanced sequence corpus | rich interactions | complexity/benchmark fragility | P3 research only |

### 6.12 Parameter catalogue และขอบเขตการค้นหา

ตารางต่อไปนี้เป็น **starting search space** ไม่ใช่ค่าที่อนุมัติ Production:

| Method | Parameter/search space เริ่มต้น | วิธีเลือก |
|---|---|---|
| robust profile | window 5/15/30/60 min; minimum 200/500/1,000 eligible windows; MAD floor จาก sensor resolution | profile-stability + false-alert budget |
| EWMA | $\lambda$ = 0.05, 0.10, 0.15, 0.20, 0.30; control width 2.5–4.0 | temporal run-length simulation |
| CUSUM | target shift $\delta$ = 0.5, 1.0, 1.5 robust sigma; $k=\delta/2$; $h$ = 3–8 | smallest false-alert budget that retains injected/known-event sensitivity |
| ARX/Ridge minute | $p,q$ = 1–10; delay $d$ = 0–10; `alpha` = $10^{-4}$–$10^3$ log scale | blocked inner temporal validation |
| ARX/Ridge 1-second | $p,q$ = 1–30; $d$ = 0–30 s; 30/60/120-s horizon | grouped event validation |
| Isolation Forest | 300–800 trees; `max_samples` 256/512/1024/0.5/1.0; `max_features` 0.5/0.75/1.0; `bootstrap=False` first | multi-seed inner validation; threshold แยก |
| ECOD/COPOD | algorithm แทบ parameter-free; tune เฉพาะ tail aggregation/operating threshold หาก implementation เปิดให้ใช้ | stability + explanation + alert budget |
| PCA/SPE | variance retained 0.80/0.90/0.95/0.99; robust scaling on/off | future-block residual stability |
| One-Class SVM | `nu` 0.001–0.10 log; `gamma` scale/auto/$10^{-4}$–$10^1$ | จำกัด profile ที่สะอาดและมี sample พอ |
| LOF | neighbors 20/35/50/100; metric Euclidean/Manhattan; novelty mode | local-density stability across machine |
| RRCF | 40–100 trees; tree size 256–2,048; shingle 1/5/15; decay/update policy | streaming shadow replay |
| Extra Trees | 300–800 trees; leaf 5–30; features 0.5–1.0; sample/class weights | nested temporal/group validation |
| CatBoost | depth 4–8; learning rate 0.02–0.10; 300–1,500 iterations; early stopping | grouped future validation; calibration after fit |
| TCN-AE | sequence 60/120 s; kernel 3/5; dilation to cover horizon; channels 16/32/64; dropout 0.1–0.3 | Hyperband/early stop inside train only |
| LSTM-AE | sequence 60/120 s; hidden 32/64; latent 8/16/32; 1–2 layers; dropout 0.1–0.3 | same split/budget as TCN |
| threshold | q = 0.99/0.995/0.999; persistence 2/3/5 windows หรือ 2/3 cycles | operations cost and realized alerts/machine-day |


---

## 7. สถาปัตยกรรมแบบจำลองที่แนะนำ

### 7.1 โครงสร้างคะแนน

```text
Raw data
  ↓
Schema/unit/time validation
  ↓
Operating-state segmentation
  ↓
Local profile normalization
  ├─ robust deviation score
  ├─ one-sided Hp2-low score
  ├─ CUSUM/drift score
  ├─ ARX/event residual score
  └─ Isolation Forest score
          ↓
Calibrated rank/p-value per profile
          ↓
Evidence fusion + persistence
          ↓
Watch / Investigate / Review required
          ↓
Technician feedback and label store
```

คะแนนจากแต่ละ detector ควรถูกแปลงเป็น percentile rank หรือ calibrated p-value ภายใน profile ก่อนรวมกัน เพื่อไม่ให้ scale ของ detector ตัวใดครองผลรวมโดยไม่ได้ตั้งใจ

ตัวอย่าง fusion score:

\[
S_t=w_1q_{robust,t}+w_2q_{IF,t}+w_3q_{dynamic,t}+w_4q_{drift,t}
\]


### 7.2 Undercharge/leak screening logic

```text
Gate A: comparable machine/module/SV/state?
  No  → no diagnostic score
  Yes ↓
Hp_2nd < 180 psi?
  No  → no undercharge contribution from Hp_2nd
  Yes ↓
Persistent below-profile residual?
  No  → transient/watch only
  Yes ↓
Lp_2nd lower + Valve demand higher + cooling performance worse?
  Partial → investigate
  Strong  → R23 undercharge/leak suspect
          → maintenance verification required
```


CP1 และ common-cause evidence ต้องถูกตรวจควบคู่ หากหลายโมดูลเปลี่ยนพร้อมกันหรือ `Hp_1st` เปลี่ยนในทิศทางคล้ายกัน ควรเพิ่มคะแนน common-cause และลดความมั่นใจของ local leak explanation

### 7.3 Explainability

ทุก alert ต้องแสดงหลักฐานที่ช่างตรวจย้อนกลับได้ ได้แก่ raw values, local baseline, residual, duration, state และ top contributing features เมื่อใช้ tree-based supervised model สามารถใช้ SHAP เพื่อแจกแจง contribution ราย feature ซึ่งงานต้นฉบับวางกรอบให้ feature attribution เป็น additive explanation ([Lundberg & Lee, 2017](https://papers.nips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html))

SHAP ไม่ใช่หลักฐานเชิงสาเหตุ หาก `Hp_2nd` มี SHAP สูง ความหมายคือ model อาศัย feature นี้มากต่อ prediction นั้น ไม่ได้พิสูจน์ว่า pressure เป็นสาเหตุของปัญหา

---

## 8. Auto-bootstrap สำหรับเครื่องใหม่และ profile epoch ใหม่

### 8.1 ความหมายของ Auto-bootstrap

Auto-bootstrap คือกระบวนการรวบรวม clean reference data, สร้าง local calibration และประเมินความพร้อมโดยอัตโนมัติ ไม่ใช่ automatic retraining ที่เขียนทับ production model และไม่ใช่การถือว่าข้อมูลใหม่ทั้งหมดเป็น normal


### 8.2 State machine

```text
UNSEEN
  ↓
COLLECTING
  ↓
DATA_QUALITY_PASSED
  ↓
STATE_COVERAGE_CHECKED
  ↓
FLEET_SCREENING_PASSED
  ↓
CANDIDATE_PROFILE
  ↓
SHADOW_VALIDATION
  ↓
READY_FOR_APPROVAL
  ↓ human approval
ACTIVE_FROZEN
```

สถานะข้างเคียงที่ต้องมี:

```text
INSUFFICIENT_DATA
INSUFFICIENT_COVERAGE
REVIEW_REQUIRED
REJECTED
SUPERSEDED
ROLLBACK_ACTIVE
```

### 8.3 แยก readiness สองประเภท



จากข้อมูลปัจจุบัน opening/SV On ไม่ผ่าน readiness และต้องใช้ shared fallback เฉพาะ feature ที่พิสูจน์ portability แล้ว หรือ abstain พร้อมสถานะ `INSUFFICIENT_COVERAGE`

### 8.4 Contamination protection

Candidate window จะเข้า profile ได้เมื่อ:

- ผ่าน schema, timestamp, unit และ missingness checks
- ผ่าน state gate และไม่อยู่ใน excluded sequence
- ไม่มี confirmed service transition อยู่กลาง window
- robust residual ไม่อยู่ใน extreme tail ของ fleet/profile provisional reference
- ไม่มี combined evidence ของ persistent degradation


### 8.5 Candidate estimation and uncertainty


Profile ผ่าน stability gate เมื่อ:

- median/MAD ไม่เปลี่ยนเกิน tolerance ระหว่างครึ่งแรกและครึ่งหลัง
- confidence interval แคบพอต่อการใช้งาน
- state coverage ไม่กระจุกเพียงวันเดียว
- shadow alert rate อยู่ใน budget
- detector score distribution ไม่แสดง unresolved drift

### 8.6 Drift and rebootstrap

ADWIN ใช้ adaptive window เพื่อตรวจ distribution change โดยปรับขนาดหน้าต่างตามข้อมูลและมีกรอบควบคุม false positive/false negative ภายใต้สมมติฐานของวิธี ([Bifet & Gavaldà, 2007](https://doi.org/10.1137/1.9781611972771.42)) ในโครงการนี้ ADWIN หรือ Page-Hinkley ควร monitor calibrated residual/score ไม่ใช่ raw pressure ที่ปะปนหลาย state

เมื่อเกิด drift ระบบทำได้เพียง:

1. เปิด drift incident
2. ตรวจ data quality, state mix และ service log
3. สร้าง candidate epoch ใหม่หากมีเหตุผลรองรับ
4. รัน shadow validation
5. ขออนุมัติ


### 8.7 Service/refill epoch


```text
machine, module, SV, state key
profile version and service epoch
source start/end
eligible windows/events/days
feature schema version
median/MAD/quantiles and uncertainty
screened/quarantined/rejected counts with reasons
shadow results
approver, approval time and rollback profile
```

### 8.8 Threshold calibration

แทนการกำหนด `contamination=1%` แล้วถือว่า 1% ของข้อมูลต้องผิดปกติ ควรแยก model score ออกจาก operating threshold Split-conformal calibration สามารถแปลง nonconformity score เป็น threshold ที่มีการควบคุม false-positive rate ภายใต้สมมติฐานที่เหมาะสม งาน CADES เสนอ finite-sample FPR control สำหรับ event sequences ([Zhang et al., 2025](https://proceedings.mlr.press/v267/zhang25dn.html))


### 8.9 คำว่า Bootstrap ที่ต้องแยกจากกัน

| คำเรียก | ความหมาย | การประยุกต์ใช้ | ลักษณะเฉพาะ |
|---|---|---|---|
| Auto-bootstrap profile | lifecycle สร้าง local candidate profile ของเครื่อง/state ใหม่ | readiness, quarantine, uncertainty, shadow, approval | ไม่ใช่ algorithm มาตรฐานชื่อเดียว |
| Block/stationary bootstrap | resample block ที่ต่อเนื่องเพื่อประมาณ uncertainty | CI ของ median/MAD/lag/gain และ profile stability | ไม่สร้างเครื่องใหม่และไม่ retrain production เอง |
| Model bootstrap/bagging | สุ่มตัวอย่างเพื่อสร้าง ensemble หลาย model | Extra Trees/Random Forest หรือ sensitivity experiment | ไม่เท่ากับ Auto-bootstrap lifecycle |
| AutoML/HPO | ค้นหา model/parameter ตาม objective | Optuna/SMAC/Hyperband ภายใน train/validation | เป็นขั้นตอนค้นหาค่าพารามิเตอร์ |

Moving-block bootstrap ของ Künsch ใช้ block ความยาวคงที่ ขณะที่ stationary bootstrap ของ Politis และ Romano ใช้ block length แบบสุ่มเพื่อสร้าง pseudo-series ที่คงคุณสมบัติ stationarity บางส่วน ([Politis & Romano, 1994](https://doi.org/10.1080/01621459.1994.10476870)) ให้ทดลองทั้งสองแบบเมื่อ cycle boundary ไม่ชัด และทำ sensitivity ต่อ mean block length เช่น 1, 2 และ 3 machine-days หรือค่าที่สัมพันธ์กับ ACF decay


### 8.10 Candidate profile algorithm

สำหรับ profile $j$ และ feature $f$ ให้ Auto-bootstrap ทำตามลำดับ:

```text
eligible = schema/time/unit gate
         ∩ stable state
         ∩ allowed sequence
         ∩ service epoch

retain / quarantine / reject
→ estimate local median, MAD and quantiles from retain
→ block-bootstrap uncertainty by cycle/day
→ compare first-half vs second-half stability
→ compare local residual distribution with fleet reference
→ shadow score future-only windows
→ package evidence for approval
```

เมื่อ local sample ยังน้อย อนุญาตให้สร้าง **shrunken candidate** ที่ผสม local estimate กับ fleet/state prior แบบชั่วคราว:

\[
\tilde m_j=w_jm_j+(1-w_j)m_{fleet,state},\qquad
w_j=\frac{n_{eff,j}}{n_{eff,j}+\kappa}
\]



- ถือว่าข้อมูลหลังต่อเครื่องใหม่เป็น normal ทั้งหมด
- ปรับ baseline ตาม anomaly ที่ค่อย ๆ ลดต่อเนื่องจนสัญญาณหาย
- รวม pre-service และ post-service epoch
- ใช้ row count แทน calendar/cycle/state coverage
- สร้าง opening หรือ SV On profile จาก closing/SV Off
- ใช้ outer LOMO/sparse test เลือก parameter
- เปลี่ยน model, threshold หรือ `ACTIVE_FROZEN` profile โดยไม่มี version และผู้อนุมัติ
- ลบ candidate ที่ไม่ผ่านจนเหลือเฉพาะผลที่ดูดีโดยไม่รายงาน quarantine rate

---

## 9. การออกแบบ validation

### 9.1 Split hierarchy

```text
Level 1 — Past-only temporal split within development machines
Level 2 — Leave-one-machine-out
Level 3 — Sparse external machines
Level 4 — Service-epoch holdout
Level 5 — Shadow production replay
```

scikit-learn ระบุว่า classical KFold/ShuffleSplit ไม่เหมาะกับ time-series ที่มี autocorrelation และเสนอ `TimeSeriesSplit`; ส่วน `LeaveOneGroupOut` ใช้ hold out กลุ่มที่กำหนดได้ ([scikit-learn Cross-validation Guide](https://scikit-learn.org/stable/modules/cross_validation.html)) สำหรับโครงการนี้ group ต้องอยู่ระดับ machine และ event/cycle ไม่ใช่ row

Pipeline ทุกขั้นที่เรียนจากข้อมูล เช่น imputer, scaler, baseline, feature selection, PCA และ threshold ต้อง fit ภายใน training fold เท่านั้น หากคำนวณ median/MAD จากข้อมูลทั้งเดือนก่อนแบ่ง split ถือว่าเกิด leakage แม้ตัว model จะไม่เห็น test labels ก็ตาม

### 9.3 Metrics ก่อนมี labels

- alerts และ watches ต่อ machine-day
- สัดส่วนวันที่มี alert
- persistence distribution
- score drift และ calibration stability
- seed rank correlation
- alert-set Jaccard ระหว่าง seeds/models
- LOMO dispersion และ worst-machine rate
- agreement กับ explicit engineering evidence
- server latency, memory และ missing-data behavior

ตัวเลขเหล่านี้วัด operational stability และ transfer ไม่ใช่ sensitivity ต่อ fault

### 9.4 Metrics หลังมี labels

- event-level precision, recall, F1/Fβ
- PR-AUC เป็นตัวหลักสำหรับ rare faults
- false alerts per machine-day
- missed confirmed faults
- median/percentile lead time ก่อน maintenance
- cause confusion matrix
- calibration curve/Brier score สำหรับ probability model
- performance ตาม machine, module, SV, state และ fault severity

Precision–recall curve ให้ข้อมูลเหมาะกว่า ROC curve เมื่อ positive class มีน้อยมาก ([Saito & Rehmsmeier, 2015](https://doi.org/10.1371/journal.pone.0118432)) แต่ PR-AUC ต้องรายงานพร้อม prevalence ของ test set เพราะค่า precision เปลี่ยนตามสัดส่วนเหตุเสีย

### 9.6 Acceptance criteria

Release candidate ต้อง:

- ลด false alerts โดยไม่พลาด known confirmed events
- ไม่สร้าง worst-machine behavior ที่ยอมรับไม่ได้
- มี explanation ที่ช่างใช้ตรวจต่อได้
- รันได้ใน latency budget
- abstain เมื่อ state/data ไม่รองรับ
- rollback ได้และ reproduce score เดิมได้


Random search เป็น baseline ที่ต้องมี เพราะงานของ Bergstra และ Bengio แสดงว่ามีประสิทธิภาพกว่าการกวาด grid เมื่อ hyperparameter ที่มีผลจริงมีเพียงบางมิติ ([Bergstra & Bengio, 2012](https://www.jmlr.org/papers/v13/bergstra12a.html)) สำหรับ model ที่ train เป็น epoch เช่น TCN/LSTM ให้ใช้ Hyperband หรือ successive halving ตัด trial ที่อ่อนตั้งแต่ต้น ([Li et al., 2018](https://www.jmlr.org/beta/papers/v18/16-558.html)) Optuna เหมาะกับ search space แบบมีเงื่อนไขและ pruning ([Akiba et al., 2019](https://arxiv.org/abs/1907.10902)) ส่วน SMAC3 เป็นทางเลือก Bayesian optimization เมื่อจำนวน evaluation มีราคาแพง ([Lindauer et al., 2022](https://www.jmlr.org/papers/v23/21-0888.html))

โครง split ที่บังคับใช้:

```text
Outer test
  ├─ future temporal block
  ├─ leave-one-machine-out machine
  └─ sparse/new-machine external set

Inner development only
  ├─ train: fit baseline/scaler/imputer/features/model
  ├─ validation: select model hyperparameters
  └─ calibration: select score threshold/persistence
```

Outer test แต่ละชุดเปิดดูครั้งเดียวเมื่อ candidate ถูก freeze หากปรับ parameter หลังเห็น test แล้ว ต้องถือว่า test นั้นกลายเป็น development evidence และสร้าง test รอบใหม่ งานของ Cawley และ Talbot แสดงว่าแม้ตัวประมาณ validation จะไม่ bias มาก แต่ variance ของกระบวนการเลือก model สามารถทำให้ overfit model-selection criterion และสร้าง optimistic selection bias ได้ ([Cawley & Talbot, 2010](https://www.jmlr.org/beta/papers/v11/cawley10a.html))

### 9.8 Objective สำหรับข้อมูลที่ยังไม่มี fault labels

ไม่มี objective ใดวัด “ความแม่นยำของ leak” ได้ในปัจจุบัน จึงต้องใช้ constrained multi-objective stability score แทน:

\[
J(\theta)=
\operatorname{median}_m A_m
+\lambda_1 Q_{0.90}(A_m)
+\lambda_2 Dispersion(A_m)
+\lambda_3 Instability_{seed}
+\lambda_4 Cost_{latency}
\]


- ไม่ต่ำกว่าความไวต่อ known service event หรือ synthetic sensitivity probe ที่ตกลงไว้
- ไม่ abstain มากเกิน budget
- explanation coverage ครบ
- worst-machine rate ไม่เกิน operational cap
- score distribution ไม่ collapse เป็นค่าคงที่

Synthetic injection ใช้ตรวจว่า model ตอบสนองต่อรูปแบบที่เราตั้งใจ เช่น gradual `Hp_2nd` residual drop, sensor stuck หรือ valve-response lag ได้หรือไม่ แต่ไม่ใช่หลักฐาน precision/recall ต่อ fault จริง เพราะ synthetic pattern มาจากสมมติฐานของผู้ออกแบบ


เมื่อมี label เป็นช่วงเวลา ให้ประเมินระดับ event/range ไม่ใช่แปลงทุกวินาทีเป็นตัวอย่างอิสระ งานของ Tatbul และคณะขยาย precision/recall ให้คำนึงถึง existence, overlap และ position ของ predicted range ([Tatbul et al., 2018](https://proceedings.neurips.cc/paper_files/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html)) ส่วน NAB ให้ความสำคัญกับการเตือนเร็วและลงโทษ false alarm ใน streaming setting ([Lavin & Ahmad, 2015](https://ieeexplore.ieee.org/document/7424283/))


- event precision/recall
- detected fraction ของ fault range
- first-alert lead time
- duplicate alerts ต่อ event
- false alerts ต่อ machine-day
- VUS-PR หรือ range metric เป็นผลเสริมเมื่อ implementation พร้อม

### 9.10 Conformal และ uncertainty สำหรับข้อมูลพึ่งพากัน

Conformal calibration มาตรฐานอาศัย exchangeability ซึ่งไม่ตรงกับ telemetry ตามเวลา งาน Chernozhukov, Wüthrich และ Zhu ขยาย conformal inference ไปยัง dependent data ด้วย block structure และให้ approximate validity ภายใต้ weak dependence ([Chernozhukov et al., 2018](https://proceedings.mlr.press/v75/chernozhukov18a.html)) จึงควรใช้ blocked/rolling calibration และตรวจ realized coverage หรือ false-alert rate แยกตามเครื่อง


---

## 10. การนำไปใช้บน Server

### 10.1 Dual-rate architecture

ข้อมูลหนึ่งนาทีไม่สามารถสร้าง trajectory หนึ่งวินาทีย้อนหลังได้หลังจากรายละเอียดถูก aggregate ทิ้งแล้ว ทางออกคือให้ server เก็บ one-second circular buffer ชั่วคราว 120–180 วินาที เมื่อพบ valve event ให้คำนวณ response feature แล้วเขียนเป็นหนึ่ง record ประกอบ minute stream

```text
1-second stream → ring buffer → event detector → 30/120-s response features
                                          ↘
1-minute stream → steady features/profile join → combined scoring
```

วิธีนี้รักษาความสัมพันธ์แบบหนึ่งวินาทีในรูป feature โดยไม่ต้องให้ model production อ่าน raw history ทั้งเดือนทุกครั้ง

### 10.2 Operational tiers

- **Tier 0 Data quality:** ทุกวินาที/นาที ต้นทุนต่ำ
- **Tier 1 Steady anomaly:** หนึ่งครั้งต่อนาทีต่อ active module
- **Tier 2 Fast event:** score หลัง event 30 วินาที
- **Tier 3 Complete event:** score/forensic summary หลัง 120 วินาที
- **Tier 4 Daily drift:** CUSUM/ADWIN/profile-health summary

### 10.3 Current benchmark evidence

Model bundles ปัจจุบันมีขนาดประมาณ 1.2–1.35 MiB และ batch inference p95 ประมาณ 40–45 ms ใน benchmark ที่ทำไว้ Estimated ring-buffer payload 180 วินาทีสำหรับ 19 เครื่องอยู่ประมาณ 2.5 MiB และ raw compressed storage ที่ density ปัจจุบันประมาณ 1.1 GiB ต่อ 30 วันสำหรับ 19 เครื่อง ตัวเลขเหล่านี้เป็น capacity estimate จาก environment ปัจจุบัน ต้อง benchmark ใหม่บน production server และ concurrency จริง

### 10.3.1 Phase 06 Auto-bootstrap implementation evidence

Notebook Phase 06 ที่รันเมื่อ 2026-09-08 นำ specification ในบทที่ 8 มาทดลองกับ state-qualified minute cache จริง โดยใช้ profile key แบบ machine–module–SV, แบ่งอดีต 70% สำหรับ calibration และอนาคต 30% สำหรับ shadow, quarantine ด้วย two-pass robust residual, ตรวจ first-half/second-half stability และประมาณ uncertainty จาก circular day-block bootstrap 400 รอบ Threshold q99/q99.5 เรียนจาก retained calibration เท่านั้น และกำหนด shadow readiness ขั้นต่ำสามวัน

ผลได้ steady-profile records 262 รายการ แบ่งเป็น `SHADOW_VALIDATION` 39, `CANDIDATE_PROFILE` 3, `REVIEW_REQUIRED` 66 และ `INSUFFICIENT_DATA` 154 ขณะที่ event-response strata 524 รายการเป็น `INSUFFICIENT_COVERAGE` ทั้งหมดเมื่อแยกตาม machine–module–SV–direction ผลนี้ไม่ใช่ความล้มเหลวของ notebook แต่เป็นหลักฐานว่าจำนวน clean events 243 รายการกระจายบางเกินไปสำหรับ local event profile ตาม gate ปัจจุบัน Candidate package ทุกตัวถูกบังคับให้ `auto_activation_allowed = false`; ไม่มีรายการใดเข้า `READY_FOR_APPROVAL` หรือ `ACTIVE_FROZEN`

การรันนี้ปิดช่องว่างด้าน lifecycle prototype, uncertainty และ audit trail แต่ยังไม่ปิดงานด้าน immutable registry, service/refill epoch, matched shallow benchmark หรือ production server replay ค่า shadow alert ที่สูงเป็น evidence ของ distribution/state mismatch ที่ต้องตรวจ ไม่ใช่ fault accuracy

### 10.4 Fail-safe behavior

- Missing/stale/invalid data ต้องคืน `DATA_QUALITY` ไม่ใช่ equipment anomaly
- Feature schema mismatch ต้อง reject request
- ไม่มี local profile ให้ใช้ approved fleet fallback เฉพาะที่รองรับ หรือ abstain
- Server restart ต้องโหลด frozen version เดิมแบบ deterministic
- ระบบนี้ต้องอยู่นอก safety-control path

### 10.5 Production feasibility จากหลักฐานปัจจุบัน

ให้แยกคำว่า “ใช้งานได้จริง” เป็นห้าระดับ:

| ระดับ | ความสามารถ | สถานะปัจจุบัน |
|---|---|---|
| P0 Reproducible offline | rerun feature/model แล้วได้ผลเดิม มี manifest/version | มีบางส่วนจาก notebook; ต้องรวมเป็น pipeline |
| P1 Shadow screening | รับข้อมูลจริงแต่ไม่ส่งผลต่อเครื่องหรือ maintenance decision | **ทำต่อได้ทันทีหลัง Auto-bootstrap implementation** |
| P2 Technician advisory | ส่ง Watch/Investigate พร้อมหลักฐานและเก็บ feedback | ทำได้เมื่อ alert budget, runbook และ owner พร้อม |
| P3 Probable-cause diagnosis | แยก leak/valve/compressor/sensor/common cause | ยังขาด confirmed labels/context |

ดังนั้นคำตอบคือ **ข้อมูลเพียงพอสำหรับเริ่ม Production engineering ของ screening service แต่ยังไม่เพียงพอสำหรับ Production claim ด้าน diagnostic accuracy** ความแตกต่างนี้ต้องปรากฏในชื่อ API, dashboard และเอกสารอนุมัติ

งาน Data Validation for Machine Learning แสดงว่าความผิดปกติของ input, schema-free data และ training-serving skew สามารถลบล้างประโยชน์ของ model และควรถูกตรวจต่อเนื่อง ([Polyzotis et al., 2019](https://proceedings.mlsys.org/paper_files/paper/2019/hash/928f1160e52192e3e0017fb63ab65391-Abstract.html)) ส่วน ML Test Score เสนอชุดการทดสอบและ monitoring requirements สำหรับประเมิน production readiness ([Breck et al., 2017](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/)) สองงานนี้สนับสนุนให้ data/state gate เป็น service tier แรก ไม่ใช่ pre-processing ที่ซ่อนอยู่

### 10.6 Provisional service-level objectives

ค่าเหล่านี้เป็น engineering target เริ่มต้น ต้องยืนยันกับ server และ operations จริง:

| SLI | เป้าหมายเริ่มต้น | Failure behavior |
|---|---:|---|
| minute score availability | ≥99.5% ของ qualified active-module minutes | missing score แสดง Data Quality; ไม่เดา |
| minute scoring p95 | <250 ms ต่อ batch ของ active fleet หลัง feature พร้อม | queue/retry; ไม่กระทบ PLC |
| fast-event score | <1 s หลังปิด 30-s horizon | ข้ามเป็น minute-only พร้อม reason |
| complete-event forensic | <5 s หลังปิด 120-s horizon | ทำ async; ไม่บล็อก fast tier |
| feature/profile/model version match | 100% | reject score request |
| deterministic replay | score/rank/alert เท่ากันภายใน numeric tolerance | block promotion |
| rollback recovery | <15 min หลังอนุมัติ rollback | กลับ frozen bundle ก่อนหน้า |
| alert duplication | ≤1 incident ต่อ machine/module/cause window | deduplicate/persistence layer |

Benchmark ปัจจุบันที่ p95 ประมาณ 40–45 ms และ bundle ราว 1.2–1.35 MiB ให้ evidence ว่า shallow path มี headroom แต่ยังไม่ได้ทดสอบ concurrency, serialization, cold start, OS scheduling และ monitoring overhead

### 10.7 Production observability

Monitoring ต้องครอบคลุมสี่กลุ่ม ไม่ใช่ดูเพียง CPU:

1. **Data:** freshness, missingness, sampling gap, schema, unit, unknown states
2. **Feature/profile:** robust residual distribution, profile coverage, fallback/abstain rate, service epoch
3. **Model/threshold:** score quantiles, alert volume, seed/version, threshold drift, model disagreement
4. **Operations:** latency, memory, queue depth, error rate, restart, rollback, alert acknowledgement และ technician outcome

งาน Hidden Technical Debt in ML Systems เตือนถึง entanglement, undeclared consumers, hidden feedback loops และการเปลี่ยนของโลกภายนอก ([Sculley et al., 2015](https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html)) สำหรับโครงการนี้ feedback loop ที่ต้องป้องกันคือการเอา score ของ model กลับไปคัด baseline จน model รับรองข้อมูลที่ตนเองชอบ และการปรับ threshold ตามจำนวน alert โดยไม่เก็บผลช่าง

### 10.8 Packaging, registry และ inference runtime

Shallow model ใช้ `joblib` ได้ใน research แต่ Production ต้องตรึง Python/library versions, feature schema และ artifact hash หากใช้ MLflow ควรใช้ model version tags และ aliases เช่น `candidate`, `shadow`, `champion`, `rollback` แทน stage ที่ไม่สะท้อน workflow เฉพาะโครงการ ([MLflow Model Registry workflow](https://www.mlflow.org/docs/latest/ml/model-registry/workflow/))


---

## 11. เครื่องมือซอฟต์แวร์ที่แนะนำ

| งาน | เครื่องมือ | เหตุผล |
|---|---|---|
| Data processing | Polars/Pandas, PyArrow | อ่าน Parquet และสร้าง feature table |
| Large local exploration | DuckDB | query Parquet ด้วย projection/filter pushdown โดยไม่ต้อง load ทุกคอลัมน์ |
| Statistical analysis | NumPy, SciPy, statsmodels | robust stats, ARX, ACF, regression |
| Change point | ruptures | PELT/Binseg สำหรับ offline service-epoch analysis |
| Online drift | River | ADWIN/Page-Hinkley สำหรับ score stream |
| Shallow ML | scikit-learn | Isolation Forest, PCA, One-Class SVM, calibration, splitters |
| Parameter-light outlier | PyOD หรือ implementation ที่ตรึง version | ECOD/COPOD benchmark |
| Subsequence analysis | STUMPY หรือ validated Matrix Profile implementation | motif/discord ของ qualified cycles |
| Supervised trees | CatBoost/LightGBM/Extra Trees | tabular nonlinear model และ class weighting |
| Sequence models | PyTorch | TCN/LSTM-AE, masked loss, reproducible training |
| Hyperparameter search | Optuna | search space แบบมี pruning; objective ต้องรวม worst-machine metric |
| Explainability | SHAP + raw evidence templates | feature contribution และ technician-facing evidence |
| Experiment tracking | MLflow | parameters, metrics, artifacts และ model/profile versions |
| Data validation | Pandera/Great Expectations | schema, units, accepted states และ freshness checks |
| Data/model versioning | Git + immutable manifest; DVC/object storage เมื่อ scale ต้องการ | เชื่อม source snapshot กับ output hash |
| Serving | FastAPI/gRPC ตาม environment; ONNX Runtime สำหรับ deep challenger | versioned inference interface และ benchmark |
| Monitoring | Prometheus/Grafana หรือ equivalent | latency, data quality, alert volume, drift and version health |

Tools ไม่ได้แก้ปัญหา leakage หรือ semantics โดยอัตโนมัติ ทุก artifact ต้องบันทึก source period, split manifest, feature version, profile version และ code revision

DuckDB รองรับการอ่าน Parquet พร้อม projection และ filter pushdown จึงเหมาะกับการสำรวจข้อมูลจำนวนมากโดยอ่านเฉพาะคอลัมน์และ partition ที่ใช้ ([DuckDB Parquet documentation](https://duckdb.org/docs/current/data/parquet/overview)) แต่ production streaming service ไม่จำเป็นต้องใช้เครื่องมือเดียวกับ offline analysis

### 11.1 Minimal stack ที่แนะนำในระยะปัจจุบัน

```text
Parquet + PyArrow/Polars
→ Pandera schema/state checks
→ statsmodels/scikit-learn feature + shallow model
→ Optuna เฉพาะ inner temporal validation
→ MLflow registry + immutable manifests
→ FastAPI worker + Prometheus metrics
```

PyTorch, ONNX, GPU serving, feature store และ distributed compute ควรเพิ่มเมื่อมี bottleneck หรือ sequence model ผ่าน acceptance gate แล้ว การเพิ่มเครื่องมือก่อนมี use case จะเพิ่ม dependency และ configuration surface ซึ่งเป็น technical debt โดยตรง

### 11.2 Reproducibility manifest ขั้นต่ำ

ทุก training/calibration run ต้องบันทึก:

```text
run_id, code_revision, README_revision
source_file_manifest/hash, source period, timezone assumption
row/event grain, inclusion/exclusion rules
train/validation/calibration/test split manifest
feature schema/order/version and availability time
profile/service epoch/version
model class/parameters/random seeds/library versions
threshold/persistence version
metrics by machine and worst-machine result
artifact hashes and exact rollback target
```

---

## 12. แผนการทดลองที่ควรดำเนินการ

### Experiment A — Robust drift baseline

เปรียบเทียบ rolling robust z-score, EWMA, CUSUM และ Page-Hinkley บน daily/cycle `Hp_2nd` residual โดยตั้งเป้าตรวจ gradual low drift และวัด false alerts per machine-day ทำ sensitivity ต่อ $(k,h)$, window และ service epoch

### Experiment B — Shallow multivariate anomaly benchmark

เปรียบเทียบ Isolation Forest, ECOD/COPOD, PCA-SPE, One-Class SVM และ LOF บน feature set เดียวกัน ใช้ temporal + LOMO + sparse external split และ calibrate threshold แยกจาก training

### Experiment C — Dynamic residual

สร้าง ARX/Ridge model สำหรับ `Lp_2nd`, `Hp_2nd` และ `ΔP_2` ทดลอง lag 5–120 วินาที แยก closing/opening/SV เมื่อ coverage พอ แล้วเทียบ residual detector กับ engineered response feature

### Experiment D — Feature ablation

เปรียบเทียบ:

```text
pressure only
pressure + valve
pressure + valve + CP1
minute + 30-s response
minute + 120-s response
```

เพื่อพิสูจน์ว่า feature ที่เพิ่มขึ้นช่วย LOMO/temporal stability จริง ไม่ใช่เพียงเพิ่ม alert rate

### Experiment E — Auto-bootstrap replay

จำลองเครื่องแต่ละตัวเข้าระบบตามลำดับเวลา ใช้เฉพาะข้อมูลอดีตสร้าง candidate จากนั้นวัดเวลาถึง readiness, quarantine rate, profile stability, shadow alert rate และความเปลี่ยนแปลงเมื่อมี service epoch

### Experiment G — Technician-labeled probable cause

หลังได้ labels ให้เปรียบเทียบ Extra Trees, CatBoost และ calibrated gradient boosting ใช้ class-weight/cost-sensitive objective และรายงาน PR-AUC, lead time, false alerts ต่อ machine-day พร้อม confusion ระหว่าง undercharge, valve, sensor และ common cause

### Experiment H — Unsupervised detector and HPO benchmark

เปรียบเทียบ robust-only, PCA-SPE, ECOD, COPOD, Isolation Forest, OCSVM, LOF และ RRCF ด้วย feature/split/calibration เดียวกัน ใช้ random search เป็น mandatory baseline แล้วเปรียบ Optuna-TPE เฉพาะกรณี search budget เดียวกัน รายงานจำนวน trial, wall time, seeds, parameter importance และ test ที่ไม่ถูกใช้ tune

### Experiment I — Profile sample-size and bootstrap study

Replay การสะสมข้อมูลทีละวันสำหรับทุก machine–module–SV profile วาด stability curve ของ median/MAD/quantile และใช้ moving-block กับ stationary bootstrap เปรียบ CI width ตาม block length เป้าหมายคือแทนค่าขั้นต่ำ 7/14 วันและ 200 windows ด้วย evidence ว่า profile เริ่มนิ่งจริงเมื่อใด

### Experiment L — Production shadow and failure injection

Replay ข้อมูลตามเวลาใน server-like process ทดสอบ missing/stale/out-of-order data, unknown state, model timeout, profile missing, restart, version mismatch และ rollback วัด SLI/SLO จากหัวข้อ 10.6 พร้อมตรวจว่าไม่มีกรณีใดส่งผลต่อ PLC/control path

---

## 13. การกำกับดูแลและการทำงานร่วมกับช่าง

ระบบต้องแสดงหลักฐานและขอบเขตของความไม่แน่ใจ ไม่ใช่แสดงคำตอบเด็ดขาดเพียงบรรทัดเดียว NIST AI RMF ให้ความสำคัญกับการกำหนดบทบาท human oversight, documentation, ongoing monitoring และการทบทวนความเสี่ยงตลอด lifecycle ([NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)) หลักการนี้นำมาใช้กับโครงการได้ดังนี้:

- Technician ต้องเลือก standard cause code; raw note เป็นหลักฐานเสริม ไม่ใช่ class ที่ระบบสร้างเอง
- คะแนน Health/Condition ที่ผ่าน gate อธิบายได้เพียงความเบี่ยงเบนเทียบ profile และ `Normal within this profile`; ไม่ใช่ probability of failure
- Cause probability ต้องเป็น calibrated probability จาก model version ที่ตรวจ temporal/LOMO แล้ว และต้อง abstain เมื่อหลักฐานไม่พอ
- Approver ต้องเห็น shadow evidence และ rollback target
- Model/profile ทุกเวอร์ชันต้อง reproducible
- การแก้ threshold ต้องผ่าน validation เช่นเดียวกับการเปลี่ยน model
- Incident ที่เกิดจาก data quality ต้องแยกจาก equipment anomaly

### 13.1 QA Loop ที่ต้องวนตรวจทุกครั้ง


**รอบที่ 1 — System semantics**

- อ่าน `README_System.md` และ `SOT.md` ใหม่
- ตรวจ CP1/CP2, tag, module, SV และ `Hp_2nd` one-sided rule
- เทียบข้อความกับ P&ID/service/controller evidence ที่มี

**รอบที่ 2 — Data and calculation**

- reconcile จำนวนไฟล์ แถว เครื่อง วัน profile และ event กับ output จริง
- ตรวจ grain, filters, timezone, missingness และ exclusion
- ตรวจว่าสมการ หน่วย และทิศทางของ feature ตรงกับ code/notebook

**รอบที่ 3 — Model and leakage**

- ตรวจ fit/transform/calibrate เป็น train-only
- ตรวจ overlapping cycle/window, purge gap และ group split
- ตรวจ HPO ไม่เห็น outer test และ rerun หลาย seed

**รอบที่ 4 — Evidence and language**

- ทุก claim สำคัญมีแหล่งต้นฉบับหรือ internal artifact
- แยก source fact, project inference และ provisional policy
- ไม่ย้าย accuracy จากระบบ refrigeration อื่นมาอ้างกับ HT9046MX
- ไม่เปลี่ยน anomaly/correlation เป็น confirmed fault/causality

**รอบที่ 5 — Presentation and Production**

- chart title, axis, unit, denominator, sample size และ caveat ถูกต้อง
- ตรวจ worst-machine ไม่รายงานแต่ค่าเฉลี่ย
- benchmark latency/restart/missing data/rollback
- อัปเดต Project, AGENTS, SOT, Roadmap, UX, graft และ change log


### 13.2 เหตุผลที่ Production ต้องตรวจระบบมากกว่า model

ML Test Score ระบุ testing/monitoring requirements ที่กว้างกว่า accuracy ขณะที่งานศึกษากระบวนการ ML production มากกว่า 10,000 pipelines พบว่าระบบจริงมี component เชื่อมต่อและการ run ซ้ำจำนวนมาก ([Xin et al., 2021](https://research.google/pubs/production-machine-learning-pipelines-empirical-analysis-and-optimization-opportunities/)) สำหรับ HT9046MX จึงต้อง QA data/state/profile/threshold/serving พร้อมกัน การรับรองเฉพาะไฟล์ model ไม่เพียงพอ

---

## 14. ข้อจำกัดของงาน

1. ไม่มี confirmed failure/no-failure labels จึงไม่มีหลักฐานวัด diagnostic accuracy
2. ขาด recipe, actual temperature, setpoint, load และ facility-water telemetry
3. Clean event กระจุกที่ closing/SV Off และไม่ครอบคลุมทุกเครื่อง
4. เครื่อง sparse test มีจำนวนวัน/เหตุการณ์น้อย อัตรา 0% หรือ 100% จึงไม่เสถียร
5. `Status_n` ยังไม่มี codebook ที่ยืนยันกับ controller
6. Service/refill record ยังไม่ครบ ทำให้ change point บางจุดระบุสาเหตุไม่ได้
7. ผลจากงานวิจัย HVAC/VRF/chiller ไม่สามารถย้ายมายัง cascade R507A/R23 ได้โดยตรง
8. Correlation, lag, model residual และ SHAP ไม่ใช่ causal proof
9. Threshold จำนวนวัน/window/event ของ Auto-bootstrap เป็น provisional policy ต้อง validate กับ replay
10. ผล benchmark server ปัจจุบันไม่ใช่ production load test
11. Unsupervised HPO เลือกความเสถียรและ alert behavior ได้ แต่ไม่สามารถเลือก sensitivity ต่อ leak จริงเมื่อไม่มี label
12. งาน deep anomaly detection ภายนอกใช้ sensor, state, label และ benchmark ต่างจาก HT9046MX จึงเป็นหลักฐานให้ทดลอง ไม่ใช่หลักฐานให้ deploy
13. Auto-bootstrap candidate lifecycle และ notebook QA ถูก implement แล้ว แต่ immutable registry, verified service epoch, matched benchmark และ shadow server ยังไม่ได้ implement end-to-end

---

## 15. ข้อสรุป


แนวทางที่สมเหตุผลที่สุดคือเริ่มจากระบบที่ประกอบด้วย state gate, robust local calibration, pressure differential, trend, CUSUM, ARX/event residual และ Isolation Forest จากนั้นรวมหลักฐานด้วย persistence policy และให้ช่างตรวจยืนยัน สถาปัตยกรรมนี้สอดคล้องกับทั้งคุณสมบัติของข้อมูลจริง งานวิจัยด้าน vapor-compression FDD และความต้องการด้านการอธิบาย


เส้นทางไปสู่ระบบ ML ที่วินิจฉัยได้จริงจึงไม่ได้เริ่มจากการเพิ่มความลึกของ neural network แต่เริ่มจากการเพิ่มคุณภาพของ context และ label: recipe, temperature outcome, facility water, service event และผลตรวจจากช่าง เมื่อ evidence เหล่านี้พร้อม จึงค่อยให้ supervised tree model แยก probable cause และให้ TCN/LSTM-AE ทดสอบว่ารูป sequence เพิ่มคุณค่าจาก shallow hybrid baseline มากพอหรือไม่

ในสถานะปัจจุบัน คำตอบที่ซื่อสัตย์และนำไปใช้ได้คือ ระบบพร้อมสำหรับ anomaly screening และ calibration research แต่ยังไม่พร้อมสำหรับ automatic leak diagnosis หรือ autonomous production activation

หลังการทบทวนฉบับขยาย ข้อสรุปนี้แข็งแรงขึ้น ไม่ได้อ่อนลง: งาน benchmark ล่าสุดไม่ได้แสดงว่า deep model ชนะเสมอ งาน production ML ยืนยันว่าคุณภาพข้อมูล versioning และ monitoring เป็นส่วนหลักของความน่าเชื่อถือ และงาน bootstrap/control-chart ยืนยันว่าการสร้าง baseline อัตโนมัติต้องป้องกัน contamination ดังนั้นเส้นทางที่มีโอกาสใช้งานจริงสูงสุดคือ deploy **shallow hybrid ใน shadow/advisory mode ก่อน** พร้อมเดินการทดลอง ARX, ECOD/COPOD/RRCF และ TCN/LSTM เป็น challenger lanes ภายใต้ nested temporal/LOMO protocol เดียวกัน


---

## 16. Fleet transfer และ conformal monitoring: ทบทวนงานวิจัยเพิ่มเติม (2026-09-24)

ส่วนนี้เป็น **ข้อเสนอการทดลอง** ไม่ใช่ผล benchmark ใหม่ของ HT9046MX และไม่เปลี่ยน release, threshold, profile หรือกติกา approval ที่ใช้อยู่ ข้อสรุปจากงานวิจัยข้ามโดเมนต้องถูกทดสอบกับข้อมูลเครื่องจริงก่อนใช้ใน Server

| งาน | สิ่งที่งานวิจัยทำจริง | สิ่งที่ย้ายมาใช้กับ HT9046MX ได้ | ข้อจำกัดที่ต้องรักษา |
|---|---|---|---|
| Wang et al. (2026) [52] | Pretrain LSTM encoder–decoder จาก source ที่มีประวัติยาวและไม่มี health labels แล้วใช้ weights เริ่มต้น fine-tune target ที่มีประวัติสั้น; case รถไฟใช้ 21 signals, source 8 เดือน, target 3 สัปดาห์ และตั้ง threshold จาก source validation ที่ percentile 99.9 | เป็น **sequence challenger** สำหรับ target machine/module ที่ข้อมูล qualified น้อย; เปรียบเทียบ source-only, target-only, transferred และ shallow baseline | งานอาศัยสมมติฐานว่าข้อมูลส่วนใหญ่ปกติและใช้ผู้เชี่ยวชาญตรวจบาง event; ไม่พิสูจน์ว่า LSTM ดีกว่า ARX/robust profile ของเรา หรือว่า source threshold ย้ายข้ามเครื่องได้ |
| Farouq et al. (2022) [53] | Unit-level ensemble (ULEM), subfleet-level ensemble (SLEM), และ combined ensemble (CEM); CEM ลด false alarms แต่ตรวจช้าขึ้นใน district-heating case | แยก `Self` กับ `Peer` evidence แล้วทดสอบการรวมสัญญาณ/alert budget; ไม่จำเป็นต้องใช้ ensemble เต็มรูปแบบทันที | งานใช้ expert-annotated intervals ในการรายงาน precision/delay; HT9046MX ยังไม่มี labels เทียบเท่า และ online conformal validity อาจเสียเมื่อ data drift/update |
| Farouq et al. (2021) [54] | เลือก conformal subfleet ด้วย k-NN/cluster stability และติดตาม conformal anomaly sequence | สร้าง peer eligibility/coverage และ sequence persistence เฉพาะ machine×module×regime ที่เทียบกันได้ | การรับประกัน Mondrian ต้องอาศัย exchangeability ในกลุ่ม; fleet ของเราเล็กกว่า subfleet 101 units ใน case study มาก. ค่า cross-sectional rank จึงหยาบ และ `p-value` ไม่ใช่โอกาสเครื่องเสีย |

### 16.1 ตีความกับสถาปัตยกรรมปัจจุบัน

แนวคิดที่ใช้ได้ทันทีในเชิง **ออกแบบและ QA** คือ conditional peer selection, regime/segment matching และการเก็บ `Self`/`Peer`/`Dynamic`/`Temporal` evidence แยกกัน. สำหรับ `Cold` ที่ผ่าน gate ให้เริ่มจาก `Status=ON`, `Status_n=On`, `Busy=0`, `SV=Off`; ไม่ตั้งสมมติฐานว่า `SV` ตัวเดียวบอก operating regime ทั้งหมด. `Opening`, `SV=On`, manual/service และ mixed-state ต้องแยก coverage และ abstain หากไม่มี reference ที่พอ. ไม่รวมทุก machine/module เข้าฐานเดียว แม้จะเป็นรุ่นเดียวกัน.


Conformal layer เป็น **วิธีปรับสเกล nonconformity score และจัดการ alert budget** ไม่ใช่ model ที่ยืนยัน fault. ตัวอย่าง split-conformal score เมื่อ calibration block แยกจาก training คือ

\[
p_t=\frac{1+\sum_{i=1}^{n}\mathbf{1}(s_i\ge s_t)}{n+1},
\]



### 16.2 การทดลองก่อนตัดสินใจเปลี่ยน model

1. แยก training / inner validation / threshold calibration / forward shadow / outer test ตามเวลา พร้อม purge ที่ครอบคลุม lookback และ event overlap; ทำ leave-one-machine-out เพื่อดู negative transfer. Profile/scaler fit จาก training เท่านั้น.
2. เทียบ `local robust + CUSUM/EWMA`, current qualified ARX-Ridge, pooled/hierarchical Ridge จาก matched regimes และ `source-only`, `target-only`, `source→target LSTM-ED`. ทดสอบ peer+conformal เป็น layer แยกโดยใช้ threshold policy เดียวกัน.
3. ผ่าน gate เมื่อ challenger ลด alert burden หรือเพิ่ม reviewed-event utility ที่ fixed operational alert budget พร้อมตรวจ sparse machines, one-second latency, explanation, rollback และ governance. หาก transfer ด้อยกว่า target-only ให้ปฏิเสธ source หรือ regime นั้น; หากไม่มี comparable peers ให้ปิด Peer lane พร้อม reason code.

**สถานะการใช้งานจริง ณ 2026-09-24:** Four-evidence เป็น design contract ไม่ใช่สี่โมเดลที่ live ครบแล้ว. Runtime inference ปัจจุบันใช้ `max(abs(relative_z))` กับ persistence และยังส่งชื่อ `ARX-Ridge__seed_13` ทั้งที่ไม่ได้โหลด artifact นั้น. ต้องแก้ score/model provenance และ retrain/recalibrate ตาม state/relationship-feature contract ใหม่ก่อนถือว่าผลวิจัยเหล่านี้เปลี่ยน production behavior.

---

## เอกสารอ้างอิงหลัก

1. Li, H., & Braun, J. E. (2007). *Decoupling features and virtual sensors for diagnosis of faults in vapor compression air conditioners*. International Journal of Refrigeration. https://doi.org/10.1016/j.ijrefrig.2006.07.024
2. Tassou, S. A., & Grace, I. N. (2005). *Fault diagnosis and refrigerant leak detection in vapour compression refrigeration systems*. International Journal of Refrigeration. https://doi.org/10.1016/j.ijrefrig.2004.12.007
3. Mtibaa et al. (2024). *Refrigerant leak detection in industrial vapor compression refrigeration systems using machine learning*. International Journal of Refrigeration. https://doi.org/10.1016/j.ijrefrig.2024.02.016
4. Yan, K., Shen, W., Mulumba, T., & Afshari, A. (2014). *ARX model based fault detection and diagnosis for chillers using support vector machines*. Energy and Buildings. https://doi.org/10.1016/j.enbuild.2014.05.049
5. Kocyigit, N. (2015). *Fault and sensor error diagnostic strategies for a vapor compression refrigeration system*. International Journal of Refrigeration. https://doi.org/10.1016/j.ijrefrig.2014.10.017
6. Li et al. (2020). *Machine learning based diagnosis strategy for refrigerant charge amount malfunction of variable refrigerant flow system*. International Journal of Refrigeration. https://doi.org/10.1016/j.ijrefrig.2019.10.026
7. Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). *Isolation Forest*. IEEE ICDM. https://doi.org/10.1109/ICDM.2008.17
8. Malhotra et al. (2016). *LSTM-based Encoder-Decoder for Multi-sensor Anomaly Detection*. https://arxiv.org/abs/1607.00148
9. Bai, S., Kolter, J. Z., & Koltun, V. (2018). *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling*. https://arxiv.org/abs/1803.01271
10. Wagner et al. (2023). *TimeSeAD: Benchmarking Deep Multivariate Time-Series Anomaly Detection*. TMLR. https://mlanthology.org/tmlr/2023/wagner2023tmlr-timesead/
11. Goodarzi, P., Schütze, A., & Schneider, T. (2025). *Domain shifts in industrial condition monitoring*. Journal of Sensors and Sensor Systems. https://doi.org/10.5194/jsss-14-119-2025
12. Bifet, A., & Gavaldà, R. (2007). *Learning from Time-Changing Data with Adaptive Windowing*. SIAM SDM. https://doi.org/10.1137/1.9781611972771.42
13. Atalay et al. (2020). *Guidelines for automating Phase I of control charts*. Quality Engineering. https://doi.org/10.1080/08982112.2019.1641210
14. Künsch, H. R. (1989). *The Jackknife and the Bootstrap for General Stationary Observations*. Annals of Statistics. https://doi.org/10.1214/aos/1176347265
15. Zhang et al. (2025). *Conformal Anomaly Detection in Event Sequences*. ICML/PMLR. https://proceedings.mlr.press/v267/zhang25dn.html
16. Lundberg, S. M., & Lee, S.-I. (2017). *A Unified Approach to Interpreting Model Predictions*. NeurIPS. https://papers.nips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html
17. Saito, T., & Rehmsmeier, M. (2015). *The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets*. PLOS ONE. https://doi.org/10.1371/journal.pone.0118432
18. NIST. (2023). *Artificial Intelligence Risk Management Framework 1.0*. https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf
19. NIST/SEMATECH. *CUSUM Control Charts*. https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm
20. Politis, D. N., & Romano, J. P. (1994). *The Stationary Bootstrap*. Journal of the American Statistical Association. https://doi.org/10.1080/01621459.1994.10476870
21. Killick, R., Fearnhead, P., & Eckley, I. A. (2012). *Optimal Detection of Changepoints With a Linear Computational Cost*. Journal of the American Statistical Association. https://doi.org/10.1080/01621459.2012.737745
22. Bergstra, J., & Bengio, Y. (2012). *Random Search for Hyper-Parameter Optimization*. JMLR. https://www.jmlr.org/papers/v13/bergstra12a.html
23. Li, L., Jamieson, K., DeSalvo, G., Rostamizadeh, A., & Talwalkar, A. (2018). *Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization*. JMLR. https://www.jmlr.org/beta/papers/v18/16-558.html
24. Akiba, T., Sano, S., Yanase, T., Ohta, T., & Koyama, M. (2019). *Optuna: A Next-generation Hyperparameter Optimization Framework*. KDD. https://arxiv.org/abs/1907.10902
25. Lindauer, M., et al. (2022). *SMAC3: A Versatile Bayesian Optimization Package for Hyperparameter Optimization*. JMLR. https://www.jmlr.org/papers/v23/21-0888.html
26. Cawley, G. C., & Talbot, N. L. C. (2010). *On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation*. JMLR. https://www.jmlr.org/beta/papers/v11/cawley10a.html
27. Li, Z., Zhao, Y., Hu, X., Botta, N., Ionescu, C., & Chen, G. H. (2022). *ECOD: Unsupervised Outlier Detection Using Empirical Cumulative Distribution Functions*. https://arxiv.org/abs/2201.00382
28. Li, Z., Zhao, Y., Botta, N., Ionescu, C., & Hu, X. (2020). *COPOD: Copula-Based Outlier Detection*. IEEE ICDM. https://ieeexplore.ieee.org/document/9338429
29. Guha, S., Mishra, N., Roy, G., & Schrijvers, O. (2016). *Robust Random Cut Forest Based Anomaly Detection on Streams*. ICML/PMLR. https://proceedings.mlr.press/v48/guha16.html
30. Schmidl, S., Wenig, P., & Papenbrock, T. (2022). *Anomaly Detection in Time Series: A Comprehensive Evaluation*. PVLDB. https://vldb.org/pvldb/vol15/p1779-wenig.pdf
31. Wu, R., & Keogh, E. (2021). *Current Time Series Anomaly Detection Benchmarks are Flawed and are Creating the Illusion of Progress*. IEEE TKDE. https://doi.org/10.1109/TKDE.2021.3112126
32. Tatbul, N., Lee, T. J., Zdonik, S., Alam, M., & Gottschlich, J. (2018). *Precision and Recall for Time Series*. NeurIPS. https://proceedings.neurips.cc/paper_files/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html
33. Lavin, A., & Ahmad, S. (2015). *Evaluating Real-Time Anomaly Detection Algorithms — The Numenta Anomaly Benchmark*. IEEE. https://ieeexplore.ieee.org/document/7424283/
34. Liu, Q., & Paparrizos, J. (2024). *The Elephant in the Room: Towards A Reliable Time-Series Anomaly Detection Benchmark*. NeurIPS Datasets and Benchmarks. https://proceedings.neurips.cc/paper_files/paper/2024/hash/c3f3c690b7a99fba16d0efd35cb83b2c-Abstract-Datasets_and_Benchmarks_Track.html
35. Xu, J., Wu, H., Wang, J., & Long, M. (2022). *Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy*. ICLR. https://openreview.net/pdf?id=LzQQ89U1qm_
36. Tuli, S., Casale, G., & Jennings, N. R. (2022). *TranAD: Deep Transformer Networks for Anomaly Detection in Multivariate Time Series Data*. PVLDB. https://vldb.org/pvldb/vol15/p1201-tuli.pdf
37. Song, J., Kim, K., Oh, J., & Cho, S. (2023). *MEMTO: Memory-guided Transformer for Multivariate Time Series Anomaly Detection*. NeurIPS. https://proceedings.neurips.cc/paper_files/paper/2023/hash/b4c898eb1fb556b8d871fbe9ead92256-Abstract.html
38. Chernozhukov, V., Wüthrich, K., & Zhu, Y. (2018). *Exact and Robust Conformal Inference Methods for Predictive Machine Learning with Dependent Data*. COLT/PMLR. https://proceedings.mlr.press/v75/chernozhukov18a.html
39. Polyzotis, N., Zinkevich, M., Roy, S., Breck, E., & Whang, S. (2019). *Data Validation for Machine Learning*. MLSys. https://proceedings.mlsys.org/paper_files/paper/2019/hash/928f1160e52192e3e0017fb63ab65391-Abstract.html
40. Breck, E., Cai, S., Nielsen, E., Salib, M., & Sculley, D. (2017). *The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction*. IEEE Big Data. https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/
41. Sculley, D., et al. (2015). *Hidden Technical Debt in Machine Learning Systems*. NeurIPS. https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html
42. Xin, D., Miao, H., Parameswaran, A., & Polyzotis, N. (2021). *Production Machine Learning Pipelines: Empirical Analysis and Optimization Opportunities*. SIGMOD. https://research.google/pubs/production-machine-learning-pipelines-empirical-analysis-and-optimization-opportunities/
43. Ratner, A., Bach, S. H., Ehrenberg, H., Fries, J., Wu, S., & Ré, C. (2017). *Snorkel: Rapid Training Data Creation with Weak Supervision*. PVLDB. https://www.vldb.org/pvldb/vol11/p269-ratner.pdf
44. Yeh, C.-C. M., et al. (2016). *Matrix Profile I: All Pairs Similarity Joins for Time Series*. IEEE ICDM. https://doi.org/10.1109/ICDM.2016.0179
45. Prokhorenkova, L., Gusev, G., Vorobev, A., Dorogush, A. V., & Gulin, A. (2018). *CatBoost: Unbiased Boosting with Categorical Features*. NeurIPS. https://proceedings.neurips.cc/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html
46. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*. KDD. https://doi.org/10.1145/2939672.2939785
47. Ke, G., et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*. NeurIPS. https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html
48. NIST/SEMATECH. *EWMA Control Chart*. https://www.itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm
49. MLflow. *Model Registry Workflows*. https://www.mlflow.org/docs/latest/ml/model-registry/workflow/
50. ONNX Runtime. *Quantize ONNX Models*. https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html
51. DuckDB. *Reading and Writing Parquet Files*. https://duckdb.org/docs/current/data/parquet/overview
52. Wang, B., Baraldi, P., Zio, E., Brown, J., & Gauthier, S. (2026). *Fleet-based transfer learning for anomaly detection in industrial systems*. Mechanical Systems and Signal Processing, 244, 113725. https://doi.org/10.1016/j.ymssp.2025.113725
53. Farouq, S., Byttner, S., Bouguelia, M.-R., & Gadd, H. (2022). *A conformal anomaly detection based industrial fleet monitoring framework: A case study in district heating*. Expert Systems with Applications, 201, 116864. https://doi.org/10.1016/j.eswa.2022.116864
54. Farouq, S., Byttner, S., Bouguelia, M.-R., & Gadd, H. (2021). *Mondrian conformal anomaly detection for fault sequence identification in heterogeneous fleets*. Neurocomputing, 462, 591–606. https://doi.org/10.1016/j.neucom.2021.08.016
55. Ghauch, Z., Young, A., Brown, B. D., Stephen, B., West, G., McArthur, S., & Duncan, A. (2025). *Predictive monitoring of asset populations in a rotating plant under operational uncertainty: a transfer learning approach*. Data-Centric Engineering, 6, e21. https://doi.org/10.1017/dce.2025.3

---

## ภาคผนวก A — Model recommendation by data maturity

| Data maturity | Production candidate | Challenger |
|---|---|---|
| Current: no confirmed labels | Robust baseline + CUSUM + ARX residual + Isolation Forest | PCA-SPE, ECOD/COPOD, One-Class SVM |
| Balanced normal sequences | Same shallow hybrid | TCN-AE and LSTM-AE |
| Sparse confirmed labels | Calibrated shallow detector + weak-label review | CatBoost/Extra Trees |
| Sufficient confirmed labels | Calibrated supervised tree model + anomaly fallback | sequence classifier/physics-guided model |
| Mature production lifecycle | Versioned ensemble with abstention | controlled online/fleet adaptation |

## ภาคผนวก B — Definition of done for the next implementation

- [x] Auto-bootstrap candidate state machine implemented and tested
- [x] Steady/event readiness separated
- [x] Candidate contamination report produced per profile and machine package
- [x] Profile uncertainty estimated with day-block bootstrap
- [x] Temporal calibration-to-shadow replay prevents future leakage
- [ ] Threshold/persistence calibration is separated from model fitting
- [ ] LOMO and sparse external results include sample counts
- [ ] Event labels use event/range metrics without point adjustment
- [ ] At least one simple/statistical baseline remains in every model benchmark
- [ ] Alert output follows `UX.md`
- [x] Candidate implementation prevents automatic `ACTIVE_FROZEN` and requires explicit approval
- [ ] Rollback restores the exact previous feature/model/profile versions
- [ ] Shadow service passes missing-data, restart, version-mismatch and latency tests
- [ ] Seven-part QA Loop in `README_System.md` section 21 is signed off — notebook/system/data/evidence/presentation/governance checks passed with caveats; production checks remain
- [x] `SOT.md`, `Roadmap.md` and `graft/README.md` updated after implementation

## ภาคผนวก C — Production readiness verdict

| Capability | Ready now? | Evidence needed next |
|---|---|---|
| Offline state-aware baseline analysis | Yes, with documented gaps | Add missing operating context |
| Unsupervised minute anomaly screening | Yes for offline research; server shadow pending | Alert budget + server replay + verified service epoch |
| 30-second derived event features | Challenger only | More balanced clean events |
| 120-second hybrid model | No for operational default | Feature reduction and larger held-out event sets |
| Technician advisory alert | Conditional | Runbook, ownership, shadow evidence, UI acceptance |
| Automatic leak diagnosis | No | Confirmed failure/no-failure labels and cause separation |
| Safety/control action | No | Outside project scope |

## Change log

- 2026-10-01 — Added current-method clarification and linked detailed control-state/EEV/multimode research with event-conditioned ARX/DPCA proposals. No retraining, active algorithm/Profile/Server change; historical ensemble tables are not the selected live architecture.

- 2026-09-24 — Reviewed four primary fleet-transfer/conformal papers and recorded applicability, assumptions, small-fleet limits, model challengers and a leakage-safe acceptance experiment in Section 16. No model/profile/threshold/production state changed.

- 2026-09-14 — Added the owner-approved controlled-label and cause-probability presentation contract; it specifies future model/UI gates and does not claim a current calibrated classifier.

- 2026-09-10 — Updated the field-reference semantics to 180–230 psi, changed one-sided undercharge screening to `<180 psi`, separated high-side investigation, and retained water/tank causality as an unverified field hypothesis.

- 2026-09-08 — Recorded executed Phase 06 candidate lifecycle evidence, updated implementation limitations and aligned the remaining QA gate with the seven-part README contract
- 2026-09-08 — Version 1.1: expanded Deep Research on anomaly benchmarks, ECOD/COPOD/RRCF/Matrix Profile, HPO and selection bias, dependent-data conformal inference, block/stationary bootstrap, weak supervision, production ML testing, registry/serving tools, production feasibility and seven-part QA Loop
- 2026-09-08 — Clarified that “Loop Check” in project conversation means repeated QA review, not a new duplicate-detection subsystem
