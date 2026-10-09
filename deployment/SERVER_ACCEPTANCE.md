# Confirmed reader grants — 8 October 2026

Verified at **2026-10-08 09:45:32 Asia/Bangkok**. Owner confirmed `OPERATION_DB_USER=ht9046mx_reader`. Created the exact-IP account `ht9046mx_reader`@`10.195.17.69` with the existing .69 hostname account's unchanged authentication definition. Granted **SELECT only** on `ht9046mx_analytics.ht9046mx_dashboard_feed`, `ht9046mx_analytics.ht9046mx_dashboard_sequence`, `ht9046mx_analytics.ht9046mx_dashboard_identity`, and preserved `ht9046mx_iot.ht9046mx_readings` SELECT at the new matching IP. SHOW GRANTS and mysql.tables_priv independently confirm only these four table-level SELECT permissions plus USAGE; no writer privilege or wildcard host.

Original hostname account definition and grants match their private backup; the new account authentication matches the original exactly. Vacuum reader grants also match backup. No passwords, source data, finalization/checkpoints, feed state, Profiles/models, configuration, firewall or services changed. No service restart is required for these MySQL grants.

Feed count remains **0**, sequence rows **0**, identity rows **0**. Publication remains blocked by existing eligible-evidence/finalization conditions; no records were fabricated. MySQL authorization is verified on .73; authenticated SELECT, effective CURRENT_USER(), receiver restart and cursor preservation must now be tested from .69. Error 1044 resolution end-to-end is not claimed before that remote test.

Evidence: `deployment/server_setup/backup_20261008_one_way/reader_grants_after.json` and `reader_grants_verified.json`. The prior reader-blocker narrative below is historical and superseded by this verified grant checkpoint; the .69 commands remain applicable.

---

# Operation .73 one-way update — 8 October 2026

**PARTIAL:** deployed release `3df5d9c5523e91e7d160432114bcdc62f59d7f78` with existing Server fixes. Analytics/config/model/Profile backups, additive InnoDB export migrations, 265 API tests, frontend build and supervised API/single detector restart/recovery passed. Profiles, Active/frozen models and original detector streams were preserved; reverse bridge disabled. Reader username/grants and actual publication remain blocked; boot persistence remains unverified.

Complete actual results, private backup locations, rollback and exact .69 checks: [ONE_WAY_SERVER_ACCEPTANCE_20261008.md](ONE_WAY_SERVER_ACCEPTANCE_20261008.md). Earlier bridge-connectivity instructions below are historical and superseded by the confirmed one-way topology.

---

# Operation Server setup — 7 October 2026

Status: **PARTIAL — working loopback Shadow rehearsal; persistent installation and LAN release pending.** This is actual Server evidence, not the earlier development-PC acceptance.

## Target and release

- Host: `th1pmdbdev1w`, IPv4 `10.195.17.73`, Windows Server 2022 (build 20348).
- Workspace: `C:\CompressorML_and_AutomaticCalibration_final-main`.
- Windows timezone: `SE Asia Standard Time`; MySQL local/UTC clocks differ by seven hours, consistent with Asia/Bangkok. NTP/boot behavior has not been certified.
- Original workspace was a GitHub ZIP without `.git`. All 488 entries in `RELEASE_SHA256.json` matched before setup, allowing Git newline normalization.
- Authenticated reference checkout: `runtime/release_git`, HEAD `0f6e83e8abf7515dee66f3a0651efde2f6f69889`. Git LFS install/pull/fsck passed. Eight pointers were replaced with their real objects; see `server_setup/lfs_restored.json`.
- Frozen ZIP SHA256: `dd132a8de13ef26b6822132821b8b842efa04d61f0662b022dcb7deb80e1b1c0`.
- Model store: `runtime/fleet-stable`; selected `fleet-stable-v1-586e67981fc6d695467f0d01`, **SHADOW**, revision 1, previous pointer empty. No prior target store was overwritten.

