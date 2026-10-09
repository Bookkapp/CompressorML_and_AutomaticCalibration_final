"""Private on-host preservation and redacted evidence for the one-way update."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from dotenv import dotenv_values
import pymysql

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / 'deployment/server_setup/backup_20261008_one_way'

def admin():
    values = dotenv_values(ROOT / 'deployment/server_setup/backup_20261007/root.env.before')
    prefix = 'HT9046MX_ANALYTICS_DB_'
    return pymysql.connect(host=values[prefix+'HOST'], user=values[prefix+'USER'],
                           password=values[prefix+'PASSWORD'], database='ht9046mx_analytics',
                           cursorclass=pymysql.cursors.DictCursor)

def registry(conn):
    result = {}
    with conn.cursor() as cursor:
        cursor.execute('SHOW TABLES')
        names = [next(iter(row.values())) for row in cursor.fetchall()]
        for name in names:
            if any(part in name for part in ('profile', 'review', 'calibration_batch', 'context_active')):
                cursor.execute('SELECT * FROM `'+name+'`')
                rows = sorted(json.dumps(row, sort_keys=True, default=str) for row in cursor.fetchall())
                result[name] = dict(count=len(rows), sha256=hashlib.sha256(json.dumps(rows).encode()).hexdigest())
    return result

def inspect():
    conn=admin()
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME,ENGINE,TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA='ht9046mx_analytics'")
        tables=cursor.fetchall()
        cursor.execute("SELECT User,Host FROM mysql.user WHERE Host='10.195.17.69'")
        accounts=cursor.fetchall()
        cursor.execute("SELECT USER,HOST,DB,COMMAND,TIME,STATE FROM information_schema.PROCESSLIST")
        processes=cursor.fetchall()
        cursor.execute('SELECT @@default_storage_engine AS engine, NOW() AS local_clock, UTC_TIMESTAMP() AS utc_clock')
        clock=cursor.fetchone()
    data=dict(tables=tables,reader_candidates=accounts,processes=processes,clock=clock,registry=registry(conn))
    conn.close()
    return data

def backup():
    BACKUP.mkdir(exist_ok=False)
    shutil.copy2(ROOT/'.env', BACKUP/'root.env.before')
    shutil.copytree(ROOT/'deployment/server_setup', BACKUP/'service_configuration',
                    ignore=shutil.ignore_patterns('backup*', '__pycache__'))
    shutil.copytree(ROOT/'runtime/fleet-stable', BACKUP/'fleet-stable')
    revision=subprocess.check_output(['git','-C',str(ROOT/'runtime/release_git'),'rev-parse','HEAD'],text=True).strip()
    (BACKUP/'previous_revision.txt').write_text(revision)
    values=dotenv_values(ROOT/'deployment/server_setup/backup_20261007/root.env.before')
    p='HT9046MX_ANALYTICS_DB_'
    def quote(value): return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
    config=BACKUP/'mysqldump.private.cnf'
    config.write_text('[client]\nhost='+quote(values[p+'HOST'])+'\nuser='+quote(values[p+'USER'])+'\npassword='+quote(values[p+'PASSWORD'])+'\n')
    command=[r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe', '--defaults-extra-file='+str(config),
             '--single-transaction','--quick','--routines','--triggers','--events','--hex-blob','--no-tablespaces',
             '--result-file='+str(BACKUP/'analytics_before.sql'),'ht9046mx_analytics']
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    data=inspect()
    (BACKUP/'before.json').write_text(json.dumps(data,indent=2,default=str))
    print(json.dumps(dict(backup=str(BACKUP),revision=revision,dump_bytes=(BACKUP/'analytics_before.sql').stat().st_size,
                         tables=len(data['tables']),registry=data['registry'],reader_candidates=data['reader_candidates']),indent=2))

if __name__=='__main__':
    if sys.argv[1]=='backup': backup()
    elif sys.argv[1]=='inspect': print(json.dumps(inspect(),indent=2,default=str))
