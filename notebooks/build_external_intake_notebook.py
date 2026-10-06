"""Build the self-contained Colab intake review and presentation companion."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = [md("""# 07B — ข้อมูล MX เพิ่มเติม: ตรวจรับข้อมูลก่อนขยายการวิเคราะห์

## tl;dr
เล่มนี้ตอบว่า **ข้อมูลเพิ่มช่วยอะไรได้ และส่วนไหนนำมาใช้ต่อได้แล้ว** อ่านตามลำดับจากช่วงเวลา → ข้อมูลซ้ำ → สถานะที่เทียบกันได้ → pressure และความสัมพันธ์ → แนวทางเข้า ML

มีข้อมูลหกเครื่อง ได้แก่ MX007, MX012, MX017, MX025, MX057 และ MX070 ผลด้านล่างคำนวณจากไฟล์รายวัน รวมไฟล์รายวันภายใน ZIP ของ MX057 ข้อมูลใหม่ถูกแปลงไว้เป็น Parquet แยกจากชุดเดิมแล้ว แต่ยังไม่มีการนำข้อมูลนี้ไปปรับโมเดลหรือ threshold

ผลตรวจวันที่ 9 กันยายน 2026: อ่าน 354 ไฟล์รายวัน รวม 29,819,668 แถว ได้ข้อมูลเพิ่มจริง 28,214,027 แถว แถวที่ซ้อนกับ primary 1,389,587 แถวตรงกันครบ 81 tags ส่วน 216,054 แถวที่เหลือเกี่ยวข้องกับ duplicate/conflicting timestamps ภายใน source และไม่ได้รวมเป็นข้อมูลใหม่

## Context & Methods
**จุดประสงค์:** ตรวจรับข้อมูลย้อนหลังสำหรับขยาย EDA, ตรวจ baseline drift และประเมินการใช้กับเครื่องที่ไม่อยู่ในชุดหลัก ผู้ใช้งานคือผู้ดูแลโครงการ ช่าง และผู้พัฒนาโมเดล

### Key Assumptions
- ต้นทางหนึ่งแถวเป็นหนึ่ง timestamp ของเครื่อง มี 8 โมดูล; output ระดับนาทีใช้ค่าจุดสุดท้ายของนาที พร้อมเวลา `available_at` จึงห้ามถือว่าค่านี้พร้อมใช้ตั้งแต่ต้นนาที
- Timezone ยังไม่ยืนยัน เก็บเวลาตามต้นทาง; วันที่จากชื่อไฟล์ต้องตรงกับวันที่ในเนื้อหา
- Pressure คงสเกลต้นทาง ไม่มีการคูณ/หารเพิ่มเติม; การเทียบข้อมูลวันซ้อนกันตรวจครบ 81 tags แต่ยังไม่ยืนยัน psig/psia
- Quality minute สำหรับ EDA ต้องมี 55–60 จุด, ช่องว่างภายในไม่เกิน 5 วินาที, ทุกจุดผ่าน Run/On/Busy=0/Valve≥0, SV คงที่ และไม่มี sentinel temperature ≤−199; ยังต้องผ่าน settling/service gate เพิ่มก่อน fit baseline
- ไม่มี confirmed fault labels; ช่วง 180–230 psi เป็น qualified field reference, ต่ำกว่า 180 เป็น undercharge screening และสูงกว่า 230 เป็น high-side investigation โดยไม่มีสิทธิ์ยืนยันสาเหตุ
- ไฟล์ Static, event fragments และ temporary copies อยู่ใน manifest แยก; ZIP อ่านสมาชิกทีละไฟล์พร้อม provenance; prepared windows เดิมไม่ได้นำมารวมเป็นข้อมูลใหม่
- ไม่มีการ fit model/scaler/HPO ในเล่มนี้ การแสดงข้อมูลย้อนหลังหลังเห็นผล outer test ถือเป็นการสำรวจเพื่อออกแบบการทดลองรุ่นถัดไป
"""), md("""### 1. ตั้งค่าตำแหน่งข้อมูล
บน Colab ให้ mount Drive และตั้ง `PROJECT_ROOT` ไปยังโฟลเดอร์โครงการที่มี outputs ถ้าจะอ่าน raw ใหม่ให้ตั้ง `EXTERNAL_ROOT`, `PRIMARY_ROOT` และ `REBUILD_RAW=True` เล่มนี้มีตัวนำเข้าฝังไว้ครบ จึงไม่ต้องหาไฟล์ support เพิ่ม

