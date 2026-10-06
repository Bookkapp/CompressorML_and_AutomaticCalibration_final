"""Executed notebook and source-backed figures for historical shadow ablation."""
from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
import numpy as np
import pandas as pd

from notebooks.support.historical_shadow_reference_phase import ROOT, OUTPUT, PROTOCOL, FEATURES, sha, write_json
from notebooks.support.local_profile_model_selection_presentation import raw_case, broken_raw, spans

LABELS={'state_only':'State only', 'steady_reference':'Steady reference',
        'segment_reference':'Segment reference', 'segment_steady_reference':'Segment + steady'}
COLORS=['#1768AC','#499895','#B68243','#7766A4']


def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#8796A4',
        'figure.facecolor':'white','axes.facecolor':'white','grid.color':'#E1E8EE','grid.alpha':.7})


def save(fig,name,output=OUTPUT):
    folder=output/'figures';folder.mkdir(exist_ok=True)
    fig.savefig(folder/(name+'.png'),dpi=160,bbox_inches='tight')
    fig.savefig(folder/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)
    return fig


def tables(output=OUTPUT):
    return {k:pd.read_csv(output/(name+'.csv'),dtype={'machine':str},float_precision='round_trip') for k,name in
        [('profiles','reference_readiness'),('burden','shadow_burden'),('cases','known_case_regression'),
         ('matched','latest_matched_totals'),('days','past_day_segment_evidence')]}


def periods(output=OUTPUT):
    setup();p=tables(output)['profiles'].drop_duplicates('experiment')
    fig,ax=plt.subplots(figsize=(13.8,5.7),layout='constrained')
    for i,row in p.reset_index(drop=True).iterrows():
        a,b,c=[mdates.date2num(pd.Timestamp(row[x])) for x in ['fit_start','shadow_start','shadow_end']]
        if row.fit_days:
            ax.broken_barh([(a,b-a)],(i-.3,.6),facecolors='#BDD5E8')
        else:
            ax.broken_barh([(a,b-a)],(i-.3,.6),facecolors='#F4F6F8',edgecolors='#AAB4BF',hatch='///')
            ax.text((a+b)/2,i,'No past source for reference',ha='center',va='center',fontsize=8,color='#576775')
        ax.broken_barh([(b,c-b)],(i-.3,.6),facecolors='#1768AC')
        ax.text(c+.35,i,pd.Timestamp(row.shadow_end).strftime('end %d %b'),va='center',fontsize=9)
    ax.set(yticks=range(len(p)),yticklabels=p.experiment.str.replace('latest_mx','Latest MX').str.replace('case_mx','Case MX'),
           title='28 past calendar days for fit → 3 disjoint complete days for shadow')
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1));ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.set_xlim(pd.Timestamp('2026-07-30'),pd.Timestamp('2026-10-05'));ax.invert_yaxis();ax.grid(axis='x')
    fig.suptitle('Historical shadow: no need to wait three future wall-clock days',fontsize=16)
    fig.text(.09,-.005,'Light blue: requested fit interval, not full data coverage  |  Hatched: no fit data  |  Dark blue: shadow  |  Asia/Bangkok; exclusive end',fontsize=9)
    return save(fig,'01_historical_time_splits',output)


def readiness(output=OUTPUT):
    setup();t=tables(output);p=t['profiles'].loc[lambda x:x.experiment.str.startswith('latest_')]
    machines=sorted(p.machine.unique());fig,axes=plt.subplots(1,4,figsize=(14,5.5),layout='constrained')
    from matplotlib.colors import ListedColormap
    for ax,(variant,label) in zip(axes,LABELS.items()):
        part=p.loc[p.variant.eq(variant)].copy()
        part['code']=np.where(~part.supported,0,np.where(part.status.eq('SCREENED_NOT_APPROVED'),2,1))
        mat=part.pivot(index='machine',columns='module',values='code').reindex(index=machines,columns=range(1,9))
        ax.imshow(mat,cmap=ListedColormap(['#E1E6EC','#E8BF8D','#A5C8DC']),vmin=0,vmax=2,aspect='auto')
        for i in range(len(machines)):
            for j in range(8):ax.text(j,i,['–','R','S'][int(mat.iloc[i,j])],ha='center',va='center',fontsize=9)
        ax.set(xticks=range(8),xticklabels=range(1,9),yticks=range(len(machines)),
               yticklabels=['MX'+m for m in machines],xlabel='Module',title=label)
    fig.suptitle('Reference support changes by machine × module; none is Active',fontsize=16)
    fig.text(.09,-.008,'S: screened but not approved  |  R: supported but needs review  |  –: insufficient  |  Screening uses past fit only',fontsize=9)
    return save(fig,'02_reference_readiness',output)


