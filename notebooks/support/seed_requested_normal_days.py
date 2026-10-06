"""Owner-requested MX058/M1 source-only Normal fixture for 7–9 October.

No UI, Profile, approval or clock mutation. Synthetic provenance is durable.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import bindparam, text

from apps.api.app.config import get_settings
from apps.api.app.context_profiles import assess_context
from apps.api.app.context_reference import get_profile
from apps.api.app.context_scope import state_of
from apps.api.app.db import get_engine, get_source_engine
from apps.api.app.inference import get_machine_candidates
from apps.api.app.observed_context import ObservedMinute
from apps.api.app.qualified_calibration import IDENTIFIER
from apps.api.app.unified_events import fingerprint
from notebooks.support.context_followup_qa import snapshot
from notebooks.support.seed_local_normal_table import LEDGER, PROFILE, values

OUT = Path(__file__).resolve().parents[1] / 'outputs/normal_days_7_8_9_20261006'
START = datetime(2026, 10, 7)
END = datetime(2026, 10, 10)
VERSION = 'owner-requested-normal-source-days-v1'


def run():
    cfg = get_settings()
    if cfg.source_db_host not in {'127.0.0.1', 'localhost', '::1'} or cfg.analytics_db_host not in {'127.0.0.1', 'localhost', '::1'}:
        raise RuntimeError('Local fixture only')
    if cfg.source_db_port != cfg.analytics_db_port or cfg.detector_worker_enabled or cfg.detector_bridge_enabled or cfg.detector_alerts_enabled:
        raise RuntimeError('Require local SQL with worker/bridge/alerts disabled')
    names = [cfg.source_db_name, cfg.source_table, cfg.analytics_db_name, cfg.source_machine_column, cfg.source_timestamp_column, cfg.source_global_status_column]
    if not all(IDENTIFIER.fullmatch(n) for n in names):
        raise RuntimeError('Unsafe source mapping')
    model = get_profile(get_engine(), PROFILE)
    if model['machine_number'] != 'MX058' or model['module'] != 1:
        raise RuntimeError('Wrong Reference')
    accepted = set(model['reference_review']['accepted_regime_ids'])
    regime = max((r for r in model['regimes'] if r['coverage_supported'] and r['regime_id'] in accepted and state_of(r['context']) == 'OFF'), key=lambda r: (r['days'], r['minutes'], r['regime_id']))
    minutes = int((END - START).total_seconds() // 60)
    windows = [ObservedMinute('MX058', 1, START + timedelta(minutes=i), START + timedelta(minutes=i+1), 60, 1., 1., 'PASS', '', values(regime, i),
        {'compressor': {'run': 60}, 'module': {'on': 60}, 'busy': {'0': 60}, 'sv': {'off': 60}}, 'run|on|0|off', {'valve_mean': 100., 'valve_min': 100., 'valve_max': 100., 'valve_samples': 60}) for i in range(minutes)]
    points = assess_context(windows, [], model)
    flagged = sum(p['category'] != 'WITHIN_PROPOSED_STEADY' for p in points)
    if flagged:
        raise RuntimeError(f'Normal probe has {flagged} out-of-Reference minutes')
    source = f'`{cfg.source_db_name}`.`{cfg.source_table}`'
    ledger = f'`{cfg.analytics_db_name}`.`{LEDGER}`'
    mc, tc, sc = cfg.source_machine_column, cfg.source_timestamp_column, cfg.source_global_status_column
    params = {'aliases': get_machine_candidates('MX058'), 'start': START, 'end': END}
    overlap = text(f'SELECT COUNT(*) FROM {source} WHERE `{mc}` IN :aliases AND `{tc}`>=:start AND `{tc}`<:end').bindparams(bindparam('aliases', expanding=True))
    batch_id = fingerprint([VERSION, PROFILE, START, END, 58])
    receipt = {'version': VERSION, 'batch_id': batch_id, 'source_kind': 'MOCK', 'raw_status': 'Run', 'module_status': 'On', 'sv': 'Off', 'busy': '0',
        'machine_number': 'MX058', 'module': 1, 'source_table': source, 'start': START.isoformat(), 'end_exclusive': END.isoformat(), 'timezone': cfg.source_timezone,
        'expected_rows': minutes*60, 'cadence_seconds': 1, 'profile_id': PROFILE, 'regime_id': regime['regime_id'], 'seed': 58,
        'normal_probe_minutes': len(points), 'normal_probe_flagged_minutes': flagged, 'other_modules': 'NULL', 'approval_eligible': False,
        'future_dates_explicitly_requested_by_owner': True, 'application_clock_and_gates_unchanged': True, 'created_at': datetime.now(timezone.utc).isoformat()}
    OUT.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    columns = [mc, tc, sc, 'Hp_1st_1', 'Lp_1st_1', 'Hp_2nd_1', 'Lp_2nd_1', 'Valve_1', 'TempHi_1', 'TempLo_1', 'Status_1', 'Busy_1', 'SV_1']
    insert = text(f'INSERT INTO {source} (' + ','.join('`'+c+'`' for c in columns) + ') VALUES (' + ','.join(':v'+str(i) for i in range(len(columns))) + ')')
    other_null = ' AND '.join(f'`{name}_{m}` IS NULL' for m in range(2, 9) for name in ('Hp_1st', 'Lp_1st', 'Hp_2nd', 'Lp_2nd', 'Valve', 'TempHi', 'TempLo', 'Status', 'Busy', 'SV'))
    proof_query = text(f'SELECT DATE(`{tc}`) AS day,COUNT(*) AS rows_count,COUNT(DISTINCT `{tc}`) AS unique_seconds,MIN(id) AS first_id,MAX(id) AS last_id,MIN(`{tc}`) AS first_at,MAX(`{tc}`) AS last_at,SUM(`{sc}`="Run" AND Status_1="On" AND Busy_1="0" AND SV_1="Off" AND Valve_1=100) AS normal_state_rows,SUM({other_null}) AS other_modules_null FROM {source} WHERE `{mc}` IN :aliases AND `{tc}`>=:start AND `{tc}`<:end GROUP BY DATE(`{tc}`) ORDER BY day').bindparams(bindparam('aliases', expanding=True))
    with get_source_engine().connect() as conn:
        key = 'ht9046mx-local-history-v1-058'
        if conn.execute(text('SELECT GET_LOCK(:key,0)'), {'key': key}).scalar_one() != 1:
            raise RuntimeError('MX058 importer is busy')
        conn.commit()
        try:
            with conn.begin():
                saved = conn.execute(text(f'SELECT receipt_json FROM {ledger} WHERE batch_id=:id'), {'id': batch_id}).scalar_one_or_none()
                if saved:
                    receipt = json.loads(saved)
                else:
                    if conn.execute(overlap, params).scalar_one():
                        raise RuntimeError('Requested interval contains source rows; do not overwrite or duplicate')
                    for offset in range(0, minutes*60, 1000):
                        batch = []
                        for second in range(offset, min(minutes*60, offset+1000)):
                            v = values(regime, second//60)
                            row = ['HT9046MX-058', START+timedelta(seconds=second), 'Run', v['hp1'], v['lp1'], v['hp2'], v['lp2'], 100., v['temphi'], v['templo'], 'On', '0', 'Off']
                            batch.append({'v'+str(i): x for i, x in enumerate(row)})
                        conn.execute(insert, batch)
                daily = [dict(r) for r in conn.execute(proof_query, params).mappings()]
                if len(daily) != 3 or any(any(int(d[k]) != 86400 for k in ('rows_count', 'unique_seconds', 'normal_state_rows', 'other_modules_null')) for d in daily):
                    raise RuntimeError('Daily row/state verification failed')
                receipt.update(inserted_rows=sum(int(d['rows_count']) for d in daily), daily=daily)
                if not saved:
                    conn.execute(text(f'INSERT INTO {ledger} (batch_id,receipt_json,created_at) VALUES (:id,:receipt,:at)'),
                        {'id': batch_id, 'receipt': json.dumps(receipt, default=str), 'at': datetime.now(timezone.utc).replace(tzinfo=None)})
        finally:
            conn.execute(text('SELECT RELEASE_LOCK(:key)'), {'key': key})
            conn.commit()
    after = snapshot()
    receipt['profile_active_registry_unchanged'] = before == after
    for name, data in [('receipt', receipt), ('registry-before', before), ('registry-after', after)]:
        (OUT/(name+'.json')).write_text(json.dumps(data, default=str, indent=2), encoding='utf-8')
    if before != after:
        raise RuntimeError('Profile/Active registry changed concurrently; inspect committed receipt')
    return receipt


if __name__ == '__main__':
    print(json.dumps(run(), default=str, indent=2))
