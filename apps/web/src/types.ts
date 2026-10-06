export type Machine = {
  machine_number: string;
  scored_rows: number;
  raw_flag_rate_pct: number;
  alerts: number;
  alerts_per_machine_day: number;
  condition_status: string;
  latest_event_time: string | null;
};

export type FleetSummary = {
  mode: string;
  release_state: string;
  configured_machines: number;
  scored_machines: number;
  open_incidents: number;
  data_quality_issues: number;
  condition_index_available: boolean;
  dashboard_refresh_minutes: number;
  scoring_interval_minutes: number;
  cadence_gate: string;
  machines: Machine[];
};

export type Incident = {
  alert_id: number;
  machine_number: string;
  module: number;
  episode_start: string;
  detected_at: string;
  last_observed_at: string | null;
  alert_status: string;
  severity: string;
  claim_level: string;
  release_version: string;
  evidence: Record<string, unknown>;
  confirmation_status: string;
  is_prospective?: boolean;
};

export type TimelinePoint = {
  event_time: string;
  hp1: number | null;
  lp1: number | null;
  hp2: number | null;
  lp2: number | null;
  valve: number | null;
  temp_high: number | null;
  temp_low: number | null;
  anomaly_score: number | null;
  threshold: number | null;
  raw_flag: boolean;
  persistent_flag: boolean;
  sv_state: string | null;
  busy_state: string | null;
  state_code: string | null;
  message_code: string | null;
  message_text: string | null;
  data_quality_status: string;
};

export type Timeline = {
  machine_number: string;
  module: number;
  source_grain: string;
  source_timezone: string;
  condition_index_available: boolean;
  points: TimelinePoint[];
};

export type AutomationStatus = {
  dashboard_refresh_minutes: number;
  desired_scoring_interval_minutes: number;
  locked_release_interval_minutes: number;
  cadence_gate: string;
  profile_schedule: string;
  model_schedule: string;
  scoring_schedule: string;
  profile_activation: string;
  model_activation: string;
  latest_runs: Record<string, unknown>[];
};

export type CalibrationBatch = {
  batch_id: string;
  batch_status: string;
  source_start: string;
  calibration_end: string;
  shadow_start: string;
  shadow_end: string;
  source_timezone: string;
  profile_algorithm_version: string;
  feature_version: string;
  profile_count: number;
  ready_for_approval_count: number;
  created_at: string | null;
};

export type FeatureBaselineStat = {
  mean: number;
  std: number;
  median: number;
  p10: number;
  p90: number;
};

export type CalibrationStatistics = {
  windows?: number;
  qualified_rows?: number;
  correlations?: Record<string, Record<string, number>>;
  detailed_baseline?: Record<string, FeatureBaselineStat>;
  [key: string]: unknown;
};

export type CalibrationProfile = {
  profile_id: number;
  batch_id: string;
  profile_version: string;
  machine_number: string;
  module: number;
  sv_state: string;
  state_code: string;
  profile_status: string;
  reason_codes: string[];
  calibration_windows: number;
  calibration_days: number;
  quarantine_pct: number | null;
  max_half_shift_rz: number | null;
  shadow_windows: number;
  shadow_days: number;
  shadow_flag_pct: number | null;
  persistent_flag_pct: number | null;
  statistics: CalibrationStatistics;
  thresholds: Record<string, unknown>;
  validation: Record<string, unknown>;
};

export type CalibrationShadowPoint = {
  event_time: string;
  deviation_score: number | null;
  threshold_value: number | null;
  raw_flag: boolean;
  persistent_flag: boolean;
  data_quality_status: string;
};

export type SourceMachine = {
  machine_number: string;
  display_name: string;
  record_count?: number | null;
  row_count?: number | null;
  latest_recorded_at?: string | null;
  first_event?: string | null;
  last_event?: string | null;
};

export type ManualCalibrationRequest = {
  machine_number?: string;
  target_machine?: string;
  history_days?: number;
  shadow_days?: number;
  force?: boolean;
};

export type ManualCalibrationResult = {
  batch_id?: string;
  target_machine?: string | null;
  profile_count?: number;
  profiles_generated?: number;
  ready_count?: number;
  ready_for_approval?: number;
  history_days?: number;
  shadow_days?: number;
  status: string;
  message: string;
};

export type ActiveProfile = {
  machine_number: string;
  module: number;
  sv_state: string;
  state_code: string;
  active_profile_id: number;
  activated_at: string;
  activated_by: string;
  rollback_mode: string;
  rollback_profile_id: number | null;
  profile_version: string;
  feature_version: string;
  calibration_windows: number;
  calibration_days: number;
  quarantine_pct: number | null;
  max_half_shift_rz: number | null;
  shadow_windows: number;
  shadow_days: number;
  shadow_flag_pct: number | null;
  persistent_flag_pct: number | null;
  statistics: CalibrationStatistics;
  thresholds: Record<string, unknown>;
  validation: Record<string, unknown>;
  reason_codes: string[];
  reviewer_id?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
};

export type MachineApprovalRequest = {
  approver_id?: string;
  batch_id?: string;
  review_note?: string;
};

export type MachineApprovalResult = {
  approved_count: number;
  profile_ids: number[];
  message: string;
};
