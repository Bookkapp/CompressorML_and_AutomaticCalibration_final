"""Build the Colab-ready Phase 7 deterministic shadow replay notebook."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "07_HT9046MX_Server_Shadow_Replay_Colab.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": OUTPUT.name, "provenance": []},
}
nb["cells"] = [
    md(
        """
# 07 — HONTECH HT9046-MX Server Shadow Replay

## tl;dr

Phase 7 replay รุ่น `hp180` ใช้ `ARX-Ridge__seed_13` ซึ่งยังชนะ **inner temporal validation** หลังเปลี่ยน field rule เป็นช่วง 180–230 psi. Threshold 7.6507 มาจาก calibration block ในอดีต และใช้ persistence 3 หน้าต่างต่อเนื่องที่ cadence 5 นาที

- Primary outer replay: 131,853 score rows, raw flag rate 0.394%, persistent alerts 36 ครั้ง หรือ 0.456 alerts ต่อ machine-day
- Restart/checkpoint replay ให้ผลตรงกับ one-shot replay
- MX-080 Module 6 มี raw deviation ก่อน transition ที่มองเห็น และเปิด persistent alert เวลา 12:35 วันที่ 7 ก.ย.; เวลานี้เป็น descriptive replay timing ไม่ใช่ validated fault lead time
- MX-080 raw flag rate ก่อน transition เท่ากับ 3.0% (100 scored rows) และหลัง transition เท่ากับ 100% (139 scored rows); เป็น sensitivity evidence ของเหตุการณ์เดียว ไม่ใช่ accuracy
- Reference ของ MX-080 มีเพียง 4 วัน จึงเป็น `INCIDENT_REPLAY_ONLY_INSUFFICIENT_FOR_PRODUCTION`
- ผลยังเป็น anomaly-screening evidence ไม่ใช่ fault accuracy และยัง deploy production ไม่ได้เพราะไม่มี rollback target/alert budget/confirmed labels
"""
    ),
    md(
        """
## Context & Methods

### Key Assumptions

- ไม่เลือก model, feature, threshold หรือ persistence จาก outer test หรือ MX-080
- Primary replay ใช้ qualified minute stream แล้ว score ทุก 5 นาทีตามลำดับเวลา
- MX-080 ใช้ Pressure รายวินาทีสร้าง minute stream และ 30/120-second ring-buffer features; ไม่ใช้ MessageLog เป็น feature
- Missing, stale, out-of-order, wrong feature version/order และ checksum mismatch ต้อง fail closed เป็น data/contract status ไม่ใช่ equipment alert
- `Busy_n` ไม่ใช่ compressor-run proof; ใช้ state gate ตาม Data Contract ปัจจุบันเท่านั้น
- Timezone เป็น Asia/Bangkok ตามบริบท แต่ source ไม่ encode timezone
- Persistence 3 × 5 นาทีเป็น pilot policy ที่ยังต้องผ่าน operations alert-budget review
- `Hp_2nd < 180 psi` เป็น low-side screening feature; `Hp_2nd > 230 psi` ยังถูกจับได้ผ่าน local/multivariate deviation แต่ไม่ถูกแปลเป็น undercharge หรือปัญหาระบบน้ำอัตโนมัติ
"""
    ),
    md("## Data\n\n### 1. Load project and dependencies"),
    code(
        """
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

required = {
    'pandas': 'pandas>=2', 'numpy': 'numpy>=1.26', 'polars': 'polars>=1',
    'sklearn': 'scikit-learn>=1.4', 'joblib': 'joblib>=1.3',
    'matplotlib': 'matplotlib>=3.8', 'pyarrow': 'pyarrow>=15'
}
missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
if missing:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *missing])

import pandas as pd
from IPython.display import Image, display

override = os.environ.get('HT9046MX_PROJECT_ROOT', '').strip()
candidates = [Path(override)] if override else []
candidates += [Path.cwd(), Path.cwd().parent, Path('/content/OPERATION_P'), Path('/content/drive/MyDrive/OPERATION_P')]
PROJECT_ROOT = next((path.resolve() for path in candidates if (path / 'README_System.md').exists()), None)
if PROJECT_ROOT is None:
    raise FileNotFoundError('ไม่พบ README_System.md — mount Google Drive หรือกำหนด HT9046MX_PROJECT_ROOT')
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_ROOT = PROJECT_ROOT / 'notebooks' / 'outputs' / 'ht9046mx_phase7_shadow_replay_v2_hp180'
print('Project:', PROJECT_ROOT)
print('Output:', OUTPUT_ROOT)
"""
    ),
    md("### 2. Run deterministic replay from locked artifacts"),
    code(
        """
from notebooks.support.phase7_shadow_replay import ReplayConfig, run_shadow_replay

