# Local Calibration และการเลือก detector — 1 ตุลาคม 2026

## ข้อสรุปที่เลือก

คง **Calibration Profile แยก Machine × Module × qualified Cold context** และใช้ **frozen robust-z + 3 adjacent-minute persistence** เป็น primary ต่อไป การเพิ่มโมเดลกลางต้องใช้ค่าที่ปรับเทียบกับ Profile ของเครื่องนั้น ไม่ใช่บังคับทุกเครื่องให้อยู่ที่ pressure/temperature baseline เดียวกัน

รอบนี้ได้ฝึกและรัน ARX-Ridge, lag-embedded DPCA และ Isolation Forest จริง พร้อม adapted leave-one-machine-out แต่ยังไม่มีหลักฐานเพียงพอให้เปลี่ยนไปใช้โมเดลเหล่านั้นเปิด Alert แทน Self วิธีที่ควรปรับก่อนคือ **คุณภาพของช่วงอ้างอิงที่ใช้ Calibration** ไม่ใช่เพิ่มความซับซ้อนของโมเดล

สิ่งที่ทำใหม่เป็น local research code, frozen offline artifacts, Notebook และเอกสาร ไม่มีการแก้ production scorer, candidate registry, threshold ของ Active, Dashboard, MySQL หรือ Server และไม่มี Git commit/push

หลักฐานอ่านง่าย: `notebooks/08L_Local_Calibration_and_Model_Selection_Colab.ipynb` — รันทุกเซลล์แล้ว 11 code cells, 8 กราฟ, ไม่มี error กราฟมี PNG/SVG สำหรับสไลด์

## 1. แหล่งข้อมูลและช่วงที่ใช้

| เครื่อง | แหล่ง | บทบาทในรอบนี้ |
|---|---|---|
| MX017, MX024, MX080 | Strict 1m cache จาก dynamic TXT ใน Downloads ZIP ที่ตรวจใน 08K | ตรวจทุก Module, baseline/correlation, local reference และ diagnostic scoring |
| MX029, MX041, MX057, MX070 | Original raw-second Parquet บน Desktop | อ่านใหม่ สร้าง strict 1m cache ตรวจทุก Module และเทียบวิธี |
| MX118, MX119 | Original raw-second Parquet บน Desktop | ทดสอบ insufficient-history/abstention ไม่ใช้ฝึก shared models |

Parquet เพิ่มเติม 124 daily files มี 9,130,464 raw rows; MX057/MX070 มี empty day-files อย่างละ 4 ไฟล์ ซึ่งบันทึกไว้ใน inventory ไม่สร้างข้อมูลเติมแทน มี 116 nonempty files การตรวจ machine identity เกิดก่อน canonicalization และ timestamp precision ถูก normalize จาก `datetime64[us]` เป็น `datetime64[ns]` โดยไม่เปลี่ยนเวลา ไม่รับ subsecond source ใน fast adapter นี้

ช่วงที่เลือกคือ 4 ส.ค.–8 ก.ย. 2026 (end-exclusive 9 ก.ย.) Parquet หลายเครื่องสิ้นสุด 1 ก.ย.; MX118/MX119 มี 17–20 ส.ค. เท่านั้น จึงไม่ได้มีระยะประเมินเท่ากันทุกเครื่อง

ใช้ source clock แบบ naive และสมมติ Asia/Bangkok สำหรับ local review เท่านั้น ยังไม่ใช่การรับรอง clock ของ Server Pressure presumed psi, temperature presumed °C, Valve source command count ตาม contract ไม่มี independent sensor-calibration certificate

ไม่ใช้ `_Static.txt`, ไม่ interpolate, ไม่รวม primary MX017/MX024 ซ้ำกับ ZIP และไม่ได้กล่าวว่าอ่านทุก dataset ที่มีบนเครื่องนี้ทั้งหมด

ผลรวม 2,580,480 calendar module-minute slots; 1,507,132 นาทีมี offline reference และ causal lags ที่ครบสำหรับการเทียบ ภายใน matched future cohort ที่ทุก lane มี threshold เท่ากันเหลือ 375,857 นาทีจาก 36 contexts

