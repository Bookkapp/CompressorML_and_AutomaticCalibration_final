"""Read real source, test rollback/retry in a separate QA schema; no source writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values, load_dotenv
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env', override=True)
from apps.api.app.config import get_settings
from apps.api.app.db import get_source_engine
from apps.api.app.fleet_bundle import current_snapshot
from apps.api.app.qualified_calibration import policy_from_settings
from apps.api.app.qualified_detector import DurableDetector, ObservedSourceReader


def main():
    settings = get_settings()
    original = dotenv_values(ROOT / 'deployment/server_setup/backup_20261007/root.env.before')
    prefix = 'HT9046MX_ANALYTICS_DB_'
    schema = 'ht9046mx_setup_qa_20261007'
    admin = pymysql.connect(host=original[prefix+'HOST'], user=original[prefix+'USER'],
                            password=original[prefix+'PASSWORD'])
    with admin.cursor() as cursor:
        cursor.execute('CREATE DATABASE IF NOT EXISTS '+schema)
        cursor.execute('GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON '+schema+'.* TO %s@%s',
                       (settings.analytics_db_user, 'localhost'))
    admin.close()
    url = URL.create('mysql+pymysql', host=settings.analytics_db_host,
                     username=settings.analytics_db_user, password=settings.analytics_db_password, database=schema)
    engine = create_engine(url, pool_pre_ping=True)
    _, fleet = current_snapshot(settings.fleet_stable_store)
    policy = policy_from_settings(settings)
    def detector():
        return DurableDetector(engine, policy, fleet=fleet, pressure_unit='psi', source_namespace='server-setup-isolated-qa')
    service = detector()
    service.create_tables()
    as_of = datetime(2026, 10, 7, 8, 40, tzinfo=ZoneInfo('Asia/Bangkok'))
    rows = ObservedSourceReader(get_source_engine(), settings).read('MX017', datetime(2026,10,7,8,10),
                                                                 as_of.replace(tzinfo=None), tuple(range(1,9)))
    run = service.initialize('MX017', tuple(range(1,9)), {})
    def counts():
        with engine.connect() as connection:
            result = {table: connection.execute(text('SELECT COUNT(*) FROM '+table)).scalar_one()
                      for table in ['ht9046mx_detector_evidence', 'ht9046mx_detector_source_receipt', 'ht9046mx_events']}
            result['cursor'] = connection.execute(text('SELECT source_cursor FROM ht9046mx_detector_stream WHERE run_id=:run'),
                                                 {'run': run}).scalar_one()
            return result
    before = counts()
    def fail():
        raise RuntimeError('Isolated precommit failure injection')
    try:
        service.cycle(run, rows, as_of=as_of, profiles={}, before_commit=fail)
    except RuntimeError as exc:
        if str(exc) != 'Isolated precommit failure injection':
            raise
    else:
        raise AssertionError('Failure hook was not reached')
    assert counts() == before, 'Rollback advanced evidence/cursor'
    first = service.cycle(run, rows, as_of=as_of, profiles={})
    committed = counts()
    engine.dispose()  # Reconnect and rebuild the worker entirely from SQL checkpoint.
    restarted = detector()
    restarted.initialize('MX017', tuple(range(1,9)), {})
    retry = restarted.cycle(run, rows, as_of=as_of, profiles={})
    assert counts() == committed, 'Repeated source overlap duplicated evidence/events/cursor'
    result = {'qa_schema': schema, 'source_rows': len(rows), 'modules': 8, 'rollback_pass': True,
              'restart_retry_pass': True, 'committed_counts': committed, 'first': first, 'retry': retry,
              'source_written': False, 'active_approved': False}
    (ROOT / 'deployment/server_setup/mysql_recovery.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    engine.dispose()


if __name__ == '__main__':
    main()
