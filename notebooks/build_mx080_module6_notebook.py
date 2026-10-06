"""Build the executed-reader notebook for MX-080 Module 6 one-second forensics."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks" / "07D_MX080_Module6_OneSecond_Forensics_Colab.ipynb"
SUPPORT = ROOT / "notebooks" / "support" / "mx080_module6_forensics.py"


def md(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text)


support_source = SUPPORT.read_text(encoding="utf-8")
notebook = nbf.v4.new_notebook()
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": TARGET.name, "provenance": []},
}
notebook["cells"] = [
    md(
        """# 07D — MX-080 Module 6: One-second forensic analysis

## tl;dr

ข้อมูล Module 6 วันที่ 3–6 กันยายนมี `Hp_2nd` ค่อนข้างคงที่ประมาณ 190.6 psi แต่เช้าวันที่ 7 ระบบเข้าสู่รอบ restart/pressure-balancing ซ้ำหลายครั้งและเกิด `ALM043` เจ็ดครั้ง หลัง 12:23:20 ค่า CP2 กลายเป็น high-pressure differential ต่อเนื่อง โดย `Hp_2nd` median ประมาณ 342.6 psi และเกิน 300 psi แทบทุกวินาทีที่ใช้ได้ในช่วงนั้น วันถัดมามี `ALM041 Compressor 2 over high pressure` ยืนยันสองครั้ง

สิ่งที่ข้อมูลสนับสนุนคือ **sequence เปลี่ยนจาก stable → balancing/restart → persistent CP2 high pressure** แต่ยังไม่สามารถระบุสาเหตุรากว่าเป็นน้ำยา, วาล์ว, condenser/facility water, sensor, relay หรือ logic ได้ และไม่ใช่หลักฐานยืนยัน refrigerant leak. กติกาหน้างานล่าสุดกำหนดช่วงอ้างอิง `Hp_2nd` ที่ผ่าน qualification เป็น 180–230 psi; ต่ำกว่า 180 เป็น low-side screening และสูงกว่า 230 เป็น high-side investigation คนละหลักฐานกัน

Notebook นี้คำนวณจาก record รายวินาทีจริง ภาพช่วงหลายวันจึงเกิด visual compression ตามจำนวน pixel ส่วนกราฟเหตุการณ์ขยายเวลาแสดงข้อมูลทุกวินาทีโดยไม่ resample."""
    ),
    md(
        """## Context & Methods

### คำถาม

Module 6 ของ HONTECH HT9046-MX เครื่อง MX-080 มีพฤติกรรมเปลี่ยนไปอย่างไรในช่วง 3–7 กันยายน 2026 และ MessageLog เชื่อมกับ pressure trajectory ได้หรือไม่?

### Key Assumptions

- เวลาใช้ Asia/Bangkok ตามบริบทโครงการ แต่ไฟล์ต้นทางไม่มี timezone จึงยังต้องให้เจ้าของเครื่องยืนยัน
- Pressure มี intended cadence 1 วินาที
- timestamp ที่ซ้ำและให้ค่าขัดกันถูกตัดออกทั้งกลุ่ม ไม่เลือกแถวใดโดยพลการ
- ไม่ interpolate เวลาที่ขาด; เส้นกราฟถูกตัดเมื่อมีช่องว่างมากกว่า 1 วินาที
- `Status_6` อ่านเป็น valve/control status ตาม Data Contract ไม่ใช่ electrical proof ว่าคอมเพรสเซอร์กำลังหมุน
- Temperature log แยก 20 ช่องยังไม่ผูกกับ Module 6 เพราะไม่มี channel mapping จึงไม่ฝืนรวมในกราฟนี้

### ชุดกราฟ

1. ภาพรวม 3–7 ก.ย. จาก one-second records
2. หน้าต่าง ALM043 วันที่ 7 เวลา 07:50–09:45 แบบ 1 วินาที
3. การเปลี่ยนเป็น persistent high CP2 เวลา 11:55–13:15 แบบ 1 วินาที
4. ALM041 วันที่ 8 เป็นหลักฐานหลังช่วงที่ผู้ใช้ระบุ ไม่ใช้สร้างข้อสรุปย้อนหลัง
5. ตรวจคำว่า water/tank/level/flow จาก MessageLogs ทุกไฟล์ที่ให้มาเพื่อทดสอบสมมติฐานเรื่องระบบน้ำ"""
    ),
    md("## Data\n\nแก้ path ใน cell ถัดไปเมื่อรันบน Colab/Google Drive ส่วนการรันในเครื่องนี้จะหาโฟลเดอร์ Desktop อัตโนมัติ"),
    code(
        """import os
