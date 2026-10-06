import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { approvalReason } from "../calibration-review";

export type EvidenceInterval = { id:string; kind:string; phase:string; start:string; end:string; minutes:number;
  feature:string; peak_score:number|null; peak_value:number|null; baseline_median:number|null; peak_time:string };
export type DiagnosticEvidence = { version:string; threshold:number|null; intervals:EvidenceInterval[]; total_intervals:number;
  scoring_policy?:{threshold_version:string;comparison:string;control_votes:boolean;primary_features:string[]};
  control?:{votes:boolean;physical_flagged_minutes:number;control_changed_physical_below_minutes:number;reference_valve_median:number;reference_valve_range:number[]|null};
  recovery?:{supported:boolean;reference_events:number;reference_event_days:number;reference_recovery_p95_minutes:number|null;
    events:{start:string;end:string;returned:boolean;recovery_minutes:number|null;observed_minutes:number;assessment:string}[]};
  quality?:{observed_minutes:number;qualified_minutes:number;gate_counts:Record<string,number>};
  intervals_limited:boolean; drift:{rz:number|null;limit:number;feature?:string;early_median?:number;late_median?:number};
  checks:{key:string;state:string;value?:number|null;limit?:number;unit?:string;reasons?:string[]}[] };
export type RawEvidence = { chart:Record<string,unknown>[]; grain:string; source_timezone:string; pressure_unit:string;
  observed_rows:number; unique_seconds:number; expected_seconds:number; duplicate_rows:number; sv_counts:Record<string,number>;read_at:string };
const names:Record<string,string>={hp1:"Hp 1st",lp1:"Lp 1st",hp2:"Hp 2nd",lp2:"Lp 2nd",dp1:"ΔP CP1",dp2:"ΔP CP2",valve:"Valve",temphi:"TempHigh",templo:"TempLow"};
const gateNames:Record<string,string>={NO_SOURCE_ROWS:"ไม่มีแถวข้อมูล",DUPLICATE_MACHINE_SECOND:"มีแถวซ้ำในวินาทีเดียวกัน",LOW_SAMPLE_COVERAGE:"จำนวนวินาทีจริงไม่พอ",SOURCE_GAP:"มีช่องว่างระหว่างตัวอย่างเกินเกณฑ์",COMPRESSOR_NOT_STABLE_RUN:"สถานะ Compressor ไม่คงที่ใน Run",MODULE_NOT_STABLE_ON:"สถานะโมดูลไม่คงที่ใน On",MANUAL_OR_UNKNOWN_BUSY:"มี Manual/Busy หรือค่าไม่ทราบ",BYPASS_OR_UNKNOWN_SV:"มี SV On หรือค่า SV ไม่ทราบ",NEGATIVE_VALVE_COMMAND:"ค่า Valve เป็นลบ"};
const local=(value:string)=>value.replace("T"," ").slice(0,16);
const coordinate=(value:string)=>Date.parse(value+"Z");
const amount=(value:number|null|undefined)=>typeof value==="number"?value.toFixed(2):"ยังประเมินไม่ได้";
const rawError=(code:string)=>({RAW_READER_BUSY_RETRY:"มีคำขออ่านข้อมูลพร้อมกัน กรุณาลองอีกครั้ง",RAW_TOO_MANY_ROWS_REDUCE_PERIOD:"ข้อมูลในช่วงนี้มากเกินไป กรุณาเลือกช่วงให้สั้นลง",POLICY_CHANGED_REVIEW_AGAIN:"การตั้งค่าต้นทางเปลี่ยนแล้ว กรุณาเตรียมรอบใหม่",DETAIL_DAY_OUTSIDE_REFERENCE:"เลือกช่วงภายใน Reference ถึงวันสิ้นสุดช่วงทดสอบ",RAW_PERIOD_MAX_30_MINUTES:"เลือกช่วงไม่เกิน 30 นาที"}[code]??"อ่านข้อมูลช่วงนี้ไม่สำเร็จ กรุณาลองอีกครั้ง");
export const humanStatus=(status:string)=>status==="REVIEW_REQUIRED"?"ต้องทบทวนหลักฐาน":status==="SHADOW_VALIDATION"?"รอยืนยันข้อมูลพื้นฐาน":status==="READY_FOR_APPROVAL"?"พร้อมให้ผู้ดูแลอนุมัติ":status==="INSUFFICIENT_DATA"?"ข้อมูลยังไม่พอ":status==="REJECTED"?"ไม่รับ Profile นี้":status==="ACTIVE_FROZEN"?"ใช้งานอยู่":status;

