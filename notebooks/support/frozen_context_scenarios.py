"""Owner-authorized synthetic scenarios against saved frozen local Profiles.

Source/Profile/Event SQL access is SELECT-only. Generated minutes/events and
receipts remain in memory or local QA files; none are approval evidence.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import gzip
import json
import math
import time
from zoneinfo import ZoneInfo

import numpy as np

from apps.api.app.config import get_settings
from apps.api.app.context_followup import source_head, summarize_day
from apps.api.app.context_profiles import assess_context
from apps.api.app.context_reference import get_profile
from apps.api.app.context_review import gate
from apps.api.app.context_scope import scope_of, state_of, validation_receipt
from apps.api.app.db import get_engine
from apps.api.app.observed_context import ObservedMinute, PHYSICAL
from apps.api.app.unified_events import fingerprint, make_event
from notebooks.support.context_followup_qa import snapshot

VERSION = 'frozen-context-scenarios-v1'
OUT = Path(__file__).resolve().parents[1] / 'outputs/context_scenarios_20261006'
PROFILE = '2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e'
OFF_ONLY_PROFILE = '65a3e0210722f339c00ee6fc8118e4f7c093e5f7a158a679150aec6526a61416'
SEED = 58
N_MINUTES = 4320
WINDOW = (420, 780)  # 07:00 to 13:00 on each virtual day.


def accepted(model):
    review = model['reference_review']
    ids = set(review['accepted_regime_ids'])
    scope = scope_of(model)
    return sorted([r for r in model['regimes'] if r['coverage_supported'] and r['regime_id'] in ids
        and (not scope or state_of(r['context']) in scope['included_sv_states'])],
        key=lambda r: (-r['days'], -r['minutes'], r['regime_id']))


def normal_minutes(model, settings, regime, seed=SEED):
    reviewed = datetime.fromisoformat(model['reference_review']['at']).astimezone(ZoneInfo(settings.source_timezone)).replace(tzinfo=None)
    start = max(reviewed, datetime.fromisoformat(model['shadow_end'])).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    sv = state_of(regime['context']).lower()
    rows = []
    for i in range(N_MINUTES):
        values = {f: float(regime['center'][j] + .04 * regime['scale'][j] *
            (math.sin(seed * .137 + i * .045 + j * .21) + .2 * math.sin(i * .19 + j)))
            for j, f in enumerate(PHYSICAL) if f not in {'dp1', 'dp2'}}
        values.update(dp1=values['hp1'] - values['lp1'], dp2=values['hp2'] - values['lp2'])
        at = start + timedelta(minutes=i)
        rows.append(ObservedMinute(model['machine_number'], model['module'], at, at + timedelta(minutes=1),
            60, 1., 1., 'PASS', 'SYNTHETIC_QA_NOT_SENSOR_DATA', values,
            {'compressor': {'run': 60}, 'module': {'on': 60}, 'busy': {'0': 60}, 'sv': {sv: 60}},
            f'run|on|0|{sv}', {'valve_mean': 100., 'valve_min': 100., 'valve_max': 100., 'valve_samples': 60}))
    return rows


def shifted(w, hp2=0., lp2=0.):
    values = {**w.features, 'hp2': w.features['hp2'] + hp2, 'lp2': w.features['lp2'] + lp2}
    values.update(dp1=values['hp1'] - values['lp1'], dp2=values['hp2'] - values['lp2'])
    return replace(w, features=values)


def state(w, sv='off', busy='0'):
    return replace(w, context_key=f'run|on|{busy}|{sv}', state_counts={
        **w.state_counts, 'sv': {sv: 60}, 'busy': {busy: 60}})


def event(model, settings, at, kind, before, after, case):
    return make_event(source_key=[VERSION, model['profile_id'], case, at.isoformat(), kind],
        machine=model['machine_number'], module=model['module'], occurred_at=at,
        timezone_name=settings.source_timezone, family='CONTROL', event_type=kind,
        mode='LOCAL_REHEARSAL', recorded_at=datetime(2026, 10, 6, tzinfo=ZoneInfo('UTC')),
        details={'before': before, 'after': after, 'witness_usable': True, 'source_kind': 'MOCK'})


def build_cases(model, settings, *, off_only=False):
    regimes = accepted(model)
    if not regimes:
        raise ValueError('No saved accepted Reference')
    base = normal_minutes(model, settings, regimes[0])
    cases = []
    def add(name, title, rows, controls=(), contract='normal', details=''):
        cases.append({'case': name, 'title': title, 'rows': rows, 'controls': list(controls),
            'contract': contract, 'details': details, 'regime_id': regimes[0]['regime_id']})
    if off_only:
        rows = [state(shifted(w, 60., 10.), 'on') if 420 <= i % 1440 < 480 else
            shifted(w, 60., 10.) if 480 <= i % 1440 < 540 else w for i, w in enumerate(base)]
        controls = [event(model, settings, base[d * 1440 + t].window_start - timedelta(seconds=30),
            'SV_CHANGED', before, after, 'excluded_on_return_outside')
            for d in range(3) for t, before, after in ((420, 'off', 'on'), (480, 'on', 'off'))]
        add('excluded_on_return_outside', 'Excluded SV ON; return OFF outside Reference', rows, controls,
            'excluded_return', 'Real saved OFF-only Profile; ON60min/day excluded; return OFF +60/+10psi for60min/day.')
        return cases
    for n, regime in enumerate(regimes, 1):
        rows = normal_minutes(model, settings, regime)
        add(f'normal_regime_{n}', f'Normal at accepted regime {n}', rows, details='Small fixed correlated variation, no control event.')
        cases[-1]['regime_id'] = regime['regime_id']
    add('spike_1m', 'Single minute HP2/LP2 spike', [shifted(w, 60., 10.) if i % 1440 == 420 else w for i, w in enumerate(base)],
        contract='spike', details='One-minute +60psi HP2/+10psi LP2 each day, no control event.')
    add('oscillation_10m', 'Ten-minute pressure oscillation', [shifted(w, 60. if i % 2 == 0 else -60., 10. if i % 2 == 0 else -10.)
        if 420 <= i % 1440 < 430 else w for i, w in enumerate(base)], contract='oscillation', details='Alternating +/−60psi HP2 and +/−10psi LP2 for10min/day.')
    for name, title, lp in [('hp2_plateau', 'HP2 raised and stable for six hours', 0.), ('cp2_plateau', 'HP2/LP2 raised and stable for six hours', 10.)]:
        add(name, title, [shifted(w, 60., lp) if WINDOW[0] <= i % 1440 < WINDOW[1] else w for i, w in enumerate(base)],
            contract='plateau', details=f'07:00–13:00 +60psi HP2/+{lp:g}psi LP2/day, no control event.')
    add('all_day_plateau', 'Three complete days at raised pressure', [shifted(w, 60., 10.) for w in base],
        contract='all_plateau', details='All4320minutes +60/+10psi; stable alone must not become accepted Normal.')
    add('slow_drift', 'Slow drift followed by raised plateau', [shifted(w, 60. * min(1., (i % 1440 - 420) / 120.),
        10. * min(1., (i % 1440 - 420) / 120.)) if 420 <= i % 1440 < 780 else w for i, w in enumerate(base)],
        contract='drift', details='Two-hour rise followed by four-hour raised plateau/day; no control event.')
    for response in (False, True):
        name = 'valve_delayed_response' if response else 'valve_no_physical_change'
        controls = [event(model, settings, base[d * 1440 + 420].window_start - timedelta(seconds=30),
            'VALVE_COMMAND_CHANGED', 100., 160., name) for d in range(3)]
        rows = [replace(w, control={**w.control, 'valve_mean': 160., 'valve_min': 160., 'valve_max': 160.})
            if i % 1440 >= 420 else w for i, w in enumerate(base)]
        if response:
            rows = [shifted(w, 60. * min(1., (i % 1440 - 430) / 20.), 10. * min(1., (i % 1440 - 430) / 20.))
                if 430 <= i % 1440 < 550 else w for i, w in enumerate(rows)]
        add(name, 'Valve command; delayed physical response' if response else 'Valve command; physical values stay Normal', rows, controls,
            'delayed' if response else 'valve_normal', 'Valve100→160 at06:59:30; response starts07:10. Saved MX058 accepts no Transition templates.' if response else
            'Valve100→160 with no pressure/thermal change; Valve is nonvoting context.')
    rows = [state(w, 'on') if 420 <= i % 1440 < 480 else w for i, w in enumerate(base)]
    controls = [event(model, settings, base[d * 1440 + t].window_start - timedelta(seconds=30), 'SV_CHANGED', before, after, 'on_missing_reference')
        for d in range(3) for t, before, after in ((420, 'off', 'on'), (480, 'on', 'off'))]
    add('on_missing_reference', 'Included SV ON without accepted Reference', rows, controls, 'missing_on', 'Real saved MX058 includes OFF/ON but accepts no ON regime.')
    add('source_gap', 'One hour missing observations', [w for i, w in enumerate(base) if not 420 <= i % 1440 < 480],
        contract='gap', details='60missingminutes/day; do not generate zeros or Normal for missing data.')
    add('sensor_quality', 'Bad sensor coverage for ten minutes', [replace(w, features=None, measurement_quality='DATA_QUALITY',
        reason='SYNTHETIC_LOW_COVERAGE', coverage=.2, sample_count=12) if 420 <= i % 1440 < 430 else w for i, w in enumerate(base)],
        contract='quality', details='10invalidminutes/day; no physical anomaly diagnosis.')
    add('manual_busy', 'Manual/Busy context for thirty minutes', [state(w, busy='1') if 420 <= i % 1440 < 450 else w for i, w in enumerate(base)],
        contract='manual', details='Busy1 for30min/day; physical values held fixed, unsupported controls remain unevaluated.')
    return cases


def check_contract(case, points):
    kind = case['contract']
    by_time = {p['time']: p for p in points}
    affected = [p for p in points if 420 <= (datetime.fromisoformat(p['time']).hour * 60 + datetime.fromisoformat(p['time']).minute) < 780]
    if kind in {'normal', 'valve_normal'}:
        assert all(p['category'] == 'WITHIN_PROPOSED_STEADY' for p in points)
    elif kind == 'spike':
        spikes = [p for p in points if p['time'][11:16] == '07:00']
        assert len(spikes) == 3 and all(p['category'] == 'STEADY_DEVIATION' for p in spikes)
    elif kind == 'oscillation':
        assert sum(p['category'] == 'STEADY_DEVIATION' for p in points) >= 30
    elif kind == 'plateau':
        assert len(affected) == 1080 and all(p['category'] in {'STEADY_DEVIATION', 'NEW_STEADY_LEVEL'} for p in affected)
        assert sum(p['category'] == 'NEW_STEADY_LEVEL' for p in affected) > 1000
    elif kind == 'all_plateau':
        assert all(p['category'] == 'NEW_STEADY_LEVEL' for p in points[4:])
    elif kind == 'drift':
        plateau = [p for p in affected if p['time'][11:16] >= '09:05']
        assert plateau and all(p['category'] == 'NEW_STEADY_LEVEL' for p in plateau)
    elif kind == 'delayed':
        assert all(p['category'] == 'WITHIN_PROPOSED_STEADY' for p in affected if p['time'][11:16] < '07:10')
        assert any(p['category'] == 'UNSUPPORTED_TRANSITION' for p in affected)
        assert all(p['category'] != 'WITHIN_PROPOSED_TRANSITION' for p in points)
    elif kind == 'missing_on':
        on = [p for p in affected if p['time'][11:16] < '08:00']
        assert len(on) == 180 and all(not p['model_evaluated'] and p['category'] not in {'WITHIN_PROPOSED_STEADY', 'WITHIN_PROPOSED_TRANSITION'} for p in on)
    elif kind == 'excluded_return':
        on = [p for p in affected if p['time'][11:16] < '08:00']
        assert len(on) == 180 and all(p['category'] == 'STATE_GATE_EXCLUDED' and not p['model_evaluated'] for p in on)
        returns = [p for p in points if p['time'][11:16] == '08:00']
        assert len(returns) == 3 and all(p['category'] == 'STEADY_DEVIATION' and p['model_evaluated'] for p in returns)
    elif kind == 'gap':
        assert len(points) == 4140 and not any(p['time'][11:16] >= '07:00' and p['time'][11:16] < '08:00' for p in points)
    elif kind == 'quality':
        assert sum(p['category'] == 'DATA_UNAVAILABLE' for p in points) == 30
    elif kind == 'manual':
        assert sum(p['category'] == 'UNSUPPORTED_CONTROL_CONTEXT' for p in points) == 90
    for p in points:
        f = p['features']
        if f is not None:
            assert math.isclose(f['dp1'], f['hp1'] - f['lp1'], abs_tol=1e-10)
            assert math.isclose(f['dp2'], f['hp2'] - f['lp2'], abs_tol=1e-10)
    assert len(by_time) == len(points)


def run_case(case, model, settings):
    before = fingerprint(model)
    began = time.perf_counter()
    points = assess_context(case['rows'], case['controls'], model)
    elapsed_ms = (time.perf_counter() - began) * 1000
    check_contract(case, points)
    assert before == fingerprint(model)
    receipt = {**validation_receipt(points, model), 'source_kind': 'MOCK', 'prospective': False, 'approval_eligible': False}
    copied = deepcopy(model)
    copied['future_validation'] = {**receipt, 'prospective': True}  # Exercise provenance even with forged bit, in memory only.
    assert 'MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE' in gate(copied, settings)['blockers']
    first = case['rows'][0].window_start.replace(hour=0, minute=0)
    daily = [summarize_day(points, (first + timedelta(days=d)).date(), closed=True,
        inspected_until=(first + timedelta(days=d + 1)).isoformat()) for d in range(3)]
    metrics_ok = receipt['supported_days'] == 3 and receipt['supported_minutes'] >= settings.profile_min_shadow_windows \
        and receipt['unresolved_minutes'] == 0 and receipt['flag_pct'] <= settings.profile_max_shadow_flag_pct
    summary = {k: case[k] for k in ('case', 'title', 'contract', 'details', 'regime_id')}
    summary.update(profile_id=model['profile_id'], machine=model['machine_number'], module=model['module'],
        categories=dict(Counter(p['category'] for p in points)), receipt=receipt,
        metrics_only_within_gate=metrics_ok, actual_readiness=gate(model, settings),
        missing_minutes=sum(d['missing_minutes'] for d in daily), daily=daily,
        control_events=len(case['controls']), scorer_ms=elapsed_ms, expectations_passed=True)
    return summary, points


def execute(out=OUT):
    settings = get_settings()
    before = snapshot()
    models = [get_profile(get_engine(), p) for p in (PROFILE, OFF_ONLY_PROFILE)]
    heads_before = {m['machine_number']: source_head(settings, m['machine_number']) for m in models}
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for model, off_only in zip(models, (False, True)):
        (out / f'profile-{model["machine_number"]}.json').write_text(json.dumps(model, indent=2), encoding='utf-8')
        for case in build_cases(model, settings, off_only=off_only):
            summary, points = run_case(case, model, settings)
            summaries.append(summary)
            payload = {'summary': summary, 'chart': points, 'controls': case['controls'], 'source_kind': 'MOCK'}
            (out / f'{case["case"]}.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
            print(f'{case["case"]}: {summary["categories"]}', flush=True)
    after = snapshot()
    assert before == after
    assert heads_before == {m['machine_number']: source_head(settings, m['machine_number']) for m in models}
    result = {'version': VERSION, 'seed': SEED, 'grain': 'SYNTHETIC_1_MINUTE_NOT_RAW_SECONDS',
        'source_kind': 'MOCK', 'approval_eligible': False, 'cases': summaries,
        'settings': {'timezone': settings.source_timezone, 'pressure_unit': 'psi', 'maximum_flag_pct': settings.profile_max_shadow_flag_pct,
            'minimum_total_minutes': settings.profile_min_shadow_windows},
        'registry_unchanged': True, 'registry_before': before, 'registry_after': after,
        'profile_hashes': {m['profile_id']: fingerprint(m) for m in models},
        'source_latest_before': {k: {n: v.isoformat() if v else None for n, v in h.items()} for k, h in heads_before.items()},
        'limitations': ['Synthetic software scenarios, not healthy/fault accuracy or real source/Raw/ingestion validation.',
            'No accepted real MX058/M1 Transition template: delayed-response case must remain unsupported.',
            'No source/Profile/review/Active/Event/job writes; virtual7–9October do not satisfy real elapsed days.',
            'Manual/unknown control and bad quality are separately unevaluated; metric-only pass is never approval.']}
    (out / 'summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    execute()
