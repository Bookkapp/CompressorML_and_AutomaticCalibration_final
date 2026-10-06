import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from '../api';
import type {ContextModel,FollowupDaySummary} from '../context-types';

const reasons:Record<string,string>={FUTURE_SOURCE_TIMESTAMP_CHECK_CLOCK:'พบเวลา Reference หรือข้อมูลต้นทางอยู่ในอนาคต ตรวจนาฬิกาและ timestamp ก่อนตรวจรับ',NO_SOURCE_DATA:'ยังไม่มีข้อมูลต้นทางของเครื่องนี้',SOURCE_NOT_AFTER_REVIEW:'ข้อมูลต้นทางยังมาไม่ถึงวันทดสอบหลังตรึง Reference',WAITING_FOR_COMPLETE_DAYS:'รับข้อมูลแล้วบางช่วง ยังไม่ครบ 3 วันเต็มหลังตรึง Reference',SOURCE_DAY_MISSING:'ช่วง 3 วันล่าสุดมีวันที่ไม่มีข้อมูลหรือยังปิดวันไม่ได้',READY_FOR_FULL_VALIDATION:'มีข้อมูลในช่วง 3 วันเต็ม พร้อมเริ่มตรวจรับ · ยังไม่ได้ยืนยันว่าผ่านเกณฑ์'};
const categories:Record<string,string>={UNEXPECTED_TRANSITION:'การตอบสนองต่างจาก Reference',STEADY_DEVIATION:'ค่าต่างจาก Reference',NEW_STEADY_LEVEL:'ระดับนิ่งใหม่ ต้องทบทวน',UNSUPPORTED_TRANSITION:'Transition ยังไม่รองรับ',INSUFFICIENT_REFERENCE:'Reference ยังไม่พอ',DATA_UNAVAILABLE:'คุณภาพข้อมูลไม่ผ่าน',UNSUPPORTED_CONTROL_CONTEXT:'สภาวะควบคุมยังไม่รองรับ'};
const time=(v:string|null|undefined)=>v?v.replace('T',' ').replace(/([+-]\d\d:\d\d|Z)$/,'').slice(0,19):'—';
const minutes=(v:number)=>v.toLocaleString();

