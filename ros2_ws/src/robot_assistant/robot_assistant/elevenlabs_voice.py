"""ElevenLabs text-to-speech helper for robot assistant responses."""

from __future__ import annotations

import os
import ssl
import subprocess
from pathlib import Path

import requests

from event_schema import current_epoch_ms
from mongo_client import PROJECT_ROOT, load_dotenv


DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_STT_MODEL_ID = "scribe_v2"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "audio"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
CERT_ENV_KEYS = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")
_SSL_ENV_CHECKED = False


def repair_ssl_cert_environment() -> None:
    """Replace inherited broken CA bundle paths with certifi's valid bundle."""
    global _SSL_ENV_CHECKED
    if _SSL_ENV_CHECKED:
        return
    _SSL_ENV_CHECKED = True

    certifi_bundle = requests.certs.where()
    try:
        ssl.create_default_context(cafile=certifi_bundle)
    except ssl.SSLError:
        return

    for key in CERT_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if not value:
            continue
        try:
            ssl.create_default_context(cafile=value)
        except (OSError, ssl.SSLError):
            os.environ[key] = certifi_bundle


def elevenlabs_error_hint(error: Exception) -> str:
    message = str(error)
    if "SSLError" in message or "PEM lib" in message or "certificate" in message.lower():
        return "Local HTTPS/certificate validation failed while calling ElevenLabs. Retry, check VPN/proxy/certificate settings, or use typed transcript fallback for the demo."
    if "401" in message:
        return "ElevenLabs rejected the API key. Check ELEVENLABS_API_KEY in .env."
    if "404" in message:
        return "ElevenLabs could not find the voice. Check ELEVENLABS_VOICE_ID in .env."
    if "429" in message:
        return "ElevenLabs rate limit or credits limit reached."
    return "Check ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, internet access, and remaining ElevenLabs credits."


def transcribe_speech(audio_path: Path) -> str:
    """Transcribe a recorded audio file using ElevenLabs speech-to-text."""
    load_dotenv()
    repair_ssl_cert_environment()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    model_id = os.getenv("ELEVENLABS_STT_MODEL_ID", DEFAULT_STT_MODEL_ID).strip()

    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is required. Add it to .env.")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    with audio_path.open("rb") as audio_file:
        response = requests.post(
            ELEVENLABS_STT_URL,
            headers={"xi-api-key": api_key},
            data={"model_id": model_id},
            files={"file": (audio_path.name, audio_file, "audio/wav")},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"ElevenLabs STT failed with HTTP {response.status_code}: {response.text[:500]}")

    payload = response.json()
    transcript = payload.get("text", "").strip()
    if not transcript:
        raise RuntimeError(f"ElevenLabs STT returned no transcript: {payload}")
    return transcript


def synthesize_speech(
    text: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    filename_prefix: str = "robot_response",
) -> Path:
    """Generate an MP3 robot response using ElevenLabs and return the saved path."""
    load_dotenv()
    repair_ssl_cert_environment()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID).strip()

    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is required. Add it to .env.")
    if not voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID is required. Add it to .env.")
    if not text.strip():
        raise ValueError("Text-to-speech input cannot be empty.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{filename_prefix}_{current_epoch_ms()}.mp3"

    response = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=voice_id),
        headers={
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.75,
                "style": 0.2,
                "use_speaker_boost": True,
            },
        },
        timeout=45,
    )
    if not response.ok:
        raise RuntimeError(f"ElevenLabs TTS failed with HTTP {response.status_code}: {response.text[:500]}")

    output_path.write_bytes(response.content)
    return output_path


def open_audio_file(audio_path: Path) -> None:
    """Open the generated audio file with the system default player."""
    if os.name == "nt":
        os.startfile(audio_path)  # type: ignore[attr-defined]
        return
    subprocess.Popen(["xdg-open", str(audio_path)])
