"""Project reviewed evidence to bounded inline outputs and an executed companion."""
import json, csv
from pathlib import Path
from datetime import datetime, timedelta
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'notebooks/outputs/mx017_shadow_diagnosis_20261004'
VIS = Path('C:/Users/Book/.codex/visualizations/2026/09/30/01a0f038-7484-7e81-8bc2-473fab2b9dd6')
receipt = json.loads((OUT/'receipt.json').read_text(encoding='utf-8'))
raw = json.loads((OUT/'raw_checks.json').read_text(encoding='utf-8'))
VIS.mkdir(parents=True, exist_ok=True)
baseline = receipt['modules'][0]['baseline']['templo']['median']
minutes = {p['time']: p for s in raw if s['module']==1 for p in s['minute_means']}
rows = []
t = datetime(2026,9,29,23,30)
while t < datetime(2026,9,30,0,20):
    key=t.isoformat(timespec='minutes')
    p=minutes.get(key)
    rows.append({'time':t.strftime('%d Sep %H:%M'), 'series':'M1 TempLow — observed minute mean', 'temperature_c':p['templo'] if p else None})
    rows.append({'time':t.strftime('%d Sep %H:%M'), 'series':'Frozen Reference median', 'temperature_c':baseline})
    t+=timedelta(minutes=1)
