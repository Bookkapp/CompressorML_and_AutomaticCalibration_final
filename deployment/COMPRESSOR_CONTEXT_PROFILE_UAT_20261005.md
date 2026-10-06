# Compressor conditional Profiles and unified Event History — local delivery

Date: 5 October 2026, Asia/Bangkok. Environment: `OPERATION_P`, local source/analytics MySQL, API `127.0.0.1:8000`, Operation UI `127.0.0.1:5176`.

**Status:** implemented local Candidate/review/investigation workflow and historical event capture. This is not a production model release or successful real-machine Active approval. Local migration applied; no Server deployment or Git push. Existing 46 legacy Active rows retain the exact hash below.

## What changed

- New all-state minute transport retains available pressure/temperature measurements and control witnesses, including SV ON and manual states. Measurement quality is separate from fit/scoring eligibility. At least 57 distinct observed seconds, no gap over 5 seconds, finite required measurements and no duplicate machine second remain necessary for a usable minute. Raw rows are retained even when a minute fails.
- New per-machine/module conditional Candidate proposes several steady regimes. SV OFF and SV ON have separate contexts. Manual/unsupported contexts stay visible without automatic healthy classification. Reference-only clustering uses a bounded sample, fixed seed 17 and up to four mixtures per context; supported regime proposals need at least 7 source days and 200 Reference minutes.
- Separate event-conditioned response templates require exact control witnesses, a recognized prior regime and repeated Reference examples (at least 3 events over 3 days). Ordinary Valve commands, state changes and bypass SV events have distinct identities. Every observed command remains in the event ledger even when no response template is supported.
- New steady levels do not have to return to an old numerical baseline. A previously unseen flat plateau remains `NEW_STEADY_LEVEL` for review. Proposed regimes/templates are not certified healthy examples.
- Shadow explains each minute as within a proposed steady/transition envelope, a deviation, an unsupported transition/context, a new steady level or unavailable data. Contributor values and selected pressure/temperature bands are inspectable; the same time opens bounded Raw.
- Reviewer acceptance creates an immutable child Profile. Reference dates/exclusions require rebuilding; an exclusion never deletes Raw or control events and cannot remove historical Shadow samples. Drafts are isolated by actor/Profile, survive reload, and stale-tab saves return a conflict instead of overwriting another save.
- Historical Shadow is diagnostic. Prospective validation uses frozen accepted Reference parameters and three complete source days after the actual Reference-review timestamp. It does not refit the baseline using the tested future block.
- Separate Context Active pointers, compare-and-swap decisions, previous frozen Profile and rollback are implemented. Real activation remains blocked by unverified source contracts, missing Engineer evidence and missing future validation.

### Delayed response repair in v4

Initially, an early minute within a known steady envelope cleared the control context. A delayed thermal/pressure response could then be evaluated without its preceding control witness. `conditional-steady-transition-candidate-v4` keeps the bounded control context for up to 120 minutes, until another relevant event, a data interruption or unsupported state supersedes it. An early steady minute can still be displayed as steady; later deviating measurements can use the applicable Reference-only response template. This is a context tracking budget, **not a blanket 120-minute suppression window**. Missing templates, unexpected trajectories and unrecognized flat plateaus still require review.

Older v1–v3 Profiles remain immutable. Their measurement charts can be inspected, but the current endpoint labels their assessment as `ARCHIVED_MODEL_VERSION` instead of silently rescoring them with v4.

## Unified event storage

Local analytics table `ht9046mx_events` now contains observed control changes, data availability/duplicate evidence, derived phase/anomaly boundaries, and Profile creation/Shadow/review lifecycle events. Source occurrences use declared source-local clocks; recording clocks are separate UTC timestamps. A global Compressor state change is machine-scoped once, not eight independent module changes.

One-second changes are captured before fit eligibility. Multiple changes within one minute survive. Source gaps are bracketed uncertainty; duplicate seconds break the usable prior witness. Deterministic source identities, bounded batches and atomic source checkpoint/ledger writes protect retries. Changed source-day revisions append correction evidence and preserve immutable day snapshots.

