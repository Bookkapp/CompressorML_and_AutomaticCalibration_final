"""Read-only acceptance snapshot; no cursor/sequence/Profile/model mutation."""
import hashlib
import json
import sys
from pathlib import Path
from .one_way_update import ROOT,BACKUP,admin,registry

def snapshot(label):
    conn=admin()
    result={}
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA='ht9046mx_analytics' AND TABLE_NAME LIKE 'ht9046mx_dashboard_%'")
        result['export_tables']=cursor.fetchall()
        assert len(result['export_tables'])==4 and all(r['ENGINE']=='InnoDB' for r in result['export_tables'])
        for name in ('sequence','identity'):
            cursor.execute('SELECT * FROM ht9046mx_dashboard_'+name)
            result[name]=cursor.fetchall()
        cursor.execute('SELECT COUNT(*) AS count,MIN(seq) AS first_seq,MAX(seq) AS last_seq,MAX(occurred_at) AS source_latest FROM ht9046mx_dashboard_feed')
        result['feed']=cursor.fetchone()
        cursor.execute('SELECT kind,COUNT(*) AS count FROM ht9046mx_dashboard_feed GROUP BY kind')
        result['kinds']=cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS invalid_shadow_status FROM ht9046mx_dashboard_feed WHERE kind='STATUS' AND (JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.status')) <> 'NOT_EVALUATED' OR JSON_EXTRACT(payload_json,'$.health_score') <> CAST('null' AS JSON))")
        result['status_check']=cursor.fetchone()
        cursor.execute('SELECT run_id,revision,source_cursor FROM ht9046mx_detector_stream ORDER BY run_id')
        result['detector_streams']=cursor.fetchall()
        cursor.execute('SELECT job_type,result_status,detail_json FROM ht9046mx_automation_run ORDER BY started_at DESC LIMIT 3')
        result['recent_jobs']=cursor.fetchall()
    result['registry']=registry(conn)
    before=json.loads((BACKUP/'before.json').read_text())['registry']
    result['registry_unchanged']=result['registry']==before
    assert result['registry_unchanged']
    result['model_pointer_sha256']=hashlib.sha256((ROOT/'runtime/fleet-stable/shadow.json').read_bytes()).hexdigest()
    result['model_pointer_unchanged']=(ROOT/'runtime/fleet-stable/shadow.json').read_bytes()==(BACKUP/'fleet-stable/shadow.json').read_bytes()
    assert result['model_pointer_unchanged']
    bundle='fleet-stable-v1-586e67981fc6d695467f0d01'
    frozen=ROOT/'runtime/fleet-stable'/bundle
    archived=BACKUP/'fleet-stable'/bundle
    result['frozen_files_unchanged']=all(hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((archived/p.relative_to(frozen)).read_bytes()).digest() for p in frozen.rglob('*') if p.is_file())
    assert result['frozen_files_unchanged']
    conn.close()
    (BACKUP/(label+'.json')).write_text(json.dumps(result,indent=2,default=str))
    summary={k:result[k] for k in ('export_tables','sequence','identity','feed','kinds','registry_unchanged','model_pointer_unchanged','frozen_files_unchanged')}
    summary['recent_jobs']=[dict(status=row['result_status'],bridge=json.loads(row['detail_json']).get('bridge'),
        machines=[{k:m.get(k) for k in ('mode','revision','accepted_rows','new_source_rows','quarantined_rows','windows_written','scan_end')}
                  for m in json.loads(row['detail_json']).get('machines',[])]) for row in result['recent_jobs'][:1]]
    print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__':snapshot(sys.argv[1])
