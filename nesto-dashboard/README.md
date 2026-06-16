# NESTO Care Dashboard

Streamlit dashboard for the university humanoid elderly-assistant project. This
app is the landing page, profile setup flow, elderly interface, guardian /
caregiver dashboard, and admin/provider view for NESTO Care.

## Architecture Source Of Truth

```text
Webots / Robot events -> MongoDB
Dashboard UI actions -> MongoDB
MongoDB new records -> Python Kafka bridge -> Kafka topics
Kafka topics -> Dashboard consumer/listener -> Redis cache
Dashboard UI -> Redis first, MongoDB fallback
Dashboard <-> ChromaDB <-> Webots
```

MongoDB Atlas is the persistent event store. Redis is the speed layer for
repeated dashboard reads. ChromaDB stores profile/preferences and semantic
memory. Kafka is the runtime streaming layer when `KAFKA_ENABLED=true` and a
broker is running locally.

ChromaDB is the personalization/object-memory lane:

```text
Dashboard -> ChromaDB -> Webots
Webots -> ChromaDB -> Dashboard
```

It stores preferred name, robot name, Guardian / Caregiver contact, medicine
routine, care preferences, important objects such as cane/medicine box, and
robot/location mapping memory. Normal users see friendly care language; Admin
and proof scripts show the technical ChromaDB status.

## What Produces Data And What Listens?

There are two data producers.

Daniel/Webots produces robot and scenario events into MongoDB Atlas. Daniel's
backend can keep writing robot status, room/environment readings, object
detection, cane/medicine-box detection, robot responses, scenario events,
medicine events, mood events, and alerts into the `humanoid_assistant`
database.

Leona/Dashboard also produces user-action events into MongoDB Atlas when users
click buttons. These writes go through `db_queries.py` wrappers:

- Today's Schedule / View Schedule -> `schedule_events`
- Take Medication / Mark as taken -> `medicine_events`
- Talk to Nesto -> `conversation_events`
- Find My Cane -> `scenario_events`
- Find My Medicine -> `scenario_events`
- Call Caregiver -> `scenario_events`
- Mood Check -> `mood_events`
- Emergency -> `alerts`
- Save Caregiver Note -> `caregiver_notes`
- Save Profile -> `user_profiles` plus ChromaDB profile memory

The dashboard listener/consumer is the Streamlit dashboard reading MongoDB
through `db_queries.py` and `data_layer.py`. Redis is only the speed/cache layer
for repeated dashboard reads. If Redis is unavailable, the dashboard continues
using local TTL fallback/direct MongoDB reads.

ChromaDB stores profile/preferences/object memory through `memory_store.py`.
The profile form saves profile memory, and object memory can store locations
such as cane, medicine box, or robot location. The elderly "Find My Cane" and
"Find My Medicine" flows read ChromaDB object memory first, then fall back to
current robot room/status data.

Kafka topics and producer/listener mappings are implemented in
`kafka_bridge_plan.py`. If Kafka is not running, MongoDB reads/writes still
work, but `proof_connections.py --kafka-proof` fails honestly until the broker
starts.

## Kafka + Redis Runtime Flow

Runtime flow:

```text
MongoDB stores events.
A Python bridge watches/polls MongoDB for new events.
The bridge publishes new events to Kafka topics.
The dashboard Kafka consumer listens to topics.
The consumer updates Redis cache.
The consumer also updates ChromaDB for profile/object/robot-location memory
when events include those fields.
Dashboard reads Redis first and MongoDB fallback.
```

Local startup:

```powershell
docker compose -f docker-compose.kafka.yml up -d
```

Required environment:

```text
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=nesto-dashboard
KAFKA_CONSUMER_GROUP=nesto-dashboard-consumer
KAFKA_POLL_SECONDS=5
REDIS_URL=redis://localhost:6379/0
```

Run the MongoDB -> Kafka bridge:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" run_kafka_bridge.py
```

Run the Kafka -> Redis dashboard consumer:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" run_kafka_consumer.py
```

Run the Kafka proof:

```powershell
$env:KAFKA_ENABLED="true"
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" proof_connections.py --kafka-proof
```

