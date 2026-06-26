"""Webots controller that exports single-humanoid camera/sensor events as JSONL.

Attach this controller to a Webots Supervisor robot with optional devices named:
- camera, Camera, rgb_camera, or colour_camera
- range_finder, range-finder, depth_camera, or depth
- gps
- compass
- distance sensors such as ps0..ps7, distance_sensor, front_sensor

The controller does not require MongoDB packages inside Webots. It writes schema
events to data/raw/webots_humanoid_events.jsonl, then webots_event_importer.py can
insert them into MongoDB from the project venv.
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
except ImportError as exc:  # Allows py_compile outside Webots.
    raise RuntimeError("This controller must be run by Webots.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROBOT_ASSISTANT_PATH = PROJECT_ROOT / "ros2_ws" / "src" / "robot_assistant" / "robot_assistant"
sys.path.insert(0, str(ROBOT_ASSISTANT_PATH))

from event_schema import DEFAULT_ROBOT_ID, DEFAULT_SOURCE, DEFAULT_USER_ID, validate_event  # noqa: E402


OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "webots_humanoid_events.jsonl"
COMMAND_PATH = PROJECT_ROOT / "data" / "raw" / "webots_command.json"
CONTROLLER_VERSION = "2026-06-10-retrieval-handoff-v1"
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
SEARCH_ROTATION_STEP = 0.18
APPROACH_STEP_METERS = 0.035
TARGET_REACHED_DISTANCE_METERS = 0.55
WAYPOINT_REACHED_DISTANCE_METERS = 0.25
ROOM_ZONES = [
    {"room": "living_room", "x_min": -2.5, "x_max": 0.0, "y_min": -2.5, "y_max": 2.5},
    {"room": "kitchen", "x_min": 0.0, "x_max": 2.5, "y_min": -2.5, "y_max": 0.0},
    {"room": "bedroom", "x_min": 0.0, "x_max": 2.5, "y_min": 0.0, "y_max": 2.5},
]


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


def get_available_devices(robot: Supervisor) -> dict[str, object]:
    devices = {}
    try:
        device_count = robot.getNumberOfDevices()
        for index in range(device_count):
            device = robot.getDeviceByIndex(index)
            devices[device.getName()] = device
    except Exception as exc:
        print(f"Could not list Webots devices, using known demo device names: {exc}")

    if not devices:
        for name in ["camera", "gps", "compass", "front_sensor"]:
            try:
                devices[name] = robot.getDevice(name)
            except Exception:
                pass
    return devices


def get_device(devices: dict[str, object], names: list[str]):
    for name in names:
        if name in devices:
            return devices[name]
    return None


def get_named_distance_sensors(devices: dict[str, object], timestep: int) -> list:
    sensors = []
    candidate_names = [
        "distance_sensor",
        "front_sensor",
        "front distance sensor",
        "sonar",
        "ps0",
        "ps1",
        "ps2",
        "ps3",
        "ps4",
        "ps5",
        "ps6",
        "ps7",
    ]
    for name in candidate_names:
        sensor = get_device(devices, [name])
        if sensor is None:
            continue
        try:
            sensor.enable(timestep)
            sensors.append(sensor)
        except Exception:
            pass
    return sensors


def room_for_position(position: list[float]) -> str:
    x = position[0]
    y = position[1] if len(position) > 1 else 0.0
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


def distance_from_position(position: list[float]) -> float:
    return round(math.sqrt(sum(value * value for value in position[:3])), 3)


def planar_distance(first: list[float], second: list[float]) -> float:
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    return round(math.sqrt(dx * dx + dy * dy), 3)


def navigation_goal_for_target(position: list[float], target_object: str | None, target_position: list[float] | None) -> list[float] | None:
    if target_position is None:
        return None

    if normalize_object_name(target_object or "") == "cane":
        # Approach the cane from the open side of the living room instead of cutting through the chair.
        cane_route = [
            [-1.0, 0.55, target_position[2]],
            [-1.0, 0.95, target_position[2]],
            [-1.18, 1.16, target_position[2]],
        ]
        for waypoint in cane_route:
            if planar_distance(position, waypoint) > WAYPOINT_REACHED_DISTANCE_METERS:
                return waypoint

    return target_position


def def_name_for_target(target_object: str | None) -> str | None:
    target = normalize_object_name(target_object or "")
    if target == "cane":
        return "CANE"
    if target == "medicine_box":
        return "MEDICINE_BOX"
    return None


def get_node_position(robot: Supervisor, def_name: str | None) -> list[float] | None:
    if not def_name:
        return None
    node = robot.getFromDef(def_name)
    if node is None:
        return None
    translation_field = node.getField("translation")
    if translation_field is None:
        return None
    return list(translation_field.getSFVec3f())


def move_target_to_handoff(robot: Supervisor, target_object: str | None, robot_position: list[float]) -> list[float] | None:
    """Move a reached target into a visible handoff position beside the humanoid."""
    def_name = def_name_for_target(target_object)
    if def_name is None:
        return None

    node = robot.getFromDef(def_name)
    if node is None:
        return None

    translation_field = node.getField("translation")
    rotation_field = node.getField("rotation")
    if translation_field is None:
        return None

    target_position = list(translation_field.getSFVec3f())
    handoff_position = [
        robot_position[0] - 0.12,
        robot_position[1] + 0.08,
        target_position[2],
    ]
    translation_field.setSFVec3f(handoff_position)

    if rotation_field is not None and normalize_object_name(target_object or "") == "cane":
        rotation_field.setSFRotation([1, 0, 0, 0.25])

    return handoff_position


def target_matches(detected_object: str, target_object: str | None) -> bool:
    if not target_object:
        return False
    detected = normalize_object_name(detected_object)
    target = normalize_object_name(target_object)
    return detected == target


def detect_objects(camera) -> list[dict]:
    if camera is None:
        return []
    try:
        objects = camera.getRecognitionObjects()
    except Exception:
        return []

    detected = []
    for item in objects:
        raw_model = ""
        try:
            raw_model = item.get_model()
        except Exception:
            try:
                raw_model = item.getModel()
            except Exception:
                raw_model = "recognized_object"

        try:
            relative_position = list(item.get_position())
        except Exception:
            try:
                relative_position = list(item.getPosition())
            except Exception:
                relative_position = [0.0, 0.0, 0.0]

        detected.append(
            {
                "object": normalize_object_name(raw_model),
                "confidence": 0.9,
                "relative_position": {
                    "x": round(relative_position[0], 3),
                    "y": round(relative_position[1], 3),
                    "z": round(relative_position[2], 3),
                },
                "distance_m": distance_from_position(relative_position),
            }
        )
    return detected


def find_target_object(detected_objects: list[dict], target_object: str | None) -> dict | None:
    for detected in detected_objects:
        if target_matches(detected["object"], target_object):
            return detected
    return None


def estimate_obstacle_distance(range_finder, distance_sensors: list) -> float | None:
    values: list[float] = []
    if range_finder is not None:
        try:
            image = range_finder.getRangeImage()
            finite_values = [value for value in image if math.isfinite(value) and value > 0]
            if finite_values:
                values.append(min(finite_values))
        except Exception:
            pass

    for sensor in distance_sensors:
        try:
            value = float(sensor.getValue())
        except Exception:
            continue
        if value > 0:
            values.append(value)

    if not values:
        return None
    return round(min(values), 3)


def write_events(events: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as output_file:
        for event in events:
            output_file.write(json.dumps(event, separators=(",", ":")) + "\n")
            print(json.dumps(event, separators=(",", ":")))


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


def apply_command_motion(self_node, command: dict | None) -> None:
    if command is None or self_node is None:
        return
    action = command.get("action")
    rotation_field = self_node.getField("rotation")
    translation_field = self_node.getField("translation")
    if rotation_field is None or translation_field is None:
        return
    rotation = list(rotation_field.getSFRotation())
    translation = list(translation_field.getSFVec3f())

    if action == "search_object":
        rotation[3] += 0.35
        translation[0] = max(-2.0, translation[0] + 0.08)
        translation[1] = min(2.0, translation[1] + 0.04)
    elif action == "check_medicine":
        rotation[3] -= 0.25
        translation[0] = min(2.0, translation[0] + 0.06)
        translation[1] = max(-2.0, translation[1] - 0.04)
    elif action == "support_user":
        rotation[3] += 0.12

    rotation_field.setSFRotation(rotation)
    translation_field.setSFVec3f(translation)


def apply_search_scan(self_node, command: dict | None) -> None:
    if command is None or self_node is None or command.get("action") != "search_object":
        return
    rotation_field = self_node.getField("rotation")
    if rotation_field is None:
        return
    rotation = list(rotation_field.getSFRotation())
    rotation[3] += SEARCH_ROTATION_STEP
    rotation_field.setSFRotation(rotation)


def approach_target(
    self_node,
    current_position: list[float],
    goal_position: list[float] | None,
    reached_distance: float,
) -> float | None:
    if self_node is None or goal_position is None:
        return None

    translation_field = self_node.getField("translation")
    rotation_field = self_node.getField("rotation")
    if translation_field is None:
        return None

    dx = goal_position[0] - current_position[0]
    dy = goal_position[1] - current_position[1]
    distance = math.sqrt(dx * dx + dy * dy)
    if distance <= reached_distance:
        return round(distance, 3)

    step = min(APPROACH_STEP_METERS, distance - reached_distance)
    next_position = list(current_position)
    next_position[0] += (dx / distance) * step
    next_position[1] += (dy / distance) * step
    translation_field.setSFVec3f(next_position)

    if rotation_field is not None:
        yaw = math.atan2(dx, -dy)
        rotation_field.setSFRotation([0, 0, 1, yaw])

    try:
        self_node.resetPhysics()
    except Exception:
        pass

    return round(distance, 3)


def main() -> None:
    robot = Supervisor()
    self_node = robot.getSelf()
    controller_started_ms = epoch_ms()
    timestep = int(robot.getBasicTimeStep())
    devices = get_available_devices(robot)
    print(f"humanoid_sensor_controller version: {CONTROLLER_VERSION}")
    print(f"Detected Webots devices: {', '.join(sorted(devices.keys())) or 'none'}")
    camera = get_device(devices, ["camera", "Camera", "rgb_camera", "colour_camera"])
    range_finder = get_device(devices, ["range_finder", "range-finder", "depth_camera", "depth"])
    gps = get_device(devices, ["gps", "GPS"])
    compass = get_device(devices, ["compass", "Compass"])

    if camera is not None:
        camera.enable(timestep)
        try:
            camera.recognitionEnable(timestep)
        except Exception:
            print("Camera exists, but recognition is not enabled on this Webots camera.")
    if range_finder is not None:
        range_finder.enable(timestep)
    if gps is not None:
        gps.enable(timestep)
    if compass is not None:
        compass.enable(timestep)

    distance_sensors = get_named_distance_sensors(devices, timestep)
    last_publish_time = -PUBLISH_INTERVAL_SECONDS
    last_room = None
    last_command_id = None
    active_command = None
    found_command_ids = set()
    completed_targets = {}

    while robot.step(timestep) != -1:
        new_command, last_command_id = read_latest_command(last_command_id, controller_started_ms)
        if new_command is not None:
            active_command = new_command
            active_command["robot_action_started_at"] = active_command.get("robot_action_started_at") or epoch_ms()
            apply_command_motion(self_node, active_command)
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
                            "sensor_source": "webots_command_bridge",
                            **telemetry_timing_payload(active_command),
                        },
                    )
                ]
            )

        motion_position = list(gps.getValues()) if gps is not None else [0.0, 0.0, 0.0]
        motion_target_object = active_command.get("target_object") if active_command else None
        motion_active_command_id = active_command.get("command_id") if active_command else None
        motion_target_position = get_node_position(robot, def_name_for_target(motion_target_object))
        motion_target_distance = (
            planar_distance(motion_position, motion_target_position) if motion_target_position is not None else None
        )
        motion_search_is_active = (
            active_command is not None
            and active_command.get("action") == "search_object"
            and motion_active_command_id not in found_command_ids
        )
        if motion_search_is_active and motion_target_position is not None:
            motion_navigation_goal = navigation_goal_for_target(motion_position, motion_target_object, motion_target_position)
            if motion_target_distance is not None and motion_target_distance > TARGET_REACHED_DISTANCE_METERS:
                approach_target(self_node, motion_position, motion_navigation_goal, WAYPOINT_REACHED_DISTANCE_METERS)
        elif motion_search_is_active:
            apply_search_scan(self_node, active_command)

        current_time = robot.getTime()
        if current_time - last_publish_time < PUBLISH_INTERVAL_SECONDS:
            continue
        last_publish_time = current_time
        timestamp = epoch_ms()

        position = list(gps.getValues()) if gps is not None else [0.0, 0.0, 0.0]
        room = room_for_position(position)
        obstacle_distance = estimate_obstacle_distance(range_finder, distance_sensors)
        detected_objects = detect_objects(camera)
        target_object = active_command.get("target_object") if active_command else None
        active_command_id = active_command.get("command_id") if active_command else None
        target_detection = find_target_object(detected_objects, target_object)
        target_position = get_node_position(robot, def_name_for_target(target_object))
        navigation_goal = navigation_goal_for_target(position, target_object, target_position)
        target_distance = planar_distance(position, target_position) if target_position is not None else None
        navigation_goal_distance = planar_distance(position, navigation_goal) if navigation_goal is not None else None
        target_area_reached = target_distance is not None and target_distance <= TARGET_REACHED_DISTANCE_METERS
        target_completion_reached = target_area_reached or (target_position is None and target_detection is not None)
        command_was_completed = active_command_id in completed_targets if active_command_id else False
        robot_action_completed_at = (
            completed_targets.get(active_command_id, {}).get("robot_action_completed_at")
            if command_was_completed
            else timestamp
            if active_command_id and (target_detection or target_area_reached)
            else None
        )
        search_is_active = (
            active_command is not None
            and active_command.get("action") == "search_object"
            and active_command_id not in found_command_ids
        )

        events = [
            create_event(
                "robot_status_updated",
                {
                    "status": "target_found" if target_detection or target_area_reached or command_was_completed else "active",
                    "task_status": "retrieval_ready" if target_area_reached or command_was_completed else "target_found" if target_detection else "approaching_target" if search_is_active else active_command.get("task_status") if active_command else "monitoring_environment",
                    "active_command_id": active_command_id,
                    "active_intent": active_command.get("intent") if active_command else None,
                    "target_object": target_object,
                    "target_distance_m": target_distance,
                    "navigation_goal": {"x": round(navigation_goal[0], 3), "y": round(navigation_goal[1], 3), "z": round(navigation_goal[2], 3)} if navigation_goal else None,
                    "navigation_goal_distance_m": navigation_goal_distance,
                    "current_room": room,
                    "position": {"x": round(position[0], 3), "y": round(position[1], 3), "z": round(position[2], 3)},
                    "sensor_source": "webots",
                    "camera_enabled": camera is not None,
                    "range_sensor_enabled": range_finder is not None or bool(distance_sensors),
                    "search_state": "retrieval_ready" if target_area_reached or command_was_completed else "found" if target_detection else "approaching" if search_is_active and target_position is not None else "scanning" if search_is_active else "idle",
                    **telemetry_timing_payload(active_command, robot_action_completed_at),
                },
                timestamp,
            )
        ]

        if room != last_room:
            events.append(
                create_event(
                    "room_detected",
                    {"room": room, "confidence": 0.85, "method": "webots_gps_zone", "position": events[0]["payload"]["position"]},
                    timestamp,
                )
            )
            last_room = room

        for detected in detected_objects:
            events.append(
                create_event(
                    "object_detected",
                    {
                        "object": detected["object"],
                        "confidence": detected["confidence"],
                        "relative_position": detected["relative_position"],
                        "sensor": "webots_camera_recognition",
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
                        "sensor": "webots_camera_recognition",
                    },
                    timestamp,
                )
            )

        scene_objects = [item["object"] for item in detected_objects]
        if scene_objects:
            events.append(
                create_event(
                    "scene_described",
                    {
                        "description": f"The humanoid is in the {room} and sees: {', '.join(scene_objects)}.",
                        "detected_objects": scene_objects,
                        "sensor": "webots_camera_recognition",
                    },
                    timestamp,
                )
            )

        if search_is_active and target_completion_reached:
            found_command_ids.add(active_command_id)
            found_object = target_detection["object"] if target_detection else normalize_object_name(target_object or "target_object")
            handoff_position = move_target_to_handoff(robot, target_object, position) if target_area_reached else None
            completed_targets[active_command_id] = {
                "object": found_object,
                "distance_m": target_detection["distance_m"] if target_detection else target_distance,
                "handoff_position": handoff_position,
                "robot_action_completed_at": timestamp,
            }
            events.append(
                create_event(
                    "important_object_alert",
                    {
                        "object": found_object,
                        "status": "retrieved_for_handoff" if handoff_position else "found",
                        "severity": "info",
                        "reason": f"Target object {found_object} reached and moved into handoff position." if handoff_position else f"Target object {found_object} found by the humanoid retrieval task.",
                        "distance_m": target_detection["distance_m"] if target_detection else target_distance,
                        "relative_position": target_detection["relative_position"] if target_detection else None,
                        "handoff_position": {"x": round(handoff_position[0], 3), "y": round(handoff_position[1], 3), "z": round(handoff_position[2], 3)} if handoff_position else None,
                        "room": room,
                        "active_command_id": active_command_id,
                        "active_intent": active_command.get("intent"),
                        "retrieval_state": "handoff_ready" if handoff_position else "target_found",
                        "sensor": "webots_camera_recognition" if target_detection else "webots_supervisor_target_position",
                        **telemetry_timing_payload(active_command, timestamp),
                    },
                    timestamp,
                )
            )

        if obstacle_distance is not None and obstacle_distance < 0.5:
            events.append(
                create_event(
                    "safety_alert",
                    {
                        "severity": "warning",
                        "reason": "Obstacle detected close to the humanoid.",
                        "obstacle_distance_m": obstacle_distance,
                        "sensor": "webots_distance_or_range_sensor",
                    },
                    timestamp,
                )
            )

        write_events(events)


if __name__ == "__main__":
    main()