รอบส่งมอบรันการตรวจ raw ครบจากตัวนำเข้า และรัน Notebook จากผลที่ตรวจ checksum แล้ว การตั้งค่าเริ่มต้นช่วยเปิดกราฟซ้ำโดยไม่อ่าน raw หลาย GB ทุกครั้ง
"""), code('''from pathlib import Path
import sys, json, hashlib, importlib.util, subprocess
for package in ['polars', 'pandas', 'matplotlib', 'numpy', 'pyarrow']:
    if importlib.util.find_spec(package) is None:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
import polars as pl
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / 'notebooks').exists() and (PROJECT_ROOT.parent / 'notebooks').exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
EXTERNAL_ROOT = Path(r'C:/Users/Book/OneDrive/เดสก์ท็อป/Data Analysis')  # Colab: change to mounted Drive
PRIMARY_ROOT = PROJECT_ROOT / 'HT9046MX-20260902T013607Z-1-001/HT9046MX/raw/table=ht9046mx_readings'
OUTPUT = PROJECT_ROOT / 'notebooks/outputs/ht9046mx_external_intake_v2'
REBUILD_RAW = False
FIGURES = OUTPUT / 'figures'
FIGURES.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'figure.dpi': 110, 'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
BLUE, GOLD, INK = '#2878A5', '#C48C2D', '#30343B'
'''), md("### 2. ตัวนำเข้าและการตรวจ checksum\nตัวนำเข้าด้านล่างอ่านต้นฉบับอย่างเดียว ผลตรวจและข้อมูลแปลงเขียนแยกไว้ใน OUTPUT"),
code("intake_namespace = {'__name__': 'external_intake_embedded'}\nexec(" + repr((ROOT / 'notebooks/support/external_dataset_intake.py').read_text(encoding='utf-8')) + ", intake_namespace)\nif REBUILD_RAW:\n    intake_namespace['run_intake'](EXTERNAL_ROOT, PRIMARY_ROOT, OUTPUT)\nchecksums = json.loads((OUTPUT / 'artifact_checksums.json').read_text())\nfor name, expected in checksums.items():\n    assert intake_namespace['sha256'](OUTPUT / name) == expected, f'Artifact changed: {name}'\nprint('Verified intake output checksums:', len(checksums))"),
md("## Data\n### 3. ข้อมูลที่ตรวจแล้วและส่วนที่เพิ่มจริง\nตารางนับ wide rows ไม่ใช่ module rows วันซ้อนกันใช้ timestamp เป็น key แล้วเทียบ tags; ข้อมูลที่มีใน primary แล้วจะถูกกันออกจาก canonical ใหม่"),
code('''summary = json.loads((OUTPUT / 'analysis_summary.json').read_text(encoding='utf-8'))
manifest = pd.read_csv(OUTPUT / 'source_manifest.csv', dtype={'machine':str})
daily = pd.read_csv(OUTPUT / 'daily_module_sv_pressure.csv', dtype={'machine':str}, parse_dates=['date'])
table = manifest[manifest['kind'].eq('DAILY_TELEMETRY')].groupby('machine').agg(
    files=('source','size'), start=('date','min'), end=('date','max'),
    parsed_rows=('parsed_rows','sum'), overlap_rows=('overlap_rows','sum'),
    equal_overlap=('overlap_equal_rows','sum'), conflicts=('overlap_conflict_rows','sum'), novel_rows=('novel_rows','sum'))
display(table)
print(f"Parsed {summary['parsed_rows']:,} rows; novel {summary['novel_rows']:,}; overlap {summary['overlap_rows']:,}")
print('Parse/schema errors:', len(summary['errors']), '| ZIP daily files audited:', summary['archive_daily_audited'], '| ZIP non-daily/error review:', summary['archive_members_pending'])
print('Within-source extra rows sharing a timestamp:', int(manifest['duplicate_timestamp_rows'].sum()))
print('Within-source timestamp keys with conflicting values:', int(manifest['conflicting_timestamp_keys'].sum()))
print('Rows removed by exact-duplicate reduction and whole-key conflict quarantine:', summary['parsed_rows']-summary['novel_rows']-summary['overlap_rows'])
display(manifest.groupby(['kind','role']).size().rename('files').reset_index())
'''), md("## Results\n### 4. ช่วงเวลาที่ข้อมูลใหม่ช่วยเติมได้\nแต่ละขีดคือวันที่มีไฟล์รายวันจริง ช่องว่างแสดงวันที่ไม่มีไฟล์ สีเข้มเป็นข้อมูลเพิ่ม สีทองเป็นวันที่ซ้อนกับ primary; วันที่ซ้อนอาจมีบางแถวเพิ่มได้"),
code('''fig, ax = plt.subplots(figsize=(12,4.8))
for y, (machine,g) in enumerate(manifest[manifest['kind'].eq('DAILY_TELEMETRY') & manifest['date'].notna()].groupby('machine')):
    dates = pd.to_datetime(g['date'])
    overlap = g['overlap_rows'].fillna(0).gt(0)
    ax.scatter(dates[~overlap], np.full((~overlap).sum(),y), marker='|', s=260, color=BLUE)
    ax.scatter(dates[overlap], np.full(overlap.sum(),y), marker='s', s=25, color=GOLD)
ax.set_yticks(range(len(table)), ['MX'+m for m in table.index])
ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.set_title('Daily source coverage by machine\\nDaily files only; blue = no primary overlap, gold squares = partial/full overlap')
ax.set_xlabel('Source calendar date — timezone unconfirmed'); ax.grid(axis='x',alpha=.2)
fig.tight_layout(); fig.savefig(FIGURES/'01_coverage.png',bbox_inches='tight'); plt.show()
'''), md("### 5. ข้อมูลที่เพิ่มจริงเทียบกับข้อมูลที่มีแล้ว\nความยาวแท่งเป็นจำนวนแถว ชุดนี้เพิ่มทั้งช่วงย้อนหลังของเครื่องเดิมและเครื่องที่ไม่อยู่ในชุดหลัก การเพิ่มจำนวนแถวไม่เท่ากับเพิ่ม fault labels"),
code('''fig, ax = plt.subplots(figsize=(11,4.5))
y = np.arange(len(table))
ax.barh(y,table['novel_rows']/1e6,color=BLUE,label='Novel rows')
ax.barh(y,table['overlap_rows']/1e6,left=table['novel_rows']/1e6,color=GOLD,label='Already in primary')
ax.set_yticks(y,['MX'+m for m in table.index]); ax.set_xlim(left=0)
ax.set_xlabel('Million wide telemetry rows'); ax.legend(frameon=False)
ax.set_title('Novel and overlapping telemetry\\nAll audited daily files; malformed or conflicting source keys handled separately')
fig.tight_layout(); fig.savefig(FIGURES/'02_novel_rows.png',bbox_inches='tight'); plt.show()
'''), md("### 6. Hp_2nd ของแต่ละเครื่อง–โมดูล เมื่อ SV Off\nแต่ละช่องคือ median ของ daily median ให้แต่ละวันมีน้ำหนักเท่ากัน จึงไม่ใช่ median ของวินาทีทั้งหมด ตัวเลขในวงเล็บคือจำนวนวันที่มี state-qualified samples ค่าเหล่านี้เป็น historical reference ที่ยังต้องตรวจ service epoch; ไม่ใช่ค่าปกติที่อนุมัติแล้ว"),
code('''off = daily[daily.sv.eq('Off')]
profile = off.groupby(['machine','module']).agg(hp2=('hp2_median','median'), days=('date','nunique')).reset_index()
values = profile.pivot(index='machine',columns='module',values='hp2').reindex(columns=range(1,9))
counts = profile.pivot(index='machine',columns='module',values='days').reindex(columns=range(1,9))
fig,ax=plt.subplots(figsize=(12,5))
im=ax.imshow(np.ma.masked_invalid(values.to_numpy()),cmap='Blues',aspect='auto')
for i in range(len(values)):
    for j in range(8):
        v=values.iloc[i,j]
        ax.text(j,i, f'{v:.1f}\\n({int(counts.iloc[i,j])} d)' if pd.notna(v) else 'No data',ha='center',va='center',fontsize=10,
                color='white' if pd.notna(v) and v>(np.nanmin(values.to_numpy())+np.nanmax(values.to_numpy()))/2 else INK)
ax.set_xticks(range(8),[f'M{i}' for i in range(1,9)]); ax.set_yticks(range(len(values)),['MX'+m for m in values.index])
ax.set_title('Hp_2nd reference by machine and module — SV Off\\nMedian of daily state-qualified medians; source pressure scale retained, psi basis unconfirmed')
fig.colorbar(im,ax=ax,label='Hp_2nd — source pressure units'); fig.tight_layout()
fig.savefig(FIGURES/'03_hp2_reference.png',bbox_inches='tight'); plt.show()
display(profile)
'''), md("### 7. ดูการเปลี่ยนตามเวลา ก่อนรวม baseline\nกราฟแยก 8 โมดูลของแต่ละเครื่องและ SV ใช้สเกล pressure เดียวกัน ช่องว่างตามวันคงไว้ แถบ 180–230 psi แสดง qualified field reference ตาม README การเปลี่ยนระดับอาจมาจาก load, state, service, water context หรือ sensor จึงต้องผูกประวัติช่างก่อนอธิบายสาเหตุ"),
code('''for machine in sorted(daily.machine.unique()):
    g=daily[daily.machine.eq(machine)]
    fig, axes=plt.subplots(2,4,figsize=(14,6),sharex=True,sharey=True)
    for module, ax in enumerate(axes.flat,1):
        if g[g.module.eq(module)].empty:
            ax.text(.5,.5,'No candidate data',transform=ax.transAxes,ha='center',color=INK)
        for sv,color,style in [('Off',BLUE,'-'),('On',GOLD,'--')]:
            s=g[g.module.eq(module)&g.sv.eq(sv)].sort_values('date').set_index('date')['hp2_median']
            if len(s):
                s=s.groupby(level=0).median().reindex(pd.date_range(g.date.min(),g.date.max(),freq='D'))
                ax.plot(s.index,s.values,color=color,linestyle=style,label=sv,linewidth=1.4)
        ax.axhspan(180,230,color='#DCEFE4',alpha=.35); ax.set_title(f'Module {module}')
        lo,hi=daily.hp2_median.min(),daily.hp2_median.max()
        ax.set_ylim(min(lo,180)-10,max(hi,230)+10); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    handles=[Line2D([0],[0],color=BLUE,linestyle='-'),Line2D([0],[0],color=GOLD,linestyle='--')]
    fig.legend(handles,['Off','On'],loc='upper right',title='SV',frameon=False)
    fig.suptitle(f'MX{machine}: daily Hp_2nd by module and SV\\n{g.date.min():%Y-%m-%d} to {g.date.max():%Y-%m-%d}; state-qualified samples, source-naive time',fontsize=13)
    fig.supylabel('Daily median Hp_2nd — source pressure units'); fig.tight_layout(rect=(0,0,1,.9))
    fig.savefig(FIGURES/f'04_MX{machine}_daily_hp2.png',bbox_inches='tight'); plt.show()
'''), md("### 8. ความสัมพันธ์ Valve กับ Lp_2nd\nใช้ quality minute สำหรับ EDA ที่ผ่านความต่อเนื่องเพิ่ม 3 นาทีและ SV คงเดิม คำนวณ Spearman แยกเครื่อง–โมดูล–SV ตารางแนบจำนวนแถวและวันเสมอ ความสัมพันธ์ระดับนาทีนี้ยังไม่ใช่ lag response ระดับวินาทีหรือหลักฐานเหตุและผล"),
code('''minute = pl.read_parquet(OUTPUT/'external_minute_module_state.parquet').to_pandas()
minute=minute.sort_values(['machine_number','module','minute'])
minute['machine_number']=minute['machine_number'].astype(str).str.zfill(3)
ok=minute['intake_quality_minute'].copy()
group=minute.groupby(['machine_number','module'],sort=False)
for lag in (1,2,3):
    ok &= group['intake_quality_minute'].shift(lag).eq(True)
    ok &= minute['minute'].sub(group['minute'].shift(lag)).eq(pd.Timedelta(minutes=lag))
    ok &= minute['sv'].eq(group['sv'].shift(lag))
rows=[]; sensor_pairs=[]
sensor_names=['hp1','lp1','hp2','lp2','valve','temphi','templo']
for (machine,module,sv),g in minute[ok].groupby(['machine_number','module','sv']):
    a=g[['valve','lp2']].dropna()
    rows.append({'machine':machine,'module':module,'sv':sv,'minutes':len(a),'days':g.minute.dt.date.nunique(),
                 'spearman_valve_lp2':a.valve.rank().corr(a.lp2.rank()) if len(a)>=200 and a.valve.nunique()>1 and a.lp2.nunique()>1 else np.nan})
    correlations=g[sensor_names].rank().corr() if len(g)>=200 else pd.DataFrame(np.nan,index=sensor_names,columns=sensor_names)
    for i,left in enumerate(sensor_names):
        for right in sensor_names[i+1:]:
            sensor_pairs.append({'machine':machine,'module':module,'sv':sv,'sensor_a':left,'sensor_b':right,
                                 'rho':correlations.loc[left,right],'minutes':len(g),'days':g.minute.dt.date.nunique()})
corr=pd.DataFrame(rows,columns=['machine','module','sv','minutes','days','spearman_valve_lp2']); corr.to_csv(OUTPUT/'minute_valve_lp2_correlations.csv',index=False)
pd.DataFrame(sensor_pairs,columns=['machine','module','sv','sensor_a','sensor_b','rho','minutes','days']).to_csv(OUTPUT/'all_sensor_pair_correlations.csv',index=False)
display(corr)
fig, axes=plt.subplots(1,2,figsize=(13,4.8))
for sv,ax in zip(['Off','On'],axes):
    p=corr[corr['sv'].eq(sv)].pivot(index='machine',columns='module',values='spearman_valve_lp2').reindex(index=sorted(daily.machine.unique()),columns=range(1,9))
    im=ax.imshow(np.ma.masked_invalid(p.to_numpy()),cmap='PuOr',vmin=-1,vmax=1,aspect='auto')
    for i in range(len(p)):
        for j in range(8):
            v=p.iloc[i,j]; ax.text(j,i,f'{v:.2f}' if pd.notna(v) else '—',ha='center',va='center',fontsize=8,color='white' if pd.notna(v) and abs(v)>.65 else INK)
    ax.set_xticks(range(8),range(1,9)); ax.set_yticks(range(len(p)),['MX'+m for m in p.index]); ax.set_xlabel('Module'); ax.set_title('SV '+sv)
fig.suptitle('Valve–Lp_2nd Spearman correlation by context\\nEDA quality-minute observations; ≥200 pairs; missing/constant strata shown as —')
fig.subplots_adjust(top=.8,bottom=.15,wspace=.3,right=.84)
fig.colorbar(im,cax=fig.add_axes([.88,.2,.018,.52]),label='Spearman rho')
fig.savefig(FIGURES/'05_correlations.png',bbox_inches='tight'); plt.show()
'''), md("### 9. เจาะความสัมพันธ์ของ sensor ทั้งเจ็ดในโมดูลที่เลือก\nเปลี่ยน MACHINE, MODULE และ SV เพื่อดูโมดูลอื่น ตาราง `all_sensor_pair_correlations.csv` เก็บคู่ sensor ครบทุกกลุ่มที่มีข้อมูลแล้ว ค่าไม่แสดงเมื่อจำนวนต่ำกว่า 200 หรือ sensor คงที่"),
code('''MACHINE, MODULE, SV = '017', 1, 'Off'
selected=minute[ok & minute.machine_number.eq(MACHINE) & minute.module.eq(MODULE) & minute.sv.eq(SV)]
matrix=selected[sensor_names].rank().corr() if len(selected)>=200 else pd.DataFrame(np.nan,index=sensor_names,columns=sensor_names)
fig,ax=plt.subplots(figsize=(8,7))
im=ax.imshow(np.ma.masked_invalid(matrix.to_numpy()),cmap='PuOr',vmin=-1,vmax=1)
for i in range(7):
    for j in range(7):
        value=matrix.iloc[i,j]
        ax.text(j,i,f'{value:.2f}' if pd.notna(value) else '—',ha='center',va='center',color='white' if pd.notna(value) and abs(value)>.65 else INK)
ax.set_xticks(range(7),sensor_names,rotation=45,ha='right'); ax.set_yticks(range(7),sensor_names)
ax.set_title(f'MX{MACHINE} / M{MODULE} / SV {SV}: sensor correlations\\n{len(selected):,} EDA quality minutes across {selected.minute.dt.date.nunique()} days; Spearman rho')
fig.colorbar(im,ax=ax,shrink=.7); fig.tight_layout(); fig.savefig(FIGURES/'06_sensor_correlations.png',bbox_inches='tight'); plt.show()
'''), md("### 10. QA ของการส่งต่อข้อมูล\nตรวจยอดจาก manifest กับ Parquet ที่แปลงจริง และตรวจ duplicate key ของข้อมูลใหม่ โดยไม่ fit หรือเปลี่ยนโมเดลเดิม"),
code('''parts=[OUTPUT/p for p in manifest['canonical_partition'].dropna()]
canonical=pl.scan_parquet(parts)
total=canonical.select(pl.len()).collect().item()
duplicate_keys=canonical.group_by('machine_number','recorded_at').len().filter(pl.col('len')>1).select(pl.len()).collect().item()
qa={'canonical_count_matches_manifest':total==summary['novel_rows'],
    'unique_machine_timestamp':duplicate_keys==0,
    'no_training_enabled':not summary['train_enabled'],
    'all_daily_parsed':len(summary['errors'])==0,
    'overlap_equality_reconciled':summary['overlap_equal_rows']+summary['overlap_conflict_rows']+int(manifest.get('overlap_unresolved_rows',pd.Series(dtype=float)).fillna(0).sum())==summary['overlap_rows']}
display(pd.Series(qa,name='Passed').to_frame())
assert all(qa.values()), qa
(OUTPUT/'notebook_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
'''), md("""## Takeaways

