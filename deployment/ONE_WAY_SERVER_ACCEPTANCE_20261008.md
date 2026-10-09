# Confirmed reader grants — 8 October 2026

Verified at **2026-10-08 09:45:32 Asia/Bangkok**. Owner confirmed `OPERATION_DB_USER=ht9046mx_reader`. Created the exact-IP account `ht9046mx_reader`@`10.195.17.69` with the existing .69 hostname account's unchanged authentication definition. Granted **SELECT only** on `ht9046mx_analytics.ht9046mx_dashboard_feed`, `ht9046mx_analytics.ht9046mx_dashboard_sequence`, `ht9046mx_analytics.ht9046mx_dashboard_identity`, and preserved `ht9046mx_iot.ht9046mx_readings` SELECT at the new matching IP. SHOW GRANTS and mysql.tables_priv independently confirm only these four table-level SELECT permissions plus USAGE; no writer privilege or wildcard host.

Original hostname account definition and grants match their private backup; the new account authentication matches the original exactly. Vacuum reader grants also match backup. No passwords, source data, finalization/checkpoints, feed state, Profiles/models, configuration, firewall or services changed. No service restart is required for these MySQL grants.

Feed count remains **0**, sequence rows **0**, identity rows **0**. Publication remains blocked by existing eligible-evidence/finalization conditions; no records were fabricated. MySQL authorization is verified on .73; authenticated SELECT, effective CURRENT_USER(), receiver restart and cursor preservation must now be tested from .69. Error 1044 resolution end-to-end is not claimed before that remote test.

Evidence: `deployment/server_setup/backup_20261008_one_way/reader_grants_after.json` and `reader_grants_verified.json`. The prior reader-blocker narrative below is historical and superseded by this verified grant checkpoint; the .69 commands remain applicable.

---

# Operation .73 one-way update — 8 October 2026

Status: **PARTIAL. Release, additive schemas, tests and supervised restarts pass. Reader grants and real feed publication remain blocked.**

## Actual installation and rollback

Host `th1pmdbdev1w`, Windows Server 2022, `10.195.17.73`; working directory `C:\CompressorML_and_AutomaticCalibration_final-main`. The root installation is a ZIP extraction, not a Git checkout. Its authenticated reference checkout is `runtime/release_git`.

Previous Git revision: `0f6e83e8abf7515dee66f3a0651efde2f6f69889`. Fetched and fast-forwarded to **`3df5d9c5523e91e7d160432114bcdc62f59d7f78`**, then merged the 17 changed non-env release files into the existing installation. Local documentation headers, Python dotenv loading, LONGTEXT checkpoint fix, test isolation, CRLF evidence and service helpers were preserved. Git LFS pull/fsck passed. No repository push was performed.

Preservation directory: `deployment/server_setup/backup_20261008_one_way/`:

- `analytics_before.sql`: consistent `--single-transaction` analytics-only dump including triggers/routines/events; 878,687,010 bytes. mysqldump succeeded, completion marker verified. SHA256 `46ff9b7ec6cd34a13d93cf04fa8c4f25322d422369430426c0eaf6a0c56f60fc`. No restore rehearsal was performed.
- `root.env.before`, service configuration copy, existing task XMLs, MySQL service/process inventory, original application files and previous revision.
- Complete `fleet-stable` copy, Profile/review/Active fingerprints in `before.json`, raw-reader grants and post-update snapshots.
- Private MySQL administrative configuration remains private; no passwords/authentication hashes are included in this report.

The dump completed before DDL. A separate post-dump inventory initially failed on a reserved SQL alias; the corrected read-only inventory was saved separately. This did not invalidate the successful dump.

Rollback code with the saved application files or the preceding checkout while retaining local Server fixes and current credentials. Keep `HT9046MX_DETECTOR_BRIDGE_ENABLED=false` under the current topology. Restart only the owned supervisors. Preserve the additive tables and all newer operational evidence. Do not restore the entire analytics dump over newer data or switch the frozen pointer as an ordinary code rollback.

