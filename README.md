# NESTO Care — Humanoid Elderly-Care Assistant

NESTO Care is a modular, end-to-end robotic elderly-care assistant demo. A user
(or a care provider) speaks to or clicks the assistant; the system understands
the request, drives a simulated NAO humanoid in Webots to act on it (find a cane,
fetch medicine, respond to mood), records every step as structured telemetry in
MongoDB Atlas, and surfaces it all on a live web UI with a real-time **Admin KPI
dashboard**.

It is a full vertical slice: **voice + vision + emotion perception → intent →
robot action → telemetry → live dashboards**, with end-to-end latency measured
across every hop of the pipeline.

---

## 1. Architecture at a glance

```text
                         ┌─────────────────────────────────────────────┐
                         │                 USER                        │
                         │  voice (mic) · webcam · web UI clicks        │
                         └───────────────┬─────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                 │
   VOICE LAYER                     PERCEPTION LAYER                    WEB LAYER
   ElevenLabs STT/TTS              YOLO (objects)                     Next.js UI (3000)
        │                          DeepFace (emotion)                 FastAPI API (8000)
        │                          ChromaDB (object memory)                │
        └──────────────┬───────────────┴───────────────┬──────────────────┘
                       │                                │
                  NLP LAYER (OpenAI)              DASHBOARD COMMAND BRIDGE
                  intent + response               UI/scenario → robot command
                       │                          mood check  → DeepFace loop
                       └───────────────┬──────────────────┘
                                       │
                              data/raw/webots_command.json
                                       │
                              WEBOTS SIMULATION (NAO supervisor)
                              navigation, retrieval, handoff
                                       │
                              webots_humanoid_events.jsonl
                                       │
                              TELEMETRY STREAMER (importer --follow)
                                       │
                              MongoDB Atlas  (humanoid_assistant)
                                       │
        ┌──────────────────────────────┴───────────────────────────────┐
        │                                                               │
   Admin KPI Dashboard (/admin)                          Streamlit provider dashboard
   live, 30s auto-refresh, 7-stage latency               (teammates' nesto-dashboard)
```

---

## 2. The stack, layer by layer

| Layer | Tech | Module(s) | What it does |
|---|---|---|---|
| **Voice** | ElevenLabs STT + TTS | `elevenlabs_voice.py`, `voice_assistant_runner.py` | Press-to-talk: records mic audio, transcribes speech to text, and speaks the assistant's reply. |
| **NLP / intent** | OpenAI | `nlp_event_runner.py` | Classifies the user message into an intent (`find_cane`, `find_medicine`, `summon`, `call_caregiver`, mood check-in…) with confidence + risk, and generates the spoken response. Emits schema-valid events. |
| **Object vision** | YOLO (Ultralytics, `yolov8n`) | `vision_yolo.py` | Detects objects in a scene image / webcam frame and turns them into `object_detected` / `scene_described` events. |
| **Emotion** | DeepFace (OpenCV backend) | `emotion_deepface.py`, `emotion_stream_monitor.py`, `webcam_capture.py` | Facial emotion recognition from a webcam snapshot → `mood_detected`, `wellbeing_score_updated`, `negative_mood_alert`. Flags negative emotions (sad/fear/angry/disgust). |
| **Memory** | ChromaDB (vector store) | `memory_chromadb.py` | Remembers where objects were last seen (e.g. `medicine_box → living room`) so the assistant can recall them on request. |
| **Bridge** | Python poller | `dashboard_command_bridge.py` | The glue: turns UI/scenario events in MongoDB into real robot commands (`webots_command.json`) and turns mood check-ins into a real DeepFace perception run written back to MongoDB. |
| **Simulation** | Webots R2025a (NAO) | `webots/` + `nao_assistant_supervisor.py`, `nao_motion_bridge.py` | Drives the humanoid: heading-aware navigation, obstacle handling, fall recovery, target retrieval and handoff. Emits robot status + telemetry. |
| **Telemetry streamer** | Python tailer | `webots_event_importer.py --follow` | Continuously streams new Webots events into MongoDB Atlas (byte-offset tracked, no duplicates) and stamps `mongodb_logged_at` / `dashboard_updated_at` so the dashboards stay live. |
| **Datastore** | MongoDB Atlas | `mongo_client.py` | Single source of truth (`humanoid_assistant` db). Every insert is schema-validated and timing-stamped. |
| **Web API** | FastAPI | `web/backend/` | Auth (JWT, roles), patient portal endpoints, and the read-only `GET /api/admin/kpis` admin dashboard route. |
| **Web UI** | Next.js 16 + React 19 + Tailwind v4 | `web/frontend/` | Patient portal (`/`) and the live Admin KPI dashboard (`/admin`, 30s auto-refresh). |
| **KPI analysis** | Python (read-only) | `analytics/mongo_kpi_analysis.py` | Computes the seven pipeline latency segments and health KPIs from real timestamp coverage — real values or "Unavailable", never invented. |