export function SourceContract() {
  const query=useQuery({queryKey:["calibration-source-contract"],queryFn:api.calibrationSourceContract,staleTime:60_000,refetchOnWindowFocus:false});
  return <details className="ref-daily source-contract" id="calibration-source-contract"><summary>ข้อมูลพื้นฐานร่วมทุกโมดูล · {query.data?.items.filter(x=>!x.verified).length??"—"} ข้อรอยืนยัน</summary>
    {query.error&&<p className="ref-error">อ่านข้อมูลพื้นฐานไม่ได้: {query.error.message}</p>}
    <p>ตั้งค่าที่แหล่งข้อมูลครั้งเดียว ใช้ร่วมกันทุกโมดูล ไม่ต้องเปลี่ยนช่วง Reference เพื่อแก้รายการนี้</p>
    <ul>{query.data?.items.map(x=><li key={x.key}><strong>{x.verified?"✓":"รอยืนยัน"} · {x.title}</strong><span>{x.value||"ยังไม่บันทึกข้อมูลที่ยืนยันแล้ว"}</span></li>)}</ul>
    <p className="ref-help">psi คือหน่วยที่เจ้าของยืนยันแล้ว ส่วน psig/psia ระบุว่าเทียบกับบรรยากาศหรือศูนย์สัมบูรณ์ ต้องยืนยันแยกก่อนอนุมัติ Active</p>
  </details>;
}

export function ScoreChart({points}:{points:Record<string,unknown>[]}) {
  const data:Array<Record<string,unknown>&{tick:number;score:unknown}>=points.map(p=>({...p,tick:coordinate(String(p.time)),score:p.score??p.score_max??null}));
  const threshold=Number(data.find(x=>typeof x.threshold==="number")?.threshold);
  if (!data.some(x=>typeof x.score==="number")) return null;
  return <figure className="ref-chart"><figcaption><strong>ผลเทียบ baseline ในช่วงทดสอบ</strong><span>เกินเส้น = ค่านาทีนั้นนอก baseline · ไม่ใช่การยืนยันว่าเครื่องเสีย</span></figcaption>
    <ResponsiveContainer width="100%" height={190}><ComposedChart data={data} syncId="reference-review" margin={{left:0,right:12,top:10,bottom:0}}>
      <CartesianGrid vertical={false}/><XAxis dataKey="tick" type="number" domain={["dataMin","dataMax"]} minTickGap={45} tickFormatter={v=>new Date(Number(v)).toISOString().slice(5,16).replace("T"," ")} tick={{fontSize:11}}/>
      <YAxis width={48}/><Tooltip labelFormatter={v=>local(new Date(Number(v)).toISOString())} formatter={v=>typeof v==="number"?v.toFixed(2):String(v)}/>
      {Number.isFinite(threshold)&&<ReferenceLine y={threshold} stroke="#b93838" strokeDasharray="5 4"/>}
      <Line name="ค่าที่ระบบใช้ตัดสิน" dataKey="score" stroke="#385d80" dot={false} connectNulls={false} isAnimationActive={false}/>
    </ComposedChart></ResponsiveContainer>
  </figure>;
}

