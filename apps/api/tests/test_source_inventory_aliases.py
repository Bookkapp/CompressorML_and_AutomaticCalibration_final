from datetime import datetime
from apps.api.app.repository import _merge_source_aliases


def test_selector_combines_alias_counts_and_coverage_without_mutating_inputs():
    raw=[{'machine_number':'080','row_count':700,'record_count':700,
          'first_event':datetime(2026,7,2),'latest_recorded_at':datetime(2026,10,1)},
         {'machine_number':'MX080','row_count':8,'record_count':8,
          'first_event':datetime(2026,9,15),'latest_recorded_at':datetime(2026,9,21)},
         {'machine_number':'041','row_count':500,'record_count':500}]
    result=_merge_source_aliases(raw)
    assert [r['machine_number'] for r in result]==['MX041','MX080']
    assert result[1]['row_count']==result[1]['record_count']==708
    assert result[1]['first_event']==datetime(2026,7,2)
    assert result[1]['latest_recorded_at']==datetime(2026,10,1)
    assert raw[0]['machine_number']=='080' and raw[0]['row_count']==700
