"""
MongoDB Atlas query and event-write helpers for NESTO Care.

This module is the dashboard bridge to the `humanoid_assistant` database. It
reads Daniel/Webots event collections, keeps UI helpers empty-safe, and exposes
explicit event insert wrappers for dashboard actions.
"""

import datetime as dt
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern

load_dotenv()
DATABASE_NAME = os.getenv("MONGO_DB_NAME") or os.getenv("MONGODB_DATABASE") or "humanoid_assistant"
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or ""
_client_init_error = None
try:
    _client = MongoClient(
        MONGO_URI or "mongodb://localhost:27017",
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
        retryWrites=False,
    )
except Exception as exc:
    _client_init_error = str(exc)
    _client = MongoClient(
        "mongodb://localhost:27017",
        serverSelectionTimeoutMS=800,
        connectTimeoutMS=800,
        socketTimeoutMS=800,
        retryWrites=False,
    )
_db = _client[DATABASE_NAME]

CORE_COLLECTIONS = [
    "alerts",
    "auth_users",
    "conversation_events",
    "environment_events",
    "medicine_events",
    "mood_events",
    "robot_status",
    "schedule_events",
    "scenario_events",
    "user_profiles",
]

OPTIONAL_COLLECTIONS = [
    "caregiver_notes",
    "support_tickets",
    "dashboard_kpis",
    "care_plans",
]

DANIEL_EVENT_COLLECTION_ROUTES = {
    "robot_status_updated": "robot_status",
    "object_detected": "environment_events",
    "room_detected": "environment_events",
    "object_distance_estimated": "environment_events",
    "scene_described": "environment_events",
    "medicine_reminder_due": "medicine_events",
    "medicine_taken": "medicine_events",
    "medicine_missed": "medicine_events",
    "mood_detected": "mood_events",
    "wellbeing_score_updated": "mood_events",
    "important_object_alert": "alerts",
    "safety_alert": "alerts",
    "negative_mood_alert": "alerts",
    "missed_medicine_alert": "alerts",
    "user_message": "conversation_events",
    "robot_response": "conversation_events",
    "session_started": "conversation_events",
    "session_ended": "conversation_events",
    "robot_command_sent": "conversation_events",
}

DASHBOARD_WRITE_ROUTES = {
    "schedule_event": "schedule_events",
    "schedule_events": "schedule_events",
    "schedule_viewed": "schedule_events",
    "schedule_task_done": "schedule_events",
    "medicine_event": "medicine_events",
    "medicine_events": "medicine_events",
    "take_medicine": "medicine_events",
    "mood_event": "mood_events",
    "mood_events": "mood_events",
    "mood_check": "mood_events",
    "alert": "alerts",
    "alerts": "alerts",
    "emergency": "alerts",
    "conversation_event": "conversation_events",
    "conversation_events": "conversation_events",
    "talk_to_nesto": "conversation_events",
    "caregiver_notification": "conversation_events",
    "caregiver_notifications": "conversation_events",
    "caregiver_note_saved": "caregiver_notes",
    "caregiver_note": "caregiver_notes",
    "profile_saved": "user_profiles",
    "profile_updated": "user_profiles",
    "user_profile": "user_profiles",
    "scenario_requested": "scenario_events",
    "find_cane": "scenario_events",
    "find_medicine": "scenario_events",
    "call_caregiver": "scenario_events",
    "summon_robot": "scenario_events",
}




def get_database_name():
    """Return the MongoDB database currently used by the dashboard."""
    return DATABASE_NAME


def get_connection_status():
    """
    Return a safe MongoDB status object without exposing the connection string.
    """
    if _client_init_error:
        return {
            "available": False,
            "status": "unavailable",
            "database_name": DATABASE_NAME,
            "uri_configured": bool(MONGO_URI),
            "collections": [],
            "error": _client_init_error,
        }
    try:
        _client.admin.command("ping")
        collection_names = _db.list_collection_names()
        return {
            "available": True,
            "status": "connected",
            "database_name": DATABASE_NAME,
            "uri_configured": bool(MONGO_URI),
            "collections": sorted(collection_names),
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "unavailable",
            "database_name": DATABASE_NAME,
            "uri_configured": bool(MONGO_URI),
            "collections": [],
            "error": str(exc),
        }