def burden(output=OUTPUT):
    setup();t=tables(output);matched=t['matched'].set_index('variant').loc[list(LABELS)]
    fig,axes=plt.subplots(1,2,figsize=(13.5,5.4),layout='constrained')
    rates=matched.persistent_percent.to_numpy()
    bars=axes[0].bar(range(4),rates,color=COLORS,width=.6)
    for bar,(_,r) in zip(bars,matched.iterrows()):
        axes[0].text(bar.get_x()+bar.get_width()/2,bar.get_height()+.5,f'{r.persistent_percent:.2f}%\n{int(r.persistent_minutes):,}',ha='center',fontsize=10)
    axes[0].set(xticks=range(4),xticklabels=['State\nonly','Steady\nreference','Segment\nreference','Segment\n+ steady'],
        ylabel='Persistent flagged minutes / evaluated minutes (%)',title='Identical latest-window cohort',ylim=(0,max(rates)*1.35+2))
    axes[0].grid(axis='y')
    b=t['burden'];b=b.loc[b.experiment.str.startswith('latest_')]
    availability=b.groupby('variant')[['qualified_minutes','evaluated_minutes']].sum().loc[list(LABELS)]
    evaluated=availability.evaluated_minutes;unsupported=availability.qualified_minutes-evaluated
    axes[1].barh(range(4),evaluated/1000,color=COLORS,height=.55)
    axes[1].barh(range(4),unsupported/1000,left=evaluated/1000,color='#DDE4EB',height=.55)
    for i,(_,r) in enumerate(availability.iterrows()):
        axes[1].text(r.qualified_minutes/1000+1,i,f'{int(r.evaluated_minutes):,}/{int(r.qualified_minutes):,}',va='center',fontsize=9)
    axes[1].set(yticks=range(4),yticklabels=list(LABELS.values()),xlabel='Qualified minutes (thousands)',
        xlim=(0,availability.qualified_minutes.max()/1000*1.40),title='All latest contexts: coverage stays visible')
    axes[1].invert_yaxis();axes[1].grid(axis='x')
    fig.suptitle('A lower flag count is not, by itself, a better detector',fontsize=16)
    fig.text(.08,-.01,'Left: matched supported contexts only  |  Right: grey = no supported reference  |  No confirmed healthy negatives: not FPR',fontsize=9)
    return save(fig,'03_burden_and_coverage',output)


def baseline_example(output=OUTPUT):
    setup();t=tables(output);day=t['days'];p=t['profiles']
    d=day.loc[day.experiment.eq('latest_mx080')&day.module.eq(6)].copy()
    refs=p.loc[p.experiment.eq('latest_mx080')&p.module.eq(6)].set_index('variant')
    fig,axes=plt.subplots(1,2,figsize=(13.5,5),layout='constrained')
    axes[0].plot(pd.to_datetime(d.day),d.hp2,color='#1768AC',lw=2,marker='o',ms=4,label='Past day median Hp2')
    chosen=d.loc[d.selected]
    if len(chosen):
        axes[0].scatter(pd.to_datetime(chosen.day),chosen.hp2,color='#B68243',s=55,zorder=4,label='Selected longest segment')
    else:
        axes[0].text(.03,.90,'No segment met the 7-day minimum',transform=axes[0].transAxes,fontsize=9,color='#715A3E')
    axes[0].set(ylabel='Hp2 (psi, source convention)',title='MX080 / M6 | past fit days only');axes[0].grid(axis='y');axes[0].legend(fontsize=9)
    axes[0].xaxis.set_major_locator(mdates.WeekdayLocator());axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    for i,(variant,label) in enumerate(LABELS.items()):
        r=refs.loc[variant]
        if pd.notna(r.get('hp2_median')):
            axes[1].errorbar(r.hp2_median,i,xerr=r.hp2_scale,fmt='o',capsize=5,color=COLORS[i],lw=2)
            axes[1].text(r.hp2_median+r.hp2_scale+4,i,f's={r.hp2_scale:.2f}',va='center',fontsize=9)
        else:axes[1].text(180,i,'Insufficient reference',fontsize=9)
    axes[1].set(yticks=range(4),yticklabels=list(LABELS.values()),xlabel='Past median ± one robust scale (not normal limits)',
                title='How the reference changes before shadow');axes[1].set_ylim(3.5,-.5);axes[1].grid(axis='x')
    fig.suptitle('Do not let a mixed reference absorb a shifted plateau',fontsize=16)
    fig.text(.08,-.008,'Stable does not mean healthy. Multiple supported segments require review; segment selection is not an automatic service epoch.',fontsize=9)
    return save(fig,'04_reference_level_and_scale',output)


