"""Build a compact, reproducible Phase 7 external-event coverage notebook."""
from pathlib import Path
import json
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "outputs" / "ht9046mx_external_event_coverage_v1"
TARGET = ROOT / "notebooks" / "07C_HT9046MX_External_OneSecond_Coverage_Colab.ipynb"
summary = json.loads((OUT / "analysis_summary.json").read_text(encoding="utf-8"))
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md("# 07C — Phase 7 checkpoint: One-second event coverage from added MX history\n\nตรวจ opening/closing × SV × module จาก external canonical rows ที่ไม่ซ้ำ primary โดยใช้ clean-window rule เดียวกับ one-second analysis เดิม."),
    md(f"## tl;dr\n\nพบ clean events {summary['clean_events']:,} จาก candidate starts {summary['candidate_starts']:,}; closing {summary['clean_events_by_direction']['Closing']:,}, opening {summary['clean_events_by_direction']['Opening']:,}. ไม่มี context ใดถึงเกณฑ์ 30 events และ 3 วัน จึงยังไม่ปลดล็อก response profile, sequence model หรือ production."),
    md("## Context & Methods\n\nClean window ต้องเป็น Run, SV คงที่, ไม่มี MValveHome/Off/negative valve, มี status On ก่อน event, valve step ≥3 และไม่มี ChangeValve ซ้อนใน horizon −30 ถึง +120 วินาที. นี่เป็น coverage audit ไม่ใช่ fault diagnosis หรือ baseline approval."),
    code("""from pathlib import Path
import json, pandas as pd, numpy as np, matplotlib.pyplot as plt
PROJECT_ROOT=Path.cwd()
if not (PROJECT_ROOT/'notebooks').exists(): PROJECT_ROOT=PROJECT_ROOT.parent
OUTPUT=PROJECT_ROOT/'notebooks/outputs/ht9046mx_external_event_coverage_v1'
FIGURES=OUTPUT/'figures'; FIGURES.mkdir(parents=True,exist_ok=True)
summary=json.loads((OUTPUT/'analysis_summary.json').read_text())
coverage=pd.read_csv(OUTPUT/'external_event_coverage_by_context.csv',dtype={'machine_number':str})
events=pd.read_parquet(OUTPUT/'external_clean_events.parquet')
print(summary)
"""),
    md("## Results\n\n### 1. Funnel: ChangeValve starts → clean events"),
    code("""fig,ax=plt.subplots(figsize=(7,4)); values=[summary['candidate_starts'],summary['clean_events']]
bars=ax.bar(['ChangeValve starts','Clean windows'],values,color=['#A9C7DD','#2878A5'])
for b,v in zip(bars,values): ax.text(b.get_x()+b.get_width()/2,v,f'{v:,}',ha='center',va='bottom')
ax.set_title('External one-second event-screening funnel'); ax.set_ylabel('Events'); ax.set_ylim(0,max(values)*1.15)
fig.tight_layout(); fig.savefig(FIGURES/'01_event_funnel.png',dpi=180,bbox_inches='tight'); plt.show()
"""),
    md("### 2. Direction balance\nValve-command direction is not refrigerant-flow direction."),
    code("""s=events.direction.value_counts().reindex(['Closing','Opening'],fill_value=0)
fig,ax=plt.subplots(figsize=(6,4)); bars=ax.bar(s.index,s.values,color=['#2878A5','#C48C2D'])
for b,v in zip(bars,s.values): ax.text(b.get_x()+b.get_width()/2,v,f'{v:,}',ha='center',va='bottom')
ax.set_title('Clean event direction — external novel history'); ax.set_ylabel('Clean windows')
fig.tight_layout(); fig.savefig(FIGURES/'02_direction_balance.png',dpi=180,bbox_inches='tight'); plt.show()
"""),
    md("### 3. Best-supported context: SV Off / Closing\nNo cross-SV or direction pooling."),
    code("""p=(coverage.query(\"sv=='Off' and direction=='Closing'\").pivot(index='machine_number',columns='module',values='clean_events').reindex(columns=range(1,9)).fillna(0))
fig,ax=plt.subplots(figsize=(10,4.5)); im=ax.imshow(p.to_numpy(),cmap='Blues',aspect='auto')
for i in range(len(p)):
 for j in range(8): ax.text(j,i,str(int(p.iloc[i,j])),ha='center',va='center',color='white' if p.iloc[i,j]>p.to_numpy().max()/2 else '#30343B')
ax.set_xticks(range(8),[f'M{i}' for i in range(1,9)]); ax.set_yticks(range(len(p)),['MX'+m for m in p.index]); ax.set_title('Clean closing events — SV Off')
fig.colorbar(im,ax=ax,label='Clean events'); fig.tight_layout(); fig.savefig(FIGURES/'03_closing_off_coverage.png',dpi=180,bbox_inches='tight'); plt.show()
"""),
    md("## QA and decision"),
    code("""qa={'count_matches':len(events)==summary['clean_events'],'unique_event_key':not events.duplicated(['machine_number','module','event_at']).any(),'no_approval_status':set(coverage.coverage_status).issubset({'INSUFFICIENT_COVERAGE','COVERAGE_MET_NOT_APPROVED'}),'opening_limited':int((events.direction=='Opening').sum())<30}
assert all(qa.values()),qa
(OUTPUT/'notebook_qa.json').write_text(json.dumps(qa,indent=2))
pd.Series(qa,name='Passed').to_frame()
"""),
    md("## Takeaway\n\nข้อมูลเพิ่มช่วยเพิ่ม closing evidence แต่ opening และ SV On ยังไม่พอ. ขั้นถัดไปคือรวม coverage counts กับ primary โดยไม่รวม raw rows ซ้ำ, ตรวจ service/refill epoch และ predeclare split ใหม่ก่อน retrain หรือ server shadow replay."),
]
nbf.write(nbf.v4.new_notebook(cells=cells, metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}}),TARGET)
print(TARGET)