def get_latest_document(collection_name):
    """Return the newest document from one collection, or None."""
    if _client_init_error:
        return None
    return _db[collection_name].find_one(sort=[("timestamp", -1), ("_id", -1)])


def get_latest_documents(collection_names=None):
    """Return newest documents keyed by collection name for proof/admin views."""
    collection_names = collection_names or CORE_COLLECTIONS
    latest = {}
    for collection_name in collection_names:
        try:
            latest[collection_name] = get_latest_document(collection_name)
        except Exception:
            latest[collection_name] = None
    return latest


def get_daniel_compatibility_report():
    """Summarize how Daniel/Webots events map into the NESTO dashboard."""
    counts = {}
    try:
        counts = get_collection_counts()
    except Exception:
        counts = {name: 0 for name in CORE_COLLECTIONS + OPTIONAL_COLLECTIONS}
    return {
        "database_name": DATABASE_NAME,
        "supported_env_vars": ["MONGO_URI", "MONGODB_URI", "MONGO_DB_NAME", "MONGODB_DATABASE"],
        "core_collections": CORE_COLLECTIONS,
        "optional_collections": OPTIONAL_COLLECTIONS,
        "daniel_event_collection_routes": DANIEL_EVENT_COLLECTION_ROUTES,
        "dashboard_write_routes": DASHBOARD_WRITE_ROUTES,
        "collection_counts": {name: counts.get(name, 0) for name in CORE_COLLECTIONS},
        "default_user_id": "elderly_user_01",
        "default_robot_id": "H1",
    }

# ----------------------------------------------------------------------
# Small shared helpers
# ----------------------------------------------------------------------


def _latest(collection_name):
    """Newest document in a collection, or None if it is empty."""
    if _client_init_error:
        return None
    return _db[collection_name].find_one(sort=[("timestamp", -1)])


def _to_time(epoch_ms):
    """Convert epoch-millisecond timestamps to 'HH:MM' text."""
    if epoch_ms is None:
        return ""
    return dt.datetime.fromtimestamp(epoch_ms / 1000).strftime("%H:%M")


def _first_text(*values):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _profile_fields_from(doc):
    if not doc:
        return {}

    payload = doc.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    profile = {}
    patient_name = _first_text(
        payload.get("patient_name"),
        payload.get("elderly_name"),
        payload.get("elderly_user_name"),
        payload.get("resident_name"),
        payload.get("user_name"),
        doc.get("patient_name"),
        doc.get("elderly_name"),
        doc.get("resident_name"),
        doc.get("name") if str(doc.get("role", "")).lower() in {"patient", "elderly", "resident"} else None,
    )
    caregiver_name = _first_text(
        (payload.get("guardian_contact") or {}).get("name") if isinstance(payload.get("guardian_contact"), dict) else None,
        payload.get("caregiver_name"),
        payload.get("family_contact_name"),
        payload.get("primary_caregiver"),
        payload.get("guardian_name"),
        doc.get("caregiver_name"),
        doc.get("family_contact_name"),
    )
    assistant_name = _first_text(
        payload.get("assistant_name"),
        payload.get("robot_name"),
        doc.get("assistant_name"),
        doc.get("robot_name"),
    )

    if patient_name:
        profile["patient_name"] = patient_name
    if caregiver_name:
        profile["caregiver_name"] = caregiver_name
    if assistant_name:
        profile["assistant_name"] = assistant_name

    patient_id = _first_text(
        payload.get("patient_id"),
        payload.get("user_id"),
        doc.get("patient_id"),
        doc.get("user_id"),
    )
    caregiver_id = _first_text(
        payload.get("caregiver_id"),
        payload.get("family_contact_id"),
        doc.get("caregiver_id"),
        doc.get("family_contact_id"),
    )
    robot_id = _first_text(payload.get("robot_id"), doc.get("robot_id"))

    if patient_id:
        profile["patient_id"] = patient_id
    if caregiver_id:
        profile["caregiver_id"] = caregiver_id
    if robot_id:
        profile["robot_id"] = robot_id
    return profile


