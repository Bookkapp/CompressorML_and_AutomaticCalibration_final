# Operation Fleet workflow — items 3–6, local UAT

6 October 2026, Asia/Bangkok. Owner authorized implementation of the original remaining items and requested a Markdown handoff for Codex on Server 10.195.17.73. No remote deployment was performed.

## Delivered scope

| Original item | Shipped behavior | Remaining data / deployment acceptance |
|---|---|---|
| 3. SV ON / Transition Reference | Frozen whole-event response catalog, compatible-source screen, independent historical holdout screen, relative response proposals, capped event-count pooling, explicit reviewer selection, immutable local review and version guard; source graphs and human-readable rejection reasons | Zero donor groups currently pass independent screening. Included SV ON still needs an accepted local steady reference; explicitly excluded SV states do not require one. Actual Normal/configuration certification remains pending. |
| 4. Real validation | Saved historical Shadow report, 1–31 day bounded range, separate excluded/unsupported/quality counts, flagged episodes → actual Raw seconds, prospective-clock guidance; existing real post-freeze validation job retained | Confirmed Normal/fault intervals and untouched observations for at least 3 days after freeze are unavailable. False alert accuracy and fault detection delay are therefore not reported as measured facts. |
| 5. Worker / common Events | Existing durable producer now adds pinned Fleet Shadow evidence to the same Event History transaction/checkpoint; source transitions still captured without Active; explicit SV gate before matrix scoring, restart/retry/version isolation; observation-only scheduler CLI | Actual Server installation/service lifecycle, authenticated producer/management, clock/late-arrival/source-load acceptance are documented for the Server session. Local global Worker remains disabled. |
| 6. Fleet Model Management | Installed-version inventory/checksum verification, isolated one-job training, persisted job recovery, compare, reviewer/reason, revision-CAS Shadow selection and rollback, embedded history; kernel leases released on crash | This is Shadow version management, not a bypass of machine Active/engineering/future-data gates. Retraining with additional machines requires a new verified intake/study. |

## Method and boundaries

The existing Fleet steady model preserves each target's frozen absolute median/scales; compatible Fleet information contributes correlation shape. All 43 steady profiles in the enriched package retain exactly the previous values. The new Transition method uses robust **relative whole-event curves** by source machine, module index, observed origin/destination context and event direction. Donor absolute baselines are never copied to the target.

Target and donor comparisons use an explicit proposal similarity screen; it is not a certified physical limit. Source counts are event counts rather than pretending each correlated minute is an independent event. Machine votes are balanced. A capped three-event prior gives less Fleet weight when a minute bin has more local events. This is bounded empirical partial pooling, **not an implemented exact NIW posterior or Hierarchical Bayesian ARX**. Hardware/configuration equivalence still requires review; module index alone is not proof of interchangeability.

Independent admission requires at least 3 heldout events on 3 days, 30 evaluated curve minutes and outside-envelope fraction ≤10%. A transfer further needs ≥2 compatible donor machines, ≥6 source events and ≥3 source days. This conservative proposal screen is declared and not tuned on a diagnostic fault case. Passing it would only permit review, not automatically certify Normal. Unknown local origin, excluded destination SV, unaccepted origin or failed independent evidence cannot be selected. An unfamiliar flat absolute level remains NEW_STEADY_LEVEL even if a Fleet response envelope is wide.

## Actual data evidence

- Six machines: 017/024/041/058/080/081. Parent study receipts cover 555 prepared days / 46,616,484 original raw rows; this work verifies minute checksums as used and records actual observed event-file checksums.
- New catalog: **144 groups, 512 unique Reference events**; capped source examples and 120-minute horizons. **114 independent historical holdout events**, zero event-ID overlap. Fit and calibration are separate per parent profile; MX080/M6 retains the owner's proposed stable intervals and known acquisition quarantine.
- 63 groups have fitted curve bins; 55 holdout events contain evaluated bins. **1,929 / 2,356 evaluated minutes outside** (~81.9%). All 144 donor groups fail either independent coverage or response screening, so **MX058/M1 has zero eligible Fleet Transition transfers**. Three direction/origin combinations that looked count-compatible before validation are deliberately rejected by the final independent gate. Original measurement/control history remains available for investigation.
- MX058/M1 saved 2–4 October Shadow: **4,320 actual observed minutes; 3,914 supported; 20 flagged (0.510986% burden); 339 unsupported; 67 quality; 7 episodes**. Manual “ดู Raw” opened 05:12–05:32 on 2 October and loaded **1,184 actual rows, zero duplicate seconds**, with pressure/temperature/valve graphs. This is not a measured healthy false-positive rate.
- MX080/M6 owner-described historical case, **7–8 September 2026**, 13:10 on 7 September through before 23:59 on 8 September: 2,089 observed minutes, 2,049 evaluated, all 2,049 raw CP2 flags, 2,039 persistent minutes; 873 evaluated steady minutes remain flagged. Five quality and 35 unsupported minutes retain their distinct categories.

## Manual browser QA

Used browser controls to click the actual Operation UI, not internal browser API calls to create successful outcomes:

