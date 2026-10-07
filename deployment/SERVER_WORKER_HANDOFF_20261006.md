> **7 Oct superseding update:** Read `ONE_WAY_MYSQL_UPDATE_20261007.md` and root `HANDOFF_SERVER.md` first. The reverse bridge is disabled; .69 pulls from .73. Merge new keys into current Server config, preserve installed frozen model/Profile/services. Explicit owner permission covers actual configuration/secrets in the PRIVATE final repository.

# Handoff: Operation Worker / Fleet — Server 10.195.17.73

Updated: 6 October 2026, Asia/Bangkok. Owner requested a handoff for Codex running on the Server, rather than deploying from the development PC.

Latest UI/API addition: include `deployment/CONTEXT_FOLLOWUP_PROGRESS_UAT_20261006.md` and followup code with the checkout. It reuses existing jobs/observed snapshots/events without a new migration. Verify source clock and indexes on Server; progress GETs use bounded seeks, while user-triggered interim jobs capture real postfreeze data without fitting or approval. Browser metadata polls do not replace the ingestion/detector service. No Mock UI. Actual development source had no postfreeze data, so actual partial/day/Raw and3-day acceptance must be repeated after ingestion on Server.

## Entry instruction for Codex

When the owner says **“Set up ระบบนี้ให้หน่อย”**, read the repository's AGENTS.md and required README_System → SOT → HANDOFF → Project → Roadmap sequence, then this document. Set up and test the **Operation observation + Fleet Shadow Worker** on the actual Server. Inspect the Server OS, checkout, Python, existing services, database schema and local configuration first. Preserve existing source data, profiles and services. Record resolved paths and service names in a Server acceptance report.

The owner has authorized installation/setup on that Server when giving this instruction. Reuse verified existing configuration and secret storage; do not ask for passwords in chat. Ask only for genuinely missing source mapping or engineering semantics. Read-only exploration, preparing the service and testing Shadow are part of setup. Machine Active approval requires its recorded engineering and prospective-data evidence; setup is not that approval.

## Deliverables to copy with the checkout

- API/web code, `apps/api/requirements.txt`, web lockfile.
- Frozen model ZIP in `notebooks/outputs/fleet_workflow_20261006/`. The manually trained package is `fleet-stable-v1-586e67981fc6d695467f0d01`; the previous local candidate is `fleet-stable-v1-bf374a30f7ccf04430693b0d`. Verify the copied manifest before installation; prefer the latest verified inventory if later versions exist.
- `deployment/FLEET_WORKFLOW_UAT_20261006.md`, executed Notebook14 and its JSON evidence.
- Do **not** copy the development `.env`, SQLite rehearsal database, test reviewer notes, or local `shadow.json` as Server configuration.
- Runtime inference needs the frozen package only. Retraining and historical Fleet evidence additionally need the prepared study `summary.json`, `intake_manifest.json`, `minutes/`, `events/`, and `transition_metrics.parquet` with valid receipts. If those are absent, deploy inference first and clearly mark training/evidence unavailable. Adding new source data later requires a new checksum reconciled intake/study; it does not update a frozen model in place.

## Architecture and bounded work

Source SELECT-only connection → overlap reader → completed observed minutes → durable checkpoint / source receipts → frozen Local Context and optional Fleet Shadow → one `ht9046mx_events` table.

Raw SV/Valve/Module/Busy/Compressor transitions, gaps, duplicate seconds and derived phase/anomaly evidence all remain inspectable. Fleet uses no PLC command, model training, auto-normal adaptation or operational alert vote. Active Context scope excludes unselected SV states while retaining raw events. Frozen Fleet responses cannot certify an unfamiliar flat absolute pressure level.

One detector service owns scheduler execution. HTTP tabs perform reads and controlled review/version requests. Cursor, checkpoint, evidence and common Events commit together. Retry identity and SQL revision checks protect repeated deliveries and concurrent updates. A Fleet switch starts a new run contract pinned to that bundle; old evidence/checkpoints retain the original version. The first scan starts from the configured overlap; downtime catch-up follows the saved watermark in bounded five-minute slices. A newly selected model's new run begins with the overlap, not a full historical replay.

