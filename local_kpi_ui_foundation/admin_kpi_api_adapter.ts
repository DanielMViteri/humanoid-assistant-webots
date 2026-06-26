import type { AdminKpiDashboardData } from "./admin_kpi_types";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertAdminKpiShape(value: unknown): asserts value is AdminKpiDashboardData {
  if (!isObject(value)) {
    throw new Error("Admin KPI response must be an object.");
  }

  const requiredKeys = [
    "generated_at",
    "database",
    "top_kpis",
    "latency",
    "event_success_rate",
    "last_robot_action",
    "mongo_sync",
    "recent_events",
    "missing_telemetry_fields",
    "nlp_guardrails",
    "safety"
  ];

  for (const key of requiredKeys) {
    if (!(key in value)) {
      throw new Error(`Admin KPI response missing key: ${key}`);
    }
  }

  if (!Array.isArray(value.top_kpis)) {
    throw new Error("Admin KPI response top_kpis must be an array.");
  }

  const latency = value.latency;
  if (!isObject(latency) || !Array.isArray(latency.segments)) {
    throw new Error("Admin KPI response latency.segments must be an array.");
  }

  const safety = value.safety;
  if (!isObject(safety) || safety.read_only !== true || safety.writes_performed !== false) {
    throw new Error("Admin KPI response safety flags are invalid.");
  }
}

export async function fetchAdminKpis(baseUrl = ""): Promise<AdminKpiDashboardData> {
  const response = await fetch(`${baseUrl}/api/admin/kpis`, {
    method: "GET",
    headers: {
      "Accept": "application/json"
    }
  });

  if (!response.ok) {
    throw new Error(`Admin KPI request failed with ${response.status}`);
  }

  const data: unknown = await response.json();
  assertAdminKpiShape(data);
  return data;
}
