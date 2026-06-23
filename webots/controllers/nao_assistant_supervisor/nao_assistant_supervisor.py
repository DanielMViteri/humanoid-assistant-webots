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
CONTROLLER_VERSION = "2026-06-23-nao-supervisor-v9-godmode-heading"
ROBOT_DEF = "NAO_ASSISTANT"
ROBOT_ID = "H1"
PUBLISH_INTERVAL_SECONDS = 1.0
NAVIGATION_HEIGHT = 0.334
TARGET_REACHED_DISTANCE_METERS = 0.55
WAYPOINT_REACHED_DISTANCE_METERS = 0.50
# The medicine box sits ON a table, so the NAO can't get as close as a floor object
# without colliding/circling. Count it as "found on the table" when seen within sight.
MEDICINE_SIGHT_DISTANCE_METERS = 1.15
STALL_DETECTION_DISTANCE_METERS = 0.02
STALL_DETECTION_STEPS = 20
TURN_ALIGNMENT_RADIANS = 0.30
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
    rotation = list(field.getSFRotation())
    return float(rotation[3])


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
        return [
            [-1.45, -3.05, robot_height],
            [-1.15, -2.78, robot_height],
            [-1.08, -2.70, target_z],
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
    motion_sequence = 0
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
                        },
                    )
                ]
            )

        position = get_position(nao_node) or [0.0, 0.0, 0.0]
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
                # --- God-mode heading control (v9) ----------------------------
                # Steer the base heading toward the goal every tick via set_yaw,
                # instead of relying on incremental turn .motion physics. The old
                # approach oscillated and never converged when the goal sat ~180deg
                # behind the robot (yaw_error flipped sign across +/-pi). Driving
                # the heading directly makes navigation start-orientation agnostic:
                # the robot pivots to face the goal, then walks straight to it.
                goal_dx = navigation_goal[0] - position[0]
                goal_dy = navigation_goal[1] - position[1]
                if goal_dx or goal_dy:
                    desired_yaw = math.atan2(goal_dx, -goal_dy)
                    current_yaw = get_yaw(nao_node)
                    yaw_error = normalize_angle(desired_yaw - current_yaw)
                    max_step = MAX_YAW_RATE_RADIANS_PER_SEC * (timestep / 1000.0)
                    set_yaw(
                        nao_node,
                        normalize_angle(current_yaw + max(-max_step, min(max_step, yaw_error))),
                    )
                    heading_aligned = abs(yaw_error) < TURN_ALIGNMENT_RADIANS
                    pivot_motion = "turn_left" if yaw_error > 0 else "turn_right"
                else:
                    heading_aligned = True
                    pivot_motion = "idle"

                if last_search_position is not None and planar_distance(position, last_search_position) < STALL_DETECTION_DISTANCE_METERS:
                    stalled_search_steps += 1
                else:
                    stalled_search_steps = 0
                last_search_position = list(position)

                if not heading_aligned:
                    # Pivot in place to face the goal. set_yaw above does the real
                    # rotation; the motion is just the matching leg animation, and
                    # we re-evaluate every tick (no hold) so steering stays smooth.
                    if committed_motion != pivot_motion:
                        committed_motion = pivot_motion
                        motion_sequence += 1
                    locomotion_motion, locomotion_loop = committed_motion, False
                    motion_hold_until = 0.0
                else:
                    # Facing the goal: walk forward in chunks (the gait advances the
                    # robot; set_yaw keeps it pointed at the goal each tick).
                    if robot.getTime() < motion_hold_until and committed_motion == "walk_forward":
                        locomotion_motion, locomotion_loop = committed_motion, False
                    else:
                        committed_motion = "walk_forward"
                        locomotion_motion, locomotion_loop = committed_motion, False
                        motion_hold_until = robot.getTime() + MOTION_STEP_SECONDS["walk_forward"]
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
            reach_now = MEDICINE_SIGHT_DISTANCE_METERS if action == "check_medicine" else TARGET_REACHED_DISTANCE_METERS
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
        reach_distance = MEDICINE_SIGHT_DISTANCE_METERS if action == "check_medicine" else TARGET_REACHED_DISTANCE_METERS
        target_reached = target_distance is not None and target_distance <= reach_distance
        support_reached = (
            action == "support_user"
            and navigation_goal_distance is not None
            and navigation_goal_distance <= WAYPOINT_REACHED_DISTANCE_METERS
        )
        command_ready = target_reached or support_reached or command_was_completed
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
