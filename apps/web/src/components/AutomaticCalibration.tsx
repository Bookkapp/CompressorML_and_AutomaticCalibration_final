import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Play, RefreshCw } from "lucide-react";
import { api } from "../api";
import { approvalReason } from "../calibration-review";
import { ReferenceReview, type ReferenceJob } from "./ReferenceReview";
import { SourceContract } from "./CalibrationEvidence";
import "./reference-review.css";

type ModuleResult = { module: number; job_id: string; status: string; candidate_created: boolean;
  reason_codes: string[]; coverage_issues: string[];
  reference_selection?:{start:string;end:string;changed:boolean;reason:string};
  summary: { reference_minutes: number; shadow_minutes: number; retained_reference_minutes: number;quarantine_pct?:number;shadow_flag_pct?:number|null } };
export type AutomaticJob = Omit<ReferenceJob,"result"> & { created_at: string; updated_at: string;
  result: null | { profiles: number; batch_id: string | null; modules: ModuleResult[];selector_version?:string;
    selection: { source_latest: string; reference_start: string; reference_end: string; shadow_start: string; shadow_end: string } } };
const busy = (status?: string) => Boolean(status && ["PREVIEW_QUEUED","PREVIEW_RUNNING"].includes(status));
const labels: Record<string,string> = { READY_FOR_APPROVAL:"พร้อมตรวจและอนุมัติ",REVIEW_REQUIRED:"ต้องตรวจหลักฐาน",
  INSUFFICIENT_DATA:"รอข้อมูลการทำงาน",SHADOW_VALIDATION:"รอยืนยันข้อมูลพื้นฐาน",CANDIDATE_PROFILE:"รอ Shadow" };
const orderedReasons = (reasons:string[]) => [...reasons].sort((a,b)=>{
  const rank=(value:string)=>value.startsWith("INSUFFICIENT_")?0:value.endsWith("EXCEEDED")?1:value==="SOURCE_PRESSURE_UNIT_UNVERIFIED"?2:3;
  return rank(a)-rank(b);
});

