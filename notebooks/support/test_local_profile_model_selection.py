"""Local experiment contract checks; no SQL or profile activation."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from notebooks.support.local_profile_model_selection import (
    FEATURES, PROTOCOL, split_masks, relative_lags, fit_profiles, apply_thresholds,
    flag_results, score_models, train_models, raw_day,
)


def sample(days=14):
    rng=np.random.default_rng(13)
    stamp=pd.date_range('2026-08-04',periods=days*1440,freq='min')
    values=rng.normal(0,.04,(len(stamp),9))+np.array([150,25,210,12,80,82,-20,125,198])
    frame=pd.DataFrame(values,columns=FEATURES)
    frame['stamp']=stamp;frame['machine']='029';frame['module']=1;frame['eligible']=True
    return frame


def test_split_is_disjoint_and_future_cannot_fit():
    d=sample(36)
    p=json.loads(PROTOCOL.read_text())
    masks=split_masks(d.stamp,p)
    assert np.column_stack(list(masks.values())).sum(axis=1).max()==1
    a,_,_=fit_profiles(d,p)
    changed=d.copy(); changed.loc[masks['future'],FEATURES]=1e9
    b,_,_=fit_profiles(changed,p)
    assert a.keys()==b.keys()
    for key in a:
        np.testing.assert_array_equal(a[key]['median'],b[key]['median'])
        np.testing.assert_array_equal(a[key]['scale'],b[key]['scale'])
        assert a[key]['threshold']==b[key]['threshold']


@pytest.mark.parametrize('break_kind',['missing_minute','ineligible','module','machine'])
def test_causal_lags_reset_on_every_boundary(break_kind):
    d=sample().head(12).copy()
    if break_kind=='missing_minute':d=d.drop(index=4).reset_index(drop=True)
    elif break_kind=='ineligible':d.loc[4,'eligible']=False
    elif break_kind=='module':d.loc[4:,'module']=2
    else:d.loc[4:,'machine']='070'
    profiles={('029',1):dict(median=np.zeros(9),scale=np.ones(9),threshold=2,status='SCREENED_CANDIDATE_NOT_APPROVED'),
              ('029',2):dict(median=np.zeros(9),scale=np.ones(9),threshold=2,status='SCREENED_CANDIDATE_NOT_APPROVED'),
              ('070',1):dict(median=np.zeros(9),scale=np.ones(9),threshold=2,status='SCREENED_CANDIDATE_NOT_APPROVED')}
    out,cols=relative_lags(d,profiles,pd.Series(True,index=d.index))
    reset=5 if break_kind=='ineligible' else 4
    assert not out.loc[reset:reset+1,'matched'].any()
    assert pd.isna(out.loc[reset,'lag1_z_hp2'])
    assert out.loc[reset+2,'lag2_z_hp2']==out.loc[reset,'z_hp2']


def test_sparse_reference_abstains():
    p=json.loads(PROTOCOL.read_text())
    profiles,table,keep=fit_profiles(sample(4),p)
    assert not profiles
    assert table.status.tolist()==['INSUFFICIENT_FIT']
    assert not keep.any()


def test_threshold_does_not_look_at_future_and_insufficient_block_abstains():
    p=json.loads(PROTOCOL.read_text())
    d=sample(30);d['matched']=True;d['legacy_threshold']=2;d['self_score']=1.
    for lane in ['arx','dpca','iforest']:d[lane+'_score']=np.arange(len(d))/1e4
    a,t=apply_thresholds(d.copy(),p)
    changed=d.copy();changed.loc[split_masks(d.stamp,p)['future'],['self_score','arx_score','dpca_score','iforest_score']]=1e9
    _,u=apply_thresholds(changed,p)
    pd.testing.assert_frame_equal(t,u)
    _,short=apply_thresholds(d.head(14*1440).copy(),p)
    assert short.arx_threshold.isna().all()


def test_persistence_is_greater_equal_and_cannot_cross_gap():
    d=pd.DataFrame({'machine':['029']*5,'module':[1]*5,
                   'stamp':pd.to_datetime(['2026-08-26 00:00','2026-08-26 00:01','2026-08-26 00:03','2026-08-26 00:04','2026-08-26 00:05']),
                   'self_score':[2.]*5})
    for lane in ['self_legacy','self_separate','arx','dpca','iforest']:
        d[lane+'_threshold']=2
        if lane not in ['self_legacy','self_separate']:d[lane+'_score']=2
    out=flag_results(d)
    assert out.self_legacy_persistent.tolist()==[False,False,False,False,True]


def test_parquet_microsecond_precision_preserves_seconds_and_machine_identity(tmp_path):
    import polars as pl
    from notebooks.support.test_october_three_machine_calibration import source_frame
    raw,stamp=source_frame()
    raw['recorded_at']=stamp.astype('datetime64[us]');raw['machine_number']='029'
    path=tmp_path/'day.parquet';pl.from_pandas(raw).write_parquet(path)
    frame,times=raw_day(path,'029')
    assert str(times.dtype)=='datetime64[ns]'
    assert times.diff().dropna().dt.total_seconds().eq(1).all()
    pd.testing.assert_series_equal(times.reset_index(drop=True),stamp.rename('recorded_at'),check_names=True)
    with pytest.raises(ValueError,match='identity mismatch'):raw_day(path,'080')


def test_subsecond_source_rejected_instead_of_faked_coverage(tmp_path):
    import polars as pl
    from notebooks.support.test_october_three_machine_calibration import source_frame
    raw,stamp=source_frame()
    stamp.iloc[20]+=pd.Timedelta(microseconds=500)
    raw['recorded_at']=stamp;raw['machine_number']='029'
    path=tmp_path/'day.parquet';pl.from_pandas(raw).write_parquet(path)
    with pytest.raises(ValueError,match='whole-second'):raw_day(path,'029')
