"""Independent read-only verification of the confirmed restricted reader."""
import json
from .one_way_update import admin,BACKUP

def main():
    conn=admin()
    user='ht9046mx_reader'
    hosts=['th1pmappdev1w.ad.analog.com','10.195.17.69']
    with conn.cursor() as cursor:
        cursor.execute('SELECT Host,plugin,authentication_string,account_locked,password_expired FROM mysql.user WHERE User=%s',(user,))
        accounts={row['Host']:row for row in cursor.fetchall()}
        assert set(accounts)==set(hosts), 'Unexpected account host'
        credentials_match=all(accounts[hosts[0]][key]==accounts[hosts[1]][key]
            for key in ('plugin','authentication_string','account_locked','password_expired'))
        assert credentials_match
        cursor.execute('SHOW CREATE USER %s@%s',(user,hosts[0]))
        definition=next(iter(cursor.fetchone().values()))
        assert definition+';\n'==(BACKUP/'reader_authentication.private.sql').read_text()
        grants={}
        for host in hosts:
            cursor.execute('SHOW GRANTS FOR %s@%s',(user,host))
            grants[host]=[next(iter(row.values())) for row in cursor.fetchall()]
        original=json.loads((BACKUP/'existing_raw_reader_grants.json').read_text())[user]
        assert grants[hosts[0]]==original
        cursor.execute('SHOW GRANTS FOR %s@%s',('vacuum_pump_db_reader',hosts[0]))
        vacuum=[next(iter(row.values())) for row in cursor.fetchall()]
        assert vacuum==json.loads((BACKUP/'existing_raw_reader_grants.json').read_text())['vacuum_pump_db_reader']
        assert len(grants[hosts[1]])==5
        assert all(row.startswith(('GRANT USAGE ', 'GRANT SELECT ')) for row in grants[hosts[1]])
        cursor.execute('SELECT Db,Table_name,Table_priv FROM mysql.tables_priv WHERE User=%s AND Host=%s',(user,hosts[1]))
        table_grants=cursor.fetchall()
        expected={('ht9046mx_analytics','ht9046mx_dashboard_'+name) for name in ('feed','sequence','identity')}
        expected.add(('ht9046mx_iot','ht9046mx_readings'))
        assert {(row['Db'],row['Table_name']) for row in table_grants}==expected
        assert all(row['Table_priv'] in ('Select', {'Select'}) for row in table_grants)
        cursor.execute('SELECT COUNT(*) AS count FROM ht9046mx_dashboard_feed')
        feed_count=cursor.fetchone()['count']
        cursor.execute('SELECT * FROM ht9046mx_dashboard_sequence')
        sequence=cursor.fetchall()
        cursor.execute('SELECT * FROM ht9046mx_dashboard_identity')
        identity=cursor.fetchall()
        cursor.execute('SELECT NOW() AS server_time')
        stamp=str(cursor.fetchone()['server_time'])
        result=dict(verified_at_bangkok=stamp,user=user,host=hosts[1],grants=grants[hosts[1]],
            credentials_match=True,existing_hostname_grants_unchanged=True,
            original_authentication_definition_unchanged=True,vacuum_grants_unchanged=True,
            permissions='SELECT_ONLY_ON_EXACT_FOUR_TABLES',feed_count=feed_count,
            sequence=sequence,identity=identity,remote_authentication_test='PENDING_ON_DASHBOARD_69')
        (BACKUP/'reader_grants_verified.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    conn.close()

if __name__=='__main__':main()
