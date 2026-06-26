"""
Friendly dashboard data layer over MongoDB, Redis/cache, ChromaDB, and Kafka readiness.
"""

import datetime as dt
import os
import time
from typing import Any


COLLECTIONS = [
    "alerts",
    "conversation_events",
    "environment_events",
    "medicine_events",
    "mood_events",
    "robot_status",
    "schedule_events",
    "scenario_events",
    "user_profiles",
]

_PROFILE_CACHE = {"expires": 0.0, "value": None}


def _db():
    import db_queries

    return db_queries


def safe_counts():
    def _load():
        try:
            return _db().get_collection_counts()
        except Exception:
            return {name: 0 for name in COLLECTIONS}

    try:
        import cache_layer

        return cache_layer.get_or_set("nesto:mongo:collection_counts", _load, ttl_seconds=5)
    except Exception:
        return _load()


def _display_from_id(value, fallback):
    text = str(value or "").strip()
    if not text:
        return fallback
    cleaned = text.replace("_", " ").replace("-", " ").title()
    return cleaned if cleaned else fallback


def _profile_from_chromadb(user_id: str = "elderly_user_01") -> dict[str, Any]:
    try:
        import memory_store

        result = memory_store.read_profile_memory(user_id)
        memory = result.get("memory") if isinstance(result, dict) else {}
        metadata = memory.get("metadata") if isinstance(memory, dict) else {}
        if not isinstance(metadata, dict):
            return {}
        return {
            "patient_name": metadata.get("preferred_name"),
            "caregiver_name": metadata.get("guardian_name"),
            "assistant_name": metadata.get("robot_name"),
            "patient_id": metadata.get("user_id") or user_id,
            "caregiver_id": metadata.get("guardian_id") or "",
            "robot_id": metadata.get("robot_id") or "",
        }
    except Exception:
        return {}


def care_profile():
    """
    App-facing profile.

    MongoDB remains the source of truth for live records. If the technical event
    pipeline adds profile names later, the UI uses them automatically. Until
    then, the app shows neutral labels derived from live IDs instead of
    scattering fixed sample names through the pages.
    """
    now = time.time()
    if _PROFILE_CACHE["value"] is not None and now < _PROFILE_CACHE["expires"]:
        return dict(_PROFILE_CACHE["value"])

    profile = {}
    try:
        if hasattr(_db(), "get_care_profile"):
            profile = _db().get_care_profile() or {}
    except Exception:
        profile = {}

    memory_profile = _profile_from_chromadb(str(profile.get("patient_id") or "elderly_user_01"))
    for key, value in memory_profile.items():
        if value and not profile.get(key):
            profile[key] = value

    patient_id = profile.get("patient_id")
    caregiver_id = profile.get("caregiver_id")
    robot_id = profile.get("robot_id")

    patient_name = (
        profile.get("patient_name")
        or os.getenv("CARE_PATIENT_NAME")
        or _display_from_id(patient_id, "Elderly user")
    )
    caregiver_name = (
        profile.get("caregiver_name")
        or os.getenv("CARE_CAREGIVER_NAME")
        or _display_from_id(caregiver_id, "Caregiver")
    )
    assistant_name = (
        profile.get("assistant_name")
        or os.getenv("CARE_ASSISTANT_NAME")
        or "Nesto"
    )

    resolved = {
        "patient_name": patient_name,
        "caregiver_name": caregiver_name,
        "assistant_name": assistant_name,
        "patient_id": patient_id or "",
        "caregiver_id": caregiver_id or "",
        "robot_id": robot_id or "",
    }
    _PROFILE_CACHE["value"] = dict(resolved)
    _PROFILE_CACHE["expires"] = now + 15
    return resolved


def patient():
    return care_profile()["patient_name"]


def caregiver():
    return care_profile()["caregiver_name"]


def assistant_name():
    return care_profile()["assistant_name"]


def care_metrics():
    counts = safe_counts()
    try:
        import cache_layer

        mood_event = cache_layer.get_latest_event("mood_events") or {}
        medicine_event = cache_layer.get_latest_event("medicine_events") or {}
        mood_payload = mood_event.get("payload") if isinstance(mood_event, dict) else {}
        med_payload = medicine_event.get("payload") if isinstance(medicine_event, dict) else {}
        cached_mood = (mood_payload or {}).get("mood") or (mood_payload or {}).get("summary")
        cached_score = (mood_payload or {}).get("wellbeing_score") or (mood_payload or {}).get("score")
        cached_medicine = (med_payload or {}).get("medicine_status") or (med_payload or {}).get("status")
    except Exception:
        cached_mood = cached_score = cached_medicine = None
    try:
        db = _db()
        mood = cached_mood or db.get_mood() or "Good"
        score = cached_score or db.get_wellbeing_score() or 82
        medicine = cached_medicine or db.get_medication() or "94%"
    except Exception:
        mood = "Good"
        score = 82
        medicine = "94%"
    return {
        "score": score,
        "mood": str(mood).replace("_", " ").title(),
        "medicine": str(medicine).replace("_", " ").title(),
        "activity": "3,120",
        "sleep": "7.2 h",
        "robot_updates": counts.get("robot_status", 0),
        "assistant_messages": counts.get("conversation_events", 0),
        "room_events": counts.get("environment_events", 0),
        "alerts": counts.get("alerts", 0),
        "medicine_events": counts.get("medicine_events", 0),
        "wellbeing_notes": counts.get("mood_events", 0),
    }


