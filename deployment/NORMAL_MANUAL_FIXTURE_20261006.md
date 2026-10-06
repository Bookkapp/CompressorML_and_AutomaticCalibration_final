# MX058/M1 — restore the standard manual workflow

6 October 2026, Asia/Bangkok. This supersedes the temporary full three-day Mock approval experiment.

## Owner correction and result

The owner requested removal of the added Mock interface/approval flow and only additional Normal source values through the real current time, so they can operate the existing manual workflow themselves.

- Removed the trial component, Active test list, client methods/types/styles, API routes, feature flag, special approval gate and virtual clock. Removed the trial seeder/verifier and dedicated trial tests.
- Removed the actual MX058/M1 test Active pointer and its one copied synthetic Profile. The original frozen Reference/reviewer record was preserved.
- Backed up and removed exactly 259,260 future second rows, 7–10 October, IDs 73704392–73963651. Removed the exact synthetic trial record/table and archived old Mock interim job `ccb29671-cec0-457b-8ebb-59f171d00d5b` before removal, so it cannot appear as a current result.
- Kept 15,420 elapsed fixture rows with their sensor values; changed only their synthetic global Status to `Run` for the requested standard numerical test. Added 5,640 elapsed seconds and a further 480 seconds through the current closed minute.
- Current fixture: **6 October 08:05:00–14:03:59, 21,540 unique seconds / 359 minutes**, MX058/M1 only. Global `Run`, module `On`, Busy `0`, SV `Off`, Valve `100`; M2–M8 remain NULL in these generated rows. Physical pressure/temperature values use fixed small correlated variation around an accepted frozen OFF regime. Delta pressures are derived. There is no Reference refitting.
- Synthetic provenance remains in `ht9046mx_local_mock_batch`; raw `Run` is an operating-state test input, not evidence that a physical machine was inspected/certified healthy. Existing source contracts/Engineer/prospective approval requirements remain unchanged.
- Existing common audit events are retained with `MOCK_TRIAL_REMOVED` appended. Source/metadata removal, same-day conversion, initial continuation and receipt/audit commit atomically on the localhost MySQL instance. No real source row is deleted or overwritten; each continuation refuses interval overlap.

## Verification

- The correction restored the exact pre-trial registry hashes/counts: legacy207 Profiles/46 Active; Context110 Profiles/0 Active; import receipts567. The original frozen MX058/M1 Profile is unchanged.
- Actual source audit: all fixture seconds unique, expected Normal control fields present; no future MX058 timestamp. The standard source/minute/evaluator pipeline samples Normal successfully. The 351-minute initial correction numerical probe has zero flags; the eight-minute continuation uses the same deterministic generator.
- Standard followup GET: correct Bangkok review time, actual source latest, no clock error, **can inspect**, no saved stale Mock job. No `/local-mock` OpenAPI routes remain.
- 27 focused API regressions pass. TypeScript and production Vite build pass. Existing large-bundle advisory remains.
- Actual browser: standard MX058/M1 Calibration/reviewer2017876 restored; no trial/TEST MODE/Mock UI. Inspection and approval buttons were left for the owner; no new preparation/review/inspection/approval was clicked after the correction.

## Real timing

The existing Reference was frozen **6 October 08:04:35**. These elapsed rows are the same review day. They are available for interim manual inspection, while completed prospective approval days remain **0/3**, with the first eligible day **7 October**. Restoring the real clock cannot honestly turn today's rows into three completed future days. Included SV ON Reference and other existing source prerequisites are still the owner's standard review items.

## Evidence and recovery

- `notebooks/outputs/normal_manual_20261006/receipt.json`, `verification.json`, registry snapshots and the standard-browser screenshot.
- Exact future raw-row gzip backup and metadata backup in the same directory; retained original batch receipts and correction/continuation ledger records. IDs are not reset/reused.
- `notebooks/support/correct_local_normal_fixture.py`: plan-only default; `--apply` performs the exact backed-up correction. `--extend --apply` is a bounded, explicit elapsed continuation, with no running generator or web button. It refuses remote SQL, active worker/bridge/alerts, future dates and existing-row overlap.
- `notebooks/support/verify_normal_manual_fixture.py`: source/gate audit, never clicks the owner's workflow.

API8000 and web5176 run locally. Worker, bridge and alerts remain disabled. No Server10.195.17.73 change, deployment, commit or push occurred. Do not carry these localhost synthetic source rows into production training/certification; use the batch receipts to identify them when returning to real telemetry.
