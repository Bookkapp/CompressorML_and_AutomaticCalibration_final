# MX080 / M6 — ตรวจ CP2 และช่วงปรับการทำงาน, 5 ตุลาคม 2026

## ข้อสรุป

ตรวจต่อจาก M6 ที่เปิดใน Fleet Reference โดยใช้ **Hp_2nd / Lp_2nd / Hp_2nd−Lp_2nd เป็นหลัก** และอ่าน Valve, SV, Busy, Status กับ CP1/temperature เป็นบริบท ไม่เทียบแรงดันจากต่างสภาวะเป็น Normal เดียวกัน

พบการเปลี่ยนรูปแบบจริงตามวันที่เจ้าของระบุ แต่ข้อมูลแยกเป็นอย่างน้อยสามชนิด: การเข้าใกล้กันของ HP/LP ขณะ `Status_6=Off/Valve=0`, การปรับควบคุม/กลับมา On, และแรงดันสูงต่อเนื่องในสภาวะ Run/On วันที่7–8Sep. มีช่วงสงสัยการอ่านข้อมูลผิดอีกหนึ่งส่วน. **ยังไม่มีหลักฐานยืนยันการเติมน้ำยาหรือการรั่ว** และการที่ค่าอยู่ระดับใหม่แล้วนิ่งไม่ยืนยันว่าปกติ

`Status_6` คือสถานะควบคุมวาล์วตาม Data Contract ไม่ใช่ electrical/motor feedback ของ CP2. คำว่า Off ในรายงานนี้จึงไม่ยืนยันว่า compressor ของ module หยุดจริง. `Status=Run/Stop` เป็นสถานะระดับเครื่องที่บันทึกไว้ และ Busy1 เป็น manual context

## ข้อมูลและการตรวจสอบ

- MX080/M6,20Aug–12Sep2026 รวม24daily source files; นาทีที่สังเกต34,550, ผ่านเกณฑ์คุณภาพเชิงตัวเลข34,367. เวลาเดิมไม่มี timezone, ใช้สมมติฐาน Asia/Bangkok
- อ่าน raw เดิมซ้ำ10focal days:23/24/26/31Aug,1/2/7/8/10/12Sep, รวม851,177แถว. CSV SHAและrow counts ตรงกับ frozen source receipts10/10; checksum minute Parquet ตรง24/24
- คำนวณค่าเฉลี่ยแรงดันจาก raw ใหม่30minute samples ครอบคลุม10วัน; ตรง derived values ในความคลาดเคลื่อน<1e−9. ไม่ interpolate; raw plotละ duplicate seconds ที่กำกวมและคงช่องว่าง
- Source คือ canonical dynamic ZIP/receipt corpus ที่ใช้ใน Notebook11 ไม่ใช่ exact current SQL snapshot; ไม่มี source/SQL/model/Active writes
- การเทียบช่วง Run ใช้ quality+stable control+StatusRun+Status_6On+Busy0+SVOff. เกณฑ์นี้ทำให้เทียบสภาวะได้ ไม่ยืนยันสุขภาพ. All-state pressure ไม่ถูกซ่อน
- Original MessageLogs หาไม่พบที่ pathเดิมในรอบนี้; ใช้ `message_events_parsed.csv` ของการตรวจครั้งก่อนเป็น **secondary context** สำหรับ2–8Sepเท่านั้น. ไม่มี original service/charge/repair/recipe/load logs มาใช้ยืนยันสาเหตุ

## ลำดับเหตุการณ์

