"""Admin KPI dashboard route.

Serves ``GET /api/admin/kpis`` for the NESTO Care Operations Admin KPI dashboard
(the ``local_kpi_ui_foundation`` integration kit, now wired into the live app).

Design rules carried over from the UI foundation:
- Read-only MongoDB. No writes are performed here.
- Real values only. KPIs that cannot be computed from complete, parseable data
  are returned as "Unavailable"/"Partial" rather than invented numbers.
- Credentials stay server-side; recent event rows are redacted.

Data is computed live by reusing two existing, validated pieces:
- ``db_queries._db`` — the shared MongoDB handle the Streamlit app and robot
  bridge already use (no second connection is opened).
- ``analytics/mongo_kpi_analysis.py`` — the read-only KPI analysis logic.

Latency is computed here directly from the seven pipeline timestamps, reading
each value whether it is stored top-level (this project's real shape) or nested
under ``timestamps.*``. The result is mapped to the ``AdminKpiDashboardData``
contract that ``admin_kpi_types.ts`` / ``admin_kpi_api_adapter.ts`` expect.
"""
from __future__ import annotations

import sys
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..nesto import SWARM_ROOT, db_queries

# Reuse the read-only analytics module without opening a second Mongo connection.
ANALYTICS_DIR = SWARM_ROOT / "analytics"
if str(ANALYTICS_DIR) not in sys.path:
    sys.path.append(str(ANALYTICS_DIR))
import mongo_kpi_analysis as mka  # noqa: E402

router = APIRouter(prefix="/api/admin", tags=["admin"])

DATABASE_NAME = getattr(db_queries, "DATABASE_NAME", "humanoid_assistant")

# Short (top-level) names of the seven pipeline timestamps the KPIs depend on.
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

# (display stage, start field, end field, short key) in fixed pipeline order.
LATENCY_SEGMENTS = [
    ("UI -> Backend", "ui_triggered_at", "backend_received_at", "ui_to_backend"),
    ("Backend -> Bridge", "backend_received_at", "bridge_received_at", "backend_to_bridge"),
    ("Bridge -> Robot Start", "bridge_received_at", "robot_action_started_at", "bridge_to_robot_start"),
    ("Robot Action Duration", "robot_action_started_at", "robot_action_completed_at", "robot_action_duration"),
    ("Robot -> MongoDB", "robot_action_completed_at", "mongodb_logged_at", "robot_to_mongodb"),
    ("MongoDB -> Dashboard", "mongodb_logged_at", "dashboard_updated_at", "mongodb_to_dashboard"),
    ("End-to-End", "ui_triggered_at", "dashboard_updated_at", "end_to_end"),
]

BLOCKED_KPI_MAP = {
    "ui_triggered_at": ["End-to-End Latency"],
    "backend_received_at": ["UI to Backend Latency"],
    "bridge_received_at": ["Backend to Bridge Latency"],
    "robot_action_started_at": ["Robot Action Duration"],
    "robot_action_completed_at": ["MongoDB Write Latency", "Robot Action Duration"],
    "mongodb_logged_at": ["MongoDB Write Latency", "Dashboard Refresh Latency"],
    "dashboard_updated_at": ["End-to-End Latency", "Dashboard Refresh Latency"],
}

AVAILABILITY = {"yes": "Available", "partial": "Partial", "no": "Unavailable"}


def require_admin(claims: dict = Depends(get_current_user)) -> dict:
    """Allow only authenticated admin/provider users."""
    if claims.get("role") != "admin_provider":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return claims


def _status_from_availability(availability: str) -> str:
    return AVAILABILITY.get(str(availability or "no"), "Unavailable")


def _doc_timestamp_value(doc: dict[str, Any], field: str) -> Any:
    """Read a timestamp whether stored top-level or nested under ``timestamps``."""
    ts = doc.get("timestamps")
    if isinstance(ts, dict) and ts.get(field) is not None:
        return ts.get(field)
    return doc.get(field)


def _field_presence(samples_by_collection: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, bool]]:
    """For each required timestamp, whether it is present at all and whether any
    value is parseable to a real datetime in the sampled data."""
    presence: dict[str, dict[str, bool]] = {
        f: {"present": False, "parseable": False} for f in REQUIRED_TIMESTAMPS
    }
    for docs in samples_by_collection.values():
        for doc in docs:
            for field in REQUIRED_TIMESTAMPS:
                value = _doc_timestamp_value(doc, field)
                if value is not None:
                    presence[field]["present"] = True
                    if mka.parse_datetime(value) is not None:
                        presence[field]["parseable"] = True
    return presence


