import json
from datetime import timedelta
import pytest
from apps.api.app.qualified_archive import export_episode, verify_export, retention_inventory
from apps.api.tests.test_qualified_detector import profiles, raw, detector
from apps.api.tests.test_qualified_stream import clock, START


def test_export_is_immutable_verified_and_not_a_label(detector,tmp_path):
    p=profiles(); run=detector.initialize('MX080',(6,),p)
    detector.cycle(run,raw(range(300),shifted=True),as_of=clock(300),profiles=p)
    episode=detector.store.episode_summaries(run)[0]
    result=export_episode(detector.store,run,episode['episode_id'],tmp_path)
    verified=verify_export(result['folder'])
    assert result['raw_rows']>0 and result['database_deletions']==0
    assert not verified['coverage_verified']
    with pytest.raises(FileExistsError): export_episode(detector.store,run,episode['episode_id'],tmp_path)
    manifest=json.loads((tmp_path/f"episode-{episode['episode_id']}"/'manifest.json').read_text())
    assert manifest['label_status']=='UNREVIEWED' and manifest['cause_status']=='UNKNOWN'
    inventory=retention_inventory(detector.store,run,now=START+timedelta(days=31))
    assert inventory['raw_rows_outside_detector_episode_ranges']==0
    assert inventory['purge_enabled'] is False