def phase_workload(output=OUTPUT):
    setup();b=tables(output)['burden'];b=b.loc[b.experiment.str.startswith('latest_')]
    mat=b.pivot(index=['experiment','machine','module'],columns='variant',values='evaluated_minutes')
    common=mat.index[mat.gt(0).all(axis=1)&mat.nunique(axis=1).eq(1)]
    b=b.set_index(['experiment','machine','module']).loc[common].reset_index()
    counts=b.groupby('variant')[['steady_persistent','changing_persistent','unknown_history_persistent']].sum().loc[list(LABELS)]
    fig,ax=plt.subplots(figsize=(12.8,5),layout='constrained');left=np.zeros(4)
    for col,label,color in [('steady_persistent','Steady candidate','#1768AC'),
            ('changing_persistent','Changing / settling','#B68243'),('unknown_history_persistent','Insufficient trailing history','#A5AFBB')]:
        ax.barh(range(4),counts[col],left=left,color=color,label=label,height=.56);left+=counts[col].to_numpy()
    ax.set(yticks=range(4),yticklabels=list(LABELS.values()),xlabel='Persistent flagged minutes (same supported contexts)',
           title='Phase provides context; no phase is used to hide a score');ax.invert_yaxis();ax.grid(axis='x')
    ax.legend(fontsize=9,loc='upper left',bbox_to_anchor=(1.01,1))
    fig.text(.08,-.008,'Steady = low trailing slope/variation, not a healthy label. Unknown actual onset is retained separately in the evidence tables.',fontsize=9)
    return save(fig,'05_phase_attribution',output)


def observed_starts(output=OUTPUT):
    """Raw seconds from bounded observed Run starts; no healthy-cycle fitting."""
    setup();path=ROOT/'notebooks/outputs/october_three_machine_calibration_v1/raw_run_trajectories.parquet'
    d=pd.read_parquet(path,filters=[('module','==',6)])
    d['start']=pd.to_datetime(d.event_id.str.split('-RUN-').str[-1])
    d=d.loc[d.start.ge('2026-08-31') & d.start.lt('2026-09-28') & d.elapsed.le(1200)]
    fig,axes=plt.subplots(2,3,figsize=(13.8,6.9),sharex=True,layout='constrained')
    support=[]
    for col,machine in enumerate(['017','024','080']):
        part=d.loc[d.machine.eq(machine)]
        all_ids=part[['event_id','start']].drop_duplicates().sort_values('start')
        ids=all_ids.head(18).event_id;part=part.loc[part.event_id.isin(ids)]
        count=part.event_id.nunique();days=part.start.dt.normalize().nunique()
        support.append(dict(machine=machine,module=6,available_sampled_run_starts=len(all_ids),plotted_starts=count,
                            plotted_days=days,fit_period_start='2026-08-31',fit_period_end_exclusive='2026-09-28',healthy_labels=False))
        for ax,field,label in [(axes[0,col],'hp2','Hp2 (psi)'),(axes[1,col],'templo','TempLo (°C)')]:
            for _,g in part.groupby('event_id',sort=False):
                g=g.sort_values('elapsed');ax.plot(g.elapsed/60,g[field],color='#1768AC',alpha=.22,lw=.8)
            ax.set_ylabel(label);ax.grid(axis='y')
        axes[0,col].set_title(f'MX{machine} / M6 | {count} plotted starts, {days} days')
        axes[1,col].set(xlabel='Observed seconds after Run entry / 60',xlim=(0,20))
        if count==0:axes[0,col].text(.5,.5,'No supported sampled starts',transform=axes[0,col].transAxes,ha='center')
    pd.DataFrame(support).to_csv(output/'plotted_observed_start_support.csv',index=False)
    fig.suptitle('Observed starts have different initial levels and responses',fontsize=16)
    fig.text(.08,-.005,'Source-second trajectories, earliest 18 sampled starts per machine in past fit. Not healthy labels, no fitted startup envelope, no fixed 20-minute suppression.',fontsize=9)
    return save(fig,'05b_observed_run_starts',output)


def case_coverage(output=OUTPUT):
    setup();c=tables(output)['cases'];fig,axes=plt.subplots(1,2,figsize=(13.5,4.8),layout='constrained')
    for ax,machine,label in zip(axes,['057','080'],['MX057 / M1 | 29 Aug','MX080 / M6 | 7 Sep']):
        rows=c.loc[c.machine.eq(machine)].set_index('variant')
        for i,variant in enumerate(LABELS):
            r=rows.loc[variant];v=r.persistent_coverage_percent
            ax.barh(i,v if pd.notna(v) else 0,color=COLORS[i],height=.55)
            text=f'{v:.2f}% | {int(r.persistent_minutes)}/{int(r.qualified_minutes)}' if r.evaluated_minutes else 'No supported reference'
            ax.text(102,i,text,va='center',fontsize=9)
        ax.set(yticks=range(4),yticklabels=list(LABELS.values()),xlim=(0,155),xticks=[0,25,50,75,100],xlabel='Case qualified-minute coverage (%)',title=label)
        ax.invert_yaxis();ax.grid(axis='x')
    fig.suptitle('Known behavioral anomaly regression — no threshold tuning on these cases',fontsize=16)
    fig.text(.08,-.005,'Owner-confirmed behavior only; no cause/fault class. Denominator includes qualified case minutes even when a profile is unsupported.',fontsize=9)
    return save(fig,'06_case_coverage',output)


