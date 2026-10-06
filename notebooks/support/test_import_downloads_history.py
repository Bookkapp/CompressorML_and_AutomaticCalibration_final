"""Importer boundaries/multiset reuse; synthetic rows are not healthy labels."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from notebooks.support.import_downloads_history import RAW_COLUMNS, NUMERIC, aliases, normalize, reuse_occurrences


def frame():
    values = {c:[1.0,1.0] if c in NUMERIC else ["0","0"] for c in RAW_COLUMNS}
    values["Time"] = ["00:00:00","00:00:00"]
    return pd.DataFrame(values), pd.Series(pd.to_datetime(["2026-07-01", "2026-07-01"]))


def test_normalize_keeps_source_duplicate_occurrences_and_states():
    f,t = frame(); f["Status_1"] = ["ChangeValve", "MValveHome"]
    out = normalize(f,t)
    assert len(out)==2 and out.recorded_at.duplicated().sum()==1
    assert out.Status_1.tolist()==["ChangeValve","MValveHome"]


def test_reuse_is_multiset_not_timestamp_deduplication():
    f,t=frame(); out=normalize(f,t)
    existing=[tuple(out.iloc[0])]
    new,reused,conflicts=reuse_occurrences(out,existing)
    assert len(new)==1 and reused==1 and conflicts==1
    assert out.equals(normalize(f,t))


def test_conflicting_existing_value_is_never_overwritten_or_discarded():
    f,t=frame(); out=normalize(f,t)
    existing=list(out.iloc[0]);existing[2]=99.
    new,reused,conflicts=reuse_occurrences(out,[tuple(existing)])
    assert len(new)==2 and reused==0 and conflicts==2


@pytest.mark.parametrize("kind", ["missing_column","invalid_time","infinite","text_control","too_long"])
def test_invalid_file_rejected_before_write(kind):
    f,t=frame()
    if kind=="missing_column": f=f.drop(columns="Hp_2nd_8")
    elif kind=="invalid_time": t.iloc[0]=pd.NaT
    elif kind=="infinite": f.loc[0,"Hp_2nd_1"]=np.inf
    elif kind=="text_control": f.loc[0,"Status"]="Run\tBAD"
    else: f.loc[0,"Status"]="X"*41
    with pytest.raises(ValueError):normalize(f,t)


def test_numeric_null_is_preserved_not_zero_filled():
    f,t=frame(); f.loc[0,"Hp_2nd_1"]=np.nan
    assert pd.isna(normalize(f,t).loc[0,"Hp_2nd_1"])


def test_machine_scope_rejects_mx080_and_unknown():
    assert "MX017" in aliases("017")
    for machine in ("080", "80", "MX080", "057"):
        with pytest.raises(ValueError):aliases(machine)
