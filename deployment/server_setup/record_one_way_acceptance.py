"""Update handoff checkpoints from the actual redacted Server evidence."""
from pathlib import Path
from .one_way_update import ROOT

def main():
    summary=('> **8 Oct 2026 — actual .73 one-way update, PARTIAL:** Release `3df5d9c5523e91e7d160432114bcdc62f59d7f78` merged from `0f6e83e`, preserving local Server fixes/config/model paths. '
             '878,687,010-byte consistent analytics backup verified; additive migrations and four InnoDB exports installed. '
             '265 API tests/build pass; existing API and exactly one detector-only scheduler restarted and recovered through their existing supervisors. '
             'Bridge false/DASHBOARD_PULL_MODE; Profiles/Active/frozen files and pointer unchanged. '
             'Actual installed Dashboard OPERATION_DB_USER unavailable; username requested, no grants/password changes, 1044 not resolved. '
             'Feed/sequence/identity empty through 09:36 Bangkok: source lag/finalization remains blocking real publication. '
             'Supervisors remain temporary; boot persistence unverified. Evidence: `deployment/ONE_WAY_SERVER_ACCEPTANCE_20261008.md`.\n\n')
    for name in ['SOT.md','Roadmap.md','Project.md','AGENTS.md','HANDOFF.md']:
        path=ROOT/name
        content=path.read_text(encoding='utf-8')
        if not content.startswith('> **8 Oct 2026 — actual .73 one-way update'):
            path.write_text(summary+content,encoding='utf-8')
    path=ROOT/'deployment/SERVER_ACCEPTANCE.md'
    content=path.read_text(encoding='utf-8')
    prefix=('# Operation .73 one-way update — 8 October 2026\n\n'
            '**PARTIAL:** deployed release `3df5d9c5523e91e7d160432114bcdc62f59d7f78` with existing Server fixes. '
            'Analytics/config/model/Profile backups, additive InnoDB export migrations, 265 API tests, frontend build and supervised API/single detector restart/recovery passed. '
            'Profiles, Active/frozen models and original detector streams were preserved; reverse bridge disabled. '
            'Reader username/grants and actual publication remain blocked; boot persistence remains unverified.\n\n'
            'Complete actual results, private backup locations, rollback and exact .69 checks: '
            '[ONE_WAY_SERVER_ACCEPTANCE_20261008.md](ONE_WAY_SERVER_ACCEPTANCE_20261008.md). '
            'Earlier bridge-connectivity instructions below are historical and superseded by the confirmed one-way topology.\n\n---\n\n')
    if not content.startswith('# Operation .73 one-way update — 8 October 2026'):
        path.write_text(prefix+content,encoding='utf-8')
    print('Updated Server acceptance and five project handoff checkpoints; no runtime state changed')

if __name__=='__main__':main()
