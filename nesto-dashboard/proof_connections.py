"""
Terminal proof for NESTO Care backend/dataflow handoff.

This script answers Daniel's integration questions without exposing secrets:
MongoDB Atlas status, collection counts, latest records, dashboard write
wrappers, Redis/cache status, ChromaDB memory status, Kafka readiness, and
Daniel/Webots event compatibility.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path
from pprint import pformat
from uuid import uuid4

import cache_layer
import data_layer
import db_queries
import kafka_bridge_plan
import memory_store
from event_contracts import CORE_MONGO_COLLECTIONS, OPTIONAL_MONGO_COLLECTIONS


REPORT_PATH = Path(__file__).with_name("connection_proof_latest.txt")
LATEST_RECORD_COLLECTIONS = [
    "robot_status",
    "scenario_events",
    "medicine_events",
    "mood_events",
    "alerts",
    "conversation_events",
    "schedule_events",
    "user_profiles",
]


def _emit(lines: list[str], text: str = "") -> None:
    print(text)
    lines.append(text)


def _print_section(lines: list[str], title: str) -> None:
    _emit(lines)
    _emit(lines, "=" * 72)
    _emit(lines, title)
    _emit(lines, "=" * 72)


def _safe_counts() -> dict[str, int]:
    names = CORE_MONGO_COLLECTIONS + OPTIONAL_MONGO_COLLECTIONS
    try:
        return db_queries.get_collection_counts()
    except Exception:
        return {name: 0 for name in names}


def _safe_latest(collection_name: str):
    try:
        return db_queries.get_latest_document(collection_name)
    except Exception:
        return None


def _sanitize(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(word in lowered for word in ("password", "secret", "token", "uri", "connection")):
                cleaned[key] = "[redacted]"
            elif "phone" in lowered:
                cleaned[key] = "[redacted phone]"
            elif "audio_path" in lowered or lowered.endswith("_path") or lowered == "path":
                cleaned[key] = "[local path redacted]"
            else:
                cleaned[key] = _sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _clean_document(doc):
    if not doc:
        return None
    payload = doc.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    metadata = doc.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {"value": metadata}
    return {
        "event_id": str(doc.get("event_id") or doc.get("_id") or ""),
        "event_type": doc.get("event_type"),
        "scenario_type": doc.get("scenario_type"),
        "status": doc.get("status"),
        "timestamp": doc.get("timestamp"),
        "time": db_queries._to_time(doc.get("timestamp")) if hasattr(db_queries, "_to_time") else "",
        "source": doc.get("source"),
        "source_page": doc.get("source_page"),
        "user_id": doc.get("user_id"),
        "robot_id": doc.get("robot_id"),
        "payload": _sanitize(payload),
        "metadata": _sanitize(metadata),
    }


def _daniel_field_report() -> dict[str, object]:
    required = ["event_id", "event_type", "timestamp", "source", "user_id", "robot_id", "payload"]
    checked = {}
    for collection in ["robot_status", "environment_events", "conversation_events", "scenario_events", "medicine_events", "mood_events", "alerts"]:
        doc = _safe_latest(collection)
        if not doc:
            checked[collection] = {"readable": False, "reason": "No records yet"}
            continue
        missing = [field for field in required if field not in doc]
        checked[collection] = {
            "readable": not missing,
            "missing_fields": missing,
            "event_type": doc.get("event_type"),
            "source": doc.get("source"),
        }
    return checked


def _dashboard_write_wrappers() -> list[dict[str, str]]:
    return [
        {"UI action": "Today's Schedule / View Schedule", "Wrapper": "record_dashboard_event -> db_queries.insert_dashboard_event", "MongoDB collection": "schedule_events"},
        {"UI action": "Take Medication / Mark as taken", "Wrapper": "create_medicine_event / insert_dashboard_event", "MongoDB collection": "medicine_events"},
        {"UI action": "Talk to Nesto", "Wrapper": "record_dashboard_event / insert_dashboard_event", "MongoDB collection": "conversation_events"},
        {"UI action": "Find My Cane", "Wrapper": "create_scenario_event / insert_dashboard_event", "MongoDB collection": "scenario_events"},
        {"UI action": "Find My Medicine", "Wrapper": "create_scenario_event / insert_dashboard_event", "MongoDB collection": "scenario_events"},
        {"UI action": "Call Caregiver", "Wrapper": "create_scenario_event / insert_dashboard_event", "MongoDB collection": "scenario_events"},
        {"UI action": "Mood Check", "Wrapper": "create_mood_event / insert_dashboard_event", "MongoDB collection": "mood_events"},
        {"UI action": "Emergency", "Wrapper": "create_alert_event / insert_dashboard_event", "MongoDB collection": "alerts"},
        {"UI action": "Save Caregiver Note", "Wrapper": "create_caregiver_note_event / insert_dashboard_event", "MongoDB collection": "caregiver_notes"},
        {"UI action": "Save Profile", "Wrapper": "upsert_profile_record + save_profile_memory", "MongoDB collection": "user_profiles"},
    ]


def _run_write_proof(lines: list[str]) -> dict[str, str]:
    _print_section(lines, "Optional Write Proof")
    mongo_status = db_queries.get_connection_status()
    if not mongo_status.get("available"):
        message = f"WRITE PROOF SKIPPED: MongoDB unavailable ({mongo_status.get('error', 'no connection')})"
        _emit(lines, message)
        return {"mongodb": message}
    proof_id = f"nesto_write_proof_{uuid4().hex[:10]}"
    proof_payload = {
        "proof_id": proof_id,
        "message": "Harmless NESTO dashboard write proof.",
        "source": "proof_connections.py",
        "status": "proof_created",
        "metadata": {"proof": True},
    }
    writes = [
        ("scenario_events", lambda: db_queries.create_scenario_event("dashboard_write_proof", payload=proof_payload, status="proof_created", role="proof", source_page="proof_connections.py")),
        ("medicine_events", lambda: db_queries.create_medicine_event(payload=proof_payload, status="proof_created", role="proof", source_page="proof_connections.py")),
        ("mood_events", lambda: db_queries.create_mood_event(payload=proof_payload, status="proof_created", role="proof", source_page="proof_connections.py")),
        ("alerts", lambda: db_queries.create_alert_event(payload=proof_payload, status="proof_created", role="proof", source_page="proof_connections.py")),
        ("conversation_events", lambda: db_queries.insert_dashboard_event("conversation_event", scenario_type="dashboard_write_proof", role="proof", status="proof_created", source_page="proof_connections.py", payload=proof_payload)),
    ]
    results: dict[str, str] = {}
    for collection, writer in writes:
        try:
            inserted_id = writer()
            found = db_queries._db[collection].find_one({"payload.proof_id": proof_id}, sort=[("timestamp", -1), ("_id", -1)])
            if inserted_id and found:
                message = f"WRITE PROOF PASSED: {collection}"
            else:
                message = f"WRITE PROOF FAILED: {collection}"
        except Exception as exc:
            message = f"WRITE PROOF FAILED: {collection} ({exc})"
        results[collection] = message
        _emit(lines, message)
    return results


def _consume_exact_kafka_proof_event(
    topic: str,
    partition: int,
    offset: int,
    expected_event_id: str,
    timeout_seconds: float = 10,
) -> dict:
    try:
        from kafka import KafkaConsumer, TopicPartition
    except Exception as exc:
        kafka_bridge_plan.update_runtime_status("listener", "error", {"error": str(exc)})
        return {"received": 0, "status": "error", "error": str(exc), "events": [], "matched": False}

    events = []
    consumer = None
    deadline = time.time() + timeout_seconds
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            client_id="nesto-dashboard-proof-exact-consumer",
            group_id=None,
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
            key_deserializer=lambda raw: raw.decode("utf-8") if raw else None,
        )
        topic_partition = TopicPartition(topic, int(partition))
        consumer.assign([topic_partition])
        consumer.seek(topic_partition, int(offset))
        print("Listening to Kafka proof offset...")
        while time.time() < deadline:
            batch = consumer.poll(timeout_ms=500, max_records=5)
            for records in batch.values():
                for record in records:
                    event = kafka_bridge_plan.handle_consumed_event(record.topic, record.value)
                    kafka_bridge_plan.update_cache_from_event(record.topic, event)
                    events.append(event)
                    print(f"Received event from {record.topic}: {event.get('event_id')}")
                    print("Updated Redis cache...")
                    if str(event.get("event_id")) == str(expected_event_id):
                        kafka_bridge_plan.update_runtime_status(
                            "listener",
                            "running",
                            {"received": len(events), "matched_event_id": expected_event_id},
                        )
                        return {"received": len(events), "status": "passed", "events": events, "matched": True}
            if events:
                break
        matched = bool(any(str(event.get("event_id")) == str(expected_event_id) for event in events))
        kafka_bridge_plan.update_runtime_status("listener", "running" if events else "waiting", {"received": len(events), "matched": matched})
        return {"received": len(events), "status": "passed" if matched else "waiting", "events": events, "matched": matched}
    except Exception as exc:
        kafka_bridge_plan.update_runtime_status("listener", "error", {"error": str(exc)})
        return {"received": 0, "status": "error", "error": str(exc), "events": [], "matched": False}
    finally:
        if consumer is not None:
            consumer.close()


def _run_kafka_proof(lines: list[str]) -> dict[str, str]:
    _print_section(lines, "Kafka + Redis Runtime Proof")
    os.environ.setdefault("KAFKA_ENABLED", "true")
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    results: dict[str, str] = {}

    status = kafka_bridge_plan.get_kafka_status()
    if status.get("available"):
        results["broker"] = "KAFKA BROKER: connected"
        _emit(lines, results["broker"])
    else:
        results["broker"] = "KAFKA BROKER: not connected"
        _emit(lines, results["broker"])
        if status.get("error"):
            _emit(lines, f"KAFKA ERROR: {status.get('error')}")
        _emit(lines, "KAFKA PROOF FAILED")
        _emit(lines, "Start Kafka using: docker compose -f docker-compose.kafka.yml up -d")
        return results

    topics = kafka_bridge_plan.ensure_kafka_topics()
    if topics.get("ready"):
        results["topics"] = "KAFKA TOPICS: ready"
        _emit(lines, results["topics"])
    else:
        results["topics"] = "KAFKA TOPICS: failed"
        _emit(lines, results["topics"])
        _emit(lines, f"KAFKA TOPIC ERROR: {topics.get('error')}")
        _emit(lines, "KAFKA PROOF FAILED")
        return results

    proof_id = f"kafka_proof_{uuid4().hex[:10]}"
    proof_document = {
        "event_id": proof_id,
        "event_type": "scenario_event",
        "scenario_type": "kafka_runtime_proof",
        "timestamp": int(dt.datetime.now().timestamp() * 1000),
        "source": "proof_connections.py",
        "source_page": "proof_connections.py",
        "user_id": "elderly_user_01",
        "robot_id": "H1",
        "status": "proof_created",
        "payload": {
            "proof_id": proof_id,
            "message": "Kafka proof event from proof_connections.py",
            "status": "proof_created",
            "scenario_type": "kafka_runtime_proof",
        },
        "metadata": {"proof": True},
    }
    publish = kafka_bridge_plan.publish_event_to_kafka("scenario_events", proof_document)
    if publish.get("published"):
        results["producer"] = "KAFKA PRODUCER: passed"
        _emit(lines, results["producer"])
    else:
        results["producer"] = "KAFKA PRODUCER: failed"
        _emit(lines, results["producer"])
        _emit(lines, f"KAFKA PRODUCER ERROR: {publish.get('error') or publish.get('status')}")
        _emit(lines, "KAFKA PROOF FAILED")
        return results

    consume = _consume_exact_kafka_proof_event(
        topic=str(publish.get("topic") or "scenario_events"),
        partition=int(publish.get("partition") or 0),
        offset=int(publish.get("offset") or 0),
        expected_event_id=proof_id,
        timeout_seconds=10,
    )
    if consume.get("matched"):
        results["consumer"] = "KAFKA CONSUMER: passed"
        _emit(lines, results["consumer"])
    else:
        results["consumer"] = "KAFKA CONSUMER: failed"
        _emit(lines, results["consumer"])
        _emit(lines, f"KAFKA CONSUMER RESULT: {pformat(consume, sort_dicts=False)}")
        _emit(lines, "KAFKA PROOF FAILED")
        return results

    cached = cache_layer.get_latest_event("scenario_events") or {}
    cached_payload = cached.get("payload") if isinstance(cached, dict) else {}
    if isinstance(cached_payload, dict) and cached_payload.get("proof_id") == proof_id:
        results["redis"] = "REDIS CACHE UPDATE: passed"
        _emit(lines, results["redis"])
    else:
        results["redis"] = "REDIS CACHE UPDATE: failed"
        _emit(lines, results["redis"])
        _emit(lines, f"CACHE RESULT: {pformat(cached, sort_dicts=False)}")
        _emit(lines, "KAFKA PROOF FAILED")
        return results

    _emit(lines, "KAFKA PROOF PASSED")
    return results


def build_report(write_proof: bool = False) -> list[str]:
    lines: list[str] = []
    timestamp = dt.datetime.now().isoformat(timespec="seconds")

    _print_section(lines, "NESTO BACKEND PROOF")
    _emit(lines, f"Checked at: {timestamp}")
    _emit(lines, "Architecture: Webots -> MongoDB -> Redis -> Dashboard")
    _emit(lines, "Architecture: Dashboard <-> ChromaDB <-> Webots")
    _emit(lines, "Architecture: MongoDB / Event Producer -> Kafka Topics -> Dashboard Consumer")

    _print_section(lines, "1. MongoDB Atlas Connection")
    mongo_status = db_queries.get_connection_status()
    _emit(lines, f"MongoDB Atlas connection status: {mongo_status.get('status')}")
    _emit(lines, f"Database: {mongo_status.get('database_name')}")
    _emit(lines, f"URI configured: {mongo_status.get('uri_configured')}")
    if mongo_status.get("error"):
        _emit(lines, f"Error: {mongo_status.get('error')}")

    _print_section(lines, "2. Collection Counts")
    counts = _safe_counts()
    _emit(lines, "Confirmed collections:")
    for collection_name in CORE_MONGO_COLLECTIONS:
        _emit(lines, f"- {collection_name}: {counts.get(collection_name, 0)}")
    _emit(lines, "")
    _emit(lines, "Optional collections:")
    for collection_name in OPTIONAL_MONGO_COLLECTIONS:
        _emit(lines, f"- {collection_name}: {counts.get(collection_name, 0)}")
    _emit(lines, f"auth_users exists: {'yes' if counts.get('auth_users', 0) else 'not detected / empty'}")

    _print_section(lines, "3. Latest Records")
    for collection_name in LATEST_RECORD_COLLECTIONS:
        _emit(lines, f"\n[{collection_name}]")
        document = _clean_document(_safe_latest(collection_name))
        _emit(lines, pformat(document, sort_dicts=False) if document else "No records yet.")

    _print_section(lines, "4. Dashboard Write Wrappers")
    _emit(lines, "Leona / Dashboard UI produces events through db_queries.py wrappers:")
    for item in _dashboard_write_wrappers():
        _emit(lines, f"- {item['UI action']} -> {item['MongoDB collection']} ({item['Wrapper']})")

    _print_section(lines, "5. Redis Cache Status")
    cache = cache_layer.cache_status()
    _emit(lines, pformat(cache, sort_dicts=False))
    _emit(lines, "Dashboard consumer: data_layer.py/db_queries.py read MongoDB; Redis is the speed layer when available.")
    _emit(lines, "Fallback: if Redis is unavailable, local TTL cache/direct MongoDB reads continue.")

    _print_section(lines, "6. ChromaDB Memory Status")
    chroma = memory_store.get_chromadb_status()
    _emit(lines, pformat(chroma, sort_dicts=False))
    profile_payload = {
        "user_id": "elderly_user_01",
        "preferred_name": "Connection proof",
        "robot_name": "Nesto",
        "guardian_contact": {"role": "Guardian / Caregiver", "name": "Proof Guardian"},
        "preferences": {"source": "proof_connections.py"},
    }
    profile_save = memory_store.save_profile_memory(profile_payload)
    profile_read = memory_store.read_profile_memory("elderly_user_01")
    object_save = memory_store.save_object_memory("elderly_user_01", "medicine box", "kitchen counter", metadata={"source": "proof_connections.py"})
    object_read = memory_store.read_object_memory("elderly_user_01", "medicine box")
    _emit(lines, f"Profile memory save: {pformat(profile_save, sort_dicts=False)}")
    _emit(lines, f"Profile memory read: {pformat(profile_read, sort_dicts=False)}")
    _emit(lines, f"Object memory save: {pformat(object_save, sort_dicts=False)}")
    _emit(lines, f"Object memory read: {pformat(object_read, sort_dicts=False)}")

    _print_section(lines, "7. Kafka Producer/Listener Readiness")
    kafka = kafka_bridge_plan.kafka_status()
    _emit(lines, pformat(kafka, sort_dicts=False))
    _emit(lines, "Producer readiness:")
    _emit(lines, pformat(kafka_bridge_plan.producer_readiness(), sort_dicts=False))
    _emit(lines, "Consumer/listener readiness:")
    _emit(lines, pformat(kafka_bridge_plan.consumer_readiness(), sort_dicts=False))
    _emit(lines, "Kafka producer/consumer wiring is implemented. If the broker is not running, --kafka-proof fails honestly with startup instructions.")

    _print_section(lines, "8. Daniel Backend Compatibility")
    _emit(lines, "Daniel/Webots producer writes robot/scenario/environment events into MongoDB Atlas.")
    _emit(lines, "Dashboard consumer reads those records through db_queries.py and data_layer.py.")
    _emit(lines, pformat(db_queries.get_daniel_compatibility_report(), sort_dicts=False))
    _emit(lines, "Daniel event fields readable by dashboard:")
    _emit(lines, pformat(_daniel_field_report(), sort_dicts=False))

    _print_section(lines, "9. Final Proof Summary")
    _emit(lines, f"MongoDB: {mongo_status.get('status')} ({mongo_status.get('database_name')})")
    _emit(lines, f"Redis/cache: {cache.get('mode', cache.get('status', 'unknown'))}")
    _emit(lines, f"ChromaDB: {chroma.get('status')}")
    _emit(lines, f"Kafka: {kafka.get('status')}")
    _emit(lines, f"Resolved care profile: {pformat(data_layer.care_profile(), sort_dicts=False)}")
    _emit(lines, "Normal dashboard users do not see backend proof details; Admin/System Health and terminal proof show them.")

    if write_proof:
        _run_write_proof(lines)

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="NESTO backend connection and dataflow proof.")
    parser.add_argument("--write-proof", action="store_true", help="Insert and read back harmless proof events.")
    parser.add_argument("--kafka-proof", action="store_true", help="Prove Kafka broker/topic/producer/consumer/cache flow.")
    args = parser.parse_args()

    if args.kafka_proof:
        os.environ.setdefault("KAFKA_ENABLED", "true")
        os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    lines = build_report(write_proof=args.write_proof)
    if args.kafka_proof:
        _run_kafka_proof(lines)
    try:
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print()
        print(f"Saved proof report: {REPORT_PATH}")
    except PermissionError as exc:
        print()
        print(f"Proof report was generated but could not be saved to {REPORT_PATH}: {exc}")


if __name__ == "__main__":
    main()
