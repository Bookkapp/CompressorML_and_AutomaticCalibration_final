# Compressor context profiles and unified event history

Date: 5 October 2026 (Asia/Bangkok). Status: agreed requirements with local implementation checkpoint below; not a production model release.

## Local implementation checkpoint

Conditional Candidates/reviews/prospective gates, all-state snapshots, six additive analytics tables and historical observed control/derived event storage are now implemented in Operation. Final v4 all8 profiles for017/024, actual manual minute/exclusion/reload/stale-tab/commonSVRaw QA,199APItests/build,320exactparity and120warmGETs pass. Existing46Active unchanged; ContextActive0. Actual PM ACK/work/service producer connection, continuous live worker/Server UAT, real conditional known-case/Engineer-reviewed healthy examples, verified source contracts and untouched future validation remain open. Read the full scope/results/runbook: `COMPRESSOR_CONTEXT_PROFILE_UAT_20261005.md`. The requirements below remain the acceptance contract; the earlier plan-only change-log entry is historical.

## Owner decisions

The owner describes the Compressor modules as cascade refrigeration with Valve control. A new steady operating level after control changes can be an acceptable regime. Returning to the old numerical baseline is therefore not a universal steady-entry requirement. Compare levels and relationships against the appropriate reviewed regime. Flat measurements alone do not establish normal operation; controller compensation and unobserved load changes remain possible.

The owner additionally requires **one common event table containing every observed Transition and anomaly-related event**, to make later investigation straightforward. Archive normal and unresolved transitions as well as unusual ones. This is an addition to the proposed context-aware Calibration/Shadow workflow, not a request to classify every event as an anomaly.

## Model and workflow direction

1. Separate all-state measurement quality from fit/score eligibility. Preserve available physical measurements, source state values, raw event witnesses and coverage even when a minute is not eligible for the current Cold profile. The current `qualified-cold-observed-1m-v1` path does not provide this separation; introduce a versioned path rather than reinterpret old stored profiles.
2. Build per-machine/module steady profiles for supported operating regimes and separate event-conditioned transition profiles. Distinguish ordinary expansion-valve command changes, observed ChangeValve/manual operations, SV bypass changes and observed Run/module-state entry. Do not assign motor-start, service completion or healthy labels from a control tag alone.
3. Propose regimes and Reference intervals automatically from past-only data. Human review establishes accepted operating examples; a previously unseen steady level remains a proposed regime. Do not select intervals or change thresholds merely to reduce the inspected Shadow burden. Avoid a separate profile for every numerical Valve command; retain individual command changes in the event ledger regardless of model grouping.
4. Explain Shadow as supported steady behavior, supported transition behavior, unexpected response, proposed new regime, or insufficient evidence. Keep original steady deviation evidence and category-specific denominators alongside the applicable phase/regime assessment.
5. Use the current telemetry first. Setpoint/recipe/load/facility-water context can strengthen discrimination when actually available. Current temperature tags do not establish DUT target achievement or valid suction superheat by themselves. Do not fabricate these inputs or make missing ones a claim of healthy performance.
6. Share streamed machine intake and daily summaries across M1–M8 and callers. Use bounded Raw queries, reusable graph summaries, durable/coalesced jobs and protected reviewer drafts. Validate known MX057/M1 and MX080/M6 cases, reviewed normal events, whole-cycle/day splits, untouched future periods and actual browser/multiple-tab operation before selecting a release.

## One common event table

Working table name: `ht9046mx_events` in the analytics database. One row is an **event occurrence or lifecycle change**, not a raw measurement row. An episode/transition may have several ledger rows linked by a common correlation ID. Append new lifecycle records so onset, review, recovery and notification history remain inspectable. Current episode/alert/work-order tables can continue to serve their existing functions, with their records referenced from this one central history table.

### Event families

| Family | Events to archive |
|---|---|
| Observed control/state | Every observed change of Valve command, SV, compressor/module state and Busy; observed ChangeValve and homing entry/exit. Store original before/after codes and timestamps. |
| Derived phase | Transition entry, phase changes, steady entry, unusual response, unresolved/censored end. Include the policy/model version and evidence establishing each boundary. |
| Anomaly evidence | Detection, continuation/reopening, recovery evidence, unknown/interrupted end and explicit review outcome, linked to the original episode and frozen profile. |
| Notification | Alert creation, suppression, delivery/failure, acknowledgement and closure, linked to the event/episode that caused it. |
| Operational context | Work-order creation/start/completion and service-log creation/update, when provided by the existing operational system; store references and occurrence times without inferring healthy recovery from DONE. |
| Profile lifecycle | Candidate creation, Shadow completion, review, approval, activation and rollback, with the relevant profile/run/version and actor. |
| Data availability | Observed data gap, resumption, duplicate/conflicting timestamp evidence, unknown state and late-data/replay correction affecting event interpretation. |

Normal, unusual and unassessed transitions all remain in the common table. Model thresholds, notification cooldowns and dashboard severity filters must not silently discard observed control changes. Never manufacture transitions across missing data or unknown order. A machine-level state change is recorded once at machine scope; module responses link to it instead of presenting eight independent machine events.

