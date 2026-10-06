# Reviewed anomaly cases

Each case records a reviewed **telemetry-behavior anomaly** with exact machine, module, interval, evidence and label provenance. A behavior-anomaly label does not imply a confirmed equipment fault or known physical cause. Keep the case interval together when constructing a future train/validation/test split; do not infer labels for adjacent minutes, manual-state rows, or other machines.

| Case | Status | Scope | Evidence |
|---|---|---|---|
| [MX057-M1-20260829-001](MX057_M1_2026-08-29/README.md) | Project-owner-confirmed behavior anomaly | MX057 / M1, 29 Aug 2026 04:06–22:50 (source clock, Asia/Bangkok assumed) | One-minute shadow and observed-second plots |
| [MX080-M6-20260907-001](MX080_M6_2026-09-07/README.md) | Project-owner-confirmed anomaly / reported equipment issue | MX080 / M6, 7 Sep 2026 12:23:28–8 Sep 00:00 (source clock, Asia/Bangkok assumed) | Observed-second forensic source; strict 1-minute incremental replay and historical Active-profile replay |

These historical review cases are separate from the prospective technician feedback/alert tables. Their labels can be considered for future supervised development only after label QA and leakage-safe episode grouping.