## Configuration, migration and invariance

The existing private config already had `HT9046MX_DETECTOR_BRIDGE_ENABLED=false`; it remains false. All other parsed env values were checked unchanged. Worker code no longer imports/calls the reverse bridge. No connection to .69, bridge migration, firewall or unrelated service change was made.

Installed dependencies in the existing Python 3.13 venv using `apps/api/requirements.txt` plus the existing RSA-driver requirements, and ran npm ci. Executed the documented module entrypoints with the private dotenv loaded explicitly to prevent inherited environment overrides:

```text
python -m apps.api.app.context_migrate --allow-remote
python -m apps.api.app.qualified_detector --allow-remote --migrate-only
```

Both succeeded; detector migration reported zero source rows read and zero Profiles activated. All four export tables exist and use **InnoDB**: `ht9046mx_dashboard_feed`, `ht9046mx_dashboard_sequence`, `ht9046mx_dashboard_identity`, `ht9046mx_dashboard_latest`.

Before/after fingerprints agree: 15 legacy Profiles, 8 Context Profiles, zero legacy Active and zero Context Active; review/job/batch registries unchanged. All frozen bundle files and pointer bytes agree with backup. Selected bundle remains `fleet-stable-v1-586e67981fc6d695467f0d01`, Shadow revision 1. No training, approval, model/Active switch, source write, Health Score generation, feed reset or deletion occurred.

## Actual services and verification

The installed mechanism is still the existing hidden `deployment.server_setup.supervise api` and `supervise worker` helpers, not registered Operation Windows services/tasks. Existing unrelated telemetry tasks/MySQL80 were preserved. API uses one uvicorn worker on loopback 8000; detector uses `apps.api.app.worker --detector-only`, one scheduler. Windows venv launcher/underlying Python pairs are one process tree, not multiple schedulers.

- Full API suite: **265 passed**, 523 existing deprecation warnings, 149.54 seconds. Focused export suite: 3 passed.
- Frontend TypeScript/Vite build passed, 28.46 seconds; existing bundle-size warning and one high-severity npm audit finding remain. No broad dependency upgrade.
- Both supervisors restarted after tests/migrations. API `/health`: HTTP 200, `live_shadow`, `SHADOW_ONLY_NOT_AUTHORIZED`, `plc_write_path=false`.
- Controlled termination of each owned service child tree left its supervisor alive. Both relaunched after five seconds; recovered API returned HTTP 200.
- One actual detector scheduler confirmed. Duplicate supervisor invocation was rejected by Windows file locking before any second scheduler started (PermissionError/exit 1).
- Post-update six-machine cycles recorded `COMPLETED`, `DASHBOARD_PULL_MODE`, zero bridge writes and `DETECTOR_SHADOW`. Existing run IDs/cursors persisted; revisions advanced without resets.
- Boot/logout persistence remains **unverified and not installed**. This request reused the existing supervisor; it did not replace it with a new service architecture. Earlier elevated registration failure remains open.

## Real feed publication blocker

Through the observed 09:35 Bangkok cycle, feed count is **0**; sequence and producer-identity tables have **no rows**. They initialize transactionally on the first real export. No identity/sequence row was fabricated to make checks pass. Real publication, advancing sequences and producer identity persistence are therefore **not certified**.

The detector resumes its original durable watermark. In a sampled run, finalized cutoff was 09:29 while actual MX017 latest source time was 09:25. Existing cycles accept zero new rows/windows; previously unseen delayed source rows are quarantined `AFTER_FINALIZATION` under the unchanged policy. Example pre-update cycle quarantined 4,143 rows across six machines. This established source-lag/finalization issue prevents new Context/Event exports. Missing evidence remains NOT_EVALUATED. Fixing producer latency/finalization requires separate diagnosis; this integration update did not retune lateness, reset checkpoints, replay old data into production or invent current evidence.

