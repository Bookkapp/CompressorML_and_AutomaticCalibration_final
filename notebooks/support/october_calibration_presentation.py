"""Plots + executed notebook scaffold for the three-machine ZIP audit."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import nbformat

OUTPUT=Path(__file__).resolve().parents[1]/'outputs'/'october_three_machine_calibration_v1'
COLORS={'017':'#1768AC','024':'#BB6D25','080':'#6554A4'}


def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':14,
                         'axes.labelsize':11,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.facecolor':'white','axes.facecolor':'white','grid.color':'#DEE4EB',
                         'grid.alpha':.65,'axes.edgecolor':'#8793A0','savefig.bbox':'tight'})


def save(fig,name,output):
    folder=output/'figures'; folder.mkdir(exist_ok=True)
    fig.savefig(folder/f'{name}.png',dpi=160)
    fig.savefig(folder/f'{name}.svg')
    return fig


def coverage(output=OUTPUT):
    setup()
    q=pd.read_csv(output/'quality.csv',dtype={'machine':str})
    summary=q.groupby('machine').agg(files=('date','size'),rows=('rows','sum'),first=('first','min'),last=('last','max'),
                                    intervals=('intervals','sum'),one_second=('one_second_intervals','sum'))
    fig,axes=plt.subplots(1,2,figsize=(12.4,4.2),layout='constrained')
    for i,(machine,row) in enumerate(summary.iterrows()):
        axes[0].barh(i,row.rows/1e6,color=COLORS[machine],height=.56)
        axes[0].text(row.rows/1e6+.08,i,f'{row.rows/1e6:.2f}M | {int(row.files)} day-files',va='center')
        dates=pd.to_datetime(q[q.machine==machine].date)
        axes[1].scatter(dates,np.full(len(dates),i),s=22,marker='s',color=COLORS[machine])
    axes[0].set(yticks=range(3),yticklabels=['MX'+x for x in summary.index],xlabel='Observed raw rows (millions)',
                title='Three machines, separate source histories',xlim=(0,summary.rows.max()/1e6*1.40))
    axes[1].set(yticks=range(3),yticklabels=['MX'+x for x in summary.index],title='Available daily raw files')
    axes[1].xaxis.set_major_locator(mdates.MonthLocator());axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    axes[0].invert_yaxis(); axes[1].invert_yaxis()
    return save(fig,'01_source_coverage',output)


def baseline_timeline(output=OUTPUT):
    setup()
    daily=pd.read_csv(output/'daily_baselines.csv',dtype={'machine':str},parse_dates=['date'])
    fig,axes=plt.subplots(3,1,figsize=(13.5,10),sharex=True,sharey=True,layout='constrained')
    palette=['#1768AC','#43A0BC','#BB6D25','#737F35','#6554A4','#BD5976','#677689','#242F3C']
    for ax,machine in zip(axes,['017','024','080']):
        block=daily[daily.machine==machine]
        # Missing calendar days/unsupported age are explicit breaks, not lines across gaps.
        for module,color in zip(range(1,9),palette):
            rows=block[block.module==module].set_index('date').sort_index()
            if not len(rows): continue
            complete=rows.reindex(pd.date_range('2026-07-01','2026-10-01'))
            values=complete.hp2.where(complete.n.ge(60))
            ax.plot(complete.index,values,color=color,lw=1.5,label=f'M{module}')
        ax.axhspan(180,230,color='#758FA7',alpha=.10)
        ax.axhline(180,color='#84919C',ls='--',lw=.8);ax.axhline(230,color='#84919C',ls='--',lw=.8)
        ax.set(title=f'MX{machine} | daily Hp_2nd median, state/data-qualified Cold minutes',ylabel='Hp_2nd (source psi)')
        ax.grid(axis='y');ax.legend(ncol=8,loc='upper left',frameon=False,fontsize=9)
        if machine=='080':
            ax.axvline(pd.Timestamp('2026-09-07'),color='#AC4052',ls=':',lw=1.4)
            ax.text(pd.Timestamp('2026-09-08'),ax.get_ylim()[1]*.94,'7 Sep: registered M6 case',fontsize=10,color='#AC4052')
    axes[-1].set_xticks(pd.to_datetime(['2026-07-01','2026-07-15','2026-08-01','2026-08-15','2026-09-01','2026-09-15','2026-10-01']))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    fig.suptitle('A quiet graph can still sit at a different level\nField band is context only; these are unverified candidate observations',fontsize=16)
    return save(fig,'02_daily_hp2_by_machine_module',output)


def context_baselines(output=OUTPUT):
    setup(); table=pd.read_csv(output/'context_summary.csv',dtype={'machine':str})
    fig,axes=plt.subplots(1,3,figsize=(13.5,5.6),sharey=True,layout='constrained')
    for ax,machine in zip(axes,['017','024','080']):
        b=table[table.machine==machine].set_index('module').reindex(range(1,9))
        y=np.arange(1,9)
        supported=b.cold_minutes.ge(200)&b.cold_days.ge(7)
        ax.hlines(y,b.hp2_all_q5.where(supported),b.hp2_all_q95.where(supported),color=COLORS[machine],lw=3,alpha=.7)
        ax.scatter(b.hp2_all_q50.where(supported),y,s=42,color=COLORS[machine],zorder=3)
        for module,row in b.iterrows():
            if supported.loc[module] and np.isfinite(row.hp2_all_q50):
                ax.text(row.hp2_all_q95+3,module,f'{row.hp2_all_q50:.1f} | n={int(row.cold_minutes):,}',va='center',fontsize=9)
            else: ax.text(160,module,f'Unsupported: n={int(row.cold_minutes)} Cold min',va='center',fontsize=9,color='#687582')
        ax.axvspan(180,230,color='#758FA7',alpha=.10)
        ax.set(title=f'MX{machine}',xlabel='Hp_2nd (source psi)',yticks=range(1,9),yticklabels=[f'M{x}' for x in range(1,9)],xlim=(140,490))
        ax.grid(axis='x')
    axes[0].invert_yaxis()
    fig.suptitle('Machine x module is the minimum local reference\nMedian and empirical Q05-Q95, Jul-Oct; not confidence intervals / not approved normal',fontsize=15)
    return save(fig,'03_local_baseline_spread',output)


def correlation_chart(output=OUTPUT):
    setup(); c=pd.read_csv(output/'correlations.csv',dtype={'machine':str})
    pairs=[('hp1','hp2'),('hp2','temphi'),('hp2','templo'),('lp2','templo'),('valve','lp2')]
    fig,axes=plt.subplots(1,3,figsize=(14,8.6),sharey=True,layout='constrained')
    for ax,machine in zip(axes,['017','024','080']):
        vals=np.full((8,len(pairs)),np.nan)
        for mi in range(1,9):
            for j,(f,other) in enumerate(pairs):
                rows=c[(c.machine==machine)&(c.module==mi)&(c.population=='within_day_all_qualified') &
                       (((c.x==f)&(c.y==other))|((c.x==other)&(c.y==f)))]
                if len(rows) and rows.iloc[0]['n']>=200: vals[mi-1,j]=rows.iloc[0].rho
        im=ax.imshow(np.ma.masked_invalid(vals),vmin=-1,vmax=1,cmap='PuOr',aspect='auto')
        for i in range(8):
            for j in range(len(pairs)):
                ax.text(j,i,'NA' if np.isnan(vals[i,j]) else f'{vals[i,j]:+.2f}',ha='center',va='center',fontsize=10,
                        color='white' if np.isfinite(vals[i,j]) and abs(vals[i,j])>.65 else '#26333E')
        ax.set(title=f'MX{machine}',yticks=range(8),yticklabels=[f'M{x}' for x in range(1,9)],
               xticks=range(len(pairs)),xticklabels=[f'{dict(hp1="HP1",hp2="HP2",lp2="LP2",valve="Valve")[a]}\n{dict(hp2="HP2",temphi="TempHi",templo="TempLo",lp2="LP2")[b]}' for a,b in pairs])
    fig.colorbar(im,ax=axes,shrink=.5,label='Spearman rho (-1 to +1)')
    fig.suptitle('Relationships differ even after removing daily level offsets\nState/data-qualified Cold; within-day median centred; NA = unsupported or constant',fontsize=15)
    return save(fig,'04_conditional_correlations',output)


def startup_chart(output=OUTPUT):
    setup()
    data=pd.read_parquet(output/'raw_run_trajectories.parquet',filters=[('module','==',6)])
    fig,axes=plt.subplots(3,3,figsize=(13.5,11),sharex=True,layout='constrained')
    features=['hp2','temphi','templo']; labels=['Hp_2nd (source psi)','TempHi (source degC)','TempLo (source degC)']
    counts=[]
    for row,machine in enumerate(['017','024','080']):
        b=data[data.machine==machine] if len(data) else data
        n=b.event_id.nunique() if len(b) else 0
        counts.append({'machine':machine,'module':6,'kind':'RAW_OBSERVED_RUN_BOUNDARY','stored_cycles':n})
        for col,(feature,label) in enumerate(zip(features,labels)):
            ax=axes[row,col]
            n20=0
            if len(b):
                group=b.groupby('elapsed')[feature]
                q=group.quantile([.1,.5,.9]).unstack().reindex(range(1801))
                support=group.count();supported=support.ge(3)
                for _,cycle in list(b.groupby('event_id'))[:15]:
                    cycle_values=cycle.set_index('elapsed')[feature].reindex(range(1801))
                    ax.plot(cycle_values.index/60,cycle_values,color=COLORS[machine],alpha=.15,lw=.6)
                ax.fill_between(q.index/60,q[.1].where(supported),q[.9].where(supported),color=COLORS[machine],alpha=.15)
                ax.plot(q.index/60,q[.5],color=COLORS[machine],lw=1.9)
                n20=int(support.get(1200,0))
            else: ax.text(.5,.5,'No observed starts\nin stored sample',ha='center',va='center',transform=ax.transAxes)
            ax.set(ylabel=label,title=f'MX{machine} / M6\n{n} observed starts | n at 20 min: {n20}',xlim=(0,30));ax.grid(axis='y')
            if row==2:ax.set_xlabel('Elapsed minutes (raw-second curves)')
    fig.suptitle('Status entering Run is not immediate thermal equilibrium\nActual seconds / ALL module states / independent y scales; Q10-Q90 spread is NOT a healthy envelope',fontsize=15)
    pd.DataFrame(counts).to_csv(output/'plotted_start_support.csv',index=False)
    return save(fig,'05_raw_second_startup_trajectories',output)


def shadow_chart(output=OUTPUT):
    setup(); e=pd.read_csv(output/'causal_shadow_experiments.csv',dtype={'machine':str})
    e=e[(e.fit_policy=='current_state_only') & pd.to_datetime(e.cut).ge('2026-09-01')].copy()
    keys=['machine','module','cut']
    complete=e.groupby(keys).lookback_days.nunique().eq(4).rename('complete').reset_index()
    e=e.merge(complete,on=keys).query('complete')
    fig,axes=plt.subplots(1,3,figsize=(13,4.9),sharey=True,layout='constrained')
    for ax,machine in zip(axes,['017','024','080']):
        b=e[e.machine==machine]
        grouped=b.groupby('lookback_days')[['raw_flag_n','shadow_n','persistent_n']].sum()
        ax.plot(grouped.index,100*grouped.raw_flag_n/grouped.shadow_n,'o-',color=COLORS[machine],label='Raw flag minutes')
        ax.plot(grouped.index,100*grouped.persistent_n/grouped.shadow_n,'s--',color=COLORS[machine],alpha=.65,label='Persistent minutes')
        ax.set(title=f'MX{machine}',xlabel='Past fit lookback (calendar days)',xticks=[7,14,30,60]);ax.grid(axis='y')
        ax.legend(frameon=False,fontsize=9)
    axes[0].set_ylabel('Flagged qualified shadow minutes (%)')
    fig.suptitle('More history is not automatically a better baseline\nMatched September module/cuts supported at all 4 lookbacks -> same next 3 days; no fault labels',fontsize=15)
    return save(fig,'06_lookback_shadow_sensitivity',output)


def case_chart(output=OUTPUT, source_dir=Path('C:/Users/Book/Downloads')):
    setup()
    from october_three_machine_calibration import read_day, inventory
    _,entries,handles=inventory(source_dir)
    entry=next(e for e in entries if e['machine']=='080' and e['date']=='2026-09-07' and e['kind']=='dynamic')
    raw,times,_=read_day(entry)
    keep=times.between('2026-09-07 11:50','2026-09-07 13:00')
    keep &= times.notna() & ~times.duplicated(keep=False)
    raw=raw[keep].copy();times=times[keep]
    order=times.sort_values().index;raw=raw.loc[order];times=times.loc[order]
    # Break every unobserved second in this detailed figure rather than drawing a false bridge.
    gap=times.diff().dt.total_seconds().gt(1)
    for column in ['Hp_2nd_6','Lp_2nd_6','TempHi_6','TempLo_6','Valve_6']:
        raw.loc[gap,column]=np.nan
    fig,axes=plt.subplots(4,1,figsize=(13,9),sharex=True,layout='constrained')
    for feature,label,color in [('Hp_2nd_6','HP CP2','#1768AC'),('Lp_2nd_6','LP CP2','#BB6D25')]:
        axes[0].plot(times,raw[feature],color=color,lw=1,label=label)
    axes[0].set_ylabel('Pressure (source psi)');axes[0].legend(frameon=False,ncol=2)
    for feature,color in [('TempHi_6','#1768AC'),('TempLo_6','#BB6D25')]:axes[1].plot(times,raw[feature],color=color,lw=1,label=feature)
    axes[1].set_ylabel('Temperature (source degC)');axes[1].legend(frameon=False,ncol=2)
    axes[2].plot(times,raw.Valve_6,color='#6554A4',lw=1);axes[2].set_ylabel('Valve command')
    axes[3].step(times,raw.Busy_6.astype(str).eq('1').astype(int),color='#BB6D25',label='Busy=1',where='post')
    axes[3].step(times,raw.Status_6.eq('On').astype(int),color='#1768AC',label='Status_6=On',where='post')
    axes[3].set(yticks=[0,1],ylabel='Control state');axes[3].legend(frameon=False,ncol=2)
    for ax in axes:
        ax.axvline(pd.Timestamp('2026-09-07 12:23:28'),color='#AC4052',ls=':',lw=1.2)
        ax.grid(axis='y')
    axes[0].set_title('MX080 / M6 | the initial thermal transition and later pressure plateau are different events\n7 Sep 2026, actual seconds; duplicate times excluded, gaps broken; marker = registered >300 psi crossing')
    axes[3].set_xticks(pd.date_range('2026-09-07 11:50','2026-09-07 13:00',freq='10min'))
    axes[3].set_xlim(pd.Timestamp('2026-09-07 11:50'),pd.Timestamp('2026-09-07 13:00'))
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    for h in handles:h.close()
    return save(fig,'07_mx080_m6_raw_second_case',output)


PLOTS=[coverage,baseline_timeline,context_baselines,correlation_chart,startup_chart,shadow_chart,case_chart]


def build_notebook():
    path=Path(__file__).resolve().parents[1]/'08K_Three_Machine_Raw_Second_AutoCalibration_Review.ipynb'
    nb=nbformat.v4.new_notebook()
    md=nbformat.v4.new_markdown_cell; code=nbformat.v4.new_code_cell
    nb.cells=[md('''# MX017 · MX024 · MX080 — ทบทวน Auto-Calibration จากข้อมูลรายวินาที

## tl;dr
ผลและกราฟด้านล่างมาจาก ZIP 5 ส่วนใน Downloads ที่ส่งเมื่อ 1 ตุลาคม 2026 ไม่ใช่ข้อมูลจำลอง และไม่ใช่ผลจาก Active Profile รุ่นใหม่

คำถามสำคัญ: baseline ต่างกันแค่ไหน, ช่วง ON นิ่งทันทีหรือไม่, การใช้ประวัติยาวขึ้นช่วยหรือกลบการเปลี่ยนระดับ, และควรปรับ lifecycle อย่างไร

**รอบนี้เป็นการวิเคราะห์และเสนอแนวทางเท่านั้น:** ไม่เขียน MySQL ไม่เปลี่ยน Profile/threshold/worker และไม่ deploy Server'''),
    md('''## Context & Methods
### Key Assumptions
- Timestamp ได้จากวันในชื่อไฟล์ + Time ในบรรทัด; log ไม่มี timezone offset จึงรักษานาฬิกาต้นทาง ไม่อ้างว่าตรวจยืนยัน timezone แล้ว
- Pressure ใช้หน่วยต้นทางที่คาดว่า psi, Temperature คาดว่า °C และ Valve เป็น command count ตาม contract; ไม่ได้มี calibration certificate
- ใช้เฉพาะ daily `.txt` ที่มี 82 columns; **ไม่ใช้ `_Static.txt`** ตามคำขอ
- ไม่มี healthy/fault labels สำหรับทุกช่วง: คำว่า qualified หมายถึงผ่านข้อมูล/สถานะ ไม่ใช่ตรวจยืนยันว่าเครื่องไม่มีปัญหา
- `Status=Run`, `Status_n=On`, `Busy_n=0`, `SV_n=Off`, Valve≥0, numeric finite ทุกวินาทีในนาที
- Minute ต้องมีอย่างน้อย 57 unique seconds, gap≤5s รวมขอบนาที และไม่มี duplicate. Features เป็น mean ของวินาทีที่สังเกตจริง ไม่ fill missing
- ช่วงอายุ Cold ≥20min เป็น **sensitivity slice** ไม่ใช่กฎ settling ที่ fitted แล้ว; onset ไม่ทราบแยกต่างหาก ไม่แต่งเวลาขึ้นมา
- กราฟ startup แสดง raw seconds หลัง observed Run entry, แยกจาก post-manual/control-entry. เก็บ ledger ทุก event แต่ raw plot cacheจำกัด 5 events/module/day/kind, duration≥120s, สูงสุด30min; censoredที่ท้ายวัน
- Correlation ไม่ใช่ causality; daily-median centering ลด level confounding บางส่วน แต่ไม่มี recipe/load/water จึงยังเทียบ context ได้ไม่ครบ'''),
    md('''### 1. Setup และการรันใหม่
Notebook ใช้ `support/october_three_machine_calibration.py` เป็น data preparation และ `support/october_calibration_presentation.py` เป็น plotting code ทั้งคู่ตรวจสอบได้

สำหรับ Colab ให้อัปโหลด notebook, สอง scripts และ derived output folder หรือ mount Drive. เปลี่ยน `SOURCE_DIR` เป็น folder ZIP ของคุณ เมื่อต้องการคำนวณจาก raw ใหม่ให้ตั้ง `REBUILD_RAW=True`. การ rebuild ใช้เวลาหลายนาทีและอ่านไฟล์หลาย GB; ค่าเริ่มต้นอ่าน cache ที่มี manifest/hash'''),
    code('''from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path.cwd()
if not (ROOT / 'support').is_dir() and (ROOT / 'notebooks/support').is_dir():
    ROOT = ROOT / 'notebooks'
sys.path.insert(0, str(ROOT / 'support'))
import october_three_machine_calibration as audit
import october_calibration_presentation as visuals
get_ipython().run_line_magic('matplotlib', 'inline')

SOURCE_DIR = Path('C:/Users/Book/Downloads')  # Colab: /content/drive/MyDrive/...
OUTPUT = ROOT / 'outputs/october_three_machine_calibration_v1'
REBUILD_RAW = False
if REBUILD_RAW:
    audit.ingest(SOURCE_DIR, OUTPUT)
    audit.summarize(OUTPUT)
    audit.extract_run_trajectories(SOURCE_DIR, OUTPUT)
manifest = json.loads((OUTPUT/'ingestion_manifest.json').read_text(encoding='utf-8'))
summary = json.loads((OUTPUT/'analysis_summary.json').read_text(encoding='utf-8'))
display(pd.Series(summary, name='Verified analysis scope'))
'''),md('''## Data
### 2. ตรวจที่มาและขอบเขตก่อนตีความ
ZIP ส่วนที่ 2 มี MX080 เดือนกรกฎาคมซ้อนอยู่ จึงต้องอ่าน nested archive ด้วย. ตาราง hash และ inventory ป้องกันการตกหล่น/นับซ้ำ; Staticมีแค่รายชื่อใน inventoryแต่ไม่ถูก parse หรือวิเคราะห์'''),
    code('''quality = pd.read_csv(OUTPUT/'quality.csv', dtype={'machine':str})
display(quality.groupby('machine').agg(day_files=('date','size'), raw_rows=('rows','sum'),
    first=('first','min'), last=('last','max'), duplicate_rows=('duplicate_seconds','sum'),
    missing_cells=('missing_cells','sum'), nonmonotonic_steps=('nonmonotonic','sum')))
display(pd.DataFrame(manifest['archives'])[['archive','bytes','sha256']])
fig = visuals.coverage(OUTPUT); display(fig); plt.close(fig)
'''),md('''## Results
### 3. Baseline ของแต่ละเครื่อง–แต่ละโมดูล
ดูทั้ง distribution และแนวโน้มตามวัน. เส้นที่นิ่งไม่ได้แปลว่าอยู่ในระดับเดิม: หากกวาดข้อมูลก่อน–หลัง shift มา fitพร้อมกัน baselineและscaleอาจรวมสอง regime. แถบ180–230psiเป็น field reference ของเจ้าของโครงการ ไม่ใช่ safety/normal labelอัตโนมัติ'''),
    code('''contexts = pd.read_csv(OUTPUT/'context_summary.csv', dtype={'machine':str})
display(contexts[['machine','module','cold_days','cold_minutes','age20_minutes','unknown_age_minutes','hp2_all_q50','hp2_all_q5','hp2_all_q95']].round(2))
fig=visuals.context_baselines(OUTPUT); display(fig); plt.close(fig)
'''),code('''fig=visuals.baseline_timeline(OUTPUT); display(fig); plt.close(fig)
'''),md('''### 4. ความสัมพันธ์เปลี่ยนหรือไม่
Spearman ใช้กับ ranking ไม่บังคับ linear relationship. กราฟนี้หัก median ของแต่ละวันก่อนคำนวณเพื่อลดการเอา level shifts มาสร้าง correlationหลอก. NA คือข้อมูลไม่พอหรือค่าconstant ไม่ใช่ rho=0. อิงทุก state/data-qualified Cold minute; age20 มีผลแยกในตาราง sensitivity จึงไม่ทิ้งนาทีที่ onset ไม่ทราบออกจากภาพหลัก'''),code('''fig=visuals.correlation_chart(OUTPUT); display(fig); plt.close(fig)
'''),md('''### 5. หลายรอบเริ่มเครื่อง บนแกนเวลารายวินาที
`Observed Run start` ต้องเห็น Run หลัง sample non-Run ที่ต่อเนื่อง≤2s. จุดแรกที่ ON อยู่แล้วหรือมี gapเป็น UNKNOWN ไม่ใช่ startที่ยืนยัน. ตัวนับจากCold ledgerนับเฉพาะRunที่เข้าColdพร้อมกัน; **กราฟrawแยกตรวจRun boundaryเอง โดยไม่บังคับColdทันที** และเก็บสถานะที่ตามมาจนRunจบ/30min/ท้ายวัน. ตรวจrawซ้ำเฉพาะวันที่มีmixedRunminute/RunหลังStopminuteหรือCold-ledgerRunentry. กราฟใช้medianข้ามcyclesและQ10–Q90เป็นspread ไม่ใช่CI/healthyenvelope; y scaleแยกต่อpanel. nต้นช่วงไม่รับรองcoverageท้ายช่วง'''),code('''events=pd.read_csv(OUTPUT/'event_counts.csv',dtype={'machine':str})
display(events.groupby(['machine','kind']).events.sum().unstack(fill_value=0))
event_ledger=pd.read_parquet(OUTPUT/'events.parquet')
display(event_ledger[event_ledger.kind.eq('OBSERVED_RUN_START')].drop_duplicates(['machine','start']).groupby('machine').size().rename('Unique observed Run boundaries'))
display(pd.read_csv(OUTPUT/'raw_run_boundaries.csv',dtype={'machine':str}).groupby('machine').size().rename('Raw observed Run entries (Cold qualification not required)'))
fig=visuals.startup_chart(OUTPUT); display(fig); plt.close(fig)
display(pd.read_csv(OUTPUT/'plotted_start_support.csv',dtype={'machine':str}))
'''),md(r'''### 6. ทดสอบประวัติย้อนหลัง → shadow 3 วัน
สูตรเหมือน candidateปัจจุบัน (parity testsแยกไว้):

$$m_j=\operatorname{median}(x_j),\quad s_j=\max(1.4826\operatorname{MAD}(x_j),\operatorname{IQR}(x_j)/1.349,f_j)$$
$$z_j=(x_j-m_j)/s_j,\qquad S=\max_j|z_j|$$

Floor $f_j=1$ สำหรับ Valve, $0.1$ สำหรับtagอื่น; screenรอบแรก $S\le8$ แล้วrefit, threshold $q_{0.995}$ ของ retained fit เท่านั้น. Raw flagใช้ $S\ge threshold$; persistent = flagged3นาที qualifiedติดกัน ไม่ข้าม gap.

ใช้weeklycuts1Augเป็นต้นไป, fitก่อนcutย้อนหลังสูงสุด7/14/30/60calendar days → ถัดไป3วัน; actual fit daysอยู่ในCSV (ก่อนSepยังมีrawhistoryไม่ครบ60วัน). Shadowเก็บทุกeligibleminuteเหมือนกัน; age20 sensitivityเปลี่ยนเฉพาะ fit population ไม่ลบstartup flagsออกจากผลทดสอบ. กราฟเปรียบเทียบเฉพาะSeptembercutsที่มีfitทั้ง4lookbacks เพื่อให้shadow denominatorตรงกัน. ไม่มีHPO/การเลือกreleaseจากผลนี้ และknowncaseที่ตรวจแล้วเป็นdiagnosticไม่ใช่freshaccuracytest'''),code('''experiments=pd.read_csv(OUTPUT/'causal_shadow_experiments.csv',dtype={'machine':str},parse_dates=['cut'])
rates=experiments.groupby(['machine','fit_policy','lookback_days'])[['shadow_n','raw_flag_n','persistent_n','early_n','early_flag_n','late_n','late_flag_n']].sum()
rates['raw_flag_pct']=100*rates.raw_flag_n/rates.shadow_n
rates['early_flag_pct']=100*rates.early_flag_n/rates.early_n.replace(0,np.nan)
rates['late_flag_pct']=100*rates.late_flag_n/rates.late_n.replace(0,np.nan)
display(rates[['shadow_n','raw_flag_pct','early_n','early_flag_pct','late_n','late_flag_pct']].round(2))
fig=visuals.shadow_chart(OUTPUT); display(fig); plt.close(fig)
'''),md('''### 7. Guard against absorbing an abnormal plateau
กราฟ MX080/M6 7Sepเป็น regression case ที่เจ้าของยืนยันพฤติกรรมผิดปกติแล้ว. แยกการเปลี่ยนอุณหภูมิช่วงแรกออกจาก pressure plateauหลัง12:23. **Slopeต่ำอย่างเดียวไม่พอสำหรับ normal baseline** ต้องเทียบlevel/differentialกับpast referenceด้วย. ไม่อ้างว่าการเปลี่ยนValveเป็นสาเหตุเสียหรือมีการเติมน้ำยา'''),code('''# Source parameter is passed explicitly; only this cell reopens one raw day for detailed verification.
fig=visuals.case_chart(OUTPUT, source_dir=SOURCE_DIR); display(fig); plt.close(fig)
'''),md('''## Takeaways
### 8. แนวทาง Auto-Calibration ที่ควรพัฒนาต่อ
1. คงlocal Machine×Module×qualified stateเป็นkeyหลัก; SVเป็นgate ไม่ใช่recipeชื่อเต็ม
2. เพิ่มphase/settling qualificationที่ใช้trailingข้อมูลเท่านั้น; เริ่มจาก slope+variation+control continuity และcompatiblelevel ไม่ใช้timer20minอย่างเดียว
3. ให้Historyยาวเป็น evidence bank แต่เลือกcandidateจากช่วงอดีตที่distributionคงที่; mixed-regimeให้REVIEW_REQUIRED ไม่เพิ่มscaleเพื่อให้ผ่าน
4. แยกmanual/state-change ledgerออกจากservice/refillที่ยืนยัน; shiftที่แบนแต่ต่างreferenceยังเก็บเป็นreview/episode
5. Candidateเก็บbaselineต่อวัน/cycle, uncertaintyและcoverageของบริบท ไม่ให้ millions ofsecondsแทนindependentcycles
6. Shadow3วันยังคงแยกqualified coverage, state availability, missing source, raw/persistentflagและcontributors; rejectต้องมีเหตุผลและเลือกช่วงอ้างอิงใหม่ ไม่retrythresholdจนผ่าน
7. ทดสอบknowncasesพร้อมfreshfuturestarts/steady periodsก่อนversioningและmanualapproval. รอบนี้ไม่มีActivepromotion

อายุ20minและlookbackที่เปรียบเทียบเป็นdiagnostic sensitivity **ยังไม่ใช่พารามิเตอร์ใหม่ที่อนุมัติ**. ไม่มีnormal/faultlabelsทั้งชุด จึงรายงานflag burdenแทนfalsepositive/recall.

### 9. QA และข้อจำกัด
ตรวจvectorizedwindowกับruntimebuilderทั้งnormal/duplicate/gap/manual/nonfinite/negativeValve/state และตรวจfitmedian/scale/q995กับexistingcandidate. Sourcehashและrowcountเก็บในmanifest. กราฟมีหน่วยและdenominator; staticexcluded. Sourceclock/unit/recipe/water/serviceไม่ครบ, trajectoriesตัดท้ายวัน/จำกัดstoredsample, age20subsetไม่แทนทั้งfleet. ไม่มีServer latency/restart/ActivequalificationclaimจากNotebookนี้

### References
- [NIST — Assessing Process Stability](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm): stabilityต้องพิจารณาdistribution/mean/varianceตามเวลา
- [NIST — Is the process stable?](https://www.itl.nist.gov/div898/handbook/pri/section2/pri22.htm): เทียบcontrol runsในrecipeที่ใกล้กัน
- [Zhang / NIST — Autocorrelated Data](https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data): processsamplesไม่จำเป็นต้องindependent

แหล่งอ้างอิงสนับสนุนmethodology ไม่ได้กำหนด20min/lookback/floorsที่เหมาะสมเฉพาะHT9046MX''')]
    nb.metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}}
    # Write conclusions only from materialized, executed calculations.
    if (OUTPUT/'analysis_summary.json').exists():
        measured=json.loads((OUTPUT/'analysis_summary.json').read_text(encoding='utf-8'))
        q=pd.read_csv(OUTPUT/'quality.csv',dtype={'machine':str})
        unknown_pct=100*measured['unknown_onset_cold_minutes']/measured['qualified_cold_minutes']
        nb.cells.insert(1,md(f'''### สรุปจากข้อมูลที่อ่านครบแล้ว
- **MX017 / MX024 / MX080**, เครื่องละ93ไฟล์รายวัน รวม **{int(q.rows.sum()):,} แถว** ตั้งแต่1Julถึง1Oct2026 (1Octเป็นวันไม่เต็ม); ไม่ใช้Static
- **{measured['qualified_cold_minutes']:,} qualified Cold module-minutes**. คำว่าqualifiedยังไม่ใช่normal label
- **{unknown_pct:.2f}%** ของqualifiedminutesไม่ทราบonsetที่เชื่อถือได้จากobserved Run/control boundary: อย่าเริ่มtimerใหม่ที่ต้นไฟล์หรือหลังsourcegap
- Module7ข้อมูลไม่พอทุกเครื่อง: MX017=0, MX024=102, MX080=36 qualifiedminutes; จึงยังไม่มีbasisสำหรับsteadyprofileของM7
- MX080/M6 daily Hp_2nd median: 3–6Sepประมาณ190psi, 7–8Sepประมาณ332–340psi, 18–21Sepประมาณ298–314psi และปลายSepประมาณ176–180psi. เป็นหลายระดับที่ต้องreviewแยก ไม่ใช่fitรวมแล้วบอกปกติ
- ตัวอย่างcut26Sep: fit7/14วันมีHp_2nd scale97.79/87.34psiและflags0/3,420minutes; ค่าเตือนที่ลดลงจึงไม่ใช่หลักฐานว่าแม่นขึ้น. ยังต้องตรวจdrift/quarantine/shadow/approvalทุกgate

**ข้อเสนอหลัก:** ทำphase-aware + stable-reference/epoch-aware calibration, ใช้ประวัติยาวเป็นevidence bank, freezebaselineเดิมระหว่างshiftreview. ยังไม่ต้องเปลี่ยนไปLSTMหรือretrainโมเดลใหม่'''))
        position=next(i for i,c in enumerate(nb.cells) if c.cell_type=='markdown' and c.source.startswith('## Takeaways'))
        nb.cells.insert(position,md('''### ข้อจำกัดของผล shadow ที่ต้องอ่านก่อนตัดสินใจ
การทดลอง1,059ชุดนี้ทำnumericalprofilefit/threshold/scoringส่วนเดียวกับcandidate แต่ **ไม่ได้สร้างCandidateในregistryหรือรันapproval lifecycleครบทุกgate**. ผล0flagไม่ใช่READY_FOR_APPROVAL: half-shift, quarantine, retainedcoverage, source/codebook/service/time prerequisitesและshadowreviewยังต้องตรวจแยก. Raw/persistentratesไม่ใช่falsepositiveหรือrecall เพราะไม่มีlabelsครบชุด

ผลไม่ได้บอกว่า14วันดีที่สุดทุกเครื่อง; ควรตรวจว่าประวัติแต่ละช่วงมีdistributionเดียวกันหรือไม่ก่อนเลือกlookback. 20minเป็นsensitivitysliceและเก็บได้เฉพาะonsetที่รู้ จึงไม่ใช้เป็นกฎตัดข้อมูลจริงจากผลนี้'''))
    nbformat.validate(nb); nbformat.write(nb,path)
    return path


if __name__=='__main__':
    print(build_notebook())