with (OUT/'m1_temperature_chart.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
chart_source={'label':'MX017/M1 raw source + saved Candidate', 'files':[{'label':'m1_temperature_chart.csv'}, {'label':'raw_checks.json'}, {'label':'receipt.json'}],
    'metricDefinitions':[{'label':'TempLow','definition':'อุณหภูมิ TempLow เฉลี่ยจากวินาทีที่บันทึกจริงในแต่ละนาที เทียบค่ามัธยฐาน Reference ของ Candidate เดิม หน่วย °C'}],
    'filters':['Machine: MX017','Module: M1','Raw: all recorded operating states'],
    'caveats':['ช่วง 00:00–00:10 ไม่ได้อ่าน Raw ในการตรวจรอบนี้ จึงเว้นช่องว่าง ไม่ได้หมายความว่าไม่มีข้อมูลในฐานข้อมูล', 'SV เปลี่ยนเป็น Off เวลา 23:35 ในข้อมูลที่อ่าน แต่ไม่ยืนยันว่าเหตุการณ์นั้นคือ balancing ปกติ', 'เส้น Reference เป็นค่าจาก Candidate ที่บันทึกไว้ ไม่ได้ปรับ baseline จาก Shadow']}
chart={'schemaVersion':1,'id':'mx017-m1-temperature','queryId':'mx017-m1-raw','title':'MX017 / M1: อุณหภูมิหลัง SV เปลี่ยนเป็น Off',
    'chart':{'type':'line','x':'time','y':'temperature_c','series':'series','showXAxisLabel':False,'yLabel':'TempLow (°C)'},'rows':rows,'source':chart_source,'theme':'codex-classic'}
(VIS/'mx017-m1-temperature.json').write_text(json.dumps(chart,ensure_ascii=False),encoding='utf-8')
chart_receipt={'schemaVersion':1,'items':[{'id':'mx017-m1-raw','title':'อุณหภูมิ M1 หลังเปลี่ยนสถานะ SV','queries':[{'id':'mx017-m1-raw','source':chart_source,'rows':rows,'columns':['time','series','temperature_c'],
    'reportingPeriod':'29 Sep 2026 23:30–30 Sep 2026 00:20 Asia/Bangkok; observed slices 23:30–00:00 and 00:10–00:20',
    'methods':[{'language':'calculation','code':'Minute mean uses only source-observed seconds. First slice: 1,775/1,800 seconds. Second slice: 591/600 seconds. No interpolation. Frozen TempLow Reference median = -64.9542372881356 °C.'}]}]}]}
(VIS/'mx017-m1-temperature-sources.json').write_text(json.dumps(chart_receipt,ensure_ascii=False),encoding='utf-8')
summary_rows=[]
for m in receipt['modules']:
    a=m.get('threshold_comparator_audit',{})
    summary_rows.append({'module':f'M{m["module"]}','qualified_shadow_minutes':m['summary']['shadow_minutes'],'flagged_minutes_current':a.get('shadow_ge'),
        'valve_only_minutes':m.get('valve_only_minutes'),'shadow_flag_pct':m['summary']['shadow_flag_pct'],'strict_gt_pct_diagnostic_only':a.get('shadow_gt_pct'),
        'reference_quarantine_pct':m['summary']['quarantine_pct'],'longest_flagged_run_minutes':m.get('episode_summary',{}).get('longest_minutes'),
        'reason_codes':', '.join(m['reason_codes'])})
extra_source={'label':'MX017 saved Calibration evidence', 'files':[{'label':'receipt.json'}, {'label':'shadow_minutes.csv'}, {'label':'raw_checks.json'}, {'label':'mx017_shadow_diagnosis.py'}],
    'metricDefinitions':[{'label':'Shadow flag percentage','definition':'Shadow flag percentage คือสัดส่วนนาทีที่ผ่าน state/data gate แล้วได้คะแนนสูงถึงเกณฑ์ Candidate ไม่ใช่สัดส่วนเครื่องเสียหรือ false-positive rate ที่ยืนยันแล้ว'},
                         {'label':'Strict comparison','definition':'Strict comparison เป็นผลคำนวณตรวจสอบโดยใช้ score > threshold กับ baseline และ threshold เดิม ไม่ได้เปลี่ยนระบบหรืออนุมัติ Profile'}],
    'filters':['Machine: MX017','Modules: M1–M8','Scoring: eligible completed one-minute windows','Reference: retained after existing quarantine rule'],
    'caveats':['M7 ไม่มีนาทีที่ผ่าน qualification จึงไม่แสดงอัตราเตือนเป็นศูนย์','ไม่มี technician healthy/fault labels สำหรับเหตุการณ์ MX017 เหล่านี้', 'การแก้ boundary ของ M1/M2 ยังไม่แก้ Reference selection, quarantine และ prerequisite blockers อื่น'],
    'evidenceFlow':[{'kind':'validation','title':'Frozen evidence parity','detail':'Recomputed scores from cached minute windows matched saved source_digest for all eight modules. Shadow percentages matched saved results to tolerance 1e-12.'}]}
extra={'schemaVersion':1,'items':[{'id':'mx017-shadow-causes','title':'สาเหตุที่ Candidate MX017 ต้องทบทวน','queries':[{'id':'mx017-all-modules','source':extra_source,'rows':summary_rows,'columns':list(summary_rows[0]),
    'reportingPeriod':'Reference 31 Aug–27 Sep 2026; Shadow 28–30 Sep 2026; Asia/Bangkok',
    'methods':[{'language':'calculation','code':'M1: Valve baseline median 102, scale 1, threshold 5; Valve 97 has score 5. 1,435/1,458 flagged minutes cross only Valve and exactly equal cutoff. M1 strict > diagnostic: 23/4,262 = 0.53965%. M2: baseline Valve 92, scale 1, threshold 8; Valve 100 has score 8. Strict > diagnostic: 20/4,263 = 0.46915%. Retained Reference exact-cutoff minutes: M1 385/34,255; M2 374/31,533. No runtime changes.'}]}]}]}
(VIS/'mx017-shadow-causes-sources.json').write_text(json.dumps(extra,ensure_ascii=False),encoding='utf-8')
nb=nbformat.v4.new_notebook()
nb.metadata['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
nb.cells=[
    nbformat.v4.new_markdown_cell('# MX017 Shadow diagnosis — 4 October 2026\nRead-only companion to the saved Candidate audit. Reference precedes Shadow. This notebook reads recorded outputs only; it does not refit, activate, or modify database state. Raw slices preserve all source states and missing seconds.'),
    nbformat.v4.new_code_cell("from pathlib import Path\nimport json, pandas as pd\nroot=Path.cwd()\nout=root/'notebooks/outputs/mx017_shadow_diagnosis_20261004'\nr=json.loads((out/'receipt.json').read_text(encoding='utf-8'))\nassert all(m['source_digest_match'] for m in r['modules'])\nprint('Parent:', r['parent_id'])\nprint('Created UTC:', r['parent_created_utc'])\nprint('All eight frozen source digests match:', True)"),
    nbformat.v4.new_code_cell("rows=[]\nfor m in r['modules']:\n a=m.get('threshold_comparator_audit',{})\n rows.append({'module':m['module'],'shadow_minutes':m['summary']['shadow_minutes'],'current_pct':m['summary']['shadow_flag_pct'],'strict_gt_pct_diagnostic_only':a.get('shadow_gt_pct'),'valve_only_minutes':m.get('valve_only_minutes'),'quarantine_pct':m['summary']['quarantine_pct']})\ndisplay(pd.DataFrame(rows))"),
    nbformat.v4.new_code_cell("for m in r['modules'][:2]:\n print('M',m['module'],'Valve baseline:',m['baseline']['valve'],'threshold:',m['threshold'])\n print(m['threshold_comparator_audit'])\n print('Episodes:',m['episode_summary'])"),
    nbformat.v4.new_code_cell("raw=json.loads((out/'raw_checks.json').read_text(encoding='utf-8'))\nfor s in raw:\n print('M',s['module'],s['start'],s['end'],'seconds:',s['observed_rows'],'/',s['expected_seconds'],'SV:',s['sv_counts'])\n display(pd.DataFrame(s['minute_means'][::5]))"),
    nbformat.v4.new_code_cell("d=pd.read_csv(out/'distributions.csv')\ndisplay(d[(d.module==1)&d.feature.isin(['hp2','lp2','temphi','templo','valve'])&d.phase.isin(['reference_retained','shadow'])])"),
    nbformat.v4.new_markdown_cell('## Interpretation limits\nThreshold ties explain most M1/M2 raw-flag burden. Genuine pressure/thermal transitions and sustained M4/M5 deviations remain separate review cases. Stable is not healthy. Neither a strict-comparison counterfactual nor a single settling trace authorizes Active promotion. Proposed next work: versioned discrete-feature boundary handling, control context versus physical evidence, independently validated phase-aware envelopes, and readable per-check blockers.')]
NotebookClient(nb,timeout=60,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
nbformat.write(nb,ROOT/'notebooks/10_MX017_Shadow_Diagnosis_20261004.ipynb')
print('Reviewed chart rows:',len(rows))
print('Executed companion cells:',sum(c.cell_type=='code' for c in nb.cells))
print('All outputs written; runtime unchanged.')
