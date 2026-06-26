"""Tests for the admin KPI route.

Covers:
- the admin-only role guard (401 unauthenticated, 403 non-admin, 200 admin),
- the response-shape contract the frontend adapter asserts,
- that the live mapping turns a complete timestamp chain into REAL latency
  numbers (the "make Unavailable latency real" fix), using an in-memory fake
  Mongo so no network/Atlas is required.

Run from web/backend:  python -m pytest tests/ -q
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.main as main_module  # noqa: E402
from app.routers import admin as admin_module  # noqa: E402
from app.security import create_access_token  # noqa: E402

client = TestClient(main_module.app)


def _auth_header(role: str) -> dict[str, str]:
    token = create_access_token({"sub": "u1", "role": role, "name": "T", "patient_id": "p1"})
    return {"Authorization": f"Bearer {token}"}


# --- a minimal but contract-complete payload for the guard/shape tests -------- #
def _fixture_payload() -> dict:
    return {
        "source": "read_only_mongodb",
        "database": "humanoid_assistant",
        "generated_at": "2026-06-26T00:00:00+00:00",
        "daniel_filter_matches": 1,
        "total_documents": 1,
        "timestamp_shape": {"top_level_fields_found": True, "nested_timestamps_found": False},
        "services": [{"name": "MongoDB", "status": "Connected", "detail": "ok"}],
        "top_kpis": [{"id": f"k{i}", "label": f"K{i}", "status": "Available", "value": "x", "detail": "d", "target": "t"} for i in range(8)],
        "latency": {"segments": [], "missing_fields": [], "parseability": {}, "notes": []},
        "event_success_rate": {"status": "Available", "success": 1, "failure": 0, "unknown": 0, "total": 1},
        "last_robot_action": {"status": "Partial", "action": "find_cane", "object": "cane", "location": None, "duration_ms": None, "note": "n"},
        "active_collections": {"status": "Available", "value": "1 / 1", "collections_with_data": 1, "collections_inspected": 1},
        "failed_events": {"status": "Available", "terminal_failures_detected": 0, "note": "n"},
        "mongo_sync": {"collections": [], "summary": {}},
        "recent_events": [],
        "missing_telemetry_fields": [],
        "nlp_guardrails": {"status": "documented_not_telemetry_validated", "note": "n"},
        "safety": {"read_only": True, "writes_performed": False, "credentials_redacted": True},
    }


@pytest.fixture()
def stub_build(monkeypatch):
    monkeypatch.setattr(admin_module, "build_admin_kpis", _fixture_payload)


def test_requires_authentication():
    assert client.get("/api/admin/kpis").status_code == 401


def test_forbids_non_admin(stub_build):
    resp = client.get("/api/admin/kpis", headers=_auth_header("elderly_user"))
    assert resp.status_code == 403


def test_admin_gets_contract_shape(stub_build):
    resp = client.get("/api/admin/kpis", headers=_auth_header("admin_provider"))
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "generated_at", "database", "top_kpis", "latency", "event_success_rate",
        "last_robot_action", "mongo_sync", "recent_events", "missing_telemetry_fields",
        "nlp_guardrails", "safety",
    ):
        assert key in data, f"missing contract key: {key}"
    assert isinstance(data["top_kpis"], list) and len(data["top_kpis"]) == 8
    assert isinstance(data["latency"]["segments"], list)
    assert data["safety"]["read_only"] is True
    assert data["safety"]["writes_performed"] is False


# --- prove a complete chain yields REAL latency numbers (the fix) ------------- #
class _Cursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return self


class _Coll:
    def __init__(self, docs):
        self._docs = docs

    def count_documents(self, query):
        if not query:
            return len(self._docs)
        if "$and" in query:
            return len(self._docs)
        return sum(
            1 for d in self._docs
            if d.get("payload", {}).get("active_command_id") and "ui_triggered_at" in d
        )

    def find(self, query=None, projection=None, batch_size=None):
        return _Cursor(self._docs)

    def find_one(self, query=None, sort=None):
        return self._docs[-1] if self._docs else None

    def aggregate(self, pipeline, **k):
        return []


class _DB:
    class _Client:
        class _Admin:
            def command(self, *a, **k):
                return {"ok": 1}

        admin = _Admin()

    client = _Client()

    def __init__(self, data):
        self._data = data

    def list_collection_names(self):
        return list(self._data)

    def __getitem__(self, name):
        return self._data[name]


def _fresh_chain_db():
    now = dt.datetime.now(dt.timezone.utc)
    ms = lambda s: int((now + dt.timedelta(seconds=s)).timestamp() * 1000)
    # A complete, parseable seven-stamp chain mirrored top-level + payload.
    doc = {
        "_id": 1,
        "event_type": "robot_status_updated",
        "status": "target_found",
        "timestamp": ms(2.3),
        "ui_triggered_at": ms(0), "backend_received_at": ms(0.05), "bridge_received_at": ms(0.1),
        "robot_action_started_at": ms(0.2), "robot_action_completed_at": ms(2.0),
        "mongodb_logged_at": ms(2.1), "dashboard_updated_at": ms(2.3),
        "payload": {
            "active_command_id": "cmd1", "task_status": "retrieval_ready", "robot_action": "find_cane",
            "ui_triggered_at": ms(0), "backend_received_at": ms(0.05), "bridge_received_at": ms(0.1),
            "robot_action_started_at": ms(0.2), "robot_action_completed_at": ms(2.0),
            "mongodb_logged_at": ms(2.1), "dashboard_updated_at": ms(2.3),
        },
    }
    return _DB({"scenario_events": _Coll([doc])})


def test_complete_chain_yields_real_latency(monkeypatch):
    monkeypatch.setattr(admin_module.db_queries, "_client_init_error", None, raising=False)
    monkeypatch.setattr(admin_module.db_queries, "_db", _fresh_chain_db(), raising=False)

    data = admin_module.build_admin_kpis()
    segments = {s["stage"]: s for s in data["latency"]["segments"]}

    # Every segment should now be computable with a real median (no invented data).
    for stage in ("UI -> Backend", "Robot Action Duration", "End-to-End"):
        assert segments[stage]["status"] == "Available", f"{stage} not Available"
        assert segments[stage]["median_ms"] is not None, f"{stage} has no median"

    # End-to-end top KPI should now show a real value, not "Unavailable".
    e2e = next(k for k in data["top_kpis"] if k["id"] == "end_to_end_latency")
    assert e2e["status"] == "Available"
    assert e2e["value"].endswith("ms")
    assert data["safety"]["writes_performed"] is False
