import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { CheckCircle2, ChevronRight, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../api";
import { draftError, type ReviewDraft } from "../calibration-review";
import { CalibrationEvidence, ScoreChart, type DiagnosticEvidence, type EvidenceInterval } from "./CalibrationEvidence";
import "./reference-review.css";

export type ReferenceSelection = {
  version: string; machine_number: string; module: number; source_timezone: string;
  source_latest: string; reference_start: string; reference_end: string;
  policy: { source_pressure_unit: string; qualified_1m_minimum_coverage?: number;
    qualified_1m_maximum_gap_seconds?: number; profile_quarantine_z?: number };
  shadow_start: string; shadow_end: string;
  latest_complete_end?: string; shadow_selection_reason?: string;
  review_note?: string;
  exclusions: { start: string; end: string; reason: string }[];
};
type AvailablePeriod = { reference_start: string; reference_end: string; shadow_start: string; shadow_end: string;
  reference_raw_days?: number; shadow_raw_days?: number; shadow_no_log_dates?: string[]; shadow_missing_sensor_dates?: string[];
  reference_observed_days: number; reference_observed_minutes: number; shadow_observed_days: number;
  shadow_observed_minutes: number; shadow_missing_dates: string[]; backtrack_days?: number };
export type ReferenceAvailability = {
  machine_number: string; module: number; source_latest: string | null; source_timezone?: string;
  module_latest_date?: string | null; source_age_days?: number; latest_complete_end?: string;
  default_period?: AvailablePeriod; suggested_period: AvailablePeriod | null;
  daily: { date: string; raw_rows: number; module_rows: number; module_minutes: number; complete_day: boolean }[];
};
type ChartPoint = { time: string; qualified: number; observed: number; phase: string; [key: string]: unknown };
export type ReferenceJob = {
  job_id: string; status: string; error_code: string | null; progress_message: string | null;
  machine_number: string; module: number;
  preview: null | {
    selection: ReferenceSelection; source_digest: string; can_build: boolean;
    candidate_status: string; reason_codes: string[]; chart: ChartPoint[];
    diagnostics?:DiagnosticEvidence;
    baseline?:Record<string,{median:number;scale:number}>;
    reference_proposal?:{changed:boolean;reason:string;candidates_checked:number;shadow_used_for_selection:boolean;needs_review?:boolean;alternatives?:{start:string;end:string;qualified_days:number;quarantine_pct:number;drift_rz:number|null;daily_level_span_rz:number;daily_level_feature?:string;control_daily_span_rz?:number;reference_checks_pass:boolean}[]};
    coverage_issues?: string[];
    daily: { date: string; phase: string; observed: number; qualified: number; selected: number; excluded: number; missing: number; reasons: Record<string, number> }[];
    summary: { reference_days: number; reference_minutes: number; shadow_minutes: number;
      retained_reference_days?: number; retained_reference_minutes?: number;
      quarantine_pct: number; shadow_flag_pct: number | null; min_reference_days: number; min_reference_minutes: number;
      max_half_shift_rz?:number|null;
      shadow_days?: number; min_shadow_minutes?: number; shadow_ready?: boolean };
  };
  result: null | { batch_id: string | null; candidate_status: string; automatic_parent_id?: string };
};
type Draft = ReviewDraft;
export type ReferenceJobSummary = { job_id: string; status: string; created_at: string; request: {
  reference_start: string | null; reference_end: string | null; shadow_end: string | null;
  shadow_selection_reason: string; exclusions: ReferenceSelection["exclusions"]; review_note: string;
} };
const blank: Draft = { start: "", end: "", shadowEnd: "", shadowReason: "", exclusions: [], note: "" };
function readSavedReview(key: string): { draft: Draft; jobId: string; reviewer: string; inputReviewer?: string; needsPreview?: boolean } | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null");
    const draft = value?.draft;
    if (!value || typeof value.jobId !== "string" || typeof value.reviewer !== "string" || !draft
      || typeof draft.start !== "string" || typeof draft.end !== "string" || typeof draft.note !== "string"
      || !Array.isArray(draft.exclusions) || draft.exclusions.length > 30
      || draft.exclusions.some((x: ReferenceSelection["exclusions"][number]) => !x || typeof x.start !== "string" || typeof x.end !== "string" || typeof x.reason !== "string")) return null;
    return { ...value, draft: { ...draft, shadowEnd: typeof draft.shadowEnd === "string" ? draft.shadowEnd : "",
      shadowReason: typeof draft.shadowReason === "string" ? draft.shadowReason : "" } };
  } catch { return null; }
}
const isBusy = (status?: string) => Boolean(status && ["PREVIEW_QUEUED", "PREVIEW_RUNNING", "BUILD_QUEUED", "BUILD_RUNNING"].includes(status));
const errorText: Record<string, string> = {
  REFERENCE_STORAGE_BUSY_RETRY: "ฐานข้อมูลกำลังใช้งานพร้อมกัน กรุณาลองเชื่อมงานเดิมอีกครั้ง ไม่ต้องสร้างงานใหม่",
  REFERENCE_STORAGE_CONNECTION_OR_PERMISSION_ERROR: "เชื่อมฐานข้อมูล Reference Review ไม่ได้ กรุณาตรวจการเชื่อมต่อและสิทธิ์ของบัญชีฐานข้อมูล",
  REFERENCE_STORAGE_SCHEMA_MISMATCH: "โครงสร้างตาราง Reference Review ไม่ตรงกับโค้ด กรุณาตรวจ columns กับ mysql_reference_review.sql ก่อนปรับ schema โดยเก็บงานเดิมไว้",
  "Reference review storage unavailable; apply mysql_reference_review.sql to the analytics schema": "ยังไม่ได้ติดตั้งตาราง Reference Review กรุณาใช้ mysql_reference_review.sql ในฐานข้อมูล Analytics",
  SOURCE_CHANGED_REVIEW_AGAIN: "ข้อมูลย้อนหลังเปลี่ยนหลังจากที่ดูกราฟ กรุณาทบทวนข้อมูลใหม่ก่อนสร้าง Candidate",
  POLICY_CHANGED_REVIEW_AGAIN: "การตั้งค่าระบบเปลี่ยน กรุณาทบทวนข้อมูลใหม่",
  INTERRUPTED_OR_TIMED_OUT: "งานหยุดกลางทางหรือหมดเวลา กรุณาเริ่มทบทวนใหม่ โดย Active Profile เดิมไม่เปลี่ยน",
  NO_SOURCE_DATA: "ไม่พบข้อมูลของเครื่องที่เลือก",
  CONTEXT_BUSY: "เครื่อง–โมดูลนี้มีงานกำลังรัน กรุณารอให้งานเดิมเสร็จก่อน",
  QUEUE_BUSY: "มีงานในคิวครบแล้ว กรุณารอสักครู่",
  INVALID_REFERENCE_OR_SOURCE: "ช่วงวันที่หรือข้อมูลไม่ผ่านเงื่อนไข ตรวจวันสิ้นสุด Reference และช่วงยกเว้นอีกครั้ง",
  SOURCE_OR_DATABASE_UNAVAILABLE: "อ่านข้อมูลหรือบันทึกผลไม่ได้ ตรวจการเชื่อมต่อฐานข้อมูลแล้วเริ่มทบทวนใหม่",
  PREVIEW_EXPIRED_REVIEW_AGAIN: "ผลทบทวนเกิน 24 ชั่วโมงแล้ว กรุณาดูข้อมูลใหม่ก่อนสร้าง Candidate",
  PREVIEW_MISMATCH: "ผลทบทวนไม่ตรงกับงานที่เลือก กรุณาเปิดผลล่าสุดแล้วตรวจใหม่",
  REFERENCE_NOT_READY: "งานนี้ยังไม่พร้อมสร้าง Candidate ตรวจสถานะและจำนวนข้อมูลก่อน",
  BUILD_REQUEST_CHANGED: "บันทึกการทบทวนเปลี่ยนหลังส่งงาน หากต้องการแก้ให้เริ่มทบทวนรอบใหม่",
  DETAIL_DAY_OUTSIDE_REFERENCE: "วันที่เลือกอยู่นอกช่วงข้อมูลที่ทบทวน",
  QUALIFIED_LIVE_SOURCE_REQUIRED: "ตั้งค่าแหล่งข้อมูลจริงและ Profile แบบราย 1 นาทีก่อนใช้งาน",
  IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_INPUT: "คำขอนี้เปลี่ยนจากครั้งก่อน กรุณาเริ่มทบทวนใหม่",
};
const displayError = (message: string) => errorText[message] ?? message;
const displayProgress = (message?: string | null) => message?.startsWith("Reading source day ")
  ? `กำลังอ่านข้อมูลวันที่ ${message.slice(19)}`
  : message === "Calculating candidate evidence" ? "กำลังคำนวณ Baseline และหลักฐาน Shadow" : message ?? "รออ่านข้อมูลทีละวัน";
