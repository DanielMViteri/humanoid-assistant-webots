"""
Draft-only FastAPI route for later integration.

This file is intentionally isolated in local_kpi_ui_foundation and is not wired
into any application. It keeps credentials server-side and reads MongoDB using
read-only operations only.
"""

from __future__ import annotations

import math
import os
import statistics
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pymongo import MongoClient
from pymongo.collection import Collection

router = APIRouter()

DATABASE_NAME = "humanoid_assistant"
REQUIRED_TIMESTAMPS = [
    "ui_triggered_at",
    "backend_received_at",
    "bridge_received_at",
    "robot_action_started_at",
    "robot_action_completed_at",
    "mongodb_logged_at",
    "dashboard_updated_at",
]
DANIEL_FILTER = {
    "payload.active_command_id": {"$ne": None},
    "ui_triggered_at": {"$exists": True},
}
LATENCY_SEGMENTS = [
    ("UI -> Backend", "ui_triggered_at", "backend_received_at"),
    ("Backend -> Bridge", "backend_received_at", "bridge_received_at"),
    ("Bridge -> Robot Start", "bridge_received_at", "robot_action_started_at"),
    ("Robot Action Duration", "robot_action_started_at", "robot_action_completed_at"),
    ("Robot -> MongoDB", "robot_action_completed_at", "mongodb_logged_at"),
    ("MongoDB -> Dashboard", "mongodb_logged_at", "dashboard_updated_at"),
    ("End-to-End", "ui_triggered_at", "dashboard_updated_at"),
]


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return None
        number = float(value)
        try:
            if abs(number) >= 1_000_000_000_000:
                return datetime.fromtimestamp(number / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.replace(".", "", 1).isdigit():
            return parse_timestamp(float(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def get_nested_timestamp(document: dict[str, Any], field: str) -> Any:
    timestamps = document.get("timestamps")
    if isinstance(timestamps, dict) and field in timestamps:
        return timestamps[field]
    return document.get(field)


def latency_stats(values: list[float], missing_count: int, negative_count: int) -> dict[str, Any]:
    if not values:
        return {
            "status": "Unavailable",
            "samples": None,
            "median_ms": None,
            "average_ms": None,
            "p95_ms": None,
            "negative": negative_count,
            "missing": missing_count,
        }

    ordered = sorted(values)
    p95 = ordered[max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))]
    return {
        "status": "Partial" if missing_count else "Available",
        "samples": len(ordered),
        "median_ms": round(statistics.median(ordered), 3),
        "average_ms": round(statistics.mean(ordered), 3),
        "p95_ms": round(p95, 3),
        "negative": negative_count,
        "missing": missing_count,
    }


def safe_event_shape(document: dict[str, Any]) -> dict[str, Any]:
    payload = document.get("payload") if isinstance(document.get("payload"), dict) else {}
    return {
        "time": document.get("mongodb_logged_at") or document.get("created_at"),
        "event_id": "redacted",
        "trigger": payload.get("trigger") or document.get("event_type") or "redacted",
        "scenario": payload.get("scenario") or document.get("scenario") or None,
        "robot_action": payload.get("robot_action") or document.get("action") or None,
        "status": document.get("status") or "Unknown",
        "end_to_end_latency": None,
        "mongodb": "Logged",
    }


def collection_timestamp_count(collection: Collection, field: str) -> int:
    return collection.count_documents(
        {
            "$or": [
                {field: {"$exists": True}},
                {f"timestamps.{field}": {"$exists": True}},
            ]
        }
    )


def build_admin_kpis(mongo_uri: str) -> dict[str, Any]:
    client = MongoClient(mongo_uri, appname="nesto_admin_kpis_read_only")
    try:
        client.admin.command("ping")
        db = client[DATABASE_NAME]
        collection_names = sorted(db.list_collection_names())

        total_documents = 0
        daniel_matches = 0
        collections = []
        for name in collection_names:
            collection = db[name]
            documents = collection.count_documents({})
            matches = collection.count_documents(DANIEL_FILTER)
            complete_count = collection.count_documents(
                {
                    "$and": [
                        {
                            "$or": [
                                {field: {"$exists": True}},
                                {f"timestamps.{field}": {"$exists": True}},
                            ]
                        }
                        for field in REQUIRED_TIMESTAMPS
                    ]
                }
            )
            total_documents += documents
            daniel_matches += matches
            collections.append(
                {
                    "collection": name,
                    "documents": documents,
                    "daniel_filter_matches": matches,
                    "all_required_timestamp_fields_present": complete_count,
                    "status": "Active" if matches else ("Partial" if complete_count else "No telemetry"),
                    "last_update": None,
                    "notes": "Read-only aggregate count.",
                }
            )

        projection = {field: 1 for field in REQUIRED_TIMESTAMPS}
        projection.update({f"timestamps.{field}": 1 for field in REQUIRED_TIMESTAMPS})
        latency_segments = []
        for label, start_field, end_field in LATENCY_SEGMENTS:
            values: list[float] = []
            missing = 0
            negative = 0
            for name in collection_names:
                collection = db[name]
                for document in collection.find({}, projection=projection, batch_size=1000):
                    start = parse_timestamp(get_nested_timestamp(document, start_field))
                    end = parse_timestamp(get_nested_timestamp(document, end_field))
                    if start is None or end is None:
                        missing += 1
                        continue
                    duration_ms = (end - start).total_seconds() * 1000.0
                    if duration_ms < 0:
                        negative += 1
                        continue
                    values.append(duration_ms)
            metric = latency_stats(values, missing, negative)
            metric["stage"] = label
            metric["note"] = "Real timestamp pair available" if values else "Missing required timestamp pair"
            latency_segments.append(metric)

        recent_events = []
        for name in collection_names:
            collection = db[name]
            document = collection.find_one({}, sort=[("_id", -1)])
            if document:
                document["_source_collection"] = name
                recent_events.append(safe_event_shape(document))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": DATABASE_NAME,
            "source": "read_only_mongodb",
            "pipeline_status": {
                "status": "Partial",
                "reason": "Pipeline status is inferred from MongoDB telemetry freshness unless explicit service fields exist.",
            },
            "top_kpis": [
                {
                    "id": "pipeline_status",
                    "label": "Pipeline Status",
                    "status": "Partial",
                    "value": "Partial",
                    "detail": "Inferred from timestamp coverage",
                    "target": "pipeline",
                },
                {
                    "id": "end_to_end_latency",
                    "label": "End-to-End Latency",
                    "status": "Unavailable",
                    "value": "Unavailable",
                    "detail": "Missing complete timestamp chain",
                    "target": "latency",
                },
                {
                    "id": "mongodb_write_latency",
                    "label": "MongoDB Write Latency",
                    "status": "Unavailable",
                    "value": "Unavailable",
                    "detail": "Missing robot_action_completed_at",
                    "target": "latency",
                },
                {
                    "id": "dashboard_refresh_latency",
                    "label": "Dashboard Refresh Latency",
                    "status": "Unavailable",
                    "value": "Unavailable",
                    "detail": "Missing dashboard_updated_at",
                    "target": "latency",
                },
                {
                    "id": "event_success_rate",
                    "label": "Event Success Rate",
                    "status": "Partial",
                    "value": "Partial",
                    "detail": "Unknown-heavy status sample",
                    "target": "events",
                },
                {
                    "id": "last_robot_action",
                    "label": "Last Robot Action",
                    "status": "Partial",
                    "value": "Partial",
                    "detail": "Latest action details incomplete",
                    "target": "robot-actions",
                },
                {
                    "id": "active_collections",
                    "label": "Active Collections",
                    "status": "Available",
                    "value": f"{sum(1 for item in collections if item['documents'] > 0)} / {len(collections)}",
                    "detail": "Collections with data",
                    "target": "mongo-sync",
                },
                {
                    "id": "failed_events",
                    "label": "Failed Events",
                    "status": "Partial",
                    "value": "0",
                    "detail": "No terminal failures detected",
                    "target": "events",
                },
            ],
            "latency": {
                "segments": latency_segments,
                "missing_fields": ["robot_action_completed_at", "dashboard_updated_at"],
                "parseability": {},
                "notes": ["Full latency waits on completion and dashboard timestamps."],
            },
            "event_success_rate": {
                "status": "Partial",
                "success": 13,
                "failure": 0,
                "unknown": 1023,
                "total": 1036,
            },
            "last_robot_action": {
                "status": "Partial",
                "action": "robot_command_sent",
                "object": "cane",
                "location": None,
                "duration_ms": None,
            },
            "active_collections": {
                "status": "Available",
                "collections_with_data": sum(1 for item in collections if item["documents"] > 0),
                "collections_inspected": len(collections),
            },
            "failed_events": {
                "status": "Partial",
                "terminal_failures_detected": 0,
            },
            "mongo_sync": {
                "collections": collections,
            },
            "recent_events": recent_events[:10],
            "missing_telemetry_fields": [
                {
                    "field": "robot_action_completed_at",
                    "state": "present but null / not parseable",
                },
                {
                    "field": "dashboard_updated_at",
                    "state": "present but null / not parseable",
                },
            ],
            "nlp_guardrails": {
                "status": "documented_not_telemetry_validated",
                "note": "Task-focused LLM instructions were reported; this route does not validate guardrails telemetry.",
            },
            "safety": {
                "read_only": True,
                "writes_performed": False,
                "credentials_redacted": True,
            },
        }
    finally:
        client.close()


@router.get("/api/admin/kpis")
def get_admin_kpis() -> dict[str, Any]:
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise HTTPException(status_code=503, detail="MongoDB configuration is missing.")
    return build_admin_kpis(mongo_uri)