The shared history view supports machine → module/global scope → dates → family/type → assessment → historical/Shadow/live mode, bounded keyset pages and correlated details. Raw investigation is shared here; removed chart widgets in Alerts/Maintenance/Logs were not reintroduced. Changing filters clears the previous detail/graph. Common Raw validates the retained event source identity or its frozen Profile source mapping before using the configured source; unknown operational telemetry mappings are blocked with a readable explanation.

### Integration boundary that remains open

- The private `operational_inbox.receive()` boundary and analytics receipt table are implemented and tested for retry, rollback and correction. **The actual Dashboard producer/outbox for ACK, Alert closure, work-order and service-log changes is not yet connected.** These events are therefore not claimed as captured from real operations in this local run.
- Detector/episode/notification hooks are opt-in and tested. **No live detector worker or PM bridge was started.** Actual observed event coverage here is the selected historical preparation period for MX017/MX024, not a continuous live capture claim.
- Producer clocks, record identities, telemetry mapping and authenticated reviewer/approver roles need target-system integration validation. Current local actor text is not a production authentication contract.

## Actual source periods and completed jobs

Machine identities are MX017/MX024. Source pressure unit is owner-confirmed **psi** and persisted in the local API configuration. Whether it is psig or psia remains unverified. Bypass SV is not interpreted as an EEV command; Busy is not interpreted as motor-running status. TempLo is not treated as verified DUT temperature or suction superheat.

Default Reference: **31 August–27 September inclusive**. Historical Shadow: **28–30 September inclusive**, Asia/Bangkok. October 1 is an incomplete latest source day and is omitted from fit/Shadow. Latest source rows remain October 1, 15:55 for 017 and 15:45 for 024; there are no three complete source days after the October 5 review.

| Machine | Final v4 job | Modules | Result | Total elapsed admission → completion |
|---|---|---|---|---:|
| MX017 | `65653574-57c3-40ee-af24-8dc202c972ac` | M1–M8 | 7 with supported steady proposals; M7 insufficient | 87 s |
| MX024 | `2aea7f32-61b6-417d-ae14-580fe84e7fdb` | M1–M8 | 7 with supported steady proposals; M7 insufficient | 155 s |

The second duration includes time waiting for the single preparation worker. These are warm shared-day preparations, not first-source-read guarantees. Initial cold/source-revision preparations during this session took about 8–15 minutes; a one-hour source-revision cache expiry can still trigger that work. Background durable jobs keep graph investigation available during preparation.

Final automatic preparations do not carry the earlier deliberately unverified QA exclusion. That custom Candidate and its original Raw/event evidence remain immutable.

### MX017/M1 final unreviewed Candidate diagnostic counts

| Historical Shadow category | Minutes |
|---|---:|
| Within proposed steady | 3,732 |
| Within proposed transition | 8 |
| New steady level to review | 289 |
| Steady deviation | 74 |
| Unexpected transition | 15 |
| Unsupported transition | 163 |
| Unsupported control context | 17 |
| Data unavailable | 22 |
| Total calendar minutes | 4,320 |

These counts describe proposal coverage/workload, not false-positive rate or certified normal operation. The manual QA reviewer accepted one supported regime solely to test immutable versioning, with an explicit unverified QA note and no Engineer evidence. The displayed original Candidate summary is labelled separately from the graph using the currently reviewed Reference version.

## Manual browser QA

All workflow actions below were performed through native browser controls/Playwright UI actions in the Codex in-app browser. HTTP/source scripts below are separate technical tests, not substitutes for these clicks.