| ช่วง | สิ่งที่เห็นจากข้อมูล | ข้อสรุปที่รองรับ |
|---|---|---|
|23Aug ก่อน15:00|Run/On: HP≈185.9,LP≈17.9psi.14:54:13มีChangeValveเพียงช่วงสั้น;15:09:40Status_6On→Off/Valve0|เปลี่ยนการควบคุมจริง. HPเกิน230ครั้งแรก15:41:28 และสูงสุด409.8ในวันนั้นหลังเข้าOff; ยังแยก planned/service stop กับเหตุเสียไม่ได้|
|24Aug|ไม่มีModule/SV/Busy/Valve event. HPค่อยลด,LPค่อยเพิ่ม.19:00–20:00ประมาณ194.2/194.0psi;Status_6Off/Valve0|pressure equalization/redistribution ในสภาวะควบคุมOff สอดคล้องข้อมูล; ไม่ใช่หลักฐานเติมน้ำยา|
|26Aug|05:46:29เข้าสู่ChangeValve/Busy1พร้อมSVเปลี่ยน;06:05:45กลับOn/Busy0|มี manual/control intervention แล้วกลับมาคงที่.27–30Augถึง31Augก่อน15:59 HPmedian189.8,LP18.2; การเติมและรั่วเป็นสมมติฐาน|
|31Aug|15:59:47On→Off/Valve0. HP/LPลดช่วงแรก,LPอยู่0ช่วงหนึ่ง ก่อนHPขึ้นเกิน230ที่20:09:44 และสูงสุด403.7|วันที่/เวลาเปลี่ยนที่เจ้าของเห็นสอดคล้อง. การขึ้นหลังเข้าOffต้องเทียบ Off response; ยังไม่พิสูจน์ว่าสภาพ Run เดิมมี fault ก่อน15:59|
|1–2Sep|1SepHPค่อยลดLPเพิ่ม;ค่ากลับมาใกล้กันเช้ามืด2Sep,absΔP≤5ครั้งแรก01:29:35|เข้าใกล้สมดุลระหว่างOff ไม่ใช่กลับมา cooling regulation.2SepมีMValveHome/ChangeValveหลายรอบ16:36–17:29 และSVสุดท้ายกลับOff17:37:43|
|3–6Sepและ7Sepก่อน08:00|Run/On HPmedian190.5,LP18.8,ΔP171.7psi;Valve94|เป็นช่วง stable run ที่ข้อมูลรองรับและเจ้าของเสนอว่าปกติ; เหมาะเสนอ Reference review|
|7Sepเริ่มเปลี่ยน|07:00–08:00 rawHPmedian190.4,LP19.0. HPออกนอก working180–230 bandครั้งแรก08:02:47;Run→Stop08:06:22;ChangeValve08:09:14|การเริ่มเปลี่ยนที่เห็นชัดอยู่หลัง08:02ใน clockนี้. ขอบเขต07:00ที่เจ้าของระบุเก็บเป็นบริบทเหตุการณ์ได้ แต่ไม่ควรกล่าวว่าทั้ง07:00–08:00มี pressure fault จากข้อมูลนี้|
|7Sep10:55:59–11:28:01|1896observed rows มีแรงดันทั้ง4ช่องของM6=580.2และอุณหภูมิทั้ง2=-200พร้อมกัน.11:05snapshotโมดูลอื่นมีค่าต่างกัน|มีลักษณะ acquisition/sentinel/defaultผิดปกติสูงมาก, localized M6. ไม่ใช้580.2เป็นหลักฐานของแรงดันกายภาพ/เติมน้ำยา. เก็บ rawและquarantineจาก Normal; hardware sentinel definitionยังไม่ยืนยัน|
|7Sepหลัง12:30–8Sep23:50|2089supported minutes:HPmedian334.9,LP27.1,ΔP308.5;Valve94. ก่อนหน้า190.5/18.8/171.7|ระดับRunเปลี่ยนต่อเนื่อง:HP+75.74%,LP+43.82%,ΔP+79.64%. 2085/2089นาทีHP>300. สอดคล้อง owner-confirmed abnormal episodeแม้กราฟนิ่ง. ไม่ใช่เพียง spikeเดียว|
|10Sep|Status_6Off/Valve0ตลอดวัน;16–17โมงrawmedianHP201.2/LP21.6,18:30–20:30เข้าใกล้283.2/282.9. ระดับเครื่องStop20:39:15→Run21:09:58|มีpressure cycling/equalityและglobal stop/restartจริง. ข้อมูลยังไม่รองรับคำว่ากลับมาNormal RunของM6ในวัน10Sep|
|12Sep|02:40:58ChangeValve/Busy1→02:49:59On/Busy0. ตั้งแต่04:00HP178.4,LP14.8,ΔP163.6,Valve100|supported Onกลับมาในวันที่12ในชุดที่ตรวจ. ระดับและValveต่างจากก่อน7Sep ควรเป็นpost-intervention epoch/regimeให้ทบทวน ไม่รวมกับก่อนหน้าโดยอัตโนมัติ|

ตัวเลขตารางเป็นmedianตามช่วงระบุ; extremaเป็นobserved raw. Working180–230psiเป็นfield bandในเอกสารเดิม ใช้อธิบายเวลาเท่านั้น ไม่ใช่โมเดล/thresholdที่รับรอง. รอบ12Sepที่HPต่ำกว่า180แสดงเหตุผลว่าต้องตรวจบริบทใหม่ ไม่ยึดbandเดียวตัดสินทุกสภาวะ

### หลักฐานแยก M6 กับ common cause

ในช่วง3Sep–7Sepก่อน08:00เทียบ7Sep12:30–8Sep23:50, M1–M5มีHP2mediansในช่วงประมาณ183–207psi และไม่มีการขึ้นระดับใกล้335แบบM6. M6HP1กลับลด150.5→143.6ในขณะที่HP2เพิ่ม. สนับสนุนว่าปัญหาCP2/บริบทของM6เด่นเฉพาะตัว แต่ไม่ปิดความเป็นไปได้ของload,control,water/heat rejectionหรือเหตุร่วมอื่น เพราะไม่มีtelemetryเหล่านั้น

### Spikeที่ต้องแยกจาก pressure fault

Message exportเดิมมีModule6 ALM043 balancing pressure differenceเจ็ดครั้งวันที่7Sep รวมครั้งแรก08:04:19, APAX_DAQ connect fail09:02:47/09:27:09/09:46:51/09:49:17, และPressure rebooting11:58:18. การอยู่วันเดียวกันเป็นหลักฐานบริบท ไม่ใช่พิสูจน์สาเหตุของค่า580.2ตรงเวลา. ALM043เป็นpressure-difference alarm text ไม่ใช่charge/refill log. QAเชิงfinite-number/coverageเดิมผ่านค่าคงที่580.2/-200ได้ จึงต้องเพิ่มsemantic/sentinel admissionในงานFleet Stableภายหลัง; ไม่ได้เปลี่ยนruntime gatesรอบนี้

