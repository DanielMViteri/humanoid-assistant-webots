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
CONVERSATION_EVENTS_COLLECTION = "conversation_events"
WEBOTS_COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
DEFAULT_POLL_SECONDS = 3.0

# Dashboard press-to-talk markers that should trigger a real mic recording.
VOICE_LISTEN_SCENARIOS = {"voice_listen", "press_to_talk", "talk_listen"}

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
def _analyze_snapshot_emotion(args: argparse.Namespace) -> dict | None:
    """Single-frame webcam capture + DeepFace. Returns the analysis result or None."""
    try:
        from webcam_capture import capture_webcam_frame, webcam_error_hint
        from emotion_deepface import analyze_face_emotion, deepface_error_hint
    except Exception as exc:
        print(f"[emotion] perception modules unavailable: {exc}")
        return None
    try:
        frame = capture_webcam_frame(
            device_index=args.device,
            countdown_seconds=args.webcam_countdown,
            label="nesto_mood_check",
        )
        print(f"[emotion] captured webcam frame: {frame}")
    except Exception as exc:
        print(f"[emotion] webcam capture FAILED: {exc.__class__.__name__}: {exc}")
        try:
            print(f"  Hint: {webcam_error_hint(exc)}")
        except Exception:
            pass
        return None
    try:
        return analyze_face_emotion(frame, detector_backend=args.detector_backend)
    except Exception as exc:
        print(f"[emotion] DeepFace analysis FAILED: {exc.__class__.__name__}: {exc}")
        try:
            print(f"  Hint: {deepface_error_hint(exc)}")
        except Exception:
            pass
        return None


def _analyze_video_emotion(args: argparse.Namespace) -> dict | None:
    """Multi-frame webcam clip + DeepFace, aggregated by majority vote. Returns result or None."""
    from collections import Counter

    try:
        from webcam_capture import capture_webcam_frames, webcam_error_hint
        from emotion_deepface import analyze_face_emotion, build_emotion_analysis_result
    except Exception as exc:
        print(f"[emotion] perception modules unavailable: {exc}")
        return None
    try:
        frames = capture_webcam_frames(
            device_index=args.device,
            frames=args.video_frames,
            interval_seconds=args.video_interval,
            countdown_seconds=args.webcam_countdown,
            label="nesto_mood_video",
        )
        print(f"[emotion] captured {len(frames)} webcam frames (video mode)")
    except Exception as exc:
        print(f"[emotion] webcam (video) capture FAILED: {exc.__class__.__name__}: {exc}")
        try:
            print(f"  Hint: {webcam_error_hint(exc)}")
        except Exception:
            pass
        return None

    summaries = []
    for frame in frames:
        try:
            summaries.append(analyze_face_emotion(frame, detector_backend=args.detector_backend)["summary"])
        except Exception:
            continue
    if not summaries:
        print("[emotion] DeepFace found no analyzable face in the video clip.")
        return None

    emotions = [summary["dominant_emotion"] for summary in summaries]
    dominant = Counter(emotions).most_common(1)[0][0]
    matching = [s["confidence"] for s in summaries if s["dominant_emotion"] == dominant]
    confidence = (sum(matching) / len(matching)) if matching else (sum(s["confidence"] for s in summaries) / len(summaries))
    print(f"[emotion] video frames -> {dict(Counter(emotions))}; dominant '{dominant}'")
    return build_emotion_analysis_result(
        dominant_emotion=dominant,
        confidence=confidence,
        signals=[f"video_{len(summaries)}_frames", *emotions[:6]],
        analysis_source="deepface_video",
    )


