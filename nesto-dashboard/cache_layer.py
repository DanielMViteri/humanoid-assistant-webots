"""
Redis-compatible cache layer for Nesto Care.

Redis is used as a speed layer for repeated dashboard reads. The app keeps
working without a local Redis server by falling back to an in-process TTL cache,
which is enough for demos and local development.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable


_LOCAL_CACHE: dict[str, tuple[float, Any]] = {}


def _redis_client():
    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, socket_connect_timeout=0.25, socket_timeout=0.5)
        client.ping()
        return client
    except Exception:
        return None


def cache_status() -> dict[str, Any]:
    client = _redis_client()
    if client is None:
        return {
            "available": False,
            "mode": "local_ttl_fallback",
            "keys": len(_LOCAL_CACHE),
            "ttl_policy": "5s live data, 300s non-critical data",
        }
    try:
        info = client.info(section="server")
        return {
            "available": True,
            "mode": "redis",
            "version": info.get("redis_version", "unknown"),
            "ttl_policy": "5s live data, 300s non-critical data",
        }
    except Exception:
        return {"available": True, "mode": "redis", "ttl_policy": "5s/300s"}


def set_json(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Store a JSON-serializable value in Redis, or local TTL fallback."""
    now = time.time()
    client = _redis_client()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, json.dumps(value, default=str))
            return True
        except Exception:
            pass
    _LOCAL_CACHE[key] = (now + ttl_seconds, value)
    return True


def get_json(key: str, default: Any = None) -> Any:
    """Read a JSON value from Redis first, then local TTL fallback."""
    now = time.time()
    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw is not None:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
    item = _LOCAL_CACHE.get(key)
    if item and item[0] > now:
        return item[1]
    return default


def set_latest_event(collection_name: str, event: dict[str, Any], ttl_seconds: int = 300) -> bool:
    """Cache the latest event for dashboard Redis-first reads."""
    if not collection_name:
        return False
    ok = set_json(f"{collection_name}:latest", event, ttl_seconds=ttl_seconds)
    payload = event.get("payload") if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    user_id = payload.get("user_id") or (event.get("user_id") if isinstance(event, dict) else None)
    guardian = payload.get("guardian_contact") if isinstance(payload, dict) else {}
    guardian_id = guardian.get("id") if isinstance(guardian, dict) else None
    if user_id:
        set_json(f"dashboard:elderly:{user_id}:summary", event, ttl_seconds=ttl_seconds)
    if guardian_id:
        set_json(f"dashboard:guardian:{guardian_id}:summary", event, ttl_seconds=ttl_seconds)
    set_json("dashboard:admin:latest_event", event, ttl_seconds=ttl_seconds)
    return ok


def get_latest_event(collection_name: str) -> Any:
    return get_json(f"{collection_name}:latest")


def get_or_set(key: str, loader: Callable[[], Any], ttl_seconds: int = 5) -> Any:
    now = time.time()
    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw is not None:
                return json.loads(raw)
            value = loader()
            client.setex(key, ttl_seconds, json.dumps(value, default=str))
            return value
        except Exception:
            pass

    item = _LOCAL_CACHE.get(key)
    if item and item[0] > now:
        return item[1]
    value = loader()
    _LOCAL_CACHE[key] = (now + ttl_seconds, value)
    return value


def invalidate(prefix: str = "nesto:") -> int:
    removed = 0
    for key in list(_LOCAL_CACHE):
        if key.startswith(prefix):
            _LOCAL_CACHE.pop(key, None)
            removed += 1
    client = _redis_client()
    if client is not None:
        try:
            keys = list(client.scan_iter(f"{prefix}*"))
            if keys:
                removed += client.delete(*keys)
        except Exception:
            pass
    return removed
