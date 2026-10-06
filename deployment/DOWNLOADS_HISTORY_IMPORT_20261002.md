# นำ raw logs MX017 / MX024 เข้า localhost MySQL

2 October 2026 · Owner-authorized historical import · **สถานะ: นำเข้าครบและตรวจ raw/SQL/API/UI แล้ว**

## ผลที่ตรวจสอบได้

| เครื่อง | Dynamic files | แถวใหม่จาก ZIP | แถวรวมใน source (รวม480เดิม) | ช่วงข้อมูล |
|---|---:|---:|---:|---|
| MX017 | 93 | 7,772,969 | 7,773,449 | 1 Jul 00:00:00 – 1 Oct 15:55:01 |
| MX024 | 93 | 7,801,416 | 7,801,896 | 1 Jul 00:00:00 – 1 Oct 15:45:00 |

ปี2026ทั้งหมด; ข้อมูลใหม่รวม15,574,385แถว. ตารางsourceทั้งหมด15,896,585แถว จาก322,200แถวเดิม. วัน1Octไม่เต็มวัน ไม่ถูกใช้เป็น historical complete-day Shadow โดยอัตโนมัติ. หน้า Operationจริง5176แสดงทั้งสองเครื่องด้วยจำนวน/เวลาเดียวกับ SQL และสถานะ `Needs Calib`: **นำเข้าเสร็จ ไม่ใช่สร้าง Active แล้ว**.

หลักฐานหลัก: `notebooks/outputs/downloads_history_import_v1/verification.json` และภาพ `operation-imported-fleet.png`; generated outputsอยู่ในlocal/ignored. Import ledgerในanalyticsเป็นแหล่งreceiptรายไฟล์ที่คงอยู่ แม้หยุดหรือรันซ้ำ; limited-run JSONไม่ใช่inventoryเต็ม.

## ขอบเขต

ต้นทางเป็น ZIP ห้าส่วน `HT9046MX-Compressor-Data-20261001T095156Z-1-001..005.zip` ใน `C:/Users/Book/Downloads`. นำเข้าเฉพาะ dynamic daily files ของ017และ024 เครื่องละ93ไฟล์ ตั้งแต่1Julถึง1Oct2026; วัน1Octเป็นวันบางส่วน. ไม่อ่าน `_Static.txt` และไม่นำ080เข้าหรือแก้ข้อมูล080

เป้าหมายจริงบนคอมนี้: **127.0.0.1 / ht9046mx_iot.ht9046mx_readings** ซึ่งหน้า Operation5176/API8000ใช้อยู่. เพิ่ม analytics metadata table **ht9046mx_analytics.ht9046mx_history_import_file** สำหรับ file hash/receipt/idempotency. ไม่เชื่อม Server10.195.17.73 และไม่สร้าง/Approve Profile, retrain, enable worker/Alert หรือ push Git

ไฟล์มี82ช่อง: Time/Status +10tags×8modules. ประกอบ recorded_atจากวันที่ชื่อไฟล์กับTime เก็บ source wall clockเดิม โดยตีความAsia/Bangkokเป็นสมมติฐานlocalที่ยังต้องยืนยัน ไม่เปลี่ยน timezoneหรือunits. ไม่ aggregate/interpolate; pressure/temperature/valve/status/Busy/SVทุกโมดูลเก็บตามค่าต้นทาง แม้manual/non-Cold/เปลี่ยนวาล์ว. ไม่มี healthy/fault labelจากการนำเข้า

ก่อนนำเข้ามีข้อมูลตัวอย่าง017และ024อย่างละ480แถวอยู่แล้ว. เปรียบเทียบ timestampและ81value columnsแบบmultiset: reuseเฉพาะoccurrenceที่เหมือนทุกช่อง มีอยู่จริง และยังไม่ถูกนับreuse; duplicate occurrencesจากไฟล์ต้นทางยังเก็บครบ. ถ้าtimestampทับแต่ไม่reuse จะเก็บเป็นอีกoccurrenceและรายงานเพื่อreview ไม่overwriteแถวเดิม; minuteที่มีduplicateจะถูกGateเดิมปฏิเสธ

## วิธีรันและความปลอดภัยของการรันต่อ

โค้ด: `notebooks/support/import_downloads_history.py`. Defaultตรวจ inventory/planอย่างเดียว; **--applyเป็นการเพิ่มข้อมูลจริงในlocal source**. Target-host/schemaและmachine allowlistบังคับในโค้ด

```powershell
python -m notebooks.support.import_downloads_history
python -m notebooks.support.import_downloads_history --apply
# หรือสอง terminal แยกเครื่อง ไม่ให้เครื่องเดียวกันรันซ้อน
python -m notebooks.support.import_downloads_history --apply --machines 017
python -m notebooks.support.import_downloads_history --apply --machines 024
```

