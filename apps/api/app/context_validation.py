"""Descriptive frozen-profile validation; never invent Normal/fault labels."""
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo

FLAGS={'UNEXPECTED_TRANSITION','STEADY_DEVIATION','NEW_STEADY_LEVEL'}
SUPPORTED={'WITHIN_PROPOSED_STEADY','WITHIN_PROPOSED_TRANSITION'}|FLAGS


def report(model,start,end,load_day,*,source_timezone='Asia/Bangkok'):
    if not 0<(end-start).days<=31:raise ValueError('Select 1–31 days, end date is exclusive')
    if start.isoformat()<model['shadow_start'][:10] or end.isoformat()>model['shadow_end'][:10]:
        raise ValueError('Select saved Shadow days; prepare new observations first for later dates')
    counts=Counter();episodes=[];previous=None;episode=None;observed=0;coverage=0.
    def close():
        nonlocal episode
        if episode:episodes.append(episode);episode=None
    for offset in range((end-start).days):
        day=start+timedelta(days=offset)
        for p in load_day(day)['chart']:
            at=datetime.fromisoformat(p['time']);category=p['category']
            counts[category]+=1;observed+=1;coverage+=float(p.get('coverage',0))
            if previous is None or at-previous!=timedelta(minutes=1):close()
            if category in FLAGS:
                if episode is None:episode={'start':p['time'],'end':p['time'],'minutes':0,'categories':{},'first_evidence':p.get('main_evidence')}
                episode['end']=p['time'];episode['minutes']+=1
                episode['categories'][category]=episode['categories'].get(category,0)+1
            else:close()
            previous=at
    close()
    supported=sum(counts[k] for k in SUPPORTED);flagged=sum(counts[k] for k in FLAGS)
    excluded=counts['STATE_GATE_EXCLUDED'];quality=counts['DATA_UNAVAILABLE']
    unresolved=observed-supported-excluded-quality
    reviewed=model.get('reference_review',{}).get('at')
    earliest=None
    if reviewed:
        at=datetime.fromisoformat(reviewed.replace('Z','+00:00'))
        if at.tzinfo is None:at=at.replace(tzinfo=timezone.utc)
        earliest=(at.astimezone(ZoneInfo(source_timezone)).date()+timedelta(days=1)).isoformat()
    return {'profile_id':model['profile_id'],'start':start.isoformat(),'end':end.isoformat(),
        'mode':'SAVED_HISTORICAL_SHADOW','normal_labels':'UNREVIEWED','prospective_verified':False,
        'observed_minutes':observed,'expected_minutes':(end-start).days*1440,'supported_minutes':supported,
        'flagged_minutes':flagged,'flag_burden_pct':100*flagged/supported if supported else None,
        'excluded_state_minutes':excluded,'quality_minutes':quality,'unsupported_minutes':unresolved,
        'mean_observed_coverage':coverage/observed if observed else None,'categories':dict(counts),
        'episodes':episodes[:200],'episodes_total':len(episodes),'episodes_truncated':len(episodes)>200,
        'reference_reviewed_at':reviewed,'earliest_prospective_day':earliest,
        'false_alert_rate':None,'fault_detection_delay':None,
        'interpretation':'Flag burden is not false-alert accuracy. Confirmed Normal/fault intervals and untouched post-freeze data are required for those claims.'}
