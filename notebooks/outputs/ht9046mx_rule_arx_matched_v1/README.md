# Matched replay: กฎจากโปรไฟล์เทียบกับ Cold ARX v2

**วันที่วิเคราะห์:** 25 กันยายน 2026 · **สถานะ:** `DESCRIPTIVE_MATCHED_REPLAY_NOT_RELEASE_SELECTION`

## คำตอบสั้น

กฎเดิมที่ดูการเบี่ยงจาก baseline ของเครื่อง–โมดูลเองยังมีประโยชน์มาก: ในการทดลอง MX080/M6 กฎนี้และ ARX ต่างพบช่วงแรงดันสูงต่อเนื่องหลัง 7 ก.ย. 12:23:20 และต่างเปิด episode หลังครบสามหน้าต่างที่ 12:45. ARX **ไม่ได้พบหน้าต่างเพิ่มเติม** ในเคสนี้เมื่อใช้โปรไฟล์และหน้าต่างเดียวกัน. บน 12 เครื่อง development นั้น ARX พบเพิ่ม 451 หน้าต่างจาก 121,492 หน้าต่าง แต่การเปิด episode เมื่อใช้ OR เพิ่มจาก 595 เป็น 641; ยังไม่มี label ยืนยันว่า episode ที่เพิ่มเหล่านั้นมีประโยชน์หรือเป็นภาระการแจ้งเตือน. ดังนั้นให้คง Self/rule เป็นหลักฐานพื้นฐาน และให้ ARX เป็นหลักฐานเสริมใน shadow เท่านั้น ณ ตอนนี้.

กราฟทั้งสามอ่านได้โดยตรง:

1. `development_matched_flag_burden.png` — สีน้ำเงินคือสัดส่วนหน้าต่างที่กฎเดิม flag ในแต่ละเครื่อง; สีส้มคือ **เฉพาะ**หน้าต่างที่ ARX เพิ่มเข้ามา. ไม่ใช่ fault rate.
2. `development_lane_agreement.png` — สี่กลุ่มที่ไม่ซ้ำกันบนตัวหารเดียว 121,492 หน้าต่าง: neither, rule only, ARX only, both.
3. `mx080_m6_matched_timeline.png` — แรงดัน CP2, Self score และ ARX residual ในวันเดียวกัน. พื้นสีเทาคือ **ไม่มี qualified Cold window** จึงจงใจไม่ลากเส้นเชื่อมข้ามช่องว่าง; เส้นประแนวตั้งคือการเปลี่ยนของแรงดันที่สังเกตจาก log รายวินาที; เส้นประจุดแนวนอนคือ threshold ที่ล็อกไว้; ข้าวหลามตัดคือ episode opening หลังสามหน้าต่าง. Self score ถูก clip ที่ 25 จึงไม่ใช่กราฟ pressure แบน.

## วิธีเทียบที่ควบคุมให้ตรงกัน

หน่วยการให้คะแนนคือ `machine × module × qualified Cold five-minute window` เท่านั้น: Compressor ON, `Status_n=On`, `Busy_n=0`, `SV_n=Off`, state/quality gate และ lag ครบ. ไม่มีการเติม missing seconds หรือคะแนนให้ mixed/manual window. ทั้งสอง lane ใช้ **แถวเดียวกัน, local profile เดียวกัน, และ persistence สาม qualified windows ที่ห่างกันครั้งละ 5 นาที**; run ถูก reset เมื่อมีช่องว่าง. การเทียบนี้ไม่ใช่การรัน runtime rule-only worker ตัวจริงซ้ำ เพราะไม่ได้อ่าน MySQL `ACTIVE_FROZEN` และ threshold/profile ของ worker อาจต่างกัน.

สำหรับ feature \(j\) ในเครื่อง–โมดูล–SV–state เดียวกัน:

