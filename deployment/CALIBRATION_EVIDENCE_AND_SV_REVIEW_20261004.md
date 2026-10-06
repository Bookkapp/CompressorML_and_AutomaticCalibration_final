# Calibration evidence, automatic Reference and SV review — 4 October 2026

## Scope and outcome

Owner-authorized local Operation changes; source SELECT only. Workflow preparation and evidence-copy actions were actual browser clicks. SQL/GET checks below are technical diagnostics. Pressure unit is now owner-confirmed **psi**, recorded in the local central configuration. Gauge/absolute basis and state/controller/service versions remain unverified. No automatic Active promotion; manual approval rules remain.

The web now explains Reference, held-out Shadow and shared prerequisites separately. Review Required does **not** always mean changing the Reference period. Shadow changes require investigation; source prerequisites require verified configuration. Readable statuses, actual values/limits, drift evidence, contributor intervals and minute/observed-second navigation replace unexplained codes. Existing frozen estimator, thresholds, gate and source rows are preserved.

## SV comparison

Original dynamic ZIP daily CSVs: **28 files / 2,385,588 observed rows**, two machines/all eight modules, **17–30 Sep 2026** (`[17 Sep, 1 Oct)`), Asia/Bangkok. All file hashes/inventories are recorded in `notebooks/outputs/sv_comparison_20261004/receipt.json`. Static excluded. Actual source state counts for all 28 files and **196 SV On Hp2 minute means** were reconciled to the audited minute evidence.

Comparison uses finite sensors, nonnegative Valve, ≥57 unique seconds, no duplicate seconds, gaps ≤5s, stable Run/module On/Busy0 and pure SV On or Off throughout each minute. Each On minute is matched to nearest Off on the same machine/module/day within60min. Off controls are reused, so these are not independent trials, a randomized causal study or an equivalence test. Neither state is labelled healthy.

| Machine/module | Matched On minutes | Unique Off controls | Days | Median Hp2 On−Off (psi) | Median TempLow On−Off (°C) |
|---|---:|---:|---:|---:|---:|
| 017/M1 | 93 | 9 | 5 | +112.666 | +57.236 |
| 017/M2 | 90 | 9 | 5 | +7.444 | +4.011 |
| 017/M3 | 93 | 9 | 5 | +20.202 | +22.754 |
| 017/M4 | 93 | 9 | 5 | +104.063 | +45.697 |
| 017/M5 | 93 | 9 | 5 | +1.407 | +28.927 |
| 017/M6 | 93 | 9 | 5 | +5.434 | +21.929 |
| 017/M7 | 0 | 0 | 0 | ไม่พอ | ไม่พอ |
| 017/M8 | 93 | 9 | 5 | -3.266 | +11.917 |
| 024/M1 | 143 | 18 | 9 | +17.567 | +0.984 |
| 024/M2 | 140 | 16 | 9 | +26.558 | +8.858 |
| 024/M3 | 141 | 17 | 9 | +61.254 | -41.192 |
| 024/M4 | 143 | 17 | 9 | +19.814 | -53.486 |
| 024/M5 | 143 | 18 | 9 | +1.488 | +4.458 |
| 024/M6 | 140 | 16 | 9 | +9.510 | -5.430 |
| 024/M7 | 0 | 0 | 0 | ไม่พอ | ไม่พอ |
| 024/M8 | 141 | 17 | 9 | -1.732 | +7.825 |

**Decision:** retain SV Off eligibility for the existing Cold baseline. Some pressure medians move little, but temperatures and tails still move substantially. E.g.017/M8 Hp2 median−3.266psi while TempLow+11.917°C; P95 absolute differences21.469psi/78.938°C. Do not infer non-running/Hot solely from SV On: actual Run/moduleOn/Busy0 co-occurrence is observed. Dedicated On or recipe-conditioned profiles require separate evidence and validation. All states remain visible in Raw review; no source rows are deleted.

## Automatic proposal and performance

Version `past-only-reference-proposal-v1`: search only the configured already-read Reference history, normally28days. Blocks7/14/21/28days with0/7/14/21day backtracks, bounded16 possibilities; current28day context has10. Keep complete days before fixed held-out Shadow. Existing retained minima/quarantine/drift/positive-threshold checks plus proposal-only daily-level-span≤2.0 compare between-day levels with within-day robust variation. Rank passing blocks by continuity, qualified days, recency and quarantine. No automatic exclusions; no Shadow feedback; no retry-until-pass. If none pass, preserve the default period and mark for review. Stable does not certify healthy. Verified service-epoch segmentation is **not implemented** because source repair epoch data are unverified.