def _compute_segment(
    stage: str, start_field: str, end_field: str, samples_by_collection: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    values: list[float] = []
    missing = 0
    negative = 0
    for docs in samples_by_collection.values():
        for doc in docs:
            start = mka.parse_datetime(_doc_timestamp_value(doc, start_field))
            end = mka.parse_datetime(_doc_timestamp_value(doc, end_field))
            if start is None or end is None:
                missing += 1
                continue
            duration_ms = (end - start).total_seconds() * 1000.0
            if duration_ms < 0:
                negative += 1
                continue
            values.append(duration_ms)
    stat = mka.stats(values)
    if stat:
        seg_status = "Partial" if missing else "Available"
    else:
        seg_status = "Unavailable"
    return {
        "stage": stage,
        "status": seg_status,
        "samples": stat.get("sample_size") if stat else None,
        "median_ms": stat.get("p50") if stat else None,
        "average_ms": stat.get("average") if stat else None,
        "p95_ms": stat.get("p95") if stat else None,
        "negative": negative,
        "note": "Real timestamp pair available" if stat else "Missing required timestamp pair",
    }


def _redacted_recent_event(collection: str, doc: dict[str, Any]) -> dict[str, Any]:
    flat = mka.flatten_document(doc)
    if "_id" in doc and "_id" not in flat:
        flat["_id"] = doc["_id"]
    payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
    ts = mka.latest_doc_timestamp(flat)
    start = mka.parse_datetime(_doc_timestamp_value(doc, "ui_triggered_at"))
    end = mka.parse_datetime(_doc_timestamp_value(doc, "dashboard_updated_at"))
    e2e = (end - start).total_seconds() * 1000.0 if (start and end) else None
    return {
        "time": ts.isoformat() if ts else None,
        "event_id": "redacted",
        "trigger": payload.get("trigger") or doc.get("event_type") or collection,
        "scenario": payload.get("scenario") or doc.get("scenario"),
        "robot_action": payload.get("robot_action") or doc.get("action") or doc.get("event_type"),
        "status": doc.get("status") or payload.get("status") or "Unknown",
        "end_to_end_latency": f"{round(e2e, 1)} ms" if isinstance(e2e, (int, float)) and e2e >= 0 else None,
        "mongodb": "Logged",
    }


def build_admin_kpis() -> dict[str, Any]:
    if getattr(db_queries, "_client_init_error", None):
        raise HTTPException(status_code=503, detail="MongoDB connection is unavailable.")

    db = db_queries._db
    try:
        db.client.admin.command("ping")
    except Exception as exc:  # pragma: no cover - network dependent
        raise HTTPException(status_code=503, detail=f"MongoDB is not reachable: {exc}") from exc

    analysis = mka.analyse_collections(db)
    _kpi_rows, snapshot = mka.evaluate_kpis(analysis)

    inventory = analysis["inventory_rows"]
    field_index = analysis["field_index"]
    samples_by_collection = analysis["samples_by_collection"]
    kpis = snapshot.get("kpis", {})

    def availability_of(name: str) -> str:
        return _status_from_availability(kpis.get(name, {}).get("availability", "no"))

    def value_of(name: str) -> Any:
        return kpis.get(name, {}).get("value")

    # --- latency segments (all seven, top-level or nested timestamps) ------ #
    seg_map: dict[str, dict[str, Any]] = {}
    segments = []
    for stage, start_field, end_field, key in LATENCY_SEGMENTS:
        seg = _compute_segment(stage, start_field, end_field, samples_by_collection)
        segments.append(seg)
        seg_map[key] = seg

    def latency_value(key: str) -> str:
        seg = seg_map.get(key, {})
        return f"{seg['median_ms']} ms" if seg.get("median_ms") is not None else "Unavailable"

    def latency_status(key: str) -> str:
        return seg_map.get(key, {}).get("status", "Unavailable")

    # --- per-collection MongoDB sync (real read-only counts) --------------- #
    collections = []
    total_documents = 0
    total_daniel = 0
    for row in inventory:
        name = row["collection"]
        documents = int(row.get("document_count", 0))
        try:
            daniel = int(db[name].count_documents(DANIEL_FILTER))
        except Exception:
            daniel = 0
        try:
            complete = int(
                db[name].count_documents(
                    {
                        "$and": [
                            {"$or": [{f: {"$exists": True}}, {f"timestamps.{f}": {"$exists": True}}]}
                            for f in REQUIRED_TIMESTAMPS
                        ]
                    }
                )
            )
        except Exception:
            complete = 0
        total_documents += documents
        total_daniel += daniel
        if documents == 0:
            coll_status = "No telemetry"
        elif daniel > 0 or complete > 0:
            coll_status = "Active"
        else:
            coll_status = "Partial"
        collections.append(
            {
                "collection": name,
                "documents": documents,
                "daniel_filter_matches": daniel,
                "all_required_timestamp_fields_present": complete,
                "status": coll_status,
                "last_update": row.get("latest_timestamp") or None,
                "notes": f"Freshness: {row.get('freshness', 'unknown')}.",
            }
        )

    collections_with_data = sum(1 for c in collections if c["documents"] > 0)
    collections_inspected = len(collections)

    # --- missing telemetry fields (honest present/parseable check) --------- #
    presence = _field_presence(samples_by_collection)
    missing_fields = []
    for field in REQUIRED_TIMESTAMPS:
        info = presence[field]
        if not info["present"]:
            state = "not found in sampled records"
        elif not info["parseable"]:
            state = "present but null / not parseable"
        else:
            continue
        missing_fields.append(
            {"field": field, "state": state, "blocked_kpis": BLOCKED_KPI_MAP.get(field, [])}
        )
    missing_field_names = [m["field"] for m in missing_fields]

    # --- event success rate ------------------------------------------------ #
    rate = snapshot.get("throughput", {}).get("success_rate", {})
    success = int(rate.get("success", 0))
    failure = int(rate.get("failure", 0))
    pending = int(rate.get("pending", 0))
    unknown = int(rate.get("unknown", 0))
    pct = rate.get("success_rate_percent")

    # --- last robot action ------------------------------------------------- #
    last_raw = value_of("Last Robot Action")
    last_action = last_raw if isinstance(last_raw, dict) else None

    # --- failed events ----------------------------------------------------- #
    failed_raw = value_of("Failed Events")
    failed_value = failed_raw if isinstance(failed_raw, dict) else {}
    failed_count = int(failed_value.get("failed_events_in_sample", 0))

    # --- recent events (redacted) ----------------------------------------- #
    recent_events = []
    for row in inventory:
        name = row["collection"]
        try:
            doc = db[name].find_one({}, sort=[("_id", -1)])
        except Exception:
            doc = None
        if doc:
            recent_events.append(_redacted_recent_event(name, doc))
    recent_events.sort(key=lambda e: e.get("time") or "", reverse=True)
    recent_events = recent_events[:10]

    # --- top KPI cards (fixed order the UI expects) ------------------------ #
    pipeline_value = value_of("Pipeline Status")
    top_kpis = [
        {
            "id": "pipeline_status",
            "label": "Pipeline Status",
            "status": availability_of("Pipeline Status"),
            "value": str(pipeline_value).title() if pipeline_value else "Unknown",
            "detail": "Inferred from latest event freshness",
            "target": "pipeline",
        },
        {
            "id": "end_to_end_latency",
            "label": "End-to-End Latency",
            "status": latency_status("end_to_end"),
            "value": latency_value("end_to_end"),
            "detail": "UI trigger to dashboard update",
            "target": "latency",
        },
        {
            "id": "mongodb_write_latency",
            "label": "MongoDB Write Latency",
            "status": latency_status("robot_to_mongodb"),
            "value": latency_value("robot_to_mongodb"),
            "detail": "Robot completion to MongoDB log",
            "target": "latency",
        },
        {
            "id": "dashboard_refresh_latency",
            "label": "Dashboard Refresh Latency",
            "status": latency_status("mongodb_to_dashboard"),
            "value": latency_value("mongodb_to_dashboard"),
            "detail": "MongoDB log to dashboard update",
            "target": "latency",
        },
        {
            "id": "event_success_rate",
            "label": "Event Success Rate",
            "status": availability_of("Event Success Rate"),
            "value": f"{pct}%" if pct is not None else "Partial",
            "detail": f"{success} success / {failure} failure (terminal)",
            "target": "events",
        },
        {
            "id": "last_robot_action",
            "label": "Last Robot Action",
            "status": availability_of("Last Robot Action"),
            "value": (last_action or {}).get("action") or "Unavailable",
            "detail": "Latest action-like event",
            "target": "robot-actions",
        },
        {
            "id": "active_collections",
            "label": "Active Collections",
            "status": "Available" if collections_inspected else "Unavailable",
            "value": f"{collections_with_data} / {collections_inspected}",
            "detail": "Collections with data",
            "target": "mongo-sync",
        },
        {
            "id": "failed_events",
            "label": "Failed Events",
            "status": availability_of("Failed Events"),
            "value": str(failed_count),
            "detail": "Terminal failures in sample",
            "target": "events",
        },
    ]

    top_level_found = any(mka.field_exists(field_index, f) for f in REQUIRED_TIMESTAMPS)
    nested_found = any(mka.field_exists(field_index, f"timestamps.{f}") for f in REQUIRED_TIMESTAMPS)

    return {
        "source": "read_only_mongodb",
        "database": DATABASE_NAME,
        "generated_from": "live read-only MongoDB analysis",
        "generated_at": snapshot.get("generated_at"),
        "daniel_filter_matches": total_daniel,
        "total_documents": total_documents,
        "timestamp_shape": {
            "top_level_fields_found": top_level_found,
            "nested_timestamps_found": nested_found,
        },
        "services": [
            {"name": "MongoDB", "status": "Connected", "detail": "Read-only connection active"},
            {"name": "Kafka", "status": "Waiting", "detail": "No live service telemetry"},
            {"name": "Redis", "status": "Waiting", "detail": "No live service telemetry"},
            {"name": "ChromaDB", "status": "Waiting", "detail": "No live service telemetry"},
        ],
        "pipeline_status": {
            "status": str(pipeline_value).title() if pipeline_value else "Unknown",
            "reason": "Inferred from MongoDB event freshness; live service status is not separately validated.",
        },
        "top_kpis": top_kpis,
        "latency": {
            "segments": segments,
            "missing_fields": missing_field_names,
            "parseability": {f: presence[f] for f in REQUIRED_TIMESTAMPS},
            "notes": ["Latency segments are computed only where both timestamps exist and parse."],
        },
        "event_success_rate": {
            "status": availability_of("Event Success Rate"),
            "success": success,
            "failure": failure,
            "unknown": unknown + pending,
            "total": success + failure + pending + unknown,
            "note": None if pct is not None else "No terminal success/failure statuses in sample.",
        },
        "last_robot_action": {
            "status": availability_of("Last Robot Action"),
            "action": (last_action or {}).get("action") or None,
            "object": (last_action or {}).get("object") or None,
            "location": (last_action or {}).get("location") or None,
            "duration_ms": None,
            "note": "Latest timestamped event with an action-like field"
            if last_action
            else "No timestamped robot action found in the sample.",
        },
        "active_collections": {
            "status": "Available" if collections_inspected else "Unavailable",
            "value": f"{collections_with_data} / {collections_inspected}",
            "collections_with_data": collections_with_data,
            "collections_inspected": collections_inspected,
        },
        "failed_events": {
            "status": availability_of("Failed Events"),
            "terminal_failures_detected": failed_count,
            "note": "Counted from sampled terminal failure statuses.",
        },
        "mongo_sync": {
            "collections": collections,
            "summary": {
                "total_documents": total_documents,
                "daniel_filter_matches": total_daniel,
                "collections_with_data": collections_with_data,
                "collections_inspected": collections_inspected,
                "main_latency_blockers": missing_field_names,
            },
        },
        "recent_events": recent_events,
        "missing_telemetry_fields": missing_fields,
        "nlp_guardrails": {
            "status": "documented_not_telemetry_validated",
            "note": "Documented task-focused instructions, not telemetry-validated.",
        },
        "safety": {
            "read_only": True,
            "writes_performed": False,
            "credentials_redacted": True,
        },
    }


@router.get("/kpis")
def get_admin_kpis(_claims: dict = Depends(require_admin)) -> dict[str, Any]:
    """Read-only admin KPI snapshot computed live from MongoDB."""
    return build_admin_kpis()
