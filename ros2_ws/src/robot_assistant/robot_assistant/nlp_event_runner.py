"""Classify user input with OpenAI and generate MongoDB-ready assistant events."""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from event_schema import collection_for_event, create_event, current_epoch_ms
from elevenlabs_voice import elevenlabs_error_hint, open_audio_file, synthesize_speech
from mongo_client import MongoEventClient, PROJECT_ROOT, load_dotenv, mongo_error_hint
from scenario_runner import SCENARIO_BUILDERS, write_jsonl


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "nlp_feature_events.jsonl"
WEBOTS_COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
DEFAULT_MODEL = "gpt-4o-mini"
SUPPORTED_INTENTS = ("find_cane", "medicine_reminder", "wellbeing_checkin", "general_support", "unknown")

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent",
        "confidence",
        "emotion",
        "risk_level",
        "robot_response",
        "suggested_events",
        "reason",
    ],
    "properties": {
        "intent": {"type": "string", "enum": list(SUPPORTED_INTENTS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "emotion": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "robot_response": {"type": "string"},
        "suggested_events": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "session_started",
                    "user_message",
                    "robot_response",
                    "room_detected",
                    "object_detected",
                    "object_distance_estimated",
                    "scene_described",
                    "medicine_reminder_due",
                    "mood_detected",
                    "wellbeing_score_updated",
                    "important_object_alert",
                    "negative_mood_alert",
                ],
            },
        },
        "reason": {"type": "string"},
    },
}


