"""Project reviewed phase evidence for the inline explanation; SELECT-only QA."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,sys
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from notebooks.support.sv_settling_diagnostic import profiles,F
from apps.api.app.reference_raw import read_raw
from apps.api.app.config import get_settings
from apps.api.app.db import source_connection,connection
from apps.api.app.inference import get_machine_candidates,_qualified_source_table
from sqlalchemy import text,bindparam
OUT=ROOT/'notebooks/outputs/sv_settling_diagnostic_20261005'
VIZ=Path('C:/Users/Book/.codex/visualizations/2026/09/30/01a0f038-7484-7e81-8bc2-473fab2b9dd6')

def approve_preview(payload):
    for item in payload['items']:
        for query in item['queries']:
            if query.get('rows'):query['columns']=list(dict.fromkeys(k for row in query['rows'] for k in row))
            src=query['source']
            if src.get('reportingPeriod'):query['reportingPeriod']=src['reportingPeriod']
            for definition in src.get('metricDefinitions',[]):
                if 'name' in definition:definition['label']=definition.pop('name')
            for step in src.get('evidenceFlow',[]):
                if 'description' in step:step['detail']=step.pop('description')
    return payload

def run():
    VIZ.mkdir(parents=True,exist_ok=True);settings=get_settings();p=profiles();prof=p['017',1];baseline=prof['baseline'];threshold=prof['threshold']
    means=pd.concat([pd.read_parquet(ROOT/'notebooks/outputs/october_three_machine_calibration_v1/minutes'/f'017_{day}.parquet') for day in ['2026-09-17','2026-09-29','2026-09-30']])
    means=means[means.module.eq(1)].sort_values('stamp').set_index('stamp');checks=[]
    for start,end in [('2026-09-17T09:00','2026-09-17T09:30'),('2026-09-17T09:30','2026-09-17T10:00'),('2026-09-29T23:35','2026-09-30T00:05'),('2026-09-30T00:00','2026-09-30T00:30')]:
        raw=read_raw(settings,'MX017',1,datetime.fromisoformat(start),datetime.fromisoformat(end));d=pd.DataFrame(raw['chart']);d['stamp']=pd.to_datetime(d.time)
        grouped=d.groupby(d.stamp.dt.floor('min'))[F].mean();joined=means[F].join(grouped,rsuffix='_raw',how='inner');err=float(np.nanmax(abs(joined[F].to_numpy()-joined[[f+'_raw' for f in F]].to_numpy())))
        assert err<1e-8 and raw['duplicate_rows']==0
        checks.append({'start':start,'end':end,'rows':raw['observed_rows'],'matched_minutes':len(joined),'maximum_feature_error':err})
    pd.DataFrame(checks).to_csv(OUT/'chart_source_parity.csv',index=False)
    source_rows=[]
    for t0,label in [('2026-09-17T09:00:29','Reference · 17 Sep'),('2026-09-29T23:34:53','Shadow · 29 Sep')]:
        t0=pd.Timestamp(t0);rows=means.loc[(means.index>=t0.ceil('min'))&(means.index<t0+pd.Timedelta('35min'))]
        assert rows.eligible.all()
        for stamp,r in rows.iterrows():
            elapsed=(stamp-t0).total_seconds()/60
            source_rows.append({'elapsed_minute':int(np.floor(elapsed)),'actual_elapsed_minute':elapsed,'series':label,'temperature_c':float(r.temphi),
              'hp2_psi':float(r.hp2),'stamp':stamp.isoformat(),'event':t0.isoformat()})
    upper=baseline['temphi']['median']+threshold*baseline['temphi']['scale']
    for minute in range(35):source_rows.append({'elapsed_minute':minute,'series':'Steady upper boundary','temperature_c':float(upper)})
    pd.DataFrame(source_rows).to_csv(OUT/'episode-trajectory-values.csv',index=False)
    generated=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat()
    source={'label':'MX017 M1 · observed transition temperatures','files':[{'label':'episode-trajectory-values.csv'},{'label':'chart_source_parity.csv'},{'label':'Saved physical-v2 Candidate 241'}],
      'metricDefinitions':[{'name':'Temperature','definition':'TempHi is the observed-second mean for each complete, qualified minute after the witnessed SV On→Off transition.'}],
      'reportingPeriod':'17 Sep09:00:29 and29 Sep23:34:53, 2026; first35 minutes; Asia/Bangkok',
      'caveats':['Elapsed labels are minute bins (floor of elapsed time); actual source offsets differ by less than one minute between the two episodes.',
         'The Reference trace is one unverified historical recovery example, not a validated normal envelope.',
         'The upper line is the frozen physical-v2 minute threshold boundary, not a safety limit or raw-second threshold.'],
      'evidenceFlow':[{'kind':'validation','title':'Source reconciliation','description':'Four bounded SELECT-only Raw slices reconciled 120 minute means across eight physical features against the archived minute means; maximum error0 and no duplicate source seconds.'}]}
    chart={'schemaVersion':1,'id':'mx017-m1-transition-temphi','title':'MX017 M1 · TempHi หลัง SV OFF','description':'ค่าเฉลี่ยรายนาที · Reference เทียบ Shadow · °C',
      'chart':{'type':'line','x':'elapsed_minute','y':'temperature_c','series':'series','xLabel':'นาทีหลัง SV OFF','yLabel':'TempHi (°C)','showXAxisLabel':True,'showYAxisLabel':True,'startAtZero':False},
      'rows':[{k:r[k] for k in ['elapsed_minute','series','temperature_c']} for r in source_rows],'source':source,'generatedAt':generated,'theme':'codex-classic'}
    (OUT/'inline-chart.json').write_text(json.dumps(chart,indent=2,ensure_ascii=False),encoding='utf-8')
    chart_receipt={'schemaVersion':1,'items':[{'id':'transition-temperature','title':'TempHi หลัง SV OFF','queries':[{'id':'mx017-temperature','source':source,'rows':source_rows}]}]}
    (OUT/'inline-chart-sources.json').write_text(json.dumps(approve_preview(chart_receipt),indent=2,ensure_ascii=False),encoding='utf-8')
    events=pd.read_csv(OUT/'multi_events.csv',dtype={'machine':str});supports=pd.read_csv(OUT/'multi_support.csv',dtype={'machine':str});contexts=pd.read_csv(OUT/'multi_contexts.csv',dtype={'machine':str})
    ref=events[events.phase.eq('reference')&events.returned_confirm_min.notna()]
    assert len(ref)==397 and ref.pre_return_flagged_minutes.gt(0).sum()==252
    summary=ref.groupby('machine').agg(returned=('event_id','size'),pre_return_physical_flags=('pre_return_flagged_minutes',lambda v:int(v.gt(0).sum())),median_minutes=('returned_confirm_min','median'),p95_minutes=('returned_confirm_min',lambda v:v.quantile(.95))).reset_index()
    summary.to_csv(OUT/'machine_reference_summary.csv',index=False)
    receipt={'schemaVersion':1,'items':[{'id':'multi-machine-on-transitions','title':'พฤติกรรมช่วงเปลี่ยนสถานะจากหลายเครื่อง','queries':[{
      'id':'multi-machine-reference','rows':summary.to_dict('records'),'source':{
        'label':'Past-only multi-machine transition review','files':[{'label':'multi_receipt.json'},{'label':'multi_events.csv'},{'label':'offline_physical_profiles.json'},{'label':'raw source event ledgers'}],
        'metricDefinitions':[{'name':'Reference recoveries','definition':'397 module-event records had three consecutive qualified minute scores at or below their frozen baseline threshold;252 had physical flags before that return.'}],
        'reportingPeriod':'017/024 Reference31Aug-before28Sep2026; other machines4Aug-before18Aug2026, Asia/Bangkok',
        'caveats':['Nine machines were inspected;118/119 lacked sufficient past Reference. Seven machines supported50 descriptive machine/module baselines.',
          'Module-event records from a common machine transition are correlated; counts are not independent machine starts or false-positive rates.',
          'Recovery-conditioned Reference examples are not verified healthy labels. Duration statistics describe only observed returns; censored episodes are retained separately.',
          '36 machine/module/event-kind groups have at least three returned Reference examples on three days; this is exploratory support, not validated95% envelope coverage.',
          'Older archive entry kinds do not distinguish SVOff from moduleOn in every event. Exact017/024 SV/state witnesses were checked separately against actual SQL Raw.'],
        'evidenceFlow':[{'kind':'validation','title':'Frozen baseline and temporal split','description':'017/024 use exact saved physical-v2 baselines; the other contexts use pure past-only physical-v2 fits. No event thresholds were chosen from Shadow; no Profile or runtime changed.'}]}}]},
      {'id':'persistent-deviation-control','title':'ค่าที่นิ่งแต่ไม่กลับเข้า baseline','queries':[{'id':'stable-abnormal-controls','source':{
        'label':'Actual024 review and known-case evidence','files':[{'label':'events.csv'},{'label':'cut_sensitivity.csv'},{'label':'known-case-regression.json'},{'label':'MX057-M1-20260829-001'},{'label':'MX080-M6-20260907-001'}],
        'metricDefinitions':[{'name':'Persistent deviation','definition':'MX024 M4/M6 after28Sep manual control return remained above their frozen baseline threshold for the full120-minute observed run, despite meeting exploratory variation criteria at roughly29/24 minutes.'}],
        'caveats':['Exploratory stability uses Reference-derived slope/range limits; stability is not a normal label or a fault diagnosis.',
          'Known057/080 cases are owner-confirmed telemetry anomalies, not technician-confirmed physical causes or a fresh prospective test.']}}]}]}
    (OUT/'inline-answer-sources.json').write_text(json.dumps(approve_preview(receipt),indent=2,ensure_ascii=False),encoding='utf-8')
    with source_connection() as c:
        table=_qualified_source_table(settings.source_db_name,settings.source_table)
        q=text(f'SELECT MAX(`{settings.source_timestamp_column}`) FROM {table} WHERE `{settings.source_machine_column}` IN :machines').bindparams(bindparam('machines',expanding=True))
        latest={m:str(c.execute(q,{'machines':get_machine_candidates('MX'+m)}).scalar()) for m in ['017','024']}
    (OUT/'delivery_checks.json').write_text(json.dumps({'generated_at':generated,'raw_reconciliation':checks,'source_latest':latest,
      'reference_returned_records':len(ref),'pre_return_flagged_records':int(ref.pre_return_flagged_minutes.gt(0).sum()),'runtime_changed':False},indent=2),encoding='utf-8')
    print(json.dumps({'source_latest':latest,'chart_rows':len(source_rows),'confirmed_rows':sum(c['rows'] for c in checks)}))

if __name__=='__main__':run()