`machine_coverage.csv` แสดง first/last **calendar minute slots** ไม่ใช่เวลาที่มี raw sample ทุกวินาที เวลาต้นทางจริงอยู่ใน raw inventory / October quality CSV

## 2. Profile และเหตุผลที่ต้องคง local calibration

Profile ใช้เฉพาะ 4–17 ส.ค. และ minimum 7 วัน / 200 นาทีหลัง quarantine:

\[
m_j=\operatorname{median}(x_j),\quad
s_j=\max(1.4826MAD_j,IQR_j/1.349,f_j),\quad
z_{t,j}=(x_{t,j}-m_j)/s_j.
\]

Valve floor 1 count; feature อื่น floor 0.1 source unit; initial quarantine เมื่อ max |z| > 8 แล้ว refit อีกครั้ง ฟีเจอร์ 9 ตัวคือ hp1/lp1/hp2/lp2/valve/temphi/templo/dp1/dp2 ผลต่าง pressure ไม่ใช่ refrigerant mass หรือ leak-rate measurement

Baseline และ within-day Spearman ต่างกันระหว่าง Machine × Module จริง ตัวอย่าง past Hp2 medians ของ M1: MX017 ≈193, MX024 ≈205, MX029 ≈189, MX041 ≈192, MX057 ≈193, MX070 ≈197, MX080 ≈183 psi ตัวเลขเป็น candidate observations ไม่ใช่การยืนยันสุขภาพหรือ standard setpoint

Within-day Lp2/TempLo ของ M1 มี Spearman ประมาณ +0.72 (MX017), −0.51 (MX024), −0.71 (MX057) และ −0.24 (MX080) ปัจจัย load, controller setting, startup, manual operation และ sensor behavior ยังแยกไม่ได้จาก correlation นี้ จึงไม่อ้างว่าเป็นความต่างเชิงกายภาพของเครื่องอย่างเดียว

### Reference screening ที่เพิ่มใน local experiment

ต้องตรวจ quarantine ≤5% และ max median shift ระหว่างครึ่งแรก/ครึ่งหลังของ retained fit ≤1.5 local z ชุดที่เกินยังแสดงเป็น `REFERENCE_REVIEW_REQUIRED` ไม่ถูกลบ แต่ไม่ใช้ฝึก shared models

| ผลคัดกรองจาก 72 Machine × Module | จำนวน |
|---|---:|
| Screened candidate — ยังไม่ approved | 9 |
| มีตัวเลข Profile แต่ reference ต้อง review | 41 |
| ประวัติไม่พอ | 22 |

เกณฑ์นี้เป็น **statistical screening** ไม่ใช่ normal label, change-point detector, learned settling envelope หรือ Active approval ตัวอย่าง MX080/M6 quarantine 16.19% จึงไม่ควร approve ช่วง fit นี้เพียงเพราะ median/scale คำนวณสำเร็จ

9 screened references ที่ใช้ shared fit: MX017/M4; MX024/M8; MX029/M3; MX057/M1,M3,M4; MX070/M3,M4,M8 มี 22,500 sampled training rows จาก 5 เครื่อง และ 9,000 inner rows การกล่าวว่าโมเดลถูกฝึกจากทั้ง 9 เครื่องจึงไม่ถูกต้อง MX041/MX080 ถูกใช้เป็น target diagnostics ไม่ใช่ shared-fit machines ส่วน MX118/119 ไม่มี supported reference

## 3. Split และวิธีที่รันจริง

| ช่วง | หน้าที่ |
|---|---|
| 4–17 ส.ค. | Profile, scaler, model weights fit |
| 18–21 ส.ค. | Ridge alpha inner selection |
| 22–25 ส.ค. | Threshold Q99.5 ราย context/lane, ≥200 นาทีและ ≥3 วัน |
| 26 ส.ค.–8 ก.ย. | Diagnostic future เท่านั้น |

ช่วงทั้งหมดมี start-inclusive/end-exclusive ตาม protocol JSON การสร้าง lag reset เมื่อ quality/context ไม่ผ่าน, missing minute, machine หรือ module เปลี่ยน Training ต้องมีปัจจุบันและสอง lag ก่อนหน้าผ่าน quarantine ด้วย