result = run_shadow_replay(ReplayConfig(PROJECT_ROOT, OUTPUT_ROOT))
summary = result['summary']
display(pd.Series({
    'status': summary['status'],
    'model': summary['selected_model'],
    'threshold': summary['threshold'],
    'persistence': summary['persistence'],
    'primary_rows': summary['primary']['scored_rows'],
    'primary_raw_flag_pct': summary['primary']['raw_flag_rate_pct'],
    'persistent_alerts': summary['primary']['persistent_alerts'],
    'alerts_per_machine_day': summary['primary']['alerts_per_machine_day'],
    'mx080_first_detection': summary['mx080']['first_persistent_detection'],
    'mx080_delay_minutes': summary['mx080']['detection_delay_from_122320_minutes'],
}))
"""
    ),
    md(
        """
## Results

### 3. Primary outer replay — alert burden

กราฟนี้ใช้ตรวจภาระ Alert และความต่างระหว่างเครื่อง ไม่ใช่ precision/recall. ค่าเครื่องสูงผิดกลุ่มต้องถูกตรวจเป็น state/profile mismatch ก่อนเรียก equipment problem.
"""
    ),
    code("display(Image(filename=summary['figures']['primary']))"),
    md("### 4. Replay summary by machine"),
    code(
        """
display(result['primary_by_machine'].sort_values('alerts_per_machine_day', ascending=False).round(4))
display(result['primary_episodes'].head(20).round(4))
"""
    ),
    md(
        """
**สิ่งที่ต้องระวัง:** MX058 และ MX082 มี alert burden สูงกว่าเครื่องอื่นชัดเจน จึงยังตั้ง fleet-wide operational budget ไม่ได้จากค่าเฉลี่ยรวม และต้องตรวจ profile/state coverage ก่อน
"""
    ),
    md(
        """
### 5. MX-080 Module 6 incident probe

แถวบนคือ pressure ที่ aggregate จากข้อมูลรายวินาที แถวล่างคือ score จาก model/threshold ที่ล็อกไว้ก่อนเห็น MX-080. จุดแดงคือการเปิด persistent alert หลังครบสามหน้าต่าง ไม่ใช่ confirmed fault.
"""
    ),
    code("display(Image(filename=summary['figures']['mx080']))"),
    md("### 6. MX-080 alert episode and ring-buffer availability"),
    code(
        """
display(result['incident_episodes'].round(4))
display(pd.Series(summary['mx080']))
display(result['ring_features'].loc[
    result['ring_features']['timestamp'].between('2026-09-07 12:15', '2026-09-07 12:40'),
    ['timestamp','Hp_2nd_6','Lp_2nd_6','hp2_delta_30s','hp2_delta_120s','hp2_slope_30s','hp2_slope_120s','availability_30s','availability_120s']
].round(3))
"""
    ),
    md(
        """
### 7. Failure-mode and contract QA

`PASS` หมายถึง replay ทำงานตาม contract; `DATA_QUALITY`, `BLOCKED` และ `INSUFFICIENT_PROFILE` เป็นผลลัพธ์ที่ถูกต้องเมื่อระบบต้องปฏิเสธการ score/activate อย่างปลอดภัย
"""
    ),
    code("display(result['failure_tests'])"),
    md("### 8. Locked shadow release manifest"),
    code("display(pd.Series(result['release_manifest']))"),
    md(
        """
## Takeaways

1. MX-080 ช่วยงานหลักได้จริง: raw flag rate เปลี่ยนจาก 3.0% ก่อน transition เป็น 100% หลัง transition และ persistent alert เปิดเวลา 12:35 โดยไม่ได้ใช้ incident เลือก model/threshold
2. Raw flag ก่อน 12:23 อาจเป็น precursor หรือ profile mismatch; เพราะไม่มี confirmed onset จึงห้ามเรียกว่า validated lead time
3. ผลนี้แสดง incident sensitivity เพียงหนึ่งเหตุการณ์ ไม่ใช่ recall หรือ fault accuracy
4. Primary replay รุ่น hp180 มี 36 persistent alerts เทียบกับ 37 ในรุ่น 200 psi; alert ที่ลดลงหนึ่งครั้งอยู่ที่ MX058 แต่ MX058/MX082 ยังมี burden สูงสุด จึงต้อง review alert budget และ state/profile mismatch ก่อนส่งช่างจริง
5. Model artifact รุ่นเดิมมี pickle class path แบบ `__main__`; replay นี้ re-export เป็น portable artifact พร้อม checksum และทดสอบ clean reload แล้ว
6. Missing/stale/out-of-order/version/order/checksum cases ถูกออกแบบให้หยุดเป็น data/contract status ไม่ออก equipment alert
7. MX-080 profile 4 วันยังใช้ Production ไม่ได้ และไม่มี automatic profile activation
8. Phase 7 ยังปิดไม่ได้จนกว่าจะมี exact rollback target, approved alert budget, timezone/unit/service epoch และ server/MySQL integration replay

### Production decision

สถานะที่ถูกต้องคือ `PASS_WITH_PRODUCTION_BLOCKERS`: พร้อมส่งต่อให้ Server owner ทำ integration ใน shadow environment แต่ยังไม่พร้อม technician advisory หรือ production activation.
"""
    ),
]

nbf.write(nb, OUTPUT)
print(OUTPUT)
