"""YOLO scene perception helpers for the humanoid assistant."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PIL import Image

from event_schema import create_event


DEFAULT_YOLO_MODEL = "yolov8n.pt"
IMPORTANT_OBJECTS = {"cane", "medicine_box", "medicine", "pill_bottle"}
ROOM_HINTS = ("living_room", "kitchen", "bedroom", "bathroom")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _prepare_ultralytics_workspace() -> Path:
    """Force Ultralytics and related caches to stay inside the project workspace."""
    repo_root = _repo_root()
    settings_dir = repo_root / "data" / "processed" / "ultralytics"
    settings_dir.mkdir(parents=True, exist_ok=True)
    matplotlib_dir = repo_root / "data" / "processed" / "matplotlib"
    matplotlib_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(settings_dir))
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_dir))
    return settings_dir


def _resolve_model_name(model_name: str) -> str:
    path = Path(model_name)
    if path.exists():
        return str(path)
    if path.suffix != ".pt":
        return model_name
    local_model = _repo_root() / "data" / "processed" / "ultralytics" / "models" / path.name
    if local_model.exists():
        return str(local_model)
    return model_name


def yolo_error_hint(error: Exception) -> str:
    """Return a short operator-friendly YOLO troubleshooting hint."""
    message = str(error).lower()
    if "no module named" in message:
        return "Ultralytics YOLO is not installed. Run: pip install -r requirements-perception.txt"
    if "not found" in message and ".pt" in message:
        return "The YOLO weights path looks invalid. Check --yolo-model or let Ultralytics download a supported model."
    if "access is denied" in message or "permissionerror" in message:
        return "YOLO could not write its local settings directory. Re-run after setting YOLO_CONFIG_DIR inside the project workspace."
    return "YOLO scene analysis failed. Check the image path, model weights, and perception dependencies."


def _normalize_label(label: str) -> str:
    normalized = label.strip().lower().replace(" ", "_")
    aliases = {
        "walking_stick": "cane",
        "stick": "cane",
        "crutch": "cane",
        "medicine": "medicine_box",
        "first_aid_kit": "medicine_box",
        "bottle": "pill_bottle",
    }
    return aliases.get(normalized, normalized)


def _estimate_distance_m(bbox_width: float, bbox_height: float, image_width: int, image_height: int) -> float:
    image_area = max(image_width * image_height, 1)
    bbox_area = max(bbox_width * bbox_height, 1.0)
    fill_ratio = min(1.0, bbox_area / image_area)
    # Simple proxy: larger boxes tend to be closer.
    distance = 2.8 - (fill_ratio * 8.0)
    return round(max(0.35, min(3.0, distance)), 3)


def _infer_room_from_path(path: Path) -> str | None:
    lowered = path.as_posix().lower()
    for hint in ROOM_HINTS:
        if hint in lowered:
            return hint
    return None


def analyze_scene(
    image_path: str | Path,
    *,
    model_name: str = DEFAULT_YOLO_MODEL,
    confidence: float = 0.25,
    target_object: str | None = None,
) -> dict[str, Any]:
    """Run YOLO on an image and convert detections into assistant events."""
    _prepare_ultralytics_workspace()
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("ultralytics is not installed. Run: pip install -r requirements-perception.txt") from exc

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Scene image was not found: {path}")

    with Image.open(path) as image:
        image_width, image_height = image.size

    resolved_model_name = _resolve_model_name(model_name)
    model = YOLO(resolved_model_name)
    results = model.predict(source=str(path), conf=confidence, verbose=False)

    detections: list[dict[str, Any]] = []
    names = getattr(model, "names", {})
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        result_names = getattr(result, "names", names) or names
        for box in boxes:
            cls_id = int(float(box.cls[0].item()))
            score = float(box.conf[0].item())
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            label = _normalize_label(str(result_names.get(cls_id, cls_id)))
            width = max(1.0, x2 - x1)
            height = max(1.0, y2 - y1)
            detections.append(
                {
                    "label": label,
                    "confidence": round(score, 3),
                    "bbox": {"x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1)},
                    "center": {"x": round((x1 + x2) / 2.0, 1), "y": round((y1 + y2) / 2.0, 1)},
                    "distance_m": _estimate_distance_m(width, height, image_width, image_height),
                }
            )

    events: list[dict[str, Any]] = []
    inferred_room = _infer_room_from_path(path)
    if inferred_room:
        events.append(
            create_event(
                "room_detected",
                {
                    "room": inferred_room,
                    "confidence": 0.7,
                    "method": "image_path_room_hint",
                },
            )
        )

    detected_labels: list[str] = []
    target_found = False
    best_target_distance: float | None = None

    for detection in detections:
        label = detection["label"]
        detected_labels.append(label)
        if target_object and label == _normalize_label(target_object):
            target_found = True
            best_target_distance = detection["distance_m"] if best_target_distance is None else min(best_target_distance, detection["distance_m"])

        events.append(
            create_event(
                "object_detected",
                {
                    "object": label,
                    "confidence": detection["confidence"],
                    "relative_position": {
                        "x": round((detection["center"]["x"] / image_width) - 0.5, 3),
                        "y": round((detection["center"]["y"] / image_height) - 0.5, 3),
                        "z": round(detection["distance_m"], 3),
                    },
                    "image_bbox": detection["bbox"],
                    "sensor": "yolo_scene_camera",
                },
            )
        )
        events.append(
            create_event(
                "object_distance_estimated",
                {
                    "object": label,
                    "distance_m": detection["distance_m"],
                    "sensor": "yolo_bbox_proxy",
                    "estimation_method": "bbox_area_proxy",
                },
            )
        )
        if label in IMPORTANT_OBJECTS:
            events.append(
                create_event(
                    "important_object_alert",
                    {
                        "object": label,
                        "severity": "info",
                        "reason": f"Important object '{label}' detected in the scene.",
                        "recommended_action": "reference_in_robot_response",
                        "sensor": "yolo_scene_camera",
                    },
                )
            )

    unique_labels = list(dict.fromkeys(detected_labels))
    if unique_labels:
        description = f"The assistant sees: {', '.join(unique_labels)}."
    else:
        description = "The assistant does not see any confident YOLO detections in the scene."
    if target_object and target_found and best_target_distance is not None:
        description += f" The target {target_object} appears to be about {best_target_distance} meters away."

    events.append(
        create_event(
            "scene_described",
            {
                "description": description,
                "detected_objects": unique_labels,
                "sensor": "yolo_scene_camera",
                "image_path": str(path),
            },
        )
    )

    return {
        "events": events,
        "detections": detections,
        "summary": {
            "image_path": str(path),
            "model_name": resolved_model_name,
            "detected_objects": unique_labels,
            "target_object": _normalize_label(target_object) if target_object else None,
            "target_found": target_found,
            "target_distance_m": best_target_distance,
            "description": description,
        },
    }
