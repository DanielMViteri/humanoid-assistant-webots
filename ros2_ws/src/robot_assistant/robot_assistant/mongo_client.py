"""MongoDB Atlas client for humanoid assistant feature events."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from event_schema import COLLECTIONS, REQUIRED_FIELDS, collection_for_event, current_epoch_ms, validate_event


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATABASE = "humanoid_assistant"
DEFAULT_TIMEOUT_MS = 15000
TELEMETRY_TIMING_FIELDS = (
    "ui_triggered_at",
    "backend_received_at",
    "bridge_received_at",
    "robot_action_started_at",
    "robot_action_completed_at",
    "mongodb_logged_at",
    "dashboard_updated_at",
)


def load_dotenv(path: Path | None = None) -> None:
    """Load key=value pairs from a local .env file without adding a dependency."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def mongo_error_hint(error: Exception) -> str:
    """Return a short operator-friendly MongoDB troubleshooting hint."""
    message = str(error)
    if "ServerSelectionTimeoutError" in error.__class__.__name__ or "No replica set members found" in message:
        return (
            "MongoDB Atlas was reachable by URI parsing, but no server became available before the timeout. "
            "Check your internet connection, Atlas network access/IP allowlist, VPN/firewall rules, and retry."
        )
    if "Authentication failed" in message:
        return "MongoDB authentication failed. Check the username/password in MONGODB_URI."
    if "MONGODB_URI is required" in message:
        return "MONGODB_URI is missing. Add it to .env."
    return "MongoDB operation failed. Check .env, Atlas status, and local network access."


class MongoEventClient:
    """Small wrapper around MongoDB collection routing and health checks."""

    def __init__(self, uri: str, database_name: str = DEFAULT_DATABASE, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise RuntimeError("pymongo is not installed. Run: pip install \"pymongo[srv]\"") from exc

        if not uri:
            raise ValueError("MONGODB_URI is required. Add it to .env or your shell environment.")

        self.database_name = database_name
        self.client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        self.db = self.client[database_name]

    @classmethod
    def from_env(cls) -> "MongoEventClient":
        load_dotenv()
        timeout_ms = int(os.getenv("MONGODB_TIMEOUT_MS", str(DEFAULT_TIMEOUT_MS)))
        return cls(
            uri=os.getenv("MONGODB_URI", ""),
            database_name=os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE),
            timeout_ms=timeout_ms,
        )

    def ping(self) -> bool:
        self.client.admin.command("ping")
        return True

    def insert_event(self, event: dict[str, Any]):
        errors = validate_event(event)
        if errors:
            raise ValueError("; ".join(errors))

        collection_name = collection_for_event(event["event_type"])
        document = dict(event)
        logged_at = current_epoch_ms()
        document["ingested_at"] = logged_at
        payload = document.get("payload")
        if isinstance(payload, dict):
            document["payload"] = dict(payload)
            payload = document["payload"]
        else:
            payload = {}
            document["payload"] = payload
        for field in TELEMETRY_TIMING_FIELDS:
            document.setdefault(field, payload.get(field))
            payload.setdefault(field, document.get(field))
        document["mongodb_logged_at"] = logged_at
        payload["mongodb_logged_at"] = logged_at
        return self.db[collection_name].insert_one(document)

    def insert_events(self, events: list[dict[str, Any]]) -> dict[str, int]:
        inserted_counts: Counter[str] = Counter()
        for event in events:
            result = self.insert_event(event)
            if result.inserted_id:
                inserted_counts[collection_for_event(event["event_type"])] += 1
        return dict(inserted_counts)

    def collection_counts(self) -> dict[str, int]:
        return {name: self.db[name].count_documents({}) for name in COLLECTIONS}

    def latest_timestamps(self) -> dict[str, int | None]:
        latest: dict[str, int | None] = {}
        for name in COLLECTIONS:
            document = self.db[name].find_one({}, sort=[("timestamp", -1)], projection={"timestamp": 1})
            latest[name] = document.get("timestamp") if document else None
        return latest

    def missing_required_field_counts(self) -> dict[str, int]:
        missing_query = {
            "$or": [{field: {"$exists": False}} for field in REQUIRED_FIELDS]
            + [{field: None} for field in REQUIRED_FIELDS]
        }
        return {name: self.db[name].count_documents(missing_query) for name in COLLECTIONS}
