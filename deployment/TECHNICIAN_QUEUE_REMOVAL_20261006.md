# Technician queue UI removal — 6 October 2026

Owner requested removal of the separate technician confirmation feature in Operation.

Removed the navigation/page, confirmation drawer and form, episode-only formatter, selected-incident state, 10-second incident polling, unused incident/simulation/confirmation client calls and queue/drawer styles. Operation navigation now contains Calibration, Active Profiles, Event History and Fleet Models.

Existing historical confirmation records and server compatibility routes are retained. No maintenance history, Profile/Active registry, source rows, Engineer reference requirements or manual approval gates were modified. Technician inspection can still be documented through the operational Dashboard's Maintenance/Service Log workflow; removing this separate UI does not establish fault or Normal labels automatically.

Verification: TypeScript and production frontend build pass; 12 existing API regressions pass. Actual localhost:5176 navigation has zero technician-queue buttons and no console errors. Screenshot and verification: ../artifacts/technician-queue-removal-qa/. No Operation backend restart or Server deployment was needed.