## Environment and preservation

Python 3.12.10 installation returned Windows policy error 1625. The existing Python 3.13.14 is used in the dedicated `.venv`; locked application requirements plus the MySQL RSA driver dependency are installed. Node 24.18.1 builds the frontend successfully through `npm.cmd`. Resolved Python dependencies are recorded in `server_setup/requirements.lock.txt`. Revalidate on Python 3.12 after approved platform installation if the handoff's exact Python version is required.

Before DDL, all 13 existing analytics tables / 64,569 rows were backed up in `server_setup/backup_20261007/analytics_before.sql`, with registry hashes and private prior root configuration beside it. Existing MySQL service, telemetry ingestion services and accounts were preserved. New private root configuration uses separate localhost accounts: source SELECT-only and analytics privileges confined to `ht9046mx_analytics`. Existing similarly named accounts were inspected and left unchanged. Passwords are not included in this report.

Process environment originally overrode the prepared file's passwords. Deployment entry points now explicitly load the workspace `.env`; API and Worker share it. The previous administrative credentials remain in the private backup, not in the runtime source account.

## Database and actual input

| Purpose | Address / schema | Access |
|---|---|---|
| Compressor source | `127.0.0.1:3306/ht9046mx_iot.ht9046mx_readings` | SELECT-only |
| Operation evidence | `127.0.0.1:3306/ht9046mx_analytics` | Dedicated analytics account |
| Isolated recovery QA | `127.0.0.1:3306/ht9046mx_setup_qa_20261007` | Derived QA evidence only |
| Dashboard bridge | `10.195.17.69:3306/predictive_maintenance` | TCP timeout; bridge disabled pending connectivity |

Source schema and composite machine/time indexes were checked. Native machine values are `017`, `024`, `041`, `058`, `080`, `081`; canonical MX aliases are handled by the existing reader. Input is wide observed-second rows, with original controller states, eight physical/control modules, declared psi and Asia/Bangkok. All observed controls are retained; no healthy labeling or baseline fitting occurred. Pressure basis/controller/service certification remains unresolved.

The successful first six-machine cycle scanned **7 Oct 2026 08:15:00–08:45:34.941958 Asia/Bangkok**, accepted **6,816 source rows** and wrote **968 module-minute records**, with zero initial quarantines and zero matching Active Profiles. The snapshots were sometimes 5–13 minutes behind the real Server clock. Subsequent Worker cycles quarantined late arrivals (296 rows in one recorded machine slice); missing/late data is uncertainty, not healthy equipment. Producer latency/finalization acceptance remains open; no clock or scoring threshold was changed to conceal it.

Additive registry/reference/cache/Context/Event/detector DDL was applied. Actual MySQL exposed a checkpoint above 130 KiB, which exceeded TEXT's 64 KiB capacity. `qualified_persistence.py` now uses MySQL LONGTEXT for checkpoints; `server_setup/mysql_checkpoint_capacity.sql` widened the existing detector column without discarding rows. The failed transaction did not advance the cursor; the next complete cycle succeeded.

## Verification

- Full API suite: **262 passed**, Python 3.13; final focused persistence/reference checks: **46 passed**.
- TypeScript/Vite production build passed. npm reported one high-severity dependency audit finding; dependency remediation was not applied during setup.
- Two historical immutable CSV files needed their original CRLF bytes to satisfy existing manifests; hashes now match exactly. Scoped `.gitattributes` rules preserve those bytes. No manifest check was weakened.
- A synthetic reference-review test fixture now isolates cache invalidation from the configured Server DB.
- MySQL QA used **1,775 real MX017 source rows / eight modules** for 7 Oct 08:10–08:40. Injected precommit failure preserved evidence/Event/cursor counts. Reconnecting/rebuilding the detector and repeating the identical source produced zero new evidence, receipts or Events. Committed totals: 232 module-minute records, 1,775 receipts, 49 Events. See `server_setup/mysql_recovery.json`; this proves reconnection/checkpoint reconstruction, not OS reboot behavior.
- API/frontend responds at **http://127.0.0.1:8000**. API restart through the temporary supervisor recovered successfully. SPA routes work; unknown API/assets return 404 rather than an HTML 200.
- Source inventory: 20 machines; actual cold request **65.905 s**. Warm cached concurrency: **60/60 HTTP 200**, ten clients, p95 **257.96 ms**, maximum 367.7 ms. This excludes browser rendering/cold source preparation; cold inventory performance remains a limitation.
- Legacy Profile/Active/Batch/Review hashes match the pre-setup backup: 15 Profiles, zero legacy Active, one Batch, zero Reviews. Context Active remains zero. See `server_setup/registry_after.json`.

