"""
Read-only MongoDB KPI analysis for the NESTO Care telemetry dashboard.

This script inspects the humanoid_assistant database, generates field and
collection inventories, evaluates KPI availability, and writes dashboard-ready
analysis outputs under analytics/output.

It intentionally performs no database writes.
"""

from __future__ import annotations

import ast
import csv
import datetime as dt
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


DATABASE_NAME = "humanoid_assistant"
MAX_SAMPLE_SIZE = 500
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

REQUIRED_TIMESTAMP_FIELDS = [
    "timestamps.ui_triggered_at",
    "timestamps.backend_received_at",
    "timestamps.bridge_received_at",
    "timestamps.robot_action_started_at",
    "timestamps.robot_action_completed_at",
    "timestamps.mongodb_logged_at",
    "timestamps.dashboard_updated_at",
]

REQUIRED_LATENCY_FIELDS = [
    "latency_ms.ui_to_backend",
    "latency_ms.backend_to_bridge",
    "latency_ms.bridge_to_robot_start",
    "latency_ms.robot_action_duration",
    "latency_ms.robot_to_mongodb",
    "latency_ms.mongodb_to_dashboard",
    "latency_ms.end_to_end",
]

LATENCY_ALIASES = [
    "latency_ms",
    "response_time_ms",
    "processing_time_ms",
    "duration_ms",
]

TIMESTAMP_ALIASES = [
    "created_at",
    "completed_at",
    "started_at",
    "received_at",
    "logged_at",
    "updated_at",
    "timestamp",
    "time",
]

IDENTIFIER_HINTS = [
    "event_id",
    "session_id",
    "robot_id",
    "patient_id",
    "user_id",
]

CATEGORY_HINTS = [
    "event_type",
    "scenario",
    "status",
    "severity",
    "trigger_type",
    "source",
    "source_module",
    "object_name",
    "room",
    "location",
    "detected_intent",
]

SUCCESS_STATUSES = {
    "success",
    "succeeded",
    "complete",
    "completed",
    "done",
    "passed",
    "resolved",
    "normal",
    "connected",
    "online",
    "taken",
    "found",
    "ok",
}

FAILURE_STATUSES = {
    "failed",
    "failure",
    "error",
    "timeout",
    "timed out",
    "rejected",
    "missed",
    "unavailable",
    "offline",
    "critical",
}

PENDING_STATUSES = {
    "pending",
    "waiting",
    "queued",
    "open",
    "in progress",
    "in_progress",
    "started",
    "running",
}

SENSITIVE_FIELD_RE = re.compile(
    r"(password|passcode|secret|token|api[_-]?key|authorization|auth|hash|email|phone|mobile|address|uri|url|command)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")
SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._-]+|sk-[A-Za-z0-9._-]{16,}|AIza[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
VALIDATION_PHONE_RE = re.compile(r"(?<!\w)\+?\d{1,3}[\s().-]\d{2,4}[\s().-]\d{3,4}(?:[\s().-]\d{2,4})?(?!\w)")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    env_path = repo_root() / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except Exception:
        pass
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_only_safety_check() -> list[str]:
    source_path = Path(__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_parts = [
        ("insert", "one"),
        ("insert", "many"),
        ("update", "one"),
        ("update", "many"),
        ("replace", "one"),
        ("delete", "one"),
        ("delete", "many"),
        ("bulk", "write"),
        ("find", "one", "and", "update"),
        ("find", "one", "and", "delete"),
    ]
    forbidden_names = {"_".join(parts) for parts in forbidden_parts}
    forbidden_stages = {"$" + "out", "$" + "merge"}
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name in forbidden_names:
                findings.append(name)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in forbidden_stages:
                findings.append(node.value)
    return sorted(set(findings))


def connect_database():
    load_local_env()
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI or MONGO_URI is missing. Create a local .env before running analysis.")
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000)
    client.admin.command("ping")
    return client, client[DATABASE_NAME]


def flatten_document(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_document(child, name))
    elif isinstance(value, list):
        if prefix:
            out[prefix] = value
        for item in value[:3]:
            if isinstance(item, dict):
                out.update(flatten_document(item, f"{prefix}[]" if prefix else "[]"))
    else:
        if prefix:
            out[prefix] = value
    return out


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, dt.datetime):
        return "datetime"
    if isinstance(value, dt.date):
        return "date"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if value.__class__.__name__ == "ObjectId":
        return "objectid"
    return type(value).__name__


