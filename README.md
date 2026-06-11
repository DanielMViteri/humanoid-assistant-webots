# Humanoid Assistant Webots

Humanoid Assistant Webots is a modular robot-assistant prototype for an elderly-care support demo. It combines a Webots house simulation, push-to-talk voice input, OpenAI-based intent classification, ElevenLabs speech, MongoDB Atlas event storage, and Webots sensor telemetry.

The current MVP scope is a functioning single-humanoid assistant that can receive typed or spoken user requests, classify the intent, respond through speech, send commands into Webots, move toward objects such as a cane, and export robot/system events for dashboard and health-check workflows.

## Project Structure

```text
swarmsense/
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

## MVP Goal

Build a small but working robot-assistant system where core abilities communicate as separate ROS2 Python nodes.

## Sprint 2 MongoDB Event Pipeline

Daniel's Sprint 2 deliverable is the feature-event data foundation:

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

Import Webots humanoid sensor events into MongoDB Atlas:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py
```

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