def raw_case_panel(machine='080',output=OUTPUT):
    setup();legacy=ROOT/'notebooks/outputs/local_profile_model_selection_v1'
    raw=raw_case(legacy,machine)
    a,b=('2026-09-07 11:45','2026-09-07 14:00') if machine=='080' else ('2026-08-29 03:45','2026-08-29 06:00')
    raw=raw.loc[raw.stamp.ge(a)&raw.stamp.lt(b)]
    module=6 if machine=='080' else 1
    s=pd.read_parquet(output/'shadow_scores.parquet',filters=[('experiment','==','case_mx'+machine),('module','==',module)])
    s=s.loc[s.stamp.ge(a)&s.stamp.lt(b)]
    fig,axes=plt.subplots(5,1,figsize=(13.5,9.5),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[1.7,1.5,1.1,.7,1.2]})
    for f,col in [('hp2','#CB566A'),('lp2','#1768AC')]:axes[0].plot(raw.stamp,broken_raw(raw,f),label=f,color=col,lw=1.1)
    for f,col in [('temphi','#BA8143'),('templo','#499895')]:axes[1].plot(raw.stamp,broken_raw(raw,f),label=f,color=col,lw=1.1)
    axes[2].plot(raw.stamp,broken_raw(raw,'valve'),color='#4F667B',lw=1.1,label='Expansion valve')
    axes[0].set_ylabel('Pressure (psi)');axes[1].set_ylabel('Temperature (°C)');axes[2].set_ylabel('Valve counts')
    controls=[('busy',lambda x:x.astype(str).eq('1'),'Busy=1'),('status',lambda x:x.ne('On'),'Module ≠ On'),
              ('sv',lambda x:x.ne('Off'),'SV ≠ Off'),('compressor_status',lambda x:x.ne('Run'),'Status ≠ Run')]
    for i,(f,fn,label) in enumerate(controls):
        axes[3].axhline(i,color='#E1E8EE',lw=.8)
        active=raw.loc[fn(raw[f]),['stamp']]
        groups=active.stamp.diff().ne(pd.Timedelta(seconds=1)).cumsum()
        for _,g in active.groupby(groups):
            left=mdates.date2num(g.stamp.iloc[0]);right=mdates.date2num(g.stamp.iloc[-1]+pd.Timedelta(seconds=1))
            axes[3].broken_barh([(left,right-left)],(i-.25,.5),facecolors=COLORS[i])
    axes[3].set(yticks=range(4),yticklabels=[x[2] for x in controls],ylabel='',ylim=(-.5,3.5))
    axes[3].tick_params(axis='y',labelsize=8)
    for i,(variant,label) in enumerate(LABELS.items()):
        d=s.loc[s.variant.eq(variant)];hits=d.loc[d.persistent]
        axes[4].scatter(hits.stamp,np.full(len(hits),i),s=8,color=COLORS[i],marker='s')
        if not d.score.notna().any():
            axes[4].text(pd.Timestamp(a)+(pd.Timestamp(b)-pd.Timestamp(a))/2,i,'Not evaluated: no supported reference',
                         ha='center',va='center',fontsize=9,color='#707E8B')
    axes[4].set(yticks=range(4),yticklabels=list(LABELS.values()),ylabel='Persistent')
    axes[4].set_ylim(3.5,-.5);axes[4].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    for ax in axes[:3]:ax.legend(loc='upper left',fontsize=9);ax.grid(axis='y')
    fig.suptitle(f'MX{machine} / M{module} | actual observed seconds + completed-minute decisions',fontsize=16)
    fig.text(.08,-.005,'No interpolated seconds. Alert markers stay in their own strip; pressure and temperature panels are not shaded by an unrelated contributor.',fontsize=9)
    return save(fig,'07_raw_case_'+machine,output)


