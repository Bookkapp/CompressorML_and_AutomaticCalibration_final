# Physical/control Calibration policy and manual UAT — 4 October 2026

## Scope and decision

Owner authorized implementation after reviewing MX017 Shadow evidence, then explicitly requested manual website checks. Local Operation is at `http://127.0.0.1:5176/`, API8000. This changes newly built qualified one-minute Candidates; existing profiles keep their stored policy. It does not certify balancing as healthy, change the observed-second source contract, approve Active, or deploy to the target Server.

New primary scoring uses eight physical features: Hp1, Lp1, Hp2, Lp2, ΔP1, ΔP2, TempHi and TempLo. Valve remains stored, plotted and reported as controller context. A changed integer command alone cannot quarantine a Reference minute, reject Reference stability, or vote in the new primary anomaly score. Threshold comparisons use strict `>` so a value equal to the empirical Q99.5 boundary is not counted as exceeding it. Legacy profiles preserve their nine-feature `>=` policy.

Pressure unit is owner-confirmed **psi**. Sensor pressure basis (psig/psia), state contract, controller codebook and service epoch remain unverified. They are explicit approval prerequisites; changing Reference dates does not supply them.

## Reproducibility and leakage boundaries

| Item | Contract |
|---|---|
| Source | Actual localhost `ht9046mx_iot.ht9046mx_readings`; source SELECT only |
| Review sample | MX017 and MX024, M1–M8 separately |
| Grain | Observed seconds → completed source-local one-minute windows; hourly review plots are aggregations |
| Timezone | Asia/Bangkok; source-local boundaries, no latest partial day |
| Default Reference | 31 Aug 2026 inclusive → 28 Sep exclusive |
| Shadow | 28 Sep inclusive → 1 Oct exclusive; never used to fit or rank Reference |
| Feature transport | `qualified-cold-observed-1m-v1` unchanged, all nine features retained |
| New Candidate | `two-pass-physical-robust-z-control-context-1m-v2` |
| New threshold | `qualified-1m-physical-retained-q995-strict-v2` |
| Legacy threshold | `qualified-1m-retained-q995-v1` |
| Review selection | `manual-reference-complete-day-shadow-v3-physical` with persisted score manifest |
| Automatic selector | `past-only-physical-current-reference-proposal-v3` |
| Recovery evidence | `reference-recovery-evidence-v1`; never suppresses flags |

Per-module Reference fitting still uses past data only: first-pass physical max robust z >8 quarantine; retained Reference medians/scales; retained physical-score Q99.5 threshold. Three adjacent qualified minutes remain the persistence rule. Gaps/manual/unknown/unstable/SV state and observed-second quality gates remain. No missing-second interpolation, auto-rebase or Shadow-based threshold adjustment was added. Unknown score versions and inconsistent new manifests fail closed. Old READY previews cannot Build under a changed score manifest without a new Preview. Runtime dispatch and JSON checkpoint/restart tests preserve legacy results.

The bounded automatic selector examines 7/14/21/28-day alternatives within the saved search envelope using physical Reference statistics only. It may automatically select only a passing block ending at the current pre-Shadow cutoff. An older stable block remains a human-review alternative: stability alone does not verify that it represents the current operating state. This prevents silent adoption of a different historical regime. The recency rule is explicit in the selector policy and tested independently of Shadow. An earlier intermediate selector without this rule was tested locally and replaced; it is not the delivered version.

## Retrospective actual-cache regression

`notebooks/support/physical_control_qa.py replay` reads the already persisted actual-source completed-day cache; it does not create workflow jobs, write source, or approve a profile. All 16 contexts were checked; M7 on both machines has zero qualified minutes, leaving 14 scorer comparisons. Candidate/scorer score, raw flag and persistent flag differences: **zero**.

| Module | MX017 Shadow out of baseline | MX024 Shadow out of baseline |
|---|---:|---:|
| M1 | 0.6804% (29/4262) | 0.2925% (12/4103) |
| M2 | 0.5630% (24/4263) | 0.2437% (10/4103) |
| M3 | 0.1173% (5/4263) | 1.3402% (55/4104) |
| M4 | 4.4100% (188/4263) | 30.5515% (1252/4098) |
| M5 | 2.0418% (87/4261) | 0.5121% (21/4101) |
| M6 | 0.3286% (14/4261) | 76.0790% (3120/4101) |
| M7 | insufficient | insufficient |
| M8 | 0.9146% (39/4264) | 1.6318% (67/4106) |

