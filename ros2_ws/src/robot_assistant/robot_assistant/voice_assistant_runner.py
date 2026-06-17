"""Push-to-talk voice runner for the humanoid assistant demo."""

from __future__ import annotations

import argparse
import time
import wave
from pathlib import Path

from elevenlabs_voice import DEFAULT_OUTPUT_DIR, elevenlabs_error_hint, open_audio_file, transcribe_speech
from event_schema import current_epoch_ms
from mongo_client import MongoEventClient, load_dotenv, mongo_error_hint
from nlp_event_runner import DEFAULT_MODEL, process_user_message


DEFAULT_RECORD_SECONDS = 7
DEFAULT_SAMPLE_RATE = 16000
MIN_RMS_LEVEL = 0.005


def microphone_error_hint(exc: Exception) -> str:
    """Return a recorder-specific hint instead of an ElevenLabs hint."""
    message = str(exc).lower()
    if "not an input device" in message:
        return "The selected audio device is an output/speaker, not a microphone. Re-run with --list-devices and choose a real input device such as 1, 2, 20, or 25."
    if "invalid number of channels" in message:
        return "This microphone rejected the requested channel count. Try a different device from --list-devices, or use the built-in microphone array."
    if "error querying device" in message or "no default input device" in message:
        return "Windows audio defaults look misconfigured. Re-run with --list-devices and pass an explicit microphone index with --device."
    if "portaudioerror" in message:
        return "The microphone could not be opened. Close any app that may be holding the mic and re-run with an explicit --device index."
    return "Check the selected microphone device with --list-devices and pass a valid input device using --device."


