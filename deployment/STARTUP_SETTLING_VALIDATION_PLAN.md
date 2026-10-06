# ตรวจช่วงเริ่มทำงานก่อนเปลี่ยน steady-state detector

วันที่ 1 ตุลาคม 2026 · สถานะ: แผนการทดลอง ไม่ใช่กฎที่เปิดใช้งานแล้ว

## เป้าหมายและสิ่งที่ทำแล้ว

เจ้าของโครงการชี้ว่าช่วงแรกของ MX080/M6 ยังทำงานปกติ แต่ candidate เตือน ข้อมูลนี้ใช้เปิดประเด็น normal-transition validation ไม่ใช้ปรับ threshold แล้วย้อนประกาศว่าผ่านการทดสอบ กราฟ Dashboard ปรับแล้วให้แถบแดงระบุเฉพาะตัวแปรใน panel ที่เข้าเงื่อนไข `|z_j| >= threshold` ระหว่าง **ผลรวม** persistent; ผลรวมยังอยู่ใน score panel ทุกคะแนน/flag/Profile เดิมคงอยู่

เวลา 7 Sep 2026 12:10 Asia/Bangkok มี TempLo z=189.25 เป็น dominant แต่แรงดันบางตัวก็เกิน local envelope จริง เช่น Hp_2nd z=11.31 ขณะที่ค่าที่วัดได้ 196.72 อยู่ใน field reference 180–230. การลบแถบ pressure ทั้งหมดหรือแสดงเฉพาะ dominant จึงทำให้หลักฐานหาย ส่วน candidate มีสี่วันและไม่ใช่ reviewed Active Profile

สิ่งที่ยังไม่ได้ทำ: multi-start dataset, fitted settling/startup limits, profile regeneration, new state/feature version, detector gating change, Active approval และ Server deployment

## 1. แยกเหตุการณ์จาก raw seconds ก่อน

ใช้ข้อมูลต้นทางเรียงตามเวลา `machine × physical module` เก็บ timezone/units/state mapping และ source hash ให้ครบ ไม่ interpolate missing seconds และไม่เรียก sample ทุกวินาทีว่าเป็น independent start

ต้องแยกชนิดเหตุการณ์อย่างน้อย:

| Event | หลักฐาน | สิ่งที่ไม่ควรเหมารวม |
|---|---|---|
| Observed compressor start | `Status` ที่ map แล้วเปลี่ยน OFF→ON พร้อม preceding coverage | ช่วงแรกของไฟล์ที่ ON อยู่แล้วไม่ใช่ observed start |
| Cold/control entry | เข้า `Status=ON, Status_n=On, Busy_n=0, SV_n=Off` | SV On→Off ไม่ได้พิสูจน์ว่า motor restart ทุกครั้ง |
| Post-manual re-entry | Busy=1/ChangeValve/MValveHome แล้วกลับเข้าสถานะ qualified | ไม่ใช่ service/refill ที่ยืนยัน และไม่เหมือน normal restart อัตโนมัติ |
| Unknown/censored transition | gap หรือเริ่ม/จบไฟล์กลาง cycle | ไม่เดา onset/เวลาหยุดเพื่อเติม event ให้ครบ |

แยกรอบเปิดเครื่องหลังหยุดนานกับกลับมารันหลังหยุดสั้น โดยใช้ elapsed OFF ที่สังเกตจริงและ initial temperatures เป็น covariates ไม่กำหนดช่วงเวลาตายตัวก่อนเห็น distribution. Recipe/load/water ถ้ามีให้ใช้เป็น context; ถ้าไม่มีให้ระบุ missing context แทนการตั้งชื่อ Hot/Room จาก SV เพียงอย่างเดียว

เก็บ start ID, machine/module, event type, source/availability time, last observed OFF, initial temperatures/pressures/Valve, manual/alarm markers, gaps และ review status. เริ่มสำรวจ 10–20 independent starts ต่อบริบทข้ามหลายวันได้ แต่เป็น exploration target ไม่ใช่เกณฑ์อนุมัติ: หากไม่ครอบคลุมระยะ OFF/initial temperature/วัน ให้เก็บเพิ่มแม้มีจำนวนครบแล้ว

