"""Read-only evidence audit after numerical replay; no production imports."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from notebooks.support.historical_shadow_reference_phase import OUTPUT, ROOT, sha, write_json, persistent_flags


def audit(output=OUTPUT):
    s=pd.read_parquet(output/'shadow_scores.parquet')
    p=pd.read_csv(output/'reference_readiness.csv',dtype={'machine':str},float_precision='round_trip')
    b=pd.read_csv(output/'shadow_burden.csv',dtype={'machine':str})
    keys=['experiment','machine','module','variant']
    frozen=json.loads((output/'offline_reference_profiles.json').read_text(encoding='utf-8'))
    lookup={tuple(x[k] for k in keys):x for x in frozen}
    assert not s.duplicated([*keys,'stamp']).any()
    for key,g in s.groupby(keys,sort=False):
        record=p.set_index(keys).loc[key];g=g.sort_values('stamp')
        assert (g.stamp >= pd.Timestamp(record.shadow_start)).all()
        assert (g.stamp < pd.Timestamp(record.shadow_end)).all()
        assert pd.Timestamp(record.fit_start)<pd.Timestamp(record.shadow_start)<pd.Timestamp(record.shadow_end)
        assert not g.loc[~g.eligible,'score'].notna().any()
        if record.supported:
            assert g.loc[g.eligible,'score'].notna().all()  # no phase suppresses valid scores
            np.testing.assert_array_equal(g.raw_flag.to_numpy(), (g.eligible & g.score.ge(record.threshold)).to_numpy())
            ref=lookup[key];valid=g.eligible.to_numpy(bool)
            from notebooks.support.historical_shadow_reference_phase import FEATURES
            recomputed=np.max(np.abs((g.loc[valid,FEATURES].to_numpy()-ref['median'])/ref['scale']),axis=1)
            np.testing.assert_array_equal(recomputed,g.loc[valid,'score'].to_numpy())
        else:
            assert not g.score.notna().any() and not g.raw_flag.any()
        np.testing.assert_array_equal(g.persistent.to_numpy(),persistent_flags(g,g.raw_flag.to_numpy()))
    # Aggregate CSV must agree with per-minute evidence, not just copied numbers.
    a=s.groupby(keys).agg(evaluated_minutes=('score','count'),qualified_minutes=('eligible','sum'),
                        persistent_minutes=('persistent','sum')).sort_index()
    expected=b.set_index(keys)[a.columns].sort_index()
    np.testing.assert_array_equal(a.to_numpy(),expected.to_numpy())
    receipt=json.loads((output/'input_receipt.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT/name)==info['sha256'] for name,info in receipt.items())
    # These bands were NOT used to tune or fit anything. They expose the initial warning limitation.
    bands=[('case_mx080',6,'2026-09-07 11:45','2026-09-07 12:20'),
           ('case_mx057',1,'2026-08-29 03:45','2026-08-29 04:06')]
    rows=[]
    for experiment,module,start,end in bands:
        for variant,g in s.loc[s.experiment.eq(experiment)&s.module.eq(module)&s.stamp.ge(start)&s.stamp.lt(end)].groupby('variant'):
            dominant=g.loc[g.persistent,'dominant'].value_counts()
            rows.append(dict(experiment=experiment,module=module,variant=variant,start=start,end_exclusive=end,
                qualified_minutes=int(g.eligible.sum()),evaluated_minutes=int(g.score.notna().sum()),
                persistent_minutes=int(g.persistent.sum()),dominant_counts=json.dumps(dominant.to_dict()),
                label='UNADJUDICATED_PRE_CASE_REVIEW_NOT_HEALTHY_NEGATIVE'))
    pd.DataFrame(rows).to_csv(output/'pre_case_review.csv',index=False)
    result=dict(minute_records=len(s),profile_comparisons=len(p),unique_minute_keys=True,
        disjoint_periods=True,all_supported_qualified_minutes_scored=True,persistence_exact=True,
        aggregate_csv_parity=True,input_hashes_verified=len(receipt),runtime_changed=False,active_changed=False,
        exact_frozen_reference_reload=True,
        db_writes=False,server_access=False)
    write_json(output/'evidence_audit.json',result);print(json.dumps(result,indent=2));return result


if __name__=='__main__':audit()
