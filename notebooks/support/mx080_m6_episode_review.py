"""Read-only, CP2-led MX080/M6 episode review; no training or registry writes."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'notebooks/outputs/fleet_reference_study_20261005'
OUT=ROOT/'notebooks/outputs/mx080_m6_episode_review_20261005'
START='2026-08-20';END='2026-09-13'
FOCAL=['2026-08-23','2026-08-24','2026-08-26','2026-08-31','2026-09-01','2026-09-02','2026-09-07','2026-09-08','2026-09-10']

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n',encoding='utf-8')

def load():
    manifest=json.loads((STUDY/'intake_manifest.json').read_text(encoding='utf-8'))
    receipts={(x['machine'],x['date']):x for x in manifest['files']}
    frames=[];events=[];provenance=[]
    for day in pd.date_range(START,pd.Timestamp(END)-pd.Timedelta(days=1)):
        date=day.strftime('%Y-%m-%d');base=f'080_{date}'
        meta=json.loads((STUDY/'minutes'/f'{base}.json').read_text(encoding='utf-8'))
        path=STUDY/'minutes'/f'{base}.parquet'
        assert meta['source_sha256']==receipts['080',date]['source_sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['minute_parquet_sha256']
        frames.append(pd.read_parquet(path))
        p=STUDY/'events'/f'{base}.parquet'
        if p.exists():events.append(pd.read_parquet(p))
        provenance.append(meta)
    frame=pd.concat(frames,ignore_index=True).sort_values(['module','time'])
    frame['dp2']=frame.hp2-frame.lp2
    return frame,pd.concat(events,ignore_index=True),provenance

def supported(f):
    return f.quality&f.stable_control&f.context.eq('SV_OFF')

def stats(f):
    out={'observed_minutes':len(f),'quality_minutes':int(f.quality.sum()),'run_sv_off_minutes':int(supported(f).sum()),
         'compressor':f.compressor.value_counts().to_dict(),'module_state':f.module_state.value_counts().to_dict(),
         'busy':f.busy.value_counts().to_dict(),'sv':f.sv.value_counts().to_dict()}
    for scope,mask in [('all_quality',f.quality),('run_sv_off',supported(f))]:
        a=f.loc[mask]
        out[scope]={c:{'median':round(float(a[c].median()),3),'p05':round(float(a[c].quantile(.05)),3),
                      'p95':round(float(a[c].quantile(.95)),3)} if a[c].notna().any() else None
                    for c in ['hp2','lp2','dp2','hp1','lp1','temphi','templo','valve']}
        out[scope]['hp2_over230_minutes']=int(a.hp2.gt(230).sum())
        out[scope]['hp2_over300_minutes']=int(a.hp2.gt(300).sum())
        out[scope]['dp2_abs_le5_minutes']=int(a.dp2.abs().le(5).sum())
    return out

def raw_review():
    from notebooks.support.fleet_reference_study import inventory,read_day
    entries,handles=inventory();receipts=json.loads((OUT/'source_receipts.json').read_text(encoding='utf-8'))
    sources={x['date']:x for x in receipts};summaries=[];parts=[];witness=[]
    import polars as pl
    import gc
    try:
        for entry in entries:
            day=entry['date']
            if entry['machine']!='080' or day not in FOCAL+['2026-09-12']:continue
            source,digest=read_day(entry)
            assert digest==sources[day]['source_sha256']
            assert source.height==sources[day]['raw_rows']
            cols=['stamp','Status']+[f'{x}_6' for x in ['Hp_1st','Lp_1st','Hp_2nd','Lp_2nd','TempHi','TempLo','Valve','Status','SV','Busy']]
            x=source.select(cols).to_pandas().rename(columns={'stamp':'time','Status':'compressor',
                'Hp_1st_6':'hp1','Lp_1st_6':'lp1','Hp_2nd_6':'hp2','Lp_2nd_6':'lp2','TempHi_6':'temphi',
                'TempLo_6':'templo','Valve_6':'valve','Status_6':'module_state','SV_6':'sv','Busy_6':'busy'})
            x['duplicate_second']=x.time.duplicated(keep=False)
            unique=x.loc[~x.duplicate_second].copy();unique['dp2']=unique.hp2-unique.lp2
            parts.append(x)
            summaries.append({'date':day,'rows':len(x),'duplicate_occurrence_rows':int(x.duplicate_second.sum()),
                'hp2_min':float(unique.hp2.min()),'hp2_max':float(unique.hp2.max()),
                'hp2_exact600_seconds':int(unique.hp2.eq(600).sum()),'templo_exact_minus200_seconds':int(unique.templo.eq(-200).sum()),
                'source_sha256':digest,'all_state_unique_seconds':len(unique)})
            if day=='2026-09-07':
                rail=pl.all_horizontal([pl.col(f'{tag}_6').eq(580.2) for tag in ['Hp_1st','Lp_1st','Hp_2nd','Lp_2nd']]+
                                      [pl.col(f'{tag}_6').eq(-200) for tag in ['TempHi','TempLo']])
                bad=source.filter(rail)
                snapshot=source.filter(pl.col('stamp').dt.strftime('%H:%M:%S').eq('11:05:00')).select(
                    [f'{tag}_{mod}' for mod in range(1,9) for tag in ['Hp_1st','Lp_1st','Hp_2nd','Lp_2nd','TempHi','TempLo']]).to_dicts()
                message_path=ROOT/'notebooks/outputs/mx080_module6_forensics_v1/message_events_parsed.csv'
                write('daq_rail_evidence.json',{'m6_all_four_pressures_equal580_2_and_both_temperatures_minus200_rows':bad.height,
                    'start':str(bad['stamp'].min()),'end':str(bad['stamp'].max()),'source_sha256':digest,
                    'cross_module_snapshot_11_05':snapshot,
                    'message_context_export_sha256':hashlib.sha256(message_path.read_bytes()).hexdigest() if message_path.exists() else None,
                    'interpretation':'Strong acquisition/sentinel suspicion, localized to M6 at the snapshot; no verified hardware rail definition. Not physical pressure/filling evidence.'})
            dayevents=pd.read_parquet(STUDY/'events'/f'080_{day}.parquet') if (STUDY/'events'/f'080_{day}.parquet').exists() else pd.DataFrame()
            changes=dayevents.loc[dayevents.module.eq(6)&dayevents.event_type.ne('VALVE_CHANGED')&dayevents.witness_usable] if len(dayevents) else dayevents
            for _,ev in changes.iterrows():
                before=unique.loc[unique.time.ge(ev.time-pd.Timedelta(minutes=5))&unique.time.lt(ev.time)]
                after=unique.loc[unique.time.ge(ev.time)&unique.time.lt(ev.time+pd.Timedelta(minutes=5))]
                witness.append({**ev.to_dict(),'pre5m':{c:float(before[c].median()) for c in ['hp2','lp2','valve']},
                                'post5m':{c:float(after[c].median()) for c in ['hp2','lp2','valve']}})
            print('raw SHA checked',day,len(x),flush=True)
            del source,x,unique;gc.collect()
    finally:
        for h in handles:h.close()
    pd.concat(parts,ignore_index=True).to_parquet(OUT/'m6_raw_focal_days.parquet',index=False)
    # Daily boundary event witness may have missing pre/post sample; retain as null.
    witness=json.loads(json.dumps(witness,default=str).replace('NaN','null'))
    write('raw_audit.json',summaries);write('control_event_witnesses.json',witness)

def comparisons(frame):
    periods=[('pre_Aug23','2026-08-22','2026-08-23 15:00'),
             ('after_Aug26','2026-08-27','2026-08-31 15:59'),
             ('after_Sep2','2026-09-03','2026-09-07 08:00'),
             ('persistent_Sep7_8','2026-09-07 12:30','2026-09-08 23:50'),
             ('after_Sep12','2026-09-12 04:00','2026-09-13')]
    result=[]
    for label,start,end in periods:
        for module in range(1,9):
            a=frame.loc[frame.module.eq(module)&frame.time.ge(start)&frame.time.lt(end)]
            result.append({'period':label,'start':start,'end':end,'module':module,**stats(a)})
    write('period_peer_comparison.json',result)

def deliver():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    import nbformat
    from nbclient import NotebookClient
    m=pd.read_parquet(OUT/'m6_observed_minutes.parquet').set_index('time').sort_index()
    raw_all=pd.read_parquet(OUT/'m6_raw_focal_days.parquet')
    raw=raw_all.loc[~raw_all.duplicate_second].set_index('time').sort_index()
    raw['dp2']=raw.hp2-raw.lp2
    # Independently recompute selected full raw-minute means, without imputation.
    parity=[]
    for date in FOCAL+['2026-09-12']:
        candidates=m.loc[m.index.strftime('%Y-%m-%d')==date]
        candidates=candidates.loc[candidates.quality]
        for stamp in candidates.iloc[np.unique(np.linspace(0,len(candidates)-1,3).astype(int))].index:
            rows=raw_all.loc[raw_all.time.ge(stamp)&raw_all.time.lt(stamp+pd.Timedelta(minutes=1))]
            err=max(abs(float(rows[c].mean())-float(m.loc[stamp,c])) for c in ['hp2','lp2','hp1','lp1'])
            assert err<1e-9
            parity.append({'minute':stamp.isoformat(),'raw_rows':len(rows),'max_pressure_mean_error':err})
    write('minute_raw_parity.json',parity)
    periods=json.loads((OUT/'period_peer_comparison.json').read_text(encoding='utf-8'))
    blocks=[{'period':d['period'],'start':d['start'],'end':d['end'],'qualified_minutes':d['run_sv_off_minutes'],
             **{c+'_median':d['run_sv_off'][c]['median'] for c in ['hp2','lp2','dp2','valve']}}
            for d in periods if d['module']==6]
    before=next(d for d in blocks if d['period']=='after_Sep2')
    after=next(d for d in blocks if d['period']=='persistent_Sep7_8')
    daq=json.loads((OUT/'daq_rail_evidence.json').read_text(encoding='utf-8'))
    summary={'machine':'MX080','module':6,'timezone':'Asia/Bangkok (assumed source naive clock)',
        'source_period':[START,END],'source_files':24,'raw_focal_files':10,
        'raw_rows_reread':sum(x['rows'] for x in json.loads((OUT/'raw_audit.json').read_text(encoding='utf-8'))),
        'observed_module_minutes':len(m),'quality_minutes':int(m.quality.sum()),'raw_minute_checks':len(parity),
        'comparison_blocks':blocks,'cp2_percent_change':{c:round(100*(after[c+'_median']/before[c+'_median']-1),2) for c in ['hp2','lp2','dp2']},
        'focal_raw_hp2_outside_field_band_first':'2026-09-07T08:02:47',
        'manual_changevalve_first':'2026-09-07T08:09:14','field_band_only_descriptive_psi':[180,230],
        'physical_cause_confirmed':False,'refill_confirmed':False,'source_writes':False,'model_or_profile_changes':False,
        'acquisition_suspect_interval':{k:daq[k] for k in ['start','end','m6_all_four_pressures_equal580_2_and_both_temperatures_minus200_rows']},
        'messages_scope':'Existing Sep2–8 parsed MessageLog is secondary context only; original MessageLogs unavailable at previous path in this task.',
        'interpretation':'Owner CP2 hypotheses investigated; observed changes and recovery do not independently establish refrigerant additions/leaks or healthy references.'}
    write('summary.json',summary)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16})
    hp='#184b79';lp='#008774'
    fig,axes=plt.subplots(3,1,figsize=(13,10),sharey=True,layout='constrained')
    spans=[('2026-08-22','2026-08-27','23 Aug: control Off; 24 Aug: pressure equalization; 26 Aug: On'),
           ('2026-08-31','2026-09-04','31 Aug: control Off; 1–2 Sep: equalization; 2 Sep: On'),
           ('2026-09-06','2026-09-13','7–8 Sep: sustained high CP2; 9–11 Sep: control Off; 12 Sep: new level')]
    for ax,(start,end,title) in zip(axes,spans):
        idx=pd.date_range(start,pd.Timestamp(end)-pd.Timedelta(minutes=1),freq='min');a=m.reindex(idx)
        ax.fill_between(idx,0,600,where=a.module_state.eq('off').to_numpy(),color='#eeeeee',alpha=.85,label='Status_6=Off')
        ax.plot(idx,a.hp2,color=hp,lw=1.1,label='Hp_2nd');ax.plot(idx,a.lp2,color=lp,lw=1.1,label='Lp_2nd')
        ax.set(title=title,ylabel='CP2 pressure (psi)',ylim=(0,600),xlim=(pd.Timestamp(start),pd.Timestamp(end)))
        ax.xaxis.set_major_locator(md.HourLocator(interval=12 if (pd.Timestamp(end)-pd.Timestamp(start)).days<=3 else 24));ax.xaxis.set_major_formatter(md.DateFormatter('%d %b\n%H:%M'))
    axes[0].legend(loc='upper left',ncol=3,frameon=False)
    fig.suptitle('MX080 / M6 · CP2 episode history | observed minute means, gaps retained',fontsize=15)
    fig.savefig(OUT/'cp2_episode_history.png',dpi=150);plt.close(fig)
    for date,start,end,name in [('2026-09-07','07:30','12:45','sep7_raw_control_detail'),('2026-09-10','14:00','22:30','sep10_raw_control_detail')]:
        idx=pd.date_range(f'{date} {start}',f'{date} {end}',freq='s');a=raw.reindex(idx)
        fig,axes=plt.subplots(3,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1,1.3]},layout='constrained')
        axes[0].plot(idx,a.hp2,color=hp,lw=.8,label='Hp_2nd');axes[0].plot(idx,a.lp2,color=lp,lw=.8,label='Lp_2nd')
        axes[0].set(ylabel='CP2 pressure (psi)',ylim=(0,600));axes[0].legend(loc='upper left',ncol=2,frameon=False)
        if date=='2026-09-07':
            axes[0].axvspan(pd.Timestamp(daq['start']),pd.Timestamp(daq['end']),color='#ffc773',alpha=.3)
            axes[0].text(pd.Timestamp('2026-09-07 11:12'),450,'Acquisition suspect\n4 P=580.2; both T=-200',ha='center',fontsize=9,
                         bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
        axes[1].plot(idx,a.valve,color='#67529a',lw=.8);axes[1].set(ylabel='Valve command',ylim=(-3,110))
        for col,match,color,label in [('compressor','run','#184b79','Status=Run'),('module_state','on','#008774','Status_6=On'),('busy','1','#bd6622','Busy_6=1')]:
            y=a[col].eq(match).astype(float).where(a[col].notna())
            axes[2].plot(idx,y,lw=.9,color=color,label=label)
        axes[2].set(ylabel='Observed state\n0=No / 1=Yes',ylim=(-.1,1.3));axes[2].legend(loc='upper left',ncol=3,frameon=False)
        axes[2].xaxis.set_major_locator(md.HourLocator());axes[2].xaxis.set_major_formatter(md.DateFormatter('%H:%M'))
        axes[2].set_xlim(pd.Timestamp(f'{date} {start}'),pd.Timestamp(f'{date} {end}'))
        fig.suptitle(f'MX080 / M6 · {date} | original unique seconds; ambiguous duplicates excluded',fontsize=14)
        fig.savefig(OUT/f'{name}.png',dpi=150);plt.close(fig)
    cells=[]
    def markdown(s):cells.append(nbformat.v4.new_markdown_cell(s))
    def code(s):cells.append(nbformat.v4.new_code_cell(s))
    markdown('# MX080 / M6: CP2 and control episode review\n\n## Summary\nPressure/state evidence supports repeated control interventions and distinct operating levels. The 7–8 September high-CP2 plateau is abnormal relative to the preceding supported run. Filling and leak hypotheses are not confirmed by telemetry. The same observed equalization shape also occurs with Status_6=Off / Valve=0 and no recorded module control change.\n\nThis is a read-only diagnostic, not a retrained or activated model.')
    markdown('## Context & Methods\n\n- Machine MX080, Module6 (assumed continuation of the displayed M6 case). CP2 HP/LP are primary; CP1, temperature and control tags are context.\n- 20 Aug–12 Sep inclusive, source naive times interpreted as Asia/Bangkok. 24 source days; 10 raw focal days reread and source-SHA checked.\n- Canonical dynamic ZIP receipts control source identity; saved minute Parquet hashes checked. The canonical corpus is not an exact SQL snapshot.\n- Minute figures show observed averages with failed-quality minutes blank; raw figures omit ambiguous duplicate seconds and never interpolate.\n- Matched run comparison: quality + stable control + Run + Status_6 On + Busy0 + SVOff. This is comparability, not verified health.\n- Status_6 denotes valve control, not independent motor feedback. Pressure equality during Off is not certified recovery or proof of charging.\n- Working 180–230 psi field band is descriptive and not a validated detector threshold. No charge amount, leak test, load/target recipe, suction/liquid temperature or current service record is available.\n- Date windows were selected after inspection; all comparisons are retrospective, not prospective accuracy.\n- Recompute: `python -m notebooks.support.mx080_m6_episode_review`, then `--raw`, then `--deliver`; no SQL reads/writes or training are performed. Artifacts require the private raw ZIPs and frozen Fleet study outputs.')
    code("from pathlib import Path\nimport json,pandas as pd\nfrom IPython.display import display,Image\nROOT=Path.cwd()\nassert (ROOT/'README_System.md').exists(), 'Run from OPERATION_P root'\nOUT=ROOT/'notebooks/outputs/mx080_m6_episode_review_20261005'\nsummary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))\ndisplay(pd.Series({k:summary[k] for k in ['source_period','source_files','raw_focal_files','raw_rows_reread','observed_module_minutes','quality_minutes','raw_minute_checks']}))")
    markdown('## Results\n\n### 1. Compare operating levels\nMedians use complete supported minutes only. Quantiles and full per-day states are available in daily.json and period_peer_comparison.json.')
    code("display(pd.DataFrame(summary['comparison_blocks']).round(2))\ndisplay(pd.Series(summary['cp2_percent_change'],name='7–8 Sep vs 3–7 Sep pre-intervention: percent change'))")
    markdown('### 2. Follow the repeated pressure trajectory\nGrey marks Status_6=Off, not an independent compressor motor shutdown. HP/LP convergence alone does not establish refrigerant filling.\nRecovery proposals: 27–30 Aug and 3–6 Sep require normal-operation review; 12 Sep has Valve100 and a different HP/LP level and needs a separate post-intervention review.')
    code("display(Image(filename=str(OUT/'cp2_episode_history.png')))")
    markdown('### 3. Inspect 7 September at original-second grain\n07:00–08:00 remains near HP190/LP19. First observed HP outside the working180–230 band is08:02:47. Run→Stop is08:06:22, first ChangeValve08:09:14. From10:55:59–11:28:01, all four M6 pressure channels simultaneously read580.2 and both temperatures-200 (1896 observed rows). Other modules differ in the11:05 source snapshot. This strongly suggests an M6 acquisition/default-value issue, not a physical580psi charging trajectory. Older parsed messages contain DAQ failures and a later11:58:18 reboot; they are secondary context and do not prove the hardware cause. Sustained high differential after restart is a separate, supported-state signal. Keep the rail interval visible and quarantined for reference admission; current finite-number quality checks alone do not detect it.')
    code("display(Image(filename=str(OUT/'sep7_raw_control_detail.png')))\naudit=pd.DataFrame(json.loads((OUT/'raw_audit.json').read_text(encoding='utf-8')))\ndisplay(audit[['date','rows','duplicate_occurrence_rows','hp2_max','templo_exact_minus200_seconds']])")
    markdown('### 4. Inspect 10 September without assuming same-day recovery\nStatus_6=Off and Valve0 persist throughout the day. Pressure cycling/equality is real; Run→Stop20:39:15 and Stop→Run21:09:58 are observed global states. The next supported Module6 On return in the inspected history is12 Sep02:49:59, following ChangeValve. No same-day supported healthy-run claim is justified.')
    code("display(Image(filename=str(OUT/'sep10_raw_control_detail.png')))\nevents=pd.read_parquet(OUT/'m6_observed_events.parquet')\ndisplay(events.loc[(events.time.ge('2026-09-12')) & events.event_type.ne('VALVE_CHANGED')].reset_index(drop=True))")
    markdown('## Checks\nSource-SHA and raw count agreement:10/10 reread files. Derived Parquet checksum agreement:24/24. Independent pressure minute mean checks:30 across10days, error<1e-9. No source, model, Active pointer or event SQL writes.')
    code("checks=json.loads((OUT/'minute_raw_parity.json').read_text(encoding='utf-8'))\nassert len(checks)==30 and max(x['max_pressure_mean_error'] for x in checks)<1e-9\nprint('30 sampled minute checks pass; maximum mean error:',max(x['max_pressure_mean_error'] for x in checks))")
    markdown('## Next Steps\nKeep observed control events, abnormal episodes and uncertain service hypotheses separate. Exclude unresolved intervention and confirmed abnormal periods from normal fit; assess Off/equalization separately. Review supported stable periods before donor admission; freeze a new service/config epoch when levels or Valve settings change. Shadow flags on a confirmed fault are positive detections; flag burden on reviewed normal data is evaluated separately. No supervised filling/leak labels are created from pressure shape.\n\n## References\n[Danfoss system fault diagnosis](https://www.danfoss.com/en-us/industries/food-and-beverage/dcs/cold-rooms/system-design-component-selection/application-vertical-market-sizing/troubleshooting-fault-diagnosis/) lists charge, valve, control and other differential diagnoses; application to this cascade system is a hypothesis. [Danfoss TXV troubleshooting](https://assets.danfoss.com/documents/latest/90976/AC307572949567en-010101.pdf) recommends system-wide verification and superheat/subcooling checks; current pressure/temperature tags do not provide those measurements.\n\nSource metadata: source_receipts.json, raw_audit.json, control_event_witnesses.json. Original MessageLogs were not recovered in this task; older parsed Sep2–8 logs are secondary context only.')
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    NotebookClient(notebook,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    target=ROOT/'notebooks/12_MX080_M6_Control_and_CP2_Episode_Review_20261005.ipynb'
    nbformat.write(notebook,target)
    print(json.dumps(summary),flush=True)
    print('executed',target,flush=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame,events,provenance=load();m=frame.loc[frame.module.eq(6)].copy()
    m.to_parquet(OUT/'m6_observed_minutes.parquet',index=False)
    events.loc[events.module.eq(6)].to_parquet(OUT/'m6_observed_events.parquet',index=False)
    daily=[];hourly=[]
    for date,g in m.groupby(m.time.dt.strftime('%Y-%m-%d')):
        daily.append({'date':date,**stats(g)})
        if date in FOCAL:
            for hour,h in g.groupby(g.time.dt.hour):hourly.append({'date':date,'hour':int(hour),**stats(h)})
    write('source_receipts.json',provenance);write('daily.json',daily);write('hourly.json',hourly)
    for d in daily:
        x=d['run_sv_off'];print(d['date'],d['run_sv_off_minutes'],*[f'{c}={x[c]["median"]}' if x[c] else f'{c}=NA' for c in ['hp2','lp2','dp2','valve']],flush=True)
    comparisons(frame)
    print('saved bounded minute review',flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--deliver' in sys.argv:deliver()
    elif '--raw' in sys.argv:raw_review()
    else:main()
