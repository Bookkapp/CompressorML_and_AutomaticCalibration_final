"""Predeclared fixed-policy case replay; no fitting/tuning on case labels."""
import sys,json
from pathlib import Path
from datetime import datetime,timedelta
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from apps.api.app.qualified_windows import QualifiedWindow,FEATURES,STATE_CODE,WINDOW_VERSION
from apps.api.app.qualified_calibration import fit_one_minute_candidate
from apps.api.app.qualified_policy import THRESHOLD_VERSION,LEGACY_THRESHOLD_VERSION
from apps.api.app.qualified_scoring import ApprovedProfile,QualifiedShadowScorer
OUT=ROOT/'notebooks/outputs/physical_control_qa_20261004'
cases=[('057',1,'2026-08-20','2026-08-27','2026-08-30','2026-08-29T04:06:00','2026-08-29T22:50:00','local_profile_model_selection_v1'),
       ('080',6,'2026-09-03','2026-09-07','2026-09-08','2026-09-07T12:24:00','2026-09-08T00:00:00','october_three_machine_calibration_v1')]
result=[]
for machine,module,start,shadow,end,a,b,folder in cases:
    start,shadow,end,a,b=map(datetime.fromisoformat,(start,shadow,end,a,b))
    frames=[]
    for day in pd.date_range(start,end-timedelta(days=1)):
        path=ROOT/'notebooks/outputs'/folder/'minutes'/f'{machine}_{day:%Y-%m-%d}.parquet'
        frames.append(pd.read_parquet(path))
    frame=pd.concat(frames);frame=frame.loc[frame.module==module].sort_values('stamp')
    windows=[]
    for row in frame.itertuples():
        t=row.stamp.to_pydatetime();ok=bool(row.eligible)
        windows.append(QualifiedWindow('MX'+machine,module,t,t+timedelta(minutes=1),'Off' if ok else 'UNKNOWN',STATE_CODE if ok else 'NOT_SCORED',
            int(row.samples),60,min(1.,row.samples/60.),float(row.gap),'PASS' if ok else 'ARCHIVE_NOT_QUALIFIED','' if ok else 'ARCHIVE_NOT_QUALIFIED',
            {f:float(getattr(row,f)) for f in FEATURES} if ok else None))
    comparison=[]
    for version in [LEGACY_THRESHOLD_VERSION,THRESHOLD_VERSION]:
        c=fit_one_minute_candidate(windows,machine_number='MX'+machine,module=module,calibration_start=start,shadow_start=shadow,shadow_end=end,scoring_version=version)
        p=ApprovedProfile(999999,'OFFLINE_NOT_ACTIVE',WINDOW_VERSION,'MX'+machine,module,'Off',STATE_CODE,c['medians'],c['scales'],c['threshold'],version,shadow)
        scorer=QualifiedShadowScorer();scores=[scorer.score(w,p) for w in windows if w.window_start>=shadow]
        positive=[s for s in scores if a<=s.window_start<b and s.status=='SCORED']
        comparison.append({'threshold_version':version,'candidate_status':c['status'],'threshold':c['threshold'],'quarantine_pct':c['quarantine_pct'],
            'case_qualified_minutes':len(positive),'case_raw_flags':sum(s.primary_raw_flag for s in positive),
            'case_persistent_minutes':sum(s.primary_persistent_flag for s in positive),
            'first_case_flag':next((s.window_start.isoformat() for s in positive if s.primary_raw_flag),None),
            'case_coverage_pct':100*sum(s.primary_raw_flag for s in positive)/len(positive)})
    value={'machine':'MX'+machine,'module':module,'case_start':a.isoformat(),'case_end':b.isoformat(),'source':'Previously raw-parity checked observed-second-derived archive minute cache',
        'comparison':comparison,'thresholds_fit_on_past_reference_only':True,'runtime_or_active_changed':False}
    result.append(value);print(json.dumps(value),flush=True)
(OUT/'known-case-regression.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
