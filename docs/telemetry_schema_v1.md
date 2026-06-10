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
  "robot_publish_ts": 1760000000000
}
```

## Sprint 1 Decision

For the MVP, `battery_pct` and `task_status` may be simulated. `speed` can be calculated from position changes once Webots position data is connected. `obstacle_distance` can use Webots distance sensors if available, otherwise it can be simulated temporarily.