export function ContextFollowupProgress({model,reviewer,dirty,running,onValidate,onOpen}:{model:ContextModel;reviewer:string;dirty:boolean;running:boolean;onValidate:()=>void;onOpen:(job:string,day:string,start:string,end:string,at?:string)=>void}){
  const client=useQueryClient();
  const key=['context-followup',model.profile_id,reviewer.trim()];
  const query=useQuery({queryKey:key,queryFn:()=>api.contextFollowup(model.profile_id,reviewer.trim()),enabled:!!model.reference_review&&reviewer.trim().length>=2,retry:false,staleTime:20000,refetchOnWindowFocus:true,
    refetchInterval:q=>q.state.data?.job?.status?.startsWith('PREVIEW_')?3000:30000,refetchIntervalInBackground:false});
  const inspect=useMutation({mutationFn:()=>api.inspectFollowup(model.profile_id,reviewer.trim()),onSuccess:()=>client.invalidateQueries({queryKey:key})});
  const p=query.data;const busy=running||inspect.isPending||!!p?.job?.status.startsWith('PREVIEW_');
  function open(day:string,at?:string){if(p?.saved_job_id&&p.inspection_start&&p.inspection_end)onOpen(p.saved_job_id,day,p.inspection_start,p.inspection_end,at);}
  function outcome(s:FollowupDaySummary){
    if((s.categories?.MOCK_DATA??0)>0)return `พบ Normal จำลอง ${minutes(s.categories?.MOCK_DATA??0)} นาที · ไม่ใช้ตรวจรับ Active`;
    if(s.day<(p?.first_day??''))return 'ตรวจหลังตรึงในวันเดียวกัน · ยังไม่นับเป็นวันเต็ม';
    if(!s.closed)return 'ตรวจบางส่วน · วันยังไม่ปิด';
    if(s.supported_minutes<60)return 'นาทีที่ประเมินได้ยังไม่ถึงขั้นต่ำ';
    if(s.unresolved_minutes>0)return 'มีสภาวะที่ยังต้องทบทวน';
    if(s.flag_pct>(p?.maximum_flag_pct??1))return 'ความเบี่ยงเบนเกินเกณฑ์';
    return 'ผลเบื้องต้นอยู่ในเกณฑ์ · รอตรวจรับเต็มรอบ';
  }
  return <section className="context-followup" aria-label="ความคืบหน้าหลังตรึง Reference">
    <header className="context-heading"><div><h4>ความคืบหน้าหลังตรึง Reference · M{model.module}</h4><p className="context-help">Reference {model.profile_id.slice(0,12)} · เวลา {p?.checked_at?'ตรวจสถานะ '+time(p.checked_at):'เครื่อง'}</p></div><button disabled={query.isFetching||!model.reference_review} onClick={()=>void query.refetch()}>อัปเดตข้อมูลใหม่</button></header>
    {!model.reference_review?<p className="context-help">บันทึกผลทบทวนเพื่อกำหนดเวลาเริ่มตรวจข้อมูลใหม่</p>:<>
      <dl className="context-followup-meta"><div><dt>ตรึง Reference</dt><dd>{time(p?.reviewed_at??model.reference_review.at)}</dd></div><div><dt>วันแรกที่ใช้ตรวจรับได้</dt><dd>{p?.first_day??'—'}</dd></div><div><dt>ข้อมูลต้นทางล่าสุด</dt><dd>{time(p?.source_latest)}</dd></div></dl>
      {query.error&&<p role="alert" className="form-error">อ่านความคืบหน้าไม่ได้: {query.error.message}</p>}
      {p&&<><div className="context-badges"><span>วันปิดที่พบข้อมูล <strong>{Math.min(3,p.received_closed_days)} / 3</strong><small>ยังต้องตรวจความครบถ้วน</small></span><span>วันปิดที่ตรวจได้ ≥ {p.minimum_daily_minutes} นาที <strong>{Math.min(3,p.inspected_supported_days)} / 3</strong><small>ยังต้องผ่านสภาวะและอัตราเบี่ยงเบน</small></span></div>
        <p className={p.clock_error?'form-error':'context-help'}>{reasons[p.reason]??p.reason}</p>
        {p.source_age_seconds!==null&&p.source_age_seconds>3600&&<p className="context-help">ข้อมูลล่าสุดห่างจากเวลาตรวจ {Math.floor(p.source_age_seconds/3600)} ชั่วโมง · ตรวจการรับข้อมูลหากเครื่องยังทำงานอยู่</p>}
        {p.validation_start&&<p className="context-help">ช่วงตรวจรับ 3 วันล่าสุด: {p.validation_start} — ก่อน {p.validation_end} · วันละ ≥ {p.minimum_daily_minutes} นาที · รวม ≥ {p.minimum_total_minutes} นาที · เบี่ยงเบน ≤ {p.maximum_flag_pct}%</p>}
        <div className="context-table-wrap"><table className="context-table"><thead><tr><th>วันที่ / การรับข้อมูล</th><th>ผลตรวจด้วย Reference ที่ตรึง</th><th>ตรวจหลักฐาน</th></tr></thead><tbody>{p.daily.map(d=><tr key={d.day}><td><strong>{d.day}</strong><small>{!d.has_data?'ยังไม่มีข้อมูล':d.day<p.first_day?'วันตรึง · นับเฉพาะข้อมูลหลังบันทึก':d.closed?'วันปิดแล้ว · ยังต้องตรวจความครบถ้วน':'รับข้อมูลบางส่วน · ยังไม่ปิดวัน'}</small>{d.last_at&&<small>ถึง {time(d.last_at)}</small>}</td><td>{d.inspection?<><strong>{outcome(d.inspection)}</strong><small>ตรวจถึง {time(d.inspection.inspected_until)}</small><small>อยู่ในกรอบ {minutes(d.inspection.within_minutes)} · เบี่ยงเบน {minutes(d.inspection.flagged_minutes)} ({d.inspection.supported_minutes?d.inspection.flag_pct.toFixed(2)+'%':'ยังประเมินไม่ได้'}) · ต้องทบทวน {minutes(d.inspection.unresolved_minutes)} นาที</small><small>State Gate {minutes(d.inspection.excluded_state_minutes)} · ควบคุมไม่รองรับ {minutes(d.inspection.unsupported_control_minutes)} · คุณภาพไม่ผ่าน {minutes(d.inspection.data_unavailable_minutes)} · ข้อมูลขาด {minutes(d.inspection.missing_minutes)} นาที</small></>:d.has_data?'ยังไม่ได้ตรวจ':'—'}</td><td><button disabled={!d.inspection||!p.saved_job_id} onClick={()=>open(d.day)}>ดูกราฟรายวัน</button>{d.inspection?.episodes.length?<details><summary>{d.inspection.episodes_total} ช่วงที่ควรตรวจ</summary>{d.inspection.episodes.slice(0,12).map(e=><div className="context-followup-episode" key={e.start}><span>{e.start.slice(11,16)} · {categories[e.category]??e.category} · {e.minutes} นาที</span><button onClick={()=>open(d.day,e.start)}>ดู Raw</button></div>)}</details>:null}</td></tr>)}</tbody></table></div>
        {p.inspection_stale&&<p className="context-help">มีข้อมูลใหม่หลังผลตรวจที่บันทึกไว้ กดตรวจข้อมูลที่มีแล้วเพื่ออัปเดตผล</p>}
        {busy&&<p role="status" className="context-progress">{p.job?.progress_message?.replace('Reading source day ','ตรวจข้อมูลวันที่ ')??'กำลังเริ่มตรวจข้อมูล'} · กลับมาเปิดหน้านี้เพื่อติดตามงานเดิมได้</p>}
        {p.job?.status==='FAILED'&&<p role="alert" className="form-error">ตรวจข้อมูลไม่สำเร็จ: {reasons[p.job.error_code??'']??p.job.error_code} · อัปเดตสถานะแล้วลองตรวจใหม่</p>}
      </>}
      {inspect.error&&<p role="alert" className="form-error">เริ่มตรวจไม่ได้: {reasons[inspect.error.message]??inspect.error.message}</p>}
      {dirty&&<p className="context-progress">ผลทบทวนหรือช่วงข้อมูลเปลี่ยนแล้ว บันทึกเวอร์ชันใหม่ก่อนตรวจข้อมูล</p>}
      <div className="context-actions"><button disabled={!p?.can_inspect||dirty||busy} onClick={()=>inspect.mutate()}>ตรวจข้อมูลที่มีแล้ว</button><button disabled={!p?.can_validate||dirty||busy} onClick={onValidate}>ตรวจข้อมูลใหม่ครบ 3 วันด้วย Reference ที่ตรึง</button></div>
      <p className="context-help">ผลรายวันใช้ตรวจระหว่างรอ · ไม่ปรับ Baseline และไม่ใช้เป็นหลักฐานอนุมัติ Active · ช่วงล่าสุดอาจล่าช้าไม่เกิน 5 นาทีบวกเวลารอข้อมูล</p>
    </>}
  </section>;
}