def sanitize_example(field: str, value: Any) -> str:
    if value is None:
        return ""
    if SENSITIVE_FIELD_RE.search(field):
        return "[REDACTED]"
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    text = json.dumps(value, default=str, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = LONG_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def parse_datetime(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        result = value
    elif isinstance(value, dt.date):
        result = dt.datetime.combine(value, dt.time.min)
    elif value.__class__.__name__ == "ObjectId" and hasattr(value, "generation_time"):
        result = value.generation_time
    elif isinstance(value, (int, float)):
        if value <= 0:
            return None
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            result = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
        except Exception:
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            result = dt.datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%H:%M:%S"):
                try:
                    parsed = dt.datetime.strptime(text, fmt)
                    if fmt == "%H:%M:%S":
                        today = dt.datetime.now(dt.timezone.utc).date()
                        parsed = dt.datetime.combine(today, parsed.time())
                    result = parsed
                    break
                except ValueError:
                    continue
            else:
                return None
    else:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)
    return result.astimezone(dt.timezone.utc)


def diff_ms(later: Any, earlier: Any) -> float | None:
    end = parse_datetime(later)
    start = parse_datetime(earlier)
    if not end or not start:
        return None
    value = (end - start).total_seconds() * 1000
    return value if value >= 0 else None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def stats(values: Iterable[float]) -> dict[str, float] | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) >= 0]
    if not clean:
        return None
    return {
        "latest": round(clean[-1], 3),
        "average": round(mean(clean), 3),
        "minimum": round(min(clean), 3),
        "maximum": round(max(clean), 3),
        "p50": round(percentile(clean, 0.50) or 0, 3),
        "p95": round(percentile(clean, 0.95) or 0, 3),
        "p99": round(percentile(clean, 0.99) or 0, 3),
        "sample_size": len(clean),
    }


def classify_freshness(latest: dt.datetime | None, now: dt.datetime | None = None, count: int = 0) -> str:
    if count == 0:
        return "empty"
    if latest is None:
        return "unknown"
    now = now or dt.datetime.now(dt.timezone.utc)
    age_minutes = (now - latest).total_seconds() / 60
    if age_minutes <= 5:
        return "active"
    if age_minutes <= 30:
        return "delayed"
    return "stale"


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def classify_status(value: Any) -> str:
    status = normalize_status(value).replace("_", " ")
    if status in SUCCESS_STATUSES:
        return "success"
    if status in FAILURE_STATUSES:
        return "failure"
    if status in PENDING_STATUSES:
        return "pending"
    return "unknown"


def success_rate(statuses: Iterable[Any]) -> dict[str, Any]:
    counts = Counter(classify_status(status) for status in statuses)
    terminal = counts["success"] + counts["failure"]
    rate = round((counts["success"] / terminal) * 100, 2) if terminal else None
    return {
        "success": counts["success"],
        "failure": counts["failure"],
        "pending": counts["pending"],
        "unknown": counts["unknown"],
        "terminal_events": terminal,
        "success_rate_percent": rate,
    }


def find_field(flat: dict[str, Any], aliases: Iterable[str]) -> tuple[str, Any] | tuple[None, None]:
    lower_to_actual = {key.lower(): key for key in flat}
    for alias in aliases:
        alias_lower = alias.lower()
        if alias_lower in lower_to_actual:
            actual = lower_to_actual[alias_lower]
            return actual, flat[actual]
    for alias in aliases:
        alias_lower = alias.lower()
        for key in flat:
            key_lower = key.lower()
            if key_lower.endswith("." + alias_lower) or key_lower == alias_lower:
                return key, flat[key]
    return None, None


def numeric_latency_from_doc(flat: dict[str, Any], aliases: Iterable[str]) -> tuple[str, float] | tuple[None, None]:
    for alias in aliases:
        field, value = find_field(flat, [alias])
        if field and isinstance(value, (int, float)) and value >= 0:
            return field, float(value)
    return None, None


