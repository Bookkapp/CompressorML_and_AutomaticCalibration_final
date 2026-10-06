# Automatic Candidate preparation — local QA, 3 Oct 2026

## Scope and use

Owner authorized automatic preparation with efficient, simple operation after comparing the old CompressorML v1 repository. Operation now offers: select machine → reviewer → prepare all M1–M8 → inspect each Candidate → open saved graph / adjust Reference when required → human approval when eligible. Manual UI actions used the real localhost page; no scripted workflow POSTs were used. Automatic calculation is authorized in this task; source telemetry remains SELECT-only.

Auto and Manual share `manual-reference-complete-day-shadow-v2`, strict observed-second → 1-minute windows and the same estimator. Default Reference is 28 complete local days, followed by 3 disjoint complete Shadow days. MX017/024 source latest is 1 Oct partial day; the tested Reference is 31 Aug–before 28 Sep, Shadow 28 Sep–before 1 Oct, Asia/Bangkok. Minima remain the existing local settings (3 days/50 minutes); no thresholds, state semantics, units or Active gates were relaxed.

## Changes

- Durable parent job (module 0), stable child job per module, machine admission, idempotency, cross-tab coalescing and atomic Candidate/children/completion transaction. Missing M7 does not prevent other modules from finishing. Expired automatic leases safely requeue; Manual jobs retain their interruption/review behavior.
- Analytics-only compressed daily window cache, per-day MySQL named lock and source count/CRC sum/xor change check. Full closed days may be reused for one hour; partial days are never cached. Changed days are rebuilt. Mixed source revisions across modules cannot be combined. CRC is a change detector, not approval evidence. Storage grows with cached contexts; retention is not configured.
- Raw source reads stream bounded partitions, retain complete minutes and all aliases, and optionally transport exact raw values in minute JSON packets. Qualification/means still run on observed seconds, not SQL AVG. State constants are computed once per chunk.
- Manual Build rereads the selected module's raw seconds without a fleet CRC/cache write, and checks exact SHA256 source-feature evidence. Changed evidence fails the Build and invalidates derived period snapshots for re-preview.
- Source machine inventory is shared across processes/tabs for five minutes. The initial/expired full inventory scan can still be slow; per-module extended availability is optional and runs only when expanded.
- Review copies are owned by the reviewer; an automatic result can be opened without redoing source reads. Selecting a module or day, editing exclusions and building remain separate explicit actions. Existing graphs stay visible while re-previewing; Build is disabled for unreviewed edits. The view scrolls to the opened Review and prioritizes module coverage/statistical reasons.
- JSON-safe graph responses use direct `JSONResponse`, removing repeated recursive chart serialization. UI polls small parent summaries and uses saved graph evidence on demand.
- Scheduler has `--profiles-only --machines MX017 MX024`, registering only the Profile Candidate job. Default cron remains 02:00 Asia/Bangkok; completed preparation retries only after the configured 3 new complete source days. The normal API and scoped local scheduler use the same durable preparation.

## Evidence and measured costs

Evidence folder: `notebooks/outputs/automatic_calibration_qa_20261003/`.

| Check | Result |
|---|---|
| Full API tests after cache/worker changes | 157 passed; existing Python 3.12 SQLite adapter warnings |
| Related API/reference tests after JSON response change | 66 passed |
| Production web build | Passed; existing large JS bundle warning (~772 kB, ~225 kB gzip) |
| Actual 30-minute source transport | 232 windows, all 8 modules exactly equal; 0.53 vs 0.21 s without CRC |
| Actual 1-day source + revision parity | 11,512 windows exactly equal; streamed and SQL fingerprints equal; 20.62 vs 17.78 s including CRC, `as_of=end` excludes final minute under late-arrival grace |
| Two actual browser tabs | MX017 prep shared across tabs; MX024 queued independently; durable results return after API restart |
| First cold preparation, before final transport/TTL optimizations | MX017 854.15 s; MX024 1,141.34 s including queue wait |
| MX017 repeat under rejected 5-minute cache policy | 574.81 s; repeated old-day fingerprints caused delay |
| MX024 repeat under final 1-hour closed-day cache | 75.45 s for all 8 modules |
| Actual 10-client GET load during Manual source verification | 100/100 parent polls: p50 41.93 ms, p95 102.03 ms; 20/20 saved Review graph reads: p50 668.38 ms, p95 1,271.23 ms |