Start with six requested machines: `MX017,MX024,MX041,MX058,MX080,MX081`, all 8 Compressor modules. These are Compressor columns; do not map Vacuum Pump readings to this feature contract.

## Configuration checklist

Use the existing Server secret mechanism; configure `.env` privately only if that is the deployment's established mechanism. `get_settings()` reads `.env` in the service working directory. Ensure API and Worker see the same resolved non-secret settings:

```dotenv
HT9046MX_APP_MODE=live
HT9046MX_DETECTOR_WORKER_ENABLED=true
HT9046MX_DETECTOR_SHADOW_ONLY=true
HT9046MX_DETECTOR_FLEET_SHADOW_ENABLED=true
HT9046MX_DETECTOR_MACHINES=MX017,MX024,MX041,MX058,MX080,MX081
HT9046MX_DETECTOR_OVERLAP_MINUTES=30
HT9046MX_DETECTOR_MAX_SOURCE_ROWS=10000
HT9046MX_DETECTOR_CRON=* * * * *
HT9046MX_SOURCE_TIMEZONE=Asia/Bangkok
HT9046MX_SOURCE_PRESSURE_UNIT=psi
```

Also resolve `HT9046MX_FLEET_STABLE_STORE` to a writable **Server-local disk** directory, separate from source data, and `HT9046MX_FLEET_REFERENCE_ROOT` only when prepared evidence is installed. Do not guess database credentials/columns. Check existing source/analytics host/name/user settings, source timestamp/machine/monotonic ID fields and 10 module templates in `ObservedSourceReader`. Source user requires SELECT only; analytics writes require its own account/schema. Avoid logging connection URLs or credentials. `10.195.17.73` identifies the target Server, not evidence that its SQL source schema is the development PC schema.

Validate observed state codes against the configured policy. Pressure is owner-confirmed psi; psig/psia, state contract, controller codebook and service epoch remain unverified locally. Fleet Shadow accepts the declared psi / Asia/Bangkok contract only. Keep these limitations visible; do not manufacture contract versions to unblock Active.

Before publishing management POST routes on the LAN, bind `X-Approver-Id` to the deployment's authenticated reviewer/approver role using its gateway/auth layer. A typed reviewer header in the local QA UI is not Server authentication. Keep loopback binding until the existing access layer is configured and tested.

## Setup commands

Run from the resolved repository root with the Server's Python environment. Create a venv and install `apps/api/requirements.txt` if not already configured. Never replace the machine's existing Python or unrelated services.

1. Inspect analytics schema and back it up according to the Server's existing process. Use the existing registry/reference SQL deployment files if required by this checkout. Do not recreate existing tables with incompatible definitions.
2. Add Context / common Event tables and detector tables explicitly:

```powershell
python -m apps.api.app.context_migrate --allow-remote
python -m apps.api.app.qualified_detector --allow-remote --migrate-only
```

Both commands are additive analytics DDL. `create_all` does not repair incompatible old columns; inspect and prepare an explicit migration when necessary. Source schema is never migrated.

3. Install the verified package into the resolved model store:

```powershell
python -m apps.api.app.fleet_bundle --store <resolved-model-store> install <copied-package-zip>
python -m apps.api.app.fleet_bundle --store <resolved-model-store> status
```

For an empty store, use the returned installed bundle ID and expected revision 0. For an existing store, read and use its actual revision. Select **Shadow** with a real setup actor and reason:

```powershell
python -m apps.api.app.fleet_bundle --store <resolved-model-store> switch <verified-bundle-id> --expected-revision <actual-revision> --actor <setup-actor> --reason "Server Shadow setup"
```

4. Perform one bounded actual-source cycle and inspect its result/Event History:

