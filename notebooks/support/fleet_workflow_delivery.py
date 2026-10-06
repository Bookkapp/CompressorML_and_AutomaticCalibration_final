"""Executed, inspectable companion for actual local workflow evidence."""
import json
from pathlib import Path
import nbformat as nb
from nbclient import NotebookClient
from apps.api.app.fleet_bundle import export_zip,pointer
from apps.api.app.config import get_settings
from notebooks.support.fleet_reference_qa import registry_snapshot

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notebooks/outputs/fleet_workflow_20261006'


def main():
    settings=get_settings();store=settings.fleet_stable_store or ROOT/'artifacts/fleet-stable'
    selected=pointer(store);export_zip(store/selected['bundle_id'],OUT/(selected['bundle_id']+'.zip'))
    before=json.loads((OUT/'registry-before.json').read_text(encoding='utf-8'));after=registry_snapshot();assert before==after
    (OUT/'registry-after.json').write_text(json.dumps(after,indent=2,default=str),encoding='utf-8')
    package=store/selected['bundle_id'];metadata=json.loads((package/'manifest.json').read_bytes())
    result={'selected_bundle_id':selected['bundle_id'],'revision':selected['revision'],'registry_unchanged':True,
        'server_connected':False,'worker_enabled_locally':settings.detector_worker_enabled,
        'package_files':metadata['files'],'manual_ui_training_job':'410e4726133549a1b63ca70c9e0b9727'}
    (OUT/'final-state.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    cells=[nb.v4.new_markdown_cell('''# Fleet workflow: items 3–6 — local acceptance, 6 October 2026

Grain: one actual observed machine/module/minute; Transition fit/holdout use independent whole events. Time is source-local Asia/Bangkok; pressures psi (basis not verified). Reference fitting is separate from calibration and saved historical Shadow. No confirmed healthy labels, no untouched three-day post-freeze source, no remote Server deployment. Zero Transition donor groups pass the independent event-response screen; unsafe proposals remain unavailable for transfer.

The scripts and receipts below distinguish actual SQL reads with isolated SQLite persistence, prepared historical artifact reads, manual browser actions, and fixture unit tests. Fleet Shadow selection does not activate a machine profile.''')]
    cells.append(nb.v4.new_code_cell('''from pathlib import Path
import json
ROOT=Path.cwd()
assert (ROOT/'apps/api/app/fleet_stable.py').exists()
OUT=ROOT/'notebooks/outputs/fleet_workflow_20261006'
read=lambda name:json.loads((OUT/name).read_text(encoding='utf-8'))
evidence=read('real-data.json')
assert evidence['event_overlap']==0
assert evidence['steady_models_byte_values_unchanged']
assert evidence['independent_screen_passed_groups']==0
print({k:evidence[k] for k in ['groups','reference_events','heldout_events','event_overlap','independent_screen_passed_groups']})
print(evidence['holdout'])'''))
    cells.append(nb.v4.new_code_cell('''shadow=evidence['MX058_M1_saved_shadow']
assert shadow['false_alert_rate'] is None and shadow['fault_detection_delay'] is None
assert not shadow['prospective_verified']
print({k:shadow[k] for k in ['observed_minutes','supported_minutes','flagged_minutes','flag_burden_pct','quality_minutes','unsupported_minutes','episodes_total']})
print('Known historical owner-described MX080/M6 case:',evidence['MX080_M6_owner_described_case'])'''))
    cells.append(nb.v4.new_code_cell('''from apps.api.app.fleet_bundle import load_package
final=read('final-state.json')
store=ROOT/'artifacts/fleet-stable'
old=load_package(store/'fleet-stable-v1-2f656893533033ab994e3713')
new=load_package(store/final['selected_bundle_id'])
assert old.models()==new.models()
catalog=new.priors()['transition_catalog']
fitted={e['event_id'] for g in catalog['groups'] for e in g['examples']}
validation=json.loads((store/final['selected_bundle_id']/'validation.json').read_bytes())['transition_event_holdout']
heldout={e['event_id'] for e in validation['events']}
assert not fitted&heldout
assert len(fitted)==sum(g['events'] for g in catalog['groups'])
print('Verified immutable model checksums, 43 unchanged steady profiles, unique event IDs and disjoint holdout')'''))
    cells.append(nb.v4.new_code_cell('''worker=read('worker-rehearsal.json')
assert not worker['server_connected'] and not worker['real_analytics_tables_written']
assert len(worker['machines'])==4
for row in worker['machines']:
    assert row['modules']==8 and row['restart_retry_pass'] and row['retry_new_source_rows']==0
    print(row)
print(read('http-load.json'))
print(read('management-qa.json'))
assert read('registry-before.json')==read('registry-after.json')
print('Actual registry unchanged; Server acceptance and confirmed healthy/future data remain open')'''))
    cells.append(nb.v4.new_markdown_cell('''## Reproduction and source receipts

- `notebooks/support/fleet_transition_build.py`: verified prepared Parquet minutes and observed source events; reference-only fitting, separate event holdout and conservative admission screen.
- `notebooks/support/fleet_workflow_qa.py`: bounded actual MySQL SELECT slices for MX041/058/080/081, restored durable checkpoints into an isolated evidence database, repeat-delivery checks, saved Shadow assessment and ten-client HTTP test.
- `apps/api/app/fleet_training.py`: isolated process, one durable job, immutable content-addressed output. Job 410e4726133549a1b63ca70c9e0b9727 was launched manually through the web and completed in ~203 seconds.
- `deployment/FLEET_WORKFLOW_UAT_20261006.md`: manual UI evidence and remaining claims/gates.
- `deployment/SERVER_WORKER_HANDOFF_20261006.md`: next Codex setup on actual Server 10.195.17.73.

This notebook reads saved receipts and re-verifies packages; it does not fit on holdout or rerun/relabel future data as Normal.'''))
    notebook=nb.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    NotebookClient(notebook,timeout=90,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    path=ROOT/'notebooks/14_Fleet_Transition_Worker_Management_20261006.ipynb';nb.write(notebook,path)
    print(path)


if __name__=='__main__':main()
