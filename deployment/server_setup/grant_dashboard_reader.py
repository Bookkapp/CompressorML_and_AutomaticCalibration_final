"""Grant only the confirmed Dashboard reader, preserving its existing password."""
import json
import sys
from .one_way_update import admin,BACKUP

def main(user):
    conn=admin()
    target='10.195.17.69'
    with conn.cursor() as cursor:
        cursor.execute('SELECT User,Host FROM mysql.user WHERE User=%s',(user,))
        accounts=cursor.fetchall()
        if not accounts:raise RuntimeError('Confirmed user does not exist; private configuration required')
        source=next((r for r in accounts if r['Host']==target),None)
        if source is None:
            candidates=[r for r in accounts if r['Host']=='th1pmappdev1w.ad.analog.com']
            if len(candidates)!=1:raise RuntimeError('Cannot identify existing .69 authentication account')
            source=candidates[0]
        cursor.execute('SHOW GRANTS FOR %s@%s',(user,source['Host']))
        before=[next(iter(r.values())) for r in cursor.fetchall()]
        if any(not r.startswith(('GRANT USAGE ', 'GRANT SELECT ')) for r in before):
            raise RuntimeError('Account is not a SELECT-only reader; no grants changed')
        (BACKUP/'reader_grants_before.json').write_text(json.dumps(dict(user=user,host=source['Host'],grants=before),indent=2))
        if source['Host']!=target:
            cursor.execute('SHOW CREATE USER %s@%s',(user,source['Host']))
            definition=next(iter(cursor.fetchone().values()))
            (BACKUP/'reader_authentication.private.sql').write_text(definition+';\n')
            quote_identifier=lambda value:'`'+value.replace('`','``')+'`'
            source_account=quote_identifier(user)+'@'+quote_identifier(source['Host'])
            target_account=quote_identifier(user)+'@'+quote_identifier(target)
            if source_account not in definition:raise RuntimeError('Unexpected SHOW CREATE USER quoting')
            cursor.execute(definition.replace(source_account,target_account,1))
            for grant in before:
                if grant.startswith('GRANT SELECT '):
                    # Preserve source permissions at the IP account which will now match .69.
                    old='`'+user.replace('`','``')+'`@`'+source['Host']+'`'
                    new='`'+user.replace('`','``')+'`@`'+target+'`'
                    if old not in grant:raise RuntimeError('Unexpected grant quoting')
                    cursor.execute(grant.replace(old,new))
        for table in ('feed','sequence','identity'):
            cursor.execute('GRANT SELECT ON ht9046mx_analytics.ht9046mx_dashboard_'+table+' TO %s@%s',(user,target))
        cursor.execute('SHOW GRANTS FOR %s@%s',(user,target))
        after=[next(iter(r.values())) for r in cursor.fetchall()]
        assert all(r.startswith(('GRANT USAGE ', 'GRANT SELECT ')) for r in after)
        result=dict(user=user,host=target,grants=after,existing_hostname_account_preserved=True,password_changed=False)
        (BACKUP/'reader_grants_after.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    conn.close()

if __name__=='__main__':
    try:
        main(sys.argv[1])
    except Exception as exc:
        # SQL authentication definitions must never enter a traceback or log.
        print(dict(error_type=type(exc).__name__,mysql_code=exc.args[0]
            if exc.args and isinstance(exc.args[0],int) else None))
        sys.exit(1)
