"""Helpers for capturing a single webcam frame for perception demos."""

from __future__ import annotations

import os
import time
from pathlib import Path

from event_schema import current_epoch_ms
from mongo_client import PROJECT_ROOT


DEFAULT_WEBCAM_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "camera_captures"


def webcam_error_hint(error: Exception) -> str:
    """Return a short operator-friendly webcam troubleshooting hint."""
    message = str(error).lower()
    if "no module named" in message or "opencv" in message:
        return "OpenCV is not installed in this environment. Run: pip install -r requirements-perception.txt"
    if "could not open webcam" in message:
        return "Check that the webcam is not busy in another app and try a different --webcam-device index."
    if "no frame" in message:
        return "The webcam opened but did not return a frame. Give it a moment, improve lighting, and retry."
    return "Webcam capture failed. Check camera permissions, device index, and whether another app is using the webcam."


def capture_webcam_frame(
    *,
    device_index: int = 0,
    countdown_seconds: int = 3,
    output_dir: Path = DEFAULT_WEBCAM_OUTPUT_DIR,
    label: str = "webcam_frame",
    warmup_frames: int = 15,
) -> Path:
    """Capture one webcam frame and save it as a JPEG."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is not installed. Run: pip install -r requirements-perception.txt") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{label}_{current_epoch_ms()}.jpg"

    if countdown_seconds > 0:
        for remaining in range(countdown_seconds, 0, -1):
            print(f"Webcam capture in {remaining}...")
            time.sleep(1)

    backend = cv2.CAP_DSHOW if os.name == "nt" and hasattr(cv2, "CAP_DSHOW") else None
    capture = cv2.VideoCapture(device_index, backend) if backend is not None else cv2.VideoCapture(device_index)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open webcam device {device_index}.")

    try:
        frame = None
        for _ in range(max(1, warmup_frames)):
            ok, candidate = capture.read()
            if ok:
                frame = candidate
            time.sleep(0.03)

        if frame is None:
            raise RuntimeError("Webcam opened, but no frame was captured.")
        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"OpenCV failed to write the webcam frame to {output_path}.")
    finally:
        capture.release()

    return output_path
