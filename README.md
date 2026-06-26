# Humanoid Assistant Webots

Humanoid Assistant Webots is a modular robot-assistant prototype for an elderly-care support demo. It combines a Webots house simulation, push-to-talk voice input, OpenAI-based intent classification, ElevenLabs speech, MongoDB Atlas event storage, and Webots sensor telemetry.

The current MVP scope is a functioning single-humanoid assistant that can receive typed or spoken user requests, classify the intent, respond through speech, send commands into Webots, move toward objects such as a cane, and export robot/system events for dashboard and health-check workflows.

## Project Structure

```text
humanoid-assistant-webots/
  ros2_ws/
    src/
      robot_assistant/  Active ROS2 package for modular robot abilities
  prototypes/
    telemetry_mvp/      Previous telemetry schema simulator and validator
    webots_telemetry/   Previous Webots telemetry proof of concept
  data/
    raw/                Raw generated or captured outputs
    processed/          Cleaned/scored outputs
  docs/
    planning/           Agile scope, backlog, sprint notes
    architecture/       Node architecture and integration decisions
  notebooks/            Optional analysis notebooks
  analytics/            Read-only MongoDB KPI analysis and generated outputs
  local_kpi_ui_foundation/
    README.md           Admin KPI dashboard access and validation guide
```

## Admin KPI Dashboard Access

The Admin KPI dashboard foundation on the `leona-nesto-dashboard-integration` branch lives in:

```text
local_kpi_ui_foundation/
```

Open the static dashboard directly from the repository:

```text
local_kpi_ui_foundation/admin_kpi_dashboard_ui.html
```

For the most reliable browser behavior, serve that folder locally from the repository root:

```bat
cd local_kpi_ui_foundation
python -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/admin_kpi_dashboard_ui.html
```

The dashboard reads the sanitized snapshot embedded in the page and, when served over HTTP, also reloads `real_analysis_snapshot.json` from the same folder. To validate the package before use, run:

```bat
python local_kpi_ui_foundation\validate_ui_foundation.py
```

## Saturday Demo

Use [docs/demo/saturday_demo_runbook.md](docs/demo/saturday_demo_runbook.md) for the current demo script, setup checklist, expected Webots behavior, MongoDB verification steps, and fallback plan.

## Initial Setup

```bat
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
pip install -r requirements-mongodb.txt
pip install -r requirements-openai.txt
pip install -r requirements-voice.txt
```

Perception note:
- `YOLO`, `DeepFace`, and `ChromaDB` are now wired in as optional features.
- `requirements-perception.txt` covers `YOLO`, `ChromaDB`, OpenCV, and Pillow for the dedicated perception environment.
- `YOLO_CONFIG_DIR` can be pointed at `data/processed/ultralytics` to keep Ultralytics settings and cache inside the repo instead of AppData.
- `DeepFace` may be easier to install from `requirements-deepface.txt` in a Python 3.11 or 3.12 environment than Python 3.14.
- The core demo still works without the perception stack.

### Rebuild Perception Environment

When the main demo environment is on Python 3.14, rebuild the dedicated perception environment with Python 3.12:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\rebuild_perception_env.ps1
```

This creates:

- `.venv-perception311`

Activate it from CMD:

```bat
call tools\activate_perception_env.cmd
```

Or skip activation entirely and call the isolated interpreter directly:

```bat
.\.venv-perception311\Scripts\python.exe tools\perception_import_check.py
```

Smoke-test the rebuilt environment:

```bat
python tools\perception_import_check.py
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --mock --text "I feel sad today" --scene-image webots\worlds\.nao_house_demo.jpg --face-image webots\worlds\.nao_house_demo.jpg --use-memory --no-output
```

## MVP Goal

Build a small but working robot-assistant system where core abilities communicate as separate ROS2 Python nodes.

## Sprint 2 MongoDB Event Pipeline

Daniel's (me) Sprint 2 deliverable is the feature-event data foundation:

```text
scripted humanoid feature events -> MongoDB Atlas -> Leona's dashboard data source
```

Kafka and the dashboard are intentionally deferred from Daniel's current implementation step.

Copy `.env.example` to `.env`, then add the team's MongoDB Atlas URI locally:

```bat
copy .env.example .env
```

Generate the Sprint 2 feature events without inserting:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\scenario_runner.py --pretty
```

