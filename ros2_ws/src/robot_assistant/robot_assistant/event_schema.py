"""Shared Sprint 2 event schema for the humanoid assistant data pipeline."""

from __future__ import annotations

from copy import deepcopy
from time import time
from typing import Any
from uuid import uuid4


DEFAULT_SOURCE = "humanoid_assistant"
DEFAULT_USER_ID = "elderly_user_01"
DEFAULT_ROBOT_ID = "H1"

REQUIRED_FIELDS = (
    "event_id",
    "event_type",
    "timestamp",
    "source",
    "user_id",
    "robot_id",
    "payload",
)

COLLECTIONS = (
    "robot_status",
    "environment_events",
    "medicine_events",
    "mood_events",
    "alerts",
    "conversation_events",
)

EVENT_COLLECTION_ROUTES = {
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


def current_epoch_ms() -> int:
    """Return the current time in epoch milliseconds."""
    return int(time() * 1000)


def create_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    timestamp: int | None = None,
    source: str = DEFAULT_SOURCE,
    user_id: str = DEFAULT_USER_ID,
    robot_id: str = DEFAULT_ROBOT_ID,
) -> dict[str, Any]:
    """Create one schema-compliant humanoid assistant event."""
    if event_type not in EVENT_COLLECTION_ROUTES:
        raise ValueError(f"Unsupported event_type: {event_type}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    event = {
        "event_id": f"evt_{current_epoch_ms()}_{uuid4().hex[:8]}",
        "event_type": event_type,
        "timestamp": timestamp if timestamp is not None else current_epoch_ms(),
        "source": source,
        "user_id": user_id,
        "robot_id": robot_id,
        "payload": deepcopy(payload),
    }
    errors = validate_event(event)
    if errors:
        raise ValueError("; ".join(errors))
    return event


def collection_for_event(event_type: str) -> str:
    """Return the MongoDB collection name for an event type."""
    try:
        return EVENT_COLLECTION_ROUTES[event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported event_type: {event_type}") from exc


def validate_event(event: dict[str, Any]) -> list[str]:
    """Return validation errors for one event. Empty list means valid."""
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in event:
            errors.append(f"missing required field: {field}")

    if errors:
        return errors

    if not isinstance(event["event_id"], str) or not event["event_id"]:
        errors.append("event_id must be a non-empty string")
    if event["event_type"] not in EVENT_COLLECTION_ROUTES:
        errors.append(f"unsupported event_type: {event['event_type']}")
    if not isinstance(event["timestamp"], int):
        errors.append("timestamp must be an integer epoch millisecond value")
    if not isinstance(event["source"], str) or not event["source"]:
        errors.append("source must be a non-empty string")
    if not isinstance(event["user_id"], str) or not event["user_id"]:
        errors.append("user_id must be a non-empty string")
    if not isinstance(event["robot_id"], str) or not event["robot_id"]:
        errors.append("robot_id must be a non-empty string")
    if not isinstance(event["payload"], dict):
        errors.append("payload must be an object")

    return errors
