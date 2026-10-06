# HONTECH HT9046-MX — Server Shadow Deployment Handoff

> **2026-09-25 release blocker:** The selected calibration/scoring feature contract is now strict observed-second → completed one-minute Cold. Candidate registry and future three-day shadow wiring are implemented, but inference is read-only preview; no operational Health/PM alert write is authorized. Existing 5m/minute-snapshot Active Profiles are incompatible. Before setup, read `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`; older cadence/production wording below is historical.

**Status:** integration-ready package with production blockers
**Mode:** shadow screening only; no PLC/control write path
**Selected next scoring policy (2026-09-25):** Active-Profile robust-z rule only; see `deployment/RULE_ONLY_ACTIVE_PROFILE_PIPELINE.md`. The current worker already uses that family, but its raw-row/5-minute parity and other production gates remain open.
**Historical ARX replay artifact (research only):** `notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/`

For a beginner-oriented end-to-end diagram and explanation, read `deployment/SYSTEM_DEPLOYMENT_FLOW.md` before implementing the components below.
For the exact Codex-on-Server starting prompt, environment audit and Definition of Done, use `deployment/CODEX_SERVER_HANDOFF.md`.
For the owner-specified ML analytics MySQL target `10.195.17.73`, schema setup, privilege boundary and acceptance checklist, use `deployment/README_ML_ANALYTICS_DATABASE_10.195.17.73.md`.

## New Cold-only candidate — offline experiment, not Active Profile scoring

**2026-09-25 matched-lane warning:** A same-row offline replay of frozen v2 Self robust-z and Cold ARX found only 451 ARX-only raw flags across 121,492 previously inspected development outer windows and no ARX-only MX080/M6 windows under a four-day forensic profile. The diagnostic OR also opens more episodes than Self alone (641 versus 595). These observations neither justify disabling the simple rule nor enabling ARX live alerts: the compared profiles are offline train-only, not approved MySQL `ACTIVE_FROZEN`, and no fresh prospective release test has run. See `notebooks/outputs/ht9046mx_rule_arx_matched_v1/README.md`; keep the v2 model shadow-only and resolve parity, burden, timezone, unit, approval and rollback gates before server wiring.



The selected operational order is **raw data → Data/State Gate → Auto-calibration candidate → three-day forward shadow → human approval to `ACTIVE_FROZEN` → rule-only score on new qualified data**. The 2026-09-24 ARX experiment stops before the Active-Profile boundary: it fits profiles from historical training rows solely for research and does not read, approve or change MySQL Active Profiles.

Rebuild the candidate only where the local controlled minute cache exists:

```powershell
py -3 -X utf8 -m notebooks.support.phase7_cold_candidate
```

Check the portable model and profile hashes without MySQL access:

```powershell
py -3 -m apps.api.app.model_bundle --cold-candidate-manifest notebooks/outputs/ht9046mx_phase7_cold_candidate_v1/candidate_manifest.json
```


## What the server should do

```text
MySQL sensor rows
→ schema/time/unit checks
→ state qualification
→ completed qualified five-minute features (target contract)
→ exact active-profile/feature/threshold version checks
→ max-absolute robust-z shadow score from the approved local profile only
→ 3 qualified five-minute windows persistence
→ append-only shadow score/alert/evidence tables
→ Web App read-only presentation
```

## Architecture extension under design — Four evidence

The owner selected the **Self/local-baseline lane alone** for the current scoring path. Dynamic/ARX, Peer and other model families remain offline research, with no alert or Health Score vote. Temporal persistence follows the rule score. Any future fusion is a separately versioned and validated change, not part of this Server handoff.



## Historical ARX package — inspection only, not the first server integration scorer

The historical package can now be checked without connecting to MySQL:

```powershell
py -3 -m apps.api.app.model_bundle --manifest notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/shadow_release_manifest.json --registry notebooks/outputs/ht9046mx_phase7_benchmark_v2_hp180/shadow_model_registry.json
```

Expected status is `LOADED_SHADOW_ONLY` with `live_eligible: false`. The API image must install `joblib`, `scikit-learn` and `polars` from `apps/api/requirements.txt`. Only load a trusted, project-controlled joblib file; its checksum is checked against the local manifest, not against an external signature. Loading this artifact does **not** connect it to the live worker, approve a profile or validate the newer Cold-only relationship-feature contract. New live robust-z rows use `robust-z-envelope-v1`; historical mislabeled rows are retained for audit.

Read `shadow_release_manifest.json` before loading any artifact. The current locked values are:

- model: `ARX-Ridge__seed_13`
- model selection: inner temporal validation only
- qualified `Hp_2nd` field-reference band: 180–230 psi
- low-side feature: `max(0, 180-Hp_2nd)/10`; values at or above 180 add no undercharge contribution
- threshold: 7.650715626730769, from separate past calibration q99.5 under the hp180 feature contract
- scoring cadence: 5 minutes
- persistence: 3 consecutive qualified windows
- capability: anomaly screening only
- activation: `SHADOW_ONLY_NOT_AUTHORIZED`
- automatic profile activation: false
- calibration rollback: first human-approved profile can return to the explicit `NO_ACTIVE_PROFILE_FAIL_CLOSED` mode; later promotion points to the previous `ACTIVE_FROZEN` profile


## Required environment variables


