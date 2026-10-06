"""Fleet Shadow evidence adapters for the existing single event ledger.

The producer owns its transaction/checkpoint and calls append_events. HTTP GETs
never write events. Source-second SV/Valve commands keep using capture_events;
these derived phase/episode events supplement, rather than replace, them.
"""
from datetime import datetime, timedelta
from .unified_events import make_event
from .inference import clean_machine_code


def evidence_events(result, *, source_digest, source_namespace=None,verified_source_mapping=False,recorded_at=None,previous_point=None):
    rows=[]
    previous=(previous_point['assessment'],previous_point['phase'],previous_point['persistent_flag']) if previous_point else None
    previous_at=datetime.fromisoformat(previous_point['time']) if previous_point else None
    for point in result['points']:
        at=datetime.fromisoformat(point['time'])
        state=(point['assessment'],point['phase'],point['persistent_flag'])
        gap=previous_at is not None and at-previous_at!=timedelta(minutes=1)
        if state!=previous or gap:
            if point['assessment']=='DATA_QUALITY':
                family='DATA_QUALITY';kind='FLEET_ACQUISITION_REVIEW'
            elif point['persistent_flag'] and (not previous or not previous[2] or gap):
                family='ANOMALY';kind='FLEET_PERSISTENT_EVIDENCE'
            elif previous and previous[2]:
                family='ANOMALY';kind='FLEET_EVIDENCE_ENDED_OR_CENSORED'
            else:
                family='TRANSITION';kind='FLEET_OBSERVED_PHASE_CHANGED'
            rows.append(make_event(source_key={'source_digest':source_digest,'time':point['time'],'derived_state':state},
                machine=clean_machine_code(result['machine']),module=result['module'],occurred_at=point['time'],timezone_name='Asia/Bangkok',
                event_type=kind,family=family,mode='SHADOW',assessment=point['assessment'],run_id=result['bundle_id'],
                policy_version='fleet-stable-shadow-inference-v1',recorded_at=recorded_at,
                details={**point,'bundle_id':result['bundle_id'],'source_digest':source_digest,'gap_before':gap,
                         'source_namespace':source_namespace,'source_mapping_status':'VERIFIED_SQL_SOURCE' if verified_source_mapping and source_namespace else 'UNVERIFIED',
                         'claim':'SHADOW_EVIDENCE_NOT_FAULT_DIAGNOSIS'}))
        previous=state;previous_at=at
    return rows
