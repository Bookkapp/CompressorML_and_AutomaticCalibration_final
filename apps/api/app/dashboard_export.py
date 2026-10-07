"""Transaction-owned export. Dashboard SELECTs this schema; no reverse connection."""
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, update
from .unified_events import dashboard_sequence as counter, dashboard_identity as identity, dashboard_feed as feed, dashboard_latest as latest, fingerprint, encode

def publish(conn, messages):
    if not messages:
        return
    # Unique insert plus current locking read safely initializes competing producers.
    if conn.dialect.name == 'mysql':
        from sqlalchemy.dialects.mysql import insert
        stmt=insert(counter).values(id=1,last_seq=0)
        conn.execute(stmt.on_duplicate_key_update(id=counter.c.id))
        stmt=insert(identity).values(id=1,stream_id=uuid.uuid4().hex)
        conn.execute(stmt.on_duplicate_key_update(id=identity.c.id))
    else:
        from sqlalchemy.dialects.sqlite import insert
        conn.execute(insert(counter).values(id=1,last_seq=0).on_conflict_do_nothing())
        conn.execute(insert(identity).values(id=1,stream_id=uuid.uuid4().hex).on_conflict_do_nothing())
    seq=conn.execute(select(counter.c.last_seq).where(counter.c.id==1).with_for_update()).scalar_one()
    # Bulk export adds two SQL calls per bounded chunk rather than per Event.
    # The same counter lock still protects allocation through the caller commit.
    for offset in range(0,len(messages),500):
        chunk=messages[offset:offset+500]
        existing=set(conn.execute(select(feed.c.event_id).where(
            feed.c.event_id.in_([item['event_id'] for item in chunk])).with_for_update()).scalars())
        values=[]
        for item in chunk:
            if item['event_id'] in existing:continue
            existing.add(item['event_id']);seq+=1
            values.append(dict(seq=seq,event_id=item['event_id'],kind=item['kind'],
                machine_number=item['machine_number'],module=item['module'],occurred_at=item['occurred_at'],
                payload_json=encode(item['payload'])))
        if values:conn.execute(feed.insert(),values)
    conn.execute(update(counter).where(counter.c.id==1).values(last_seq=seq))

def status_for(point, *, approved, mode):
    if not approved or mode != 'DETECTOR_LIVE':
        return 'NOT_EVALUATED'
    category=point['category']
    if category in {'WITHIN_PROPOSED_STEADY','WITHIN_PROPOSED_TRANSITION'}:
        return 'NORMAL'
    if category in {'STEADY_DEVIATION','UNEXPECTED_TRANSITION','NEW_STEADY_LEVEL'}:
        return 'WARNING'
    return 'NOT_EVALUATED'

def publish_points(conn, machine, module, points, *, profile_id, approved, mode, run_id, timezone_name):
    for p in points:
        at=p['time']
        identity=(latest.c.machine_number==machine,latest.c.module==module)
        old=conn.execute(select(latest).where(*identity).with_for_update()).mappings().first()
        if old and old['occurred_at']>=at:
            continue
        payload=dict(machine_number=machine,module=module,occurred_at=at,source_timezone=timezone_name,
            mode=mode,run_id=run_id,profile_id=profile_id,approved=bool(approved),
            status=status_for(p,approved=approved,mode=mode),category=p['category'],
            main_evidence=p.get('main_evidence'),health_score=None,
            claim='CONTEXT_STATUS_NO_SYNTHETIC_HEALTH_SCORE')
        key=fingerprint([payload[k] for k in ('mode','run_id','profile_id','approved','status','category')])
        export=not old or key!=old['state_key'] or datetime.fromisoformat(at)-datetime.fromisoformat(old['exported_at'])>=timedelta(minutes=5)
        if export:
            publish(conn,[dict(event_id=fingerprint(payload),kind='STATUS',machine_number=machine,module=module,
                               occurred_at=at,payload=payload)])
        values=dict(occurred_at=at,exported_at=at if export else old['exported_at'],state_key=key,payload_json=encode(payload))
        if old:conn.execute(latest.update().where(*identity).values(**values))
        else:conn.execute(latest.insert().values(machine_number=machine,module=module,**values))
