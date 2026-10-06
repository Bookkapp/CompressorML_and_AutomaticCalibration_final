# One-second Valve / Cold-state audit — Phase 7 diagnostic

**Status:** `REVIEW_REQUIRED`, exploratory evidence only (2026-09-24). This is not an approved calibration profile, new model release, fault label, or production test.

## What was read

Original one-second `ht9046mx_readings` Parquet for MX041/M6, MX083/M2, MX072/M1 and MX070/M5: 16 partitions, 1,210,423 source rows dated 2026-08-19 through 2026-09-01.


## Gate and denominators

One module at a time was eligible only when `Status=Run`, `Status_n=On`, `Busy_n=0`, `SV_n=Off`, `Valve_n>=0`, and required pressure/temperature fields were present. The first 180 elapsed seconds of each continuous qualified segment were excluded. A two-second inter-sample gap was tolerated as a missing observation, while a gap above two seconds split the segment. This tolerance is **diagnostic only**; it has not changed the production Data Gate. The resulting 981,831 eligible *observed samples* are 81.11% of the 1,210,423 selected source rows. Two selected 2026-09-01 module-days had zero eligible samples; they remain in the denominator and are not treated as normal or abnormal.

## What the second-level evidence shows

1. All four selected candidate profiles have `valve__scale=0.05`, inherited from the earlier generic zero-MAD fallback in `phase7_benchmark.py`. `Valve_n` in these samples is an integer command. Thus a one-step shift produces `|rz_valve|=20` and exceeds the candidate's Self threshold (~7.69), even if it is a stable command. This explains why the current Self lane is not reliable as a release gate. It does **not** prove all Self flags are harmless.
2. MX041/M6 already had a daily qualified Valve median of 99 on 2026-08-22 versus its train-only median 104, *before* its outer future period. MX072/M1 likewise had 81 versus train-only 78 on 2026-08-19. Therefore later `ChangeValve` events cannot by themselves explain every profile mismatch.
3. Across selected days, 27 `Busy=1`/`Status_n=ChangeValve` episodes were found. Six had at least 300 qualified observed samples in both the ten minutes before and minutes 3–13 after the manual episode. For MX041/M6 at 2026-08-28 02:17:59, qualified medians moved Valve 113→84, `Hp_2nd` by −0.30 source units, and `Lp_2nd` by −8.5. A second MX041/M6 event at 12:30:54 moved Valve by +11 and `Lp_2nd` by +8.7. The shapes visibly differ, so one fixed Valve→pressure rule is unsupported. MX070/M5 has a paired event with Valve −5 and `Hp_2nd` −65.75, but operating recipe/load and source units are unknown; this must be investigated as a state/context transition, not labeled as a fault or valve causality.
4. There were zero isolated `|ΔValve|>=3` steps inside an already settled, continuously qualified Cold period with an exact one-second 20-second pre/60-second post event window. The larger moves observed here occur in manual-control sequences and are rightly excluded from Cold response fitting. There is insufficient clean-event coverage for a second-level Valve→pressure lag model from this sample.

`Hp_2nd >230` remains separate high-side/local-deviation evidence under `README_System.md`; MX070's higher local baseline here does not establish cause, safety, or a universal normal range. No causal claim can be made from these before/after associations.

## Decision for the system

- Keep the present five-minute scoring cadence. This audit reads original second-level history; the live worker does **not** yet compute one-second hybrid features and the new Cold ARX candidate is **not** using MySQL `ACTIVE_FROZEN` profiles.
- If second-level features are eventually deployed, ingest or retain original second-level rows in a bounded ring buffer and summarize coverage, transitions, slopes, differential pressure and lag response into each five-minute score. Five-minute or one-minute aggregates cannot reconstruct missing one-second events. Require source timezone, unit, late-data/restart parity and server latency checks first.

## Reproduce and inspect

Run `py -3 -X utf8 -m notebooks.support.one_second_valve_audit` from the project root with the original Parquet export and minute-cache/candidate artifacts in their documented paths. `selected_contexts.csv`, `one_second_daily_context.csv`, `manual_changevalve_plateaus.csv`, `isolated_valve_step_responses.csv` and `one_second_audit_summary.json` are the tabular evidence. `figures/*_manual.png` shows the one-second manual-control episode with Valve, CP2 high and low pressure on separate axes; the blue shading is the **excluded** manual state. The daily figures are illustrative qualified Cold periods, not proof of normal health.

The analysis does not modify raw data, Active Profiles, thresholds, model weights, Health Scores or technician labels. No `ChangeValve` episode is treated as training-normal data. Missing recipe/load/facility-water and service/refill records, plus the absent source timezone/unit contract, prevent a production conclusion.