| วิธี | Inputs / parameters | หน้าที่และข้อจำกัด |
|---|---|---|
| Self original | 9 local z, max absolute, fit-retained Q99.5, >=, 3 adjacent minutes | Frozen-level deviation; same algorithm as primary แต่คนละ offline Profile/threshold ไม่ใช่ replay ของ Active จริง |
| Self separate-cut | Same Self score, threshold จาก separate past block | เปรียบเทียบ threshold-calibration policy ไม่ใช่ model ใหม่หรือ live retuning |
| ARX-Ridge | 14 lag inputs (7 sensors × lag 1,2m); targets Hp2/Lp2/TempHi/TempLo; inner alphas .1/1/10/100 เลือก 100 | Sensor prediction/residual ไม่มี fault labels; prediction residual อาจลดเมื่อผิดระดับแล้วนิ่ง |
| DPCA Q/SPE | 21 features (current7 + lag14), train-only StandardScaler, full SVD, variance ≥95%, ได้ 6 PCs /95.94% | ตรวจ reconstruction relationship; ไม่มี T² lane หรือ fault-cause model bank |
| Isolation Forest | Same21, 200 trees, max_samples1024, seed13, n_jobs1; -score_samples | Novelty score; ไม่ใช้ predict()/generic contamination cut และไม่ตี score เป็น fault probability |

ARX เป็น supervised regression เชิง task แต่ target คือ sensor ไม่ใช่ fault class ค่า residual ใช้ train-only median/MAD floor .1 Ridge inner objective เป็น prediction MSE เฉลี่ยเท่ากันราย Profile ไม่ใช่ anomaly detection F-score

PCA/IF hyperparameters fixed ตาม protocol ไม่ได้เลือกจาก case หรือ future; model-fit balanced cap 2,500 rows/context ทุก challenger ใช้ past-local threshold และ 3-minute persistence ไม่มีการเลือก OR voting จากผลเคส

Adapted LOMO มี 5 folds สำหรับ 5 shared-fit machines: held unit ไม่อยู่ใน shared weights/inner choice แต่ local reference และ past threshold ของ held unitยังใช้ได้ จึงเป็น target adaptation ไม่ใช่ zero-shot ใหม่ ไม่มี supervised fault classifier และไม่ได้ฝึก LSTM

## 4. ผลบน matched future cohort

| วิธี | Persistent minutes | % จาก 375,857 นาที | Persistent openings |
|---|---:|---:|---:|
| Self original | 55,875 | 14.866% | 2,392 |
| Self separate-cut | 28,365 | 7.547% | 963 |
| ARX-Ridge | 1,452 | 0.386% | 357 |
| DPCA | 21,320 | 5.672% | 965 |
| Isolation Forest | 37,601 | 10.004% | 1,631 |

จำนวนนี้เป็น **flag workload** ไม่ใช่ false-positive rate เครื่องมีช่วงที่ยังไม่ review, known cases และ operating context ที่ไม่รู้ครบ จึงเลือก “ดีที่สุด” จากเปอร์เซ็นต์ต่ำสุดไม่ได้ Openings ในที่นี้เป็นการเริ่มช่วง persistent flags ของ offline replay ไม่ใช่จำนวน PM Alert/ใบงานจริง

### Known-case regression

MX057/M1 วันที่ 29 ส.ค. 04:06–22:50 มี 1,124 matched case minutes:

- Self original: 1,122/1,124 (99.82%)
- ARX: 93/1,124 (8.27%)
- DPCA: 1,119/1,124 (99.56%)
- IF: 1,122/1,124 (99.82%)

ทุก lane มี first decision ในเคสประมาณ 04:09 แต่ ARX coverage ต่อเนื่องต่ำกว่ามาก สอดคล้องกับข้อจำกัดของ short-lag prediction: เมื่อระดับใหม่อยู่ใน lag แล้ว model อาจทำนายตามระดับนั้นได้ดี โดยไม่รู้ว่าระดับนั้นต่างจาก frozen healthy reference

