# Case regression and five-minute delivery rehearsal

**Run date:** 30 Sep 2026. **Result:** `CASE_AND_INCREMENTAL_REGRESSION_PASS`. This is a local historical replay of two project-owner-confirmed cases using the existing qualified one-minute robust-z/persistence scorer. The source clock is interpreted as Asia/Bangkok. It is not a Server throughput measurement or an independent prospective accuracy test.

## Inputs and profile fitting

| Item | MX057 / M1 | MX080 / M6 |
|---|---|---|
| Source | Daily raw Parquet machine=057 | Existing Module 6 observed-second forensic Parquet |
| Past fit | 20–26 Aug 2026, 7 days | 3–6 Sep 2026, 4 days |
| Evaluation | 27–29 Aug, 254,416 raw rows | 7 Sep, 84,257 raw rows |
| Profile status | REVIEW_REQUIRED | INSUFFICIENT_DATA |
| Score threshold | 6.9640463485078214 | 7.8593737923352505 |
| Confirmed case | 29 Aug 04:06–22:50 | 7 Sep 12:23:28–8 Sep 00:00 |

Profiles were fitted only on past data. Neither confirmed case contributes to its fitted median, scale or q99.5 threshold. The scorer still uses nine features and three consecutive qualified primary-score flags. No threshold was retuned to these cases. Both profiles are in-memory diagnostic candidates. MX080 has insufficient history for seven-day calibration and insufficient evaluation length for three-day shadow; its successful case detection does not resolve those coverage limits. The forensic MX080 source had ambiguous duplicate timestamps excluded in earlier processing, so the replay is scoped to that retained file.

The experiment explicitly pins minimum calibration to 7 days/200 windows, shadow to 3 days/200 windows, quarantine z to 8, maximum quarantine to 5%, maximum half-period shift to 1.5 robust scales and maximum shadow flags to 1%. This avoids local `.env` overriding the experiment's gates: the inspected local minimum-days configuration was 3. The local environment itself was not edited.

## Case detection

| Result | MX057 / M1 | MX080 / M6 |
|---|---:|---:|
| Qualified minutes inside confirmed interval | 1,124 | 693 |
| Raw flagged minutes inside interval | 1,124 | 693 |
| Persistent minutes inside interval | 1,124 | 687 |
| First persistent window inside case (window start) | 29 Aug 04:06 | 7 Sep 12:24 |
| First persistent result available in five-minute delivery simulation | 29 Aug 04:10 | 7 Sep 12:30 |

The MX080 incident anchor is the first observed `Hp_2nd >300` at 12:23:28. Its first persistent result becomes available at 12:30 in this five-minute schedule, 6 minutes 32 seconds later. A one-minute window must close and pass the 30-second late-arrival grace before it is delivered. The results do not imply that live Server ingestion has the same timing.

The primary persistence rule can span different dominant features: MX080 at 12:22 is dominated by `TempLo`, then 12:23–12:24 by `dp2`. Thus 12:24 is the first persistent *multifeature anomaly* window in the confirmed interval, not a claim that pressure alone exceeded a threshold for three minutes. The new strict one-minute contract has no separate three-minute post-manual settling filter; the historical Active-profile replay used a different feature/state contract and first persisted at 12:26. Those timestamps are not interchangeable.

MX057/M1 on 27 Aug retains its historical zero-flag result across 1,430 qualified minutes. Other reviewed-source flags remain visible: MX057 has 82 raw/71 persistent minutes before its confirmed interval across the three evaluation days; MX080 has 23 raw/17 persistent minutes before 12:23:28 on 7 Sep. Their occurrence is not automatically labeled a false alarm or normal data. MX080's earlier high score around 08:00 and temperature-dominated minutes before the pressure event warrant separate review.

## Incremental parity and edge checks

`CompletedMinuteStream` receives chronological, non-overlapping source slices every five minutes. It emits completed one-minute windows and retains the still-open minute. Retries use a batch ID and payload digest; source duplicate seconds within a batch are preserved for the quality gate. Late samples in an open minute can arrive during grace; samples for a closed minute are reported as late and do not rewrite earlier evidence.

| Check | MX057 / M1 | MX080 / M6 |
|---|---:|---:|
| Five-minute cycles, plus final grace flush | 864 | 288 |
| Observed module-minute windows | 4,308 | 1,430 |
| Scored minutes | 4,123 | 1,194 |
| Window differences versus whole-data builder | 0 | 0 |
| Score/evidence differences versus one-shot scorer | 0 | 0 |
| Missing/unexpected emitted windows | 0 / 0 | 0 / 0 |
| Repeated batch deliveries tested | 51 | 17 |
| JSON checkpoint/restart cycles | 35 | 12 |
| Duplicate/retry errors | 0 | 0 |
| Deliberate late-after-close probe rows dropped | 1 | 1 |
| Largest pending source-row buffer after a cycle | 60 | 60 |
| Cycle processing p95 | 16.010 ms | 13.317 ms |
| Cycle processing maximum | 30.568 ms | 20.011 ms |

Timings include window construction, scoring, retry and checkpoint probes for one module; they exclude source decoding, MySQL queries, network, persistent storage and UI rendering. The complete fit/replay run took 146.165 seconds. Retaining 60 pending rows describes the incremental stream buffer, not total process memory: the benchmark also retains reference windows and evidence for comparison.

Twenty-three targeted tests passed (`test_qualified_stream.py` and `test_qualified_temporal.py`), covering observed coverage/state rules, source duplicates versus delivery retry, late data inside/outside grace, incomplete-minute restart, changed retry payload, backwards clock, future samples, wrong checkpoint version, scorer parity and temporal state. The graph was visually inspected; absent minutes and unscored minutes remain gaps.

## Files and next integration step

- `summary.json`: aggregate counts, gates, timings and case timestamps.
- `case_incremental_timeline.png`: owner-confirmed case shading and score/threshold traces.
- Local, ignored `MX057_m1_minute_evidence.csv` and `MX080_m6_minute_evidence.csv`: exact per-minute results and simulated availability times.
- `apps/api/app/qualified_stream.py`: pure incremental window buffer; not wired to live MySQL workers.
- `notebooks/support/case_incremental_replay.py`: reproduction command and case regression assertions.

Reproduce from the project root:

```powershell
python -m notebooks.support.case_incremental_replay --raw-root '<local table=ht9046mx_readings folder>'
python -m pytest apps/api/tests/test_qualified_stream.py apps/api/tests/test_qualified_temporal.py -q
```

The next integration step is local MySQL source cursor + durable checkpoint/evidence transactions + Dashboard transport using a reviewed, matching one-minute Active Profile. This rehearsal wrote no database, profile, model, Health Score or alert.
