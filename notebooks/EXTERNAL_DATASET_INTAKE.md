# ข้อมูลเพิ่มเติมจาก Data Analysis

Updated: 2026-09-10, Asia/Bangkok

Notebook: `07B_HT9046MX_External_Dataset_Intake_Colab.ipynb`


ตัวนำเข้า `support/external_dataset_intake.py` อ่านไฟล์รายวันจาก MX_007,
MX017, MX057, MX070, Clean Data MX12 และ Clean Data MX25 รวม daily logs
ภายใน ZIP ของ MX057 แล้วเขียนผลแยกใน `outputs/ht9046mx_external_intake_v2/`.
ไฟล์ต้นทางไม่ได้ถูกแก้ไข ตัวแปลงไม่ fit baseline หรือ model และไม่เปลี่ยน
outer-test allocation ของการทดลองเดิม

| แหล่งข้อมูล | Canonical machine | บทบาทของข้อมูลเพิ่ม |
|---|---|---|
| MX_007 | 007 | ศึกษาเครื่องที่ไม่อยู่ใน primary 19 เครื่อง; retrospective external evidence |
| Clean Data MX12 | 012 | เช่นเดียวกับ 007; ตรวจ cleaning provenance และ service epoch ก่อน calibration |
| Clean Data MX25 | 025 | เช่นเดียวกับ 012; เก็บ anomaly/service hypothesis เป็น unknown จนช่างยืนยัน |
| MX017 | 017 | ขยายประวัติย้อนหลัง; ตัด timestamp ที่มีใน primary แล้ว |
| MX057 รวม ZIP | 057 | ขยายประวัติย้อนหลัง; ตัด timestamp ที่มีใน primary แล้ว |
| MX070 | 070 | ขยายประวัติย้อนหลัง; แยก temporary copies ออก |

เครื่อง 007/012/025 เคยอยู่ในงานและ artifacts ของ Data Analysis เดิม จึงเรียกได้ว่า
เป็น blind test ของ historical shared LSTM ที่เคยฝึกด้วยเครื่องเหล่านี้

## การแปลงและข้อมูลซ้ำ

หนึ่งแถว canonical เป็นหนึ่ง machine–timestamp พร้อม 8 modules ตาม wide schema.
วันที่จากชื่อไฟล์ถูกตรวจเทียบวันที่ในเนื้อหา ค่า pressure/temperature คงสเกลต้นทาง
โดย `TempHi`/`TempLo` คง tag เดิมตาม mapping ของ README.

ตัวนำเข้าเทียบวันซ้อนกับ primary ครบ 81 tags หลัง normalize whitespace และ numeric
type. Timestamp ที่มีใน primary แล้วถูกกันออกจาก novel partitions ไม่ว่าจะเท่ากัน
หรือขัดแย้ง โดยบันทึกจำนวนแต่ละแบบ ถ้า primary key ซ้ำแบบค่าขัดแย้งจะนับ unresolved.
ภายในไฟล์ source, exact duplicate ถูกลดเหลือหนึ่งแถว ส่วน timestamp ที่มีหลายค่า
ถูก quarantine ทั้ง key; raw ยังอยู่ครบสำหรับตรวจสอบ

Minute output เก็บค่าจุดสุดท้ายในนาทีเช่นเดียวกับ cache เดิม พร้อม `available_at`,
แล้วทิ้ง gate columns เพราะนาทีที่มีหลาย state อาจถูกเข้าใจว่าเป็น steady state.
EDA quality minute ต้องมี 55–60 วินาที, ช่องว่างภายในไม่เกิน 5 วินาที,
Run/On/Busy=0/Valve≥0 และ SV คงเดิม. กฎนี้สะท้อน cadence ที่มี one-second gap
เป็นครั้งคราว และมีไว้เพื่อการสำรวจ/visualization เท่านั้น ยังต้องผ่าน
settling/service exclusion ก่อนใช้สร้าง baseline หรือ train

## ผลตรวจรับ v2

