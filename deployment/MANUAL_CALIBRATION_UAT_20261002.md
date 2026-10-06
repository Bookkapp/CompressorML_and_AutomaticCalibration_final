# Manual Calibration UAT — 2 October 2026

Status: manual Preview/graph/Candidate review completed for all16 machine/module contexts. A successful Active approval remains blocked by unverified source contracts and statistical gates. Owner requested actual browser interaction for MX017 and MX024, M1–M8. Workflow actions use the localhost Operation UI (5176/API8000), reviewer `MANUAL_QA_20261002`; no scripted Preview/Build/Approve requests. Source/code/SQL status reads are diagnostic only. No production deployment or source telemetry writes.

## Confirmed defects and repairs

- Adding an exclusion after READY erased both charts and the job handle. Keep the completed preview while editing; mark it as an old result and require a new Preview before Build. Preserve draft by machine/module across reload. Minute charts keep their height while loading.
- Add a read-only list of the reviewer's last 12 jobs for the selected machine/module, allowing orphaned READY jobs to be reopened without recomputation. Existing job ownership checks remain.
- Approval selection previously retained a stale profile object after refetch. Resolve the selected ID against refreshed profiles. Reset approval messages/notes on context changes. Reject requires at least eight characters; terminal profiles cannot be reviewed again in the UI.
- Explain approval blockers in Thai, before technical codes. Do not invent units/contracts or bypass approval gates. Hide the all-eight approval control for one-profile batches.
- Empty qualified graphs explicitly explain that no minute values passed Gate; display Quarantine as unavailable rather than misleading0%. Correct the Shadow warning when Reference is also insufficient. Wrap long Matrix status/parameter text and profile-list text; actual desktop width1265 now has scrollWidth1265, removing the previous6px page overflow.
- Source-day inventory stays fresh for five minutes, remains cached for thirty minutes, and does not refetch on window focus. Background refresh does not block inspection or a new Preview if a previous inventory exists; its check time is visible. Explicit refresh remains; Preview/Build still check actual source and policy. This reduces repeat scans, not the cost of the initial inventory scan.

## Actual manual observations

All source-local times are Asia/Bangkok; intervals are half-open. Shadow is 28 September–before 1 October, disjoint from Reference.

| Machine/module | Reference | Qualified / retained minutes | Shadow | Observed result |
|---|---|---|---|---|
| MX017/M1 | 31 August–before 28 September | 35,410 / 34,255 | 4,262 | Default READY Preview; hourly and 16 September minute graphs inspected |
| MX017/M1 | Same; exclude 16 September 23:00–23:59 | 35,364; Quarantine 3.15% | 4,262 | Re-preview succeeded; 46 eligible minutes removed, Shadow unchanged |
| MX017/M1 | Same excluded selection | — | Flagged 34.21%; persistent 33.36% | Candidate batch `6fbc0dae-a1e0-406c-95cf-4e9535cf1708`, REVIEW_REQUIRED, Approve disabled. Manually rejected with explanatory note; UI updated to REJECTED and reported Active unchanged |
| MX017/M2 | 21 September–before 28 September | 9,550 / 7,761 | 4,263 | Temperature minute graph inspected. Quarantine 18.73%; quarantine/shadow blockers. Candidate `f28518b3…` REVIEW_REQUIRED; Approve disabled |
| MX017/M3 | Same seven-day selection | 9,550 / 8,429 | 4,263 | Valve hourly graph inspected. Quarantine 11.74%; quarantine/shadow blockers. Candidate `cbcd70b0…` REVIEW_REQUIRED; Approve disabled |
| MX017/M4 | Same seven-day selection | 9,549 / 8,741 | 4,263 | CP1 hourly graph inspected. Quarantine 8.46%; Candidate `494f704c…` REVIEW_REQUIRED; Approve disabled |
| MX017/M5 | Same seven-day selection | 9,538 / 8,258 | 4,261 | CP2 graph; Quarantine13.42%; drift/quarantine/shadow blockers. Candidate `3bba894d…` REVIEW_REQUIRED; Shadow flagged64.68%; Approve disabled |
| MX017/M6 | Same seven-day selection | 9,539 / 8,684 | 4,261 | Temperature graph; Quarantine8.96%; drift/quarantine/shadow blockers. Candidate `b5fc9184…` REVIEW_REQUIRED; Approve disabled |
| MX017/M7 | Same seven-day selection | 0 / 0 | 0 | Logs exist; mostly MODULE_NOT_STABLE_ON. Empty-graph explanation and insufficient Reference/Shadow message; Build disabled, no Candidate |
| MX017/M8 | Same seven-day selection | 9,557 / 8,690 | 4,264 | Valve graph; Quarantine9.07%; quarantine/shadow blockers. Candidate `699f169a…` REVIEW_REQUIRED; same result reopened in second tab; Approve disabled |
| MX024/M1 | Same seven-day selection | 9,013 / 8,192 | 4,103 | CP2 graph; Quarantine9.11%; quarantine blocker. Candidate `b273d227…` REVIEW_REQUIRED; Approve disabled |
| MX024/M2 | Same seven-day selection | 9,003 / 8,180 | 4,103 | CP2 graph; Quarantine9.14%; quarantine blocker. Candidate `f3975fcc…` REVIEW_REQUIRED; Approve disabled |
| MX024/M3 | Same seven-day selection | 9,013 / 7,825 | 4,104 | Differential graph; Quarantine13.18%; drift/quarantine/shadow blockers. Candidate `74c3cb63…` REVIEW_REQUIRED; Approve disabled |
| MX024/M4 | Same seven-day selection | 9,008 / 8,246 | 4,098 | Temperature graph; Quarantine8.46%; quarantine/shadow blockers. Candidate `6563fe3f…` REVIEW_REQUIRED; Approve disabled |
| MX024/M5 | Same seven-day selection | 9,008 / 8,485 | 4,101 | CP2 graph; Quarantine5.81%; quarantine blocker. Candidate `2fbfdc97…` REVIEW_REQUIRED; Approve disabled |
| MX024/M6 | Same seven-day selection | 9,009 / 6,860 | 4,101 | CP2 around200 in much of Reference and240 in Shadow (unverified units); not a fault diagnosis. Quarantine23.85%; quarantine/shadow blockers. Candidate `0e8f279c…` REVIEW_REQUIRED; Approve disabled |
| MX024/M7 | Same seven-day selection | 0 / 0 | 0 | Logs exist; mostly MODULE_NOT_STABLE_ON. Empty-graph explanation; Build disabled, no Candidate |
| MX024/M8 | Same seven-day selection | 9,028 / 7,684 | 4,106 | Valve graph; Quarantine14.89%; Shadow flagged2.00%; quarantine/shadow blockers. Candidate `51baf50a…` REVIEW_REQUIRED; Approve disabled |

