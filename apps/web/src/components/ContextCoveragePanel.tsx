import {useQuery} from "@tanstack/react-query";
import {api} from "../api";

const names:Record<string,string>={STATE_GATE_EXCLUDED:"งดประเมินตามขอบเขต",REFERENCE_REVIEWED:"บันทึก Reference แล้ว",NEEDS_REVIEW:"มี Reference · รอทบทวน",INSUFFICIENT_REFERENCE:"Reference ยังไม่พอ"};

export function ContextCoveragePanel({jobId,reviewer,module,onModule}:{jobId:string;reviewer:string;module:number;onModule:(m:number)=>void}){
  const data=useQuery({queryKey:["context-coverage",jobId,reviewer.trim()],queryFn:()=>api.contextCoverage(jobId,reviewer.trim()),
    enabled:reviewer.trim().length>=2,retry:false,staleTime:30_000,refetchOnWindowFocus:true});
  return <section className="context-coverage-card" aria-label="Coverage ตามสภาวะ">
    <header><h3>Coverage ของ Profile · M1–M8</h3><button onClick={()=>void data.refetch()}>อัปเดต Coverage</button></header>
    <p className="context-help">เลือกโมดูลเพื่อดูกราฟและทบทวน · จำนวนวันและนาทีเป็นความครอบคลุมของข้อมูล ยังไม่ยืนยันว่าเครื่องปกติ</p>
    {data.error&&<p className="form-error" role="alert">{data.error.message}</p>}
    <div className="context-table-wrap"><table className="context-table"><thead><tr><th>Module</th><th>SV OFF</th><th>SV ON</th><th>Active</th></tr></thead><tbody>
      {data.data?.modules.map(m=><tr key={m.module}><td><button aria-pressed={m.module===module} onClick={()=>onModule(m.module)}>M{m.module}</button></td>
        {m.states.map(s=><td key={s.sv}><strong>{names[s.status]??s.status}</strong><small>{s.best_regime_days} วัน · {s.proposed_steady_minutes.toLocaleString()} นาทีที่ใช้เสนอสภาวะ</small><small>{s.supported_regimes} สภาวะถึงขั้นต่ำ · รับไว้ {s.accepted_regimes}</small>{s.reason&&<small>{s.reason}</small>}</td>)}
        <td>{m.active?"Active ในขอบเขตที่รับรอง":"ยังไม่ Active"}</td></tr>)}
    </tbody></table></div>
    {!data.data&&<p className="context-help">กำลังอ่านสรุปจาก Profile ที่บันทึกไว้</p>}
  </section>;
}