---

## 3. End-to-end telemetry & latency

Every dashboard action is traced through seven epoch-millisecond timestamps,
stored both top-level and mirrored into `payload` (per `docs/telemetry_schema_v1.md`):

```text
ui_triggered_at          UI click / dashboard action
backend_received_at      FastAPI receipt
bridge_received_at       dashboard_command_bridge picked up the request
robot_action_started_at  Webots accepted & started the command
robot_action_completed_at Webots marked the action complete / handoff ready
mongodb_logged_at        document inserted into MongoDB Atlas
dashboard_updated_at     admin/provider telemetry refreshed
```

The Admin KPI dashboard derives seven latency segments from these (UI→Backend,
Backend→Bridge, Bridge→Robot Start, **Robot Action Duration**, **Robot→MongoDB
(write latency)**, MongoDB→Dashboard, and End-to-End). A segment only shows a
number when both of its timestamps exist and parse on the same document —
otherwise it honestly reads "Unavailable".

> **Command → MongoDB write time** is exactly the *Robot → MongoDB* segment
> (`mongodb_logged_at − robot_action_completed_at`). It populates when the
> telemetry streamer ingests a robot-completion document, which is why you run
> `run_telemetry_streamer.cmd` during a live retrieval.

---

## 4. Running the full demo

Prereqs: the `.env` file at the repo root with Atlas + API keys (see §6), the
web venv (`.venv-web`), the perception venv (`.venv-perception311`), the main
venv (`.venv`), and Webots installed.

Open the world `webots/worlds/humanoid_house_demo.wbt` in Webots and press Play.
**Quickest web start (one command):** `tools\run_web.cmd` launches BOTH the
API (:8000) and the UI (:3000), each in its own window. Use this for the web
app; run the bridge / Webots / telemetry streamer separately as below.

Then open these terminals (each is one long-running process):

```bat
:: 1) Bridge — turns UI clicks / scenarios into robot commands + runs the mood loop
tools\run_dashboard_bridge.cmd

:: 2) Telemetry streamer — streams Webots events into Atlas live (keeps dashboards fresh)
::    Add --skip-types to cut idle perception noise:
tools\run_telemetry_streamer.cmd --skip-types object_detected,object_distance_estimated,scene_described

:: 3) Web API (FastAPI, port 8000)
tools\run_web_backend.cmd

:: 4) Web UI (Next.js, port 3000)
tools\run_web_frontend.cmd
```

Open the apps:

- **Patient portal:** http://localhost:3000
- **Admin KPI dashboard:** http://localhost:3000/admin  (sign in as an `admin_provider`)
- **API health:** http://127.0.0.1:8000/api/health

### Demo logins

Sign in at `/login`. The admin KPI dashboard requires the `admin_provider`
account.

| Role | Email | Password | Lands on |
|---|---|---|---|
| Admin / care team | `admintest@gmail.com` | `test1234` | `/admin` (KPI dashboard) |
| Patient (elderly user) | `maria@example.com` | `NestoCare2026!` | `/patient` |
| Guardian / caregiver | `anna@example.com` | `NestoCare2026!` | guardian view |
| Guardian / caregiver | `daniel@example.com` | `NestoCare2026!` | guardian view |

Seed password is `NestoCare2026!` unless overridden via the `NESTO_SEED_PASSWORD`
env var (the admin account is pinned to `test1234`). Any accounts you register
yourself also work.

> **Multiple pages at once:** the auth token is stored per-browser in
> localStorage, so logging in as a second role in the same browser replaces the
> first session. To show patient + guardian + admin simultaneously, use separate
> browsers / incognito windows (or the phone via ngrok for one of them).

Optional, for the voice + perception experience:

```bat
:: Push-to-talk voice with webcam scene/face capture, speaks the reply, drives Webots
tools\run_voice_with_perception.cmd --device 1 --duration 7 --insert --speak --play-audio --webots-command

:: Live facial-emotion monitor (standalone DeepFace loop)
tools\run_live_emotion_monitor.cmd
```