All16 Preview/graph results were inspected through UI. Fourteen Candidate builds were completed and reviewed, one explicitly rejected in the decision-state test; no Candidate was built for either M7. All candidates additionally have the four shared unverified-contract blockers below. The Active Profiles UI still shows46modules for001/057/100/111/777/080, with no017/024 Active. This verifies the count/list, not a byte-level hash of every historical Active artifact.

## Additional cases already verified through UI

- Recovery of orphaned READY M1 job `42d85b5a…` through recent jobs.
- Blank exclusion retains two charts and blocks Preview with a clear missing-time message; a valid interval re-enables Preview.
- Invalid Reference end before start is blocked; Reference overlapping Shadow is blocked after source cutoff is known.
- Explicit historical Shadow cutoff without a reason is blocked.
- Module switches preserve separate job/draft contexts while asynchronous work continues.
- Two-character Reject note stays disabled; a descriptive note permits Reject. Approve remains disabled in REVIEW_REQUIRED.
- The fifth pending request shows a localized queue-capacity message and retains the draft. Retrying after capacity frees successfully queues MX024/M5. A request rejected by admission is not counted as a completed module test.
- Overlapping exclusions, reversed times, Shadow exclusions and short reasons are blocked; adjacent half-open intervals are accepted. Both graphs remain and dirty Build stays disabled.
- After actual page reload, MX017/M5 restored both draft intervals, two graphs and the dirty warning/Build block. Reopening the original READY job discarded validation-only draft intervals; Candidate used its original selection.
- A second browser tab reopened the same017/M8 Candidate batch without new calculation. Both tabs displayed the same REVIEW_REQUIRED result. This is a two-tab functional check, not a throughput/multi-device certification; browser controls intermittently timed out under resource pressure.

## Approval prerequisites and limits

Current source pressure unit and state contract/controller codebook/service epoch versions are unverified. User has been asked for verified supporting values/documents. These are legitimate blockers, not values to fabricate for QA. A valid READY_FOR_APPROVAL → ACTIVE_FROZEN path is not yet tested.

The source owner/platform maintainer must verify and configure `HT9046MX_SOURCE_PRESSURE_UNIT` (distinguish psig/psia), `HT9046MX_PROFILE_STATE_CONTRACT_VERSION`, `HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION` and `HT9046MX_PROFILE_SERVICE_EPOCH_VERSION`, then create a fresh reviewed candidate. Verification alone does not waive quarantine/drift/shadow gates. Build acknowledgement and decision notes do not certify healthy data. No settings were fabricated or changed in this task.

Memory pressure was observed on this 8 GB computer, including about 530 MB free RAM after the owner closed heavy programs. Source-day inventory and raw daily reads remain slow. Browser control timeouts are reported separately from confirmed UI defects; this UAT does not establish production latency or multi-device capacity.

Evidence: `notebooks/outputs/manual_calibration_uat_20261002/manual-cases.json` and saved browser JPEGs. `diagnostic-job-audit.json` is a separately labelled read-only SQL audit (14COMPLETED jobs, two M7READY previews and the original M1READY preview), not the manual UAT itself. Latest web build passed (`index-DXSNx9gF.js`, `index-gDbcUd_O.css`); only the existing bundle-size warning remains. No scripted workflow or automatic approval tests were performed. Active-success and initial-source-read performance gates remain open.