Run the ChromaDB profile/object memory proof:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" test_chromadb_memory.py
```

Expected success:

```text
KAFKA BROKER: connected
KAFKA TOPICS: ready
KAFKA PRODUCER: passed
KAFKA CONSUMER: passed
REDIS CACHE UPDATE: passed
KAFKA PROOF PASSED
```

If Kafka is not running:

```text
KAFKA BROKER: not connected
KAFKA PROOF FAILED
Start Kafka using: docker compose -f docker-compose.kafka.yml up -d
```

Redis keys updated by the consumer include:

```text
robot_status:latest
alerts:latest
scenario_events:latest
medicine_events:latest
mood_events:latest
conversation_events:latest
environment_events:latest
schedule_events:latest
dashboard:admin:summary
dashboard:elderly:{user_id}:summary
dashboard:guardian:{guardian_id}:summary
```

Update timing expectations:

- Faster / near real-time: alerts, robot health/status, wellbeing, emergency actions, critical sensor issues.
- Timed / sliding window: steps/activity, environment events, conversation counts, general KPIs.
- Queue / scheduled logic: medicine reminder due, wait for taken confirmation, then create/publish a missed event if not confirmed within the grace window.

## How To Prove The Backend Works

Run these from the project folder. On this Windows setup, replace `python` with
the bundled runtime path if needed:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m py_compile *.py
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" proof_connections.py
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" proof_connections.py --write-proof
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" proof_connections.py --kafka-proof
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" test_mongodb.py
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" test_chromadb_memory.py
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" seed_admin_user.py
```

What each command proves:

- `python -m py_compile *.py`: Python syntax/import-readiness for the repo.
- `python proof_connections.py`: MongoDB Atlas connection, database name,
  collection counts, latest records, Redis/cache status, ChromaDB status,
  Kafka readiness, Daniel compatibility, and dashboard write-wrapper mapping.
- `python proof_connections.py --write-proof`: inserts and reads back harmless
  proof events in `scenario_events`, `medicine_events`, `mood_events`,
  `alerts`, and `conversation_events`.
- `python proof_connections.py --kafka-proof`: checks Kafka broker, topics,
  producer, consumer, and Redis/latest cache update.
- `python test_mongodb.py`: direct MongoDB connection check.
- `python test_chromadb_memory.py`: profile memory save/read and object memory
  save/read proof, or honest unavailable/fallback status.
- `python seed_admin_user.py`: creates/updates the provider admin account
  needed for Admin / Provider dashboard login.

Admin/System Health also shows the same handoff proof in the dashboard:
MongoDB Atlas, database name, collection counts, Redis/local TTL fallback,
ChromaDB, Kafka status, Kafka topic readiness, Daniel Backend Data Source, and
the Producer / Consumer Matrix.

GitHub handoff branch:

```text
nesto-dataflow-proof
```

## MongoDB Atlas

Expected database:

```text
humanoid_assistant
```

Supported environment variable names:

```text
MONGO_URI=your_atlas_connection_string
MONGO_DB_NAME=humanoid_assistant
```

Daniel compatibility aliases are also supported:

```text
MONGODB_URI=your_atlas_connection_string
MONGODB_DATABASE=humanoid_assistant
```

Never commit `.env` or any secret connection string.

## Collections

Core collections used by the dashboard:

- `alerts`
- `auth_users`
- `conversation_events`
- `environment_events`
- `medicine_events`
- `mood_events`
- `robot_status`
- `schedule_events`
- `scenario_events`
- `user_profiles`

Optional dashboard collections:

- `caregiver_notes`
- `support_tickets`
- `dashboard_kpis`
- `care_plans`

Daniel's Webots backend writes the standard event shape:

```text
event_id, event_type, timestamp, source, user_id, robot_id, payload
```

The event-to-collection and Kafka-topic contract lives in
`event_contracts.py`.

## Five Required Pages

1. Landing Page
2. User Creation + Preferences Page
3. Elderly User Interface
4. Guardian / Caregiver Dashboard
5. Admin / Provider / NESTO Team Dashboard

## Approved NESTO Theme

The app uses one shared NESTO Care visual system from `ui_theme.py`:
warm cream background, soft warm-white cards, dark green text, sage/mint
accents, subtle borders, rounded controls, and the reusable NESTO brand
pattern. The sign-in screen, Guardian / Caregiver dashboard, and Admin /
Provider operations dashboard should stay on this same theme.