Optional, the teammates' Streamlit provider dashboard:

```bat
tools\run_dashboard.cmd
```

**Demo flow:** click *Find My Cane* / *Find My Medicine* (or say it) in the UI →
the bridge writes the Webots command → the NAO navigates and performs the handoff
→ the streamer pushes the events to Atlas → the Admin KPI dashboard's cards and
latency segments update within ~30s.

---

## 5. Individual component commands

```bat
:: Classify typed input with OpenAI and insert events
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "Can you help me find my cane?" --insert

:: Same, but no API call (mock) — useful offline
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "I feel lonely today" --mock --insert

:: With ChromaDB memory, YOLO scene, and DeepFace emotion together
python ros2_ws\src\robot_assistant\robot_assistant\nlp_event_runner.py --text "Can you help me find my cane?" --use-memory --scene-image data\raw\webots_scene.png --face-image data\raw\user_face.jpg --insert

:: Push-to-talk voice → speech → Webots command
python ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py --insert --speak --play-audio --webots-command

:: One-shot import of Webots events (vs. the --follow streamer)
python ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py --tail 150

:: MongoDB health check
python ros2_ws\src\robot_assistant\robot_assistant\mongo_health_check.py

:: Backup + reset demo collections for a clean run
python ros2_ws\src\robot_assistant\robot_assistant\demo_reset.py
python ros2_ws\src\robot_assistant\robot_assistant\demo_reset.py --backup-only

:: Read-only KPI analysis snapshot
python analytics\mongo_kpi_analysis.py
```

---

## 6. Environments & setup

Three Python environments keep heavy perception deps isolated from the web/API:

- **`.venv`** — main demo (Streamlit, pymongo, dnspython, OpenAI, ElevenLabs).
- **`.venv-web`** — FastAPI backend (`web/backend/requirements.txt`).
- **`.venv-perception311`** — Python 3.11/3.12 for YOLO + DeepFace + ChromaDB + OpenCV.

```bat
:: Main env
.\.venv\Scripts\activate.bat
pip install -r requirements.txt -r requirements-mongodb.txt -r requirements-openai.txt -r requirements-voice.txt

:: Perception env (Python 3.11/3.12)
powershell -ExecutionPolicy Bypass -File .\tools\rebuild_perception_env.ps1
python tools\perception_import_check.py
```

`.env` (repo root, never committed) must contain:

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

Notes:
- The Next.js frontend uses `NODE_OPTIONS=--use-system-ca` so Node trusts the
  machine certificate store behind a TLS-inspecting proxy.
- `YOLO_CONFIG_DIR` can point at `data/processed/ultralytics` to keep Ultralytics
  cache inside the repo.
- The core voice/robot/telemetry demo runs even without the perception stack.

---

## 7. Remote access for the demo (optional, ngrok)

To show the patient portal on a phone while the Admin dashboard runs on the
laptop — without building a separate mobile app — tunnel the running port:

```bat
:: after installing ngrok and adding your authtoken
ngrok http 3000
```

ngrok prints a public `https://…` URL that maps to `localhost:3000`; open it on
the phone. (Tunnel `8000` instead if you need the API reachable remotely.) This
serves the exact same web app, no iOS build required.

---

## 8. Project structure

```text
swarmsense/
  web/
    backend/        FastAPI API: auth, patient portal, /api/admin/kpis
    frontend/       Next.js UI: patient portal (/) + Admin KPI dashboard (/admin)
  ros2_ws/src/robot_assistant/robot_assistant/
    voice_assistant_runner.py   elevenlabs_voice.py     (voice layer)
    nlp_event_runner.py                                 (OpenAI intent)
    vision_yolo.py  emotion_deepface.py  memory_chromadb.py  (perception)
    dashboard_command_bridge.py                         (UI → robot bridge)
    webots_event_importer.py                            (telemetry streamer)
    mongo_client.py  event_schema.py  mongo_health_check.py  demo_reset.py
  webots/           NAO world + supervisor / motion controllers
  nesto-dashboard/  Streamlit provider dashboard + shared data_layer
  analytics/        read-only MongoDB KPI analysis
  local_kpi_ui_foundation/  original Admin KPI UI kit (now wired into web/)
  tools/            run_*.cmd launchers + env builders
  docs/             telemetry schema, demo runbook, architecture/planning
```

See [docs/demo/saturday_demo_runbook.md](docs/demo/saturday_demo_runbook.md) for
the step-by-step demo script and fallback plan.
