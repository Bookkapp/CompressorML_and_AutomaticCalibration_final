import {useMemo,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "../api";
import {ContextChart,type ChartRow} from "./ContextChart";
import type {LedgerEvent} from "../context-types";

export function EventEvidence({event,onClose}:{event:LedgerEvent;onClose:()=>void}){
  const x=Math.floor(Date.parse(event.occurred_at+"Z")/60000)*60000;
  const [module,setModule]=useState(event.module??1);
  const [start,setStart]=useState(new Date(x-10*60000).toISOString().slice(0,16));
  const [end,setEnd]=useState(new Date(x+10*60000).toISOString().slice(0,16));
  const [slice,setSlice]=useState<[string,string]>([start+":00",end+":00"]);
  const [inputError,setInputError]=useState("");
  const data=useQuery({queryKey:["event-raw",event.event_id,module,slice],queryFn:()=>api.eventRaw(event.event_id,module,...slice),refetchOnWindowFocus:false,retry:false,staleTime:60000});
  const rows:ChartRow[]=useMemo(()=>(data.data?.chart??[]).map(r=>({...r,...(r.duplicate_second?Object.fromEntries(["hp1","lp1","hp2","lp2","temphi","templo","valve"].map(k=>[k,null])):{}),time:String(r.time)})),[data.data]);
  function loadRaw(){
    const first=Date.parse(start+"Z"),last=Date.parse(end+"Z");
    if(!Number.isFinite(first)||!Number.isFinite(last)||last<=first||last-first>30*60000){setInputError("เลือกเวลา Raw ให้สิ้นสุดหลังเริ่ม และไม่เกิน 30 นาที");return;}
    setInputError("");
    const next:[string,string]=[start+":00",end+":00"];
    if(next[0]===slice[0]&&next[1]===slice[1])void data.refetch();else setSlice(next);
  }
  return <section className="context-event-detail"><header><div><h3>หลักฐาน Raw · {event.machine_number} · M{module}</h3><p>{event.occurred_at.replace("T"," ")} · {event.source_timezone}</p></div><button onClick={onClose}>ปิดกราฟ</button></header>
    <div className="context-filters">{!event.module&&<label>Module สำหรับหลักฐาน<select value={module} onChange={e=>setModule(Number(e.target.value))}>{Array.from({length:8},(_,i)=><option key={i} value={i+1}>M{i+1}</option>)}</select></label>}<label>เริ่ม Raw<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>สิ้นสุด Raw<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label><button onClick={loadRaw}>ดู Raw ช่วงนี้</button></div>
    {(inputError||data.isError)&&<p role="alert" className="form-error">{inputError||(data.error?.message.includes("EVENT_RAW_SOURCE_MAPPING_UNVERIFIED")?"แหล่งข้อมูลของ Event นี้ยังยืนยันไม่ได้ ประวัติยังอยู่ แต่ต้องตรวจการเชื่อมข้อมูลก่อนเปิด Raw":data.error?.message)}</p>}
    <p className="context-help">ข้อมูลต้นทาง {data.data?.observed_rows??0} แถว · วินาทีซ้ำ {data.data?.duplicate_rows??0} · ไม่เติมข้อมูลขาด · ครั้งละไม่เกิน 30 นาที</p>
    <div className="context-grid" aria-busy={data.isFetching}><article className="context-chart-card"><h3>Pressure</h3><ContextChart rows={rows} kind="pressure" unit={data.data?.pressure_unit??"psi"}/></article><article className="context-chart-card"><h3>Temperature</h3><ContextChart rows={rows} kind="temperature"/></article><article className="context-chart-card"><h3>Valve command</h3><ContextChart rows={rows} kind="valve"/></article></div>
    {!data.isFetching&&data.data?.observed_rows===0&&<p>ไม่พบ Raw ในช่วงที่เลือก · ประวัติ Event ที่บันทึกไว้ยังคงอยู่</p>}
  </section>;
}
