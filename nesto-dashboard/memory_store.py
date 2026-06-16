"""
ChromaDB memory store for the Nesto Care app.

Purpose:
This file is responsible for long-term conversation memory and
personalization memory. The Streamlit app can save scenario events here and
search them later so Nesto can respond using previous context.

Important:
The app still works if ChromaDB is not installed. In that case, these
functions return safe fallback values so the dashboard does not crash during
local runs or presentation checks.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path


# ----------------------------------------------------------------------
# MEMORY CONFIGURATION
# ----------------------------------------------------------------------
# Purpose:
# Keep ChromaDB files inside the project folder so memory persists between
# app runs but does not require an external database server.
CHROMA_DIR = Path(__file__).parent / "chroma_memory"
COLLECTION_NAME = "elderly_assistant_memory"


def _get_collection():
    """
    Purpose:
    Lazily connect to ChromaDB only when memory is used. This keeps app startup
    faster and avoids crashing if chromadb has not been installed yet.
    """
    try:
        os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client.get_or_create_collection(name=COLLECTION_NAME)
    except Exception:
        return None


def chroma_is_available():
    """
    Purpose:
    Let the UI show whether ChromaDB is active or whether the app is using
    temporary Streamlit session memory only.
    """
    return _get_collection() is not None


def memory_status():
    collection = _get_collection()
    if collection is None:
        return {"available": False, "status": "unavailable", "count": 0, "mode": "fallback"}
    try:
        return {"available": True, "status": "connected", "count": collection.count(), "mode": "chromadb"}
    except Exception:
        return {"available": True, "status": "connected", "count": 0, "mode": "chromadb"}


def get_chromadb_status():
    """Return a backend-proof friendly ChromaDB status object."""
    status = memory_status()
    status.update({
        "path": str(CHROMA_DIR),
        "collection": COLLECTION_NAME,
        "profile_memory_api": "save_profile_memory/read_profile_memory",
        "object_memory_api": "save_object_memory/read_object_memory",
    })
    return status


def save_memory(text, metadata=None):
    """
    Purpose:
    Save one memory item into ChromaDB.

    Example memory:
    - "The patient prefers a calm reminder after lunch."
    - metadata: {"type": "scenario", "source": "Scenario Input"}
    """
    collection = _get_collection()
    if collection is None:
        return False

    metadata = metadata or {}
    memory_id = f"memory-{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    metadata.setdefault("saved_at", dt.datetime.now().isoformat(timespec="seconds"))

    try:
        collection.add(
            ids=[memory_id],
            documents=[text],
            metadatas=[metadata],
        )
        return True
    except Exception:
        return False


def upsert_memory(memory_id, text, metadata=None):
    """
    Purpose:
    Save or replace one known memory item in ChromaDB.
    This is useful for tests because it avoids duplicate records every time
    the same proof script is run.
    """
    collection = _get_collection()
    if collection is None:
        return False

    metadata = metadata or {}
    metadata.setdefault("saved_at", dt.datetime.now().isoformat(timespec="seconds"))

    try:
        collection.upsert(
            ids=[memory_id],
            documents=[text],
            metadatas=[metadata],
        )
        return True
    except Exception:
        return False


def save_profile_memory(profile_payload):
    """
    Save profile/preferences memory for NESTO personalization.

    The returned status is internal/backend-facing so UI screens can stay
    friendly while proof scripts can show whether ChromaDB is connected.
    """
    payload = dict(profile_payload or {})
    guardian = payload.get("guardian_contact")
    if guardian and "next_of_kin" not in payload:
        payload["next_of_kin"] = "legacy alias for guardian_contact"

    preferred_name = payload.get("preferred_name") or payload.get("full_name") or "elderly user"
    robot_name = payload.get("robot_name") or "Nesto"
    medicine = payload.get("medicine_schedule") or payload.get("medicine_routine") or payload.get("medicine") or {}
    preferences = payload.get("preferences") or {}
    if not isinstance(guardian, dict):
        guardian = {}
    if not isinstance(preferences, dict):
        preferences = {}
    medicine_count = len(medicine) if isinstance(medicine, list) else int(bool(medicine))

    text = (
        f"{robot_name} care profile for {preferred_name}. "
        f"Guardian / Caregiver: {guardian}. "
        f"Medicine schedule: {medicine}. "
        f"Preferences: {preferences}."
    )
    metadata = {
        "type": "profile_preference",
        "source": "profile_preferences",
        "user_id": str(payload.get("user_id") or "elderly_user_01"),
        "preferred_name": str(preferred_name),
        "robot_name": str(robot_name),
        "guardian_name": str(guardian.get("name") or ""),
        "guardian_relationship": str(guardian.get("relationship") or "Guardian / Caregiver"),
        "guardian_phone": str(guardian.get("phone") or ""),
        "important_object": str(preferences.get("important_object") or ""),
        "preferred_language": str(preferences.get("preferred_language") or ""),
        "medicine_count": int(medicine_count),
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    memory_id = f"profile-{payload.get('user_id') or 'elderly_user_01'}"
    connected = upsert_memory(memory_id, text, metadata=metadata)
    return {
        "connected": connected,
        "mode": "chromadb" if connected else "fallback",
        "memory_id": memory_id,
        "status": "saved" if connected else "not_saved",
    }


def read_profile_memory(user_id):
    """Read back the stable profile/preference memory for one user."""
    collection = _get_collection()
    memory_id = f"profile-{user_id or 'elderly_user_01'}"
    if collection is None:
        return {
            "connected": False,
            "mode": "fallback",
            "memory_id": memory_id,
            "status": "unavailable",
            "memory": None,
        }
    try:
        result = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        if not documents:
            return {
                "connected": True,
                "mode": "chromadb",
                "memory_id": memory_id,
                "status": "not_found",
                "memory": None,
            }
        return {
            "connected": True,
            "mode": "chromadb",
            "memory_id": memory_id,
            "status": "found",
            "memory": {"text": documents[0], "metadata": (metadatas or [{}])[0] or {}},
        }
    except Exception as exc:
        return {
            "connected": True,
            "mode": "chromadb",
            "memory_id": memory_id,
            "status": "error",
            "error": str(exc),
            "memory": None,
        }


def save_object_memory(user_id, object_name, location, metadata=None):
    """Save stable memory for important objects such as cane or medicine box."""
    clean_user = str(user_id or "elderly_user_01").strip() or "elderly_user_01"
    clean_object = str(object_name or "important_object").strip().lower().replace(" ", "_")
    clean_location = str(location or "unknown location").strip()
    memory_id = f"object-{clean_user}-{clean_object}"
    data = dict(metadata or {})
    data.update({
        "type": "object_memory",
        "source": data.get("source", "memory_store.save_object_memory"),
        "user_id": clean_user,
        "object_name": clean_object,
        "location": clean_location,
    })
    text = f"{clean_object.replace('_', ' ').title()} for {clean_user} was last known at {clean_location}."
    connected = upsert_memory(memory_id, text, metadata=data)
    return {
        "connected": connected,
        "mode": "chromadb" if connected else "fallback",
        "memory_id": memory_id,
        "status": "saved" if connected else "not_saved",
    }


def read_object_memory(user_id, object_name):
    """Read back stable object/location memory for one user's object."""
    collection = _get_collection()
    clean_user = str(user_id or "elderly_user_01").strip() or "elderly_user_01"
    clean_object = str(object_name or "important_object").strip().lower().replace(" ", "_")
    memory_id = f"object-{clean_user}-{clean_object}"
    if collection is None:
        return {
            "connected": False,
            "mode": "fallback",
            "memory_id": memory_id,
            "status": "unavailable",
            "memory": None,
        }
    try:
        result = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        if not documents:
            return {
                "connected": True,
                "mode": "chromadb",
                "memory_id": memory_id,
                "status": "not_found",
                "memory": None,
            }
        return {
            "connected": True,
            "mode": "chromadb",
            "memory_id": memory_id,
            "status": "found",
            "memory": {"text": documents[0], "metadata": (metadatas or [{}])[0] or {}},
        }
    except Exception as exc:
        return {
            "connected": True,
            "mode": "chromadb",
            "memory_id": memory_id,
            "status": "error",
            "error": str(exc),
            "memory": None,
        }


