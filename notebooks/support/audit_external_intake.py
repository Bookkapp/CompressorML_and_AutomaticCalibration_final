"""Independent manifest/partition reconciliation after full intake."""
from pathlib import Path
import json
import platform
import sys
import pandas as pd
import polars as pl
from external_dataset_intake import sha256


def audit(output):
    output=Path(output)
    summary=json.loads((output/'analysis_summary.json').read_text(encoding='utf-8'))
    manifest=pd.read_csv(output/'source_manifest.csv',dtype={'machine':str})
    counts=[]
    for _, row in manifest.dropna(subset=['canonical_partition']).iterrows():
        path=output/row.canonical_partition
        f=pl.read_parquet(path,columns=['recorded_at','machine_number'])
        assert f.height==int(row.novel_rows), path
        assert f['recorded_at'].n_unique()==f.height, path
        counts.append({'path':row.canonical_partition,'rows':f.height,'sha256':sha256(path)})
    total=sum(x['rows'] for x in counts)
    assert total==summary['novel_rows']
    assert manifest.groupby('sha256').machine.nunique().max()==1, 'Cross-machine digest copies require rerun with identity-aware deduplication'
    parsed=manifest[manifest.parsed_rows.notna()]
    # unique_rows includes all unique valid keys after conflicting-key quarantine.
    assert int(parsed.unique_rows.sum())==summary['novel_rows']+summary['overlap_rows']
    assert len(summary['errors'])==0, summary['errors']
    report={
        'status':'PASS_WITH_CAVEATS', 'canonical_partitions':len(counts), 'canonical_rows':total,
        'manifest_rows_reconcile':True, 'within_partition_unique_timestamps':True,
        'source_errors':0, 'canonical_checksums':counts,
        'python':sys.version,'platform':platform.platform(),'polars':pl.__version__,'pandas':pd.__version__,
        'cross_machine_identical_source_hashes':0,
        'limitations':summary['limits'],
    }
    (output/'partition_qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print({k:v for k,v in report.items() if k not in ['canonical_checksums','limitations','python','platform']})
    return report


if __name__=='__main__':
    audit(Path('notebooks/outputs/ht9046mx_external_intake_v2'))
