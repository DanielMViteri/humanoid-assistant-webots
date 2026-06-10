"""Generate and optionally insert Sprint 2 humanoid assistant feature events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import sleep
from typing import Callable

from event_schema import collection_for_event, create_event
from mongo_client import MongoEventClient, PROJECT_ROOT, mongo_error_hint


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "sprint2_feature_events.jsonl"


def build_find_cane_scenario() -> list[dict]:
    """Demo scenario: the user asks the robot to locate a cane."""
    scenario_id = "find_cane_demo_01"
    return [
        create_event(
            "session_started",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_find_cane_01",
                "channel": "typed_text",
            },
        ),
        create_event(
            "user_message",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_find_cane_01",
                "text": "Can you help me find my cane?",
                "detected_intent": "find_object",
            },
        ),
        create_event(
            "robot_status_updated",
            {
                "scenario_id": scenario_id,
                "status": "active",
                "battery_pct": 96.4,
                "current_room": "living_room",
                "navigation_state": "stationary",
            },
        ),
        create_event(
            "room_detected",
            {
                "scenario_id": scenario_id,
                "room": "living_room",
                "confidence": 0.97,
                "method": "simulated_webots_zone",
            },
        ),
        create_event(
            "object_detected",
            {
                "scenario_id": scenario_id,
                "object": "cane",
                "confidence": 0.91,
                "position": {"x": 1.35, "y": 0.0, "z": 0.42},
            },
        ),
        create_event(
            "object_distance_estimated",
            {
                "scenario_id": scenario_id,
                "object": "cane",
                "distance_m": 1.24,
                "sensor": "simulated_depth_camera",
            },
        ),
        create_event(
            "scene_described",
            {
                "scenario_id": scenario_id,
                "description": "The cane is near the chair in the living room.",
                "detected_objects": ["cane", "chair", "table"],
            },
        ),
        create_event(
            "robot_response",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_find_cane_01",
                "text": "I found your cane near the chair in the living room, about 1.2 meters away.",
                "response_type": "object_location_guidance",
            },
        ),
    ]


def build_medicine_reminder_scenario() -> list[dict]:
    """Demo scenario: the robot sees medication and creates a reminder event."""
    scenario_id = "medicine_reminder_demo_01"
    return [
        create_event(
            "robot_status_updated",
            {
                "scenario_id": scenario_id,
                "status": "active",
                "battery_pct": 94.8,
                "current_room": "kitchen",
                "navigation_state": "observing",
            },
        ),
        create_event(
            "room_detected",
            {
                "scenario_id": scenario_id,
                "room": "kitchen",
                "confidence": 0.95,
                "method": "simulated_webots_zone",
            },
        ),
        create_event(
            "object_detected",
            {
                "scenario_id": scenario_id,
                "object": "medicine_box",
                "confidence": 0.88,
                "position": {"x": 0.62, "y": 0.0, "z": -0.25},
            },
        ),
        create_event(
            "object_distance_estimated",
            {
                "scenario_id": scenario_id,
                "object": "medicine_box",
                "distance_m": 0.72,
                "sensor": "simulated_depth_camera",
            },
        ),
        create_event(
            "medicine_reminder_due",
            {
                "scenario_id": scenario_id,
                "medicine_name": "afternoon_medication",
                "scheduled_time": "15:00",
                "reminder_status": "due",
            },
        ),
        create_event(
            "important_object_alert",
            {
                "scenario_id": scenario_id,
                "object": "medicine_box",
                "severity": "info",
                "reason": "Medication-related object detected in the current room.",
                "recommended_action": "remind_user_if_reminder_due",
            },
        ),
        create_event(
            "robot_response",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_medicine_01",
                "text": "I can see your medicine box on the kitchen table. It is time for your afternoon medication.",
                "response_type": "medicine_reminder",
            },
        ),
    ]


def build_wellbeing_checkin_scenario() -> list[dict]:
    """Demo scenario: the robot performs a short wellbeing check-in."""
    scenario_id = "wellbeing_checkin_demo_01"
    return [
        create_event(
            "session_started",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_wellbeing_01",
                "channel": "typed_text",
            },
        ),
        create_event(
            "user_message",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_wellbeing_01",
                "text": "I feel a bit lonely and tired today.",
                "detected_intent": "wellbeing_checkin",
            },
        ),
        create_event(
            "mood_detected",
            {
                "scenario_id": scenario_id,
                "mood": "low",
                "confidence": 0.82,
                "signals": ["lonely", "tired"],
            },
        ),
        create_event(
            "wellbeing_score_updated",
            {
                "scenario_id": scenario_id,
                "score": 42,
                "scale": "0-100",
                "trend": "decreasing",
            },
        ),
        create_event(
            "negative_mood_alert",
            {
                "scenario_id": scenario_id,
                "severity": "warning",
                "reason": "Low wellbeing score and negative mood language detected.",
                "recommended_action": "suggest_supportive_conversation",
            },
        ),
        create_event(
            "robot_response",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_wellbeing_01",
                "text": "I'm sorry you're feeling this way. Would you like to talk for a few minutes or contact someone you trust?",
                "response_type": "emotional_support",
            },
        ),
        create_event(
            "session_ended",
            {
                "scenario_id": scenario_id,
                "session_id": "sess_wellbeing_01",
                "summary": "User reported feeling lonely and tired; supportive response provided.",
            },
        ),
    ]


SCENARIO_BUILDERS: dict[str, Callable[[], list[dict]]] = {
    "find_cane": build_find_cane_scenario,
    "medicine_reminder": build_medicine_reminder_scenario,
    "wellbeing_checkin": build_wellbeing_checkin_scenario,
}


def build_sprint2_events(scenario_name: str) -> list[dict]:
    """Create Sprint 2 demo events for one named scenario or all scenarios."""
    if scenario_name == "all":
        events: list[dict] = []
        for builder in SCENARIO_BUILDERS.values():
            events.extend(builder())
        return events
    return SCENARIO_BUILDERS[scenario_name]()


def write_jsonl(events: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Sprint 2 humanoid assistant feature-event scenario.")
    parser.add_argument(
        "--scenario",
        choices=[*SCENARIO_BUILDERS.keys(), "all"],
        default="all",
        help="Demo scenario to generate. Default: all.",
    )
    parser.add_argument("--insert", action="store_true", help="Insert generated events into MongoDB Atlas.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSONL output path for generated events.")
    parser.add_argument("--no-output", action="store_true", help="Do not write a local JSONL copy.")
    parser.add_argument("--delay", type=float, default=0.0, help="Optional delay in seconds between printed events.")
    parser.add_argument("--pretty", action="store_true", help="Print events in readable JSON.")
    args = parser.parse_args()

    events = build_sprint2_events(args.scenario)
    route_counts: dict[str, int] = {}

    for event in events:
        collection = collection_for_event(event["event_type"])
        route_counts[collection] = route_counts.get(collection, 0) + 1
        if args.pretty:
            print(json.dumps(event, indent=2))
        else:
            print(json.dumps(event, separators=(",", ":")))
        if args.delay > 0:
            sleep(args.delay)

    if not args.no_output:
        write_jsonl(events, args.output)
        print(f"Wrote {len(events)} events to {args.output}")

    print(f"Generated {len(events)} events for scenario '{args.scenario}': {route_counts}")

    if args.insert:
        try:
            mongo = MongoEventClient.from_env()
            mongo.ping()
            inserted_counts = mongo.insert_events(events)
        except Exception as exc:
            print("MongoDB insert: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {mongo_error_hint(exc)}")
            print("Local JSONL event generation completed successfully.")
            return 1
        print(f"Inserted {sum(inserted_counts.values())} events into MongoDB Atlas: {inserted_counts}")
    else:
        print("MongoDB insert skipped. Re-run with --insert after configuring .env.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