from pathlib import Path
import json
import pandas as pd
from IPython.display import Image, display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / 'README_System.md').exists() and (PROJECT_ROOT.parent / 'README_System.md').exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
elif not (PROJECT_ROOT / 'README_System.md').exists():
    PROJECT_ROOT = Path('/content/drive/MyDrive/OPERATION_P')  # แก้เมื่อใช้ Colab

desktop_base = Path(r'C:\\Users\\Book\\OneDrive\\เดสก์ท็อป')
pressure_candidates = [
    Path(os.environ['MX080_PRESSURE_ROOT']) if os.environ.get('MX080_PRESSURE_ROOT') else None,
    desktop_base / 'Pressure - Copy' / '2026_09',
    PROJECT_ROOT / 'data' / 'mx080' / 'Pressure - Copy' / '2026_09',
]
message_candidates = [
    Path(os.environ['MX080_MESSAGE_FILE']) if os.environ.get('MX080_MESSAGE_FILE') else None,
    desktop_base / 'MessageLogs - Copy' / '2026_09_01.csv',
    PROJECT_ROOT / 'data' / 'mx080' / 'MessageLogs - Copy' / '2026_09_01.csv',
]
PRESSURE_ROOT = next((path for path in pressure_candidates if path and path.exists()), None)
MESSAGE_FILE = next((path for path in message_candidates if path and path.exists()), None)
if PRESSURE_ROOT is None or MESSAGE_FILE is None:
    raise FileNotFoundError(
        'ไม่พบ MX-080 logs: บน Colab ให้ mount Google Drive แล้ววางไฟล์ใต้ '
        'OPERATION_P/data/mx080/ หรือกำหนด MX080_PRESSURE_ROOT และ MX080_MESSAGE_FILE'
    )
OUTPUT_ROOT = PROJECT_ROOT / 'notebooks' / 'outputs' / 'mx080_module6_forensics_v2_hp180'

print('Pressure:', PRESSURE_ROOT)
print('Messages:', MESSAGE_FILE)
print('Output:', OUTPUT_ROOT)"""
    ),
    md("### 1. Load the reproducible analysis code"),
    code("analysis_namespace = {'__name__': 'mx080_module6_embedded'}\nexec(" + repr(support_source) + ", analysis_namespace)\nprint('Analysis functions loaded.')"),
    md("### 2. Execute from raw logs"),
    code(
        """AnalysisConfig = analysis_namespace['AnalysisConfig']
run_analysis = analysis_namespace['run_analysis']

result = run_analysis(AnalysisConfig(
    pressure_root=PRESSURE_ROOT,
    message_file=MESSAGE_FILE,
    output_root=OUTPUT_ROOT,
))
summary = result['summary']
display(pd.Series(summary).drop(labels=['figures']))"""
    ),
    md("### 3. Data-quality gate"),
    code(
        """quality = result['quality'].copy()
display(quality[['date','raw_rows','duplicate_timestamps_excluded',
                 'conflicting_duplicate_timestamps','usable_unique_seconds',
                 'coverage_pct','missing_expected_seconds']].round(2))

assert quality['usable_unique_seconds'].gt(0).all()
assert quality['coverage_pct'].between(90, 100).all()
assert result['snapshots'].loc[result['snapshots']['code'].isin(['ALM043','ALM041']), 'Hp_2nd_6'].notna().all()
print('QA checks passed: source days present, coverage bounded, alarm timestamps matched exactly.')"""
    ),
    md("## Results\n\n### 4. ภาพรวม 3–7 กันยายน\n\nพื้นที่สีแดงอ่อนคือช่วง balancing/restart และสีทองอ่อนคือช่วง high CP2 ต่อเนื่อง กราฟใช้ข้อมูลรายวินาที แต่ช่วง 5 วันถูกบีบตามความกว้างของภาพ จึงใช้กราฟขยายในส่วนถัดไปสำหรับอ่านลำดับเหตุการณ์"),
    code("display(Image(filename=str(result['figure_paths']['overview'])))"),
    md(
        """**วิธีอ่าน:** วันที่ 3–6 และก่อน 08:00 วันที่ 7 เส้น Hp/Lp ของ CP2 แยกกันค่อนข้างคงที่ เช้าวันที่ 7 เส้นเข้าหากันระหว่างการ balancing/restart หลายรอบ ต่อมาหลัง 12:23 เส้นแยกออกด้วย differential สูงกว่าช่วงอ้างอิงอย่างชัดเจน