def run_emotion_recognition(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    """Capture the webcam (snapshot or video), run DeepFace, and write the detected emotion to MongoDB."""
    requested_mood = (document.get("payload") or {}).get("mood")
    source_event_id = document.get("event_id")

    if args.simulate_emotion:
        from emotion_deepface import build_emotion_analysis_result

        result = build_emotion_analysis_result(
            dominant_emotion=args.simulate_emotion,
            confidence=0.85,
            signals=["simulated"],
            analysis_source="dashboard_simulated",
        )
    elif args.video:
        result = _analyze_video_emotion(args)
    else:
        result = _analyze_snapshot_emotion(args)

    if result is None:
        return False

    summary = result["summary"]
    mode = "video" if args.video and not args.simulate_emotion else ("simulated" if args.simulate_emotion else "snapshot")
    # Tag the events so the dashboard can tie the detection back to the request.
    for event in result["events"]:
        event["payload"]["source_event_id"] = source_event_id
        event["payload"]["self_reported_mood"] = requested_mood
        event["payload"]["trigger"] = "nesto_dashboard_mood_check"
        event["payload"]["capture_mode"] = mode

    inserted = mongo.insert_events(result["events"])
    print(
        f"[emotion] detected '{summary['dominant_emotion']}' "
        f"(confidence={summary['confidence']}, wellbeing={summary['wellbeing_score']}, "
        f"mode={mode}, self_reported={requested_mood}) -> MongoDB {inserted}"
    )
    return True


def handle_mood_request(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    event_type = str(document.get("event_type") or "").strip().lower()
    scenario_type = str((document.get("scenario_type") or "")).strip().lower()
    if event_type not in MOOD_TRIGGER_EVENT_TYPES and scenario_type not in MOOD_TRIGGER_EVENT_TYPES:
        return False
    return run_emotion_recognition(mongo, document, args)


# --------------------------------------------------------------------------- #
# Press-to-talk voice requests -> record + transcribe + NLP -> MongoDB
# --------------------------------------------------------------------------- #
def _build_voice_nlp_args(args: argparse.Namespace) -> argparse.Namespace:
    """Build the Namespace expected by nlp_event_runner.process_user_message.

    insert=True writes the transcript/reply into conversation_events; webots_command=True
    so a spoken "find my cane" also drives the NAO -- exactly like the typed path.
    """
    from nlp_event_runner import DEFAULT_MODEL

    return argparse.Namespace(
        mock=args.voice_mock,
        model=DEFAULT_MODEL,
        insert=True,
        speak=args.voice_speak,
        play_audio=False,
        webots_command=True,
        output="data/raw/nlp_feature_events.jsonl",
        no_output=False,
        pretty=False,
        scene_image=None,
        face_image=None,
        webcam_scene=False,
        webcam_face=False,
        webcam_device=args.device,
        webcam_countdown=args.webcam_countdown,
        use_live_emotion=False,
        live_emotion_path=None,
        live_emotion_max_age=10.0,
        use_memory=False,
        memory_top_k=3,
        memory_collection=None,
        yolo_model="yolov8n.pt",
        yolo_confidence=0.25,
        deepface_detector_backend=args.detector_backend,
    )


def run_voice_capture(mongo: MongoEventClient, args: argparse.Namespace) -> bool:
    """Record the mic, transcribe (ElevenLabs), and run NLP (process_user_message).

    process_user_message writes the user_message (transcript) and robot_response
    (reply) into conversation_events and, for actionable intents, the Webots
    command file -- so the spoken request both shows on the dashboard and drives
    the robot.
    """
    try:
        from voice_assistant_runner import record_wav
        from elevenlabs_voice import transcribe_speech
        from nlp_event_runner import process_user_message
    except Exception as exc:
        print(f"[voice] voice modules unavailable: {exc}")
        return False

    try:
        print("[voice] recording... speak now")
        audio_path, levels = record_wav(args.voice_duration, 16000, device=args.mic_device)
        print(f"[voice] recorded {audio_path} (rms={levels['rms']:.4f}, peak={levels['peak']:.4f})")
    except Exception as exc:
        print(f"[voice] microphone capture FAILED: {exc.__class__.__name__}: {exc}")
        print("  Hint: list mics with run_voice_with_perception.cmd --list-devices, then pass --mic-device N.")
        return False

    try:
        transcript = str(transcribe_speech(audio_path) or "").strip()
    except Exception as exc:
        print(f"[voice] transcription FAILED: {exc.__class__.__name__}: {exc}")
        return False
    if not transcript:
        print("[voice] empty transcript; nothing to process.")
        return False
    print(f"[voice] transcript: {transcript}")

    try:
        process_user_message(transcript, _build_voice_nlp_args(args), mongo=mongo)
    except Exception as exc:
        print(f"[voice] NLP processing FAILED: {exc.__class__.__name__}: {exc}")
        return False
    return True


def handle_voice_request(mongo: MongoEventClient, document: dict[str, Any], args: argparse.Namespace) -> bool:
    scenario_type = str(document.get("scenario_type") or "").strip().lower()
    payload = document.get("payload") or {}
    trigger = str(payload.get("trigger") or "").strip().lower()
    if scenario_type not in VOICE_LISTEN_SCENARIOS and trigger != "press_to_talk":
        return False  # an ordinary conversation event, not a press-to-talk request
    return run_voice_capture(mongo, args)


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
    parser.add_argument("--no-voice", action="store_true", help="Disable the conversation_events -> press-to-talk voice handler.")
    parser.add_argument("--mic-device", type=int, default=None, help="Microphone input device index (see run_voice_with_perception.cmd --list-devices).")
    parser.add_argument("--voice-duration", type=int, default=7, help="Seconds to record per press-to-talk request.")
    parser.add_argument("--voice-mock", action="store_true", help="Use the local mock NLP classifier instead of OpenAI for voice requests.")
    parser.add_argument("--voice-speak", action="store_true", help="Speak the robot reply with ElevenLabs after a voice request.")
    parser.add_argument("--device", type=int, default=0, help="Webcam device index for emotion recognition.")
    parser.add_argument("--webcam-countdown", type=int, default=3, help="Seconds before the webcam frame is captured.")
    parser.add_argument("--detector-backend", default="opencv", help="DeepFace detector backend.")
    parser.add_argument("--video", action="store_true", help="Mood check: analyze a short multi-frame video clip (majority vote) instead of one snapshot.")
    parser.add_argument("--video-frames", type=int, default=5, help="Frames to capture in --video mode.")
    parser.add_argument("--video-interval", type=float, default=0.4, help="Seconds between frames in --video mode.")
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
    if not args.no_voice:
        handlers.append((CONVERSATION_EVENTS_COLLECTION, handle_voice_request))

    print("MongoDB connection: OK")
    print(f"Database: {mongo.database_name}")
    print(f"Watching: {', '.join(name for name, _ in handlers) or '(nothing)'}")
    if not args.no_scenarios:
        print(f"  scenario_events -> {WEBOTS_COMMAND_PATH}")
    if not args.no_emotion:
        if args.simulate_emotion:
            mode = f"SIMULATED ({args.simulate_emotion})"
        elif args.video:
            mode = f"webcam device {args.device} VIDEO {args.video_frames} frames + DeepFace"
        else:
            mode = f"webcam device {args.device} snapshot + DeepFace"
        print(f"  mood_events -> facial emotion recognition [{mode}] -> MongoDB")
    if not args.no_voice:
        mic = "auto" if args.mic_device is None else f"device {args.mic_device}"
        print(f"  conversation_events -> press-to-talk [mic {mic}, {args.voice_duration}s] -> STT + NLP -> MongoDB")

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