ตรวจ daily telemetry 354 ไฟล์ ได้ 29,819,668 wide rows; เขียน novel canonical rows
28,214,027 แถว. มี 1,389,587 timestamp ซ้อนกับ primary และตรงกันครบทั้ง 81 tags
ไม่มี cross-source conflict. หลังลด exact duplicate และ quarantine source timestamp ที่มี
หลายค่า จะเหลือ minute-module 3,839,048 แถว โดย 2,651,784 แถวผ่าน EDA quality gate.
`partition_qa.json` รายงาน `PASS_WITH_CAVEATS`; Notebook 07B รันครบโดยไม่มี cell error.

## ผลลัพธ์และทางเชื่อม

- `source_manifest.csv`: แหล่งข้อมูล, SHA-256, role, counts, period, overlap และ error
- `archive_inventory.csv`: ZIP members และ key สำหรับค้นใน manifest
- `canonical_novel/`: Parquet ระดับวินาทีที่เพิ่มจาก primary จริง ใช้ต่อสำหรับ event/window analysis
- `external_minute_module_state.parquet`: minute input สำหรับ EDA และ candidate screening
- `daily_module_sv_pressure.csv`: daily Hp_2nd summaries แยก machine/module/SV พร้อม denominator
- `minute_valve_lp2_correlations.csv`: ความสัมพันธ์ที่ Notebook คำนวณจาก EDA quality minutes
- `all_sensor_pair_correlations.csv`: คู่ความสัมพันธ์ sensor ทั้งเจ็ด ครบทุก machine/module/SV ที่มีข้อมูล พร้อมจำนวน minutes/days
- `analysis_summary.json`, `artifact_checksums.json`, `notebook_qa.json`: หลักฐานผลรันและ QA
- `figures/`: กราฟสำหรับนำเสนอ

## ข้อจำกัดสำหรับ ML รุ่นถัดไป

ยังไม่ยืนยัน timezone, psig/psia, service/refill epoch และ healthy labels.
ข้อมูล Static, event fragments และ temporary copies จึงแยกสำหรับ review ตามบริบท.
Prepared windows เดิมไม่ใช่ข้อมูลใหม่ มีทั้ง overlap windows และ cap จำนวนไฟล์/window;
ต้องเริ่มจาก canonical source และประกาศ split ใหม่ก่อนทดลอง

จาก `prepared_dataset/shared_full_v2/manifest.json` เดิม มี 60-second windows
155,309 รายการจาก 42 machine-module groups, 24 features, stride ตาม config 5 วินาที,
จำกัด 10 ไฟล์ต่อเครื่องและสูงสุด 5,000 windows ต่อ group. ชุดเหล่านี้ไม่ใช่
155,309 independent events. Historical LSTM manifest ระบุหกเครื่องเดียวกับ
external intake และมี source fragments ที่อ่านไม่สำเร็จ 3 ไฟล์ จึงไม่ใช้
artifact เดิมเป็นหลักฐานว่าข้อมูลเพิ่มทั้งหมดผ่าน QA หรือ model generalization แล้ว

การวิเคราะห์ข้อมูลเพิ่มหลังได้เห็น outer test รุ่นเดิมแล้ว ใช้เป็นการออกแบบการทดลอง
เป็นผลยืนยันอิสระ. Sequence coverage และ Auto-bootstrap acceptance ต้องวัดใหม่
จากข้อมูลที่ผ่าน gate; จำนวนวินาทีที่มากขึ้นไม่พิสูจน์ว่า opening/SV On เพียงพอ

## รันซ้ำ

```powershell
python notebooks/support/external_dataset_intake.py --external-root 'C:/path/to/Data Analysis' --primary-root 'HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings' --output 'notebooks/outputs/ht9046mx_external_intake_v2'
python -m unittest notebooks.support.test_external_dataset_intake
python notebooks/build_external_intake_notebook.py
python -m jupyter nbconvert --execute --to notebook --inplace notebooks/07B_HT9046MX_External_Dataset_Intake_Colab.ipynb
```

บน Colab ใช้ตัวนำเข้าที่ฝังใน Notebook ตั้ง source roots เป็นโฟลเดอร์ Drive
และเปิด `REBUILD_RAW=True` หากต้องการตรวจ raw ใหม่ เก็บ output root แยกจาก source.
เมื่อ rerun หลังแก้ parser ให้ใช้ output version ใหม่สำหรับงานที่เผยแพร่ไปแล้ว