def make_notebook(output=OUTPUT):
    nb=nbformat.v4.new_notebook();m=nbformat.v4.new_markdown_cell;c=nbformat.v4.new_code_cell
    nb.cells=[m('''# 08M — ทดลองเลือกช่วงอ้างอิงและ Shadow ย้อนหลัง 3 วัน

## อ่านผลนี้เพื่ออะไร

คำถามคือ **การสร้างโปรไฟล์ให้เหมาะกับเครื่องแต่ละตัว ควรคัดช่วงข้อมูลอย่างไร โดยไม่เผลอทำให้ความผิดปกติกลายเป็นค่าปกติใหม่**

เล่มนี้เปรียบเทียบ 4 วิธีบนข้อมูลจริง 9 เครื่อง ทุกโมดูล ผลถูกคำนวณและบันทึกแล้ว ไม่ใช่กราฟตัวอย่าง ไม่มีการเปลี่ยน Active Profile, threshold ที่ใช้งานจริง, MySQL หรือ Server

กราฟใช้ภาษาอังกฤษเพื่อให้ฟอนต์แสดงตรงกันเมื่อย้ายไป Colab; คำอธิบายและการตีความใช้ภาษาไทย งานนี้เป็น retrospective experiment บนข้อมูลที่เคยเปิดดู ไม่ใช่ blind test และไม่มีชุดช่วงปกติที่ช่างยืนยันครบ จึงยังรายงาน accuracy หรือ false-positive rate ไม่ได้'''),
    m('''## 1. ข้อมูลมาจากที่ไหน

| เครื่อง | ต้นทาง | Shadow ล่าสุดในงานนี้ |
|---|---|---|
| MX017, MX024, MX080 | ZIP Compressor dynamic logs ที่ตรวจใน Notebook 08K; ไม่ใช้ `_Static.txt` | 28–30 Sep 2026 |
| MX029, MX041, MX057, MX070 | raw Parquet ที่ตรวจใน Notebook 08L; 1 Sep เป็นวันไม่เต็ม | 29–31 Aug 2026 |
| MX118, MX119 | raw Parquet; มีเพียง 17–20 Aug และ 20 Aug เป็นวันไม่เต็ม | 17–19 Aug; ไม่มีอดีตพอสร้าง reference |

ตรวจทั้ง M1–M8; M7 หรือบริบทข้อมูลน้อยยังแสดงเป็น insufficient ไม่ซ่อนออก กราฟเคสอาศัย observed raw seconds ของ MX080/M6 และ MX057/M1 โดยตรวจค่าเฉลี่ยกับ minute cache อีกครั้ง

**Grain:** raw observed seconds → completed 1-minute windows; source time ใช้ Asia/Bangkok ตาม local archive convention ไม่ได้ยืนยัน timezone ของ Server จากการทดลองนี้ ไม่มีการเติมวินาทีที่ขาด

**Gate ที่สืบทอด:** ต้องมี ≥57 unique seconds, ไม่ซ้ำ, gap ≤5 วินาที, ตลอดนาทีมี `Status=Run`, module `On`, Busy=0, SV=Off และ sensor finite. Manual/ChangeValve/SV events ไม่ถูกลบจาก raw evidence แต่ไม่ใช้ fit steady Cold

**รันซ้ำ:** ต้องมี support scripts และ output caches ของ 08K/08L ในโครงสร้างโครงการเดียวกัน; Git ไม่ได้บรรจุ raw telemetry. เปิดบน Colab ให้ upload/mount โฟลเดอร์โปรเจกต์พร้อม cache ส่วนตัว ตั้ง `PROJECT_ROOT` ตามจริง และใช้ dependency versions ใน summary. Notebook ไม่เชื่อม Database'''),
    c('''from pathlib import Path
import sys, json
import pandas as pd
from IPython.display import display
# Colab: set an explicit mounted project directory if needed.
PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "research/historical_shadow_reference_phase_protocol_v1.json").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "research/historical_shadow_reference_phase_protocol_v1.json").exists():
    raise FileNotFoundError("Set PROJECT_ROOT to the project folder; upload/mount private 08K/08L caches separately.")
sys.path.insert(0, str(PROJECT_ROOT))
from notebooks.support.historical_shadow_reference_phase import run, sha
from notebooks.support import historical_shadow_reference_phase_presentation as viz
from IPython import get_ipython
get_ipython().run_line_magic("matplotlib", "inline")
OUT = PROJECT_ROOT / "notebooks/outputs/historical_shadow_reference_phase_v1"
RUN_EXPERIMENT = False  # True rebuilds all numerical comparisons from private minute caches; no SQL.
if RUN_EXPERIMENT:
    run(OUT)
summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
assert sha(OUT / "shadow_scores.parquet") == summary["score_sha256"]
assert sha(PROJECT_ROOT / "research/historical_shadow_reference_phase_protocol_v1.json") == summary["protocol_sha256"]
t = viz.tables(OUT)
display(pd.DataFrame([{k: summary[k] for k in ["contexts", "matched_contexts", "latest_matched_contexts", "cache_files", "runtime_seconds"]}]))'''),
    m('''## 2. แบ่งวันอย่างไรไม่ให้ข้อมูลรั่ว

ให้ $D$ เป็นเที่ยงคืนของวันที่ตัดข้อมูลตามเวลาเครื่อง: Shadow = $[D-3d,D)$, Fit = $[D-31d,D-3d)$. ข้อมูลวันนี้ไม่เข้า Shadow และแถวเดียวกันไม่มีทางเข้า Fit กับ Shadow

สำหรับชุดล่าสุด 3 เครื่อง: Fit 31 Aug–27 Sep, Shadow 28–30 Sep, cutoff 1 Oct. อีก 4 เครื่อง cutoff เป็น 1 Sep และ 2 เครื่องข้อมูลน้อย cutoff 20 Aug ตาม inventory รายเครื่อง ไม่ใช่วันที่ล่าสุดของ fleet รวม

QA รอบแรกจับได้ว่าการใช้ fleet cutoff 9 Sep ให้ 6 เครื่องทำให้ Shadow ไม่มีข้อมูล จึงแก้เฉพาะ source cutoff ก่อนสรุป ไม่ปรับ method parameter ตามผล และไม่ใช้ผลรอบนั้นเลือกวิธี; audit อยู่ใน protocol

เคสย้อนหลังแยกออกรายงาน regression: MX080 Shadow 5–7 Sep และ MX057 Shadow 27–29 Aug. ไม่ใช้ผลเคสเลือก parameter, threshold หรือ segment และไม่รวมซ้ำใน headline fleet rate

นี่เป็น **numerical shadow replay** ไม่ได้จำลอง source late-commit, timezone Server, downtime หรือทำทะเบียน Profile/Approval จริง. Historical shadow ทำงานเร็วขึ้นได้ แต่ยังต้องตรวจ production integration แยก'''),
    c('display(viz.periods(OUT))'),
    m(r'''## 3. สูตรที่ใช้ และสิ่งที่เปลี่ยนในแต่ละวิธี

ทั้ง 4 วิธีใช้ score/persistence เดียวกัน ต่างกันเฉพาะ **แถว Fit ที่เลือก**:

1. State only: ทุกนาทีผ่าน gate ในอดีต
2. Steady reference: เลือกอดีตที่ slope/variation ต่ำต่อเนื่อง
3. Segment reference: แยกอดีตเมื่อ day median กระโดด แล้วเลือก segment มีหลักฐานพอ
4. Segment + steady: ใช้สองข้อร่วมกัน

สำหรับ feature $j$ ในแถว Fit:

$$m_j=\mathrm{median}(x_j),\quad s_j=\max(1.4826\,MAD_j, IQR_j/1.349, f_j)$$
$$z_j(t)=\frac{x_j(t)-m_j}{s_j},\quad A_t=\max_j |z_j(t)|$$

ใช้ feature 9 ตัว: hp1, lp1, hp2, lp2, Valve, TempHi, TempLo, $dp1=hp1-lp1$, $dp2=hp2-lp2$. Floor Valve=1 count, อื่น=.1 source unit. Quarantine แถว Fit ที่ initial $A>8$, fit รอบสองจากแถวที่เหลือ, cut = Q99.5 ของ retained Fit; flag เมื่อ $A_t\ge cut$. Persistent ต้อง flag 3 นาทีที่ติดกันจริง ข้อมูลขาด/นาทีไม่ผ่าน gate ตัด continuity

Scale สูตรนี้สืบทอด **research 08K/08L**, ไม่อ้างว่าเท่ากับ robust-scale implementation/Active Profile จริงทุกตัว การทดลองไม่เปลี่ยน production scale

### ช่วงนิ่งที่เราทดลอง ไม่ใช่ normal label

ใช้ 5 นาที **ที่ผ่านมาเท่านั้น** บนค่าเฉลี่ยนาทีที่มีคุณภาพ:

$$S_j(t)=\left|\mathrm{median}_{0\le a<b<5}\frac{x_j(t-4+b)-x_j(t-4+a)}{b-a}\right|$$
$$V_j(t)=1.4826\,\mathrm{median}_{u=t-4}^{t}|x_j(u)-\mathrm{median}(x_j(t-4:t))|$$

ขีดจำกัดแต่ละ feature = Q90 ของ S/V จากอดีต Fit เท่านั้น พร้อม minimum floors ที่ดูได้ใน code/protocol. ต้องต่ำกว่า limits ทุก feature ต่อเนื่อง 3 windows จึงเรียก `STEADY_CANDIDATE`; เริ่มใหม่หลัง gap/control boundary. สถานะ `CHANGING_OR_SETTLING` ไม่ได้พิสูจน์ normal startup; ไม่มี onset ให้เรียก unknown onset ตามจริง

**สำคัญ:** Phase ไม่ปิด score/flag ช่วงเริ่มทำงาน กราฟนิ่งที่ Hp2=340 ยังตรวจ deviation ได้ ไม่ได้กลายเป็น Normal เพราะ slope ต่ำ

### Segment ช่วยอะไร

เปรียบเทียบ day median ของ hp2/lp2/TempHi/TempLo ระหว่างวันติดกัน หารด้วย median within-day MAD scales (pressure floor .1, temperature .05). Max normalized jump >6 หรือวันขาด จะเริ่ม segment ใหม่. วันต้องมี ≥60 qualified minutes; segment ต้องมี ≥7 วันและ ≥200 นาที เลือก segment มีนาทีมากที่สุด ถ้าเสมอเลือกก่อน ไม่เลือกจากผล Shadow

ถ้ามีหลาย supported segments ต้อง review: ไม่มี service records ที่พิสูจน์ว่าค่าใหม่หลัง manual เป็นค่าปกติ ไม่มี HPO รอบนี้ ตัวเลขทั้งหมดล็อกใน protocol ก่อนรันผล'''),
    c('display(viz.readiness(OUT))\ndisplay(t["profiles"].groupby(["variant", "status"]).size().rename("contexts").reset_index())'),
    m('''## 4. ดูการเตือนควบคู่กับ coverage

กราฟซ้ายเปรียบเทียบนาทีเดียวกันเฉพาะบริบทที่ทั้ง 4 วิธีมี reference พอ. กราฟขวาแสดงทุกบริบทล่าสุด: สีเทาคือ qualified แต่ไม่มี reference รองรับ ไม่ใช่ Normal

โปรไฟล์กว้างจากการปนหลายระดับอาจทำให้เตือนน้อย ขณะที่คัด reference ให้แคบอาจเตือนมากขึ้น ทั้งสองกรณีต้องดูเหตุการณ์จริงและ negative periods ที่ยืนยันก่อนตัดสินว่าดีกว่า. การเพิ่ม/ลด flag rate ไม่ใช่ accuracy'''),
    c('display(viz.burden(OUT))\ndisplay(t["matched"].round(3))'),
    c('display(viz.baseline_example(OUT))'),
    m('''## 5. แยกบริบทของแถบเตือน

แสดง persistent minutes ที่อยู่ในช่วง stable/changing/history insufficient โดยยังเก็บ score ทั้งหมด สัดส่วน onset observed มีอยู่ใน `shadow_burden.csv`; ไม่ตีช่วงแรกของไฟล์เป็น compressor restart

ยังไม่มี trajectory envelope ของ healthy startups ที่ช่างทบทวนครบ การทดลองนี้ทดสอบ causal steady selector ไม่ใช่ trained startup-normal model. ถ้าจะลด normal-startup alarm ต้องแยก observed start / Cold entry / post-manual และ validate หลายรอบก่อน'''),
    c('display(viz.phase_workload(OUT))'),
    m('''### หลายรอบเริ่มทำงานหน้าตาเหมือนกันหรือไม่

กราฟต่อไปใช้ raw seconds จาก observed `Run` transitions ของ 3 เครื่อง/M6 ในช่วง Fit 31 Aug–27 Sep เท่านั้น แสดงต้นรอบตามเวลา ไม่เลือกเพราะกราฟดูสวย. เส้นละหนึ่งรอบ; จำกัดภาพที่ 18 รอบจาก archive ที่ sample ไว้ มีตารางจำนวนรอบ/วันประกอบ

เส้นที่นิ่งอยู่ระดับสูงยังไม่ถูกเรียก healthy และไม่รวม median เป็น normal envelope เพราะไม่มี healthy-cycle review. กราฟนี้ชี้ว่า initial conditions และการตอบสนองไม่เหมือนกัน แต่ไม่ได้พิสูจน์ว่าแต่ละเส้นมี fault. ถ้ารอบมีน้อย ให้แสดงตามจริง ไม่ยืดให้ครบจำนวน'''),
    c('display(viz.observed_starts(OUT))\ndisplay(pd.read_csv(OUT / "plotted_observed_start_support.csv", dtype={"machine":str}))'),
    m('''## 6. ตรวจว่าเคสที่รู้แล้วไม่หาย

MX080/M6 ช่วง 7 Sep และ MX057/M1 ช่วง 29 Aug เป็น owner-confirmed **behavioral anomaly** ไม่ใช่ cause label. Coverage นับ persistent/qualified case minutes รวมกรณี unsupported ใน denominator. First persistent เป็นเวลา minute decision ภายใต้ replay ไม่ใช่ real ingestion latency

กราฟ raw seconds แยกหน่วยและมีแถบ decision ด้านล่าง ไม่ย้อม pressure แดงเพราะ temperature contributor. การเปลี่ยน Valve/Busy เป็น control context ไม่ใช่ confirmed refill หรือ fault'''),
    c('display(viz.case_coverage(OUT))\ndisplay(t["cases"].round(3))'),
    c('display(viz.raw_case_panel("080", OUT))'),
    c('display(viz.raw_case_panel("057", OUT))'),
    m('''## 7. สรุปสำหรับตัดสินใจ

อย่าเลือกวิธีจากจำนวนแถบแดงเพียงอย่างเดียว อ่านพร้อมกัน 4 อย่าง: จำนวน reference ที่มีหลักฐานพอ, scale/ระดับที่ใช้, coverage ของทุกบริบท และเคสที่ต้องไม่หาย

**ผลจริงของรอบนี้:** บน 37 บริบท/123,658 นาทีที่ทั้งสี่วิธีรองรับ วิธีเดิมเตือน 11.72%, steady 12.85%, segment 27.96%, segment+steady 33.80%. ตัวเลขนี้เป็นภาระการตรวจ ไม่ใช่ false-positive rate. Segment ไม่ได้ชนะและมี coverage ต่ำกว่า; MX080/M6 ไม่มี segment ผ่านขั้นต่ำ

State-only และ steady ยังครอบคลุมเคส MX080/M6 686/692 นาที (99.13%) และ MX057/M1 1,124/1,124 นาที (100%). เป็น case regression ไม่ใช่ accuracy. ก่อน Hp2 กระโดด ช่วง 11:45–12:20 ของ MX080 ทั้งสองวิธียัง flag 11/13 qualified minutes โดย dominant เป็น Lp1 จาก reference ใหม่ จึงยังแก้ startup specificity ไม่ได้ และไม่เท่ากับ contributor ของ Active Profile เดิม

**สิ่งที่ใช้ต่อได้ทันทีในแนวทางระบบ:** manual start ของงาน calibration, historical complete-day split ที่แยก fit/shadow, แสดง selected reference period + omitted days + phase evidence ใน approval report, เก็บ score ช่วงเปลี่ยนผ่าน ไม่ลบหลักฐาน. ทั้งหมดเป็นข้อเสนอ integration; code runtime ยังไม่ได้เปลี่ยน

**สิ่งที่ยังไม่ควรเปิดอัตโนมัติจากงานนี้:** เปลี่ยน Active ตาม segment ล่าสุด, suppress startup ตามเวลา, approve จาก low flag rate, หรือบอก leak/cause. ไม่มีการ train ML ใหม่ เพราะรอบนี้กำลังปรับคุณภาพ reference ที่ primary algorithm ใช้ ไม่ใช่เพิ่ม classifier

ดูผล/คำแนะนำจริงพร้อมข้อจำกัดใน `deployment/HISTORICAL_SHADOW_REFERENCE_PHASE_EXPERIMENT_20261001.md` และเปิด CSV เพื่อดูทุก machine × module โดยไม่รวมข้อมูลน้อยกับ Normal

### QA และขอบเขต

Tests ตรวจ prefix causality, train-only limits/fit/segment, gap reset, minimum days, disjoint calendar split, persistence และ stable abnormal plateau. Notebook รันทุก cell และตรวจ raw-minute parity อีกครั้ง. ข้อมูลต้นทาง/Active/DB/Serverไม่เปลี่ยน; ยังไม่มี production approval. Artifact hash ทำให้ตรวจได้ว่าผลตรงกับ input/protocol ใด'''),
    c('''receipt = json.loads((OUT / "input_receipt.json").read_text(encoding="utf-8"))
missing = [p for p in receipt if not (PROJECT_ROOT / p).exists()]
if missing:
    print(f"{len(missing)} private input caches not mounted; figures above use saved experiment outputs.")
else:
    assert all(sha(PROJECT_ROOT / p) == info["sha256"] for p, info in receipt.items())
    print(f"Verified SHA256 for {len(receipt)} private minute inputs.")
display(pd.DataFrame({"Boundary":["Runtime changed", "Active changed", "DB writes", "Server access"],
                      "Result":[summary[k] for k in ["runtime_changed", "active_changed", "db_writes", "server_access"]]}))''')]
    nb.metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
                 'language_info':{'name':'python','version':'3.12'},'colab':{'name':'08M_Historical_Shadow_Reference_and_Phase_Comparison_Colab.ipynb'}}
    path=ROOT/'notebooks/08M_Historical_Shadow_Reference_and_Phase_Comparison_Colab.ipynb'
    nbformat.write(nb,path);return path