\[
z_{j,t}=\operatorname{clip}\!\left(\frac{x_{j,t}-\operatorname{median}_{\rm past}(x_j)}{s_{j,\rm past}},-25,25\right),\qquad
s^{(0)}_{j,\rm past}=\begin{cases}1.4826\operatorname{MAD}_{\rm past}(x_j),&\text{ถ้าค่านี้}>10^{-6}\\0.05,&\text{otherwise}\end{cases}.
\]

Self/rule ใช้ \(S_t=\max_j |z_{j,t}|\) ของ pressure, valve, temperature และ pressure differential รวม 9 feature; flag เมื่อ \(S_t\ge8.0\). สำหรับ Valve รุ่น v2 ใช้ \(s_{valve}=\max(s^{(0)}_{valve},1\text{ command count})\); feature อื่นใช้ \(s^{(0)}\). ARX-Ridge ใช้ CP1/Valve ปัจจุบันกับ CP2 และ Valve/temperature จาก lag 5 และ 10 นาทีใน Cold segment เดียวกัน เพื่อทำนาย `rz_hp2` และ `rz_lp2`; Dynamic score คือ \(D_t=\max(|z_{hp2,t}-\hat z_{hp2,t}|,|z_{lp2,t}-\hat z_{lp2,t}|)\), flag เมื่อ \(D_t\ge4.7410326466\). Ridge alpha = 10 มาจาก inner temporal validation; threshold มาจาก past calibration. Feature/profile/threshold versions คือ `cold-arx-causal-5m-valve-quantized-v2`, `cold-machine-module-sv-state-valve-quantized-v2`, `cold-past-calibration-q995-valve-quantized-v2`; model SHA-256 `ef6b27274012977bcc7d166e740fb18773236544465369352b648c3fba38ae12` และ profile SHA-256 `342ecf46e583747563548360b5d1d1abaa6ae8dc8462c19afdff103278ab4e6f`. โมเดล, scaler, alpha, profile, threshold และ persistence ถูกล็อกมาจาก candidate v2; รอบนี้ไม่ได้ fit/tune ใหม่. `either` คือ union ของ flag รายหน้าต่าง ก่อนทำ persistence จึงมี episode ที่สลับ lane กันได้.

## หลักฐานจาก 12 เครื่อง development

แหล่งข้อมูลคือ local `notebooks/outputs/ht9046mx_colab_analysis/cache/minute_module_state.parquet` (SHA-256 `65fbe69f62031ce6f8d0b5359430ea86bf87c1f5bbfad99f1290011c75daa9c9`). Split manifest ของ v2 ถูกตรวจให้ตรงกันก่อน replay. เปรียบเทียบเฉพาะ outer temporal block ที่เคยถูกเปิดดูแล้ว ระหว่าง **20 ส.ค. 2026 00:15 ถึง 1 ก.ย. 2026 17:05**, 12 development machines (`017, 022, 024, 029, 041, 057, 058, 070, 072, 081, 082, 083`), 74 machine-days, 121,492 matched windows. Timestamp ต้นทางไม่ encode timezone. Seven sparse machines ไม่อยู่ในตัวหารนี้เพราะไม่มี target profile ที่ผ่านเงื่อนไข.

| ผลรายหน้าต่าง (กลุ่มไม่ซ้ำ) | จำนวน | สัดส่วนของ 121,492 |
|---|---:|---:|
| ไม่ flag ทั้งคู่ | 99,401 | 81.82% |
| Self/rule เท่านั้น | 20,891 | 17.20% |
| ARX เท่านั้น | 451 | 0.37% |
| ทั้งคู่ | 749 | 0.62% |


## MX080 / Module 6: forensic probe แยกจาก fleet test


| ช่วง | Matched windows | Self flags | ARX flags | ARX-only | Persistent openings ของแต่ละ lane |
|---|---:|---:|---:|---:|---:|
| ก่อน observed transition 12:23:20 | 98 | 2 | 1 | 0 | 0 |
| หลัง observed transition | 137 | 137 | 137 | 0 | 1 |


## การตัดสินใจและงานถัดไป