export function CalibrationEvidence({evidence,baseline,summary,reasons,jobId,reviewer,onLocate,disabled=false,period}: {
  baseline?:Record<string,{median:number;scale:number}>;
  evidence?:DiagnosticEvidence; summary:{quarantine_pct:number;shadow_flag_pct:number|null;max_half_shift_rz?:number|null};reasons:string[];
  jobId:string;reviewer:string;onLocate:(interval:EvidenceInterval)=>void;disabled?:boolean;period:{start:string;end:string};
}) {
  const [selected,setSelected]=useState<EvidenceInterval|null>(null);
  const [rawRange,setRawRange]=useState<{start:string;end:string}|null>(null);
  const [rawFeature,setRawFeature]=useState("hp2");
  const [kind,setKind]=useState("all");
  const [intervalLimit,setIntervalLimit]=useState(8);
  const [customStart,setCustomStart]=useState(period.start.slice(0,16));
  const [customEnd,setCustomEnd]=useState(new Date(coordinate(period.start)+5*60_000).toISOString().slice(0,16));
  const [rangeError,setRangeError]=useState("");
  const raw=useQuery({queryKey:["reference-raw",jobId,reviewer,rawRange?.start,rawRange?.end],
    queryFn:()=>api.referenceRaw(jobId,reviewer,rawRange!.start,rawRange!.end),enabled:Boolean(rawRange),staleTime:60_000,refetchOnWindowFocus:false,retry:1});
  const contracts=reasons.filter(x=>x.endsWith("_UNVERIFIED"));
  const refProblem=reasons.some(x=>["REFERENCE_SELECTION_NEEDS_REVIEW","QUARANTINE_RATE_EXCEEDED","CALIBRATION_DRIFT_EXCEEDED","ALL_WINDOWS_QUARANTINED","NONPOSITIVE_THRESHOLD"].includes(x));
  const shadowProblem=reasons.includes("SHADOW_FLAG_RATE_EXCEEDED");
  const refWaiting=reasons.some(r=>r.startsWith("INSUFFICIENT")&&!r.includes("SHADOW"));
  const shadowWaiting=summary.shadow_flag_pct===null||reasons.some(r=>r.includes("SHADOW")&&r!=="SHADOW_FLAG_RATE_EXCEEDED");
  const refLimit=evidence?.checks.find(x=>x.key==="reference")?.limit??5;
  const shadowLimit=evidence?.checks.find(x=>x.key==="shadow")?.limit??1;
  const intervals=evidence?.intervals.filter(x=>kind==="all"||x.kind===kind)??[];
  const locate=(item:EvidenceInterval)=>{setSelected(item);setRawRange(null);setRawFeature(item.feature);onLocate(item);
    requestAnimationFrame(()=>document.getElementById("reference-evidence-selected")?.scrollIntoView({behavior:"smooth",block:"start"}));};
  const openCustom=()=>{
    const start=coordinate(customStart),end=coordinate(customEnd);
    if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start||end-start>30*60_000){setRangeError("เลือกเวลาเริ่มและสิ้นสุดให้ครบ ช่วงต้องไม่เกิน 30 นาที");return;}
    if(start<coordinate(period.start)||end>coordinate(period.end)){setRangeError("เลือกช่วงภายใน Reference ถึงวันสิ้นสุดช่วงทดสอบของงานนี้");return;}
    setRangeError("");
    const first=new Date(start).toISOString().slice(0,19),last=new Date(end).toISOString().slice(0,19);
    setSelected({id:"raw-custom",kind:"raw",phase:"raw",start:first,end:last,peak_time:first,feature:rawFeature,minutes:(end-start)/60_000,peak_score:null,peak_value:null,baseline_median:null});
    setRawRange({start:first,end:last});
  };
  const openRaw=()=>{
    if(!selected)return;
    // Zoom to the exact peak and its surrounding minutes. Never request an
    // entire multi-hour episode as raw seconds.
    const peak=coordinate(selected.peak_time||selected.start);
    const selectionStart=coordinate(selected.start);
    const start=Math.max(selectionStart,peak-2*60_000);
    const end=Math.min(coordinate(selected.end),start+10*60_000);
    setRawRange({start:new Date(start).toISOString().slice(0,19),end:new Date(Math.max(end,start+60_000)).toISOString().slice(0,19)});
  };
  return <section className="calibration-evidence" aria-label="เหตุผลและช่วงที่ต้องตรวจ">
    <h3>ผลตรวจและสิ่งที่ต้องทำ</h3>
    {evidence?.scoring_policy&&!evidence.scoring_policy.control_votes&&<div className="evidence-policy"><strong>คะแนนหลัก: แรงดันและอุณหภูมิ · Valve เป็นบริบทการควบคุม</strong><p>เกินเกณฑ์เมื่อคะแนน &gt; เส้นเกณฑ์ · ค่าเท่าขอบไม่ถูกนับว่าเกิน · รอบเดิมยังใช้กติกาเดิมที่บันทึกไว้</p></div>}
    {evidence?.control?.votes===false&&<details className="ref-daily"><summary>Valve ต่างจากค่ากลาง แต่ค่าทางกายภาพไม่เกินเกณฑ์ · {evidence.control.control_changed_physical_below_minutes.toLocaleString()} นาที</summary><p>ค่ากลาง Valve ใน Reference {evidence.control.reference_valve_median} count · ช่วงที่พบ {evidence.control.reference_valve_range?.join("–")??"—"} count</p><p>ระบบแสดงคำสั่ง Valve ให้ตรวจร่วมกับแรงดันและอุณหภูมิ การเปลี่ยนคำสั่งเพียงตัวเดียวไม่สร้างคะแนนเตือนหลัก และยังไม่ยืนยันว่าเครื่องปกติ</p></details>}
    <div className="evidence-checks">
      <article className={refProblem?"needs-review":refWaiting?"check-waiting":"check-pass"}><strong>{refWaiting?"ข้อมูลยังไม่พอ":refProblem?"ต้องตรวจ":"ผล Reference"} · ข้อมูลสำหรับสร้าง baseline</strong><p>{refWaiting?"ดูจำนวนวันและนาทีที่ผ่านเงื่อนไขด้านบน":`คัดออก ${amount(summary.quarantine_pct)}% / เกณฑ์ไม่เกิน ${refLimit}%`}</p>
        <p>{refProblem?"ตรวจช่วงที่ถูกคัดออกหรือเปลี่ยนระดับ ก่อนตัดสินใจปรับ Reference":"ตรวจความเหมาะสมของช่วงด้วย การผ่านสถิติยังไม่ยืนยันว่าเครื่องปกติ"}</p></article>
      <article className={shadowProblem?"needs-review":shadowWaiting?"check-waiting":"check-pass"}><strong>{shadowWaiting?"รอข้อมูลครบ":shadowProblem?"ต้องตรวจ":"ผลช่วงทดสอบ"} · ข้อมูลหลัง Reference</strong><p>นอก baseline {amount(summary.shadow_flag_pct)}{summary.shadow_flag_pct!==null?"%":""} / เกณฑ์ไม่เกิน {shadowLimit}%</p>
        <p>{shadowProblem?"กดดูช่วงที่ต่างจาก baseline อาจเป็นสภาวะเปลี่ยนหรือพฤติกรรมเครื่อง ต้องตรวจเพิ่ม":"ข้อมูลช่วงนี้ไม่ได้ใช้เลือกหรือสร้าง baseline"}</p></article>
      <article className={contracts.length?"check-waiting":"check-pass"}><strong>{contracts.length?"รอยืนยัน":"ผ่าน"} · ข้อมูลพื้นฐาน</strong><p>{contracts.length?`${contracts.length} ข้อรอยืนยันที่แหล่งข้อมูล` :"ข้อมูลพื้นฐานครบตามการตั้งค่า"}</p><p>การเปลี่ยนช่วง Reference ไม่แก้รายการนี้</p></article>
    </div>
    {reasons.length>0&&<ul className="evidence-reasons">{reasons.map(r=><li key={r}>{approvalReason(r)}</li>)}</ul>}
    {evidence?.quality&&<details className="ref-daily"><summary>ทำไมบางข้อมูลไม่เข้า baseline · ผ่านเงื่อนไข {evidence.quality.qualified_minutes.toLocaleString()} / มีข้อมูล {evidence.quality.observed_minutes.toLocaleString()} นาที</summary><ul className="evidence-reasons">{Object.entries(evidence.quality.gate_counts).sort((a,b)=>b[1]-a[1]).map(([code,count])=><li key={code}>{gateNames[code]??(code.startsWith("MISSING_OR_NONFINITE_")?`sensor ${code.replace("MISSING_OR_NONFINITE_","")} ไม่มีค่าที่ใช้ได้`:code)} · {count.toLocaleString()} นาที</li>)}</ul><p className="ref-help">ข้อมูลเหล่านี้ยังอยู่ใน Raw view การไม่ใช้ Fit ไม่ใช่การลบข้อมูลหรือการยืนยันว่าเครื่องเสีย</p></details>}
    {evidence?.drift.rz!==null&&evidence?.drift.feature&&<p>การเปลี่ยนระดับเด่น: <strong>{names[evidence.drift.feature]}</strong> · ครึ่งแรก {amount(evidence.drift.early_median)} → ครึ่งหลัง {amount(evidence.drift.late_median)} · ค่าการเปลี่ยน {amount(evidence.drift.rz)} / เกณฑ์ {evidence.drift.limit}</p>}
    {evidence?.recovery&&<details className="ref-daily"><summary>ตรวจช่วงฟื้นตัวหลังขอบสถานะ SV · {evidence.recovery.events.length} รอบใน Shadow</summary><p>Reference มี {evidence.recovery.reference_events} รอบที่กลับต่ำกว่าเกณฑ์ต่อเนื่อง 3 นาที จาก {evidence.recovery.reference_event_days} วัน{evidence.recovery.supported?` · ระยะฟื้นตัว P95 ${amount(evidence.recovery.reference_recovery_p95_minutes)} นาที`:" · ตัวอย่างยังไม่พอเทียบรูปแบบ"}</p><p className="ref-help">ขอบนี้อาจเป็น SV On หรือค่า SV ไม่ทราบ ต้องดู Raw ยืนยัน ระบบยังนับการเบี่ยงเบนครบ และไม่ใช้รูปแบบนี้รับรอง balancing ปกติ</p><div className="evidence-intervals">{evidence.recovery.events.map(item=><button disabled={disabled} key={item.start} onClick={()=>{const first=Math.max(coordinate(period.start),coordinate(item.start)-5*60_000);setCustomStart(new Date(first).toISOString().slice(0,16));setCustomEnd(new Date(Math.min(coordinate(period.end),first+30*60_000)).toISOString().slice(0,16));setRawFeature("templo");setSelected({id:`recovery-${item.start}`,kind:"raw",phase:"raw",start:new Date(first).toISOString().slice(0,19),end:new Date(Math.min(coordinate(period.end),first+30*60_000)).toISOString().slice(0,19),minutes:30,peak_time:item.start,feature:"templo",peak_score:null,peak_value:null,baseline_median:null});setRawRange({start:new Date(first).toISOString().slice(0,19),end:new Date(Math.min(coordinate(period.end),first+30*60_000)).toISOString().slice(0,19)});requestAnimationFrame(()=>document.getElementById("reference-evidence-selected")?.scrollIntoView({behavior:"smooth",block:"start"}));}}><strong>{local(item.start)} · {item.returned?`กลับต่ำกว่าเกณฑ์ใน ${item.recovery_minutes} นาที`:"ยังไม่พบการกลับในข้อมูลต่อเนื่อง"}</strong><span>{({recovery_similar_to_reference:"รูปแบบฟื้นตัวใกล้ตัวอย่าง Reference",recovery_differs_from_reference:"รูปแบบหรือระยะฟื้นตัวต่างจาก Reference",reference_examples_insufficient:"Reference ยังไม่มีตัวอย่างฟื้นตัวพอ",not_returned_in_observed_run:"ช่วงข้อมูลจบก่อนยืนยันการฟื้นตัว"} as Record<string,string>)[item.assessment]}</span><span>ดู Raw ก่อน–หลังขอบสถานะ →</span></button>)}</div></details>}
    <div className="evidence-list-heading"><h4>ช่วงข้อมูลที่ควรตรวจ</h4><label>เลือกประเภท<select value={kind} onChange={e=>{setKind(e.target.value);setIntervalLimit(8);}}><option value="all">ทุกประเภท</option><option value="shadow_deviation">แรงดัน/อุณหภูมินอก baseline</option><option value="control_context">คำสั่ง Valve ต่างจากค่ากลาง</option><option value="reference_outlier">คัดออกจาก Reference</option></select></label></div>
    {!evidence?<p className="ref-help">รอบเดิมยังไม่มีตำแหน่งหลักฐาน กดเตรียมรอบใหม่เพื่อเพิ่มรายการช่วง โดย Active เดิมไม่เปลี่ยน</p>:intervals.length===0?<p className="ref-help">ไม่พบช่วงในประเภทนี้ ตรวจข้อที่รอยืนยันหรือความครอบคลุมด้านล่าง</p>:<div className="evidence-intervals">{intervals.slice(0,intervalLimit).map(item=><button disabled={disabled} key={item.id} className={selected?.id===item.id?"selected":""} onClick={()=>locate(item)}><strong>{names[item.feature]??item.feature} · {item.kind==="shadow_deviation"?"นอก baseline":item.kind==="control_context"?"บริบทการควบคุม Valve":"คัดออกจาก Reference"}</strong><span>{local(item.start)} → {local(item.end)} · {item.minutes} นาที</span><span>กดดูวันและตัวแปรนี้ →</span></button>)}</div>}
    {intervals.length>8&&<button type="button" onClick={()=>setIntervalLimit(intervalLimit>=intervals.length?8:intervals.length)}>{intervalLimit>=intervals.length?"ย่อรายการช่วงข้อมูล":`ดูช่วงเพิ่มเติม · ${intervals.length-intervalLimit} ช่วง`}</button>}
    {evidence?.intervals_limited&&<p className="ref-help">แสดง 200 จาก {evidence.total_intervals} ช่วง เรียงตามค่าการเปลี่ยนเด่นและระยะเวลา กราฟรายวันยังแสดงข้อมูลครบ</p>}
    <details className="ref-daily"><summary>เลือกช่วง Raw data เอง · รวม SV On และข้อมูลที่ไม่ผ่าน Gate</summary><div className="ref-fields"><label>เริ่ม Raw data<input type="datetime-local" value={customStart} onChange={e=>setCustomStart(e.target.value)} step={60}/></label><label>สิ้นสุด Raw data<input type="datetime-local" value={customEnd} onChange={e=>setCustomEnd(e.target.value)} step={60}/></label></div><p className="ref-help">เวลาข้อมูลต้นทาง · ไม่เกิน 30 นาทีต่อครั้ง</p><button onClick={openCustom} disabled={disabled||raw.isFetching}>ดู Raw data ช่วงที่เลือก</button>{rangeError&&<p className="ref-error">{rangeError}</p>}</details>
    {selected&&<div className="raw-review" id="reference-evidence-selected"><strong>ช่วงที่เลือก · {names[selected.feature]} · {local(selected.start)}</strong>{selected.kind!=="raw"&&<p>จุดเด่น {local(selected.peak_time)} · ค่า {amount(selected.peak_value)} · median baseline {amount(selected.baseline_median)} · เป็นหลักฐานการเปลี่ยนค่า ไม่ใช่สาเหตุที่ยืนยันแล้ว</p>}
      {selected.kind!=="raw"&&<button onClick={openRaw} disabled={disabled||raw.isFetching}>เปิด Raw data รอบจุดเด่น · ไม่เกิน 10 นาที</button>}
      {rawRange&&<p className="ref-help">{local(rawRange.start)} → {local(rawRange.end)} · โหลดวินาทีจริงเฉพาะช่วงนี้</p>}
      {raw.isFetching&&<div className="raw-placeholder" role="status">กำลังอ่านข้อมูลจริงเฉพาะช่วง…</div>}
      {raw.error&&<p className="ref-error">{rawError(raw.error.message)} <button onClick={()=>raw.refetch()}>ลองอีกครั้ง</button></p>}
      {raw.data&&!raw.isFetching&&<><label>ตัวแปร Raw data<select value={rawFeature} onChange={e=>setRawFeature(e.target.value)}>{Object.entries(names).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
        {raw.data.observed_rows?<RawChart data={raw.data} feature={rawFeature} baseline={baseline?.[rawFeature]} threshold={evidence?.threshold} controlRange={rawFeature==="valve"?evidence?.control?.reference_valve_range:undefined}/>:<div className="raw-placeholder">ไม่พบแถวข้อมูลจริงในช่วงนี้ ลองเลือกเวลาอื่น</div>}
        <p className="ref-help">{raw.data.observed_rows.toLocaleString()} แถว / {raw.data.unique_seconds.toLocaleString()} วินาทีจริงจาก {raw.data.expected_seconds} วินาที · แถวในวินาทีซ้ำ {raw.data.duplicate_rows} · SV {Object.entries(raw.data.sv_counts).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
        <p className="ref-help">แสดงทุก state รวม SV On ไม่เติมข้อมูลที่ขาด ไม่ใช้ Raw view นี้เปลี่ยน baseline · อ่าน {new Date(raw.data.read_at).toLocaleString("th-TH",{timeZone:raw.data.source_timezone})} · cache ไม่เกิน 60 วินาที</p>
        <details className="ref-daily"><summary>ดูแถวข้อมูลจริงและ state</summary><div className="ref-table-scroll"><table><thead><tr><th>เวลา</th><th>{names[rawFeature]}</th><th>Compressor</th><th>Module</th><th>Busy</th><th>SV</th><th>วินาทีซ้ำ</th></tr></thead><tbody>{raw.data.chart.slice(0,300).map((p,i)=><tr key={i}><td>{String(p.time).replace("T"," ")}</td><td>{amount(p[rawFeature] as number|null)}</td><td>{String(p.global_state)}</td><td>{String(p.module_state)}</td><td>{String(p.busy)}</td><td>{String(p.sv)}</td><td>{p.duplicate_second?"ซ้ำ":"—"}</td></tr>)}</tbody></table></div><p>ตารางแสดง 300 แถวแรก กราฟใช้ทุกแถวที่อ่าน</p></details>
      </>}
    </div>}
  </section>;
}

function RawChart({data,feature,baseline,threshold,controlRange}:{data:RawEvidence;feature:string;baseline?:{median:number;scale:number};threshold?:number|null;controlRange?:number[]|null}) {
  const points=data.chart.map(p=>({...p,tick:coordinate(String(p.time)),value:p[feature],svOn:p.sv==="On"?p[feature]:null}));
  // Segment at actual timestamp gaps. Do not draw through absent seconds.
  const plotted:typeof points=[];
  points.forEach((p,i)=>{if(i&&p.tick-points[i-1].tick>1000)plotted.push({...p,tick:points[i-1].tick+1000,value:null,svOn:null});plotted.push(p);});
  return <figure className="ref-chart"><figcaption><strong>{names[feature]} · Raw data รายวินาที</strong><span>{["temphi","templo"].includes(feature)?"°C":feature==="valve"?"count":data.pressure_unit} · ม่วง = SV On · ช่องว่าง = ไม่มีแถวข้อมูล</span></figcaption>
    {baseline&&<p className="ref-help">เส้นประ = median Reference {baseline.median.toFixed(2)} · {feature==="valve"?"แถบ = ช่วงคำสั่งที่พบใน Reference ไม่ใช่เกณฑ์เตือนหลัก":"แถบ = ขอบเกณฑ์ของค่านาทีจาก Profile นี้ ใช้ประกอบการดู Raw รายวินาที"}</p>}
    <ResponsiveContainer width="100%" height={230}><ComposedChart data={plotted} margin={{left:0,right:12,top:10,bottom:0}}><CartesianGrid vertical={false}/><XAxis dataKey="tick" type="number" domain={["dataMin","dataMax"]} minTickGap={45} tickFormatter={v=>new Date(Number(v)).toISOString().slice(11,19)} tick={{fontSize:11}}/><YAxis width={48}/><Tooltip labelFormatter={v=>new Date(Number(v)).toISOString().slice(0,19).replace("T"," ")} formatter={v=>typeof v==="number"?v.toFixed(3):String(v)}/>
      {baseline&&feature!=="valve"&&threshold&&<ReferenceArea y1={baseline.median-threshold*baseline.scale} y2={baseline.median+threshold*baseline.scale} fill="#3e9a79" fillOpacity={.09} ifOverflow="extendDomain"/>}
      {feature==="valve"&&controlRange&&<ReferenceArea y1={controlRange[0]} y2={controlRange[1]} fill="#3e9a79" fillOpacity={.09} ifOverflow="extendDomain"/>}
      {baseline&&<ReferenceLine y={baseline.median} stroke="#7a8793" strokeDasharray="4 4" ifOverflow="extendDomain"/>}
      <Line dataKey="value" name={names[feature]} stroke="#32658b" dot={false} connectNulls={false} isAnimationActive={false}/><Line dataKey="svOn" name="SV On" stroke="#8757b5" strokeWidth={2.3} dot={false} connectNulls={false} isAnimationActive={false}/>
    </ComposedChart></ResponsiveContainer></figure>;
}