แต่ละเครื่องใช้ MySQL named lock; day/source rows + import receipt commitในInnoDB transactionเดียวกันข้ามสองschemasบนlocalhost. File ledger unique(machine,date), versionและSHA256ต้องตรงก่อนskip; เนื้อหาที่เปลี่ยนต้องreconcileแยก ไม่เขียนทับเงียบๆ

ใช้ `LOAD DATA INFILE` จากdirectory `secure_file_priv` ที่MySQLตั้งไว้แล้ว. ไม่เปิด `local_infile`, ไม่เปลี่ยนbinlog/foreign-key/flush/security settings. สร้างTSVชั่วคราวเฉพาะfileUUIDในrestricted Uploads แล้วลบเฉพาะไฟล์ที่importerสร้างหลังtransaction; ZIPต้นฉบับไม่ลบ. Rejectinvalidschema/time/infinite/textcontrol/length และ SQLconversionwarningsโดยrollbackไฟล์ ไม่ใช้IGNOREหรือcoerceค่าให้ผ่าน. NumericNULLยังเป็นNULL ไม่เติม0

ตรวจfree diskอย่างน้อย15GiBก่อนเขียนไฟล์ใหม่แรกของrun และ5GiBก่อนเขียนไฟล์ใหม่ถัดไป. การretryที่checksumตรงและskipทุกไฟล์ไม่ต้องมีพื้นที่เผื่อนำเข้าทั้งชุดอีก. ช่วงนำเข้าอ่านข้อมูลจากเว็บได้ แต่บางช่วงอาจช้าลงเพราะDB/diskกำลังทำงาน. ไม่ต้องเปิดworkerเพื่อให้importสำเร็จ. หลังนำเข้าเหลือพื้นที่Cประมาณ14GiB; ไม่ลบZIPหรือMySQLbinlogเพื่อเพิ่มพื้นที่

## หลักฐาน QA ระหว่างงาน

- Importer unit tests10passed: mapping, timestamps, text/domain boundaries, numericNULL, scopeไม่รับ080, manual statesและmultisetduplicate handling
- Technicalfirst-file85,195rowsเข้าสำเร็จ; fullrunข้ามfileเดิมตามchecksum
- เปลี่ยนจากsingle-runเป็นtwo-machine local runsหลังหยุดprocessที่เราสร้าง. ตรวจconsistent SQLsnapshotแล้ว source rows =480เดิม +sum(inserted_rowsจากcommittedreceipts) ของแต่ละเครื่อง ไม่มีhalf-fileที่ไร้receipt
- ลบเฉพาะgenerated TSV23MBที่processเดิมทิ้งไว้: `ht9046mx-owner-history-0bfa53c70cb94daaa804110215c52ea2.tsv`; ไม่ลบZIP/rawlogs. เป็นไฟล์สร้างใหม่ได้จากZIP
- MX080ก่อนตรวจต่อ:8,582rows; SHA256ตามidของทุกrow `5e7e71bef5425215807565e8fe99cebc82e6a6a7ce682d5d889644154a2f9498`. จะตรวจซ้ำเมื่อจบ
- NormalProfile119/Active46เป็นexisting local registryรวมfixture; importerใช้hashเทียบก่อน–หลัง ไม่เปลี่ยนapprovalหรืออ้างproduction readiness

## QA เมื่อครบ186ไฟล์

- Ledgerครบ93files/เครื่อง; sum(raw)=sum(inserted)+sum(reused); reused0ทั้งสองเครื่อง. ไม่ใช่การdrop duplicateต้นทาง
- เปรียบเทียบ204source rowsจาก6daily files (1Jul/15Aug/1Octทั้งสองเครื่อง), seed1302: recorded_atและ81valuesตรงกับSQLทุกช่อง. เป็นsample audit ไม่ใช่full-rowhashของ15.6Mrows
- First-hour1Jul/M6 raw→1mเทียบกับreal SQL loader: เครื่องละ60windows **exact match** รวม120windows. Gateผ่าน01755/60และ02459/60; remainderยังNOT_SCOREDตามเหตุผลเดิม ไม่มีการลดcoverage/state/duplicate gates
- แถวต้นทางที่อยู่ในกลุ่มtimestampซ้ำ:01740,617;02413,143 (`duplicated(keep=False)` ไม่ใช่จำนวนแถวเกิน). Out-of-ordersteps700/220; nullcells0. เก็บrawตามเดิม ไม่มีinterpolationหรือhealthy labels
- Existing-source timestamp overlapsที่ไม่ได้reuse:017474/024473incomingoccurrences; original480/เครื่องไม่ถูกลบ. บางminuteจึงถูกduplicate gateปฏิเสธ แม้coverage inventoryแสดงมีข้อมูล
- ตรวจold/newoccurrenceแรกที่timestampตรงกันของแต่ละเครื่อง: numeric fieldsหลายช่องต่างกัน และ024มีmoduleStatusต่างกันด้วย; ทั้งold/newไม่มีNULL. จึงไม่ถือว่าเป็นfull-rowduplicateหรือเติมNULLจากrawโดยอัตโนมัติ. เป็นเพียงสองตัวอย่าง ไม่ยืนยันprovenance/สาเหตุความต่างของ480เดิมทั้งหมด
- Actualretry firstfileของทั้งสองเครื่อง: `already_imported=true`, newrows0, registryunchanged. Interrupted originalrunมีatomic receipt/countparityและresumeด้วยhashสำเร็จ
- MX0808582rowsทุกช่อง/hashยังเดิม; Profile119/Active46ทุกrowhashยังเดิม. Analyticsfileledgerใหม่เท่านั้น ไม่มีCandidateBuild/Approval/retrain/worker/PM Alert activationโดยงานนี้
- FullAPI+importer suite158passed; source discovery/APIและmainUIตรงกับSQLcounts/latest. Earlier audit assertion on raw017key was corrected to the endpoint's existingdisplayID `MX017`; no data changed to make an assertion pass