แถบสีเขียว 180–230 psi เป็นช่วงอ้างอิงหน้างานสำหรับข้อมูลที่ผ่าน qualification ไม่ใช่ universal safety band และใช้ตัดสินไม่ได้ใน mixed/start/stop state. ค่าต่ำกว่า 180 เป็น undercharge screening เท่านั้น ส่วนค่ามากกว่า 230 ต้องตรวจเป็น high-side deviation แยกต่างหาก."""
    ),
    md("### 5. ALM043 ซ้ำในช่วง pressure-balancing — ทุก 1 วินาที\n\nเส้นแดงคือ `ALM043 Model06`; เส้นเทาประคือ DAQ/network/reboot context"),
    code("display(Image(filename=str(result['figure_paths']['balancing'])))"),
    md(
        """**ข้อสังเกต:** alarm แรกเกิดขณะ CP2 differential ลดลงมาก และ alarm หลังจากนั้นส่วนใหญ่เกิดเมื่อ `Hp_2nd` กับ `Lp_2nd` เกือบเท่ากัน พร้อม `Valve_6=0`, `Status_6=ChangeValve` และ `Busy_6=1` ตาม log พฤติกรรมนี้สอดคล้องกับรอบ control/start attempt มากกว่าการทำงาน steady-state

ความหมาย `Busy_6` ใน README ควรถูกตรวจจาก PLC codebook เพิ่ม เพราะในข้อมูลจริงค่า 1 เกิดพร้อม `ChangeValve` อย่างสม่ำเสมอ จึงอาจเป็น busy flag ของ sequence/valve ไม่ใช่ proof of compressor rotation."""
    ),
    md("### 6. เปลี่ยนเป็น persistent high CP2 — ทุก 1 วินาที"),
    code("display(Image(filename=str(result['figure_paths']['high_pressure'])))"),
    md(
        """**ข้อสังเกต:** หลัง 12:23:20 ค่า `Hp_2nd_6` ไม่ได้สูงเพียง spike เดียว แต่คงอยู่ในช่วงสูงต่อเนื่อง ขณะที่ `Lp_2nd_6` กลับอยู่แถว high-20 psi ทำให้ ΔP สูงประมาณ 315 psi โดย median ช่วงนี้ การคงอยู่ต่อเนื่องมีน้ำหนักมากกว่าการตัดสินจาก sample เดียว แต่ยังไม่ระบุ root cause."""
    ),
    md("### 7. หลักฐานวันถัดมา — ใช้ยืนยันพฤติกรรม ไม่ใช้เลือก threshold"),
    code("display(Image(filename=str(result['figure_paths']['followup'])))"),
    md("### 8. ตารางเปรียบเทียบช่วง"),
    code("display(result['period_summary'].round(2))"),
    md("### 9. ตรวจสมมติฐาน MessageLog เรื่องระบบน้ำ"),
    code(
        """display(result['water_messages'])
display(result['water_snapshots'][['timestamp','code','message','pressure_timestamp','pressure_lag_seconds','Status','Hp_1st_6','Hp_2nd_6','pressure_match_status']])
print('Water-keyword messages during 3–8 Sep:', summary['water_keyword_messages_sep3_to_sep8'])"""
    ),
    md(
        """**ผลตรวจ:** ไม่พบข้อความ water/tank/level ในช่วง high-pressure episode วันที่ 3–8 ก.ย. จาก MessageLogs ที่ให้มา พบเพียง `ALM004 Water flow error!! [IN]` เมื่อ 30 ส.ค. หนึ่งครั้ง และค่าก่อน event หนึ่งวินาทีของ Module 6 คือ `Hp_2nd_6 ≈ 213.9 psi` ระหว่าง Run/Stop transition. ตัวอย่างเดียวและ state ที่ไม่ steady จึงยืนยันหรือหักล้างสาเหตุไม่ได้ โดยเฉพาะข้อความ *Water level in tank near full* ที่ผู้ใช้จำได้นั้นไม่ปรากฏในไฟล์ปัจจุบัน."""
    ),
    md("### 10. ค่าตรงวินาทีของ event ที่เกี่ยวกับ Module 6"),
    code(
        """events = result['snapshots'].copy()