## 2. นำหลายรอบมาวางบนแกนเวลาเดียวกัน

ตั้ง `elapsed_seconds = recorded_at - observed_start_at` ให้ t=0 เป็นจุดเริ่มที่เห็นจริง แสดง raw-second trajectories แยก pressure/temperature/differential/Valve/control state ไม่รวมต่างหน่วยในแกนเดียว

กราฟที่ใช้ตรวจ:

1. เส้นแต่ละรอบสีอ่อน + median trajectory/empirical Q10–Q90 จาก reference runs ที่ทบทวนว่าเป็น normal candidate พร้อมจำนวนรอบที่ยังมีข้อมูลในแต่ละ elapsed time; band คือ observation spread ไม่ใช่ confidence interval
2. แผนภาพ cycle × elapsed time ของ slope/variation เพื่อดูว่ารอบใด settle ช้าหรือไม่ settle
3. Distribution ของ settling duration แยก machine/module/event context พร้อม left/right-censored counts
4. เทียบ detector flags เดิมกับ proposed regime/quality รอบเดียวกัน รวม known anomalies MX080/M6 และ MX057/M1; ไม่ทิ้งช่วงที่ไม่ถูก score ออกจาก denominator

ใช้ median across **cycles** ก่อนสรุป fleet เพื่อไม่ให้ cycle ยาวหรือเครื่องข้อมูลมากครองน้ำหนัก หากยืนยัน normal startup ยังไม่ได้ ให้เรียก reference ว่า unverified candidate ไม่ใช่ equipment-healthy label

## 3. ตรวจว่าหยุดเปลี่ยนเร็วหรือยัง ไม่ใช่ดู ON อย่างเดียว

สำหรับ feature j ใช้ trailing window ที่สิ้นสุด ณ เวลาปัจจุบันเท่านั้น เช่น robust slope แบบ Theil–Sen:

$$S_j(t)=\operatorname{median}_{a<b\in[t-W,t]}\frac{x_j(b)-x_j(a)}{b-a}$$

และ robust variation:

$$V_j(t)=1.4826\operatorname{median}_{u\in[t-W,t]}|x_j(u)-\operatorname{median}(x_j)|$$

ทำเช่นเดียวกับ `dp1=hp1-lp1`, `dp2=hp2-lp2` และตรวจ control-state continuity, coverage, recent manual/Valve boundaries. เริ่มทดลอง W=2/3/5 นาทีและจำนวน stable windows L=2/3/5 ใน **inner temporal validation** ได้; ยังไม่เลือกค่าและไม่เปิดใช้จากกราฟ MX080 ที่ดูแล้ว เวลา/หน่วยในสมการต้องคงที่ เช่น °C/min หรือ source-pressure-unit/min

Proposed settling ต้องครบสามส่วน:

- สถานะ/คุณภาพข้อมูลต่อเนื่อง และมี trailing history พอ
- `|S_j| <= a_j` และ `V_j <= b_j` ต่อเนื่อง L windows โดย a/b fit จาก reviewed **past reference** เท่านั้น
- ระดับและความสัมพันธ์เข้ากับ comparable steady reference; หากค่าหยุดไหลแต่ค้างที่ระดับผิดปกติ ให้เป็น `SETTLED_REVIEW` ไม่ใช่ normal หรือ baseline ใหม่

สำคัญ: ช่วง high-pressure ของ MX080 อาจนิ่งที่ระดับผิดปกติ การใช้ slope ต่ำอย่างเดียวจะทำให้หลุดตรวจ ต้องใช้ level/relationship evidence ต่อ ไม่ reset ระดับปกติตาม plateau ปัจจุบัน

## 4. วิธีใช้เมื่อรันจริงในอนาคต