export function AutomaticCalibration({ machine, module, reviewer, onReviewer, onModule, onBuilt }: {
  machine:string; module:number; reviewer:string; onReviewer:(value:string)=>void;
  onModule:(value:number)=>void; onBuilt:(batch:string)=>void;
}) {
  const [manual,setManual] = useState(false);
  const [opened,setOpened] = useState<{module:number;job:string}|null>(null);
  const [requestKey,setRequestKey] = useState(()=>crypto.randomUUID());
  const [jobId,setJobId] = useState<string|null>(null);
  const [lastCompleted,setLastCompleted]=useState<AutomaticJob|null>(null);
  useEffect(()=>{if(manual)document.getElementById("ref-title")?.scrollIntoView({behavior:"smooth",block:"start"});},[manual,opened?.job]);
  useEffect(()=>{
    try { if (!reviewer) onReviewer(localStorage.getItem("ht9046mx-calibration-reviewer") ?? ""); } catch { /* storage optional */ }
  },[]);
  useEffect(()=>{ try { if (reviewer.trim()) localStorage.setItem("ht9046mx-calibration-reviewer",reviewer); } catch { /* storage optional */ } },[reviewer]);
  const latest = useQuery({queryKey:["automatic-reference",machine,reviewer.trim()],
    queryFn:()=>api.latestAutomatic(machine,reviewer.trim()),enabled:reviewer.trim().length>=2,
    staleTime:30_000,refetchOnWindowFocus:false,retry:false,
    refetchInterval:q=>busy(q.state.data?.status) ? 2000 : 30_000 });
  const job = useQuery({queryKey:["automatic-reference-job",jobId,reviewer.trim()],
    queryFn:()=>api.automaticJob(jobId!,reviewer.trim()),enabled:Boolean(jobId)&&reviewer.trim().length>=2,
    refetchOnWindowFocus:false,retry:1,refetchInterval:q=>busy(q.state.data?.status) ? 2000 : false});
  const prepare = useMutation({mutationFn:()=>api.prepareAutomatic(reviewer.trim(),{
    machine_number:machine,history_days:28,idempotency_key:requestKey}),
    onSuccess:value=>{setJobId(value.job_id);setRequestKey(crypto.randomUUID());latest.refetch();}});
  const current = jobId ? job.data ?? prepare.data : latest.data;
  useEffect(()=>{if(current?.status==="COMPLETED"&&current.result)setLastCompleted(current);},[current?.job_id,current?.status]);
  const open = useMutation({mutationFn:(item:ModuleResult)=>api.copyAutomaticReview(item.job_id,reviewer.trim()),
    onSuccess:value=>{onModule(value.module);setOpened({module:value.module,job:value.job_id});setManual(true);
      if(value.result?.batch_id)onBuilt(value.result.batch_id);}});
  const running = prepare.isPending || busy(current?.status);
  useEffect(()=>{if(current?.status==="COMPLETED" && current.result?.batch_id)onBuilt(current.result.batch_id);},[current?.job_id,current?.status]);
  const error = prepare.error?.message ?? open.error?.message ?? current?.error_code ?? latest.error?.message ?? job.error?.message;
  const resultJob=current?.result?current:lastCompleted;
  const result = resultJob?.result;
  const ready = result?.modules.filter(m=>m.status==="READY_FOR_APPROVAL").length ?? 0;
  const progress = (busy(current?.status)?current?.progress_message:undefined)?.replace("Reading source day ","ตรวจข้อมูลวันที่ ")
    .replace("Resuming automatic preparation","กลับมาประมวลผลต่อ")
    .replace("Preparing M","เตรียม Module ").replace("Saving candidates and review evidence","บันทึก Candidate และกราฟสำหรับตรวจสอบ");
  return <>
    <section className="reference-review automatic-calibration" aria-labelledby="automatic-calibration-title">
      <header className="ref-header"><div><span className="ref-eyebrow">CALIBRATION · {machine}</span>
        <h2 id="automatic-calibration-title">เตรียม Profile อัตโนมัติ</h2>
        <p>ระบบเตรียม M1–M8 ให้ ตรวจกราฟหรือปรับช่วงข้อมูลเฉพาะโมดูลที่ต้องการ แล้วอนุมัติเป็นรายโมดูล</p></div>
        <label>ผู้ทบทวน<input aria-label="ผู้ทบทวน Calibration" value={reviewer} maxLength={100} onChange={e=>onReviewer(e.target.value)} placeholder="ชื่อหรือรหัสผู้ใช้งาน" /></label>
      </header>
      <div className="auto-actions"><button className="primary" disabled={running||reviewer.trim().length<2} onClick={()=>prepare.mutate()}>
        {running ? <RefreshCw size={16} className="spin"/>:<Play size={16}/>} {running ? "กำลังเตรียมข้อมูล" : result ? "เตรียม Candidate รอบใหม่" : "เตรียม Candidate ทั้ง 8 โมดูล"}</button>
        <button disabled={running} onClick={()=>{setManual(v=>!v);setOpened(null);}}>{manual ? "ปิดการปรับ Reference" : "เลือกช่วงข้อมูลเอง"}</button>
      </div>
      <p className="ref-help">Reference เริ่มต้น 28 วัน · Shadow 3 วันเต็มถัดจาก Reference · ไม่ใช้วันที่ข้อมูลยังไม่ครบวัน</p>
      <p className="ref-help">กราฟใช้ข้อมูลวันเต็มที่ตรวจต้นทางภายใน 1 ชั่วโมง · เมื่อสร้าง Candidate จากช่วงที่ปรับเอง ระบบจะตรวจข้อมูลต้นทางอีกครั้ง</p>
      <SourceContract/>
      {running && <div className="auto-progress" role="status"><Clock3 size={18}/><div><strong>{progress || "รอคิวประมวลผล"}</strong><p>งานอยู่บนเซิร์ฟเวอร์ ปิดหน้านี้แล้วกลับมาดูผลได้</p></div></div>}
      {error && <p className="ref-error" role="alert">{({QUEUE_BUSY:"คิวเต็ม กรุณาลองอีกครั้งเมื่อมีงานเสร็จ",CONTEXT_BUSY:"เครื่องนี้มีงานกำลังรัน รอให้งานเดิมเสร็จก่อน",NO_SOURCE_DATA:"ไม่พบข้อมูลเครื่องนี้",SOURCE_OR_DATABASE_UNAVAILABLE:"อ่านข้อมูลหรือบันทึกผลไม่ได้ กรุณาตรวจการเชื่อมต่อฐานข้อมูล",INTERRUPTED_OR_TIMED_OUT:"งานหยุดหรือหมดเวลา กดเตรียมรอบใหม่ได้"} as Record<string,string>)[error] ?? error}</p>}
      {result && <>
        {running&&<p className="ref-help">กำลังเตรียมรอบใหม่ · ด้านล่างเป็นผลรอบเดิม ยังเปิดหลักฐานเดิมได้</p>}
        <div className="auto-summary"><span><CheckCircle2 size={17}/><strong>{result.profiles}</strong> Candidate</span>
          <span><strong>{ready}</strong> พร้อมตรวจและอนุมัติ</span><span><strong>{8-result.profiles}</strong> รอข้อมูล</span></div>
        <p className="ref-help">ผลรอบ {new Date(resultJob!.updated_at).toLocaleString("th-TH",{timeZone:"Asia/Bangkok"})} · {result.selector_version?"Reference เลือกจากข้อมูลก่อนช่วงทดสอบเป็นรายโมดูล":`Reference รอบเดิม ${result.selection.reference_start.slice(0,10)} → ก่อน ${result.selection.reference_end.slice(0,10)}`} · Shadow {result.selection.shadow_start.slice(0,10)} → ก่อน {result.selection.shadow_end.slice(0,10)}</p>
        <div className="auto-modules">{result.modules.map(item=><article key={item.module} className={`auto-module ${item.status==="READY_FOR_APPROVAL"?"ready":item.candidate_created?"review":"waiting"}`}>
          <div className="auto-module-title"><strong>M{item.module}</strong><span>{labels[item.status]??item.status}</span></div>
          <p>Reference {item.summary.retained_reference_minutes.toLocaleString()} นาที · Shadow {item.summary.shadow_minutes.toLocaleString()} นาที</p>
          {item.reference_selection&&<small>Reference {item.reference_selection.start.slice(0,10)} → ก่อน {item.reference_selection.end.slice(0,10)}{item.reference_selection.changed?" · ระบบเลือกช่วงใหม่":""}</small>}
          {item.summary.quarantine_pct!==undefined&&<small>Reference คัดออก {item.summary.quarantine_pct.toFixed(2)}%{item.summary.shadow_flag_pct!=null?` · Shadow นอก baseline ${item.summary.shadow_flag_pct.toFixed(2)}%`:""}</small>}
          <ul>{orderedReasons(item.reason_codes.filter(r=>!r.endsWith("_UNVERIFIED"))).slice(0,2).map(reason=><li key={reason}>{approvalReason(reason)}</li>)}</ul>
          {item.reason_codes.some(r=>r.endsWith("_UNVERIFIED"))&&<small>ข้อมูลพื้นฐานรอยืนยัน · ดูรายการร่วมด้านบน การเปลี่ยนช่วงไม่แก้ข้อเหล่านี้</small>}
          <button disabled={open.isPending||reviewer.trim().length<2} onClick={()=>open.mutate(item)}>ดูหลักฐานและช่วงข้อมูล →</button>
          {item.candidate_created && result.batch_id && <button onClick={()=>{onModule(item.module);onBuilt(result.batch_id!);document.getElementById("calibration-approval")?.scrollIntoView({behavior:"smooth",block:"start"});}}>ตรวจ Candidate →</button>}
        </article>)}</div>
      </>}
    </section>
    {manual && <ReferenceReview key={`${machine}:${module}:${opened?.module===module?opened.job:"manual"}`} machine={machine} module={module}
      initialJobId={opened?.module===module?opened.job:undefined} reviewer={reviewer} onReviewer={onReviewer} onModule={onModule} onBuilt={onBuilt}/>} 
  </>;
}
