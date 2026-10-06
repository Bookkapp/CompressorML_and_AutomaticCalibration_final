# Explicit SV scope and Coverage — local UAT, 6 October 2026

## Owner-authorized change

An Active frozen conditional Profile may cover only SV OFF or only SV ON when that is its reviewed scope. Missing Reference for the other state need not block creation. The excluded state is explicitly **NOT_EVALUATED**, never inferred Healthy. At least one state must remain selected, and an exclusion requires a recorded reason. This implements the owner's latest direction; it supersedes any earlier requirement to obtain Reference for every SV state before approval.

Scope is per immutable Machine × Module Profile, not a fleet-wide checkbox. A valid Reference and the existing evidence/approval gates are still required for each included state. Existing unscoped profiles retain their previous semantics. The frozen Fleet Stable bundle remains a separate Shadow Candidate and was not retrained or activated by this change.

## Policy and implementation

`explicit-sv-evaluation-scope-v1` records included/excluded states, exclusion reason, retained-data policy and unknown-state behavior in `reference_review.evaluation_scope`. Review changes create a new immutable model ID and clear prospective validation. Validation receipts fingerprint the scope; changing it requires validation of the newly frozen version.

- `context_scope.py`: canonical scope, covered-state summary and validation accounting.
- `context_profiles.py`: excluded-state gate before vectors, scores and envelopes; analysis copies prevent excluded observations entering stability or phase matching. Original physical/control witnesses remain returned and stored.
- `context_review.py`: included-state Reference, policy receipt, Engineer/contracts/future coverage checks; existing revision CAS and immutable review lifecycle.
- `context_reference.py`: future validation counts evaluated, intentionally excluded and unresolved periods separately. A period consisting only of excluded observations cannot pass.
- `context_monitor.py`: excluded assessment is NOT_EVALUATED in the common event ledger, not an anomaly or healthy event. Exclusion does not close a previous alert or establish recovery.
- `context_coverage.py` / `context_api.py`: eight-module Coverage endpoint, fresh reviewer/Active pointer metadata, bulk immutable summaries with bounded shared cache. It reads no source telemetry and performs no model fitting.
- `ContextCoveragePanel.tsx`: eight rows, SV OFF/SV ON/Active state, Reference counts and explicit reason. Legacy saved candidates show proposed-regime coverage, not invented total observed coverage.
- `ContextCalibrationWorkspace.tsx`: scope checkboxes, reason, selection filtering, dirty-review guard, saved policy restoration and reviewer/model-specific draft hydration. Mutations are disabled during reviewer/model hydration. Selected Reference is never auto-certified.
- `FleetStablePanel.tsx` / `fleet_stable.py`: read-only OFF/ON availability matrix from the frozen bundle. Frozen Shadow Reference availability is distinct from an approved local Active scope.

On returning from an excluded SV state, a supported reviewed local steady Reference evaluates the first included minute immediately. No fixed 5–10 minute suppression is added. A delayed pressure/thermal abnormality still becomes deviation/new steady level and remains unresolved until reviewed. Unknown controls and data quality failures retain their existing non-evaluated categories; the SV scope does not convert them to Normal.

## Manual browser workflow

Local Operation: `http://127.0.0.1:5176/`, API `127.0.0.1:8000`; current source-local timezone Asia/Bangkok. Prepared context jobs:

| Machine | Job | Reference / Shadow |
|---|---|---|
| MX017 | `65653574-57c3-40ee-af24-8dc202c972ac` | 31 Aug–27 Sep / 28–30 Sep 2026 |
| MX024 | `2aea7f32-61b6-417d-ae14-580fe84e7fdb` | 31 Aug–27 Sep / 28–30 Sep 2026 |

Actual browser clicks used the separate reviewer `ScopeManualQA_20261006`. This actor's note explicitly says the review is technical QA and **not Engineer-certified healthy evidence**; the Engineer evidence field stayed empty.