Full-history preparation is a background job, not instant. Cold source reads, checksum revalidation after cache expiry and optional 93-day availability remain expensive on this local database. These measurements are local, not a production SLA or an unlimited-client/device benchmark. The pre-JSON response load receipt used a different concurrent preparation phase and is retained as diagnostic evidence, not a controlled speedup claim.

## Candidate and approval findings

MX017 and MX024 each created 7 Candidates (M1–M6, M8), with M7 showing zero qualified Reference/Shadow minutes and no Candidate. Initial and repeat batches remain inspectable. Four source prerequisites remain unverified: pressure unit, state-contract version, controller-codebook version and service-epoch version. Statistical review blockers also vary by module. MX017/M8 and MX024/M1,M2,M5 pass the tested statistical gates but remain `SHADOW_VALIDATION` because those prerequisites are missing. This is not a healthy label.

Actual Active pointer rows remain 46 with exact unchanged SHA256 `3f2473685cfd3e16e99d6ccb117a970f2a7e4433dcb847d16af5a9767be85c21`. No Active approval, source rewrite, model retraining, PM mutation, Server deployment or Git push occurred. Actual eligible READY→Active still needs verified source prerequisites and human review; synthetic tests do not establish equipment health.

## Installation and operations

Apply both `mysql_reference_review.sql` (existing) and `mysql_qualified_day_cache.sql` to analytics before enabling this code. The latter was applied to localhost only; CREATE IF NOT EXISTS does not repair an incompatible existing schema. Minute JSON transport was validated on MySQL 8.0.46; validate the target MySQL implementation and indexes before deployment.

Run the API and web app normally. For scoped automatic preparation:

```powershell
python -m apps.api.app.worker --profiles-only --machines MX017 MX024
```

The CLI's qualified automatic cycle requires three complete Shadow days and covers M1–M8; use the Manual Review UI for a selected module/custom dates. The worker process must remain running and be managed by the host's service mechanism for restart persistence. No Windows startup/service registration was added.

After the source owner verifies the four prerequisite values, update the corresponding existing settings and create a new round. Old Candidate parameters remain immutable; adding a review note cannot bypass approval gates. The rollback path is unchanged.

## Final UI verification — completed 4 Oct 2026

- Opened saved automatic Review through actual browser clicks for all 16 machine/module combinations (MX017 and MX024, M1–M8). M1–M6/M8 showed the corresponding pressure graphs; M7 explicitly showed insufficient qualified data and blocked Build. Review copies did not create duplicate Candidates.
- MX024/M1 Manual exception test excluded 21 Sep 12:00–12:30 with an explicit QA-only reason. Existing graphs remained visible; edits required a new Preview before Build. After review acknowledgement, the actual fresh-source Build completed in 83.17 seconds and created a `SHADOW_VALIDATION` Candidate. The exclusion was a workflow test, not an assertion that this period was unhealthy.
- At the 1280×900 desktop test viewport, document width and scroll width were both 1,265 px; the automatic cards used four columns without horizontal overflow. The temporary viewport override was reset after testing.
- Screenshots: [Automatic preparation](../notebooks/outputs/automatic_calibration_qa_20261003/automatic-overview.png), [Saved MX017/M8 pressure graphs](../notebooks/outputs/automatic_calibration_qa_20261003/automatic-review-graph.png).
- Final read-only audit: 497 derived cache rows, 54 Reference jobs, and the same 46 Active pointers with unchanged hash. Local API (PID 19848), Vite (PID 16192) and scoped Profile-only worker (PID 18532) were running at handoff. These are local processes, not a persistent Windows service or Server deployment.
