// Development-only source-backed preview; not included in the production entry.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Database, RefreshCw, SlidersHorizontal } from "lucide-react";
import { ReferenceReview } from "./components/ReferenceReview";
import "./styles.css";
import "./source-mysql-experiment.css";

type Inventory = {machine_number:string; record_count:number; first_time:string; last_time:string; origin:string};
type SourceContext = {host:string; schema:string; table:string; timezone:string; pressure_unit:string; experimental_schema:string; normal_analytics_schema:string; machines:Inventory[]};
type DayData = {rows:number; duplicate_timestamp_rows:number; occupied_minutes:number; median_positive_interval_seconds:number|null; strict_qualified_minutes:number; gate_reasons:Record<string,number>; points:Record<string,unknown>[]; raw_preview:Record<string,unknown>[]};
const base = import.meta.env.VITE_API_BASE_URL ?? "";
async function read<T>(url:string):Promise<T> {
  const r = await fetch(`${base}${url}`);
  if (!r.ok) { const error = await r.json().catch(()=>({detail:"เชื่อมต่อไม่สำเร็จ"})); throw new Error(error.detail ?? `HTTP ${r.status}`); }
  return r.json();
}
const clock = (v:unknown) => String(v).slice(11,16);
const localDate = (v:string) => v.replace("T"," ").slice(0,19);
function SourceChart({data,title,lines,unit}:{data:Record<string,unknown>[];title:string;lines:[string,string][];unit:string}) {
  return <article className="sql-chart"><h3>{title}</h3><small>{unit} · ค่าเฉลี่ยของแถวที่มีจริงในแต่ละนาที</small>
    <ResponsiveContainer width="100%" height={215}><LineChart data={data} margin={{top:15,right:15,left:4,bottom:0}}>
      <CartesianGrid stroke="#e4edf4" vertical={false}/><XAxis dataKey="stamp" ticks={[0,360,720,1080,1439].map(i=>String(data[i]?.stamp ?? ""))} tickFormatter={clock} minTickGap={30} tick={{fontSize:11}}/>
      <YAxis width={48} domain={["auto","auto"]} tick={{fontSize:11}}/>
      <Tooltip labelFormatter={v=>localDate(String(v))} formatter={(v:unknown,name:unknown)=>[typeof v === "number" ? v.toFixed(2):"—",String(name)]}/>
      {lines.map(([key,color])=><Line key={key} dataKey={key} name={key} stroke={color} strokeWidth={1.8} type="linear" connectNulls={false} dot={false} isAnimationActive={false}/>)}
    </LineChart></ResponsiveContainer><div className="sql-legend">{lines.map(([key,color])=><span key={key}><i style={{background:color}}/>{key}</span>)}</div>
  </article>;
}
function Experiment() {
  const [view,setView] = useState("source");
  const [machine,setMachine] = useState("MX080");
  const [module,setModule] = useState(6);
  const [day,setDay] = useState("2026-09-07");
  const [reviewer,setReviewer] = useState("");
  const [batch,setBatch] = useState("");
  const context = useQuery({queryKey:["sql-context"],queryFn:()=>read<SourceContext>("/api/v1/experiment/source-context"),refetchInterval:300000});
  const data = useQuery({queryKey:["sql-day",machine,module,day],queryFn:()=>read<DayData>(`/api/v1/experiment/source-day?machine=${encodeURIComponent(machine)}&module=${module}&day=${day}`),enabled:!!day && view==="source",retry:false});
  const selected = context.data?.machines.find(m=>m.machine_number===machine);
  return <div className="sql-experiment"><aside className="sql-sidebar"><img src="/assets/adi-logo.png" alt="Analog Devices"/><strong>OPERATION</strong><span>MySQL experiment</span>
    <nav><button className={view==="source"?"chosen":""} onClick={()=>setView("source")}><Database size={19}/>ข้อมูลต้นทาง MySQL</button><button className={view==="reference"?"chosen":""} onClick={()=>setView("reference")}><SlidersHorizontal size={19}/>ทดลอง Calibration</button></nav>
    <p>อ่านตารางต้นทางจริง<br/>ผลทดลองแยกฐาน<br/>ไม่เปิด Active / Alert</p>
  </aside><main className="sql-main"><header className="sql-heading"><div><small>HONTECH HT9046-MX · LOCAL EXPERIMENT</small><h1>{view==="source"?"ข้อมูล Compressor จาก MySQL":"ทบทวน Reference ก่อนสร้าง Candidate"}</h1></div><button className="button secondary" onClick={()=>{context.refetch();data.refetch();}}><RefreshCw size={16}/>อ่านใหม่</button></header>
    <div className="sql-source-note"><strong>{context.data ? `${context.data.host} · ${context.data.schema}.${context.data.table}` : "กำลังอ่านชื่อแหล่งข้อมูล…"}</strong><span>ข้อมูลย้อนหลัง/ข้อมูลทดสอบบนเครื่องนี้ ไม่ใช่ feed สดจาก Server 10.195.17.73 · เวลา {context.data?.timezone ?? "—"}</span><span>เก็บงานทดลองใน {context.data?.experimental_schema ?? "—"}; ฐาน Analytics เดิม {context.data?.normal_analytics_schema ?? "—"} ไม่ถูกแก้ไข</span></div>
    {context.error && <p role="alert" className="form-error">{context.error.message}</p>}
    <section className="sql-controls"><label>เครื่อง<select value={machine} onChange={e=>{setMachine(e.target.value);setBatch("");}}>{!context.data?.machines.length && <option>MX080</option>}{context.data?.machines.map(m=><option key={m.machine_number} value={m.machine_number}>{m.machine_number} · {m.record_count.toLocaleString()} rows{m.origin==="known local fixture"?" · MOCK":""}</option>)}</select></label><label>โมดูล<select value={module} onChange={e=>{setModule(Number(e.target.value));setBatch("");}}>{Array.from({length:8},(_,i)=><option key={i+1} value={i+1}>Module {i+1}</option>)}</select></label>{view==="source" && <label>วันที่<input type="date" value={day} onChange={e=>setDay(e.target.value)}/></label>}</section>
    {selected && <p className="sql-availability">ข้อมูลในตาราง: {localDate(selected.first_time)} ถึง {localDate(selected.last_time)} ({context.data?.timezone}) · {selected.origin==="known local fixture"?"ข้อมูลจำลองที่ทราบจาก QA เดิม":"มีข้อมูลนำเข้าย้อนหลัง/ส่วนเพิ่มเติมที่ยังไม่ยืนยัน provenance"}</p>}
    {view==="reference" ? <><ReferenceReview key={`${machine}-${module}`} machine={machine} module={module} reviewer={reviewer} onReviewer={setReviewer} onModule={setModule} onBuilt={setBatch}/>{batch && <p>Candidate batch {batch} · เฉพาะฐานทดลอง ไม่ใช่ Active</p>}</> : <>
      {data.isFetching && <p role="status">กำลัง SELECT ข้อมูลของวันจาก MySQL…</p>}{data.error && <p role="alert" className="form-error">{data.error.message}</p>}
      {data.data && <><div className="sql-metrics"><article><small>แถวข้อมูลจริง · {day}</small><strong>{data.data.rows.toLocaleString()}</strong><span>{machine} / M{module}</span></article><article><small>ระยะห่าง timestamp มัธยฐาน</small><strong>{data.data.median_positive_interval_seconds ?? "—"} s</strong><span>ไม่นับ timestamp ซ้ำ</span></article><article><small>นาทีที่มีข้อมูล</small><strong>{data.data.occupied_minutes.toLocaleString()} / 1,440</strong><span>แถว timestamp ซ้ำ {data.data.duplicate_timestamp_rows}</span></article><article><small>ผ่าน strict 1m Gate</small><strong>{data.data.strict_qualified_minutes.toLocaleString()}</strong><span>≥57 occupied seconds; state Cold</span></article></div>
      <div className="sql-warning">กราฟนี้แสดง telemetry เท่านั้น ไม่ใช่ Anomaly Score หรือผลจาก Active Profile. {data.data.strict_qualified_minutes===0?"ข้อมูลวันที่เลือกยังไม่ผ่าน Gate สำหรับสร้าง Profile ราย 1 นาทีจากวินาทีจริง; ไม่ขยายข้อมูลรายนาทีเป็นวินาทีเทียม.":"ผ่าน Gate ไม่ได้หมายความว่ายืนยัน healthy แล้ว."} Pressure: {context.data?.pressure_unit}. ช่วง Manual/Valve change ยังอยู่ในข้อมูลต้นทาง.</div>
      {data.data.rows>0 ? <div className="sql-chart-grid"><SourceChart data={data.data.points} title={`${machine} / M${module} · ${day} · High pressure`} lines={[["hp1","#e39239"],["hp2","#246bb8"]]} unit={context.data?.pressure_unit ?? "source unit"}/><SourceChart data={data.data.points} title={`${machine} / M${module} · ${day} · Low pressure`} lines={[["lp1","#3e81ab"],["lp2","#119a93"]]} unit={context.data?.pressure_unit ?? "source unit"}/><SourceChart data={data.data.points} title="Compressor / Discharge-pipe temperature" lines={[["temphi","#d87851"],["templo","#558fc3"]]} unit="source unit (ยังไม่ยืนยันหน่วย)"/><SourceChart data={data.data.points} title="Expansion Valve command" lines={[["valve","#7b65b4"]]} unit="count"/></div>:<p className="empty-state">ไม่มีแถวข้อมูลในวันและเครื่องที่เลือก ไม่ใช่ผลว่าเครื่องปกติ</p>}
      <details className="sql-details"><summary>ดูแถวต้นทาง 10 แถวแรก และเหตุผลที่ไม่ผ่าน Gate</summary><p>ผล strict Gate: {Object.entries(data.data.gate_reasons).map(([key,n])=>`${key}: ${n}`).join(" · ") || "ไม่มี window"}</p><div className="sql-table"><table><thead><tr>{Object.keys(data.data.raw_preview[0]??{}).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{data.data.raw_preview.map((r,i)=><tr key={i}>{Object.values(r).map((v,j)=><td key={j}>{v==null?"—":String(v)}</td>)}</tr>)}</tbody></table></div></details></>}
    </>}
  </main></div>;
}
const root = (import.meta.hot?.data.root as ReturnType<typeof createRoot> | undefined) ?? createRoot(document.getElementById("root")!);
if (import.meta.hot) import.meta.hot.data.root = root;
root.render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{refetchOnWindowFocus:false}}})}><Experiment/></QueryClientProvider>);
