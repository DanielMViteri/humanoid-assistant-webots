"""Motion bridge and on-board perception producer for the official NAO demo.

Two responsibilities:

1. Motion playback (unchanged): the supervisor decides high-level locomotion
   intent and writes it to the shared motion state file; this controller turns
   that intent into official Webots NAO motion playback.
2. Perception producer (new): this controller owns the NAO's head devices, so it
   reads the head recognition camera (target detection) and the head depth camera
   (RangeFinder, obstacle clearance) and publishes a perception feed that the
   supervisor consumes for camera-driven navigation. Only the robot's own
   controller can read its devices, hence the file bridge.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

try:
    from controller import Motion, Robot
except ImportError as exc:
    raise RuntimeError("This controller must be run by Webots.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MOTION_STATE_PATH = PROJECT_ROOT / "data" / "raw" / "webots_motion_state.json"
PERCEPTION_PATH = PROJECT_ROOT / "data" / "raw" / "webots_perception.json"
RECOGNITION_IMAGE_PATH = PROJECT_ROOT / "data" / "raw" / "recognition_camera_view.png"
MOTION_ROOT = PROJECT_ROOT / "webots" / "motions" / "nao"
CONTROLLER_VERSION = "2026-06-25-nao-motion-bridge-v8-perception-gated"
# The head recognition camera (320x240 + Recognition) and depth RangeFinder are
# only needed for camera-driven navigation, which the supervisor currently keeps
# OFF (CAMERA_NAV_ENABLED = False -> it navigates via god-mode visibility instead).
# A Webots Camera/RangeFinder only renders while enabled, and a 320x240 recognition
# render every basic timestep is the single biggest simulation cost in this world --
# it dragged the real-time factor down so a ~6 s retrieval took ~2 min of wall time.
# Leaving perception disabled removes that cost with zero effect on navigation or on
# the dashboard (its object/scene events come from the supervisor, not these cameras).
# Flip back to True together with the supervisor's CAMERA_NAV_ENABLED to restore the
# camera-driven perception feed.
PERCEPTION_ENABLED = False
PERCEPTION_INTERVAL_SECONDS = 0.2
IMAGE_SAVE_EVERY_N = 0  # set >0 to periodically dump the recognition camera view (debug only)
RECOGNITION_CAMERA_NAME = "recognition_camera"
DEPTH_CAMERA_NAME = "depth_camera"
MOTION_FILES = {
    "walk_forward": "Forwards50.motion",
    "turn_left": "TurnLeft40.motion",
    "turn_right": "TurnRight40.motion",
    "hand_wave": "HandWave.motion",
    "support": "WipeForehead.motion",
}
OBJECT_ALIASES = {
    "walking_stick": "cane",
    "pill_box": "medicine_box",
    "medication_box": "medicine_box",
}


def epoch_ms() -> int:
    return int(time.time() * 1000)


def normalize_object_name(raw_name: str) -> str:
    name = (raw_name or "unknown_object").strip().lower().replace(" ", "_")
    return OBJECT_ALIASES.get(name, name)


def _call_first(item, names: tuple[str, ...]):
    """Call the first available method name on item (handles snake/camel API variants)."""
    for name in names:
        fn = getattr(item, name, None)
        if fn is None:
            continue
        try:
            return fn()
        except Exception:
            continue
    return None


def _object_model(item) -> str:
    model = _call_first(item, ("getModel", "get_model"))
    return str(model) if model else "recognized_object"


def _object_position(item) -> list[float]:
    position = _call_first(item, ("getPosition", "get_position"))
    try:
        return [float(value) for value in position]
    except Exception:
        return [0.0, 0.0, 0.0]


def _object_image_x(item):
    pixel = _call_first(item, ("getPositionOnImage", "get_position_on_image"))
    try:
        return float(pixel[0])
    except Exception:
        return None


def detections_from_camera(camera) -> list[dict]:
    """Build target detections from the head recognition camera.

    bearing_rad is derived from the object's horizontal image position so it does
    not depend on the camera's coordinate-frame axis convention:
    positive bearing => target is to the robot's right (turn right to face it).
    """
    if camera is None:
        return []
    try:
        objects = camera.getRecognitionObjects()
    except Exception:
        return []

    width = float(camera.getWidth() or 1)
    field_of_view = float(camera.getFov() or 1.0)
    detections: list[dict] = []
    for item in objects:
        position = _object_position(item)
        distance = round(math.sqrt(sum(value * value for value in position[:3])), 3)
        image_x = _object_image_x(item)
        if image_x is not None and width > 1:
            bearing = (image_x - width / 2.0) / width * field_of_view
        else:
            # Fallback: assume camera looks down +x, lateral on +y to the left.
            bearing = math.atan2(-position[1], max(position[0], 1e-3))
        detections.append(
            {
                "object": normalize_object_name(_object_model(item)),
                "confidence": 0.9,
                "distance_m": distance,
                "bearing_rad": round(bearing, 4),
            }
        )
    return detections


def depth_sectors(depth_camera) -> dict | None:
    """Split the depth image into left/center/right column bands and report the
    nearest finite obstacle distance in each. 'left' is the robot's left side."""
    if depth_camera is None:
        return None
    try:
        image = depth_camera.getRangeImage()
    except Exception:
        return None
    if not image:
        return None

    width = int(depth_camera.getWidth())
    height = int(depth_camera.getHeight())
    max_range = float(depth_camera.getMaxRange() or 4.0)
    if width <= 0 or height <= 0:
        return None

    # Only sample the middle rows so the near floor (and the robot's own feet,
    # visible in the lower image when the camera is pitched down) don't get
    # mistaken for obstacles. This keeps clearance to upright objects ahead.
    row_start = height // 4
    row_end = max(row_start + 1, (3 * height) // 4)

    third = max(1, width // 3)
    bands = {"left_m": (0, third), "center_m": (third, 2 * third), "right_m": (2 * third, width)}
    sectors: dict[str, float] = {}
    overall_nearest = max_range
    overall_found = False
    for key, (col_start, col_end) in bands.items():
        nearest = max_range
        found = False
        for row in range(row_start, row_end):
            base = row * width
            for col in range(col_start, col_end):
                value = image[base + col]
                if math.isfinite(value) and value > 0 and value < nearest:
                    nearest = value
                    found = True
        sectors[key] = round(nearest, 3) if found else round(max_range, 3)
        if found and nearest < overall_nearest:
            overall_nearest = nearest
            overall_found = True

    sectors["min_m"] = round(overall_nearest, 3) if overall_found else round(max_range, 3)
    return sectors


class NaoMotionBridge(Robot):
    def __init__(self) -> None:
        super().__init__()
        self.time_step = int(self.getBasicTimeStep())
        self.motions = self._load_motions()
        self.current_motion_name: str | None = None
        self.current_motion: Motion | None = None
        self.current_loop = False
        self.last_state_signature: tuple[str, str, bool, int] | None = None
        self.last_perception_time = 0.0
        self.perception_writes = 0
        if PERCEPTION_ENABLED:
            self.recognition_camera = self._init_recognition_camera()
            self.depth_camera = self._init_depth_camera()
        else:
            self.recognition_camera = None
            self.depth_camera = None
            print("nao_motion_bridge perception: disabled (camera-nav off; cameras not rendered for speed)")
        print(f"nao_motion_bridge version: {CONTROLLER_VERSION}")
        print(f"nao_motion_bridge motions: {sorted(self.motions)}")

    def _load_motions(self) -> dict[str, Motion]:
        motions: dict[str, Motion] = {}
        for name, filename in MOTION_FILES.items():
            motion_path = MOTION_ROOT / filename
            if not motion_path.exists():
                raise RuntimeError(f"Missing NAO motion file: {motion_path}")
            motions[name] = Motion(str(motion_path))
        return motions

    def _init_recognition_camera(self):
        camera = self.getDevice(RECOGNITION_CAMERA_NAME)
        if camera is None:
            print(f"WARNING: '{RECOGNITION_CAMERA_NAME}' not found; target detection disabled.")
            return None
        try:
            camera.enable(self.time_step)
            camera.recognitionEnable(self.time_step)
            print(f"nao_motion_bridge recognition camera: {RECOGNITION_CAMERA_NAME} enabled")
        except Exception as exc:
            print(f"WARNING: could not enable recognition on '{RECOGNITION_CAMERA_NAME}': {exc}")
            return None
        return camera

    def _init_depth_camera(self):
        depth = self.getDevice(DEPTH_CAMERA_NAME)
        if depth is None:
            print(f"WARNING: '{DEPTH_CAMERA_NAME}' not found; obstacle sensing disabled.")
            return None
        try:
            depth.enable(self.time_step)
            print(f"nao_motion_bridge depth camera: {DEPTH_CAMERA_NAME} enabled")
        except Exception as exc:
            print(f"WARNING: could not enable '{DEPTH_CAMERA_NAME}': {exc}")
            return None
        return depth

    def read_motion_state(self) -> dict:
        if not MOTION_STATE_PATH.exists():
            return {"state": "idle", "motion": "idle", "loop": False}
        try:
            return json.loads(MOTION_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"state": "idle", "motion": "idle", "loop": False}

    def write_perception(self) -> None:
        rec = self.recognition_camera
        recognition_enabled = False
        recognition_count = -1
        if rec is not None:
            try:
                recognition_enabled = bool(rec.hasRecognition())
            except Exception:
                recognition_enabled = True  # older API without hasRecognition()
            try:
                recognition_count = int(rec.getRecognitionNumberOfObjects())
            except Exception:
                recognition_count = -1
        payload = {
            "timestamp": epoch_ms(),
            "source": "nao_head_camera",
            "detections": detections_from_camera(rec),
            "depth": depth_sectors(self.depth_camera),
            "recognition_enabled": recognition_enabled,
            "recognition_object_count": recognition_count,
        }
        PERCEPTION_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Debug aid: periodically dump what the recognition camera actually sees.
        self.perception_writes += 1
        if IMAGE_SAVE_EVERY_N and rec is not None and self.perception_writes % IMAGE_SAVE_EVERY_N == 0:
            try:
                rec.saveImage(str(RECOGNITION_IMAGE_PATH), 100)
            except Exception:
                pass

        text = json.dumps(payload, indent=2)
        for attempt in range(6):
            try:
                PERCEPTION_PATH.write_text(text, encoding="utf-8")
                return
            except OSError:
                # Includes PermissionError and Windows/OneDrive EINVAL (Errno 22).
                if attempt == 5:
                    return
                time.sleep(0.05)

    def stop_current_motion(self) -> None:
        if self.current_motion is not None:
            try:
                self.current_motion.stop()
            except Exception:
                pass
        self.current_motion_name = None
        self.current_motion = None
        self.current_loop = False

    def start_motion(self, motion_name: str, loop: bool) -> None:
        if motion_name == "idle":
            if self.current_motion_name is not None:
                print("nao_motion_bridge motion: idle")
            self.stop_current_motion()
            return

        motion = self.motions.get(motion_name)
        if motion is None:
            print(f"WARNING: unknown NAO motion requested: {motion_name}")
            return

        self.stop_current_motion()
        motion.setLoop(loop)
        motion.play()
        self.current_motion_name = motion_name
        self.current_motion = motion
        self.current_loop = loop
        print(f"nao_motion_bridge motion: {motion_name} loop={loop}")

    def run(self) -> None:
        while self.step(self.time_step) != -1:
            state = self.read_motion_state()
            state_name = str(state.get("state", "idle"))
            motion_name = str(state.get("motion", "idle"))
            loop = bool(state.get("loop", False))
            sequence = int(state.get("sequence", 0))
            state_signature = (state_name, motion_name, loop, sequence)
            if state_signature != self.last_state_signature:
                self.last_state_signature = state_signature
                print(
                    f"nao_motion_bridge state: {state_name} motion={motion_name} "
                    f"loop={loop} sequence={sequence}"
                )
                self.start_motion(motion_name, loop)

            if PERCEPTION_ENABLED:
                now = time.time()
                if now - self.last_perception_time >= PERCEPTION_INTERVAL_SECONDS:
                    self.last_perception_time = now
                    self.write_perception()


if __name__ == "__main__":
    NaoMotionBridge().run()
