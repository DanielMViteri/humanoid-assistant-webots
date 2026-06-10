"""Generate MVP robot telemetry for three simulated robots.

This is the first SwarmSense telemetry artifact. It does not require Webots,
ROS2, or Kafka yet. It proves that the team can produce messages matching
Telemetry Schema v1 before the Webots adapter is connected.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "robot_telemetry.jsonl"
VALID_TASK_STATUSES = {"idle", "moving", "warning", "error"}


@dataclass
class RobotState:
    robot_id: str
    x: float
    y: float
    z: float
    battery_pct: float
    speed: float
    obstacle_distance: float
    task_status: str = "idle"

    def step(self, tick: int, fault_robot: str | None = None, fault_start_tick: int = 0) -> None:
        """Update the robot with simple repeatable movement and health signals."""
        phase = tick / 8.0 + int(self.robot_id[1:])
        self.speed = round(0.08 + 0.04 * abs(math.sin(phase)), 3)
        self.x = round(self.x + self.speed * math.cos(phase), 3)
        self.z = round(self.z + self.speed * math.sin(phase), 3)
        self.battery_pct = round(max(0.0, self.battery_pct - random.uniform(0.02, 0.08)), 2)
        self.obstacle_distance = round(max(0.05, 0.75 + 0.4 * math.sin(phase * 1.7)), 3)

        if fault_robot == self.robot_id and tick >= fault_start_tick:
            fault_age = tick - fault_start_tick + 1
            self.battery_pct = round(max(0.0, self.battery_pct - 1.2 * fault_age), 2)
            self.obstacle_distance = round(max(0.05, self.obstacle_distance - 0.09 * fault_age), 3)
            self.speed = round(max(0.0, self.speed - 0.01 * fault_age), 3)

        if self.battery_pct < 15 or self.obstacle_distance < 0.12:
            self.task_status = "error"
        elif self.battery_pct < 30 or self.obstacle_distance < 0.25:
            self.task_status = "warning"
        else:
            self.task_status = "moving"

    def telemetry(self) -> dict:
        timestamp = int(time.time() * 1000)
        return {
            "robot_id": self.robot_id,
            "timestamp": timestamp,
            "position": {"x": self.x, "y": self.y, "z": self.z},
            "battery_pct": self.battery_pct,
            "speed": self.speed,
            "obstacle_distance": self.obstacle_distance,
            "task_status": self.task_status,
            "robot_publish_ts": timestamp,
        }


def initial_robots() -> list[RobotState]:
    return [
        RobotState("R1", x=-0.6, y=0.0, z=0.2, battery_pct=100.0, speed=0.0, obstacle_distance=1.0),
        RobotState("R2", x=0.0, y=0.0, z=-0.2, battery_pct=98.0, speed=0.0, obstacle_distance=1.0),
        RobotState("R3", x=0.6, y=0.0, z=0.2, battery_pct=96.0, speed=0.0, obstacle_distance=1.0),
    ]


def generate_events(
    robots: Iterable[RobotState],
    ticks: int,
    interval_seconds: float,
    fault_robot: str | None,
    fault_start_tick: int,
) -> Iterable[dict]:
    for tick in range(ticks):
        for robot in robots:
            robot.step(tick, fault_robot=fault_robot, fault_start_tick=fault_start_tick)
            yield robot.telemetry()
        if tick < ticks - 1:
            time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SwarmSense Telemetry Schema v1 sample data.")
    parser.add_argument("--ticks", type=int, default=10, help="Number of telemetry ticks to generate.")
    parser.add_argument("--interval", type=float, default=0.25, help="Seconds between telemetry ticks.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSONL file to write.")
    parser.add_argument("--append", action="store_true", help="Append to the output file instead of replacing it.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for repeatable demo output.")
    parser.add_argument("--fault-robot", choices=["R1", "R2", "R3"], help="Robot that should develop a fault.")
    parser.add_argument("--fault-start-tick", type=int, default=5, help="Tick when the fault starts.")
    args = parser.parse_args()

    random.seed(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    robots = initial_robots()
    file_mode = "a" if args.append else "w"

    with args.output.open(file_mode, encoding="utf-8") as output_file:
        for event in generate_events(
            robots,
            args.ticks,
            args.interval,
            fault_robot=args.fault_robot,
            fault_start_tick=args.fault_start_tick,
        ):
            line = json.dumps(event, separators=(",", ":"))
            print(line)
            output_file.write(line + "\n")

    print(f"\nWrote telemetry to {args.output}")


if __name__ == "__main__":
    main()