Vectorized proposal yields exact full-result equality to the prior implementation on017/M1,M8 and024/M1,M6 (each≈40,320 cached windows). Proposal time ranges 3.347–4.493s before, 0.559–0.656s after. This measures proposal computation, **not** total raw history preparation latency. Saved comparison implementation and receipt support reproduction.

Source validation/reading31historical days is still expensive on this local8GBmachine:017 preparation took701.743s. Jobs run durably in the background; old evidence remains accessible during preparation. Closed-day cacheTTL1hour and fresh source-digest checks on Manual Build remain. Per-profile persisted Reference boundaries now match each selected module's reviewed period; batch scope remains the search envelope.

Raw GET: actor/job-scope authorization before cache; minute-aligned bounds within saved review, maximum30minutes/6000rows; excess fails explicitly. SQL retains all states. Two source readers, coalesced identical requests, eight-slice60sec cache, fixed230px graph, no interpolation across gaps. Hourly/minute graphs are loaded on demand; evidence intervals bounded200 with explicit truncation, exact minute score/threshold and dominant contributor.

## Actual UI and load QA

- MX017: COMPLETED, job `87c973c8-c531-4181-ab43-64da368dbbb8`, 7 Candidates; 2026-10-03 18:21:38.478802 → 2026-10-03 18:33:20.221560 UTC.
- MX024: COMPLETED, job `9b142986-341c-4255-8373-0241adf88b1b`, 7 Candidates; 2026-10-03 18:45:39.288083 → 2026-10-03 18:55:58.931807 UTC.

- 017/M1: click TempLow interval29Sep23:35→23:40 → matching day/thermal feature ±30min view → Raw296rows/296distinct seconds/300expected, no duplicates, SVOff296; score view present. Saved `shadow-raw-evidence.png`.
- 024/M1: custom Raw19Sep05:28→05:38 →592rows/591distinct seconds/600expected, duplicate-affected rows2, SVOff120/On472. Saved `raw-sv-review.png`.
- 024/M7: actualUI reports0qualified/44,640observedminutes; prioritized gate reasons42,130module-not-stable-On,1,344duplicate-minute,1,146global-not-stable-Run,20low-coverage. Build remains disabled, Raw remains available.
- Invalid70minute custom request rejected in UI with readable30minute limit. Existing graph retained. User-selected period is never silently broadened.
- Desktop1280×900 and narrow603px layouts checked; desktop cards do not overflow (client/scroll widths1265px). Temporary viewport override reset afterQA. No fabricated successful Active path.
- Raw read load: **10 clients / 40 GETs / 40 successful**, p50216.7ms, p95270.7ms, max310.0ms. Cached ten-minute slice of592actual rows; not a cold full-history or Server SLA.
- Final backend **167 full-suite tests passed**, then the11-test evidence suite (including one additional saved-quarantine-policy regression) passed; frontend production build passed (existing large-bundle warning810.20kB/233.86kB gzip); diff whitespace check passed. Source SHA/reviewer/queue/copy/raw range/auth/coalescing/past-only split and per-module persistence tests included.
- Active pointer count **46**, SHA256 `3f2473685cfd3e16e99d6ccb117a970f2a7e4433dcb847d16af5a9767be85c21` matches pre-work snapshot. No source DML, no Active approval, no normal detector/ML job activation, no target Server deployment or Git push.

## Reproduction / remaining limits

From repository root: `python -m notebooks.support.sv_on_comparison`, `python notebooks/support/calibration_evidence_qa.py parity`, `python notebooks/support/calibration_evidence_qa.py load`, `python notebooks/support/calibration_evidence_qa.py audit`, `python -m pytest apps/api/tests -q`; `apps/web`: `npm run build`. Analysis notebook09 and source receipts contain actual executed results. LocalRaw is read-time context, not an immutable source snapshot; final Manual Build still rechecks source. Historical profiles/jobs remain immutable and may still show previous unverified-unit state. Production clock/auth/resource/worker acceptance and a genuinely eligible human-approved Active flow remain unverified.

## Local services at delivery

API127.0.0.1:8000 PID10332, scoped profile-only scheduler PID17096 (`MX017 MX024`,02:00Asia/Bangkok), Vite5176 PID16192. No active review jobs at restart. These are local processes, not installed autostart services; current PIDs/hidden-launch logs are in the ignored output folder. Review tabs for024/M1 and017/M1 Raw were retained, with temporary viewport reset.
