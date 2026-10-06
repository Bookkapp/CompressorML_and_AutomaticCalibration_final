import { useEffect,useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { LedgerEvent } from "../context-types";
import "./context-calibration.css";
import {EventEvidence} from "./EventEvidence";

const eventNames:Record<string,string>={VALVE_COMMAND_CHANGED:"ปรับ Valve",SV_CHANGED:"เปลี่ยน SV",BUSY_CHANGED:"เปลี่ยน Busy",MODULE_STATE_CHANGED:"เปลี่ยนสถานะ Module",COMPRESSOR_STATE_CHANGED:"เปลี่ยนสถานะ Compressor",SOURCE_GAP:"ช่องว่างข้อมูล",DUPLICATE_SECOND:"ข้อมูลวินาทีซ้ำ",OBSERVATION_START:"เริ่มช่วงข้อมูลที่สังเกตได้",OBSERVATION_RESUMED:"กลับมามีข้อมูล",PHASE_ASSESSMENT_CHANGED:"เปลี่ยนผลประเมินสภาวะ",ANOMALY_ASSESSMENT_CHANGED:"เปลี่ยนผลตรวจความเบี่ยงเบน",PROFILE_CANDIDATE_CREATED:"สร้าง Candidate",PROFILE_SHADOW_COMPLETED:"ตรวจ Shadow เสร็จ",PROFILE_REFERENCE_REVIEWED:"บันทึกผลทบทวน Reference",PROFILE_ACTIVATED:"เปิด Active Profile",PROFILE_ROLLED_BACK:"ย้อนกลับ Active Profile",SOURCE_REVISION_CHANGED:"ข้อมูลต้นฉบับมีการแก้ไข",NOTIFICATION_DELIVERY_RECORDED:"บันทึกการส่งแจ้งเตือน",ALERT_CREATED:"สร้างการแจ้งเตือน",ALERT_ACKNOWLEDGED:"รับทราบการแจ้งเตือน",ALERT_CLOSED:"ปิดการแจ้งเตือน",WORK_ORDER_CREATED:"สร้าง Work order",WORK_ORDER_STARTED:"เริ่ม Work order",WORK_ORDER_COMPLETED:"จบ Work order",SERVICE_LOG_CREATED:"บันทึก Service log",SERVICE_LOG_UPDATED:"แก้ไข Service log"};
export function EventHistory({machine:fixedMachine,module:fixedModule,onInvestigate}:{machine?:string;module?:number;onInvestigate?:(event:LedgerEvent)=>void}){
  const [machine,setMachine]=useState(fixedMachine??"");const [module,setModule]=useState(fixedModule?String(fixedModule):"");
  const [family,setFamily]=useState("");const [mode,setMode]=useState("");const [assessment,setAssessment]=useState("");const [eventType,setEventType]=useState("");const [start,setStart]=useState("");const [end,setEnd]=useState("");
  const [cursor,setCursor]=useState("");const [cursors,setCursors]=useState<string[]>([]);const [selected,setSelected]=useState<LedgerEvent|null>(null);
  const [evidence,setEvidence]=useState<LedgerEvent|null>(null);
  useEffect(()=>{setMachine(fixedMachine??"");setModule(fixedModule?String(fixedModule):"");},[fixedMachine,fixedModule]);
  useEffect(()=>{setCursor("");setCursors([]);setSelected(null);setEvidence(null);},[machine,module,family,mode,assessment,eventType,start,end]);
  const machines=useQuery({queryKey:["source-machines"],queryFn:api.sourceMachines,enabled:!fixedMachine,staleTime:60_000});
  const params:Record<string,string>={machine_number:machine,limit:"100"};
  if(module)params.module=module;if(family)params.family=family;if(mode)params.mode=mode;if(start)params.start=start+"T00:00:00";
  if(assessment)params.assessment=assessment;if(eventType)params.event_type=eventType;
  if(end){const d=new Date(end+"T00:00:00Z");d.setUTCDate(d.getUTCDate()+1);params.end=d.toISOString().slice(0,19);}if(cursor)params.cursor=cursor;
  const history=useQuery({queryKey:["unified-events",params],queryFn:()=>api.eventHistory(params),enabled:!!machine,refetchOnWindowFocus:false,retry:1});
  const detail=useQuery({queryKey:["event-detail",selected?.event_id],queryFn:()=>api.eventDetail(selected!.event_id),enabled:!!selected,staleTime:60_000});
  return <section className="context-section"><header className="context-heading"><div><h2>Event History</h2><p>Transition · Anomaly · Profile · ประวัติเหตุการณ์ร่วมกัน</p></div><button onClick={()=>history.refetch()} disabled={!machine||history.isFetching}>อัปเดต</button></header>
    <div className="context-filters">{!fixedMachine&&<label>เครื่อง<select value={machine} onChange={e=>setMachine(e.target.value)}><option value="">เลือกเครื่อง</option>{machines.data?.map(m=><option key={m.machine_number} value={m.machine_number}>{m.machine_number}</option>)}</select></label>}
      {!fixedModule&&<label>Module<select value={module} onChange={e=>setModule(e.target.value)}><option value="">ทุก Module และเหตุการณ์ระดับเครื่อง</option>{Array.from({length:8},(_,i)=><option key={i} value={i+1}>M{i+1}</option>)}</select></label>}
      <label>ประเภท<select value={family} onChange={e=>setFamily(e.target.value)}><option value="">ทั้งหมด</option><option value="CONTROL">Valve / SV / State</option><option value="PHASE">สภาวะ / Transition</option><option value="ANOMALY">Anomaly</option><option value="PROFILE">Profile</option><option value="DATA_QUALITY">คุณภาพข้อมูล</option><option value="NOTIFICATION">การแจ้งเตือน</option><option value="OPERATIONAL">งานและ Service</option></select></label>
      <label>เหตุการณ์<select value={eventType} onChange={e=>setEventType(e.target.value)}><option value="">ทั้งหมด</option>{Object.entries(eventNames).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label>ผลประเมิน<select value={assessment} onChange={e=>setAssessment(e.target.value)}><option value="">ทั้งหมด</option><option value="UNASSESSED">บันทึกไว้ ยังไม่ยืนยันความผิดปกติ</option><option value="PROPOSED">ผลประเมิน Candidate</option><option value="SOURCE_RECORDED">บันทึกจากระบบงาน</option></select></label>
      <label>ที่มา<select value={mode} onChange={e=>setMode(e.target.value)}><option value="">ทั้งหมด</option><option value="HISTORICAL">ข้อมูลอดีต</option><option value="SHADOW">Shadow</option><option value="LIVE">เหตุการณ์ระบบงานจริง</option><option value="DETECTOR_LIVE">Live detector</option><option value="DETECTOR_SHADOW">Detector Shadow</option></select></label>
      <label>ตั้งแต่วันที่<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>ถึงวันที่<input type="date" value={end} min={start} onChange={e=>setEnd(e.target.value)}/></label></div>
    {history.isError&&<p className="form-error">{history.error.message}</p>}
    {!machine?<p className="context-empty">เลือกเครื่องเพื่อดูประวัติ</p>:<div className="context-table-wrap" aria-busy={history.isFetching}><table className="context-table"><thead><tr><th>เวลาเครื่อง</th><th>Module</th><th>เหตุการณ์</th><th>ก่อน → หลัง</th><th>ที่มา</th><th>รายละเอียด</th></tr></thead><tbody>
      {history.data?.items.map(event=><tr key={event.event_id}><td>{event.occurred_at.replace("T"," ")}<small>{event.source_timezone}</small></td><td>{event.module?`M${event.module}`:"ทั้งเครื่อง"}</td><td>{eventNames[event.event_type]??event.event_type}<small>{event.assessment==="PROPOSED"?"ผลประเมิน Candidate":event.assessment==="UNASSESSED"?"บันทึกเหตุการณ์ · ยังไม่ยืนยันความผิดปกติ":event.assessment}</small></td><td>{String(event.payload.details.before??"—")} → {String(event.payload.details.after??"—")}</td><td>{event.mode}</td><td><button onClick={()=>setSelected(event)}>ดูเหตุการณ์</button>{event.family!=="PROFILE"&&<button onClick={()=>onInvestigate?onInvestigate(event):setEvidence(event)}>ดูกราฟ</button>}</td></tr>)}
    </tbody></table>{history.isPending?<p className="context-empty">กำลังอ่านประวัติ</p>:history.data?.items.length===0&&<p className="context-empty">ไม่มีเหตุการณ์ที่ตรงกับตัวกรอง</p>}</div>}
    <div className="context-actions"><button disabled={!cursor} onClick={()=>{const prev=[...cursors];setCursor(prev.pop()??"");setCursors(prev);}}>ก่อนหน้า</button><button disabled={!history.data?.next_cursor} onClick={()=>{setCursors([...cursors,cursor]);setCursor(history.data!.next_cursor!);}}>ถัดไป</button></div>
    {selected&&<aside className="context-event-detail"><header><h3>{eventNames[selected.event_type]??selected.event_type}</h3><button onClick={()=>setSelected(null)}>ปิดรายละเอียด</button></header><p>{selected.machine_number} · {selected.module?`M${selected.module}`:"ทั้งเครื่อง"} · {selected.occurred_at.replace("T"," ")}</p>
      <dl>{Object.entries(selected.payload.details).filter(([,v])=>typeof v!=="object").map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v??"—")}</dd></div>)}</dl>
      {Boolean(selected.payload.details.physical_after)&&<details><summary>ค่าที่วัดหลังเหตุการณ์</summary><pre>{JSON.stringify(selected.payload.details.physical_after,null,2)}</pre></details>}
      <p>เหตุการณ์ที่สัมพันธ์กัน: {detail.data?.related.length??0}</p><ul>{detail.data?.related.slice(0,12).map(e=><li key={e.event_id}>{eventNames[e.event_type]??e.event_type} · {e.module?`M${e.module}`:"ทั้งเครื่อง"}</li>)}</ul>
    </aside>}
    {evidence&&<EventEvidence key={evidence.event_id} event={evidence} onClose={()=>setEvidence(null)}/>}
  </section>;
}

