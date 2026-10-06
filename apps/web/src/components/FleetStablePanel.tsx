import {useEffect,useMemo,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "../api";
import {ContextChart,type ChartRow} from "./ContextChart";

const reason=(error:unknown)=>{
  const value=error instanceof Error?error.message:"";
  if(value.includes("version changed"))return "มีการเปลี่ยนเวอร์ชัน Fleet กรุณากดอ่านเวอร์ชันล่าสุดแล้วเปิดกราฟอีกครั้ง";
  if(value.includes("verification failed"))return "ไฟล์โมเดลตรวจสอบไม่ผ่าน กรุณาตรวจเวอร์ชันที่ติดตั้งก่อนใช้งาน";
  if(value.includes("not installed"))return "ยังไม่ได้ติดตั้ง Fleet Stable ในระบบนี้";
  if(value.includes("committed day"))return "วันที่เลือกยังไม่มีข้อมูลในชุดย้อนหลังนี้";
  return value||"ยังอ่านข้อมูลไม่ได้ กรุณาลองอีกครั้ง";
};
const assessment=(v:string)=>({REVIEW:"ควรตรวจสอบ",WITHIN_REFERENCE:"อยู่ในกรอบ Reference",DATA_QUALITY:"ข้อมูลอ่านผิดหรือไม่ครบ",NOT_EVALUATED:"ไม่ได้ประเมินในสภาวะนี้"}[v]??v);
const pointReason=(v:string)=>({ACQUISITION_SUSPECT:"สงสัยค่าอ่านผิดหรือค่าเริ่มต้นเซนเซอร์",INCOMPLETE_MEASUREMENTS:"ข้อมูลนาทีนี้ไม่ครบตามเกณฑ์",CONTROL_CONTEXT_UNSUPPORTED:"ไม่อยู่ในสภาวะ Run / Module On / Busy 0 ที่รองรับ",NO_LOCAL_PROFILE:"ยังมีข้อมูล Local สำหรับสร้างกรอบไม่พอ",REFERENCE_DEVIATION:"ค่าออกจาก Reference เดิม"}[v]??v);

export function FleetStablePanel({machine,module,onModule}:{machine:string;module:number;onModule:(value:number)=>void}){
  const [day,setDay]=useState("2026-09-07"),[show,setShow]=useState(false);
  useEffect(()=>{setShow(false);},[machine,module]);
  const reference=useQuery({queryKey:["fleet-stable",machine,module],queryFn:()=>api.fleetStableReference(machine,module),
    staleTime:60_000,retry:false,refetchOnWindowFocus:false});
  const version=reference.data?.bundle_id;
  const [firstDay,lastDay]=reference.data?.evidence_dates??["2026-07-01","2026-10-01"];
  const chart=useQuery({queryKey:["fleet-stable-day-v2",version,machine,module,day],
    queryFn:()=>api.fleetStableDay(machine,module,day,version!),enabled:show&&!!version,
    staleTime:300_000,retry:false,refetchOnWindowFocus:false});
  const rows=useMemo<ChartRow[]>(()=>chart.data?.chart.map(point=>({time:point.time,
    ...(point.assessment==="DATA_QUALITY"?{}:point.features)}))??[],[chart.data]);
  const validDay=/^\d{4}-\d{2}-\d{2}$/.test(day)&&day>=firstDay&&day<=lastDay;
  return <section className="fleet-stable-section" aria-label="Fleet Stable frozen model">
    <div className="fleet-evidence-controls"><h3>Fleet Stable v1</h3><button onClick={()=>{setShow(false);void reference.refetch();}}>อ่านเวอร์ชันล่าสุด</button></div>
    {reference.error&&<p role="status" className="form-error">{reason(reference.error)}</p>}
    {reference.data&&<>
      <div className="context-badges"><span>ตรึงโมเดลแล้ว · ทดลอง Shadow</span><span>รอรับรอง Normal</span><span>เวอร์ชัน {version?.slice(-12)}</span><span>ยังไม่ส่ง Alert</span></div>
      <p className="context-help">ใช้ข้อมูลกลางจาก {reference.data.source_machines.map(m=>`MX${m}`).join(" · ")} ช่วยรูปแบบความสัมพันธ์ โดยรักษาระดับ Baseline ของแต่ละเครื่องไว้ รุ่นนี้โหลดจากไฟล์โมเดลที่ตรึงแล้ว การเปิดกราฟไม่เทรนใหม่</p>
      <p className="context-help">Reference ของรุ่นนี้รองรับช่วงค่าคงที่ (Steady) · Transition จาก Fleet ยังเป็นข้อมูลเหตุการณ์และสถิติ ยังไม่ได้ใช้เติมกรอบ Transition ให้ Local Profile อัตโนมัติ</p>
      {!!reference.data.module_coverage?.length&&<details className="fleet-coverage"><summary>Coverage ของ Fleet · M1–M8 · {machine}</summary><div className="context-table-wrap"><table className="context-table"><thead><tr><th>Module</th><th>SV OFF</th><th>SV ON</th></tr></thead><tbody>{reference.data.module_coverage.map(m=><tr key={m.module}><td><button aria-pressed={m.module===module} onClick={()=>onModule(m.module)}>M{m.module}</button></td>{m.states.map(s=><td key={s.sv}>{s.status==="FROZEN_SHADOW_REFERENCE"?"มี Reference · Shadow":"Reference ยังไม่พอ"}</td>)}</tr>)}</tbody></table></div><p className="context-help">Coverage ของ Fleet เป็นคนละชุดกับ Profile ที่ทบทวนด้านล่าง การเลือก State Gate ต้องบันทึกใน Profile ของโมดูลนั้น</p></details>}
      <div className="fleet-evidence-controls"><label>Module ของ {machine}<select aria-label="Fleet Stable module" value={module} onChange={e=>onModule(Number(e.target.value))}>{Array.from({length:8},(_,i)=><option key={i+1} value={i+1}>M{i+1}</option>)}</select></label>
        <label>วันที่ดูหลักฐาน<input aria-label="Fleet Stable evidence date" type="date" min={firstDay} max={lastDay} value={day} onInput={e=>{setDay(e.currentTarget.value);setShow(false);}} onChange={e=>{setDay(e.target.value);setShow(false);}}/></label>
        <button disabled={!validDay} onClick={()=>setShow(true)}>ดูกราฟ Fleet Stable</button></div>
      <div className="context-table-wrap"><table className="context-table"><thead><tr><th>สภาวะ</th><th>ช่วงสร้าง Reference</th><th>ช่วงกำหนดเกณฑ์</th><th>ส่วนช่วยจาก Fleet</th></tr></thead><tbody>
        {reference.data.profiles.length?reference.data.profiles.map(p=><tr key={p.context}><td>{p.context.replace("_"," ")}</td><td>{p.reference_start} → {p.reference_end}<br/>{p.n.toLocaleString()} จุดห่าง 15 นาที</td><td>{p.threshold_period.join(" → ")}</td><td>{(p.fleet_weight*100).toFixed(1)}%<br/>{p.donor_machines.map(m=>`MX${m}`).join(" · ")||"ใช้ Local"}</td></tr>):<tr><td colSpan={4}>M{module} ยังมีข้อมูลสำหรับสร้างกรอบไม่พอ สามารถเปิดข้อมูลจริงดูได้</td></tr>}
      </tbody></table></div>
      <p className="context-help">วันสิ้นสุดในตารางไม่รวมวันนั้น ช่วงของ MX080/M6 ที่เสนอว่าปกติยังรอ Engineer รับรอง การนิ่งและการอยู่ในกรอบ Reference ยังไม่ยืนยันสุขภาพเครื่อง</p>
      {show&&<>
        <p className="context-help">{machine} / M{module} · {day} · psi · เวลา Asia/Bangkok</p>
        {chart.error&&<p role="alert" className="form-error">{reason(chart.error)}</p>}
        <div className="context-badges fleet-stable-counts">{["WITHIN_REFERENCE","REVIEW","DATA_QUALITY","NOT_EVALUATED"].map(key=><span key={key}>{assessment(key)} {chart.data?(chart.data.counts[key]??0).toLocaleString():"—"} นาที</span>)}</div>
        <div className="context-grid" aria-busy={chart.isFetching}><article className="context-chart-card"><header><h3>Pressure · psi</h3></header><ContextChart rows={rows} kind="pressure"/></article><article className="context-chart-card"><header><h3>Temperature · °C</h3></header><ContextChart rows={rows} kind="temperature"/></article></div>
        {!!chart.data?.counts.DATA_QUALITY&&<p className="context-help">ช่วงข้อมูลอ่านผิดหรือไม่ครบแสดงเป็นช่องว่าง ไม่ใช้เป็น Normal หรือแรงดันผิดปกติทางกายภาพ ข้อมูลต้นฉบับยังเก็บอยู่</p>}
        {chart.data&&<details><summary>ช่วงที่ควรตรวจสอบและข้อมูลที่ยังไม่รองรับ</summary><div className="context-table-wrap"><table className="context-table"><thead><tr><th>เวลา</th><th>ผลและเหตุผล</th><th>พฤติกรรม / การควบคุม</th><th>หลักฐาน CP2</th></tr></thead><tbody>{chart.data.chart.filter(p=>p.assessment!=="WITHIN_REFERENCE").filter((p,i,a)=>!i||p.assessment!==a[i-1].assessment||p.phase!==a[i-1].phase||p.reason!==a[i-1].reason||p.cp2_level_flag!==a[i-1].cp2_level_flag||Date.parse(p.time)-Date.parse(a[i-1].time)>60_000).slice(0,40).map(p=><tr key={p.time}><td>{p.time.slice(11,16)}</td><td>{assessment(p.assessment)}<small>{pointReason(p.reason)}</small></td><td>{p.phase==="STEADY_OBSERVATION"?"นิ่งแล้ว แต่ต้องตรวจระดับค่า":p.phase==="RESPONSE_OR_CHANGING"?"ค่ากำลังตอบสนองหรือเปลี่ยน": "ไม่ประเมินสุขภาพ"}<small>{p.control?.compressor??"—"} / Module {p.control?.module_state??"—"} · SV {p.control?.sv??"—"} · Busy {p.control?.busy??"—"}</small></td><td>{p.cp2_level_flag?"HP2 / LP2 ออกจากกรอบ Local":"—"}</td></tr>)}</tbody></table></div><p className="context-help">แสดงจุดเริ่มหรือเปลี่ยนประเภทสูงสุด 40 จุดในวัน การเปลี่ยน SV / Valve ไม่ซ่อนคะแนน ช่วงตอบสนองยังต้องทบทวนกับ control และ raw data</p></details>}
      </>}
      <details><summary>สิ่งที่ต้องตรวจให้ครบก่อนเปิดใช้งานจริง</summary><p className="context-help">รับรองช่วง Normal และ hardware / configuration / state / controller / service epoch / psig หรือ psia จากนั้นทดสอบรอบปกติและข้อมูลใหม่หลังตรึงโมเดล พร้อมตรวจการเชื่อมต่อ Server และ Approval</p></details>
    </>}
  </section>;
}
