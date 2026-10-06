import numpy as np
import pandas as pd
from notebooks.support.fleet_reference_benchmark import fit,event_split,steady
from apps.api.app.fleet_assistance import FEATURES


def test_minute_sampling_independent_of_parquet_datetime_precision():
    stamps=pd.date_range('2026-08-14',periods=1440,freq='min')
    frame=pd.DataFrame({'time':stamps,'quality':True,'context':'SV_OFF'})
    for i,feature in enumerate(FEATURES):frame[feature]=200+i+np.sin(np.arange(1440)/100)*.1
    results=[]
    for unit in ('ns','us'):
        data=frame.copy();data['time']=data.time.astype(f'datetime64[{unit}]')
        result=fit(data,'041',1,'SV_OFF','2026-08-14','2026-08-15')
        assert result is not None and result['n']==95
        results.append(result)
    assert results[0]['center']==results[1]['center']
    assert results[0]['covariance']==results[1]['covariance']


def test_transition_split_uses_same_exclusive_periods_as_steady_study():
    for day,expected in [('2026-07-01','outside_evaluation'),('2026-07-02','reference'),
                         ('2026-08-15','calibration'),('2026-08-22','outside_evaluation'),
                         ('2026-09-01','diagnostic'),('2026-10-01','outside_evaluation')]:
        assert event_split(pd.Timestamp(day))==expected


def test_stability_rejects_accumulated_drift_and_cross_context_or_gap_windows():
    frame=pd.DataFrame({'time':pd.date_range('2026-08-14',periods=12,freq='min'),
                        'quality':True,'context':'SV_OFF'})
    for feature in FEATURES:frame[feature]=np.arange(12)*.1
    # Each adjacent change is .1, but five-minute range .4 exceeds .35.
    assert not steady(frame,np.ones(6)).any()
    for feature in FEATURES:frame[feature]=1.
    assert steady(frame,np.ones(6)).iloc[4:].all()
    frame.loc[6:,'context']='SV_ON'
    assert not steady(frame,np.ones(6)).iloc[6:10].any()
    frame.loc[10:,'time']+=pd.Timedelta(minutes=2)
    assert not steady(frame,np.ones(6)).iloc[10:].any()