MX017 M1/M2 previously had approximately34.21%/34.25% flags dominated by discrete Valve ties. Their new physical burden is lower; this is a retrospective workload comparison, **not** a measured false-positive rate. M4/M5 and MX024 M4/M6 retain substantial physical deviations. Values in older saved batches can differ because they preserve their original policy/quarantine. Fresh prospective holdout and verified healthy negatives remain required before claims about long-term normal recognition.

`notebooks/support/physical_case_regression.py` reuses previously parity-checked raw-derived minute archive caches for known cases (not a new source/raw parity study):

- MX057/M1, 29 Aug04:06–22:50:1124 qualified case minutes,1124 raw and1124 persistent flags under both legacy/new fits; first persistent04:06.
- MX080/M6, 7 Sep12:24–midnight:692 qualified case minutes,692 raw/686 persistent flags under both policies; first persistent12:24. Its four Reference days do not make an approvable production Profile; this is a diagnostic regression only.

No confirmed fault label was inferred from newly flagged017/024 data. Known-case retention does not establish general sensitivity or specificity.

## Recovery/Raw UX

The review distinguishes physical deviations from nonvoting Valve context, displays shared source prerequisites and per-check actions, and offers bounded contributor intervals → minute graphs → all-state Raw. Raw includes SV On, gaps and duplicates and overlays the frozen Reference median and per-feature minute threshold bounds. The overlay is explicitly labelled as a minute criterion on raw seconds, not a second-level fault criterion. Valve instead shows its observed Reference command range.

Recovery evidence searches an adjacent `BYPASS_OR_UNKNOWN_SV` boundary to qualified Off, then observes three consecutive physical minutes below/equal threshold. Gaps, state changes and manual exclusions terminate a run; a120-minute scan cap bounds work, not a suppression grace period. It fits duration/trajectory evidence only from Reference examples with observed recovery, requiring at least three events on three distinct days for comparison. The cache boundary cannot prove SV On rather than unknown; Raw must confirm it. Insufficient examples and incomplete recovery are visible. All original flags still count; there is no live healthy-phase classification or automatic balancing suppression.

During actual MX017/M1 GUI testing, the29Sep23:35 boundary returned below threshold in21minutes. Reference had only1recovery example on1day, so the UI correctly abstained from declaring a matching normal pattern. Clicking the event opened23:30–00:00 Raw:1775rows/1775distinct seconds of1800expected, no duplicates, SVOn289/Off1486. Pressure Raw labelled psi; changing the variable retained the interval and frozen Reference overlay. Thus physical transients are inspectable even after Valve stops voting.

Manual review found an overly long interval list. The UI now initially renders eight intervals per filter, with an explicit expand/collapse control. Review status reads “ต้องทบทวนหลักฐาน”, avoiding the implication that every REVIEW_REQUIRED needs a date change. Preparation progress no longer reuses a previous completed job's final progress message while the next job queues. New policy text is conditional, so legacy evidence is not relabelled as new scoring.

## Manual browser UAT / performance receipts

Workflow actions used actual GUI clicks, selections and typing; SQL/cache replay and HTTP load reads are supplemental diagnostics, not manual workflow evidence. The scoped profile-only scheduler was paused while manual jobs ran. Evidence/screenshots, timing receipts and the final Active hash are stored in `notebooks/outputs/physical_control_qa_20261004/`.

| Manual action | Observed result |
|---|---|
| Prepare MX017 and MX024 in separate tabs | Both final-policy parents completed; seven Candidates each, M7 insufficient. Duplicate preparation disabled while busy; previous evidence remained accessible. |
| Open M1–M8 for each machine | All 16 contexts manually opened and checked against machine/module identity. Fourteen showed review plots; both M7 contexts showed insufficient qualified data and blocked Build. Receipt: `manual-module-checks.json`. |
| MX017/M1 physical, Valve and Reference filters | Filters changed visible evidence. Recovery event opened all-state Raw; changing Raw variable to Hp2 retained dates, psi label and frozen Reference overlay. |
| Exclude reviewed Reference Lp2 spike, 31 Aug07:03–07:07 | Incomplete edits disabled Preview while retaining graphs. Dates/reason accepted; explicit Preview recalculation completed. The exclusion was QA-only, not a verified fault label. |
| Acknowledge new Preview and Build | Build completed as SHADOW_VALIDATION. Preview had 35,406 selected/34,464 retained Reference minutes, quarantine2.66%, Shadow0.68%. Job `c88bc424-0a7f-4ca8-b4f0-5625904895ee`, batch `5ad9f5c5-048d-426b-9598-1fb50f280207`. |
| Approval note and prerequisite check | Approval remained disabled for four unverified source prerequisites. A note did not bypass them; note cleared after checking. No Reject or Active promotion. |
| Switch machines | Matching review contexts opened; reviewer persisted within the working QA tab. |
| Reload/reopen | Saved Candidate remained accessible, and a fresh tab read the saved reviewer. Editing the reviewer after reload was **not verified**: supported locator/native typing reported success without a visible change, and browser control had intermittent timeouts. This is an unresolved UAT path; evidence does not establish whether the cause is the browser control bridge or the app. |

