"""Classify user input with OpenAI and generate MongoDB-ready assistant events."""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from emotion_deepface import (
    DEFAULT_DETECTOR_BACKEND,
    analyze_face_emotion,
    build_emotion_analysis_result,
    deepface_error_hint,
)
from event_schema import collection_for_event, create_event, current_epoch_ms
from elevenlabs_voice import (
    elevenlabs_error_hint,
    open_audio_file,
    repair_ssl_cert_environment,
    synthesize_speech,
)
from memory_chromadb import ChromaMemoryStore, build_memory_context, chroma_error_hint
from mongo_client import MongoEventClient, PROJECT_ROOT, load_dotenv, mongo_error_hint
from scenario_runner import SCENARIO_BUILDERS, write_jsonl
from vision_yolo import DEFAULT_YOLO_MODEL, analyze_scene, yolo_error_hint
from webcam_capture import capture_webcam_frame, webcam_error_hint


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "nlp_feature_events.jsonl"
WEBOTS_COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
DEFAULT_LIVE_EMOTION_PATH = PROJECT_ROOT / "data" / "raw" / "live_emotion" / "latest_emotion.json"
DEFAULT_MODEL = "gpt-4o-mini"
SUPPORTED_INTENTS = ("find_cane", "medicine_reminder", "wellbeing_checkin", "general_support", "unknown")
SCENE_EVENT_TYPES = {"object_detected", "object_distance_estimated", "scene_described", "important_object_alert"}
FACE_EVENT_TYPES = {"mood_detected", "wellbeing_score_updated", "negative_mood_alert"}
INTENT_TARGETS = {
    "find_cane": "cane",
    "medicine_reminder": "medicine_box",
}

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


def resolve_input_path(raw_path: str | None) -> Path | None:
    """Resolve a CLI path relative to the project root when needed."""
    if not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def infer_target_hint(user_text: str) -> str | None:
    """Infer a target object hint from raw user text before intent classification."""
    lowered = user_text.lower()
    if "cane" in lowered or "walking stick" in lowered:
        return "cane"
    if "medicine" in lowered or "pill" in lowered or "medication" in lowered:
        return "medicine_box"
    return None


def build_runtime_context(
    memory_hits: list[dict[str, Any]] | None = None,
    scene_summary: dict[str, Any] | None = None,
    face_summary: dict[str, Any] | None = None,
) -> str:
    """Build one compact context block for the OpenAI classifier."""
    blocks: list[str] = []
    if memory_hits:
        memory_block = build_memory_context(memory_hits)
        if memory_block:
            blocks.append(f"Relevant past conversation memory:\n{memory_block}")
    if scene_summary:
        blocks.append(
            "Scene perception summary:\n"
            + json.dumps(
                {
                    "detected_objects": scene_summary.get("detected_objects", []),
                    "target_object": scene_summary.get("target_object"),
                    "target_found": scene_summary.get("target_found"),
                    "target_distance_m": scene_summary.get("target_distance_m"),
                    "description": scene_summary.get("description"),
                },
                ensure_ascii=True,
            )
        )
    if face_summary:
        blocks.append(
            "Facial emotion summary:\n"
            + json.dumps(
                {
                    "dominant_emotion": face_summary.get("dominant_emotion"),
                    "confidence": face_summary.get("confidence"),
                    "wellbeing_score": face_summary.get("wellbeing_score"),
                    "signals": face_summary.get("signals", []),
                },
                ensure_ascii=True,
            )
        )
    return "\n\n".join(blocks)


