# Web App QA Report

**Date:** 2026-09-15
**Scope:** Local/demo verification of the FastAPI + React/Vite application
**Verdict:** `PASS_WITH_PRODUCTION_BLOCKERS`

## Evidence and data boundary

- Demo input: verified Phase 7 hp180 replay artifacts under `notebooks/outputs/ht9046mx_phase7_shadow_replay_v2_hp180/`
- Primary score grain: one row per machine–module–SV at the locked 5-minute scoring point
- MX-080 graph grain: 5-minute replay fixture derived from the one-second incident analysis
- Source timezone: unverified; the UI and API state this limitation
- Pressure unit and live tag mapping: must be confirmed on the Server before live acceptance
- Demo technician-confirmation writes: rejected by design

## Automated checks

| Check | Result |
|---|---|
| FastAPI/contract tests | PASS — 8/8 |
| Dashboard refresh cadence | PASS — 5 minutes |
| Model scoring cadence | PASS — locked 5 minutes |
| Cadence gate | PASS — `MATCHED` |
| Frontend TypeScript/Vite production build | PASS |
| Git whitespace check | PASS; Windows line-ending warnings only |
| Demo write boundary | PASS — technician confirmation returns HTTP 409 |
| Prospective-feedback configuration | PASS — timezone-aware start time is normalized to UTC; missing start time or unconfigured IANA timezone for alert `DATETIME(6)` fails closed in live mode |
| Binary confirmation contract | PASS — accepts anomaly/no-anomaly/unresolved with no cause, action or refill fields |
| Calibration demo contract | PASS — batch, profile list and three-day shadow-point endpoints render read-only historical evidence |
| Candidate-profile algorithm | PASS — synthetic past-calibration/future-shadow case reaches `READY_FOR_APPROVAL` only after configured state/codebook/service/timezone gates |
| Docker Compose runtime validation | NOT RUN — Docker is not installed on this workstation; validate on the target Server |

The production bundle emits a non-blocking size warning because the chart library is included in the main JavaScript chunk. Code splitting is a performance improvement for a later Server hardening pass, not a correctness blocker.

## Visual and interaction checks

- Fleet overview clearly separates scored machines, persistent alerts, data-quality status and unavailable Health Score
- Dashboard and Model scoring both display 5 minutes with a `MATCHED` badge
- Machine view renders synchronized Pressure, Temperature, Valve and Anomaly charts
- `Hp_2nd` 180–230 psi is presented as a qualified field-reference band, not a universal safety threshold
- State context exposes SV/Status and explicitly reports when Busy or MessageLog is absent from the snapshot
- Incident queue contains the 36 primary replay episodes plus the MX-080 Module 6 review case
- MX-080 technician-confirmation drawer retains non-causal wording and safely says when an incident snapshot is absent
- Drawer shows only anomaly found, no anomaly found or unresolved; there are no cause, action, refill or incident-time editing fields
- Drawer includes technician ID and an optional note explicitly excluded from model targets
- Automation page shows 5-minute scoring, daily Profile candidate, weekly Model candidate and human approval before `ACTIVE_FROZEN`
- Desktop layout was visually checked at the current preview viewport; responsive CSS is present for tablet/mobile but device acceptance remains a Server/UAT item

## QA Loop review

- **System:** no tag/pressure semantics changed; no PLC write path exists
- **Data:** demo provenance and unsupported/missing fields remain visible; no raw data was changed
- **Model:** release/model/threshold/persistence are reused unchanged; no outer test or MX-080 data was used for selection
- **Evidence:** anomaly and persistence are not described as diagnosis or probability
- **Presentation:** Health Score and cause output remain withheld; Demo and Shadow status are explicit
- **Production:** live MySQL connectivity, latency, late-arrival/restart, authentication, alert budget and rollback remain untested
- **Governance:** Project, SOT, Roadmap, UX, AGENTS, README_System, HANDOFF and graft map were updated in the same change

## Production blockers

1. Apply MySQL schemas only after DBA review and verify the target role of `10.195.17.73`.
2. Confirm raw-source host/schema, read-only account, timezone, pressure unit and tag mapping.
3. Configure the real scoring/profile/model candidate commands; blank commands intentionally record `SKIPPED_NOT_CONFIGURED`.
4. Add TLS, SSO/reverse-proxy authentication, role-based access and immutable audit logging.
5. Run deterministic late-arrival/restart replay and measure target-server latency, memory and storage.
6. Approve per-machine alert budget, especially MX058 and MX082, and define an exact rollback target.
7. Configure `HT9046MX_ALERT_DATETIME_TIMEZONE` from the approved `detected_at` clock policy, then set `HT9046MX_TECHNICIAN_FEEDBACK_START_AT`; operate Label QA before any yes/no confirmation becomes training data.
8. Apply `mysql_phase6_calibration_registry.sql`, verify source wide-column templates against the real `ht9046mx_iot.ht9046mx_readings` schema, then set `HT9046MX_PROFILE_CANDIDATE_ENABLED=true` in staging.
9. Visually inspect the new Calibration view on the target Server: the local browser test channel blocked a fresh localhost navigation after build, so its new layout has build/API coverage but needs target-browser acceptance before release.

This report validates a local deployable scaffold and its claim boundaries. It does not approve live deployment, model/profile activation or fault diagnosis.

## Change log

- 2026-09-15 — Added automated-calibration QA: 8/8 API tests include the demo batch/profile/three-day graph contract and a synthetic future-only candidate case. Frontend production build passed; target-browser visual acceptance remains pending.
- 2026-09-15 — Added and tested the fail-closed IANA timezone requirement for alert `DATETIME(6)` before prospective confirmation can be saved in live mode.
- 2026-09-15 — Re-ran API tests, frontend build and local visual review after replacing cause selection with prospective binary technician confirmation. No live API/database write was made.
