# Local source Normal mock — 6 October 2026

Owner explicitly requested inserting mock values into the table currently used by Operation. The earlier isolated sandbox proposal was withdrawn; its unstarted application files were removed. No Mock button or new running port was added.

## Inserted batch

- Target: localhost `ht9046mx_iot.ht9046mx_readings`.
- Machine: `HT9046MX-058` (UI `MX058`), Compressor M1 only.
- Period: **2026-10-06 08:05:00 through 12:21:59**, Asia/Bangkok; end exclusive 12:22:00. First full minute after the original review at08:04:35. No future timestamps or overlap/overwrite.
- **15,420 raw-second rows /257 full minutes**; IDs73688972–73704391.
- Batch `08c03af157479fcede24db1ed6579c57c25130ec6b929ac58fd06ef68dcc88d2`.
- Frozen parent `2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e`; accepted OFF regime `c5b91b3da8e5ea9cd89f`.
- Seed58; six physical channels use fixed small correlated variation around the frozen center. Delta pressures are derived HP−LP. Valve100, moduleOn, Busy0, SVOff; other modules remainNULL. Repetition within each simulated minute is synthetic, not observed sensor dynamics.
- **Global Status=`MOCK_NORMAL`**, an explicit provenance marker, not a real controller status. Numerical probe with Run **only in memory** finds257/257 within the frozen Reference, zero deviations; inserted rows remain marked Mock.
- Source insertion and receipt in `ht9046mx_analytics.ht9046mx_local_mock_batch` committed in one InnoDB transaction. Scoped importer lock, overlap recheck, exact row count and localhost/disabled-detector guards apply.

## Behavior

Raw/graphs remain readable. Context output category `MOCK_DATA` and `MOCK_SOURCE_DATA` explanation distinguish synthetic values. No physical model vote is made; Mock cannot enter Reference fitting. Legacy qualified windows reject the non-Run status. A mixed Context validation receipt containing any such row carries `source_kind=MOCK, approval_eligible=false`, so the existing real approval gate rejects it. Interim summaries retain and display the Mock count. Older immutable interim receipts are normalized on read from their daily provenance; they are not rewritten.

This batch **does not make real Active approval available**. Actual review is today, so the first prospective complete day is7Oct; current closed-day coverage remains0/3. Pressure basis, state/controller/service contracts and included ON Reference also remain unresolved. No date/OS-clock/freeze change, Engineer certification, gate bypass, worker/alert startup or Server action.

## Verification

- First16 targeted provenance/Context scope/scorer tests and12 final provenance/followup regressions pass; final TypeScript check also passes.
- TypeScript and production Vite build pass (existing large-chunk advisory only).
- Actual manual browser on Operation5176: refresh → **ตรวจข้อมูลที่มีแล้ว** → completed job `ccb29671-cec0-457b-8ebb-59f171d00d5b` → **ดูกราฟรายวัน**. Pressure/temperature/Valve graphs display the actual inserted values and Mock label. Inspection takes≈17s; shared open-day cutoff retained254minutes through12:19, as specified by the existing five-minute snapshot and late-arrival rules. No missing minutes in this inspected interval.
- Before/after canonical Profile/Active registries match. Existing source rows were not edited; only the bounded marked batch was inserted. Context inspection adds its normal cache/job/event records; it does not create a new Profile or Active.
- Main API restarted on8000 (final PID13816; PID20420 was the first restart); web5176 preserved. No sandbox API/web launched. Final SQL reread verifies15420 unique seconds, HP2 195.4681–195.5573psi, LP2 12.1422–12.2313psi and no other-module HP2 populated. Saved-chart read confirms254 marked Mock minutes/no model vote; public job provenance isMOCK. Details: `verification.json`. Screenshot: `mx058-normal-table-chart.png`.

## Files and future work

Seeder: `notebooks/support/seed_local_normal_table.py` (plan-only by default; `--apply` explicitly inserts). Its same-day/frozen-period limit intentionally prevents accidental later execution or duplicates. Evidence: `notebooks/outputs/normal_table_20261006/{plan,receipt,registry-before,registry-after}.json`, UI screenshot and final verification.

Do not treat `MOCK_NORMAL` as a new valid Run code or include this batch in healthy training. Keep its SQL ledger and original source marker together when moving data. An eventual removal must target this exact marked machine/time/ID batch and be explicitly requested; do not delete unmarked sensor rows. This is a numerical/table/graph test, not successful real Active UAT.