- **ยังไม่เปลี่ยน** live scorer, Active Profile, threshold, Health Score, Alert หรือ Server deployment. Candidate v2 ยังคง `REVIEW_REQUIRED` / `SHADOW_ONLY_NOT_AUTHORIZED`.
- ก่อนจะพิจารณา ARX เป็น lane ส่ง alert จริง ต้องแก้ Self burden ที่มีมาตั้งแต่ past calibration, ยืนยัน service/regime/clock/unit context, ทดสอบบน fresh prospective holdout และเทียบกับ **approved** Active Profiles/worker ภายใต้ alert budget ที่เจ้าของระบบยอมรับ.
- ควรแสดง Self กับ Dynamic แยกกันใน shadow evidence; OR แบบง่ายอาจสร้าง mixed-lane persistence โดยไม่รู้ความหมายทางวิศวกรรม. ตัดสิน fusion policy จาก inner development/calibration และ predeclare ก่อนเปิดข้อมูลอนาคตใหม่.
- ไม่มีการพิสูจน์สาเหตุ, ความแม่นยำของ fault, production parity หรือความพร้อม launch จากผลย้อนหลังนี้.

## ทำซ้ำและ QA

จาก project root ที่มี local cache, original MX080 Parquet และ dependencies ตาม `apps/api/requirements.txt`:

```powershell
py -3 -X utf8 -m notebooks.support.compare_rule_arx_matched
py -3 -X utf8 -m notebooks.support.compare_rule_arx_matched --figures-only
```

สคริปต์ตรวจ source SHA-256, split manifest, candidate model/profile hashes และเทียบ episode counts กับ frozen candidate summary ก่อนเขียนผล. `summary.json` และ `development_matched_machine_rates.csv` เป็น aggregate ที่ส่งต่อได้; row-level score Parquet และ minute aggregate ของ MX080 อยู่ใน local ignored output เท่านั้น. รูปและรายงานเป็นหลักฐานประกอบการ review ไม่ใช่ production configuration. งานนี้ตรวจ system/data/model/evidence/presentation/production/governance ตาม `README_System.md` §21 โดยผล production QA ยัง **ไม่ผ่าน** เพราะไม่มี server/Active-Profile parity, rollback และ prospective shadow.

| QA ตาม README §21 | ผลรอบนี้ |
|---|---|
| System | รักษา CP1/CP2, Cold/SV-Off/Busy-0 gate และไม่ตีความแรงดันเป็นสาเหตุ |
| Data | ตรวจ cache SHA-256/split, source period/grain, MX080 quality-minute counts และช่องว่างที่ไม่มี qualified windows; timezone/unit ยัง unverified |
| Model | ใช้ frozen alpha/scaler/profile/threshold, ไม่ fit จาก outer/MX080, episode counts ตรงกับ candidate v2; outer เคย inspect จึงไม่เป็น independent test |
| Evidence | `summary.json` category sums และ Self/ARX counts reconcile; ไม่มี labels จึงรายงานเฉพาะ screening/alert burden |
| Presentation | ตรวจภาพ PNG ทั้งสาม; สัดส่วนมีตัวหาร, timeline ไม่เชื่อมข้าม gap และแยก flag จาก episode |
| Production | **ยังไม่ผ่าน:** ไม่มี approved Active-Profile parity, fresh prospective shadow, target-server replay, alert budget หรือ rollback acceptance |
| Governance | SOT/Project/Roadmap/Handoff/UX/AGENTS/graft และ Server guide อัปเดตโดยไม่เลื่อน phase หรือเปิด alert |

Local QA: `py -3 -m py_compile notebooks/support/compare_rule_arx_matched.py`, `py -3 -m pytest apps/api/tests -q` (**31 passed**), `git diff --check` ผ่าน; ตรวจ aggregate invariant `neither + rule-only + ARX-only + both = 121,492` ผ่าน. การรัน local นี้ไม่แทน independent review หรือ commissioning บน Server.
