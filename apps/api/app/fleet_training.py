"""One bounded training child, independent of HTTP/server restarts."""
import argparse
import json
from pathlib import Path
import time
from .fleet_management import lease,save


def run(path):
    path=Path(path).resolve();job=json.loads(path.read_bytes());folder=path.parent
    def update(**values):
        job.update(values,updated_epoch=time.time());save(path,job)
    try:
        with lease(folder.parent/'worker.lock'):
            update(status='RUNNING',message='Verifying source checksums and fitting frozen steady references')
            from notebooks.support import fleet_stable_build as build
            build.configure_plan(job['plan']);build.SOURCE=Path(job['source_root']);build.OUT=folder/'output'
            result=build.run()
            update(message='Extracting observed Transition responses and evaluating independent event holdout')
            from notebooks.support.fleet_transition_build import enrich
            enriched=enrich(Path(result['packages']['cp2_candidate']),Path(job['source_root']),Path(job['store']))
            update(status='COMPLETED',message='New immutable candidate is ready for comparison; release is unchanged',
                   bundle_id=enriched['bundle_id'],elapsed_seconds=time.time()-job['created_epoch'])
    except Exception as exc:
        update(status='FAILED',message=f'{type(exc).__name__}: {str(exc)[:400]}')
        raise
    return job


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True)
    run(p.parse_args().job)