def robot_status(use_live=True):
    if not use_live:
        return {
            "online": True,
            "status": "Active",
            "battery": 96.4,
            "room": "Living Room",
            "navigation": "Stationary",
            "alerts": 0,
            "updated": dt.datetime.now().strftime("%H:%M:%S"),
        }
    try:
        import cache_layer

        cached = cache_layer.get_latest_event("robot_status")
        payload = cached.get("payload") if isinstance(cached, dict) else {}
        if isinstance(payload, dict) and payload:
            return {
                "online": True,
                "status": str(payload.get("status") or cached.get("status") or "Active").replace("_", " ").title(),
                "battery": payload.get("battery_pct") or payload.get("battery") or 96.4,
                "room": str(payload.get("current_room") or payload.get("room") or "Living Room").replace("_", " ").title(),
                "navigation": str(payload.get("navigation_state") or "Stationary").replace("_", " ").title(),
                "alerts": len(_db().get_alerts()) if hasattr(_db(), "get_alerts") else 0,
                "updated": dt.datetime.now().strftime("%H:%M:%S"),
                "source": "redis_latest",
            }
    except Exception:
        pass
    try:
        db = _db()
        alerts = db.get_alerts()
        return {
            "online": True,
            "status": (db.get_status() or "Active").replace("_", " ").title(),
            "battery": db.get_battery() or 96.4,
            "room": (db.get_location() or "Living Room").replace("_", " ").title(),
            "navigation": (db.get_navigation_state() or "Stationary").replace("_", " ").title(),
            "alerts": len(alerts),
            "updated": dt.datetime.now().strftime("%H:%M:%S"),
        }
    except Exception:
        return robot_status(use_live=False)


def _friendly_event(event_type):
    labels = {
        "Robot Command Sent": "Robot command sent",
        "Robot Status Updated": "Robot update",
        "User Message": "User request",
        "Robot Response": "Assistant response",
        "Session Started": "Care session started",
        "Session Ended": "Care session ended",
        "Room Detected": "Room identified",
        "Object Detected": "Object found",
        "Object Distance Estimated": "Distance estimated",
        "Scene Described": "Room described",
        "Important Object Alert": "Important object alert",
        "Safety Alert": "Safety alert",
        "Mood Detected": "Mood noted",
        "Medicine Reminder Due": "Medicine reminder due",
        "Medicine Taken": "Medicine marked taken",
        "Medicine Missed": "Medicine marked missed",
    }
    return labels.get(event_type, event_type)


def _friendly_source(source):
    labels = {
        "robot_status": "Robot updates",
        "conversation_events": "Assistant messages",
        "environment_events": "Room and object events",
        "alerts": "Care alerts",
        "medicine_events": "Medication reminders",
        "mood_events": "Wellbeing notes",
    }
    return labels.get(source, "Care records")


def _friendly_scenario(scenario):
    text = str(scenario or "")
    if "find_cane" in text or text == "cane":
        return "Object finder"
    if "medicine" in text:
        return "Medication reminder"
    if "wellbeing" in text or "mood" in text:
        return "Wellbeing check-in"
    if "safety" in text or "fall" in text:
        return "Safety check"
    return "Care activity"


def _friendly_description(text):
    raw = str(text or "")
    replacements = {
        "active": "Nesto is active for the current task.",
        "cane": "Nesto is looking for the cane.",
        "Session Started": "A care support session started.",
        "Object Detected": "Nesto found a relevant object.",
        "Object Distance Estimated": "Nesto estimated the object's distance.",
        "Room Detected": "Nesto identified the room.",
    }
    return replacements.get(raw, raw)


