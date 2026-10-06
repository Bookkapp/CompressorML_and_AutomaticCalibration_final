"""Reproducible read-only Fleet study on checksum-reconciled imported ZIP days.

Sources stay untouched. Derived evidence is day-partitioned and resumable.
Unreviewed operating data are not healthy labels; all models are proposals.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import zipfile

os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("POLARS_MAX_THREADS","2")
import numpy as np
import pandas as pd
import polars as pl
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from apps.api.app.fleet_assistance import FEATURES,VERSION,fit_local,pool,scores,self_scores,calibrate
from apps.api.app.config import get_settings

OUT=ROOT/'notebooks/outputs/fleet_reference_study_20261005'
MACHINES=('017','024','041','058','080','081')
DERIVED_VERSION='all-state-study-1m-v3'
TAGS={'hp1':'Hp_1st','lp1':'Lp_1st','hp2':'Hp_2nd','lp2':'Lp_2nd',
      'temphi':'TempHi','templo':'TempLo','valve':'Valve'}
PATTERN=re.compile(r'^(2026_\d{2}_\d{2})\.txt$')
RAW_COLUMNS=['Time','Status',*[f'{tag}_{m}' for m in range(1,9)
              for tag in ('Hp_1st','Lp_1st','Hp_2nd','Lp_2nd','Valve','Status','TempHi','TempLo','SV','Busy')]]
PROTOCOL={'version':VERSION,'source_clock':'Asia/Bangkok, naive original DATETIME interpretation',
          'source_period':['2026-07-01','2026-10-02'],'reference':['2026-07-02','2026-08-15'],
          'calibration':['2026-08-15','2026-08-22'],'diagnostic':['2026-09-01','2026-10-01'],
          'sparse_days':[1,3,7,14],'features':list(FEATURES),'sample_spacing_minutes':15,
          'stability_trailing_minutes':5,'stability_limit':.35,'threshold_quantile':.995,
          'stability_definition':'physical max-minus-min over five contiguous supported minutes, normalized by Reference scale',
          'minimum_threshold_points':200,'minimum_threshold_days':3,'seed':17,
          'transfer_center_rms_max':1.5,'transfer_correlation_distance_max':.5,
          'transfer_min_target_points':20,'min_donor_machines':2,'prior_strength_cap':20,
          'grouping':'same module index is an explicit unverified research stratum, not production role mapping',
          'interpretation':'historical diagnostic; healthy/fault classification and prospective accuracy not established',
          'model_policy':'Local absolute evidence retained; Fleet and transition proposals nonvoting; ARX offline challenger'}


def write_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding='utf-8')
    temp.replace(path)


class DigestReader(io.RawIOBase):
    def __init__(self,stream):self.stream=stream;self.digest=hashlib.sha256()
    def readable(self):return True
    def readinto(self,b):
        chunk=self.stream.read(len(b));b[:len(chunk)]=chunk;self.digest.update(chunk);return len(chunk)


def ledger():
    settings=get_settings()
    if make_url(settings.database_url).host not in ('localhost','127.0.0.1','::1'):
        raise RuntimeError('study only uses configured local receipts')
    engine=create_engine(settings.database_url,pool_pre_ping=True)
    with engine.connect() as conn:
        columns=[r[0] for r in conn.execute(text('SHOW COLUMNS FROM ht9046mx_history_import_file'))]
        rows=[dict(r) for r in conn.execute(text('SELECT * FROM ht9046mx_history_import_file')).mappings()]
    engine.dispose()
    return {(str(r['machine_number']).zfill(3),str(r['source_date'])):
            {**json.loads(r['receipt_json']),**r} for r in rows},columns


def inventory():
    root=Path('C:/Users/Book/Downloads');entries=[];handles=[]
    paths=list(root.glob('HT9046MX-Compressor-Data-20261001*.zip'))
    for m in ('041','058','081'):paths.extend((root/f'MX{m}').glob('*.zip'))
    for path in sorted(paths):
        archive=zipfile.ZipFile(path);handles.append(archive)
        candidates=[(archive,member,None) for member in archive.infolist()]
        for nested in archive.infolist():
            if not nested.filename.endswith('.zip'):continue
            if nested.file_size>128*2**20:raise ValueError('Nested archive exceeds bounded study memory budget')
            inner=zipfile.ZipFile(io.BytesIO(archive.read(nested)));handles.append(inner)
            hint=next((part for part in nested.filename.split('/') if part in MACHINES),None)
            candidates.extend((inner,member,hint) for member in inner.infolist())
        for handle,member,hint in candidates:
            match=PATTERN.match(member.filename.rsplit('/',1)[-1])
            if not match:continue
            parts=member.filename.split('/')
            machine=parts[1] if parts[0]=='HT9046MX-Compressor-Data' else parts[0]
            if machine not in MACHINES and hint:machine=hint
            day=match[1].replace('_','-')
            if machine not in MACHINES or not PROTOCOL['source_period'][0]<=day<PROTOCOL['source_period'][1]:continue
            entries.append({'machine':machine,'date':day,'archive':path.name,'member':member.filename,
                            'crc32':member.CRC,'bytes':member.file_size,'handle':handle,'info':member})
    keys=[(e['machine'],e['date']) for e in entries]
    if len(keys)!=len(set(keys)):raise ValueError('ambiguous canonical machine/day')
    return sorted(entries,key=lambda e:(e['machine'],e['date'])),handles


def read_day(entry):
    with entry['handle'].open(entry['info']) as s:first=s.readline().decode('utf-8-sig').strip()
    numeric=[f'{tag}_{m}' for m in range(1,9) for tag in TAGS.values()]
    with entry['handle'].open(entry['info']) as stream:
        reader=DigestReader(stream)
        with io.BufferedReader(reader,buffer_size=2**20) as buffered:
            frame=pl.read_csv(buffered,skip_rows=0 if first.startswith('Time') else 1,
                              infer_schema=False)
        digest=reader.digest.hexdigest()
    frame=frame.rename({c:c.strip() for c in frame.columns})
    if set(frame.columns)!=set(RAW_COLUMNS):raise ValueError(f'Unexpected source schema {entry["machine"]} {entry["date"]}')
    frame=frame.with_columns([pl.col(c).str.strip_chars().cast(pl.Float64,strict=False) for c in numeric]+
          [pl.col(c).str.strip_chars().str.to_lowercase() for c in RAW_COLUMNS if c not in numeric])
    frame=frame.with_columns((pl.lit(entry['date']+' ')+pl.col('Time')).str.strptime(pl.Datetime,
                         format='%Y-%m-%d %H:%M:%S',strict=False).alias('stamp'))
    if frame['stamp'].null_count():raise ValueError('invalid/subsecond source time')
    return frame.sort('stamp',maintain_order=True),digest


def derive_polars(frame,machine):
    """Vectorized all-state adapter; parity checked against production builder."""
    frame=frame.with_columns(pl.col('stamp').dt.truncate('1m').alias('_minute'))
    expressions=[pl.len().alias('samples'),pl.col('stamp').n_unique().alias('occupied'),
                 pl.col('stamp').min().alias('first'),pl.col('stamp').max().alias('last'),
                 pl.col('stamp').diff().dt.total_seconds().max().alias('internal_gap')]
    for module in range(1,9):
        expressions += [pl.col(f'{tag}_{module}').mean().alias(f'{feature}_{module}') for feature,tag in TAGS.items()]
        expressions += [pl.all_horizontal([pl.col(f'{TAGS[f]}_{module}').is_finite().fill_null(False)
                                          for f in FEATURES]).all().alias(f'complete_{module}')]
        expressions += [pl.col(f'Valve_{module}').is_finite().fill_null(False).all().alias(f'valve_complete_{module}')]
        for key,col in [('compressor','Status'),('module_state',f'Status_{module}'),('busy',f'Busy_{module}'),('sv',f'SV_{module}')]:
            expressions += [pl.col(col).fill_null('').first().alias(f'{key}_{module}'),
                            pl.col(col).fill_null('').n_unique().alias(f'{key}_count_{module}')]
    wide=frame.group_by('_minute',maintain_order=True).agg(expressions)
    wide=wide.with_columns(pl.max_horizontal(pl.col('internal_gap').fill_null(0),
          (pl.col('first')-pl.col('_minute')).dt.total_seconds(),
          (pl.col('_minute')+pl.duration(minutes=1)-pl.col('last')).dt.total_seconds()).alias('gap'))
    wide=wide.with_columns(((pl.col('samples')==pl.col('occupied'))&(pl.col('occupied')>=57)&
                           (pl.col('gap')<=5)).alias('base_quality'))
    parts=[];event_parts=[]
    for module in range(1,9):
        out=wide.select([pl.col('_minute').alias('time'),pl.lit(machine).alias('machine'),pl.lit(module).alias('module'),
              pl.col('samples'),(pl.col('occupied')/60).alias('coverage'),pl.col('gap'),
              (pl.col('base_quality')&pl.col(f'complete_{module}')).alias('quality'),
              pl.all_horizontal([(pl.col(f'{k}_count_{module}')==1)&(pl.col(f'{k}_{module}')!='')
                                 for k in ('compressor','module_state','busy','sv')]).alias('stable_control'),
              *[pl.col(f'{key}_{module}').alias(key) for key in ('compressor','module_state','busy','sv')],
              *[pl.col(f'{f}_{module}').alias(f) for f in FEATURES],
              pl.when(pl.col(f'valve_complete_{module}')).then(pl.col(f'valve_{module}')).otherwise(None).alias('valve')])
        eligible=pl.col('stable_control')&(pl.col('compressor')=='run')&(pl.col('module_state')=='on')&\
                 pl.col('busy').is_in(['0','false','off'])&pl.col('sv').is_in(['on','off','1','0','true','false'])&\
                 (pl.col('valve')>=0)&pl.col('valve').is_finite()
        out=out.with_columns(pl.when(eligible).then(pl.when(pl.col('sv').is_in(['on','1','true']))
                   .then(pl.lit('SV_ON')).otherwise(pl.lit('SV_OFF'))).otherwise(pl.lit('UNSUPPORTED')).alias('context'),
                   *[pl.when(pl.col('quality')).then(pl.col(f)).otherwise(None).alias(f) for f in FEATURES])
        parts.append(out)
        for kind,col in [('SV_CHANGED',f'SV_{module}'),('MODULE_STATE_CHANGED',f'Status_{module}'),
                         ('BUSY_CHANGED',f'Busy_{module}'),('VALVE_CHANGED',f'Valve_{module}')]:
            event=frame.select(pl.col('stamp').alias('time'),pl.col(col).shift().cast(pl.String).alias('before'),
                pl.col(col).cast(pl.String).alias('after'),pl.col('stamp').diff().dt.total_seconds().alias('gap_seconds'))
            event=event.filter(pl.col('before').is_not_null()&(pl.col('before')!=pl.col('after')))
            if event.height:
                usable=pl.col('gap_seconds').is_between(1,5)
                if kind=='VALVE_CHANGED':
                    usable=usable&pl.col('before').cast(pl.Float64,strict=False).is_finite().fill_null(False)&pl.col('after').cast(pl.Float64,strict=False).is_finite().fill_null(False)
                event=event.with_columns(pl.lit(module).alias('module'),pl.lit(machine).alias('machine'),
                  pl.lit(kind).alias('event_type'),usable.alias('witness_usable'))
                event_parts.append(event)
    minutes=pl.concat(parts).to_pandas();events=pl.concat(event_parts).to_pandas() if event_parts else pd.DataFrame()
    return minutes,events


def derive_day(frame,machine):
    stamp=frame.stamp;minute=stamp.dt.floor('min');groups=frame.groupby(minute,sort=True)
    base=groups.stamp.agg(['size','min','max','nunique'])
    internal=stamp.diff().dt.total_seconds().where(minute.eq(minute.shift())).groupby(minute).max().reindex(base.index).fillna(0)
    gap=pd.concat([internal,(base['min']-pd.Series(base.index,index=base.index)).dt.total_seconds(),
                  (pd.Series(base.index+pd.Timedelta(minutes=1),index=base.index)-base['max']).dt.total_seconds()],axis=1).max(axis=1)
    quality=base['size'].eq(base['nunique'])&base['nunique'].ge(57)&gap.le(5)
    result=[];event_parts=[]
    for module in range(1,9):
        cols=[f'{tag}_{module}' for tag in TAGS.values()]
        numeric=frame[cols]
        physical=[f'{TAGS[f]}_{module}' for f in FEATURES]
        valid=np.isfinite(frame[physical].to_numpy()).all(axis=1)
        complete=pd.Series(valid,index=frame.index).groupby(minute).all().reindex(base.index)
        means=numeric.groupby(minute).mean().rename(columns={f'{tag}_{module}':key for key,tag in TAGS.items()})
        valve_complete=pd.Series(np.isfinite(frame[f'Valve_{module}']),index=frame.index).groupby(minute).all()
        means.loc[~valve_complete,'valve']=np.nan
        states={key:frame[col] for key,col in [('compressor','Status'),('module_state',f'Status_{module}'),
                 ('busy',f'Busy_{module}'),('sv',f'SV_{module}') ]}
        stable_state=pd.Series(True,index=base.index)
        state_values={}
        for key,series in states.items():
            clean=series.fillna('');grouped=clean.groupby(minute)
            state_values[key]=grouped.first().reindex(base.index)
            stable_state &= grouped.nunique().reindex(base.index).eq(1)&state_values[key].ne('')
        out=means.copy();out['time']=base.index;out['machine']=machine;out['module']=module
        out['samples']=base['size'].to_numpy();out['coverage']=base['nunique'].to_numpy()/60;out['gap']=gap.to_numpy()
        out['quality']=quality.to_numpy()&complete.to_numpy();out['stable_control']=stable_state.to_numpy()
        for key,values in state_values.items():out[key]=values.to_numpy()
        out['context']=np.where(out.stable_control & out.compressor.eq('run') & out.module_state.eq('on') &
             out.busy.isin(['0','false','off']) & out.sv.isin(['on','off','1','0','true','false']) &out.valve.ge(0)&np.isfinite(out.valve),
             np.where(out.sv.isin(['on','1','true']),'SV_ON','SV_OFF'),'UNSUPPORTED')
        out.loc[~out.quality,list(FEATURES)]=np.nan
        result.append(out.reset_index(drop=True))
        # Original event timestamps retained. First row is censored: no invented prior-day witness.
        for kind,column in [('SV_CHANGED',f'SV_{module}'),('MODULE_STATE_CHANGED',f'Status_{module}'),
                            ('BUSY_CHANGED',f'Busy_{module}'),('VALVE_CHANGED',f'Valve_{module}')]:
            values=frame[column];changed=values.ne(values.shift()).fillna(False);changed.iloc[0]=False
            if changed.any():
                e=pd.DataFrame({'time':stamp[changed],'before':values.shift()[changed].astype(str),
                                'after':values[changed].astype(str),'module':module,'event_type':kind})
                e['gap_seconds']=stamp.diff().dt.total_seconds()[changed]
                e['witness_usable']=e.gap_seconds.between(1,5)
                if kind=='VALVE_CHANGED':e['witness_usable'] &= np.isfinite(values.shift()[changed]) & np.isfinite(values[changed])
                e['machine']=machine;event_parts.append(e)
    return pd.concat(result,ignore_index=True),pd.concat(event_parts,ignore_index=True) if event_parts else pd.DataFrame()


def intake(limit=None):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'minutes').mkdir(exist_ok=True);(OUT/'events').mkdir(exist_ok=True)
    receipts,columns=ledger();entries,handles=inventory();start=time.perf_counter();completed=[];done=0
    write_json(OUT/'protocol.json',PROTOCOL)
    try:
        for entry in entries:
            key=(entry['machine'],entry['date']);receipt=receipts.get(key)
            # Use only committed files; stopped import is never resumed here.
            if not receipt:continue
            name=f'{key[0]}_{key[1]}';metadata=OUT/'minutes'/f'{name}.json';destination=metadata.with_suffix('.parquet')
            if metadata.exists() and destination.exists():
                saved=json.loads(metadata.read_text(encoding='utf-8'))
                if saved.get('derived_version')==DERIVED_VERSION and saved['source_sha256']==receipt['file_sha256']:
                    completed.append(saved);continue
            frame,digest=read_day(entry)
            if digest!=receipt['file_sha256']:raise ValueError(f'Imported ZIP checksum mismatch {key}')
            if len(frame)!=receipt['raw_rows']:raise ValueError(f'Imported ZIP row count mismatch {key}')
            invalid_valve=sum(int((~frame[f'Valve_{m}'].is_finite().fill_null(False)).sum()) for m in range(1,9))
            # v2 is numerically identical when every Valve observation is finite.
            # Validate each original file before reusing its derivative; record the proof.
            if metadata.exists() and destination.exists():
                saved=json.loads(metadata.read_text(encoding='utf-8'))
                if saved.get('derived_version')=='all-state-study-1m-v2' and saved['source_sha256']==digest and invalid_valve==0:
                    saved.update(derived_version=DERIVED_VERSION,invalid_valve_observations=0,
                                 valve_completeness_verified=True,
                                 minute_parquet_sha256=hashlib.file_digest(destination.open('rb'),'sha256').hexdigest())
                    write_json(metadata,saved);completed.append(saved);done+=1
                    del frame;gc.collect()
                    if done%5==0:print(json.dumps({'phase':'valve_completeness_audit','files_done':len(completed),'last':name,'elapsed_seconds':round(time.perf_counter()-start,1)}),flush=True)
                    if limit and done>=limit:break
                    continue
            minutes,events=derive_polars(frame,key[0]);temp=destination.with_suffix('.tmp.parquet')
            minutes.to_parquet(temp,index=False,compression='zstd');temp.replace(destination)
            if len(events):events.to_parquet(OUT/'events'/f'{name}.parquet',index=False,compression='zstd')
            record={k:v for k,v in entry.items() if k not in ('handle','info')}
            record.update(source_sha256=digest,raw_rows=len(frame),minute_module_rows=len(minutes),
                          duplicate_rows=int(frame['stamp'].is_duplicated().sum()),
                          quality_minutes=int(minutes.quality.sum()),source_events=len(events),
                          minute_parquet_sha256=hashlib.file_digest(destination.open('rb'),'sha256').hexdigest(),
                          pass_context_counts=minutes.loc[minutes.quality].context.value_counts().to_dict(),
                          derived_version=DERIVED_VERSION,schema_columns=len(frame.columns)-1,
                          invalid_valve_observations=invalid_valve,valve_completeness_verified=True,
                          event_boundary_policy='first source row has no invented predecessor; day boundaries censored')
            write_json(metadata,record);completed.append(record);done+=1
            del frame,minutes,events;gc.collect()
            if done%5==0 or limit:
                print(json.dumps({'phase':'intake','files_done':len(completed),'last':name,
                                  'elapsed_seconds':round(time.perf_counter()-start,1)}),flush=True)
            if limit and done>=limit:break
    finally:
        for handle in handles:handle.close()
    manifest={'version':DERIVED_VERSION,'source_period':PROTOCOL['source_period'],
              'source_family':'canonical dynamic ZIP files, matched to committed local MySQL receipt SHA and row count',
              'files':completed,'raw_rows':sum(r['raw_rows'] for r in completed),
              'elapsed_seconds':time.perf_counter()-start,'source_writes':False,
              'known_limitation':'Does not merge older SQL fixtures/changed overlapping source rows; not a live SQL snapshot.',
              'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_json(OUT/'intake_manifest.json',manifest)
    print(json.dumps({'phase':'intake_complete','files':len(completed),'seconds':round(manifest['elapsed_seconds'],2)}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--intake',action='store_true')
    parser.add_argument('--limit',type=int);args=parser.parse_args()
    if args.intake:intake(args.limit)
    else:parser.error('choose --intake')


if __name__=='__main__':main()
