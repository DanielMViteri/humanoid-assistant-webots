# Mohammad and Daniel KPI Requirements

## Mohammad KPI Request

Mohammad asked for an Admin KPI Dashboard that:

- Uses the same NESTO color palette.
- Looks like the approved NESTO Care Operations dashboard, not a narrow static report.
- Shows the requested KPI cards.
- Uses real MongoDB data only.
- Does not invent values.
- Does not invent latency.
- Shows waiting or missing states when timestamp data is incomplete.
- Can be built now as a UI foundation while the final web app branch is pending.
- Includes interactive controls for refresh, time range selection, collection filtering, log search, sortable tables, expandable missing telemetry details, and section navigation.

Required top KPI cards:

1. Pipeline Status
2. End-to-End Latency
3. MongoDB Write Latency
4. Dashboard Refresh Latency
5. Event Success Rate
6. Last Robot Action
7. Active Collections
8. Failed Events

Required dashboard sections:

1. Pipeline Health Overview
2. Latency KPIs
3. Event Throughput and Success Rate
4. Robot Action Status
5. MongoDB Sync Monitor
6. Recent Event Logs
7. Missing Telemetry Fields

## Daniel MongoDB Analysis Request

Daniel asked to analyze what MongoDB already contains and identify what is missing for KPI calculations.

Daniel filter:

```json
{
  "payload.active_command_id": { "$ne": null },
  "ui_triggered_at": { "$exists": true }
}
```

Required timestamp fields:

- `ui_triggered_at`
- `backend_received_at`
- `bridge_received_at`
- `robot_action_started_at`
- `robot_action_completed_at`
- `mongodb_logged_at`
- `dashboard_updated_at`

Latency formulas to support later:

- UI to Backend: `backend_received_at - ui_triggered_at`
- Backend to Bridge: `bridge_received_at - backend_received_at`
- Bridge to Robot Start: `robot_action_started_at - bridge_received_at`
- Robot Action Duration: `robot_action_completed_at - robot_action_started_at`
- Robot to MongoDB: `mongodb_logged_at - robot_action_completed_at`
- MongoDB to Dashboard: `dashboard_updated_at - mongodb_logged_at`
- End-to-End: `dashboard_updated_at - ui_triggered_at`

## Current Verified Findings

- Daniel filter matched `79` documents.
- Timestamp fields are top-level only.
- No nested `timestamps.*` fields were found.
- `robot_action_completed_at` is null / not parseable where present.
- `dashboard_updated_at` is null / not parseable where present.
- Full end-to-end latency is blocked until these values are non-null and parseable.

## NLP Guardrails Note

Daniel reported task-focused LLM instructions. This dashboard should not invent additional guardrail telemetry. Current UI wording is:

```text
Documented task-focused instructions, not telemetry-validated.
```
