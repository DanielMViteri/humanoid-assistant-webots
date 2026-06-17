# Repo Handoff

This file is a compact handoff for the current working state of the `swarmsense` repo. It is meant to help resume work quickly in a new chat, on a new machine, or after a pause.

## What This Repo Does

This project is a simulated elderly-care humanoid assistant built around:

- OpenAI intent classification
- ElevenLabs speech-to-text and text-to-speech
- MongoDB Atlas event export
- Webots simulation with a NAO-based house demo
- ChromaDB conversation memory
- YOLO scene analysis
- DeepFace emotion analysis
- Webcam capture utilities

The main demo goal is:

1. User speaks to the assistant.
2. Voice is transcribed.
3. Assistant classifies intent and optionally uses memory/perception context.
4. Assistant speaks back.
5. A Webots command is written for the robot.
6. Webots runs the robot behavior.
7. Events are exported to MongoDB Atlas for downstream dashboard/analytics use.

## Current Working State

As of this handoff, the repo has a working integrated path for:

- voice input
- OpenAI response generation
- ElevenLabs speech output
- MongoDB export with `--insert`
- ChromaDB memory retrieval and storage
- YOLO scene perception
- DeepFace emotion analysis in the dedicated perception environment
- Webots cane-finding command bridge
- Webots event import into MongoDB

The NAO demo is functional enough for demo use, but still should be treated as a guided simulation rather than fully autonomous physical navigation.

## Main Environments

There are multiple virtual environments in the repo history, but the important ones are:

- `.venv`
  - main project environment
- `.venv-perception311`
  - dedicated working perception environment
  - used for YOLO, ChromaDB, webcam capture, and DeepFace support

Avoid relying on older broken environments such as legacy perception/deepface envs unless they are rebuilt intentionally.

## Most Important Commands

Run from:

```bat
C:\Users\danie\OneDrive\Documents\Project Managment Project Ifnal\Project Managment\swarmsense
```

### Activate the perception environment

```bat
call tools\activate_perception_env.cmd
```

### Import check for perception stack

```bat
python tools\perception_import_check.py
```

### Voice + perception demo

```bat
tools\run_voice_with_perception.cmd --device 1 --duration 7 --insert --speak --play-audio --webcam-face --webots-command --use-memory
```

If device `1` is not right on the current machine, list devices first:

```bat
python ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py --list-devices
```

Then rerun with the correct input device number.

### Voice + webcam scene + webcam face

```bat
tools\run_voice_with_perception.cmd --device 1 --duration 7 --insert --speak --play-audio --webcam-scene --webcam-face --webots-command --use-memory
```

### MongoDB health check

```bat
python ros2_ws\src\robot_assistant\robot_assistant\mongo_health_check.py
```

### Import Webots events into MongoDB

```bat
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py
```

### Live emotion monitor

```bat
tools\run_live_emotion_monitor.cmd
```

## Where the Important Logic Lives

### Core assistant flow

- `ros2_ws/src/robot_assistant/robot_assistant/voice_assistant_runner.py`
  - push-to-talk voice workflow
- `ros2_ws/src/robot_assistant/robot_assistant/nlp_event_runner.py`
  - intent classification
  - event generation
  - MongoDB export
  - memory/perception integration

### Memory

- `ros2_ws/src/robot_assistant/robot_assistant/memory_chromadb.py`

ChromaDB stores conversation exchanges as local persistent memory under:

- `data/processed/chroma_memory`

It stores the user message and the robot response with metadata such as:

- intent
- emotion
- risk level
- speaker
- timestamp

When `--use-memory` is enabled, the assistant queries the most relevant previous exchanges and injects them into the runtime context before classification.

### Perception

- `ros2_ws/src/robot_assistant/robot_assistant/vision_yolo.py`
  - YOLO object detection
- `ros2_ws/src/robot_assistant/robot_assistant/emotion_deepface.py`
  - DeepFace emotion analysis
- `ros2_ws/src/robot_assistant/robot_assistant/webcam_capture.py`
  - webcam frame capture
- `ros2_ws/src/robot_assistant/robot_assistant/emotion_stream_monitor.py`
  - live emotion feed support

### MongoDB

- `ros2_ws/src/robot_assistant/robot_assistant/mongo_client.py`
- `ros2_ws/src/robot_assistant/robot_assistant/mongo_health_check.py`

### Webots bridge

- `ros2_ws/src/robot_assistant/robot_assistant/webots_event_importer.py`
- Webots controller files under `webots/`

## MongoDB Event Behavior

When the assistant is run with `--insert`, generated events are inserted into MongoDB Atlas.

Typical routing:

- `robot_status_updated` -> `robot_status`
- scene/object events -> `environment_events`
- `mood_detected`, `wellbeing_score_updated` -> `mood_events`
- negative mood or safety conditions -> `alerts`
- user/robot messages -> `conversation_events`

So yes: if DeepFace succeeds, emotion-related events are exported to MongoDB too.

## Why the Assistant Sometimes Mentions the Living Room

There are three possible sources:

1. Mock classifier behavior
   - in mock mode, the canned cane response explicitly mentions checking the living room first
2. Scenario defaults
   - the scripted cane scenario is initialized around `living_room`
3. ChromaDB memory
   - if `--use-memory` is enabled and prior exchanges mention room context, that context can influence the reply

So if you heard "let's check the living room," that may be memory-informed, but it is not coming from memory alone.

## Known Demo Realities

- The Webots demo is working, but it is still a demo-first navigation stack.
- The NAO behavior is good enough to show command-to-motion-to-event export, but not yet a production-grade physical planner.
- DeepFace depends on the dedicated perception environment and can be affected by Windows security controls if DLL loading is blocked.
- Webcam emotion analysis is currently snapshot-based unless the live monitor is explicitly used.

## Suggested Demo Sequence

1. Open Webots and load the NAO house world.
2. Start the simulation in a ready state.
3. Open CMD in repo root.
4. Activate or use the perception runner.
5. Run the voice+perception command with `--insert`.
6. Speak:
   - "Can you help me find my cane?"
7. Show:
   - robot response
   - Webots movement
   - MongoDB health check or Atlas collections
8. Optionally demonstrate mood capture with:
   - "I feel sad today"

## Good Files to Read First in a New Chat

- `README.md`
- `REPO_HANDOFF.md`
- `ros2_ws/src/robot_assistant/robot_assistant/nlp_event_runner.py`
- `ros2_ws/src/robot_assistant/robot_assistant/voice_assistant_runner.py`
- `ros2_ws/src/robot_assistant/robot_assistant/memory_chromadb.py`
- `ros2_ws/src/robot_assistant/robot_assistant/emotion_deepface.py`
- `ros2_ws/src/robot_assistant/robot_assistant/vision_yolo.py`

## Branching Note

This working integration state should be preserved on `dev`.

If a risky refactor starts after this point, create a new branch from the saved `dev` state rather than editing blindly on top of it.