def latency_breakdown(flat: dict[str, Any]) -> dict[str, float | None]:
    fields = {
        "ui_to_backend": (
            "timestamps.backend_received_at",
            "timestamps.ui_triggered_at",
            ["latency_ms.ui_to_backend"],
        ),
        "backend_to_bridge": (
            "timestamps.bridge_received_at",
            "timestamps.backend_received_at",
            ["latency_ms.backend_to_bridge"],
        ),
        "bridge_to_robot_start": (
            "timestamps.robot_action_started_at",
            "timestamps.bridge_received_at",
            ["latency_ms.bridge_to_robot_start"],
        ),
        "robot_action_duration": (
            "timestamps.robot_action_completed_at",
            "timestamps.robot_action_started_at",
            ["latency_ms.robot_action_duration", "duration_ms"],
        ),
        "robot_to_mongodb": (
            "timestamps.mongodb_logged_at",
            "timestamps.robot_action_completed_at",
            ["latency_ms.robot_to_mongodb"],
        ),
        "mongodb_to_dashboard": (
            "timestamps.dashboard_updated_at",
            "timestamps.mongodb_logged_at",
            ["latency_ms.mongodb_to_dashboard"],
        ),
        "end_to_end": (
            "timestamps.dashboard_updated_at",
            "timestamps.ui_triggered_at",
            ["latency_ms.end_to_end"],
        ),
    }
    result: dict[str, float | None] = {}
    for name, (later_field, earlier_field, aliases) in fields.items():
        _, stored = numeric_latency_from_doc(flat, aliases)
        if stored is not None:
            result[name] = stored
            continue
        _, later = find_field(flat, [later_field])
        _, earlier = find_field(flat, [earlier_field])
        result[name] = diff_ms(later, earlier)
    return result


def choose_timestamp_field(samples: list[dict[str, Any]]) -> tuple[str, list[dt.datetime]]:
    candidates: dict[str, list[dt.datetime]] = defaultdict(list)
    for doc in samples:
        flat = flatten_document(doc)
        for field, value in flat.items():
            field_lower = field.lower()
            if field == "_id" or any(marker in field_lower for marker in TIMESTAMP_ALIASES) or field_lower.startswith("timestamps."):
                parsed = parse_datetime(value)
                if parsed:
                    candidates[field].append(parsed)
        if "_id" not in flat and "_id" in doc:
            parsed = parse_datetime(doc["_id"])
            if parsed:
                candidates["_id"].append(parsed)
    if not candidates:
        return "", []
    best_field = max(candidates, key=lambda field: (len(candidates[field]), field != "_id"))
    return best_field, candidates[best_field]