1. Fleet Models: reviewer `Codex-local-QA`, explicit QA reason, all six machines, fit 2 July–before15 August and calibration15–before22 August; clicked **เทรนรุ่นใหม่**. Job `410e4726133549a1b63ca70c9e0b9727` completed in **202.894 seconds**, created immutable `fleet-stable-v1-586e67981fc6d695467f0d01`, and left the selected version unchanged until manual approval.
2. Kept MX058 Calibration in another tab during training; actual saved graphs/report remained usable. Selected the trained version, compared the 43 profiles, clicked **Approve → ใช้รุ่นนี้ใน Shadow** (revision18), clicked **Rollback** (revision19), then restored the trained version (revision20).
3. Opened the actual saved MX058 report and its Raw seconds. A browser automation mouse-command timeout occurred after one Raw click; the UI had nevertheless completed the action, with the 1,184-row Raw result visible. No application error was logged. Later frontend hot updates reset transient selections during development; the final UI was rechecked after edits.
4. Opened rejection details, refreshed Fleet Transition after version changes, and opened actual **MX041/M1, 13 July20:30:07** source pressure measurements around an SV event. Source graph is explicitly minute averages ±45 minutes, not synthetic data or Raw seconds; no Normal certification is implied.
5. Final browser error logs: zero errors in both Operation and Calibration tabs. Mock buttons/section remain absent. Chart containers retain the existing fixed 280px plot height and do not display “Loading chart data”. Actual final screenshot/layout inspected; cards/table controls have no overlapping text.

Screenshots: `notebooks/outputs/fleet_workflow_20261006/fleet-model-management.png`, `fleet-transition-evidence.png`, `mx058-raw.png`.

## Worker / concurrency QA

The new Fleet lane is pinned in the persisted run contract. Changing its bundle makes a new run; attempting to advance an old run with another bundle fails. The existing source receipt, cursor, checkpoint, outbox and common Event transaction remain atomic. Persistence spans source midnight in bounded history. Active scope exclusions are applied **before** model matrix scoring, with no scores for excluded states. Derived phase changes during an ongoing persistent flag no longer create a duplicate anomaly-opening event.

Actual SELECT-only source slices were replayed into an **isolated SQLite evidence database**, rather than changing normal analytics detector state:

| Machine | Raw SQL rows | Modules | Completed module-minutes | Repeated slice new rows |
|---|---:|---:|---:|---:|
| 041 | 474 | 8 | 64 | 0 |
| 058 | 473 | 8 | 64 | 0 |
| 080 | 542 | 8 | 64 | 0 |
| 081 | 474 | 8 | 64 | 0 |

Restoring the producer from committed checkpoints and repeating delivery did not add duplicate Events. MX080's selected actual SQL slice contains duplicate seconds; those were retained as 65 duplicate-second Events and eight Fleet acquisition-review Events, not turned into physical fault claims. SV/Valve/module/busy events in the 081 slice were retained. Failure injection in isolated fixtures verifies rollback of the Event/cursor transaction, then successful retry.

Prepared HTTP test: **10 clients, 120/120 successful requests**, warm p50 **60.5ms**, p95 **172.7ms**, max **240.0ms**. Cold prepared request max **3,196.8ms**. These figures exclude cold SQL intake, browser rendering and training; they are not Server SLA claims. Package/assessment caches have bounded entries/bytes and immutable version keys; heavy training runs in a subprocess with BLAS threads capped at one.

API was restarted locally after training; the completed durable job and selected/revision history remained. A stale release HTTP request returned **409**, with the pointer unchanged. Kernel locks protect training and release across processes and release automatically on process death; abandoned jobs become INTERRUPTED rather than keeping a permanent stale PID lock.

## Tests, artifacts and reproducibility

- Full API suite before final lock refinements: **248 passed**. Final affected-package/worker/transition suite including the new state-before-scoring/midnight test: **25 passed**.
- TypeScript check and Vite production build pass. Existing Vite >500kB bundle warning remains; SQLite/Python datetime and notebook Windows event-loop warnings are unrelated to workflow correctness.
- Executed `notebooks/14_Fleet_Transition_Worker_Management_20261006.ipynb`: re-verifies immutable packages, all 43 unchanged steady profiles, unique/disjoint event IDs, actual SQL persistence receipts and HTTP/management results.
- Evidence JSONs are in `notebooks/outputs/fleet_workflow_20261006/`; reproduction scripts `notebooks/support/fleet_transition_build.py`, `fleet_workflow_qa.py`, `fleet_workflow_delivery.py`.
- Original 207 legacy profiles / 46 legacy Active records remained unchanged by canonical snapshot comparison. No actual Context profile/review/Active mutation or source import occurred in this turn. New version history and training artifacts are local Shadow changes only. Context Active remains0; actual Server is not connected.
- Portable verified ZIP for the selected trained version is saved in the evidence directory. No Git commit/push or remote installation was requested/performed.

## Next actual Server action

Copy the checkout and verified package to Server10.195.17.73. Give its Codex **“Set up ระบบนี้ให้หน่อย”**. Entry points are `deployment/CODEX_SERVER_HANDOFF.md` and `deployment/SERVER_WORKER_HANDOFF_20261006.md`. The Server session performs installation and its real restart/clock/auth/source-load acceptance. For model acceptance, collect Engineer-confirmed Normal/configuration and post-freeze observations; do not expand unstable Transition envelopes or label balancing/charging/leak solely from pressure patterns to force approval.
