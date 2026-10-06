"""Evidence export and retention inventory. This module never deletes rows.

Exports freeze run/profile/parameters and preserve incomplete-coverage notices.
Open Episodes have bounded available evidence, not an invented recovery end.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import and_, func, or_, select
from .qualified_persistence import canonical


def export_episode(store, run_id, episode_id, output_dir):
    item = next((x for x in store.episode_summaries(run_id) if x['episode_id']==episode_id), None)
    if item is None:
        raise ValueError('Episode not found')
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    folder = target / f'episode-{episode_id}'
    folder.mkdir(exist_ok=False)  # Never overwrite an earlier reviewed export.
    with store.engine.connect() as conn:
        contract = json.loads(conn.execute(select(store.runs.c.contract_json).where(
            store.runs.c.run_id==run_id)).scalar_one())
        left = datetime.fromisoformat(item['requested_evidence_start'])
        right = datetime.fromisoformat(item['requested_evidence_end'] or item['last_observed_at'])
        files=[]
        def write_rows(name, query, transform=lambda row:json.loads(row[0])):
            path=folder/name
            digest=hashlib.sha256(); count=0
            # SQL cursor streaming limits Python memory; source telemetry remains untouched.
            with path.open('xb') as handle:
                for row in conn.execution_options(stream_results=True).execute(query).yield_per(1000):
                    line=(canonical(transform(row))+'\n').encode('utf-8')
                    handle.write(line); digest.update(line); count+=1
            files.append({'file':name,'rows':count,'sha256':digest.hexdigest()})
        cursor=left
        while cursor<right:
            stop=min(cursor+timedelta(hours=6),right)
            raw=store.raw_evidence
            write_rows(f'raw-{len(files):03d}.jsonl',select(raw.c.payload_json).where(
                raw.c.run_id==run_id,raw.c.machine_number==item['machine_number'],
                raw.c.recorded_at>=cursor.isoformat(),raw.c.recorded_at<stop.isoformat())
                .order_by(raw.c.recorded_at,raw.c.batch_id,raw.c.row_index))
            cursor=stop
        e=store.evidence
        write_rows('windows.jsonl',select(e.c.payload_json).where(e.c.run_id==run_id,
            e.c.machine_number==item['machine_number'],e.c.module==item['module'],
            e.c.window_start>=left.isoformat(),e.c.window_start<right.isoformat()).order_by(e.c.window_start))
    manifest={'schema_version':1,'run_id':run_id,'episode':item,'contract':contract,'files':files,
        'exported_at':datetime.now(timezone.utc).isoformat(),'range_start':left.isoformat(),
        'range_end_exclusive':right.isoformat(),'coverage_verified':False,
        'label_status':'UNREVIEWED','cause_status':'UNKNOWN',
        'limitations':['Observed archive only; missing source seconds are not reconstructed.',
            'Notes and Episode recovery are not technician-confirmed fault/cause labels.',
            'Manual Dashboard reports and data-issue ledger must be joined separately before training.']}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'folder':str(folder),'files':len(files),'raw_rows':sum(x['rows'] for x in files if x['file'].startswith('raw-')),
            'coverage_verified':False,'database_deletions':0}


def verify_export(folder):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path=(folder/item['file']).resolve()
        if path.parent!=folder:
            raise ValueError('Export file escapes manifest directory')
        digest=hashlib.sha256(); count=0
        with path.open('rb') as handle:
            for line in handle:
                json.loads(line); digest.update(line); count+=1
        if digest.hexdigest()!=item['sha256'] or count!=item['rows']:
            raise ValueError('Export checksum or row count differs')
    return {'verified_files':len(manifest['files']),'coverage_verified':manifest['coverage_verified']}


def retention_inventory(store, run_id, *, now, hot_days=30):
    if now.tzinfo is not None or hot_days<7:
        raise ValueError('Source-local inventory clock and hot retention >=7 days required')
    cutoff=(now-timedelta(days=hot_days)).isoformat()
    protected=store.episode_summaries(run_id)
    raw=store.raw_evidence
    conditions=[raw.c.run_id==run_id,raw.c.recorded_at<cutoff]
    for episode in protected:
        match=and_(raw.c.machine_number==episode['machine_number'],
                   raw.c.recorded_at>=episode['requested_evidence_start'])
        if episode['requested_evidence_end']:
            match=and_(match,raw.c.recorded_at<episode['requested_evidence_end'])
        conditions.append(~match)
    with store.engine.connect() as conn:
        candidate=conn.execute(select(func.count()).select_from(raw).where(*conditions)).scalar_one()
    return {'run_id':run_id,'hot_days':hot_days,'cutoff_source_local':cutoff,
        'raw_rows_outside_detector_episode_ranges':candidate,'database_deletions':0,
        'purge_enabled':False,'manual_report_intervals_included':False,
        'next_gate':'Join Dashboard manual reports, verify exports and approve backup/retention before any purge.'}


def main():
    from .config import get_settings
    from .db import get_engine
    from .qualified_persistence import PersistentRehearsal
    parser=argparse.ArgumentParser(description='Export Episode evidence / dry-run retention inventory')
    parser.add_argument('--run',required=True); parser.add_argument('--episode')
    parser.add_argument('--output',default='artifacts/episode_exports'); parser.add_argument('--allow-remote',action='store_true')
    args=parser.parse_args(); settings=get_settings()
    if not args.allow_remote and settings.analytics_db_host not in {'localhost','127.0.0.1','::1'}:
        parser.error('Local export requires localhost analytics')
    store=PersistentRehearsal(get_engine(),table_prefix='ht9046mx_detector',mode='DETECTOR_SHADOW')
    if args.episode:
        result=export_episode(store,args.run,args.episode,args.output)
    else:
        from zoneinfo import ZoneInfo
        result=retention_inventory(store,args.run,now=datetime.now(ZoneInfo(settings.source_timezone)).replace(tzinfo=None))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