```text
Observed transition + good source coverage
       ↓
STARTUP / SETTLING (retain measurements and old shadow scores)
       ├─ normal trajectory reference available → compare elapsed-time trajectory
       ├─ missing/ambiguous context → UNKNOWN, not green/healthy
       ├─ no settle / incompatible plateau → STARTUP_REVIEW / SETTLED_REVIEW
       └─ state + slope + variation + comparable level qualified
                     ↓
             STEADY Cold → frozen steady Profile → existing z/persistence
```

ไม่มีการปิดการตรวจทุกอย่าง 10–15 นาทีแบบ blanket suppression. Preserve existing PLC/message/safety notifications and supported severe-deviation evidence; 180–230 เป็น qualified field reference ไม่ใช่ certified safety limit. หากยังไม่มี startup reference อย่าสร้างเปอร์เซ็นต์ความปกติหรืออ้างว่า low steady-profile specificity ถูกแก้แล้ว

Startup envelope สามารถทำแบบ robust elapsed-time profile โดยไม่ต้องฝึก LSTM: median/MAD trajectory ตาม elapsed time และบริบท พร้อม scale floors/coverage. Maximum expected settling duration fit จาก normal-candidate cycle distribution; timeout เป็น review evidence ไม่ใช่ physical-fault diagnosis. Sampling ที่มีแต่ minute aggregate ไม่สามารถ reconstruct raw-second transient; ยังใช้ trailing-minute settling evidence ได้แต่ต้องบอกความละเอียด

## 5. Validation และเกณฑ์ตัดสินก่อนเปลี่ยน Profile

- แบ่ง train/inner/calibration/future holdout ตามทั้ง **cycle/day**; ไม่แยกวินาทีจากรอบเดียวกันไว้คนละ split และไม่ใช้ future tail เพื่อบอก steady ย้อนหลังใน online result
- Fit phase parameters/scales/trajectory จาก past reference; เลือก W/L/limits ภายใน development; inspected MX080 first-band เป็น diagnostic regression ไม่ใช่ untouched outer test
- ตรวจ future normal starts และ cross-machine/module contexts ที่ไม่ได้ใช้ fit: alert episodes per start/day, STARTUP/UNKNOWN coverage, censored counts, duration-to-score และ worst-context result
- ตรวจ known anomaly regression: ยังตรวจ MX080 sustained high-pressure และ MX057 persistent shift ได้ไหมและช้ากว่าเดิมเท่าไร; ใช้ source-onset กับ five-minute delivery availability แยกกัน
- ใช้ cycle/day block bootstrap เมื่อสรุป uncertainty; seconds/minutes ในรอบเดียวกันมี autocorrelation จึงไม่สุ่มเป็น independent units
- ถ้าหลักฐานไม่พอ ให้คง review/unsupported context ไม่ auto-adopt abnormal plateau. ปรับ feature/state/profile versions → candidate ใหม่ → future 3-day shadow → manual approval; ไม่แก้ Active เดิมแบบ in-place

## 6. เหตุผลและแหล่งอ้างอิง

NIST อธิบาย process stability โดยระดับและความแปรปรวนที่ไม่เปลี่ยนตามเวลา และแนะนำตรวจ control runs ใน operating recipe ที่เทียบกันได้ หลักนี้รองรับการไม่เทียบ warm/transition กับ steady baseline โดยไม่แยกบริบท แต่ **ไม่ได้กำหนด** W/L/จำนวน starts สำหรับ HT9046MX; แผนและสูตรข้างต้นเป็น proposed engineering method ที่ต้องตรวจข้อมูลจริง

- [NIST — Assessing Process Stability](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm)
- [NIST — Is the process stable?](https://www.itl.nist.gov/div898/handbook/pri/section2/pri22.htm)
- [Zhang / NIST — Statistical Process Monitoring for Autocorrelated Data](https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data): cautions against assuming process samples are independent

## Change log

- 2026-10-01 — Documented owner-requested multi-start investigation method and completed contributor-aware Dashboard presentation. No fitted startup limit, scorer/Profile change, retraining, database write or Server action.
