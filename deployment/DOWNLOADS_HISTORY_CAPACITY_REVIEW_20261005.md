# MX041 / MX058 / MX081 / MX080 Downloads intake capacity review

**5 October 2026 — inventory and owner-authorized partial three-month import; stopped at owner request.**

## Download inventory

The requested exports are in `Downloads/MX041`, `Downloads/MX058`, and `Downloads/MX081` (three ZIP parts each). The MX080 export is in the five `HT9046MX-Compressor-Data-20261001...` ZIP parts already inspected on 2 Oct.

| Machine | Dynamic day files | Date range | Raw rows | Uncompressed text bytes |
|---|---:|---|---:|---:|
| MX041 | 127 | 1 Jun–5 Oct 2026 | 10,700,805 | 4,758,365,724 |
| MX058 | 127 | 1 Jun–5 Oct 2026 | 10,700,512 | 4,748,710,252 |
| MX081 | 127 | 1 Jun–5 Oct 2026 | 10,699,626 | 4,695,548,795 |
| MX080 | 93 | 1 Jul–1 Oct 2026 | 7,773,188 | 3,472,660,832 |
| **Total** | **474** | — | **39,874,131** | **17,675,285,603** |

Static files and noncanonical `.tmp`/timestamped files were excluded from the daily-file count; no ZIPs were extracted, modified, or deleted. The line count is the number of newline records minus one header per file. The project importer additionally validates the exact 82-column mapping before any row is eligible for import.

## Import performed and current state

The project owner authorized importing the four machines. The importer appended raw dynamic rows to the normal local source `ht9046mx_iot.ht9046mx_readings`, preserving the 82-column wide row and the observed-second grain. Each day is one source-plus-ledger transaction; source rows and a SHA/version receipt are committed atomically. Existing rows were not overwritten. Changed values at timestamps that already existed were retained as additional rows; exact identical occurrence reuse was zero.

| Machine | Committed daily files | Inserted rows | Imported date coverage |
|---|---:|---:|---|
| MX041 | 96 | 8,065,095 | 2 Jul–5 Oct 2026 |
| MX058 | 96 | 8,059,038 | 2 Jul–5 Oct 2026 |
| MX081 | 97 | 8,151,940 | 1 Jul–5 Oct 2026 |
| MX080 | 92 | 7,687,891 | 2 Jul–1 Oct 2026 |
| **Total** | **381 / 474** | **31,963,964** | — |

The importer was resumed for the working three-month window and then stopped immediately when the owner said “พอละแค่นี้ๆ”. Each completed day is an atomic source-plus-receipt transaction. At stop, C: had **24.80 GiB free**; MySQL80 remained running. No Profile, Candidate, Active Profile, score, alert, Server, or MySQL configuration was changed. The interrupted run did not write its optional end-of-run JSON summary, but durable per-file receipts were queried directly from the analytics ledger.

One source-quality issue needs to follow the data into analysis: all four source files dated **12 Aug 2026** are much shorter than a normal day—MX041 7,236 rows; MX058 6,947; MX081 6,916; MX080 11,440. They were ingested as-is, without interpolation. Treat those dates as partial/low-coverage days and inspect timestamp spans before using them for calibration or comparison.

## Three-month analysis scope and stopping point

The working interpretation of “about three months” is **1 Jul–1 Oct 2026**, because MX080's available export ends on 1 Oct. This is an explicit working date assumption. The interval has 372 target daily members (93 per machine). At the owner's stop request, **369/372 target files** were present: MX041 92/93, MX058 92/93, MX081 93/93, MX080 92/93. Exactly three target files were not started: 1 Jul for MX041, MX058, and MX080. The target interval contains **31,042,099 inserted rows**. Including 12 previously imported Oct2–5 files for MX041/058/081, the durable ledger contains 381 receipts / 31,963,964 inserted rows total. June for MX041/058/081 and the 12 later October days are outside the comparison window. No more files were imported after the owner asked to stop.

