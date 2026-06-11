# Saturday Demo Runbook

Target demo date: Saturday, June 13, 2026

## Current Status

The project currently has a working end-to-end MVP path:

```text
Voice input
-> ElevenLabs speech-to-text
-> OpenAI intent classification and response
-> ElevenLabs text-to-speech
-> MongoDB Atlas event insertion
-> Webots command file
-> Webots humanoid controller
-> Webots sensor and retrieval events
-> MongoDB import for dashboard/health checks
```

The main demo scenario is:

```text
User asks the humanoid to find a cane.
The assistant understands the request, replies with speech, sends a Webots command,
the robot moves toward the cane, and the cane is moved into a handoff position.
```

## Demo Roles

- Daniel: voice assistant, Webots robot behavior, MongoDB event pipeline.
- Leona: dashboard or data visualization using MongoDB collections.
- Clara: MongoDB health check and ingestion verification.
- PM/Scrum Master: project framing, sprint scope, and presentation flow.

## Pre-Demo Setup

Use the `dev` branch for active demo preparation:

```cmd
cd "C:\Users\danie\OneDrive\Documents\Project Managment Project Ifnal\Project Managment\swarmsense"
git checkout dev
git pull origin dev
```

Confirm local environment exists:

```cmd
.venv\Scripts\activate.bat
```

Confirm `.env` exists locally and contains:

```text
MONGODB_URI
MONGODB_DATABASE
OPENAI_API_KEY
OPENAI_MODEL
ELEVENLABS_API_KEY
ELEVENLABS_VOICE_ID
ELEVENLABS_MODEL_ID
ELEVENLABS_STT_MODEL_ID
```

Do not commit `.env` or any `.env.*` file.

## Webots Setup

Open:

```text
webots/worlds/humanoid_house_demo.wbt
```

Press reset/reload, then Play.

In the Webots console, confirm:

```text
humanoid_sensor_controller version: 2026-06-10-retrieval-handoff-v1
```

Expected idle behavior:

- The robot does not move before a fresh voice command.
- Webots emits monitoring/environment events.
- The robot waits for `data/raw/webots_command.json` to receive a new command.

## Voice Demo Command

From the project root:

```cmd
cd "C:\Users\danie\OneDrive\Documents\Project Managment Project Ifnal\Project Managment\swarmsense\ros2_ws\src\robot_assistant\robot_assistant"
python voice_assistant_runner.py --device 2 --duration 7 --insert --speak --play-audio --webots-command
```

If device `2` fails, list devices:

```cmd
python voice_assistant_runner.py --list-devices
```

Try laptop mic:

```cmd
python voice_assistant_runner.py --device 1 --duration 7 --insert --speak --play-audio --webots-command
```

Say:

```text
Can you help me find my cane?
```

Expected command output:

- Transcript appears.
- Intent is `find_cane`.
- Events are inserted into MongoDB Atlas.
- Robot speech MP3 is generated and played.
- `webots_command.json` is written.

Expected Webots behavior:

- Console prints `Accepted Webots command`.
- Robot moves toward the cane through the living room.
- Robot stops once it reaches the retrieval distance.
- Cane moves into a visible handoff position beside the humanoid.
- Console emits an `important_object_alert` with:

```text
status: retrieved_for_handoff
retrieval_state: handoff_ready
```

## MongoDB Verification

After the Webots movement demo, import recent Webots events:

```cmd
cd "C:\Users\danie\OneDrive\Documents\Project Managment Project Ifnal\Project Managment\swarmsense\ros2_ws\src\robot_assistant\robot_assistant"
python webots_event_importer.py --tail 150
```

Run health check:

```cmd
python mongo_health_check.py
```

Expected result:

```text
MongoDB connection: OK
Required field check: OK
```

Expected active collections:

- `conversation_events`
- `robot_status`
- `environment_events`
- `alerts`

## Presentation Story

Use this simple story:

1. The user speaks a request: "Can you help me find my cane?"
2. The assistant turns voice into text.
3. The LLM classifies the intent as `find_cane`.
4. The assistant replies with speech.
5. The system stores structured events in MongoDB.
6. The robot receives a Webots command.
7. Webots simulates robot movement and object retrieval.
8. Webots emits telemetry and safety/retrieval events.
9. MongoDB becomes the shared source for dashboard, health checks, and future Kafka integration.

## Fallback Plan

If microphone recording fails:

```cmd
python nlp_event_runner.py --text "Can you help me find my cane?" --insert --speak --play-audio --webots-command
```

If ElevenLabs speech-to-text fails:

- Use typed input fallback above.
- Explain that the voice path worked during testing but the typed path uses the same event and Webots command pipeline.

If Webots movement fails:

- Show `webots_command.json`.
- Show MongoDB health check.
- Show Webots console sensor events.
- Explain that the controller consumes commands through the local command bridge and emits robot telemetry.

If MongoDB fails:

- Show local JSONL files in `data/raw`.
- Explain that the system stores the same schema locally and imports to MongoDB when Atlas is reachable.

## Demo Success Criteria

Minimum successful demo:

- Voice or typed request is classified.
- Assistant response is spoken or printed.
- MongoDB receives events.
- Webots receives command.
- Robot moves or Webots telemetry confirms command processing.

Strong successful demo:

- Voice request works.
- Robot moves toward cane.
- Cane moves into handoff position.
- MongoDB health check confirms new records.
- Leona can show dashboard data from MongoDB.

