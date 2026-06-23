"""Per-user profile resolution, reusing profile_preferences' pure helpers.

profile_preferences.get_profile() reads Streamlit session_state; the underlying
source readers (`_profile_from_mongodb` / `_profile_from_chromadb` / `_merge_non_empty`
/ `DEFAULT_PROFILE`) are pure and parameterised by user_id, so we compose them here
in the same precedence get_profile uses (default < chromadb < mongodb).
"""
from __future__ import annotations

from ..nesto import memory_store, profile_preferences as pp

# Object memory is written by the robot bridge under the robot's world-scoped id.
OBJECT_MEMORY_USER_ID = "elderly_user_01"


def resolve_profile(user_id: str) -> dict:
    """Resolve a patient's care profile (preferred name, robot name, important object, guardian)."""
    profile = dict(pp.DEFAULT_PROFILE)
    pp._merge_non_empty(profile, pp._profile_from_chromadb(user_id))
    pp._merge_non_empty(profile, pp._profile_from_mongodb(user_id))
    return profile


def remembered_object_location(user_id: str, object_key: str) -> str | None:
    """Room the robot last found this object in (ChromaDB), or None.

    The bridge writes object memory under OBJECT_MEMORY_USER_ID, so try both that
    and the patient id (mirrors the old dashboard's _remembered_object_location).
    """
    if not object_key:
        return None
    for uid in (user_id, OBJECT_MEMORY_USER_ID):
        if not uid:
            continue
        try:
            result = memory_store.read_object_memory(uid, object_key)
        except Exception:
            continue
        if not (isinstance(result, dict) and result.get("status") == "found"):
            continue
        metadata = ((result.get("memory") or {}).get("metadata")) or {}
        location = metadata.get("location")
        if location:
            return str(location)
    return None
