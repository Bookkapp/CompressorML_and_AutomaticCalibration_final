# Fleet Stable v1 — portable Shadow handoff, 6 October 2026

## Delivered

- Frozen Candidate `fleet-stable-v1-2f656893533033ab994e3713`: **43 calibrated profiles**, 40 with compatible correlation assistance, 70 donor summaries. All six machines/eight modules/SV contexts considered; missing calibration contexts remain unsupported. Numerical support is not reviewed health.
- 555 prepared source days /46,616,484 original-row receipts rechecked; canonical ZIP corpus, not exact current SQL. No source DML/import resume. Existing207Profile/46Active hashes unchanged and ContextActive0.
- Portable ZIP **131,414 bytes** with JSON models/scalers/covariance/thresholds, priors, curation, provenance, validation, README and manifest checksums. SHA256 `1566095c67d4b37777bdc07f58886ca032c478d31cf22108644851a2339509e8`. Only JSON loading, no pickle/joblib. Copied outside repo and loaded with exact prediction parity without SQL/notebook inputs; this is not a target-Server test.
- Local Shadow repository installed; actual base→Candidate→base rollback→Candidate tested. CAS rejects stale revision. Each request pins one immutable version; malformed/tampered package fails closed. Checksum guards accidental changes; no cryptographic publisher authentication is claimed. Store permissions must be restricted to the deploying operator.
- Calibration Fleet Stable UI shows version, per-module supported contexts, separate fit/calibration periods and on-demand actual minute graphs. Prepared graph requests never fit models or rewrite shared Profiles.
- Common `ht9046mx_events` adapter covers derived phase changes, persistent evidence and acquisition review idempotently. Original observed-second SV/Valve capture remains responsible for every control command. This task adds no live producer/worker, no new SQL Fleet-event backfill and no production Alert votes; version deployment history is an atomic file document.

## Method and curation

Frozen Local median and MAD/IQR scales; selective compatible donor correlation shapes, asset-balanced with capped prior strength20, same target machine excluded, source cutoff before target Reference end. Robust empirical moments are an EB-style approximation, not exact NIW/Student-t probabilities. Same M/SV is an unverified research stratum, not a verified hardware/ATC/recipe hierarchy. ARX is absent from this runtime; previous offline challengers remain.

Default Reference2Jul–14Aug; separate threshold15–21Aug. MX080/M6 Candidate uses owner-proposed Reference27–30Aug and threshold3–6Sep. These are NOT Engineer-certified healthy intervals. Old0.35×scale-only stability left156threshold minutes and no M6 Candidate. Frozen Fit-only Q90 five-minute coordinate ranges, max with0.35robust scale/0.1physical units, tolerate ordinary sensor variation; actual Candidate n/model phase bounds are serialized. Calibration/case/future never fit phase bounds. Statistical stability does not admit unreviewed new levels as healthy.

All-state data and transitions retained. -200 temperature defaults/all four pressures580.2 are conservative acquisition-suspect evidence; hardware sentinel codes remain unverified. The independently audited7Sep10:55:59–11:28:01 interval rounds outward to34minute rows, so mixed boundary averages cannot slip through. Live source adapters must set invalid-second `semantic_bad`; minute averages alone cannot prove all underlying seconds valid. This does not modify legacy ingestion/Data Gate.

Scores are visible during physical response, without an exclusion timer. Raw persistence is3adjacent same-context valid minutes; response/steady descriptors never clear an ongoing flag. This batch day adapter resets at midnight; a streaming producer must retain continuity/checkpoint across days. WITHIN_REFERENCE is not a health label. Post12Sep/newValve100 remains a regime/epoch review.

## Actual regression and performance

| Check | Observed result | Interpretation |
|---|---|---|
|Owner-confirmed7Sep12:30–8Sep23:50|2089/2089 eligible minute flags;2079 persistent;875 stable flags|Retrospective previously inspected case; unsupported/bad minutes excluded|
|7Sep00:00–08:00 proposed stable holdout|2/480 raw;0persistent;0/395stable flags|Owner-proposed, not independently healthy FPR|
|Suspect acquisition interval|34DATA_QUALITY;0physical anomaly flags|Separate sensor/data investigation|
|12Sep04:00–midnight|1200/1200raw flags|Different control level, unreviewed regime; NOT proof of fault|
|Compiled/fitting-function parity|43,227 actual points;0score error|Numerical parity, not independent accuracy|
|Full1430minute-module-day inference|p5034.4ms /p9550.8ms|Excludes IO, fitting and UI|
|Prepared HTTP10clients/120GETs|120success;warm p95201.5ms|Not cold source SQL or browser-render latency|

