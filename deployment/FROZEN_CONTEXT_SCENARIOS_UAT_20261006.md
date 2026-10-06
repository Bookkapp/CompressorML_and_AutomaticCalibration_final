# Frozen Reference: Mock หลายกรณี

6 October 2026 · Asia/Bangkok · owner-authorized isolated software QA.

## ขอบเขต

ทดสอบ17กรณี /73,260synthetic observed minutes โดยใช้ **MX058/M1 frozen Profile `2a7990dd1d81…` จริง16กรณี** และ **MX017/M1 OFF-only frozen Profile `65a3e0210722…` จริง1กรณี** ค่าพารามิเตอร์และผลทบทวนอ่านจากฐานข้อมูลlocalด้วยSELECTเท่านั้น

ข้อมูลจำลองมี grain1นาที ช่วงเสมือน7–9Oct2026 ไม่ใช่ Raw sensor ไม่ผ่าน ingestion และไม่ใช่เวลาผ่านไปจริง ทุกผลเป็นMOCK/nonprospective/nonapproval ไม่มีsource/Profile/review/Active/Event/job writes ไม่มีปุ่มMockเพิ่ม

Seed58; normal variation0.04×local scale; HP2±60psi/LP2±10psiตามกรณี; DP1/DP2คำนวณจากHP−LPทุกจุด ไม่fit/tune Referenceจากผลทดสอบ ไม่อ้างว่าtrajectoryจำลองเป็นพฤติกรรมทางฟิสิกส์ที่รับรองแล้ว

## ผลที่ตรวจแล้ว

| กรณี | ผลรวม3วัน |
|---|---|
| Normalใน4สภาวะที่MX058รับไว้ | 17,280นาทีในReferenceทั้งหมด /0flags |
| Spike1นาที/วัน | พบ3/3นาที; flag0.0695%ต่ำกว่าเกณฑ์รวม1% |
| Oscillation10นาที/วัน | พบ30/30นาที; flag0.6944%ต่ำกว่าเกณฑ์รวม1% |
| HP2สูงแล้วนิ่ง6ชั่วโมง/วัน | 12นาทีDeviation +1,068นาทีNEW_STEADY_LEVEL; ไม่มี raised minuteกลายเป็นNormal |
| HP2/LP2สูงแล้วนิ่ง6ชั่วโมง/วัน | 12นาทีDeviation +1,068นาทีNEW_STEADY_LEVEL; numerical acceptanceไม่ผ่านเพราะunresolved |
| สูงนิ่งตลอด3วัน | 4นาทีDeviation +4,316นาทีNEW_STEADY_LEVEL; supported day0 |
| Drift2ชั่วโมงแล้วนิ่งสูง4ชั่วโมง/วัน | 315นาทีDeviation +708นาทีNEW_STEADY_LEVEL; flag8.721%ของsupportedminutes |
| Valveเปลี่ยนแต่physical valuesไม่เปลี่ยน | 4,320นาทีในReference /0flags; Valveไม่voteเป็นAnomalyเอง |
| Valveเปลี่ยนแล้วresponseล่าช้า10นาที | initial valuesยังในReference;69นาทีUNSUPPORTED_TRANSITION +288นาทีNEW_STEADY_LEVEL;ไม่ผ่านnumerical acceptance |
| IncludedSV ONแต่ไม่มีacceptedONReference | ON180นาทีไม่ถูกประเมินเป็นNormal;รวมunsupported/new-level192นาที; included-state gateยังบล็อก |
| ข้อมูลขาด60นาที/วัน | missing180นาที;ไม่เติมค่า0หรือสร้างNormalให้ช่วงขาด |
| Sensor qualityไม่ผ่าน10นาที/วัน | DATA_UNAVAILABLE30นาที;ไม่เรียกphysical anomaly |
| Manual/Busy1เป็นเวลา30นาที/วัน | UNSUPPORTED_CONTROL_CONTEXT90นาที;ไม่เรียกNormal |
| MX017excludedON60นาที/วันและกลับOFFค่ายังสูง | excluded180นาที; OFFนาทีแรกตรวจและDeviationทันทีทั้ง3วัน;12Deviation+168new-level,ไม่มีcooldown |