def recent_activity(limit=8):
    try:
        import cache_layer

        cached_rows = []
        for collection in ("scenario_events", "conversation_events", "environment_events", "medicine_events", "mood_events", "alerts", "schedule_events"):
            event = cache_layer.get_latest_event(collection)
            if isinstance(event, dict) and event:
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                cached_rows.append({
                    "time": dt.datetime.now().strftime("%H:%M"),
                    "title": _friendly_event(str(event.get("event_type", collection)).replace("_", " ").title()),
                    "source": _friendly_source(collection),
                    "scenario": _friendly_scenario(event.get("scenario_type") or payload.get("scenario_type")),
                    "description": _friendly_description(payload.get("message") or payload.get("text") or event.get("status") or "Cached Kafka update"),
                })
        if cached_rows:
            return cached_rows[:limit]
    except Exception:
        pass

    def _load_events():
        try:
            return _db().get_scenario_events(limit=limit)
        except Exception:
            return []

    try:
        import cache_layer

        events = cache_layer.get_or_set(f"nesto:mongo:scenario_events:{limit}", _load_events, ttl_seconds=5)
    except Exception:
        events = _load_events()
    rows = []
    for event in events:
        rows.append(
            {
                "time": event["time"],
                "title": _friendly_event(event["event_type"]),
                "source": _friendly_source(event["collection"]),
                "scenario": _friendly_scenario(event["scenario_id"]),
                "description": _friendly_description(event["description"]),
            }
        )
    return rows


def memories(limit=5, allowed_types=None):
    try:
        import memory_store

        if hasattr(memory_store, "get_latest_memories"):
            return memory_store.get_latest_memories(limit=limit, allowed_types=allowed_types)
        return memory_store.get_latest_scenario_memories(limit=limit)
    except Exception:
        return []


def system_health():
    counts = safe_counts()
    mongo_available = any(counts.get(name, 0) for name in COLLECTIONS)
    try:
        import memory_store

        chroma = memory_store.memory_status()
    except Exception:
        chroma = {"available": False, "count": 0}
    try:
        import cache_layer

        cache = cache_layer.cache_status()
    except Exception:
        cache = {"available": False, "mode": "not_configured"}
    return {
        "mongo": {"available": mongo_available, "counts": counts},
        "chroma": chroma,
        "cache": cache,
    }


def record_dashboard_event(event_type, scenario_type=None, role="dashboard", status="requested", source_page="", payload=None):
    try:
        import cache_layer
        import db_queries

        inserted_id = db_queries.insert_dashboard_event(
            event_type=event_type,
            scenario_type=scenario_type,
            role=role,
            status=status,
            source_page=source_page,
            payload=payload or {},
        )
        cache_layer.invalidate("nesto:")
        return inserted_id
    except Exception:
        return None


def save_memory(text, metadata):
    try:
        import memory_store

        return memory_store.save_memory(text, metadata=metadata)
    except Exception:
        return False


# ----------------------------------------------------------------------
# Admin / Provider data aggregation
# ----------------------------------------------------------------------

ADMIN_EVENT_COLLECTIONS = [
    "robot_status",
    "environment_events",
    "conversation_events",
    "schedule_events",
    "scenario_events",
    "medicine_events",
    "mood_events",
    "alerts",
]

TELEMETRY_TIMING_FIELDS = (
    "ui_triggered_at",
    "backend_received_at",
    "bridge_received_at",
    "robot_action_started_at",
    "robot_action_completed_at",
    "mongodb_logged_at",
    "dashboard_updated_at",
)

_ADMIN_MONGO_STATUS_CACHE = {"expires": 0.0, "value": None}


def _admin_payload(doc: dict[str, Any] | None) -> dict[str, Any]:
    payload = (doc or {}).get("payload") or {}
    return payload if isinstance(payload, dict) else {"value": payload}