def get_care_profile():
    """
    Purpose:
    Return display profile fields when MongoDB has them.

    The current event records include live user_id and robot_id values. If a
    future profile/patient collection or event payload includes names, this
    function will pick them up automatically without changing UI code.
    """
    profile = {}
    if _client_init_error:
        return profile

    profile_collections = [
        "care_profiles",
        "care_profile",
        "patient_profiles",
        "patients",
        "users",
        "settings",
    ]
    for collection_name in profile_collections:
        doc = _db[collection_name].find_one(sort=[("updated_at", -1), ("timestamp", -1), ("_id", -1)])
        profile.update(_profile_fields_from(doc))

    event_collections = [
        "robot_status",
        "conversation_events",
        "environment_events",
        "mood_events",
        "medicine_events",
        "alerts",
    ]
    for collection_name in event_collections:
        profile.update(_profile_fields_from(_latest(collection_name)))

    return profile


def get_collection_counts():
    """
    Purpose:
    Return document counts for the MongoDB collections used by the dashboard.
    The Family Dashboard uses this to show which values are real and which
    values are fallback because their source collection is still empty.
    """
    collection_names = CORE_COLLECTIONS + OPTIONAL_COLLECTIONS

    counts = {}
    if _client_init_error:
        return {collection_name: 0 for collection_name in collection_names}
    for collection_name in collection_names:
        counts[collection_name] = _db[collection_name].count_documents({})
    return counts


# ----------------------------------------------------------------------
# Robot Dashboard tiles  (robot_status confirmed REAL)
# ----------------------------------------------------------------------


def get_battery():
    """Latest battery percentage, or None if no data yet."""
    doc = _latest("robot_status")
    if doc is None:
        return None
    return doc.get("payload", {}).get("battery_pct")


def get_location():
    """Latest room the robot is in, or None if no data yet."""
    doc = _latest("robot_status")
    if doc is None:
        return None
    return doc.get("payload", {}).get("current_room")


def get_status():
    """Latest robot state (e.g. 'active'), or None if no data yet."""
    doc = _latest("robot_status")
    if doc is None:
        return None
    return doc.get("payload", {}).get("status")


def get_navigation_state():
    """Latest navigation state (e.g. 'stationary'), or None if no data yet."""
    doc = _latest("robot_status")
    if doc is None:
        return None
    return doc.get("payload", {}).get("navigation_state")


def get_event_feed(limit=10):
    """
    Most recent events across ALL collections, newest first.
    Returns a list of (time_text, description) tuples, with labels
    prettified, e.g. [("07:11", "Robot Status Updated"), ...].
    Empty list if no data yet.
    """
    if _client_init_error:
        return []
    everything = []
    for name in ["robot_status", "alerts", "environment_events",
                 "conversation_events", "mood_events", "medicine_events"]:
        docs = _db[name].find(sort=[("timestamp", -1)], limit=limit)
        everything.extend(docs)

    everything.sort(key=lambda d: d.get("timestamp", 0), reverse=True)
    everything = everything[:limit]

    feed = []
    for doc in everything:
        time_text = _to_time(doc.get("timestamp"))
        label = doc.get("event_type", "event").replace("_", " ").title()
        feed.append((time_text, label))
    return feed


def get_scenario_events(limit=12):
    """
    Purpose:
    Read scenario-related robot/app events from MongoDB.
    MongoDB is the source of truth for structured robot readings and scenario
    outputs. ChromaDB can later use these events as memory context, but it does
    not replace MongoDB.
    """
    if _client_init_error:
        return []
    scenario_events = []
    collections = [
        "robot_status",
        "conversation_events",
        "environment_events",
        "scenario_events",
        "alerts",
        "medicine_events",
        "mood_events",
    ]

    scenario_filter = {
        "$or": [
            {"payload.scenario_id": {"$exists": True}},
            {"payload.active_command_id": {"$exists": True}},
            {"payload.active_intent": {"$exists": True}},
            {"payload.target_object": {"$exists": True}},
            {"payload.retrieval_state": {"$exists": True}},
            {"payload.scenario_type": {"$exists": True}},
            {"scenario_type": {"$exists": True}},
            {"payload.action": {"$exists": True}},
            {"payload.notify_guardian": True},
        ]
    }

    for collection_name in collections:
        docs = _db[collection_name].find(
            scenario_filter,
            sort=[("timestamp", -1)],
            limit=limit,
        )

        for doc in docs:
            payload = doc.get("payload", {})
            event_type = doc.get("event_type", "event")
            scenario_id = (
                payload.get("scenario_id")
                or payload.get("active_intent")
                or payload.get("active_command_id")
                or payload.get("target_object")
                or "nesto_care_event"
            )
            description = (
                payload.get("message")
                or payload.get("text")
                or payload.get("transcript")
                or payload.get("reason")
                or payload.get("description")
                or payload.get("retrieval_state")
                or payload.get("task_status")
                or payload.get("status")
                or payload.get("target_object")
                or event_type.replace("_", " ").title()
            )

            scenario_events.append({
                "time": _to_time(doc.get("timestamp")),
                "scenario_id": scenario_id,
                "event_type": event_type.replace("_", " ").title(),
                "collection": collection_name,
                "description": description,
                "timestamp": doc.get("timestamp", 0),
            })

    scenario_events.sort(key=lambda item: item["timestamp"], reverse=True)
    return scenario_events[:limit]


