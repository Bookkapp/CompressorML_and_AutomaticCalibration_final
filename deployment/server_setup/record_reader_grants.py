"""Record verified permissions without exposing private authentication data."""
import json
from .one_way_update import ROOT,BACKUP

def main():
    result=json.loads((BACKUP/'reader_grants_verified.json').read_text())
    assert result['credentials_match'] and result['original_authentication_definition_unchanged']
    header=('> **8 Oct 2026 — .73 Dashboard reader grants completed:** Owner confirmed `OPERATION_DB_USER=ht9046mx_reader`. '
        'Verified `ht9046mx_reader`@`10.195.17.69` has SELECT only on Dashboard feed/sequence/identity plus preserved compressor raw-source SELECT. '
        'Authentication definition unchanged; original hostname account and Vacuum grants unchanged; no wildcard host, password/config/service or finalization change. '
        'Feed remains empty; .69 authenticated connectivity/receiver restart/cursor checks remain pending. '
        'Evidence: `deployment/ONE_WAY_SERVER_ACCEPTANCE_20261008.md`; private redacted `reader_grants_verified.json`.\n\n')
    for name in ['AGENTS.md','SOT.md','Roadmap.md','Project.md','HANDOFF.md']:
        path=ROOT/name
        path.write_text(header+path.read_text(encoding='utf-8'),encoding='utf-8')
    section=('# Confirmed reader grants — 8 October 2026\n\n'
        f"Verified at **{result['verified_at_bangkok']} Asia/Bangkok**. Owner confirmed `OPERATION_DB_USER=ht9046mx_reader`. "
        'Created the exact-IP account `ht9046mx_reader`@`10.195.17.69` with the existing .69 hostname account\'s unchanged authentication definition. '
        'Granted **SELECT only** on `ht9046mx_analytics.ht9046mx_dashboard_feed`, `ht9046mx_analytics.ht9046mx_dashboard_sequence`, '
        '`ht9046mx_analytics.ht9046mx_dashboard_identity`, and preserved `ht9046mx_iot.ht9046mx_readings` SELECT at the new matching IP. '
        'SHOW GRANTS and mysql.tables_priv independently confirm only these four table-level SELECT permissions plus USAGE; no writer privilege or wildcard host.\n\n'
        'Original hostname account definition and grants match their private backup; the new account authentication matches the original exactly. '
        'Vacuum reader grants also match backup. No passwords, source data, finalization/checkpoints, feed state, Profiles/models, configuration, firewall or services changed. '
        'No service restart is required for these MySQL grants.\n\n'
        f"Feed count remains **{result['feed_count']}**, sequence rows **{len(result['sequence'])}**, identity rows **{len(result['identity'])}**. "
        'Publication remains blocked by existing eligible-evidence/finalization conditions; no records were fabricated. '
        'MySQL authorization is verified on .73; authenticated SELECT, effective CURRENT_USER(), receiver restart and cursor preservation must now be tested from .69. '
        'Error 1044 resolution end-to-end is not claimed before that remote test.\n\n'
        'Evidence: `deployment/server_setup/backup_20261008_one_way/reader_grants_after.json` and `reader_grants_verified.json`. '
        'The prior reader-blocker narrative below is historical and superseded by this verified grant checkpoint; the .69 commands remain applicable.\n\n---\n\n')
    for name in ['deployment/SERVER_ACCEPTANCE.md','deployment/ONE_WAY_SERVER_ACCEPTANCE_20261008.md']:
        path=ROOT/name
        path.write_text(section+path.read_text(encoding='utf-8'),encoding='utf-8')
    print('Updated Server acceptance and project checkpoints from verified grant evidence')

if __name__=='__main__':main()