| Case | Observed result |
|---|---|
| Machine first, 017/024 → M1–M8 | Final v4 minute graphs opened for all 16 selections; 1,440 day-minute records, fixed Pressure/Temperature/Valve panels. Both M7 show insufficient baseline evidence. |
| Raw investigation | 017/M1 29 Sep 23:25–23:45 rendered 1,183 source rows. Manual all-16 Raw navigation is not claimed. |
| Common Event History | Filtered 017/M1, historical SV, 29 Sep; exact ON 23:14:09 and OFF 23:34:53 with before/after values. OFF → common Raw 23:24–23:44 rendered 1,183 rows and pressure/temperature response. |
| Invalid Raw range, valid retry | Longer-than-30-minute selection shows Thai explanation and preserves old graph; restoring the same valid range refetches successfully. Tested again after final API restart. |
| Reference-only exclusion | Viewed 25 Sep 08:00–08:20 Raw (1,183 rows; 2 duplicate rows), added 08:00–08:01 with explicit QA reason. Draft survived reload, old graph remained, review was blocked until actual rebuild completed. |
| Shadow exclusion | Rejected with Reference-only explanation. |
| Immutable review | Empty acceptance remains ineligible; explicit QA note/one regime saved as version 1 then 2. No invented healthy/Engineer proof. |
| Stale-tab save | A second tab with version 1 could not overwrite version 2. Message requests refresh; refresh loaded version 2. Reload → reselect MX017 restored the saved reviewer/note/version 2. |
| Multiple tabs/machines | Three actual tabs inspected different machines/modules, with no review overwrite. This is not ten rendered browser tabs. |
| Prospective check | Actual click gives “ยังไม่มีข้อมูลใหม่ครบ 3 วันหลังทบทวน Reference จึงยังตรวจเพื่อเปิด Active ไม่ได้”. Approve remains disabled with readable missing contracts/Engineer/future evidence. |
| Active success / rollback | Covered by isolated SQLite fixtures. Successful real 017/024 activation/rollback remains untested and was not performed. |

Problems repaired during this run: delayed physical-response context loss; unsupported short-context/duplicate sample clustering failures; a one-module future result losing the other seven navigation entries; repeated large graph serialization; charts redrawing on every job poll; Raw same-range retries; stale-tab overwrite/reload behavior; initial machine overview accidentally rendering legacy calibration; pressure-unit configuration lost on restart; history filter details retained from a previous query; retained event opening a newly configured source.

## Technical QA and measured performance

- Final API suite: **199 passed**, 451 existing warnings, 19.23 seconds. Warnings are Python 3.12 SQLite datetime adapter deprecations and a joblib physical-core detection warning. Exact output: `notebooks/outputs/context_profile_uat_20261005/pytest-final.log`.
- Final TypeScript/project production build passed: 2,315 modules; JS 863.32 KB (gzip 245.85 KB), CSS 55.07 KB. The existing >500 KB bundle warning remains; measured graph-read improvements are not a bundle-size claim.
- Actual source SELECT reconciliation: 017 29 Sep 23:25–23:45 and 024 30 Sep 08:00–08:20, all eight modules. **320 exact minute-module quality/physical-value comparisons**; observed controls reconcile as an exact set (7 and 0 changes respectively), including before/after values and clocks.
- Bounded first graph/history/Raw reads with 10 concurrent clients: p95 **3,769.21 ms**. Some model/day reads were already opened by parity testing, so this is not a fully cold benchmark.
- Warm shared graph/history/Raw GETs: **10 clients, 120 requests, 120 HTTP 200**. p50 **42.25 ms**, p95 **86.98 ms**, max **123.44 ms**. HTTP response latency is distinct from browser rendering latency.
- Before the wire-cache repair, the same technical warm workload had p50 ~8.29 seconds and p95 ~18.06 seconds. Native JSON serialization once plus bounded gzip wire caching/coalescing eliminated repeated FastAPI traversal of roughly 2 MB graph responses. Typical compressed day transfer is about 175–209 KB. Internal mutable values stay isolated; inflight reads, wire-cache memory/entry count and Raw concurrency are bounded.
- Crash/retry/atomic-checkpoint, within-minute changes, gap/duplicates, immutable corrections, job coalescing, reviewer/CAS/idempotency, delayed response, unseen flat level, no Shadow refit, prospective navigation and private inbox cases are covered by the suite.
- Previously raw-parity checked known 057/M1 and 080/M6 archive cases still flag on the retained legacy/physical primary path (057 1,124 persistent minutes; 080 686 persistent minutes). **This does not validate the new v4 conditional model against those real cases.** That new-model replay and Engineer-reviewed normal cycles remain release gates.

### Local ledger / storage snapshot