Role routing is account-based:

- Elderly user accounts open the Elderly User Interface.
- Guardian / Caregiver accounts open their linked loved one's dashboard.
- Admin / Provider accounts open Nesto Care Operations.

The UI should not use demo-role wording. If a backend service is unavailable,
the app should show a polished fallback state while preserving the real
MongoDB-first data flow.

## File Purpose Map

- `app.py`: Streamlit launcher, login/session routing, and page selection.
- `ui_theme.py`: reusable NESTO visual system, cards, badges, pattern, and layout CSS.
- `data_layer.py`: friendly app-facing data helpers over MongoDB/cache/memory.
- `db_queries.py`: MongoDB Atlas query helpers and dashboard event insert wrappers.
- `cache_layer.py`: Redis-compatible cache with local TTL fallback.
- `memory_store.py`: ChromaDB memory helpers, including profile memory saving.
- `event_contracts.py`: source-of-truth architecture, collections, event routes, and Kafka topics.
- `kafka_bridge_plan.py`: Kafka broker/topic checks, MongoDB polling producer bridge, Kafka consumer, and Redis cache updater.
- `page_overview.py`: landing/product overview page.
- `page_family.py`: elderly interface and guardian/caregiver dashboard.
- `page_enterprise.py`: admin/provider dashboard and system health proof UI.
- `profile_preferences.py`: user creation, guardian/caregiver contact, consent, and profile memory.
- `auth_store.py`: database-backed login and password hashing helpers.
- `proof_connections.py`: terminal proof for MongoDB, Redis/cache, ChromaDB, Kafka readiness, and Daniel compatibility.
- `peek_db.py`: quick database inspection helper.
- `test_mongodb.py`: MongoDB connection check.
- `test_chromadb_memory.py`: ChromaDB memory check.

## Daniel Backend Alignment

Reference backend:

```text
https://github.com/DanielMViteri/humanoid-assistant-webots
```

Observed Daniel scenarios:

- `find_cane_demo_01` -> scenario/find-cane dashboard events.
- `medicine_reminder_demo_01` -> medicine reminder dashboard events.
- `wellbeing_checkin_demo_01` -> mood/wellbeing dashboard events.

Observed Daniel event routes include `robot_status_updated`,
`object_detected`, `room_detected`, `medicine_taken`,
`medicine_missed`, `mood_detected`, `wellbeing_score_updated`,
`safety_alert`, `user_message`, `robot_response`, and
`robot_command_sent`.

## Dashboard Event Actions

Dashboard buttons write through explicit wrappers in `db_queries.py`:

- `create_scenario_event`
- `create_medicine_event`
- `create_mood_event`
- `create_alert_event`
- `create_caregiver_note_event`
- `create_profile_updated_event`

These wrappers preserve the MongoDB-first dataflow and invalidate dashboard
cache after writes where the app uses `data_layer.record_dashboard_event`.

## Run In PowerShell

From the project folder:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit run app.py --server.port 8516 --server.address 127.0.0.1 --server.fileWatcherType none
```

Open:

```text
http://127.0.0.1:8516
```

For CMD, do not use the PowerShell `&` operator. Use:

```cmd
"C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit run app.py --server.port 8516 --server.address 127.0.0.1 --server.fileWatcherType none
```

## Proof Commands

Compile-check:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m py_compile app.py ui_theme.py data_layer.py db_queries.py cache_layer.py memory_store.py event_contracts.py kafka_bridge_plan.py page_overview.py page_family.py page_enterprise.py profile_preferences.py proof_connections.py peek_db.py test_mongodb.py test_chromadb_memory.py
```

Connection proof:

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" proof_connections.py
```

## Current Status

- MongoDB Atlas: connected when `MONGO_URI`/`MONGODB_URI` is configured.
- Redis: optional; app falls back to local TTL cache if Redis is unavailable.
- ChromaDB: local persistent memory in `chroma_memory/` when installed.
- Kafka: local broker support, producer bridge, consumer/listener, and `--kafka-proof` are implemented; proof passes when Kafka is running.
- Daniel backend: event schema and route compatibility are documented in code and proof output.
