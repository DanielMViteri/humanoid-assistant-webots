"""Bridge NESTO dashboard actions into real robot/perception behaviour.

The NESTO dashboard (teammates' Streamlit UI) records user actions into the
shared MongoDB. On its own that is just logged intent -- nothing happens on the
robot side. This bridge is the glue that makes UI clicks do real things:

1. Scenario requests (Find My Cane / Find My Medicine / Summon / Call Caregiver)
   in `scenario_events` -> translated into `data/raw/webots_command.json`, which
   the Webots supervisor consumes to move the NAO.

2. Mood / wellbeing check-ins in `mood_events` -> trigger real facial emotion
   recognition (webcam + DeepFace) and write the DETECTED emotion back into
   MongoDB (mood_detected / wellbeing_score_updated / negative_mood_alert), so
   the dashboard shows the real reading. This is the end-to-end perception loop.

Direction: Dashboard -> MongoDB -> THIS BRIDGE -> (Webots command file | webcam+DeepFace -> MongoDB).

Run alongside Webots (perception venv, so webcam + DeepFace are available):
    tools\\run_dashboard_bridge.cmd
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from event_schema import create_event, current_epoch_ms
from mongo_client import MongoEventClient, PROJECT_ROOT, load_dotenv, mongo_error_hint


SCENARIO_EVENTS_COLLECTION = "scenario_events"
MOOD_EVENTS_COLLECTION = "mood_events"
WEBOTS_COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
DEFAULT_POLL_SECONDS = 3.0

# Aliases the dashboard may use for each actionable robot scenario.
SCENARIO_ALIASES = {
    "find_cane": "find_cane",
    "find_my_cane": "find_cane",
    "find_medicine": "find_medicine",
    "find_my_medicine": "find_medicine",
    "summon_robot": "summon_robot",
    "summon": "summon_robot",
    "call_caregiver": "call_caregiver",
    "caregiver_call_requested": "call_caregiver",
}

# scenario -> Webots command shape (matches nlp_event_runner.command_for_decision).
SCENARIO_COMMANDS = {
    "find_cane": {
        "action": "search_object",
        "target_object": "cane",
        "intent": "find_cane",
        "task_status": "searching_for_cane",
        "robot_response": "Okay, I'll look for your cane.",
    },
    "find_medicine": {
        "action": "check_medicine",
        "target_object": "medicine_box",
        "intent": "medicine_reminder",
        "task_status": "checking_medicine",
        "robot_response": "Let me check on your medicine.",
    },
    "summon_robot": {
        "action": "support_user",
        "target_object": None,
        "intent": "general_support",
        "task_status": "summoned_to_user",
        "robot_response": "I'm on my way to you.",
    },
    "call_caregiver": {
        "action": "support_user",
        "target_object": None,
        "intent": "wellbeing_checkin",
        "task_status": "contacting_caregiver",
        "robot_response": "I'll help you reach your caregiver.",
    },
}

# Dashboard mood/wellbeing event types that should trigger facial recognition.
MOOD_TRIGGER_EVENT_TYPES = {"mood_event", "mood_check", "wellbeing_checkin"}

# Objects the Webots world actually contains. A dashboard-provided target is only
# honoured if it is one of these; otherwise the scenario's canonical target is used
# (so a profile's placeholder object like "test" still resolves find_cane -> cane).
KNOWN_WEBOTS_TARGETS = {"cane", "medicine_box"}
OBJECT_ALIASES = {
    "walking_stick": "cane",
    "pill_box": "medicine_box",
    "medication_box": "medicine_box",
}


def normalize_target(raw: str | None) -> str:
    key = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    return OBJECT_ALIASES.get(key, key)


# --------------------------------------------------------------------------- #
# Scenario requests -> Webots command file
# --------------------------------------------------------------------------- #
def normalize_scenario(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    return SCENARIO_ALIASES.get(key)


def scenario_from_document(document: dict[str, Any]) -> str | None:
    payload = document.get("payload") or {}
    for candidate in (
        document.get("scenario_type"),
        payload.get("scenario_type"),
        document.get("event_type"),
        payload.get("intent"),
    ):
        scenario = normalize_scenario(candidate)
        if scenario:
            return scenario
    return None


def build_command(scenario: str, document: dict[str, Any]) -> dict[str, Any]:
    spec = SCENARIO_COMMANDS[scenario]
    payload = document.get("payload") or {}
    requested = normalize_target(payload.get("target_object"))
    target_object = requested if requested in KNOWN_WEBOTS_TARGETS else spec["target_object"]
    now = current_epoch_ms()
    return {
        "command_id": f"cmd_dash_{now}",
        "timestamp": now,
        "source": "nesto_dashboard_bridge",
        "robot_id": document.get("robot_id", "H1"),
        "intent": spec["intent"],
        "scenario": scenario,
        "scenario_event_id": document.get("event_id"),
        "user_text": f"(dashboard) {scenario}",
        "robot_response": spec["robot_response"],
        "action": spec["action"],
        "target_object": target_object,
        "task_status": spec["task_status"],
    }


def write_webots_command(command: dict[str, Any], path: Path = WEBOTS_COMMAND_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(command, indent=2), encoding="utf-8")
    return path


def write_dispatch_event(mongo: MongoEventClient, command: dict[str, Any]) -> None:
    event = create_event(
        "robot_command_sent",
        {
            "command_id": command["command_id"],
            "intent": command["intent"],
            "action": command["action"],
            "target_object": command["target_object"],
            "scenario": command["scenario"],
            "scenario_event_id": command["scenario_event_id"],
            "command_source": "nesto_dashboard_bridge",
        },
    )
    mongo.insert_event(event)


def handle_scenario_request(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    scenario = scenario_from_document(document)
    if scenario is None:
        return False  # not an actionable robot scenario (e.g. talk_to_nesto, *_opened)
    command = build_command(scenario, document)
    command_path = write_webots_command(command)
    print(
        f"[scenario] {scenario} -> {command['action']} target={command['target_object']} "
        f"(from {document.get('event_id')}) -> {command_path}"
    )
    if not args.no_status_writeback:
        try:
            write_dispatch_event(mongo, command)
        except Exception as exc:
            print(f"  warning: could not write dispatch event: {exc}")
    return True


# --------------------------------------------------------------------------- #
# Mood check-ins -> real facial emotion recognition -> MongoDB
# --------------------------------------------------------------------------- #
def run_emotion_recognition(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    """Capture the webcam, run DeepFace, and write the detected emotion to MongoDB."""
    requested_mood = (document.get("payload") or {}).get("mood")
    source_event_id = document.get("event_id")

    if args.simulate_emotion:
        # Test path: skip webcam/DeepFace and write a canned detected emotion.
        from emotion_deepface import build_emotion_analysis_result

        result = build_emotion_analysis_result(
            dominant_emotion=args.simulate_emotion,
            confidence=0.85,
            signals=["simulated"],
            analysis_source="dashboard_simulated",
        )
    else:
        # Real path: lazy-import perception so the bridge stays robust if it is unavailable.
        try:
            from webcam_capture import capture_webcam_frame, webcam_error_hint
        except Exception as exc:
            print(f"[emotion] webcam module unavailable: {exc}")
            return False
        try:
            frame = capture_webcam_frame(
                device_index=args.device,
                countdown_seconds=args.webcam_countdown,
                label="nesto_mood_check",
            )
            print(f"[emotion] captured webcam frame: {frame}")
        except Exception as exc:
            print("[emotion] webcam capture FAILED")
            print(f"  Reason: {exc.__class__.__name__}: {exc}")
            try:
                print(f"  Hint: {webcam_error_hint(exc)}")
            except Exception:
                pass
            return False

        try:
            from emotion_deepface import analyze_face_emotion, deepface_error_hint
        except Exception as exc:
            print(f"[emotion] deepface module unavailable: {exc}")
            return False
        try:
            result = analyze_face_emotion(frame, detector_backend=args.detector_backend)
        except Exception as exc:
            print("[emotion] DeepFace analysis FAILED")
            print(f"  Reason: {exc.__class__.__name__}: {exc}")
            try:
                print(f"  Hint: {deepface_error_hint(exc)}")
            except Exception:
                pass
            return False

    summary = result["summary"]
    # Tag the events so the dashboard can tie the detection back to the request.
    for event in result["events"]:
        event["payload"]["source_event_id"] = source_event_id
        event["payload"]["self_reported_mood"] = requested_mood
        event["payload"]["trigger"] = "nesto_dashboard_mood_check"

    inserted = mongo.insert_events(result["events"])
    print(
        f"[emotion] detected '{summary['dominant_emotion']}' "
        f"(confidence={summary['confidence']}, wellbeing={summary['wellbeing_score']}, "
        f"self_reported={requested_mood}) -> MongoDB {inserted}"
    )
    return True


def handle_mood_request(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    event_type = str(document.get("event_type") or "").strip().lower()
    scenario_type = str((document.get("scenario_type") or "")).strip().lower()
    if event_type not in MOOD_TRIGGER_EVENT_TYPES and scenario_type not in MOOD_TRIGGER_EVENT_TYPES:
        return False
    return run_emotion_recognition(mongo, document, args)


# --------------------------------------------------------------------------- #
# Polling
# --------------------------------------------------------------------------- #
def process_collection(
    mongo: MongoEventClient,
    collection_name: str,
    since_ms: int,
    seen: set[str],
    handler: Callable[[MongoEventClient, dict[str, Any], argparse.Namespace], bool],
    args: argparse.Namespace,
) -> int:
    """Run `handler` over new dashboard-originated docs in a collection."""
    collection = mongo.db[collection_name]
    cursor = collection.find(
        {"timestamp": {"$gt": since_ms}, "source": "dashboard"}
    ).sort("timestamp", 1)

    highest = since_ms
    for document in cursor:
        timestamp = int(document.get("timestamp", since_ms))
        highest = max(highest, timestamp)
        event_id = str(document.get("event_id") or f"_id:{document.get('_id')}")
        if event_id in seen:
            continue
        seen.add(event_id)
        try:
            handler(mongo, document, args)
        except Exception as exc:
            print(f"  warning: handler error on {event_id}: {exc.__class__.__name__}: {exc}")
    return highest


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge NESTO dashboard actions to robot/perception behaviour.")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS, help="Polling interval.")
    parser.add_argument("--once", action="store_true", help="Run a single poll pass and exit (for testing).")
    parser.add_argument("--backfill", action="store_true", help="Also process requests already present at startup.")
    parser.add_argument("--no-status-writeback", action="store_true", help="Do not write robot_command_sent events back to MongoDB.")
    parser.add_argument("--no-scenarios", action="store_true", help="Disable the scenario_events -> Webots command handler.")
    parser.add_argument("--no-emotion", action="store_true", help="Disable the mood_events -> facial recognition handler.")
    parser.add_argument("--device", type=int, default=0, help="Webcam device index for emotion recognition.")
    parser.add_argument("--webcam-countdown", type=int, default=3, help="Seconds before the webcam frame is captured.")
    parser.add_argument("--detector-backend", default="opencv", help="DeepFace detector backend.")
    parser.add_argument("--simulate-emotion", default="", help="Skip webcam/DeepFace and record this emotion instead (testing).")
    args = parser.parse_args()

    load_dotenv()
    try:
        mongo = MongoEventClient.from_env()
        mongo.ping()
    except Exception as exc:
        print("MongoDB connection: FAILED")
        print(f"Reason: {exc}")
        print(f"Hint: {mongo_error_hint(exc)}")
        return 1

    handlers: list[tuple[str, Callable[..., bool]]] = []
    if not args.no_scenarios:
        handlers.append((SCENARIO_EVENTS_COLLECTION, handle_scenario_request))
    if not args.no_emotion:
        handlers.append((MOOD_EVENTS_COLLECTION, handle_mood_request))

    print("MongoDB connection: OK")
    print(f"Database: {mongo.database_name}")
    print(f"Watching: {', '.join(name for name, _ in handlers) or '(nothing)'}")
    if not args.no_scenarios:
        print(f"  scenario_events -> {WEBOTS_COMMAND_PATH}")
    if not args.no_emotion:
        mode = f"SIMULATED ({args.simulate_emotion})" if args.simulate_emotion else f"webcam device {args.device} + DeepFace"
        print(f"  mood_events -> facial emotion recognition [{mode}] -> MongoDB")

    seen: set[str] = set()
    # Only react to requests created after the bridge starts unless --backfill.
    start_ms = 0 if args.backfill else current_epoch_ms()
    since: dict[str, int] = {name: start_ms for name, _ in handlers}

    if args.once:
        for name, handler in handlers:
            since[name] = process_collection(mongo, name, since[name], seen, handler, args)
        return 0

    print(f"Polling every {args.poll_seconds:.1f}s. Press Ctrl+C to stop.")
    try:
        while True:
            for name, handler in handlers:
                since[name] = process_collection(mongo, name, since[name], seen, handler, args)
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("\nDashboard action bridge stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
