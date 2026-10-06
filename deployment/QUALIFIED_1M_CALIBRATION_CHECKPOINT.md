# Qualified observed-second → one-minute calibration checkpoint

**Date:** 2026-09-25 (Asia/Bangkok). **Status:** local-first rehearsal of the candidate and scorer; Server connection is not required for this stage.

## Current contract

The raw source is `ht9046mx_iot.ht9046mx_readings`, one wide row per machine/timestamp when the source actually records seconds. A completed minute is eligible only if it has at least 57 of 60 occupied second bins, no gap over five seconds, and every observed second is the confirmed Cold state (`Status=Run`, module `Status_n=On`, `Busy_n=0`, `SV_n=Off`). Missing seconds are neither interpolated nor treated as normal. `Busy=1`, bypass, changing state, missing sensors and negative Valve commands abstain. The nine one-minute mean features are `hp1`, `lp1`, `hp2`, `lp2`, `dp1=hp1-lp1`, `dp2=hp2-lp2`, `valve`, `temphi`, `templo`. This is **not** equivalent to one minute-snapshot row or the historical five-minute feature version.

Per machine–module–Cold state, the existing Auto-Calibration entry point fits a two-pass robust median/scale on past calibration minutes, quarantines first-pass `max |z| > 8`, uses a Valve floor of one integer command and 0.1 for other features, and sets a candidate threshold at the retained calibration-score 99.5th percentile. A disjoint final three-day block supplies the shadow graph and review statistics; no shadow values refit the candidate. Three **adjacent qualified one-minute windows** above the threshold produce a persistence flag. Unqualified or missing minutes break the run; absent-source minutes are explicit graph gaps and count against a 95% shadow-source coverage gate. EWMA/CUSUM remain numerical shadow research only, not live alert votes. The old raw-row mutating inference route is blocked; the version-matched one-minute preview is read-only and cannot write Health, score tables or PM Alerts.


## Actual local data check: MX057 / M6

