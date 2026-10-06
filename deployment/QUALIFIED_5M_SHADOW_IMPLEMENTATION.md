# Qualified 5-minute scorer and EWMA/CUSUM shadow — implementation checkpoint


**2026-09-25 · Asia/Bangkok · development only, not a Server release**

## What runs now

The new path reads source MySQL through the configured source connection and constructs closed `[start,end)` five-minute windows from observed rows, expected at one-second cadence. It does not fill missing seconds. A window passes only with at least 95% occupied one-second bins, no observed gap above five seconds, no duplicate sample within one machine-second, finite seven physical sensor values, nonnegative Valve, and stable `Status=Run`, `Status_n=On`, `Busy_n=0`, `SV_n=Off` throughout. These literals and source timezone require source-owner verification on the Server. A failed window is `NOT_SCORED` with a reason, not `NORMAL`.

Known source machine aliases are normalized to `MXnnn` before grouping; if two aliases yield the same physical timestamp, the window fails as a duplicate instead of silently double-counting. Multiple Active pointers that collapse to the same canonical machine/module are excluded rather than arbitrarily selected.


For `qualified-cold-observed-5m-v1`, the 1 s / 95% / 5 s quality policy is fixed in code. Changing those three environment settings is rejected until a new feature/profile/threshold version is built; this prevents a quiet policy change under an old Active Profile. Candidate fitting requires explicit source-local naive `calibration_start < shadow_start < shadow_end`, excludes any later test rows and rejects duplicate window keys. The actual service epoch and source-clock semantics still need independent verification.

The pure scorer accepts only an exact-version, same-machine/module/SV/state profile with all nine finite median/scale values and a positive threshold. It computes signed `z_j=(x_j−median_j)/scale_j`, then primary `D=max_j|z_j|` and a raw flag for `D≥threshold`. Primary persistence becomes true on the third consecutive qualified five-minute window under the same versioned context. Gaps, invalid state/data and profile changes reset the run. Duplicates are idempotent; revisions and out-of-order windows abstain pending explicit replay.


## Runtime safety boundary


The old `python -m apps.api.app.inference` scheduled CLI now exits nonzero when guarded, so the scheduler cannot record a blocked no-write cycle as `CANDIDATE_CREATED`. Historical simulator/burst scripts that call the old inference function will also receive a blocked status until they are migrated to the new contract; they are not evidence of a working live scorer.


Read-only invocation on an environment configured for source and analytics MySQL:

```powershell
python -m apps.api.app.qualified_shadow_preview --machine MX080 --start "2026-09-21T02:00:00+07:00" --end "2026-09-21T03:20:00+07:00"
```


## Code and QA

| File | Responsibility |
|---|---|
| `apps/api/app/qualified_windows.py` | Observed-second quality/state gate and shared five-minute feature contract |
| `apps/api/app/qualified_calibration.py` | Bounded read-only intake and past-only immutable candidate calculation; no registry writes |
| `apps/api/app/qualified_scoring.py` | Exact-profile primary robust-z/persistence and shadow EWMA/CUSUM; restart checkpoint serialization |
| `apps/api/app/qualified_temporal_fit.py` | Separate-block temporal candidate limits; no automatic activation |
| `apps/api/app/qualified_shadow_preview.py` | Strict Active-profile lookup and read-only diagnostic CLI |
| `apps/api/app/inference.py` | Blocks the old mutating raw-row route; opt-in preview still has no writes |
| `apps/api/tests/test_qualified_temporal.py` | Window, state, split, reset, idempotency, checkpoint and no-write boundary tests |


## Still required before Server launch

1. Confirm source timezone, units, tag literals, one-second cadence and late-arrival distribution with source owner. Benchmark full day/machine chunks on target Server.
2. Freeze an exact five-minute candidate manifest from past-only data; review contamination/service boundaries, at least three future shadow days, alert budget and graph; create immutable registry artifact and authenticated **human** approval with rollback pointer. No automatic `ACTIVE_FROZEN` promotion.
3. Build atomic analytics score/checkpoint/episode persistence with unique machine/module/window/context/version key; test crash/replay/late correction and migration rollback. Current checkpoint is an in-memory serializable object, not durable storage.
4. Run matched offline temporal-vs-primary replay using a new untouched time block, then fresh prospective Server shadow. Evaluate flags and episodes per qualified machine-day, temporal-only burden, worst module and latency. No fault recall/precision without confirmed labels.
5. Conduct security, source-read-only role, rollback and operational review for score or alert writes. The current code has no production scoring switch for this path.


**Change log:** 2026-09-25 — Added deterministic qualified-window, strict scorer, shadow temporal engine/fit, read-only preview and default block of the legacy raw-row mutating path. No Server deployment, schema migration, profile approval or database write was performed for this change.