ทุก17behavioral expectationผ่าน และexecutedNotebookทำซ้ำได้ตรงทั้งcategory counts/validation receipts พร้อมยืนยันfrozen hashก่อน–หลัง

## วิธีอ่านผล

- `flag_pct`ใช้เฉพาะsupported/scoredminutesเป็นdenominator ช่วงNEW_STEADY_LEVEL/unsupportedTransitionเป็นunresolvedแยกต่างหาก จึงเป็นไปได้ที่Flag%ต่ำแต่ยังไม่ผ่านตรวจรับ
- ค่าสูงแล้วนิ่ง **ไม่ได้รับเป็นNormalอัตโนมัติ** การนิ่งตาม5-minute criterionเพียงเปลี่ยนคำอธิบายเป็นnewlevelที่ต้องทบทวน ไม่เปลี่ยนbaseline
- Spikeสั้นตรวจพบ แต่เกณฑ์รวม1%อาจยังให้numericalconditionsผ่าน นั่นไม่ใช่คำยืนยันว่าปลอดภัยหรือการทดสอบepisode/operationalalertครบวงจร
- Gap/quality/manualcontrolอาจมีFlag0และnumericalconditionsผ่านเพราะยังมีsupportedminutesพอ ดูdailyquality/missing/unsupportedประกอบเสมอ ไม่ถือว่าunevaluatedminutesเป็นhealthy
- ActualMX058/M1ไม่มีacceptedTransitiontemplate จึงไม่สร้างtemplateสมมติให้ผ่านกรณีdelayedresponse การทดสอบนี้ยังไม่พิสูจน์acceptedhealthyTransitionของเครื่องจริง
- `metrics_only_within_gate`ในJSONไม่ใช่Active readiness ทุกMockถูกprovenanceguardบล็อก แม้ลองเปลี่ยนprospectivebitเฉพาะสำเนาในmemoryเป็นtrue

## เสถียรภาพ/ต้นทุน

Scorerรวม17กรณี8.09วินาทีบนเครื่องพัฒนานี้ เฉพาะassess_context ไม่รวมDB/graph/render/generation ไม่ใช่ServerSLA Registry/import/source-headก่อน–หลังเหมือนเดิม: legacyProfiles207/Active46, ContextProfiles110/ContextActive0, importreceipts567

ไม่มีการเปลี่ยนruntime/scorer/threshold/sourceclock/worker/approval ไม่มีremoteServerdeployment

## หลักฐานและทำซ้ำ

- ExecutedNotebook: `notebooks/15_Frozen_Context_Scenarios_20261006.ipynb`
- Generatedinput/scoring: `notebooks/support/frozen_context_scenarios.py`
- Notebook/figure delivery: `notebooks/support/frozen_context_scenario_delivery.py`
- `notebooks/outputs/context_scenarios_20261006/summary.json`, frozenProfileexports และ17compressedtrace files
- Figures: composition, CP2plateau, delayedValve, excludedONreturn; HTMLnotebookpreview

```powershell
python -m notebooks.support.frozen_context_scenarios
python -m notebooks.support.frozen_context_scenario_delivery
```

Firstcommandอ่านsavedProfilesจริงและยืนยันregistry/sourceheadไม่เปลี่ยน Secondcommandใช้exportedfrozenProfilesทำซ้ำแบบmemory สร้างexecutedNotebookพร้อมfigures ไม่มีlive telemetryqueryจากNotebook

ตรวจnumerical/category assertionsทุกกรณีแล้ว ตรวจภาพ4figures แก้footnoteทับxlabelและฝังPNGในNotebookแทนtext-onlyfigurerepr ผลนี้ไม่แทนrealpostfreeze/manualRaw/ingestion/3-dayActiveacceptanceหรือEngineer/sourcecontractverification

## Change log

- 2026-10-06 — Owner requested Normal and outside-Baseline scenarios without restoring Mock UI. Executed17isolatedcases/frozen invariance, deterministicNotebook/parity and visual QA. Runtime/Active/source unchanged.
