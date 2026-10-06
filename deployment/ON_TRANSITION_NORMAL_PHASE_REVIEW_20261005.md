# ON transition / steady normal review — 5 October 2026

## Decision requested and scope

The owner clarified that transient measurements should remain in Shadow and be evaluated as potentially acceptable normal operating behavior. This investigation therefore supports a separate conditional transition profile, rather than a fixed post-SV/ChangeValve exclusion or broadening the steady baseline until Shadow passes. No runtime, threshold, Profile, job, Active pointer, source table or Server was changed.

Local source latest, checked with SELECT: MX0171Oct15:55:01 and MX0241Oct15:45:00. The current review uses complete days through30Sep, interpreted in Asia/Bangkok. These are historical observations, not fresh prospective validation.

Reproduction scripts:

- `notebooks/support/sv_settling_diagnostic.py`: exact raw017/024 SV/ChangeValve witnesses; frozen SQL Candidate comparisons; exploratory slope/range and cut sensitivity.
- `notebooks/support/multi_machine_transition_review.py`: past-only physical-v2 fits, observed start ledgers, separately keyed Reference trajectories for nine machines.
- `notebooks/support/transition_review_delivery.py`: four additional Raw reconciliations and projected inline evidence.

Receipts and inspectable results: `notebooks/outputs/sv_settling_diagnostic_20261005/`.

## Source, grain and quality

The exact017/024 witness study reads62 original dynamic ZIP day-files,31Aug–30Sep:5,282,414 valid-time rows, including17,166 duplicate rows. Duplicate boundaries are excluded from transition witnesses; the existing minute gate rejects duplicate/low-coverage/gap/manual/unknown-state minutes. No missing seconds are synthesized. Files are sorted for analysis, with source nonmonotonicity recorded. Static files are excluded.

There are731 **module boundary records**,309 SVOff and422 ChangeValve end records. They are not731 independent compressor starts: modules often share a machine control event. Seventy bounded SELECT-only source Raw checks match event state witnesses and minute feature means exactly (maximum feature error0). Four additional30-minute Raw slices reconcile120 minute means across eight physical features for the chart, also maximum error0; comparisons overlap and are not independent observations.

Broader evidence reuses previously audited observed-second event ledgers and one-minute archives for017,024,080,029,041,057,070,118,119. Nine machines/72 contexts were inspected; seven machines/50 contexts had sufficient past baseline coverage.118/119 did not.1,833 observed module-entry records have a supported descriptive baseline. Gap/left-censored starts are excluded rather than called observed motor starts. The historical `COLD_CONTROL_ENTRY` subtype does not distinguish SVOff from moduleOn entry; the exact017/024 study supplies that distinction. `POST_MANUAL` is not proof of maintenance or a refill.

017/024 retain saved physical-v2 SQL Candidates241–254, Reference31Aug→before28Sep and Shadow28Sep→before1Oct. Other contexts use pure physical-v2 fits4Aug→before18Aug and later available archive evaluation throughbefore9Sep. Known057/M1 (29Aug) and080/M6 (7Sep) cases are outside those fits. Different clocks/periods/populations are preserved; no pooled absolute baseline is fitted. Some descriptive Candidates remain REVIEW_REQUIRED. This is not a release or accuracy benchmark.

## What the measurements show

### MX017/M1: pressure recovers faster than temperature

SV changes On→Off on29Sep23:34:53 while Run/On/Busy0. Frozen Reference Hp2 median196.215psi; TempHi median61.012°C and upper minute boundary72.235°C.

| Approximate elapsed minute | Hp2 psi | TempHi °C | Physical deviation explanation |
|---|---:|---:|---|
| 0 | 311.451 | 110.890 | Multiple physical features exceed the steady boundary |
| 5 | 205.119 | 98.278 | Lp2/TempHi/TempLo still exceed |
| 10 | 195.770 | 79.180 | Hp2 is near Reference; TempHi alone still exceeds |
| 15 | 194.127 | 73.962 | TempHi still exceeds |
| 20 | 194.117 | 72.276 | TempHi remains just above72.235 |
| 25 | 195.490 | 70.115 | No physical feature exceeds the frozen boundary |

The first of three consecutive below/equal-boundary minutes starts at elapsed21.117min; confirmation is24.117min. Exploratory Reference-derived range/slope tests also require compatible levels:3-minute and5-minute definitions confirm at25.117 and34.117min. They are sensitivity checks, not a validated true stable-time label.

A past Reference SVOff episode on17Sep09:00:29 has a similar temperature decay and confirms below boundary at27.517min; compatible-level stability at28.517/30.517min. This supports a thermal recovery hypothesis. It does not establish refrigerant balancing as the physical cause or certify either episode healthy. Only one direct MX017/M1 Reference SV event has a completely observed return; the other qualifying event is censored after10minutes. One trace cannot certify an automatic normal envelope.

### Modules do not recover at the same speed

For the same29Sep23:34:53 machine event:

| MX017 module | First below-boundary entry, min | Three-minute confirmation, min |
|---|---:|---:|
| M1 | 21.117 | 24.117 |
| M2 | 12.117 | 15.117 |
| M3 | 0.117 | 3.117 |
| M4 | 15.117 | 18.117 |
| M5 | 43.117 | 46.117 |
| M6 | 6.117 | 9.117 |
| M8 | 24.117 | 27.117 |

