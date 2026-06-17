"""Continuous webcam emotion monitor for near-real-time assistant demos."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from emotion_deepface import (
    DEFAULT_DETECTOR_BACKEND,
    build_emotion_analysis_result,
    deepface_error_hint,
)
from event_schema import current_epoch_ms
from mongo_client import PROJECT_ROOT
from webcam_capture import webcam_error_hint


DEFAULT_STREAM_DIR = PROJECT_ROOT / "data" / "raw" / "live_emotion"
DEFAULT_STREAM_JSON = DEFAULT_STREAM_DIR / "latest_emotion.json"


def _open_capture(device_index: int):
    import cv2

    backend = cv2.CAP_DSHOW if os.name == "nt" and hasattr(cv2, "CAP_DSHOW") else None
    capture = cv2.VideoCapture(device_index, backend) if backend is not None else cv2.VideoCapture(device_index)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open webcam device {device_index}.")
    return capture


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuously analyze live webcam emotion and persist the latest summary.")
    parser.add_argument("--device", type=int, default=0, help="Webcam device index.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between DeepFace analyses.")
    parser.add_argument("--preview", action="store_true", help="Show a live webcam preview window with the latest emotion overlay.")
    parser.add_argument("--label", default="live_emotion", help="Filename prefix for captured frames.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_STREAM_JSON, help="Where to write the latest emotion JSON.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_STREAM_DIR, help="Where to store captured frames.")
    parser.add_argument("--detector-backend", default=DEFAULT_DETECTOR_BACKEND, help=f"DeepFace detector backend. Default: {DEFAULT_DETECTOR_BACKEND}")
    parser.add_argument("--warmup-frames", type=int, default=15, help="Frames to read before the first analysis.")
    args = parser.parse_args()

    try:
        import cv2
        from deepface import DeepFace  # noqa: F401
    except ImportError as exc:
        if "deepface" in str(exc).lower():
            raise SystemExit(f"DeepFace startup failed. Hint: {deepface_error_hint(exc)}")
        raise SystemExit(f"Webcam startup failed. Hint: {webcam_error_hint(exc)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    window_name = "Humanoid Assistant Live Emotion"
    latest_overlay = "warming up..."
    last_error = ""

    try:
        capture = _open_capture(args.device)
    except Exception as exc:
        raise SystemExit(f"Webcam startup failed. Hint: {webcam_error_hint(exc)}")

    try:
        frame = None
        for _ in range(max(1, args.warmup_frames)):
            ok, candidate = capture.read()
            if ok:
                frame = candidate
            time.sleep(0.03)

        next_analysis_at = time.monotonic()
        while True:
            ok, candidate = capture.read()
            if ok:
                frame = candidate
            if frame is None:
                time.sleep(0.03)
                continue

            now = time.monotonic()
            if now >= next_analysis_at:
                captured_at = current_epoch_ms()
                image_path = args.output_dir / f"{args.label}_{captured_at}.jpg"
                if not cv2.imwrite(str(image_path), frame):
                    print(f"Live emotion: failed to write frame to {image_path}")
                else:
                    try:
                        analysis = build_emotion_analysis_result(
                            **{
                                **__import__("emotion_deepface").analyze_face_emotion(
                                    image_path,
                                    detector_backend=args.detector_backend,
                                ),
                            }
                        )
                    except TypeError:
                        # Fallback for direct DeepFace output path below.
                        analysis = None
                    except Exception:
                        analysis = None

                    if analysis is None:
                        try:
                            from emotion_deepface import analyze_face_emotion

                            analysis = analyze_face_emotion(
                                image_path,
                                detector_backend=args.detector_backend,
                            )
                            summary = dict(analysis["summary"])
                            summary["captured_at"] = captured_at
                            summary["analysis_source"] = "deepface_live_stream"
                            _write_summary(args.output_json, summary)
                            latest_overlay = (
                                f"{summary['dominant_emotion']} "
                                f"conf={summary['confidence']:.2f} "
                                f"wellbeing={summary['wellbeing_score']}"
                            )
                            print(f"Live emotion: {latest_overlay}")
                            last_error = ""
                        except Exception as exc:
                            error_text = f"{exc.__class__.__name__}: {exc}"
                            if error_text != last_error:
                                print("Live emotion analysis: FAILED")
                                print(f"Reason: {error_text}")
                                print(f"Hint: {deepface_error_hint(exc)}")
                                last_error = error_text
                            latest_overlay = "emotion unavailable"
                            _write_summary(
                                args.output_json,
                                {
                                    "captured_at": captured_at,
                                    "image_path": str(image_path),
                                    "error": error_text,
                                    "hint": deepface_error_hint(exc),
                                },
                            )

                next_analysis_at = now + max(0.5, args.interval)

            if args.preview:
                display = frame.copy()
                cv2.putText(display, latest_overlay, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 220, 30), 2)
                cv2.putText(display, "Press Q to stop", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
                cv2.imshow(window_name, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
            else:
                time.sleep(0.02)
    finally:
        capture.release()
        if args.preview:
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