## Reader grant blocker

No authenticated/local source for the **installed private .69 `.env`** is available in this session. The companion private Git release and its guide were read at `5bfa10a`, but packaged config is not proof of installed `OPERATION_DB_USER`. Owner was asked for the username only. **No grant or password/account change was applied.** MySQL 1044 is not claimed resolved.

Actual existing raw readers use host `th1pmappdev1w.ad.analog.com`: `ht9046mx_reader` has SELECT only on `ht9046mx_iot.ht9046mx_readings`; `vacuum_pump_db_reader` has SELECT only on `vacuum_pump_db.vacuum_pump_readings`. Both otherwise have USAGE only. No literal `10.195.17.69` account existed before this update. These accounts/grants were preserved. These observations do not prove the configured Operation receiver username.

After confirmation, `deployment/server_setup/grant_dashboard_reader.py` is prepared to create the literal-IP reader using the existing .69 hostname account's unchanged authentication definition, preserve its raw SELECT grants at the matching IP, and grant SELECT only on feed/sequence/identity. It refuses writer accounts and ambiguous/missing authentication. No wildcard host or analytics writer is used. Then verify authenticated selection **from .69**, not a localhost impersonation.

## Exact .69 confirmation checks

Run from the installed Dashboard working directory with its own venv/private env. Resolve the effective reader without revealing passwords:

```powershell
.venv\Scripts\python.exe -c "from app.config import settings; print(settings.operation_db_user)"
```

After .73 applies the confirmed reader grants, run this using the installed receiver credentials (save as a local Python file; never put passwords on the command line):

```python
import pymysql
from app.config import settings
c = pymysql.connect(host=settings.telemetry_db_host,
    port=settings.telemetry_db_port, user=settings.operation_db_user,
    password=settings.operation_db_password,
    database=settings.operation_db_schema)
with c.cursor() as q:
    for sql in [
        'SELECT USER(), CURRENT_USER()',
        'SHOW GRANTS',
        'SELECT id, stream_id FROM ht9046mx_dashboard_identity',
        'SELECT id, last_seq FROM ht9046mx_dashboard_sequence',
        'SELECT COUNT(*), MIN(seq), MAX(seq), MAX(occurred_at) FROM ht9046mx_dashboard_feed',
        'SELECT seq,event_id,kind,machine_number,module,occurred_at FROM ht9046mx_dashboard_feed ORDER BY seq DESC LIMIT 5',
        'SELECT machine_number,recorded_at FROM ht9046mx_iot.ht9046mx_readings ORDER BY recorded_at DESC LIMIT 1',
    ]:
        q.execute(sql)
        print(sql, q.fetchall())
c.close()
```

`CURRENT_USER()` must match the confirmed username at `10.195.17.69`; grants must be USAGE/SELECT only. Independently test Vacuum with its existing separate configured reader and preserve `device_id`. Successful SELECT of empty tables proves grant/connectivity only, not delivery.

With authenticated Dashboard access, inspect **GET `/api/db/status`** twice at least 10 seconds apart. `operation_pull.enabled=true`, `connected=true`, no 1044, `last_success_at` advances. Once real exports exist, `last_seq` must advance toward the .73 `last_seq`, backlog must drain, and `pm_operation_source_identity.stream_id` must equal the producer identity. Compare `pm_operation_cursor` and receipts to feed; do not reset stream namespace/cursor. STATUS receipts must remain NOT_EVALUATED/null Health Score for this Shadow deployment.

Restart the existing single Dashboard API with its installed restart mechanism, recheck source identity/cursor/receipt and Alert dedupe, and confirm both raw sources still work. Perform outage/replay experiments in isolated QA rather than deleting production evidence or opening reverse connectivity. Verify hourly-history gaps remain gaps and unsupported Shadow never votes Good. Dashboard end-to-end/browser/boot checks remain .69-owned acceptance work.