```text
# Raw telemetry source: read-only
HT9046MX_SOURCE_DB_HOST=
HT9046MX_SOURCE_DB_PORT=3306
HT9046MX_SOURCE_DB_NAME=
HT9046MX_SOURCE_DB_USER=
HT9046MX_SOURCE_DB_PASSWORD=
HT9046MX_SOURCE_TABLE=
HT9046MX_TIMESTAMP_COLUMN=
HT9046MX_MACHINE_COLUMN=

# Append-only ML analytics output
HT9046MX_ANALYTICS_DB_HOST=10.195.17.73
HT9046MX_ANALYTICS_DB_PORT=3306
HT9046MX_ANALYTICS_DB_NAME=ht9046mx_analytics
HT9046MX_ANALYTICS_DB_USER=
HT9046MX_ANALYTICS_DB_PASSWORD=
HT9046MX_PROJECT_ROOT=
HT9046MX_RELEASE_MANIFEST=notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/shadow_release_manifest.json
```

The local analysis environment cannot validate the real MySQL host, source table or credentials. The server owner must map the source columns to the canonical contract before enabling the worker.

## Canonical input contract

Each source record must resolve to:

```text
machine_number, timestamp, global_status,
module, module_status, sv, busy,
hp1, lp1, hp2, lp2, valve, temphi, templo
```

Minimum checks before feature calculation:

- machine/module/timestamp key is unique or has a deterministic upstream revision key
- timestamp is monotonic per machine and module
- timezone and pressure unit are explicitly configured
- required pressure, valve and state fields are present
- stale, late or out-of-order data are quarantined
- `Busy_n` is treated as an unresolved controller flag, not motor feedback
- MValveHome, negative valve command, ChangeValve/control sequence, Emergency Down and mixed-state windows are not steady baseline data

## Output tables


Recommended UI query flow:

1. latest `shadow_score` per machine/module
2. open `shadow_alert_episode`
3. evidence rows linked by `score_id` and release version
4. `DATA_QUALITY` and contract failures shown separately from equipment screening

## Safe failure behavior

| Failure | Required server behavior |
|---|---|
| feature version/order mismatch | reject batch and record audit event |
| model checksum mismatch | refuse model load |
| worker restart | restore checkpoint and reproduce one-shot persistence state |
| release/rollback version missing | keep new release blocked |

## MX-080 acceptance probe

Use MX-080 Module 6 only as an offline replay fixture:

- expected observed transition: 2026-09-07 12:23:20, timezone still assumed
- expected first persistent shadow detection: 2026-09-07 12:35:00
- descriptive delay from the observed pressure transition: approximately 11 minutes 40 seconds
- raw deviation flags occur before 12:23:20; treat them as possible precursor/profile mismatch, not validated lead time
- expected raw flag rate in this fixture: 3.0% before the transition and 100% after the transition; this is one-fixture sensitivity evidence, not accuracy
- reference profile status: `INCIDENT_REPLAY_ONLY_INSUFFICIENT_FOR_PRODUCTION`

The fixture proves deterministic incident sensitivity for this episode. It does not prove the cause or model recall.

## Server acceptance checks

- [ ] Source-to-canonical mapping is signed by server owner and data/ML reviewer
- [ ] Unit and timezone are verified against historian/controller configuration
- [ ] Backfill and late-arrival rules are tested
- [ ] Model checksum and feature order fail closed
- [ ] One-shot and restart/checkpoint outputs match
- [ ] Database writes are idempotent and append-only
- [ ] Missing/stale records cannot produce equipment alerts
- [ ] MX-080 offline fixture reproduces the expected timestamp and score path
- [ ] Alert budget is approved per machine/day and worst machine is reviewed
- [ ] Previous `ACTIVE_FROZEN` release exists as exact rollback target
- [ ] Web App clearly says “Shadow screening — not confirmed diagnosis”
- [ ] No analytics component can write PLC or safety commands

Until every item is complete, the deployment verdict remains `SHADOW_ONLY_NOT_AUTHORIZED`.

## Change log

- 2026-09-25 — Superseded the planned ARX first-integration scorer with owner-selected Active-Profile robust-z rule only. Linked the implementation-faithful pipeline and retained ARX packages as historical research; raw-row scoring and approval/security gaps still block production.

- 2026-09-25 — Added matched rule/ARX replay caveats for Server handoff; no model, runtime scoring or alert enablement changed.

- 2026-09-24 — Added the past-only profile-readiness evidence and explicit no-auto-rebase warning for `ChangeValve` markers; server activation remains blocked.

- 2026-09-24 — Documented the new offline Cold-only ARX candidate and its loader/QA commands, explicitly distinguishing train-only development profiles from approved MySQL Active Profiles. Excessive Self/valve flags keep it review-required; no live inference path changed.

- 2026-09-24 — Added the isolated model-load/checksum/feature-order smoke command and clarified that it is shadow-only, not live scoring or activation.

- 2026-09-15 — Added the Server-ready read-only historical calibration worker, immutable registry and 3-day shadow review graph. It remains unexecuted against any Server/MySQL host.
- 2026-09-15 — Added the fail-closed `DATETIME(6)` timezone requirement to the prospective confirmation contract; no server or database was operated.
- 2026-09-15 — Replaced the planned cause-feedback path with a prospective binary confirmation contract. It is separate from the locked release and blocked until Server time policy, feedback boundary and Label QA are operational.

- 2026-09-15 — Documented the system-only Four-evidence architecture extension as a future, separately versioned candidate. The locked ARX-Ridge shadow package and all deployment blockers are unchanged.

- 2026-09-14 — Linked the dedicated analytics-database guide and split source read-only versus analytics append-only environment variables. No host connection or live deployment was performed.

- 2026-09-11 — Linked the curated Codex Server handoff and kept the live deployment/approval state unchanged.

- 2026-09-11 — Linked the beginner deployment flow covering the read-only machine boundary, dual-rate processing, evidence path, technician feedback and release gates. No server service or production authorization is implied.

- 2026-09-10 — Switched the staging handoff to release v2/hp180, updated the manifest path and calibrated threshold, and explicitly blocked mixing the historical 200-psi feature/model/threshold contract with the current release.
