from datetime import datetime,timedelta
import pytest
from sqlalchemy import create_engine,select
from apps.api.app.unified_events import metadata,dashboard_feed,dashboard_sequence,dashboard_latest
from apps.api.app.dashboard_export import publish,publish_points,status_for

def test_transaction_rollback_never_leaves_sequence_gap_and_retries_are_idempotent():
    engine=create_engine('sqlite://');metadata.create_all(engine)
    row=dict(event_id='a',kind='EVENT',machine_number='MX058',module=1,occurred_at='2026-10-07T10:00:00',payload={})
    with pytest.raises(RuntimeError):
        with engine.begin() as c:publish(c,[row]);raise RuntimeError('rollback')
    with engine.begin() as c:publish(c,[row]);publish(c,[row])
    with engine.connect() as c:
        assert c.execute(select(dashboard_feed.c.seq)).scalars().all()==[1]
        assert c.execute(select(dashboard_sequence.c.last_seq)).scalar()==1

def test_shadow_unknown_and_active_reference_are_distinct_and_heartbeat_bounded():
    engine=create_engine('sqlite://');metadata.create_all(engine)
    args=dict(profile_id='frozen',approved=True,mode='DETECTOR_LIVE',run_id='r',timezone_name='Asia/Bangkok')
    points=[dict(time=(datetime(2026,10,7,10)+timedelta(minutes=n)).isoformat(),category='WITHIN_PROPOSED_STEADY') for n in range(7)]
    with engine.begin() as c:publish_points(c,'MX058',1,points,**args)
    with engine.connect() as c:
        assert c.execute(select(dashboard_feed.c.seq)).scalars().all()==[1,2]
        assert c.execute(select(dashboard_latest.c.occurred_at)).scalar()==points[-1]['time']
    assert status_for(points[0],approved=True,mode='DETECTOR_SHADOW')=='NOT_EVALUATED'
    assert status_for(dict(category='STATE_GATE_EXCLUDED'),approved=True,mode='DETECTOR_LIVE')=='NOT_EVALUATED'
    assert status_for(dict(category='NEW_STEADY_LEVEL'),approved=True,mode='DETECTOR_LIVE')=='WARNING'

def test_bulk_export_duplicates_across_chunk_boundary_keep_contiguous_sequence():
    engine=create_engine('sqlite://');metadata.create_all(engine)
    rows=[dict(event_id=str(i),kind='EVENT',machine_number='MX058',module=1,
        occurred_at='2026-10-07T10:00:00',payload={}) for i in range(501)]
    with engine.begin() as c:publish(c,rows[:500]+[rows[0]]+rows[500:]);publish(c,rows)
    with engine.connect() as c:
        assert c.execute(select(dashboard_feed.c.seq).order_by(dashboard_feed.c.seq)).scalars().all()==list(range(1,502))