def execute():
    started=time.perf_counter();path=make_notebook();nb=nbformat.read(path,as_version=4)
    NotebookClient(nb,timeout=240,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.validate(nb);nbformat.write(nb,path)
    html,_=HTMLExporter().from_notebook_node(nb);(OUTPUT/'08M_executed_preview.html').write_text(html,encoding='utf-8')
    code=[c for c in nb.cells if c.cell_type=='code'];errors=[o for c in code for o in c.outputs if o.output_type=='error']
    png=sum('image/png' in o.get('data',{}) for c in code for o in c.outputs)
    if errors or png<9 or not all(c.execution_count for c in code):raise AssertionError('Incomplete notebook execution')
    raw_parity=[]
    for machine,module,day in [('080',6,'2026-09-07'),('057',1,'2026-08-29')]:
        raw=raw_case(ROOT/'notebooks/outputs/local_profile_model_selection_v1',machine)
        raw=raw.loc[raw.stamp.ge(day)&raw.stamp.lt(pd.Timestamp(day)+pd.Timedelta(days=1))]
        raw['minute']=raw.stamp.dt.floor('min')
        # Compare only complete raw minutes; forensic archive can have clipped edges.
        counts=raw.groupby('minute').stamp.nunique();idx=counts.index[counts.eq(60)]
        means=raw.groupby('minute')[FEATURES[:7]].mean().loc[idx]
        roots=[ROOT/'notebooks/outputs/october_three_machine_calibration_v1',ROOT/'notebooks/outputs/local_profile_model_selection_v1']
        cache=next(root/'minutes'/f'{machine}_{day}.parquet' for root in roots if (root/'minutes'/f'{machine}_{day}.parquet').exists())
        minute=pd.read_parquet(cache);minute=minute.loc[minute.module.eq(module)&minute.eligible].set_index('stamp')
        common=means.index.intersection(minute.index)
        delta=float(np.abs(means.loc[common].to_numpy()-minute.loc[common,FEATURES[:7]].to_numpy()).max()) if len(common) else None
        if not len(common) or delta>1e-8:raise AssertionError(f'MX{machine} source-second parity mismatch')
        raw_parity.append(dict(machine=machine,module=module,complete_qualified_minutes=len(common),max_abs_mean_difference=delta))
    qa=dict(code_cells=len(code),embedded_pngs=png,errors=len(errors),all_executed=True,
            elapsed_seconds=time.perf_counter()-started,notebook_sha256=sha(path),raw_minute_parity=raw_parity,
            raw_run_trajectory_sha256=sha(ROOT/'notebooks/outputs/october_three_machine_calibration_v1/raw_run_trajectories.parquet'),
            manual_visual_review='PENDING',runtime_changed=False,active_changed=False,db_writes=False,server_access=False)
    write_json(OUTPUT/'notebook_qa.json',qa);print(json.dumps(qa,indent=2))


if __name__=='__main__':execute()