def duplicate_event_ids(collection) -> int:
    pipeline = [
        {"$match": {"event_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$event_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ]
    rows = list(collection.aggregate(pipeline, allowDiskUse=False))
    return int(rows[0]["duplicates"]) if rows else 0


def analyse_collections(db) -> dict[str, Any]:
    collections = sorted(db.list_collection_names())
    inventory_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    samples_by_collection: dict[str, list[dict[str, Any]]] = {}
    field_index: dict[str, dict[str, dict[str, Any]]] = {}
    duplicate_counts: dict[str, int] = {}
    now = dt.datetime.now(dt.timezone.utc)

    for name in collections:
        collection = db[name]
        count = int(collection.count_documents({}))
        samples = list(collection.find({}).sort("_id", -1).limit(MAX_SAMPLE_SIZE))
        samples_by_collection[name] = samples
        sample_size = len(samples)
        timestamp_field, timestamps = choose_timestamp_field(samples)
        earliest = min(timestamps).isoformat() if timestamps else ""
        latest_dt = max(timestamps) if timestamps else None
        latest = latest_dt.isoformat() if latest_dt else ""
        freshness = classify_freshness(latest_dt, now=now, count=count)
        try:
            duplicate_counts[name] = duplicate_event_ids(collection)
        except Exception:
            duplicate_counts[name] = 0

        inventory_rows.append(
            {
                "collection": name,
                "document_count": count,
                "freshness": freshness,
                "earliest_timestamp": earliest,
                "latest_timestamp": latest,
                "detected_timestamp_field": timestamp_field,
                "sample_size": sample_size,
                "duplicate_event_id_values": duplicate_counts[name],
            }
        )

        field_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"present": 0, "types": Counter(), "example": ""})
        for doc in samples:
            flat = flatten_document(doc)
            if "_id" in doc and "_id" not in flat:
                flat["_id"] = doc["_id"]
            for field, value in flat.items():
                stat = field_stats[field]
                stat["present"] += 1
                stat["types"][type_name(value)] += 1
                if not stat["example"]:
                    stat["example"] = sanitize_example(field, value)
        field_index[name] = field_stats
        for field in sorted(field_stats):
            stat = field_stats[field]
            coverage = round((stat["present"] / sample_size) * 100, 2) if sample_size else 0.0
            field_rows.append(
                {
                    "collection": name,
                    "field": field,
                    "types": "|".join(sorted(stat["types"].keys())),
                    "coverage_percent": coverage,
                    "missing_percent": round(100 - coverage, 2),
                    "present_in_sample": stat["present"],
                    "sample_size": sample_size,
                    "sanitized_example": stat["example"],
                }
            )

    return {
        "collections": collections,
        "inventory_rows": inventory_rows,
        "field_rows": field_rows,
        "samples_by_collection": samples_by_collection,
        "field_index": field_index,
        "duplicate_counts": duplicate_counts,
    }


def all_sample_documents(samples_by_collection: dict[str, list[dict[str, Any]]]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    rows = []
    for collection, docs in samples_by_collection.items():
        for doc in docs:
            flat = flatten_document(doc)
            if "_id" in doc and "_id" not in flat:
                flat["_id"] = doc["_id"]
            rows.append((collection, doc, flat))
    return rows


def field_exists(field_index: dict[str, dict[str, dict[str, Any]]], field: str) -> bool:
    return any(field in fields for fields in field_index.values())


def collect_latency_values(all_docs: list[tuple[str, dict[str, Any], dict[str, Any]]], key: str) -> tuple[list[float], list[str]]:
    values: list[float] = []
    sources: set[str] = set()
    for collection, _, flat in all_docs:
        breakdown = latency_breakdown(flat)
        value = breakdown.get(key)
        if value is not None:
            values.append(float(value))
            sources.add(collection)
    return values, sorted(sources)


def latest_doc_timestamp(flat: dict[str, Any]) -> dt.datetime | None:
    best: dt.datetime | None = None
    for field, value in flat.items():
        field_lower = field.lower()
        if field == "_id" or any(marker in field_lower for marker in TIMESTAMP_ALIASES) or field_lower.startswith("timestamps."):
            parsed = parse_datetime(value)
            if parsed and (best is None or parsed > best):
                best = parsed
    return best


def evaluate_kpis(analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    field_index = analysis["field_index"]
    inventory_rows = analysis["inventory_rows"]
    samples_by_collection = analysis["samples_by_collection"]
    docs = all_sample_documents(samples_by_collection)
    now = dt.datetime.now(dt.timezone.utc)
    kpi_rows: list[dict[str, Any]] = []
    snapshot: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "database": DATABASE_NAME,
        "kpis": {},
        "pipeline_health": {},
        "throughput": {},
        "robot_actions": {},
        "collection_freshness": {row["collection"]: row["freshness"] for row in inventory_rows},
    }

    def add_kpi(
        name: str,
        availability: str,
        collections: list[str],
        required_fields: list[str],
        found_fields: list[str],
        formula: str,
        value: Any,
        reason: str,
        visual: str,
        refresh: str,
    ) -> None:
        row = {
            "kpi": name,
            "available_now": availability,
            "source_collection": "|".join(collections) if collections else "",
            "required_fields": "|".join(required_fields),
            "fields_actually_found": "|".join(found_fields),
            "formula": formula,
            "current_value": json.dumps(value, default=str, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value or ""),
            "reason_unavailable": reason,
            "suggested_visual": visual,
            "recommended_refresh_frequency": refresh,
        }
        kpi_rows.append(row)
        snapshot["kpis"][name] = {
            "availability": availability,
            "value": value,
            "source_collections": collections,
            "fields": found_fields,
            "reason": reason,
        }

    latest_events: list[tuple[dt.datetime, str, dict[str, Any]]] = []
    status_values: list[Any] = []
    failed_events = []
    event_type_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for collection, _, flat in docs:
        ts = latest_doc_timestamp(flat)
        if ts:
            latest_events.append((ts, collection, flat))
        status_field, status_value = find_field(flat, ["status", "event_status", "result.status", "outcome"])
        if status_field:
            status_values.append(status_value)
            if classify_status(status_value) == "failure":
                failed_events.append((collection, flat))
        event_field, event_value = find_field(flat, ["event_type", "scenario", "action", "robot_action", "detected_intent"])
        if event_field and event_value:
            event_type_counts[str(event_value)] += 1
        source_field, source_value = find_field(flat, ["source_module", "source", "module"])
        if source_field and source_value:
            source_counts[str(source_value)] += 1

    latest_events.sort(key=lambda item: item[0], reverse=True)
    latest_ts = latest_events[0][0] if latest_events else None
    pipeline_value = "unknown"
    if latest_ts:
        pipeline_value = classify_freshness(latest_ts, now=now, count=1)
    add_kpi(
        "Pipeline Status",
        "partial" if latest_ts else "no",
        sorted({item[1] for item in latest_events[:10]}),
        ["recent timestamp", "status/source fields"],
        ["timestamp"] if latest_ts else [],
        "Infer freshness from latest MongoDB event timestamp. MongoDB alone cannot prove live service status.",
        pipeline_value,
        "" if latest_ts else "No timestamped events were found.",
        "Status pill with last event time",
        "15 seconds",
    )

    latency_requirements = {
        "End-to-End Latency": ("end_to_end", ["timestamps.ui_triggered_at", "timestamps.dashboard_updated_at", "latency_ms.end_to_end"]),
        "MongoDB Write Latency": ("robot_to_mongodb", ["timestamps.robot_action_completed_at", "timestamps.mongodb_logged_at", "latency_ms.robot_to_mongodb"]),
        "Dashboard Refresh Latency": ("mongodb_to_dashboard", ["timestamps.mongodb_logged_at", "timestamps.dashboard_updated_at", "latency_ms.mongodb_to_dashboard"]),
    }
    for display_name, (key, required_fields) in latency_requirements.items():
        values, sources = collect_latency_values(docs, key)
        found_fields = [field for field in required_fields if field_exists(field_index, field)]
        stat = stats(values)
        reason = "" if stat else "Reliable latency cannot currently be calculated because the required pipeline timestamps or latency fields were not found."
        add_kpi(
            display_name,
            "yes" if stat and len(found_fields) == len(required_fields) else ("partial" if stat else "no"),
            sources,
            required_fields,
            found_fields,
            f"{key} latency statistics from explicit latency field or timestamp difference",
            stat,
            reason,
            "Latency KPI card with sparkline",
            "5 seconds",
        )

    rate = success_rate(status_values)
    found_status_fields = sorted(
        {
            field
            for fields in field_index.values()
            for field in fields
            if field.lower().endswith("status") or field.lower() in {"status", "outcome"}
        }
    )
    add_kpi(
        "Event Success Rate",
        "yes" if rate["terminal_events"] else ("partial" if status_values else "no"),
        sorted(samples_by_collection.keys()),
        ["status"],
        found_status_fields,
        "successful completed events / total terminal events * 100",
        rate,
        "" if rate["terminal_events"] else "No terminal success/failure status values were found.",
        "Percentage KPI with success/failure split",
        "10 seconds",
    )

    latest_action = None
    action_fields_found: set[str] = set()
    for ts, collection, flat in latest_events:
        action_field, action_value = find_field(
            flat,
            ["robot_action", "action", "scenario", "event_type", "detected_intent", "object_name"],
        )
        if action_field and action_value:
            action_fields_found.add(action_field)
            status_field, status_value = find_field(flat, ["status", "event_status", "result.status"])
            object_field, object_value = find_field(flat, ["object_name", "object_detected", "target_object"])
            room_field, room_value = find_field(flat, ["room", "location", "object_location"])
            latest_action = {
                "time": ts.isoformat(),
                "collection": collection,
                "action": sanitize_example(action_field, action_value),
                "status": sanitize_example(status_field or "status", status_value) if status_field else "",
                "object": sanitize_example(object_field or "object", object_value) if object_field else "",
                "location": sanitize_example(room_field or "location", room_value) if room_field else "",
            }
            break
    add_kpi(
        "Last Robot Action",
        "partial" if latest_action else "no",
        [latest_action["collection"]] if latest_action else [],
        ["robot_action/action/scenario/event_type", "timestamp", "status"],
        sorted(action_fields_found),
        "Latest timestamped event containing an action-like field",
        latest_action,
        "" if latest_action else "No timestamped robot action field was found in sampled documents.",
        "Recent action card",
        "5 seconds",
    )

    freshness_counts = Counter(row["freshness"] for row in inventory_rows)
    add_kpi(
        "Active Collections",
        "yes" if inventory_rows else "no",
        sorted(samples_by_collection.keys()),
        ["document count", "latest timestamp"],
        ["document_count", "latest_timestamp"],
        "active <=5m, delayed 5-30m, stale >30m, empty = zero records",
        dict(freshness_counts),
        "" if inventory_rows else "No collections were found.",
        "Collection freshness bar",
        "30 seconds",
    )

    add_kpi(
        "Failed Events",
        "yes" if failed_events else ("partial" if status_values else "no"),
        sorted({collection for collection, _ in failed_events}) if failed_events else sorted(samples_by_collection.keys()),
        ["status/error fields"],
        found_status_fields,
        "Count sampled terminal failure statuses and explicit error values",
        {"failed_events_in_sample": len(failed_events), "sampled_status_values": len(status_values)},
        "" if status_values else "No status or error fields were found to classify failed events.",
        "Alert count with recent failure list",
        "10 seconds",
    )

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    events_today = [event for event in latest_events if event[0] >= today_start]
    events_last_10 = [event for event in latest_events if (now - event[0]).total_seconds() <= 600]
    snapshot["throughput"] = {
        "total_events_today_sampled": len(events_today),
        "events_last_10_minutes_sampled": len(events_last_10),
        "success_rate": rate,
        "events_grouped_by_event_type": dict(event_type_counts.most_common(20)),
        "events_grouped_by_source_module": dict(source_counts.most_common(20)),
        "status_classification": {
            "success": sorted(SUCCESS_STATUSES),
            "failure": sorted(FAILURE_STATUSES),
            "pending": sorted(PENDING_STATUSES),
        },
    }
    if latest_ts:
        snapshot["pipeline_health"]["last_event_time"] = latest_ts.isoformat()
    snapshot["pipeline_health"].update(
        {
            "bridge_status": "inferred from recent bridge events only if present",
            "webots_status": "inferred from explicit Webots status records or recent Webots events",
            "mongodb_status": "connected during analysis",
            "dashboard_sync": "requires dashboard_updated_at or equivalent",
            "voice_pipeline_status": "requires explicit voice/OpenAI/ElevenLabs status or recent voice pipeline events",
        }
    )
    snapshot["robot_actions"] = analyse_robot_actions(latest_events)
    return kpi_rows, snapshot


def analyse_robot_actions(latest_events: list[tuple[dt.datetime, str, dict[str, Any]]]) -> dict[str, Any]:
    targets = {
        "Find My Cane": ["cane", "find_cane", "find my cane"],
        "Find My Medicine": ["medicine", "find_medicine", "medicine box"],
        "Mood Check": ["mood", "emotion", "deepface"],
        "Voice Command": ["voice", "conversation", "speech", "openai", "elevenlabs"],
        "Robot Movement": ["movement", "move", "navigation", "path"],
        "Object Detection": ["object", "yolo", "detection", "detected"],
    }
    result: dict[str, Any] = {}
    for label, keywords in targets.items():
        match = None
        for ts, collection, flat in latest_events:
            searchable = " ".join(f"{key} {value}" for key, value in flat.items()).lower()
            if any(keyword in searchable for keyword in keywords):
                status_field, status_value = find_field(flat, ["status", "event_status", "result.status"])
                object_field, object_value = find_field(flat, ["object_name", "object_detected", "target_object"])
                location_field, location_value = find_field(flat, ["room", "location", "object_location"])
                mood_field, mood_value = find_field(flat, ["mood", "emotion", "deepface_result", "detected_emotion"])
                duration_field, duration_value = numeric_latency_from_doc(flat, ["duration_ms", "latency_ms.robot_action_duration"])
                match = {
                    "collection": collection,
                    "latest_time": ts.isoformat(),
                    "latest_status": sanitize_example(status_field or "status", status_value) if status_field else "",
                    "action_duration_ms": duration_value,
                    "duration_field": duration_field or "",
                    "object_detected": sanitize_example(object_field or "object", object_value) if object_field else "",
                    "object_location": sanitize_example(location_field or "location", location_value) if location_field else "",
                    "last_mood_or_deepface_result": sanitize_example(mood_field or "mood", mood_value) if mood_field else "",
                    "webots_status": "inferred from event record; explicit Webots status required for live status",
                }
                break
        result[label] = match or {"availability": "not found in sampled MongoDB records"}
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=True), encoding="utf-8")