1. Open MX017/M1 and a Reference example graph. Uncheck SV ON; check one supported OFF regime for technical QA. Leaving the reason blank disables Save. The last remaining state cannot be unchecked.
2. Enter the real reason: ON Reference has only three proposed days and no supported regime. Save through the browser creates reviewed Profile `65a3e0210722f339c00ee6fc8118e4f7c093e5f7a158a679150aec6526a61416`, revision 1.
3. An already-open tab tries a different reason at revision 0: visibly rejected with the Thai another-tab message; it does not overwrite revision 1.
4. Reload, choose MX017: OFF scope, ON exclusion and saved reason restore. Coverage shows one recorded OFF regime and ON intentionally excluded, still not Active.
5. Open an ON Reference example on 10 Sep, then click its excluded boundary's **ดู Raw**. The 07:14–07:34 raw view renders 1,188 rows, with 54 duplicate rows identified. Raw/control evidence remains accessible. Read-only API verification finds 273 STATE_GATE_EXCLUDED minutes that day, with no steady/transition scores, main evidence or envelopes.
6. Check ON again without saving: validation and Approve are disabled. Restore the saved OFF-only selection.
7. Switch to new actor `ScopeIsolationQA_20261006`: no accepted regimes or note are inherited. Return to the saved technical QA actor. Draft persistence cannot run against a different reviewer/model identity during hydration.
8. In the second tab open MX024/M7: no supported Reference; Approve remains disabled. Change to M2 independently; the MX017 tab retains its own model and graph context.
9. At the actual narrow 447 px viewport, fix checkbox width/text wrapping found by screenshot inspection. Final document scroll width equals viewport width (447 px), with no horizontal overflow. No chart Loading text was introduced, and fixed chart slots remain. Main tab has no browser error logs.

The spare QA tab was closed; the main Operation Calibration page is retained. Screenshot: `notebooks/outputs/context_scope_20261006/sv-scope-manual.png`.

## Test and performance evidence

- Full API suite: **237 passed**, 451 existing warnings, 86.59 seconds.
- New scope-focused cases: **9 passed**. Included-state Reference/contract gates, missing/invalid scope, validation fingerprint and all-excluded coverage, no excluded-state vector/model calls, immediate OFF normal/deviation/new-level detection, bad quality/unknown controls, stale CAS, 16 concurrent deterministic scoring calls, reviewer Coverage isolation, and isolated scoped Active + common-ledger NOT_EVALUATED path.
- Final TypeScript check and Vite production build pass. Existing bundle warning remains: main JS approximately 894 kB / 253 kB gzip; this change is not a code-splitting claim.
- Actual prepared Coverage/day GET load: **10 clients, 120/120 success, 18 distinct views**, correct machine/module isolation. After the web build, warm p50 **506.1 ms**, p95 **680.1 ms**, maximum **885.4 ms**. The first run while build/UI work overlapped recorded p95 **932.3 ms**, maximum **1,464.3 ms**, also 120/120 success. Both receipts retained.
- These are prepared HTTP reads; neither cold source preparation nor rendered-browser latency is included. No blanket production throughput or latency guarantee follows.
- Registry before/after exactly matches: legacy Profiles 207, Active pointers 46, Context Active 0, import receipts 567. Canonical hashes are in receipts. Only the separate technical QA actor's immutable context review metadata was added.

Evidence directory: `notebooks/outputs/context_scope_20261006/` (`registry-before.json`, `registry-after.json`, `http-qa.json`, `http-qa-during-build.json`, `reviewed-scopes.json`, screenshot). Read-only reproducible GET/load helper: `python -m notebooks.support.context_scope_qa before|after`; review actions themselves were manual browser clicks.

## Use and release scope

1. Select Machine, Module and inspect physical/control Reference and Raw.
2. Include states the Engineer can support; explicitly exclude any other SV state with a reason.
3. Save a versioned Reference review with actual evidence. Changes to selection/scope invalidate downstream validation until saved.
4. Validate new data under that frozen scope. Excluded SV minutes have their own count; only included evaluable coverage contributes to minimum days/minutes and flag rate. Included unresolved regimes still require review.
5. Approve the ready frozen version; the excluded state abstains during runtime, including common-ledger provenance. Expansion to ON is a new reviewed/validated version with normal CAS/rollback lifecycle.

The actual MX017 QA reviewed version is correctly **not ready**: four source contracts (state, Controller, service epoch, psig/psia), Engineer evidence and prospective validation remain outstanding. Removing ON alone does not manufacture any of those. Successful scoped activation/runtime was exercised in isolated fixtures; no real Context Profile was activated. Legacy 46 pointers, source rows, import state, thresholds and Fleet model bundle were preserved. No target Server installation, live producer/worker launch, SQL Fleet-event backfill or Git push occurred. The server/producer/future-data acceptance tasks remain in Roadmap.