const localLabel = (value: unknown) => String(value ?? "").replace("T", " ").slice(0, 16);
const axisTime = (value: string) => Date.parse(`${value}Z`); // coordinate only; source-local labels, no browser TZ conversion

function ReviewChart({ data, selection, title, unit, fields, minuteView = false }: {
  data: ChartPoint[]; selection: ReferenceSelection; title: string; unit: string; fields: [string, string, string][]; minuteView?: boolean;
}) {
  const plotted = data.map(point => ({ ...point, tick: axisTime(point.time),problem:((point.flagged||Number(point.flagged_minutes)>0)&&point.contributor===fields[0][0])||(point.reference_outlier&&point.reference_contributor===fields[0][0])?point[fields[0][0]]:null }));
  const ticks = minuteView && plotted.length ? [0,.25,.5,.75,1].map(r=>plotted[0].tick+r*(plotted[plotted.length-1].tick-plotted[0].tick)) : undefined;
  return <figure className="ref-chart">
    <figcaption><strong>{title} · {selection.machine_number} / M{selection.module}</strong><span>{unit} · {minuteView ? "ค่าเฉลี่ยรายนาทีจากวินาทีที่วัดจริง ช่องว่างไม่ใช่ปกติ" : "มัธยฐานรายชั่วโมง + ช่วงต่ำสุด–สูงสุดของค่านาที"}</span></figcaption>
    {data.some(point => fields.some(([key]) => typeof point[key] === "number" && Number.isFinite(point[key]))) ? <ResponsiveContainer width="100%" height={230}>
      <ComposedChart data={plotted} syncId="reference-review" accessibilityLayer margin={{ left: 0, right: 12, top: 10, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#e9eef4" />
        <XAxis dataKey="tick" type="number" domain={["dataMin", "dataMax"]} ticks={ticks} tickFormatter={v => new Date(Number(v)).toISOString().slice(minuteView ? 11 : 5,minuteView ? 16 : 10)} minTickGap={45} tick={{ fontSize: 11 }} />
        <YAxis width={48} tick={{ fontSize: 11 }} />
        <Tooltip labelFormatter={v => localLabel(new Date(Number(v)).toISOString())} formatter={(v, name) => [Array.isArray(v) ? v.map(x => Number(x).toFixed(2)).join(" – ") : typeof v === "number" ? v.toFixed(2) : v, name]} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <ReferenceArea x1={axisTime(selection.shadow_start)} x2={plotted.at(-1)?.tick} fill="#8b6db8" fillOpacity={.09} />
        {selection.reference_end < selection.shadow_start && <ReferenceArea x1={axisTime(selection.reference_end)} x2={axisTime(selection.shadow_start)} fill="#7d8998" fillOpacity={.1} />}
        {selection.exclusions.map((x, i) => <ReferenceArea key={i} x1={axisTime(x.start)} x2={axisTime(x.end)} fill="#7d8998" fillOpacity={.16} ifOverflow="hidden" />)}
        {!minuteView && fields.map(([key, label, color]) => <Area key={`${key}-range`} dataKey={`${key}_range`} name={`${label} min–max`} stroke="none" fill={color} fillOpacity={.08} legendType="none" connectNulls={false} isAnimationActive={false} />)}
        {fields.map(([key, label, color]) => <Line key={key} type="linear" dataKey={key} name={label} stroke={color} strokeWidth={1.8} dot={false} connectNulls={false} isAnimationActive={false} />)}
        <Scatter dataKey="problem" name="ตัวแปรเด่นที่ต้องตรวจ" fill="#ba4343" isAnimationActive={false}/>
      </ComposedChart>
    </ResponsiveContainer> : <div className="ref-chart-placeholder" role="status">ไม่มีค่านาทีที่ผ่าน Gate สำหรับกราฟนี้ · ตรวจเหตุผลในตารางความครอบคลุมด้านล่าง</div>}
  </figure>;
}

export function ReferenceReview({ machine, module, reviewer, onReviewer, onModule, onBuilt, initialJobId }: {
  machine: string; module: number; reviewer: string; onReviewer: (value: string) => void;
  onModule: (value: number) => void; onBuilt: (batch: string) => void; initialJobId?: string;
}) {
  const storageKey = `ht9046mx-reference-v1:${machine}:${module}`;
  const [saved] = useState(() => readSavedReview(storageKey));
  const [draft, setDraft] = useState<Draft>(initialJobId ? blank : saved?.draft ?? blank);
  const [jobId, setJobId] = useState<string | null>(initialJobId ?? saved?.jobId ?? null);
  const [jobReviewer, setJobReviewer] = useState<string>(initialJobId ? reviewer.trim() : saved?.reviewer ?? reviewer);
  const [needsPreview, setNeedsPreview] = useState(initialJobId ? false : saved?.needsPreview ?? false);
  const [lastPreview, setLastPreview] = useState<ReferenceJob["preview"]>(null);
  const [ack, setAck] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [signalGroup, setSignalGroup] = useState("pressure2");
  const [zoomDay, setZoomDay] = useState("");
  const [focusWindow,setFocusWindow]=useState<{start:number;end:number}|null>(null);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const delivered = useRef<string | null>(null);
  const [inventoryOpen,setInventoryOpen] = useState(false);
  const availability = useQuery({ queryKey: ["reference-availability", machine, module],
    queryFn: () => api.referenceAvailability(machine, module), staleTime: 300_000,
    gcTime: 1_800_000, refetchOnWindowFocus: false, retry: false, enabled:inventoryOpen });
  useEffect(() => { if (!reviewer && (saved?.inputReviewer || saved?.reviewer)) onReviewer(saved.inputReviewer || saved.reviewer); }, []);
  const recent = useQuery({ queryKey: ["reference-recent", machine, module, reviewer.trim()],
    queryFn: () => api.referenceRecentJobs(machine, module, reviewer.trim()), enabled: reviewer.trim().length >= 2,
    staleTime: 60_000, retry: false });
  const job = useQuery({ queryKey: ["reference-job", jobId, jobReviewer],
    queryFn: () => api.referenceJob(jobId!, jobReviewer), enabled: Boolean(jobId),
    staleTime: 0, retry: 1,
    refetchInterval: query => isBusy(query.state.data?.status) ? 2000 : false });
  const current = job.data;
  const initialized = useRef(false);
  useEffect(() => {
    if (initialJobId && current?.preview && !initialized.current) {
      initialized.current = true;
      const s = current.preview.selection;
      setDraft({start:s.reference_start.slice(0,10),end:s.reference_end.slice(0,10),
        shadowEnd:s.shadow_selection_reason?s.shadow_end.slice(0,10):"",shadowReason:s.shadow_selection_reason??"",
        exclusions:s.exclusions,note:s.review_note??""});
    }
  },[initialJobId,current?.preview]);
  const preview = current?.preview ?? lastPreview;
  useEffect(() => { if (current?.preview) setLastPreview(current.preview); }, [current?.preview]);
  useEffect(() => { if (current && !isBusy(current.status)) recent.refetch(); }, [current?.status, current?.job_id]);
  const outdatedPreview = Boolean(preview && preview.selection.version !== "manual-reference-complete-day-shadow-v3-physical" && !current?.result);
  const minute = useQuery({ queryKey: ["reference-day",jobId,jobReviewer,zoomDay],
    queryFn: () => api.referenceDay(jobId!,jobReviewer,zoomDay), enabled: Boolean(preview && zoomDay), retry: false });
  const previewMutation = useMutation({
    mutationFn: (key: string) => api.previewReference(reviewer.trim(), { idempotency_key: key,
      machine_number: machine, module, history_days: 28,
      reference_start: draft.start || null, reference_end: draft.end || null,
      shadow_end: draft.shadowEnd || null, shadow_selection_reason: draft.shadowReason,
      exclusions: draft.exclusions, review_note: draft.note }),
    onSuccess: result => { setJobReviewer(reviewer.trim()); setJobId(result.job_id); setNeedsPreview(false); recent.refetch(); },
  });
  const build = useMutation({ mutationFn: () => api.buildReference(current!.job_id, jobReviewer, {
    source_digest: preview!.source_digest, acknowledge_reference: ack, review_note: reviewNote.trim() }),
    onSuccess: () => job.refetch(),
  });
  const busy = isBusy(current?.status) || previewMutation.isPending || build.isPending || (Boolean(jobId) && job.isPending);
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify({ jobId: jobId ?? "", reviewer: jobReviewer,
        inputReviewer: reviewer, draft, needsPreview }));
    } catch { setStorageUnavailable(true); }
  }, [jobId, jobReviewer, reviewer, draft, needsPreview, storageKey]);
  useEffect(() => {
    if (current?.result?.batch_id && delivered.current !== current.result.batch_id) {
      delivered.current = current.result.batch_id;
      onBuilt(current.result.batch_id);
    }
  }, [current?.result, onBuilt]);
  function edit(next: Draft) {
    setDraft(next); setNeedsPreview(true); setAck(false); setReviewNote(""); setRequestKey(crypto.randomUUID());
    build.reset(); previewMutation.reset();
  }
  function resume(entry: ReferenceJobSummary) {
    const r = entry.request;
    setDraft({ start: r.reference_start ?? "", end: r.reference_end ?? "", shadowEnd: r.shadow_end ?? "",
      shadowReason: r.shadow_selection_reason ?? "", exclusions: r.exclusions, note: r.review_note });
    setJobReviewer(reviewer.trim()); setJobId(entry.job_id); setLastPreview(null); setNeedsPreview(false);
    setAck(false); setReviewNote(""); setZoomDay(""); setRequestKey(crypto.randomUUID());
    build.reset(); previewMutation.reset();
  }
  const validationError = draftError(draft, availability.data?.latest_complete_end ?? preview?.selection.latest_complete_end?.slice(0,10));
  const canOpenExistingPreview = current?.status === "READY" && !outdatedPreview && !needsPreview;
  const groups: Record<string, { title: string; unit: string; fields: [string, string, string][] }> = {
    pressure2: { title: "CP2 · High / Low Pressure", unit: preview?.selection.policy.source_pressure_unit || "หน่วยแรงดันยังไม่ยืนยัน", fields: [["hp2", "Hp 2nd", "#1f6fa7"], ["lp2", "Lp 2nd", "#098a86"]] },
    pressure1: { title: "CP1 · High / Low Pressure", unit: preview?.selection.policy.source_pressure_unit || "หน่วยแรงดันยังไม่ยืนยัน", fields: [["hp1", "Hp 1st", "#1f6fa7"], ["lp1", "Lp 1st", "#098a86"]] },
    temperature: { title: "อุณหภูมิ", unit: "หน่วย sensor ตาม source contract", fields: [["temphi", "TempHi", "#bd692c"], ["templo", "TempLo", "#327ca5"]] },
    valve: { title: "Expansion Valve", unit: "count", fields: [["valve", "Valve", "#7b60a3"]] },
    differential: { title: "Pressure Differential", unit: preview?.selection.policy.source_pressure_unit || "หน่วยแรงดันยังไม่ยืนยัน", fields: [["dp1", "ΔP CP1", "#1f6fa7"], ["dp2", "ΔP CP2", "#098a86"]] },
  };
  const error = current?.error_code ?? build.error?.message ?? previewMutation.error?.message ?? job.error?.message;
  function locateEvidence(interval:EvidenceInterval) {
    setZoomDay(interval.peak_time.slice(0,10));
    const peak=axisTime(interval.peak_time);setFocusWindow({start:peak-30*60_000,end:peak+30*60_000});
    setSignalGroup(["hp1","lp1"].includes(interval.feature)?"pressure1":["hp2","lp2"].includes(interval.feature)?"pressure2":["dp1","dp2"].includes(interval.feature)?"differential":interval.feature==="valve"?"valve":"temperature");
  }
  const step = current?.result ? 4 : current?.status?.startsWith("BUILD") ? 3 : preview ? 2 : 1;
  const dayPoints=(minute.data?.chart??[]) as ChartPoint[];
  const chartPoints=zoomDay?focusWindow?dayPoints.filter(p=>axisTime(p.time)>=focusWindow.start&&axisTime(p.time)<=focusWindow.end):dayPoints:preview?.chart??[];
  return <section className="reference-review" aria-labelledby="ref-title">
    <header className="ref-header"><div><span className="ref-eyebrow">PROFILE SETUP · {machine} / M{module}</span>
      <h2 id="ref-title">เลือกข้อมูลอ้างอิงก่อนสร้าง Profile</h2>
      <p>ทำครั้งแรกหรือเมื่อต้องการปรับ Profile ไม่ต้องทำซ้ำทุกครั้งที่ข้อมูลใหม่เข้ามา</p></div>
      <label>โมดูล<select aria-label="โมดูลสำหรับ Reference" value={module} disabled={busy} onChange={e => onModule(Number(e.target.value))}>{[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Module {n}</option>)}</select></label>
    </header>
    <ol className="ref-steps" aria-label="ขั้นตอนสร้าง Profile">{["เลือกช่วงข้อมูล", "ทบทวนกราฟ", "สร้าง Candidate + Shadow", "ตรวจผลและอนุมัติ"].map((label, i) => <li key={label} aria-current={step === i + 1 ? "step" : undefined} className={step >= i + 1 ? "current" : ""}><span>{i + 1}</span>{label}</li>)}</ol>
    <details className="ref-availability" onToggle={e=>setInventoryOpen(e.currentTarget.open)} aria-label="ตรวจวันที่มีข้อมูลรวม Shadow">
      <summary>ตรวจวันข้อมูลเพิ่มเติม / ค้นหาช่วงย้อนหลัง</summary>
      <div className="ref-availability-heading"><strong>ตรวจข้อมูลก่อนเลือกช่วง</strong><button type="button" disabled={busy || availability.isFetching} onClick={() => availability.refetch()}><RefreshCw size={14} />ตรวจล่าสุด</button></div>
      {availability.isFetching && <p role="status">กำลังตรวจวันที่มีข้อมูลของ {machine} / M{module}…</p>}
      {availability.error && <p className="ref-error" role="alert">ยังตรวจวันข้อมูลล่าสุดไม่ได้ · {availability.error.message} {availability.data?.source_latest ? "กำลังแสดงผลตรวจครั้งก่อน; Preview จะตรวจข้อมูลจริงอีกครั้ง" : "กรุณาตรวจล่าสุดอีกครั้งก่อนทำ Preview"}</p>}
      {availability.data && !availability.data.source_latest && <p role="alert">ไม่พบข้อมูลต้นทางของเครื่องนี้</p>}
      {availability.data?.source_latest && <>
        <p className="ref-help">ตรวจวันที่มีข้อมูลเมื่อ {new Date(availability.dataUpdatedAt).toLocaleString("th-TH", {timeZone:"Asia/Bangkok"})} · Preview จะอ่านข้อมูลจริงและตรวจ Gate อีกครั้ง</p>
        <p>แถวล่าสุดของเครื่อง: <strong>{localLabel(availability.data.source_latest)}</strong> · โมดูลนี้มี sensor ครบ 7 ช่องล่าสุดวันที่ <strong>{availability.data.module_latest_date ?? "ไม่พบในช่วงที่ตรวจ"}</strong> · {availability.data.source_timezone}</p>
        {availability.data.source_age_days !== undefined && availability.data.source_age_days >= 1 && <p className="ref-help">ข้อมูลย้อนหลัง ห่างจากเวลาปัจจุบันประมาณ {Math.floor(availability.data.source_age_days)} วัน ไม่ใช่ข้อมูลสด</p>}
        {availability.data.default_period && <>
          <p>ตามแถวล่าสุด: Reference {availability.data.default_period.reference_start} → ก่อน {availability.data.default_period.reference_end} · มี log {availability.data.default_period.reference_raw_days ?? "—"} วัน · sensor ครบ 7 ช่อง {availability.data.default_period.reference_observed_days} วัน / {availability.data.default_period.reference_observed_minutes.toLocaleString()} นาที</p>
          <p>Shadow {availability.data.default_period.shadow_start} → ก่อน {availability.data.default_period.shadow_end} · มี log {availability.data.default_period.shadow_raw_days ?? "—"}/3 วัน · sensor ครบ 7 ช่อง {availability.data.default_period.shadow_observed_days}/3 วัน / {availability.data.default_period.shadow_observed_minutes.toLocaleString()} นาที</p>
          {Boolean(availability.data.default_period.shadow_no_log_dates?.length) && <p className="ref-warning">วันที่ไม่มี log: {availability.data.default_period.shadow_no_log_dates!.join(", ")}</p>}
          {Boolean(availability.data.default_period.shadow_missing_sensor_dates?.length) && <p className="ref-warning">มี log แต่โมดูลนี้ไม่มีแถวที่ sensor ครบ 7 ช่อง: {availability.data.default_period.shadow_missing_sensor_dates!.join(", ")}</p>}
        </>}
        {availability.data.suggested_period ? <>
          <p>ช่วงเสนอจากข้อมูลที่มี: Reference {availability.data.suggested_period.reference_start} → ก่อน {availability.data.suggested_period.reference_end} ({availability.data.suggested_period.reference_observed_days} วันที่มีข้อมูล) · Shadow {availability.data.suggested_period.shadow_start} → ก่อน {availability.data.suggested_period.shadow_end} (3 วันติดกัน)</p>
          <button type="button" disabled={busy} onClick={() => {
            const p = availability.data!.suggested_period!;
            edit({ ...draft, start: p.reference_start, end: p.reference_end,
              shadowEnd: p.shadow_end, shadowReason: "เลือกช่วงที่มีข้อมูลต่อเนื่องจากการตรวจวันข้อมูล รวม Reference และ Shadow" });
          }}>ใช้ช่วงเสนอ แล้วตรวจ Gate ใน Preview</button>
        </> : <p className="ref-warning" role="status">ยังไม่พบช่วงที่มีข้อมูลเพียงพอทั้ง Reference และ Shadow 3 วันติดกันในขอบเขตที่ตรวจ เลือกช่วงเองเพื่อดูกราฟได้ แต่ยังไม่พร้อมสร้าง Profile</p>}
        <p className="ref-help">จำนวนนี้นับนาทีที่พบข้อมูล sensor ไม่ใช่นาทีที่ผ่าน Gate และไม่รับรองว่าเครื่องปกติ ระบบยังต้องตรวจวินาทีจริง/สถานะ/Gap ใน Preview ก่อนสร้าง Candidate</p>
      </>}
    </details>
    <fieldset disabled={busy} className="ref-fields">
      <label>ผู้ทบทวน<input value={reviewer} maxLength={100} onChange={e => { onReviewer(e.target.value); edit(draft); }} placeholder="ชื่อหรือรหัสผู้ใช้งาน" /></label>
      <label>วันเริ่ม Reference<input type="date" value={draft.start} onInput={e => edit({ ...draft, start: e.currentTarget.value })} /></label>
      <label>วันสิ้นสุด Reference (ไม่รวมวันนี้)<input type="date" value={draft.end} onInput={e => edit({ ...draft, end: e.currentTarget.value })} /></label>
    </fieldset>
    <fieldset disabled={busy} className="ref-shadow-fields">
      <label>Shadow สิ้นสุดก่อนวันที่<input type="date" value={draft.shadowEnd} max={availability.data?.latest_complete_end} onInput={e => edit({ ...draft, shadowEnd: e.currentTarget.value })} /></label>
      <label>เหตุผลเลือกช่วง Shadow ย้อนหลัง<input value={draft.shadowReason} maxLength={500} onChange={e => edit({ ...draft, shadowReason: e.target.value })} placeholder="ระบุเมื่อเลือกวันเอง เช่น ช่วงล่าสุดมีวันขาด" /></label>
    </fieldset>
    <p className="ref-help">Shadow = 3 วันเต็มติดกันก่อนวันสิ้นสุดที่เลือก · เว้น Shadow ให้ใช้ cutoff ตามแถวล่าสุด · เว้น Reference ทั้งสองช่องให้ใช้ 28 วันก่อน Shadow · ไม่รวมวันล่าสุดที่ยังไม่ครบ และไม่ใช้ Shadow สร้าง Baseline</p>
    {recent.data && recent.data.length > 0 && <details className="ref-daily ref-job-history"><summary>เปิดงานทบทวนเดิมของ {machine} / M{module} ({recent.data.length})</summary>
      <p>งานของผู้ทบทวนรหัสนี้เท่านั้น เปิดกราฟหรือกลับมาติดตามงานได้โดยไม่เริ่มประมวลผลใหม่</p>
      <div>{recent.data.map(entry => <button type="button" key={entry.job_id} disabled={busy} onClick={() => resume(entry)}>
        {new Date(entry.created_at).toLocaleString("th-TH",{timeZone:"Asia/Bangkok"})} · {entry.status} · {entry.job_id.slice(0,8)}
      </button>)}</div>
    </details>}
    {recent.error && <p className="ref-help">เปิดรายการงานเดิมไม่ได้: {displayError(recent.error.message)}</p>}
    <details className="ref-exclusions" open={draft.exclusions.length > 0}>
      <summary>ไม่ใช้บางช่วงสร้าง Baseline <span>({draft.exclusions.length} ช่วง)</span></summary>
      <p>ใช้เมื่อทราบว่าช่วงนั้นมีปัญหาหรือไม่เหมาะเป็นข้อมูลอ้างอิง ไม่ลบ log และไม่ตัดข้อมูล Shadow</p>
      {draft.exclusions.map((x, i) => <fieldset disabled={busy} key={i} className="ref-exclusion-row">
        <label>เริ่มช่วงยกเว้น {i + 1}<input type="datetime-local" value={x.start} onInput={e => edit({ ...draft, exclusions: draft.exclusions.map((y,j) => j === i ? { ...y, start: e.currentTarget.value } : y) })} /></label>
        <label>จบช่วงยกเว้น {i + 1} (ไม่รวม)<input type="datetime-local" value={x.end} onInput={e => edit({ ...draft, exclusions: draft.exclusions.map((y,j) => j === i ? { ...y, end: e.currentTarget.value } : y) })} /></label>
        <label>เหตุผลช่วงยกเว้น {i + 1}<input value={x.reason} maxLength={500} onChange={e => edit({ ...draft, exclusions: draft.exclusions.map((y,j) => j === i ? { ...y, reason: e.target.value } : y) })} placeholder="เช่น ช่วงที่พบอาการผิดปกติ" /></label>
        <button type="button" aria-label={`ลบช่วงยกเว้น ${i + 1}`} onClick={() => edit({ ...draft, exclusions: draft.exclusions.filter((_, j) => j !== i) })}><Trash2 size={16} /></button>
      </fieldset>)}
      <button type="button" disabled={busy || draft.exclusions.length >= 30} onClick={() => edit({ ...draft, exclusions: [...draft.exclusions, { start: "", end: "", reason: "" }] })}>+ เพิ่มช่วงยกเว้น</button>
    </details>
    <div className="ref-actions">
      <button className="ref-primary" disabled={busy || (!canOpenExistingPreview && (reviewer.trim().length < 2 || Boolean(validationError)))} onClick={() => {
        if (current?.status === "READY" && !outdatedPreview && !needsPreview) { document.querySelector(".ref-signal")?.scrollIntoView({behavior:"smooth"}); return; }
        const key = current?.status === "FAILED" || current?.result || outdatedPreview ? crypto.randomUUID() : requestKey;
        setRequestKey(key); setAck(false); setZoomDay(""); build.reset(); previewMutation.mutate(key);
      }}>
        {busy ? <RefreshCw size={16} className="spin" /> : <ChevronRight size={16} />}{busy ? "กำลังประมวลผล" : needsPreview && preview ? "1. คำนวณ Preview ใหม่ตามช่วงที่แก้" : current?.status === "READY" && !outdatedPreview ? "ดูกราฟ Reference ด้านล่าง" : current?.status === "FAILED" || current?.result || outdatedPreview ? "เริ่มทบทวนรอบใหม่" : "1. ดูกราฟและตรวจช่วงข้อมูล"}
      </button>
      {preview && !busy && <button type="button" onClick={() => edit({ ...draft, start: preview.selection.reference_start.slice(0,10), end: preview.selection.reference_end.slice(0,10) })}>ย้อนกลับปรับช่วง Reference</button>}
    </div>
    {reviewer.trim().length < 2 && <p className="ref-help">กรอกชื่อหรือรหัสผู้ทบทวนอย่างน้อย 2 ตัวอักษรก่อนเริ่ม</p>}
    {validationError && <p className="ref-warning" role="alert">{validationError}</p>}
    {preview && (needsPreview || (busy && !current?.preview)) && <p className="ref-warning" role="status">{busy ? "กำลังคำนวณ Preview ใหม่" : "แก้ช่วงข้อมูลแล้ว"} · กราฟและจำนวนด้านล่างยังเป็นผลรอบเดิม ใช้ตรวจช่วงได้ แต่ต้องรอ Preview ใหม่ก่อนสร้าง Candidate</p>}
    {busy && <p className="ref-status" role="status">{displayProgress(current?.progress_message)} · {storageUnavailable ? "งานยังทำต่อบนระบบ" : "ออกจากหน้านี้แล้วกลับมาติดตามงานเดิมได้"}</p>}
    {storageUnavailable && <p className="ref-help" role="status">เบราว์เซอร์นี้ไม่อนุญาตให้จำงานหลังรีเฟรช อาจต้องเริ่มทบทวนใหม่ แต่ข้อมูลที่ส่งไปยังคงบันทึกในระบบ{jobId ? ` · รหัสงาน ${jobId}` : ""}</p>}
    {error && <div role="alert" className="ref-error">{displayError(error)}{job.error && <button onClick={() => job.refetch()}>เชื่อมต่ออีกครั้ง</button>}</div>}
    {outdatedPreview && <p className="ref-warning" role="alert">ผลทบทวนนี้ใช้กติกาเลือกวันรุ่นเก่า กรุณาเริ่มทบทวนรอบใหม่เพื่อเช็ค Reference และ Shadow ให้ครบก่อนสร้าง Candidate</p>}
    {preview && <>
      <div className="ref-periods"><div><span>REFERENCE · สร้าง Baseline</span><strong>{localLabel(preview.selection.reference_start)} → {localLabel(preview.selection.reference_end)} (ไม่รวม)</strong></div><div className="ref-shadow"><span>SHADOW · ทดสอบเท่านั้น</span><strong>{localLabel(preview.selection.shadow_start)} → {localLabel(preview.selection.shadow_end)} (ไม่รวม)</strong></div></div>
      <p className="ref-help">เวลาทั้งหมด: {preview.selection.source_timezone} · ข้อมูลล่าสุด {localLabel(preview.selection.source_latest)} · เทา = ไม่ใช้ Fit · ม่วง = Shadow ไม่ใช่ช่วงผิดปกติ</p>
      <div className="ref-metrics"><div><span>Reference ที่เลือกใช้</span><strong>{preview.summary.reference_days} วัน / {preview.summary.reference_minutes.toLocaleString()} นาที</strong></div><div><span>ข้อมูล Cold ที่ผ่าน Gate ใน Shadow</span><strong>{preview.summary.shadow_minutes.toLocaleString()} นาที</strong></div><div><span>Quarantine จาก Reference</span><strong>{preview.summary.reference_minutes ? `${preview.summary.quarantine_pct.toFixed(2)}%` : "— ไม่มีนาทีผ่าน Gate"}</strong></div></div>
      {preview.summary.retained_reference_minutes !== undefined && <p className="ref-help">เหลือหลัง Quarantine: {preview.summary.retained_reference_days} วัน / {preview.summary.retained_reference_minutes.toLocaleString()} นาทีสำหรับ Fit ขั้นสุดท้าย</p>}
      {preview.summary.shadow_days !== undefined && <p className={preview.summary.shadow_ready ? "ref-help" : "ref-warning"}>Shadow ผ่าน Gate {preview.summary.shadow_days}/3 วัน · {preview.summary.shadow_minutes.toLocaleString()}/{preview.summary.min_shadow_minutes} นาทีขั้นต่ำ{!preview.summary.shadow_ready && " · ต้องผ่าน Gate ครบทั้ง Reference และ Shadow ก่อนสร้าง Candidate"}</p>}
      {preview.coverage_issues && preview.coverage_issues.length > 0 && <p className="ref-warning" role="alert">ตรวจตารางรายวัน: {preview.daily.filter(d => d.phase === "shadow" && !d.qualified).map(d => `${d.date}: ${d.observed ? "มี log แต่ไม่มีนาทีผ่าน Gate" : "ไม่มี log"}`).join(" · ") || "จำนวน Shadow ต่ำกว่าขั้นต่ำ"}</p>}
      <p className="ref-help">ข้อมูลผ่าน Gate ไม่ได้ยืนยันว่าเครื่องปกติ · อัตราเตือนย้อนหลังไม่ใช่ความแม่นยำหรือ false-positive rate</p>
      {preview.reference_proposal&&<p className="ref-help">ช่วงที่ระบบเสนอ: {preview.reference_proposal.reason} · ตรวจ {preview.reference_proposal.candidates_checked} ช่วง · ไม่ใช้ Shadow เลือกช่วง · ยังต้องให้ผู้ดูแลตรวจความเหมาะสม</p>}
      {preview.reference_proposal?.needs_review&&<details className="ref-daily"><summary>เหตุใดระบบยังไม่เลือกช่วงใหม่ให้</summary><p>ระบบตรวจช่วงย้อนหลัง 7 / 14 / 21 / 28 วันตามข้อมูลที่มี ระบบเลือกอัตโนมัติเฉพาะช่วงที่จบใกล้ข้อมูลล่าสุดก่อน Shadow ช่วงเก่าที่คงที่อาจเป็นคนละสภาวะ จึงเก็บไว้ให้คนทบทวน ไม่เปลี่ยนช่วงตามผล Shadow</p><div className="ref-table-scroll"><table><thead><tr><th>ช่วง Reference</th><th>วันผ่าน Gate</th><th>คัดออก ≤5%</th><th>การเปลี่ยนระดับต้น–ท้าย ≤1.5</th><th>ความต่างระดับรายวัน ≤2.0</th><th>ตัวแปรที่เปลี่ยนเด่น</th></tr></thead><tbody>{preview.reference_proposal.alternatives?.map(x=><tr key={x.start+x.end}><td>{x.start.slice(0,10)} → {x.end.slice(0,10)}</td><td>{x.qualified_days}</td><td>{x.quarantine_pct.toFixed(2)}%</td><td>{x.drift_rz?.toFixed(2)??"ยังประเมินไม่ได้"}</td><td>{x.daily_level_span_rz.toFixed(2)}</td><td>{x.daily_level_feature??"รอบเดิมไม่ได้บันทึก"}</td></tr>)}</tbody></table></div><p className="ref-help">{preview.diagnostics?.scoring_policy?.control_votes===false?"กติกาใหม่ใช้แรงดันและอุณหภูมิตรวจความคงที่ ค่า Valve แสดงเป็นบริบท ไม่ทำให้ช่วงถูกตัดทิ้งเพียงตัวเดียว":"รอบนี้ใช้กติกาที่บันทึกไว้ตอนเตรียมข้อมูล"} · ยังไม่ใช่ผลยืนยันว่าเครื่องปกติหรือเสีย</p></details>}
      <CalibrationEvidence key={jobId??"none"} evidence={preview.diagnostics} baseline={preview.baseline} summary={preview.summary} reasons={preview.reason_codes} jobId={jobId!} reviewer={jobReviewer} onLocate={locateEvidence} disabled={busy} period={{start:preview.selection.reference_start,end:preview.selection.shadow_end}}/>
      <label className="ref-signal">ดูตัวแปร<select value={signalGroup} onChange={e => setSignalGroup(e.target.value)}>{Object.entries(groups).map(([key, group]) => <option key={key} value={key}>{group.title}</option>)}</select></label>
      <label className="ref-signal">ความละเอียดกราฟ<select value={zoomDay} onChange={e => {setZoomDay(e.target.value);setFocusWindow(null);}}><option value="">ภาพรวม · รายชั่วโมง</option>{preview.daily.map(d => <option key={d.date} value={d.date}>{d.date} · {d.phase} · ราย 1 นาที</option>)}</select></label>
      {focusWindow&&zoomDay&&<p className="ref-help">ซูมรอบจุดเด่น ±30 นาที <button onClick={()=>setFocusWindow(null)}>ดูทั้งวัน</button></p>}
      {minute.isFetching && zoomDay && <p role="status">กำลังอ่านกราฟรายนาทีของวันที่เลือก…</p>}
      {minute.error && zoomDay && <p className="ref-error" role="alert">{displayError(minute.error.message)}</p>}
      {groups[signalGroup].fields.map(field => (!zoomDay || minute.data)
        ? <ReviewChart key={field[0]} data={chartPoints} minuteView={Boolean(zoomDay)} selection={preview.selection} title={field[1]} unit={groups[signalGroup].unit} fields={[field]} />
        : <figure key={field[0]} className="ref-chart"><figcaption><strong>{field[1]} · {machine} / M{module}</strong></figcaption><div className="ref-chart-placeholder">{minute.error ? "อ่านกราฟไม่ได้ กรุณาเลือกวันอีกครั้งหรือตรวจข้อความด้านบน" : "กำลังอ่านกราฟรายนาที…"}</div></figure>)}
      <ScoreChart points={chartPoints}/>
      <details className="ref-daily"><summary>ตรวจความครอบคลุมรายวันและช่วง Manual / State / Gap</summary><div className="ref-table-scroll"><table><caption>นาทีที่มีข้อมูลจริงเทียบกับ 1,440 นาที/วัน · สรุป Gate ไม่ใช่การยืนยันสาเหตุ</caption><thead><tr><th>วัน / ช่วง</th><th>มีข้อมูล</th><th>ผ่าน Gate</th><th>ใช้ Reference</th><th>ยกเว้น</th><th>ไม่มีข้อมูล</th><th>ไม่ผ่าน Gate</th></tr></thead><tbody>{preview.daily.map(d => <tr key={d.date}><td>{d.date}<small>{d.phase}</small></td><td>{d.observed}</td><td>{d.qualified}</td><td>{d.phase === "reference" ? d.selected : "—"}</td><td>{d.excluded}</td><td>{d.missing}</td><td>{Object.entries(d.reasons).map(([key, count]) => `${key}: ${count}`).join(" · ") || "—"}</td></tr>)}</tbody></table></div></details>
      <details className="ref-daily"><summary>รายละเอียดทางเทคนิคและข้อควรทบทวน ({preview.reason_codes.length})</summary><p>1 นาทีจาก ≥{Math.ceil(60*(preview.selection.policy.qualified_1m_minimum_coverage ?? .95))} วินาทีจริง · gap ≤{preview.selection.policy.qualified_1m_maximum_gap_seconds ?? 5} วินาที · Cold / SV Off · median + MAD / IQR / scale floor · quarantine z&gt;{preview.selection.policy.profile_quarantine_z ?? 8} · threshold Q99.5 · persistence 3 นาทีติดกัน ไม่มีการเพิ่มโมเดลหรือเปลี่ยน threshold policy ในขั้นตอนนี้</p><p>{preview.reason_codes.join(" · ") || "ไม่พบข้อทบทวนตามเกณฑ์อัตโนมัติ ยังต้องตรวจกราฟก่อนอนุมัติ"}</p><code>Source digest: {preview.source_digest}</code></details>
      {current?.status === "READY" && <div className="ref-confirm">
        {!preview.can_build && <p role="alert">ข้อมูลยังไม่พร้อมสร้าง Candidate: Reference ต้องเหลืออย่างน้อย {preview.summary.min_reference_days} วัน / {preview.summary.min_reference_minutes} นาทีหลัง Quarantine และ Shadow ต้องผ่าน Gate ครบ 3 วัน / อย่างน้อย {preview.summary.min_shadow_minutes} นาที</p>}
        <label className="ref-check"><input type="checkbox" disabled={busy} checked={ack} onChange={e => setAck(e.target.checked)} />ฉันตรวจกราฟและช่วง Reference แล้ว ต้องการนำช่วงนี้ไปสร้าง Candidate (ยังไม่เปิดใช้งาน)</label>
        <label>บันทึกการทบทวน<textarea disabled={busy} value={reviewNote} maxLength={2000} onChange={e => setReviewNote(e.target.value)} placeholder="เหตุผลที่เลือกช่วงนี้ และข้อสังเกตที่ควรตรวจใน Shadow" /></label>
        <button className="ref-primary" disabled={needsPreview || outdatedPreview || !preview.can_build || !ack || reviewNote.trim().length < 3 || busy} onClick={() => build.mutate()}>2. ยืนยันช่วงและสร้าง Candidate + Shadow</button>
      </div>}
      {current?.result?.batch_id && <div className="ref-success" role="status"><CheckCircle2 size={20} /><div><strong>สร้าง Candidate และทดสอบ Shadow แล้ว · {current.result.candidate_status}</strong><p>ดูกราฟ Shadow และรายละเอียด Profile ด้านล่างก่อนอนุมัติ</p><button onClick={() => document.querySelector(".calibration-layout")?.scrollIntoView({ behavior: "smooth" })}>3. ไปตรวจผล Candidate</button></div></div>}
    </>}
  </section>;
}