```powershell
python -m apps.api.app.qualified_detector --allow-remote
```

5. Start API and the observation-only scheduler with the **same working directory/env**:

```powershell
python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
python -m apps.api.app.worker --detector-only
```

Register the Worker with the Server's existing service supervisor (Windows service/task infrastructure or Linux systemd as discovered). Use its venv's absolute Python path, repository working directory, one service instance, startup at boot, automatic restart/backoff and rotating logs. Windows background helpers must use hidden windows. Do not use a foreground terminal as the persistent service. Do not start the legacy profile/model training scheduler just to enable the detector. Build the web UI with the checked-in lockfile and configure its reverse proxy to the local API.

## Server acceptance gates

Record actual outcomes, including an initial dry read of timestamp range/state codes and maximum source rows. If a slice exceeds the row budget, reject the whole slice before advancing a checkpoint; investigate duplicates/volume and tune the declared budget. No partial truncated data may be scored as complete.

- First start with **no Active Context**: all observed control Events still captured; context health is NOT_SCORED; supported Fleet data produces Shadow evidence only.
- Restart the process/service while ingesting. Compare cursor, minute IDs, event IDs, pinned bundle and consecutive anomaly persistence before/after. Repeat the same source slice: no additional evidence/events from retries.
- Inject a controlled analytics transaction failure in an isolated QA schema, then retry; cursor and Events must commit together. Never corrupt actual source rows for a test.
- Open Calibration/Fleet/Event pages in several tabs for different machines/modules while Worker runs. Record request latency, CPU/RAM, source query time and event lag. Local warm HTTP results exclude cold source reads and browser rendering.
- Compare and select a new **Shadow** Fleet version; confirm a new pinned detector run. Try a stale expected revision: conflict, no pointer change. Roll back through Fleet Models and restart: selected version must persist.
- Confirm raw controls remain present during SV states outside an Active Profile scope; model scores for excluded states must be absent. Returning to a supported state uses its frozen reference immediately.
- Confirm model/receipt tampering is rejected; no old checkpoint advances with a changed model contract.
- Test late commits within overlap and after finalization. Document quarantine behavior and data freshness limits; without CDC, arbitrary lateness beyond overlap is not guaranteed.
- Shadow flags are review evidence; Normal/fault accuracy and detection delay need independently confirmed labeled intervals. Do not call historical archived data untouched prospective validation.

Acceptance report must identify the Server hostname/OS, resolved paths/services, database mapping (without secrets), bundle/checksums, source clock, restart/retry results, Event counts, multi-tab latency, unresolved gates and the rollback command. Setup success does not change a machine's Active Profile.

## Current local evidence / limits

248 API tests passed before final lock changes; targeted regression and final counts are recorded in the linked UAT report. Real SELECT-only slices for 041/058/080/081 × 8 modules were replayed into an isolated SQLite evidence store with restart/retry; no real analytics tables were written by that rehearsal. 10 clients / 120 prepared HTTP GETs passed (warm p95 ~173 ms). These are development results; actual Server clock/service lifecycle/source-load acceptance remains to be run there.

The Transition proposal library has 144 groups / 512 Reference events and 114 separate historical holdout events. 55 holdout events have evaluable curve minutes, with 1,929 / 2,356 minutes outside the fitted envelopes. **Zero donor groups pass the conservative independent response screen**, so none is automatically admitted as a transfer reference. This is deliberately visible in Fleet Models and Calibration with source graphs. Engineer-referred Normal cycles and/or better regime/configuration grouping are needed before transfer, rather than widening envelopes to hide abnormal behavior.

MX058/M1 saved Shadow 2–4 October: 4,320 observed minutes, 3,914 evaluated, 20 flagged (0.511% burden), 339 unsupported, 67 data-quality, 7 flagged episodes. These dates predate the saved review/freeze and do not satisfy post-freeze validation. If an SV state has no adequate reference, the owner can explicitly exclude that state per Profile and review the included states; excluded raw/control events remain available.
