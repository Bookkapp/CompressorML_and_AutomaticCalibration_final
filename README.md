> **Final private Server release — 6 Oct 2026:** On “Set up ระบบนี้ให้หน่อย”, read `HANDOFF_SERVER.md` first. Owner explicitly authorized real deploy secrets/config in this PRIVATE `_final` repository. This supersedes older secret-exclusion instructions for this release. Server .69 Dashboard / .73 Operation; no Server installation or Profile approval has occurred in packaging.


# OPERATION_P

**Server setup:** When running Codex on10.195.17.73 with “Set up ระบบนี้ให้หน่อย”, follow [Worker/Fleet handoff](deployment/SERVER_WORKER_HANDOFF_20261006.md) and the required AGENTS reading order. Current local items3–6 UAT: [report](deployment/FLEET_WORKFLOW_UAT_20261006.md).


**5 Oct — Fleet Reference / selective transfer delivered:** [Fleet study + local UI/QA](deployment/FLEET_REFERENCE_AND_SELECTIVE_TRANSFER_UAT_20261005.md) · [Executed Notebook11](notebooks/11_Fleet_Reference_and_Selective_Transfer_20261005.ipynb). Calibration now shows Reference-only comparisons for041/058/080/081 and017/024 with machine/module/day graphs. Frozen Local means/scales are retained; compatible Fleet correlation sharing is an offline proposal, no Active/runtime detector replacement. Warm prepared reads p95≈109ms; cold intake/source SQL and prospective approval remain separate.

**Latest local-only integration:** [Durable detector/Dashboard QA](deployment/DURABLE_DETECTOR_LOCAL_QA.md) · [Future Server installation guide](deployment/SERVER_DETECTOR_RUNBOOK.md). New code is opt-in; actual Active qualification/startup specificity/Server acceptance remain open. No installation or Git push this turn.

**Episode / work-report workflow (1 Oct 2026):** [Dashboard-owned incident reporting, local Episode archive and QA](deployment/EPISODE_ARCHIVE_DASHBOARD_WORKFLOW.md). Daily work goes through the operational Dashboard; this app administers Profiles. New live Active→Alert bridge is still pending, not a completed production deployment.

HONTECH HT9046-MX compressor-module data analysis and predictive-maintenance project.

**Private v1 repository:** `https://github.com/Bookkapp/CompressorML_and_AutomaticCalibration_v1`

## Current status

- Selected new path: observed-second source → qualified one-minute Cold windows → local per-machine/module candidate → three-day shadow → robust-z/persistence scorer. Dashboard refresh stays five minutes.
- Local-first rehearsal now runs the candidate and scorer together from raw Parquet without Server access. MX057/M1+M6 and MX070/M6 passed exact shadow parity; MX057/M6 and MX070/M6 also passed checkpoint/restart checks. MX057/M1's high flag burden needs investigation before activation. See [one-minute checkpoint](deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md).
- Phase 0–6 analytical work and candidate-profile lifecycle are implemented with documented limitations.
- Phase 7 deterministic offline shadow replay is complete.
- Live Server/MySQL integration, alert-budget approval and exact rollback remain open.
- Current release is `phase07-shadow-replay-v2-hp180` in `SHADOW_ONLY_NOT_AUTHORIZED` mode.
- The system is anomaly screening and technician decision support. It is not automatic fault diagnosis and has no PLC/control write path.
- A FastAPI + React/Lovable-compatible Web App scaffold is available in `apps/`. Its historical five-minute shadow path is superseded by the selected one-minute scorer; Dashboard refresh remains five minutes.

## Start here

Read these files in order before making changes:

1. `README_System.md`
2. `SOT.md`
3. `HANDOFF.md`
4. `Project.md`
5. `Roadmap.md`
6. `AGENTS.md`
7. `deployment/CODEX_SERVER_HANDOFF.md` for Server implementation
8. `deployment/SYSTEM_DEPLOYMENT_FLOW.md` for the beginner-oriented system flow
9. `apps/README.md` for Web App, MySQL and Automation setup
10. `docs/V1_ARCHITECTURE_AND_DEPLOYMENT.md` for the frozen v1 schema, pipeline, diagrams and Server handoff
11. `deployment/SERVER_INPUTS_CHECKLIST.md` for the exact two-system files, environment variables, accounts, migration order and startup checks

## Clone the deployment package

This repository contains source code, executed notebooks, governance documents, the current local-profile artifacts, the portable shadow model and compact parity evidence. Raw telemetry and reproducible intermediate outputs remain outside GitHub.

Git LFS is used for the selected Parquet/model artifacts retained in the deployment package.

```bash
git lfs install
git clone https://github.com/Bookkapp/CompressorML_and_AutomaticCalibration_v1.git
cd OPERATION_P
git lfs pull
git lfs ls-files
```


## Important operating boundary

The owner-confirmed qualified field-reference range for `Hp_2nd` is 180–230 psi. Values below 180 psi are one-sided undercharge/leak screening evidence only. Values above 230 psi are separate high-side/local-deviation evidence. No pressure value, anomaly score, lag, correlation or model explanation confirms a fault without technician/service evidence.