## สมมติฐานเติมน้ำยา/รั่ว

ลำดับ intervention→stable interval→เกิดปัญหาอีก **เข้ากับสมมติฐานของเจ้าของ** แต่แต่ละการฟื้นหลังadjustment/restartไม่ได้ระบุว่ามีการเติมอะไรหรือปริมาณเท่าใด. HP/LPเข้าใกล้กันเกิดเมื่อการควบคุมOffด้วย และมีวันที่ไม่มีrecorded adjustmentเลย; จึงไม่ควรสร้างlabelว่าequalizationทุกครั้งคือเติมน้ำยา

การตรวจunderchargeต้องใช้หลักฐานเพิ่มเติม เช่นcharge/service records,leak testและค่าที่รองรับsuperheat/subcooling. CurrentTempLoเป็นtagตามDataContractที่ยังไม่ให้suction/liquid-line temperatureคู่สำหรับคำนวณเหล่านั้น. [Danfoss fault diagnosis](https://www.danfoss.com/en-us/industries/food-and-beverage/dcs/cold-rooms/system-design-component-selection/application-vertical-market-sizing/troubleshooting-fault-diagnosis/) แยกundercharge,valve/controlและปัจจัยอื่น; [Danfoss TXV troubleshooting](https://assets.danfoss.com/documents/latest/90976/AC307572949567en-010101.pdf) สนับสนุนการตรวจsystem-wideและsuperheat/subcooling. เป็นข้อควรตรวจทั่วไป ไม่ใช่คู่มือเฉพาะHT9046MXหรือการยืนยันfaultจากข้อมูลนี้

## ผลต่อ Fleet Stable v1

1. เก็บ**CP2 level และrelationship evidence**เป็นหลักพร้อมcontext; DPเป็นderived evidence ไม่ใส่ซ้ำเป็นcovariance coordinateจนเมทริกซ์rank-deficient
2. แยก Off/equalization,manual transition,data acquisition issue และsupported steady run. ไม่ฝึกNormalรวมทั้งกราฟและไม่ลบช่วงที่ถูกกันจากfit
3. เสนอreview27–30Augและ3–6Sepเป็นlocal Normal referencesของM6; กัน23Augหลัง15:09–26Augช่วงกลับOn,31Augหลัง15:59–2Sepช่วงintervention และ7–11Sepจากsteady Normal admissionจนทบทวนรายcontext. ขอบเขตนี้คือ**quarantine/review proposal ไม่ใช่confirmed fault labelsทั้งหมด**
4. 12Sepเป็นepoch/regimeใหม่ที่ต้องตรวจrecipe/config/serviceและhealthy behaviorแยก. ไม่เลื่อนค่าnormalเดิมไป335เพราะplateauนิ่งหรือเพราะมีSV/Valveevent
5. Known7–8Sepcaseใช้regression test;ช่วง580.2/-200ใช้data-qualitycaseต่างหาก. แยกShadow flagsบนconfirmed abnormal dataจากfalse-alert assessmentบนreviewed Normal. วันเหล่านี้ถูกเปิดดูแล้ว ไม่ใช่untouched prospective test

ไม่มีการเทรนFleetรุ่นใหม่หรือเปิดworker/Server/Activeในงานวิเคราะห์นี้. ชุดFleetปัจจุบันฝึก2Jul–14Augและตั้งเกณฑ์15–21Aug จึงไม่ได้รับช่วงที่ตรวจตั้งแต่23Augเข้าNormalfitอยู่แล้ว

## ภาพและการทำซ้ำ

![CP2 history](C:/Users/Book/OneDrive/Documents/ChatGPT/OPERATION_P/notebooks/outputs/mx080_m6_episode_review_20261005/cp2_episode_history.png)

![7Sep original seconds](C:/Users/Book/OneDrive/Documents/ChatGPT/OPERATION_P/notebooks/outputs/mx080_m6_episode_review_20261005/sep7_raw_control_detail.png)

![10Sep original seconds](C:/Users/Book/OneDrive/Documents/ChatGPT/OPERATION_P/notebooks/outputs/mx080_m6_episode_review_20261005/sep10_raw_control_detail.png)

Executed Notebook12: `notebooks/12_MX080_M6_Control_and_CP2_Episode_Review_20261005.ipynb`. Reproduce fromrepo root: `python -m notebooks.support.mx080_m6_episode_review`, `python -m notebooks.support.mx080_m6_episode_review --raw`, `python -m notebooks.support.mx080_m6_episode_review --deliver`. Privateoriginal ZIPs/frozenstudy partitionsrequired. QAreceiptsและexactperiod/control/source tablesอยู่ใน`notebooks/outputs/mx080_m6_episode_review_20261005/`
