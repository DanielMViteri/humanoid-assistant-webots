# Sprint 3 Webots Integration Plan

## Goal

Connect a single simulated humanoid robot in Webots to the same event pipeline already used by the OpenAI, ElevenLabs, and MongoDB assistant.

```text
Webots camera/sensors
-> humanoid_sensor_controller.py
-> data/raw/webots_humanoid_events.jsonl
-> webots_event_importer.py
-> MongoDB Atlas
```

## Sensor Events

The controller is designed to emit:

- `robot_status_updated` from robot state, GPS position, and sensor availability
- `room_detected` from GPS zone mapping
- `object_detected` from Webots camera recognition
- `object_distance_estimated` from camera recognition position or range sensors
- `scene_described` from visible recognized objects
- `safety_alert` when an obstacle is close

## Webots Device Names

Attach `webots/controllers/humanoid_sensor_controller/humanoid_sensor_controller.py` to a Webots robot that has some of these devices:

- `camera`, `Camera`, `rgb_camera`, or `colour_camera`
- `range_finder`, `range-finder`, `depth_camera`, or `depth`
- `gps`
- `compass`
- distance sensors such as `ps0` to `ps7`, `front_sensor`, or `distance_sensor`

The controller degrades gracefully. Missing devices do not crash the whole demo; they simply reduce the event detail.

## Import To MongoDB

After running Webots long enough to generate events:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py
```

To import only the latest 25 events:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py --tail 25
```
