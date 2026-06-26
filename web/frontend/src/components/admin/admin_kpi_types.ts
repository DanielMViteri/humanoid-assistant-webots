export type KpiStatus = "Available" | "Partial" | "Unavailable";

export type ServiceStatus = "Connected" | "Waiting" | "Unavailable";

export type AdminKpiService = {
  name: string;
  status: ServiceStatus;
  detail: string;
};

export type AdminTopKpi = {
  id: string;
  label: string;
  status: KpiStatus;
  value: string;
  detail: string;
  target?: string;
};

export type LatencySegment = {
  stage: string;
  status: KpiStatus;
  samples: number | null;
  median_ms: number | null;
  average_ms: number | null;
  p95_ms: number | null;
  negative: number;
  note: string;
};

export type EventSuccessRate = {
  status: KpiStatus;
  success: number;
  failure: number;
  unknown: number;
  total: number;
  note?: string;
};

export type LastRobotAction = {
  status: KpiStatus;
  action: string | null;
  object: string | null;
  location: string | null;
  duration_ms: number | null;
  note: string;
};

export type ActiveCollections = {
  status: KpiStatus;
  value: string;
  collections_with_data: number;
  collections_inspected: number;
};

export type FailedEvents = {
  status: KpiStatus;
  terminal_failures_detected: number;
  note: string;
};

export type MongoSyncCollection = {
  collection: string;
  documents: number;
  daniel_filter_matches: number;
  all_required_timestamp_fields_present: number;
  status: string;
  last_update?: string | null;
  notes: string;
};

export type MongoSync = {
  collections: MongoSyncCollection[];
  summary: {
    total_documents: number;
    daniel_filter_matches: number;
    collections_with_data: number;
    collections_inspected: number;
    main_latency_blockers: string[];
  };
};

export type RecentEvent = {
  time?: string | null;
  event_id?: string | null;
  trigger?: string | null;
  scenario?: string | null;
  robot_action?: string | null;
  status?: string | null;
  end_to_end_latency?: string | null;
  mongodb?: string | null;
};

export type MissingTelemetryField = {
  field: string;
  state: string;
  blocked_kpis: string[];
};

export type AdminKpiDashboardData = {
  source: "real_read_only_analysis_snapshot" | "read_only_mongodb";
  database: "humanoid_assistant" | string;
  generated_from?: string;
  generated_at: string;
  daniel_filter_matches: number;
  total_documents: number;
  timestamp_shape: {
    top_level_fields_found: boolean;
    nested_timestamps_found: boolean;
  };
  top_kpis: AdminTopKpi[];
  services?: AdminKpiService[];
  pipeline_status?: Record<string, unknown>;
  latency: {
    segments: LatencySegment[];
    missing_fields: string[];
    parseability?: Record<string, unknown>;
    notes?: string[];
  };
  event_success_rate: EventSuccessRate;
  last_robot_action: LastRobotAction;
  active_collections?: ActiveCollections;
  failed_events?: FailedEvents;
  mongo_sync: MongoSync;
  recent_events: RecentEvent[];
  missing_telemetry_fields: MissingTelemetryField[];
  nlp_guardrails: {
    status: string;
    note: string;
  };
  safety: {
    read_only: boolean;
    writes_performed: boolean;
    credentials_redacted: boolean;
  };
};

export type AdminKpiDashboardProps = {
  data: AdminKpiDashboardData;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  selectedRange?: string;
  onRangeChange?: (range: string) => void;
};