### ความเร็ว source-day inventory ยังเป็นงานเปิด

หลังเพิ่มข้อมูลจำนวนมาก queryเก่า93dayGROUP BYเลือกfull-table scan/filesortและHTTP90sหมดเวลา. เปลี่ยน `reference_availability.py` เป็นdailyboundedqueriesบนconnection/snapshotเดียว ใช้existingmachine/timeindexและintegerdistinctminute-of-dayแทนstring; counts/aliases/NULL/latestinclusive/defaultdatesไม่เปลี่ยน. เพิ่มregressiontest dailybounds/duplicate/NULL/snapshot. EXPLAINของonedayเป็นrange `idx_comp_machine_time`.

**นี่ไม่ใช่การยืนยันว่าlatencyแก้แล้ว**: actualMX017/M6หลังbulkimportใช้120.462s (ยังมีaudit/discoveryอ่านพร้อมกัน). Latest1Oct15:55:01; Reference31Aug–28Sep exclusive มี28observeddays/40,318observedminutes; Shadow28–30Sep มี3days/4,320observedminutes. Coverageไม่ใช่qualifiedCold/healthyreadiness. GUIdiscoveryแสดงข้อมูลได้ แต่ inventory93วันยังช้า; cache/query/index/loadacceptanceต้องวางแผนก่อนproduction. No DBindex/config/security change.

ActualMX024/M6หลังนำเข้าครบ:78.480s; latest1Oct15:45:00, Referenceช่วงเดียวกัน28days/40,320observedminutes, Shadow3days/4,320observedminutes, backtrack0และไม่มีno-log/missing-sensor datesในdefaultShadow. เป็นcoverage auditเท่านั้น ไม่ใช่qualifiedCold/approval. ทั้งสองคำขอHTTP200; ตัวเลขlatencyแต่ละครั้งไม่ใช่p95/SLAbenchmark.

### QA ตาม README_System §21

- System/data: actuallocalhostschematarget, mappingครบ8modules, secondgrainและrawduplicates/manualcontextsคงเดิม, SQL/API/UIreconciled
- Model/evidence: nofit/HPO/newthreshold; train-only/outertestrequirementsไม่ถูกแตะ, noapproval/health/faultclaimจากcoverage
- Reproducibility: fiveZIPhashes/filehashes/importerversion/seed1302/durableledger; retriesและsample/windowparityตรวจจริง
- Presentation: เครื่อง/จำนวน/วันล่าสุดบนmainUIตรงกับsource; `Needs Calib`ไม่ถูกเปลี่ยนเป็นActive
- Production/governance: targetServerไม่ได้เชื่อม, clock/unitsยังต้องยืนยัน, sourceinventorylatencyยังเปิด, Active/MX080hashunchanged. Importสำเร็จไม่ใช่productionacceptance

คำสั่งตรวจซ้ำแบบread-only:

```powershell
python -m notebooks.support.verify_downloads_history_import
python -m pytest apps/api/tests notebooks/support/test_import_downloads_history.py -q
```

## ข้อจำกัด

Raw ingestionไม่ใช่DataGate/Reference review/Calibration/Shadow/Active approval. หลังนำเข้าผู้ดูแลยังเลือกเครื่อง–โมดูล ทบทวนReferenceและShadowผ่านหน้าOperationตามเดิม. Latestจริงของทั้งสองเครื่องเป็น1Octpartialday; latestcompletecutoff1Oct00:00 local. Referenceที่มีcoverageยังไม่ใช่healthy label; manual/regime shiftsและหน่วย/codebookต้องreview. ยังไม่ยืนยันsource clockหรือProductionServer. ไม่ดำเนินReferencePreview/Build/Approveเพิ่มในการimportQAครั้งนี้; owner's existingjobsไม่ถูกลบ

Change log:2026-10-02 — Completed owner-authorized017/024historical wide/raw import:186files/15,574,385newrows;204all-column samples/120exact1mwindows, twozero-rowretries,158tests/API/UI and unchangedMX080/Profile/Active hashes. Dailyavailabilityquery preservescoverage but120s latency remains open. No Server/Profile activation/push
