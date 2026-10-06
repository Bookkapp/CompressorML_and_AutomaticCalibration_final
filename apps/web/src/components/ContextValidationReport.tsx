import {useEffect,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '../api';
import type {ContextModel} from '../context-types';

export function ContextValidationReport({model,onInspect}:{model:ContextModel;onInspect:(time:string)=>void}){
  const [start,setStart]=useState(model.shadow_start.slice(0,10)),[end,setEnd]=useState(model.shadow_end.slice(0,10)),[selected,setSelected]=useState<[string,string]|null>(null);
  useEffect(()=>{setStart(model.shadow_start.slice(0,10));setEnd(model.shadow_end.slice(0,10));setSelected(null);},[model.profile_id]);
  const report=useQuery({queryKey:['context-validation-report',model.profile_id,selected],queryFn:()=>api.contextValidationReport(model.profile_id,selected![0],selected![1]),enabled:!!selected,staleTime:300000,retry:false});
  const r=report.data;
  return <section className="context-review-card"><h3>สรุปการตรวจข้อมูลจริงด้วย Profile ที่ตรึง</h3><p className="context-help">ช่วง Shadow ที่บันทึกไว้ · แยกข้อมูลขาด / สภาวะไม่รองรับ / สภาวะที่งดประเมินออกจากค่าที่เบี่ยงเบน การแจ้งให้ตรวจยังไม่เท่ากับ False alert จนกว่าจะมีผลตรวจจาก Engineer</p>
    <div className="context-filters"><label>วันเริ่ม<input type="date" value={start} min={model.shadow_start.slice(0,10)} onChange={e=>setStart(e.target.value)}/></label><label>วันสิ้นสุด (ไม่รวมวัน)<input type="date" value={end} max={model.shadow_end.slice(0,10)} onChange={e=>setEnd(e.target.value)}/></label><button disabled={!start||!end||end<=start||report.isFetching} onClick={()=>setSelected([start,end])}>ตรวจช่วงข้อมูล</button></div>
    {report.error&&<p role="alert" className="form-error">{String(report.error)}</p>}
    {r&&<><div className="context-badges"><span>ข้อมูลจริง {r.observed_minutes.toLocaleString()} / {r.expected_minutes.toLocaleString()} นาที</span><span>ประเมินได้ {r.supported_minutes.toLocaleString()} นาที</span><span>ควรตรวจ {r.flagged_minutes.toLocaleString()} นาที · {r.flag_burden_pct?.toFixed(2)??'—'}%</span><span>ไม่รองรับ {r.unsupported_minutes.toLocaleString()} นาที</span><span>State Gate {r.excluded_state_minutes.toLocaleString()} นาที</span><span>คุณภาพไม่ผ่าน {r.quality_minutes.toLocaleString()} นาที</span></div>
      <p className="context-help">{r.episodes_total} ช่วงที่ควรตรวจ · ผลนี้เป็นข้อมูลย้อนหลัง ยังใช้แทนการตรวจข้อมูลใหม่หลังตรึงเพื่อเปิด Active ไม่ได้{r.earliest_prospective_day&&` · เริ่มตรวจข้อมูลใหม่ได้ตั้งแต่ ${r.earliest_prospective_day} เมื่อมีข้อมูลครบตามเกณฑ์`}</p>
      <div className="context-table-wrap"><table className="context-table"><thead><tr><th>เริ่ม</th><th>สิ้นสุด</th><th>เวลาที่พบ</th><th>ตรวจหลักฐาน</th></tr></thead><tbody>{r.episodes.slice(0,30).map(e=><tr key={e.start}><td>{e.start.replace('T',' ')}</td><td>{e.end.replace('T',' ')}</td><td>{e.minutes} นาที</td><td><button onClick={()=>onInspect(e.start)}>ดู Raw</button></td></tr>)}</tbody></table></div></>}
  </section>;
}
