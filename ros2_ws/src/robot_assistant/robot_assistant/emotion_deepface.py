"""DeepFace emotion analysis helpers for the humanoid assistant."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from event_schema import create_event


DEFAULT_DETECTOR_BACKEND = "opencv"
NEGATIVE_EMOTIONS = {"sad", "fear", "angry", "disgust"}
POSITIVE_EMOTIONS = {"happy", "surprise"}
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEEPFACE_HOME = PROJECT_ROOT / "data" / "processed" / "deepface"


def deepface_error_hint(error: Exception) -> str:
    """Return a short operator-friendly DeepFace troubleshooting hint."""
    message = str(error).lower()
    if "application control policy has blocked this file" in message or "smart app control" in message:
        return (
            "Windows App Control / Smart App Control blocked a TensorFlow or DeepFace dependency. "
            "Check Windows Security > App & browser control and confirm whether Smart App Control is enforcing on this PC."
        )
    if "no module named" in message:
        return "DeepFace is not installed. Run: pip install -r requirements-deepface.txt in a compatible perception environment."
    if "tensorflow" in message or "keras" in message:
        return "DeepFace depends on a compatible ML stack. If install/runtime fails, use Python 3.11 or 3.12 for the perception environment."
    return "DeepFace analysis failed. Check the face image path and the perception dependencies."


def _normalize_emotion(value: str | None) -> str:
    if not value:
        return "neutral"
    return value.strip().lower().replace(" ", "_")


def _top_signals(emotions: dict[str, Any], *, limit: int = 3) -> list[str]:
    ranked = sorted(((str(name), float(score)) for name, score in emotions.items()), key=lambda item: item[1], reverse=True)
    return [name for name, _score in ranked[:limit]]


def prepare_deepface_runtime() -> None:
    """Keep DeepFace cache local to the repo and make console logging UTF-8-safe on Windows."""
    DEEPFACE_HOME.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DEEPFACE_HOME", str(DEEPFACE_HOME))

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except OSError:
                pass


def emotion_to_wellbeing_score(emotion: str, confidence: float) -> int:
    """Map a dominant emotion and confidence to a simple 0-100 wellbeing score."""
    normalized = _normalize_emotion(emotion)
    if normalized in POSITIVE_EMOTIONS:
        baseline = 78
    elif normalized == "neutral":
        baseline = 62
    elif normalized in NEGATIVE_EMOTIONS:
        baseline = 35
    else:
        baseline = 50

    adjustment = int(round(confidence * 10))
    if normalized in NEGATIVE_EMOTIONS:
        score = baseline - adjustment
    else:
        score = baseline + adjustment
    return max(0, min(100, score))


def build_emotion_analysis_result(
    *,
    dominant_emotion: str,
    confidence: float,
    image_path: str | Path | None = None,
    detector_backend: str = DEFAULT_DETECTOR_BACKEND,
    signals: list[str] | None = None,
    analysis_source: str = "deepface_emotion",
) -> dict[str, Any]:
    """Convert a dominant-emotion reading into the standard event bundle."""
    normalized_emotion = _normalize_emotion(dominant_emotion)
    bounded_confidence = max(0.0, min(1.0, float(confidence)))
    wellbeing_score = emotion_to_wellbeing_score(normalized_emotion, bounded_confidence)
    trend = "decreasing" if normalized_emotion in NEGATIVE_EMOTIONS else "stable"

    mood_payload = {
        "mood": normalized_emotion,
        "confidence": round(bounded_confidence, 3),
        "signals": signals or [],
        "analysis_source": analysis_source,
    }
    if image_path is not None:
        mood_payload["image_path"] = str(image_path)

    events = [
        create_event("mood_detected", mood_payload),
        create_event(
            "wellbeing_score_updated",
            {
                "score": wellbeing_score,
                "scale": "0-100",
                "trend": trend,
                "analysis_source": analysis_source,
            },
        ),
    ]

    if normalized_emotion in NEGATIVE_EMOTIONS or wellbeing_score < 50:
        events.append(
            create_event(
                "negative_mood_alert",
                {
                    "severity": "warning",
                    "reason": f"Facial emotion analysis suggests '{normalized_emotion}' with confidence {bounded_confidence:.2f}.",
                    "recommended_action": "offer_supportive_conversation",
                    "analysis_source": analysis_source,
                },
            )
        )

    return {
        "events": events,
        "summary": {
            "dominant_emotion": normalized_emotion,
            "confidence": round(bounded_confidence, 3),
            "wellbeing_score": wellbeing_score,
            "signals": signals or [],
            "image_path": str(image_path) if image_path is not None else None,
            "detector_backend": detector_backend,
        },
    }


def analyze_face_emotion(image_path: str | Path, *, detector_backend: str = DEFAULT_DETECTOR_BACKEND) -> dict[str, Any]:
    """Analyze a face image and convert it into assistant mood events."""
    prepare_deepface_runtime()
    try:
        from deepface import DeepFace
    except ImportError as exc:
        raise RuntimeError("deepface is not installed. Run: pip install -r requirements-deepface.txt") from exc

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Face image was not found: {path}")

    result = DeepFace.analyze(
        img_path=str(path),
        actions=["emotion"],
        enforce_detection=False,
        detector_backend=detector_backend,
        silent=True,
    )
    if isinstance(result, list):
        result = result[0]

    emotions = result.get("emotion", {}) if isinstance(result, dict) else {}
    dominant_emotion = _normalize_emotion(result.get("dominant_emotion") if isinstance(result, dict) else None)
    raw_confidence = float(emotions.get(dominant_emotion, 0.0))
    confidence = raw_confidence / 100.0 if raw_confidence > 1.0 else raw_confidence
    return build_emotion_analysis_result(
        dominant_emotion=dominant_emotion,
        confidence=confidence,
        image_path=path,
        detector_backend=detector_backend,
        signals=_top_signals(emotions),
        analysis_source="deepface_emotion",
    )
