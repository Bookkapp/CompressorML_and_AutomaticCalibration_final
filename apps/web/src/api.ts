import type {
  ActiveProfile,
  AutomationStatus,
  CalibrationBatch,
  CalibrationProfile,
  CalibrationShadowPoint,
  FleetSummary,
  MachineApprovalRequest,
  MachineApprovalResult,
  ManualCalibrationRequest,
  ManualCalibrationResult,
  SourceMachine,
  Timeline
} from "./types";
import type { ReferenceJob, ReferenceAvailability, ReferenceJobSummary } from "./components/ReferenceReview";
import type { AutomaticJob } from "./components/AutomaticCalibration";
import type { RawEvidence } from "./components/CalibrationEvidence";
import type { ContextJob,ContextModel,ContextDay,EventPage,LedgerEvent,ContextReviewState,ContextReadiness,ContextCoverage } from "./context-types";
import type {FleetReference,FleetReferenceDay,FleetStable,FleetStableDay,FleetTransitions,ValidationReport} from "./context-types";
import type {FollowupProgress,FollowupJob} from "./context-types";
import type {FleetInventory,FleetVersion,FleetComparison,FleetTrainingJob} from "./fleet-types";

const base = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((x: {msg: string}) => x.msg).join(" · ") : `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  fleetInventory:()=>request<FleetInventory>("/api/v1/calibration/fleet/manage"),
  fleetVersion:(id:string)=>request<FleetVersion>(`/api/v1/calibration/fleet/manage/versions/${encodeURIComponent(id)}`),
  fleetCompare:(a:string,b:string)=>request<FleetComparison>(`/api/v1/calibration/fleet/manage/compare/${encodeURIComponent(a)}/${encodeURIComponent(b)}`),
  fleetTrain:(who:string,payload:Record<string,unknown>)=>request<FleetTrainingJob>("/api/v1/calibration/fleet/manage/train",{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify(payload)}),
  fleetRelease:(who:string,payload:Record<string,unknown>)=>request<FleetInventory["pointer"]>("/api/v1/calibration/fleet/manage/release",{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify(payload)}),
  fleetTransitions:(id:string)=>request<FleetTransitions>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/fleet-transitions`),
  contextValidationReport:(id:string,start:string,end:string)=>request<ValidationReport>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/validation-report?${new URLSearchParams({start,end})}`),
  contextFollowup:(id:string,who:string)=>request<FollowupProgress>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/followup`,{headers:{"X-Approver-Id":who}}),
  inspectFollowup:(id:string,who:string)=>request<FollowupJob>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/followup`,{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify({idempotency_key:crypto.randomUUID()})}),
  followupDay:(id:string,job:string,day:string)=>request<ContextDay>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/followup/${encodeURIComponent(job)}/day?day=${encodeURIComponent(day)}`),
  followupRaw:(id:string,job:string,start:string,end:string)=>request<RawEvidence>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/followup/${encodeURIComponent(job)}/raw?${new URLSearchParams({start,end})}`),
  fleetStableReference:(machine:string,module:number)=>request<FleetStable>(`/api/v1/calibration/fleet/stable/reference?machine_number=${encodeURIComponent(machine)}&module=${module}`),
  fleetStableDay:(machine:string,module:number,day:string,version:string)=>request<FleetStableDay>(`/api/v1/calibration/fleet/stable/day?${new URLSearchParams({machine_number:machine,module:String(module),day,bundle_id:version})}`),
  fleetReference:(machine:string,module:number)=>request<FleetReference>(`/api/v1/calibration/fleet/reference?machine_number=${encodeURIComponent(machine)}&module=${module}`),
  fleetReferenceDay:(machine:string,module:number,day:string)=>request<FleetReferenceDay>(`/api/v1/calibration/fleet/day?machine_number=${encodeURIComponent(machine)}&module=${module}&day=${encodeURIComponent(day)}`),
  prepareContext:(reviewer:string,payload:Record<string,unknown>)=>request<ContextJob>("/api/v1/calibration/context/prepare",{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":reviewer},body:JSON.stringify(payload)}),
  latestContext:(machine:string,reviewer:string,completed=false)=>request<ContextJob|null>(`/api/v1/calibration/context/latest?machine_number=${encodeURIComponent(machine)}&completed_only=${completed}`,{headers:{"X-Approver-Id":reviewer}}),
  contextJob:(id:string,reviewer:string)=>request<ContextJob>(`/api/v1/calibration/context/jobs/${encodeURIComponent(id)}`,{headers:{"X-Approver-Id":reviewer}}),
  contextCoverage:(id:string,reviewer:string)=>request<ContextCoverage>(`/api/v1/calibration/context/jobs/${encodeURIComponent(id)}/coverage`,{headers:{"X-Approver-Id":reviewer}}),
  contextProfile:(id:string)=>request<ContextModel>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}`),
  contextDay:(id:string,day:string)=>request<ContextDay>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/day?day=${encodeURIComponent(day)}`),
  contextRaw:(id:string,start:string,end:string)=>request<RawEvidence>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/raw?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
  contextReview:(id:string,who:string)=>request<ContextReviewState>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/review`,{headers:{"X-Approver-Id":who}}),
  saveContextReview:(id:string,who:string,payload:Record<string,unknown>)=>request<ContextReviewState>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/review`,{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify(payload)}),
  contextReadiness:(id:string)=>request<ContextReadiness>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/readiness`),
  approveContext:(id:string,who:string,payload:Record<string,unknown>)=>request<Record<string,unknown>>(`/api/v1/calibration/context/profiles/${encodeURIComponent(id)}/approve`,{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify(payload)}),
  contextActive:(machine:string)=>request<{module:number;profile_id:string;previous_profile_id:string|null;revision:number}[]>(`/api/v1/calibration/context/active?machine_number=${encodeURIComponent(machine)}`),
  rollbackContext:(machine:string,module:number,who:string,payload:Record<string,unknown>)=>request<Record<string,unknown>>(`/api/v1/calibration/context/active/${encodeURIComponent(machine)}/${module}/rollback`,{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":who},body:JSON.stringify(payload)}),
  eventRaw:(id:string,module:number,start:string,end:string)=>request<RawEvidence>(`/api/v1/events/${id}/raw?${new URLSearchParams({module:String(module),start,end})}`),
  eventHistory:(params:Record<string,string>)=>request<EventPage>(`/api/v1/events?${new URLSearchParams(params)}`),
  eventDetail:(id:string)=>request<{event:LedgerEvent;related:LedgerEvent[]}>(`/api/v1/events/${encodeURIComponent(id)}`),
  calibrationSourceContract:()=>request<{items:{key:string;title:string;value:string;verified:boolean}[];scope:string}>("/api/v1/calibration/source-contract"),
  referenceRaw:(id:string,reviewer:string,start:string,end:string)=>request<RawEvidence>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}/raw?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,{headers:{"X-Approver-Id":reviewer}}),
  prepareAutomatic: (reviewer:string,payload:Record<string,unknown>) => request<AutomaticJob>("/api/v1/calibration/reference/automatic",{method:"POST",headers:{"Content-Type":"application/json","X-Approver-Id":reviewer},body:JSON.stringify(payload)}),
  latestAutomatic: (machine:string,reviewer:string) => request<AutomaticJob|null>(`/api/v1/calibration/reference/automatic?machine_number=${encodeURIComponent(machine)}`,{headers:{"X-Approver-Id":reviewer}}),
  automaticJob: (id:string,reviewer:string) => request<AutomaticJob>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}`,{headers:{"X-Approver-Id":reviewer}}),
  copyAutomaticReview: (id:string,reviewer:string) => request<ReferenceJob>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}/copy`,{method:"POST",headers:{"X-Approver-Id":reviewer}}),
  referenceAvailability: (machine: string, module: number) => request<ReferenceAvailability>(`/api/v1/calibration/reference/availability?machine_number=${encodeURIComponent(machine)}&module=${module}`),
  referenceRecentJobs: (machine: string, module: number, reviewer: string) => request<ReferenceJobSummary[]>(`/api/v1/calibration/reference/jobs?machine_number=${encodeURIComponent(machine)}&module=${module}`, { headers: { "X-Approver-Id": reviewer } }),
  previewReference: (reviewer: string, payload: Record<string, unknown>) => request<ReferenceJob>("/api/v1/calibration/reference/preview", { method: "POST", headers: { "Content-Type": "application/json", "X-Approver-Id": reviewer }, body: JSON.stringify(payload) }),
  referenceJob: (id: string, reviewer: string) => request<ReferenceJob>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}`, { headers: { "X-Approver-Id": reviewer } }),
  referenceDay: (id: string, reviewer: string, day: string) => request<{chart: Record<string, unknown>[] }>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}/day?day=${encodeURIComponent(day)}`, { headers: { "X-Approver-Id": reviewer } }),
  buildReference: (id: string, reviewer: string, payload: Record<string, unknown>) => request<ReferenceJob>(`/api/v1/calibration/reference/jobs/${encodeURIComponent(id)}/build`, { method: "POST", headers: { "Content-Type": "application/json", "X-Approver-Id": reviewer }, body: JSON.stringify(payload) }),
  fleet: () => request<FleetSummary>("/api/v1/fleet/summary"),
  automation: () => request<AutomationStatus>("/api/v1/automation/status"),
  sourceMachines: () => request<SourceMachine[]>("/api/v1/source/machines"),
  calibrationBatches: () => request<CalibrationBatch[]>("/api/v1/calibration/batches"),
  calibrationProfiles: (batchId: string) => request<CalibrationProfile[]>(`/api/v1/calibration/batches/${encodeURIComponent(batchId)}/profiles`),
  calibrationShadow: (profileId: number) => request<CalibrationShadowPoint[]>(`/api/v1/calibration/profiles/${profileId}/shadow`),
  runCalibration: (payload: ManualCalibrationRequest) =>
    request<ManualCalibrationResult>("/api/v1/calibration/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        machine_number: payload.machine_number ?? payload.target_machine,
      })
    }),
  reviewCalibration: (profileId: number, approverId: string, payload: Record<string, unknown>) =>
    request(`/api/v1/calibration/profiles/${profileId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Approver-Id": approverId },
      body: JSON.stringify(payload)
    }),
  activeProfiles: () => request<ActiveProfile[]>("/api/v1/calibration/active_profiles"),
  approveMachineAll: (machineNumber: string, approverId: string, payload?: MachineApprovalRequest) =>
    request<MachineApprovalResult>(`/api/v1/calibration/machines/${encodeURIComponent(machineNumber)}/approve_all`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Approver-Id": approverId },
      body: JSON.stringify({ approver_id: approverId, ...payload })
    }),
  timeline: (machine: string, module: number, start?: string, end?: string) => {
    const query = start && end ? `?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}` : "";
    return request<Timeline>(`/api/v1/machines/${machine}/modules/${module}/timeline${query}`);
  },

};