Command (replace the local raw root with the operator's own path):

```powershell
python -m notebooks.support.qualified_1m_parquet_replay --raw-root 'C:\Users\Book\OneDrive\เดสก์ท็อป\HT9046MX-20260902T013607Z-1-001\HT9046MX\raw\table=ht9046mx_readings' --machine 057 --module 6 --start-date 2026-08-20 --days 10
```

Input: ten daily raw Parquet files, 810,894 rows, 2026-08-20 00:00 to 2026-08-30 00:00 exclusive; machine–module–minute is the analysis grain. `Asia/Bangkok` was an **assumption for this local replay**, not confirmation of the Server DATETIME clock. There were 13,760 observed minutes and 13,362 eligible Cold minutes. Exclusions included 36 bypass/unknown SV, 118 compressor-not-stable, 98 low-coverage and 146 module-not-stable minutes. Past calibration comprised 9,237 eligible minutes over seven days. The future three-day shadow had 4,308 observed and 4,125 eligible minutes; its 4,320-point graph explicitly includes 12 absent-source-minute gaps. It produced 49 raw flags, 21 persistent flagged minutes and a 1.1879% raw-flag share. The candidate threshold was 9.3255; retained `Hp_2nd` median was 210.5356 source units with scale 1.6246.

Result: `REVIEW_REQUIRED`, principally `SHADOW_FLAG_RATE_EXCEEDED` (>1%). Source pressure unit, state/controller codebook and service-epoch versions also remain unverified. These flags are deviations from a fitted local profile, **not** confirmed faults or accuracy. No profile was activated; this replay did not write MySQL, scores, Health or alerts. Local MySQL snapshots with one row per minute cannot pass the 57-second coverage gate; target Server `10.195.17.73` was not reached.

## Local-first scorer rehearsal (same raw files)

Add `--score-rehearsal` to the command above. The script fits a candidate on the first seven days, builds a synthetic in-memory profile from that candidate, scores only the later three shadow days through `QualifiedShadowScorer`, and compares each eligible minute's score and raw/persistent flags against the calibration shadow graph. It also serializes a checkpoint halfway through the three-day shadow, resumes the scorer, and compares every resumed result with the one-shot run. This lets candidate/scorer and restart parity be checked without MySQL, `ACTIVE_FROZEN` or Server access. For more than one module, use `--modules 1,6`; daily Parquet is read once for both modules.

```powershell
python -m notebooks.support.qualified_1m_parquet_replay --raw-root 'C:\Users\Book\OneDrive\เดสก์ท็อป\HT9046MX-20260902T013607Z-1-001\HT9046MX\raw\table=ht9046mx_readings' --machine 057 --modules 1,6 --start-date 2026-08-20 --days 10 --score-rehearsal
```

| Local run | Raw rows / files | Total time | Peak working set | Scorer parity |
|---|---:|---:|---:|---|
| MX057/M6, 20–30 Aug | 810,894 / 10 | 30.625–50.039 s in local runs | 266.3–268.9 MB | 4,125 scored, 49 raw, 21 persistent; 0 candidate/scorer and restart mismatches |
| MX057/M1+M6, same days | 810,894 / 10 | 88.467 s | 382.3 MB | M1: 4,123 scored, 1,269 raw, 1,254 persistent; M6: same as above; 0 mismatches each |
| MX070/M6, same days | 808,135 / 10 | 43.700–67.975 s in two local runs | 253.5–269.4 MB | 4,256 scored, 163 raw, 33 persistent; 0 candidate/scorer and restart mismatches |

These are individual local wall-clock observations, not a sustained throughput benchmark. All three tested candidates remain `REVIEW_REQUIRED`. MX057/M1's shadow raw-flag share is 30.7786%, far above MX057/M6's 1.1879%; this is a module-specific deviation burden requiring graph/regime/profile review, not evidence of 1,269 confirmed faults. The result also shows why a fleet-wide threshold alone is insufficient. The local replay records timing and peak process memory so later changes can be compared on the same machine and input period. `Asia/Bangkok` remains an assumption for the source timestamps.

The independent MX070/M6 replay has 13,755 observed and 13,584 qualified minutes, with 171 low-coverage exclusions. Its future shadow has 4,256 qualified minutes and 163 flags (3.8299%): 3 on 27 Aug, 37 on 28 Aug and 123 on 29 Aug. `templo` (79), `hp2` (44) and `lp2` (40) were the largest normalized contributors on flagged minutes. Its fitted `Hp_2nd` median is 248.1 **source units**. Being above the owner's approximate 180–230 psi reference does not alone establish a fault; the source pressure unit is still unverified and the local profile itself is machine–module specific. This candidate also remains `REVIEW_REQUIRED`. The 24-second difference between two wall-clock runs on the same input shows why the timing numbers are diagnostic observations rather than a fixed performance guarantee.

The new per-day report narrows the review: M1 was 0/1,430 on 27 Aug, 55/1,264 on 28 Aug and 1,214/1,429 (84.955%) on 29 Aug; among all M1 raw flags the largest local z-score came from `lp2` in 1,107 minutes, `templo` in 147, `temphi` in 11 and Valve in four. M6 was 0/1,430, 31/1,263 and 18/1,432 on the same days; all 21 M6 persistent minutes occurred on 28 Aug. The scorer identifies the **largest normalized deviation**, not a physical cause. Inspect M1's 29 Aug `Lp_2nd` trace, local scale and operating changes before judging whether its profile is stale or the process actually changed.

Performance profiling points to intake/window construction as the dominant local cost: 84.845 of 88.467 seconds in the M1+M6 run, while candidate fit plus shadow scorer replay took 3.622 seconds. Batch reading avoids a second daily-file scan but does not make a full ten-day rebuild a suitable five-minute live loop. Subsequent optimization should benchmark Parquet decoding and one-minute aggregation separately, then test bounded incremental updates; no threshold adjustment is justified by this runtime result.

The final MX057/M6 repeat after source-machine integrity validation preserved all counts and flags and also passed midpoint checkpoint/restart parity. Its 49 raw flags had dominant normalized features `temphi` 27, `lp2` 18 and `templo` four. The script now checks every source row's machine ID against its partition (accepting numeric, `MX` and `HT9046MX-` aliases), so an accidental mixed-machine file fails visibly rather than being relabeled. Runtime varied from 30.625 to 50.039 seconds across local runs; compare timings only under controlled cache/CPU conditions.

## Next local tests, then Server integration

1. Repeat batch replay for the remaining MX057 modules and at least one other machine with ten observed-second days. Compare per-day flags, coverage, profile scale, CPU time and memory; review long flag runs graphically before changing a threshold.
2. Rehearse resume/checkpoint and incremental five-minute fetch using a local database or bounded raw-file stream. Compare it with the full-file replay; the 88-second ten-day rebuild is a calibration benchmark, not the target latency for each live cycle.
3. Once local candidate/scorer parity and alert burden are understood, connect the same versioned pipeline to Server history and fresh data. At that point verify source clock/unit mapping, storage/restart behavior, profile activation and alert/UI behavior on the actual Server. These Server-specific checks do not block the local experiments above.

