"""
Executable architecture and event contracts for Daniel/Webots and NESTO Care.

This module is the dashboard source of truth for the integration contract:
Webots -> MongoDB -> Redis -> Dashboard, Dashboard <-> ChromaDB <-> Webots,
and MongoDB/event producers -> Kafka topics -> dashboard consumers.
"""

from __future__ import annotations

import json


DEFAULT_DATABASE_NAME = "humanoid_assistant"
DEFAULT_USER_ID = "elderly_user_01"
DEFAULT_ROBOT_ID = "H1"


CORE_MONGO_COLLECTIONS = [
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


OPTIONAL_MONGO_COLLECTIONS = [
    "caregiver_notes",
    "support_tickets",
    "dashboard_kpis",
    "care_plans",
]


MONGO_COLLECTIONS = CORE_MONGO_COLLECTIONS + OPTIONAL_MONGO_COLLECTIONS


KAFKA_TOPICS = [
    "robot_status",
    "conversation_events",
    "environment_events",
    "medicine_events",
    "mood_events",
    "alerts",
    "scenario_events",
    "schedule_events",
    "profile_updated",
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


DASHBOARD_EVENT_COLLECTION_ROUTES = {
    "scenario_requested": "scenario_events",
    "find_cane": "scenario_events",
    "find_medicine": "scenario_events",
    "summon_robot": "scenario_events",
    "talk_to_nesto": "conversation_events",
    "caregiver_call_requested": "scenario_events",
    "schedule_event": "schedule_events",
    "schedule_viewed": "schedule_events",
    "schedule_task_done": "schedule_events",
    "medicine_event": "medicine_events",
    "mood_event": "mood_events",
    "alert": "alerts",
    "caregiver_note_saved": "caregiver_notes",
    "profile_saved": "user_profiles",
    "profile_updated": "user_profiles",
}


EVENT_TO_COLLECTION = {
    **DANIEL_EVENT_COLLECTION_ROUTES,
    **DASHBOARD_EVENT_COLLECTION_ROUTES,
}


DANIEL_TO_DASHBOARD_EVENT_MAP = {
    "find_cane_demo_01": {
        "scenario_type": "find_cane",
        "dashboard_collection": "scenario_events",
        "robot_command": {"action": "search_object", "target_object": "cane"},
    },
    "medicine_reminder_demo_01": {
        "scenario_type": "medicine_reminder",
        "dashboard_collection": "medicine_events",
        "robot_command": {"action": "check_medicine", "target_object": "medicine_box"},
    },
    "wellbeing_checkin_demo_01": {
        "scenario_type": "wellbeing_checkin",
        "dashboard_collection": "mood_events",
        "robot_command": {"action": "support_user"},
    },
    "general_support": {
        "scenario_type": "general_support",
        "dashboard_collection": "conversation_events",
        "robot_command": None,
    },
}


EVENT_SCHEMAS = {
    "robot_status": {
        "topic": "robot_status",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["status", "battery_pct", "current_room", "navigation_state", "sensor_status"],
        "dashboard": "Robot location, battery, readiness, sensor health, and admin telemetry.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "conversation_events": {
        "topic": "conversation_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["text", "transcript", "detected_intent", "response_text", "scenario_id", "command_id"],
        "dashboard": "Push-to-talk, NESTO response history, scenario routing, and care activity.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "environment_events": {
        "topic": "environment_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["room", "object", "position", "distance_m", "confidence", "sensor"],
        "dashboard": "Object finder, cane location, room/object history, and robot activity.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "medicine_events": {
        "topic": "medicine_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["medicine_name", "dose", "scheduled_time", "reminder_status", "status"],
        "dashboard": "Medication reminders, taken/missed state, and family summary.",
        "realtime": False,
        "redis_ttl_seconds": 300,
    },
    "mood_events": {
        "topic": "mood_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["mood", "wellbeing_score", "score", "confidence", "signals", "summary"],
        "dashboard": "Wellbeing monitor, family mood card, and admin care trend.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "alerts": {
        "topic": "alerts",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"],
        "payload": ["severity", "reason", "status", "recommended_action", "related_event_id"],
        "dashboard": "Care alerts, provider triage, and family notification.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "scenario_events": {
        "topic": "schedule_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "role", "status", "payload"],
        "payload": ["scenario_type", "scenario_id", "action", "target_object", "message", "metadata"],
        "dashboard": "Find cane, find medicine, summon robot, caregiver call, and approved scenario requests.",
        "realtime": True,
        "redis_ttl_seconds": 5,
    },
    "schedule_events": {
        "topic": "scenario_events",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "role", "status", "payload"],
        "payload": ["schedule_date", "task_name", "task_status", "scheduled_time", "message", "metadata"],
        "dashboard": "Today's schedule views, task completion, and routine acknowledgements.",
        "realtime": False,
        "redis_ttl_seconds": 300,
    },
    "user_profiles": {
        "topic": "profile_updated",
        "required": ["event_id", "event_type", "timestamp", "source", "user_id", "role", "status", "payload"],
        "payload": ["preferred_name", "robot_name", "guardian_contact", "next_of_kin_legacy_alias", "medicine_schedule", "preferences"],
        "dashboard": "Profile/preferences summary saved from the User Creation + Preferences page.",
        "realtime": False,
        "redis_ttl_seconds": 600,
    },
}


CHROMADB_MEMORY_TYPES = {
    "profile_preference": "User name, preferred name, guardian / caregiver contact, robot name, medicine schedule, language, tone, and care preferences.",
    "object_memory": "Important object and location memory, such as cane or medicine box locations.",
    "robot_mapping_memory": "Semantic memory from Webots/robot mapping that can help future scenario search.",
    "caregiver_note": "Family/caregiver notes used as context for NESTO responses.",
    "scenario_summary": "Condensed scenario result saved after MongoDB/Webots event processing.",
}


ARCHITECTURE = {
    "persistent_event_flow": ["Webots", "MongoDB", "Redis", "Dashboard"],
    "memory_flow": ["Dashboard", "ChromaDB", "Webots"],
    "streaming_flow": ["MongoDB/Event Producer", "Kafka Topics", "Dashboard Consumer"],
    "mongodb_role": "Main persistent event storage in the humanoid_assistant Atlas database.",
    "redis_role": "Cache layer checked by dashboard helpers before repeated MongoDB reads.",
    "chromadb_role": "Memory/profile layer for semantic preferences and object/location memory.",
    "kafka_role": "Prepared real-time streaming layer; not claimed as fully live until producer and consumer are wired.",
}


def contract_snapshot() -> dict:
    return {
        "architecture": ARCHITECTURE,
        "database_name": DEFAULT_DATABASE_NAME,
        "core_mongo_collections": CORE_MONGO_COLLECTIONS,
        "optional_mongo_collections": OPTIONAL_MONGO_COLLECTIONS,
        "kafka_topics": KAFKA_TOPICS,
        "event_to_collection": EVENT_TO_COLLECTION,
        "daniel_event_collection_routes": DANIEL_EVENT_COLLECTION_ROUTES,
        "daniel_to_dashboard_event_map": DANIEL_TO_DASHBOARD_EVENT_MAP,
        "event_schemas": EVENT_SCHEMAS,
        "chromadb_memory_types": CHROMADB_MEMORY_TYPES,
    }


def main() -> None:
    print("NESTO CARE ARCHITECTURE AND EVENT CONTRACT")
    print(json.dumps(contract_snapshot(), indent=2))


if __name__ == "__main__":
    main()
