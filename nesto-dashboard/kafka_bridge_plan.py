"""
Kafka + Redis runtime bridge for NESTO Care.

Runtime flow:
MongoDB new records -> Python polling bridge -> Kafka topics -> dashboard
consumer -> Redis/latest cache -> Streamlit dashboard Redis-first reads.

Kafka is optional at app startup. If `KAFKA_ENABLED=false`, MongoDB reads/writes
continue. If enabled but the broker/client is unavailable, proof commands and
Admin/System Health report the exact error without breaking user-facing pages.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from bson import json_util
from dotenv import load_dotenv

from event_contracts import EVENT_SCHEMAS, EVENT_TO_COLLECTION, KAFKA_TOPICS


load_dotenv()

KAFKA_COLLECTIONS = [
    "robot_status",
    "environment_events",
    "conversation_events",
    "scenario_events",
    "medicine_events",
    "mood_events",
    "alerts",
    "schedule_events",
    "user_profiles",
]
EXPECTED_TOPICS = list(KAFKA_TOPICS)
OFFSET_FILE = Path(__file__).with_name(".kafka_offsets.json")
RUNTIME_STATUS_FILE = Path(__file__).with_name(".kafka_runtime_status.json")

COLLECTION_TO_TOPIC = {
    "robot_status": "robot_status",
    "conversation_events": "conversation_events",
    "environment_events": "environment_events",
    "medicine_events": "medicine_events",
    "mood_events": "mood_events",
    "alerts": "alerts",
    "scenario_events": "scenario_events",
    "schedule_events": "schedule_events",
    "user_profiles": "profile_updated",
}

EVENT_TO_TOPIC = {
    event_type: COLLECTION_TO_TOPIC.get(collection)
    for event_type, collection in EVENT_TO_COLLECTION.items()
    if COLLECTION_TO_TOPIC.get(collection)
}

PRODUCER_MAPPING = {
    "robot_status event": "robot_status",
    "conversation event": "conversation_events",
    "environment event": "environment_events",
    "medicine event": "medicine_events",
    "mood event": "mood_events",
    "alert event": "alerts",
    "scenario event": "scenario_events",
    "schedule event": "schedule_events",
    "profile save": "profile_updated",
}


def _enabled() -> bool:
    return str(os.getenv("KAFKA_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS") or os.getenv("KAFKA_BOOTSTRAP") or "localhost:9092"


def _client_id() -> str:
    return os.getenv("KAFKA_CLIENT_ID", "nesto-dashboard")


def _consumer_group() -> str:
    return os.getenv("KAFKA_CONSUMER_GROUP", "nesto-dashboard-consumer")


def _poll_seconds() -> float:
    try:
        return float(os.getenv("KAFKA_POLL_SECONDS", "5"))
    except Exception:
        return 5.0


def _bootstrap_endpoint() -> tuple[str, int]:
    first = _bootstrap().split(",")[0].strip()
    if "://" in first:
        first = first.split("://", 1)[1]
    host, _, port = first.partition(":")
    try:
        return host or "localhost", int(port or "9092")
    except Exception:
        return host or "localhost", 9092


def _tcp_reachable(timeout_seconds: float = 0.75) -> tuple[bool, str]:
    host, port = _bootstrap_endpoint()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True, f"{host}:{port}"
    except Exception as exc:
        return False, f"{host}:{port} ({exc})"


def _import_kafka():
    try:
        from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
        from kafka.admin import NewTopic
        from kafka.errors import KafkaError, TopicAlreadyExistsError
        return {
            "KafkaAdminClient": KafkaAdminClient,
            "KafkaConsumer": KafkaConsumer,
            "KafkaProducer": KafkaProducer,
            "NewTopic": NewTopic,
            "KafkaError": KafkaError,
            "TopicAlreadyExistsError": TopicAlreadyExistsError,
            "error": None,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _json_safe(value: Any) -> Any:
    return json.loads(json_util.dumps(value))


def _normalize_document(collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
    payload = document.get("payload") if isinstance(document, dict) else {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    metadata = document.get("metadata") if isinstance(document, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {"value": metadata}
    return _json_safe({
        "collection": collection_name,
        "topic": map_collection_to_topic(collection_name),
        "event_id": document.get("event_id") or str(document.get("_id", "")),
        "event_type": document.get("event_type") or collection_name,
        "scenario_type": document.get("scenario_type") or payload.get("scenario_type"),
        "timestamp": document.get("timestamp") or int(time.time() * 1000),
        "source": document.get("source") or "mongodb",
        "source_page": document.get("source_page"),
        "user_id": document.get("user_id") or payload.get("user_id") or "elderly_user_01",
        "robot_id": document.get("robot_id") or payload.get("robot_id") or "H1",
        "status": document.get("status") or payload.get("status") or "created",
        "payload": payload,
        "metadata": metadata,
    })


def _load_offsets() -> dict[str, int]:
    try:
        data = json.loads(OFFSET_FILE.read_text(encoding="utf-8"))
        return {str(key): int(value or 0) for key, value in data.items()}
    except Exception:
        return {}


def _save_offsets(offsets: dict[str, int]) -> None:
    OFFSET_FILE.write_text(json.dumps(offsets, indent=2, sort_keys=True), encoding="utf-8")


def _runtime_status() -> dict[str, Any]:
    try:
        return json.loads(RUNTIME_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def update_runtime_status(component: str, status: str, detail: dict[str, Any] | None = None) -> None:
    data = _runtime_status()
    data[component] = {
        "status": status,
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        **(detail or {}),
    }
    RUNTIME_STATUS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")


def get_runtime_status() -> dict[str, Any]:
    return _runtime_status()


def map_collection_to_topic(collection_name: str) -> str:
    return COLLECTION_TO_TOPIC.get(collection_name, "scenario_events")


def get_kafka_status() -> dict[str, Any]:
    enabled = _enabled()
    libs = _import_kafka()
    runtime = get_runtime_status()
    base = {
        "enabled": enabled,
        "available": False,
        "configured": bool(_bootstrap()),
        "status": "disabled" if not enabled else "error",
        "bootstrap_servers": _bootstrap(),
        "client_id": _client_id(),
        "consumer_group": _consumer_group(),
        "expected_topics": EXPECTED_TOPICS,
        "collection_to_topic": COLLECTION_TO_TOPIC,
        "event_to_topic": EVENT_TO_TOPIC,
        "producer_mapping": PRODUCER_MAPPING,
        "runtime": runtime,
    }
    if not enabled:
        return base
    if libs.get("error"):
        base.update({
            "status": "missing_dependency",
            "error": f"kafka-python is not installed or could not import: {libs['error']}",
            "startup": "pip install kafka-python && docker compose -f docker-compose.kafka.yml up -d",
        })
        return base
    reachable, reach_detail = _tcp_reachable()
    if not reachable:
        base.update({
            "status": "not_connected",
            "error": f"No Kafka TCP listener reachable at {reach_detail}",
            "startup": "docker compose -f docker-compose.kafka.yml up -d",
        })
        return base
    try:
        admin = libs["KafkaAdminClient"](
            bootstrap_servers=_bootstrap(),
            client_id=f"{_client_id()}-status",
            request_timeout_ms=3000,
        )
        topics = sorted(admin.list_topics())
        admin.close()
        missing = [topic for topic in EXPECTED_TOPICS if topic not in topics]
        base.update({
            "available": True,
            "status": "connected" if not missing else "connected_missing_topics",
            "topics_available": topics,
            "missing_topics": missing,
        })
        return base
    except Exception as exc:
        base.update({
            "status": "not_connected",
            "error": str(exc),
            "startup": "docker compose -f docker-compose.kafka.yml up -d",
        })
        return base


def kafka_status() -> dict[str, Any]:
    """Backward-compatible alias for existing admin/proof code."""
    return get_kafka_status()


def ensure_kafka_topics() -> dict[str, Any]:
    status = get_kafka_status()
    if not status.get("enabled"):
        return {"ready": False, "status": "disabled", "topics": EXPECTED_TOPICS}
    if status.get("status") == "missing_dependency":
        return {"ready": False, "status": "missing_dependency", "error": status.get("error")}
    if not status.get("available"):
        return {"ready": False, "status": status.get("status", "not_connected"), "error": status.get("error"), "topics": EXPECTED_TOPICS}
    libs = _import_kafka()
    try:
        admin = libs["KafkaAdminClient"](
            bootstrap_servers=_bootstrap(),
            client_id=f"{_client_id()}-admin",
            request_timeout_ms=5000,
        )
        existing = set(admin.list_topics())
        missing = [topic for topic in EXPECTED_TOPICS if topic not in existing]
        if missing:
            topics = [libs["NewTopic"](name=topic, num_partitions=1, replication_factor=1) for topic in missing]
            try:
                admin.create_topics(new_topics=topics, validate_only=False)
            except Exception as exc:
                if "TopicAlreadyExists" not in str(exc):
                    raise
        ready_topics = sorted(admin.list_topics())
        admin.close()
        update_runtime_status("topics", "ready", {"topics": EXPECTED_TOPICS})
        return {"ready": True, "status": "ready", "topics": EXPECTED_TOPICS, "available_topics": ready_topics}
    except Exception as exc:
        update_runtime_status("topics", "error", {"error": str(exc)})
        return {"ready": False, "status": "error", "error": str(exc), "topics": EXPECTED_TOPICS}


def _producer():
    libs = _import_kafka()
    if libs.get("error"):
        raise RuntimeError(libs["error"])
    return libs["KafkaProducer"](
        bootstrap_servers=_bootstrap(),
        client_id=f"{_client_id()}-producer",
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        key_serializer=lambda value: str(value).encode("utf-8") if value is not None else None,
        linger_ms=20,
        request_timeout_ms=5000,
    )


def publish_event_to_kafka(collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
    if not _enabled():
        return {"published": False, "status": "disabled", "topic": map_collection_to_topic(collection_name)}
    topic_result = ensure_kafka_topics()
    if not topic_result.get("ready"):
        return {"published": False, "status": topic_result.get("status", "error"), "error": topic_result.get("error"), "topic": map_collection_to_topic(collection_name)}
    topic = map_collection_to_topic(collection_name)
    event = _normalize_document(collection_name, document)
    try:
        producer = _producer()
        future = producer.send(topic, key=event.get("event_id"), value=event)
        record = future.get(timeout=10)
        producer.flush(timeout=5)
        producer.close(timeout=5)
        update_runtime_status("producer", "passed", {"topic": topic, "event_id": event.get("event_id")})
        return {
            "published": True,
            "status": "passed",
            "topic": topic,
            "partition": record.partition,
            "offset": record.offset,
            "event": event,
        }
    except Exception as exc:
        update_runtime_status("producer", "error", {"topic": topic, "error": str(exc)})
        return {"published": False, "status": "error", "topic": topic, "error": str(exc)}


def poll_mongodb_new_events_and_publish(limit_per_collection: int = 50) -> dict[str, Any]:
    import db_queries

    if not _enabled():
        return {"published": 0, "status": "disabled"}
    offsets = _load_offsets()
    published = 0
    errors: list[str] = []
    print("Watching MongoDB collections:")
    print(", ".join(KAFKA_COLLECTIONS))
    print("Publishing new events to Kafka topics...")
    for collection_name in KAFKA_COLLECTIONS:
        last_ts = int(offsets.get(collection_name, 0))
        try:
            docs = list(
                db_queries._db[collection_name]
                .find({"timestamp": {"$gt": last_ts}}, sort=[("timestamp", 1), ("_id", 1)], limit=limit_per_collection)
            )
        except Exception as exc:
            errors.append(f"{collection_name}: {exc}")
            continue
        for doc in docs:
            result = publish_event_to_kafka(collection_name, doc)
            if result.get("published"):
                published += 1
                offsets[collection_name] = max(int(offsets.get(collection_name, 0)), int(doc.get("timestamp") or 0))
                print(f"Published {collection_name} -> {result.get('topic')} event_id={doc.get('event_id') or doc.get('_id')}")
            else:
                errors.append(f"{collection_name}: {result.get('error') or result.get('status')}")
    _save_offsets(offsets)
    status = "running" if not errors else "error"
    update_runtime_status("bridge", status, {"published": published, "errors": errors[-5:]})
    return {"published": published, "errors": errors, "status": status}


def handle_consumed_event(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = dict(payload or {})
    event.setdefault("topic", topic)
    collection = event.get("collection") or topic
    if topic == "profile_updated":
        collection = "user_profiles"
    if topic == "schedule_events":
        collection = "schedule_events"
    event.setdefault("collection", collection)
    return event


def update_chromadb_from_event(topic: str, event: dict[str, Any]) -> dict[str, Any]:
    """Update profile/object/robot memory from consumed Kafka events when possible."""
    try:
        import memory_store
    except Exception as exc:
        return {"updated": False, "status": "unavailable", "error": str(exc)}

    payload = event.get("payload") if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    user_id = event.get("user_id") or payload.get("user_id") or payload.get("patient_id") or "elderly_user_01"

    try:
        if topic == "profile_updated" or event.get("collection") == "user_profiles":
            profile_payload = dict(payload or {})
            profile_payload.setdefault("user_id", user_id)
            return {"updated": bool(memory_store.save_profile_memory(profile_payload).get("connected")), "type": "profile_memory"}

        object_name = (
            payload.get("object_name")
            or payload.get("target_object")
            or payload.get("object")
            or payload.get("detected_object")
        )
        location = (
            payload.get("location")
            or payload.get("last_known_location")
            or payload.get("current_room")
            or payload.get("room")
        )
        if object_name and location:
            result = memory_store.save_object_memory(
                user_id,
                object_name,
                location,
                metadata={"source": "kafka_consumer", "topic": topic, "event_id": str(event.get("event_id") or "")},
            )
            return {"updated": bool(result.get("connected")), "type": "object_memory", "object_name": object_name}

        if topic == "robot_status" and location:
            result = memory_store.save_object_memory(
                user_id,
                "robot location",
                location,
                metadata={"source": "kafka_consumer", "topic": topic, "event_id": str(event.get("event_id") or ""), "memory_kind": "robot_mapping"},
            )
            return {"updated": bool(result.get("connected")), "type": "robot_location_memory"}
    except Exception as exc:
        return {"updated": False, "status": "error", "error": str(exc)}

    return {"updated": False, "status": "not_applicable"}


def update_cache_from_event(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    import cache_layer

    event = handle_consumed_event(topic, payload)
    collection = event.get("collection") or topic
    ttl = 300
    cache_layer.set_latest_event(collection, event, ttl_seconds=ttl)
    cache_layer.set_json("kafka:last_event", event, ttl_seconds=ttl)
    cache_layer.set_json("dashboard:admin:summary", {"last_kafka_event": event, "updated_at": dt.datetime.now().isoformat(timespec="seconds")}, ttl_seconds=ttl)
    memory_result = update_chromadb_from_event(topic, event)
    update_runtime_status("consumer", "passed", {"topic": topic, "event_id": event.get("event_id")})
    return {"updated": True, "cache_key": f"{collection}:latest", "event": event, "memory": memory_result}


def _consumer(group_id: str | None = None, auto_offset_reset: str = "latest"):
    libs = _import_kafka()
    if libs.get("error"):
        raise RuntimeError(libs["error"])
    return libs["KafkaConsumer"](
        *EXPECTED_TOPICS,
        bootstrap_servers=_bootstrap(),
        client_id=f"{_client_id()}-consumer",
        group_id=group_id or _consumer_group(),
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        consumer_timeout_ms=1000,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        key_deserializer=lambda raw: raw.decode("utf-8") if raw else None,
    )


def consume_kafka_events_once(
    timeout_seconds: float = 5,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
    expected_event_id: str | None = None,
) -> dict[str, Any]:
    if not _enabled():
        return {"received": 0, "status": "disabled", "events": []}
    events = []
    deadline = time.time() + timeout_seconds
    try:
        consumer = _consumer(group_id=group_id, auto_offset_reset=auto_offset_reset)
        print("Listening to Kafka topics...")
        while time.time() < deadline:
            batch = consumer.poll(timeout_ms=500, max_records=20)
            for records in batch.values():
                for record in records:
                    event = handle_consumed_event(record.topic, record.value)
                    update_cache_from_event(record.topic, event)
                    events.append(event)
                    print(f"Received event from {record.topic}: {event.get('event_id')}")
                    print("Updated Redis cache...")
                    if expected_event_id and str(event.get("event_id")) == str(expected_event_id):
                        consumer.close()
                        update_runtime_status("listener", "running", {"received": len(events), "matched_event_id": expected_event_id})
                        return {"received": len(events), "status": "passed", "events": events, "matched": True}
            if events and not expected_event_id:
                break
        consumer.close()
        matched = bool(expected_event_id and any(str(event.get("event_id")) == str(expected_event_id) for event in events))
        update_runtime_status("listener", "running" if events else "waiting", {"received": len(events), "matched": matched})
        return {"received": len(events), "status": "passed" if (events and (matched or not expected_event_id)) else "waiting", "events": events, "matched": matched}
    except Exception as exc:
        update_runtime_status("listener", "error", {"error": str(exc)})
        return {"received": 0, "status": "error", "error": str(exc), "events": []}


def consume_kafka_events_loop() -> None:
    print("Listening to Kafka topics...")
    while True:
        result = consume_kafka_events_once(timeout_seconds=max(_poll_seconds(), 1), auto_offset_reset="latest")
        if result.get("status") == "error":
            print(f"Kafka consumer error: {result.get('error')}")
        time.sleep(_poll_seconds())


def producer_readiness() -> dict[str, Any]:
    status = get_kafka_status()
    return {
        "ready": status.get("available", False),
        "status": status.get("status"),
        "owner": "MongoDB polling bridge / db_queries.py dashboard write publisher",
        "collection_to_topic": COLLECTION_TO_TOPIC,
        "producer_mapping": PRODUCER_MAPPING,
        "runtime": status.get("runtime", {}).get("producer", {}),
    }


def consumer_readiness() -> dict[str, Any]:
    status = get_kafka_status()
    return {
        "ready": status.get("available", False),
        "status": status.get("status"),
        "owner": "NESTO dashboard Kafka consumer/listener",
        "expected_topics": EXPECTED_TOPICS,
        "runtime": status.get("runtime", {}).get("consumer", {}),
    }


def mark_event_for_streaming(event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    topic = EVENT_TO_TOPIC.get(event_type) or "scenario_events"
    return {
        "event_type": event_type,
        "topic": topic,
        "streaming_status": "enabled" if _enabled() else "disabled",
        "metadata": metadata or {},
    }


def run_bridge_loop() -> None:
    while True:
        result = poll_mongodb_new_events_and_publish()
        if result.get("errors"):
            print("Bridge errors:", result["errors"][-3:])
        time.sleep(_poll_seconds())


def main() -> None:
    status = get_kafka_status()
    print("NESTO KAFKA + REDIS RUNTIME")
    print()
    print("Kafka topics:")
    for topic in EXPECTED_TOPICS:
        print(f"- {topic}")
    print()
    print("Producer mapping:")
    for event_name, topic in PRODUCER_MAPPING.items():
        print(f"- {event_name} -> {topic} topic")
    print()
    print("Kafka status:", status["status"])
    if status.get("error"):
        print("Kafka error:", status["error"])
    if status.get("startup"):
        print("Start Kafka using:", status["startup"])
    print("Redis/cache is updated by consume_kafka_events_once/loop via cache_layer.py.")


if __name__ == "__main__":
    main()