events['timestamp'] = pd.to_datetime(events['timestamp'])
display(events.loc[events['timestamp'].ge('2026-09-07'), [
    'timestamp','code','message','Hp_2nd_6','Lp_2nd_6','dp_2nd_6',
    'Valve_6','Status_6','SV_6','Busy_6'
]].round(2))"""
    ),
    md(
        """## Takeaways

1. **ช่วงอ้างอิง 3–6 ก.ย.** — `Hp_2nd_6` median 190.6 psi, ช่วง q05–q95 ประมาณ 189.6–191.3 psi จึงอยู่ภายในช่วงอ้างอิงหน้างาน 180–230 psi และไม่พบ sample ที่เกิน 300 psi หลังตัด timestamp ซ้ำ
2. **เช้า 7 ก.ย.** — เกิด ALM043 เจ็ดครั้งระหว่างหลายรอบ balancing/restart โดย state ไม่ใช่ steady operation จึงห้ามนำไปสร้าง normal baseline หรือใช้กฎ undercharge
3. **หลัง 12:23:20 วันที่ 7** — `Hp_2nd_6` median 342.6 psi, q05–q95 ประมาณ 339.1–352.5 psi และเกิน 300 psi 99.98% ของวินาทีที่ใช้ได้ ลักษณะนี้เป็น persistent regime change ไม่ใช่ spike เดี่ยว
4. **วันที่ 8** — ALM041 ระบุ `Compressor 2 over high pressure` ที่ 392.2 และ 380.0 psi สนับสนุนว่าพฤติกรรม high CP2 ต่อเนื่องเข้าสู่ alarm จริง
5. **ช่วยอะไรได้:** ระบุช่วงเวลาตรวจสอบช่างได้แคบลง, สร้าง exclusion windows สำหรับ baseline/ML, ใช้เป็น candidate incident label และออกแบบ alarm persistence ได้
6. **สมมติฐานระบบน้ำ:** ไม่มี water/tank/level message ในช่วง 3–8 ก.ย.; log มี Water flow error เพียงหนึ่งครั้งในวันที่ 30 ส.ค. จึงยังเชื่อม `Hp_2nd > 230` กับท่อน้ำ/ระดับ tank แบบ causal ไม่ได้
7. **ยังพิสูจน์ไม่ได้:** refrigerant leak/charge, valve/check-valve fault, condenser/facility-water issue, sensor error, relay/electrical failure หรือ PLC timing ต้องตรวจร่วมกับ service record, current/relay feedback, water telemetry และ P&ID

### Technician check package ที่แนะนำ

- ตรวจ sequence และ relay/timer ของ CP2 โดยเฉพาะเพราะ MessageLog มี `start relay timer setting too short` ตั้งแต่ 2 ก.ย.
- ตรวจ pressure sensor ทั้ง high/low และ equalization/bypass path ก่อนเปลี่ยน charge
- ตรวจ condenser/facility-water condition ในช่วงหลัง 12:23 วันที่ 7
- เก็บ current feedback ของ CP1/CP2 และผลตรวจจริงเป็น maintenance label

### Sources used for interpretation

- HON Precision related tri-temperature handler family: https://www.honprec.com/en/products/?index_a_go=Y&index_m_blink=501
- Danfoss compressor pressure-equalization/start guidance: https://assets.danfoss.com/documents/latest/50920/AX268748862633en-000301.pdf
- Advantech APAX I/O documentation: https://advdownload.advantech.com/productfile/Downloadfile4/1-1EAYN81/APAX-5000_Series_User_Manual_V2.0%28EN%29.pdf"""
    ),
]

nbf.write(notebook, TARGET)
print(TARGET)
