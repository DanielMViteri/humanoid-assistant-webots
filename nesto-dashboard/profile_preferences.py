"""
Profile and preference helpers for the Nesto Care dashboard.

The canonical long-term personalization memory is ChromaDB. Streamlit session
state is used so the UI updates immediately during a demo.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import auth_store


DEFAULT_PROFILE = {
    "patient_name": "",
    "preferred_name": "",
    "age": "",
    "next_of_kin_name": "",
    "relationship": "",
    "next_of_kin_phone": "",
    "guardian_contact": {},
    "caregiver_name": "",
    "medicine_name": "",
    "medicine_dose": "",
    "medicine_frequency": "",
    "medicine_time": "",
    "robot_name": "",
    "important_object": "",
    "preferred_language": "",
    "preferred_tone": "",
    "user_preferences": "",
    "care_notes": "",
}


DEMO_PROFILE = {
    "patient_name": "Maria Johnson",
    "preferred_name": "Maria",
    "age": "78",
    "next_of_kin_name": "Anna Smith",
    "relationship": "Daughter",
    "next_of_kin_phone": "+44 7700 900123",
    "guardian_contact": {},
    "caregiver_name": "Anna Smith",
    "medicine_name": "Morning Medicine",
    "medicine_dose": "As prescribed",
    "medicine_frequency": "Twice daily",
    "medicine_time": "09:00 AM",
    "robot_name": "Nesto",
    "important_object": "Cane",
    "preferred_language": "English",
    "preferred_tone": "Calm and direct",
    "user_preferences": "",
    "care_notes": "Calm in the morning",
}

def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _session_from_account(guardian_id: str = "guardian_01", patient_id: str = "") -> dict[str, Any]:
    session = auth_store.get_guardian_session_by_ids(str(guardian_id or "guardian_01"), str(patient_id or ""))
    if session:
        return session
    fallback_patient = {
        "patient_id": str(patient_id or "assigned_patient"),
        "patient_name": "Assigned care profile",
        "preferred_name": "Assigned care profile",
    }
    session = {
        "role": "guardian_caregiver",
        "guardian_id": str(guardian_id or "guardian"),
        "guardian_name": "Guardian / Caregiver",
        "guardian_phone": "",
        "guardian_relationship": "Guardian / Caregiver",
        "assigned_patient_id": fallback_patient["patient_id"],
        "assigned_patient_name": fallback_patient["patient_name"],
        "assigned_patient_preferred_name": fallback_patient["preferred_name"],
        "linked_patients": [fallback_patient],
        "source": "database_login_fallback",
    }
    session.update(
        {
            "userName": session["guardian_name"],
            "linkedPatientId": session["assigned_patient_id"],
            "linkedPatientName": session["assigned_patient_name"],
            "linkedPatientPreferredName": session["assigned_patient_preferred_name"],
        }
    )
    return session


def load_guardian_session(session_state: Any, guardian_id: str = "", patient_id: str = "") -> dict[str, Any]:
    session = _session_from_account(str(guardian_id or "guardian_01"), str(patient_id or ""))
    session_state["active_care_session"] = session
    return session


def _session_from_saved_profile(session_state: Any, profile: dict[str, Any], base_session: dict[str, Any]) -> dict[str, Any] | None:
    if not session_state.get("care_profile_form"):
        return None
    guardian_contact = profile.get("guardian_contact", {}) if isinstance(profile.get("guardian_contact"), dict) else {}
    guardian_name = _first_text(
        guardian_contact.get("name"),
        profile.get("next_of_kin_name"),
        profile.get("caregiver_name"),
        base_session.get("guardian_name"),
    )
    patient_name = _first_text(profile.get("patient_name"), base_session.get("assigned_patient_name"))
    preferred_name = _first_text(profile.get("preferred_name"), patient_name, base_session.get("assigned_patient_preferred_name"))
    patient_id = _first_text(profile.get("patient_id"), profile.get("user_id"), base_session.get("assigned_patient_id"), "elderly_user_01")
    if not guardian_name and not patient_name:
        return None
    session = dict(base_session)
    session.update(
        {
            "role": "guardian_caregiver",
            "guardian_id": base_session.get("guardian_id", "guardian_profile"),
            "guardian_name": guardian_name or "Guardian / Caregiver",
            "guardian_phone": _first_text(guardian_contact.get("phone"), profile.get("next_of_kin_phone"), base_session.get("guardian_phone")),
            "guardian_relationship": _first_text(guardian_contact.get("relationship"), profile.get("relationship"), base_session.get("guardian_relationship"), "Guardian / Caregiver"),
            "assigned_patient_id": patient_id,
            "assigned_patient_name": patient_name or "Elderly User 01",
            "assigned_patient_preferred_name": preferred_name or patient_name or "Elderly User 01",
            "source": "saved_profile",
            "linked_patients": [{"patient_id": patient_id, "patient_name": patient_name or "Elderly User 01", "preferred_name": preferred_name or patient_name or "Elderly User 01"}],
        }
    )
    session.update(
        {
            "userName": session["guardian_name"],
            "linkedPatientId": session["assigned_patient_id"],
            "linkedPatientName": session["assigned_patient_name"],
            "linkedPatientPreferredName": session["assigned_patient_preferred_name"],
        }
    )
    return session


def ensure_active_care_session(session_state: Any) -> dict[str, Any]:
    current = session_state.get("active_care_session")
    base_session = dict(current) if isinstance(current, dict) else _session_from_account()
    profile_session = _session_from_saved_profile(session_state, get_profile(session_state), base_session)
    session = profile_session or base_session
    session_state["active_care_session"] = session
    return session



def build_profile_memory_payload(profile: dict[str, str]) -> dict[str, Any]:
    raw_age = str(profile.get("age", "") or "").strip()
    try:
        age_value: int | str = int(raw_age)
    except ValueError:
        age_value = raw_age
    guardian_contact = {
        "name": str(profile.get("next_of_kin_name", "") or "").strip(),
        "relationship": str(profile.get("relationship", "") or "").strip(),
        "phone": str(profile.get("next_of_kin_phone", "") or "").strip(),
        "caregiver_name": str(profile.get("caregiver_name", "") or profile.get("next_of_kin_name", "") or "").strip(),
        "role": "Guardian / Caregiver",
    }
    medicine_routine = [
        {
            "medicine_name": str(profile.get("medicine_name", "") or "").strip(),
            "dose": str(profile.get("medicine_dose", "") or "").strip(),
            "frequency": str(profile.get("medicine_frequency", "") or "").strip(),
            "reminder_time": str(profile.get("medicine_time", "") or "").strip(),
        }
    ]
    for item in profile.get("additional_medicines", []) or []:
        if not isinstance(item, dict):
            continue
        row = {
            "medicine_name": str(item.get("medicine_name", "") or "").strip(),
            "dose": str(item.get("dose", "") or "").strip(),
            "frequency": str(item.get("frequency", "") or "").strip(),
            "reminder_time": str(item.get("reminder_time", "") or "").strip(),
        }
        if any(row.values()):
            medicine_routine.append(row)
    preferences = {
        "important_object": str(profile.get("important_object", "") or "").strip(),
        "nesto_tone": str(profile.get("preferred_tone", "") or "").strip(),
        "preferred_language": str(profile.get("preferred_language", "") or "").strip(),
        "care_notes": str(profile.get("care_notes", "") or "").strip(),
    }
    extra_notes = str(profile.get("user_preferences", "") or "").strip()
    if extra_notes:
        preferences["extra_memory_notes"] = extra_notes
    consent = profile.get("consent", {}) if isinstance(profile.get("consent", {}), dict) else {}
    return {
        "user_id": str(profile.get("user_id") or profile.get("patient_id") or "elderly_user_01"),
        "full_name": str(profile.get("patient_name", "") or "").strip(),
        "preferred_name": str(profile.get("preferred_name", "") or "").strip(),
        "age": age_value,
        "robot_name": str(profile.get("robot_name", "") or "").strip(),
        "robot_id": str(profile.get("robot_id") or "H1"),
        "guardian_contact": guardian_contact,
        "medicine_routine": medicine_routine,
        "preferences": preferences,
        "consent": {
            "terms_accepted": bool(consent.get("terms_accepted")),
            "privacy_accepted": bool(consent.get("privacy_accepted")),
            "consent_checklist_accepted": bool(consent.get("consent_checklist_accepted")),
            "accepted_at": str(consent.get("accepted_at", "") or "").strip(),
        },
        "next_of_kin": "legacy alias for guardian_contact",
    }


def _merge_non_empty(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    for key, value in (update or {}).items():
        if isinstance(value, dict):
            current = base.get(key) if isinstance(base.get(key), dict) else {}
            merged = dict(current)
            _merge_non_empty(merged, value)
            if merged:
                base[key] = merged
        elif isinstance(value, list):
            if value:
                base[key] = value
        elif str(value or "").strip():
            base[key] = value
    return base


def _profile_payload_to_form(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    guardian = payload.get("guardian_contact") if isinstance(payload.get("guardian_contact"), dict) else {}
    preferences = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else {}
    medicine_routine = payload.get("medicine_routine") or payload.get("medicine_schedule") or []
    primary_medicine = medicine_routine[0] if isinstance(medicine_routine, list) and medicine_routine else {}
    if not isinstance(primary_medicine, dict):
        primary_medicine = {}
    additional = medicine_routine[1:] if isinstance(medicine_routine, list) else []
    return {
        "user_id": _first_text(payload.get("user_id"), payload.get("patient_id")),
        "patient_id": _first_text(payload.get("patient_id"), payload.get("user_id")),
        "patient_name": _first_text(payload.get("full_name"), payload.get("patient_name")),
        "preferred_name": _first_text(payload.get("preferred_name"), payload.get("full_name"), payload.get("patient_name")),
        "age": _first_text(payload.get("age")),
        "next_of_kin_name": _first_text(guardian.get("name"), payload.get("guardian_name"), payload.get("next_of_kin_name")),
        "relationship": _first_text(guardian.get("relationship"), payload.get("guardian_relationship"), payload.get("relationship")),
        "next_of_kin_phone": _first_text(guardian.get("phone"), payload.get("guardian_phone"), payload.get("next_of_kin_phone")),
        "guardian_contact": guardian,
        "caregiver_name": _first_text(guardian.get("caregiver_name"), guardian.get("name"), payload.get("caregiver_name")),
        "medicine_name": _first_text(primary_medicine.get("medicine_name"), payload.get("medicine_name")),
        "medicine_dose": _first_text(primary_medicine.get("dose"), payload.get("medicine_dose")),
        "medicine_frequency": _first_text(primary_medicine.get("frequency"), payload.get("medicine_frequency")),
        "medicine_time": _first_text(primary_medicine.get("reminder_time"), primary_medicine.get("scheduled_time"), payload.get("medicine_time")),
        "additional_medicines": [item for item in additional if isinstance(item, dict)],
        "robot_name": _first_text(payload.get("robot_name")),
        "robot_id": _first_text(payload.get("robot_id")),
        "important_object": _first_text(preferences.get("important_object"), payload.get("important_object")),
        "preferred_language": _first_text(preferences.get("preferred_language"), payload.get("preferred_language")),
        "preferred_tone": _first_text(preferences.get("nesto_tone"), preferences.get("tone"), payload.get("preferred_tone")),
        "user_preferences": _first_text(preferences.get("extra_memory_notes"), payload.get("user_preferences")),
        "care_notes": _first_text(preferences.get("care_notes"), payload.get("care_notes")),
        "consent": payload.get("consent") if isinstance(payload.get("consent"), dict) else {},
    }


def _profile_from_active_session(session_state: Any) -> dict[str, Any]:
    session = session_state.get("active_user_session") if isinstance(session_state.get("active_user_session"), dict) else {}
    care_session = session_state.get("active_care_session") if isinstance(session_state.get("active_care_session"), dict) else {}
    role = session.get("role")
    if role == "elderly_user":
        user_id = _first_text(session.get("user_id"), session.get("profile_id"))
        display_name = _first_text(session.get("display_name"), session.get("username"), "Elderly user")
        return {
            "user_id": user_id,
            "patient_id": user_id,
            "patient_name": display_name,
            "preferred_name": display_name.split(" ")[0] if display_name else "",
        }
    if role == "guardian_caregiver" or care_session:
        patient_id = _first_text(care_session.get("assigned_patient_id"), session.get("active_patient_id"))
        patient_name = _first_text(care_session.get("assigned_patient_name"), patient_id)
        preferred = _first_text(care_session.get("assigned_patient_preferred_name"), patient_name)
        guardian_name = _first_text(care_session.get("guardian_name"), session.get("display_name"))
        return {
            "user_id": patient_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "preferred_name": preferred,
            "next_of_kin_name": guardian_name,
            "relationship": _first_text(care_session.get("guardian_relationship"), "Guardian / Caregiver"),
            "next_of_kin_phone": _first_text(care_session.get("guardian_phone")),
            "caregiver_name": guardian_name,
            "guardian_contact": {
                "name": guardian_name,
                "relationship": _first_text(care_session.get("guardian_relationship"), "Guardian / Caregiver"),
                "phone": _first_text(care_session.get("guardian_phone")),
                "role": "Guardian / Caregiver",
            },
        }
    return {}


def _profile_from_mongodb(user_id: str) -> dict[str, Any]:
    if not str(user_id or "").strip():
        return {}
    try:
        import db_queries

        doc = db_queries._db["user_profiles"].find_one(
            {
                "$or": [
                    {"user_id": user_id},
                    {"patient_id": user_id},
                    {"profile_id": user_id},
                    {"event_id": f"profile_{user_id}"},
                    {"payload.user_id": user_id},
                    {"payload.patient_id": user_id},
                ]
            },
            sort=[("timestamp", -1), ("updated_at", -1), ("_id", -1)],
        )
        if not isinstance(doc, dict):
            return {}
        payload = doc.get("payload") if isinstance(doc, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        return _profile_payload_to_form({**payload, "user_id": payload.get("user_id") or doc.get("user_id")})
    except Exception:
        return {}


def _profile_from_chromadb(user_id: str) -> dict[str, Any]:
    if not str(user_id or "").strip():
        return {}
    try:
        import memory_store

        result = memory_store.read_profile_memory(user_id)
        memory = result.get("memory") if isinstance(result, dict) else {}
        metadata = memory.get("metadata") if isinstance(memory, dict) else {}
        if not isinstance(metadata, dict):
            return {}
        preferred_name = _first_text(metadata.get("preferred_name"))
        if preferred_name.lower() in {"connection proof", "proof user"}:
            return {}
        return {
            "user_id": _first_text(metadata.get("user_id"), user_id),
            "patient_id": _first_text(metadata.get("user_id"), user_id),
            "patient_name": preferred_name,
            "preferred_name": preferred_name,
            "next_of_kin_name": _first_text(metadata.get("guardian_name")),
            "relationship": _first_text(metadata.get("guardian_relationship")),
            "next_of_kin_phone": _first_text(metadata.get("guardian_phone")),
            "caregiver_name": _first_text(metadata.get("guardian_name")),
            "guardian_contact": {
                "name": _first_text(metadata.get("guardian_name")),
                "relationship": _first_text(metadata.get("guardian_relationship")),
                "phone": _first_text(metadata.get("guardian_phone")),
                "role": "Guardian / Caregiver",
            },
            "robot_name": _first_text(metadata.get("robot_name")),
            "robot_id": _first_text(metadata.get("robot_id")),
            "important_object": _first_text(metadata.get("important_object")),
            "preferred_language": _first_text(metadata.get("preferred_language")),
        }
    except Exception:
        return {}


def get_profile(session_state: Any) -> dict[str, str]:
    profile = dict(DEFAULT_PROFILE)
    session_profile = _profile_from_active_session(session_state)
    _merge_non_empty(profile, session_profile)
    profile_id = _first_text(profile.get("patient_id"), profile.get("user_id"), "elderly_user_01")
    _merge_non_empty(profile, _profile_from_chromadb(profile_id))
    _merge_non_empty(profile, _profile_from_mongodb(profile_id))
    _merge_non_empty(profile, session_state.get("care_profile_form", {}))
    if not profile.get("guardian_contact"):
        profile["guardian_contact"] = {
            "name": profile.get("next_of_kin_name", ""),
            "relationship": profile.get("relationship", ""),
            "phone": profile.get("next_of_kin_phone", ""),
            "role": "Guardian / Caregiver",
        }
    return profile


def save_profile(session_state: Any, profile: dict[str, str]) -> bool:
    cleaned: dict[str, Any] = {}
    for key, value in profile.items():
        if key == "guardian_contact":
            continue
        if key == "additional_medicines":
            cleaned[key] = value if isinstance(value, list) else []
        elif key == "consent":
            cleaned[key] = value if isinstance(value, dict) else {}
        else:
            cleaned[key] = str(value or "").strip()
    memory_payload = build_profile_memory_payload(cleaned)
    guardian_contact = memory_payload["guardian_contact"]
    cleaned["guardian_contact"] = guardian_contact
    cleaned["next_of_kin"] = "legacy alias for guardian_contact"
    cleaned["memory_payload"] = memory_payload
    session_state["care_profile_form"] = cleaned
    ensure_active_care_session(session_state)

    text = (
        f"Care profile for {cleaned.get('patient_name')} preferred as {cleaned.get('preferred_name')}: "
        f"age {cleaned.get('age')}, guardian contact {guardian_contact['name']} "
        f"({guardian_contact['relationship']}, {guardian_contact['phone']}), "
        f"caregiver {cleaned.get('caregiver_name')}, robot name {cleaned.get('robot_name')}, "
        f"medicine routine {cleaned.get('medicine_name')} {cleaned.get('medicine_dose')} "
        f"{cleaned.get('medicine_frequency')} at {cleaned.get('medicine_time')}, "
        f"important object {cleaned.get('important_object')}, language {cleaned.get('preferred_language')}, "
        f"tone {cleaned.get('preferred_tone')}, preferences {cleaned.get('user_preferences')}, "
        f"care notes {cleaned.get('care_notes')}."
    )
    metadata = {
        "type": "profile_preference",
        "source": "dashboard_profile_form",
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        "patient": cleaned.get("patient_name", ""),
        "robot": cleaned.get("robot_name", "Nesto"),
        "next_of_kin": "legacy alias for guardian_contact",
    }

    chroma_saved = False
    try:
        import memory_store

        chroma_result = memory_store.save_profile_memory(memory_payload)
        chroma_saved = bool(chroma_result.get("connected"))
    except Exception:
        chroma_saved = False

    try:
        import cache_layer

        cache_layer.invalidate("nesto:")
    except Exception:
        pass

    try:
        import db_queries

        db_queries.upsert_profile_record(
            memory_payload,
            status="saved",
            role="caregiver",
            source_page="Profile & Preferences",
        )
    except Exception:
        pass

    return chroma_saved