def classify_with_openai(user_text: str, model: str) -> dict[str, Any]:
    """Ask OpenAI for a structured intent decision."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is not installed. Run: pip install -r requirements-openai.txt") from exc

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You classify user messages for a simulated elderly-care humanoid assistant. "
                    "Return only the structured decision. The system can currently demonstrate these "
                    "intents: find_cane, medicine_reminder, wellbeing_checkin, general_support, unknown. "
                    "Use find_cane for lost cane or mobility-aid requests. Use medicine_reminder for "
                    "medicine, pills, reminders, or medication boxes. Use wellbeing_checkin for loneliness, "
                    "sadness, tiredness, stress, anxiety, or emotional support."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "humanoid_assistant_intent_decision",
                "strict": True,
                "schema": DECISION_SCHEMA,
            }
        },
    )
    return json.loads(response.output_text)


def classify_with_mock(user_text: str) -> dict[str, Any]:
    """Local deterministic classifier for quick tests without API calls."""
    lowered = user_text.lower()
    if "cane" in lowered or "walking stick" in lowered:
        return {
            "intent": "find_cane",
            "confidence": 0.9,
            "emotion": "neutral",
            "risk_level": "low",
            "robot_response": "I can help you find your cane. I will check the living room first.",
            "suggested_events": ["user_message", "room_detected", "object_detected", "object_distance_estimated", "robot_response"],
            "reason": "The user is asking for help locating a cane.",
        }
    if "medicine" in lowered or "pill" in lowered or "medication" in lowered:
        return {
            "intent": "medicine_reminder",
            "confidence": 0.88,
            "emotion": "neutral",
            "risk_level": "medium",
            "robot_response": "I can help with your medication reminder and check where the medicine box is.",
            "suggested_events": ["user_message", "object_detected", "medicine_reminder_due", "important_object_alert", "robot_response"],
            "reason": "The user mentioned medicine or pills.",
        }
    if any(word in lowered for word in ("lonely", "sad", "tired", "stress", "anxious", "alone")):
        return {
            "intent": "wellbeing_checkin",
            "confidence": 0.86,
            "emotion": "low",
            "risk_level": "medium",
            "robot_response": "I'm sorry you're feeling this way. Would you like to talk for a few minutes?",
            "suggested_events": ["user_message", "mood_detected", "wellbeing_score_updated", "negative_mood_alert", "robot_response"],
            "reason": "The user expressed negative or low mood language.",
        }
    return {
        "intent": "general_support",
        "confidence": 0.6,
        "emotion": "neutral",
        "risk_level": "low",
        "robot_response": "I understand. I can help with finding objects, medication reminders, or wellbeing check-ins.",
        "suggested_events": ["user_message", "robot_response"],
        "reason": "The message did not clearly match a supported demo scenario.",
    }


def build_events_from_decision(user_text: str, decision: dict[str, Any]) -> list[dict]:
    """Convert an OpenAI decision into approved schema events."""
    intent = decision["intent"]
    scenario_id = f"nlp_{intent}_{current_epoch_ms()}"
    session_id = f"sess_{current_epoch_ms()}"

    events = [
        create_event(
            "session_started",
            {"scenario_id": scenario_id, "session_id": session_id, "channel": "typed_text"},
        ),
        create_event(
            "user_message",
            {
                "scenario_id": scenario_id,
                "session_id": session_id,
                "text": user_text,
                "detected_intent": intent,
                "intent_confidence": round(float(decision["confidence"]), 3),
            },
        ),
    ]

    if intent in SCENARIO_BUILDERS:
        for event in SCENARIO_BUILDERS[intent]():
            if event["event_type"] in {"session_started", "user_message", "robot_response", "session_ended"}:
                continue
            copied = deepcopy(event)
            copied["payload"]["scenario_id"] = scenario_id
            if copied["event_type"] == "mood_detected":
                copied["payload"]["mood"] = decision["emotion"]
                copied["payload"]["confidence"] = round(float(decision["confidence"]), 3)
            if copied["event_type"].endswith("_alert"):
                copied["payload"]["severity"] = "warning" if decision["risk_level"] == "medium" else decision["risk_level"]
            events.append(copied)

    events.append(
        create_event(
            "robot_response",
            {
                "scenario_id": scenario_id,
                "session_id": session_id,
                "text": decision["robot_response"],
                "response_type": intent,
                "llm_reason": decision["reason"],
            },
        )
    )

    if intent == "wellbeing_checkin":
        events.append(
            create_event(
                "session_ended",
                {
                    "scenario_id": scenario_id,
                    "session_id": session_id,
                    "summary": "Wellbeing check-in completed from NLP-classified user input.",
                },
            )
        )

    return events


def summarize_routes(events: list[dict]) -> dict[str, int]:
    route_counts: dict[str, int] = {}
    for event in events:
        collection = collection_for_event(event["event_type"])
        route_counts[collection] = route_counts.get(collection, 0) + 1
    return route_counts


def attach_audio_to_robot_response(events: list[dict], audio_path: str) -> None:
    """Annotate the robot response event with the generated audio artifact path."""
    for event in reversed(events):
        if event["event_type"] == "robot_response":
            event["payload"]["speech_provider"] = "elevenlabs"
            event["payload"]["audio_path"] = audio_path
            return


def command_for_decision(user_text: str, decision: dict[str, Any]) -> dict[str, Any] | None:
    """Translate an NLP decision into a simple Webots robot command."""
    intent = decision["intent"]
    actions = {
        "find_cane": {
            "action": "search_object",
            "target_object": "cane",
            "task_status": "searching_for_cane",
        },
        "medicine_reminder": {
            "action": "check_medicine",
            "target_object": "medicine_box",
            "task_status": "checking_medicine",
        },
        "wellbeing_checkin": {
            "action": "support_user",
            "target_object": None,
            "task_status": "wellbeing_support",
        },
    }
    if intent not in actions:
        return None

    command = {
        "command_id": f"cmd_{current_epoch_ms()}",
        "timestamp": current_epoch_ms(),
        "source": "assistant_nlp",
        "robot_id": "H1",
        "intent": intent,
        "user_text": user_text,
        "robot_response": decision["robot_response"],
        **actions[intent],
    }
    return command


def write_webots_command(command: dict[str, Any], path: Path = WEBOTS_COMMAND_PATH) -> Path:
    """Write the latest assistant command for the Webots controller to poll."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(command, indent=2), encoding="utf-8")
    return path