These are source-time, retrospectively observed first returns, not an online availability SLA or a guarantee that subsequent behavior remains normal. M4 has later TempLo deviation runs on30Sep (01:52–02:28,02:40–03:14,03:25–03:55). A first return is not permission to erase later flags.

In024, observed Shadow SVOff occurs while ChangeValve/Busy1. The separate post-manual qualification boundary matters; it must not be described as a pure SV recovery beginning in steady On. M4/M6 after28Sep04:29:52/04:28:26 remain above the frozen boundary throughout the120-minute observed run. Range/slope alone become stable near29.133/23.567min. Thus **stable does not mean normal**. Large sustained dp2 deviations and later long runs remain; a generic30-minute exclusion does not address them.

### Broader Reference behavior supports a separate transition description

397 observed Reference module-event records returned to their frozen baseline by the three-minute criterion.252 had physical flags **before** that return. The denominator is a recovery-conditioned set, not all starts, and this is not a false-positive estimate or a confirmed-negative dataset.

| Machine | Returned Reference records | With physical flags before return | Median confirmation min | Conditional empirical P95 min |
|---|---:|---:|---:|---:|
| 017 | 76 | 55 | 6.62 | 13.93 |
| 024 | 125 | 70 | 4.33 | 19.55 |
| 029 | 10 | 8 | 24.61 | 41.85 |
| 041 | 18 | 13 | 16.48 | 42.54 |
| 057 | 34 | 31 | 19.11 | 41.90 |
| 070 | 32 | 23 | 16.48 | 34.74 |
| 080 | 102 | 52 | 4.09 | 27.49 |

These aggregate different module/event contexts for descriptive comparison; their P95s are not machine-wide timeout settings. Censored/no-return events remain in `multi_events.csv`. Thirty-six machine/module/event-kind groups have at least three returned Reference examples on three days. This is exploratory support, not validated95% interval coverage. Direct SV/On entry, manual response and genuine Run start must not be pooled solely to increase counts.

## Proposed implementation after this review

1. Preserve all observed measurements. Derive a versioned phase within existing ON: `ON_TRANSITION`, `ON_STEADY`, `ON_TRANSITION_UNUSUAL`, and unresolved/unknown. SV/Busy/state/quality determine the observed boundary; elapsed time alone does not make the phase normal. SVOn, post-SVOff recovery, observed Run entry and manual response remain different contexts; SVOn itself does not prove healthy balancing or a motor restart.
2. Fit a frozen **steady profile** and a separate **transition profile** from past Reference. The transition profile describes elapsed-time P/T/ΔP trajectories, initial thermal/pressure conditions, controller context and expected settling behavior. Valve remains controller context. Keep pressure/temperature relationships and level compatibility; do not simply increase the steady z threshold. The current live v1 minute cache discards features when Cold/SVOff eligibility fails, so this requires a new version separating all-state observed-minute measurements/quality from phase scoring eligibility. Retain strict duplicate/gap/finite-value checks, state counts and original raw evidence. Read all eight modules in the shared streamed source pass; do not add eight competing source-history reads or relabel existing Active v1 profiles.
3. Use a small event-weighted robust median/observed-band template initially. Store sample/event/day support by machine/module/event kind. Fit/compare signed per-feature behavior and decline toward the appropriate steady target, not just a max-score peak. Do not call an empirical observation band a confidence interval or a guarantee.
4. Review Reference examples before assigning healthy/normal labels. Where local SV examples are sparse, search a longer **past-only** phase history (e.g.90days) while keeping a recent steady Reference. Require compatible hardware role, source semantics and operating regime. Cross-machine shape priors may assist only after leaving whole machines/cycles out for validation; never share absolute normal pressures across all modules. Unsupported phases remain explicit for review.
5. In Shadow, retain the original steady deviation as evidence. A supported transition following its expected envelope is assessed against the transition model, rather than automatically failing the steady-only burden gate. Display separate steady deviations, expected transitions, unexpected transitions and unsupported phase coverage. Every category retains its denominator, dates and Raw evidence; data are not silently discarded.
6. Move to ON_STEADY only after causal trailing variation/slope and comparable level/relationship criteria. A flat abnormal plateau stays `ON_TRANSITION_UNUSUAL`/stable deviation. An unexpected spike, opposite-direction rise, new level, prolonged recovery, unknown state or gap must not be marked normal just because the clock expires. If a changed setpoint is intended, it is an explicit reviewed operating regime/new Candidate, not an automatically absorbed anomaly.
7. Freeze versions and validate by complete cycle/day before integration: known057/M1 sustained Lp2 change and080/M6 rising high pressure must remain detectable; separately validate technician/operator-reviewed normal starts, leave-machine-out transfer and fresh future cycles. The already viewed Shadow is diagnostic evidence, not a fresh test for a redesigned model. Maintain per-module state/checkpoint and bounded minute computations for concurrent use. UI should explain the physical reason and elapsed phase time, with before/after Raw links.

The purpose is to let supported normal transitions pass **their own validated phase criteria**. It is not to guarantee every Candidate becomes Active. Four unverified source contracts still independently govern actual approval. This turn implements only reproducible diagnostic files and the proposed design, not a runtime phase model or an approval waiver.

## Change log

5Oct2026: owner clarified accepted ON transition behavior rather than time exclusions. Completed exact017/024 Raw study, nine-machine past-only archive diagnosis, conditional Reference trajectory support and source-reconciled temperature comparison. Scripts and receipts above. No DB/source DML, gate/threshold/Profile/Active changes, deployment or Git push.
