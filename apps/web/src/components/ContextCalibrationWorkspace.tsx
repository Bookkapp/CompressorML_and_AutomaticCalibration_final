import {useEffect,useMemo,useRef,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "../api";
import {SourceContract} from "./CalibrationEvidence";
import {ContextChart,type ChartRow} from "./ContextChart";
import {EventHistory} from "./EventHistory";
import {FleetReferencePanel} from "./FleetReferencePanel";
import {ContextCoveragePanel} from "./ContextCoveragePanel";
import {FleetTransitionReview} from "./FleetTransitionReview";
import {ContextValidationReport} from "./ContextValidationReport";
import {ContextFollowupProgress} from "./ContextFollowupProgress";
import type {ContextExclusion,ContextPoint,LedgerEvent} from "../context-types";
import "./context-calibration.css";

const categoryName:Record<string,string>={WITHIN_PROPOSED_STEADY:"อยู่ในกรอบสภาวะที่เสนอ",WITHIN_PROPOSED_TRANSITION:"อยู่ในกรอบ Transition ที่เสนอ",UNEXPECTED_TRANSITION:"การตอบสนองต่างจากรูปแบบอ้างอิง",NEW_STEADY_LEVEL:"ระดับนิ่งใหม่ที่ต้องทบทวน",UNSUPPORTED_TRANSITION:"Transition ยังมีตัวอย่างไม่พอ",STEADY_DEVIATION:"ค่าต่างจากสภาวะอ้างอิง",INSUFFICIENT_REFERENCE:"ข้อมูลอ้างอิงไม่พอ",UNSUPPORTED_CONTROL_CONTEXT:"สภาวะควบคุมยังไม่รองรับ",DATA_UNAVAILABLE:"คุณภาพข้อมูลไม่ผ่าน"};
const blockers:Record<string,string>={STATE_CONTRACT_UNVERIFIED:"ยืนยันเวอร์ชันกติกาสถานะ",CONTROLLER_CODEBOOK_UNVERIFIED:"ยืนยันเวอร์ชันคำจำกัดความรหัส Controller",SERVICE_EPOCH_UNVERIFIED:"ยืนยันช่วงประวัติการซ่อมที่ใช้สร้าง Reference",PRESSURE_BASIS_UNVERIFIED:"ระบุว่าแรงดัน psi เป็น psig หรือ psia",CONTRACT_CHANGED_PREPARE_AGAIN:"ข้อมูลพื้นฐานเปลี่ยน ต้องเตรียม Profile ใหม่",REFERENCE_ACCEPTANCE_REQUIRED:"บันทึกสภาวะอ้างอิงที่ทบทวน",ENGINEER_EVIDENCE_REQUIRED:"ระบุหลักฐานตรวจรับจาก Engineer",PROSPECTIVE_VALIDATION_REQUIRED:"ตรวจข้อมูลใหม่อย่างน้อย 3 วันหลังทบทวน Reference",VALIDATION_COVERAGE_INSUFFICIENT:"ข้อมูลใหม่ที่ประเมินได้ยังไม่ครบขั้นต่ำ",VALIDATION_UNSUPPORTED_PERIODS_REQUIRE_REVIEW:"ข้อมูลใหม่ยังมีสภาวะที่ Reference ไม่รองรับ",VALIDATION_FLAG_RATE_EXCEEDED:"ข้อมูลใหม่มีความเบี่ยงเบนเกินเกณฑ์",MODEL_OR_SOURCE_VERSION_CHANGED:"รุ่นโมเดลหรือแหล่งข้อมูลเปลี่ยน ต้องเตรียมใหม่"};
const friendly=(v?:string)=>v?.includes("FUTURE_SOURCE_REQUIRED")?"ยังไม่มีข้อมูลใหม่ครบ 3 วันหลังทบทวน Reference จึงยังตรวจเพื่อเปิด Active ไม่ได้":v?.includes("RAW_PERIOD_MAX_30_MINUTES")?"เลือกเวลา Raw ให้สิ้นสุดหลังเริ่ม และไม่เกิน 30 นาที":v?.includes("DETAIL_DAY_OUTSIDE_REFERENCE")?"เลือกเวลา Raw ภายในช่วง Reference หรือ Shadow ของรอบนี้":v?.includes("EXCLUDE_REFERENCE_ONLY")?"เลือกช่วงยกเว้นเฉพาะ Reference ช่วง Shadow ใช้ทดสอบและไม่ตัดออก":v?.includes("ANOTHER_TAB")?"มีการบันทึกจากแท็บอื่นแล้ว กดอัปเดตเพื่อใช้เวอร์ชันล่าสุด":v;
const stamp=(v:string)=>v.length===16?v+":00":v;
Object.assign(categoryName,{STATE_GATE_EXCLUDED:"ไม่ได้ประเมิน · สภาวะอยู่นอกขอบเขต Profile"});
Object.assign(categoryName,{MOCK_DATA:"ข้อมูล Normal จำลอง · ไม่ใช้ตรวจรับ Active"});
Object.assign(blockers,{MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE:"ข้อมูลจำลองไม่ใช้เป็นหลักฐานเปิด Active ของเครื่องจริง"});
Object.assign(blockers,{INCLUDED_STATE_REFERENCE_REQUIRED:"เลือก Reference ที่รับรองอย่างน้อยหนึ่งสภาวะสำหรับ SV ทุกสถานะที่ต้องการประเมิน",EVALUATION_SCOPE_INVALID:"ขอบเขตสภาวะของ Profile ไม่ถูกต้อง",VALIDATION_SCOPE_CHANGED:"ขอบเขตสภาวะเปลี่ยน ต้องตรวจข้อมูลใหม่ด้วยรุ่นที่ตรึงนี้"});
const contextLabel=(v:string)=>v.replace("RUN_MODULE_ON_BUSY0_SV_","Compressor ทำงาน · Busy 0 · SV ");
const fields=["hp1","lp1","hp2","lp2","dp1","dp2","temphi","templo"];

export function ContextCalibration({machine,module,reviewer,onReviewer,onModule}:{machine:string;module:number;reviewer:string;onReviewer:(v:string)=>void;onModule:(v:number)=>void}){
  const client=useQueryClient();
  const [jobId,setJobId]=useState<string|null>(null),[historyDays,setHistoryDays]=useState(28),[day,setDay]=useState("");
  const [kind,setKind]=useState<"minute"|"raw">("minute"),[tab,setTab]=useState<"evidence"|"events">("evidence");
  const [rawStart,setRawStart]=useState(""),[rawEnd,setRawEnd]=useState(""),[slice,setSlice]=useState<[string,string]|null>(null);
  const [pressure,setPressure]=useState("hp2"),[temperature,setTemperature]=useState("temphi");
  const [refStart,setRefStart]=useState(""),[splitDay,setSplitDay]=useState(""),[endDay,setEndDay]=useState("");
  const [exclusions,setExclusions]=useState<ContextExclusion[]>([]),[excludeStart,setExcludeStart]=useState(""),[excludeEnd,setExcludeEnd]=useState(""),[excludeReason,setExcludeReason]=useState("");
  const [acceptedRegimes,setAcceptedRegimes]=useState<string[]>([]),[acceptedTemplates,setAcceptedTemplates]=useState<string[]>([]),[note,setNote]=useState(""),[engineerRef,setEngineerRef]=useState("");
  const [localError,setLocalError]=useState("");
  const [followupView,setFollowupView]=useState<{job:string;start:string;end:string}|null>(null);
  const [includedSV,setIncludedSV]=useState<("OFF"|"ON")[]>(["OFF","ON"]),[scopeReason,setScopeReason]=useState("");
  const [hydratedIdentity,setHydratedIdentity]=useState("");
  const investigation=useRef<LedgerEvent|null>(null);
  const chartAnchor=useRef<HTMLDivElement|null>(null);
  const enabled=reviewer.trim().length>=2;
  useEffect(()=>{try{if(!reviewer)onReviewer(localStorage.getItem("ht9046mx-calibration-reviewer")??"");}catch{}},[]);
  useEffect(()=>{try{if(enabled)localStorage.setItem("ht9046mx-calibration-reviewer",reviewer);}catch{}},[reviewer]);
  const latest=useQuery({queryKey:["context-latest",machine,reviewer],queryFn:()=>api.latestContext(machine,reviewer.trim()),enabled,retry:false,refetchOnWindowFocus:false,refetchInterval:q=>q.state.data?.status?.startsWith("PREVIEW_")?3000:false});
  const completed=useQuery({queryKey:["context-completed",machine,reviewer],queryFn:()=>api.latestContext(machine,reviewer.trim(),true),enabled,refetchOnWindowFocus:false});
  const job=useQuery({queryKey:["context-job",jobId,reviewer],queryFn:()=>api.contextJob(jobId!,reviewer.trim()),enabled:!!jobId&&enabled,retry:1,refetchOnWindowFocus:false,refetchInterval:q=>q.state.data?.status?.startsWith("PREVIEW_")?3000:false});
  const current=jobId?job.data:latest.data;
  const saved=current?.result?current:completed.data;
  useEffect(()=>{if(current?.status==="COMPLETED")client.invalidateQueries({queryKey:["context-completed",machine,reviewer]});},[current?.job_id,current?.status]);
  const selected=saved?.result?.modules.find(m=>m.module===module);
  const review=useQuery({queryKey:["context-review",selected?.profile_id,reviewer],queryFn:()=>api.contextReview(selected!.profile_id,reviewer.trim()),enabled:!!selected&&enabled,refetchOnWindowFocus:false,retry:false});
  const effective=review.data?.reviewed_profile_id??selected?.profile_id;
  const fleetTransitions=useQuery({queryKey:["fleet-transitions",selected?.profile_id],queryFn:()=>api.fleetTransitions(selected!.profile_id),enabled:!!selected,staleTime:300000,refetchOnWindowFocus:false,retry:false});
  const model=useQuery({queryKey:["context-model",effective],queryFn:()=>api.contextProfile(effective!),enabled:!!effective,staleTime:60_000,refetchOnWindowFocus:false});
  const draftKey=selected?`context-draft:${selected.profile_id}:${reviewer}`:"";
  const draftIdentity=effective?`${draftKey}:${effective}`:"";
  const draftReady=review.isSuccess&&model.data?.profile_id===effective&&hydratedIdentity===draftIdentity;
  function inspect(at:string,min:string,max:string,keepFollowup=false){
    if(!keepFollowup)setFollowupView(null);
    const x=Date.parse(at+"Z"),lo=Math.max(Date.parse(min+"Z"),Math.floor(x/60000)*60000-10*60000),hi=Math.min(Date.parse(max+"Z"),Math.floor(x/60000)*60000+10*60000);
    if(hi<=lo){setLocalError("เหตุการณ์อยู่นอกช่วงข้อมูลของ Profile นี้ ให้เปิดดูผ่าน Event History");return;}
    const from=new Date(lo).toISOString().slice(0,19),to=new Date(hi).toISOString().slice(0,19);
    setDay(at.slice(0,10));setRawStart(from.slice(0,16));setRawEnd(to.slice(0,16));setSlice([from,to]);setKind("raw");setTab("evidence");chartAnchor.current?.scrollIntoView({behavior:"smooth",block:"start"});
  }
  useEffect(()=>{
    if(!review.isSuccess||!model.data||model.data.profile_id!==effective)return;
    const m=model.data;
    setDay(m.shadow_start.slice(0,10));setKind("minute");setSlice(null);setLocalError("");setFollowupView(null);
    setRefStart(m.reference_start.slice(0,10));setSplitDay(m.shadow_start.slice(0,10));setEndDay(m.shadow_end.slice(0,10));
    setExclusions(m.exclusions??[]);setAcceptedRegimes(m.reference_review?.accepted_regime_ids??[]);setAcceptedTemplates(m.reference_review?.accepted_template_ids??[]);setNote(m.reference_review?.note??"");setEngineerRef(m.reference_review?.engineer_evidence_ref??"");
    setIncludedSV(m.reference_review?.evaluation_scope?.included_sv_states??["OFF","ON"]);setScopeReason(m.reference_review?.evaluation_scope?.excluded_reason??"");
    try{const d=JSON.parse(localStorage.getItem(draftKey)??"null");if(d&&d.model===m.profile_id){setExclusions(d.exclusions??[]);setNote(d.note??"");setEngineerRef(d.engineerRef??"");setAcceptedRegimes(d.acceptedRegimes??[]);setAcceptedTemplates(d.acceptedTemplates??[]);setIncludedSV(d.includedSV??m.reference_review?.evaluation_scope?.included_sv_states??["OFF","ON"]);setScopeReason(d.scopeReason??m.reference_review?.evaluation_scope?.excluded_reason??"");}}catch{}
    setHydratedIdentity(draftIdentity);
    const pending=investigation.current;
    if(pending&&(!pending.module||pending.module===module)){investigation.current=null;inspect(pending.occurred_at,m.reference_start,m.shadow_end);}
  },[model.data?.profile_id,reviewer,review.isSuccess,draftIdentity]);
  useEffect(()=>{if(!draftReady||!draftKey||!model.data)return;try{localStorage.setItem(draftKey,JSON.stringify({model:model.data.profile_id,exclusions,note,engineerRef,acceptedRegimes,acceptedTemplates,includedSV,scopeReason}));}catch{}},[draftReady,draftKey,model.data?.profile_id,exclusions,note,engineerRef,acceptedRegimes,acceptedTemplates,includedSV,scopeReason]);
  const points=useQuery({queryKey:["context-day",effective,day,followupView?.job],queryFn:()=>followupView?api.followupDay(effective!,followupView.job,day):api.contextDay(effective!,day),enabled:!!effective&&!!day,staleTime:60_000,refetchOnWindowFocus:false,retry:false});
  const raw=useQuery({queryKey:["context-raw",effective,slice,followupView?.job],queryFn:()=>followupView?api.followupRaw(effective!,followupView.job,slice![0],slice![1]):api.contextRaw(effective!,slice![0],slice![1]),enabled:!!effective&&!!slice,staleTime:60_000,refetchOnWindowFocus:false,retry:false});
  const active=useQuery({queryKey:["context-active",machine],queryFn:()=>api.contextActive(machine),staleTime:30000});
  const activeModule=active.data?.find(a=>a.module===module);
  const previous=useQuery({queryKey:["context-model",activeModule?.previous_profile_id],queryFn:()=>api.contextProfile(activeModule!.previous_profile_id!),enabled:!!activeModule?.previous_profile_id,staleTime:60_000});
  const previousReady=useQuery({queryKey:["context-readiness",activeModule?.previous_profile_id],queryFn:()=>api.contextReadiness(activeModule!.previous_profile_id!),enabled:!!activeModule?.previous_profile_id});
  const readiness=useQuery({queryKey:["context-readiness",effective],queryFn:()=>api.contextReadiness(effective!),enabled:!!effective,refetchOnWindowFocus:false});
  const selectionDirty=!!model.data&&(JSON.stringify(exclusions)!==JSON.stringify(model.data.exclusions??[])||refStart!==model.data.reference_start.slice(0,10)||splitDay!==model.data.shadow_start.slice(0,10)||endDay!==model.data.shadow_end.slice(0,10));
  const same=(a:string[],b:string[])=>JSON.stringify([...a].sort())===JSON.stringify([...b].sort());
  const reviewDirty=!!model.data&&(!model.data.reference_review?.evaluation_scope||!same(acceptedRegimes,model.data.reference_review.accepted_regime_ids)||!same(acceptedTemplates,model.data.reference_review.accepted_template_ids)||!same(includedSV,model.data.reference_review.evaluation_scope.included_sv_states)||scopeReason.trim()!==model.data.reference_review.evaluation_scope.excluded_reason||engineerRef.trim()!==model.data.reference_review.engineer_evidence_ref);
  const scopeValid=includedSV.length>0&&(includedSV.length===2||scopeReason.trim().length>=8);
  function chooseSV(sv:"OFF"|"ON",checked:boolean){
    const next=checked?[...includedSV,sv]:includedSV.filter(v=>v!==sv);setIncludedSV(next);
    if(!checked&&model.data){setAcceptedRegimes(acceptedRegimes.filter(id=>!model.data!.regimes.some(r=>r.regime_id===id&&r.context.endsWith(`_SV_${sv}`))));setAcceptedTemplates(acceptedTemplates.filter(id=>![...model.data!.transition_templates,...(fleetTransitions.data?.templates??[])].some(t=>t.template_id===id&&t.key.endsWith(`_SV_${sv}`))));}
  }
  const prepare=useMutation({mutationFn:(payload:Record<string,unknown>)=>api.prepareContext(reviewer.trim(),{idempotency_key:crypto.randomUUID(),machine_number:machine,history_days:historyDays,...payload}),onSuccess:j=>{setJobId(j.job_id);setLocalError("");}});
  const running=prepare.isPending||!!current?.status?.startsWith("PREVIEW_");
  const saveReview=useMutation({mutationFn:()=>{const fleetIDs=acceptedTemplates.filter(id=>fleetTransitions.data?.templates.some(t=>t.template_id===id));return api.saveContextReview(selected!.profile_id,reviewer.trim(),{expected_revision:review.data?.revision??0,source_digest:model.data!.source_digest,accepted_regime_ids:acceptedRegimes,accepted_template_ids:acceptedTemplates.filter(id=>!fleetIDs.includes(id)),accepted_fleet_template_ids:fleetIDs,fleet_bundle_id:fleetIDs.length?fleetTransitions.data?.bundle_id:null,note,engineer_evidence_ref:engineerRef,included_sv_states:includedSV,excluded_sv_reason:scopeReason});},onSuccess:()=>{client.invalidateQueries({queryKey:["context-review",selected?.profile_id,reviewer]});client.invalidateQueries({queryKey:["context-coverage"]});setLocalError("");}});
  const approve=useMutation({mutationFn:()=>api.approveContext(effective!,reviewer.trim(),{expected_revision:active.data?.find(a=>a.module===module)?.revision??0,source_digest:model.data!.source_digest,note}),onSuccess:()=>client.invalidateQueries({queryKey:["context-active",machine]})});
  const rollback=useMutation({mutationFn:()=>api.rollbackContext(machine,module,reviewer.trim(),{expected_revision:activeModule!.revision,source_digest:previous.data!.source_digest,note}),onSuccess:()=>client.invalidateQueries({queryKey:["context-active",machine]})});
  function openEvent(e:LedgerEvent){if(e.module&&e.module!==module){investigation.current=e;onModule(e.module);}else if(model.data)inspect(e.occurred_at,model.data.reference_start,model.data.shadow_end);}
  function openFollowup(job:string,nextDay:string,start:string,end:string,at?:string){setFollowupView({job,start,end});setDay(nextDay);setSlice(null);setKind("minute");setTab("evidence");setLocalError("");if(at)inspect(at,start,end,true);else chartAnchor.current?.scrollIntoView({behavior:"smooth",block:"start"});}
  const evidenceStart=followupView?.start??model.data?.reference_start??"";
  const evidenceEnd=followupView?.end??model.data?.shadow_end??"";
  const followupDays=followupView?Array.from({length:Math.min(4,Math.ceil((Date.parse(followupView.end+"Z")-Date.parse(followupView.start.slice(0,10)+"T00:00:00Z"))/86400000))},(_,i)=>new Date(Date.parse(followupView.start.slice(0,10)+"T00:00:00Z")+i*86400000).toISOString().slice(0,10)):[];
  function addExclusion(){
    if(!model.data)return;
    const from=stamp(excludeStart),to=stamp(excludeEnd);
    if(!from||!to||from>=to||from<model.data.reference_start||to>model.data.shadow_start||excludeReason.trim().length<8){setLocalError("เลือกช่วงภายใน Reference และเขียนเหตุผลอย่างน้อย 8 ตัวอักษร");return;}
    setExclusions([...exclusions,{module,start:from,end:to,reason:excludeReason.trim()}]);setLocalError("");
  }
  function loadRaw(){
    const next:[string,string]=[stamp(rawStart),stamp(rawEnd)];
    const minutes=(Date.parse(next[1]+"Z")-Date.parse(next[0]+"Z"))/60000;
    if(!Number.isFinite(minutes)||minutes<=0||minutes>30){setLocalError("เลือกเวลา Raw ให้สิ้นสุดหลังเริ่ม และไม่เกิน 30 นาที");return;}
    setLocalError("");
    if(slice&&slice[0]===next[0]&&slice[1]===next[1])raw.refetch();else setSlice(next);
  }
  const byMinute=useMemo(()=>new Map((points.data?.chart??[]).map(p=>[p.time.slice(0,16),p])),[points.data]);
  function bands(p?:ContextPoint){const e=p?.transition_envelope??p?.steady_envelope;const range=(key:string)=>{const i=fields.indexOf(key);return e?[e.center[i]-e.radius[i],e.center[i]+e.radius[i]]:null;};return {pressure_range:range(pressure),temperature_range:range(temperature),transition_event_id:p?.transition_event_id??null};}
  const rows:ChartRow[]=useMemo(()=>kind==="raw"?(raw.data?.chart??[]).map(p=>{const t=String(p.time);const numeric=p.duplicate_second?Object.fromEntries([...fields,"valve"].map(k=>[k,null])):p;return {...numeric,time:t,...bands(byMinute.get(t.slice(0,16)))};}):(points.data?.chart??[]).map(p=>({time:p.time,...(p.features??{}),valve:p.control.valve_mean,category:p.category,...bands(p)})),[kind,raw.data,points.data,byMinute,pressure,temperature]);
  const boundaries=useMemo(()=>points.data?.chart.filter((p,i,all)=>i===0||p.category!==all[i-1].category)??[],[points.data]);
  const rawStates=useMemo(()=>raw.data?.chart.filter((p,i,all)=>!i||["global_state","module_state","busy","sv"].some(k=>p[k]!==all[i-1][k]))??[],[raw.data]);
  const error=friendly(localError||prepare.error?.message||saveReview.error?.message||approve.error?.message||rollback.error?.message||latest.error?.message||job.error?.message||current?.error_code||model.error?.message||points.error?.message||raw.error?.message||review.error?.message);
  return <section className="context-section">
    <header className="context-heading"><div><h2>Calibration ตามสภาวะการทำงาน</h2><p>{machine} · Steady หลายสภาวะ + Transition · ประวัติเหตุการณ์ร่วมกัน</p></div><label>ผู้ทบทวน<input value={reviewer} onChange={e=>onReviewer(e.target.value)} placeholder="ชื่อหรือรหัสผู้ใช้งาน" maxLength={100}/></label></header>
    <div className="context-filters"><label>Reference ย้อนหลัง<select value={historyDays} onChange={e=>setHistoryDays(Number(e.target.value))}><option value={28}>28 วัน</option><option value={60}>60 วัน</option><option value={90}>90 วัน</option></select></label><button className="primary" disabled={running||!enabled} onClick={()=>prepare.mutate({})}>{running?"กำลังเตรียมข้อมูล":"เตรียม Profile และ Event ทั้ง 8 โมดูล"}</button><button disabled={!enabled} onClick={()=>{setLocalError("");saveReview.reset();approve.reset();rollback.reset();latest.refetch();jobId&&job.refetch();completed.refetch();selected&&review.refetch();effective&&readiness.refetch();}}>อัปเดตสถานะ</button></div>
    <p className="context-help">อ่านข้อมูลแต่ละวันร่วมกันทุกโมดูล · การปรับ Valve ไม่ถือเป็น Anomaly เอง · สภาวะใหม่ต้องมีหลักฐานและทบทวนก่อนรับเป็น Reference</p>
    <SourceContract/>{error&&<p className="form-error" role="alert">{error}</p>}
    <FleetReferencePanel machine={machine} module={module} onModule={onModule}/>
    {running&&<div className="context-progress" role="status">{current?.progress_message?.replace("Reading source day ","ตรวจข้อมูลวันที่ ")??"กำลังเริ่มงาน"}<p>ปิดหน้านี้แล้วกลับมาติดตามงานเดิมได้ · กราฟของรอบที่บันทึกไว้ยังดูได้</p></div>}
    {saved?.result&&<>
      <ContextCoveragePanel jobId={saved.job_id} reviewer={reviewer} module={module} onModule={onModule}/>
      <p className="context-help">Reference {saved.result.selection.reference_start.slice(0,10)} — ก่อน {(saved.result.selection.reference_end??saved.result.selection.shadow_start).slice(0,10)} · Shadow ถึงก่อน {saved.result.selection.shadow_end.slice(0,10)}</p>
      <div className="context-modules">{saved.result.modules.map(m=><button key={m.module} className={m.module===module?"active":""} aria-pressed={m.module===module} onClick={()=>onModule(m.module)}><strong>M{m.module}</strong><small>{m.supported_regimes} สภาวะ · {m.supported_templates} Transition</small></button>)}</div>
      {selected&&<div className="context-badges">{Object.entries(selected.shadow_categories).map(([name,n])=><span key={name}>{categoryName[name]??name}<br/><strong>{n.toLocaleString()} นาที</strong></span>)}</div>}
      {model.data?.reference_review&&<p className="context-help">จำนวนด้านบนเป็นผลของ Candidate ตอนเตรียม · กราฟด้านล่างใช้สภาวะที่บันทึกใน Reference เวอร์ชันที่กำลังเปิด</p>}
      <div className="context-actions"><button className={tab==="evidence"?"primary":""} onClick={()=>setTab("evidence")}>กราฟและสภาวะอ้างอิง</button><button className={tab==="events"?"primary":""} onClick={()=>setTab("events")}>Event Timeline</button></div>
      {tab==="events"?<EventHistory machine={machine} module={module} onInvestigate={openEvent}/>:<>
        <div className="context-filters"><label>วันที่<select value={followupView?"followup:"+day:day} onChange={e=>{const isFollowup=e.target.value.startsWith("followup:");setDay(e.target.value.replace("followup:",""));if(!isFollowup)setFollowupView(null);setKind("minute");setSlice(null);}}>{Object.keys(model.data?.day_receipts??{}).map(d=><option key={d} value={d}>{d}{d>=(model.data?.shadow_start.slice(0,10)??"")?" · Shadow":" · Reference"}</option>)}{followupDays.map(d=><option key={"followup:"+d} value={"followup:"+d}>{d} · ตรวจระหว่างรอ</option>)}</select></label><button onClick={()=>setKind("minute")}>ข้อมูลรายนาที</button><button onClick={()=>setKind("raw")}>Raw รายวินาที</button></div>
        {followupView&&<p className="context-progress">ข้อมูลใหม่ที่ตรวจระหว่างรอ · Reference {effective?.slice(0,12)} · ผลรอบนี้ยังไม่ใช้อนุมัติ Active</p>}
        {kind==="raw"&&<div className="context-filters"><label>เริ่ม Raw<input type="datetime-local" value={rawStart} onChange={e=>setRawStart(e.target.value)}/></label><label>สิ้นสุด Raw<input type="datetime-local" value={rawEnd} onChange={e=>setRawEnd(e.target.value)}/></label><button disabled={!rawStart||!rawEnd||raw.isFetching} onClick={loadRaw}>ดู Raw ช่วงนี้</button><span className="context-help">ไม่เกิน 30 นาที · เวลาเครื่อง · วินาทีซ้ำไม่ลากเส้นทับกัน</span></div>}
        <div ref={chartAnchor} className="context-grid" aria-busy={kind==="raw"?raw.isFetching:points.isFetching}>
          <article className="context-chart-card"><header><h3>Pressure</h3><label>กรอบ Pressure<select value={pressure} onChange={e=>setPressure(e.target.value)}>{["hp1","lp1","hp2","lp2"].map(k=><option key={k}>{k}</option>)}</select></label></header><ContextChart rows={rows} kind="pressure" unit={points.data?.pressure_unit??"psi"} focus={pressure}/></article>
          <article className="context-chart-card"><header><h3>Temperature</h3><label>กรอบ Temperature<select value={temperature} onChange={e=>setTemperature(e.target.value)}><option value="temphi">Temp High</option><option value="templo">Temp Low</option></select></label></header><ContextChart rows={rows} kind="temperature" focus={temperature}/></article>
          <article className="context-chart-card"><h3>Valve command</h3><ContextChart rows={rows} kind="valve"/></article>
          <article className="context-chart-card"><h3>ช่วงที่ควรตรวจ</h3><p className="context-help">{kind==="raw"?`${raw.data?.observed_rows??0} แถว · วินาทีซ้ำ ${raw.data?.duplicate_rows??0}`:`${points.data?.chart.length??0} นาที · ${points.data?.source_timezone??"เวลาเครื่อง"}`} · ไม่เติมข้อมูลขาด</p><div className="context-table-wrap context-boundaries"><table className="context-table"><thead><tr><th>เวลา</th><th>ผลประเมิน</th><th>หลักฐาน</th></tr></thead><tbody>{boundaries.map(p=><tr key={p.time}><td>{p.time.slice(11,16)}</td><td>{categoryName[p.category]??p.category}{p.main_evidence&&<small>{p.main_evidence.feature}: {p.main_evidence.value.toFixed(2)} · กรอบ {p.main_evidence.lower.toFixed(2)}–{p.main_evidence.upper.toFixed(2)}</small>}<small>{p.state_gate_reason||p.quality_reason|| (p.transition_elapsed_minutes!==null?`หลังเหตุการณ์ ${p.transition_elapsed_minutes} นาที`:p.stable?"ระดับนิ่ง · ตรวจสภาวะที่รับรอง":"ตรวจกรอบแรงดันและอุณหภูมิ")}</small></td><td><button onClick={()=>model.data&&inspect(p.time,evidenceStart,evidenceEnd,!!followupView)}>ดู Raw</button></td></tr>)}</tbody></table></div></article>
        </div>
        <p className="context-help">พื้นที่แรเงาเป็นกรอบที่เสนอของค่าที่เลือก · เส้นประคือเหตุการณ์ควบคุมที่ใช้ประเมิน Transition · กรอบนี้ยังต้องทบทวน</p>
        {kind==="raw"&&rawStates.length>0&&<details className="context-review-card"><summary>สถานะควบคุมใน Raw · {rawStates.length} ช่วง</summary><div className="context-table-wrap"><table className="context-table"><thead><tr><th>เวลา</th><th>Compressor</th><th>Module</th><th>Busy</th><th>SV</th></tr></thead><tbody>{rawStates.map((p,i)=><tr key={i}><td>{String(p.time).slice(11)}</td>{["global_state","module_state","busy","sv"].map(k=><td key={k}>{String(p[k]??"—")}</td>)}</tr>)}</tbody></table></div></details>}
        {model.data&&<section className="context-review-card" aria-busy={!draftReady}><fieldset className="context-review-fields" disabled={!draftReady}>
          <h3>1. ตรวจช่วง Reference</h3><div className="context-filters"><label>Reference เริ่ม<input type="date" value={refStart} onChange={e=>setRefStart(e.target.value)}/></label><label>Shadow เริ่ม<input type="date" value={splitDay} onChange={e=>setSplitDay(e.target.value)}/></label><label>Shadow สิ้นสุด (ไม่รวมวัน)<input type="date" value={endDay} onChange={e=>setEndDay(e.target.value)}/></label></div>
          <details><summary>ยกเว้นช่วงที่ไม่ใช้สร้าง Reference</summary><p className="context-help">ยกเว้นเฉพาะโมดูลนี้ · Raw และ Event อยู่ครบ · กราฟเดิมยังแสดงจนเตรียมรอบใหม่เสร็จ</p><div className="context-filters"><label>เริ่มยกเว้น<input type="datetime-local" value={excludeStart} min={model.data.reference_start.slice(0,16)} max={model.data.shadow_start.slice(0,16)} onChange={e=>setExcludeStart(e.target.value)}/></label><label>สิ้นสุดยกเว้น<input type="datetime-local" value={excludeEnd} onChange={e=>setExcludeEnd(e.target.value)}/></label><label>เหตุผลยกเว้น<input value={excludeReason} onChange={e=>setExcludeReason(e.target.value)} maxLength={1000}/></label><button disabled={exclusions.length>=50} onClick={addExclusion}>เพิ่มช่วงยกเว้น</button></div><ul>{exclusions.map((e,i)=><li key={i}>{e.start.replace("T"," ")} → {e.end.replace("T"," ")} · {e.reason} <button onClick={()=>setExclusions(exclusions.filter((_,n)=>n!==i))}>ใช้ช่วงนี้อีกครั้ง</button></li>)}</ul></details>
          {selectionDirty&&<p className="context-progress">ช่วงที่เลือกเปลี่ยนแล้ว กดเตรียมรอบใหม่ก่อนบันทึกผลทบทวน · กราฟข้างบนเป็นรอบที่บันทึกไว้</p>}
          <button disabled={!selectionDirty||running} onClick={()=>prepare.mutate({parent_profile_id:effective,reference_start:refStart,shadow_start:splitDay,shadow_end:endDay,exclusions})}>เตรียมใหม่จากช่วงที่เลือก</button>
          <h3>2. กำหนดขอบเขตและเลือก Reference ที่ทบทวน</h3>
          <fieldset className="context-scope"><legend>สภาวะที่จะใช้โมเดลประเมิน · M{module}</legend>
            <p className="context-help">รับรองเฉพาะสภาวะที่มี Reference ได้ ไม่ต้องรอครบทุก State · ต้องเลือกอย่างน้อยหนึ่งสภาวะ</p>
            {(["OFF","ON"] as const).map(sv=><label className="context-check" key={sv}><input aria-label={`ใช้โมเดลประเมิน SV ${sv}`} type="checkbox" checked={includedSV.includes(sv)} disabled={selectionDirty||(includedSV.length===1&&includedSV.includes(sv))} onChange={e=>chooseSV(sv,e.target.checked)}/><span><strong>ใช้โมเดลประเมิน SV {sv}</strong><small>{model.data!.regimes.filter(r=>r.coverage_supported&&r.context.endsWith(`_SV_${sv}`)).length} สภาวะมีข้อมูลถึงขั้นต่ำ · ยังต้องทบทวน</small></span></label>)}
            {includedSV.length<2&&<><label>เหตุผลที่งดประเมินสภาวะที่ไม่เลือก<input aria-label="เหตุผลงดประเมิน SV" value={scopeReason} onChange={e=>setScopeReason(e.target.value)} maxLength={1000} placeholder="เช่น ยังไม่มี Reference ของ SV ON ที่เพียงพอ"/></label><p className="context-help">State Gate จะงดใช้โมเดลในสภาวะนี้ และบันทึกว่าไม่ได้ประเมิน · Raw และ Event อยู่ครบ · เมื่อกลับสภาวะที่รองรับ จะตรวจค่าทันทีโดยไม่เพิ่มเวลาตัดทิ้ง</p></>}
            {!scopeValid&&<p className="form-error">ระบุเหตุผลงดประเมินอย่างน้อย 8 ตัวอักษร</p>}
          </fieldset>
          {reviewDirty&&model.data.reference_review&&<p className="context-progress">ผลทบทวนหรือขอบเขตเปลี่ยนแล้ว กราฟยังเป็นรุ่นที่บันทึกไว้ · บันทึกผลทบทวนก่อนตรวจข้อมูลใหม่หรือเปิด Active</p>}
          {!model.data.regimes.length&&<p>ข้อมูลยังไม่พอสำหรับเสนอ Baseline ของโมดูลนี้</p>}
          {model.data.regimes.map(r=><article className="context-regime" key={r.regime_id}><label className="context-check"><input type="checkbox" checked={acceptedRegimes.includes(r.regime_id)} disabled={!r.coverage_supported||selectionDirty||!includedSV.some(sv=>r.context.endsWith(`_SV_${sv}`))} onChange={e=>setAcceptedRegimes(e.target.checked?[...acceptedRegimes,r.regime_id]:acceptedRegimes.filter(id=>id!==r.regime_id))}/><strong>รวมสภาวะนี้ใน Reference · {contextLabel(r.context)}</strong></label><p className="context-help">{r.days} วัน · {r.minutes.toLocaleString()} นาที · {r.coverage_supported?"มีความครอบคลุมสำหรับทบทวน":"ต้องมีอย่างน้อย 7 วัน และ 200 นาที"}</p><dl>{[["Hp2",r.center[2],"psi"],["Lp2",r.center[3],"psi"],["Temp High",r.center[6],"°C"],["Temp Low",r.center[7],"°C"]].map(([k,v,u])=><div key={String(k)}><dt>{k}</dt><dd>{Number(v).toFixed(2)} {u}</dd></div>)}</dl><button onClick={()=>{setFollowupView(null);setSlice(null);setDay(r.start.slice(0,10));setKind("minute");}}>ดูตัวอย่างสภาวะนี้</button></article>)}
          <h3>ตัวอย่าง Transition อ้างอิง</h3>{!model.data.transition_templates.length&&<p className="context-help">ไม่มีตัวอย่าง Transition ที่วิเคราะห์ได้ใน Reference · เหตุการณ์ต้นฉบับยังดูได้ใน Event Timeline</p>}
          {model.data.transition_templates.filter(t=>!t.fleet_assistance).map(t=><article className="context-regime" key={t.template_id}><label className="context-check"><input type="checkbox" disabled={!t.coverage_supported||selectionDirty||!includedSV.some(sv=>t.key.endsWith(`_SV_${sv}`))} checked={acceptedTemplates.includes(t.template_id)} onChange={e=>setAcceptedTemplates(e.target.checked?[...acceptedTemplates,t.template_id]:acceptedTemplates.filter(id=>id!==t.template_id))}/><strong>{t.key.split("|")[0].replaceAll("_"," ")}</strong></label><p className="context-help">{t.events} รอบ · {t.days} วัน · {t.coverage_supported?"ต้องทบทวนร่วมกับสภาวะก่อนเหตุการณ์":"ตัวอย่างหรือสภาวะเริ่มต้นยังไม่พอ"}</p><details><summary>ดูรอบที่ใช้เสนอรูปแบบ</summary>{t.examples.map(e=><button key={e.event_id} onClick={()=>inspect(e.at,model.data!.reference_start,model.data!.shadow_end)}>{e.at.replace("T"," ")} · {e.observed_minutes} นาที</button>)}</details></article>)}
          <FleetTransitionReview data={fleetTransitions.data} onRefresh={()=>fleetTransitions.refetch()} error={fleetTransitions.error} accepted={acceptedTemplates} origins={acceptedRegimes} includedSV={includedSV} disabled={selectionDirty||!draftReady} onChange={ids=>{const keys=new Set((fleetTransitions.data?.templates??[]).filter(t=>ids.includes(t.template_id)).map(t=>t.key));setAcceptedTemplates(ids.filter(id=>!model.data!.transition_templates.some(t=>t.template_id===id&&!t.fleet_assistance&&keys.has(t.key))));}}/>
          <label>บันทึกผลทบทวน<textarea className="context-note" value={note} onChange={e=>setNote(e.target.value)} placeholder="อธิบายสภาวะที่ยอมรับหรือยังต้องตรวจ อย่างน้อย 8 ตัวอักษร" maxLength={2000}/></label>
          <label>หลักฐานตรวจรับจาก Engineer (สำหรับ Active)<input className="context-note" value={engineerRef} onChange={e=>setEngineerRef(e.target.value)} placeholder="อ้างอิงผลตรวจจริง / Service log / Case ที่ยืนยันแล้ว" maxLength={1000}/></label>
          <div className="context-actions"><button disabled={!enabled||!scopeValid||note.trim().length<8||selectionDirty||running||saveReview.isPending} onClick={()=>saveReview.mutate()}>บันทึกผลทบทวน</button>{model.data.reference_review&&<span>บันทึกแล้วโดย {model.data.reference_review.actor} · เวอร์ชัน {review.data?.revision??1}</span>}</div>
          <h3>3. ตรวจข้อมูลใหม่และเปิด Active</h3><p className="context-help">Reference ที่ทบทวนจะตรึงไว้ การตรวจข้อมูลใหม่ไม่ใช้ข้อมูลนั้นปรับ Baseline เอง</p>
          <ul>{readiness.data?.blockers.map(b=><li key={b}>{blockers[b]??b}</li>)}</ul>
          {model.data.future_validation&&<div className="context-badges"><span>ประเมินได้ {String(model.data.future_validation.supported_minutes??0)} นาที</span><span>State Gate งดประเมิน {String(model.data.future_validation.excluded_state_minutes??0)} นาที</span><span>สภาวะที่รองรับแต่ยังต้องทบทวน {String(model.data.future_validation.unresolved_minutes??0)} นาที</span></div>}
          <ContextFollowupProgress model={model.data} reviewer={reviewer} dirty={reviewDirty||selectionDirty} running={running} onValidate={()=>prepare.mutate({parent_profile_id:effective,validation_only:true})} onOpen={openFollowup}/>
          <div className="context-actions"><button className="primary" disabled={!readiness.data?.ready||reviewDirty||selectionDirty||approve.isPending||note.trim().length<8} onClick={()=>approve.mutate()}>Approve → Active Profile</button></div>
          {active.data?.some(a=>a.module===module&&a.profile_id===effective)&&<p>Active Profile นี้กำลังถูกใช้ประเมินใน Context detector</p>}
          {activeModule&&<details><summary>Active และการย้อนกลับเวอร์ชัน</summary><p>Active: {activeModule.profile_id.slice(0,12)} · เวอร์ชัน {activeModule.revision}</p>{activeModule.previous_profile_id?<><p>เวอร์ชันก่อนหน้า: {activeModule.previous_profile_id.slice(0,12)}</p><ul>{previousReady.data?.blockers.map(b=><li key={b}>{blockers[b]??b}</li>)}</ul><button disabled={!previousReady.data?.ready||!previous.data||!enabled||note.trim().length<8||rollback.isPending} onClick={()=>rollback.mutate()}>ย้อนกลับไปใช้ Active เวอร์ชันก่อนหน้า</button></>:<p>ยังไม่มี Active เวอร์ชันก่อนหน้า</p>}</details>}
        </fieldset></section>}
        {model.data&&<ContextValidationReport model={model.data} onInspect={time=>inspect(time,model.data!.reference_start,model.data!.shadow_end)}/>}
      </>}
    </>}
  </section>;
}

