# MX058 frozen Reference normal Mock — 6 October 2026

## Later owner correction: remove Mock from the website

On6Oct, owner asked to remove the clickable Mock section and confirm original next items3–6. Deleted `ContextMockValidation.tsx` and its workspace mount/import, frontend API wrapper/type and CSS. Step3 directly shows real-data validation/readiness/Approve. Actual saved MX058/M1 view has zero Mock buttons and no console errors; final TypeScript/Vite production build passes (existing large-chunk warning remains). Screenshot: `notebooks/outputs/mx058_normal_mock_20261006/mx058-mock-removed.png`. No source, review, model or Active mutation was performed. Internal QA generator/tests/receipt rejection and historical evidence remain; the Mock UI description below is historical.

The earlier plan's next items are3reviewedSVON/TransitionReference,4realhealthy/frozenfuturevalidation,5ServerWorker/commonEvents,6FleetModelManagementUI. Intentionally excluded ON remains NOT_EVALUATED and is not required for OFF-only acceptance. Fleet Transition transfer remains a next implementation task; removal of the UI does not complete those model/Server tasks.

## Request and result

Owner asked whether Fleet Stable supplies Transition References, and asked for new Normal mock values while MX058 is validating a frozen Reference. Operation now provides an explicit **Mock** action in step 3, with three selectable virtual days and pressure/temperature graphs. The actual saved MX058/M1 Reference was used without refitting.

**Fleet Stable v1 capability:** its frozen profiles cover steady physical distributions and selectively shared correlation shape. Bundle `transition_counts` are observed event statistics with `transitions_voting: false`; they are not approved response envelopes. Local context Transition envelopes are still proposed from the target machine's Reference events. Automatic Fleet-to-Local Transition envelope transfer is not implemented. The Fleet UI now states this limit. Existing all-event history remains available.

## Exact test inputs

| Item | Value |
| --- | --- |
| Machine / module | MX058 / M1 only |
| Frozen reviewed Profile | `2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e` |
| Preparation job | `defaf170-eafb-436f-a4a4-0eafabbe3d4e` |
| Actual Reference / historical Shadow | 3 Aug to before 2 Oct / 2 Oct to before 5 Oct 2026 |
| Saved review | Revision 1, 6 Oct 2026 01:04:35.480746 UTC |
| Mock version / seed | `frozen-reference-normal-mock-v1` / 58 |
| Virtual mock period | 7 Oct to before 10 Oct 2026, Asia/Bangkok |
| Grain | 4,320 synthetic minute observations, 1,440 per day; not ingested Raw-second readings |
| Operating context | One accepted Steady SV OFF regime; no invented Transition or ON data |
| Pressure | psi; real psig/psia contract remains unverified |

The selected regime has 37 source days / 7,122 Reference minutes. Six physical channels use deterministic small sinusoidal variation, amplitude coefficient 0.04 of their frozen scales. Delta pressures are calculated from HP minus LP. Simulated quality/control witnesses are labeled synthetic; they do not demonstrate real acquisition coverage. The frozen `assess_context` evaluator and existing validation accounting are called without fitting parameters from the mock. There is no HPO or outer-test inference in this software smoke test.

## Implementation

- `apps/api/app/context_mock.py`: bounded deterministic generation, saved accepted-regime requirement, virtual dates after review, one-day chart response, explicit `source_kind: MOCK`, `prospective: false`, `approval_eligible: false`.
- `apps/api/app/context_api.py`: reviewer-required GET `/api/v1/calibration/context/profiles/{profile_id}/mock-validation`; bounded existing wire cache keyed by frozen Profile/seed/day/source/config/version.
- `apps/api/app/context_review.py`: explicit `MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE` blocker. Even changing a mock receipt's prospective bit cannot make it eligible for Active.
- `ContextMockValidation.tsx`, API/types/workspace/CSS: on-demand action, three-day selector, profile/module/SV/version labels, missing-state warning and two fixed 280px charts. Day changes retain the prior view while fetching; the keyed Profile component isolates machines/modules.
- `FleetStablePanel.tsx`: explains that Fleet Transition statistics do not yet fill Local Transition References automatically.

Mock receipts are returned to the browser and saved in the QA evidence folder only. The action does not update sensor source, Reference, jobs, source clock, events, validation records or Active pointers. It does not fabricate future validation from actual new sensor data.

## Verification

- Targeted mock, scope and workflow suites: **20 passed**; existing loky warning only. Tests cover deterministic physical values, no frozen-model mutation/refit, dates/timezone/day bounds, missing ON/unreviewed Reference, rejection as Active evidence and concurrent seed isolation.
- Final TypeScript check and production Vite build passed. Existing large-chunk warning remains.
- Actual Operation UI: selected MX058/M1 and its saved review, clicked Mock, viewed 7/8/9 October, verified result/version/missing ON notice and pressure/temperature graphs. Desktop width 1,265px equals document width; both chart areas remain 280px. No browser error logs in the tested tab.
- **4,320/4,320 simulated minutes** assessed `WITHIN_PROPOSED_STEADY`, three supported days, **Flag 0.00%**, zero unresolved minutes.
- Prepared GET load check: **8 clients, 48/48 successes**, warm p95 **641.7ms**, maximum **690.4ms**, including JSON parse. This excludes browser rendering, source preparation, ingestion and target-Server performance; first HTTP was already warm.
- Before/after frozen Profile canonical SHA matches: `9e7fc32dd3df76c1a31f1e7bcd075e1f5aa5e1c5bec5fde4a743296c6c50bd41`. Legacy 207 Profiles / 46 Active canonical hashes match; Context Active remains 0; import receipts remain 567. Evidence comparison is exact.

## Interpretation and real remaining gates

This proves the software accepts reference-close synthetic steady observations and renders its result with a frozen model. It does **not** prove healthy-machine accuracy, transition acceptance, independent data performance or Active eligibility. The tiny designed variation is a smoke-test input, not an estimated real noise distribution.

MX058/M1's saved scope includes OFF and ON but its four accepted regimes are OFF only. Real readiness remains false: state/controller/service/pressure-basis contracts, an accepted Reference for included ON, and actual prospective validation are required. Other MX058 modules were not reviewed or mock-tested by this action. User-entered Engineer-note text was not certified or changed.

Next Fleet enhancement, if undertaken: build separately reviewed SV/Valve response envelopes grouped by direction, origin regime and compatible configuration, evaluate delay/overshoot/new steady levels, then validate selective transfer on held-out local events. Do not use event counts alone to treat a response as Normal or suppress anomalous plateaus. This enhancement is not part of the delivered Mock feature.

## Evidence and services

- `notebooks/outputs/mx058_normal_mock_20261006/qa.json`, `before.json`, `after.json`, three `mock-2026-10-0*.json.gz` responses and `mx058-normal-mock.png`.
- Reproduce saved reviewed-profile HTTP checks: Python 3.12 `-m notebooks.support.mx058_normal_mock_qa` from the repo root. Requires the saved profile and baseline receipt, local API/MySQL; GET-only.
- Local service receipt: `notebooks/outputs/mx058_normal_mock_20261006/services.json`. API PID 3528 on 8000 replaced owned PID 19008; web PID 1332 on 5176, MySQL PID 6140 on 3306. Prior Fleet run's API process receipt is historical. No target Server deployment.
