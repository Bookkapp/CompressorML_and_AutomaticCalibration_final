# MX080 / M6 — confirmed anomaly case

**Case:** `MX080-M6-20260907-001`. The project owner reaffirmed on 30 Sep 2026 that MX080/M6 had a real issue. This record preserves the previously investigated high-pressure episode: **7 Sep 2026 12:23:28 through midnight** (source clock; Asia/Bangkok assumed). The physical cause is unspecified. The start is the first observed `Hp_2nd >300` in the existing second-level forensic file, not a universal anomaly threshold.

The source is the 424,894-row Module 6 forensic export for 3–7 Sep, whose SHA-256 is in `case.json`. Missing seconds and ambiguous timestamps were documented by the earlier forensic analysis. Other dates, including the temperature-dominated flags on 5 Sep, retain their separate review status.

The current [case regression and incremental replay](../../notebooks/outputs/case_incremental_replay_v1/README.md) uses the shared qualified observed-second → one-minute scorer. It fits only 3–6 Sep, then evaluates 7 Sep with five-minute source deliveries, retries and checkpoint/resume. Four reference days do not satisfy the normal seven-day calibration requirement; this in-memory profile is a diagnostic comparator, not an Active Profile. The earlier [actual historical Active-profile replay](../../notebooks/outputs/mx080_active_profile_replay_v1/README.md) remains a separate contract and result.

Recording and replaying this case does not write a technician-feedback row or retrain a model. Future train/test allocation should keep the incident as a single episode group.
