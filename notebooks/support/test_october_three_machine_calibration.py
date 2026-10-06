"""Local data-analysis parity tests; no SQL execution."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from apps.api.app.qualified_windows import build_completed_windows, WindowPolicy
from apps.api.app.qualified_calibration import fit_one_minute_candidate
from notebooks.support.october_three_machine_calibration import minute_day, fit_array, persistent_flags, FEATURES


def source_frame():
    stamps = pd.Series(pd.date_range('2026-07-01',periods=240,freq='s'))
    data = {'Status':['Run']*240}
    for module in range(1,9):
        for tag,value in [('Hp_1st',150),('Lp_1st',25),('Hp_2nd',210),('Lp_2nd',12),
                          ('Valve',80),('TempHi',82),('TempLo',-20)]:
            data[f'{tag}_{module}'] = np.arange(240)*.001+value
        data[f'Status_{module}'] = ['On']*240
        data[f'Busy_{module}'] = ['0']*240
        data[f'SV_{module}'] = ['Off']*240
    return pd.DataFrame(data),stamps


@pytest.mark.parametrize('issue',['clean','duplicate','gap','manual','nan','negative_valve','state'])
def test_vectorized_matches_runtime_window_gate(issue):
    frame,stamps=source_frame()
    if issue=='duplicate': stamps.iloc[20]=stamps.iloc[19]
    if issue=='gap':
        keep=~stamps.index.isin(range(20,30))
        frame=frame.loc[keep].reset_index(drop=True); stamps=stamps.loc[keep].reset_index(drop=True)
    if issue=='manual': frame.loc[20,'Busy_6']='1'
    if issue=='nan': frame.loc[20,'TempLo_6']=np.nan
    if issue=='negative_valve': frame.loc[20,'Valve_6']=-1
    if issue=='state': frame.loc[20,'Status_6']='ChangeValve'
    actual=minute_day(frame,stamps,'080',{},[],[])
    rows=frame.assign(recorded_at=stamps,machine_number='080').to_dict('records')
    expected=build_completed_windows(rows,as_of=datetime(2026,7,2,tzinfo=timezone.utc),policy=WindowPolicy('Asia/Bangkok'))
    for window in expected:
        point=actual[(actual.module==window.module)&actual.stamp.eq(window.window_start)].iloc[0]
        assert bool(point.eligible)==window.eligible
        if window.eligible:
            assert point[FEATURES].astype(float).to_dict()==pytest.approx(window.features,abs=1e-10)


def test_unknown_file_start_is_not_observed_start_and_cross_day_age_continues():
    frame,stamps=source_frame()
    tails,events={},[]
    points=minute_day(frame,stamps,'080',tails,events,[])
    assert points.loc[points.eligible,'elapsed_known_seconds'].eq(0).all()
    assert all(e['kind']=='UNKNOWN_GAP_OR_LEFT_CENSORED' for e in events)
    frame.loc[30,'Status']='Stop'
    tails,events={},[]
    points=minute_day(frame,stamps,'080',tails,events,[])
    assert any(e['kind']=='OBSERVED_RUN_START' for e in events)
    next_stamps=stamps+pd.Timedelta(seconds=240)
    next_points=minute_day(source_frame()[0],next_stamps,'080',tails,[],[])
    assert next_points[(next_points.module==6)&next_points.stamp.eq('2026-07-01 00:04')].iloc[0].elapsed_min_seconds==209


def test_quantile_fit_matches_existing_candidate():
    from apps.api.app.qualified_windows import QualifiedWindow,STATE_CODE,WINDOW_VERSION
    rng=np.random.default_rng(13)
    stamps=pd.date_range('2026-07-01',periods=10*1440,freq='min')
    values=rng.normal(size=(len(stamps),9))+np.array([150,25,210,12,80,82,-20,125,198])
    data=pd.DataFrame(values,columns=FEATURES); data['stamp']=stamps
    windows=[QualifiedWindow('080',6,s.to_pydatetime(),(s+pd.Timedelta(minutes=1)).to_pydatetime(),'Off',STATE_CODE,
                             60,60,1,1,'PASS','',dict(zip(FEATURES,v)),WINDOW_VERSION) for s,v in zip(stamps,values)]
    cut=datetime(2026,7,8)
    candidate=fit_one_minute_candidate(windows,machine_number='080',module=6,
                                      calibration_start=datetime(2026,7,1),shadow_start=cut,shadow_end=datetime(2026,7,11))
    med,scale,threshold,_=fit_array(data[data.stamp<cut])
    assert dict(zip(FEATURES,med))==pytest.approx(candidate['medians'])
    assert dict(zip(FEATURES,scale))==pytest.approx(candidate['scales'])
    assert threshold==pytest.approx(candidate['threshold'])


def test_persistence_does_not_bridge_gap():
    data=pd.DataFrame({'stamp':pd.to_datetime(['2026-07-01 00:00','2026-07-01 00:01','2026-07-01 00:03','2026-07-01 00:04','2026-07-01 00:05'])})
    assert persistent_flags(data,np.ones(5,dtype=bool)).tolist()==[False,False,False,False,True]
