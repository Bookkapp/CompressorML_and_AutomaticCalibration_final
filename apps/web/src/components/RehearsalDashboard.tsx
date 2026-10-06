import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Point = {
  window: { window_start: string; window_end: string; machine_number: string; module: number; features: Record<string, number> | null };
  score: { status: string; reason: string; primary_score: number | null; primary_threshold: number | null; primary_persistent_flag: boolean | null;
    robust_z?: Record<string, number> | null; dominant_feature?: string | null; dominant_z?: number | null };
  available_at: string;
};
type Episode = { episode_id: string; episode_group_id: string; first_deviation_at: string; detected_at: string;
  status: string; close_reason: string | null; closed_at: string | null; peak_score_ratio: number;
  machine_number: string; module: number };
type Response = { mode: string; run_id: string; source_timezone: string; source_cursor: number; revision: number;
  points: Point[]; episodes?: Episode[] };

export function RehearsalDashboard({ runId }: { runId: string }) {
  const query = useQuery<Response>({ queryKey: ["rehearsal", runId], refetchInterval: 300_000,
    queryFn: async () => {
      const base = import.meta.env.VITE_API_BASE_URL ?? "";
      const response = await fetch(`${base}/api/v1/rehearsal/${encodeURIComponent(runId)}/points`);
      if (!response.ok) throw new Error("เปิดข้อมูลทดสอบไม่ได้ — ตรวจ run ID และ local rehearsal setting");
      return response.json();
    } });
  if (query.isPending) return <main style={{ padding: 32 }}>กำลังอ่านผลจาก MySQL…</main>;
  if (query.error) return <main style={{ padding: 32 }}>{query.error.message}</main>;
  const data = query.data!;
  const points = data.points;
  if (!points.length) return <main style={{ padding: 32 }}>ยังไม่มีหน้าต่างข้อมูลใน run นี้</main>;
  // Source-local timestamps are decoded using the declared IANA timezone in the API.
  // This local fixture is Bangkok; reject other zones instead of silently guessing offsets.
  if (data.source_timezone !== "Asia/Bangkok") return <main>QA view currently supports Asia/Bangkok only</main>;
  const stamp = (s: string) => Date.parse(s + "+07:00");
  const byTime = new Map(points.map(p => [stamp(p.window.window_start), p]));
  const rows: { t: number; ratio: number | null; flag: boolean; reason: string; available: string; [key: string]: string | number | boolean | null }[] = [];
  for (let t = stamp(points[0].window.window_start); t <= stamp(points[points.length - 1].window.window_start); t += 60_000) {
    const p = byTime.get(t);
    rows.push({ t, ...p?.window.features,
      ratio: p?.score.status === "SCORED" && p.score.primary_threshold ? p.score.primary_score! / p.score.primary_threshold : null,
      flag: p?.score.primary_persistent_flag === true,
      reason: p?.score.reason ?? "MISSING_MINUTE", available: p?.available_at ?? "—" });
  }
  const timeLabel = (v: number) => new Date(v).toLocaleTimeString("th-TH", { timeZone: data.source_timezone, hour: "2-digit", minute: "2-digit" });
  const colors = ["#1677b8", "#e87528", "#6a52a3", "#00a096"];
  const names: Record<string,string> = {hp1:"Hp_1st",lp1:"Lp_1st",hp2:"Hp_2nd",lp2:"Lp_2nd",dp1:"ΔP CP1",dp2:"ΔP CP2",temphi:"TempHi",templo:"TempLo",valve:"Valve",ratio:"Score / threshold"};
  const contributors = (p: Point | undefined, fields: string[]) => {
    if (p?.score.status !== "SCORED" || !p.score.primary_threshold || !Number.isFinite(p.score.primary_threshold)) return [];
    return Object.entries(p.score.robust_z ?? {}).filter(([f,z]) => typeof z === "number" && Number.isFinite(z)
      && (fields.includes("ratio") || fields.includes(f)) && Math.abs(z) >= p.score.primary_threshold!)
      .sort((a,b)=>Math.abs(b[1])-Math.abs(a[1]));
  };
  const charts = [
    { title: "Pressure — CP1 / CP2", unit: "source pressure units", fields: ["hp1", "lp1", "hp2", "lp2"] },
    { title: "Pressure differential — HP − LP", unit: "source pressure units", fields: ["dp1", "dp2"] },
    { title: "Temperature", unit: "source temperature units", fields: ["temphi", "templo"] },
    { title: "Expansion Valve", unit: "controller command", fields: ["valve"] },
    { title: "Deviation / threshold — ≥1 meets the profile threshold", unit: "ratio", fields: ["ratio"] }
  ];
  return <main style={{ maxWidth: 1200, margin: "auto", padding: 28, background: "#f5f8fb", color: "#18212b" }}>
    <h1>MX080 · Module 6 — Local replay</h1>
    <p>ข้อมูลรายวินาที → หน้าต่าง 1 นาที → รับทุก 5 นาที · {data.source_timezone}</p>
    <p style={{ background: "#fff1db", padding: 16 }}>ทดสอบเท่านั้น: ใช้ candidate อ้างอิง 4 วัน ไม่ใช่ Active Profile หรือผลวินิจฉัยสาเหตุ</p>
    <p>แดงบนกราฟตัวแปร = ตัวแปรในกราฟนั้นที่ |z| ≥ threshold ระหว่างผลรวมเตือนต่อเนื่อง · ผลรวมอยู่ที่กราฟคะแนน · Contributor ไม่ใช่สาเหตุความเสียหาย · เส้นขาด = ไม่มีข้อมูล · สีขาวไม่ยืนยันว่าเครื่องปกติ</p>
    <p>Run: {data.run_id} · Cursor: {data.source_cursor} · Checkpoint revision: {data.revision}</p>
    <section style={{ padding: 20, background: "white", borderRadius: 12, marginBottom: 20 }}>
      <h2>Episode archive — สำหรับ QA ไม่ใช่ Assigned Work</h2>
      <p>ผู้ใช้หน้างานรายงานและบันทึก Service Log ที่ Dashboard หลัก ไม่ต้องสร้างรายงานซ้ำที่ Operation</p>
      {(data.episodes ?? []).filter(e => e.machine_number === points[0].window.machine_number && e.module === points[0].window.module).map(e => <article key={e.episode_id}>
        <h3>{e.status} · peak / threshold {e.peak_score_ratio.toFixed(2)}</h3>
        <p>เริ่มเบี่ยงเบน {e.first_deviation_at} · ผลพร้อมเปิด Episode {e.detected_at}</p>
        <p>สิ้นสุด {e.closed_at ?? "ยังไม่ยืนยัน recovery"} · เหตุผล {e.close_reason ?? "—"}</p>
        <small>Episode {e.episode_id} · Group {e.episode_group_id}</small>
        <p><a href={`${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1/rehearsal/${encodeURIComponent(runId)}/episodes/${encodeURIComponent(e.episode_id)}/raw`} target="_blank" rel="noreferrer">ดู Raw evidence JSON (สูงสุด 20,000 แถว; ตรวจ truncated/coverage)</a></p>
      </article>)}
      {!(data.episodes?.length) && <p>ยังไม่มี persistent Episode ในช่วงนี้</p>}
    </section>
    {charts.map(chart => <section key={chart.title} style={{ marginBottom: 20, padding: 20, background: "white", borderRadius: 12 }}>
      <h2 style={{ fontSize: 18 }}>{chart.title}</h2><p>{chart.unit}</p>
      <p>{chart.fields.includes("ratio") ? "ผลเตือนรวม; ชี้เวลาบนกราฟเพื่อดูตัวแปรสูงสุด" : `ตัวแปรที่เกินเกณฑ์ระหว่างผลเตือนรวมในช่วงนี้: ${[...new Set(points.filter(p=>p.score.primary_persistent_flag===true).flatMap(p=>contributors(p,chart.fields).map(([f])=>names[f] ?? f)))].join(", ") || "ไม่มี / หลักฐาน z ไม่พร้อม"}`}</p>
      <ResponsiveContainer width="100%" height={210}>
        <LineChart data={rows} margin={{ left: 10, right: 20 }}>
          <CartesianGrid stroke="#e6edf2" vertical={false} />
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={timeLabel} />
          <YAxis width={65} />
          <Tooltip content={({active,label,payload}) => {
            if (!active) return null;
            const p=byTime.get(Number(label));
            return <div style={{background:"white",border:"1px solid #d7e2eb",padding:12,maxWidth:300,overflowWrap:"anywhere"}}>
              <strong>{timeLabel(Number(label))} UTC+7</strong>
              {payload?.map(item=><div key={String(item.dataKey)}>{item.name}: {typeof item.value==="number" ? item.value.toFixed(2) : "—"}</div>)}
              <p>เกณฑ์ |z| ≥ {p?.score.primary_threshold?.toFixed(2) ?? "—"}<br/>ตัวแปรเกินเกณฑ์ในกราฟนี้: {contributors(p,chart.fields).map(([f,z])=>`${names[f] ?? f} (${z>0?'+':''}${z.toFixed(2)})`).join(", ") || "ไม่มี / หลักฐาน z ไม่พร้อม"}</p>
              <p>สูงสุด: {p?.score.dominant_feature ? names[p.score.dominant_feature] ?? p.score.dominant_feature : "—"} · z={p?.score.dominant_z?.toFixed(2) ?? "—"}</p>
            </div>;
          }} />
          {chart.fields[0] === "ratio" && <ReferenceLine y={1} stroke="#64748b" strokeDasharray="4 4" />}
          {rows.filter(r => r.flag && (chart.fields.includes("ratio") || contributors(byTime.get(r.t),chart.fields).length>0)).map(r => <ReferenceArea key={r.t} x1={r.t} x2={r.t + 60_000} fill="#df4d4d" fillOpacity={0.12} strokeOpacity={0} />)}
          {chart.fields.map((field, i) => <Line key={field} dataKey={field} name={names[field]} stroke={colors[i]} dot={false} strokeWidth={1.7} connectNulls={false} isAnimationActive={false} />)}
        </LineChart>
      </ResponsiveContainer>
      <p>{chart.fields.map((f, i) => <span key={f} style={{ color: colors[i], marginRight: 24 }}>{names[f]}</span>)}</p>
    </section>)}
    <h2>ตรวจเวลาและเหตุผลรายนาที</h2>
    <div style={{ maxHeight: 240, overflow: "auto" }}><table><thead><tr><th>Window start</th><th>Result available</th><th>Status</th><th>Persistent</th><th>Reason</th></tr></thead>
      <tbody>{points.map(p => <tr key={p.window.window_start}><td>{p.window.window_start}</td><td>{p.available_at}</td><td>{p.score.status}</td><td>{String(p.score.primary_persistent_flag)}</td><td>{p.score.reason}</td></tr>)}</tbody>
    </table></div>
  </main>;
}
