import {useEffect,useMemo,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "../api";
import {ContextChart,type ChartRow} from "./ContextChart";
import {FleetStablePanel} from "./FleetStablePanel";

const duration=(value:number|null)=>value===null?"ยังวัดไม่ได้":`${value.toFixed(0)} นาที`;
const splitName=(value:string)=>({reference:"Reference",calibration:"กำหนดเกณฑ์",diagnostic:"ตรวจย้อนหลัง",outside_evaluation:"นอกช่วงประเมิน"}[value]??value);
const eventName=(value:string)=>{
  if(value==="OFF_TO_ON")return "SV OFF → ON";
  if(value==="ON_TO_OFF")return "SV ON → OFF";
  const match=value.match(/^(?:(SV_ON|SV_OFF)_)?VALVE_(UP|DOWN)_STEP_(3_9|10_29|30_PLUS)$/);
  if(match)return `${match[1]?.replace("_"," ")??"สภาวะไม่รองรับ"} · Valve ${match[2]==="UP"?"เพิ่ม":"ลด"} ${match[3]==="30_PLUS"?"ตั้งแต่ 30":match[3].replace("_","–")} หน่วย`;
  return value.replaceAll("_"," ");
};
const friendly=(error:unknown)=>{
  const message=error instanceof Error?error.message:"";
  if(message.includes("not prepared"))return "กำลังเตรียมข้อมูล Fleet สำหรับทบทวน";
  if(message.includes("outside"))return "เครื่องนี้ยังไม่ได้รวมอยู่ในรอบศึกษา Fleet";
  if(message.includes("committed day"))return "วันที่เลือกไม่มีข้อมูลที่นำเข้าแล้ว กรุณาเลือกวันอื่น";
  return message||"ยังอ่านหลักฐานไม่ได้ ลองเปิดอีกครั้ง";
};

export function FleetReferencePanel({machine,module,onModule}:{machine:string;module:number;onModule:(value:number)=>void}){
  const [opened,setOpened]=useState(false),[sourceMachine,setSourceMachine]=useState(machine);
  const [showResearch,setShowResearch]=useState(false);
  const [day,setDay]=useState("2026-09-15"),[showChart,setShowChart]=useState(false),[fitDays,setFitDays]=useState(14);
  useEffect(()=>{setSourceMachine(machine);setShowChart(false);},[machine]);
  const reference=useQuery({queryKey:["fleet-reference",machine,module],queryFn:()=>api.fleetReference(machine,module),
    enabled:opened&&showResearch,staleTime:300_000,retry:false,refetchOnWindowFocus:false,placeholderData:previous=>previous});
  const chart=useQuery({queryKey:["fleet-reference-day",sourceMachine,module,day],
    queryFn:()=>api.fleetReferenceDay(sourceMachine,module,day),enabled:opened&&showResearch&&showChart&&!!reference.data,
    staleTime:300_000,retry:false,refetchOnWindowFocus:false});
  const rows=useMemo<ChartRow[]>(()=>chart.data?.chart.map(point=>({time:point.time,...point.features}))??[],[chart.data]);
  const data=reference.data,coverage=reference.isPlaceholderData?undefined:data?.coverage.find(value=>value.module===module);
  const variants=reference.isPlaceholderData?[]:data?.variants.filter(value=>value.fit_days_requested===fitDays)??[];
  const validDay=/^\d{4}-\d{2}-\d{2}$/.test(day)&&day>="2026-07-01"&&day<="2026-10-01";
  return <details className="fleet-reference-panel" open={opened} onToggle={event=>setOpened(event.currentTarget.open)}>
    <summary><strong>Fleet Reference · เปรียบเทียบกับเครื่องอื่น</strong><span>041 · 058 · 080 · 081 และข้อมูล 017/024</span></summary>
    {opened&&<div className="fleet-reference-body">
      <FleetStablePanel machine={machine} module={module} onModule={onModule}/>
      <details onToggle={e=>setShowResearch(e.currentTarget.open)}><summary>ผลทดลองเปรียบเทียบช่วง Local และการตอบสนอง SV / Valve</summary>
      {showResearch&&<>
      <p className="context-help">ใช้ข้อมูลย้อนหลังเสนอเครื่องและพฤติกรรมที่เทียบกันได้ ต้องทบทวน Reference ก่อนนำไปใช้ใน Active Profile</p>
      <div className="fleet-evidence-controls"><label>Module ของ {machine}<select aria-label="Fleet Reference module" value={module} onChange={event=>onModule(Number(event.target.value))}>{Array.from({length:8},(_,i)=><option value={i+1} key={i+1}>M{i+1}</option>)}</select></label><label>ช่วงข้อมูล Local สำหรับ Fit<select aria-label="Fleet Local fit days" value={fitDays} onChange={event=>setFitDays(Number(event.target.value))}>{[1,3,7,14].map(value=><option key={value} value={value}>{value} วัน</option>)}</select></label></div>
      {reference.isPending&&<p className="context-help">กำลังอ่านผลที่เตรียมไว้</p>}
      {reference.error&&<p role="status" className="context-help">{friendly(reference.error)}</p>}
      {data&&<>
        <div className="context-badges"><span>ข้อมูล {coverage?.source_days??"—"} วัน · M{module}</span><span>ข้อมูลผ่านคุณภาพ {coverage?.quality_minutes.toLocaleString()??"—"} นาที</span><span>SV ON {coverage?.sv_on_minutes.toLocaleString()??"—"} นาที</span><span>SV OFF {coverage?.sv_off_minutes.toLocaleString()??"—"} นาที</span></div>
        <div className="context-table-wrap"><table className="context-table"><thead><tr><th>สภาวะ</th><th>ข้อมูลสำหรับ Fit</th><th>เครื่องที่เข้ากันในรอบทดลอง</th><th>ส่วนช่วยจาก Fleet</th></tr></thead><tbody>
          {reference.isPlaceholderData?['SV OFF','SV ON'].map(context=><tr key={context}><td>{context}</td><td colSpan={3}>กำลังอ่านผลของ M{module}</td></tr>):variants.map(value=><tr key={value.context}><td>{value.context.replace("_"," ")}</td><td>{value.fit_points===undefined?"ข้อมูลไม่พอ":`${value.fit_points.toLocaleString()} จุด · ${value.fit_days_observed} วัน`}</td><td>{value.relationship_donor_machines?.length?value.relationship_donor_machines.map(m=>`MX${m}`).join(" · "):"ยังไม่มีกลุ่มที่รองรับ"}</td><td>{value.status!=="RESEARCH_PROPOSAL"?"ต้องเพิ่มหลักฐาน":value.relationship_fleet_weight?`${(value.relationship_fleet_weight*100).toFixed(1)}% · รอทบทวน`:"ใช้ Local ก่อน"}</td></tr>)}
        </tbody></table></div>
        <p className="context-help">Fleet ช่วยเฉพาะรูปแบบความสัมพันธ์ ระดับ Baseline และสเกลรายช่องยังคงเป็น Local ผลด้านบนใช้ Fit ย้อนหลังไม่เกิน {fitDays} วัน และข้อมูลแยกอีก 7 วันสำหรับกำหนดเกณฑ์ ไม่ใช่ผลทดลองที่มีข้อมูลเครื่องใหม่เพียงวันเดียว กลุ่ม M เดียวกันยังต้องยืนยัน configuration และหน้าที่ Module</p>
        {!!data.transitions.length&&<details className="fleet-transition-details"><summary>เวลาตอบสนองหลัง SV / Valve เปลี่ยน · ดูรายละเอียด</summary>{reference.isPlaceholderData?<p>กำลังอ่านเหตุการณ์ของ M{module}</p>:<div className="context-table-wrap"><table className="context-table"><thead><tr><th>เหตุการณ์</th><th>ช่วงข้อมูล</th><th>จำนวนรอบ</th><th>รอบที่สังเกตว่านิ่ง</th><th>เวลานิ่งค่ากลาง / P90</th></tr></thead><tbody>{data.transitions.map(value=><tr key={value.direction+value.split}><td>{eventName(value.direction)}</td><td>{splitName(value.split)}</td><td>{value.events}</td><td>{value.settled_observations} / {value.events}</td><td>{duration(value.settling_p50_minutes)} / {duration(value.settling_p90_minutes)}</td></tr>)}</tbody></table></div>}<p className="context-help">เวลานิ่งเป็นสิ่งที่สังเกตได้ ยังไม่ได้ยืนยันว่าเป็นการทำงานปกติ และไม่ใช่ระยะเวลาตัดข้อมูลทิ้ง รอบที่ข้อมูลขาดหรือยังไม่นิ่งถูกเก็บไว้ด้วย ตัวอย่าง Valve ใช้ step ตั้งแต่ 3 หน่วยและเว้นอย่างน้อย 2 ชั่วโมงเพื่อลดรอบซ้อน การตอบสนองอาจมี control อื่นร่วมด้วย</p></details>}
        <h3>ดูข้อมูลจริงของเครื่องใน Fleet</h3>
        <div className="fleet-evidence-controls"><label>เครื่อง<select aria-label="Fleet evidence machine" value={sourceMachine.replace(/^.*MX-?/i,"")} onChange={event=>{setSourceMachine(event.target.value);setShowChart(false);}}>{data.source_machine_order.map(value=><option key={value} value={value}>MX{value}</option>)}</select></label><label>วันที่<input aria-label="Fleet evidence date" type="date" value={day} min="2026-07-01" max="2026-10-01" onInput={event=>{setDay(event.currentTarget.value);setShowChart(false);}} onChange={event=>{setDay(event.target.value);setShowChart(false);}}/></label><button disabled={!validDay} onClick={()=>setShowChart(true)}>ดูกราฟ M{module}</button></div>
        {!validDay&&<p role="status" className="context-help">เลือกวันที่ตั้งแต่ 1 กรกฎาคม ถึง 1 ตุลาคม 2026 ในรอบข้อมูลนี้</p>}
        {showChart&&<><p className="context-help">ข้อมูลเฉลี่ยที่สังเกตจริงรายนาที · {chart.data?.machine??sourceMachine} / M{module} · {day} · เวลา Asia/Bangkok</p>{chart.error&&<p className="form-error" role="alert">{friendly(chart.error)}</p>}<div className="context-grid" aria-busy={chart.isFetching}><article className="context-chart-card"><header><h3>Pressure · psi</h3></header><ContextChart rows={rows} kind="pressure"/></article><article className="context-chart-card"><header><h3>Temperature · °C</h3></header><ContextChart rows={rows} kind="temperature"/></article></div></>}
        <details className="fleet-study-notes"><summary>ขอบเขตข้อมูลและเงื่อนไขก่อนใช้งานจริง</summary><p>Reference {data.protocol.reference.join(" → ")} · กำหนดเกณฑ์ {data.protocol.calibration.join(" → ")} · ตรวจย้อนหลัง {data.protocol.diagnostic.join(" → ")}</p><p>เครื่องเป้าหมายถูกแยกออกจากกลุ่มที่ให้ข้อมูลช่วยเสมอ ผลนี้ยังไม่ใช่การรับรอง Normal หรือความแม่นยำ ต้องยืนยัน Source contracts, Reference จาก Engineer และตรวจข้อมูลใหม่หลังตรึง Profile ก่อน Active</p></details>
      </>}
      </>}
      </details>
    </div>}
  </details>;
}