def process_user_message(user_text: str, args: argparse.Namespace, mongo: MongoEventClient | None = None) -> int:
    """Classify one user message, print the robot response, and optionally insert events."""
    decision = classify_with_mock(user_text) if args.mock else classify_with_openai(user_text, args.model)
    events = build_events_from_decision(user_text, decision)
    command = command_for_decision(user_text, decision)
    if args.webots_command and command is not None:
        command_path = write_webots_command(command)
        events.append(
            create_event(
                "robot_command_sent",
                {
                    "command_id": command["command_id"],
                    "intent": command["intent"],
                    "action": command["action"],
                    "target_object": command["target_object"],
                    "command_path": str(command_path),
                },
            )
        )
        print(f"Webots command: {command['action']} -> {command_path}")
    route_counts = summarize_routes(events)

    print(f"\nRobot: {decision['robot_response']}")
    print(f"Intent: {decision['intent']} | confidence={decision['confidence']} | risk={decision['risk_level']}")
    print(f"Generated {len(events)} events: {route_counts}")

    if args.speak:
        try:
            audio_path = synthesize_speech(decision["robot_response"])
            attach_audio_to_robot_response(events, str(audio_path))
            print(f"Speech audio: {audio_path}")
            if args.play_audio:
                open_audio_file(audio_path)
        except Exception as exc:
            print("ElevenLabs speech: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {elevenlabs_error_hint(exc)}")

    if args.pretty:
        print("NLP decision")
        print(json.dumps(decision, indent=2))
        for event in events:
            print(json.dumps(event, indent=2))

    if not args.no_output:
        output_path = DEFAULT_OUTPUT if args.output == str(DEFAULT_OUTPUT) else PROJECT_ROOT / args.output
        write_jsonl(events, output_path)
        print(f"Wrote {len(events)} events to {output_path}")

    if args.insert:
        try:
            active_mongo = mongo or MongoEventClient.from_env()
            if mongo is None:
                active_mongo.ping()
            inserted_counts = active_mongo.insert_events(events)
        except Exception as exc:
            print("MongoDB insert: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {mongo_error_hint(exc)}")
            print("OpenAI classification and local JSONL event generation completed successfully.")
            return 1
        print(f"Inserted {sum(inserted_counts.values())} events into MongoDB Atlas: {inserted_counts}")
    else:
        print("MongoDB insert skipped. Re-run with --insert when ready.")

    return 0


def run_interactive(args: argparse.Namespace) -> int:
    """Run a simple terminal assistant loop."""
    print("Interactive humanoid assistant mode. Type 'exit' or 'quit' to stop.")
    mongo: MongoEventClient | None = None
    if args.insert:
        try:
            mongo = MongoEventClient.from_env()
            mongo.ping()
            print("MongoDB connection: OK")
        except Exception as exc:
            print("MongoDB connection: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {mongo_error_hint(exc)}")
            print("Continuing without insertion. Your messages can still be classified.")
            args.insert = False

    while True:
        user_text = input("\nYou: ").strip()
        if user_text.lower() in {"exit", "quit"}:
            print("Session ended.")
            return 0
        if not user_text:
            continue
        process_user_message(user_text, args, mongo=mongo)


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify user input with OpenAI and generate assistant events.")
    parser.add_argument("--text", help="User message to classify. If omitted, the script prompts for input.")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL), help=f"OpenAI model. Default: {DEFAULT_MODEL}")
    parser.add_argument("--mock", action="store_true", help="Use local mock classification instead of OpenAI.")
    parser.add_argument("--insert", action="store_true", help="Insert generated events into MongoDB Atlas.")
    parser.add_argument("--interactive", action="store_true", help="Keep prompting for user messages until exit.")
    parser.add_argument("--speak", action="store_true", help="Generate ElevenLabs speech audio for each robot response.")
    parser.add_argument("--play-audio", action="store_true", help="Open the generated audio file after speech generation.")
    parser.add_argument("--webots-command", action="store_true", help="Write the latest robot command for Webots to consume.")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="JSONL output path for generated events.")
    parser.add_argument("--no-output", action="store_true", help="Do not write a local JSONL copy.")
    parser.add_argument("--pretty", action="store_true", help="Print readable JSON.")
    args = parser.parse_args()

    load_dotenv()
    if args.interactive:
        return run_interactive(args)

    user_text = args.text or input("User message: ").strip()
    if not user_text:
        raise SystemExit("No user message provided.")
    return process_user_message(user_text, args)


if __name__ == "__main__":
    raise SystemExit(main())