## Services and remaining installation

API/frontend and one detector-only Worker currently run as **temporary hidden supervisors**, using rotating 10 MiB logs with five backups and restart backoff. File locks prevent duplicate supervisors. Windows Job Objects terminate children when a supervisor ends. These processes are verification helpers, **not installed boot-persistent services**. Runtime supervisor PIDs are in `runtime/server-logs/*-supervisor.pid`.

The native Windows Job Object child-cleanup check passed, and final loopback `/health` returned HTTP 200 after the supervisor restart. This does not replace the pending Scheduled Task/SYSTEM/boot checks.

Creating a Scheduled Task was attempted and returned **Access is denied**. Current Windows token is non-elevated. Prepared PowerShell scripts parse successfully, but registration/SYSTEM execution cannot be certified in this session.

In an **Administrator PowerShell on .73**, after reviewing this report:

```powershell
Set-Location C:\CompressorML_and_AutomaticCalibration_final-main
& .\deployment\server_setup\install_tasks.ps1
```

This hands over the recorded temporary supervisors and registers two new tasks, `HT9046MX-Operation-api` and `HT9046MX-Operation-worker`, running at startup under SYSTEM with restart and one-instance settings. Existing tasks are never overwritten automatically. Then verify task restart/boot, SYSTEM access to the venv/config/store, and event identities under actual ingestion. Supervisor stop/restart must be tested before declaring persistent acceptance.

LAN access remains pending an authenticated gateway and confirmed Reviewer/Approver Windows/AD identities/roles. No proxy was present on .73 and IIS administration requires elevation. Keep loopback binding until that layer is configured. The same-origin wrapper includes the built frontend, preserves `/api`, and can sit behind the approved reverse proxy. Browser manual multi-tab validation and actual LAN access have not been performed.

Dashboard .69 installation is not claimed. WinRM TCP is reachable but no remote authenticated administration was established. Fix .69 MySQL reachability and initialize its metadata before bridge migration; enable the bridge only after a real connection/grant test. This setup did not modify .69 or create optional health-score producers.

## Rollback and open gates

Use `server_setup/stop_tasks.ps1` in the appropriate elevated session to stop only the recorded Operation supervisor trees and disable the two installed tasks if present. Preserve telemetry, Profiles and derived history. Private prior config is in `backup_20261007/root.env.before`; retain the new private account values before restoring it. The original config enables an unreachable bridge, so restoration alone is not a verified runnable state.

The initial Fleet pointer had no previous package. To suspend this initial deployment, stop its Worker or disable Fleet/Worker in private config; do not invent a prior model. Future package rollback uses the actual preceding bundle and current revision CAS. Never restore a whole analytics dump over newer operational evidence without a separate reviewed recovery plan.

Outstanding: Administrator service registration and restart/boot checks; authenticated LAN gateway/roles; Dashboard/bridge connectivity; cold inventory/browser/source-load QA; ingestion lag/late arrivals; clock synchronization; actual labeled healthy/case/future evidence and verified contracts. Installation does not approve a Profile, certify Normal or emit live equipment alerts. Fleet Transition donor admission remains zero; unsupported regimes remain NOT_EVALUATED.
