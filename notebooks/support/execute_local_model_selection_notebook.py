"""Execute the companion top-to-bottom, export HTML and record artifact QA."""
import json
from pathlib import Path
import time
import pandas as pd
import polars as pl

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from notebooks.support.local_profile_model_selection import OUTPUT, ROOT, sha, json_write
from notebooks.support.local_profile_model_selection_presentation import make_notebook
from notebooks.support.local_profile_model_selection_presentation import raw_case


def main():
    started=time.perf_counter()
    summary=json.loads((OUTPUT/'summary.json').read_text(encoding='utf-8'))
    coverage=pd.read_csv(OUTPUT/'machine_coverage.csv',dtype={'machine':str})
    coverage.rename(columns={'first':'first_calendar_minute','last':'last_calendar_minute'}).to_csv(OUTPUT/'machine_coverage.csv',index=False)
    burden=pd.read_csv(OUTPUT/'future_burden_by_context.csv',dtype={'machine':str})
    wide=burden.pivot(index=['machine','module'],columns='lane',values='rows')
    common=wide.index[wide.gt(0).all(axis=1)&wide.nunique(axis=1).eq(1)]
    common_summary=burden.set_index(['machine','module']).loc[common].reset_index().groupby('lane').agg(
        rows=('rows','sum'),persistent_flags=('persistent_flags','sum'),openings=('openings','sum')).reset_index()
    common_summary['persistent_pct']=100*common_summary.persistent_flags/common_summary.rows
    common_summary.to_csv(OUTPUT/'common_cohort_summary.csv',index=False)
    summary['common_cohort_contexts']=len(common)
    summary['common_cohort_minutes']=int(common_summary.rows.iloc[0])
    # Retain control-phase availability as descriptive evidence, not a normal label.
    future=pl.scan_parquet(OUTPUT/'matched_scores.parquet').filter(
        (pl.col('stamp')>=pd.Timestamp(summary['protocol']['diagnostic_future'][0]).to_pydatetime()) &
        (pl.col('stamp')<pd.Timestamp(summary['protocol']['diagnostic_future'][1]).to_pydatetime()))
    phase=future.with_columns(pl.when(pl.col('elapsed_known_seconds')!=pl.col('samples')).then(pl.lit('UNKNOWN_ONSET'))
        .when(pl.col('elapsed_min_seconds')<300).then(pl.lit('OBSERVED_ENTRY_UNDER_5M'))
        .when(pl.col('elapsed_min_seconds')<1200).then(pl.lit('OBSERVED_ENTRY_5_TO_20M'))
        .otherwise(pl.lit('OBSERVED_ENTRY_OVER_20M')).alias('phase'))
    phase.group_by('machine','module','phase').agg(pl.len().alias('rows'),
        pl.col('self_legacy_persistent').sum().alias('persistent_self'),
        pl.col('self_score').median().alias('median_self_score')).collect().sort(['machine','module','phase']).write_csv(OUTPUT/'phase_availability_diagnostic.csv')
    # Extend evidence checks without refitting or modifying the frozen score artifact.
    for name in ['matched_scores.parquet','additional_raw_inventory.csv','additional_cold_entry_events.parquet',
                 'machine_coverage.csv','common_cohort_summary.csv','phase_availability_diagnostic.csv']:
        summary['hashes'][name]=sha(OUTPUT/name)
    json_write(OUTPUT/'summary.json',summary)
    path=make_notebook()
    notebook=nbformat.read(path,as_version=4)
    client=NotebookClient(notebook,timeout=240,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}})
    client.execute()
    nbformat.validate(notebook)
    nbformat.write(notebook,path)
    html,_=HTMLExporter().from_notebook_node(notebook)
    (OUTPUT/'08L_executed_preview.html').write_text(html,encoding='utf-8')
    code=[c for c in notebook.cells if c.cell_type=='code']
    errors=[o for c in code for o in c.outputs if o.output_type=='error']
    images=sum('image/png' in o.get('data',{}) for c in code for o in c.outputs)
    if errors or not all(c.execution_count is not None for c in code) or images<8:
        raise AssertionError(f'Notebook incomplete: errors={len(errors)}, embedded PNGs={images}')
    # The raw-second MX080 panel is from the earlier forensic archive. Check it
    # against this trial's ZIP minute means before presenting them together.
    raw=raw_case(OUTPUT,'080')
    raw=raw.loc[raw.stamp.ge('2026-09-07 11:45')&raw.stamp.lt('2026-09-07 14:00')]
    fields=['hp1','lp1','hp2','lp2','valve','temphi','templo']
    means=raw.groupby(raw.stamp.dt.floor('min'))[fields].mean()
    cached=pd.read_parquet(ROOT/'notebooks/outputs/october_three_machine_calibration_v1/minutes/080_2026-09-07.parquet')
    cached=cached.loc[cached.module.eq(6)&cached.eligible].set_index('stamp')
    common=means.index.intersection(cached.index)
    delta=(means.loc[common]-cached.loc[common,fields]).abs().to_numpy().max()
    if delta>1e-8:raise AssertionError('Raw case / ZIP plotted minute provenance mismatch')
    qa=dict(code_cells=len(code),all_executed=True,errors=len(errors),embedded_pngs=images,
            executed_seconds=time.perf_counter()-started,notebook_sha256=sha(path),
            summary_sha256=sha(OUTPUT/'summary.json'),manual_visual_review='PENDING',
            runtime_not_changed=True,profile_activation=False,db_writes=False,server_access=False,
            mx080_plot_cross_source_complete_minutes=len(common),mx080_plot_max_abs_mean_difference=float(delta),
            raw_mx080_forensic_sha256=sha(ROOT/'notebooks/outputs/mx080_module6_forensics_v1/module6_one_second_unique.parquet'),
            raw_mx057_case_sha256=sha(OUTPUT/'raw_cases/MX057_M1_20260829.parquet'))
    json_write(OUTPUT/'notebook_qa.json',qa)
    print(json.dumps(qa,indent=2),flush=True)


if __name__=='__main__':main()