Generate one named scenario:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\scenario_runner.py --scenario find_cane
python ros2_ws\src\robot_assistant\robot_assistant\scenario_runner.py --scenario medicine_reminder
python ros2_ws\src\robot_assistant\robot_assistant\scenario_runner.py --scenario wellbeing_checkin
```

Insert all demo scenarios into MongoDB Atlas after `.env` is configured:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\scenario_runner.py --scenario all --insert
```

Run Clara's health check:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\mongo_health_check.py
```

Backup and reset MongoDB demo collections before a clean demo:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\demo_reset.py
```

Create a backup without deleting records:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\demo_reset.py --backup-only
```

Classify typed user input with OpenAI, convert it to approved events, and insert it:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "Can you help me find my cane?" --insert
```

Run an interactive typed assistant session:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --interactive --insert
```

Run the assistant with ElevenLabs speech output:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --interactive --insert --speak
```

Run the assistant with ChromaDB memory enabled:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --interactive --insert --use-memory
```

Run the assistant with YOLO scene perception from an image:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "Can you help me find my cane?" --scene-image data\raw\webots_scene.png --insert
```

Run the assistant with DeepFace emotion analysis from a face image:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "I feel a bit sad today." --face-image data\raw\user_face.jpg --insert
```

Run the assistant with memory, YOLO, and DeepFace together:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "Can you help me find my cane?" --use-memory --scene-image data\raw\webots_scene.png --face-image data\raw\user_face.jpg --insert
```

Open the generated MP3 after each response:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --interactive --insert --speak --play-audio
```

Run push-to-talk voice input with spoken responses:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py --insert --speak --play-audio
```

Run push-to-talk voice input and send commands to Webots:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py --insert --speak --play-audio --webots-command
```

Run the voice assistant with optional memory and perception context:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py --insert --speak --webots-command --use-memory --scene-image data\raw\webots_scene.png --face-image data\raw\user_face.jpg
```

Run the voice assistant with live webcam scene and face capture from the dedicated perception environment:

```bat
tools\run_voice_with_perception.cmd --device 2 --duration 7 --insert --speak --play-audio --webcam-scene --webcam-face
```

Import Webots humanoid sensor events into MongoDB Atlas:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py
```

### End-to-end telemetry timing fields

The dashboard, backend, bridge, Webots controllers, MongoDB importer, and
admin telemetry table now carry these timing fields when the data is available:

```text
ui_triggered_at
backend_received_at
bridge_received_at
robot_action_started_at
robot_action_completed_at
mongodb_logged_at
dashboard_updated_at
```

All values are epoch milliseconds. They are used to trace one dashboard action
from the UI click through backend receipt, bridge pickup, robot action start and
completion, MongoDB persistence, and the provider dashboard refresh. The fields
are stored on the MongoDB document and mirrored into `payload` where existing
dashboard helpers read nested values.

Test the same flow without using the OpenAI API:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "I feel lonely today" --mock --insert
```

## MVP Node Direction

- `input_node`: receives typed or spoken user input.
- `nlp_node`: uses the OpenAI API for response generation and structured mood/intent output.
- `tts_node`: speaks the response using a text-to-speech provider.
- `session_node`: stores conversation/session events.
- `dashboard_node`: displays status, mood/session history, and robot/system state.
- `telemetry_node`: publishes robot/system telemetry using the existing Telemetry Schema v1.

## Preserved Prototype

The earlier telemetry simulator is preserved under `prototypes/telemetry_mvp` as evidence that Telemetry Schema v1 can be generated and validated for three robots.

Run it from the project root:

```bat
python prototypes\telemetry_mvp\src\simulator\telemetry_simulator.py --ticks 10
python prototypes\telemetry_mvp\src\analytics\validate_telemetry.py
```