Backend/API package, mutation, isolation and event tests; TSC/Vite and actual manual browser evidence are recorded in the companion QA receipts. Existing Vite large-bundle and SQLite datetime warnings remain. Figures and all exact per-context receipts are in executed Notebook13/local outputs.

Final focused regression: **34 tests passed in 8.26 s** across Fleet package/API and context workflow/events. TypeScript passed; final Vite build passed in 9.69 s with the existing large-bundle warning. Actual final browser checks kept MX080/M6/7 Sep, MX041/M3/15 Sep and MX081/M8/16 Sep open concurrently: all three graphs retained the correct machine/module/day, each chart card was 358 px high, with no horizontal page overflow or “Loading chart data” text. MX041 control details correctly explain Module Off as unsupported evaluation; this is distinct from missing Local Profile. An older development tab previously lost its Fleet section; day-query cache schema isolation and defensive nullable-control rendering were added, then fresh three-tab checks passed. The earlier blank-tab cause was not independently confirmed.

Receipts: `notebooks/outputs/fleet_stable_v1_20261006/qa.json`, `browser-qa.json`, `technical-checks.json` and `fleet-stable-mx080-m6.png`. The API was restarted with final source-mapping/loader code; the Calibration page remains open at `http://127.0.0.1:5176/` for MX080/M6.

## Installation on Server

Copy this ZIP and the reviewed Operation API code to a controlled Server directory. Inference requiresPython>=3.11/NumPy2.x/SciPy>=1.13,<2; actual local tested environment isPython3.12.10/NumPy2.2.1/SciPy1.16.2. Keep API dependencies as declared by Operation. The model loader itself does not need SQL or notebook raw data.

```powershell
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" install "D:/Release/fleet-stable-v1-2f656893533033ab994e3713.zip"
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" status
```

For an empty store, `status` has no selected model until switching. Read `shadow.json` revision (0when absent), then:

```powershell
python -m apps.api.app.fleet_bundle --store "D:/Operation/models/fleet" switch fleet-stable-v1-2f656893533033ab994e3713 --expected-revision 0 --actor "ServerOwner" --reason "Approved Shadow installation"
```

Set `HT9046MX_FLEET_STABLE_STORE` to that directory. Model status isGET`/api/v1/calibration/fleet/stable/reference?machine_number=080&module=6`. Historical day charts optionally need an independently installed prepared evidence store via`HT9046MX_FLEET_REFERENCE_ROOT`; inference itself takes observed rows and needs no notebook folder. No fitting occurs in HTTP. The target source-minute adapter must match clock/controls/coverage/quality contract; do not send legacy snapshot/five-minute rows as observed completed minutes.

Producer integration:

```python
from apps.api.app.fleet_bundle import current_snapshot
from apps.api.app.fleet_stable_events import evidence_events
from apps.api.app.unified_events import append_events
pointer, fleet = current_snapshot(model_store)
result = fleet.evaluate("080", 6, observed_module_day_rows)
records = evidence_events(result, source_digest=verified_source_digest,
    source_namespace=verified_source_namespace, verified_source_mapping=True)
# producer-owned transaction: append_events(conn, records), then checkpoint
```

Live worker/outbox, authentication, clock/service recovery and production activation are not enabled by these instructions. Target-Server acceptance remains unperformed. The package only permitsShadow; it cannot becomeActive by editing a pointer mode.

## Retraining and rollback

Add new data to a new checksum-reconciled prepared evidence inventory. Copy `build-plan.json`, set explicit fit/calibration periods, machines and optional machine/module overrides. Keep disjoint periods and review contamination/service epochs. Run:

```powershell
python -m notebooks.support.fleet_stable_build --source-root "D:/Evidence/new_snapshot" --plan "D:/Plans/fleet_v2.json" --output-root "D:/Candidates/fleet_v2"
```

Plan periods3–90days, machine count1–32; calibrated Reference coverage still needs>=3days,>=20spacedpoints,>=200separate threshold points/3days. Unreviewed references remainShadow-only. Refit/validate writes a new immutable version and does not change deployed pointers. Install new version, validate before switching, and use the current expected revision.

Rollback by switching to `previous_bundle_id` with the current revision; no deletion or in-place model mutation. Cross-process file lock fails promptly on competing deployers. If a deploying process crashes with `.shadow-pointer.lock` remaining, an operator must verify that PID is gone before removing only that stale lock. Missing/corrupt files block inference; do not silently train or choose a different model.

## Remaining acceptance

Engineer-reviewed Normal intervals and hardware/role/configuration/recipe/state/controller/service/pressure-basis contracts; independent healthy-cycle alert burden; truly untouched future validation after this frozen version; authenticated source producer/worker/common-event checkpoint; real target-Server Shadow/approval/rollback/live votes. AllSource rows and known anomalies remain retained. NoActive was promoted, no Server deployed and no Gitpush occurred in this local task.