def _admin_first(*values: Any, fallback: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return fallback


def _admin_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return fallback


def _admin_epoch_ms(value: Any) -> int | str:
    if value in (None, ""):
        return ""
    try:
        return int(float(value))
    except Exception:
        return str(value)


def _admin_time_text(value: Any) -> str:
    if not value:
        return ""
    try:
        number = int(float(value))
        if number > 10_000_000_000:
            number = int(number / 1000)
        return dt.datetime.fromtimestamp(number).strftime("%H:%M:%S")
    except Exception:
        text = str(value or "")
        if "T" in text:
            try:
                return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%H:%M:%S")
            except Exception:
                return text[:8]
        return text[:8]


def _admin_date_text(value: Any) -> str:
    if not value:
        return ""
    try:
        number = int(float(value))
        if number > 10_000_000_000:
            number = int(number / 1000)
        return dt.datetime.fromtimestamp(number).strftime("%d %b %Y")
    except Exception:
        text = str(value or "")
        if "T" in text:
            try:
                return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d %b %Y")
            except Exception:
                return text[:10]
        return text[:10]


def _admin_sort_key(doc: dict[str, Any]) -> Any:
    return doc.get("timestamp") or doc.get("updated_at") or doc.get("created_at") or doc.get("_id") or ""


def _admin_docs(collection: str, query: dict[str, Any] | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if not _admin_mongo_status().get("available"):
        return []
    try:
        db = _db()
        docs = list(db._db[collection].find(query or {}, sort=[("timestamp", -1), ("updated_at", -1), ("_id", -1)], limit=limit))
        return docs
    except Exception:
        return []


def _admin_mongo_status() -> dict[str, Any]:
    now = time.time()
    cached = _ADMIN_MONGO_STATUS_CACHE.get("value")
    if cached is not None and now < _ADMIN_MONGO_STATUS_CACHE.get("expires", 0.0):
        return dict(cached)
    try:
        status = _db().get_connection_status()
    except Exception as exc:
        status = {"available": False, "status": "unavailable", "database_name": "humanoid_assistant", "error": str(exc)}
    status = dict(status or {})
    status.setdefault("last_check", dt.datetime.now().isoformat(timespec="seconds"))
    _ADMIN_MONGO_STATUS_CACHE["value"] = dict(status)
    _ADMIN_MONGO_STATUS_CACHE["expires"] = now + 15
    return status


def _admin_cache_status() -> dict[str, Any]:
    try:
        import cache_layer

        status = cache_layer.cache_status()
    except Exception as exc:
        status = {"available": False, "mode": "not_configured", "error": str(exc)}
    status = dict(status or {})
    status.setdefault("last_check", dt.datetime.now().isoformat(timespec="seconds"))
    return status


def _admin_chroma_status() -> dict[str, Any]:
    try:
        import memory_store

        status = memory_store.memory_status()
    except Exception as exc:
        status = {"available": False, "count": 0, "error": str(exc)}
    status = dict(status or {})
    status.setdefault("last_check", dt.datetime.now().isoformat(timespec="seconds"))
    return status


def _admin_kafka_status() -> dict[str, Any]:
    try:
        import kafka_bridge_plan

        status = kafka_bridge_plan.kafka_status()
    except Exception as exc:
        status = {"status": "not_configured", "available": False, "error": str(exc)}
    status = dict(status or {})
    status.setdefault("status", "not_configured")
    status.setdefault("last_check", dt.datetime.now().isoformat(timespec="seconds"))
    return status


def admin_patients() -> list[dict[str, Any]]:
    guardian_lookup = {}
    for user in _admin_docs("auth_users", {"role": "guardian_caregiver"}, limit=100):
        for linked in user.get("linked_patients") or []:
            patient_id = str(linked.get("patient_id") or "")
            if patient_id and patient_id not in guardian_lookup:
                guardian_lookup[patient_id] = user

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    profile_docs = _admin_docs("user_profiles", limit=100)
    grouped: dict[str, dict[str, Any]] = {}
    for doc in profile_docs:
        payload = _admin_payload(doc)
        patient_id = _admin_first(payload.get("user_id"), doc.get("user_id"), fallback="elderly_user_01")
        current = grouped.get(patient_id)
        if current is None or str(_admin_sort_key(doc)) >= str(_admin_sort_key(current)):
            grouped[patient_id] = doc

    for doc in grouped.values():
        payload = _admin_payload(doc)
        guardian = payload.get("guardian_contact") if isinstance(payload.get("guardian_contact"), dict) else {}
        preferences = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else {}
        medicine = payload.get("medicine_routine") or payload.get("medicine_schedule") or []
        consent = payload.get("consent") if isinstance(payload.get("consent"), dict) else {}
        patient_id = _admin_first(payload.get("user_id"), doc.get("user_id"), fallback=f"patient_{len(rows) + 1:02d}")
        linked_guardian = guardian_lookup.get(patient_id, {})
        rows.append(
            {
                "id": patient_id,
                "full_name": _admin_first(payload.get("full_name"), payload.get("patient_name"), doc.get("display_name"), fallback="Registered patient"),
                "preferred_name": _admin_first(payload.get("preferred_name"), payload.get("full_name"), fallback="Patient"),
                "age": _admin_first(payload.get("age"), fallback="-"),
                "guardian": _admin_first(guardian.get("name"), linked_guardian.get("display_name"), fallback="Unassigned"),
                "guardian_phone": _admin_first(guardian.get("phone"), linked_guardian.get("guardian_phone"), fallback=""),
                "relationship": _admin_first(guardian.get("relationship"), linked_guardian.get("guardian_relationship"), fallback="Guardian / Caregiver"),
                "medicine_count": len(medicine) if isinstance(medicine, list) else int(bool(medicine)),
                "important_object": _admin_first(preferences.get("important_object"), payload.get("important_object"), fallback="Not set"),
                "robot_name": _admin_first(payload.get("robot_name"), fallback="Nesto"),
                "status": _admin_first(doc.get("status"), payload.get("status"), fallback="Active"),
                "last_activity": _admin_time_text(doc.get("timestamp") or doc.get("updated_at")),
                "consent_status": "Accepted" if all(bool(consent.get(key)) for key in ("terms_accepted", "privacy_accepted", "consent_checklist_accepted")) else "Pending",
                "source": "user_profiles",
                "profile_payload": payload,
            }
        )
        seen.add(patient_id)

    for user in _admin_docs("auth_users", {"role": "elderly_user"}, limit=100):
        patient_id = _admin_first(user.get("user_id"), fallback=f"elderly_user_{len(rows) + 1:02d}")
        if patient_id in seen:
            continue
        linked_guardian = guardian_lookup.get(patient_id, {})
        rows.append(
            {
                "id": patient_id,
                "full_name": _admin_first(user.get("display_name"), user.get("username"), fallback="Registered patient"),
                "preferred_name": _admin_first(user.get("preferred_name"), user.get("display_name"), fallback="Patient"),
                "age": _admin_first(user.get("age"), fallback="-"),
                "guardian": _admin_first(linked_guardian.get("display_name"), fallback="Unassigned"),
                "guardian_phone": _admin_first(linked_guardian.get("guardian_phone"), fallback=""),
                "relationship": _admin_first(linked_guardian.get("guardian_relationship"), fallback="Guardian / Caregiver"),
                "medicine_count": 0,
                "important_object": "Not set",
                "robot_name": "Nesto",
                "status": _admin_first(user.get("status"), fallback="Active"),
                "last_activity": _admin_date_text(user.get("updated_at") or user.get("created_at")),
                "consent_status": "Pending",
                "source": "auth_users",
                "profile_payload": {},
            }
        )
        seen.add(patient_id)

    if rows:
        return rows
    return [
        {
            "id": "elderly_user_01",
            "full_name": "Elderly User 01",
            "preferred_name": "Elderly User",
            "age": "-",
            "guardian": "Guardian / Caregiver not assigned",
            "guardian_phone": "",
            "relationship": "Guardian / Caregiver",
            "medicine_count": 0,
            "important_object": "Not set",
            "robot_name": "Nesto",
            "status": "Waiting",
            "last_activity": "Waiting for profile",
            "consent_status": "Pending",
            "source": "structured fallback",
            "profile_payload": {},
        }
    ]


def admin_guardians() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for user in _admin_docs("auth_users", {"role": "guardian_caregiver"}, limit=100):
        linked = user.get("linked_patients") or []
        rows.append(
            {
                "id": _admin_first(user.get("user_id"), user.get("profile_id"), fallback=f"guardian_{len(rows) + 1:02d}"),
                "name": _admin_first(user.get("display_name"), user.get("username"), fallback="Guardian / Caregiver"),
                "username": _admin_first(user.get("email"), user.get("username"), fallback="-"),
                "linked_patients": ", ".join(_admin_first(item.get("preferred_name"), item.get("patient_name"), item.get("patient_id")) for item in linked) or "No linked patient",
                "relationship": _admin_first(user.get("guardian_relationship"), fallback="Guardian / Caregiver"),
                "phone": _admin_first(user.get("guardian_phone"), fallback="-"),
                "last_login": _admin_date_text(user.get("last_login_at") or user.get("updated_at")),
                "status": _admin_first(user.get("status"), fallback="Active"),
                "source": "auth_users",
                "raw": user,
            }
        )
    if rows:
        return rows
    return [
        {
            "id": "guardian_01",
            "name": "Guardian / Caregiver",
            "username": "-",
            "linked_patients": "Waiting for linked patient",
            "relationship": "Guardian / Caregiver",
            "phone": "-",
            "last_login": "-",
            "status": "Waiting",
            "source": "structured fallback",
            "raw": {},
        }
    ]


def admin_robots() -> list[dict[str, Any]]:
    docs = _admin_docs("robot_status", limit=100)
    grouped: dict[str, dict[str, Any]] = {}
    for doc in docs:
        robot_id = _admin_first(doc.get("robot_id"), _admin_payload(doc).get("robot_id"), fallback="H1")
        current = grouped.get(robot_id)
        if current is None or str(_admin_sort_key(doc)) >= str(_admin_sort_key(current)):
            grouped[robot_id] = doc

    rows = []
    for doc in grouped.values():
        payload = _admin_payload(doc)
        battery = _admin_float(payload.get("battery_pct") or payload.get("battery") or payload.get("battery_percent"), 0.0)
        status_text = _admin_first(payload.get("status"), doc.get("status"), fallback="online").replace("_", " ").title()
        rows.append(
            {
                "id": _admin_first(doc.get("robot_id"), payload.get("robot_id"), fallback="H1"),
                "patient": _admin_first(doc.get("user_id"), payload.get("user_id"), fallback="elderly_user_01"),
                "online": "offline" not in status_text.lower(),
                "status": status_text,
                "battery": battery,
                "location": _admin_first(payload.get("current_room"), payload.get("room"), payload.get("location"), fallback="Unknown"),
                "movement": _admin_first(payload.get("navigation_state"), payload.get("movement"), fallback="Stationary").replace("_", " ").title(),
                "last_sync": _admin_time_text(doc.get("timestamp") or doc.get("updated_at")),
                "sensor_status": _admin_first(payload.get("sensor_status"), fallback="Ready").replace("_", " ").title(),
                "maintenance_status": "Low battery" if battery and battery < 25 else "Normal",
                "source": "robot_status",
                "raw": doc,
            }
        )
    if rows:
        return rows
    return [
        {
            "id": "H1",
            "patient": "elderly_user_01",
            "online": False,
            "status": "Waiting for robot_status",
            "battery": 0.0,
            "location": "Unknown",
            "movement": "Waiting",
            "last_sync": "-",
            "sensor_status": "Waiting",
            "maintenance_status": "Waiting",
            "source": "structured fallback",
            "raw": {},
        }
    ]


def admin_alerts(limit=40) -> list[dict[str, Any]]:
    docs = _admin_docs("alerts", limit=limit)
    rows = []
    for doc in docs:
        payload = _admin_payload(doc)
        rows.append(
            {
                "id": _admin_first(doc.get("event_id"), doc.get("_id"), fallback=f"alert_{len(rows) + 1:02d}"),
                "type": _admin_first(payload.get("message"), payload.get("reason"), doc.get("event_type"), fallback="Care alert").replace("_", " ").title(),
                "patient": _admin_first(doc.get("user_id"), payload.get("patient"), fallback="elderly_user_01"),
                "robot": _admin_first(doc.get("robot_id"), payload.get("robot_id"), fallback="H1"),
                "time": _admin_time_text(doc.get("timestamp") or doc.get("created_at")),
                "severity": _admin_first(payload.get("severity"), doc.get("severity"), fallback="Medium").title(),
                "status": _admin_first(payload.get("status"), doc.get("status"), fallback="Open").title(),
                "source": "alerts",
                "summary": _admin_first(payload.get("recommended_action"), payload.get("description"), fallback="Review required"),
            }
        )
    if rows:
        return rows
    return [
        {"id": "alert_waiting_01", "type": "High heart rate detected", "patient": "Elderly User 01", "robot": "H1", "time": "-", "severity": "High", "status": "Waiting", "source": "structured fallback", "summary": "Waiting for alerts collection."},
        {"id": "alert_waiting_02", "type": "Possible fall detected", "patient": "Patient 02", "robot": "H1", "time": "-", "severity": "High", "status": "Waiting", "source": "structured fallback", "summary": "Waiting for safety alert events."},
        {"id": "alert_waiting_03", "type": "Missed medication reminder", "patient": "Patient 03", "robot": "H1", "time": "-", "severity": "Medium", "status": "Waiting", "source": "structured fallback", "summary": "Waiting for medicine_events or alerts."},
        {"id": "alert_waiting_04", "type": "Low battery", "patient": "Device", "robot": "R1058", "time": "-", "severity": "Low", "status": "Waiting", "source": "structured fallback", "summary": "Waiting for robot_status battery data."},
    ]


def admin_telemetry(limit=80) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dashboard_updated_at = int(time.time() * 1000)
    for collection in ADMIN_EVENT_COLLECTIONS:
        for doc in _admin_docs(collection, limit=limit):
            payload = _admin_payload(doc)
            timing_values = {
                field: _admin_epoch_ms(doc.get(field) if doc.get(field) not in (None, "") else payload.get(field))
                for field in TELEMETRY_TIMING_FIELDS
            }
            timing_values["dashboard_updated_at"] = timing_values.get("dashboard_updated_at") or dashboard_updated_at
            row = {
                "timestamp": doc.get("timestamp") or doc.get("created_at") or "",
                "time": _admin_time_text(doc.get("timestamp") or doc.get("created_at")),
                "event_id": _admin_first(doc.get("event_id"), doc.get("_id"), fallback=f"{collection}_{len(rows) + 1:02d}"),
                "source_collection": collection,
                "robot_id": _admin_first(doc.get("robot_id"), payload.get("robot_id"), fallback="-"),
                "patient": _admin_first(doc.get("user_id"), payload.get("user_id"), payload.get("patient"), fallback="-"),
                "event_type": _admin_first(doc.get("event_type"), payload.get("event_type"), fallback="event").replace("_", " ").title(),
                "room": _admin_first(payload.get("current_room"), payload.get("room"), payload.get("location"), fallback="-"),
                "status": _admin_first(doc.get("status"), payload.get("status"), fallback="Normal").replace("_", " ").title(),
                "summary": _admin_first(payload.get("message"), payload.get("text"), payload.get("description"), payload.get("reason"), payload.get("target_object"), fallback="Event received"),
            }
            row.update(timing_values)
            rows.append(row)
    rows.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    if rows:
        return rows[:limit]
    return [
        {
            "timestamp": "",
            "time": "-",
            "event_id": "waiting_for_events",
            "source_collection": "structured fallback",
            "robot_id": "H1",
            "patient": "elderly_user_01",
            "event_type": "Waiting For Events",
            "room": "-",
            "status": "Waiting",
            "summary": "No telemetry/event records found yet.",
            "ui_triggered_at": "",
            "backend_received_at": "",
            "bridge_received_at": "",
            "robot_action_started_at": "",
            "robot_action_completed_at": "",
            "mongodb_logged_at": "",
            "dashboard_updated_at": dashboard_updated_at,
        }
    ]


def admin_support_tickets() -> list[dict[str, Any]]:
    docs = _admin_docs("support_tickets", limit=50)
    rows = []
    for doc in docs:
        payload = _admin_payload(doc)
        rows.append(
            {
                "id": _admin_first(doc.get("ticket_id"), doc.get("event_id"), doc.get("_id"), fallback=f"T-{len(rows) + 1:04d}"),
                "title": _admin_first(doc.get("title"), payload.get("title"), payload.get("message"), fallback="Support ticket"),
                "type": _admin_first(doc.get("type"), payload.get("type"), fallback="Support"),
                "patient": _admin_first(doc.get("patient"), payload.get("patient"), doc.get("user_id"), fallback="-"),
                "robot": _admin_first(doc.get("robot_id"), payload.get("robot_id"), fallback="-"),
                "priority": _admin_first(doc.get("priority"), payload.get("priority"), fallback="Medium").title(),
                "status": _admin_first(doc.get("status"), payload.get("status"), fallback="Open").title(),
                "created": _admin_date_text(doc.get("created_at") or doc.get("timestamp")),
                "assigned": _admin_first(doc.get("assigned_to"), payload.get("assigned_to"), fallback="NESTO support"),
                "source": "support_tickets",
            }
        )
    if rows:
        return rows
    return [
        {"id": "T-1001", "title": "Device not responding", "type": "Device", "patient": "Elderly User 01", "robot": "H1", "priority": "High", "status": "Open", "created": "-", "assigned": "NESTO support", "source": "structured fallback"},
        {"id": "T-1002", "title": "Medication reminder issue", "type": "Reminder", "patient": "Patient 03", "robot": "H1", "priority": "Medium", "status": "In Progress", "created": "-", "assigned": "Care ops", "source": "structured fallback"},
        {"id": "T-1003", "title": "App login problem", "type": "Account", "patient": "Guardian app", "robot": "-", "priority": "Low", "status": "Resolved", "created": "-", "assigned": "Support", "source": "structured fallback"},
        {"id": "T-1004", "title": "Robot low battery", "type": "Device", "patient": "Device fleet", "robot": "R1058", "priority": "Medium", "status": "Open", "created": "-", "assigned": "Maintenance", "source": "structured fallback"},
    ]


def admin_care_plans(patient_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs = _admin_docs("care_plans", limit=50)
    rows = []
    for doc in docs:
        payload = _admin_payload(doc)
        rows.append(
            {
                "id": _admin_first(doc.get("plan_id"), doc.get("_id"), fallback=f"plan_{len(rows) + 1:02d}"),
                "patient": _admin_first(doc.get("patient"), payload.get("patient"), doc.get("user_id"), fallback="Patient"),
                "status": _admin_first(doc.get("status"), payload.get("status"), fallback="Active").title(),
                "medicine": _admin_first(payload.get("medicine_name"), payload.get("medicine_routine"), fallback="Routine on file"),
                "schedule": _admin_first(payload.get("reminder_schedule"), payload.get("scheduled_time"), fallback="Review schedule"),
                "guardian": _admin_first(payload.get("guardian"), payload.get("caregiver"), fallback="Guardian / Caregiver"),
                "support": _admin_first(payload.get("support_needs"), fallback="Daily care support"),
                "objects": _admin_first(payload.get("important_object"), fallback="Not set"),
                "notes": _admin_first(payload.get("care_notes"), fallback="No notes"),
                "updated": _admin_date_text(doc.get("updated_at") or doc.get("timestamp")),
                "source": "care_plans",
            }
        )
    if rows:
        return rows
    return [
        {
            "id": f"plan_{index + 1:02d}",
            "patient": row["preferred_name"],
            "status": row["status"],
            "medicine": f"{row['medicine_count']} routine item(s)",
            "schedule": "From user profile",
            "guardian": row["guardian"],
            "support": "Personalized daily support",
            "objects": row["important_object"],
            "notes": "Built from profile and Guardian / Caregiver notes",
            "updated": row["last_activity"],
            "source": "user_profiles",
        }
        for index, row in enumerate(patient_rows[:8])
    ]


def admin_reports(counts: dict[str, int], patient_rows: list[dict[str, Any]], guardian_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"title": "Daily care summary", "metric": f"{counts.get('scenario_events', 0)} scenario events", "source": "scenario_events"},
        {"title": "Weekly activity summary", "metric": f"{counts.get('environment_events', 0)} room/object events", "source": "environment_events"},
        {"title": "Medicine adherence summary", "metric": f"{counts.get('medicine_events', 0)} medicine events", "source": "medicine_events"},
        {"title": "Alert summary", "metric": f"{counts.get('alerts', 0)} alerts", "source": "alerts"},
        {"title": "Robot uptime summary", "metric": f"{counts.get('robot_status', 0)} robot updates", "source": "robot_status"},
        {"title": "Caregiver activity summary", "metric": f"{len(guardian_rows)} Guardian / Caregiver account(s)", "source": "auth_users"},
        {"title": "Registered patient summary", "metric": f"{len(patient_rows)} patient profile(s)", "source": "user_profiles/auth_users"},
    ]


def admin_dashboard_snapshot() -> dict[str, Any]:
    def _load() -> dict[str, Any]:
        try:
            from event_contracts import KAFKA_TOPICS, MONGO_COLLECTIONS
        except Exception:
            KAFKA_TOPICS = []
            MONGO_COLLECTIONS = COLLECTIONS

        mongo = _admin_mongo_status()
        counts = safe_counts() if mongo.get("available") else {name: 0 for name in MONGO_COLLECTIONS}
        patient_rows = admin_patients()
        guardian_rows = admin_guardians()
        robot_rows = admin_robots()
        alert_rows = admin_alerts()
        telemetry_rows = admin_telemetry()
        care_plan_rows = admin_care_plans(patient_rows)
        ticket_rows = admin_support_tickets()
        cache = _admin_cache_status()
        chroma = _admin_chroma_status()
        kafka = _admin_kafka_status()

        online = sum(1 for item in robot_rows if item.get("online"))
        low_battery = sum(1 for item in robot_rows if _admin_float(item.get("battery")) and _admin_float(item.get("battery")) < 25)
        live_alert_count = counts.get("alerts", 0)
        active_alerts = sum(1 for item in alert_rows if item.get("source") != "structured fallback" and str(item.get("status", "")).lower() not in {"resolved", "closed"})
        if live_alert_count == 0:
            active_alerts = 0

        return {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "counts": counts,
            "kpis": {
                "robots_online": online,
                "robots_total": len(robot_rows),
                "active_alerts": active_alerts,
                "care_messages": counts.get("conversation_events", 0),
                "room_events": counts.get("environment_events", 0),
                "registered_patients": len(patient_rows),
                "guardian_caregivers": len(guardian_rows),
            },
            "fleet": {
                "online": online,
                "offline": max(len(robot_rows) - online, 0),
                "low_battery": low_battery,
                "total": len(robot_rows),
            },
            "patients": patient_rows,
            "guardians": guardian_rows,
            "robots": robot_rows,
            "alerts": alert_rows,
            "telemetry": telemetry_rows,
            "care_plans": care_plan_rows,
            "reports": admin_reports(counts, patient_rows, guardian_rows),
            "support_tickets": ticket_rows,
            "system": {
                "mongo": mongo,
                "cache": cache,
                "chroma": chroma,
                "kafka": kafka,
                "topics": KAFKA_TOPICS,
                "collections": MONGO_COLLECTIONS,
            },
            "source": {
                "summary": "MongoDB via Redis/local TTL cache",
                "cache_mode": cache.get("mode", "unknown"),
                "admin_only": True,
            },
        }

    try:
        import cache_layer

        return cache_layer.get_or_set("dashboard:admin:view_snapshot", _load, ttl_seconds=5)
    except Exception:
        return _load()
