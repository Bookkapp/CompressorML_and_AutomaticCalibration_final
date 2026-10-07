# One-way MySQL update — 7 October 2026

Read this before older installation instructions. The owner confirmed that only **.69 can initiate .73:3306**. Operation cannot initiate any connection to .69. No reverse firewall opening, Dashboard SQL writer credential on .73, or Operation HTTP connection is needed.

## Data path and ownership

1. Operation .73 commits frozen Context assessment, controls, phases and anomaly Events locally, together with its detector checkpoint.
2. New `ht9046mx_dashboard_feed` stores ordered STATUS/EVENT exports; `ht9046mx_dashboard_sequence` serializes committed sequence allocation. `ht9046mx_dashboard_identity` detects a replaced producer DB. `ht9046mx_dashboard_latest` bounds status heartbeats to five minutes or status/category/version changes.
3. One Dashboard API process on .69 SELECTs the feed in batches of 500, normally every five seconds. Additional catch-up pages are bounded. Raw Compressor/Vacuum reads remain separate SELECT-only connections.
4. Dashboard commits its receipts, local status/Alerts and cursor together. Retry, outage, concurrent consumer and process restart do not duplicate a committed delivery. Unknown machine/module results are buffered and retried after discovery.
5. Browsers receive the shared state through the existing WebSocket. Opening additional tabs does not start additional feed consumers. A one-minute idle broadcast refreshes signal ageing even without new readings.

Operation scheduler never calls the old reverse bridge, even if an old flag remains true. Old bridge tables/receipts are preserved. Do not run `qualified_bridge --migrate-only` or its delivery command for this topology.

## Update .73 first

- Back up `ht9046mx_analytics`, existing service configuration and model/Profile pointers. Fetch this private repository and merge the current release by fast-forward; preserve Server-specific working changes.
- Merge configuration keys into the Server's current `.env`; do not replace working Server credentials or model paths with development paths.
- Set `HT9046MX_DETECTOR_BRIDGE_ENABLED=false`. Preserve the current Shadow/live decision, approved Profiles and frozen model pointer. This update does not approve a Profile or turn Shadow into operational health.
- Use the existing Python environment and run:

```sh
python -m pip install -r apps/api/requirements.txt
python -m apps.api.app.context_migrate --allow-remote
python -m apps.api.app.qualified_detector --allow-remote --migrate-only
```

These commands add analytics metadata only. Verify all new export tables use InnoDB. Restart the existing Operation API and its single detector-only Worker using the existing service supervisor. Do not reinstall or switch a working frozen model as part of this update.

Grant the Dashboard's configured reader account, restricted to host **10.195.17.69**, SELECT on:

- `ht9046mx_analytics.ht9046mx_dashboard_feed`
- `ht9046mx_analytics.ht9046mx_dashboard_sequence`
- `ht9046mx_analytics.ht9046mx_dashboard_identity`

Use the existing Server MySQL admin mechanism. Resolve the real `OPERATION_DB_USER` from Dashboard configuration locally and quote the account/host correctly. Never print passwords or use a wildcard host as a shortcut. No INSERT/UPDATE/DELETE/DDL permission on these tables is required for .69. Existing source grants remain SELECT-only.

## Update .69 second

- Back up `predictive_maintenance` and current `.env`, service/proxy configuration and Git revision.
- Preserve installed Server changes based on `eb3b097`; fetch `final-origin/main` or the matching `_final` origin. Do not reset the installation blindly.
- Merge these keys into the existing Server configuration:

```dotenv
OPERATION_PULL_ENABLED=true
OPERATION_DB_SCHEMA=ht9046mx_analytics
OPERATION_PULL_INTERVAL_SECONDS=5
OPERATION_PULL_BATCH_SIZE=500
OPERATION_PULL_ALERTS_ENABLED=true
COMPRESSOR_HEALTH_ENABLED=false
```

`OPERATION_DB_USER` / `OPERATION_DB_PASSWORD` in this private release reuse the existing Compressor source reader. Confirm that account's restricted .69 grant on the new analytics tables before startup. Use a separate SELECT-only account if the current Server already has one, and save actual credentials privately. Do not borrow the Operation analytics writer. Source host/port remain `TELEMETRY_DB_HOST=10.195.17.73`, `TELEMETRY_DB_PORT=3306`; metadata DB stays local to .69.

```sh
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm ci
npm run frontend:build
```

Restart the existing single Dashboard API service. Startup adds `pm_operation_*`, `pm_module_status_*`, `pm_module_health_hourly`, `pm_fleet_health_hourly`, capture/dirty-hour tracking and system-settings tables. Review definitions and InnoDB engine before accepting an existing incompatible schema. No raw source table is migrated or written. Keep the existing proxy /api and WebSocket configuration.

## Status contract

- Only supported assessments from an approved frozen Context in `DETECTOR_LIVE` vote Good/Warning. Shadow, missing/expired evidence, unsupported/excluded states and no Active Context are **NOT_EVALUATED**, never Good.
- Supported steady/transition -> Good. Steady deviation, unexpected transition or unresolved new steady level -> Warning. This mapping introduces no synthetic Health Score and no new critical threshold. Repair now is reserved for an explicit `MAINTENANCE_REQUIRED` producer result; the current Context classifier does not infer Critical from a score that it does not produce.
- Under Maintenance is preserved; Alerts honor daily severity dedupe, suppression and the last Clear time. Replayed old evidence does not create new current Alerts. Dashboard-owned alerts use the same metadata workflows as before.
- Raw signal older than 30 minutes -> Offline. Compressor remains Online through the inclusive 30-minute boundary. Fresh raw data with stale/missing analysis is NOT_EVALUATED, not healthy.