def write_missing_fields(path: Path, analysis: dict[str, Any], kpi_rows: list[dict[str, Any]]) -> int:
    field_index = analysis["field_index"]
    required = REQUIRED_TIMESTAMP_FIELDS + REQUIRED_LATENCY_FIELDS
    missing = [field for field in required if not field_exists(field_index, field)]
    alias_fields = [
        alias
        for alias in LATENCY_ALIASES + TIMESTAMP_ALIASES
        if any(alias.lower() in field.lower() for fields in field_index.values() for field in fields)
    ]
    unavailable = [row for row in kpi_rows if row["available_now"] == "no"]
    text = [
        "# Missing Telemetry Fields",
        "",
        "MongoDB was treated as the source of truth. Missing fields below were not found in sampled records.",
        "",
        "## Exact Missing Required Fields",
    ]
    text.extend(f"- `{field}`" for field in missing)
    if not missing:
        text.append("- None detected.")
    text.extend(
        [
            "",
            "## Alias Fields Found",
        ]
    )
    text.extend(f"- `{field}`" for field in sorted(set(alias_fields))) if alias_fields else text.append("- None detected.")
    text.extend(["", "## Unavailable KPI Reasons"])
    for row in unavailable:
        text.append(f"- **{row['kpi']}**: {row['reason_unavailable']}")
    text.extend(
        [
            "",
            "## Recommended Telemetry Event Schema",
            "",
            "```json",
            json.dumps(
                {
                    "event_id": "uuid",
                    "session_id": "uuid",
                    "robot_id": "H1",
                    "patient_id": "elderly_user_01",
                    "user_id": "authenticated_user_id",
                    "event_type": "voice_command | robot_action | object_detection | medicine | mood_check | movement",
                    "scenario": "find_my_cane | find_my_medicine | mood_check | take_medication | emergency",
                    "trigger_type": "ui_button | voice | scheduler | webots_sensor",
                    "source_module": "dashboard | fastapi | kafka_bridge | webots | robot_controller",
                    "status": "pending | completed | failed",
                    "severity": "low | medium | high | critical",
                    "object_name": "cane",
                    "room": "Living Room",
                    "detected_intent": "find_cane",
                    "timestamps": {
                        "ui_triggered_at": "ISO-8601",
                        "backend_received_at": "ISO-8601",
                        "bridge_received_at": "ISO-8601",
                        "robot_action_started_at": "ISO-8601",
                        "robot_action_completed_at": "ISO-8601",
                        "mongodb_logged_at": "ISO-8601",
                        "dashboard_updated_at": "ISO-8601",
                    },
                    "latency_ms": {
                        "ui_to_backend": 0,
                        "backend_to_bridge": 0,
                        "bridge_to_robot_start": 0,
                        "robot_action_duration": 0,
                        "robot_to_mongodb": 0,
                        "mongodb_to_dashboard": 0,
                        "end_to_end": 0,
                    },
                    "error": {"message": "", "code": ""},
                },
                indent=2,
            ),
            "```",
        ]
    )
    path.write_text("\n".join(text), encoding="utf-8")
    return len(missing)