Exact row counts after manual review: CONTROL/HISTORICAL **18,408**; DATA_QUALITY/HISTORICAL **84,759**; PHASE/SHADOW **20,896**; ANOMALY/SHADOW **5,611**; PROFILE/SHADOW **195**. Repeated preparations retain versioned derived interpretations, while historical source-control counts remain stable. Source control rows are unassessed occurrences, not 18,408 fault diagnoses.

MySQL `information_schema` estimates for the ledger: data **289,243,136 bytes**, indexes **90,046,464 bytes** (~362 MiB combined); day snapshots ~52 MiB and Candidate payloads ~3.5 MiB. Metadata row estimates differ from exact COUNT. Frequent commands and duplicate evidence make retention/partitioning and long-duration ingestion/storage benchmarking necessary before Server rollout. No storage-per-event guarantee is inferred from this mixed replay table.

Legacy Active: **46 rows**, SHA256 `3f2473685cfd3e16e99d6ccb117a970f2a7e4433dcb847d16af5a9767be85c21`, unchanged. Context Active: **0**. Source writes in this work: **0**.

## Local runbook / files

Additive analytics tables: `ht9046mx_events`, `ht9046mx_observed_day`, `ht9046mx_context_profile`, `ht9046mx_context_review_state`, `ht9046mx_context_active`, `ht9046mx_operational_event_receipt`. The explicit `python -m app.context_migrate` command is scoped to localhost and a separate Analytics schema; it creates no source tables. They are already installed locally. An authorized Server migration must be separately reviewed/applied in its target environment.

Backend: `observed_context.py`, `unified_events.py`, `context_storage.py`, `context_profiles.py`, `context_reference.py`, `context_request.py`, `context_review.py`, `context_reads.py`, `context_api.py`, `context_monitor.py`, `operational_inbox.py`, plus opt-in hooks in qualified detector/persistence/bridge and preparation jobs.

Frontend: `ContextCalibrationWorkspace.tsx`, `ContextChart.tsx`, `EventHistory.tsx`, `EventEvidence.tsx`, `context-types.ts`, and API/App wiring.

Routes below `/api/v1/calibration/context`: `/prepare`, `/latest`, `/jobs/{id}`, `/profiles/{id}` (model), `/profiles/{id}/day`, `/profiles/{id}/raw`, `/profiles/{id}/review`, `/profiles/{id}/readiness`, `/profiles/{id}/approve`, `/active`, `/active/{machine}/{module}/rollback`; unified `/api/v1/events`, `/api/v1/events/{event_id}`, `/api/v1/events/{event_id}/raw`. API health is `/health`.

Technical evidence: `notebooks/outputs/context_profile_uat_20261005/technical-qa.json`, `technical-before-wire-cache.json`, `final-state.json`, `legacy-known-case-regression.json`, `manual-qa.json`, `services.json`, service logs and screenshot files. HTTP/source parity script: `notebooks/support/context_profile_local_qa.py`.

## Remaining release gates

1. Verify psi basis, state-contract version, controller-codebook version and actual service epoch. Persist these verified contracts and prepare a new matching immutable Candidate.
2. Engineer review of retained Reference regimes/transition examples and independently observed normal/refrigeration performance. A low historical Shadow burden is not such evidence.
3. Actual untouched future source days after review, using frozen parameters; sufficient assessed coverage, unsupported contexts resolved and deviation budget passing.
4. Real v4 known-case replay/normal-cycle specificity, successful eligible real-machine Active/rollback, target authentication/concurrent approval handling and multi-tab Server UAT. A different-profile concurrent first activation can still surface a MySQL deadlock/unique-pointer error rather than a friendly conflict; pointers cannot both commit.
5. Connect the real operational producer/outbox, validate source clocks and telemetry mapping, enable detector/bridge deliberately, and verify end-to-end live transition/episode/notification/ACK/work/service history with retry and retention.
6. Cold preparation/source-revision, longer concurrent ingestion/storage and Server performance acceptance. Current source namespace guards do not make Raw immutable: Raw is a current read of the verified source; day snapshots/old event records remain immutable.

## Change log

- 5 October 2026: implemented and tested local conditional Candidate/review/event workflow, explicit analytics migration and actual 017/024 all-module preparations; repaired delayed response context and graph transport/manual UX. Real Active and live operational producer integration remain open as described above.
