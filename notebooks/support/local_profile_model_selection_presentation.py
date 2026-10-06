"""Source-backed figures and executed notebook companion for the local trial."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd
import nbformat
import polars as pl

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'notebooks/outputs/local_profile_model_selection_v1'
NAMES={'self_legacy':'Self | original cut','self_separate':'Self | separate past cut',
       'arx':'ARX-Ridge','dpca':'DPCA Q/SPE','iforest':'Isolation Forest'}
COLORS={'self_legacy':'#1768AC','self_separate':'#68899C','arx':'#BD7B35','dpca':'#7568A8','iforest':'#478F85'}


def tables(output=OUTPUT):
    result={}
    for key,name in [('profiles','profile_readiness'),('coverage','machine_coverage'),('burden','future_burden_by_context'),
                     ('cases','case_regression'),('lomo','adapted_lomo_burden'),('correlations','train_within_day_correlations')]:
        result[key]=pd.read_csv(output/f'{name}.csv',dtype={'machine':str})
    result['summary']=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    return result


def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.titlesize':13,
                         'axes.labelsize':10.5,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.facecolor':'white','axes.facecolor':'white','grid.color':'#E1E7EE',
                         'grid.alpha':.7,'axes.edgecolor':'#8C98A3','savefig.bbox':'tight'})


def save(fig,name,output=OUTPUT):
    path=output/'figures';path.mkdir(exist_ok=True)
    fig.savefig(path/f'{name}.png',dpi=160)
    fig.savefig(path/f'{name}.svg')
    plt.close(fig)  # explicit display in the notebook, no duplicate end-of-cell image
    return fig


def source_and_reference(output=OUTPUT):
    setup();t=tables(output);c=t['coverage'];p=t['profiles']
    fig,axes=plt.subplots(1,2,figsize=(13.4,5.6),layout='constrained')
    y=np.arange(len(c));axes[0].barh(y,c.qualified_minutes/1000,color='#1768AC',height=.58)
    for i,row in c.iterrows():
        axes[0].text(row.qualified_minutes/1000+1,i,f'{row.qualified_minutes:,.0f}',va='center',fontsize=9)
    axes[0].set(yticks=y,yticklabels=['MX'+x for x in c.machine],xlabel='Strict qualified Cold minutes (thousands)',
                title='Nine machines audited; sparse machines remain visible',xlim=(0,c.qualified_minutes.max()/1000*1.32))
    axes[0].invert_yaxis();axes[0].grid(axis='x')
    status={'INSUFFICIENT_FIT':0,'INSUFFICIENT_AFTER_QUARANTINE':0,'REFERENCE_REVIEW_REQUIRED':1,'SCREENED_CANDIDATE_NOT_APPROVED':2}
    p['code']=p.status.map(status)
    matrix=p.pivot(index='machine',columns='module',values='code').reindex(index=c.machine,columns=range(1,9))
    from matplotlib.colors import ListedColormap
    axes[1].imshow(matrix,cmap=ListedColormap(['#DDE4EB','#EDC18B','#A9C9E1']),vmin=0,vmax=2,aspect='auto')
    for i in range(len(matrix)):
        for j in range(8):axes[1].text(j,i,['--','R','S'][int(matrix.iloc[i,j])],ha='center',va='center',color='#22384B')
    axes[1].set(xticks=range(8),xticklabels=[f'M{x}' for x in range(1,9)],yticks=range(len(matrix)),
                yticklabels=['MX'+x for x in matrix.index],title='Train-only reference screen | not Active approval')
    fig.suptitle('Local calibration is retained for every machine × module',fontsize=16)
    fig.text(.56,-.02,'S: screened candidate  |  R: needs reference review  |  --: insufficient history',fontsize=9,color='#4D5C69')
    return save(fig,'01_source_profile_readiness',output)


def baseline_and_relationship(output=OUTPUT):
    setup();t=tables(output);p=t['profiles'].dropna(subset=['hp2_median']);c=t['correlations']
    machines=sorted(t['coverage'].machine.unique())
    hp=p.pivot(index='machine',columns='module',values='hp2_median').reindex(index=machines,columns=range(1,9))
    corr=c[c.pair.eq('lp2/templo')].pivot(index='machine',columns='module',values='rho').reindex(index=machines,columns=range(1,9))
    corr=corr.where(hp.notna())  # sparse one-day fit correlations stay in the CSV, not an equivalent fleet reference
    fig,axes=plt.subplots(1,2,figsize=(13.4,5.8),layout='constrained')
    for ax,values,cmap,title,fmt,bounds,label in [
        (axes[0],hp,'Blues','Hp_2nd | past reference median','{:.0f}',(np.nanmin(hp),np.nanmax(hp)),'Source pressure (presumed psi)'),
        (axes[1],corr,'RdBu_r','Lp_2nd vs TempLo | within-day Spearman','{:+.2f}',(-1,1),'Spearman correlation')]:
        palette=plt.get_cmap(cmap).copy();palette.set_bad('#EDF1F5')
        im=ax.imshow(values,cmap=palette,vmin=bounds[0],vmax=bounds[1],aspect='auto')
        for i in range(len(values)):
            for j in range(8):
                value=values.iloc[i,j]
                text=fmt.format(value) if pd.notna(value) else '--'
                ax.text(j,i,text,ha='center',va='center',fontsize=9,
                        color='white' if pd.notna(value) and ((cmap=='Blues' and value>bounds[0]+.65*(bounds[1]-bounds[0])) or (cmap=='RdBu_r' and abs(value)>.65)) else '#23384C')
        ax.set(xticks=range(8),xticklabels=[f'M{x}' for x in range(1,9)],yticks=range(len(values)),
               yticklabels=['MX'+x for x in values.index],title=title)
        fig.colorbar(im,ax=ax,shrink=.7,label=label)
    fig.suptitle('Levels and relationships differ: one raw fleet baseline would hide this',fontsize=16)
    fig.text(.04,-.02,'Fit: 4–17 Aug 2026. Unsupported references blank. Qualified is not healthy; correlation is not causation.',color='#4D5C69',fontsize=9)
    return save(fig,'02_local_baselines_and_correlations',output)


def reference_quality(output=OUTPUT):
    setup();p=tables(output)['profiles'].dropna(subset=['quarantine_pct'])
    fig,ax=plt.subplots(figsize=(11.6,5.2),layout='constrained')
    for status,color,name in [('SCREENED_CANDIDATE_NOT_APPROVED','#1768AC','Screened, not approved'),
                              ('REFERENCE_REVIEW_REQUIRED','#BD7B35','Reference review required')]:
        b=p[p.status.eq(status)];ax.scatter(b.quarantine_pct,b.max_half_shift_z.clip(upper=20),c=color,s=43,alpha=.8,label=name)
    ax.axvline(5,color='#7C8A98',ls='--',lw=1);ax.axhline(1.5,color='#7C8A98',ls='--',lw=1)
    for _,row in p.sort_values('max_half_shift_z',ascending=False).head(5).iterrows():
        ax.annotate(f'MX{row.machine}/M{row.module}',(row.quarantine_pct,min(20,row.max_half_shift_z)),xytext=(5,5),textcoords='offset points',fontsize=8)
    ax.set(xlabel='First-pass quarantine (% of past fit minutes)',ylabel='Largest first-half → second-half median shift (local robust z)',
           title='Automatic calculation needs a stable reference, not just more data')
    ax.grid();ax.legend(frameon=False)
    fig.text(.05,-.025,'Dashed review gates: 5% quarantine and 1.5 z half-shift. Display cap: 20 z; full values are in the table.',fontsize=9,color='#4D5C69')
    return save(fig,'03_reference_quality_screen',output)


def matched_burden(output=OUTPUT):
    setup();t=tables(output);b=t['burden']
    # A common cohort across all five policies; omitted/unsupported contexts are explicit.
    wide=b.pivot(index=['machine','module'],columns='lane',values='rows')
    common=wide.index[wide.gt(0).all(axis=1)&wide.nunique(axis=1).eq(1)]
    kept=b.set_index(['machine','module']).loc[common].reset_index()
    total=kept.groupby('lane').agg(rows=('rows','sum'),flags=('persistent_flags','sum'),openings=('openings','sum'))
    total['pct']=100*total['flags']/total.rows
    machines=sorted(kept.machine.unique());lanes=list(NAMES)
    fig,axes=plt.subplots(1,2,figsize=(13.5,5.2),layout='constrained')
    for i,lane in enumerate(lanes):
        row=total.loc[lane];axes[0].barh(i,row.pct,color=COLORS[lane],height=.55)
        axes[0].text(row.pct+.4,i,f'{row.pct:.2f}% | {int(row.openings):,} openings',va='center',fontsize=9)
    axes[0].set(yticks=range(5),yticklabels=list(NAMES.values()),xlabel='Persistent flagged minutes / matched minutes (%)',
                title=f'Identical cohort: {int(total.rows.iloc[0]):,} minutes',xlim=(0,total.pct.max()*1.45))
    axes[0].invert_yaxis();axes[0].grid(axis='x')
    for i,lane in enumerate(lanes):
        per=kept[kept.lane.eq(lane)].groupby('machine').agg(rows=('rows','sum'),flags=('persistent_flags','sum'))
        axes[1].scatter(np.arange(len(machines))+(i-2)*.08,100*per.reindex(machines)['flags']/per.reindex(machines).rows,
                        color=COLORS[lane],label=NAMES[lane],s=37)
    axes[1].set(xticks=range(len(machines)),xticklabels=['MX'+x for x in machines],ylabel='Persistent flagged minutes (%)',
                title='Fleet average does not describe every machine')
    axes[1].grid(axis='y');axes[1].legend(frameon=False,fontsize=8)
    fig.suptitle('Flag burden is a workload diagnostic — not false-positive rate',fontsize=16)
    fig.text(.05,-.025,f'{len(common)} contexts with thresholds for every lane; previously inspected future, 26 Aug–8 Sep. No confirmed-negative set.',fontsize=9,color='#4D5C69')
    return save(fig,'04_matched_future_burden',output)


def case_comparison(output=OUTPUT):
    setup();c=tables(output)['cases'];fig,axes=plt.subplots(1,2,figsize=(12.7,4.8),layout='constrained')
    for ax,machine,title in zip(axes,['057','080'],['MX057 / M1 | 29 Aug','MX080 / M6 | 7 Sep']):
        b=c[c.machine.eq(machine)].set_index('lane')
        for i,lane in enumerate(NAMES):
            row=b.loc[lane];v=row.coverage_pct
            ax.barh(i,v if pd.notna(v) else 0,color=COLORS[lane],height=.55)
            label=f'{v:.1f}% | {int(row.persistent_rows)}/{int(row.supported_rows)}' if pd.notna(v) else 'Abstains: past threshold unavailable'
            ax.text(102,i,label,va='center',fontsize=9)
        ax.set(yticks=range(5),yticklabels=list(NAMES.values()),xlim=(0,160),xticks=[0,25,50,75,100],
               xlabel='Persistent coverage of matched case minutes (%)',title=title)
        ax.invert_yaxis();ax.grid(axis='x')
    fig.suptitle('Can the candidates retain the two owner-confirmed behavioral cases?',fontsize=16)
    fig.text(.03,-.02,'These known cases are regression checks, not an independent accuracy test. No cause, fault class or probability is inferred.',fontsize=9,color='#4D5C69')
    return save(fig,'05_known_case_regression',output)


def spans(ax,stamps,mask,color='#D86470',alpha=.16):
    series=pd.DataFrame({'stamp':stamps.to_numpy(),'flag':np.asarray(mask,dtype=bool)})
    picks=series[series.flag]
    if not len(picks):return
    starts=picks.stamp.diff().ne(pd.Timedelta(minutes=1)).cumsum()
    for _,g in picks.groupby(starts):ax.axvspan(g.stamp.iloc[0],g.stamp.iloc[-1]+pd.Timedelta(minutes=1),color=color,alpha=alpha,lw=0)


def raw_case(output=OUTPUT,machine='080'):
    if machine=='057':return pd.read_parquet(output/'raw_cases/MX057_M1_20260829.parquet')
    path=ROOT/'notebooks/outputs/mx080_module6_forensics_v1/module6_one_second_unique.parquet'
    d=pd.read_parquet(path)
    out=pd.DataFrame({f:d[f'{tag}_6'] for f,tag in zip(['hp1','lp1','hp2','lp2','valve','temphi','templo'],
                         ['Hp_1st','Lp_1st','Hp_2nd','Lp_2nd','Valve','TempHi','TempLo'])})
    out['stamp']=d.timestamp;out['status']=d.Status_6;out['busy']=d.Busy_6
    out['sv']=d.SV_6;out['compressor_status']=d.Status
    return out


def broken_raw(raw,field):
    # Plot-only NaNs break lines at genuinely missing seconds; no values synthesized.
    values=raw[field].copy();values.loc[raw.stamp.diff().gt(pd.Timedelta(seconds=2))]=np.nan
    return values


def case_timeline(output=OUTPUT,machine='080'):
    setup();module=6 if machine=='080' else 1
    start,end=(pd.Timestamp('2026-09-07 11:45'),pd.Timestamp('2026-09-07 14:00')) if machine=='080' else (pd.Timestamp('2026-08-29 03:45'),pd.Timestamp('2026-08-29 06:00'))
    onset=pd.Timestamp('2026-09-07 12:23:28') if machine=='080' else pd.Timestamp('2026-08-29 04:06')
    s=pl.scan_parquet(output/'matched_scores.parquet').filter(
        (pl.col('machine')==machine)&(pl.col('module')==module)&
        (pl.col('stamp')>=start.to_pydatetime())&(pl.col('stamp')<=end.to_pydatetime())).collect().to_pandas()
    r=raw_case(output,machine);r=r.loc[r.stamp.ge(start)&r.stamp.le(end)].copy()
    p=tables(output)['profiles'];p=p.loc[p.machine.eq(machine)&p.module.eq(module)].iloc[0]
    fig,axes=plt.subplots(6,1,figsize=(13.5,11.8),sharex=True,layout='constrained',height_ratios=[1,1,1.2,.9,1,.65])
    groups=[(['hp2'],'Hp_2nd\n(source psi)'),(['lp2'],'Lp_2nd\n(source psi)'),
            (['temphi','templo'],'Temperature\n(source °C)'),(['valve'],'Valve\n(command count)')]
    colors={'hp2':'#C54856','lp2':'#1768AC','temphi':'#BD7B35','templo':'#478F85','valve':'#7568A8'}
    for ax,(fields,label) in zip(axes,groups):
        for f in fields:
            ax.plot(r.stamp,broken_raw(r,f),color=colors[f],lw=1.3,label=f)
            ax.axhline(p[f'{f}_median'],color=colors[f],ls='--',lw=.9,alpha=.65)
        contributor=s.self_legacy_persistent & s[[f'z_{f}' for f in fields]].abs().ge(s.self_legacy_threshold,axis=0).any(axis=1)
        spans(ax,s.stamp,contributor)
        ax.set_ylabel(label);ax.grid(axis='y');ax.legend(loc='upper left',ncol=len(fields),frameon=False,fontsize=9)
        contributors=[f for f in fields if (s.self_legacy_persistent & s['z_'+f].abs().ge(s.self_legacy_threshold)).any()]
        ax.text(.99,.95,'Red contributor: '+', '.join(contributors) if contributors else 'No persistent Self contributor',
                transform=ax.transAxes,ha='right',va='top',fontsize=8,color='#9A4751' if contributors else '#697684')
    # Score ratios retain separate score units but share the decision boundary 1.
    missing=[]
    for lane in ['self_legacy','arx','dpca','iforest']:
        if s[lane+'_threshold'].isna().all():
            missing.append(NAMES[lane]);continue
        field='self_score' if lane=='self_legacy' else lane+'_score'
        ratio=s[field]/s[lane+'_threshold'].where(s[lane+'_threshold']>0)
        series=pd.Series(ratio.to_numpy(),index=s.stamp).reindex(pd.date_range(start,end,freq='min'))
        axes[4].plot(series.index,series,color=COLORS[lane],lw=1.2,label=NAMES[lane])
    axes[4].axhline(1,color='#6A7682',ls='--',lw=1)
    axes[4].set_yscale('symlog',linthresh=1);axes[4].set_ylabel('Score / cut\n(symlog)')
    axes[4].legend(ncol=4,frameon=False,fontsize=8);axes[4].grid(axis='y')
    if missing:
        axes[4].text(.01,.97,'Not scored: '+', '.join(missing)+' (past threshold block lacks 3 days)',
                     transform=axes[4].transAxes,va='top',fontsize=9,color='#99652D')
    states=pd.DataFrame({'manual':r.busy.astype(str).eq('1')|r.status.isin(['ChangeValve','MValveHome']),
                         'cold':r.compressor_status.eq('Run')&r.status.eq('On')&r.busy.astype(str).eq('0')&r.sv.eq('Off')})
    states['other']=~states[['cold','manual']].any(axis=1)
    for i,(name,color) in enumerate([('cold','#1768AC'),('manual','#BD7B35'),('other','#A3AFBA')]):
        points=r.stamp.loc[states[name]]
        axes[5].scatter(points,np.full(len(points),i),color=color,marker='|',s=24)
    axes[5].set(ylabel='Observed\nstate',yticks=[0,1,2],yticklabels=['Cold','Manual','Other'],ylim=(-.5,2.5))
    for ax in axes:ax.axvline(onset,color='#6E7882',ls=':',lw=1)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'));axes[-1].set_xlabel('Source clock (Asia/Bangkok assumption)')
    fig.suptitle(f'MX{machine} / M{module} | actual seconds, frozen past reference and model response',fontsize=16)
    fig.text(.025,-.025,'Dashed sensor lines: offline past medians. Red: that panel contributes to persistent Self, not physical cause. Manual data stay visible; steady models do not score them.',fontsize=9,color='#4D5C69')
    return save(fig,f'06_MX{machine}_M{module}_raw_second_case',output)


def workflow(output=OUTPUT):
    setup();fig,ax=plt.subplots(figsize=(13.8,6.2));ax.set(xlim=(0,14),ylim=(0,6));ax.axis('off')
    boxes=[(.2,4.3,2.25,1.05,'Observed raw seconds\npressure / temperature\nvalve / state'),(2.95,4.3,2.25,1.05,'Quality + context\nretain manual evidence\nsteady Cold eligibility'),
           (5.7,4.3,2.25,1.05,'Local calibration\nMachine × Module\nreference stability review'),(8.45,4.3,2.25,1.05,'3-day future shadow\nreview graph + approval\nACTIVE_FROZEN'),
           (11.2,4.3,2.45,1.05,'Selected primary\nrobust z + persistence\ncontributor evidence'),
           (5.7,1.45,2.25,1.35,'Local relative features\n1m causal lags\nno universal raw baseline'),
           (8.45,1.45,2.25,1.35,'Shared challengers\nARX / DPCA / IF\nnon-voting shadow'),
           (11.2,1.45,2.45,1.35,'Episode + Dashboard\ntechnician review\nfuture supervised data')]
    for x,y,w,h,label in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.04,rounding_size=.12',facecolor='#EEF5FB',edgecolor='#7399B9',lw=1))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=9.5,color='#213B51')
    for i in range(4):
        x,y,w,h,_=boxes[i];nx=boxes[i+1][0];ax.annotate('',xy=(nx-.08,y+h/2),xytext=(x+w+.07,y+h/2),arrowprops=dict(arrowstyle='->',color='#6D8597',lw=1.5))
    ax.annotate('',xy=(6.82,2.88),xytext=(6.82,4.22),arrowprops=dict(arrowstyle='->',color='#6D8597',lw=1.5))
    ax.annotate('',xy=(8.37,2.12),xytext=(8.02,2.12),arrowprops=dict(arrowstyle='->',color='#6D8597',lw=1.5))
    ax.annotate('',xy=(12.42,2.88),xytext=(12.42,4.22),arrowprops=dict(arrowstyle='->',color='#6D8597',lw=1.5))
    ax.text(6.85,3.6,'This trial uses OFFLINE references, not the Active branch',ha='center',fontsize=10,color='#99652D')
    ax.text(9.58,.72,'Challengers do not open alerts or approve Profiles',ha='center',fontsize=10,color='#99652D')
    ax.text(7,5.65,'Upper row: target operating flow; approval / Active branch not executed in this trial',ha='center',fontsize=10,color='#506A7F')
    ax.set_title('Keep machine-specific calibration; test ML after local normalization',fontsize=16,pad=12)
    return save(fig,'07_selected_architecture',output)


def make_notebook(output=OUTPUT):
    t=tables(output);summary=t['summary'];cells=[]
    md=lambda s:cells.append(nbformat.v4.new_markdown_cell(s))
    code=lambda s:cells.append(nbformat.v4.new_code_cell(s))
    md('# 08L — Local Calibration และการเลือกวิธีตรวจ Anomaly\n\n'
       'HT9046MX · การทดลองบนคอมเครื่องนี้ · 1 ตุลาคม 2026\n\n'
       'คำถามของงานนี้คือ: **เมื่อเก็บเส้นอ้างอิงแยกรายเครื่องแล้ว การเพิ่ม ML ให้ประโยชน์กว่ากฎเดิมจริงหรือไม่?** '
       'Notebook นี้เล่าจากแหล่งข้อมูล ไปถึงความพร้อมของ Profile การเปรียบเทียบแบบใช้แถวเดียวกัน และกรณี MX057/M1 กับ MX080/M6 '
       'ที่เจ้าของโครงการยืนยันว่าเป็นพฤติกรรมผิดปกติแล้ว\n\n'
       'ผลไม่ใช่การรับรองสาเหตุรั่วหรือ fault accuracy และไม่มีการเปลี่ยน Active Profile, MySQL หรือ Server. '
       'ในที่นี้ `Profile` ทุกชุดเป็น **offline train-only reference** ไม่ใช่ ACTIVE_FROZEN ของระบบใช้งานจริง.')
    md('## 1. เปิดผลที่รันแล้ว และวิธีรันซ้ำ\n\n'
       'กราฟและตารางด้านล่างสร้างจากการทดลองที่รันจริง โดยมี source inventory และ SHA-256 กำกับ Notebook รันทุกเซลล์แล้ว '
       'แต่การเปิดอ่านไม่จำเป็นต้องเทรนซ้ำทุกครั้ง\n\n'
       'บน Colab ให้วาง project checkout และโฟลเดอร์ผล `notebooks/outputs/local_profile_model_selection_v1` ใน Drive แล้วตั้ง `PROJECT_ROOT` '
       'ข้อมูล raw ไม่รวมใน Git: การ rebuild ต้องมี Parquet ต้นทาง และ cache ZIP ที่ได้จาก Notebook 08K ตาม protocol '
       'ไม่มีเซลล์เชื่อม MySQL หรือ approve Profile\n\n'
       'คำสั่ง rebuild อยู่ท้าย notebook; ค่า path ของ source เปลี่ยนได้ผ่าน `--raw-root`. รูป PNG/SVG ถูกส่งออกไว้สำหรับสไลด์ด้วย')
    code("from pathlib import Path\nimport sys, json\nimport pandas as pd\nfrom IPython.display import display\nfrom IPython import get_ipython\nPROJECT_ROOT = next((p for p in [Path.cwd(), Path.cwd().parent] if (p/'README_System.md').exists()), Path('/content/drive/MyDrive/OPERATION_P'))\nif not (PROJECT_ROOT/'README_System.md').exists():\n    raise FileNotFoundError('ตั้ง PROJECT_ROOT ให้ชี้ไปยัง project checkout บนเครื่องนี้หรือ Colab Drive')\nsys.path.insert(0, str(PROJECT_ROOT))\nfrom notebooks.support import local_profile_model_selection_presentation as viz\nget_ipython().run_line_magic('matplotlib', 'inline')\nOUT = PROJECT_ROOT/'notebooks/outputs/local_profile_model_selection_v1'\nt = viz.tables(OUT)\nprint('Status:', t['summary']['status'])\nprint('Clock:', t['summary']['source_clock'])\nprint('Protocol SHA-256:', t['summary']['protocol_sha256'])\nprint('Selected primary:', t['summary']['decision'])")
    md('## 2. ข้อมูลมาจากเครื่องไหน และใช้ทำอะไร\n\n'
       'MX017, MX024, MX080 ใช้ daily dynamic TXT ที่อ่านจาก ZIP ทั้งห้าส่วนใน Downloads ผ่านตัวสร้าง strict-minute cache ของ 08K '
       'ส่วน MX029, MX041, MX057, MX070, MX118, MX119 อ่าน original raw-second Parquet ใหม่ '
       '**ไม่ใช้ `_Static.txt`** และไม่รวมแถวของเครื่องเดียวกันจากสอง source families ซ้ำกัน\n\n'
       'ช่วงที่เลือกของรอบนี้คือ 4 ส.ค.–8 ก.ย. 2026; Parquet บางเครื่องสิ้นสุด 1 ก.ย. จึงมีระยะทดสอบไม่เท่ากัน '
       'MX118/MX119 มีวันไม่พอสร้าง Profile จึงเก็บเป็นตัวอย่าง abstention ไม่ใช้เทรนโมเดลกลาง '
       'ทุกเครื่องตรวจครบ Module 1–8 แม้บาง Module ไม่มี qualified Cold data')
    code("display(t['coverage'])\ndisplay(viz.source_and_reference(OUT))")
    md('อ่านกราฟ: S คือผ่าน screening เชิงสถิติสำหรับ candidate เท่านั้น ไม่ใช่ช่างยืนยันปกติ; R ต้องทบทวนช่วงอ้างอิง; -- วัน/นาทีไม่พอ '
       'ช่องว่างไม่ใช่ค่า Anomaly Score = 0 และไม่ควรแสดงสีเขียวว่าเครื่องปกติ')
    md('## 3. เส้นปกติและ Correlation จำเป็นต้องแยกรายเครื่องจริงไหม\n\n'
       'แต่ละช่องซ้ายคือ median ของ Hp_2nd ในช่วง fit ของ Machine × Module นั้น ไม่ใช่ pressure target กลางของทั้ง fleet '
       'ขวาดูความสัมพันธ์ Lp_2nd กับ TempLo หลังลบ median รายวันเพื่อลดผลของคนละระดับ pressure '
       'ค่า Spearman ใกล้ +1 หมายถึงเคลื่อนทิศเดียวกัน ใกล้ −1 หมายถึงสวนทางกัน และใกล้ 0 หมายถึงความสัมพันธ์แบบอันดับไม่เด่น\n\n'
       'การมี sign/strength ต่างกันสนับสนุนให้เก็บ local context แต่ correlation ไม่พิสูจน์เหตุ–ผล และอาจปน load, manual setting, startup หรือ sensor behavior '
       'ค่าช่องซ้ายยังเป็นเพียง candidate reference: ถ้าช่วง fit มีหลาย plateau การได้ median หนึ่งค่าก็ไม่ได้ทำให้ชุดนั้นเหมาะสำหรับ approve')
    code("display(viz.baseline_and_relationship(OUT))\ndisplay(t['correlations'].sort_values(['pair','machine','module']))")
    md(r'''## 4. Auto-Calibration ในการทดลองนี้ทำอะไรบ้าง

เริ่มจาก raw ที่สังเกตได้จริง: ภายใน 1 นาทีต้องมีอย่างน้อย 57 จาก 60 second bins ไม่มี duplicate machine-second และ gap รวมขอบนาทีไม่เกิน 5 วินาที State ทั้งนาทีเป็น Run/On/Busy=0/SV=Off และ physical sensors ทั้งเจ็ด finite, Valve ไม่ติดลบ

Manual/ChangeValve/MValveHome และ SV/stop transition **ยังเก็บเป็น evidence** แต่ไม่ใส่ใน steady Cold baseline ตัวตรวจนี้ยังไม่ได้เรียนรู้ transition envelope และไม่มีการถือว่าระดับใหม่หลัง manual เป็นปกติโดยอัตโนมัติ

ฟีเจอร์ 9 ตัวคือ Hp1, Lp1, Hp2, Lp2, Valve, TempHi, TempLo และผลต่าง pressure สองวงจร:

$$dp_1=Hp_1-Lp_1,\qquad dp_2=Hp_2-Lp_2.$$

Profile ใช้เฉพาะ 4–17 ส.ค. และ fit 2 รอบ: รอบแรก quarantine แถวที่ $\max_j|z_j|>8$ จากนั้นคำนวณ median/scale อีกครั้ง **การ quarantine ไม่ใช่การยืนยัน healthy label**

$$m_j=\operatorname{median}(x_j),\qquad MAD_j=\operatorname{median}|x_j-m_j|$$
$$s_j=\max\left(1.4826MAD_j,\frac{Q_{.75,j}-Q_{.25,j}}{1.349},f_j\right),\qquad z_{t,j}=\frac{x_{t,j}-m_j}{s_j}.$$

$f_j=1$ count สำหรับ Valve และ 0.1 source unit สำหรับตัวอื่น ป้องกัน scale เป็นศูนย์/การขยับเพียงหนึ่ง command count กลายเป็น z สูงมาก ตัวเลขเหล่านี้สืบจาก contract ปัจจุบัน ไม่ได้ fit จากเคสที่ยืนยันแล้ว

ต้องเหลืออย่างน้อย 7 วันและ 200 นาทีหลัง quarantine การทดลองนี้เพิ่ม **reference screening** ว่า quarantine ไม่เกิน 5% และ median ครึ่งแรก–ครึ่งหลังต่างกันไม่เกิน 1.5 local z ชุดที่เกินยังแสดงใน diagnostic แต่ไม่ใช้เป็น shared-model fit data เกณฑ์นี้ไม่ใช่ change-point detector หรือสิทธิ์ approve

ขั้นในระบบจริงยังต้องเป็น Candidate → future 3-day Shadow → review/approval → ACTIVE_FROZEN การทดลองรอบนี้ **ไม่ได้ execute registry lifecycle นั้น** ไม่มีการย้าย offline reference ไป Active''')
    code("display(viz.reference_quality(OUT))\ndisplay(t['profiles'][['machine','module','status','fit_days','fit_rows','retained_rows','quarantine_pct','max_half_shift_z']])")
    md('### รู้เวลาหลังเริ่มทำงานจริงมากแค่ไหน\n\n'
       'ตารางต่อไปนับเฉพาะ matched diagnostic future ที่มี offline reference ในรอบนี้ '
       'unknown onset ไม่ใช่ startup และเวลาเริ่มไฟล์ไม่ใช่เวลาเปิด compressor. เมื่อรู้ onset ยังต้องแยก run start, post-manual และ Cold control entry '
       'สัดส่วนเตือนตามอายุเป็น descriptive association ไม่ได้บอกว่า early flags ทุกจุดเป็น false alarms และไม่ได้ถูกใช้ตั้ง fixed suppression')
    code("phase=pd.read_csv(OUT/'phase_availability_diagnostic.csv',dtype={'machine':str})\nphase_summary=phase.groupby('phase')[['rows','persistent_self']].sum()\nphase_summary['flagged_pct']=100*phase_summary.persistent_self/phase_summary.rows\ndisplay(phase_summary)\nprint('Unknown onset (% matched future):',round(100*phase_summary.loc['UNKNOWN_ONSET','rows']/phase_summary.rows.sum(),2))")
    md('## 5. แยกข้อมูลตามเวลาและป้องกัน leakage\n\n'
       '| ช่วง | หน้าที่ | ใช้กำหนดอะไร |\n|---|---|---|\n'
       '| 4–17 ส.ค. | Fit | Local reference, scaler, Ridge/PCA/IF weights |\n'
       '| 18–21 ส.ค. | Inner validation | เลือก Ridge alpha ด้วย prediction MSE เฉลี่ยเท่ากันราย Profile |\n'
       '| 22–25 ส.ค. | Past threshold block | Q99.5 ราย Machine × Module ต่อ lane ต้องมี ≥200 นาทีและ ≥3 วัน |\n'
       '| 26 ส.ค.–8 ก.ย. | Diagnostic future | เปรียบเทียบผล ไม่ fit หรือปรับค่า |\n\n'
       'ช่วงในตารางเป็น start-inclusive/end-exclusive ตาม protocol JSON การใช้ lag reset ทุกครั้งที่มี manual, state, missing-window หรือเปลี่ยนเครื่อง/โมดูล '
       'Training ไม่ใช้แถวที่ปัจจุบันหรือสอง lag ก่อนหน้าถูก quarantine\n\n'
       '**ข้อจำกัดสำคัญ:** ข้อมูลและเคสบางส่วนถูกเปิดดูในงานก่อนแล้ว จึงไม่เรียกว่า untouched outer test หรือใช้ประกาศความแม่นยำ '
       'LOMO ในรอบนี้เป็น adapted LOMO: model weights ไม่เห็น held machine แต่ใช้ local profile และ threshold block จากอดีตของ held machine ได้ '
       'จึงไม่ใช่ zero-shot สำหรับเครื่องที่ไม่มีข้อมูลเลย')
    code("print(json.dumps(t['summary']['models'], indent=2))\ndisplay(pd.read_csv(OUT/'thresholds.csv', dtype={'machine':str}))")
    md(r'''## 6. วิธีที่นำมาเทียบ สมการและเหตุผล

**Self deviation — วิธีหลักเดิม:** $S_t=\max_j|z_{t,j}|$. เส้นเตือนเดิมคือ Q99.5 ของ retained fit scores; ต้องเกินหรือเท่ากับเกณฑ์ 3 นาทีที่ติดกันจริง วิธีนี้ยังเห็น plateau ผิดระดับแม้ค่าจะนิ่ง การเพิ่ม Self separate-cut เป็นการทดลองแยก threshold ไปอดีตอีกช่วง ไม่ได้เปลี่ยน production threshold

**ARX-Ridge — dynamic challenger:** input เป็น 7 relative sensors ที่ lag 1 และ 2 นาที (14 inputs) ทำนาย Hp2, Lp2, TempHi, TempLo ปัจจุบัน (4 targets) โดยไม่ใส่ target ปัจจุบันกลับเป็น predictor

$$\hat{\mathbf y}_t=\mathbf b+\sum_{\ell=1}^2W_\ell\mathbf z_{t-\ell},\qquad
\hat W=\arg\min_W\|Y-XW\|_F^2+\alpha\|W\|_F^2.$$
$$A_t=\max_k\left|\frac{(\hat y_{t,k}-y_{t,k})-\tilde e_k}{\max(1.4826MAD(e_k),0.1)}\right|.$$

Ridge เป็น supervised regression ในเชิงสมการ แต่ target เป็น sensor ถัดไป ไม่ใช่ fault label จึงใช้ฝึก task นี้กับ unlabeled telemetry ได้ **ไม่ได้หมายความว่า training rows ทุกแถวเป็น healthy** Alpha ทดลอง 0.1/1/10/100 ผ่าน inner validation เท่านั้น ข้อจำกัดคือเมื่อผิดระดับแล้วนิ่ง model อาจทำนายจากระดับผิดเมื่อหนึ่งนาทีก่อนได้แม่น residual จึงกลับมาต่ำ ไม่ควรใช้แทน frozen-level Self

**DPCA challenger:** concatenate $v_t=[z_t,z_{t-1},z_{t-2}]$ รวม 21 features ใช้ StandardScaler train-only และ PCA แบบ full SVD เก็บ variance อย่างน้อย 95% จาก train

$$\hat v_t=PP^\top(v_t-\mu)+\mu,\qquad Q_t=\|v_t-\hat v_t\|_2^2.$$

คะแนน Q/SPE วัดการหลุดจากโครงสร้าง covariance/lag ที่เรียนมา ไม่ใช่ความน่าจะเป็นเกิด fault; ไม่มี T² lane ในการทดลองนี้ Shared PCA อาจจับ cross-machine heterogeneity แทน anomaly หาก contextual normalization ไม่พอ

**Isolation Forest challenger:** ใช้ 21 features ชุดเดียวกับ DPCA, 200 trees, max_samples=1024, seed=13, n_jobs=1 ใช้ $I_t=-\operatorname{score\_samples}(v_t)$ และ threshold Q99.5 ของ past block ราย context ไม่ใช้ `predict()` หรือ generic contamination cut ของ library. `contamination=auto` ไม่ใช่การตั้งว่ามี fault กี่เปอร์เซ็นต์

สำหรับ challenger ทั้งสาม ใช้ max 2,500 fit rows ต่อ screened reference เพื่อให้เครื่องที่มีข้อมูลมากไม่ครอบงำ และใช้ persistence แบบ 3 นาทีเหมือนกัน ไม่มีการรวม OR แล้วปรับเกณฑ์จากเคส''')
    code("display(viz.matched_burden(OUT))\ndisplay(t['burden'])")
    md('อ่านกราฟอย่างระวัง: เปอร์เซ็นต์ที่ต่ำกว่าหมายถึง flagged workload ต่ำกว่า ไม่ได้แปลว่าแม่นยำกว่า เพราะยังไม่มีชุด verified-normal negatives '
       'กราฟใช้เฉพาะ context ที่ทุก lane มี threshold และมีจำนวน matched rows เท่ากัน ช่วงเวลาของแต่ละเครื่องต่างกันตาม coverage '
       'เส้นในกราฟขวาจึงอธิบายความต่างของ burden ไม่ใช่ ranking ความเสี่ยงของเครื่อง')
    md('## 7. กรณีที่ยืนยันแล้ว: ตรวจช่วงเดิมได้ไหม และใครเป็น contributor\n\n'
       'MX057/M1 29 ส.ค. 04:06–22:50 และ MX080/M6 7 ก.ย. 12:23:28–8 ก.ย. 00:00 เป็น owner-confirmed behavioral cases '
       'ยังไม่มี technician cause confirmation. Coverage ข้างล่างนับเฉพาะ matched qualified minutes ที่มี threshold จึงไม่ใช่ sensitivity บนทุก raw second '
       'เวลา decision เป็นปลายนาทีที่ window complete แล้ว ยังไม่รวมรอ worker fetch 5 นาทีหรือ network delay')
    code("display(viz.case_comparison(OUT))\ndisplay(t['cases'])\ndisplay(viz.case_timeline(OUT,'080'))\ndisplay(viz.case_timeline(OUT,'057'))")
    md('**MX080/M6:** ในวันที่ 22–25 ส.ค. มี matched Cold data เพียงสองวัน (2,289 นาที) '
       'จึงไม่ผ่านขั้นต่ำสามวันสำหรับ threshold ของ ML/Self-separate lanes แม้จำนวนแถวจะมากพอ '
       'ช่องนี้ต้องอ่านว่า **abstain เพราะไม่มี threshold ที่ qualified** ไม่ใช่ score=0 หรือโมเดลตรวจไม่พบ '
       'Self-original ในกราฟเป็น offline reference probe ไม่ใช่การอนุมัติ Profile ที่ review-required\n\n'
       'เส้น sensor เป็นค่ารายวินาทีจริง ไม่ interpolate และแยก pressure/temperature/Valve คนละแกน '
       'เส้นประเป็น offline fit median. พื้นแดงเกิดเฉพาะ panel ที่มี stored feature ข้าม Self threshold พร้อม global persistence '
       'จึงไม่ทำให้ Valve ดูผิดปกติเพียงเพราะ temperature เป็นตัวดัน global score '
       'Manual/status strip ยังอยู่เพื่ออ่านลำดับเหตุการณ์ แต่ temporal association ไม่ใช่ข้อยืนยันว่า manual ทำให้เครื่องเสีย')
    md('## 8. ทดสอบการถ่ายโอนระหว่างเครื่อง และต้นทุน\n\n'
       'แต่ละ fold ฝึก shared model โดยตัด held machine ออก แล้วสร้าง threshold จาก past block ของ held machine เท่านั้น '
       'ทุก fold ยังคง local reference ของเครื่องนั้นอยู่เพื่อเลียนแบบ target adaptation. ต้องอ่าน worst-machine/context ด้วย ไม่ใช่ค่า fleet เฉลี่ยอย่างเดียว '
       'ผลนี้ยังไม่ทดสอบ transfer ไป new model of machine หรือ SV/mode ที่ไม่เคย qualified')
    code("display(t['lomo'].groupby(['machine','lane']).agg(rows=('rows','sum'), persistent=('persistent_flags','sum'), openings=('openings','sum')))\nprint('Batch model scoring seconds:', t['summary']['model_score_seconds'])\nprint('Measured seconds / 1000 matched rows:', t['summary']['seconds_per_1000_matched_rows'])\nprint('Artifact reload max |difference|:', t['summary']['artifact_reload_max_abs_error'])\nprint('Actual source / runtime window comparisons:', t['summary']['strict_actual_source_window_comparisons'])")
    md('ตัวเลข latency มาจาก batch บนคอมเครื่องนี้ ไม่ใช่ benchmark Server หรือ live p95 end-to-end: ยังต้องตรวจ MySQL read, checkpoint, late arrival, alert bridge และ UI บน target staging อีกครั้ง '
       'โมเดล sklearn ไม่มี epoch แบบ LSTM; Ridge/DPCA แก้ optimization/SVD และ IF ใช้จำนวน trees ไม่ควรถาม epoch เพื่อตัดสินว่าฝึกพอหรือไม่')
    md('## 9. วิธีที่เลือก และสิ่งที่จะปรับ Auto-Calibration\n\n'
       '**เลือก local frozen robust-z + 3 adjacent-minute persistence เป็น primary ในตอนนี้** โดยคง Machine × Module × qualified state/SV context '
       'เหตุผลคือมีหลักฐานระดับค่าตัวเองชัด อธิบาย contributor ได้ และไม่ปล่อยให้ persistent plateau ถูก prediction จากอดีตระยะสั้นกลืนเป็นปกติ '
       'ยังไม่มี independently reviewed incremental benefit หรือ healthy negatives มากพอจะยกระดับ ARX/DPCA/IF ให้เปิด alert\n\n'
       'การทดลองนี้ทำ reference screening และ train-only artifacts ใช้งานได้จริงใน local research path แล้ว แต่ **ยังไม่ได้เปลี่ยน Auto-Calibration registry/runtime** '
       'ทิศทางที่ควรทำต่อคือแยก data quality ออกจาก operating phase, เก็บ manual events, ตรวจ stable reference period ก่อน approve และเรียนรู้ startup/settling จากหลายครั้งที่มี onset จริง '
       'ไม่ใช้ fixed 20-minute suppression หรือ re-zero Profile ตาม plateau ล่าสุดโดยอัตโนมัติ\n\n'
       'ARX ช่วยเป็น dynamic evidence, DPCA ช่วย covariance/lag evidence, IF เป็น novelty comparator: ทั้งสามเก็บเป็น non-voting shadow เพื่อให้ช่าง review ช่วงที่เพิ่มจาก Self '
       'LSTM ไม่ได้ train ในรอบนี้: ความซับซ้อนและข้อมูล unlabeled เพิ่มไม่ได้แก้ปัญหา reference contamination เอง จึงยังไม่มีเหตุผลจากผลทดลองนี้ให้แทน primary')
    code("display(viz.workflow(OUT))")
    md('## 10. QA และวิธีทำซ้ำ\n\n'
       'Unit tests ตรวจ split isolation, future mutation ไม่เปลี่ยน Profile/threshold, insufficient reference, lag reset และ `>=` persistence '
       'Actual source comparison ใช้ตัวสร้าง window ของระบบจริงใน clean/manual/source boundaries; model reload ต้องให้คะแนนต่างกัน = 0 '
       'Source files ไม่ถูกแก้ และมี SHA-256 ของ input inventory, protocol, code, models และตารางผล\n\n'
       'Rebuild จาก project root:\n\n'
       '```bash\npython -X utf8 -m notebooks.support.local_profile_model_selection ingest --raw-root <raw_parquet_root>\n'
       'python -X utf8 -m notebooks.support.local_profile_model_selection benchmark --raw-root <raw_parquet_root>\n'
       'python -X utf8 -m pytest notebooks/support/test_local_profile_model_selection.py notebooks/support/test_october_three_machine_calibration.py -q\n```\n\n'
       'หากยังไม่มี cache ของ October ZIP ให้รัน Notebook 08K/intake ของมันก่อน การสร้าง raw cache ยังใช้ timestamp precision normalization และ strict gate เหมือนเดิม '
       'อย่าโหลด joblib จากแหล่งที่ไม่ไว้วางใจ; ใช้ artifact ที่ตรวจ hash และ sklearn version ตรงกับ manifest')
    code("import hashlib\nfailures=[]\nfor name, expected in t['summary']['hashes'].items():\n    with (OUT/name).open('rb') as stream:\n        actual=hashlib.file_digest(stream,'sha256').hexdigest()\n    if actual != expected: failures.append(name)\nassert not failures, failures\nprint('Artifact hash QA: PASS')\nprint(*t['summary']['limits'], sep=chr(10))")
    md('## แหล่งอ้างอิงและเหตุผลการเลือกวิธี\n\n'
       'รายละเอียดงานวิจัยพร้อมขอบเขตที่อ่านได้อยู่ใน `research/HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md` '
       'ผลของ papers ไม่ได้ถูกถือเป็นผลของ HT9046MX ของเรา\n\n'
       '- [Ku et al. (1995), DPCA](https://doi.org/10.1016/0169-7439(95)00076-3): ใช้แนว lag-embedded relationship monitoring ไม่ได้ implement fault model bank ของงานเดิม\n'
       '- [Yan et al. (2014), ARX + SVM](https://doi.org/10.1016/j.enbuild.2014.05.049): ใช้แนว predictive residual แต่ไม่ใช้ supervised fault SVM เพราะไม่มี fault labels\n'
       '- [Farouq et al. (2022), unit/subfleet monitoring](https://doi.org/10.1016/j.eswa.2022.116864): รองรับการคง local reference แทน raw global baseline ไม่ได้ให้ conformal guarantee กับข้อมูล drift ของเรา\n'
       '- [Ridge API](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.Ridge.html), [PCA API](https://scikit-learn.org/1.8/modules/generated/sklearn.decomposition.PCA.html), [IsolationForest API](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.IsolationForest.html): อ้าง parameter/score semantics; รันจริง sklearn 1.8.0 ตาม manifest\n\n'
       'บทสรุปของงานนี้เป็นการเลือกวิธีที่เหมาะกับหลักฐานที่มีตอนนี้ ไม่ใช่การอ้างว่า model หนึ่งดีที่สุดสำหรับ fault ทุกชนิด')
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                                      'language_info':{'name':'python','version':summary['python']}})
    path=ROOT/'notebooks/08L_Local_Calibration_and_Model_Selection_Colab.ipynb'
    nbformat.write(notebook,path)
    print(path)
    return path


if __name__=='__main__':make_notebook()