- D: is NTFS with `Healthy` volume status and **53.27 GiB free** at the preflight check.
- MySQL80's Windows service points to `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe` and `C:\ProgramData\MySQL\MySQL Server 8.0\my.ini`; its configured datadir is still `C:/ProgramData/MySQL/MySQL Server 8.0\Data` on C:.
- The current Codex session received Windows **Access denied** reading/listing the protected datadir. A migration needs Administrator access, controlled stop, verified backup/copy to D:, datadir and `secure_file_priv`/staging path updates, service-account ACLs, restart/data checks, and tested rollback. None of those migration steps were attempted; service/config/datadir location are unchanged. Do not treat D:'s free capacity as proof that MySQL has moved.
- The importer is resumable from the durable daily SHA/version ledger. It skipped matching receipts on resume; source rows are append-only and exact occurrence reuse was zero. Three target daily files remain (MX041/058/080 on 1 Jul), approximately 255k raw rows total by neighboring daily counts. The owner asked to stop; do not resume unless requested.
- MySQL remains on C:; D: had 53.27 GiB free at preflight, but no datadir move was performed. At stop, C: had 24.80 GiB free. No migration was necessary for the work already completed, and no storage/config/service changes were made.

No ZIP was extracted, modified, or deleted. Static and noncanonical `.tmp`/timestamped members remain excluded.

## Initial capacity estimate (historical preflight)

- The live local MySQL source is MySQL 8.0.46, `ht9046mx_iot.ht9046mx_readings`, under `C:\ProgramData\MySQL\MySQL Server 8.0\Data` on C:. It has `innodb_file_per_table=ON`; the configured secure import directory is also on C:.
- At the initial preflight C: free space was about **20.5 GB**. D: had about **57.2 GB**, but the active MySQL source tablespace was not on D:.
- The current source table reports about 9.68 GB data and 0.38 GB indexes for roughly 15.9 million rows. Applying this table's observed average footprint to 39.9 million new rows suggests about **25 GB** including a similar index share. This is a planning estimate, not a guarantee: actual row compression, indexes, overlap reuse, binlogs, and filesystem changes affect final use.
- That estimate exceeded C: free space before preserving the importer's 5 GiB reserve, so the full import was expected to pause. It has now paused after237 daily files as recorded above; the initial estimate was not a guarantee of actual growth.

## Historical capacity checkpoint before the resumed intake

At the earlier checkpoint, C: was near its reserve and storage migration was considered. The later resumed intake proceeded after free space recovered. The notes below explain the unchanged storage layout; they are not a request to migrate now:

1. If a future, separately authorized import is requested, recalculate free-space needs from observed table/binlog growth first and preserve a safe reserve.
2. Moving MySQL to D: would require Windows Administrator, verified backup, controlled service stop, datadir/`secure_file_priv` changes, ACLs and rollback. This was not done or needed to complete the stopped intake.

Existing fixture rows and MX080's earlier rows were preserved; changed same-timestamp rows were appended. The existing Profile registry hash stayed unchanged. No Profile, Candidate, Active Profile, scoring worker, or Server state was changed.

## Evidence and reproducibility

The inventory was read directly from ZIP central directories and counted in streaming 4 MiB blocks; no file extraction was needed. Raw ZIP row totals above were checked against all matching daily member records. MySQL free space, active datadir, table statistics and engine settings were read-only queries. Current exact source-row snapshots from 2 Oct remain in `notebooks/outputs/downloads_history_import_v1/verification.json`; live table statistics are approximate.

Change log: 2026-10-05 — Inventoried474daily files; owner-authorized import stopped on request at369/372 files in the working1Jul–1Oct scope (31,042,099 rows). Three 1Jul files remain (041/058/080); total ledger is381 files/31,963,964 rows including12 later Oct2–5 files. C: had24.80GiB free at stop; MySQL stayed on C:, with no service/config/Profile/Active change. Partial-day counts remain marked for analysis QA.