def resolve_perception_inputs(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    """Resolve static image inputs and optionally capture a live webcam frame."""
    scene_image = resolve_input_path(getattr(args, "scene_image", None))
    face_image = resolve_input_path(getattr(args, "face_image", None))
    use_webcam_scene = bool(getattr(args, "webcam_scene", False))
    use_webcam_face = bool(getattr(args, "webcam_face", False))

    if not (use_webcam_scene or use_webcam_face):
        return scene_image, face_image

    try:
        webcam_image = capture_webcam_frame(
            device_index=getattr(args, "webcam_device", 0),
            countdown_seconds=getattr(args, "webcam_countdown", 3),
            label="assistant_webcam",
        )
        print(f"Webcam frame: {webcam_image}")
    except Exception as exc:
        print("Webcam capture: FAILED")
        print(f"Reason: {exc.__class__.__name__}: {exc}")
        print(f"Hint: {webcam_error_hint(exc)}")
        return scene_image, face_image

    if use_webcam_scene:
        scene_image = webcam_image
    if use_webcam_face:
        face_image = webcam_image
    if use_webcam_scene and use_webcam_face:
        print("Reusing the same live webcam frame for scene and face perception.")
    return scene_image, face_image


def resolve_live_emotion_summary(args: argparse.Namespace) -> dict[str, Any] | None:
    """Load the latest summary written by the background emotion monitor."""
    if not getattr(args, "use_live_emotion", False):
        return None

    configured = getattr(args, "live_emotion_path", None)
    path = resolve_input_path(configured) if configured else DEFAULT_LIVE_EMOTION_PATH
    if not path.exists():
        print(f"Live emotion feed: not found at {path}")
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    if "error" in payload:
        print("Live emotion feed: unavailable")
        print(f"Reason: {payload['error']}")
        hint = payload.get("hint")
        if hint:
            print(f"Hint: {hint}")
        return None

    captured_at = int(payload.get("captured_at", 0))
    max_age = float(getattr(args, "live_emotion_max_age", 10.0))
    age_seconds = None
    if captured_at > 0:
        age_seconds = max(0.0, (current_epoch_ms() - captured_at) / 1000.0)
        if age_seconds > max_age:
            print(f"Live emotion feed: stale ({age_seconds:.1f}s old, max {max_age:.1f}s)")
            return None

    age_suffix = f", age={age_seconds:.1f}s" if age_seconds is not None else ""
    print(
        "Live emotion feed: "
        f"{payload.get('dominant_emotion', 'unknown')} "
        f"(confidence={payload.get('confidence', 0)}, wellbeing={payload.get('wellbeing_score', 'n/a')}{age_suffix})"
    )
    return payload


def classify_with_openai(user_text: str, model: str, *, context_block: str = "") -> dict[str, Any]:
    """Ask OpenAI for a structured intent decision."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is not installed. Run: pip install -r requirements-openai.txt") from exc

    repair_ssl_cert_environment()
    client = OpenAI()
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You classify user messages for a simulated elderly-care humanoid assistant. "
                "Return only the structured decision. The system can currently demonstrate these "
                "intents: find_cane, medicine_reminder, wellbeing_checkin, general_support, unknown. "
                "Use find_cane for lost cane or mobility-aid requests. Use medicine_reminder for "
                "medicine, pills, reminders, or medication boxes. Use wellbeing_checkin for loneliness, "
                "sadness, tiredness, stress, anxiety, or emotional support. "
                "If runtime context is provided, use it to improve the response, emotion estimate, and risk level."
            ),
        }
    ]
    if context_block:
        messages.append({"role": "system", "content": f"Runtime context:\n{context_block}"})
    messages.append({"role": "user", "content": user_text})
    response = client.responses.create(
        model=model,
        input=cast(Any, messages),
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


def annotate_context_on_events(
    events: list[dict],
    *,
    memory_hits: list[dict[str, Any]] | None = None,
    scene_summary: dict[str, Any] | None = None,
    face_summary: dict[str, Any] | None = None,
    stored_memory_ids: list[str] | None = None,
) -> None:
    """Attach optional memory/perception context to the conversation events."""
    for event in events:
        if event["event_type"] == "user_message" and memory_hits:
            event["payload"]["memory_hits"] = [
                {
                    "id": hit.get("id"),
                    "speaker": hit.get("metadata", {}).get("speaker"),
                    "intent": hit.get("metadata", {}).get("intent"),
                    "document": hit.get("document"),
                    "distance": hit.get("distance"),
                }
                for hit in memory_hits
            ]
        if event["event_type"] == "robot_response":
            if memory_hits:
                event["payload"]["memory_context_used"] = len(memory_hits)
            if scene_summary:
                event["payload"]["scene_context"] = {
                    "detected_objects": scene_summary.get("detected_objects", []),
                    "target_found": scene_summary.get("target_found"),
                    "target_distance_m": scene_summary.get("target_distance_m"),
                }
            if face_summary:
                event["payload"]["face_context"] = {
                    "dominant_emotion": face_summary.get("dominant_emotion"),
                    "confidence": face_summary.get("confidence"),
                    "wellbeing_score": face_summary.get("wellbeing_score"),
                }
            if stored_memory_ids:
                event["payload"]["stored_memory_ids"] = stored_memory_ids


def merge_contextual_events(
    events: list[dict],
    *,
    scene_analysis: dict[str, Any] | None = None,
    face_analysis: dict[str, Any] | None = None,
) -> list[dict]:
    """Replace generic scenario events with optional perception-driven events when available."""
    merged = list(events)
    if scene_analysis:
        merged = [event for event in merged if event["event_type"] not in SCENE_EVENT_TYPES]
        merged.extend(scene_analysis["events"])
    if face_analysis:
        merged = [event for event in merged if event["event_type"] not in FACE_EVENT_TYPES]
        merged.extend(face_analysis["events"])
    return merged


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
        "general_support": {
            "action": "support_user",
            "target_object": None,
            "task_status": "general_support",
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
    target_hint = infer_target_hint(user_text)
    memory_store: ChromaMemoryStore | None = None
    memory_hits: list[dict[str, Any]] = []
    scene_analysis: dict[str, Any] | None = None
    face_analysis: dict[str, Any] | None = None
    live_face_summary = resolve_live_emotion_summary(args)

    if getattr(args, "use_memory", False):
        try:
            memory_store = ChromaMemoryStore.from_env(getattr(args, "memory_collection", None))
            memory_hits = memory_store.query(user_text, top_k=getattr(args, "memory_top_k", 3))
            print(f"Memory hits: {len(memory_hits)}")
        except Exception as exc:
            print("Chroma memory: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {chroma_error_hint(exc)}")

    scene_image, face_image = resolve_perception_inputs(args)
    if scene_image is not None:
        try:
            scene_analysis = analyze_scene(
                scene_image,
                model_name=getattr(args, "yolo_model", DEFAULT_YOLO_MODEL),
                confidence=getattr(args, "yolo_confidence", 0.25),
                target_object=target_hint,
            )
            detected = scene_analysis["summary"].get("detected_objects", [])
            print(f"YOLO scene: detected {len(detected)} object(s): {detected}")
        except Exception as exc:
            print("YOLO scene analysis: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {yolo_error_hint(exc)}")

    if live_face_summary is not None:
        face_analysis = build_emotion_analysis_result(
            dominant_emotion=str(live_face_summary.get("dominant_emotion", "neutral")),
            confidence=float(live_face_summary.get("confidence", 0.0)),
            image_path=live_face_summary.get("image_path"),
            detector_backend=str(live_face_summary.get("detector_backend", DEFAULT_DETECTOR_BACKEND)),
            signals=list(live_face_summary.get("signals", [])),
            analysis_source="deepface_live_stream",
        )
        face_analysis["summary"]["captured_at"] = live_face_summary.get("captured_at")
    elif face_image is not None:
        try:
            face_analysis = analyze_face_emotion(
                face_image,
                detector_backend=getattr(args, "deepface_detector_backend", DEFAULT_DETECTOR_BACKEND),
            )
            face_summary = face_analysis["summary"]
            print(
                "DeepFace emotion: "
                f"{face_summary['dominant_emotion']} "
                f"(confidence={face_summary['confidence']}, wellbeing={face_summary['wellbeing_score']})"
            )
        except Exception as exc:
            print("DeepFace analysis: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {deepface_error_hint(exc)}")

    context_block = build_runtime_context(
        memory_hits=memory_hits,
        scene_summary=scene_analysis["summary"] if scene_analysis else None,
        face_summary=face_analysis["summary"] if face_analysis else None,
    )
    decision = (
        classify_with_mock(user_text)
        if args.mock
        else classify_with_openai(user_text, args.model, context_block=context_block)
    )
    events = build_events_from_decision(user_text, decision)
    events = merge_contextual_events(events, scene_analysis=scene_analysis, face_analysis=face_analysis)
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

    stored_memory_ids: list[str] = []
    if memory_store is not None:
        try:
            stored_memory_ids = memory_store.store_exchange(user_text, decision["robot_response"], decision)
        except Exception as exc:
            print("Chroma memory store: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {chroma_error_hint(exc)}")

    annotate_context_on_events(
        events,
        memory_hits=memory_hits,
        scene_summary=scene_analysis["summary"] if scene_analysis else None,
        face_summary=face_analysis["summary"] if face_analysis else None,
        stored_memory_ids=stored_memory_ids,
    )
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
    parser.add_argument("--scene-image", help="Optional image path for YOLO scene perception.")
    parser.add_argument("--face-image", help="Optional image path for DeepFace emotion analysis.")
    parser.add_argument("--webcam-scene", action="store_true", help="Capture one live webcam frame for YOLO scene perception.")
    parser.add_argument("--webcam-face", action="store_true", help="Capture one live webcam frame for DeepFace emotion analysis.")
    parser.add_argument("--webcam-device", type=int, default=0, help="Webcam device index for live perception capture.")
    parser.add_argument("--webcam-countdown", type=int, default=3, help="Seconds to wait before taking the live webcam frame.")
    parser.add_argument("--use-live-emotion", action="store_true", help="Read the latest summary from the background live emotion monitor.")
    parser.add_argument("--live-emotion-path", help="Optional path to latest_emotion.json from emotion_stream_monitor.py.")
    parser.add_argument("--live-emotion-max-age", type=float, default=10.0, help="Maximum age in seconds for the live emotion summary.")
    parser.add_argument("--use-memory", action="store_true", help="Retrieve and store conversation memory in ChromaDB.")
    parser.add_argument("--memory-top-k", type=int, default=3, help="Number of relevant memory hits to retrieve.")
    parser.add_argument("--memory-collection", help="Optional ChromaDB collection name override.")
    parser.add_argument("--yolo-model", default=os.getenv("YOLO_MODEL", DEFAULT_YOLO_MODEL), help=f"YOLO weights or model name. Default: {DEFAULT_YOLO_MODEL}")
    parser.add_argument("--yolo-confidence", type=float, default=0.25, help="Minimum YOLO confidence threshold.")
    parser.add_argument("--deepface-detector-backend", default=os.getenv("DEEPFACE_DETECTOR_BACKEND", DEFAULT_DETECTOR_BACKEND), help=f"DeepFace detector backend. Default: {DEFAULT_DETECTOR_BACKEND}")
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