def get_alerts(limit=5):
    """
    Most recent alerts, newest first.
    Returns a list of (time_text, message) tuples. Empty list if none yet.
    NOTE: alerts collection is currently empty; field names unconfirmed.
    """
    if _client_init_error:
        return []
    docs = _db["alerts"].find(sort=[("timestamp", -1)], limit=limit)
    alerts = []
    for doc in docs:
        time_text = _to_time(doc.get("timestamp"))
        payload = doc.get("payload", {})
        message = (
            payload.get("message")
            or payload.get("reason")
            or payload.get("retrieval_state")
            or payload.get("status")
            or doc.get("event_type", "alert")
        )
        alerts.append((time_text, message))
    return alerts


# ----------------------------------------------------------------------
# Family Dashboard tiles  (collections may be empty; return None so app uses safe fallbacks)
# ----------------------------------------------------------------------


def get_mood():
    """Latest mood, or None. mood_events is empty for now."""
    doc = _latest("mood_events")
    if doc is None:
        return None
    return doc.get("payload", {}).get("mood")


def get_wellbeing_score():
    """Latest wellbeing score, or None. mood_events is empty for now."""
    doc = _latest("mood_events")
    if doc is None:
        return None
    return doc.get("payload", {}).get("wellbeing_score")


def get_medication():
    """Latest medication status, or None. medicine_events is empty for now."""
    doc = _latest("medicine_events")
    if doc is None:
        return None
    return doc.get("payload", {}).get("status")


# ----------------------------------------------------------------------
# Event writes from dashboard actions
# ----------------------------------------------------------------------


def _now_ms():
    return int(dt.datetime.now().timestamp() * 1000)


def insert_dashboard_event(event_type, scenario_type=None, role="dashboard", status="requested", source_page="", payload=None):
    """
    Insert a dashboard action into the correct MongoDB collection.

    This keeps the UI functional for the demo: user/caregiver/admin actions are
    no longer only visual. They produce care events that the dashboard can read.
    """
    timestamp = _now_ms()
    payload = dict(payload or {})
    if scenario_type:
        payload.setdefault("scenario_type", scenario_type)
    payload.setdefault("status", status)
    payload.setdefault("source_page", source_page)
    metadata = dict(payload.pop("metadata", {}) or {})
    metadata.setdefault("producer", "Leona / Dashboard UI")
    metadata.setdefault("write_wrapper", "db_queries.insert_dashboard_event")
    metadata.setdefault("target_collection", DASHBOARD_WRITE_ROUTES.get(event_type, "scenario_events"))

    collection = DASHBOARD_WRITE_ROUTES.get(event_type, "scenario_events")

    document = {
        "event_id": f"dash_{timestamp}_{collection}",
        "event_type": event_type,
        "scenario_type": scenario_type or payload.get("scenario_type", ""),
        "timestamp": timestamp,
        "time": _to_time(timestamp),
        "source": "dashboard",
        "source_alias": "nesto_dashboard",
        "source_page": source_page,
        "user_id": payload.get("user_id", "elderly_user_01"),
        "robot_id": payload.get("robot_id", "H1"),
        "role": role,
        "status": status,
        "payload": payload,
        "metadata": metadata,
    }
    try:
        if _client_init_error:
            return None
        result = _db[collection].with_options(write_concern=WriteConcern(w=1, wtimeout=3000)).insert_one(document)
        try:
            import kafka_bridge_plan

            kafka_bridge_plan.publish_event_to_kafka(collection, document)
        except Exception:
            pass
        return str(result.inserted_id)
    except Exception:
        return None