MX080/M6 วันที่ 7 ก.ย. 12:23:28–8 ก.ย. 00:00:

- Self original offline probe: 679/686 matched minutes (98.98%), first decision 12:27
- Self-separate/ARX/DPCA/IF: **abstain** เพราะ threshold block มี 2,289 นาทีแต่เพียงสอง qualified days ไม่ครบสามวัน

การ abstain ไม่ใช่ model miss, score zero หรือ normal การทดลองนี้จึง **ยังไม่พิสูจน์ ML comparison บน MX080** และ Self probe ใช้ reference ที่ review-required ไม่ได้ทำให้ Profile นั้นพร้อม Active

ทั้งสองเคสเจ้าของโครงการยืนยัน behavioral anomaly แล้ว แต่ physical cause / technician cause confirmation ยังไม่ทราบ ช่วงถูกเปิดดูมาก่อน จึงเป็น regression ไม่ใช่ independent sensitivity/accuracy หรือ validated lead time Decision delay นี้นับปลายนาทีที่ complete ยังไม่รวม five-minute fetch/network/UI latency

## 5. สิ่งที่นำไปปรับ Auto-Calibration ได้

1. **คง local Profile** และ immutable reference อย่าให้ model กลางรับ raw pressure โดยสมมติ distribution เดียวกัน
2. **ตรวจ reference quality ก่อน approve**: วัน/นาทีพอไม่เพียงพอ ต้องเห็น quarantine, daily levels, half-shift และ control-state evidence กราฟนิ่งที่ผิดระดับไม่ควรกลายเป็น baseline ใหม่เพราะเพิ่งเกิดล่าสุด
3. **แยก quality กับ context**: manual/state transition อยู่ใน evidence แต่ไม่ปน steady fit ไม่เปิด gate กว้างจน manual values ถูกถือเป็น normal
4. **ตรวจ multi-start ก่อนสร้าง settling policy**: ใน matched diagnostic future 85.17% ไม่มี observed onset ที่รู้จริง การตัด 20 นาทีหลังเวลาเริ่มไฟล์จะไม่เท่ากับเวลาหลังเริ่ม compressor แถวที่เห็น onset ยังมีทั้ง run start, post-manual, Cold control entry ไม่ใช่ startup ชนิดเดียว
5. **Flexible past coverage ต้อง predeclare**: เมื่อ threshold blockมีสองวัน ระบบควรรอ/จัด candidate reference period ใหม่จากอดีตที่มีวันครบ ไม่ยืดช่วงด้วยข้อมูลในเคสที่กำลังประเมินเพื่อลดการ abstain
6. **คง Self เป็นหลักและทดสอบ incremental ML shadow**: ทบทวน ARX/DPCA/IF-only episodes ด้วย actual seconds กับช่างก่อนออก alert vote; ต้องมี independently reviewed cases/negative periods และ prospective holdout ใหม่

ข้อ 2 มี pure local screening implementation ใน `fit_profiles` ของ support script แล้ว ส่วนการ integrate เข้า Auto-Calibration registry/UI, learned phase/event-response policy และ activation ของ ML **ยังไม่ได้ทำในรอบนี้** ไม่มีการย้าย offline profile เข้า `ACTIVE_FROZEN`

## 6. Artifacts และการทำซ้ำ

- Protocol: `research/local_profile_model_selection_protocol_v1.json` ล็อกก่อนฝึก
- Intake/model trial: `notebooks/support/local_profile_model_selection.py`
- Presentation: `notebooks/support/local_profile_model_selection_presentation.py`
- Executed companion/export QA: `notebooks/support/execute_local_model_selection_notebook.py`
- Tests: `notebooks/support/test_local_profile_model_selection.py`
- Results: `notebooks/outputs/local_profile_model_selection_v1/`
- Frozen non-voting models: `shadow_model_bundle.joblib` กับ `offline_reference_profiles.joblib`
- Source rows/cache/model files อยู่ local outputs ไม่ได้ push ข้อมูลหรือ artifacts ใหญ่เข้า Git

