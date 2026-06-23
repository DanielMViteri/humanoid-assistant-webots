"""Patient (elderly) experience: home data, actions, and live reads.

Action writes use the SAME db_queries helpers the Streamlit app used, so the
events are byte-compatible with the robot bridge (source "dashboard", same
collections + markers): find -> scenario_events, mood -> mood_events,
press-to-talk -> conversation_events(voice_listen / trigger=press_to_talk).
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_current_user, patient_id_for
from ..nesto import data_layer, db_queries
from ..services.profile import remembered_object_location, resolve_profile

router = APIRouter(prefix="/api/patient", tags=["patient"])

SOURCE_PAGE = "web-patient"


def _guardian(profile: dict) -> dict:
    contact = profile.get("guardian_contact") or {}
    return {
        "name": profile.get("next_of_kin_name") or contact.get("name") or "Guardian / Caregiver",
        "phone": profile.get("next_of_kin_phone") or contact.get("phone") or "",
        "relationship": profile.get("relationship") or contact.get("relationship") or "Guardian / Caregiver",
    }


@router.get("/home")
def home(claims: dict = Depends(get_current_user)):
    pid = patient_id_for(claims)
    profile = resolve_profile(pid)
    guardian = _guardian(profile)
    return {
        "patient": {
            "name": profile.get("preferred_name") or profile.get("patient_name") or claims.get("name") or "Friend",
            "robot_name": profile.get("robot_name") or "Nesto",
            "important_object": (profile.get("important_object") or "Cane"),
            "medicine_name": profile.get("medicine_name") or "Morning medicine",
            "medicine_time": profile.get("medicine_time") or "09:00 AM",
            "guardian": guardian,
        },
        "robot": data_layer.robot_status(use_live=True),
    }


# --------------------------------------------------------------------------- #
# Actions (write events the robot bridge consumes)
# --------------------------------------------------------------------------- #
class FindBody(BaseModel):
    object: str | None = None  # "cane" | "medicine" | None (defaults to the important object)


@router.post("/find-object")
def find_object(body: FindBody, claims: dict = Depends(get_current_user)):
    raw = (body.object or "").strip().lower()
    if raw in {"medicine", "medicine_box", "medication", "pills"}:
        scenario, target = "find_medicine", "medicine_box"
    else:
        scenario, target = "find_cane", "cane"
    location = remembered_object_location(patient_id_for(claims), target)
    db_queries.create_scenario_event(
        scenario,
        payload={"object": target, "target_object": target, "last_known_location": location, "search_status": "requested"},
        status="requested",
        role="elderly_user",
        source_page=SOURCE_PAGE,
    )
    return {"ok": True, "scenario": scenario, "target": target, "remembered_location": location}


class MoodBody(BaseModel):
    mood: str


@router.post("/mood")
def mood(body: MoodBody, claims: dict = Depends(get_current_user)):
    db_queries.create_mood_event(
        payload={"mood": body.mood, "clinical": False},
        status="recorded",
        role="elderly_user",
        source_page=SOURCE_PAGE,
    )
    return {"ok": True, "tapped_at_ms": int(time.time() * 1000)}


@router.post("/voice/press-to-talk")
def press_to_talk(claims: dict = Depends(get_current_user)):
    db_queries.insert_dashboard_event(
        "conversation_event",
        scenario_type="voice_listen",
        role="elderly_user",
        status="listening",
        source_page=SOURCE_PAGE,
        payload={"trigger": "press_to_talk"},
    )
    return {"ok": True, "pressed_at_ms": int(time.time() * 1000)}


@router.post("/medication-taken")
def medication_taken(claims: dict = Depends(get_current_user)):
    db_queries.create_medicine_event(
        payload={"medicine_status": "taken"}, status="taken", role="elderly_user", source_page=SOURCE_PAGE
    )
    return {"ok": True}


@router.post("/emergency")
def emergency(claims: dict = Depends(get_current_user)):
    db_queries.create_alert_event(
        payload={"alert_type": "emergency", "severity": "high", "status": "active"},
        status="active",
        role="elderly_user",
        source_page=SOURCE_PAGE,
    )
    return {"ok": True}


@router.post("/call")
def call_caregiver(claims: dict = Depends(get_current_user)):
    db_queries.create_scenario_event(
        "call_caregiver",
        payload={"call_status": "requested"},
        status="requested",
        role="elderly_user",
        source_page=SOURCE_PAGE,
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Live reads (polled by the frontend to power the banners)
# --------------------------------------------------------------------------- #
def _coll(name):
    return db_queries._db[name]


@router.get("/mood/latest")
def mood_latest(since_ms: int | None = None, claims: dict = Depends(get_current_user)):
    query: dict = {"event_type": "mood_detected", "payload.trigger": "nesto_dashboard_mood_check"}
    if since_ms:
        query["timestamp"] = {"$gte": int(since_ms) - 3000}
    try:
        doc = _coll("mood_events").find_one(query, sort=[("timestamp", -1)])
    except Exception:
        return {"reading": None}
    if not doc:
        return {"reading": None}
    p = doc.get("payload") or {}
    return {
        "reading": {
            "mood": p.get("mood"),
            "confidence": float(p.get("confidence") or 0.0),
            "capture_mode": p.get("capture_mode", "snapshot"),
            "timestamp": int(doc.get("timestamp") or 0),
        }
    }


@router.get("/voice/latest")
def voice_latest(since_ms: int | None = None, claims: dict = Depends(get_current_user)):
    bound = {"$gte": int(since_ms) - 3000} if since_ms else None

    def latest(event_type: str):
        q: dict = {"event_type": event_type}
        if bound:
            q["timestamp"] = bound
        try:
            return _coll("conversation_events").find_one(q, sort=[("timestamp", -1)])
        except Exception:
            return None

    user_doc = latest("user_message")
    reply_doc = latest("robot_response")
    transcript = None
    if user_doc:
        raw = (user_doc.get("payload") or {}).get("text") or ""
        transcript = str(raw).split("[recall]")[0].strip()  # strip the internal NLP recall note
    reply = (reply_doc.get("payload") or {}).get("text") if reply_doc else None
    if not transcript and not reply:
        return {"exchange": None}
    return {"exchange": {"transcript": transcript, "reply": reply}}


@router.get("/object-memory/{object_key}")
def object_memory(object_key: str, claims: dict = Depends(get_current_user)):
    target = "medicine_box" if object_key.lower() in {"medicine", "medicine_box", "medication"} else "cane"
    return {"object": target, "location": remembered_object_location(patient_id_for(claims), target)}