## Hourly Fleet Health Trend

`pm_module_status_events` retains status changes and bounded heartbeats using source timestamps. `pm_module_health_hourly` stores each module's state at each **completed hour end**, and `pm_fleet_health_hourly` stores counts for Good/Warning/Repair now/Offline/Not evaluated/No signal/Repairing. The existing unified `ht9046mx_events` on .73 and EVENT receipts on .69 retain controls/transitions/anomalies.

The graph reads **168 completed-hour points**, Bangkok timezone, with a shared 60-second cache and one-minute UI refresh. Counts are modules, not machines. A brief Warning resolved before hour end remains in the event history; the graph point is the end-state snapshot, not the worst state during the hour. Late evidence can repair affected existing buckets in bounded batches. Missing capture is null, not zero or carried-forward Good. Capture starts with this release; it does not invent seven historical days from today's status.

Retain the feed and state history while consumers may need them. This release does not automatically prune receipts/feed. Before future retention cleanup, reconcile committed cursors and backups and document the replay horizon. A replaced producer identity, reset sequence, missing sequence, invalid contract or future result blocks cursor advancement visibly. Recover by inspecting/backing up both ledgers and explicitly selecting a replay/source namespace; never silently reset the cursor or delete records to make the error disappear.

For a deliberate producer DB replacement, confirm the new feed starts at sequence 1, back up both sides, then set a new persistent Dashboard `OPERATION_STREAM_NAMESPACE` (for example `recovery_20261007`). This starts a separate receipt/cursor identity and bounded replay while preserving the original ledger. Do not change that namespace on ordinary restarts. Missing/pruned feed ranges require recovery from backups; a new namespace does not manufacture missing records.

## Charts and source units

Compressor stages now use blue HP1/LP1 and orange HP2/LP2; LP is dashed. Differential Temperature is replaced by separate linked SV/Busy step plots (0/1; missing remains a gap). The shared chart wrapper compensates for CSS 90% scaling in pointer coordinates, including related history/Analytics charts.

Vacuum overview has Current/Vibration/Estimated Pressure on separate unit axes; both requested pressure plots remove Temperature and put **0 at the bottom**, retaining negative values. Vibration display/metric metadata uses owner-requested **G rms**. No numerical conversion, threshold or pressure-calibration coefficient was changed. Confirm that the ingestion firmware computes true RMS and that existing `V = -0.0439P - 2.2098` calibration used the same input unit before certifying physical pressure accuracy. An archived vector-magnitude firmware example alone does not establish temporal RMS.

## Server acceptance and rollback

Record actual Server revision, service names, redacted DB mapping and outcomes in `deployment/SERVER_ACCEPTANCE.md`:

1. From .69 test authenticated SELECT on all three feed tables and both raw schemas. Inspect existing Vacuum `device_id` / `devices_id` column; preserve the configured real column.
2. `/api/db/status` must show `operation_pull.enabled/connected`, advancing cursor, success time and backlog. Missing tables/grants remain visible errors; no fabricated health.
3. Restart Dashboard and Worker; replay a bounded page in isolated QA; confirm unchanged receipts/Alert counts. Stop .73 connectivity briefly: raw/analysis freshness is visible, cursor retained; reconnect catches up without duplicates.
4. Open several machine/module tabs, Historical Charts and Analytics, inspect pointer position, drag/zoom, SV/Busy and Vacuum axes. Measure cold SQL, API, browser render, RAM and actual .69–.73 lag separately. Worker normally finalizes one-minute source evidence; five-second polling does not make that inference subsecond.
5. Confirm hourly counts reconcile to module snapshots, gaps remain gaps, unsupported Shadow never votes Good and Maintenance is preserved. Test the 30-minute signal boundary with a QA clock/fixture, not by modifying production raw data.
6. Roll back code/config to the recorded revision while keeping additive metadata/source/model/Profile data. Re-enable an old bridge only if topology actually changes; it cannot operate under the confirmed one-way network.

## Local verification (not Server deployment)

Dashboard: 91 Python tests, 13 Node tests and production build passed. Operation: full API suite and targeted transaction/Context tests are recorded in the companion release QA note. Isolated real-MySQL QA covered transaction rollback, duplicate retries, concurrent commit ordering, restart/outage, replaced stream rejection, unmapped replay, Alert dedupe/clear/Maintenance, 30-minute Offline and late hourly corrections. `artifacts/operation-pull-qa/http.json`: 10 clients / 90 successful reads, warm p95 1000.84 ms; initial bounded history responses 11.26–963.65 ms (shared-cache hits are possible). These measurements exclude browser rendering and target Server network. Raw telemetry/Profile writes: zero. Local visual checks include both families and multiple tabs; the screenshots are QA evidence, not certification of a real Active Profile.

Shared Dashboard devices/summary cache misses now coalesce into one query per key, including failure/retry unlock tests. A separate load round concurrent with a Vite build reached p95 4422.50 ms; retained as `http-during-build.json`. This is not a controlled attribution experiment: compilation competes for CPU/RAM, and Server latency still needs measurement under its actual workload.