ข้อมูลเพิ่มถูกเชื่อมเข้าชั้นอ่านข้อมูลและ EDA แล้ว โดยมีไฟล์ต้นทางและ checksum ย้อนกลับได้ การนำไปฝึก ML ต่อใช้แผนดังนี้:

1. **MX017 / MX057 / MX070:** ใช้ช่วงก่อนชุดหลักศึกษาความเสถียรระยะยาวและเตรียม calibration candidate แยก service epoch ต้องประกาศ split รุ่นใหม่ก่อน fit
2. **MX007 / MX012 / MX025:** ใช้ศึกษาการย้ายไปเครื่องอื่นและทดสอบแบบย้อนหลัง แยกให้ชัดว่าเครื่องเหล่านี้ไม่อยู่ในชุดหลัก 19 เครื่อง แต่เคยปรากฏในโครงการ Data Analysis เดิม จึงไม่ถือเป็น blind holdout สำหรับทุกการทดลอง
3. **One-second analysis:** canonical ใหม่ยังเก็บ timestamp จริง จึงนำไปตรวจ coverage ของ opening/SV On และสร้าง window 30/120 วินาทีได้ ข้อมูลที่เพิ่มขึ้นยังไม่พิสูจน์ว่า coverage ของทุก state ผ่านแล้ว
4. **Auto-bootstrap:** เริ่มจาก EDA quality minutes แล้วเพิ่ม settling/service exclusion, uncertainty, shadow และ approval ตาม Phase 06
5. **ก่อน retrain:** ยืนยันหน่วยและ timezone, ผูก service/refill epoch, ประกาศ train/inner validation/calibration/outer test รุ่นใหม่ และให้ผล benchmark เดิมคงเป็นหลักฐานของ dataset รุ่นเดิม

ผล pressure และ correlation ในเล่มนี้ใช้ชี้จุดให้ตรวจต่อ การยืนยัน leak และการรับรอง baseline ต้องมีหลักฐานจากช่าง งาน server replay, deployment package และการทดลอง sequence ยังเป็นงานแยกที่ต้องทำต่อ
""")]
nb = nbf.v4.new_notebook(cells=cells, metadata={'kernelspec': {'display_name':'Python 3','language':'python','name':'python3'}})
target=ROOT/'notebooks/07B_HT9046MX_External_Dataset_Intake_Colab.ipynb'
nbf.write(nb,target)
print(target)
