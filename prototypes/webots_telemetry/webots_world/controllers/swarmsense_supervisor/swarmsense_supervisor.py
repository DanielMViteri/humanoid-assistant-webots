"""Webots supervisor that exports live SwarmSense telemetry as JSONL."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from controller import Supervisor


ROBOT_DEFS = {
    "R1": "ROBOT_R1",
    "R2": "ROBOT_R2",
    "R3": "ROBOT_R3",
}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "webots_telemetry.jsonl"
ARENA_HALF_WIDTH = 0.6
ARENA_HALF_HEIGHT = 0.9


def epoch_ms() -> int:
    return int(time.time() * 1000)


def distance_2d(a: list[float], b: list[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def estimated_obstacle_distance(position: list[float]) -> float:
    """Estimate distance to arena boundary until distance sensors are wired in."""
    x, y, _z = position
    distance_to_wall = min(
        ARENA_HALF_WIDTH - abs(x),
        ARENA_HALF_HEIGHT - abs(y),
    )
    return round(max(0.0, distance_to_wall), 3)


def task_status(battery_pct: float, obstacle_distance: float, speed: float) -> str:
    if battery_pct < 15 or obstacle_distance < 0.05:
        return "error"
    if battery_pct < 30 or obstacle_distance < 0.12 or speed < 0.005:
        return "warning"
    return "moving"


def main() -> None:
    supervisor = Supervisor()
    timestep = int(supervisor.getBasicTimeStep())
    nodes = {}

    for robot_id, def_name in ROBOT_DEFS.items():
        node = supervisor.getFromDef(def_name)
        if node is None:
            raise RuntimeError(f"Could not find Webots node {def_name} for {robot_id}")
        nodes[robot_id] = node

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    previous_positions = {
        robot_id: node.getField("translation").getSFVec3f()
        for robot_id, node in nodes.items()
    }
    previous_time = supervisor.getTime()
    battery_pct = {"R1": 100.0, "R2": 98.0, "R3": 96.0}

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        while supervisor.step(timestep) != -1:
            current_time = supervisor.getTime()
            dt = max(current_time - previous_time, timestep / 1000)

            for robot_id, node in nodes.items():
                position = node.getField("translation").getSFVec3f()
                speed = distance_2d(position, previous_positions[robot_id]) / dt
                obstacle_distance = estimated_obstacle_distance(position)
                battery_pct[robot_id] = round(max(0.0, battery_pct[robot_id] - speed * 0.02), 2)
                timestamp = epoch_ms()

                event = {
                    "robot_id": robot_id,
                    "timestamp": timestamp,
                    "position": {
                        "x": round(position[0], 3),
                        "y": round(position[1], 3),
                        "z": round(position[2], 3),
                    },
                    "battery_pct": battery_pct[robot_id],
                    "speed": round(speed, 3),
                    "obstacle_distance": obstacle_distance,
                    "task_status": task_status(battery_pct[robot_id], obstacle_distance, speed),
                    "robot_publish_ts": timestamp,
                }

                output_file.write(json.dumps(event, separators=(",", ":")) + "\n")
                output_file.flush()
                print(json.dumps(event, separators=(",", ":")))
                previous_positions[robot_id] = position

            previous_time = current_time


if __name__ == "__main__":
    main()
