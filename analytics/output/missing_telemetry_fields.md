# MongoDB Telemetry Timestamp Field Check

Generated at: `2026-06-25T22:19:54.559949+00:00`
Database: `humanoid_assistant`
Connection status: `connected`
Daniel filter total matches: `79`

## Required Timestamp Fields

| Field | Top-level count | Nested count | Any-shape count | Status |
|---|---:|---:|---:|---|
| `ui_triggered_at` | 414 | 0 | 414 | Partial |
| `backend_received_at` | 414 | 0 | 414 | Partial |
| `bridge_received_at` | 414 | 0 | 414 | Partial |
| `robot_action_started_at` | 408 | 0 | 408 | Partial |
| `robot_action_completed_at` | 408 | 0 | 408 | Partial |
| `mongodb_logged_at` | 2897 | 0 | 2897 | Partial |
| `dashboard_updated_at` | 408 | 0 | 408 | Partial |

## Missing Globally

- None. All required timestamp fields appear at least once in MongoDB.

## Partial Coverage Globally

- `ui_triggered_at`
- `backend_received_at`
- `bridge_received_at`
- `robot_action_started_at`
- `robot_action_completed_at`
- `mongodb_logged_at`
- `dashboard_updated_at`

## Latency KPI Availability

| Metric | Status | Valid samples | Missing fields | Invalid parse | Negative durations |
|---|---|---:|---:|---:|---:|
| `ui_to_backend` | Partial | 93 | 26705 | 0 | 0 |
| `backend_to_bridge` | Partial | 93 | 26705 | 0 | 0 |
| `bridge_to_robot_start` | Partial | 78 | 26720 | 0 | 0 |
| `robot_action_duration` | Unavailable | 0 | 26798 | 0 | 0 |
| `robot_to_mongodb` | Unavailable | 0 | 26798 | 0 | 0 |
| `mongodb_to_dashboard` | Unavailable | 0 | 26798 | 0 | 0 |
| `end_to_end` | Unavailable | 0 | 26798 | 0 | 0 |

## Null Timestamp Values

| Field | Top-level null | Nested null | Any null |
|---|---:|---:|---:|
| `ui_triggered_at` | 321 | 0 | 321 |
| `backend_received_at` | 321 | 0 | 321 |
| `bridge_received_at` | 321 | 0 | 321 |
| `robot_action_started_at` | 330 | 0 | 330 |
| `robot_action_completed_at` | 408 | 0 | 408 |
| `mongodb_logged_at` | 0 | 0 | 0 |
| `dashboard_updated_at` | 408 | 0 | 408 |