def create_scenario_event(scenario_type, payload=None, status="requested", role="dashboard", source_page=""):
    data = dict(payload or {})
    data.setdefault("scenario_type", scenario_type)
    return insert_dashboard_event("scenario_requested", scenario_type=scenario_type, role=role, status=status, source_page=source_page, payload=data)


def create_schedule_event(payload=None, status="recorded", role="dashboard", source_page=""):
    return insert_dashboard_event("schedule_event", scenario_type="schedule", role=role, status=status, source_page=source_page, payload=payload or {})


def create_medicine_event(payload=None, status="recorded", role="dashboard", source_page=""):
    return insert_dashboard_event("medicine_event", scenario_type="medicine_reminder", role=role, status=status, source_page=source_page, payload=payload or {})


def create_mood_event(payload=None, status="recorded", role="dashboard", source_page=""):
    return insert_dashboard_event("mood_event", scenario_type="wellbeing_checkin", role=role, status=status, source_page=source_page, payload=payload or {})


def create_alert_event(payload=None, status="open", role="dashboard", source_page=""):
    return insert_dashboard_event("alert", scenario_type="safety_alert", role=role, status=status, source_page=source_page, payload=payload or {})


def create_caregiver_note_event(payload=None, status="saved", role="guardian", source_page=""):
    return insert_dashboard_event("caregiver_note_saved", scenario_type="caregiver_note", role=role, status=status, source_page=source_page, payload=payload or {})


def create_profile_updated_event(profile_payload, status="saved", role="care_profile", source_page="User Creation + Preferences"):
    payload = dict(profile_payload or {})
    guardian = payload.get("guardian_contact")
    if guardian and "next_of_kin" not in payload:
        payload["next_of_kin"] = "legacy alias for guardian_contact"
    return insert_dashboard_event("profile_updated", scenario_type="profile", role=role, status=status, source_page=source_page, payload=payload)


def upsert_profile_record(profile_payload, status="saved", role="care_profile", source_page="User Creation + Preferences"):
    """
    Create or update the stable profile document used by onboarding.

    This keeps profile setup idempotent: pressing Save again refreshes the same
    profile record instead of adding duplicate user_profiles rows.
    """
    timestamp = _now_ms()
    payload = dict(profile_payload or {})
    guardian = payload.get("guardian_contact")
    if guardian and "next_of_kin" not in payload:
        payload["next_of_kin"] = "legacy alias for guardian_contact"
    user_id = str(payload.get("user_id") or "elderly_user_01")
    event_id = f"profile_{user_id}"
    document = {
        "event_id": event_id,
        "event_type": "profile_updated",
        "scenario_type": "profile",
        "timestamp": timestamp,
        "time": _to_time(timestamp),
        "source": "dashboard",
        "source_alias": "nesto_dashboard",
        "source_page": source_page,
        "user_id": user_id,
        "robot_id": str(payload.get("robot_id") or "H1"),
        "role": role,
        "status": status,
        "profile_id": user_id,
        "payload": payload,
        "metadata": {
            "producer": "Leona / Dashboard UI",
            "write_wrapper": "db_queries.upsert_profile_record",
            "target_collection": "user_profiles",
            "kafka_topic": "profile_updated",
        },
    }
    try:
        if _client_init_error:
            return None
        result = _db["user_profiles"].with_options(write_concern=WriteConcern(w=1, wtimeout=3000)).update_one(
            {"event_id": event_id},
            {"$set": document},
            upsert=True,
        )
        try:
            import kafka_bridge_plan

            kafka_bridge_plan.publish_event_to_kafka("user_profiles", document)
        except Exception:
            pass
        return str(result.upserted_id or event_id)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Quick self-test: run `python db_queries.py`
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("battery:   ", get_battery())
    print("location:  ", get_location())
    print("status:    ", get_status())
    print("navigation:", get_navigation_state())
    print("mood:      ", get_mood())
    print("wellbeing: ", get_wellbeing_score())
    print("medication:", get_medication())
    print("alerts:    ", get_alerts())
    print("event feed:", get_event_feed())
    print("scenarios: ", get_scenario_events())
