# MX057 / M1 — confirmed abnormal-behavior case

**Case ID:** `MX057-M1-20260829-001`  
**Confirmation:** project owner, 30 Sep 2026  
**Label:** abnormal telemetry behavior = **confirmed**; equipment damage and physical cause = **not confirmed**.

The confirmed interval is **29 Aug 2026, 04:06–22:50** in source `recorded_at` (Asia/Bangkok assumed). It is the longest uninterrupted run of qualified one-minute persistent anomaly flags (1,124 minutes). The candidate profile used for review was fitted only on 20–26 Aug; 27–29 Aug was future shadow. It was an in-memory `REVIEW_REQUIRED` candidate, not an Active Profile.

The observed-second plot shows `Status_1=ChangeValve` and `Busy_1=1` at 04:00:35–04:03:57, then Valve 83→95, `Lp_2nd` ~10.3→14.0 and `TempLo` ~−8.5→−20.6 in the selected before/after windows. This supports a real operating-pattern change closely following the manual state, but does not tell whether the action was intended or whether a fault exists. The project owner has explicitly confirmed **the behavior is anomalous**. Other flagged intervals on the same day are listed separately in `case.json`, not silently added to this label.

Evidence, in reading order:

1. [Source-second onset and ChangeValve marker](evidence/04_mx057_m1_onset_source_seconds.png)
2. [29 Aug aligned sensor relationships](evidence/02_mx057_m1_relationship_29aug.png)
3. [27–29 Aug shadow overview and M6 context](evidence/01_mx057_shadow_overview.png)
4. [Source-second sustained-hour detail](evidence/03_mx057_m1_source_seconds.png)
5. [Machine-readable statistics and source-state counts](evidence/summary.json)

The day-29 source Parquet SHA-256 is recorded in `case.json`; raw telemetry remains outside this folder. No MySQL feedback row, Active Profile, model, threshold, Health Score or alert was changed by recording this historical case. Future supervised work can use it as a reviewed behavior-anomaly case after label QA, but must keep the episode together across splits and must not treat it as an independently sampled production test.
