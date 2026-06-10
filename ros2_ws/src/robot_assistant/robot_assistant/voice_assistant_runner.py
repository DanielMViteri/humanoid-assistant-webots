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

    for remaining in range(3, 0, -1):
        print(f"Recording starts in {remaining}...")
        time.sleep(1)

    recording = sd.rec(
        int(duration_seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()

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
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Push-to-talk voice assistant demo.")
    parser.add_argument("--duration", type=int, default=DEFAULT_RECORD_SECONDS, help="Recording duration in seconds.")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE, help="Microphone sample rate.")
    parser.add_argument("--list-devices", action="store_true", help="List microphone input devices and exit.")
    parser.add_argument("--device", type=int, help="Microphone device index from --list-devices.")
    parser.add_argument("--play-input", action="store_true", help="Open the recorded user WAV before transcription.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model. Default: {DEFAULT_MODEL}")
    parser.add_argument("--mock", action="store_true", help="Use local mock NLP classification after transcription.")
    parser.add_argument("--insert", action="store_true", help="Insert generated events into MongoDB Atlas.")
    parser.add_argument("--speak", action="store_true", help="Speak the robot response with ElevenLabs.")
    parser.add_argument("--play-audio", action="store_true", help="Open the generated robot response MP3.")
    parser.add_argument("--webots-command", action="store_true", help="Write the latest robot command for Webots to consume.")
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
            print(f"Hint: {elevenlabs_error_hint(exc)}")
            continue

        print(f"Transcript: {transcript}")
        process_user_message(transcript, nlp_args, mongo=mongo)


if __name__ == "__main__":
    raise SystemExit(main())
