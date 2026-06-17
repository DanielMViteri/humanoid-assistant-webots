"""ChromaDB-backed conversation memory for the humanoid assistant."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from event_schema import current_epoch_ms
from mongo_client import PROJECT_ROOT


DEFAULT_MEMORY_DIR = PROJECT_ROOT / "data" / "processed" / "chroma_memory"
DEFAULT_COLLECTION = "assistant_memory"
EMBEDDING_DIMENSION = 128
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_']+")


def chroma_error_hint(error: Exception) -> str:
    """Return a short operator-friendly ChromaDB troubleshooting hint."""
    message = str(error).lower()
    if "chromadb" in error.__class__.__name__.lower() or "chromadb" in message:
        return "ChromaDB operation failed. Check that requirements-perception.txt is installed in the active environment."
    if "no module named" in message:
        return "ChromaDB is not installed. Run: pip install -r requirements-perception.txt"
    return "Memory storage failed. Check the local Chroma path and optional perception dependencies."


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _hashed_embedding(text: str, *, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Create a deterministic local embedding without external model downloads."""
    vector = np.zeros(dimension, dtype=np.float32)
    for token in _tokenize(text):
        bucket = hash(token) % dimension
        sign = 1.0 if (hash(f"{token}:sign") % 2 == 0) else -1.0
        vector[bucket] += sign

    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return vector.tolist()


def _flatten_metadata(metadata: dict[str, Any] | None) -> dict[str, str | int | float | bool]:
    flattened: dict[str, str | int | float | bool] = {}
    for key, value in (metadata or {}).items():
        if isinstance(value, (str, int, float, bool)):
            flattened[key] = value
        elif value is None:
            continue
        else:
            flattened[key] = str(value)
    return flattened


class ChromaMemoryStore:
    """Small wrapper around a persistent Chroma collection for conversation memory."""

    def __init__(self, persist_directory: Path = DEFAULT_MEMORY_DIR, collection_name: str = DEFAULT_COLLECTION) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed. Run: pip install -r requirements-perception.txt") from exc

        persist_directory.mkdir(parents=True, exist_ok=True)
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        persistent_client = getattr(chromadb, "PersistentClient", None)
        if persistent_client is not None:
            self.client = persistent_client(path=str(persist_directory))
        else:
            settings_cls = getattr(chromadb, "Settings", None)
            if settings_cls is None:
                self.client = chromadb.Client()
            else:
                self.client = chromadb.Client(
                    settings=settings_cls(is_persistent=True, persist_directory=str(persist_directory))
                )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Humanoid assistant conversation memory"},
        )

    @classmethod
    def from_env(cls, collection_name: str | None = None) -> "ChromaMemoryStore":
        persist_dir = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", str(DEFAULT_MEMORY_DIR)))
        collection = collection_name or os.getenv("CHROMA_COLLECTION", DEFAULT_COLLECTION)
        return cls(persist_directory=persist_dir, collection_name=collection)

    def add_memory(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
    ) -> str:
        memory_text = text.strip()
        if not memory_text:
            raise ValueError("memory text must be non-empty")

        identifier = memory_id or f"mem_{current_epoch_ms()}_{uuid4().hex[:8]}"
        flattened = _flatten_metadata(metadata)
        flattened.setdefault("stored_at", current_epoch_ms())

        self.collection.add(
            ids=[identifier],
            documents=[memory_text],
            metadatas=[flattened],
            embeddings=[_hashed_embedding(memory_text)],
        )
        return identifier

    def store_exchange(self, user_text: str, robot_text: str, decision: dict[str, Any]) -> list[str]:
        timestamp = current_epoch_ms()
        shared_metadata = {
            "intent": decision.get("intent", "unknown"),
            "risk_level": decision.get("risk_level", "low"),
            "emotion": decision.get("emotion", "neutral"),
            "timestamp": timestamp,
        }
        user_memory_id = self.add_memory(
            user_text,
            metadata={**shared_metadata, "speaker": "user", "role": "request"},
        )
        robot_memory_id = self.add_memory(
            robot_text,
            metadata={**shared_metadata, "speaker": "assistant", "role": "response"},
        )
        return [user_memory_id, robot_memory_id]

    def query(self, query_text: str, *, top_k: int = 3) -> list[dict[str, Any]]:
        question = query_text.strip()
        if not question:
            return []

        results = self.collection.query(
            query_embeddings=[_hashed_embedding(question)],
            n_results=max(1, top_k),
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        hits: list[dict[str, Any]] = []
        for identifier, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            hits.append(
                {
                    "id": identifier,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": float(distance) if distance is not None else None,
                }
            )
        return hits


def build_memory_context(hits: list[dict[str, Any]]) -> str:
    """Format retrieved memories into a compact prompt block."""
    if not hits:
        return ""

    lines = []
    for index, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata", {})
        speaker = metadata.get("speaker", "memory")
        intent = metadata.get("intent", "unknown")
        distance = hit.get("distance")
        distance_text = f"{distance:.3f}" if isinstance(distance, float) else "n/a"
        lines.append(f"{index}. [{speaker} | intent={intent} | distance={distance_text}] {hit['document']}")
    return "\n".join(lines)