def write_dashboard_spec(path: Path) -> None:
    text = """# Telemetry Dashboard Specification

Use the existing NESTO design palette: warm cream background, dark forest green headings, sage/mint accents, white cards, and green/yellow/red/gray status indicators.

## 1. Pipeline Health Overview

Cards: Bridge Status, Webots Status, MongoDB Status, Dashboard Sync, Voice Pipeline Status, Last Event Time.

Rule: MongoDB can show evidence and freshness, but it cannot prove a live service is running unless explicit status events exist.

## 2. Latency KPIs

Cards: End-to-End Latency, MongoDB Write Latency, Dashboard Refresh Latency, plus optional UI-to-Backend, Backend-to-Bridge, Bridge-to-Robot, Robot Action Duration, Robot-to-MongoDB.

Show latest, average, min, max, p50, p95, p99 when valid timestamp pairs or numeric latency fields exist. If unavailable, show the exact missing-field reason.

## 3. Event Throughput and Success Rate

Cards: Total Events Today, Events Last 10 Minutes, Success Rate, Failed Events, Pending Events, Average Events Per Minute.

Charts: events grouped by event type and source module.

## 4. Robot Action Status

Cards: Find My Cane, Find My Medicine, Mood Check, Voice Command, Robot Movement, Object Detection.

Each card should show latest action, status, action duration, object detected, object location, latest mood/DeepFace result, and Webots status evidence.

## 5. MongoDB Sync Monitor

Cards: Connection Availability, Latest Insert Time, Active Collections, Collections With No Recent Data, Latest Event ID, Failed Write Events, Average Write Latency, Collection Freshness.

Freshness: active <= 5 minutes, delayed 5-30 minutes, stale > 30 minutes, empty = zero records.

## 6. Recent Event Logs

Table columns:
- time
- event ID
- trigger type
- scenario
- detected intent
- robot action
- status
- end-to-end latency
- MongoDB status
- error message

Privacy: do not display full private user commands. Redact emails, phone numbers, addresses, tokens, passwords, hashes, and sensitive command text.
"""
    path.write_text(text, encoding="utf-8")


