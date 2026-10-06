from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import polars as pl
import pytest

from apps.api.app.observed_context import build_observed_minutes
from apps.api.app.qualified_windows import WindowPolicy
from notebooks.support.fleet_reference_study import TAGS, FEATURES, derive_polars, derive_day


@pytest.mark.parametrize('case', ['complete','coverage57','coverage56','duplicate','gap',
                                   'mixed_sv','missing_pressure','missing_valve','infinite_valve'])
def test_vector_adapter_matches_observed_builder_on_quality_and_valve_context(case):
    rows=[]
    for second in range(60):
        row={'stamp':datetime(2026,9,15)+timedelta(seconds=second),'Status':'run'}
        for module in range(1,9):
            row.update({f'{tag}_{module}':100.+i+second*.01 for i,tag in enumerate(TAGS.values())})
            row.update({f'Status_{module}':'on',f'Busy_{module}':'0',f'SV_{module}':'off'})
        rows.append(row)
    if case=='coverage57':rows=[r for i,r in enumerate(rows) if i not in (15,16,17)]
    if case=='coverage56':rows=rows[4:]
    if case=='duplicate':rows.insert(20,dict(rows[20]))
    if case=='gap':rows=[r for i,r in enumerate(rows) if i not in range(20,26)]
    if case=='mixed_sv':rows[30]['SV_1']='on'
    if case=='missing_pressure':rows[30]['Hp_1st_1']=None
    if case=='missing_valve':rows[30]['Valve_1']=None
    if case=='infinite_valve':rows[30]['Valve_1']=float('inf')
    raw=[{**r,'recorded_at':r['stamp'],'machine_number':'041'} for r in rows]
    observed=build_observed_minutes(raw,as_of=datetime(2026,9,15,0,2,tzinfo=ZoneInfo('Asia/Bangkok')),
                                    policy=WindowPolicy('Asia/Bangkok'),modules=(1,))[0]
    frame=pd.DataFrame(rows)
    for builder,input_frame in ((derive_day,frame),(derive_polars,pl.from_pandas(frame))):
        minutes,_=builder(input_frame,'041');actual=minutes[minutes.module.eq(1)].iloc[0]
        assert bool(actual.quality)==observed.measured
        assert actual.coverage==observed.coverage
        assert actual.gap==observed.maximum_observed_gap_seconds
        valve=observed.control['valve_mean']
        assert pd.isna(actual.valve) if valve is None else actual.valve==pytest.approx(valve)
        if observed.measured:
            for feature in FEATURES:assert actual[feature]==pytest.approx(observed.features[feature],abs=1e-10)
        else:assert np.isnan(actual[list(FEATURES)].to_numpy(dtype=float)).all()
        if case in ('mixed_sv','missing_valve','infinite_valve'):assert actual.context=='UNSUPPORTED'
        else:assert actual.context=='SV_OFF'


def test_invalid_valve_changes_never_have_usable_event_witness():
    rows=[]
    for i,valve in enumerate((10.,float('inf'),12.,None,14.,15.)):
        row={'stamp':datetime(2026,9,15)+timedelta(seconds=i),'Status':'run'}
        for module in range(1,9):
            row.update({f'{tag}_{module}':valve if tag=='Valve' else 100. for tag in TAGS.values()})
            row.update({f'Status_{module}':'on',f'Busy_{module}':'0',f'SV_{module}':'off'})
        rows.append(row)
    _,events=derive_polars(pl.from_pandas(pd.DataFrame(rows)),'041')
    changes=events[(events.module==1)&events.event_type.eq('VALVE_CHANGED')]
    assert changes.witness_usable.sum()==1
    assert changes[changes.witness_usable].iloc[0]['after']=='15.0'
