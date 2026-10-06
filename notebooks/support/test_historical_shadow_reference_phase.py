"""Leakage, causal phase, coverage and no-suppression regression tests."""
import json
from io import StringIO
import numpy as np
import pandas as pd

from notebooks.support.historical_shadow_reference_phase import (
    PROTOCOL, complete_day_bounds, trailing_dynamics, dynamic_limits,
    classify_phase, select_segment, fit_reference, FEATURES, persistent_flags,
)

P=json.loads(PROTOCOL.read_text(encoding='utf-8'))


def frame(days=14, perday=240):
    stamps=pd.DatetimeIndex(np.concatenate([pd.date_range('2026-08-01',periods=perday,freq='min').values
        + np.timedelta64(d,'D') for d in range(days)]))
    t=np.arange(len(stamps))
    values=np.tile(np.array([150.,20.,200.,10.,20.,70.,-20.,130.,190.]),(len(t),1))
    values+=.02*np.sin(t[:,None]/13)
    data=pd.DataFrame(values,columns=FEATURES);data['stamp']=stamps;data['eligible']=True
    return data


def test_complete_calendar_days_disjoint_excludes_today():
    a,b,c=complete_day_bounds('2026-10-01 14:59')
    assert a==pd.Timestamp('2026-08-31') and b==pd.Timestamp('2026-09-28') and c==pd.Timestamp('2026-10-01')
    assert (c-b).days==3 and (b-a).days==28


def test_timezone_is_preserved_at_local_midnight():
    a,b,c=complete_day_bounds(pd.Timestamp('2026-10-01 08:00',tz='Asia/Bangkok'))
    assert str(c.tz)=='Asia/Bangkok' and c.hour==0 and a<b<c


def test_trailing_slope_units():
    d=frame(1,20)
    d[FEATURES]=np.arange(20)[:,None]*np.ones((1,9))*2.
    s,v,c=trailing_dynamics(d)
    assert np.allclose(s[c],2.) and not c[:4].any()


def test_prefix_causality_dynamic_features():
    d=frame(2,200)
    full=trailing_dynamics(d);prefix=trailing_dynamics(d.iloc[:170])
    for a,b in zip(full,prefix):
        np.testing.assert_allclose(a[:170],b,equal_nan=True)


def test_invalid_and_gaps_restart_history():
    d=frame(1,30);d.loc[10,'eligible']=False
    _,_,c=trailing_dynamics(d)
    assert not c[10:15].any() and c[15]
    d.loc[20:,'stamp']+=pd.Timedelta(minutes=1)
    _,_,c=trailing_dynamics(d)
    assert not c[20:24].any() and c[24]


def test_limits_do_not_see_shadow():
    d=frame();fit=d.stamp.lt('2026-08-11').to_numpy()
    limits,*_=dynamic_limits(d,fit,P)
    d.loc[~fit,FEATURES]+=np.arange((~fit).sum())[:,None]*100.
    changed,*_=dynamic_limits(d,fit,P)
    for a,b in zip(limits,changed):np.testing.assert_array_equal(a,b)


def test_segment_choice_does_not_see_shadow():
    d=frame(21);fit=d.stamp.lt('2026-08-19').to_numpy()
    d.loc[d.stamp.ge('2026-08-10'),'hp2']+=100
    first,_,info=select_segment(d,fit,P)
    d.loc[~fit,'hp2']-=1000
    second,_,info2=select_segment(d,fit,P)
    assert info==info2 and info['supported_segments']==2
    np.testing.assert_array_equal(first,second)


def test_profile_minimum_retained_days():
    d=frame(6);profile,info=fit_reference(d,np.ones(len(d),bool),P)
    assert profile is None and not info['supported']


def test_fit_is_train_only():
    d=frame();fit=d.stamp.lt('2026-08-11').to_numpy()
    a,info=fit_reference(d,fit,P);d.loc[~fit,FEATURES]+=10000
    b,info2=fit_reference(d,fit,P)
    assert info==info2
    for x,y in zip(a,b):np.testing.assert_allclose(x,y)


def test_flat_abnormal_plateau_stays_detectable():
    d=frame();fit=d.stamp.lt('2026-08-11').to_numpy()
    profile,_=fit_reference(d,fit,P)
    d.loc[~fit,'hp2']=340
    limits,s,v,c=dynamic_limits(d,fit,P)
    phase,steady=classify_phase(d,limits,s,v,c,P)
    score=np.max(np.abs((d[FEATURES].to_numpy()-profile[0])/profile[1]),axis=1)
    flag=~fit & d.eligible & (score>=profile[2])
    assert steady[-1] and flag.iloc[-1] and phase[-1]=='STEADY_CANDIDATE'
    assert persistent_flags(d,flag.to_numpy())[-1]


def test_persistence_needs_adjacent_minutes():
    d=frame(1,10);d.loc[5:,'stamp']+=pd.Timedelta(minutes=1)
    flags=persistent_flags(d,np.ones(len(d),bool))
    assert flags[4] and not flags[5] and not flags[6] and flags[7]


def test_phase_never_claims_observed_start_from_file_beginning():
    d=frame(1,40);limits,s,v,c=dynamic_limits(d,np.ones(len(d),bool),{**P,'minimum_minutes':10})
    phase,_=classify_phase(d,limits,s,v,c,P)
    assert phase[0]=='UNKNOWN_HISTORY' and not any('START' in x for x in phase)


def test_threshold_exact_round_trip_preserves_greater_equal():
    thresholds=np.array([np.nextafter(8.,np.inf),1.2345678901234567,.12345678901234567])
    saved=pd.DataFrame({'threshold':thresholds}).to_csv(index=False)
    restored=pd.read_csv(StringIO(saved),float_precision='round_trip').threshold.to_numpy()
    np.testing.assert_array_equal(restored,thresholds)
    score=np.nextafter(thresholds,-np.inf)
    np.testing.assert_array_equal(score>=restored,score>=thresholds)