Manual UAT also found and fixed a frontend guard still expecting the old v2 Preview version. It prevented Build on a valid v3 Preview. After the fix, the actual exclusion → Preview → Build sequence above completed.

Final GUI parent timings: MX017 job `4316a695-7822-45d5-a7ff-13a20888fd07`, **81.865s** with warm completed-day cache; MX024 job `0fca7c97-8b66-4f82-a92e-3933afbb2a39`, **693.187s (11min33s)** including cold source verification and overlapping queue. These are local elapsed job times, not isolated CPU or production SLA measurements. The manual exclusion job elapsed about413s including queueing, Preview and human actions; no isolated Build-speed claim is made.

Supplemental GET-only Raw load: ten clients,40/40 successful responses, each1775 observed rows; p50 **395.744ms**, p95 **538.679ms**, maximum645.51ms. This measures the already cached30-minute slice, not first-time full-history loading. Receipt: `raw-load.json`.

Backend full suite: **174 passed**,450 warnings,41.16s (`final-tests.log`). Frontend production build passed; existing bundle-size warning remains. Scorer replay and stored-manifest/legacy/checkpoint tests passed. The final audit retained46 existing Active pointers and unchanged SHA256 `3f2473685cfd3e16e99d6ccb117a970f2a7e4433dcb847d16af5a9767be85c21`; those pointers include pre-existing local fixtures and are not46 certified production profiles.

Actual UI proof: `mx017-m1-recovery-narrow.jpg` shows Hp2 all-state Raw and the Reference overlay; `approval-blockers.jpg` shows disabled approval with the four source prerequisites. The successful manual actions above do not make the unresolved reload-input path or genuine Active-success acceptance pass.

At delivery, API `/health` and web5176 both returned HTTP200. API PID7276, web PID17664 and the restored hidden profile-only017/024 scheduler PID3816 were alive. The scheduler remains scoped and cannot activate profiles automatically. Temporary reviewer tracing and viewport overrides were removed; the user's existing MX017 Candidate tab remains open. Runtime receipt: `services.json`.

## Acceptance limits

- Successful Active approval remains dependent on verified source contracts and an eligible fresh Candidate; no invented metadata or approval waiver is permitted.
- Reference stability is not a healthy label; historical Shadow already inspected is not a fresh prospective holdout.
- SVOff qualification remains because observed SVOn can materially change physical measurements. Recovery is explanatory evidence; a learned state-specific normal envelope needs independent examples and validation.
- Local closed-day cache improves repeat preparation; cold source verification/full-history preparation remains expensive. Cached Raw load does not establish a cold-source or production Server SLA.
- API tests and desktop/narrow UI checks do not replace authenticated target-Server, clock, concurrent ingestion/late commits and genuine Active-success acceptance.

## Change log

4 Oct2026: versioned physical primary/control context, strict quantile comparison, current-regime Reference selection, Reference-only recovery evidence, Raw frozen baseline overlays, manual review UX and backward-compatible replay. Main files: `qualified_policy.py`, `qualified_calibration.py`, `qualified_candidate_registry.py`, `qualified_scoring.py`, `qualified_shadow_preview.py`, `reference_review.py`, `reference_jobs.py`, `reference_selector.py`, `automatic_reference.py`, `calibration_recovery.py`, `calibration_diagnostics.py`, `qualified_episodes.py`, Calibration/Reference UI and `test_physical_control_policy.py`. No source DML, Active promotion, target-Server deployment or Git push.
