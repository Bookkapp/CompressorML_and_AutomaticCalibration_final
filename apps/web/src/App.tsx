import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity, AlertTriangle, BookOpen, Bot, CheckCircle2, ChevronRight,
  CircleGauge, Clock3, Cpu, Database, Factory, History,
  Radio, RefreshCw, Search, ShieldCheck, SlidersHorizontal,
  Thermometer, Waves, Zap
} from "lucide-react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import { api } from "./api";
import { CorrelationHeatmap } from "./components/CorrelationHeatmap";
import { RehearsalDashboard } from "./components/RehearsalDashboard";
import { AutomaticCalibration } from "./components/AutomaticCalibration";
import { ContextCalibration } from "./components/ContextCalibration";
import { EventHistory } from "./components/EventHistory";
import { FleetModelManagement } from "./components/FleetModelManagement";
import { humanStatus } from "./components/CalibrationEvidence";
import { approvalReason } from "./calibration-review";
import type {
  ActiveProfile,
  CalibrationProfile,
  CalibrationShadowPoint,
  FeatureBaselineStat,
  TimelinePoint
} from "./types";

type View = "calibration" | "profiles" | "events" | "fleet";

const timeLabel = (value: string | number) =>
  new Intl.DateTimeFormat("th-TH", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
    .format(new Date(value));

function StatusPill({ children, tone = "blue" }: { children: React.ReactNode; tone?: "teal" | "blue" | "amber" | "red" | "grey" | "green" }) {
  return <span className={`pill pill-${tone}`}>{typeof children==="string"?humanStatus(children):children}</span>;
}

function Kpi({ label, value, note, icon: Icon, tone = "blue" }: { label: string; value: string | number; note: string; icon: typeof Activity; tone?: string }) {
  return (
    <article className={`kpi-card kpi-${tone}`}>
      <div className={`icon-box icon-${tone}`}><Icon size={19} /></div>
      <div><p>{label}</p><strong>{value}</strong><span>{note}</span></div>
    </article>
  );
}

function SignalChart({ points, kind, height = 260 }: { points: TimelinePoint[]; kind: "pressure" | "temperature" | "valve" | "score"; height?: number }) {
  const persistent = points.filter(p => p.persistent_flag);
  const start = persistent.at(0)?.event_time;
  const end = persistent.at(-1)?.event_time;
  const common = {
    data: points,
    syncId: "module-timeline",
    margin: { top: 10, right: 18, bottom: 2, left: 0 }
  };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart {...common}>
        <CartesianGrid stroke="#e9f0f6" vertical={false} />
        <XAxis dataKey="event_time" tickFormatter={timeLabel} minTickGap={48} tick={{ fill: "#718096", fontSize: 11 }} />
        <YAxis tick={{ fill: "#718096", fontSize: 11 }} width={44} />
        <Tooltip labelFormatter={(label) => label == null ? "" : timeLabel(String(label))} contentStyle={{ borderRadius: 12, borderColor: "#d9e7f3" }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
        {start && end && <ReferenceArea x1={start} x2={end} fill="#e45757" fillOpacity={0.08} />}
        {kind === "pressure" && <>
          <ReferenceArea y1={180} y2={230} fill="#2c78b8" fillOpacity={0.08} />
          <Line type="monotone" dataKey="hp1" name="Hp 1st" stroke="#2c78b8" dot={false} strokeWidth={1.7} connectNulls={false} />
          <Line type="monotone" dataKey="lp1" name="Lp 1st" stroke="#80acd0" dot={false} strokeWidth={1.4} connectNulls={false} />
          <Line type="monotone" dataKey="hp2" name="Hp 2nd" stroke="#0d3d68" dot={false} strokeWidth={2.1} connectNulls={false} />
          <Line type="monotone" dataKey="lp2" name="Lp 2nd" stroke="#46a9a3" dot={false} strokeWidth={1.6} connectNulls={false} />
        </>}
        {kind === "temperature" && <>
          <Line type="monotone" dataKey="temp_high" name="Temp High" stroke="#e1784f" dot={false} strokeWidth={2} connectNulls={false} />
          <Line type="monotone" dataKey="temp_low" name="Temp Low" stroke="#50a4cf" dot={false} strokeWidth={2} connectNulls={false} />
        </>}
        {kind === "valve" && <>
          <Area type="stepAfter" dataKey="valve" name="Valve command" stroke="#7159b7" fill="#7159b7" fillOpacity={0.12} connectNulls={false} />
        </>}
        {kind === "score" && <>
          <Area type="monotone" dataKey="anomaly_score" name="Anomaly score" stroke="#2c78b8" fill="#2c78b8" fillOpacity={0.12} connectNulls={false} />
          <Line type="stepAfter" dataKey="threshold" name="Threshold" stroke="#d65b5b" strokeDasharray="5 4" dot={false} />
          {points.find(p => p.threshold)?.threshold != null && <ReferenceLine y={points.find(p => p.threshold)!.threshold!} stroke="#d65b5b" strokeDasharray="5 4" />}
        </>}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function CalibrationShadowChart({ points }: { points: CalibrationShadowPoint[] }) {
  const data = points.map(point => ({ ...point, normal_score: point.raw_flag ? null : point.deviation_score, flagged_score: point.raw_flag ? point.deviation_score : null }));
  return <ResponsiveContainer width="100%" height={280}><ComposedChart data={data} margin={{ top: 10, right: 20, bottom: 2, left: 0 }}>
    <CartesianGrid stroke="#e9f0f6" vertical={false} />
    <XAxis dataKey="event_time" tickFormatter={timeLabel} minTickGap={54} tick={{ fill: "#718096", fontSize: 11 }} />
    <YAxis tick={{ fill: "#718096", fontSize: 11 }} width={44} />
    <Tooltip labelFormatter={label => label == null ? "" : timeLabel(String(label))} contentStyle={{ borderRadius: 12, borderColor: "#d9e7f3" }} />
    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
    <Area type="linear" dataKey="normal_score" name="Qualified / below threshold" stroke="#3e9a79" fill="#3e9a79" fillOpacity={.12} connectNulls={false} isAnimationActive={false} />
    <Line type="linear" dataKey="deviation_score" name="Minute deviation (all scored)" stroke="#8299aa" strokeWidth={1} dot={false} connectNulls={false} isAnimationActive={false} />
    <Line type="linear" dataKey="flagged_score" name="Above candidate threshold" stroke="#d65757" strokeWidth={2.2} dot={false} connectNulls={false} isAnimationActive={false} />
    <Line type="stepAfter" dataKey="threshold_value" name="Candidate threshold" stroke="#b56b27" strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
  </ComposedChart></ResponsiveContainer>;
}

function profileTone(status: string): "green" | "amber" | "red" | "grey" | "blue" {
  if (status === "ACTIVE_FROZEN" || status === "READY_FOR_APPROVAL") return "green";
  if (status === "REVIEW_REQUIRED" || status === "REJECTED") return "red";
  if (status === "INSUFFICIENT_DATA" || status === "CANDIDATE_PROFILE") return "amber";
  return "blue";
}

function pressureUnit(profile?: { validation: Record<string, unknown> } | null): string {
  const unit = profile?.validation?.source_pressure_unit;
  return typeof unit === "string" && unit.trim() ? unit.trim() : "source unit";
}

function BaselineRow({ name, stat, unit = "source unit" }: { name: string; stat?: FeatureBaselineStat; unit?: string }) {
  if (!stat) {
    return (
      <div className="baseline-row">
        <span className="name">{name}</span>
        <div className="vals"><span className="mean">—</span></div>
      </div>
    );
  }
  return (
    <div className="baseline-row">
      <span className="name">{name}</span>
      <div className="vals">
        <span className="mean">{stat.mean.toFixed(1)} {unit}</span>
        <span className="range">P10-P90: [{stat.p10.toFixed(1)} – {stat.p90.toFixed(1)}] · σ={stat.std.toFixed(1)}</span>
      </div>
    </div>
  );
}

function CalibrationPanel() {
  const [selectedProfile, setSelectedProfile] = useState<CalibrationProfile | null>(null);
  const [targetMachine, setTargetMachine] = useState<string>("ALL");
  const [activeModule, setActiveModule] = useState<number>(1);
  const [reviewBatchId, setReviewBatchId] = useState<string | null>(null);
  const [legacyCalibration,setLegacyCalibration] = useState(false);

  const [approverId, setApproverId] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  const machinesQuery = useQuery({ queryKey: ["source-machines"], queryFn: api.sourceMachines, refetchInterval: 60_000 });
  const batches = useQuery({ queryKey: ["calibration-batches"], queryFn: api.calibrationBatches, refetchInterval: 5 * 60_000 });
  const activeProfilesQuery = useQuery({ queryKey: ["active-profiles"], queryFn: api.activeProfiles, refetchInterval: 30_000 });

  const activeProfiles = activeProfilesQuery.data ?? [];

  const batch = batches.data?.find(b => b.batch_id === reviewBatchId) ?? batches.data?.at(0);
  const selectedBatchId = reviewBatchId ?? batch?.batch_id;
  const profiles = useQuery({
    queryKey: ["calibration-profiles", selectedBatchId],
    queryFn: () => api.calibrationProfiles(selectedBatchId!),
    enabled: Boolean(selectedBatchId) && legacyCalibration
  });

  const normalizeMach = (m?: string | null) => {
    if (!m) return "";
    const upper = m.toUpperCase().trim();
    const digits = upper.replace(/^MX/, "").replace(/^0+/, "") || "0";
    return digits;
  };

  const isSameMachine = (a?: string | null, b?: string | null) => {
    if (!a || !b) return false;
    if (a.toUpperCase() === b.toUpperCase()) return true;
    return normalizeMach(a) === normalizeMach(b);
  };

  const getMachineActiveCount = (machNumber: string) => {
    return activeProfiles.filter(ap => isSameMachine(ap.machine_number, machNumber)).length;
  };

  // Filter profiles based on selected machine
  const filteredProfiles = useMemo(() => {
    if (!profiles.data) return [];
    if (targetMachine === "ALL") return profiles.data;
    return profiles.data.filter(p => isSameMachine(p.machine_number, targetMachine));
  }, [profiles.data, targetMachine]);

  // Selected profile matching active module or direct selection
  const selected = useMemo(() => {
    if (selectedProfile && (targetMachine === "ALL" || isSameMachine(selectedProfile.machine_number, targetMachine))) {
      return filteredProfiles.find(profile => profile.profile_id === selectedProfile.profile_id) ?? null;
    }
    const matchMod = filteredProfiles.find(p => p.module === activeModule);
    return matchMod ?? (targetMachine === "ALL" ? filteredProfiles[0] : null) ?? null;
  }, [selectedProfile, filteredProfiles, targetMachine, activeModule]);

  // Find active profile for the currently selected machine & module
  const currentActiveForMod = useMemo(() => {
    if (!selected) return null;
    return activeProfiles.find(
      ap => isSameMachine(ap.machine_number, selected.machine_number) && ap.module === selected.module
    );
  }, [activeProfiles, selected]);

  // Compute automation pipeline stage (1-6)
  const currentStage = useMemo(() => {
    if (!selected) return 1;
    if (selected.profile_status === "ACTIVE_FROZEN") return 6;
    if (selected.profile_status === "READY_FOR_APPROVAL" || selected.profile_status === "FLEET_PROVISIONAL") return 5;
    if (selected.profile_status === "SHADOW_FLAGGED" || selected.profile_status === "REVIEW_REQUIRED") return 4;
    if (selected.profile_status === "INSUFFICIENT_DATA") return 2;
    return 3;
  }, [selected, currentActiveForMod]);

  const shadow = useQuery({
    queryKey: ["calibration-shadow", selected?.profile_id],
    queryFn: () => api.calibrationShadow(selected!.profile_id),
    enabled: Boolean(selected) && legacyCalibration
  });

  const review = useMutation({
    mutationFn: (decision: "APPROVE" | "REJECT") => api.reviewCalibration(selected!.profile_id, approverId, {
      idempotency_key: `${selected!.profile_id}-${decision}-${approverId}-${Date.now()}`,
      decision,
      review_note: reviewNote,
    }),
    onSuccess: () => {
      batches.refetch();
      profiles.refetch();
      activeProfilesQuery.refetch();
    },
  });

  const approveAllMutation = useMutation({
    mutationFn: () => api.approveMachineAll(targetMachine, approverId, { batch_id: selectedBatchId, review_note: reviewNote }),
    onSuccess: () => {
      batches.refetch();
      profiles.refetch();
      activeProfilesQuery.refetch();
    },
  });

  useEffect(() => {
    review.reset();
    approveAllMutation.reset();
    setReviewNote("");
  }, [targetMachine, activeModule, selectedBatchId, selected?.profile_id]);

  const isDemo = Boolean(batch?.batch_status?.startsWith("DEMO"));
  const canApprove = !isDemo && (
    selected?.profile_status === "READY_FOR_APPROVAL"
  );

  // Check Hp2 180-230 psi band for selected profile baseline
  const hp2Stat = selected?.statistics?.detailed_baseline?.hp2;
  const selectedPressureUnit = pressureUnit(selected);
  const isHp2InBand = selectedPressureUnit.toLowerCase() === "psi" && hp2Stat ? hp2Stat.mean >= 180 && hp2Stat.mean <= 230 : false;

  return (
    <section className="calibration-stack">
      {/* 1. Machine Discovery & Selection Section */}
      <section className="machine-selection-section">
        <div className="machine-selection-header">
          <h3><Factory size={16} /> Source Telemetry Machines ({machinesQuery.data?.length ?? 0})</h3>
          <p>เลือกเครื่องเพื่อตรวจสอบสถานะ Active Profile และขั้นตอนการทำ Calibration</p>
          <label className="calibration-machine-picker">เครื่องสำหรับ Calibration
            <select value={targetMachine} onChange={e=>{setTargetMachine(e.target.value);setActiveModule(1);setSelectedProfile(null);setReviewBatchId(null);}}>
              <option value="ALL">เลือกเครื่อง / ภาพรวมทั้งหมด</option>
              {machinesQuery.data?.map(m=><option key={m.machine_number} value={m.machine_number}>{m.machine_number}</option>)}
            </select>
          </label>
        </div>
        <details open={targetMachine==="ALL"} className="calibration-machine-catalog"><summary>ดูรายการเครื่องและสถานะทั้งหมด</summary>
        <div className="machine-cards-grid">
          <button
            type="button"
            className={`machine-select-card ${targetMachine === "ALL" ? "active" : ""}`}
            onClick={() => { setTargetMachine("ALL"); setSelectedProfile(null); }}
          >
            <div className="machine-card-head">
              <strong><Database size={15} /> All Fleet Machines</strong>
              <StatusPill tone="blue">{profiles.data?.length ?? 0} Profiles</StatusPill>
            </div>
            <div className="machine-card-meta">
              <span>ภาพรวมทุกเครื่องจักรในระบบ</span>
            </div>
            <div className="machine-card-footer">
              <span>{machinesQuery.data?.length ?? 0} Discovered</span>
              <span style={{ color: targetMachine === "ALL" ? "var(--teal)" : "var(--muted)" }}>
                {targetMachine === "ALL" ? "Selected ✓" : "Fleet View →"}
              </span>
            </div>
          </button>

          {machinesQuery.data?.map(m => {
            const isSelected = isSameMachine(targetMachine, m.machine_number);
            const activeCount = getMachineActiveCount(m.machine_number);
            const machineProfiles = profiles.data?.filter(p => isSameMachine(p.machine_number, m.machine_number)) ?? [];
            const readyCount = machineProfiles.filter(p => p.profile_status === "READY_FOR_APPROVAL" || p.profile_status === "ACTIVE_FROZEN").length;
            const rows = m.record_count ?? m.row_count;
            const lastTime = m.latest_recorded_at ?? m.last_event;
            return (
              <button
                key={m.machine_number}
                type="button"
                className={`machine-select-card ${isSelected ? "active" : ""}`}
                onClick={() => { setTargetMachine(m.machine_number); setSelectedProfile(null); }}
              >
                <div className="machine-card-head">
                  <strong><Cpu size={15} /> {m.machine_number.startsWith("MX") ? m.machine_number : `MX${m.machine_number}`}</strong>
                  {activeCount > 0 ? (
                    <StatusPill tone="green">
                      <span className="pulse-dot" style={{ width: 6, height: 6, background: "var(--green)" }} />
                      {activeCount}/8 Active
                    </StatusPill>
                  ) : readyCount > 0 ? (
                    <StatusPill tone="blue">
                      {readyCount}/8 Ready
                    </StatusPill>
                  ) : (
                    <StatusPill tone="amber">
                      Needs Calib
                    </StatusPill>
                  )}
                </div>
                <div className="machine-card-meta">
                  <span><strong>{rows == null ? "—" : rows.toLocaleString()}</strong> rows telemetry</span>
                  {lastTime && (
                    <span style={{ display: "block", marginTop: "2px", fontSize: "9.5px" }}>
                      {timeLabel(lastTime)}
                    </span>
                  )}
                </div>
                <div className="machine-card-footer">
                  <span>HT-9046MX · 8-Mod</span>
                  <span style={{ color: isSelected ? "var(--teal)" : "var(--muted)" }}>
                    {isSelected ? "Selected ✓" : "Inspect →"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
        </details>
      </section>

      {targetMachine!=="ALL"&&<div className="context-actions"><button onClick={()=>setLegacyCalibration(v=>!v)}>{legacyCalibration?"ใช้ Calibration ตามสภาวะ":"เปิด Calibration รุ่นเดิม"}</button></div>}
      {targetMachine!=="ALL"&&!legacyCalibration&&<ContextCalibration key={targetMachine} machine={targetMachine} module={activeModule} reviewer={approverId} onReviewer={setApproverId} onModule={setActiveModule}/>}
      {targetMachine === "ALL" ? <section className="panel" style={{ padding: 20 }}><h2>เริ่มสร้าง Profile</h2><p>เลือกเครื่องด้านบน แล้วระบบจะเตรียม Candidate แยกทุกโมดูลให้ตรวจสอบ</p></section> : legacyCalibration&&
        <AutomaticCalibration key={targetMachine} machine={targetMachine} module={activeModule}
          reviewer={approverId} onReviewer={setApproverId} onModule={value => { setActiveModule(value); setSelectedProfile(null); }}
          onBuilt={id => { setReviewBatchId(id); setSelectedProfile(null); batches.refetch(); }} />}
      {legacyCalibration&&<>
      {batches.data && batches.data.length > 0 && <label className="manual-calib-bar">รอบ Candidate ที่กำลังตรวจ
        <select value={selectedBatchId ?? ""} onChange={e => { setReviewBatchId(e.target.value); setSelectedProfile(null); }}>
          {batches.data.map(b => <option key={b.batch_id} value={b.batch_id}>{b.batch_id.slice(0,8)} · {b.shadow_start.slice(0,10)} → {b.shadow_end.slice(0,10)} · {b.profile_count} profiles</option>)}
        </select>
      </label>}

      {/* 3. Automation Pipeline Stepper */}
      <details className="panel" style={{ padding: 16 }}><summary>สถานะใน Data Pipeline ของ Candidate ที่เลือก</summary>
      <section className="automation-stepper">
        <div className={`stepper-step ${currentStage >= 1 ? "completed" : "active"}`}>
          <div className="step-number">1</div>
          <div className="step-info">
            <strong>1. Telemetry Ingestion</strong>
            <small>MySQL Stream</small>
          </div>
        </div>
        <div className={`stepper-step ${currentStage >= 2 ? "completed" : currentStage === 1 ? "active" : ""}`}>
          <div className="step-number">2</div>
          <div className="step-info">
            <strong>2. State Gate</strong>
            <small>Cold Run + SV Off</small>
          </div>
        </div>
        <div className={`stepper-step ${currentStage >= 3 ? "completed" : currentStage === 2 ? "active" : ""}`}>
          <div className="step-number">3</div>
          <div className="step-info">
            <strong>3. Baseline & Heatmap</strong>
            <small>Robust Envelopes</small>
          </div>
        </div>
        <div className={`stepper-step ${currentStage >= 4 ? "completed" : currentStage === 3 ? "active" : ""}`}>
          <div className="step-number">4</div>
          <div className="step-info">
            <strong>4. 3-Day Shadow</strong>
            <small>Disjoint historical holdout</small>
          </div>
        </div>
        <div className={`stepper-step ${currentStage >= 5 ? "completed" : currentStage === 4 ? "active" : ""}`}>
          <div className="step-number">5</div>
          <div className="step-info">
            <strong>5. Candidate Review</strong>
            <small>Human Approval Gate</small>
          </div>
        </div>
        <div className={`stepper-step ${currentStage >= 6 ? "completed" : currentStage === 5 ? "active" : ""}`}>
          <div className="step-number">6</div>
          <div className="step-info">
            <strong>6. Active Frozen</strong>
            <small>Production Profile</small>
          </div>
        </div>
      </section>
      </details>

      {/* 4. 8-Module Calibration Status & Baseline Matrix */}
      <section className="module-matrix-section">
        <div className="module-matrix-header">
          <h3><SlidersHorizontal size={15} /> 8-Module Calibration Status & Baseline Matrix ({targetMachine === "ALL" ? "All Machines" : targetMachine})</h3>
          <p>คลิกเลือกโมดูลเพื่อดูค่า Envelope, Correlation Heatmap และอนุมัติโปรไฟล์</p>
        </div>
        <div className="module-matrix-grid">
          {[1, 2, 3, 4, 5, 6, 7, 8].map(modNum => {
            const prof = filteredProfiles.find(p => p.module === modNum);
            const activeForMod = activeProfiles.find(ap => isSameMachine(ap.machine_number, targetMachine) && ap.module === modNum);
            const isSelected = activeModule === modNum;
            const hp2Mean = prof?.statistics?.detailed_baseline?.hp2?.mean;
            const dp2Mean = prof?.statistics?.detailed_baseline?.dp2?.mean;
            const unit = pressureUnit(prof);
            const inBand = unit.toLowerCase() === "psi" && hp2Mean != null && hp2Mean >= 180 && hp2Mean <= 230;

            return (
              <div
                key={modNum}
                className={`module-matrix-card ${isSelected ? "selected" : ""}`}
                role="button" tabIndex={0} aria-label={`ดู Candidate Module ${modNum}`} aria-pressed={isSelected}
                onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setActiveModule(modNum); setSelectedProfile(prof ?? null); } }}
                onClick={() => {
                  setActiveModule(modNum);
                  setSelectedProfile(prof ?? null);
                }}
              >
                <div className="module-matrix-top">
                  <span className="module-matrix-title">
                    <Radio size={14} color={isSelected ? "var(--teal)" : "var(--muted)"} />
                    Module {modNum}
                  </span>
                  <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    {activeForMod ? (
                      <span className="active-indicator-tag" title={`Active Profile #${activeForMod.active_profile_id}`}>
                        ● Active
                      </span>
                    ) : (
                      <span className="active-indicator-tag inactive">
                        Inactive
                      </span>
                    )}
                    <StatusPill tone={prof ? profileTone(prof.profile_status) : "grey"}>
                      {prof ? (prof.profile_status === "ACTIVE_FROZEN" ? "Frozen" : prof.profile_status === "READY_FOR_APPROVAL" ? "Ready" : prof.profile_status) : "—"}
                    </StatusPill>
                  </div>
                </div>

                <div className="module-matrix-kpis">
                  <div className="module-kpi-item">
                    <label>Hp 2nd Mean</label>
                    <strong>{hp2Mean != null ? `${hp2Mean.toFixed(1)} ${unit}` : "—"}</strong>
                  </div>
                  <div className="module-kpi-item">
                    <label>ΔP 2nd Comp</label>
                    <strong>{dp2Mean != null ? `${dp2Mean.toFixed(1)} ${unit}` : "—"}</strong>
                  </div>
                </div>

                <div className="module-matrix-foot">
                  <span>
                    {prof ? (
                      unit.toLowerCase() !== "psi" ? "ยังไม่ยืนยันหน่วย psi" : inBand ? (
                        <span style={{ color: "var(--teal)", fontWeight: 750 }}>✓ 180–230 psi band</span>
                      ) : (
                        <span style={{ color: "#d97706", fontWeight: 750 }}>Ref: 180–230 psi</span>
                      )
                    ) : "ไม่มี Candidate ในรอบนี้"}
                  </span>
                  <span>{prof ? `${prof.calibration_windows.toLocaleString()} win` : "—"}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. Detailed Profile Inspection & Validation */}
      <section className="calibration-layout">
        {/* Profile List */}
        <article className="panel calibration-list">
          <header>
            <div>
              <h2>Profiles List ({targetMachine})</h2>
              <p>เลือกโมดูลเพื่อดูพารามิเตอร์</p>
            </div>
            <StatusPill tone="grey">{filteredProfiles.length}</StatusPill>
          </header>
          <div>
            {filteredProfiles.length === 0 ? (
              <p style={{ padding: "24px 16px", color: "var(--muted)", fontSize: 11, textAlign: "center" }}>
                ไม่มี Profile สำหรับเครื่อง {targetMachine} ใน batch นี้
              </p>
            ) : (
              filteredProfiles.map(profile => {
                const isModActive = activeProfiles.some(ap => isSameMachine(ap.machine_number, profile.machine_number) && ap.module === profile.module);
                return (
                  <button
                    key={profile.profile_id}
                    className={selected?.profile_id === profile.profile_id ? "selected" : ""}
                    onClick={() => {
                      setSelectedProfile(profile);
                      setActiveModule(profile.module);
                    }}
                  >
                    <span>
                      <strong>{profile.machine_number} · M{profile.module}</strong>
                      <small>SV {profile.sv_state} · {profile.state_code}</small>
                    </span>
                    <span>
                      {isModActive && <span className="active-indicator-tag" style={{ marginRight: "4px" }}>● Active</span>}
                      <StatusPill tone={profileTone(profile.profile_status)}>{profile.profile_status}</StatusPill>
                      <small>{profile.shadow_days}d · {profile.shadow_windows.toLocaleString()} win</small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                );
              })
            )}
          </div>
        </article>

        {/* Profile Detail & Validation Section */}
        <article className="panel calibration-detail">
          <header>
            <div>
              <h2>{selected ? `${selected.machine_number} · Module ${selected.module} · SV ${selected.sv_state}` : "เลือก Profile"}</h2>
              <p>ผล Baseline และ Shadow ที่ไม่ใช้สร้าง Profile · ตรวจช่วงวันที่ของรอบที่เลือก</p>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {currentActiveForMod && <span className="badge-active-live">{selected?.profile_id === currentActiveForMod.active_profile_id ? "ACTIVE_FROZEN" : `มี Active เดิม #${currentActiveForMod.active_profile_id}`}</span>}
              {selected && <StatusPill tone={profileTone(selected.profile_status)}>{selected.profile_status}</StatusPill>}
            </div>
          </header>

          {selected ? (
            <div style={{ padding: "16px" }}>

              {/* Baseline Summary Cards */}
              <div className="baseline-section">
                <div className="baseline-section-header">
                  <div>
                    <h3>Operational Baseline Values</h3>
                    <p>สถิติ Mean, Median, ช่วง P10-P90 และ Standard Deviation ใน qualified window</p>
                  </div>
                </div>

                <div className="baseline-cards-grid">
                  {/* Card 1: CP1 Stage (R507A) */}
                  <div className="baseline-card">
                    <div className="baseline-card-header">
                      <div>
                        <h4>Compressor Stage 1</h4>
                        <small>High / Low Pressure และผลต่างแรงดัน</small>
                      </div>
                    </div>
                    <div className="baseline-rows">
                      <BaselineRow name="Hp 1st (Discharge)" stat={selected.statistics?.detailed_baseline?.hp1} unit={selectedPressureUnit} />
                      <BaselineRow name="Lp 1st (Suction)" stat={selected.statistics?.detailed_baseline?.lp1} unit={selectedPressureUnit} />
                      <BaselineRow name="ΔP 1st (Compression)" stat={selected.statistics?.detailed_baseline?.dp1} unit={selectedPressureUnit} />
                    </div>
                  </div>

                  {/* Card 2: CP2 Stage (R23) */}
                  <div className="baseline-card">
                    <div className="baseline-card-header">
                      <div>
                        <h4>Compressor Stage 2</h4>
                        <small>High / Low Pressure และผลต่างแรงดัน</small>
                      </div>
                      <span className={`ref-band-badge ${isHp2InBand ? "in-band" : ""}`} title="Reference Band หน้างาน 180–230 psi">
                        {selectedPressureUnit.toLowerCase() !== "psi" ? "ยังไม่ยืนยันหน่วย psi" : isHp2InBand ? "Hp2 in 180–230 band" : "Ref band: 180–230 psi"}
                      </span>
                    </div>
                    <div className="baseline-rows">
                      <BaselineRow name="Hp 2nd (Discharge)" stat={selected.statistics?.detailed_baseline?.hp2} unit={selectedPressureUnit} />
                      <BaselineRow name="Lp 2nd (Suction)" stat={selected.statistics?.detailed_baseline?.lp2} unit={selectedPressureUnit} />
                      <BaselineRow name="ΔP 2nd (Compression)" stat={selected.statistics?.detailed_baseline?.dp2} unit={selectedPressureUnit} />
                    </div>
                  </div>

                  {/* Card 3: Valve & Temperatures */}
                  <div className="baseline-card">
                    <div className="baseline-card-header">
                      <div>
                        <h4>EEV & Thermal</h4>
                        <small>Expansion valve, Compressor / Discharge Pipe</small>
                      </div>
                    </div>
                    <div className="baseline-rows">
                      <BaselineRow name="EEV Valve Cmd" stat={selected.statistics?.detailed_baseline?.valve} unit="count" />
                      <BaselineRow name="TempHi · Compressor" stat={selected.statistics?.detailed_baseline?.temphi} unit="source unit" />
                      <BaselineRow name="TempLo · Discharge Pipe" stat={selected.statistics?.detailed_baseline?.templo} unit="source unit" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Correlation Heatmap */}
              <CorrelationHeatmap
                correlations={selected.statistics?.correlations}
                title={`${selected.machine_number} · Module ${selected.module} Inter-Feature Correlation Matrix`}
                subtitle="Pearson correlation coefficients during qualified operating state"
              />

              {/* Shadow Graph */}
              <div style={{ marginTop: "18px" }}>
                <div className="baseline-section-header">
                  <div>
                    <h3>ผลทดสอบข้อมูล 3 วันหลัง Reference</h3>
                    <p>ประเมินอัตราเตือนและความต่อเนื่องในช่วงที่ไม่ใช้ Fit · ไม่ใช่ false-positive rate หากไม่มีผลตรวจยืนยัน</p>
                    <p>{selected.thresholds.threshold_version==="qualified-1m-physical-retained-q995-strict-v2"?"กติกาใหม่: คะแนนหลักใช้แรงดันและอุณหภูมิ · เกินเกณฑ์เมื่อคะแนน > threshold · Valve เป็นบริบทการควบคุม":"รอบเดิม: ใช้กติกาคะแนนและเกณฑ์ที่บันทึกไว้ใน Profile เดิม"}</p>
                  </div>
                </div>
                <div className="calibration-chart">
                  {shadow.data?.length ? (
                    <CalibrationShadowChart points={shadow.data} />
                  ) : (
                    <p>ยังไม่มี shadow points สำหรับ profile นี้</p>
                  )}
                </div>
              </div>

              {/* Profile Evidence KPIs */}
              <div className="profile-evidence" style={{ marginTop: "14px" }}>
                <div>
                  <span>Calibration Windows</span>
                  <strong>{selected.calibration_days} วัน · {selected.calibration_windows.toLocaleString()} win</strong>
                </div>
                <div>
                  <span>คัดออกจาก Reference · เกณฑ์ ≤5%</span>
                  <strong>{selected.quarantine_pct?.toFixed(2) ?? "—"}%</strong>
                </div>
                <div>
                  <span>นอก baseline ในช่วงทดสอบ · เกณฑ์ ≤1%</span>
                  <strong>{selected.shadow_flag_pct?.toFixed(2) ?? "—"}%</strong>
                </div>
                <div>
                  <span>Persistent Flagged</span>
                  <strong>{selected.persistent_flag_pct?.toFixed(2) ?? "—"}%</strong>
                </div>
              </div>

              {/* Gate / Reason Codes */}
              <div className="reason-list">
                <strong>เหตุผลที่ยังต้องตรวจหรือยืนยัน</strong>
                {selected.reason_codes.length ? (
                  selected.reason_codes.map(reason => (
                    <p key={reason}>{approvalReason(reason)}</p>
                  ))
                ) : (
                  <StatusPill tone="green">All configured gates passed</StatusPill>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <Database />
              <h2>กรุณาเลือก Profile</h2>
              <p>เลือก Machine และ Module จากด้านบนเพื่อดู Baseline และผล Validation</p>
            </div>
          )}
        </article>
      </section>

      {/* Approval Gate */}
      <section id="calibration-approval" className="panel approval-panel">
        <header>
          <div>
            <h2>Approval gate</h2>
            <p>อนุมัติ Candidate ที่ผ่านเกณฑ์เป็น Active Profile ในระบบนี้ พร้อมบันทึก Rollback Pointer</p>
          </div>
          <ShieldCheck size={18} />
        </header>
        <div className="approval-body">
          <label>
            รหัสผู้อนุมัติ
            <input
              value={approverId}
              onChange={event => setApproverId(event.target.value)}
              placeholder="เช่น APPROVER-01"
            />
          </label>
          <label>
            หมายเหตุการตัดสินใจ {canApprove ? "(ไม่บังคับ)" : "(จำเป็นเมื่อ Reject)"}
            <textarea
              rows={2}
              value={reviewNote}
              onChange={event => setReviewNote(event.target.value)}
              placeholder="บันทึกผลการตรวจสอบพารามิเตอร์"
            />
          </label>
          <div className="approval-actions">
            <button
              className="button secondary"
              disabled={isDemo || !selected || ["ACTIVE_FROZEN", "REJECTED"].includes(selected.profile_status) || approverId.trim().length < 2 || reviewNote.trim().length < 8 || review.isPending}
              onClick={() => review.mutate("REJECT")}
            >
              Reject candidate
            </button>
            <button
              className="button primary"
              disabled={!canApprove || approverId.trim().length < 2 || review.isPending}
              onClick={() => review.mutate("APPROVE")}
            >
              Approve → Active Profile
            </button>
            {targetMachine !== "ALL" && filteredProfiles.length >= 8 && (
              <button
                type="button"
                className="button primary"
                style={{ background: "#0f766e", display: "inline-flex", alignItems: "center", gap: "6px" }}
                disabled={isDemo || approverId.trim().length < 2 || approveAllMutation.isPending || filteredProfiles.filter(p => p.profile_status === "READY_FOR_APPROVAL").length !== 8}
                onClick={() => approveAllMutation.mutate()}
                title={`อนุมัติครบทั้ง 8 โมดูลสำหรับเครื่อง ${targetMachine}`}
              >
                <ShieldCheck size={16} />
                {approveAllMutation.isPending ? "กำลังอนุมัติทั้งเครื่อง…" : `อนุมัติทุก Module ของเครื่อง ${targetMachine} (ครบ 8 โมดูล)`}
              </button>
            )}
          </div>
          {approveAllMutation.error && <p className="form-error">{approveAllMutation.error.message}</p>}
          {approveAllMutation.isSuccess && (
            <p className="form-success">
              {String((approveAllMutation.data as { message?: string })?.message ?? "อนุมัติทั้งเครื่องสำเร็จ")}
            </p>
          )}
          {!canApprove && !isDemo && (
            <p className="form-error">
              {!selected ? "เลือก Candidate ของเครื่องและโมดูลที่ต้องการก่อน"
                : selected.profile_status === "ACTIVE_FROZEN" ? "Profile นี้เป็น Active แล้ว ตรวจได้ที่หน้า Active Profiles"
                : selected.profile_status === "REJECTED" ? "Candidate รอบนี้ถูก Reject แล้ว ต้องทบทวน Reference และสร้างรอบใหม่"
                : `${humanStatus(selected.profile_status)} · ตรวจรายการด้านล่างและสร้างรอบใหม่หลังแก้ไข หมายเหตุไม่ข้ามเกณฑ์อนุมัติ`}
            </p>
          )}
          {selected && !canApprove && selected.reason_codes.length > 0 && <ul className="approval-blockers">{selected.reason_codes.map(reason => <li key={reason}>{approvalReason(reason)}</li>)}</ul>}
          {approverId.trim().length < 2 && <p className="form-error">กรอกรหัสผู้อนุมัติอย่างน้อย 2 ตัวอักษร</p>}
          {selected && !["ACTIVE_FROZEN", "REJECTED"].includes(selected.profile_status) && reviewNote.trim().length < 8 && <p className="panel-note">หาก Reject ต้องระบุเหตุผลอย่างน้อย 8 ตัวอักษร</p>}
          {isDemo && (
            <p className="form-error">Demo เป็นหลักฐาน offline เท่านั้น จึงไม่อนุญาตให้กดอนุมัติ</p>
          )}
          {review.error && <p className="form-error">{review.error.message}</p>}
          {review.isSuccess && (
            <p className="form-success">
              {String((review.data as { message?: string })?.message ?? "บันทึกผล review แล้ว")}
            </p>
          )}
        </div>
      </section>
      </>}
    </section>
  );
}

function ActiveProfilesView() {
  const [selectedMachine, setSelectedMachine] = useState<string>("");
  const [selectedModule, setSelectedModule] = useState<number>(1);
  const profilesQuery = useQuery({
    queryKey: ["active-profiles"],
    queryFn: api.activeProfiles,
    refetchInterval: 30_000,
  });

  const activeProfiles = profilesQuery.data ?? [];
  const machines = useMemo(() => {
    const list = Array.from(new Set(activeProfiles.map(p => p.machine_number)));
    return list.sort();
  }, [activeProfiles]);

  const currentMachine = machines.includes(selectedMachine) ? selectedMachine : (machines[0] ?? "");

  const machineProfiles = useMemo(() => {
    return activeProfiles.filter(p => p.machine_number === currentMachine);
  }, [activeProfiles, currentMachine]);

  const currentProfile = machineProfiles.find(p => p.module === selectedModule) ?? machineProfiles[0];

  const hp2Stat = currentProfile?.statistics?.detailed_baseline?.hp2;
  const activePressureUnit = pressureUnit(currentProfile);
  const isHp2InBand = activePressureUnit.toLowerCase() === "psi" && hp2Stat ? hp2Stat.mean >= 180 && hp2Stat.mean <= 230 : false;

  return (
    <div className="active-profiles-view">
      {/* 1. Top Banner */}
      <section className="active-profiles-banner">
        <div className="banner-left">
          <div className="pulse-icon-box">
            <ShieldCheck size={24} color="var(--teal)" />
          </div>
          <div>
            <h2>Active Frozen Production Profiles (โปรไฟล์โมเดลที่ใช้งานจริงบน Production)</h2>
            <p>
              โปรไฟล์พารามิเตอร์ที่ผ่านการอนุมัติและล็อกไว้ในระบบ เพื่อใช้ทำ Online Scoring พร้อม Transactional Rollback Pointers
            </p>
          </div>
        </div>
        <div className="banner-actions">
          <StatusPill tone="green">
            <span className="pulse-dot" style={{ background: "var(--green)" }} />
            {activeProfiles.length} Active Frozen Modules
          </StatusPill>
          <button className="icon-button" onClick={() => profilesQuery.refetch()} aria-label="Refresh">
            <RefreshCw size={16} />
          </button>
        </div>
      </section>

      {/* 2. Machine Selector Tabs */}
      <section className="machine-selector-row">
        <div className="machine-tabs">
          {machines.length === 0 ? (
            <div className="empty-state" style={{ padding: "16px", width: "100%" }}>
              <p>ยังไม่มี Active Profiles ในฐานข้อมูล กรุณาไปที่หน้า Calibration เพื่ออนุมัติ Profile</p>
            </div>
          ) : (
            machines.map(m => {
              const count = activeProfiles.filter(p => p.machine_number === m).length;
              const isSel = m === currentMachine;
              return (
                <button
                  key={m}
                  type="button"
                  className={`machine-tab-btn ${isSel ? "active" : ""}`}
                  onClick={() => {
                    setSelectedMachine(m);
                    const firstMod = activeProfiles.filter(p => p.machine_number === m)[0]?.module ?? 1;
                    setSelectedModule(firstMod);
                  }}
                >
                  <Cpu size={16} />
                  <span className="tab-name">{m.startsWith("MX") ? m : `MX${m}`}</span>
                  <StatusPill tone={isSel ? "teal" : "grey"}>{count}/8 Modules Active</StatusPill>
                </button>
              );
            })
          )}
        </div>
      </section>

      {/* 3. 8-Module Grid for Current Machine */}
      {currentMachine && <section className="panel">
        <header>
          <div>
            <h3>8-Module Production Matrix ({currentMachine})</h3>
            <p>เลือกโมดูลเพื่อดูพารามิเตอร์ Normal Envelope, Threshold และ Correlation Matrix ที่นำไปใช้จริง</p>
          </div>
          <StatusPill tone="green">{machineProfiles.length}/8 Active Modules</StatusPill>
        </header>

        <div className="active-module-grid">
          {[1, 2, 3, 4, 5, 6, 7, 8].map(modNum => {
            const prof = machineProfiles.find(p => p.module === modNum);
            const isSel = currentProfile?.module === modNum;
            const hp2 = prof?.statistics?.detailed_baseline?.hp2?.mean;
            const dp2 = prof?.statistics?.detailed_baseline?.dp2?.mean;
            const inBand = hp2 != null && hp2 >= 180 && hp2 <= 230;

            return (
              <div
                key={modNum}
                className={`active-module-card ${isSel ? "selected" : ""}`}
                onClick={() => {
                  if (prof) setSelectedModule(modNum);
                }}
              >
                <div className="card-top">
                  <strong>Module {modNum}</strong>
                  <StatusPill tone={prof ? "green" : "grey"}>
                    {prof ? "ACTIVE_FROZEN" : "INACTIVE"}
                  </StatusPill>
                </div>

                <div className="card-kpi-pair">
                  <div>
                    <label>Hp 2nd Mean</label>
                    <span className="kpi-val">{hp2 != null ? `${hp2.toFixed(1)} psi` : "—"}</span>
                  </div>
                  <div>
                    <label>ΔP 2nd Mean</label>
                    <span className="kpi-val">{dp2 != null ? `${dp2.toFixed(1)} psi` : "—"}</span>
                  </div>
                </div>

                <div className="card-bottom">
                  {prof ? (
                    <>
                      <span className={`ref-indicator ${inBand ? "ok" : "warn"}`}>
                        {inBand ? "✓ 180–230 psi" : "Ref: 180–230"}
                      </span>
                      <small>{prof.calibration_windows.toLocaleString()} win</small>
                    </>
                  ) : (
                    <span>ไม่มี Profile</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>}

      {/* 4. Active Profile Detail Inspector */}
      {currentProfile && (
        <section className="panel">
          <header>
            <div>
              <h3>
                Active Profile: {currentProfile.machine_number} · Module {currentProfile.module} (SV {currentProfile.sv_state})
              </h3>
              <p>พารามิเตอร์และสถิติ Normal State ที่ระบบใช้คำนวณ Anomaly Detection เรียลไทม์</p>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <StatusPill tone="blue">Registry ACTIVE_FROZEN #{currentProfile.active_profile_id}</StatusPill>
              <StatusPill tone="blue">Rollback: {currentProfile.rollback_mode}</StatusPill>
            </div>
          </header>

          <div style={{ padding: "20px" }}>
            {/* Meta Governance Bar */}
            <div className="governance-meta-strip">
              <div>
                <label>Profile Version</label>
                <strong>{currentProfile.profile_version}</strong>
              </div>
              <div>
                <label>Approved By</label>
                <strong>{currentProfile.activated_by || currentProfile.reviewer_id || "APPROVER-01"}</strong>
              </div>
              <div>
                <label>Activated At</label>
                <strong>{timeLabel(currentProfile.activated_at)}</strong>
              </div>
              <div>
                <label>Rollback Target</label>
                <strong>
                  {currentProfile.rollback_profile_id ? `Profile #${currentProfile.rollback_profile_id}` : "FAIL_CLOSED"}
                </strong>
              </div>
              <div>
                <label>Calibration Windows</label>
                <strong>{currentProfile.calibration_windows.toLocaleString()} windows ({currentProfile.calibration_days} วัน)</strong>
              </div>
            </div>

            {/* Evidence Tags */}
            <div className="active-reason-strip" style={{ marginTop: "14px" }}>
              <span>Evidence & Validation Tags:</span>
              {currentProfile.reason_codes && currentProfile.reason_codes.length > 0 ? (
                currentProfile.reason_codes.map(r => (
                  <StatusPill key={r} tone={r.includes("BOOTSTRAP") ? "blue" : "grey"}>{r}</StatusPill>
                ))
              ) : (
                <StatusPill tone="green">Standard Qualified Calibration</StatusPill>
              )}
            </div>

            {/* Baseline Section */}
            <div className="baseline-section" style={{ marginTop: "24px" }}>
              <div className="baseline-section-header">
                <div>
                  <h4>1. Production Operational Baseline Envelopes</h4>
                  <p>ค่ากลาง (Median) และส่วนเบี่ยงเบนมาตรฐาน (Scale) สำหรับใช้ตรวจ Anomaly</p>
                </div>
              </div>

              <div className="baseline-cards-grid">
                {/* CP1 Stage */}
                <div className="baseline-card">
                  <div className="baseline-card-header">
                    <div>
                      <h5>CP1 Stage (R507A)</h5>
                      <small>Medium-temperature cycle</small>
                    </div>
                  </div>
                  <div className="baseline-rows">
                    <BaselineRow name="Hp 1st (Discharge)" stat={currentProfile.statistics?.detailed_baseline?.hp1} unit={activePressureUnit} />
                    <BaselineRow name="Lp 1st (Suction)" stat={currentProfile.statistics?.detailed_baseline?.lp1} unit={activePressureUnit} />
                    <BaselineRow name="ΔP 1st (Compression)" stat={currentProfile.statistics?.detailed_baseline?.dp1} unit={activePressureUnit} />
                  </div>
                </div>

                {/* CP2 Stage */}
                <div className="baseline-card">
                  <div className="baseline-card-header">
                    <div>
                      <h5>CP2 Stage (R23)</h5>
                      <small>Ultra-low temperature cycle</small>
                    </div>
                    <span className={`ref-band-badge ${isHp2InBand ? "in-band" : ""}`} title="Reference Band หน้างาน 180–230 psi">
                      {activePressureUnit.toLowerCase() !== "psi" ? "ยังไม่ยืนยันหน่วย psi" : isHp2InBand ? "Hp2 in 180–230 band" : "Ref: 180–230 psi"}
                    </span>
                  </div>
                  <div className="baseline-rows">
                    <BaselineRow name="Hp 2nd (Discharge)" stat={currentProfile.statistics?.detailed_baseline?.hp2} unit={activePressureUnit} />
                    <BaselineRow name="Lp 2nd (Suction)" stat={currentProfile.statistics?.detailed_baseline?.lp2} unit={activePressureUnit} />
                    <BaselineRow name="ΔP 2nd (Compression)" stat={currentProfile.statistics?.detailed_baseline?.dp2} unit={activePressureUnit} />
                  </div>
                </div>

                {/* Valve & Temperatures */}
                <div className="baseline-card">
                  <div className="baseline-card-header">
                    <div>
                      <h5>EEV & Temperatures</h5>
                      <small>Expansion valve · Compressor / Discharge Pipe</small>
                    </div>
                  </div>
                  <div className="baseline-rows">
                    <BaselineRow name="EEV Valve Cmd" stat={currentProfile.statistics?.detailed_baseline?.valve} unit="count" />
                    <BaselineRow name="TempHi · Compressor" stat={currentProfile.statistics?.detailed_baseline?.temphi} unit="source unit" />
                    <BaselineRow name="TempLo · Discharge Pipe" stat={currentProfile.statistics?.detailed_baseline?.templo} unit="source unit" />
                  </div>
                </div>
              </div>
            </div>

            {/* Inference Specifications */}
            <div className="inference-specs-grid" style={{ marginTop: "24px" }}>
              <article className="spec-box">
                <div className="spec-box-head">
                  <Activity size={18} color="var(--teal)" />
                  <strong>Real-time Scoring Algorithm</strong>
                </div>
                <div className="spec-box-content">
                  <p>Robust Z-Score Local Deviation Metric:</p>
                  <pre>Deviation Score = max_i ( |x_i - Median_i| / max(Scale_i, Scale_Floor) )</pre>
                  <p className="spec-note">
                    Scale Floor ป้องกันการหารด้วยศูนย์ในสภาวะ Ultra-steady state
                  </p>
                </div>
              </article>

              <article className="spec-box">
                <div className="spec-box-head">
                  <SlidersHorizontal size={18} color="var(--teal)" />
                  <strong>Decision Cutoff & Persistence Filter</strong>
                </div>
                <div className="spec-box-content">
                  <div className="spec-metric-row">
                    <span>Cutoff Threshold (&tau;):</span>
                    <strong>{currentProfile.thresholds?.deviation_score_q995 == null ? "Not available" : String(currentProfile.thresholds.deviation_score_q995)}</strong>
                  </div>
                  <div className="spec-metric-row">
                    <span>Persistence Requirement:</span>
                    <strong>{currentProfile.feature_version === "qualified-cold-observed-1m-v1" ? "3 consecutive qualified minutes (3 นาที)" : "Historical profile — check version"}</strong>
                  </div>
                  <div className="spec-metric-row">
                    <span>Evaluation Grain:</span>
                    <strong>{currentProfile.feature_version === "qualified-cold-observed-1m-v1" ? "1-minute mean from observed seconds" : currentProfile.feature_version || "Unknown profile grain"}</strong>
                  </div>
                </div>
              </article>
            </div>

            {/* Inter-Feature Correlation Heatmap */}
            <div style={{ marginTop: "24px" }}>
              <CorrelationHeatmap
                correlations={currentProfile.statistics?.correlations}
                title={`${currentProfile.machine_number} · Module ${currentProfile.module} Active Inter-Feature Correlation Matrix`}
                subtitle="Historical profile correlations for review; association is not proof of cause"
              />
            </div>

          </div>
        </section>
      )}
    </div>
  );
}

export default function App() {
  const runId = new URLSearchParams(window.location.search).get("rehearsal");
  return runId ? <RehearsalDashboard runId={runId} /> : <OperationsApp />;
}

function OperationsApp() {
  const [view, setView] = useState<View>("calibration");

  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet, refetchInterval: 5 * 60_000 });
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img src="/assets/adi-logo.png" alt="Analog Devices" />
          <div>
            <strong>OPERATION</strong>
            <span>Calibration & Monitoring</span>
          </div>
        </div>
        <nav>
          <button className={view === "calibration" ? "active" : ""} onClick={() => setView("calibration")}>
            <SlidersHorizontal />
            Calibration
          </button>
          <button className={view === "profiles" ? "active" : ""} onClick={() => setView("profiles")}>
            <ShieldCheck />
            Active Profiles
          </button>
          <button className={view === "events" ? "active" : ""} onClick={() => setView("events")}><History/>Event History</button>
          <button className={view === "fleet" ? "active" : ""} onClick={() => setView("fleet")}><ShieldCheck/>Fleet Models</button>
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="eyebrow">HONTECH HT9046-MX · OPERATION</span>
            <h1>
              {view === "calibration"
                ? "Calibration Workflow & Management"
                : view === "profiles"
                ? "Active Frozen Production Profiles"
                : view === "events" ? "Compressor Event History" : "Fleet Model Management"}
            </h1>
          </div>
          <div className="top-actions">
            <StatusPill tone={fleet.data?.mode.startsWith("DEMO") ? "amber" : "teal"}>
              {fleet.data?.mode ?? "กำลังเชื่อมต่อ"}
            </StatusPill>
            <button className="icon-button" onClick={() => fleet.refetch()} aria-label="Refresh">
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        {fleet.isError && (
          <div className="error-state">
            <AlertTriangle />
            <div>
              <strong>เชื่อมต่อ API ไม่สำเร็จ</strong>
              <span>{fleet.error.message}</span>
            </div>
          </div>
        )}

        {view === "calibration" && <CalibrationPanel />}

        {view === "profiles" && <ActiveProfilesView />}
        {view === "events" && <EventHistory/>}
        {view === "fleet" && <FleetModelManagement/>}

      </main>
    </div>
  );
}