def search_memories(query, limit=3):
    """
    Purpose:
    Search ChromaDB for memories related to the current scenario.
    The result helps verify personalization and conversation memory.
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        results = collection.query(query_texts=[query], n_results=limit)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
    except Exception:
        return []

    memories = []
    for document, metadata in zip(documents, metadatas):
        memories.append({
            "text": document,
            "metadata": metadata or {},
        })
    return memories


def get_latest_memories(limit=5, allowed_types=None):
    """
    Purpose:
    Return the newest saved memories already stored in ChromaDB.

    allowed_types lets each UI surface show the right kind of memory:
    caregiver notes on the wellbeing page, care requests in chat, and scenario
    evidence in terminal checks.
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        results = collection.get(include=["documents", "metadatas"])
    except Exception:
        return []

    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    allowed = set(allowed_types) if allowed_types else None

    memories = []
    for document, metadata in zip(documents, metadatas):
        metadata = metadata or {}
        if allowed is not None and metadata.get("type") not in allowed:
            continue

        memories.append({
            "text": document,
            "metadata": metadata,
            "saved_at": metadata.get("saved_at") or metadata.get("created") or "",
        })

    memories.sort(key=lambda item: item["saved_at"], reverse=True)
    return memories[:limit]


def get_latest_scenario_memories(limit=5):
    """
    Purpose:
    Return the newest scenario memories already stored in ChromaDB.
    This supports the real app flow: Scenario Input saves a care event, then
    the app or terminal health check can confirm that same saved event exists.
    """
    return get_latest_memories(limit=limit, allowed_types={"scenario"})