def validate_outputs(paths: list[Path]) -> None:
    secret_patterns = [EMAIL_RE, VALIDATION_PHONE_RE, SECRET_VALUE_RE]
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"Missing output file: {path}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".json":
            json.loads(text)
        for pattern in secret_patterns:
            if pattern.search(text):
                raise RuntimeError(f"Potential unredacted private data found in {path.name}")
        if "mongodb+srv://" in text or "mongodb://" in text:
            raise RuntimeError(f"Connection string leaked in {path.name}")


def main() -> None:
    safety_findings = read_only_safety_check()
    if safety_findings:
        raise RuntimeError(f"Read-only safety check failed: {', '.join(safety_findings)}")

    client, db = connect_database()
    try:
        analysis = analyse_collections(db)
        kpi_rows, snapshot = evaluate_kpis(analysis)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        collection_inventory = OUTPUT_DIR / "collection_inventory.csv"
        field_dictionary = OUTPUT_DIR / "field_dictionary.csv"
        kpi_matrix = OUTPUT_DIR / "kpi_availability_matrix.csv"
        current_snapshot = OUTPUT_DIR / "current_kpi_snapshot.json"
        missing_fields = OUTPUT_DIR / "missing_telemetry_fields.md"
        dashboard_spec = OUTPUT_DIR / "telemetry_dashboard_spec.md"

        write_csv(collection_inventory, analysis["inventory_rows"])
        write_csv(field_dictionary, analysis["field_rows"])
        write_csv(kpi_matrix, kpi_rows)
        write_json(current_snapshot, snapshot)
        missing_count = write_missing_fields(missing_fields, analysis, kpi_rows)
        write_dashboard_spec(dashboard_spec)

        output_paths = [
            collection_inventory,
            field_dictionary,
            kpi_matrix,
            current_snapshot,
            missing_fields,
            dashboard_spec,
        ]
        validate_outputs(output_paths)

        totals = Counter(row["available_now"] for row in kpi_rows)
        counts = {row["collection"]: row["document_count"] for row in analysis["inventory_rows"]}
        print(f"database connected: {DATABASE_NAME}")
        print(f"collections analysed: {len(analysis['collections'])}")
        print(f"document counts: {json.dumps(counts, sort_keys=True)}")
        print(
            "KPI availability totals: "
            f"available={totals.get('yes', 0)}, partial={totals.get('partial', 0)}, unavailable={totals.get('no', 0)}"
        )
        print(f"missing-field count: {missing_count}")
        print("generated output paths:")
        for path in output_paths:
            print(f"- {path.relative_to(repo_root())}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