def list_input_devices() -> None:
    """Print available microphone/input devices."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Voice recording dependencies are missing. Run: pip install -r requirements-voice.txt") from exc

    print("Available audio input devices:")
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            default_marker = " default" if index == sd.default.device[0] else ""
            print(f"- {index}: {device['name']} ({device['max_input_channels']} input channels){default_marker}")


def resolve_input_device(sd: object, requested_device: int | None) -> int | None:
    """Return a safe microphone device index for recording."""
    devices = sd.query_devices()

    if requested_device is not None:
        info = sd.query_devices(requested_device)
        max_input = int(info.get("max_input_channels", 0))
        if max_input <= 0:
            raise ValueError(f"Not an input device: '{info.get('name', requested_device)}'")
        return requested_device

    default_input = None
    try:
        default_input = int(sd.default.device[0])
    except Exception:
        default_input = None

    if default_input is not None and default_input >= 0:
        try:
            info = sd.query_devices(default_input)
            if int(info.get("max_input_channels", 0)) > 0:
                return default_input
        except Exception:
            pass

    preferred: list[int] = []
    fallback: list[int] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        name = str(device.get("name", "")).lower()
        if any(token in name for token in ("speaker", "output", "stereo mix")):
            fallback.append(index)
            continue
        preferred.append(index)

    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    raise RuntimeError("No microphone/input devices were found.")


def record_wav(
    duration_seconds: int,
    sample_rate: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    device: int | None = None,
) -> tuple[Path, dict[str, float]]:
    """Record microphone audio and save it as a mono 16-bit WAV file."""
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Voice recording dependencies are missing. Run: pip install -r requirements-voice.txt") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"user_input_{current_epoch_ms()}.wav"
    resolved_device = resolve_input_device(sd, device)
    if resolved_device is not None:
        selected = sd.query_devices(resolved_device)
        print(f"Using microphone device {resolved_device}: {selected.get('name', 'unknown device')}")

    for remaining in range(3, 0, -1):
        print(f"Recording starts in {remaining}...")
        time.sleep(1)

    requested_channels = 1
    try:
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=requested_channels,
            dtype="float32",
            device=resolved_device,
        )
    except Exception as exc:
        if "Invalid number of channels" not in str(exc):
            raise
        device_info = sd.query_devices(resolved_device, "input") if resolved_device is not None else sd.query_devices(kind="input")
        fallback_channels = max(1, int(device_info.get("max_input_channels", requested_channels)))
        print(f"Mono recording was rejected by this device; retrying with {fallback_channels} input channel(s).")
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=fallback_channels,
            dtype="float32",
            device=resolved_device,
        )
    sd.wait()

    if recording.ndim == 2 and recording.shape[1] > 1:
        recording = recording.mean(axis=1, keepdims=True)

    clipped = np.clip(recording, -1.0, 1.0)
    rms_level = float(np.sqrt(np.mean(np.square(clipped))))
    peak_level = float(np.max(np.abs(clipped)))
    pcm_audio = (clipped * 32767).astype(np.int16)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_audio.tobytes())

    return output_path, {"rms": rms_level, "peak": peak_level}


def build_nlp_args(args: argparse.Namespace) -> argparse.Namespace:
    """Build the argument object expected by nlp_event_runner.process_user_message."""
    return argparse.Namespace(
        mock=args.mock,
        model=args.model,
        insert=args.insert,
        speak=args.speak,
        play_audio=args.play_audio,
        webots_command=args.webots_command,
        output=args.output,
        no_output=args.no_output,
        pretty=args.pretty,
        scene_image=args.scene_image,
        face_image=args.face_image,
        webcam_scene=args.webcam_scene,
        webcam_face=args.webcam_face,
        webcam_device=args.webcam_device,
        webcam_countdown=args.webcam_countdown,
        use_live_emotion=args.use_live_emotion,
        live_emotion_path=args.live_emotion_path,
        live_emotion_max_age=args.live_emotion_max_age,
        use_memory=args.use_memory,
        memory_top_k=args.memory_top_k,
        memory_collection=args.memory_collection,
        yolo_model=args.yolo_model,
        yolo_confidence=args.yolo_confidence,
        deepface_detector_backend=args.deepface_detector_backend,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Push-to-talk voice assistant demo.")
    parser.add_argument("--duration", type=int, default=DEFAULT_RECORD_SECONDS, help="Recording duration in seconds.")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE, help="Microphone sample rate.")
    parser.add_argument("--list-devices", action="store_true", help="List microphone input devices and exit.")
    parser.add_argument("--device", type=int, help="Microphone device index from --list-devices.")
    parser.add_argument("--play-input", action="store_true", help="Open the recorded user WAV before transcription.")
    parser.add_argument("--no-manual-fallback", action="store_true", help="Do not prompt for typed transcript if speech-to-text fails.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model. Default: {DEFAULT_MODEL}")
    parser.add_argument("--mock", action="store_true", help="Use local mock NLP classification after transcription.")
    parser.add_argument("--insert", action="store_true", help="Insert generated events into MongoDB Atlas.")
    parser.add_argument("--speak", action="store_true", help="Speak the robot response with ElevenLabs.")
    parser.add_argument("--play-audio", action="store_true", help="Open the generated robot response MP3.")
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
    parser.add_argument("--yolo-model", default="yolov8n.pt", help="YOLO weights or model name for scene perception.")
    parser.add_argument("--yolo-confidence", type=float, default=0.25, help="Minimum YOLO confidence threshold.")
    parser.add_argument("--deepface-detector-backend", default="opencv", help="DeepFace detector backend for face analysis.")
    parser.add_argument("--output", default="data/raw/nlp_feature_events.jsonl", help="JSONL output path for generated events.")
    parser.add_argument("--no-output", action="store_true", help="Do not write a local JSONL copy.")
    parser.add_argument("--pretty", action="store_true", help="Print full event JSON.")
    args = parser.parse_args()

    load_dotenv()
    if args.list_devices:
        list_input_devices()
        return 0

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
            print("Continuing without insertion.")
            args.insert = False

    nlp_args = build_nlp_args(args)
    print("Push-to-talk voice assistant. Press Enter to record, or type 'exit' to stop.")
    while True:
        command = input("\nPress Enter to record: ").strip()
        if command.lower() in {"exit", "quit"}:
            print("Voice session ended.")
            return 0

        audio_path = None
        try:
            print(f"Recording for {args.duration} seconds...")
            audio_path, levels = record_wav(args.duration, args.sample_rate, device=args.device)
            print(f"Recorded: {audio_path}")
            print(f"Input level: rms={levels['rms']:.4f}, peak={levels['peak']:.4f}")
            if levels["rms"] < MIN_RMS_LEVEL:
                print("Warning: microphone input looks very quiet. Check the selected device and speak closer/louder.")
            if args.play_input:
                open_audio_file(audio_path)
                input("Press Enter after listening to the recorded input...")
            transcript = transcribe_speech(audio_path)
        except Exception as exc:
            print("Voice input: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            hint = microphone_error_hint(exc) if audio_path is None else elevenlabs_error_hint(exc)
            print(f"Hint: {hint}")
            if audio_path is None or args.no_manual_fallback:
                continue
            transcript = input("Type the transcript to continue, or press Enter to retry: ").strip()
            if not transcript:
                continue
            if transcript.lower() in {"exit", "quit"}:
                print("Voice session ended.")
                return 0
            print("Continuing with typed transcript fallback.")

        print(f"Transcript: {transcript}")
        process_user_message(transcript, nlp_args, mongo=mongo)


if __name__ == "__main__":
    raise SystemExit(main())
