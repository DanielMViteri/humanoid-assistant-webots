"""Webots supervisor for the official NAO Saturday demo.

The visible robot is a standard SoftBank NAO instance. The supervisor consumes
the existing command bridge, decides high-level navigation intent, and
publishes the event schema consumed by MongoDB tooling. The actual robot motion
is delegated to the NAO motion bridge so Webots' built-in humanoid motions can
drive the physical movement.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from uuid import uuid4

try:
    from controller import Supervisor
except ImportError as exc:
    raise RuntimeError("This controller must be run by Webots.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROBOT_ASSISTANT_PATH = PROJECT_ROOT / "ros2_ws" / "src" / "robot_assistant" / "robot_assistant"
sys.path.insert(0, str(ROBOT_ASSISTANT_PATH))

from event_schema import DEFAULT_ROBOT_ID, DEFAULT_SOURCE, DEFAULT_USER_ID, validate_event  # noqa: E402


OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "webots_humanoid_events.jsonl"
COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
MOTION_STATE_PATH = PROJECT_ROOT / "data" / "raw" / "webots_motion_state.json"
CONTROLLER_VERSION = "2026-06-27-nao-supervisor-v19-obstacle-stop-fall-recovery"
ROBOT_DEF = "NAO_ASSISTANT"
ROBOT_ID = "H1"
PUBLISH_INTERVAL_SECONDS = 1.0
TELEMETRY_TIMING_FIELDS = (
    "ui_triggered_at",
    "backend_received_at",
    "bridge_received_at",
    "robot_action_started_at",
    "robot_action_completed_at",
    "mongodb_logged_at",
    "dashboard_updated_at",
)
NAVIGATION_HEIGHT = 0.334
TARGET_REACHED_DISTANCE_METERS = 0.55
WAYPOINT_REACHED_DISTANCE_METERS = 0.50
# The medicine box sits in the MIDDLE of the coffee table (table spans x[-1.2,-0.4],
# box at x=-0.82). The NAO can't reach the box itself without walking onto the table,
# so it walks up to the table's west edge and "picks it up" there (the box is then
# moved into the hand-off pose). 0.72 m lands the robot at the table edge (~x=-1.38)
# once the 1 Hz completion check + walk overshoot are accounted for.
MEDICINE_REACH_DISTANCE_METERS = 0.80  # standoff so the NAO stops on open floor
                                       # WEST of the table, never walking into it
STALL_DETECTION_DISTANCE_METERS = 0.02
STALL_DETECTION_STEPS = 20
TURN_ALIGNMENT_RADIANS = 0.42  # > half the 40deg (0.70 rad) turn step, so a single
                               # turn can't overshoot into a reverse turn (oscillation)
TURN_HARD_ALIGNMENT_RADIANS = 0.65
# God-mode heading control: how fast the supervisor may steer the robot's base
# heading toward the goal (rad/s). At ~1.6 rad/s a full 180deg turn takes ~2s.
MAX_YAW_RATE_RADIANS_PER_SEC = 1.6
MOTION_STEP_SECONDS = {
    "walk_forward": 6.9,
    "turn_left": 3.0,
    "turn_right": 3.0,
    "hand_wave": 5.2,
    "support": 5.2,
}
# Pause (motors holding the settled stance) inserted BETWEEN gait motions. The
# official NAO demo only stays upright because a human paces the motions and lets
# the robot stabilise before the next one; we switch gaits automatically, so each
# stop()+play() snaps the leg pose on a still-moving robot and it topples. This
# settle window reproduces that pacing -- the robot finishes a gait, holds its
# (statically stable, symmetric) end stance, then starts the next gait from rest.
SETTLE_SECONDS = 0.8
SEARCH_MEMORY_SECONDS = 6.0
MAX_VISIBILITY_DISTANCE_METERS = 3.0
VISIBILITY_HALF_ANGLE_RADIANS = 1.25
SAFETY_ALERT_DISTANCE_METERS = 0.32
ROOM_ZONES = [
    {"room": "living_room", "x_min": -3.2, "x_max": 0.6, "y_min": -3.9, "y_max": -0.4},
    {"room": "kitchen", "x_min": 0.6, "x_max": 2.2, "y_min": -3.9, "y_max": -0.4},
    {"room": "bedroom", "x_min": -3.2, "x_max": 2.2, "y_min": -0.4, "y_max": 1.9},
]
KNOWN_OBJECTS = {
    "cane": "CANE",
    "medicine_box": "MEDICINE_BOX",
    "chair": "LIVING_ARMCHAIR",
    "table": "COFFEE_TABLE",
}
OBSTACLES = {
    "LIVING_ARMCHAIR": 0.42,
    "COFFEE_TABLE": 0.50,
    "LEFT_SOFA": 0.55,
    "RIGHT_SOFA": 0.55,
    "GUEST_CHAIR": 0.30,
}
OBSTACLE_LABELS = {
    "LIVING_ARMCHAIR": "chair",
    "COFFEE_TABLE": "table",
    "LEFT_SOFA": "left_sofa",
    "RIGHT_SOFA": "right_sofa",
    "GUEST_CHAIR": "guest_chair",
}
PRESENTATION_HOME = [-1.55, -3.0, NAVIGATION_HEIGHT]

# Camera-driven navigation (sense-and-steer from the NAO head perception feed).
# Disabled for now: the discrete .motion turn granularity (~40 deg) overshoots the
# centering tolerance and the head-camera aim does not track body heading reliably,
# so the robot circled instead of reaching the target. The proven god-mode route
# planner is used instead. Flip back to True to resume tuning camera-driven nav.
PERCEPTION_PATH = PROJECT_ROOT / "data" / "raw" / "webots_perception.json"
CAMERA_NAV_ENABLED = False
CAMERA_FALLBACK_ENABLED = True
PERCEPTION_MAX_AGE_SECONDS = 1.0
SAFE_FORWARD_CLEARANCE_M = 0.6

# --- Real-walk safety (v19): stop before obstacles, recover from stumbles -----
# The god-mode route planner aims the heading; the NAO then walks with real
# physics gaits. Two guards keep that from ending in a fall:
#   * never commit walk_forward when an obstacle is within the lookahead, and
#   * if the base drops/tips below FALL_RECOVERY_MIN_Z, stand it back up in place
#     (keep x/y progress + heading) so a single stumble does not abort the task.
FORWARD_LOOKAHEAD_M = 0.45
WALK_STOP_CLEARANCE_M = 0.15
AVOID_TURN_PROBE_RADIANS = 0.6
FALL_RECOVERY_MIN_Z = 0.20
TARGET_BEARING_TOLERANCE_RAD = 0.30
CAMERA_NAV_ACTIONS = {"search_object", "check_medicine"}


def epoch_ms() -> int:
    return int(time.time() * 1000)


def create_event(event_type: str, payload: dict, timestamp: int | None = None) -> dict:
    event = {
        "event_id": f"evt_{epoch_ms()}_{uuid4().hex[:8]}",
        "event_type": event_type,
        "timestamp": timestamp if timestamp is not None else epoch_ms(),
        "source": DEFAULT_SOURCE,
        "user_id": DEFAULT_USER_ID,
        "robot_id": DEFAULT_ROBOT_ID,
        "payload": payload,
    }
    errors = validate_event(event)
    if errors:
        raise ValueError("; ".join(errors))
    return event


def telemetry_timing_payload(command: dict | None, completed_at: int | None = None) -> dict:
    if command is None:
        return {}
    payload = {
        field: command[field]
        for field in TELEMETRY_TIMING_FIELDS
        if command.get(field) not in (None, "")
    }
    if completed_at is not None:
        payload["robot_action_completed_at"] = completed_at
    return payload


def _safe_print(text: str) -> None:
    """Print without ever crashing the controller (Webots console writes can raise OSError)."""
    try:
        print(text)
    except OSError:
        pass


def write_events(events: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, separators=(",", ":")) for event in events]
    for attempt in range(6):
        try:
            with OUTPUT_PATH.open("a", encoding="utf-8") as output_file:
                for compact in lines:
                    output_file.write(compact + "\n")
            for compact in lines:
                _safe_print(compact)
            return
        except OSError as exc:
            # Includes PermissionError and Windows/OneDrive EINVAL (Errno 22).
            # Event logging must never crash the robot, so warn and continue.
            if attempt == 5:
                _safe_print(f"WARNING: could not append Webots events after retries: {exc}")
                return
            time.sleep(0.15)


def write_motion_state(state: dict) -> None:
    MOTION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2)
    for attempt in range(6):
        try:
            MOTION_STATE_PATH.write_text(payload, encoding="utf-8")
            return
        except OSError as exc:
            if attempt == 5:
                _safe_print(f"WARNING: could not write motion state after retries: {exc}")
                return
            time.sleep(0.1)


def read_latest_command(last_command_id: str | None, controller_started_ms: int) -> tuple[dict | None, str | None]:
    if not COMMAND_PATH.exists():
        return None, last_command_id
    try:
        command = json.loads(COMMAND_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read Webots command file: {exc}")
        return None, last_command_id

    command_id = command.get("command_id")
    if not command_id or command_id == last_command_id:
        return None, last_command_id

    command_timestamp = command.get("timestamp")
    if not isinstance(command_timestamp, int) or command_timestamp <= controller_started_ms:
        return None, command_id

    return command, command_id


def room_for_position(position: list[float]) -> str:
    x = position[0]
    y = position[1]
    for zone in ROOM_ZONES:
        if zone["x_min"] <= x < zone["x_max"] and zone["y_min"] <= y < zone["y_max"]:
            return zone["room"]
    return "unknown_room"


def normalize_object_name(raw_name: str) -> str:
    name = (raw_name or "unknown_object").strip().lower().replace(" ", "_")
    aliases = {
        "walking_stick": "cane",
        "pill_box": "medicine_box",
        "medication_box": "medicine_box",
    }
    return aliases.get(name, name)


def get_node(robot: Supervisor, def_name: str):
    return robot.getFromDef(def_name)


def get_position(node) -> list[float] | None:
    if node is None:
        return None
    field = node.getField("translation")
    if field is None:
        return None
    return list(field.getSFVec3f())


def set_yaw(node, yaw: float) -> None:
    field = node.getField("rotation")
    if field is not None:
        field.setSFRotation([0, 0, 1, yaw])


def get_yaw(node) -> float:
    field = node.getField("rotation")
    if field is None:
        return 0.0
    values = list(field.getSFRotation())
    if len(values) < 4:
        return 0.0
    ax, ay, az, angle = values[0], values[1], values[2], values[3]
    # Robust yaw extraction. The old code returned `angle` directly, but Webots
    # stores a rotation about -z as a POSITIVE angle with the axis flipped to
    # [0,0,-1], so `angle` flips sign with orientation and the robot circled.
    # With set_yaw gone (real walking) the body's stored axis is no longer pinned
    # to +z, so we derive heading from the rotation matrix: rotate the NAO's local
    # forward axis (+y) into the world via Rodrigues' formula and read it off that.
    norm = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / norm, ay / norm, az / norm
    c = math.cos(angle)
    s = math.sin(angle)
    one_c = 1.0 - c
    # World forward = R * (0, 1, 0)  (second column of the rotation matrix).
    forward_x = ax * ay * one_c - az * s
    forward_y = c + ay * ay * one_c
    # Match the heading_vector(yaw) = (sin yaw, -cos yaw) convention used elsewhere.
    return math.atan2(forward_x, -forward_y)


def planar_distance(first: list[float], second: list[float]) -> float:
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    return round(math.sqrt(dx * dx + dy * dy), 3)


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def heading_vector(yaw: float) -> tuple[float, float]:
    return math.sin(yaw), -math.cos(yaw)


def world_heading_deg(yaw: float) -> float:
    """Compass-style world direction (degrees) the robot faces for a given yaw,
    using the same heading_vector convention as navigation. Lets a debug line
    compare 'where it thinks it faces' against 'where it actually moved'."""
    fx, fy = heading_vector(yaw)
    return math.degrees(math.atan2(fy, fx))


def relative_position(robot_position: list[float], robot_yaw: float, target_position: list[float]) -> dict[str, float]:
    dx = target_position[0] - robot_position[0]
    dy = target_position[1] - robot_position[1]
    dz = target_position[2] - robot_position[2]
    right_x = math.cos(robot_yaw)
    right_y = math.sin(robot_yaw)
    forward_x, forward_y = heading_vector(robot_yaw)
    side = right_x * dx + right_y * dy
    forward = forward_x * dx + forward_y * dy
    return {"x": round(side, 3), "y": round(dz, 3), "z": round(forward, 3)}


def node_visibility(robot_position: list[float], robot_yaw: float, target_position: list[float]) -> tuple[bool, float]:
    dx = target_position[0] - robot_position[0]
    dy = target_position[1] - robot_position[1]
    distance = math.sqrt(dx * dx + dy * dy)
    if distance > MAX_VISIBILITY_DISTANCE_METERS:
        return False, round(distance, 3)
    forward_x, forward_y = heading_vector(robot_yaw)
    if distance == 0:
        return True, 0.0
    dot = (forward_x * dx + forward_y * dy) / distance
    dot = max(-1.0, min(1.0, dot))
    angle = math.acos(dot)
    return angle <= VISIBILITY_HALF_ANGLE_RADIANS, round(distance, 3)


def detect_visible_objects(robot: Supervisor, robot_position: list[float], robot_yaw: float) -> list[dict]:
    detections: list[dict] = []
    for object_name, def_name in KNOWN_OBJECTS.items():
        node = get_node(robot, def_name)
        position = get_position(node)
        if position is None:
            continue
        visible, distance = node_visibility(robot_position, robot_yaw, position)
        if not visible:
            continue
        detections.append(
            {
                "object": object_name,
                "confidence": 0.95 if object_name in {"cane", "medicine_box"} else 0.88,
                "relative_position": relative_position(robot_position, robot_yaw, position),
                "distance_m": distance,
            }
        )
    return detections


def find_target_object(detected_objects: list[dict], target_object: str | None) -> dict | None:
    if not target_object:
        return None
    target = normalize_object_name(target_object)
    for detected in detected_objects:
        if normalize_object_name(detected["object"]) == target:
            return detected
    return None


def read_perception() -> dict | None:
    """Read the on-board perception feed produced by the NAO motion bridge."""
    if not PERCEPTION_PATH.exists():
        return None
    try:
        return json.loads(PERCEPTION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def perception_is_fresh(perception: dict | None) -> bool:
    if not perception:
        return False
    timestamp = perception.get("timestamp")
    if not isinstance(timestamp, int):
        return False
    age_seconds = (epoch_ms() - timestamp) / 1000.0
    return 0.0 <= age_seconds <= PERCEPTION_MAX_AGE_SECONDS


def camera_detections(perception: dict | None) -> list[dict]:
    """Adapt the camera perception feed to the detection shape the event code expects.

    A relative position is synthesized from bearing + distance so downstream event
    payloads keep the same structure as the god-mode detections.
    """
    detections: list[dict] = []
    if not perception:
        return detections
    for detected in perception.get("detections", []):
        try:
            distance = float(detected.get("distance_m", 0.0))
            bearing = float(detected.get("bearing_rad", 0.0))
        except Exception:
            continue
        detections.append(
            {
                "object": normalize_object_name(detected.get("object", "")),
                "confidence": float(detected.get("confidence", 0.9)),
                "relative_position": {
                    "x": round(distance * math.sin(bearing), 3),
                    "y": 0.0,
                    "z": round(distance * math.cos(bearing), 3),
                },
                "distance_m": round(distance, 3),
                "bearing_rad": round(bearing, 4),
            }
        )
    return detections


def perceive(robot: Supervisor, position: list[float], yaw: float, use_camera_nav: bool, perception: dict | None) -> list[dict]:
    """Return detections from the head camera when camera-nav is active, else god-mode."""
    if use_camera_nav:
        return camera_detections(perception)
    return detect_visible_objects(robot, position, yaw)


def target_from_perception(perception: dict | None, target_object: str | None) -> dict | None:
    """Pick the nearest camera detection matching the requested target object."""
    if not perception or not target_object:
        return None
    target = normalize_object_name(target_object)
    best: dict | None = None
    for detected in perception.get("detections", []):
        if normalize_object_name(detected.get("object", "")) != target:
            continue
        if best is None or float(detected.get("distance_m", 1e9)) < float(best.get("distance_m", 1e9)):
            best = detected
    return best


def current_target_distance(
    use_camera_nav: bool,
    camera_target: dict | None,
    position: list[float],
    target_position: list[float] | None,
) -> float | None:
    if use_camera_nav:
        if camera_target is None:
            return None
        try:
            return round(float(camera_target.get("distance_m")), 3)
        except Exception:
            return None
    return planar_distance(position, target_position) if target_position is not None else None


def perception_min_clearance(perception: dict | None) -> float | None:
    depth = (perception or {}).get("depth") or {}
    value = depth.get("min_m")
    try:
        return round(float(value), 3) if value is not None else None
    except Exception:
        return None


def reactive_motion(perception: dict | None, target_object: str | None) -> str:
    """Choose the next discrete motion chunk from sensed data (camera-driven).

    Returns one of walk_forward / turn_left / turn_right / idle. bearing_rad is
    positive when the target is to the robot's right, so we turn right to face it.
    """
    depth = (perception or {}).get("depth") or {}
    center = float(depth.get("center_m", SAFE_FORWARD_CLEARANCE_M))
    left = float(depth.get("left_m", center))
    right = float(depth.get("right_m", center))
    target = target_from_perception(perception, target_object)

    if target is not None:
        bearing = float(target.get("bearing_rad", 0.0))
        distance = float(target.get("distance_m", 1e9))
        if distance <= TARGET_REACHED_DISTANCE_METERS:
            return "idle"
        if abs(bearing) > TARGET_BEARING_TOLERANCE_RAD:
            return "turn_right" if bearing > 0 else "turn_left"
        if center < SAFE_FORWARD_CLEARANCE_M:
            # Obstacle between us and the target: steer toward the more open side.
            return "turn_left" if left >= right else "turn_right"
        return "walk_forward"

    # Target not in view: rotate in place to scan; never walk forward blindly.
    return "turn_left"


def estimate_obstacle_distance(robot: Supervisor, robot_position: list[float]) -> float | None:
    distances: list[float] = []
    for def_name, radius in OBSTACLES.items():
        position = get_position(get_node(robot, def_name))
        if position is None:
            continue
        clearance = planar_distance(robot_position, position) - radius
        if clearance > 0:
            distances.append(clearance)
    if not distances:
        return None
    return round(min(distances), 3)


def obstacle_clearance_for_point(robot: Supervisor, point: list[float], ignore_def: str | None = None) -> float:
    clearances: list[float] = []
    for def_name, radius in OBSTACLES.items():
        if ignore_def is not None and def_name == ignore_def:
            continue
        position = get_position(get_node(robot, def_name))
        if position is None:
            continue
        clearances.append(planar_distance(point, position) - radius)
    if not clearances:
        return 999.0
    return min(clearances)


def _heading_forward(yaw: float) -> tuple[float, float]:
    # Unit vector the NAO base faces, matching desired_yaw = atan2(dx, -dy).
    return math.sin(yaw), -math.cos(yaw)


def _clearance_along_heading(robot: Supervisor, position: list[float], yaw: float, distance: float) -> float:
    fx, fy = _heading_forward(yaw)
    probe = [position[0] + fx * distance, position[1] + fy * distance, NAVIGATION_HEIGHT]
    return obstacle_clearance_for_point(robot, probe)


def forward_is_clear(robot: Supervisor, position: list[float], yaw: float) -> bool:
    return _clearance_along_heading(robot, position, yaw, FORWARD_LOOKAHEAD_M) >= WALK_STOP_CLEARANCE_M


def turn_toward_open_side(robot: Supervisor, position: list[float], yaw: float) -> str:
    left = _clearance_along_heading(robot, position, yaw + AVOID_TURN_PROBE_RADIANS, FORWARD_LOOKAHEAD_M)
    right = _clearance_along_heading(robot, position, yaw - AVOID_TURN_PROBE_RADIANS, FORWARD_LOOKAHEAD_M)
    return "turn_left" if left >= right else "turn_right"


def recover_if_fallen(robot: Supervisor, nao_node, position: list[float], yaw: float) -> bool:
    # Stand the NAO upright in place if it tipped or sank (a real-physics
    # stumble), preserving x/y progress and heading so navigation continues.
    if position[2] >= FALL_RECOVERY_MIN_Z:
        return False
    translation_field = nao_node.getField("translation")
    rotation_field = nao_node.getField("rotation")
    if translation_field is None or rotation_field is None:
        return False
    translation_field.setSFVec3f([position[0], position[1], NAVIGATION_HEIGHT])
    rotation_field.setSFRotation([0.0, 0.0, 1.0, yaw])
    try:
        nao_node.resetPhysics()
    except Exception:
        pass
    return True


def nearest_obstacle_to_point(
    robot: Supervisor,
    point: list[float],
    ignore_def: str | None = None,
) -> tuple[str | None, list[float] | None, float | None]:
    nearest_name: str | None = None
    nearest_position: list[float] | None = None
    nearest_clearance: float | None = None
    for def_name, radius in OBSTACLES.items():
        if ignore_def is not None and def_name == ignore_def:
            continue
        position = get_position(get_node(robot, def_name))
        if position is None:
            continue
        clearance = planar_distance(point, position) - radius
        if nearest_clearance is None or clearance < nearest_clearance:
            nearest_name = def_name
            nearest_position = position
            nearest_clearance = clearance
    return nearest_name, nearest_position, round(nearest_clearance, 3) if nearest_clearance is not None else None


def approach_goal_for_target(
    robot: Supervisor,
    robot_position: list[float],
    target_key: str | None,
    target_position: list[float] | None,
) -> list[float] | None:
    if target_position is None:
        return None

    normalized_target = normalize_object_name(target_key or "")
    direct_goal = [target_position[0], target_position[1], NAVIGATION_HEIGHT]
    if normalized_target != "cane":
        return direct_goal

    robot_to_target = planar_distance(robot_position, target_position)
    if robot_to_target <= TARGET_REACHED_DISTANCE_METERS + 0.35:
        return direct_goal

    _, nearest_obstacle_position, nearest_obstacle_clearance = nearest_obstacle_to_point(robot, target_position)

    if nearest_obstacle_position is not None:
        away_dx = target_position[0] - nearest_obstacle_position[0]
        away_dy = target_position[1] - nearest_obstacle_position[1]
    else:
        away_dx = target_position[0] - robot_position[0]
        away_dy = target_position[1] - robot_position[1]

    magnitude = math.sqrt(away_dx * away_dx + away_dy * away_dy)
    if magnitude < 1e-6:
        away_dx, away_dy = 0.0, -1.0
        magnitude = 1.0

    away_x = away_dx / magnitude
    away_y = away_dy / magnitude
    perp_x, perp_y = -away_y, away_x

    candidate_offsets = [
        (away_x * 0.62, away_y * 0.62),
        (away_x * 0.50 + perp_x * 0.28, away_y * 0.50 + perp_y * 0.28),
        (away_x * 0.50 - perp_x * 0.28, away_y * 0.50 - perp_y * 0.28),
        (away_x * 0.35 + perp_x * 0.42, away_y * 0.35 + perp_y * 0.42),
        (away_x * 0.35 - perp_x * 0.42, away_y * 0.35 - perp_y * 0.42),
    ]

    best_goal = direct_goal
    best_score = float("-inf")
    for offset_x, offset_y in candidate_offsets:
        candidate = [target_position[0] + offset_x, target_position[1] + offset_y, NAVIGATION_HEIGHT]
        clearance = obstacle_clearance_for_point(robot, candidate)
        robot_distance = planar_distance(robot_position, candidate)
        target_distance = planar_distance(candidate, target_position)
        score = (clearance * 2.6) - (robot_distance * 0.30) - (target_distance * 0.90)
        if score > best_score:
            best_score = score
            best_goal = candidate

    return best_goal


def route_for_command(
    active_command: dict | None,
    target_position: list[float] | None,
    robot_height: float,
) -> list[list[float]]:
    if active_command is None:
        return []

    action = active_command.get("action")
    target = normalize_object_name(active_command.get("target_object") or "")
    target_z = target_position[2] if target_position is not None else robot_height

    if action == "search_object" and target == "cane":
        cane_x = target_position[0] if target_position is not None else -2.12
        cane_y = target_position[1] if target_position is not None else -0.76
        return [
            [-1.65, -2.05, robot_height],
            [-1.55, -1.65, robot_height],
            [-1.58, -1.20, robot_height],
            [round(cane_x + 0.42, 3), round(cane_y - 0.18, 3), target_z],
        ]

    if action == "check_medicine" and target == "medicine_box":
        # Real walking must NEVER aim the robot at the box: the box sits on the
        # coffee table (centre ~(-0.8,-2.5), x[-1.2,-0.4]), so walking toward it
        # drives the NAO into the table and it topples -- exactly how v15 fell.
        # Instead route over OPEN FLOOR to a standing spot just WEST of the table
        # and stop there. The box (-0.82,-2.42) is ~0.63 m from that spot, inside
        # MEDICINE_REACH_DISTANCE_METERS (0.80), so the pick-up/hand-off fires while
        # the robot is still clear of the table. Two waypoints: a staging point NW
        # of the table (reachable from the spawn or from the cane-retrieval corner)
        # then the west standing spot. Because reach (0.80) > standing-spot-to-box
        # (0.63), completion triggers on the inbound approach, before the robot ever
        # reaches -- let alone overshoots into -- the table.
        return [
            [-1.7, -2.05, robot_height],
            [-1.45, -2.42, robot_height],
        ]

    if action == "support_user":
        return [
            [-1.75, -3.30, robot_height],
            [-1.55, -3.05, robot_height],
            [PRESENTATION_HOME[0], PRESENTATION_HOME[1], robot_height],
        ]

    return []


def navigation_goal_for_command(
    robot: Supervisor,
    position: list[float],
    active_command: dict | None,
    target_position: list[float] | None,
    route_index: int = 0,
    target_visible: bool = False,
    last_seen_target_position: list[float] | None = None,
) -> tuple[list[float] | None, int]:
    if active_command is None:
        return None, route_index

    action = active_command.get("action")
    if action == "search_object":
        target_key = normalize_object_name(active_command.get("target_object") or "")
        if target_key == "cane" and target_position is not None:
            route = route_for_command(active_command, target_position, NAVIGATION_HEIGHT)
            clamped_index = max(0, min(route_index, len(route)))
            while (
                clamped_index < len(route)
                and planar_distance(position, route[clamped_index]) <= WAYPOINT_REACHED_DISTANCE_METERS
            ):
                clamped_index += 1

            if clamped_index < len(route):
                return route[clamped_index], clamped_index
            return None, len(route)

        if target_visible and target_position is not None:
            return approach_goal_for_target(robot, position, active_command.get("target_object"), target_position), route_index
        if last_seen_target_position is not None:
            return approach_goal_for_target(
                robot,
                position,
                active_command.get("target_object"),
                last_seen_target_position,
            ), route_index
        return None, route_index

    route = route_for_command(active_command, target_position, NAVIGATION_HEIGHT)
    if not route:
        return None, route_index

    clamped_index = max(0, min(route_index, len(route)))
    while clamped_index < len(route) and planar_distance(position, route[clamped_index]) <= WAYPOINT_REACHED_DISTANCE_METERS:
        clamped_index += 1

    if clamped_index >= len(route):
        return None, len(route)
    return route[clamped_index], clamped_index


def move_target_to_handoff(robot: Supervisor, target_object: str | None, robot_position: list[float]) -> list[float] | None:
    target_key = normalize_object_name(target_object or "")
    target_def = KNOWN_OBJECTS.get(target_key)
    if target_def is None:
        return None
    node = get_node(robot, target_def)
    if node is None:
        return None

    translation_field = node.getField("translation")
    rotation_field = node.getField("rotation")
    if translation_field is None:
        return None

    current_position = list(translation_field.getSFVec3f())
    handoff_position = [robot_position[0] - 0.18, robot_position[1] + 0.10, max(current_position[2], 0.60)]
    translation_field.setSFVec3f(handoff_position)
    if rotation_field is not None and target_key == "cane":
        rotation_field.setSFRotation([1, 0, 0, 0.15])
    return handoff_position


def locomotion_for_goal(
    nao_node,
    current_position: list[float],
    goal_position: list[float] | None,
    reached_distance: float,
    prefer_turn_only: bool = False,
) -> tuple[str, bool, float | None]:
    if goal_position is None:
        return "idle", False, None

    dx = goal_position[0] - current_position[0]
    dy = goal_position[1] - current_position[1]
    distance = math.sqrt(dx * dx + dy * dy)
    if distance <= reached_distance:
        return "idle", False, round(distance, 3)

    desired_yaw = math.atan2(dx, -dy)
    yaw_error = normalize_angle(desired_yaw - get_yaw(nao_node))

    if abs(yaw_error) >= TURN_HARD_ALIGNMENT_RADIANS:
        return ("turn_left" if yaw_error > 0 else "turn_right"), True, round(distance, 3)
    if prefer_turn_only or abs(yaw_error) >= TURN_ALIGNMENT_RADIANS:
        return ("turn_left" if yaw_error > 0 else "turn_right"), True, round(distance, 3)
    return "walk_forward", True, round(distance, 3)


def motion_state_for_command(
    active_command: dict | None,
    command_ready: bool,
    locomotion_motion: str,
    locomotion_loop: bool,
    sequence: int,
) -> dict:
    if active_command is None:
        return {
            "timestamp": epoch_ms(),
            "command_id": None,
            "intent": None,
            "state": "idle",
            "motion": "idle",
            "loop": False,
            "sequence": sequence,
            "presentation_mode": True,
        }

    action = active_command.get("action")
    state = active_command.get("task_status") or "active"
    motion = locomotion_motion
    loop = locomotion_loop
    if action == "search_object" and command_ready:
        state = "retrieval_ready"
        motion = "hand_wave"
        loop = False
    elif action == "search_object" and motion in {"walk_forward", "turn_left", "turn_right"}:
        state = "approaching"
    elif action == "search_object":
        state = "scanning"
    elif action == "check_medicine" and command_ready:
        state = "medicine_ready"
        motion = "hand_wave"
        loop = False
    elif action == "check_medicine" and motion in {"walk_forward", "turn_left", "turn_right"}:
        state = "approaching"
    elif action == "support_user":
        state = "support_ready" if command_ready else "support"
        motion = "hand_wave" if command_ready else locomotion_motion
        loop = False if command_ready else locomotion_loop

    return {
        "timestamp": epoch_ms(),
        "command_id": active_command.get("command_id"),
        "intent": active_command.get("intent"),
        "action": action,
        "state": state,
        "motion": motion,
        "loop": loop,
        "sequence": sequence,
        "presentation_mode": True,
    }


def main() -> None:
    robot = Supervisor()
    controller_started_ms = epoch_ms()
    timestep = int(robot.getBasicTimeStep())
    nao_node = get_node(robot, ROBOT_DEF)
    if nao_node is None:
        raise RuntimeError(f"Could not find DEF {ROBOT_DEF} in the NAO demo world.")

    print(f"nao_assistant_supervisor version: {CONTROLLER_VERSION}")
    last_publish_time = -PUBLISH_INTERVAL_SECONDS
    last_room = None
    last_command_id = None
    active_command = None
    completed_targets: dict[str, dict] = {}
    last_motion_state: dict | None = None
    last_motion_signature: tuple[object, ...] | None = None
    last_search_position: list[float] | None = None
    stalled_search_steps = 0
    locomotion_motion = "idle"
    locomotion_loop = False
    committed_motion = "idle"
    motion_hold_until = 0.0
    settle_until = 0.0
    motion_sequence = 0
    nav_debug_last_pos: list[float] | None = None
    nav_debug_last_motion = "start"
    active_route_index = 0
    route_command_id: str | None = None
    last_seen_target_position: list[float] | None = None
    last_seen_target_time = -1.0
    announced_target_visibility: set[str] = set()
    announced_route_safety: set[str] = set()
    fallback_warned = False
    write_motion_state(
        {
            "timestamp": epoch_ms(),
            "command_id": None,
            "intent": None,
            "state": "idle",
            "motion": "idle",
            "loop": False,
            "sequence": motion_sequence,
            "presentation_mode": True,
        }
    )

    while robot.step(timestep) != -1:
        new_command, last_command_id = read_latest_command(last_command_id, controller_started_ms)
        if new_command is not None:
            active_command = new_command
            active_command["robot_action_started_at"] = active_command.get("robot_action_started_at") or epoch_ms()
            route_command_id = active_command.get("command_id")
            active_route_index = 0
            last_seen_target_position = None
            last_seen_target_time = -1.0
            print(
                "Accepted Webots command: "
                f"{active_command.get('command_id')} action={active_command.get('action')} "
                f"target={active_command.get('target_object')}"
            )
            write_events(
                [
                    create_event(
                        "robot_status_updated",
                        {
                            "status": "command_received",
                            "task_status": active_command.get("task_status"),
                            "active_command_id": active_command.get("command_id"),
                            "active_intent": active_command.get("intent"),
                            "target_object": active_command.get("target_object"),
                            "robot_model": "softbank_nao",
                            "sensor_source": "webots_supervisor_command_bridge",
                            **telemetry_timing_payload(active_command),
                        },
                    )
                ]
            )

        position = get_position(nao_node) or [0.0, 0.0, 0.0]
        if recover_if_fallen(robot, nao_node, position, get_yaw(nao_node)):
            position = get_position(nao_node) or position
        action = active_command.get("action") if active_command else None
        target_object = active_command.get("target_object") if active_command else None
        active_command_id = active_command.get("command_id") if active_command else None
        target_def = KNOWN_OBJECTS.get(normalize_object_name(target_object or ""))
        target_position = get_position(get_node(robot, target_def)) if target_def else None
        yaw = get_yaw(nao_node)
        perception = read_perception()
        camera_nav_possible = CAMERA_NAV_ENABLED and action in CAMERA_NAV_ACTIONS
        perception_fresh = perception_is_fresh(perception)
        use_camera_nav = camera_nav_possible and perception_fresh
        perception_source = "nao_head_camera" if use_camera_nav else "supervisor_godmode_fallback"
        camera_target = target_from_perception(perception, target_object) if use_camera_nav else None
        detections = perceive(robot, position, yaw, use_camera_nav, perception)
        target_detection = find_target_object(detections, target_object)
        target_distance = current_target_distance(use_camera_nav, camera_target, position, target_position)
        if target_detection is not None and target_position is not None:
            last_seen_target_position = [target_position[0], target_position[1], NAVIGATION_HEIGHT]
            last_seen_target_time = robot.getTime()
        remembered_target_position = (
            last_seen_target_position
            if last_seen_target_position is not None and robot.getTime() - last_seen_target_time <= SEARCH_MEMORY_SECONDS
            else None
        )
        navigation_is_active = (
            active_command is not None
            and action in {"search_object", "check_medicine", "support_user"}
            and active_command_id not in completed_targets
        )

        if navigation_is_active and use_camera_nav:
            # Camera-driven: pick the next motion chunk from sensed data, keeping the
            # existing chunk-commit machinery (motion_hold_until / MOTION_STEP_SECONDS).
            if robot.getTime() < motion_hold_until and committed_motion != "idle":
                locomotion_motion, locomotion_loop = committed_motion, False
            else:
                committed_motion = reactive_motion(perception, target_object)
                locomotion_motion, locomotion_loop = committed_motion, False
                motion_hold_until = robot.getTime() + MOTION_STEP_SECONDS.get(committed_motion, 0.0)
                motion_sequence += 1
            last_search_position = None
            stalled_search_steps = 0
        elif navigation_is_active and camera_nav_possible and not perception_fresh and not CAMERA_FALLBACK_ENABLED:
            # Camera-nav wanted but the feed is unavailable and fallback is disabled: hold.
            if not fallback_warned:
                print("Camera perception feed unavailable and fallback disabled; holding position.")
                fallback_warned = True
            locomotion_motion, locomotion_loop = "idle", False
            committed_motion = "idle"
            motion_hold_until = 0.0
            last_search_position = None
            stalled_search_steps = 0
        elif navigation_is_active:
            if camera_nav_possible and not perception_fresh and not fallback_warned:
                print("Camera perception feed unavailable; falling back to god-mode navigation.")
                fallback_warned = True
            if active_command_id != route_command_id:
                route_command_id = active_command_id
                active_route_index = 0
                last_seen_target_position = None
                last_seen_target_time = -1.0

            navigation_goal, active_route_index = navigation_goal_for_command(
                robot,
                position,
                active_command,
                target_position,
                route_index=active_route_index,
                target_visible=target_detection is not None,
                last_seen_target_position=remembered_target_position,
            )
            if navigation_goal is not None:
                # --- Real-physics navigation (v17): turn + walk, NO set_yaw ----
                # Drive heading and translation with the official TurnLeft40 /
                # TurnRight40 / Forwards50 gaits and let physics keep the robot
                # upright, so it actually STEPS. set_yaw teleported the base
                # orientation and toppled the walk, so it is not used here at all.
                # Each motion is held for its full duration (no mid-stride
                # interruption -> stays balanced), and we re-decide once it ends.
                # A wide alignment tolerance (> half a 40deg turn step) stops the
                # heading from ping-ponging; we only walk once roughly facing the
                # goal. Routes stay on open floor and stop before furniture, so the
                # robot never walks into a table and falls (that was v15's failure).
                goal_dx = navigation_goal[0] - position[0]
                goal_dy = navigation_goal[1] - position[1]
                desired_yaw = math.atan2(goal_dx, -goal_dy)
                yaw_error = normalize_angle(desired_yaw - get_yaw(nao_node))
                heading_aligned = abs(yaw_error) < TURN_ALIGNMENT_RADIANS

                if last_search_position is not None and planar_distance(position, last_search_position) < STALL_DETECTION_DISTANCE_METERS:
                    stalled_search_steps += 1
                else:
                    stalled_search_steps = 0
                last_search_position = list(position)

                now = robot.getTime()
                if now < motion_hold_until and committed_motion != "idle":
                    # Current gait is still playing -> let it finish (no mid-stride
                    # interruption keeps the NAO balanced).
                    locomotion_motion, locomotion_loop = committed_motion, False
                elif now < settle_until:
                    # Gait finished: hold the settled stance for SETTLE_SECONDS so
                    # physics can stabilise before the next gait starts from rest.
                    # This is the key fix -- back-to-back stop()+play() gait switches
                    # on a still-moving robot snap the leg pose and topple it.
                    committed_motion = "idle"
                    locomotion_motion, locomotion_loop = "idle", False
                else:
                    if heading_aligned and forward_is_clear(robot, position, get_yaw(nao_node)):
                        committed_motion = "walk_forward"
                    elif heading_aligned:
                        # Heading is right but an obstacle (e.g. the coffee table)
                        # is within the lookahead -- steer around it, don't walk in.
                        committed_motion = turn_toward_open_side(robot, position, get_yaw(nao_node))
                    else:
                        committed_motion = "turn_left" if yaw_error > 0 else "turn_right"
                    locomotion_motion, locomotion_loop = committed_motion, False
                    motion_hold_until = now + MOTION_STEP_SECONDS[committed_motion]
                    settle_until = motion_hold_until + SETTLE_SECONDS
                    motion_sequence += 1
            elif action == "search_object":
                if robot.getTime() < motion_hold_until and committed_motion != "idle":
                    locomotion_motion, locomotion_loop = committed_motion, False
                else:
                    committed_motion = "turn_left"
                    locomotion_motion, locomotion_loop = committed_motion, False
                    motion_hold_until = robot.getTime() + MOTION_STEP_SECONDS["turn_left"]
                    motion_sequence += 1
                last_search_position = list(position)
                stalled_search_steps = 0
            else:
                locomotion_motion, locomotion_loop = "idle", False
                committed_motion = "idle"
                motion_hold_until = 0.0
                last_search_position = None
                stalled_search_steps = 0
        else:
            locomotion_motion, locomotion_loop = "idle", False
            committed_motion = "idle"
            motion_hold_until = 0.0
            last_search_position = None
            stalled_search_steps = 0

        support_reached_now = False
        command_completed_now = active_command_id in completed_targets if active_command_id else False
        if navigation_is_active:
            position = get_position(nao_node) or position
            target_position = get_position(get_node(robot, target_def)) if target_def else None
            yaw = get_yaw(nao_node)
            detections = perceive(robot, position, yaw, use_camera_nav, perception)
            target_detection = find_target_object(detections, target_object)
            if target_detection is not None and target_position is not None:
                last_seen_target_position = [target_position[0], target_position[1], NAVIGATION_HEIGHT]
                last_seen_target_time = robot.getTime()
            remembered_target_position = (
                last_seen_target_position
                if last_seen_target_position is not None and robot.getTime() - last_seen_target_time <= SEARCH_MEMORY_SECONDS
                else None
            )
            navigation_goal, active_route_index = navigation_goal_for_command(
                robot,
                position,
                active_command,
                target_position,
                route_index=active_route_index,
                target_visible=target_detection is not None,
                last_seen_target_position=remembered_target_position,
            )
            target_distance_now = current_target_distance(use_camera_nav, camera_target, position, target_position)
            navigation_goal_distance_now = planar_distance(position, navigation_goal) if navigation_goal is not None else None
            support_reached_now = (
                action == "support_user"
                and navigation_goal_distance_now is not None
                and navigation_goal_distance_now <= WAYPOINT_REACHED_DISTANCE_METERS
            )
            reach_now = MEDICINE_REACH_DISTANCE_METERS if action == "check_medicine" else TARGET_REACHED_DISTANCE_METERS
            target_reached_now = target_distance_now is not None and target_distance_now <= reach_now
            command_ready_now = target_reached_now or support_reached_now or command_completed_now
        else:
            command_ready_now = command_completed_now

        motion_state = motion_state_for_command(
            active_command,
            command_ready_now,
            locomotion_motion,
            locomotion_loop,
            motion_sequence,
        )
        motion_signature = (
            motion_state.get("command_id"),
            motion_state.get("intent"),
            motion_state.get("action"),
            motion_state.get("state"),
            motion_state.get("motion"),
            motion_state.get("loop"),
            motion_state.get("sequence"),
            motion_state.get("presentation_mode"),
        )
        if motion_signature != last_motion_signature:
            write_motion_state(motion_state)
            last_motion_state = motion_state
            last_motion_signature = motion_signature

        current_time = robot.getTime()
        if current_time - last_publish_time < PUBLISH_INTERVAL_SECONDS:
            continue
        last_publish_time = current_time
        timestamp = epoch_ms()

        position = get_position(nao_node) or [0.0, 0.0, 0.0]
        yaw = get_yaw(nao_node)
        room = room_for_position(position)
        detections = perceive(robot, position, yaw, use_camera_nav, perception)
        target_detection = find_target_object(detections, target_object)
        if target_detection is not None and target_position is not None:
            last_seen_target_position = [target_position[0], target_position[1], NAVIGATION_HEIGHT]
            last_seen_target_time = robot.getTime()
        remembered_target_position = (
            last_seen_target_position
            if last_seen_target_position is not None and robot.getTime() - last_seen_target_time <= SEARCH_MEMORY_SECONDS
            else None
        )
        target_position = get_position(get_node(robot, target_def)) if target_def else None
        navigation_goal, active_route_index = navigation_goal_for_command(
            robot,
            position,
            active_command,
            target_position,
            route_index=active_route_index,
            target_visible=target_detection is not None,
            last_seen_target_position=remembered_target_position,
        )
        target_distance = current_target_distance(use_camera_nav, camera_target, position, target_position)
        navigation_goal_distance = planar_distance(position, navigation_goal) if navigation_goal is not None else None
        obstacle_distance = perception_min_clearance(perception) if use_camera_nav else estimate_obstacle_distance(robot, position)
        command_was_completed = active_command_id in completed_targets if active_command_id else False
        reach_distance = MEDICINE_REACH_DISTANCE_METERS if action == "check_medicine" else TARGET_REACHED_DISTANCE_METERS
        target_reached = target_distance is not None and target_distance <= reach_distance
        support_reached = (
            action == "support_user"
            and navigation_goal_distance is not None
            and navigation_goal_distance <= WAYPOINT_REACHED_DISTANCE_METERS
        )
        command_ready = target_reached or support_reached or command_was_completed
        robot_action_completed_at = (
            completed_targets.get(active_command_id, {}).get("robot_action_completed_at")
            if command_was_completed
            else timestamp
            if active_command_id and command_ready
            else None
        )
        events = [
            create_event(
                "robot_status_updated",
                {
                    "status": "target_found" if command_ready else "active",
                    "task_status": (
                        "retrieval_ready"
                        if action == "search_object" and command_ready
                        else "medicine_ready"
                        if action == "check_medicine" and command_ready
                        else "support_ready"
                        if action == "support_user" and command_ready
                        else "approaching_target"
                        if navigation_is_active
                        else active_command.get("task_status")
                        if active_command
                        else "monitoring_environment"
                    ),
                    "active_command_id": active_command_id,
                    "active_intent": active_command.get("intent") if active_command else None,
                    "target_object": target_object,
                    "target_distance_m": target_distance,
                    "navigation_goal": {"x": round(navigation_goal[0], 3), "y": round(navigation_goal[1], 3), "z": round(navigation_goal[2], 3)} if navigation_goal else None,
                    "navigation_goal_distance_m": navigation_goal_distance,
                    "current_room": room,
                    "position": {"x": round(position[0], 3), "y": round(position[1], 3), "z": round(position[2], 3)},
                    "robot_model": "softbank_nao",
                    "sensor_source": "nao_head_camera_recognition" if use_camera_nav else "webots_supervisor_visibility",
                    "perception_source": perception_source,
                    "camera_enabled": True,
                    "range_sensor_enabled": True,
                    "search_state": (
                        "retrieval_ready"
                        if action == "search_object" and command_ready
                        else "medicine_ready"
                        if action == "check_medicine" and command_ready
                        else "support_ready"
                        if action == "support_user" and command_ready
                        else "found"
                        if target_detection
                        else "approaching"
                        if navigation_is_active and navigation_goal is not None
                        else "scanning"
                        if action == "search_object"
                        else "idle"
                    ),
                    "presentation_mode": True,
                    **telemetry_timing_payload(active_command, robot_action_completed_at),
                },
                timestamp,
            )
        ]

        if room != last_room:
            events.append(
                create_event(
                    "room_detected",
                    {
                        "room": room,
                        "confidence": 0.9,
                        "method": "webots_nao_zone_map",
                        "position": events[0]["payload"]["position"],
                    },
                    timestamp,
                )
            )
            last_room = room

        for detected in detections:
            events.append(
                create_event(
                    "object_detected",
                    {
                        "object": detected["object"],
                        "confidence": detected["confidence"],
                        "relative_position": detected["relative_position"],
                        "sensor": "webots_supervisor_visibility",
                    },
                    timestamp,
                )
            )
            events.append(
                create_event(
                    "object_distance_estimated",
                    {
                        "object": detected["object"],
                        "distance_m": detected["distance_m"],
                        "sensor": "webots_supervisor_visibility",
                    },
                    timestamp,
                )
            )

        if detections:
            scene_names = [item["object"] for item in detections]
            events.append(
                create_event(
                    "scene_described",
                    {
                        "description": f"The NAO assistant is in the {room} and sees: {', '.join(scene_names)}.",
                        "detected_objects": scene_names,
                        "sensor": "webots_supervisor_visibility",
                    },
                    timestamp,
                )
            )

        if (
            navigation_is_active
            and action == "search_object"
            and target_detection is not None
            and active_command_id is not None
            and active_command_id not in announced_target_visibility
        ):
            announced_target_visibility.add(active_command_id)
            normalized_target = normalize_object_name(target_object or "target_object")
            events.append(
                create_event(
                    "important_object_alert",
                    {
                        "object": normalized_target,
                        "status": "located",
                        "severity": "info",
                        "reason": f"Requested {normalized_target} detected in view. The NAO is moving into retrieval position.",
                        "distance_m": target_detection["distance_m"],
                        "relative_position": target_detection["relative_position"],
                        "room": room,
                        "active_command_id": active_command_id,
                        "active_intent": active_command.get("intent"),
                        "sensor": "webots_supervisor_visibility",
                    },
                    timestamp,
                )
            )

        if (
            navigation_is_active
            and not use_camera_nav
            and action == "search_object"
            and normalize_object_name(target_object or "") == "cane"
            and target_position is not None
            and active_command_id is not None
            and active_command_id not in announced_route_safety
        ):
            obstacle_name, _, obstacle_clearance = nearest_obstacle_to_point(robot, target_position)
            if obstacle_name is not None and obstacle_clearance is not None and obstacle_clearance < 0.55:
                announced_route_safety.add(active_command_id)
                events.append(
                    create_event(
                        "safety_alert",
                        {
                            "severity": "warning",
                            "reason": "Obstacle detected close to the requested cane. The NAO is using a safer approach path.",
                            "obstacle_distance_m": max(0.0, obstacle_clearance),
                            "obstacle_name": OBSTACLE_LABELS.get(obstacle_name, obstacle_name.lower()),
                            "target_object": "cane",
                            "active_command_id": active_command_id,
                            "active_intent": active_command.get("intent"),
                            "room": room,
                            "sensor": "webots_supervisor_target_context",
                        },
                        timestamp,
                    )
                )

        if (
            navigation_is_active
            and action in {"search_object", "check_medicine"}
            and target_reached
            and active_command_id not in completed_targets
        ):
            handoff_position = move_target_to_handoff(robot, target_object, position)
            completed_targets[active_command_id] = {
                "object": normalize_object_name(target_object or "target_object"),
                "distance_m": target_distance,
                "handoff_position": handoff_position,
                "robot_action_completed_at": timestamp,
            }
            events.append(
                create_event(
                    "important_object_alert",
                    {
                        "object": normalize_object_name(target_object or "target_object"),
                        "status": "retrieved_for_handoff",
                        "severity": "info",
                        "reason": f"Target object {normalize_object_name(target_object or 'target_object')} reached and placed beside the humanoid for handoff.",
                        "distance_m": target_distance,
                        "handoff_position": {"x": round(handoff_position[0], 3), "y": round(handoff_position[1], 3), "z": round(handoff_position[2], 3)} if handoff_position else None,
                        "room": room,
                        "active_command_id": active_command_id,
                        "active_intent": active_command.get("intent"),
                        "retrieval_state": "handoff_ready",
                        "sensor": "webots_supervisor_target_position",
                        **telemetry_timing_payload(active_command, timestamp),
                    },
                    timestamp,
                )
            )
        elif (
            navigation_is_active
            and action == "support_user"
            and support_reached
            and active_command_id not in completed_targets
        ):
            completed_targets[active_command_id] = {
                "object": "support_zone",
                "distance_m": navigation_goal_distance,
                "handoff_position": {"x": round(position[0], 3), "y": round(position[1], 3), "z": round(position[2], 3)},
                "robot_action_completed_at": timestamp,
            }

        if obstacle_distance is not None and obstacle_distance < SAFETY_ALERT_DISTANCE_METERS:
            events.append(
                create_event(
                    "safety_alert",
                    {
                        "severity": "warning",
                        "reason": "Obstacle detected close to the humanoid.",
                        "obstacle_distance_m": obstacle_distance,
                        "sensor": "webots_supervisor_clearance",
                    },
                    timestamp,
                )
            )

        write_events(events)


if __name__ == "__main__":
    main()
