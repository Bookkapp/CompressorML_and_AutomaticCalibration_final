from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apps.api.app.context_profiles import assess_context, fit_context_candidate
from apps.api.app.context_scope import validation_receipt
from apps.api.app.observed_context import build_observed_minutes
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows
from apps.api.app.context_followup import result_provenance
from apps.api.tests.test_context_profiles import minute, reference


def rows():
    return [dict(machine_number='MX058',recorded_at=datetime(2026,10,6,8,5)+timedelta(seconds=i),
        Status='MOCK_NORMAL',Status_1='On',Busy_1='0',SV_1='Off',Hp_1st_1=190.,Lp_1st_1=15.,
        Hp_2nd_1=200.,Lp_2nd_1=5.,Valve_1=100.,TempHi_1=60.,TempLo_1=-65.) for i in range(60)]


def test_mock_raw_is_visible_but_never_legacy_fit_eligible():
    policy=WindowPolicy(source_timezone='Asia/Bangkok')
    at=datetime(2026,10,6,8,7,tzinfo=ZoneInfo('Asia/Bangkok'))
    observed=build_observed_minutes(rows(),as_of=at,policy=policy,modules=[1])
    qualified=build_completed_windows(rows(),as_of=at,policy=policy,modules=[1])
    assert observed[0].features['hp2']==200 and observed[0].reason=='MOCK_SOURCE_DATA'
    assert observed[0].state_counts['compressor']=={'mock_normal':60}
    assert not qualified[0].eligible and qualified[0].reason=='COMPRESSOR_NOT_STABLE_RUN'


def test_mock_cannot_vote_or_change_fitted_reference_and_mixed_receipt_is_blocked():
    start=datetime(2026,9,8)
    ref=reference()
    original=fit_context_candidate(ref,[],machine='MX017',module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    fake=replace(minute(start-timedelta(minutes=1),9000),context_key='mock_normal|on|0|off',
        state_counts={'compressor':{'mock_normal':60}},reason='MOCK_SOURCE_DATA')
    fitted=fit_context_candidate(ref+[fake],[],machine='MX017',module=1,shadow_start=start,shadow_end=start+timedelta(days=3))
    assert original['regimes']==fitted['regimes'] and original['stability_scale']==fitted['stability_scale']
    normal=assess_context([minute(start)],[],deepcopy(original))
    mock=assess_context([replace(fake,window_start=start+timedelta(minutes=1),window_end=start+timedelta(minutes=2))],[],deepcopy(original))
    assert mock[0]['category']=='MOCK_DATA' and not mock[0]['model_evaluated']
    assert mock[0]['features']['hp2']==9000 and mock[0]['steady_score'] is None
    receipt=validation_receipt(normal+mock,original)
    assert receipt['source_kind']=='MOCK' and receipt['approval_eligible'] is False and receipt['mock_minutes']==1
    assert 'source_kind' not in validation_receipt(normal,original)


def test_saved_interim_mock_provenance_survives_a_read_without_mutating_receipt():
    saved={'source_kind':'OBSERVED_SOURCE','approval_eligible':False,'daily':[{'categories':{'MOCK_DATA':254}}]}
    shown=result_provenance(saved)
    assert shown['source_kind']=='MOCK' and shown['approval_eligible'] is False
    assert saved['source_kind']=='OBSERVED_SOURCE'
    actual={'source_kind':'OBSERVED_SOURCE','daily':[{'categories':{'WITHIN_PROPOSED_STEADY':60}}]}
    assert result_provenance(actual)==actual
