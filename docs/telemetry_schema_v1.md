# Telemetry Schema v1

Working MVP schema for SwarmSense robot telemetry.

## Mandatory Fields

| Field | Type | Source for MVP | Notes |
|---|---|---|---|
| `robot_id` | string | Assigned manually | Examples: `R1`, `R2`, `R3` |
| `timestamp` | integer | Python epoch milliseconds | Time the telemetry record is created |
| `position` | object | Webots GPS or simulated | `{ "x": float, "y": float, "z": float }` |
| `battery_pct` | float | Simulated | Range: `0` to `100` |
| `speed` | float | Calculated or simulated | Meters per second |
| `obstacle_distance` | float | Webots sensor or simulated | Meters |
| `task_status` | string | Derived or simulated | Allowed: `idle`, `moving`, `warning`, `error` |

## Optional KPI Fields

| Field | Type | Source | Notes |
|---|---|---|---|
| `robot_publish_ts` | integer | Robot/controller publish time | Useful for latency measurement |
| `bridge_forward_ts` | integer | ROS2/Kafka bridge forward time | Useful after the bridge exists |
| `ui_triggered_at` | integer | Web UI/dashboard action | Browser click or dashboard action time in epoch milliseconds |
| `backend_received_at` | integer | FastAPI/dashboard writer | Backend receipt time in epoch milliseconds |
| `bridge_received_at` | integer | `dashboard_command_bridge.py` | Time the bridge picked up the MongoDB dashboard request |
| `robot_action_started_at` | integer | Webots controller | Time Webots accepted and started the robot command |
| `robot_action_completed_at` | integer | Webots controller | Time Webots marked the requested robot action complete or ready |
| `mongodb_logged_at` | integer | MongoDB insert helpers/importer | Time the event document was inserted into MongoDB |
| `dashboard_updated_at` | integer | Dashboard telemetry formatter | Time the admin/provider telemetry output was generated |

## Example Message

```json
{
  "robot_id": "R1",
  "timestamp": 1760000000000,
  "position": {
    "x": 1.2,
    "y": 0.0,
    "z": -0.4
  },
  "battery_pct": 98.5,
  "speed": 0.12,
  "obstacle_distance": 0.45,
  "task_status": "moving",
  "robot_publish_ts": 1760000000000,
  "ui_triggered_at": 1760000000100,
  "backend_received_at": 1760000000200,
  "bridge_received_at": 1760000000300,
  "robot_action_started_at": 1760000000400,
  "robot_action_completed_at": 1760000005000,
  "mongodb_logged_at": 1760000005100,
  "dashboard_updated_at": 1760000005200
}
```

## Sprint 1 Decision

For the MVP, `battery_pct` and `task_status` may be simulated. `speed` can be calculated from position changes once Webots position data is connected. `obstacle_distance` can use Webots distance sensors if available, otherwise it can be simulated temporarily.