Notebook รันกราฟ/ตารางและ hash checks จากการเทรนที่ execute แล้ว ไม่ได้ retrain ทุกครั้งที่เปิด การ rebuild มีคำสั่งชัดเจนใน notebook ต้องมี raw/cache ที่ระบุและ libraries ตรง manifest บน Colab ต้องวาง project/support/result files และตั้ง `PROJECT_ROOT`; ไม่ใช่ notebook ที่ download sensitive raw อัตโนมัติ

`mutations` ใน protocol ใช้คำย่อ “no Git changes” หมายถึงไม่มี Git operation/commit/push ไม่ใช่ห้าม local code/document authoring กติกาวิธีทดลอง/splits/parameters ไม่ได้เปลี่ยนหลังเห็นผล

คำสั่งจาก project root:

```powershell
python -X utf8 -m notebooks.support.local_profile_model_selection ingest --raw-root <raw_parquet_root>
python -X utf8 -m notebooks.support.local_profile_model_selection benchmark --raw-root <raw_parquet_root>
python -X utf8 -m notebooks.support.execute_local_model_selection_notebook
python -X utf8 -m pytest notebooks/support/test_local_profile_model_selection.py notebooks/support/test_october_three_machine_calibration.py -q
```

## 7. QA ที่ทำและสิ่งที่ยังพิสูจน์ไม่ได้

| QA ด้าน | ผล / ข้อจำกัด |
|---|---|
| System | No SQL/approval/runtime call; non-voting offline candidate path |
| Data | identity, empty days, precision, duplicate keys/gaps, retained states; **336 actual-source windows** เทียบ eligibility/features กับ runtime builder ผ่าน |
| Model | train-only fit; separate inner/calibration; seed/order recorded; joblib reload score difference = **0** |
| Evidence | Known owner cases ไม่แต่ง technician/cause labels; no verified-normal negative set; retrospective not new outer test |
| Presentation | 8 figures inspected; pressure scales separated, contributor-specific red, source-second/control strip, missing raw gap, explicit abstention; duplicate notebook images removed |
| Production | Batch inference 40.97s /1,507,132 rows (~.0272s/1,000 rows) บนคอมนี้ **ไม่ใช่ Server end-to-end benchmark**; Active/late-arrival/bridge/UAT ยังเปิด |
| Governance | Docs updated; frozen artifacts/status/limitations explicit; no auto-approval, no Server or Git operation |

20 local analysis tests passed; notebook 11/11 code cells executed, 0 errors. Raw MX080 forensic panel เทียบกับ ZIP means ผ่าน 107 complete qualified minutes (difference ≤1e-8); เป็น cross-source graph provenance QA เพิ่มจาก 336 runtime-builder comparisons ไม่มีการรับรอง false alarm rate, fault detection accuracy, leak diagnosis, safety, full-fleet generalization หรือ production readiness จากรอบนี้

## Research mapping

ผล trial ในเอกสารนี้มาจากข้อมูล local ไม่ใช่ค่าที่อ้างจาก paper แนว lag DPCA อ้าง [Ku et al. (1995)](https://doi.org/10.1016/0169-7439(95)00076-3); sensor-prediction ARX ไม่เท่ากับ fault classifier ตาม [Yan et al. (2014)](https://doi.org/10.1016/j.enbuild.2014.05.049); local unit/subfleet reference เชื่อมกับ [Farouq et al. (2022)](https://doi.org/10.1016/j.eswa.2022.116864). Library parameters ตรวจจาก official [Ridge](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.Ridge.html), [PCA](https://scikit-learn.org/1.8/modules/generated/sklearn.decomposition.PCA.html), [IsolationForest](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.IsolationForest.html) docs รุ่น 1.8 ที่ใช้จริง ขอบเขต literature access อื่นอยู่ใน research report ของวันที่ 1 ต.ค.

## Change log

- 2026-10-01 — Executed additional raw intake, local-reference screen, same-row Self/ARX/DPCA/IF trial, 5-fold adapted LOMO, known-case regression, eight-figure executed Notebook 08L and local QA. Kept frozen Self as primary; no runtime/Active/DB/Server/Git operation.