### Common searchable fields

- Stable `event_id`, schema/event-policy version and `event_type`/family.
- Canonical machine ID, nullable module for machine-wide events, component scope and shared correlation/parent event IDs.
- Source occurrence timestamp with its declared timezone/precision, normalized UTC timestamp only when the source clock is verified, plus separate detection/recording times. Unknown occurrence time or clock stays explicit; ingestion time must not substitute for it.
- Lifecycle/classification/severity fields. Unassessed events remain explicit; an observed Valve change carries no automatic anomaly or normal-health label.
- Source identity and deterministic idempotency key; producer/environment, historical/live/Shadow mode, dataset and run IDs. Historical replay must be distinguishable from live events.
- Before/after values, source codes, relevant pressure/temperature snapshot and units, observed coverage, and evidence interval/source references.
- Profile/model/parameter versions used for any interpretation, and links to episode, PM Alert, work order, service log and profile IDs with their actual source-system identity.
- Actor, review reason and structured `details_json` for family-specific information. Frequently filtered fields remain normal columns rather than JSON-only fields.

Raw data remains in its source/evidence storage. Event records point to the relevant before/after interval and state witnesses rather than copy unlimited Raw into every row. Evidence availability and retention must be visible; a retained event row must not imply that all associated Raw is still available.

### Reliability and throughput

- Capture observed control transitions in the common streamed source pass before Cold/fit eligibility filtering. Minute-only comparisons are insufficient for multiple changes within one minute. Retain every observed change, including normal commands; preserve duplicate/conflicting observations as quality evidence rather than inventing a unique ordered transition.
- Commit local event writes and the corresponding source checkpoint atomically. Deterministic keys prevent duplicate events on retry or when multiple tabs attach to one preparation job.
- Integrate operational-system events through durable outbox/inbox delivery or another verifiable retry mechanism. A cross-database distributed transaction is not assumed. Eventual delivery status and retry failures must be inspectable.
- Reinterpretation/late data appends a correction/superseding event with its policy and source revision. Preserve the original recorded decision and its evidence; do not overwrite historical boundaries silently.
- Index machine/module + occurrence time + stable event ID, and family/type + occurrence time for common queries. Use bounded batches, keyset pagination, daily event counts and bounded correlation lookups. Measure storage and write throughput for frequent Valve commands before choosing partitioning/retention settings.
- Historical backfill uses checkpointed bounded day/machine batches with provenance and idempotency. It generates historical records, not live notifications. Missing source observations remain explicit.

## Investigation experience

Provide a unified Event History view/filter: machine -> module or machine scope -> date range -> event type -> assessment -> historical/live mode. Its default timeline shows control actions, physical response/phase, anomaly evidence and related operational events in source-time order where the clock is known. Detail opens the common historical investigation graph with Raw coverage, before/after markers, applicable baseline/phase envelope and related event links.

This does not reinstate the removed graph widgets in Alerts, Maintenance or Logs. Those existing pages may link to the common event/investigation view while keeping their agreed layout.

## Acceptance evidence

1. Reconcile a source-second fixture and actual selected windows against all observed Valve/SV/state/Busy changes, including several changes within a minute and transitions with no anomaly. Confirm before/after codes, exact observed clocks and appropriate gap/duplicate handling.
2. Demonstrate unified queries retrieving a correlated transition, anomaly, recovery and notification/operational history. Confirm cooldown, acknowledgement and closure preserve history.
3. Demonstrate crash/retry/restart and concurrent-caller idempotency; commit rollback must not advance a checkpoint without its event records. Demonstrate operational event delivery retry and correction provenance.
4. Keep machine-global events distinct from module responses and historical/Shadow/replay events distinct from live occurrences. Verify real source IDs rather than equating numeric IDs from different databases.
5. Measure ingestion/write/storage costs and history/Raw query p50/p95 with concurrent preparation, multiple tabs and multiple machines. Publish the tested scope and observed results; no latency guarantee is assumed from earlier smaller benchmarks.
6. Verify the existing known anomaly cases remain visible when phase/regime classification is introduced. Confirm proposed/unsupported regimes do not become accepted normal automatically.

## Delivery order

1. Finalize event contract and migration design together with all-state measurement transport.
2. Add observed-transition capture, common event persistence and idempotent bounded historical backfill.
3. Integrate anomaly/episode and profile lifecycle events; connect notification/operational producers with reliable delivery.
4. Add conditional steady/transition Candidates and explainable Shadow categories.
5. Add unified history/investigation UX and complete actual manual browser/load/regression QA.
6. Release the validated version with reviewed Active selection and rollback. Pressure-basis, state/controller/service contracts remain independent approval requirements.

## Change log

- 5 October 2026: local implementation/migration/backfill/manual QA checkpoint added. Production/operational producer/eligible real Active acceptance remains open; see the linked UAT report.

- 5 October 2026: recorded the owner's clarification on acceptable new steady regimes and the requirement for one unified event table retaining all transitions, including normal ones. Planning document and checkpoints only; runtime event storage, migration and backfill are not implemented by this entry.
