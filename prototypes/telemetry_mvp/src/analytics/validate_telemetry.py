"""Validate SwarmSense Telemetry Schema v1 JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "robot_telemetry.jsonl"
MANDATORY_FIELDS = {
    "robot_id",
    "timestamp",
    "position",
    "battery_pct",
    "speed",
    "obstacle_distance",
    "task_status",
}
VALID_TASK_STATUSES = {"idle", "moving", "warning", "error"}


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def validate_event(event: dict, line_number: int) -> list[str]:
    errors: list[str] = []
    missing = MANDATORY_FIELDS - set(event)
    if missing:
        errors.append(f"line {line_number}: missing fields {sorted(missing)}")

    if not isinstance(event.get("robot_id"), str) or not event.get("robot_id"):
        errors.append(f"line {line_number}: robot_id must be a non-empty string")

    if not isinstance(event.get("timestamp"), int):
        errors.append(f"line {line_number}: timestamp must be an integer epoch milliseconds value")

    position = event.get("position")
    if not isinstance(position, dict):
        errors.append(f"line {line_number}: position must be an object")
    else:
        for axis in ("x", "y", "z"):
            if not is_number(position.get(axis)):
                errors.append(f"line {line_number}: position.{axis} must be numeric")

    battery_pct = event.get("battery_pct")
    if not is_number(battery_pct) or not 0 <= battery_pct <= 100:
        errors.append(f"line {line_number}: battery_pct must be numeric and between 0 and 100")

    if not is_number(event.get("speed")) or event["speed"] < 0:
        errors.append(f"line {line_number}: speed must be a non-negative number")

    if not is_number(event.get("obstacle_distance")) or event["obstacle_distance"] < 0:
        errors.append(f"line {line_number}: obstacle_distance must be a non-negative number")

    if event.get("task_status") not in VALID_TASK_STATUSES:
        errors.append(f"line {line_number}: task_status must be one of {sorted(VALID_TASK_STATUSES)}")

    for optional_ts in ("robot_publish_ts", "bridge_forward_ts"):
        if optional_ts in event and not isinstance(event[optional_ts], int):
            errors.append(f"line {line_number}: {optional_ts} must be an integer when present")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a SwarmSense Telemetry Schema v1 JSONL file.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="JSONL telemetry file to validate.")
    args = parser.parse_args()

    all_errors: list[str] = []
    event_count = 0
    robot_ids: set[str] = set()

    with args.input.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                all_errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue

            event_count += 1
            robot_ids.add(str(event.get("robot_id")))
            all_errors.extend(validate_event(event, line_number))

    if all_errors:
        print("Telemetry validation failed:")
        for error in all_errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"Telemetry validation passed: {event_count} events for robots {sorted(robot_ids)}")


if __name__ == "__main__":
    main()
