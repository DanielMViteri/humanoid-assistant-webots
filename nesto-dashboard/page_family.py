"""
Elderly interface and Guardian / Caregiver dashboard pages.
"""

import datetime as dt
import re
import textwrap
import streamlit as st
import streamlit.components.v1 as components
from html import escape
from urllib.parse import quote

import auth_store

from data_layer import care_metrics, caregiver, patient, recent_activity, save_memory, system_health, robot_status, record_dashboard_event
from profile_preferences import DEFAULT_PROFILE, build_profile_memory_payload, ensure_active_care_session, get_profile, save_profile
from ui_theme import AMBER, BLUE, GREEN, PURPLE, RED, badge, page_header


ELDERLY_ACTIONS = {
    "schedule": {
        "title": "Today's schedule",
        "icon": "&#128197;",
        "short": "See meals, reminders, and the next care task.",
        "speech": "Let's check your plan together.",
        "goal": f"Help {patient()} understand what is happening today without needing to ask the family.",
    },
    "medication": {
        "title": "Medication reminder",
        "icon": "&#128138;",
        "short": "Get a gentle reminder and mark it done.",
        "speech": f"I can remind you gently and let {caregiver()} know.",
        "goal": "Support preset reminders only. Nesto does not give dosage advice.",
    },
    "call": {
        "title": f"Call {caregiver()}",
        "icon": "&#128222;",
        "short": f"Reach family when {patient()} wants reassurance.",
        "speech": f"I can help you reach {caregiver()} now.",
        "goal": f"Keep {patient()} connected with family when reassurance is needed.",
    },
    "chat": {
        "title": "Talk to Nesto",
        "icon": "&#128172;",
        "short": "Ask for help in normal words.",
        "speech": "Tell me what you need. I will use approved care actions.",
        "goal": f"Let {patient()} speak naturally while the system routes only to safe approved scenarios.",
    },
    "mood": {
        "title": "How are you feeling?",
        "icon": "&#128578;",
        "short": "Tap a simple mood check-in.",
        "speech": "You can tap how you feel. No pressure.",
        "goal": "Capture a simple wellbeing signal that the family can understand quickly.",
    },
    "emergency": {
        "title": "Emergency",
        "icon": "&#128737;",
        "short": "Prepare an urgent family alert.",
        "speech": f"I can prepare an urgent alert for {caregiver()}.",
        "goal": "Escalate urgent support to family or care contacts. Nesto is not an emergency-service replacement.",
    },
    "find_cane": {
        "title": "Find My Cane",
        "icon": "&#128269;",
        "short": "Ask Nesto to start the cane search scenario.",
        "speech": "I will start by checking the last known cane location.",
        "goal": "Create a find_cane scenario event for Webots/robot handling.",
    },
    "find_medicine": {
        "title": "Find My Medicine",
        "icon": "&#128138;",
        "short": "Ask Nesto to look for the medicine box.",
        "speech": "I will look for the medicine box using the approved object-finder flow.",
        "goal": "Create a find_medicine scenario event for robot/object search.",
    },
    "summon": {
        "title": "Summon robot",
        "icon": "&#129302;",
        "short": "Ask Nesto to come to the user.",
        "speech": "I will move toward your current room when the robot controller is connected.",
        "goal": "Create a summon_robot scenario event for Webots/robot handling.",
    },
}

ACTION_ORDER = ["schedule", "medication", "call", "chat", "mood", "find_cane", "find_medicine", "summon", "emergency"]

CAREGIVER_ACTIONS = {
    "summary": {
        "title": "Acknowledge update",
        "icon": "&#10003;",
        "short": f"Confirm that {caregiver()} has seen {patient()}'s daily update.",
        "result": "The latest Nesto update is marked as reviewed for the care team.",
    },
    "call": {
        "title": f"Call {patient()}",
        "icon": "&#128222;",
        "short": "Start a reassuring family call.",
        "result": f"Nesto prepares a family call between {caregiver()} and {patient()}.",
    },
    "message": {
        "title": "Message Nesto",
        "icon": "&#128172;",
        "short": "Send a care note or question to the assistant.",
        "result": "Nesto receives the caregiver message and can use it as care context.",
    },
    "alerts": {
        "title": "Review alerts",
        "icon": "&#128276;",
        "short": "Check activity, medication, and safety alerts.",
        "result": f"{caregiver()} can review urgent items first and decide whether to contact {patient()}.",
    },
}

CAREGIVER_ACTION_ORDER = ["summary", "call", "message", "alerts"]


def _care_profile():
    return get_profile(st.session_state)


def _care_name():
    profile = _care_profile()
    return profile.get("preferred_name") or profile.get("patient_name") or patient()


def _robot_name():
    return _care_profile().get("robot_name") or "Nesto"


def _important_object():
    return (_care_profile().get("important_object") or "cane").strip()


def _object_label(value, fallback="cane"):
    text = str(value or fallback or "cane").strip().replace("_", " ")
    return " ".join(part.capitalize() for part in text.split()) or str(fallback).title()


def _active_elderly_context():
    profile = _care_profile()
    session = ensure_active_care_session(st.session_state)
    patient_name = (
        session.get("assigned_patient_preferred_name")
        or session.get("assigned_patient_name")
        or profile.get("preferred_name")
        or profile.get("patient_name")
        or patient()
    )
    guardian_name = (
        session.get("guardian_name")
        or profile.get("next_of_kin_name")
        or profile.get("caregiver_name")
        or caregiver()
    )
    return {
        "patient_id": str(session.get("assigned_patient_id") or profile.get("patient_id") or "elderly_user_01"),
        "patient_name": str(patient_name or "Elderly user"),
        "guardian_id": str(session.get("guardian_id") or profile.get("guardian_id") or "guardian_01"),
        "guardian_name": str(guardian_name or "Guardian / Caregiver"),
        "guardian_phone": str(session.get("guardian_phone") or profile.get("next_of_kin_phone") or ""),
        "relationship": str(session.get("guardian_relationship") or profile.get("relationship") or "Guardian / Caregiver"),
        "robot_id": str(profile.get("robot_id") or "H1"),
        "robot_name": str(profile.get("robot_name") or "Nesto"),
    }


def _append_guardian_update(kind, message, payload=None):
    context = _active_elderly_context()
    update = {
        "kind": kind,
        "message": message,
        "time": dt.datetime.now().strftime("%I:%M %p").lstrip("0"),
        "patient_id": context["patient_id"],
        "patient_name": context["patient_name"],
        "guardian_id": context["guardian_id"],
        "guardian_name": context["guardian_name"],
        "payload": payload or {},
    }
    st.session_state.setdefault("caregiver_notifications", []).append(update)
    st.session_state.setdefault("carebot_actions", []).append({"text": message, "time": update["time"]})
    return update


def _write_elderly_event(event_type, scenario_type, status, message, payload=None, notify_guardian=True):
    context = _active_elderly_context()
    event_payload = {
        "message": message,
        "source": "elderly_user_interface",
        "user_id": context["patient_id"],
        "patient_id": context["patient_id"],
        "patient_name": context["patient_name"],
        "guardian_contact": {
            "id": context["guardian_id"],
            "name": context["guardian_name"],
            "relationship": context["relationship"],
            "phone": context["guardian_phone"],
            "role": "Guardian / Caregiver",
        },
        "robot_id": context["robot_id"],
        "robot_name": context["robot_name"],
        "notify_guardian": notify_guardian,
    }
    event_payload.update(payload or {})
    inserted_id = record_dashboard_event(
        event_type=event_type,
        scenario_type=scenario_type,
        role="elderly_user",
        status=status,
        source_page="Elderly User Interface",
        payload=event_payload,
    )
    if notify_guardian:
        _append_guardian_update(scenario_type or event_type, message, event_payload)
    return inserted_id


def _record_elderly_panel_opened(action):
    info = ELDERLY_ACTIONS.get(action)
    if not info:
        return
    _write_elderly_event(
        "scenario_event",
        f"{action}_opened",
        "opened",
        f"{_care_name()} opened {info['title'].lower()}.",
        payload={"action": action, "label": info["title"]},
        notify_guardian=False,
    )


def _friendly_now():
    return dt.datetime.now().strftime("%I:%M %p").lstrip("0")


def _render_elderly_action_widgets(action, medicine_time, next_walk):
    if (action not in ELDERLY_ACTIONS and action != "settings") or action == "chat":
        return
    st.markdown('<span id="elder-panel" class="elder-action-widget-anchor"></span>', unsafe_allow_html=True)
    if action == "schedule":
        _render_schedule_interaction(medicine_time, next_walk)
    elif action == "medication":
        _render_medication_interaction(medicine_time)
    elif action == "call":
        _render_call_interaction()
    elif action == "find_cane":
        important_object = _important_object() or "cane"
        _render_object_search_interaction(important_object, "find_cane", f"Finding your {_object_label(important_object).lower()}")
    elif action == "find_medicine":
        _render_object_search_interaction("medicine_box", "find_medicine", "Finding your medicine")
    elif action == "mood":
        _render_mood_interaction()
    elif action == "emergency":
        _render_emergency_interaction()
    elif action == "settings":
        _render_settings_interaction()


def _render_schedule_interaction(medicine_time, next_walk):
    _write_once_key = "elder_schedule_viewed_recorded"
    if not st.session_state.get(_write_once_key):
        _write_elderly_event(
            "schedule_event",
            "schedule_viewed",
            "viewed",
            f"{_care_name()} viewed today's schedule.",
            payload={"schedule_date": dt.date.today().isoformat()},
            notify_guardian=False,
        )
        st.session_state[_write_once_key] = True
    rows = [
        ("08:00 AM", "Morning greeting / wellbeing check", "Ready"),
        ("08:30 AM", "Breakfast", "Ready"),
        (medicine_time, "Morning medicine", "Reminder"),
        (next_walk, "Walk reminder", "Next"),
        ("12:00 PM", "Lunch", "Later"),
        ("02:00 PM", "Rest / reading time", "Later"),
        ("06:00 PM", "Evening medicine", "Later"),
        ("08:30 PM", "Bedtime routine", "Later"),
    ]
    items = "".join(
        f'<div class="elder-timeline-row"><b>{escape(time)}</b><span>{escape(label)}</span><em>{escape(status)}</em></div>'
        for time, label, status in rows
    )
    done = st.session_state.get("elder_schedule_task_done")
    _render_html(
        f"""
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128197;</span><div><h3>Today's Schedule</h3><p>Nesto will keep the day simple and gentle.</p></div></div>
            <div class="elder-timeline">{items}</div>
            {f'<div class="elder-success">Lunch check-in marked done at {escape(done)}.</div>' if done else ''}
        </div>
        """
    )
    c1, c2 = st.columns(2)
    if c1.button("Mark task done", type="primary", use_container_width=True, key="elder_schedule_done"):
        done_time = _friendly_now()
        st.session_state["elder_schedule_task_done"] = done_time
        ok = _write_elderly_event(
            "schedule_event",
            "schedule_task_done",
            "done",
            f"{_care_name()} completed a schedule task.",
            payload={"task": "lunch_check_in", "completed_at": done_time},
        )
        if ok:
            st.success("Task marked done. Your Guardian / Caregiver will be updated.")
        else:
            st.info("Nesto saved this action locally and will try again.")
        st.rerun()
    if c2.button("Close", use_container_width=True, key="elder_schedule_close"):
        st.session_state["elderly_action"] = None
        st.rerun()


def _render_medication_interaction(medicine_time):
    profile = _care_profile()
    medicine_name = str(profile.get("medicine_name") or "Morning medicine")
    taken_at = st.session_state.get("elder_medication_taken_at")
    status = f"{escape(medicine_name)} taken at {escape(taken_at)}." if taken_at else f"{escape(medicine_name)} is scheduled for {escape(medicine_time)}."
    _render_html(
        f"""
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128138;</span><div><h3>Take Medication</h3><p>{status}</p></div></div>
            <div class="elder-soft-callout">Nesto records preset reminder status only. It does not give dosage advice.</div>
            {f'<div class="elder-success">Medication marked as taken. Your Guardian / Caregiver will be updated.</div>' if taken_at else ''}
        </div>
        """
    )
    c1, c2 = st.columns(2)
    if c1.button("Mark as taken", type="primary", use_container_width=True, key="elder_med_taken"):
        taken_time = _friendly_now()
        st.session_state["elder_medication_taken_at"] = taken_time
        ok = _write_elderly_event(
            "medicine_event",
            "take_medicine",
            "taken",
            "Medication marked as taken.",
            payload={
                "medicine_status": "taken",
                "medicine_name": medicine_name,
                "taken_at": taken_time,
                "reminder_time": medicine_time,
            },
        )
        if ok:
            st.success("Medication marked as taken. Your Guardian / Caregiver will be updated.")
        else:
            st.info("Nesto saved this action locally and will try again.")
        st.rerun()
    if c2.button("Close", use_container_width=True, key="elder_med_close"):
        st.session_state["elderly_action"] = None
        st.rerun()


def _render_call_interaction():
    context = _active_elderly_context()
    status = st.session_state.get("elder_call_request_status", "ringing")
    title = "Call request sent." if status == "sent" else "Calling Guardian / Caregiver"
    body = "Your Guardian / Caregiver has been notified." if status == "sent" else "Calling your Guardian / Caregiver now..."
    _render_html(
        f"""
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128222;</span><div><h3>{escape(title)}</h3><p>{escape(body)}</p></div></div>
            <div class="elder-call-card">
                <span class="elder-ring-dot"></span>
                <div><b>{escape(context['guardian_name'])}</b><small>{escape(context['relationship'])}</small></div>
            </div>
        </div>
        """
    )
    c1, c2 = st.columns(2)
    if c1.button("Send call request", type="primary", use_container_width=True, key="elder_call_send"):
        st.session_state["elder_call_request_status"] = "sent"
        ok = _write_elderly_event(
            "scenario_event",
            "caregiver_call_requested",
            "requested",
            f"Call request sent to {context['guardian_name']}.",
            payload={"call_status": "requested"},
        )
        if ok:
            st.success("Call request sent.")
        else:
            st.info("Nesto saved this action locally and will try again.")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="elder_call_cancel"):
        st.session_state["elder_call_request_status"] = "cancelled"
        st.info("Call request cancelled.")


def _last_search_location(object_key=None):
    if object_key:
        try:
            import memory_store

            context = _active_elderly_context()
            memory = memory_store.read_object_memory(context.get("patient_id") or "elderly_user_01", object_key)
            payload = memory.get("memory") if isinstance(memory, dict) else {}
            metadata = payload.get("metadata") if isinstance(payload, dict) else {}
            location = metadata.get("location") if isinstance(metadata, dict) else ""
            if location:
                return str(location)
        except Exception:
            pass
    try:
        status = robot_status(use_live=True)
        return str(status.get("room") or "Living Room")
    except Exception:
        return "Living Room"


def _render_object_search_interaction(object_key, scenario_type, title):
    display_object = "medicine box" if object_key == "medicine_box" else object_key
    started_key = f"elder_search_started_{scenario_type}"
    location = _last_search_location(object_key)
    started = st.session_state.get(started_key)
    result = (
        f"Your {display_object} may be in the {location}."
        if started
        else "Last known location unavailable; Nesto can start a room search."
    )
    steps = [
        "Checking last known location...",
        "Searching nearby rooms...",
        f"Looking for {display_object} using object memory...",
    ]
    step_html = "".join(f"<li>{escape(step)}</li>" for step in steps)
    _render_html(
        f"""
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128269;</span><div><h3>{escape(title)}</h3><p>{escape(result)}</p></div></div>
            <div class="elder-search-card">
                <div class="elder-scan-pulse"></div>
                <ol>{step_html}</ol>
            </div>
            {f'<div class="elder-success">Search started. Please wait nearby while Nesto checks the home.</div>' if started else ''}
        </div>
        """
    )
    c1, c2 = st.columns(2)
    if c1.button("Start search", type="primary", use_container_width=True, key=f"elder_start_{scenario_type}"):
        st.session_state[started_key] = _friendly_now()
        ok = _write_elderly_event(
            "scenario_event",
            scenario_type,
            "requested",
            f"Nesto started searching for the {display_object}.",
            payload={
                "object": object_key,
                "target_object": object_key,
                "last_known_location": location,
                "search_status": "requested",
            },
        )
        if ok:
            st.success(f"Nesto is looking for your {display_object}.")
        else:
            st.info("Nesto saved this action locally and will try again.")
        st.rerun()
    if c2.button("Close", use_container_width=True, key=f"elder_close_{scenario_type}"):
        st.session_state["elderly_action"] = None
        st.rerun()


def _render_mood_interaction():
    selected = st.session_state.get("elder_mood_selected")
    _render_html(
        f"""
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128578;</span><div><h3>How are you feeling?</h3><p>Tap the closest option. This is only a simple wellbeing check-in.</p></div></div>
            {f'<div class="elder-success">Thanks for checking in. Your update was shared with your Guardian / Caregiver.</div>' if selected else ''}
        </div>
        """
    )
    moods = ["Happy", "Calm", "Sad", "Tired", "Worried", "Angry", "In pain", "I prefer not to say"]
    cols = st.columns(4)
    for index, mood in enumerate(moods):
        if cols[index % 4].button(mood, use_container_width=True, key=f"elder_mood_{index}"):
            st.session_state["elder_mood_selected"] = mood
            ok = _write_elderly_event(
                "mood_event",
                "mood_check",
                "recorded",
                f"{_care_name()} completed a wellbeing check-in.",
                payload={"mood": mood, "clinical": False},
            )
            if ok:
                st.success("Thank you. I'll share a simple wellbeing update with your Guardian / Caregiver.")
            else:
                st.info("Nesto saved this action locally and will try again.")
            st.rerun()


def _render_emergency_interaction():
    context = _active_elderly_context()
    sent = st.session_state.get("elder_emergency_alert_sent")
    _render_html(
        f"""
        <div class="elder-action-workspace emergency">
            <div class="elder-workspace-head"><span>&#9888;</span><div><h3>Do you need urgent help?</h3><p>Nesto can alert your Guardian / Caregiver. This does not replace emergency services.</p></div></div>
            <div class="elder-soft-callout">Primary contact: {escape(context['guardian_name'])}</div>
            {f'<div class="elder-success">Urgent alert sent to your Guardian / Caregiver.</div>' if sent else ''}
        </div>
        """
    )
    c1, c2 = st.columns(2)
    if c1.button("Alert Guardian / Caregiver", type="primary", use_container_width=True, key="elder_emergency_send"):
        st.session_state["elder_emergency_alert_sent"] = _friendly_now()
        ok = _write_elderly_event(
            "alert",
            "emergency_request",
            "active",
            "Urgent alert sent to Guardian / Caregiver.",
            payload={
                "alert_type": "emergency",
                "severity": "high",
                "status": "active",
            },
        )
        if ok:
            st.error("Urgent alert sent to your Guardian / Caregiver.")
        else:
            st.info("Nesto saved this action locally and will try again.")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="elder_emergency_cancel"):
        st.session_state["elderly_action"] = None
        st.rerun()


def _render_settings_interaction():
    _render_html(
        """
        <div class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#9881;</span><div><h3>Settings</h3><p>Your Guardian / Caregiver can update profile details, medicine reminders, and care preferences.</p></div></div>
        </div>
        """
    )
    if st.button("Open care profile", type="primary", use_container_width=True, key="elder_open_profile_settings"):
        _set_profile_mode("edit")
        _navigate_to("Caregiver", "User Creation + Preferences Page", "Care profile opened", "Review profile details and preferences.")
        st.rerun()


def _render_talk_to_nesto_interaction(robot_name, talk_response, talk_command, talk_button_label):
    st.markdown('<span id="elder-panel" class="talk-widget-anchor"></span>', unsafe_allow_html=True)
    _render_html(
        f"""
        <section class="elder-talk-panel">
            <div class="elder-talk-content">
                <span class="elder-panel-kicker">Talk to Nesto</span>
                <h2>Talk to {escape(robot_name)}</h2>
                <p>Press to talk, choose a quick request, or type what you need.</p>
                <div class="elder-listen-state">
                    <div class="elder-talk-avatar" aria-hidden="true"><span></span></div>
                    <div>
                        <b>{escape(talk_response)}</b>
                        <small>{escape(talk_command or "Waiting for your request")}</small>
                    </div>
                </div>
            </div>
        </section>
        """
    )
    if st.button(talk_button_label, type="primary", use_container_width=True, key="talk_press_to_talk"):
        st.session_state["talk_to_nesto_response"] = "Nesto is listening. You can also type your request below."
        st.session_state["talk_to_nesto_command"] = "Listening..."
        st.session_state["talk_to_nesto_listening"] = True
        st.session_state["talk_to_nesto_scenario"] = "talk_to_nesto"
        st.rerun()

    st.markdown('<p class="elder-talk-row-title">Quick requests</p>', unsafe_allow_html=True)
    sample_cols = st.columns(4)
    samples = [
        "Can you find my cane?",
        "Did I take my medicine today?",
        "Call my caregiver.",
        "I need help.",
    ]
    for column, sample in zip(sample_cols, samples):
        if column.button(sample, use_container_width=True, key=f"talk_sample_{sample}"):
            _handle_talk_to_nesto_command(sample)
            st.rerun()

    st.markdown('<p class="elder-talk-input-label">Type your request</p>', unsafe_allow_html=True)
    typed_command = st.text_input(
        "Type your request",
        value="",
        placeholder="Example: Can you find my medicine?",
        key="talk_to_nesto_input",
        label_visibility="collapsed",
    )
    if st.button("Send to Nesto", use_container_width=True, key="talk_send_to_nesto"):
        _handle_talk_to_nesto_command(typed_command or "Talk to Nesto", typed=True)
        st.rerun()


def _elder_action_href(route_base, action, command=None, extra=None):
    href = f"{route_base}&nesto_action={quote(str(action), safe='')}"
    if command:
        href += f"&elder_action_command={quote(str(command), safe='')}"
    for key, value in (extra or {}).items():
        href += f"&{quote(str(key), safe='')}={quote(str(value), safe='')}"
    return f"{href}#elder-panel"


def _elder_close_href(route_base):
    return f"{route_base}&elder_action_command=close#elder-panel"


def _handle_elderly_action_command(command, selected_action, medicine_time):
    if not command:
        return
    action_for_command = {
        "schedule_done": "schedule",
        "medication_taken": "medication",
        "call_send": "call",
        "call_cancel": "call",
        "find_cane_start": "find_cane",
        "find_medicine_start": "find_medicine",
        "mood_select": "mood",
        "emergency_send": "emergency",
        "emergency_cancel": "emergency",
        "talk_press": "chat",
        "talk_send": "chat",
    }
    if command == "close":
        st.session_state["elderly_action"] = None
        _clear_query_params("elder_action_command", "talk_text", "elder_mood", "nesto_action")
        st.rerun()

    selected_action = action_for_command.get(command, selected_action)
    if selected_action:
        st.session_state["elderly_action"] = selected_action

    if command == "schedule_done":
        done_time = _friendly_now()
        st.session_state["elder_schedule_task_done"] = done_time
        _write_elderly_event(
            "schedule_event",
            "schedule_task_done",
            "done",
            f"{_care_name()} completed a schedule task.",
            payload={"task": "lunch_check_in", "completed_at": done_time},
        )
    elif command == "medication_taken":
        profile = _care_profile()
        medicine_name = str(profile.get("medicine_name") or "Morning medicine")
        taken_time = _friendly_now()
        st.session_state["elder_medication_taken_at"] = taken_time
        _write_elderly_event(
            "medicine_event",
            "take_medicine",
            "taken",
            "Medication marked as taken.",
            payload={
                "medicine_status": "taken",
                "medicine_name": medicine_name,
                "taken_at": taken_time,
                "reminder_time": medicine_time,
            },
        )
    elif command == "call_send":
        context = _active_elderly_context()
        st.session_state["elder_call_request_status"] = "sent"
        _write_elderly_event(
            "scenario_event",
            "caregiver_call_requested",
            "requested",
            f"Call request sent to {context['guardian_name']}.",
            payload={"call_status": "requested"},
        )
    elif command == "call_cancel":
        st.session_state["elder_call_request_status"] = "cancelled"
        st.session_state["elderly_action"] = None
    elif command in {"find_cane_start", "find_medicine_start"}:
        scenario_type = "find_cane" if command == "find_cane_start" else "find_medicine"
        object_key = _important_object() if scenario_type == "find_cane" else "medicine_box"
        display_object = "medicine box" if object_key == "medicine_box" else _object_label(object_key).lower()
        st.session_state[f"elder_search_started_{scenario_type}"] = _friendly_now()
        _write_elderly_event(
            "scenario_event",
            scenario_type,
            "requested",
            f"Nesto started searching for the {display_object}.",
            payload={
                "object": object_key,
                "target_object": object_key,
                "last_known_location": _last_search_location(object_key),
                "search_status": "requested",
            },
        )
    elif command == "mood_select":
        mood = _query_param("elder_mood") or "I prefer not to say"
        st.session_state["elder_mood_selected"] = mood
        _write_elderly_event(
            "mood_event",
            "mood_check",
            "recorded",
            f"{_care_name()} completed a wellbeing check-in.",
            payload={"mood": mood, "clinical": False},
        )
    elif command == "emergency_send":
        st.session_state["elder_emergency_alert_sent"] = _friendly_now()
        _write_elderly_event(
            "alert",
            "emergency_request",
            "active",
            "Urgent alert sent to Guardian / Caregiver.",
            payload={
                "alert_type": "emergency",
                "severity": "high",
                "status": "active",
            },
        )
    elif command == "emergency_cancel":
        st.session_state["elderly_action"] = None
    elif command == "talk_press":
        st.session_state["talk_to_nesto_response"] = "Nesto is listening. You can also type your request below."
        st.session_state["talk_to_nesto_command"] = "Listening..."
        st.session_state["talk_to_nesto_listening"] = True
        st.session_state["talk_to_nesto_scenario"] = "talk_to_nesto"
    elif command == "talk_send":
        text = _query_param("talk_text") or "Talk to Nesto"
        _handle_talk_to_nesto_command(text, typed=True)

    _clear_query_params("elder_action_command", "talk_text", "elder_mood", "nesto_action")
    st.rerun()


def _elderly_selected_action_panel_html(action, route_base, robot_name, medicine_time, next_walk, talk_response, talk_command, talk_button_label):
    if not action:
        return ""
    close_link = _elder_close_href(route_base)
    if action == "schedule":
        rows = [
            ("08:00 AM", "Morning greeting / wellbeing check", "Ready"),
            ("08:30 AM", "Breakfast", "Ready"),
            (medicine_time, "Morning medicine", "Reminder"),
            (next_walk, "Walk reminder", "Next"),
            ("12:00 PM", "Lunch", "Later"),
            ("02:00 PM", "Rest / reading time", "Later"),
            ("06:00 PM", "Evening medicine", "Later"),
            ("08:30 PM", "Bedtime routine", "Later"),
        ]
        items = "".join(
            f'<div class="elder-timeline-row"><b>{escape(time)}</b><span>{escape(label)}</span><em>{escape(status)}</em></div>'
            for time, label, status in rows
        )
        done = st.session_state.get("elder_schedule_task_done")
        success = f'<div class="elder-success">Lunch check-in marked done at {escape(done)}.</div>' if done else ""
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128197;</span><div><h3>Today's Schedule</h3><p>Nesto will keep the day simple and gentle.</p></div></div>
            <div class="elder-timeline">{items}</div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary" href="{_elder_action_href(route_base, 'schedule', 'schedule_done')}">Mark task done</a>
                <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
            </div>
        </section>
        """
    if action == "medication":
        profile = _care_profile()
        medicine_name = str(profile.get("medicine_name") or "Morning medicine")
        taken_at = st.session_state.get("elder_medication_taken_at")
        status = f"{escape(medicine_name)} taken at {escape(taken_at)}." if taken_at else f"{escape(medicine_name)} is scheduled for {escape(medicine_time)}."
        success = '<div class="elder-success">Medication marked as taken. Your Guardian / Caregiver will be updated.</div>' if taken_at else ""
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128138;</span><div><h3>Take Medication</h3><p>{status}</p></div></div>
            <div class="elder-soft-callout">Nesto records preset reminder status only. It does not give dosage advice.</div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary" href="{_elder_action_href(route_base, 'medication', 'medication_taken')}">Mark as taken</a>
                <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
            </div>
        </section>
        """
    if action == "chat":
        samples = [
            "Can you find my cane?",
            "Did I take my medicine today?",
            "Call my caregiver.",
            "I need help.",
        ]
        chips = "".join(
            f'<a class="elder-workspace-button secondary" href="{_elder_action_href(route_base, "chat", "talk_send", {"talk_text": sample})}">{escape(sample)}</a>'
            for sample in samples
        )
        return f"""
        <section id="elder-panel" class="elder-talk-panel">
            <div class="elder-talk-content">
                <span class="elder-panel-kicker">Talk to Nesto</span>
                <h2>Talk to {escape(robot_name)}</h2>
                <p>Press to talk, choose a quick request, or type what you need.</p>
                <div class="elder-listen-state">
                    <div class="elder-talk-avatar" aria-hidden="true"><span></span></div>
                    <div>
                        <b>{escape(talk_response)}</b>
                        <small>{escape(talk_command or "Waiting for your request")}</small>
                    </div>
                </div>
                <div class="elder-workspace-actions">
                    <a class="elder-workspace-button primary" href="{_elder_action_href(route_base, 'chat', 'talk_press')}">{escape(talk_button_label)}</a>
                    <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
                </div>
                <p class="elder-talk-row-title">Quick requests</p>
                <div class="elder-workspace-actions chips">{chips}</div>
                <form class="elder-talk-form" method="get">
                    <input type="hidden" name="nav_role" value="Elderly user">
                    <input type="hidden" name="nav_page" value="Elderly User Interface">
                    <input type="hidden" name="nesto_action" value="chat">
                    <input type="hidden" name="elder_action_command" value="talk_send">
                    <input class="elder-talk-input" name="talk_text" placeholder="Example: Can you find my medicine?">
                    <button class="elder-workspace-button primary" type="submit">Send to Nesto</button>
                </form>
            </div>
        </section>
        """
    if action == "call":
        context = _active_elderly_context()
        status = st.session_state.get("elder_call_request_status", "ringing")
        title = "Call request sent." if status == "sent" else "Calling Guardian / Caregiver"
        body = "Your Guardian / Caregiver has been notified." if status == "sent" else "Calling your Guardian / Caregiver now..."
        success = '<div class="elder-success">Call request sent.</div>' if status == "sent" else ""
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128222;</span><div><h3>{escape(title)}</h3><p>{escape(body)}</p></div></div>
            <div class="elder-call-card">
                <span class="elder-ring-dot"></span>
                <div><b>{escape(context['guardian_name'])}</b><small>{escape(context['relationship'])}</small></div>
            </div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary" href="{_elder_action_href(route_base, 'call', 'call_send')}">Send call request</a>
                <a class="elder-workspace-button secondary" href="{_elder_action_href(route_base, 'call', 'call_cancel')}">Cancel</a>
            </div>
        </section>
        """
    if action in {"find_cane", "find_medicine"}:
        object_key = "medicine_box" if action == "find_medicine" else (_important_object() or "cane")
        display_object = "medicine box" if object_key == "medicine_box" else _object_label(object_key).lower()
        started_key = f"elder_search_started_{action}"
        location = _last_search_location(object_key)
        started = st.session_state.get(started_key)
        result = f"Your {display_object} may be in the {location}." if started else "Last known location unavailable; Nesto can start a room search."
        steps = "".join(
            f"<li>{escape(step)}</li>"
            for step in [
                "Checking last known location...",
                "Searching nearby rooms...",
                f"Looking for {display_object} using object memory...",
            ]
        )
        success = f'<div class="elder-success">Search started. Please wait nearby while Nesto checks the home.</div>' if started else ""
        command = "find_medicine_start" if action == "find_medicine" else "find_cane_start"
        title = "Finding your medicine" if action == "find_medicine" else f"Finding your {display_object}"
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128269;</span><div><h3>{escape(title)}</h3><p>{escape(result)}</p></div></div>
            <div class="elder-search-card">
                <div class="elder-scan-pulse"></div>
                <ol>{steps}</ol>
            </div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary" href="{_elder_action_href(route_base, action, command)}">Start search</a>
                <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
            </div>
        </section>
        """
    if action == "mood":
        selected = st.session_state.get("elder_mood_selected")
        moods = ["Happy", "Calm", "Sad", "Tired", "Worried", "Angry", "In pain", "I prefer not to say"]
        buttons = "".join(
            f'<a class="elder-mood-button{" active" if selected == mood else ""}" href="{_elder_action_href(route_base, "mood", "mood_select", {"elder_mood": mood})}">{escape(mood)}</a>'
            for mood in moods
        )
        success = '<div class="elder-success">Thanks for checking in. Your update was shared with your Guardian / Caregiver.</div>' if selected else ""
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#128578;</span><div><h3>How are you feeling?</h3><p>Tap the closest option. This is only a simple wellbeing check-in.</p></div></div>
            <div class="elder-mood-grid">{buttons}</div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
            </div>
        </section>
        """
    if action == "emergency":
        context = _active_elderly_context()
        sent = st.session_state.get("elder_emergency_alert_sent")
        success = '<div class="elder-success">Urgent alert sent to your Guardian / Caregiver.</div>' if sent else ""
        return f"""
        <section id="elder-panel" class="elder-action-workspace emergency">
            <div class="elder-workspace-head"><span>&#9888;</span><div><h3>Do you need urgent help?</h3><p>Nesto can alert your Guardian / Caregiver. This does not replace emergency services.</p></div></div>
            <div class="elder-soft-callout">Primary contact: {escape(context['guardian_name'])}</div>
            {success}
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary emergency" href="{_elder_action_href(route_base, 'emergency', 'emergency_send')}">Alert Guardian / Caregiver</a>
                <a class="elder-workspace-button secondary" href="{_elder_action_href(route_base, 'emergency', 'emergency_cancel')}">Cancel</a>
            </div>
        </section>
        """
    if action == "settings":
        return f"""
        <section id="elder-panel" class="elder-action-workspace">
            <div class="elder-workspace-head"><span>&#9881;</span><div><h3>Settings</h3><p>Your Guardian / Caregiver can update profile details, medicine reminders, and care preferences.</p></div></div>
            <div class="elder-workspace-actions">
                <a class="elder-workspace-button primary" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=edit">Open care profile</a>
                <a class="elder-workspace-button secondary" href="{close_link}">Close</a>
            </div>
        </section>
        """
    return ""


def family_landing():
    metrics = care_metrics()
    activity = recent_activity(limit=5)
    _render_html(_family_landing_html(metrics, activity))

    c1, c2, c3 = st.columns(3)
    if c1.button("Open family dashboard", use_container_width=True, type="primary"):
        _navigate_to("Caregiver", "Guardian / Caregiver Dashboard", "Family dashboard opened", f"{caregiver()} can review {patient()}'s care summary, messages, and alerts.")
        st.rerun()
    if c2.button("Review care profile", use_container_width=True):
        _set_profile_mode("edit")
        _navigate_to("Caregiver", "User Creation + Preferences Page", "Care profile opened", "Review the profile details Nesto can use for personalization.")
        st.rerun()
    if c3.button("Check consent setup", use_container_width=True):
        _set_profile_mode("edit")
        _navigate_to("Caregiver", "User Creation + Preferences Page", "Consent setup opened", "Review safety boundaries, consent, and profile setup.")
        st.rerun()



def elderly_home():
    action_from_url = _query_action()
    if action_from_url == "home":
        st.session_state["elderly_action"] = None
        _clear_query_params("nesto_action")
    elif action_from_url in ELDERLY_ACTIONS or action_from_url == "settings":
        st.session_state["elderly_action"] = action_from_url
        if action_from_url in ELDERLY_ACTIONS and st.session_state.get("last_url_action") != action_from_url:
            st.session_state["last_url_action"] = action_from_url
            _record_elderly_panel_opened(action_from_url)
        _clear_query_params("nesto_action")

    selected_action = st.session_state.get("elderly_action")
    profile = _care_profile()
    context = _active_elderly_context()
    status_info = robot_status(use_live=True)
    raw_name = str(profile.get("preferred_name") or profile.get("patient_name") or "Elderly User 01").strip()
    name = escape(raw_name or "Elderly User 01")
    robot_name_raw = str(profile.get("robot_name") or "Nesto").strip()
    robot_name = escape(robot_name_raw or "Nesto")
    important_object_raw = _important_object() or "cane"
    important_object_label = _object_label(important_object_raw)
    guardian_button_label = f"Call {context['guardian_name']}" if context.get("guardian_name") else "Call Guardian / Caregiver"
    robot_online = bool(status_info.get("online"))
    robot_status_text = escape(str(status_info.get("status") or ("Online" if robot_online else "Offline")))
    robot_battery = escape(str(status_info.get("battery") or "0"))
    robot_room = escape(str(status_info.get("room") or "Unknown"))
    raw_medicine_time = str(profile.get("medicine_time") or "09:00 AM").strip()
    medicine_time = escape(raw_medicine_time or "09:00 AM")
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", raw_medicine_time):
        parsed_time = _parse_time_value(raw_medicine_time)
        medicine_time = escape(parsed_time.strftime("%I:%M %p").lstrip("0") if parsed_time else raw_medicine_time)
    now = dt.datetime.now()
    current_time = escape(now.strftime("%I:%M %p").lstrip("0"))
    current_date = escape(now.strftime("%B %d, %Y").replace(" 0", " "))
    talk_response = st.session_state.get(
        "talk_to_nesto_response",
        "Nesto is ready to listen.",
    )
    talk_command = st.session_state.get("talk_to_nesto_command", "")
    talk_button_label = "Listening..." if st.session_state.get("talk_to_nesto_listening") else "Press to talk"
    next_walk = "10:00 AM"
    route_base = "?nav_role=Elderly%20user&nav_page=Elderly%20User%20Interface"
    _handle_elderly_action_command(_query_param("elder_action_command"), selected_action, medicine_time)
    selected_action = st.session_state.get("elderly_action")
    speech = escape(ELDERLY_ACTIONS[selected_action]["speech"] if selected_action in ELDERLY_ACTIONS else "How can I help you today?")
    selected_panel_html = _elderly_selected_action_panel_html(
        selected_action,
        route_base,
        robot_name_raw or "Nesto",
        medicine_time,
        next_walk,
        talk_response,
        talk_command,
        talk_button_label,
    )

    sidebar_items = [
        ("home", "&#8962;", "Home", ""),
        ("schedule", "&#128197;", "Today's Schedule", "schedule"),
        ("medication", "&#128138;", "Take Medication", "medication"),
        ("chat", "&#128172;", f"Talk to {robot_name}", "chat"),
        ("find_cane", "&#128269;", f"Find My {important_object_label}", "find_cane"),
        ("find_medicine", "&#128138;", "Find My Medicine", "find_medicine"),
        ("call", "&#128222;", guardian_button_label, "call"),
        ("mood", "&#128578;", "How are you feeling?", "mood"),
        ("emergency", "&#9888;", "Emergency", "emergency"),
        ("settings", "&#9881;", "Settings", "settings"),
    ]
    nav_html = []
    for key, icon, label, action in sidebar_items:
        active = " active" if (not action and not selected_action) or selected_action == action else ""
        href = f"{route_base}&nesto_action=home" if not action else f"{route_base}&nesto_action={action}#elder-panel"
        nav_html.append(f'<a class="elder-nav-item{active}" href="{href}"><span>{icon}</span>{label}</a>')

    cards = [
        ("schedule", "&#128197;", "Today's Schedule", "See your tasks", "#eee9ff"),
        ("medication", "&#128138;", "Take Medication", "Mark as taken", "#fff0ea"),
        ("chat", "&#128172;", f"Talk to {robot_name}", "Press to speak", "#e9f7ff"),
        ("call", "&#128222;", guardian_button_label, "Make a call", "#fff0f1"),
        ("find_cane", "&#128269;", f"Find My {important_object_label}", f"Locate your {important_object_label.lower()}", "#fff5e8"),
        ("find_medicine", "&#128138;", "Find My Medicine", "Locate medicine", "#ecf7ff"),
        ("mood", "&#128578;", "How are you feeling?", "Mood check-in", "#fff8dd"),
        ("emergency", "&#9888;", "Emergency", "Get help now", "#fff0f0"),
    ]
    card_html = []
    for action, icon, title, subtitle, color in cards:
        active = " active" if selected_action == action else ""
        danger = " danger" if action == "emergency" else ""
        card_html.append(
            f"""
            <a class="elder-action-card{active}{danger}" href="{route_base}&nesto_action={action}#elder-panel">
                <span class="elder-card-icon" style="background:{color};">{icon}</span>
                <strong>{title}</strong>
                <small>{subtitle}</small>
            </a>
            """
        )

    _render_html(
        f"""
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {{
                display: none !important;
            }}
            .block-container {{
                max-width: 1180px !important;
                padding: 10px !important;
            }}
            .stApp {{
                background: #f4efe5 !important;
            }}
            .stApp::before {{
                opacity: .045 !important;
            }}
            .elder-shell {{
                display: grid;
                grid-template-columns: 210px minmax(0, 1fr);
                gap: 18px;
                max-width: 1160px;
                margin: 0 auto;
                color: #102f32;
            }}
            .elder-sidebar {{
                min-height: 720px;
                border: 1px solid #e7ded0;
                border-radius: 18px;
                background: rgba(255,255,255,.92);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                padding: 18px 16px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}
            .elder-brand {{
                display: flex;
                align-items: center;
                gap: 10px;
                color: #123536;
                font-weight: 950;
                margin-bottom: 22px;
            }}
            .elder-brand span {{ font-size: 1.7rem; }}
            .elder-nav {{ display: grid; gap: 6px; }}
            .elder-nav-item {{
                min-height: 36px;
                border-radius: 9px;
                padding: 0 10px;
                display: flex;
                align-items: center;
                gap: 9px;
                color: #25413f !important;
                text-decoration: none !important;
                font-size: .78rem;
                font-weight: 800;
            }}
            .elder-nav-item.active,
            .elder-nav-item:hover {{ background: #e7f1eb; }}
            .elder-nav-item span {{ width: 17px; text-align: center; }}
            .elder-side-robot {{
                margin-top: auto;
                display: grid;
                place-items: center;
                text-align: center;
                gap: 4px;
                color: #123536;
                font-weight: 850;
            }}
            .elder-side-robot .nesto-bot {{ transform: scale(.62); margin: -16px auto -24px; }}
            .elder-side-robot span {{ color: #006b45; font-size: .76rem; font-weight: 950; }}
            .elder-logout {{
                margin-top: 10px;
                min-height: 38px;
                width: 100%;
                border: 1px solid #e3d8c7;
                border-radius: 999px;
                background: #fffdf8;
                color: #183f3a !important;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none !important;
                font-size: .78rem;
                font-weight: 950;
                box-shadow: 0 8px 18px rgba(37,65,63,.05);
            }}
            .elder-logout:hover {{
                border-color: #a8bfae;
                background: #edf4ee;
            }}
            .elder-main {{ min-width: 0; }}
            .elder-status {{
                display: grid;
                grid-template-columns: repeat(3, minmax(120px, 1fr)) auto;
                gap: 18px;
                align-items: start;
                margin: 4px 0 26px;
                font-weight: 750;
                color: #63716e;
            }}
            .elder-status b {{
                display: block;
                color: #102f32;
                margin-top: 4px;
                font-size: .95rem;
            }}
            .elder-clock {{ text-align: right; color: #102f32; min-width: 150px; }}
            .elder-clock strong {{ display: block; font-size: 1rem; }}
            .nesto-hero,
            .elder-hero {{
                display: grid;
                grid-template-columns: 1.4fr 0.9fr;
                gap: 32px;
                align-items: start;
                margin-bottom: 18px;
            }}
            .nesto-hero-left {{
                min-width: 0;
            }}
            .elder-title h1 {{
                font-size: clamp(2.15rem, 3.5vw, 3rem);
                line-height: 1.08;
                margin: 0 0 18px;
                letter-spacing: 0;
            }}
            .elder-title p {{
                max-width: 360px;
                color: #546763;
                font-size: .98rem;
                line-height: 1.65;
                margin: 0;
                font-weight: 650;
            }}
            .nesto-hero-right,
            .elder-robot-wrap {{
                position: relative;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 260px;
                width: 100%;
            }}
            .elder-robot-wrap .nesto-bot {{
                transform: scale(1.18);
                transform-origin: center;
                margin: 0 auto;
                animation: nesto-elder-float 4s ease-in-out infinite;
                z-index: 1;
            }}
            .nesto-speech-bubble,
            .elder-helper {{
                position: relative;
                align-self: flex-end;
                max-width: 220px;
                width: fit-content;
                margin: 0 0 16px;
                z-index: 2;
            }}
            .elder-helper summary {{
                list-style: none;
                cursor: pointer;
                padding: 18px 20px;
                border: 1px solid #e5ded2;
                border-radius: 20px;
                background: #ffffff;
                box-shadow: 0 10px 30px rgba(31,61,52,.08);
                color: #183f3a;
                font-weight: 850;
                line-height: 1.45;
            }}
            .elder-helper summary::-webkit-details-marker {{ display:none; }}
            .elder-helper div {{
                margin-top: 8px;
                padding: 12px;
                border-radius: 14px;
                background: #f8fff9;
                border: 1px solid #d8eadf;
                box-shadow: 0 12px 26px rgba(33,45,38,.1);
                font-size: .82rem;
                font-weight: 750;
                color: #31584d;
            }}
            .elder-actions {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 14px;
                margin-top: 8px;
            }}
            .elder-action-card {{
                min-height: 154px;
                border: 1px solid #e5ded2;
                border-radius: 14px;
                background: rgba(255,255,255,.88);
                box-shadow: 0 12px 28px rgba(40,55,44,.07);
                color: #102f32 !important;
                text-decoration: none !important;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 16px 12px;
                gap: 8px;
                transition: transform .12s ease, border-color .12s ease, box-shadow .12s ease;
            }}
            .elder-action-card:hover {{
                transform: translateY(-2px);
                border-color: #b9d1c4;
                box-shadow: 0 16px 34px rgba(40,55,44,.12);
            }}
            .elder-action-card.active {{
                border-color: #176b4d;
                box-shadow: 0 0 0 2px rgba(23,107,77,.12), 0 16px 34px rgba(40,55,44,.12);
            }}
            .elder-action-card.danger {{
                color: #c7363c !important;
                background: #fff7f7;
                border-color: #f4caca;
            }}
            .elder-card-icon {{
                width: 58px;
                height: 58px;
                border-radius: 999px;
                display: grid;
                place-items: center;
                font-size: 1.8rem;
            }}
            .elder-action-card strong {{ display:block; max-width:120px; font-size:1.02rem; line-height:1.12; }}
            .elder-action-card small {{ color:#667773; font-weight:650; }}
            .elder-reminder {{
                display: flex;
                justify-content: space-between;
                gap: 16px;
                margin-top: 18px;
                padding: 14px 18px;
                border: 1px solid #e5ded2;
                border-radius: 14px;
                background: rgba(255,255,255,.88);
                color: #2c4847;
                font-weight: 750;
            }}
            .elder-reminder span:first-child::before {{ content: "\\1F514"; margin-right: 8px; }}
            .elder-panel {{
                margin-top: 16px;
                border: 1px solid #dce8df;
                border-radius: 18px;
                background: linear-gradient(135deg, rgba(255,252,246,.94), rgba(244,239,229,.76));
                box-shadow: 0 18px 42px rgba(32,63,58,.08);
                padding: 18px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 18px;
            }}
            .elder-panel.emergency {{ border-color:#f2caca; background: linear-gradient(135deg,#fff8f8,#fff1f1); }}
            .elder-talk-panel {{
                margin-top: 16px;
                border: 1px solid #dce8df;
                border-radius: 20px;
                background: linear-gradient(135deg, rgba(255,252,246,.97), rgba(245,250,246,.88));
                box-shadow: 0 18px 42px rgba(32,63,58,.08);
                padding: 22px;
                display: block;
            }}
            .elder-talk-content h2 {{ margin: 4px 0 8px; font-size: 1.35rem; letter-spacing: 0; }}
            .elder-talk-content p {{ margin: 0 0 14px; color: #5e716c; font-weight: 650; line-height: 1.55; }}
            .elder-listen-state {{
                border: 1px solid #d8eadf;
                border-radius: 16px;
                background: rgba(248,255,249,.95);
                padding: 14px;
                color: #163d38;
                display: grid;
                grid-template-columns: 46px minmax(0, 1fr);
                gap: 12px;
                align-items: center;
            }}
            .elder-talk-avatar {{
                width: 46px;
                height: 46px;
                border-radius: 16px;
                background: #173f3a;
                border: 4px solid #e6dccb;
                display: grid;
                place-items: center;
                box-shadow: 0 10px 22px rgba(32,63,58,.13);
            }}
            .elder-talk-avatar span {{
                width: 25px;
                height: 17px;
                border-radius: 0 0 14px 14px;
                border-bottom: 3px solid #8ff1ce;
                position: relative;
                display: block;
            }}
            .elder-talk-avatar span::before,
            .elder-talk-avatar span::after {{
                content: "";
                position: absolute;
                top: 0;
                width: 6px;
                height: 12px;
                border-radius: 999px;
                background: #8ff1ce;
            }}
            .elder-talk-avatar span::before {{ left: 2px; }}
            .elder-talk-avatar span::after {{ right: 2px; }}
            .elder-talk-row-title,
            .elder-talk-input-label {{
                color: #244540;
                font-weight: 950;
                margin: 12px 0 8px;
                font-size: .98rem;
            }}
            .elder-listen-state b {{ display:block; font-size: 1rem; line-height: 1.45; }}
            .elder-listen-state small {{ display:block; margin-top: 6px; color:#6a7c77; font-weight:800; }}
            .elder-panel-kicker {{ color:#176b4d; font-weight:900; font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; }}
            .elder-panel h2 {{ margin: 4px 0 8px; font-size: 1.25rem; letter-spacing: 0; }}
            .elder-panel p {{ margin:0; color:#5e716c; font-weight:650; line-height:1.55; }}
            .elder-panel-status {{
                flex: 0 0 auto;
                border-radius: 999px;
                background: #176b4d;
                color: #fff !important;
                padding: 12px 18px;
                text-decoration: none !important;
                font-weight: 900;
                box-shadow: 0 12px 28px rgba(23,107,77,.16);
            }}
            .elder-action-workspace {{
                border: 1px solid #dce8df;
                border-radius: 20px;
                background: linear-gradient(135deg, rgba(255,252,246,.98), rgba(245,250,246,.9));
                box-shadow: 0 18px 42px rgba(32,63,58,.08);
                padding: 20px;
                color: #153d39;
                margin: 0 0 18px;
            }}
            .elder-action-workspace.emergency {{
                border-color: #f0c7c7;
                background: linear-gradient(135deg, #fff8f8, #fff1f1);
            }}
            .elder-workspace-head {{
                display: grid;
                grid-template-columns: 58px minmax(0, 1fr);
                gap: 14px;
                align-items: center;
                margin-bottom: 14px;
            }}
            .elder-workspace-head > span {{
                width: 58px;
                height: 58px;
                border-radius: 18px;
                display: grid;
                place-items: center;
                background: #e8f2ec;
                font-size: 1.7rem;
            }}
            .elder-workspace-head h3 {{
                margin: 0 0 4px;
                font-size: 1.35rem;
                letter-spacing: 0;
            }}
            .elder-workspace-head p {{
                margin: 0;
                color: #60746f;
                font-weight: 700;
                line-height: 1.45;
            }}
            .elder-timeline {{
                display: grid;
                gap: 9px;
            }}
            .elder-timeline-row {{
                display: grid;
                grid-template-columns: 94px minmax(0, 1fr) auto;
                gap: 12px;
                align-items: center;
                border: 1px solid #e4ded2;
                background: rgba(255,255,255,.72);
                border-radius: 14px;
                padding: 11px 13px;
                font-weight: 800;
            }}
            .elder-timeline-row span {{ color: #263f3c; }}
            .elder-timeline-row em {{
                font-style: normal;
                color: #176b4d;
                background: #e7f2eb;
                border-radius: 999px;
                padding: 5px 9px;
                font-size: .76rem;
            }}
            .elder-soft-callout,
            .elder-success {{
                margin-top: 12px;
                border-radius: 15px;
                padding: 13px 15px;
                font-weight: 800;
                line-height: 1.45;
            }}
            .elder-soft-callout {{
                border: 1px solid #e5ded2;
                background: rgba(255,255,255,.74);
                color: #526660;
            }}
            .elder-success {{
                border: 1px solid #b9ddc7;
                background: #e9f7ee;
                color: #176b4d;
            }}
            .elder-call-card {{
                display: flex;
                gap: 13px;
                align-items: center;
                border: 1px solid #e5ded2;
                border-radius: 16px;
                background: rgba(255,255,255,.78);
                padding: 16px;
            }}
            .elder-call-card small {{ display:block; color:#687872; font-weight:800; margin-top:3px; }}
            .elder-ring-dot {{
                width: 44px;
                height: 44px;
                border-radius: 999px;
                background: #176b4d;
                box-shadow: 0 0 0 8px rgba(23,107,77,.1);
                animation: elder-ring 1.4s ease-out infinite;
            }}
            .elder-search-card {{
                display: grid;
                grid-template-columns: 88px minmax(0, 1fr);
                gap: 16px;
                align-items: center;
                border: 1px solid #e5ded2;
                border-radius: 16px;
                background: rgba(255,255,255,.74);
                padding: 16px;
            }}
            .elder-search-card ol {{ margin:0; padding-left:20px; color:#314b46; font-weight:800; line-height:1.8; }}
            .elder-workspace-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 14px;
                align-items: center;
            }}
            .elder-workspace-actions.chips {{
                margin-top: 8px;
            }}
            .elder-workspace-button,
            .elder-talk-form button,
            .elder-mood-button {{
                min-height: 44px;
                border-radius: 999px;
                border: 1px solid #cbdccb;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 10px 16px;
                color: #183f3a !important;
                background: rgba(255,255,255,.86);
                text-decoration: none !important;
                font-weight: 900;
                box-sizing: border-box;
                cursor: pointer;
            }}
            .elder-workspace-button.primary,
            .elder-talk-form button {{
                background: #176b4d;
                border-color: #176b4d;
                color: #fffdf8 !important;
                box-shadow: 0 12px 28px rgba(23,107,77,.16);
            }}
            .elder-workspace-button.primary.emergency {{
                background: #d7373f;
                border-color: #d7373f;
            }}
            .elder-workspace-button.secondary,
            .elder-mood-button {{
                background: rgba(255,255,255,.88);
                border-color: #e3d8c7;
            }}
            .elder-mood-grid {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 10px;
                margin-top: 12px;
            }}
            .elder-mood-button.active {{
                border-color: #176b4d;
                background: #e7f2eb;
                color: #176b4d !important;
            }}
            .elder-talk-form {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 10px;
                margin-top: 14px;
            }}
            .elder-talk-input {{
                min-height: 44px;
                border-radius: 14px;
                border: 1px solid #d8e4dc;
                background: rgba(255,255,255,.9);
                color: #183d39;
                padding: 0 14px;
                font: inherit;
                font-weight: 750;
                box-sizing: border-box;
                width: 100%;
            }}
            .elder-scan-pulse {{
                width: 74px;
                height: 74px;
                border-radius: 999px;
                background: radial-gradient(circle, #176b4d 0 16%, rgba(23,107,77,.16) 17% 50%, transparent 51%);
                box-shadow: 0 0 0 0 rgba(23,107,77,.22);
                animation: elder-scan 1.7s ease-out infinite;
            }}
            @keyframes elder-ring {{
                0% {{ box-shadow: 0 0 0 0 rgba(23,107,77,.22); }}
                100% {{ box-shadow: 0 0 0 18px rgba(23,107,77,0); }}
            }}
            @keyframes elder-scan {{
                0% {{ transform: scale(.92); opacity:.9; }}
                50% {{ transform: scale(1.04); opacity:1; }}
                100% {{ transform: scale(.92); opacity:.9; }}
            }}
            @keyframes nesto-elder-float {{
                0%, 100% {{ transform: translateY(0) scale(1.18); }}
                50% {{ transform: translateY(-6px) scale(1.18); }}
            }}
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor),
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) {{
                margin: 16px 0 18px;
                max-width: none;
                border: 0;
                border-radius: 0;
                background: transparent;
                box-shadow: none;
                padding: 0;
            }}
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) button,
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) button {{
                min-height: 48px;
                border-radius: 999px !important;
                font-weight: 900 !important;
                border-color: #cbdccb !important;
            }}
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) button[kind="primary"],
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) button[data-testid="stBaseButton-primary"],
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) button[kind="primary"],
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) button[data-testid="stBaseButton-primary"] {{
                background: #176b4d !important;
                border-color: #176b4d !important;
                color: #fff !important;
                box-shadow: 0 14px 30px rgba(23,107,77,.18) !important;
            }}
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) input,
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) textarea,
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) input,
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) textarea {{
                border-radius: 14px !important;
                border-color: #d8e4dc !important;
                min-height: 48px;
                color: #183d39 !important;
                font-weight: 750;
            }}
            div[data-testid="stVerticalBlock"]:has(.talk-widget-anchor) label p,
            div[data-testid="stVerticalBlock"]:has(.elder-action-widget-anchor) label p {{
                color: #244540 !important;
                font-weight: 900 !important;
            }}
            @media (max-width: 1000px) {{
                .elder-shell {{ grid-template-columns: 1fr; }}
                .elder-sidebar {{ min-height: auto; }}
                .elder-side-robot {{ display:none; }}
                .elder-status {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
                .elder-clock {{ text-align:left; }}
                .elder-hero {{ grid-template-columns: 1fr; }}
                .elder-actions {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
                .elder-helper {{ align-self: center; }}
            }}
            @media (max-width: 560px) {{
                .elder-actions {{ grid-template-columns: 1fr; }}
                .elder-reminder, .elder-panel {{ flex-direction: column; align-items: stretch; }}
                .elder-mood-grid, .elder-talk-form {{ grid-template-columns: 1fr; }}
            }}
        </style>
        <div class="elder-layout-css-anchor"></div>
        """
    )
    sidebar_col, main_col = st.columns([210, 950], gap="medium")
    with sidebar_col:
        _render_html(
            f"""
            <aside class="elder-sidebar">
                <div class="elder-brand"><span>&#127968;</span><b>Nesto Care</b></div>
                <nav class="elder-nav">{''.join(nav_html)}</nav>
                <div class="elder-side-robot">
                    {_nesto_robot()}
                    <b>{robot_name} is ready</b>
                    <span>&#9679; Online</span>
                    <a target="_self" class="elder-logout" href="?logout=1">Log out</a>
                </div>
            </aside>
            """
        )
    with main_col:
        _render_html(
            f"""
            <main class="elder-main">
                <div class="elder-status">
                    <div>Nesto Status <b><span style="color:{'#176b4d' if robot_online else '#d7373f'};">&#9679;</span> {robot_status_text}</b></div>
                    <div>Battery <b>&#128267; {robot_battery}%</b></div>
                    <div>Location <b>&#8962; {robot_room}</b></div>
                    <div class="elder-clock"><strong id="elder-live-time">{current_time}</strong><span><span id="elder-live-date">{current_date}</span> &nbsp; &#128276;</span></div>
                </div>
                <div class="elder-hero nesto-hero">
                    <div class="elder-title nesto-hero-left">
                        <h1>Good morning,<br>{name} <span style="color:#6aa783;">&#9829;</span></h1>
                        <p>I'm here to help you have a calm, safe, and connected day.</p>
                    </div>
                    <div class="elder-robot-wrap nesto-hero-right">
                        <details class="elder-helper nesto-speech-bubble">
                            <summary>{speech}</summary>
                            <div>I can help with reminders, medicine, finding items, family calls, and emergencies.</div>
                        </details>
                        {_nesto_robot()}
                    </div>
                </div>
                {selected_panel_html}
            </main>
            """
        )
        _render_html(
            f"""
            <div class="elder-actions">{''.join(card_html)}</div>
            <div class="elder-reminder">
                <span><b>Reminder:</b> Morning medicine at {medicine_time}</span>
                <span><b>Next:</b> Walk reminder at {next_walk}</span>
            </div>
            """
        )
    components.html(
        """
        <script>
        const keepElderLinksInCurrentTab = () => {
          const doc = window.parent.document;
          doc.querySelectorAll("a.elder-nav-item, a.elder-action-card, a.summary-ai-card, a.elder-panel a, a.elder-workspace-button, a.elder-mood-button").forEach((link) => {
            link.removeAttribute("target");
            link.removeAttribute("rel");
            link.setAttribute("onclick", "event.preventDefault(); window.location.href = this.href; return false;");
            if (link.dataset.nestoCurrentTabReady === "true") return;
            link.dataset.nestoCurrentTabReady = "true";
            link.addEventListener("click", (event) => {
              const href = link.getAttribute("href");
              if (!href) return;
              event.preventDefault();
              const current = new URL(window.parent.location.href);
              const next = new URL(href, window.parent.location.href);
              next.searchParams.forEach((value, key) => current.searchParams.set(key, value));
              current.hash = next.hash;
              window.parent.location.href = current.toString();
            });
          });
        };
        const updateNestoClock = () => {
          const doc = window.parent.document;
          const timeTarget = doc.getElementById("elder-live-time");
          const dateTarget = doc.getElementById("elder-live-date");
          if (!timeTarget || !dateTarget) return;
          const now = new Date();
          timeTarget.textContent = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
          dateTarget.textContent = now.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
        };
        keepElderLinksInCurrentTab();
        updateNestoClock();
        setTimeout(keepElderLinksInCurrentTab, 250);
        setInterval(updateNestoClock, 1000);
        </script>
        """,
        height=0,
    )


def care_setup():
    profile()
    return


def _profile_form():
    current = get_profile(st.session_state)
    with st.form("profile_preferences_form"):
        c1, c2 = st.columns(2)
        with c1:
            patient_name = st.text_input("Elderly user name", current["patient_name"])
            preferred_name = st.text_input("Preferred name", current["preferred_name"])
            age = st.text_input("Age", current["age"])
            robot_name = st.text_input("Robot name", current["robot_name"])
            next_of_kin_name = st.text_input("Guardian / Caregiver name", current["next_of_kin_name"])
            relationship = st.text_input("Relationship to elderly user", current["relationship"])
            next_of_kin_phone = st.text_input("Phone number", current["next_of_kin_phone"])
            caregiver_name = st.text_input("Caregiver name", current["caregiver_name"])
        with c2:
            medicine_name = st.text_input("Medicine name", current["medicine_name"])
            medicine_dose = st.text_input("Dose", current["medicine_dose"])
            medicine_frequency = st.selectbox(
                "Frequency",
                ["Once daily", "Twice daily", "Three times daily", "As needed"],
                index=["Once daily", "Twice daily", "Three times daily", "As needed"].index(current.get("medicine_frequency", "Twice daily")) if current.get("medicine_frequency") in ["Once daily", "Twice daily", "Three times daily", "As needed"] else 1,
            )
            medicine_time = st.text_input("Reminder time", current["medicine_time"])
            important_object = st.text_input("Important object to find", current["important_object"])
            preferred_language = st.text_input("Preferred language", current["preferred_language"])
            preferred_tone = st.selectbox(
                "Nesto tone",
                ["Calm and direct", "Very gentle", "Short instructions", "Family-style encouragement"],
                index=["Calm and direct", "Very gentle", "Short instructions", "Family-style encouragement"].index(current.get("preferred_tone", "Calm and direct")) if current.get("preferred_tone") in ["Calm and direct", "Very gentle", "Short instructions", "Family-style encouragement"] else 0,
            )
            user_preferences = st.text_area("User preferences", current["user_preferences"])
            care_notes = st.text_area("Care notes", current["care_notes"])
        submitted = st.form_submit_button("Save profile to ChromaDB memory", type="primary")
    if submitted:
        profile_data = {
            "patient_name": patient_name,
            "preferred_name": preferred_name,
            "age": age,
            "next_of_kin_name": next_of_kin_name,
            "relationship": relationship,
            "next_of_kin_phone": next_of_kin_phone,
            "caregiver_name": caregiver_name,
            "medicine_name": medicine_name,
            "medicine_dose": medicine_dose,
            "medicine_frequency": medicine_frequency,
            "medicine_time": medicine_time,
            "robot_name": robot_name,
            "important_object": important_object,
            "preferred_language": preferred_language,
            "preferred_tone": preferred_tone,
            "user_preferences": user_preferences,
            "care_notes": care_notes,
        }
        saved = save_profile(st.session_state, profile_data)
        if saved:
            st.success("Profile and preferences saved to ChromaDB memory.")
        else:
            st.warning("Profile saved in the app session, but ChromaDB did not confirm the write.")


def _profile_summary_cards():
    profile_data = get_profile(st.session_state)
    _render_html(
        f"""
        <div class="metric-grid">
            <div class="metric"><div class="metric-label">Elderly user</div><div class="metric-value">{escape(profile_data['preferred_name'] or profile_data['patient_name'])}</div><p class="muted">{escape(profile_data['patient_name'])}, age {escape(profile_data['age'])}</p></div>
            <div class="metric"><div class="metric-label">Guardian / Caregiver</div><div class="metric-value">{escape(profile_data['next_of_kin_name'])}</div><p class="muted">{escape(profile_data['relationship'])} / {escape(profile_data['next_of_kin_phone'] or 'phone pending')}</p></div>
            <div class="metric"><div class="metric-label">Robot name</div><div class="metric-value">{escape(profile_data['robot_name'])}</div><p class="muted">{escape(profile_data['preferred_tone'])}</p></div>
            <div class="metric"><div class="metric-label">Medicine</div><div class="metric-value">{escape(profile_data['medicine_time'])}</div><p class="muted">{escape(profile_data['medicine_name'])} / {escape(profile_data['medicine_frequency'])}</p></div>
        </div>
        """
    )


def care_setup_legacy():
    page_header("Customer / Family App", "Care Setup", "Profile, consent, safety boundaries, and robot personalization.", "Setup")
    cols = st.columns(2)
    with cols[0]:
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Profile setup</p>
                <div class="row"><span class="row-main">Elderly user</span>{badge(patient(),"purple")}</div>
                <div class="row"><span class="row-main">Family contact</span>{badge(caregiver(),"green")}</div>
                <div class="row"><span class="row-main">Robot name</span>{badge("Nesto","amber")}</div>
                <div class="row"><span class="row-main">Care plan</span>{badge("Standard","gray")}</div>
            </div>
            <div class="card">
                <p class="section-title">Robot customization</p>
                <div class="row"><span class="row-main">Preferred tone</span>{badge("Calm","green")}</div>
                <div class="row"><span class="row-main">Important object</span>{badge("Cane","purple")}</div>
                <div class="row"><span class="row-main">Routine anchor</span>{badge("After lunch","amber")}</div>
                <div class="row"><span class="row-main">Emergency contact</span>{badge("Family first","red")}</div>
            </div>
            """
        )
    with cols[1]:
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Consent and terms</p>
                <div class="row"><span class="dot" style="background:{GREEN};"></span><span class="row-main">Consent form included in onboarding</span></div>
                <div class="row"><span class="dot" style="background:{GREEN};"></span><span class="row-main">Terms and Conditions acknowledged</span></div>
                <div class="row"><span class="dot" style="background:{GREEN};"></span><span class="row-main">Simulated project data only</span></div>
                <div class="row"><span class="dot" style="background:{AMBER};"></span><span class="row-main">No diagnosis or dosage advice</span></div>
            </div>
            <div class="card">
                <p class="section-title">Personalization flow</p>
                <div class="row"><span class="row-main">App profile and routine</span>{badge("Input","purple")}</div>
                <div class="row"><span class="row-main">Saved preferences and notes</span>{badge("Memory","purple")}</div>
                <div class="row"><span class="row-main">Approved scenario route</span>{badge("Nesto","green")}</div>
                <div class="row"><span class="row-main">Care updates shown in dashboards</span>{badge("Live","green")}</div>
            </div>
            """
        )
    _render_html('<div class="card"><p class="section-title">Save a personalization note</p></div>')
    with st.form("personalization_note_form", clear_on_submit=True):
        note = st.text_area("Personalization note", f"{patient()} prefers calm reminders and needs help locating an important item in the living room.")
        submitted = st.form_submit_button("Save personalization note")
    if submitted:
        now = dt.datetime.now()
        metadata = {
            "type": "profile_customization",
            "patient": patient(),
            "robot": "Nesto",
            "created": now.isoformat(timespec="seconds"),
            "display_time": now.strftime("%H:%M"),
            "display_date": now.strftime("%d %b %Y"),
        }
        if save_memory(note.strip(), metadata):
            st.success(f"Personalization note saved at {now.strftime('%H:%M')}.")
        else:
            st.warning("The note was not saved. Please check the memory service.")




def _profile_setup_sidebar_html():
    items = [
        ("&#8962;", "Home"),
        ("&#9881;", "Features"),
        ("&#128279;", "How it works"),
        ("&#128172;", "About Nesto"),
        ("?", "FAQ"),
        ("&#128274;", "Privacy Policy"),
        ("&#9635;", "Terms of Service"),
        ("&#128222;", "Contact Us"),
    ]
    nav = "".join(
        f'<a class="profile-nav-item{ " active" if label == "Home" else ""}" href="?nav_role=Product&nav_page=Landing%20Page#{label.lower().replace(" ", "-")}"><span>{icon}</span>{label}</a>'
        for icon, label in items
    )
    return f"""
    <aside class="profile-sidebar-card">
        <div class="profile-brand"><span>&#127968;</span><b>Nesto Care</b></div>
        <nav class="profile-nav">{nav}</nav>
        <div class="profile-side-robot">
            {_nesto_robot()}
            <b>Nesto is ready</b>
            <span>&#9679; Online</span>
        </div>
    </aside>
    """


PROFILE_PLACEHOLDERS = {
    "patient_name": "Maria Johnson",
    "preferred_name": "Maria",
    "age": "78",
    "robot_name": "Nesto",
    "next_of_kin_name": "Anna Smith",
    "relationship": "Daughter",
    "next_of_kin_phone": "+44 7700 900123",
    "caregiver_name": "Anna Smith",
    "medicine_name": "Morning Medicine",
    "medicine_dose": "As prescribed",
    "medicine_time": "09:00 AM",
    "important_object": "Cane",
    "care_notes": "Calm in the morning",
    "user_preferences": "Example: prefers short reminders, likes family updates after medication.",
}


PROFILE_STEPS = ["profile", "medicine", "preferences", "review"]
PROFILE_FORM_STATE_KEYS = [
    "care_profile_form",
    "profile_setup_step",
    "profile_setup_saved",
    "profile_create_flow_active",
    "profile_setup_last_save",
    "profile_success_heading",
    "profile_account_status_label",
    "profile_auth_accounts_created",
    "profile_created_accounts",
    "profile_account_conflict",
    "profile_field_errors",
    "profile_medicine_rows",
    "profile_terms_accepted",
    "profile_privacy_accepted",
    "profile_consent_accepted",
    "profile_active_doc",
    "_profile_step_transition",
    "profile_account_identifier",
    "profile_account_password",
    "profile_account_confirm_password",
    "guardian_account_identifier",
    "guardian_account_password",
    "guardian_account_confirm_password",
    "profile_form",
    "profile_draft",
    "full_name",
    "preferred_name",
    "age",
    "robot_name",
    "guardian_name",
    "guardian_phone",
    "medicine_name",
    "dose",
    "care_notes",
    "extra_preferences",
    "account_email",
    "password",
    "confirm_password",
    "guardian_email",
    "guardian_password",
    "primary_medicine_time",
    "profile_language_other",
    "profile_relationship_other",
]
PROFILE_WIDGET_KEY_PREFIXES = (
    "profile_input_",
    "profile_select_",
    "medicine_name_",
    "medicine_dose_",
    "medicine_frequency_",
    "medicine_time_",
)
RELATIONSHIP_OPTIONS = [
    "Daughter",
    "Son",
    "Spouse",
    "Sibling",
    "Parent",
    "Relative",
    "Friend",
    "Professional caregiver",
    "Legal guardian",
    "Other",
]
FREQUENCY_OPTIONS = ["Once daily", "Twice daily", "Three times daily", "Weekly", "As needed", "As prescribed"]
TONE_OPTIONS = ["Calm and direct", "Warm and friendly", "Gentle reminders", "Very simple instructions", "Encouraging"]
LANGUAGE_OPTIONS = ["English", "Spanish", "Filipino / Tagalog", "Turkish", "French", "German", "Italian", "Portuguese", "Arabic", "Other"]

NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ\s'-]*$")
ROBOT_RE = re.compile(r"^[A-Za-z0-9À-ÖØ-öø-ÿ][A-Za-z0-9À-ÖØ-öø-ÿ\s-]*$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s-]{6,18}[0-9]$")
GENERAL_RE = re.compile(r"^[A-Za-z0-9À-ÖØ-öø-ÿ][A-Za-z0-9À-ÖØ-öø-ÿ\s\-./'(),]*$")

CONSENT_DOCUMENTS = {
    "terms": {
        "title": "Terms and Conditions",
        "button": "Read Terms and Conditions",
        "accepted": "Terms accepted",
        "checkbox": "I agree to the Terms and Conditions.",
        "body": [
            "Nesto Care is a university MVP/demo system.",
            "It is not a medical device, diagnostic system, emergency-response system, or replacement for professional care.",
            "Medication support is limited to reminders and taken/missed tracking.",
            "Mood and emotion outputs are non-clinical emotional indicators for demonstration only.",
            "Care decisions remain with the user, family, caregiver, and qualified professionals.",
        ],
    },
    "privacy": {
        "title": "Privacy Notice",
        "button": "Read Privacy Notice",
        "accepted": "Privacy accepted",
        "checkbox": "I agree to the Privacy Notice.",
        "body": [
            "This app uses simulated/demo data for the university project.",
            "It may use profile data, interaction data, mood indicators, medication reminder data, robot/environment data, alerts, and family dashboard summaries.",
            "MongoDB may store structured event data, and ChromaDB may store preferences and memory.",
            "Kafka may stream robot/scenario events in the architecture.",
            "A real EU deployment would require access rights, deletion rights, consent withdrawal, retention limits, secure storage, and stronger safeguards.",
        ],
    },
    "consent": {
        "title": "Consent Checklist",
        "button": "Review Consent Checklist",
        "accepted": "Consent accepted",
        "checkbox": "I agree to the Consent Checklist.",
        "body": [
            "I understand this is a university demo system using simulated/demo data.",
            "I understand this is not a medical device and does not provide diagnosis, treatment, medication dosage advice, or emergency response.",
            "I understand mood labels are only emotional indicators for demonstration purposes.",
            "I understand medication features are limited to preset reminders and taken/missed tracking.",
            "I understand profile preferences, interaction events, robot status events, mood indicators, medication reminder events, safety alerts, and dashboard summaries may be stored.",
            "I agree to continue with this demo experience.",
        ],
    },
}


def _profile_step_index(step):
    return PROFILE_STEPS.index(step) if step in PROFILE_STEPS else 0


def _profile_step_classes(active_step):
    active_index = _profile_step_index(active_step)
    return {
        step: "active" if index == active_index else ("done" if index < active_index else "")
        for index, step in enumerate(PROFILE_STEPS)
    }


def _profile_step_url(step):
    mode = str(st.session_state.get("profile_mode") or "create").strip().lower()
    if mode not in {"create", "edit"}:
        mode = "create"
    return f"?nav_role=guardian_caregiver&nav_page=profile_preferences&profile_mode={mode}&profile_step={step}"


def _set_profile_step(step, remember_transition=True):
    if step not in PROFILE_STEPS:
        step = "profile"
    st.session_state["profile_setup_step"] = step
    if remember_transition:
        st.session_state["_profile_step_transition"] = step
    mode = str(st.session_state.get("profile_mode") or "create").strip().lower()
    if mode not in {"create", "edit"}:
        mode = "create"
    try:
        st.query_params["nav_role"] = "guardian_caregiver"
        st.query_params["nav_page"] = "profile_preferences"
        st.query_params["profile_mode"] = mode
        st.query_params["profile_step"] = step
    except Exception:
        pass
    return step


def clear_profile_form_state():
    keys_to_clear = set(PROFILE_FORM_STATE_KEYS)
    for key in list(st.session_state.keys()):
        if key in keys_to_clear or any(str(key).startswith(prefix) for prefix in PROFILE_WIDGET_KEY_PREFIXES):
            st.session_state.pop(key, None)


def start_new_profile():
    clear_profile_form_state()
    st.session_state["profile_mode"] = "create"
    st.session_state["profile_create_flow_active"] = True
    st.session_state["profile_medicine_rows"] = 1
    _set_profile_step("profile", remember_transition=False)


def _profile_mode_from_query():
    try:
        mode = st.query_params.get("profile_mode", "")
    except Exception:
        mode = ""
    mode = str(mode or "").strip().lower()
    return mode if mode in {"create", "edit"} else ""


def _consume_profile_reset_query():
    try:
        reset = str(st.query_params.get("profile_reset", "") or "").strip()
    except Exception:
        return False
    if reset != "1":
        return False
    try:
        del st.query_params["profile_reset"]
    except Exception:
        try:
            st.query_params["profile_reset"] = "0"
        except Exception:
            pass
    return True


def _set_profile_mode(mode):
    mode = "edit" if mode == "edit" else "create"
    st.session_state["profile_mode"] = mode
    if mode == "edit":
        st.session_state.pop("profile_create_flow_active", None)
    try:
        st.query_params["profile_mode"] = mode
    except Exception:
        pass
    return mode


def _empty_profile_draft():
    return dict(DEFAULT_PROFILE)


def _current_profile_for_mode(session_state):
    mode = str(session_state.get("profile_mode") or "create").strip().lower()
    if mode == "edit":
        return get_profile(session_state)
    draft = _empty_profile_draft()
    form = session_state.get("care_profile_form", {})
    if isinstance(form, dict):
        draft.update(form)
    if not isinstance(draft.get("guardian_contact"), dict):
        draft["guardian_contact"] = {}
    return draft


def _profile_text_input(column, label, key, current, **kwargs):
    widget_key = kwargs.pop("key", f"profile_input_{key}")
    return column.text_input(
        label,
        value=str(current.get(key, "") or ""),
        placeholder=PROFILE_PLACEHOLDERS.get(key, ""),
        key=widget_key,
        **kwargs,
    )


def _profile_selectbox(column, label, key, current, options):
    value = current.get(key, "")
    select_options = ["Select"] + options
    index = select_options.index(value) if value in select_options else 0
    selected = column.selectbox(label, select_options, index=index, key=f"profile_select_{key}")
    return "" if selected == "Select" else selected


def _profile_data_from_values(current, **updates):
    data = dict(current)
    data.update(updates)
    return data


def _profile_required_missing(data, keys):
    labels = {
        "patient_name": "full name",
        "preferred_name": "preferred name",
        "next_of_kin_name": "Guardian / Caregiver name",
        "relationship": "relationship",
        "next_of_kin_phone": "phone number",
        "medicine_name": "medicine name",
        "medicine_dose": "dose",
        "medicine_frequency": "frequency",
        "medicine_time": "reminder time",
    }
    return [labels.get(key, key) for key in keys if not str(data.get(key, "") or "").strip()]


def _valid_name(value):
    return bool(NAME_RE.fullmatch(str(value or "").strip()))


def _valid_optional_name(value):
    text = str(value or "").strip()
    return not text or _valid_name(text)


def _valid_age(value):
    try:
        number = int(str(value or "").strip())
    except ValueError:
        return False
    return 1 <= number <= 120


def _valid_robot_name(value):
    return bool(ROBOT_RE.fullmatch(str(value or "").strip()))


def _valid_phone(value):
    text = str(value or "").strip()
    return bool(PHONE_RE.fullmatch(text)) and text.count("+") <= 1 and ("+" not in text or text.startswith("+"))


def _valid_general_text(value, required=True):
    text = str(value or "").strip()
    if not text:
        return not required
    return bool(GENERAL_RE.fullmatch(text)) and any(ch.isalnum() for ch in text)


def _valid_time(value):
    text = str(value or "").strip()
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        return True
    return bool(re.fullmatch(r"(0?[1-9]|1[0-2]):[0-5]\d\s?(AM|PM|am|pm)", text))


def _parse_time_value(value):
    text = str(value or "").strip()
    for pattern in ("%H:%M", "%I:%M %p"):
        try:
            return dt.datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return None


def _format_time_value(value):
    if isinstance(value, dt.time):
        return value.strftime("%H:%M")
    return str(value or "").strip()


def _flatten_field_errors(field_errors):
    return [message for messages in field_errors.values() for message in messages]


def _profile_field_errors(data):
    errors = {}
    required = {
        "patient_name": "patient_name",
        "preferred_name": "preferred_name",
        "age": "age",
        "robot_name": "robot_name",
        "next_of_kin_name": "next_of_kin_name",
        "relationship": "relationship",
        "next_of_kin_phone": "next_of_kin_phone",
    }
    for field in required:
        if not str(data.get(field, "") or "").strip():
            errors.setdefault(required[field], []).append("This field is required.")
    if not _valid_name(data.get("patient_name")):
        errors.setdefault("patient_name", []).append("Use letters only.")
    if not _valid_name(data.get("preferred_name")):
        errors.setdefault("preferred_name", []).append("Use letters only.")
    if not _valid_age(data.get("age")):
        errors.setdefault("age", []).append("Enter an age from 1 to 120.")
    if not _valid_robot_name(data.get("robot_name")):
        errors.setdefault("robot_name", []).append("Use letters and numbers only.")
    if not _valid_name(data.get("next_of_kin_name")):
        errors.setdefault("next_of_kin_name", []).append("Use letters only.")
    if not str(data.get("relationship", "") or "").strip():
        errors.setdefault("relationship", []).append("Select a relationship.")
    if not _valid_phone(data.get("next_of_kin_phone")):
        errors.setdefault("next_of_kin_phone", []).append("Enter a valid phone number.")
    if not _valid_optional_name(data.get("caregiver_name")):
        errors.setdefault("caregiver_name", []).append("Use letters only.")
    return errors


def _validate_profile_step(data):
    return _flatten_field_errors(_profile_field_errors(data))


def _medicine_field_errors(data):
    errors = {}
    for field in ("medicine_name", "medicine_dose", "medicine_frequency", "medicine_time"):
        if not str(data.get(field, "") or "").strip():
            errors.setdefault(field, []).append("This field is required.")
    if not _valid_general_text(data.get("medicine_name")):
        errors.setdefault("medicine_name", []).append("Enter a valid medicine name.")
    if not _valid_general_text(data.get("medicine_dose")):
        errors.setdefault("medicine_dose", []).append("Enter a valid dose.")
    if data.get("medicine_frequency") not in FREQUENCY_OPTIONS:
        errors.setdefault("medicine_frequency", []).append("Select a valid frequency.")
    if not _valid_time(data.get("medicine_time")):
        errors.setdefault("medicine_time", []).append("Use HH:MM or 09:00 AM.")
    for index, item in enumerate(data.get("additional_medicines", []) or [], start=2):
        if not any(str(value or "").strip() for value in item.values()):
            continue
        if not _valid_general_text(item.get("medicine_name")):
            errors.setdefault(f"additional_{index}_medicine_name", []).append("Enter a valid medicine name.")
        if not _valid_general_text(item.get("dose")):
            errors.setdefault(f"additional_{index}_dose", []).append("Enter a valid dose.")
        if item.get("frequency") not in FREQUENCY_OPTIONS:
            errors.setdefault(f"additional_{index}_frequency", []).append("Select a valid frequency.")
        if not _valid_time(item.get("reminder_time")):
            errors.setdefault(f"additional_{index}_reminder_time", []).append("Use HH:MM or 09:00 AM.")
    return errors


def _validate_medicine_step(data):
    return _flatten_field_errors(_medicine_field_errors(data))


def _preferences_field_errors(data):
    errors = {}
    for field in ("important_object", "preferred_tone", "preferred_language"):
        if not str(data.get(field, "") or "").strip():
            errors.setdefault(field, []).append("This field is required.")
    if not _valid_general_text(data.get("important_object")):
        errors.setdefault("important_object", []).append("Enter a valid object.")
    if data.get("preferred_tone") not in TONE_OPTIONS:
        errors.setdefault("preferred_tone", []).append("Select a Nesto tone.")
    language = data.get("preferred_language")
    if language not in LANGUAGE_OPTIONS and not _valid_general_text(language):
        errors.setdefault("preferred_language", []).append("Select a preferred language.")
    return errors


def _validate_preferences_step(data):
    return _flatten_field_errors(_preferences_field_errors(data))


def _set_field_errors(step, field_errors):
    st.session_state["profile_field_errors"] = {
        "step": step,
        "fields": field_errors,
    }


def _clear_field_errors():
    st.session_state.pop("profile_field_errors", None)


def _current_field_errors(step):
    state = st.session_state.get("profile_field_errors", {})
    if state.get("step") != step:
        return {}
    return state.get("fields", {}) or {}


def _render_field_error(container, field_errors, key):
    messages = field_errors.get(key, [])
    message = escape(messages[0]) if messages else "&nbsp;"
    visible = " visible" if messages else ""
    container.markdown(f'<div class="field-error{visible}">{message}</div>', unsafe_allow_html=True)


def _show_validation_errors(errors):
    if errors:
        error_items = "".join(f"<li>{escape(error)}</li>" for error in errors)
        _render_html(
            f"""
            <div class="field-error-list" role="alert">
                <b>Please check these fields:</b>
                <ul>{error_items}</ul>
            </div>
            """
        )
        return True
    return False


def _consent_state():
    return {
        "terms_accepted": bool(st.session_state.get("profile_terms_accepted")),
        "privacy_accepted": bool(st.session_state.get("profile_privacy_accepted")),
        "consent_checklist_accepted": bool(st.session_state.get("profile_consent_accepted")),
    }


def _all_consent_accepted():
    state = _consent_state()
    return all(state.values())


def _save_profile_and_log(session_state, profile_data):
    saved = save_profile(session_state, profile_data)
    payload = build_profile_memory_payload(profile_data)
    session_state["profile_setup_last_save"] = {
        "saved_to_memory": bool(saved),
        "profile_status": "saved",
        "memory_status": "connected" if saved else "sync pending",
    }
    return saved


def _profile_summary_html(profile_data):
    guardian = escape(profile_data.get("next_of_kin_name") or "Not provided")
    relationship = escape(profile_data.get("relationship") or "Relationship pending")
    phone = escape(profile_data.get("next_of_kin_phone") or "Phone pending")
    patient_name = escape(profile_data.get("patient_name") or "Not provided")
    preferred_name = escape(profile_data.get("preferred_name") or "Not provided")
    medicine_name = escape(profile_data.get("medicine_name") or "Not provided")
    medicine_time = escape(profile_data.get("medicine_time") or "Time pending")
    tone = escape(profile_data.get("preferred_tone") or "Not selected")
    language = escape(profile_data.get("preferred_language") or "Not selected")
    important_object = escape(profile_data.get("important_object") or "Not provided")
    return f"""
    <div class="setup-review-grid">
        <div><b>Elderly user</b><span>{patient_name}</span><small>Preferred name: {preferred_name}</small></div>
        <div><b>Guardian / Caregiver</b><span>{guardian}</span><small>{relationship} / {phone}</small></div>
        <div><b>Medicine routine</b><span>{medicine_name}</span><small>Reminder: {medicine_time}</small></div>
        <div><b>Preferences</b><span>{important_object}</span><small>{tone} / {language}</small></div>
    </div>
    """


def _saved_profile_html(profile_data):
    preferred = escape(profile_data.get("preferred_name") or profile_data.get("patient_name") or "the user")
    account_status = st.session_state.get("profile_account_status_label") or "Account ready"
    heading = st.session_state.get("profile_success_heading") or (
        "Profile and account created successfully." if st.session_state.get("profile_auth_accounts_created") else "Profile saved successfully"
    )
    return f"""
    <div class="success-banner">
        <div class="success-mark">&#10003;</div>
        <div>
            <h1>{heading}</h1>
            <p>Nesto is ready to personalize care for {preferred}.</p>
        </div>
    </div>
    {_profile_summary_html(profile_data)}
    <div class="setup-review-grid">
        <div><b>Consent status</b><span>Terms accepted</span><small>Terms and Conditions confirmed</small></div>
        <div><b>Privacy status</b><span>Privacy accepted</span><small>Privacy Notice confirmed</small></div>
        <div><b>Care consent</b><span>Consent accepted</span><small>Consent Checklist confirmed</small></div>
        <div><b>Account status</b><span>{escape(str(account_status))}</span><small>Profile setup is complete</small></div>
    </div>
    """


def _render_consent_dialog():
    active_key = st.session_state.get("profile_active_doc")
    if active_key not in CONSENT_DOCUMENTS:
        return
    doc = CONSENT_DOCUMENTS[active_key]

    def body():
        _render_html(
            f"""
            <div class="setup-side-card" style="max-height:360px;overflow:auto;margin-bottom:12px;">
                <h3>{escape(doc["title"])}</h3>
                <ul>
                    {''.join(f'<li>{escape(item)}</li>' for item in doc["body"])}
                </ul>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        if c1.button("I agree", type="primary", use_container_width=True, key=f"agree_{active_key}"):
            if active_key == "terms":
                st.session_state["profile_terms_accepted"] = True
            elif active_key == "privacy":
                st.session_state["profile_privacy_accepted"] = True
            else:
                st.session_state["profile_consent_accepted"] = True
            st.session_state.pop("profile_active_doc", None)
            st.rerun()
        if c2.button("Close", use_container_width=True, key=f"close_{active_key}"):
            st.session_state.pop("profile_active_doc", None)
            st.rerun()

    if hasattr(st, "dialog"):
        try:
            dialog = st.dialog(doc["title"], width="large")
        except TypeError:
            dialog = st.dialog(doc["title"])

        @dialog
        def _dialog_body():
            body()

        _dialog_body()
    else:
        with st.expander(doc["title"], expanded=True):
            body()


def _render_account_setup_fields():
    _render_html(
        """
        <div class="profile-shell">
            <div class="setup-section-title">Account setup</div>
            <p class="setup-muted">Create sign-in credentials so Nesto can route each person to the correct care dashboard.</p>
        </div>
        """
    )
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.text_input("Username or email", key="profile_account_identifier", placeholder="maria@example.com")
    c2.text_input("Password", key="profile_account_password", type="password")
    c3.text_input("Confirm password", key="profile_account_confirm_password", type="password")
    _render_html('<div class="setup-rule"></div><div class="setup-section-title">Guardian / Caregiver login access</div>')
    g1, g2, g3 = st.columns(3, gap="medium")
    g1.text_input("Guardian / Caregiver email or username", key="guardian_account_identifier", placeholder="anna@example.com")
    g2.text_input("Guardian / Caregiver password", key="guardian_account_password", type="password")
    g3.text_input("Confirm Guardian / Caregiver password", key="guardian_account_confirm_password", type="password")


def _account_setup_values():
    return {
        "patient_identifier": st.session_state.get("profile_account_identifier", ""),
        "patient_password": st.session_state.get("profile_account_password", ""),
        "patient_confirm_password": st.session_state.get("profile_account_confirm_password", ""),
        "guardian_identifier": st.session_state.get("guardian_account_identifier", ""),
        "guardian_password": st.session_state.get("guardian_account_password", ""),
        "guardian_confirm_password": st.session_state.get("guardian_account_confirm_password", ""),
    }


def _clear_account_password_fields():
    for key in [
        "profile_account_password",
        "profile_account_confirm_password",
        "guardian_account_password",
        "guardian_account_confirm_password",
    ]:
        st.session_state.pop(key, None)


def _render_consent_cards():
    cols = st.columns(3)
    states = {
        "terms": bool(st.session_state.get("profile_terms_accepted")),
        "privacy": bool(st.session_state.get("profile_privacy_accepted")),
        "consent": bool(st.session_state.get("profile_consent_accepted")),
    }
    for col, key in zip(cols, ["terms", "privacy", "consent"]):
        doc = CONSENT_DOCUMENTS[key]
        with col:
            status = doc["accepted"] if states[key] else "Required"
            checked = "checked" if states[key] else ""
            _render_html(
                f"""
                <div class="setup-side-card consent-card" style="margin-bottom:8px;">
                    <div>
                        <h3>{escape(doc["title"])}</h3>
                        <p>{escape(status)}</p>
                    </div>
                    <label class="consent-check"><input type="checkbox" disabled {checked}> <span>{escape(doc["checkbox"])}</span></label>
                </div>
                """
            )
            if st.button(doc["button"], key=f"open_{key}", use_container_width=True):
                st.session_state["profile_active_doc"] = key
                st.rerun()


def profile():
    _render_consent_dialog()
    query_mode = _profile_mode_from_query()
    existing_mode = str(st.session_state.get("profile_mode") or "").strip().lower()
    reset_requested = _consume_profile_reset_query()
    query_step = ""
    try:
        query_step = st.query_params.get("profile_step", "")
    except Exception:
        query_step = ""
    if reset_requested:
        start_new_profile()
    elif query_mode == "create" and (
        existing_mode != "create"
        or not st.session_state.get("profile_create_flow_active")
        or (
            query_step == "profile"
            and st.session_state.get("profile_setup_saved")
        )
    ):
        start_new_profile()
    elif query_mode == "edit":
        _set_profile_mode("edit")
    elif existing_mode not in {"create", "edit"}:
        start_new_profile()

    pending_step = str(st.session_state.pop("_profile_step_transition", "") or "")
    if pending_step in PROFILE_STEPS:
        _set_profile_step(pending_step, remember_transition=False)
    elif query_step in PROFILE_STEPS:
        _set_profile_step(query_step, remember_transition=False)
    active_step = st.session_state.get("profile_setup_step", "profile")
    if active_step not in PROFILE_STEPS:
        active_step = _set_profile_step("profile", remember_transition=False)
    current = _current_profile_for_mode(st.session_state)
    medicine_rows = int(st.session_state.get("profile_medicine_rows", 1) or 1)
    medicine_rows = max(1, min(medicine_rows, 4))
    step_classes = _profile_step_classes(active_step)
    profile_done = _profile_step_index(active_step) > 0
    medicine_done = _profile_step_index(active_step) > 1
    preferences_done = _profile_step_index(active_step) > 2
    active_field_errors = _current_field_errors(active_step)

    _render_html(
        f"""
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {{
                display: none !important;
            }}
            .block-container {{
                max-width: 1120px !important;
                padding: 10px 10px 12px !important;
            }}
            .stApp {{
                background: #f4efe5 !important;
            }}
            .stApp::before {{
                opacity: .055 !important;
            }}
            div[data-testid="InputInstructions"],
            div[data-testid="stTextInput"] div[data-testid="InputInstructions"],
            div[data-testid="stTextArea"] div[data-testid="InputInstructions"],
            div[data-testid="stNumberInput"] div[data-testid="InputInstructions"],
            div[data-testid="stTimeInput"] div[data-testid="InputInstructions"],
            div[data-baseweb="input"] + div,
            div[data-baseweb="textarea"] + div {{
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            .profile-sidebar-card {{
                min-height: 686px;
                border: 1px solid #e7ded0;
                border-radius: 18px;
                background: rgba(255,255,255,.92);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                padding: 18px 16px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}
            .profile-brand {{
                display: flex;
                align-items: center;
                gap: 9px;
                color: #123536;
                font-weight: 950;
                margin-bottom: 22px;
            }}
            .profile-brand span {{
                font-size: 1.65rem;
            }}
            .profile-nav {{
                display: grid;
                gap: 6px;
            }}
            .profile-nav-item {{
                min-height: 34px;
                border-radius: 8px;
                padding: 0 9px;
                display: flex;
                align-items: center;
                gap: 9px;
                color: #25413f !important;
                text-decoration: none !important;
                font-size: .78rem;
                font-weight: 750;
            }}
            .profile-nav-item.active,
            .profile-nav-item:hover {{
                background: #e7f1eb;
            }}
            .profile-nav-item span {{
                width: 16px;
                text-align: center;
            }}
            .profile-side-robot {{
                margin-top: auto;
                border: 0;
                border-radius: 0;
                background: transparent;
                min-height: 198px;
                display: grid;
                place-items: center;
                text-align: center;
                padding: 8px 0 0;
                overflow: visible;
                color: #123536;
                font-weight: 850;
            }}
            .profile-side-robot .nesto-bot {{
                transform: scale(.78);
                transform-origin: center;
                margin: -16px 0 -22px;
                animation: nesto-sidebar-float 4s ease-in-out infinite;
            }}
            .profile-side-robot span {{
                color: #006b45;
                font-size: .8rem;
                font-weight: 950;
            }}
              .profile-shell {{
                  border: 1px solid #e7ded0;
                  border-radius: 24px;
                  background:
                      linear-gradient(135deg, rgba(255,252,246,.94), rgba(244,239,229,.76)),
                      rgba(255,255,255,.58);
                  box-shadow:
                      0 24px 60px rgba(32,63,58,.08),
                      inset 0 1px 0 rgba(255,255,255,.78);
                  backdrop-filter: blur(18px);
                  -webkit-backdrop-filter: blur(18px);
                  margin-bottom: 10px;
                  padding: 18px 18px 14px;
                  color: #102f32;
              }}
            .setup-steps {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0;
                margin: 0 0 14px;
                color: #697a77;
                font-size: .86rem;
                font-weight: 750;
            }}
            .setup-step {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                white-space: nowrap;
                position: relative;
                padding: 0 13px;
                color: #60706d !important;
                text-decoration: none !important;
                font-weight: 850;
            }}
            .setup-step.active,
            .setup-step.done {{
                color: #176b4d !important;
            }}
            .setup-step:not(:last-child)::after {{
                content: "";
                position: absolute;
                left: calc(100% - 7px);
                width: 14px;
                height: 1px;
                background: #d9ded8;
            }}
            .setup-step-number {{
                width: 22px;
                height: 22px;
                border-radius: 999px;
                display: inline-grid;
                place-items: center;
                border: 1px solid #d9ded8;
                background: #fff;
                color: #6f7d7b;
                font-size: .72rem;
                font-weight: 950;
            }}
            .setup-step.active .setup-step-number,
            .setup-step.done .setup-step-number {{
                background: #176b4d;
                border-color: #176b4d;
                color: #fff;
            }}
            .setup-title h1 {{
                font-size: 1.5rem;
                line-height: 1.08;
                margin: 0 0 8px;
                letter-spacing: 0;
            }}
            .setup-title p {{
                margin: 0;
                color: #60706d;
                font-weight: 650;
            }}
              div[data-testid="stForm"] {{
                  border: 1px solid rgba(230,215,191,.75) !important;
                  background:
                      linear-gradient(135deg, rgba(255,252,246,.92), rgba(244,239,229,.72)),
                      rgba(255,255,255,.55) !important;
                  border-radius: 24px !important;
                  box-shadow:
                      0 24px 60px rgba(32,63,58,.08),
                      inset 0 1px 0 rgba(255,255,255,.75) !important;
                  backdrop-filter: blur(18px);
                  -webkit-backdrop-filter: blur(18px);
                  padding: 16px 16px 10px !important;
              }}
              div[class*="st-key-profile-step-card"] {{
                  border: 1px solid rgba(230,215,191,.75) !important;
                  background:
                      linear-gradient(135deg, rgba(255,252,246,.92), rgba(244,239,229,.72)),
                      rgba(255,255,255,.55) !important;
                  border-radius: 24px !important;
                  box-shadow:
                      0 24px 60px rgba(32,63,58,.08),
                      inset 0 1px 0 rgba(255,255,255,.75) !important;
                  backdrop-filter: blur(18px);
                  -webkit-backdrop-filter: blur(18px);
                  padding: 16px 16px 10px !important;
                  margin-bottom: 10px !important;
              }}
            .setup-section-title {{
                margin: 4px 0 6px;
                color: #123536;
                font-size: .94rem;
                font-weight: 950;
            }}
            .setup-rule {{
                height: 1px;
                background: #ece4d7;
                margin: 14px 0 10px;
            }}
              .nesto-form-field,
              div[data-testid="stTextInput"],
              div[data-testid="stNumberInput"],
              div[data-testid="stTimeInput"],
              div[data-testid="stSelectbox"],
              div[data-testid="stTextArea"] {{
                  margin-bottom: 0 !important;
                  min-width: 0 !important;
              }}
              .nesto-field-label,
              div[data-testid="stTextInput"] label,
              div[data-testid="stNumberInput"] label,
              div[data-testid="stTimeInput"] label,
              div[data-testid="stSelectbox"] label,
              div[data-testid="stTextArea"] label {{
                  display: flex !important;
                  align-items: flex-end !important;
                  min-height: 38px !important;
                  margin: 0 0 8px !important;
                  padding: 0 !important;
                  color: #24423c !important;
                  font-size: 14px !important;
                  font-weight: 600 !important;
                  line-height: 1.35 !important;
                  white-space: normal !important;
                  overflow: visible !important;
              }}
              div[data-testid="stTextInput"] label p,
              div[data-testid="stNumberInput"] label p,
              div[data-testid="stTimeInput"] label p,
              div[data-testid="stSelectbox"] label p,
              div[data-testid="stTextArea"] label p {{
                  font-size: 14px !important;
                  line-height: 1.35 !important;
                  font-weight: 600 !important;
                  margin: 0 !important;
                  color: #24423c !important;
              }}
              div[data-testid="stTextInput"] > div,
              div[data-testid="stNumberInput"] > div,
              div[data-testid="stTimeInput"] > div,
              div[data-testid="stSelectbox"] > div,
              div[data-testid="stTextArea"] > div,
              div[data-baseweb="input"],
              div[data-baseweb="select"],
              div[data-baseweb="textarea"] {{
                  width: 100% !important;
                  max-width: 100% !important;
                  box-sizing: border-box !important;
              }}
              .nesto-field-control,
              .stTextInput input,
              .stNumberInput input,
              .stTimeInput input,
              .stSelectbox div[data-baseweb="select"],
              .stSelectbox div[data-baseweb="select"] > div,
              div[data-testid="stTextInput"] input,
              div[data-testid="stNumberInput"] input,
              div[data-testid="stTimeInput"] input,
              div[data-testid="stSelectbox"] div[data-baseweb="select"],
              div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
              div[data-testid="stTextInput"] div[data-baseweb="input"],
              div[data-testid="stNumberInput"] div[data-baseweb="input"],
              div[data-testid="stTimeInput"] div[data-baseweb="input"] {{
                  width: 100% !important;
                  max-width: 100% !important;
                  height: 46px !important;
                  min-height: 46px !important;
                  max-height: 46px !important;
                  border-radius: 14px !important;
                  border: 1px solid rgba(168, 191, 174, 0.45) !important;
                  background: rgba(255, 252, 246, 0.9) !important;
                  color: #183f3a !important;
                  box-shadow: none !important;
                  font-size: 14px !important;
                  line-height: 46px !important;
                  box-sizing: border-box !important;
                  font-family: inherit !important;
              }}
              .stTextInput input,
              .stNumberInput input,
              .stTimeInput input,
              div[data-testid="stTextInput"] input,
              div[data-testid="stNumberInput"] input,
              div[data-testid="stTimeInput"] input {{
                  padding: 0 14px !important;
              }}
              .nesto-select-control,
              div[data-testid="stSelectbox"] div[data-baseweb="select"],
              .stSelectbox div[data-baseweb="select"] > div,
              div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
                  display: flex !important;
                  align-items: center !important;
                  width: 100% !important;
                  min-width: 100% !important;
                  max-width: 100% !important;
                  height: 46px !important;
                  min-height: 46px !important;
                  max-height: 46px !important;
                  color: #183f3a !important;
                  font-size: 13px !important;
                  line-height: normal !important;
                  background-color: rgba(255, 252, 246, 0.9) !important;
                  box-sizing: border-box !important;
                  cursor: pointer !important;
              }}
              div[data-testid="stSelectbox"] div[data-baseweb="select"] * {{
                  color: #183f3a !important;
                  font-size: 13px !important;
                  line-height: normal !important;
              }}
              div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
                  padding: 0 7px 0 12px !important;
                  border: 0 !important;
                  background: transparent !important;
                  box-shadow: none !important;
              }}
              div[data-testid="stSelectbox"] div[data-baseweb="select"] {{
                  padding: 0 !important;
                  overflow: visible !important;
              }}
              div[data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"] {{
                  border: 0 !important;
                  box-shadow: none !important;
                  background: transparent !important;
                  color: #183f3a !important;
                  caret-color: #183f3a !important;
                  min-width: 1px !important;
              }}
              div[data-testid="stSelectbox"] svg {{
                  color: #31584d !important;
                  flex: 0 0 auto !important;
                  width: 16px !important;
                  height: 16px !important;
                  pointer-events: none !important;
              }}
              .stTextInput input:focus,
              .stNumberInput input:focus,
              .stTimeInput input:focus,
              .stTextArea textarea:focus,
              .stSelectbox div[data-baseweb="select"]:focus-within > div,
              div[data-testid="stTextInput"] input:focus,
              div[data-testid="stNumberInput"] input:focus,
              div[data-testid="stTimeInput"] input:focus,
              div[data-testid="stTextArea"] textarea:focus,
              div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within > div,
              div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
              div[data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within,
              div[data-testid="stTimeInput"] div[data-baseweb="input"]:focus-within {{
                  outline: none !important;
                  border-color: #a8bfae !important;
                  box-shadow: 0 0 0 4px rgba(168,191,174,.18) !important;
              }}
              .nesto-textarea,
              .stTextArea textarea,
              div[data-testid="stTextArea"] textarea {{
                  width: 100% !important;
                  min-height: 120px !important;
                  resize: vertical !important;
                  border-radius: 16px !important;
                  border: 1px solid rgba(168, 191, 174, 0.45) !important;
                  background: rgba(255, 252, 246, 0.9) !important;
                  color: #183f3a !important;
                  padding: 14px !important;
                  font-size: 14px !important;
                  line-height: 1.45 !important;
                  font-family: inherit !important;
                  box-sizing: border-box !important;
                  box-shadow: none !important;
                  outline: none !important;
              }}
              div[data-testid="stTextArea"] div[data-baseweb="textarea"] {{
                  border-radius: 16px !important;
                  border: 1px solid rgba(168,191,174,.42) !important;
                  background: rgba(255,252,246,.82) !important;
                  box-shadow: none !important;
                  outline: none !important;
              }}
              div[data-testid="stTextArea"] div[data-baseweb="textarea"]:focus-within {{
                  border-color: #a8bfae !important;
                  box-shadow: 0 0 0 4px rgba(168,191,174,.18) !important;
                  outline: none !important;
              }}
              input:focus,
              textarea:focus,
              input:focus-visible,
              textarea:focus-visible {{
                  outline: none !important;
                  border-color: #a8bfae !important;
                  box-shadow: 0 0 0 4px rgba(168,191,174,.18) !important;
              }}
              .stTextInput input::placeholder,
              .stNumberInput input::placeholder,
              .stTimeInput input::placeholder,
              .stTextArea textarea::placeholder,
              div[data-testid="stTextInput"] input::placeholder,
              div[data-testid="stNumberInput"] input::placeholder,
              div[data-testid="stTimeInput"] input::placeholder,
              div[data-testid="stTextArea"] textarea::placeholder {{
                  color: rgba(32,63,58,.42) !important;
              }}
              div[data-testid="stHorizontalBlock"] {{
                  gap: 16px !important;
              }}
              div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
                  min-width: 0 !important;
              }}
            .stButton button,
            .stFormSubmitButton button {{
                border-radius: 999px !important;
                min-height: 46px;
                font-weight: 900 !important;
                border: 1px solid #176b4d !important;
                box-shadow: 0 12px 24px rgba(23,107,77,.13) !important;
                font-size: .86rem !important;
            }}
            .stFormSubmitButton button {{
                background: #176b4d !important;
                color: #fff !important;
            }}
            .stButton button[kind="primary"],
            .stButton button[data-testid="stBaseButton-primary"],
            .stButton button[data-testid="baseButton-primary"],
            button[kind="primary"],
            button[data-testid="stBaseButton-primary"],
            button[data-testid="baseButton-primary"] {{
                background: #176b4d !important;
                color: #fff !important;
                border-color: #176b4d !important;
            }}
            .stFormSubmitButton button:hover,
            .stButton button[kind="primary"]:hover,
            .stButton button[data-testid="stBaseButton-primary"]:hover,
            .stButton button[data-testid="baseButton-primary"]:hover,
            button[kind="primary"]:hover,
            button[data-testid="stBaseButton-primary"]:hover,
            button[data-testid="baseButton-primary"]:hover {{
                background: #0f5139 !important;
                color: #fff !important;
                border-color: #0f5139 !important;
            }}
            .setup-robot-card {{
                position: relative;
                min-height: 184px;
                display: grid;
                place-items: center;
                margin-bottom: 14px;
                border: 0;
                border-radius: 0;
                background: transparent;
                overflow: visible;
            }}
            .setup-robot-card .nesto-bot {{
                transform: scale(.82);
                animation: nesto-float 3.8s ease-in-out infinite;
            }}
            .setup-speech {{
                position: absolute;
                right: 10px;
                top: 8px;
                max-width: 150px;
                border: 1px solid #e2d7c8;
                border-radius: 14px;
                background: #fff;
                color: #123536;
                padding: 8px 10px;
                font-size: .74rem;
                line-height: 1.35;
                font-weight: 900;
                box-shadow: 0 10px 22px rgba(37,65,63,.08);
            }}
              .setup-side-card,
              .setup-privacy {{
                  border: 1px solid rgba(230,215,191,.75);
                  border-radius: 22px;
                  background:
                      linear-gradient(135deg, rgba(255,252,246,.92), rgba(244,239,229,.72)),
                      rgba(255,255,255,.55);
                  box-shadow:
                      0 18px 42px rgba(32,63,58,.07),
                      inset 0 1px 0 rgba(255,255,255,.72);
                  backdrop-filter: blur(18px);
                  -webkit-backdrop-filter: blur(18px);
                  color: #60706d;
                  font-weight: 650;
                  line-height: 1.55;
                  padding: 18px;
                  margin-bottom: 14px;
              }}
            .setup-side-card h3 {{
                color: #123536;
                margin: 0 0 8px;
                font-size: 1rem;
            }}
            .consent-card {{
                min-height: 174px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                gap: 12px;
                padding: 16px;
            }}
            .consent-card h3 {{
                margin: 0;
            }}
            .consent-card p {{
                margin: 0;
                color: #60706d;
            }}
            .consent-check {{
                display: flex;
                align-items: flex-start;
                gap: 8px;
                margin-top: auto;
                color: #25413f;
                font-size: .82rem;
                font-weight: 800;
                line-height: 1.35;
            }}
            .consent-check input {{
                accent-color: #176b4d;
                margin-top: 2px;
            }}
            .setup-review-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
                margin: 6px 0 14px;
            }}
              .setup-review-grid div {{
                  border: 1px solid rgba(230,215,191,.75);
                  border-radius: 18px;
                  background:
                      linear-gradient(135deg, rgba(255,252,246,.92), rgba(244,239,229,.72)),
                      rgba(255,255,255,.55);
                  box-shadow:
                      0 14px 34px rgba(32,63,58,.06),
                      inset 0 1px 0 rgba(255,255,255,.7);
                  backdrop-filter: blur(18px);
                  -webkit-backdrop-filter: blur(18px);
                  padding: 14px;
                  display: grid;
                  gap: 5px;
              }}
              .field-error-list {{
                  border: 1px solid rgba(185,74,72,.2);
                  border-radius: 16px;
                  background: rgba(255,245,244,.9);
                  color: #8f3432;
                  padding: 10px 12px;
                  margin: 12px 0 2px;
                  font-size: .78rem;
                  line-height: 1.35;
                  box-shadow: 0 10px 24px rgba(185,74,72,.08);
              }}
              .field-error-list b {{
                  display: block;
                  margin-bottom: 4px;
                  color: #8f3432;
                  font-size: .78rem;
              }}
              .field-error-list ul {{
                  margin: 0;
                  padding-left: 18px;
              }}
              .field-error-list li {{
                  margin: 2px 0;
              }}
              .nesto-field-error,
              .field-error {{
                  min-height: 16px;
                  margin: 6px 0 0;
                  color: transparent;
                  font-size: 12px;
                  line-height: 1.3;
                  font-weight: 800;
              }}
              .field-error.visible {{
                  color: #a8443f;
              }}
              .nesto-warning-banner {{
                  background: rgba(230, 215, 191, 0.55);
                  border: 1px solid rgba(166, 95, 63, 0.22);
                  color: #7a5638;
                  border-radius: 18px;
                  padding: 16px 18px;
                  font-size: 15px;
                  font-weight: 600;
                  line-height: 1.45;
                  margin: 12px 0 4px;
                  box-shadow: 0 14px 30px rgba(122,86,56,.08);
              }}
            .setup-review-grid b {{
                color: #123536;
                font-size: .82rem;
            }}
            .setup-review-grid span {{
                color: #173b3c;
                font-weight: 900;
            }}
            .setup-review-grid small {{
                color: #657673;
                font-weight: 650;
            }}
            .success-banner {{
                border: 1px solid #b9d9c8;
                border-left: 6px solid #176b4d;
                border-radius: 18px;
                background: linear-gradient(135deg, #effaf3, #f8fff9);
                box-shadow: 0 18px 42px rgba(23,107,77,.12);
                margin-bottom: 12px;
                padding: 18px 20px;
                display: flex;
                align-items: center;
                gap: 14px;
                color: #123536;
            }}
            .success-banner h1 {{
                margin: 0 0 6px;
                font-size: 1.45rem;
                letter-spacing: 0;
            }}
            .success-banner p {{
                margin: 0;
                color: #31584d;
                font-weight: 750;
            }}
            .success-mark {{
                width: 40px;
                height: 40px;
                border-radius: 999px;
                display: grid;
                place-items: center;
                background: #176b4d;
                color: #fff;
                font-weight: 950;
                flex: 0 0 auto;
                box-shadow: 0 10px 22px rgba(23,107,77,.18);
            }}
            @keyframes nesto-float {{
                0%, 100% {{ transform: translateY(0) scale(.82); }}
                50% {{ transform: translateY(-5px) scale(.82); }}
            }}
            @keyframes nesto-sidebar-float {{
                0%, 100% {{ transform: translateY(0) scale(.78); }}
                50% {{ transform: translateY(-5px) scale(.78); }}
            }}
            @media (max-width: 720px) {{
                .setup-steps {{
                    justify-content: flex-start;
                    gap: 10px;
                    overflow-x: auto;
                    padding-bottom: 8px;
                }}
                .setup-review-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
        """
    )

    sidebar_col, main_col, helper_col = st.columns([0.42, 1.22, 0.46], gap="small")
    with sidebar_col:
        _render_html(_profile_setup_sidebar_html())

    with main_col:
        _render_html(
            f"""
            <div class="profile-shell">
                <div class="setup-steps">
                    <a class="setup-step {step_classes['profile']}" href="{_profile_step_url('profile')}"><span class="setup-step-number">1</span>Profile</a>
                    <a class="setup-step {step_classes['medicine']}" href="{_profile_step_url('medicine')}"><span class="setup-step-number">2</span>Medicine</a>
                    <a class="setup-step {step_classes['preferences']}" href="{_profile_step_url('preferences')}"><span class="setup-step-number">3</span>Preferences</a>
                    <a class="setup-step {step_classes['review']}" href="{_profile_step_url('review')}"><span class="setup-step-number">4</span>Consent & Review</a>
                </div>
                <div class="setup-title">
                    <h1>Let's create a care profile</h1>
                    <p>This helps Nesto personalize care and remember what matters.</p>
                </div>
            </div>
            """
        )

        if st.session_state.get("profile_setup_saved"):
            saved_profile = _current_profile_for_mode(st.session_state)
            _render_html(_saved_profile_html(saved_profile))
            c1, c2 = st.columns([1, 1.3])
            if c1.button("Edit profile", use_container_width=True):
                _set_profile_mode("edit")
                st.session_state["profile_setup_saved"] = False
                _set_profile_step("profile")
                st.rerun()
            if c2.button("Continue to Nesto", type="primary", use_container_width=True):
                _navigate_to("Elderly user", "Elderly User Interface", "Profile setup completed", "Opening the elderly user interface after onboarding.")
                st.rerun()

        if st.session_state.get("profile_setup_saved"):
            pass
        elif active_step == "profile":
            with st.container(key="profile-step-card-profile"):
                _render_html('<div class="setup-section-title">Elderly User Information</div>')
                c1, c2, c3, c4 = st.columns(4, gap="medium")
                patient_name = _profile_text_input(c1, "Full name", "patient_name", current)
                preferred_name = _profile_text_input(c2, "Preferred name", "preferred_name", current)
                age = _profile_text_input(c3, "Age", "age", current)
                robot_name = _profile_text_input(c4, "Robot name", "robot_name", current)
                _render_field_error(c1, active_field_errors, "patient_name")
                _render_field_error(c2, active_field_errors, "preferred_name")
                _render_field_error(c3, active_field_errors, "age")
                _render_field_error(c4, active_field_errors, "robot_name")

                _render_html('<div class="setup-rule"></div><div class="setup-section-title">Guardian / Caregiver details</div>')
                c1, c2, c3, c4 = st.columns(4, gap="medium")
                guardian_name = _profile_text_input(c1, "Guardian / Caregiver name", "next_of_kin_name", current)
                relationship = _profile_selectbox(c2, "Relationship to elderly user", "relationship", current, RELATIONSHIP_OPTIONS)
                guardian_phone = _profile_text_input(c3, "Phone number", "next_of_kin_phone", current)
                caregiver_name = _profile_text_input(c4, "Caregiver name, if different", "caregiver_name", current)
                _render_field_error(c1, active_field_errors, "next_of_kin_name")
                _render_field_error(c2, active_field_errors, "relationship")
                _render_field_error(c3, active_field_errors, "next_of_kin_phone")
                _render_field_error(c4, active_field_errors, "caregiver_name")
                relationship_other = ""
                if relationship == "Other":
                    relationship_other = st.text_input(
                        "Relationship details",
                        value=str(current.get("relationship_other", "") or ""),
                        placeholder="Example: neighbour",
                        key="profile_input_relationship_other",
                    )

                _show_validation_errors(_flatten_field_errors(active_field_errors))
                next_clicked = st.button("Next: Medicine Routine", type="primary", use_container_width=True, key="profile_next_medicine")
                if next_clicked:
                    profile_data = _profile_data_from_values(
                        current,
                        patient_name=patient_name,
                        preferred_name=preferred_name,
                        age=age,
                        robot_name=robot_name,
                        next_of_kin_name=guardian_name,
                        relationship=relationship_other or relationship,
                        relationship_other=relationship_other,
                        next_of_kin_phone=guardian_phone,
                        caregiver_name=caregiver_name or guardian_name,
                    )
                    st.session_state["care_profile_form"] = profile_data
                    field_errors = _profile_field_errors(profile_data)
                    if field_errors:
                        _set_field_errors("profile", field_errors)
                        st.rerun()
                    else:
                        _clear_field_errors()
                        _set_profile_step("medicine")
                        st.rerun()

        elif active_step == "medicine":
            with st.container(key="profile-step-card-medicine"):
                _render_html('<div class="setup-section-title">Medicine Routine</div>')
                c1, c2, c3, c4 = st.columns(4, gap="medium")
                medicine_name = _profile_text_input(c1, "Medicine name", "medicine_name", current)
                medicine_dose = _profile_text_input(c2, "Dose", "medicine_dose", current)
                medicine_frequency = _profile_selectbox(c3, "Frequency", "medicine_frequency", current, FREQUENCY_OPTIONS)
                medicine_time = c4.text_input(
                    "Reminder time",
                    value=str(current.get("medicine_time") or ""),
                    placeholder="09:00",
                    key="primary_medicine_time",
                )
                _render_field_error(c1, active_field_errors, "medicine_name")
                _render_field_error(c2, active_field_errors, "medicine_dose")
                _render_field_error(c3, active_field_errors, "medicine_frequency")
                _render_field_error(c4, active_field_errors, "medicine_time")

                additional_medicines = list(current.get("additional_medicines", []) or [])[: medicine_rows - 1]
                while len(additional_medicines) < medicine_rows - 1:
                    additional_medicines.append({"medicine_name": "", "dose": "", "frequency": "", "reminder_time": ""})
                for row_index, item in enumerate(additional_medicines, start=2):
                    _render_html(f'<div class="setup-rule"></div><div class="setup-section-title">Additional medicine {row_index}</div>')
                    ac1, ac2, ac3, ac4 = st.columns(4, gap="medium")
                    item["medicine_name"] = ac1.text_input("Medicine name", value=item.get("medicine_name", ""), key=f"medicine_name_{row_index}", placeholder="Optional medicine")
                    item["dose"] = ac2.text_input("Dose", value=item.get("dose", ""), key=f"medicine_dose_{row_index}", placeholder="As prescribed")
                    additional_frequency_options = ["Select"] + FREQUENCY_OPTIONS
                    additional_frequency_index = additional_frequency_options.index(item.get("frequency", "")) if item.get("frequency", "") in additional_frequency_options else 0
                    selected_frequency = ac3.selectbox(
                        "Frequency",
                        additional_frequency_options,
                        key=f"medicine_frequency_{row_index}",
                        index=additional_frequency_index,
                    )
                    item["frequency"] = "" if selected_frequency == "Select" else selected_frequency
                    item["reminder_time"] = ac4.text_input(
                        "Reminder time",
                        value=str(item.get("reminder_time") or ""),
                        key=f"medicine_time_{row_index}",
                        placeholder="14:00",
                    )
                    _render_field_error(ac1, active_field_errors, f"additional_{row_index}_medicine_name")
                    _render_field_error(ac2, active_field_errors, f"additional_{row_index}_dose")
                    _render_field_error(ac3, active_field_errors, f"additional_{row_index}_frequency")
                    _render_field_error(ac4, active_field_errors, f"additional_{row_index}_reminder_time")

                _show_validation_errors(_flatten_field_errors(active_field_errors))
                action_cols = st.columns([1, 1.15, 1, 1.25], gap="medium")
                back_clicked = action_cols[0].button("Back", use_container_width=True, key="medicine_back_profile")
                add_clicked = action_cols[1].button("+ Add medicine", use_container_width=True, key="medicine_add_row")
                remove_clicked = action_cols[2].button("Remove last", use_container_width=True, key="medicine_remove_row") if medicine_rows > 1 else False
                next_clicked = action_cols[3].button("Next: Preferences", type="primary", use_container_width=True, key="medicine_next_preferences")
                if back_clicked or add_clicked or remove_clicked or next_clicked:
                    profile_data = _profile_data_from_values(
                        current,
                        medicine_name=medicine_name,
                        medicine_dose=medicine_dose,
                        medicine_frequency=medicine_frequency,
                        medicine_time=medicine_time,
                        additional_medicines=additional_medicines,
                    )
                    st.session_state["care_profile_form"] = profile_data
                    if back_clicked:
                        _clear_field_errors()
                        _set_profile_step("profile")
                        st.rerun()
                    if add_clicked:
                        st.session_state["profile_medicine_rows"] = min(medicine_rows + 1, 4)
                        _set_profile_step("medicine")
                        st.rerun()
                    if remove_clicked:
                        st.session_state["profile_medicine_rows"] = max(medicine_rows - 1, 1)
                        _set_profile_step("medicine")
                        st.rerun()
                    field_errors = _medicine_field_errors(profile_data)
                    if field_errors:
                        _set_field_errors("medicine", field_errors)
                        st.rerun()
                    else:
                        _clear_field_errors()
                        _set_profile_step("preferences")
                        st.rerun()

        elif active_step == "preferences":
            with st.container(key="profile-step-card-preferences"):
                _render_html('<div class="setup-section-title">Preferences</div>')
                c1, c2, c3, c4 = st.columns(4, gap="medium")
                important_object = _profile_text_input(c1, "Important object to find", "important_object", current)
                preferred_tone = _profile_selectbox(c2, "Nesto tone", "preferred_tone", current, TONE_OPTIONS)
                preferred_language = _profile_selectbox(c3, "Preferred language", "preferred_language", current, LANGUAGE_OPTIONS)
                care_notes = _profile_text_input(c4, "Care notes", "care_notes", current)
                _render_field_error(c1, active_field_errors, "important_object")
                _render_field_error(c2, active_field_errors, "preferred_tone")
                _render_field_error(c3, active_field_errors, "preferred_language")
                _render_field_error(c4, active_field_errors, "care_notes")
                language_other = ""
                if preferred_language == "Other":
                    language_other = st.text_input(
                        "Preferred language details",
                        value=str(current.get("preferred_language_other", "") or ""),
                        placeholder="Language",
                        key="profile_input_preferred_language_other",
                    )
                user_preferences = st.text_area(
                    "Extra preferences for Nesto memory",
                    value=str(current.get("user_preferences", "") or ""),
                    placeholder=PROFILE_PLACEHOLDERS["user_preferences"],
                    key="profile_input_user_preferences",
                )
                _show_validation_errors(_flatten_field_errors(active_field_errors))
                back_col, next_col = st.columns([1, 1.4], gap="medium")
                back_clicked = back_col.button("Back", use_container_width=True, key="preferences_back_medicine")
                next_clicked = next_col.button("Next: Consent & Review", type="primary", use_container_width=True, key="preferences_next_review")
                profile_data = _profile_data_from_values(
                    current,
                    important_object=important_object,
                    preferred_tone=preferred_tone,
                    preferred_language=language_other or preferred_language,
                    preferred_language_other=language_other,
                    care_notes=care_notes,
                    user_preferences=user_preferences,
                )
                if back_clicked:
                    st.session_state["care_profile_form"] = profile_data
                    _clear_field_errors()
                    _set_profile_step("medicine")
                    st.rerun()
                if next_clicked:
                    st.session_state["care_profile_form"] = profile_data
                    field_errors = _preferences_field_errors({
                        **profile_data,
                        "preferred_language": preferred_language,
                    })
                    if field_errors:
                        _set_field_errors("preferences", field_errors)
                        st.rerun()
                    else:
                        _clear_field_errors()
                        _set_profile_step("review")
                        st.rerun()

        else:
            profile_data = _current_profile_for_mode(st.session_state)
            _render_html('<div class="profile-shell"><div class="setup-section-title">Consent & Review</div>')
            _render_html(_profile_summary_html(profile_data))
            _render_html("</div>")
            _render_account_setup_fields()
            _render_consent_cards()
            c1, c2 = st.columns([1, 1.4], gap="medium")
            if c1.button("Back", use_container_width=True):
                _set_profile_step("preferences")
                st.rerun()
            save_disabled = not _all_consent_accepted()
            if save_disabled:
                _render_html('<div class="nesto-warning-banner">Please read and accept the Terms, Privacy Notice, and Consent Checklist before saving.</div>')
            if c2.button("Save and continue", type="primary", use_container_width=True, disabled=save_disabled):
                errors = []
                errors.extend(_validate_profile_step(profile_data))
                errors.extend(_validate_medicine_step(profile_data))
                errors.extend(_validate_preferences_step(profile_data))
                if not _all_consent_accepted():
                    errors.append("Please accept all required consent documents.")
                account_values = _account_setup_values()
                account_errors = auth_store.registration_errors(account_values)
                if _show_validation_errors(errors + account_errors):
                    return
                consent = {
                    **_consent_state(),
                    "accepted_at": dt.datetime.now().isoformat(timespec="seconds"),
                }
                profile_data = _profile_data_from_values(profile_data, consent=consent)
                account_result, account_save_errors = auth_store.create_accounts_for_profile(profile_data, account_values)
                if _show_validation_errors(account_save_errors):
                    st.session_state["profile_account_conflict"] = True
                    return
                if account_result and account_result.get("profile_id"):
                    profile_data["user_id"] = account_result["profile_id"]
                    profile_data["patient_id"] = account_result["profile_id"]
                    profile_data["robot_id"] = "H1"
                    if account_result.get("patient_user"):
                        auth_store.apply_user_session(st.session_state, account_result["patient_user"])
                st.session_state["profile_auth_accounts_created"] = True
                st.session_state["profile_created_accounts"] = account_result or {}
                account_status = (account_result or {}).get("status", "created")
                if account_status == "already_saved":
                    st.session_state["profile_success_heading"] = "Profile already saved. You can continue to Nesto."
                    st.session_state["profile_account_status_label"] = "Already saved"
                else:
                    st.session_state["profile_success_heading"] = "Profile and account created successfully."
                    st.session_state["profile_account_status_label"] = "Created successfully"
                st.session_state["care_profile_form"] = profile_data
                _save_profile_and_log(st.session_state, profile_data)
                _clear_account_password_fields()
                st.session_state.pop("profile_account_conflict", None)
                st.session_state["profile_setup_saved"] = True
                st.rerun()
            if st.session_state.get("profile_account_conflict"):
                conflict_left, conflict_right = st.columns(2, gap="medium")
                if conflict_left.button("Sign in with existing account", use_container_width=True):
                    st.query_params["auth_mode"] = "signin"
                    st.rerun()
                if conflict_right.button("Use another email", use_container_width=True):
                    st.session_state.pop("profile_account_conflict", None)
                    st.rerun()

    with helper_col:
        _render_html(
            f"""
            <div class="setup-robot-card">
                <div class="setup-speech">I'll remember what matters. <span style="color:#7fa98c;">&#9829;</span></div>
                {_nesto_robot()}
            </div>
            <div class="setup-side-card">
                <h3>Why we ask this?</h3>
                <p>This information helps Nesto provide the right reminders, support, and care at the right time.</p>
            </div>
            <div class="setup-privacy">
                <b>Your data is safe and private.</b><br>
                Only you and your family can see it.
            </div>
            """
        )

def _profile_legacy_debug():
    current = get_profile(st.session_state)
    query_step = ""
    try:
        query_step = st.query_params.get("profile_step", "")
    except Exception:
        query_step = ""
    if query_step in {"profile", "medicine", "preferences", "review"}:
        st.session_state["profile_setup_step"] = query_step
    active_step = st.session_state.get("profile_setup_step", "profile")
    medicine_rows = int(st.session_state.get("profile_medicine_rows", 1) or 1)
    medicine_rows = max(1, min(medicine_rows, 4))
    step_classes = {
        "profile": "active" if active_step == "profile" else "",
        "medicine": "active" if active_step == "medicine" else "",
        "preferences": "active" if active_step == "preferences" else "",
        "review": "active" if active_step == "review" else "",
    }
    _render_html(
        f"""
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {{
                display: none !important;
            }}
            .block-container {{
                max-width: 1120px !important;
                padding: 10px 10px 12px !important;
            }}
            .stApp {{
                background: #f4efe5 !important;
            }}
            .stApp::before {{
                opacity: .025 !important;
            }}
            .profile-sidebar-card {{
                min-height: 686px;
                border: 1px solid #e7ded0;
                border-radius: 18px;
                background: rgba(255,255,255,.92);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                padding: 18px 16px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}
            .profile-brand {{
                display: flex;
                align-items: center;
                gap: 9px;
                color: #123536;
                font-weight: 950;
                margin-bottom: 22px;
            }}
            .profile-brand span {{
                font-size: 1.65rem;
            }}
            .profile-nav {{
                display: grid;
                gap: 6px;
            }}
            .profile-nav-item {{
                min-height: 34px;
                border-radius: 8px;
                padding: 0 9px;
                display: flex;
                align-items: center;
                gap: 9px;
                color: #25413f !important;
                text-decoration: none !important;
                font-size: .78rem;
                font-weight: 750;
            }}
            .profile-nav-item.active,
            .profile-nav-item:hover {{
                background: #e7f1eb;
            }}
            .profile-nav-item span {{
                width: 16px;
                text-align: center;
            }}
            .profile-side-robot {{
                margin-top: auto;
                border: 1px solid #eee5d9;
                border-radius: 14px;
                background: rgba(255,253,248,.86);
                min-height: 184px;
                display: grid;
                place-items: center;
                text-align: center;
                padding: 10px;
                overflow: hidden;
                color: #123536;
                font-weight: 850;
            }}
            .profile-side-robot .nesto-bot {{
                transform: scale(.72);
                transform-origin: center;
                margin: -20px 0 -30px;
            }}
            .profile-side-robot span {{
                color: #006b45;
                font-size: .8rem;
                font-weight: 950;
            }}
            .profile-shell {{
                border: 1px solid #e7ded0;
                border-radius: 18px;
                background: rgba(255,255,255,.88);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                margin-bottom: 10px;
                padding: 18px 18px 14px;
                color: #102f32;
            }}
            .setup-steps {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0;
                margin: 0 0 14px;
                color: #697a77;
                font-size: .86rem;
                font-weight: 750;
            }}
            .setup-step {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                white-space: nowrap;
                position: relative;
                padding: 0 13px;
                color: #176b4d !important;
                text-decoration: none !important;
                font-weight: 850;
            }}
            .setup-step:hover {{
                color: #0f5139 !important;
                text-decoration: none !important;
            }}
            .setup-step:not(:last-child)::after {{
                content: "";
                position: absolute;
                left: calc(100% - 7px);
                width: 14px;
                height: 1px;
                background: #d9ded8;
            }}
            .setup-step-number {{
                width: 22px;
                height: 22px;
                border-radius: 999px;
                display: inline-grid;
                place-items: center;
                border: 1px solid #d9ded8;
                background: #fff;
                color: #6f7d7b;
                font-size: .72rem;
                font-weight: 950;
            }}
            .setup-step.active .setup-step-number {{
                background: #176b4d;
                border-color: #176b4d;
                color: #fff;
            }}
            .setup-title h1 {{
                font-size: 1.5rem;
                line-height: 1.08;
                margin: 0 0 8px;
                letter-spacing: 0;
            }}
            .setup-title p {{
                margin: 0;
                color: #60706d;
                font-weight: 650;
            }}
            .setup-card, .setup-side-card {{
                border: 1px solid #e5ded2;
                background: rgba(255,255,255,.84);
                border-radius: 14px;
                box-shadow: 0 12px 30px rgba(40, 55, 44, .07);
            }}
            .setup-section-title {{
                margin: 6px 0 8px;
                color: #123536;
                font-size: 1rem;
                font-weight: 950;
            }}
            .setup-section-title.focused {{
                border-radius: 12px;
                background: #e7f1eb;
                border: 1px solid #cbd9d2;
                padding: 10px 12px;
            }}
            div[data-testid="stForm"] {{
                border: 1px solid #e5ded2 !important;
                background: rgba(255,255,255,.92) !important;
                border-radius: 14px !important;
                box-shadow: 0 12px 30px rgba(40, 55, 44, .07) !important;
                padding: 16px 16px 10px !important;
            }}
            .stTextInput input,
            .stTextArea textarea,
            .stSelectbox div[data-baseweb="select"] > div {{
                border-radius: 10px !important;
                border-color: #e3d8c7 !important;
                background: #fffdf8 !important;
                color: #123536 !important;
                box-shadow: none !important;
            }}
            .stButton button,
            .stFormSubmitButton button {{
                border-radius: 999px !important;
                min-height: 44px;
                font-weight: 900 !important;
                border: 1px solid #176b4d !important;
                box-shadow: 0 12px 24px rgba(23,107,77,.13) !important;
            }}
            .stFormSubmitButton:first-of-type button {{
                background: #176b4d !important;
                color: #fff !important;
            }}
            .setup-rule {{
                height: 1px;
                background: #ece4d7;
                margin: 12px 0 9px;
            }}
            .setup-helper {{
                padding: 16px;
                color: #183b3c;
            }}
            .setup-card.nesto-pattern-surface::before {{
                opacity: .025;
            }}
            .setup-side-card.nesto-pattern-surface::before,
            .setup-robot-card.nesto-pattern-surface::before,
            .setup-privacy.nesto-pattern-surface::before,
            .profile-side-robot.nesto-pattern-surface::before {{
                opacity: .045;
            }}
            .setup-helper h3 {{
                margin: 0 0 8px;
                font-size: 1rem;
            }}
            .setup-helper p {{
                margin: 0;
                color: #60706d;
                font-size: .9rem;
                line-height: 1.55;
                font-weight: 650;
            }}
            .setup-privacy {{
                margin-top: 14px;
                padding: 16px;
                border: 1px solid #e5ded2;
                border-radius: 14px;
                background: #fffdf8;
                color: #60706d;
                font-size: .86rem;
                line-height: 1.55;
                font-weight: 650;
            }}
            .add-medicine-note {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                margin-top: 8px;
                padding: 8px 12px;
                border: 1px solid #cbd9d2;
                border-radius: 10px;
                color: #176b4d;
                font-weight: 850;
                background: #fbfffc;
                font-size: .88rem;
            }}
            .setup-robot-card {{
                position: relative;
                min-height: 184px;
                display: grid;
                place-items: center;
                margin-bottom: 14px;
                border: 1px solid #e5ded2;
                border-radius: 18px;
                background: rgba(255,253,248,.82);
                overflow: hidden;
            }}
            .setup-robot-card .nesto-bot {{
                transform: scale(.92);
            }}
            .setup-speech {{
                position: absolute;
                right: 10px;
                top: 8px;
                max-width: 150px;
                border: 1px solid #e2d7c8;
                border-radius: 14px;
                background: #fff;
                color: #123536;
                padding: 8px 10px;
                font-size: .74rem;
                line-height: 1.35;
                font-weight: 900;
                box-shadow: 0 10px 22px rgba(37,65,63,.08);
            }}
            @media (max-width: 720px) {{
                .setup-steps {{
                    justify-content: flex-start;
                    gap: 10px;
                    overflow-x: auto;
                    padding-bottom: 8px;
                }}
                .profile-shell {{
                    padding-inline: 0;
                }}
            }}
        </style>
        <div class="profile-style-anchor"></div>
        """
    )

    sidebar_col, main_col, helper_col = st.columns([0.42, 1.22, 0.46], gap="small")
    with sidebar_col:
        _render_html(_profile_setup_sidebar_html())
    with main_col:
        _render_html(
            f"""
            <div class="profile-shell">
                <div class="setup-steps">
                    <a class="setup-step {step_classes['profile']}" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_step=profile"><span class="setup-step-number">1</span>Profile</a>
                    <a class="setup-step {step_classes['medicine']}" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_step=medicine"><span class="setup-step-number">2</span>Medicine</a>
                    <a class="setup-step {step_classes['preferences']}" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_step=preferences"><span class="setup-step-number">3</span>Preferences</a>
                    <a class="setup-step {step_classes['review']}" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_step=review"><span class="setup-step-number">4</span>Review</a>
                </div>
                <div class="setup-title">
                    <h1>Let's create a care profile</h1>
                    <p>This helps Nesto personalize care and remember what matters.</p>
                </div>
            </div>
            """
        )
        with st.form("profile_preferences_form"):
            _render_html('<div class="setup-section-title">Elderly User Information</div>')
            c1, c2, c3, c4 = st.columns([1.35, 1.05, 0.62, 1.0])
            patient_name = c1.text_input("Full name", current["patient_name"])
            preferred_name = c2.text_input("Preferred name", current["preferred_name"])
            age = c3.text_input("Age", current["age"])
            robot_name = c4.text_input("Robot name", current["robot_name"])

            _render_html('<div class="setup-rule"></div><div class="setup-section-title">Guardian / Caregiver details</div>')
            c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.18, 1.2])
            next_of_kin_name = c1.text_input("Guardian / Caregiver name", current["next_of_kin_name"])
            relationship = c2.text_input("Relationship to elderly user", current["relationship"])
            next_of_kin_phone = c3.text_input("Phone number", current["next_of_kin_phone"])
            caregiver_name = c4.text_input("Caregiver name, if different", current.get("caregiver_name", ""))

            medicine_focus = " focused" if st.session_state.get("profile_setup_step") == "medicine" else ""
            _render_html(f'<div class="setup-rule"></div><div id="medicine-routine" class="setup-section-title{medicine_focus}">Medicine Routine (Primary)</div>')
            c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.0, 1.0])
            medicine_name = c1.text_input("Medicine name", current["medicine_name"])
            medicine_dose = c2.text_input("Dose", current["medicine_dose"])
            frequency_options = ["Once daily", "Twice daily", "Three times daily", "As needed"]
            medicine_frequency = c3.selectbox(
                "Frequency",
                frequency_options,
                index=frequency_options.index(current.get("medicine_frequency", "Twice daily"))
                if current.get("medicine_frequency") in frequency_options
                else 1,
            )
            medicine_time = c4.text_input("Reminder time", current["medicine_time"])
            additional_medicines = []
            for row_index in range(2, medicine_rows + 1):
                _render_html(f'<div class="setup-rule"></div><div class="setup-section-title">Additional medicine {row_index}</div>')
                ac1, ac2, ac3, ac4 = st.columns([1.2, 1.0, 1.0, 1.0])
                additional_medicines.append({
                    "medicine_name": ac1.text_input("Medicine name", "", key=f"medicine_name_{row_index}", placeholder="Optional medicine"),
                    "dose": ac2.text_input("Dose", "", key=f"medicine_dose_{row_index}", placeholder="As prescribed"),
                    "frequency": ac3.selectbox("Frequency", frequency_options, key=f"medicine_frequency_{row_index}", index=1),
                    "reminder_time": ac4.text_input("Reminder time", "", key=f"medicine_time_{row_index}", placeholder="02:00 PM"),
                })
            med_action_cols = st.columns([1, 1])
            add_medicine_clicked = med_action_cols[0].form_submit_button("+ Add another medicine", use_container_width=True)
            remove_medicine_clicked = med_action_cols[1].form_submit_button("Remove last medicine", use_container_width=True) if medicine_rows > 1 else False

            _render_html('<div class="setup-rule"></div><div class="setup-section-title">Important Details / Preferences</div>')
            c1, c2, c3, c4 = st.columns([1.05, 1.05, 1.0, 1.2])
            important_object = c1.text_input("Important object to find", current["important_object"])
            tone_options = ["Calm and direct", "Very gentle", "Short instructions", "Family-style encouragement"]
            preferred_tone = c2.selectbox(
                "Nesto tone",
                tone_options,
                index=tone_options.index(current.get("preferred_tone", "Calm and direct"))
                if current.get("preferred_tone") in tone_options
                else 0,
            )
            language_options = ["English", "Spanish", "Arabic", "French"]
            preferred_language = c3.selectbox(
                "Preferred language",
                language_options,
                index=language_options.index(current.get("preferred_language", "English"))
                if current.get("preferred_language") in language_options
                else 0,
            )
            care_notes = c4.text_input("Care notes", current["care_notes"] or "Calm in the morning")

            user_preferences = st.text_area(
                "Extra preferences for Nesto memory",
                current["user_preferences"],
                placeholder="Example: prefers short reminders, likes family updates after medication.",
            )
            save_col, next_col = st.columns([1.2, 1])
            save_clicked = save_col.form_submit_button("Save profile to ChromaDB memory", type="primary", use_container_width=True)
            next_clicked = next_col.form_submit_button("Next: Medicine Routine ->", use_container_width=True)
        submitted = save_clicked or next_clicked or add_medicine_clicked or remove_medicine_clicked
        if submitted:
            profile_data = {
                "patient_name": patient_name,
                "preferred_name": preferred_name,
                "age": age,
                "next_of_kin_name": next_of_kin_name,
                "relationship": relationship,
                "next_of_kin_phone": next_of_kin_phone,
                "caregiver_name": caregiver_name or next_of_kin_name,
                "medicine_name": medicine_name,
                "medicine_dose": medicine_dose,
                "medicine_frequency": medicine_frequency,
                "medicine_time": medicine_time,
                "robot_name": robot_name,
                "important_object": important_object,
                "preferred_language": preferred_language,
                "preferred_tone": preferred_tone,
                "user_preferences": user_preferences,
                "care_notes": care_notes,
                "additional_medicines": additional_medicines,
            }
            if add_medicine_clicked:
                st.session_state["care_profile_form"] = profile_data
                st.session_state["profile_medicine_rows"] = min(medicine_rows + 1, 4)
                st.session_state["profile_setup_step"] = "medicine"
                st.session_state["profile_setup_notice"] = "Added another medicine row."
                st.rerun()
            if remove_medicine_clicked:
                st.session_state["care_profile_form"] = profile_data
                st.session_state["profile_medicine_rows"] = max(medicine_rows - 1, 1)
                st.session_state["profile_setup_step"] = "medicine"
                st.session_state["profile_setup_notice"] = "Removed the last medicine row."
                st.rerun()
            if next_clicked:
                st.session_state["care_profile_form"] = profile_data
                st.session_state["profile_setup_step"] = "medicine"
                st.session_state["profile_setup_notice"] = "Medicine routine is ready to review. The page stayed on profile setup."
                st.rerun()

            saved = save_profile(st.session_state, profile_data)
            st.session_state["profile_setup_step"] = "review"
            if saved:
                st.success("Profile saved successfully. Nesto is ready to personalize care.")
            else:
                st.info("Profile saved for this session. Personalization memory will sync when the memory service is available.")

    with helper_col:
        notice = st.session_state.pop("profile_setup_notice", "")
        if notice:
            st.info(notice)
        _render_html(
            f"""
            <div class="setup-robot-card nesto-pattern-surface nesto-pattern-soft">
                <div class="setup-speech">I'll remember what matters. <span style="color:#7fa98c;">&#9829;</span></div>
                {_nesto_robot()}
            </div>
            <div class="setup-side-card setup-helper nesto-pattern-surface nesto-pattern-soft">
                <h3>Why we ask this?</h3>
                <p>This information helps Nesto provide the right reminders, support, and care at the right time.</p>
            </div>
            <div class="setup-privacy nesto-pattern-surface nesto-pattern-soft">
                <b>Your data is safe and private.</b><br>
                Only you and your family can see it.
            </div>
            """
        )



def consent():
    page_header("Customer / Family App", "Consent", "Data permissions, legal checks, and safety boundaries.", "Consent")
    left, right = st.columns(2)
    with left:
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Consent scope</p>
                <div class="row"><span class="row-main">Robot status and safety events</span>{badge("Allowed","green")}</div>
                <div class="row"><span class="row-main">Care routine and profile information</span>{badge("Allowed","green")}</div>
                <div class="row"><span class="row-main">Scenario monitoring and test input</span>{badge("Allowed","green")}</div>
                <div class="row"><span class="row-main">Personalization memory</span>{badge("Allowed","green")}</div>
            </div>
            <div class="card">
                <p class="section-title">Legal checklist</p>
                <div class="row"><span class="dot" style="background:{PURPLE};"></span><span class="row-main">Terms and Conditions prepared</span></div>
                <div class="row"><span class="dot" style="background:{PURPLE};"></span><span class="row-main">GDPR considerations documented</span></div>
                <div class="row"><span class="dot" style="background:{PURPLE};"></span><span class="row-main">DPIA summary prepared</span></div>
                <div class="row"><span class="dot" style="background:{PURPLE};"></span><span class="row-main">AI safety boundary noted</span></div>
            </div>
            """
        )
    with right:
        _render_html(
            f"""
            <div class="card" style="border-color:#ffd1d1;background:#fff7f7;">
                <p class="section-title" style="color:{RED};">Safety boundaries</p>
                <div class="row"><span class="dot" style="background:{RED};"></span><span class="row-main">No medical diagnosis</span></div>
                <div class="row"><span class="dot" style="background:{RED};"></span><span class="row-main">No medication dosage advice</span></div>
                <div class="row"><span class="dot" style="background:{RED};"></span><span class="row-main">No emergency-service replacement</span></div>
                <div class="row"><span class="dot" style="background:{RED};"></span><span class="row-main">Simulated or project data only</span></div>
            </div>
            """
        )
        st.checkbox(f"{patient()} and the caregiver consent to using this data for the care assistant project.", value=True)



def family_dashboard():
    metrics = care_metrics()
    activity = recent_activity(limit=6)
    profile = _care_profile()
    active_session = ensure_active_care_session(st.session_state)

    care_name_raw = str(
        active_session.get("assigned_patient_preferred_name")
        or active_session.get("assigned_patient_name")
        or "Elderly User 01"
    ).strip()
    patient_full_raw = str(active_session.get("assigned_patient_name") or care_name_raw).strip()
    family_name_raw = str(active_session.get("guardian_name") or "Guardian / Caregiver").strip()
    care_name = escape(care_name_raw)
    patient_full = escape(patient_full_raw)
    family_name = escape(family_name_raw)
    family_full = escape(family_name_raw)
    relationship = escape(str(active_session.get("guardian_relationship") or profile.get("relationship") or "Guardian / Caregiver"))
    phone = escape(str(active_session.get("guardian_phone") or profile.get("next_of_kin_phone") or "+44 7700 900123"))
    robot_name = escape(str(profile.get("robot_name") or "Nesto"))
    guardian_id = str(active_session.get("guardian_id") or "guardian_01")
    patient_id = str(active_session.get("assigned_patient_id") or "elderly_user_01")
    linked_patients = active_session.get("linked_patients") if isinstance(active_session.get("linked_patients"), list) else []

    route_base = f"?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&guardian_id={guardian_id}&patient_id={patient_id}"
    caregiver_section = (_query_param("caregiver_section") or "overview").strip().lower()
    caregiver_action = (_query_param("caregiver_action") or "").strip().lower()
    if caregiver_action == "summary":
        caregiver_action = "full_summary"
    activity_detail = _query_param("activity_detail")
    alert_detail = _query_param("alert_detail")
    prompt_key = (_query_param("cg_prompt") or "").strip()
    message_text = str(_query_param("cg_message_text") or "").strip()
    note_text = str(_query_param("care_note_text") or "").strip()

    action_events = {
        "acknowledge": ("acknowledge_update", "Update acknowledged."),
        "medicine": ("remind_medicine", "Medicine reminder prepared."),
        "call": ("call_elderly_user", f"Preparing caregiver call to {care_name}."),
        "alerts": ("review_alerts", "Alert review opened."),
        "note": ("caregiver_note_saved", "Care Notes opened."),
        "message": ("message_nesto", "Message Nesto opened."),
        "full_summary": ("view_daily_summary", "Full summary opened."),
    }
    if caregiver_action in action_events:
        event_name, feedback = action_events[caregiver_action]
        action_token = f"{caregiver_action}:{message_text}:{note_text}:{prompt_key}"
        if st.session_state.get("last_caregiver_action") != action_token:
            st.session_state["last_caregiver_action"] = action_token
            event_type = "scenario_event"
            if caregiver_action == "message":
                event_type = "conversation_event"
            elif caregiver_action == "note":
                event_type = "caregiver_note_saved"
            elif caregiver_action == "alerts":
                event_type = "alert"
            record_dashboard_event(
                event_type=event_type,
                scenario_type=event_name,
                role="guardian_caregiver",
                status="requested" if caregiver_action != "note" else "saved",
                source_page="Guardian / Caregiver Dashboard",
                payload={
                    "guardian_id": guardian_id,
                    "guardian_name": family_name_raw,
                    "patient_id": patient_id,
                    "patient_name": patient_full_raw,
                    "patient_preferred_name": care_name_raw,
                    "message": message_text or note_text or feedback,
                    "caregiver_action": caregiver_action,
                },
            )
        st.session_state["caregiver_action_feedback"] = feedback

    if prompt_key:
        prompt_map = {
            "how_today": f"{care_name_raw} is calm today. Medicine is on track and there are no critical alerts.",
            "medicine": f"{care_name_raw}'s morning medicine is marked as taken. The next reminder is later today.",
            "alerts": f"There are two watch items for {care_name_raw}: low activity and a possible missed medication reminder.",
            "activity": f"Recent activity for {care_name_raw} includes a medicine check, a Nesto conversation, object found, and mood check-in.",
        }
        if prompt_key in prompt_map:
            st.session_state["caregiver_nesto_response"] = prompt_map[prompt_key]
            st.session_state["caregiver_nesto_prompt"] = prompt_key

    if message_text and st.session_state.get("last_caregiver_message") != message_text:
        st.session_state["last_caregiver_message"] = message_text
        st.session_state["caregiver_nesto_response"] = "Nesto received your note and will keep it with today's care context."
        record_dashboard_event(
            event_type="conversation_event",
            scenario_type="message_nesto",
            role="guardian_caregiver",
            status="sent",
            source_page="Guardian / Caregiver Dashboard",
            payload={
                "guardian_id": guardian_id,
                "guardian_name": family_name_raw,
                "patient_id": patient_id,
                "patient_name": patient_full_raw,
                "message": message_text,
            },
        )

    if note_text and st.session_state.get("last_caregiver_note") != note_text:
        st.session_state["last_caregiver_note"] = note_text
        st.session_state.setdefault("caregiver_notes", []).append(
            {
                "guardian_id": guardian_id,
                "guardian_name": family_name_raw,
                "patient_id": patient_id,
                "patient_name": patient_full_raw,
                "patient_preferred_name": care_name_raw,
                "event_name": "caregiver_note_saved",
                "text": note_text,
                "time": dt.datetime.now().strftime("%I:%M %p").lstrip("0"),
            }
        )
        st.session_state["caregiver_note_feedback"] = "Care note saved."
        record_dashboard_event(
            event_type="caregiver_note_saved",
            scenario_type="caregiver_note_saved",
            role="guardian_caregiver",
            status="saved",
            source_page="Guardian / Caregiver Dashboard",
            payload={
                "guardian_id": guardian_id,
                "guardian_name": family_name_raw,
                "patient_id": patient_id,
                "patient_name": patient_full_raw,
                "note": note_text,
                "message": f"{family_name_raw} saved a care note for {care_name_raw}.",
            },
        )

    score = metrics.get("score", 82)
    medicine = metrics.get("medicine", "94%")
    if not str(medicine).endswith("%"):
        medicine = "94%"
    mood = metrics.get("mood", "Calm")
    if mood in {"Good", "Ok"}:
        mood = "Calm"
    steps = metrics.get("activity", "4,350")
    if steps == "3,120":
        steps = "4,350"
    battery = 87

    fallback_rows = [
        {"title": "Medication taken", "description": "Morning medicine marked as taken.", "time": "09:05 AM", "icon": "&#128138;"},
        {"title": "Talked to Nesto", "description": '"I feel a little tired this morning."', "time": "08:52 AM", "icon": "&#128172;"},
        {"title": "Cane found", "description": "Living Room", "time": "08:45 AM", "icon": "&#128269;"},
        {"title": "Mood check-in", "description": "Calm", "time": "08:45 AM", "icon": "&#128578;"},
        {"title": "Care session started", "description": f"{robot_name} began the morning support routine.", "time": "08:15 AM", "icon": "&#9825;"},
        {"title": "Robot update", "description": f"{robot_name} is online and ready.", "time": "08:00 AM", "icon": "&#129302;"},
    ]
    rows = []
    for index in range(6):
        source = activity[index] if index < len(activity) else fallback_rows[index]
        fallback = fallback_rows[index]
        rows.append(
            {
                "title": str(source.get("title") or fallback["title"]),
                "description": str(source.get("description") or fallback["description"]),
                "time": str(source.get("time") or fallback["time"]),
                "icon": fallback["icon"],
            }
        )

    activity_html = []
    for index, row in enumerate(rows):
        selected = " selected" if str(activity_detail or "") == str(index) else ""
        activity_html.append(
            f"""
            <a target="_self" class="cg-row{selected}" href="{route_base}&caregiver_section=activity&activity_detail={index}#cg-detail">
                <span class="cg-row-icon">{row['icon']}</span>
                <span><b>{escape(row['title'])}</b><small>{escape(row['description'])}</small></span>
                <time>{escape(row['time'])}</time>
            </a>
            """
        )

    fallback_alerts = [
        {
            "title": "Low activity detected",
            "message": "Less active than usual today.",
            "time": "09:15 AM",
            "severity": "Watch",
            "icon": "&#9888;",
        },
        {
            "title": "Possible missed medication",
            "message": "Morning medicine not marked.",
            "time": "08:20 AM",
            "severity": "Medium",
            "icon": "&#128138;",
        },
        {
            "title": "Robot battery low",
            "message": "Nesto should charge later today.",
            "time": "07:40 AM",
            "severity": "Low",
            "icon": "&#128267;",
        },
    ]
    alerts = []
    try:
        import db_queries

        for time_text, message in db_queries.get_alerts(limit=3):
            clean_message = str(message or "Care alert").replace("_", " ").title()
            alerts.append(
                {
                    "title": clean_message,
                    "message": clean_message,
                    "time": str(time_text or ""),
                    "severity": "Watch",
                    "icon": "&#9888;",
                }
            )
    except Exception:
        alerts = []
    if not alerts:
        alerts = fallback_alerts
    loved_count = len(linked_patients) if linked_patients else 1
    active_alert_count = len(alerts)
    message_count = max(1, sum(1 for row in rows if "nesto" in row["title"].lower() or "talk" in row["title"].lower()))
    care_task_count = max(3, sum(1 for row in rows if any(word in row["title"].lower() for word in ("medicine", "mood", "care", "schedule"))))
    robot_status_label = "Online" if battery >= 20 else "Low battery"
    robot_status_sub = f"{battery}% battery"
    alert_html = []
    for index, alert in enumerate(alerts):
        selected = " selected" if str(alert_detail or "") == str(index) else ""
        alert_html.append(
            f"""
            <a target="_self" class="cg-alert{selected}" href="{route_base}&caregiver_action=alerts&caregiver_section=alerts&alert_detail={index}#cg-detail">
                <span class="cg-alert-icon">{alert['icon']}</span>
                <span><b>{escape(alert['title'])}</b><small>{escape(alert['message'])}</small></span>
                <time>{escape(alert['time'])}</time>
                <em>{escape(alert['severity'])}</em>
            </a>
            """
        )

    detail_html = ""
    try:
        if activity_detail is not None:
            detail_row = rows[int(activity_detail)]
            detail_html = f"""
            <div id="cg-detail" class="cg-feedback cg-detail">
                <b>{escape(detail_row['title'])}</b>
                <span>{escape(detail_row['description'])} This item is now highlighted for review.</span>
            </div>
            """
    except (ValueError, IndexError):
        detail_html = ""
    try:
        if alert_detail is not None:
            detail_alert = alerts[int(alert_detail)]
            detail_html = f"""
            <div id="cg-detail" class="cg-feedback cg-detail alert">
                <b>{escape(detail_alert['title'])}</b>
                <span>{escape(detail_alert['message'])} Review this item and call {care_name} if reassurance is needed.</span>
            </div>
            """
    except (ValueError, IndexError):
        pass

    action_copy = {
        "acknowledge": ("Update acknowledged.", f"{family_name} has reviewed the latest care update."),
        "medicine": ("Medicine reminder prepared.", f"{robot_name} will use the approved reminder flow for {care_name}."),
        "call": (f"Preparing caregiver call to {care_name}.", "Use this for a calm family check-in."),
        "alerts": ("Alert review opened.", "The latest alerts are highlighted above."),
        "note": ("Care Notes opened.", "Add a short family-facing note below."),
        "message": ("Message Nesto", "Ask Nesto for a care update or leave a note."),
        "full_summary": ("Full daily summary", f"{care_name} is doing well. Medication is on track, mood is calm, and no critical alerts are active."),
    }
    action_panel_html = ""
    if caregiver_action in action_copy:
        title, body = action_copy[caregiver_action]
        action_panel_html = f"""
        <section id="cg-action-panel" class="cg-action-panel">
            <div>
                <span>Caregiver action</span>
                <h3>{escape(title)}</h3>
                <p>{escape(body)}</p>
            </div>
            <a target="_self" class="cg-secondary-button" href="{route_base}&caregiver_section=overview#cg-overview">Back to overview</a>
        </section>
        """

    nesto_response = escape(st.session_state.get("caregiver_nesto_response", "Ask Nesto for a care update or leave a note."))
    note_feedback = st.session_state.get("caregiver_note_feedback", "")
    note_feedback_html = f'<div class="cg-success">{escape(note_feedback)}</div>' if note_feedback else ""
    saved_notes = st.session_state.get("caregiver_notes", [])
    note_rows = "".join(
        f'<div class="cg-note-row"><b>{escape(note["time"])}</b><span>{escape(note["text"])}</span></div>'
        for note in reversed(saved_notes[-3:])
    )
    if not note_rows:
        note_rows = '<div class="cg-note-row muted"><b>No notes yet</b><span>Saved care notes will appear here.</span></div>'
    linked_loved_html = ""
    if len(linked_patients) > 1:
        loved_rows = []
        for item in linked_patients:
            loved_id = escape(str(item.get("patient_id") or ""))
            loved_name = escape(str(item.get("preferred_name") or item.get("patient_name") or item.get("patient_id") or "Loved one"))
            loved_full = escape(str(item.get("patient_name") or loved_name))
            active = " active" if str(item.get("patient_id") or "") == patient_id else ""
            loved_rows.append(
                f"""
                <a target="_self" class="cg-loved-card{active}" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&guardian_id={guardian_id}&patient_id={loved_id}#cg-overview">
                    <b>{loved_name}</b>
                    <span>{loved_full}</span>
                    <small>Mood: {escape(str(mood))} · Medicine: {escape(str(medicine))} · Last update: {escape(rows[0]["time"] if rows else "Today")}</small>
                    <em>View patient</em>
                </a>
                """
            )
        linked_loved_html = f"""
            <section class="cg-card cg-loved-ones">
                <h3 class="cg-section-title">Linked loved ones</h3>
                <div class="cg-loved-grid">{''.join(loved_rows)}</div>
            </section>
        """

    _render_html(
        f"""
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {{
                display: none !important;
            }}
            .block-container {{
                max-width: 1560px !important;
                padding: 16px !important;
            }}
            .cg-shell {{
                display: grid;
                grid-template-columns: 250px minmax(0, 1fr);
                gap: 18px;
                max-width: 1500px;
                margin: 0 auto 32px;
                color: #183f3a;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                letter-spacing: 0;
            }}
            .cg-shell * {{
                box-sizing: border-box;
            }}
            .cg-sidebar {{
                min-height: 760px;
                border: 1px solid #e7ded0;
                border-radius: 22px;
                background: rgba(255,253,248,.92);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                padding: 20px 18px;
                display: flex;
                flex-direction: column;
                position: sticky;
                top: 14px;
            }}
            .cg-side-brand {{
                display: flex;
                align-items: center;
                gap: 10px;
                color: #123536;
                font-weight: 950;
                margin-bottom: 20px;
                font-size: 1.06rem;
            }}
            .cg-side-brand span {{
                font-size: 1.75rem;
            }}
            .cg-side-label {{
                color: #6b7d78;
                font-size: .72rem;
                font-weight: 950;
                margin: 0 0 10px;
                text-transform: uppercase;
                letter-spacing: 0;
            }}
            .cg-side-nav {{
                display: grid;
                gap: 6px;
            }}
            .cg-side-nav a,
            .cg-side-support,
            .cg-side-logout {{
                min-height: 40px;
                border-radius: 11px;
                padding: 0 12px;
                display: flex;
                align-items: center;
                gap: 10px;
                color: #25413f !important;
                text-decoration: none !important;
                font-size: .84rem;
                font-weight: 850;
            }}
            .cg-side-nav a.active,
            .cg-side-nav a:hover {{
                background: #e7f1eb;
            }}
            .cg-side-nav span {{
                width: 18px;
                text-align: center;
            }}
            .cg-side-card {{
                margin-top: auto;
                border: 1px solid #e3d8c7;
                border-radius: 18px;
                background: #fffdf8;
                padding: 14px;
                text-align: center;
                color: #123536;
                overflow: hidden;
            }}
            .cg-side-card .nesto-bot {{
                transform: scale(.58);
                margin: -22px auto -34px;
                pointer-events: none;
            }}
            .cg-side-card b,
            .cg-side-card small {{
                display: block;
            }}
            .cg-side-card small {{
                color: #176b4d;
                font-weight: 950;
                margin-top: 4px;
            }}
            .cg-side-support,
            .cg-side-logout {{
                justify-content: center;
                border: 1px solid #e3d8c7;
                background: rgba(255,253,248,.86);
                margin-top: 10px;
            }}
            .cg-side-logout {{
                color: #8a2b2b !important;
                background: #fff7f5;
                border-color: #f1d1ca;
            }}
            .cg-page {{
                min-width: 0;
                color: #183f3a;
                padding: 2px 2px 32px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                letter-spacing: 0;
            }}
            .cg-page * {{
                box-sizing: border-box;
            }}
            .cg-page a,
            .cg-page a:visited,
            .cg-page a:hover,
            .cg-page a *,
            .cg-page button {{
                text-decoration: none !important;
                text-decoration-line: none !important;
            }}
            .cg-top {{
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 20px;
                align-items: start;
                margin-bottom: 18px;
            }}
            .cg-dashboard-kicker {{
                display: inline-flex;
                align-items: center;
                margin-bottom: 8px;
                border: 1px solid #cbdccb;
                border-radius: 999px;
                background: #edf4ee;
                padding: 6px 11px;
                color: #176b4d;
                font-size: .72rem;
                font-weight: 950;
                letter-spacing: 0;
            }}
            .cg-top h1 {{
                margin: 0 0 6px;
                font-size: clamp(1.65rem, 2.2vw, 2.2rem);
                letter-spacing: 0;
                line-height: 1.08;
            }}
            .cg-top p {{
                margin: 0;
                color: #61716d;
                font-weight: 700;
            }}
            .cg-actions-top {{
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 10px;
                flex-wrap: wrap;
            }}
            .cg-pill,
            .cg-primary-button,
            .cg-secondary-button,
            .cg-quick-button,
            .cg-logout,
            .cg-note-form button {{
                border-radius: 999px;
                min-height: 42px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 10px 16px;
                font-weight: 900;
                letter-spacing: 0;
                border: 1px solid #cbdccb;
                cursor: pointer;
                box-sizing: border-box;
            }}
            .cg-primary-button,
            .cg-note-form button {{
                background: #176b4d;
                color: #fffdf8 !important;
                border-color: #176b4d;
                box-shadow: 0 12px 28px rgba(23, 107, 77, .18);
            }}
            .cg-pill,
            .cg-secondary-button,
            .cg-quick-button {{
                background: rgba(255, 253, 248, .88);
                color: #183f3a !important;
                border-color: #e3d8c7;
                box-shadow: 0 10px 26px rgba(37, 65, 63, .07);
            }}
            .cg-logout {{
                background: #fff7f5;
                color: #8a2b2b !important;
                border-color: #f1d1ca;
                box-shadow: 0 10px 26px rgba(138,43,43,.05);
            }}
            .cg-pill:hover,
            .cg-secondary-button:hover,
            .cg-quick-button:hover,
            .cg-logout:hover,
            .cg-row:hover,
            .cg-alert:hover {{
                transform: translateY(-2px);
                border-color: #a8bfae;
            }}
            .cg-bell {{
                width: 42px;
                height: 42px;
                border-radius: 999px;
                background: rgba(255, 253, 248, .92);
                border: 1px solid #e3d8c7;
                display: grid;
                place-items: center;
                color: #183f3a !important;
                position: relative;
                box-shadow: 0 10px 26px rgba(37, 65, 63, .07);
            }}
            .cg-bell span {{
                position: absolute;
                top: -6px;
                right: -5px;
                min-width: 20px;
                height: 20px;
                border-radius: 999px;
                display: grid;
                place-items: center;
                color: #fff;
                background: #ef4444;
                font-size: .72rem;
                font-weight: 950;
            }}
            .cg-hero {{
                display: grid;
                grid-template-columns: 1fr 245px;
                gap: 16px;
                align-items: stretch;
                margin-bottom: 16px;
            }}
            .cg-robot-card {{
                border: 1px solid #e3d8c7;
                border-radius: 24px;
                background:
                    linear-gradient(rgba(255, 253, 248, .9), rgba(255, 253, 248, .9)),
                    var(--nesto-brand-pattern),
                    linear-gradient(135deg, rgba(255, 253, 248, .94), rgba(237, 244, 238, .8));
                background-size: auto, 150px 150px, auto;
                padding: 16px;
                box-shadow: 0 18px 40px rgba(37,65,63,.08);
                min-height: 180px;
                overflow: visible;
                cursor: default;
                pointer-events: none;
                display: grid;
                justify-items: center;
                align-content: center;
                gap: 8px;
            }}
            .cg-robot-card .nesto-bot {{
                transform: scale(.72);
                margin: -8px auto -20px;
                animation: cg-nesto-float 4s ease-in-out infinite;
                pointer-events: none;
            }}
            .cg-robot-card b {{
                color: #183f3a;
                text-align: center;
            }}
            .cg-robot-card span {{
                color: #176b4d;
                font-weight: 950;
                font-size: .82rem;
            }}
            .cg-kpis {{
                display: grid;
                grid-template-columns: repeat(6, minmax(0, 1fr));
                gap: 12px;
                margin-bottom: 16px;
            }}
            .cg-card {{
                border: 1px solid #e3d8c7;
                border-radius: 22px;
                background: rgba(255, 253, 248, .88);
                backdrop-filter: blur(12px);
                box-shadow: 0 18px 40px rgba(37, 65, 63, .075);
                padding: 18px;
            }}
            .cg-kpi-card {{
                min-height: 138px;
            }}
            .cg-kpi-label {{
                display: block;
                color: #3e5350;
                font-weight: 900;
                font-size: .8rem;
                margin-bottom: 8px;
            }}
            .cg-kpi-value {{
                font-size: 1.85rem;
                font-weight: 950;
                color: #176b4d;
                line-height: 1.05;
            }}
            .cg-kpi-value.dark {{
                color: #183f3a;
            }}
            .cg-kpi-sub {{
                display: block;
                margin-top: 8px;
                color: #61716d;
                font-weight: 750;
                font-size: .82rem;
            }}
            .spark {{
                width: 100%;
                height: 28px;
                margin-top: 10px;
                background: linear-gradient(135deg, transparent 8%, rgba(41,166,115,.2) 8% 12%, transparent 12% 23%, rgba(41,166,115,.34) 23% 28%, transparent 28% 40%, rgba(41,166,115,.22) 40% 45%, transparent 45% 58%, rgba(41,166,115,.36) 58% 63%, transparent 63% 78%, rgba(41,166,115,.28) 78% 83%, transparent 83%);
                border-bottom: 2px solid #34b27b;
                border-radius: 6px;
            }}
            .spark.orange {{
                background: linear-gradient(135deg, transparent 8%, rgba(249,115,22,.18) 8% 12%, transparent 12% 24%, rgba(249,115,22,.30) 24% 29%, transparent 29% 43%, rgba(249,115,22,.22) 43% 48%, transparent 48% 64%, rgba(249,115,22,.34) 64% 70%, transparent 70%);
                border-bottom-color: #f97316;
            }}
            .cg-grid {{
                display: grid;
                grid-template-columns: 1fr 1.15fr 1fr;
                gap: 16px;
                margin-bottom: 16px;
            }}
            .cg-section-title {{
                margin: 0 0 14px;
                font-weight: 950;
                color: #183f3a;
                font-size: 1.05rem;
            }}
            .cg-row,
            .cg-alert {{
                display: grid;
                align-items: center;
                gap: 12px;
                color: #183f3a !important;
                border-bottom: 1px solid #ede4d8;
                transition: transform .16s ease, border-color .16s ease, background .16s ease;
            }}
            .cg-row {{
                grid-template-columns: 42px 1fr auto;
                padding: 12px 0;
            }}
            .cg-alert {{
                grid-template-columns: 42px 1fr auto auto;
                padding: 14px 0;
            }}
            .cg-row:last-child,
            .cg-alert:last-child {{
                border-bottom: 0;
            }}
            .cg-row.selected,
            .cg-alert.selected {{
                background: rgba(233, 242, 236, .62);
                border-radius: 14px;
                padding-left: 10px;
                padding-right: 10px;
            }}
            .cg-row-icon,
            .cg-alert-icon {{
                width: 34px;
                height: 34px;
                border-radius: 12px;
                display: grid;
                place-items: center;
                background: #eaf5ee;
                color: #176b4d;
                border: 1px solid #d8e7dc;
            }}
            .cg-alert-icon {{
                background: #fff0f0;
                color: #ef4444;
                border-color: #f7caca;
            }}
            .cg-row b,
            .cg-alert b {{
                display: block;
                color: #183f3a;
            }}
            .cg-row small,
            .cg-alert small {{
                display: block;
                color: #61716d;
                font-weight: 650;
                margin-top: 3px;
            }}
            .cg-row time,
            .cg-alert time {{
                color: #61716d;
                font-weight: 750;
                font-size: .8rem;
                white-space: nowrap;
            }}
            .cg-alert em {{
                font-style: normal;
                border-radius: 999px;
                background: #fff3dc;
                color: #9a5b05;
                padding: 5px 9px;
                font-size: .72rem;
                font-weight: 900;
            }}
            .cg-summary {{
                margin-top: 16px;
            }}
            .cg-summary p {{
                color: #3e5350;
                line-height: 1.6;
                font-weight: 650;
                margin: 0;
            }}
            .cg-summary .cg-secondary-button {{
                margin-top: 12px;
                width: fit-content;
                margin-left: auto;
            }}
            .cg-feedback,
            .cg-action-panel {{
                border: 1px solid #cbdccb;
                border-radius: 22px;
                background: linear-gradient(135deg, #edf4ee, #fffdf8);
                box-shadow: 0 12px 28px rgba(37,65,63,.08);
                color: #183f3a;
                padding: 16px 18px;
                margin-bottom: 16px;
            }}
            .cg-feedback b,
            .cg-action-panel h3 {{
                display: block;
                color: #183f3a;
                font-weight: 950;
            }}
            .cg-feedback span,
            .cg-action-panel p {{
                display: block;
                color: #3e5350;
                line-height: 1.48;
                margin: 6px 0 0;
                font-weight: 650;
            }}
            .cg-action-panel {{
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 16px;
                align-items: center;
            }}
            .cg-action-panel > div > span {{
                color: #176b4d;
                font-size: .72rem;
                font-weight: 950;
                text-transform: uppercase;
                letter-spacing: .08em;
            }}
            .cg-action-panel h3 {{
                margin: 4px 0 6px;
                font-size: 1.24rem;
            }}
            .cg-quick {{
                margin-bottom: 16px;
            }}
            .cg-quick-row {{
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 12px;
            }}
            .cg-quick-button {{
                text-align: center;
                min-height: 48px;
                padding: 10px;
            }}
            .cg-bottom-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
                align-items: start;
            }}
            .cg-message-panel,
            .cg-note-panel,
            .cg-profile-panel,
            .cg-settings-panel {{
                min-height: 236px;
            }}
            .cg-message-head {{
                display: grid;
                grid-template-columns: 58px 1fr;
                gap: 12px;
                align-items: center;
                margin-bottom: 14px;
            }}
            .cg-mini-robot {{
                width: 54px;
                height: 54px;
                border-radius: 18px;
                display: grid;
                place-items: center;
                background: #edf4ee;
                border: 1px solid #cbdccb;
                box-shadow: inset 0 0 0 5px rgba(255,255,255,.55);
            }}
            .cg-mini-robot span {{
                position: relative;
                width: 32px;
                height: 24px;
                border-radius: 14px;
                background: #123f3a;
                display: block;
            }}
            .cg-mini-robot span::before,
            .cg-mini-robot span::after {{
                content: "";
                position: absolute;
                top: 7px;
                width: 7px;
                height: 10px;
                border-radius: 999px;
                background: #8ff1ce;
            }}
            .cg-mini-robot span::before {{ left: 8px; }}
            .cg-mini-robot span::after {{ right: 8px; }}
            .cg-prompt-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin: 12px 0;
            }}
            .cg-prompt-row a {{
                border: 1px solid #cbdccb;
                background: #edf4ee;
                color: #183f3a !important;
                border-radius: 999px;
                padding: 8px 12px;
                font-weight: 850;
                font-size: .82rem;
            }}
            .cg-note-form {{
                display: grid;
                gap: 10px;
            }}
            .cg-note-form input,
            .cg-note-form textarea {{
                width: 100%;
                border: 1px solid rgba(168, 191, 174, .55);
                border-radius: 16px;
                background: rgba(255, 252, 246, .9);
                color: #183f3a;
                padding: 13px 14px;
                font: inherit;
                box-sizing: border-box;
                resize: vertical;
                min-height: 46px;
            }}
            .cg-note-form textarea {{
                min-height: 92px;
            }}
            .cg-note-row {{
                display: grid;
                grid-template-columns: 82px 1fr;
                gap: 10px;
                border-top: 1px solid #ede4d8;
                padding: 10px 0 0;
                margin-top: 10px;
                color: #3e5350;
                font-weight: 650;
            }}
            .cg-note-row b {{
                color: #176b4d;
            }}
            .cg-note-row.muted {{
                color: #61716d;
            }}
            .cg-success {{
                border: 1px solid #cbdccb;
                background: #edf4ee;
                color: #176b4d;
                border-radius: 14px;
                padding: 10px 12px;
                font-weight: 900;
                margin-bottom: 10px;
            }}
            .cg-profile-list {{
                display: grid;
                gap: 10px;
            }}
            .cg-profile-list div {{
                border: 1px solid #ede4d8;
                border-radius: 14px;
                background: rgba(255,255,255,.58);
                padding: 11px 12px;
            }}
            .cg-profile-list b {{
                display: block;
                color: #183f3a;
                margin-bottom: 3px;
            }}
            .cg-profile-list span {{
                color: #61716d;
                font-weight: 700;
            }}
            .cg-loved-ones {{
                margin-bottom: 16px;
            }}
            .cg-loved-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
                gap: 12px;
            }}
            .cg-loved-card {{
                border: 1px solid #e3d8c7;
                border-radius: 16px;
                background: rgba(255,255,255,.72);
                color: #183f3a !important;
                text-decoration: none !important;
                padding: 14px;
                display: grid;
                gap: 5px;
            }}
            .cg-loved-card.active {{
                border-color: #176b4d;
                background: #edf4ee;
            }}
            .cg-loved-card b {{ font-size: 1.02rem; }}
            .cg-loved-card span,
            .cg-loved-card small {{ color: #61716d; font-weight: 750; }}
            .cg-loved-card em {{
                font-style: normal;
                color: #176b4d;
                font-weight: 950;
                margin-top: 4px;
            }}
            @keyframes cg-nesto-float {{
                0%, 100% {{ transform: translateY(0) scale(.72); }}
                50% {{ transform: translateY(-6px) scale(.72); }}
            }}
            @media (max-width: 1100px) {{
                .cg-shell {{
                    grid-template-columns: 1fr;
                }}
                .cg-sidebar {{
                    min-height: auto;
                    position: relative;
                    top: auto;
                }}
                .cg-kpis {{
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }}
                .cg-hero,
                .cg-grid,
                .cg-bottom-grid {{
                    grid-template-columns: 1fr;
                }}
                .cg-actions-top {{
                    justify-content: flex-start;
                }}
            }}
            @media (max-width: 760px) {{
                .cg-top {{
                    grid-template-columns: 1fr;
                }}
                .cg-quick-row,
                .cg-kpis {{
                    grid-template-columns: 1fr;
                }}
                .cg-alert {{
                    grid-template-columns: 42px 1fr;
                }}
                .cg-alert time,
                .cg-alert em {{
                    grid-column: 2;
                }}
            }}
        </style>
        <div class="cg-shell">
            <aside class="cg-sidebar">
                <div class="cg-side-brand"><span>&#127968;</span><b>Nesto Care</b></div>
                <div class="cg-side-label">Guardian Dashboard</div>
                <nav class="cg-side-nav">
                    <a target="_self" class="active" href="{route_base}&caregiver_section=overview#cg-overview"><span>&#8962;</span>Overview</a>
                    <a target="_self" href="{route_base}&caregiver_section=profile#cg-profile"><span>&#128101;</span>My Loved Ones</a>
                    <a target="_self" href="{route_base}&caregiver_action=alerts&caregiver_section=alerts#cg-alerts"><span>&#128276;</span>Alerts</a>
                    <a target="_self" href="{route_base}&caregiver_action=message&caregiver_section=messages#cg-message"><span>&#128172;</span>Messages</a>
                    <a target="_self" href="{route_base}&caregiver_action=note&caregiver_section=notes#cg-care-notes"><span>&#128221;</span>Care Notes</a>
                    <a target="_self" href="{route_base}&caregiver_section=activity#cg-activity"><span>&#128197;</span>Calendar</a>
                    <a target="_self" href="{route_base}&caregiver_action=full_summary&caregiver_section=summary#cg-action-panel"><span>&#128196;</span>Reports</a>
                    <a target="_self" href="{route_base}&caregiver_section=settings#cg-settings"><span>&#9881;</span>Settings</a>
                </nav>
                <div class="cg-side-card">
                    {_nesto_robot()}
                    <b>{robot_name} is ready</b>
                    <small>&#9679; Online</small>
                </div>
                <a target="_self" class="cg-side-support" href="{route_base}&caregiver_action=message&caregiver_section=messages#cg-message">Contact support</a>
                <a target="_self" class="cg-side-logout" href="?logout=1">Log out</a>
            </aside>
        <main class="cg-page" id="cg-overview">
            <section class="cg-hero">
                <div>
                    <div class="cg-top">
                        <div>
                            <span class="cg-dashboard-kicker">Guardian / Caregiver Dashboard</span>
                            <h1>Good morning, {family_name} <span style="color:#6aa783;">&#9829;</span></h1>
                            <p>Here's how {care_name} is doing today.</p>
                        </div>
                        <div class="cg-actions-top">
                            <a target="_self" class="cg-pill" href="{route_base}&caregiver_action=call&caregiver_section=messages#cg-action-panel">&#128222; Call {care_name}</a>
                            <a target="_self" class="cg-primary-button" href="{route_base}&caregiver_action=message&caregiver_section=messages#cg-message">&#128172; Message Nesto</a>
                            <a target="_self" class="cg-bell" href="{route_base}&caregiver_action=alerts&caregiver_section=alerts#cg-alerts">&#128276;<span>5</span></a>
                            <a target="_self" class="cg-logout" href="?logout=1">Log out</a>
                        </div>
                    </div>
                    <div class="cg-kpis">
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Loved Ones</span><span class="cg-kpi-value">{loved_count}</span><span class="cg-kpi-sub">Linked care profile(s)</span></div>
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Active Alerts</span><span class="cg-kpi-value dark">{active_alert_count}</span><span class="cg-kpi-sub">Needs review</span></div>
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Messages</span><span class="cg-kpi-value">{message_count}</span><span class="cg-kpi-sub">Recent Nesto updates</span></div>
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Care Tasks</span><span class="cg-kpi-value dark">{care_task_count}</span><span class="cg-kpi-sub">Today</span></div>
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Wellbeing Score</span><span class="cg-kpi-value">{escape(str(score))}</span><span class="cg-kpi-sub">Good</span><div class="spark"></div></div>
                        <div class="cg-card cg-kpi-card"><span class="cg-kpi-label">Robot Status</span><span class="cg-kpi-value dark">{robot_status_label}</span><span class="cg-kpi-sub">{robot_status_sub}</span></div>
                    </div>
                    {linked_loved_html}
                </div>
                <aside class="cg-robot-card nesto-robot-card nesto-robot-illustration" aria-label="Nesto status">
                    {_nesto_robot()}
                    <b>Nesto is monitoring gently. &#9829;</b>
                    <span>Status only</span>
                </aside>
            </section>
            {detail_html}
            {action_panel_html}
            <section class="cg-grid">
                <div class="cg-card" id="cg-loved-ones">
                    <h3 class="cg-section-title">My Loved Ones</h3>
                    <div class="cg-profile-list">
                        <div><b>{care_name}</b><span>{patient_full}</span></div>
                        <div><b>Mood</b><span>{escape(str(mood))}</span></div>
                        <div><b>Medicine</b><span>{escape(str(medicine))} on track</span></div>
                        <div><b>Robot</b><span>{escape(robot_status_label)} - {escape(robot_status_sub)}</span></div>
                    </div>
                </div>
                <div class="cg-card" id="cg-alerts">
                    <h3 class="cg-section-title">Latest Alerts</h3>
                    {''.join(alert_html)}
                </div>
                <div class="cg-card" id="cg-reminders">
                    <h3 class="cg-section-title">Upcoming Care Reminders</h3>
                    <div class="cg-profile-list">
                        <div><b>09:00 AM</b><span>Morning medicine reminder</span></div>
                        <div><b>10:00 AM</b><span>Walk reminder</span></div>
                        <div><b>12:30 PM</b><span>Lunch check-in</span></div>
                        <div><b>Today</b><span>{care_name} is doing well. No critical alerts.</span></div>
                    </div>
                </div>
            </section>
            <section class="cg-card cg-quick" id="cg-actions">
                <h3 class="cg-section-title">Send a quick action</h3>
                <div class="cg-quick-row">
                    <a target="_self" class="cg-quick-button" href="{route_base}&caregiver_action=acknowledge&caregiver_section=overview#cg-action-panel">&#10003; Acknowledge update</a>
                    <a target="_self" class="cg-quick-button" href="{route_base}&caregiver_action=medicine&caregiver_section=messages#cg-action-panel">&#128138; Remind medicine</a>
                    <a target="_self" class="cg-quick-button" href="{route_base}&caregiver_action=call&caregiver_section=messages#cg-action-panel">&#128222; Call {care_name}</a>
                    <a target="_self" class="cg-quick-button" href="{route_base}&caregiver_action=alerts&caregiver_section=alerts#cg-alerts">&#9825; Review alerts</a>
                    <a target="_self" class="cg-quick-button" href="{route_base}&caregiver_action=note&caregiver_section=notes#cg-care-notes">&#9998; Add care note</a>
                </div>
            </section>
            <section class="cg-bottom-grid">
                <div class="cg-card cg-message-panel" id="cg-message">
                    <div class="cg-message-head">
                        <div class="cg-mini-robot" aria-hidden="true"><span></span></div>
                        <div>
                            <h3 class="cg-section-title" style="margin-bottom:4px;">Message Nesto</h3>
                            <p style="margin:0;color:#61716d;font-weight:700;">Ask Nesto for a care update or leave a note.</p>
                        </div>
                    </div>
                    <div class="cg-feedback"><b>Nesto response</b><span>{nesto_response}</span></div>
                    <div class="cg-prompt-row">
                        <a target="_self" href="{route_base}&caregiver_action=message&caregiver_section=messages&cg_prompt=how_today#cg-message">How is {care_name} today?</a>
                        <a target="_self" href="{route_base}&caregiver_action=message&caregiver_section=messages&cg_prompt=medicine#cg-message">Show latest medicine update.</a>
                        <a target="_self" href="{route_base}&caregiver_action=message&caregiver_section=messages&cg_prompt=alerts#cg-message">Any alerts today?</a>
                        <a target="_self" href="{route_base}&caregiver_action=message&caregiver_section=messages&cg_prompt=activity#cg-message">Summarize recent activity.</a>
                    </div>
                    <form class="cg-note-form" method="get" action="">
                        <input type="hidden" name="nav_role" value="Caregiver">
                        <input type="hidden" name="nav_page" value="Guardian / Caregiver Dashboard">
                        <input type="hidden" name="guardian_id" value="{guardian_id}">
                        <input type="hidden" name="patient_id" value="{patient_id}">
                        <input type="hidden" name="caregiver_action" value="message">
                        <input type="hidden" name="caregiver_section" value="messages">
                        <input name="cg_message_text" placeholder="Example: Please send me a quick care update." aria-label="Message to Nesto">
                        <button type="submit">Send message</button>
                    </form>
                </div>
                <div class="cg-card cg-note-panel" id="cg-care-notes">
                    <h3 class="cg-section-title">Care Notes</h3>
                    {note_feedback_html}
                    <form class="cg-note-form" method="get" action="">
                        <input type="hidden" name="nav_role" value="Caregiver">
                        <input type="hidden" name="nav_page" value="Guardian / Caregiver Dashboard">
                        <input type="hidden" name="guardian_id" value="{guardian_id}">
                        <input type="hidden" name="patient_id" value="{patient_id}">
                        <input type="hidden" name="caregiver_action" value="note">
                        <input type="hidden" name="caregiver_section" value="notes">
                        <textarea name="care_note_text" placeholder="Example: {care_name} was calm after lunch." aria-label="Care note"></textarea>
                        <button type="submit">Save care note</button>
                    </form>
                    {note_rows}
                </div>
                <div class="cg-card cg-settings-panel" id="cg-system-status">
                    <h3 class="cg-section-title">System Status</h3>
                    <div class="cg-profile-list">
                        <div><b>Nesto</b><span>{escape(robot_status_label)}</span></div>
                        <div><b>Battery</b><span>{battery}%</span></div>
                        <div><b>Care profile</b><span>Linked to {family_name}</span></div>
                        <div><b>Updates</b><span>Dashboard data refreshed from Nesto records.</span></div>
                    </div>
                </div>
            </section>
            <section class="cg-bottom-grid" style="margin-top:16px;">
                <div class="cg-card cg-profile-panel" id="cg-profile">
                    <h3 class="cg-section-title">Elderly Profile</h3>
                    <div class="cg-profile-list">
                        <div><b>Elderly user</b><span>{patient_full}</span></div>
                        <div><b>Guardian / Caregiver</b><span>{family_full} · {relationship}</span></div>
                        <div><b>Phone number</b><span>{phone}</span></div>
                        <div><b>Robot name</b><span>{robot_name}</span></div>
                    </div>
                </div>
                <div class="cg-card cg-settings-panel" id="cg-settings">
                    <h3 class="cg-section-title">Settings</h3>
                    <p style="color:#61716d;font-weight:700;line-height:1.55;margin:0;">Caregiver settings will let the family choose alert preferences, contact methods, and summary frequency. For now, this section keeps the dashboard route ready without showing provider-only details.</p>
                    <a target="_self" class="cg-secondary-button" style="margin-top:14px;" href="{route_base}&caregiver_section=profile#cg-profile">Review profile</a>
                </div>
            </section>
        </main>
        </div>
        """
    )




def _talk_to_nesto_scenario(command):
    text = str(command or "").strip().lower()
    quick_requests = {
        "can you find my cane?": ("find_cane", "Nesto will help you look for your cane."),
        "did i take my medicine today?": ("medicine_status_check", "Let me check your medicine reminder."),
        "call my caregiver.": ("call_caregiver", "I'll prepare a caregiver call."),
        "i need help.": ("emergency_request", "I'll prepare an urgent support alert for your Guardian / Caregiver."),
    }
    if text in quick_requests:
        return quick_requests[text]
    return "talk_to_nesto", "Nesto heard your request. I will stay with you and help in simple steps."


def _handle_talk_to_nesto_command(command, typed=False):
    clean_command = str(command or "").strip() or "Talk to Nesto"
    if typed:
        scenario_type = "talk_to_nesto"
        response = "Nesto heard your request. I will stay with you and help in simple steps."
    else:
        scenario_type, response = _talk_to_nesto_scenario(clean_command)
    st.session_state["talk_to_nesto_command"] = clean_command
    st.session_state["talk_to_nesto_response"] = response
    st.session_state["talk_to_nesto_listening"] = False
    st.session_state["talk_to_nesto_scenario"] = scenario_type
    _record_patient_action(
        f"Talk to Nesto request: {clean_command}",
        payload={"prepared_scenario_type": scenario_type},
    )


def _scenario_for_text(text):
    lowered = str(text or "").lower()
    if "talk to nesto request" in lowered:
        command_text = lowered.split("talk to nesto request:", 1)[-1].strip()
        scenario_type, _response = _talk_to_nesto_scenario(command_text)
        event_type = "conversation_event"
        if scenario_type in {"find_cane", "find_medicine", "call_caregiver"}:
            event_type = "scenario_event"
        if scenario_type == "medicine_status_check":
            event_type = "medicine_event"
        if scenario_type == "emergency_request":
            event_type = "alert"
        return (event_type, scenario_type, "requested")
    if "medicine" in lowered and ("taken" in lowered or "acknowledged" in lowered):
        return ("medicine_event", "take_medicine", "taken")
    if "medicine" in lowered and ("status" in lowered or "today" in lowered or "did i take" in lowered):
        return ("medicine_event", "medicine_status_check", "requested")
    if "medicine" in lowered and ("find" in lowered or "object" in lowered):
        return ("scenario_event", "find_medicine", "requested")
    if "cane" in lowered or "object" in lowered or "finder" in lowered:
        return ("scenario_event", "find_cane", "requested")
    if "call" in lowered:
        return ("scenario_event", "call_caregiver", "requested")
    if "emergency" in lowered or "urgent" in lowered or "alert" in lowered:
        return ("alert", "emergency_request", "high")
    if "feel" in lowered or "mood" in lowered or "worried" in lowered or "tired" in lowered:
        return ("mood_event", "mood_check", "recorded")
    if "summon" in lowered or "come here" in lowered:
        return ("scenario_event", "summon_robot", "requested")
    if "caregiver note" in lowered or "saved a caregiver note" in lowered:
        return ("caregiver_note_saved", "caregiver_note_saved", "saved")
    if "talk" in lowered or "nesto" in lowered:
        return ("conversation_event", "talk_to_nesto", "recorded")
    return ("scenario_event", "dashboard_action", "recorded")


def _record_patient_action(text, role="elderly_user", source_page="Elderly User Interface", payload=None):
    st.session_state.setdefault("carebot_actions", []).append(
        {"text": text, "time": dt.datetime.now().strftime("%H:%M")}
    )
    payload = payload or {}
    event_type, scenario_type, status = _scenario_for_text(text)
    prepared_scenario = payload.get("prepared_scenario_type")
    if prepared_scenario:
        scenario_type = prepared_scenario
        event_type = "conversation_event"
        if prepared_scenario in {"find_cane", "find_medicine", "call_caregiver"}:
            event_type = "scenario_event"
        elif prepared_scenario == "medicine_status_check":
            event_type = "medicine_event"
        elif prepared_scenario == "emergency_request":
            event_type = "alert"
    record_dashboard_event(
        event_type=event_type,
        scenario_type=scenario_type,
        role=role,
        status=status,
        source_page=source_page,
        payload={"message": text, **payload},
    )


def _set_elderly_action(action, text):
    st.session_state["elderly_action"] = action
    _record_patient_action(text)
    st.toast(ELDERLY_ACTIONS[action]["title"])
    st.rerun()


def _query_action():
    return _query_param("nesto_action")


def _query_param(name):
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _clear_query_params(*names):
    try:
        for name in names:
            if name in st.query_params:
                del st.query_params[name]
    except Exception:
        return

def _initial(name):
    text = str(name or "").strip()
    return escape(text[:1].upper() or "N")


def _render_html(html):
    cleaned = str(html or "").strip()
    if not cleaned:
        return
    cleaned = " ".join(line.strip() for line in cleaned.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)

def _action_hub(selected_action=None):
    cards = []
    for action in ACTION_ORDER:
        info = ELDERLY_ACTIONS[action]
        active = " active" if selected_action == action else ""
        tone = " emergency" if action == "emergency" else ""
        cards.append(
            f"""
            <a class="care-action-card{active}{tone}" href="?nav_role=Elderly%20user&nav_page=Elderly%20User%20Interface&nesto_action={action}#nesto-action-panel">
                <div class="care-action-icon">{info["icon"]}</div>
                <div>
                    <b>{info["title"]}</b>
                    <span>{info["short"]}</span>
                </div>
            </a>
            """
        )
    return f"""
    <div class="care-action-hub">
        <div class="care-action-intro">
            <span class="goal-label">What do you need?</span>
            <h3>Tap a picture. Nesto will guide the next step.</h3>
            <p>Designed for an elderly user: large icons, simple words, and friendly feedback. Every action stays within the approved care scenarios.</p>
        </div>
        <div class="care-action-grid">
            {''.join(cards)}
        </div>
    </div>
    """


def _caregiver_action_hub(selected_action=None):
    cards = []
    for action in CAREGIVER_ACTION_ORDER:
        info = CAREGIVER_ACTIONS[action]
        active = " active" if selected_action == action else ""
        cards.append(
            f"""
            <a class="family-action-card{active}" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action={action}#caregiver-action-panel">
                <div class="family-action-icon">{info["icon"]}</div>
                <div>
                    <b>{info["title"]}</b>
                    <span>{info["short"]}</span>
                </div>
            </a>
            """
        )
    return f"""
    <div class="family-action-hub">
        <div>
            <span class="goal-label">What can the caregiver do?</span>
            <h3>Quick family actions</h3>
            <p>Simple caregiver controls with clear visual cues, so the family can understand {patient()}'s situation at a glance.</p>
        </div>
        <div class="family-action-grid">
            {''.join(cards)}
        </div>
    </div>
    """


def _caregiver_action_panel(action):
    details = CAREGIVER_ACTIONS.get(action, CAREGIVER_ACTIONS["summary"])
    _render_html(
        f"""
        <div id="caregiver-action-panel" class="action-panel">
            <div class="action-panel-main">
                <span class="goal-label">Caregiver action</span>
                <h3>{details["icon"]} {details["title"]}</h3>
                <p>{details["result"]}</p>
            </div>
            <div class="action-panel-side">
                <b>Why it matters</b>
                <span>{details["short"]}</span>
            </div>
        </div>
        """
    )

    if action == "summary":
        c1, c2 = st.columns(2)
        if c1.button("Mark update reviewed", use_container_width=True):
            _record_patient_action(f"{caregiver()} acknowledged the latest update.", role="caregiver", source_page="Guardian / Caregiver Dashboard")
            st.success("Update reviewed.")
        if c2.button("Open wellbeing monitor", use_container_width=True):
            _navigate_to("Admin / team", "Admin / Provider / NESTO Team Dashboard", "Wellbeing Monitor opened", "Review wellbeing rings, reminders, activity, and care notes.")
            st.rerun()
    elif action == "call":
        c1, c2 = st.columns(2)
        if c1.button(f"Start call with {patient()}", use_container_width=True):
            _record_patient_action(f"{caregiver()} started a call with {patient()}.", role="caregiver", source_page="Guardian / Caregiver Dashboard")
            st.success(f"Calling {patient()}.")
        if c2.button("Send reassurance note", use_container_width=True):
            _record_patient_action(f"{caregiver()} sent reassurance to {patient()}.", role="caregiver", source_page="Guardian / Caregiver Dashboard")
            st.info("Nesto will show a calm reassurance message.")
    elif action == "message":
        with st.form("caregiver_message_form", clear_on_submit=True):
            message = st.text_input("Message to Nesto", placeholder=f"Example: Please remind {patient()} about the afternoon walk.")
            sent = st.form_submit_button("Send message")
        if sent and message.strip():
            _record_patient_action(f"{caregiver()} messaged Nesto: {message.strip()}", role="caregiver", source_page="Guardian / Caregiver Dashboard", payload={"message_to_nesto": message.strip()})
            st.success("Message sent to Nesto.")
    elif action == "alerts":
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Care alerts</p>
                <div class="row"><span class="activity-icon">&#128694;</span><div><div class="row-main">Low activity detected</div><div class="row-sub">Review today's movement and check in if needed.</div></div>{badge("Low","amber")}</div>
                <div class="row"><span class="activity-icon">&#128274;</span><div><div class="row-main">Medication missed</div><div class="row-sub">Follow up if the afternoon reminder is not acknowledged.</div></div>{badge("Medium","amber")}</div>
                <div class="row"><span class="activity-icon">&#10084;</span><div><div class="row-main">Unusual heart rate</div><div class="row-sub">Monitoring indicator only, not diagnosis.</div></div>{badge("High","red")}</div>
            </div>
            """
        )


def _elderly_action_panel(action):
    details = ELDERLY_ACTIONS.get(action, ELDERLY_ACTIONS["schedule"])
    _render_html(
        f"""
        <div id="nesto-action-panel" class="action-panel">
            <div class="action-panel-main">
                <span class="goal-label">Selected action</span>
                <h3>{details["title"]}</h3>
                <p>{details["goal"]}</p>
            </div>
            <div class="action-panel-side">
                <b>{_robot_name()} says</b>
                <span>{details["speech"]}</span>
            </div>
        </div>
        """
    )

    if action == "schedule":
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Today's gentle plan</p>
                <div class="row"><span class="time">08:00</span><span class="row-main">Breakfast</span>{badge("Done","green")}</div>
                <div class="row"><span class="time">09:00</span><span class="row-main">Morning medication</span>{badge("Done","green")}</div>
                <div class="row"><span class="time">12:00</span><span class="row-main">Lunch check-in</span>{badge("Next","purple")}</div>
                <div class="row"><span class="time">16:00</span><span class="row-main">Afternoon walk</span>{badge("Later","amber")}</div>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        if c1.button("Mark lunch check-in done", use_container_width=True):
            _record_patient_action(f"{patient()} completed lunch check-in.")
            st.success(f"Nice. Nesto will show {caregiver()} that lunch check-in is complete.")
        if c2.button("Ask about afternoon walk", use_container_width=True):
            _record_patient_action(f"{patient()} asked about the afternoon walk.")
            st.info("{_robot_name()} says: Your walk is planned for 4:00 PM. We can keep it gentle.")

    elif action == "medication":
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Medication reminder</p>
                <div class="row"><span class="row-main">Morning medication</span>{badge("Taken","green")}</div>
                <div class="row"><span class="row-main">Afternoon reminder</span>{badge("Upcoming","purple")}</div>
                <p class="muted">Nesto can remind {patient()} and record whether the reminder was acknowledged. It does not give dosage advice.</p>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        if c1.button("Mark reminder acknowledged", use_container_width=True):
            _record_patient_action(f"{patient()} acknowledged a medication reminder.")
            st.success("Medication reminder acknowledged.")
        if c2.button(f"Notify {caregiver()}", use_container_width=True):
            _record_patient_action(f"{caregiver()} was notified about a medication reminder.")
            st.info(f"{caregiver()} will see this in the family companion app.")

    elif action == "call":
        _render_html(
            f"""
            <div class="card">
                <p class="section-title">Family connection</p>
                <div class="row"><span class="row-main">{caregiver()}</span>{badge("Primary caregiver","green")}</div>
                <div class="row"><span class="row-main">Reason</span><span class="row-sub">{patient()} wants reassurance or family support</span></div>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        if c1.button(f"Start call with {caregiver()}", use_container_width=True):
            _record_patient_action(f"Call started with {caregiver()}.")
            st.success(f"Nesto is calling {caregiver()}.")
        if c2.button("Open family companion view", use_container_width=True):
            _navigate_to("Caregiver", "Guardian / Caregiver Dashboard", "Family companion view opened", f"{caregiver()} can review {patient()}'s summary, reminders, and Nesto messages.")
            st.rerun()

    elif action == "chat":
        with st.form("elderly_chat_form", clear_on_submit=True):
            request = st.text_input("Ask Nesto", placeholder="Example: Can you help me find my cane?")
            sent = st.form_submit_button("Send to Nesto")
        if sent and request.strip():
            text = request.strip()
            route = "Find important object" if "cane" in text.lower() or "find" in text.lower() else "General support"
            _record_patient_action(f"{patient()} asked: {text}")
            st.success(f"Nesto received the request and matched it to: {route}.")
        c1, c2 = st.columns(2)
        if c1.button("Start object finder", use_container_width=True):
            _record_patient_action(f"{patient()} asked Nesto to find an important item.")
            st.info("{_robot_name()} says: I will start the approved object-finder scenario.")
        if c2.button("Open admin chat monitor", use_container_width=True):
            _navigate_to("Admin / team", "Admin / Provider / NESTO Team Dashboard", "Chat Monitor opened", "The provider team can review Nesto requests and approved actions.")
            st.rerun()

    elif action == "mood":
        _render_html('<div class="card"><p class="section-title">How are you feeling?</p><p class="muted">This is a simple wellbeing check-in, not a medical assessment.</p></div>')
        c1, c2, c3, c4 = st.columns(4)
        mood_buttons = [(c1, "Great", f"{patient()} feels great."), (c2, "Okay", f"{patient()} feels okay."), (c3, "Tired", f"{patient()} feels tired."), (c4, "Worried", f"{patient()} feels worried.")]
        for col, label, message in mood_buttons:
            if col.button(label, use_container_width=True):
                _record_patient_action(message)
                st.success(f"Thanks. Nesto recorded: {label}.")

    elif action == "emergency":
        _render_html(
            f"""
            <div class="card" style="border-color:#f7caca;background:#fff7f7;">
                <p class="section-title" style="color:{RED};">Urgent support</p>
                <p class="muted">Nesto can alert family contacts in the care flow. For a real emergency, call local emergency services.</p>
                <div class="row"><span class="row-main">Primary contact</span>{badge(caregiver(),"red")}</div>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        if c1.button(f"Alert {caregiver()}", type="primary", use_container_width=True):
            _record_patient_action(f"Emergency alert prepared for {caregiver()}.")
            st.error(f"Urgent alert prepared for {caregiver()}.")
        if c2.button("Open provider dashboard", use_container_width=True):
            _navigate_to("Admin / team", "Admin / Provider / NESTO Team Dashboard", "Provider dashboard opened", "The team can review care records, robot status, and live activity.")
            st.rerun()


def _record_direct_scenario(action, label):
    event_map = {
        "find_cane": ("scenario_event", "find_cane", "requested"),
        "find_medicine": ("scenario_event", "find_medicine", "requested"),
        "summon": ("scenario_event", "summon_robot", "requested"),
        "chat": ("scenario_event", "talk_to_nesto", "requested"),
    }
    event_type, scenario_type, status = event_map.get(action, ("scenario_event", action, "requested"))
    record_dashboard_event(
        event_type=event_type,
        scenario_type=scenario_type,
        role="elderly_user",
        status=status,
        source_page="Elderly User Interface",
        payload={"action": action, "label": label},
    )


def _navigate_to(role, page_name, title, message):
    st.session_state["pending_role"] = role
    st.session_state["pending_page"] = page_name
    st.session_state["app_notice"] = {"title": title, "message": message}


def _show_patient_actions():
    actions = st.session_state.get("carebot_actions", [])
    if not actions:
        return
    rows = "".join(_activity_row(action) for action in reversed(actions[-5:]))
    _render_html(
        f"""
        <div class="card">
            <p class="section-title">What just happened</p>
            <p class="muted">These friendly care updates can be shown to the family companion app.</p>
            <div class="activity-feed">{rows}</div>
        </div>
        """
    )


def _activity_row(action):
    if isinstance(action, dict):
        text = str(action.get("text", ""))
        time = str(action.get("time", ""))
    else:
        text = str(action)
        time = ""
    lowered = text.lower()
    icon = "&#128172;"
    label = "Nesto message"
    tone = "chat"
    if "schedule" in lowered or "lunch" in lowered or "walk" in lowered:
        icon, label, tone = "&#128197;", "Schedule update", "schedule"
    elif "medication" in lowered or "reminder" in lowered:
        icon, label, tone = "&#128138;", "Medication update", "medicine"
    elif "call" in lowered or "family" in lowered or caregiver().lower() in lowered:
        icon, label, tone = "&#128222;", "Family contact", "call"
    elif "feel" in lowered or "mood" in lowered or "worried" in lowered or "tired" in lowered:
        icon, label, tone = "&#128578;", "Wellbeing check-in", "mood"
    elif "alert" in lowered or "emergency" in lowered or "safety" in lowered:
        icon, label, tone = "&#128737;", "Safety alert", "emergency"
    elif "cane" in lowered or "object" in lowered or "find" in lowered:
        icon, label, tone = "&#128269;", "Object finder", "object"
    detail = f"{label} - {time}" if time else label
    return (
        f'<div class="activity-row {tone}">'
        f'<div class="activity-icon">{icon}</div>'
        f'<div><b>{escape(text)}</b><span>{escape(detail)}</span></div>'
        f'</div>'
    )


def _elderly_feed():
    _render_html(
        f"""
        <div class="fb-feed">
            <div class="fb-post">
                <div class="fb-post-head"><div class="fb-avatar">N</div><div><div class="fb-post-title">Nesto is nearby</div><div class="row-sub">Ready to help with reminders, family calls, and finding important objects.</div></div>{badge("Ready","green")}</div>
                <div class="fb-actions"><span>Talk</span><span>Call family</span><span>Reminder</span></div>
            </div>
        </div>
        """
    )


def _family_feed(metrics):
    _render_html(
        f"""
        <div class="fb-feed">
            <div class="fb-post">
                <div class="fb-post-head"><div class="fb-avatar">R</div><div><div class="fb-post-title">{patient()} is doing well today</div><div class="row-sub">Care score {metrics["score"]}. No active care alerts are currently shown.</div></div>{badge("All good","green")}</div>
                <div class="fb-actions"><span>Message</span><span>Call</span><span>Care note</span></div>
            </div>
            <div class="fb-post">
                <div class="fb-post-head"><div class="fb-avatar">N</div><div><div class="fb-post-title">Nesto activity summary</div><div class="row-sub">{metrics["robot_updates"]} robot updates, {metrics["assistant_messages"]} assistant messages, and {metrics["room_events"]} room/object records are available.</div></div>{badge("Live","purple")}</div>
                <div class="fb-actions"><span>Review</span><span>Share</span><span>Save</span></div>
            </div>
        </div>
        """
    )


def _family_landing_html(metrics, activity):
    robot_messages = _robot_message_rows(activity)
    return f"""
    <section class="family-landing">
        <nav class="family-landing-nav">
            <div class="family-brand">
                <span class="family-brand-icon">&#8962;</span>
                <b>Nesto</b><em>Family</em>
            </div>
            <div class="family-nav-links">
                <a href="#family-overview">Overview</a>
                <a href="#family-features">Features</a>
                <a href="#family-how">How it works</a>
                <a href="#family-security">Security</a>
                <a href="#family-faq">FAQs</a>
            </div>
            <a class="family-download" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard">Open App</a>
        </nav>

        <div id="family-overview" class="family-hero">
            <div class="family-copy">
                <span class="family-pill">For families</span>
                <h1>Stay connected.<br>Stay reassured.</h1>
                <p>Nesto Family helps {caregiver()} stay informed, support {patient()}, and understand what happened at home at a glance.</p>
                <div class="family-benefits">
                    <div><span>&#9825;</span><b>Real-time updates</b><em>Know how your loved one is doing.</em></div>
                    <div><span>&#129302;</span><b>Nesto insights</b><em>Short summaries from approved care events.</em></div>
                    <div><span>&#128101;</span><b>Easy for everyone</b><em>Simple enough for families to use quickly.</em></div>
                </div>
                <div class="family-cta-row">
                    <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard">&#128241; Open family app</a>
                    <a class="secondary" href="#family-features">&#9655; See features</a>
                </div>
                <div class="family-secure-line">&#128274; Secure, consent-first, and built for peace of mind.</div>
            </div>

            <div class="family-phone-showcase">
                <div class="landing-phone">
                    <div class="phone-top"><span>9:41</span><span>&#128276;</span></div>
                    <div class="landing-phone-brand"><span>&#8962;</span><b>Nesto</b></div>
                    <p class="phone-sub">Good morning,</p>
                    <p class="phone-title">{caregiver()} &#127793;</p>
                    <div class="landing-status-card">
                        <span class="status-check">&#10003;</span>
                        <div><b>{patient()} is doing well</b><em>All care indicators are normal</em><small>Updated 8:30 AM</small></div>
                        <span class="patient-photo">&#128117;</span>
                    </div>
                    <div class="landing-summary-card">
                        <div><b>&#10024; AI Daily Summary</b><a>View all</a></div>
                        <p>{patient()} completed the routine, took the medication, and had good activity.</p>
                        <div class="landing-bot-small">{_nesto_robot()}</div>
                    </div>
                    <div class="landing-mini-grid">
                        {_landing_stat("&#10084;", "Heart Rate", "72", "bpm", "Normal")}
                        {_landing_stat("&#127769;", "Sleep", "7h 30m", "", "Good")}
                        {_landing_stat("&#128694;", "Activity", "4,350", "steps", "Today")}
                        {_landing_stat("&#128138;", "Medication", "1 of 2", "", "Taken")}
                    </div>
                    {_family_nav("Home")}
                </div>

                <div class="landing-phone second">
                    <div class="phone-top"><span>&lt;</span><span>&#128197;</span></div>
                    <p class="phone-title">{patient()}'s Health</p>
                    <div class="landing-tabs"><span>Day</span><b>Week</b><span>Month</span><span>Year</span></div>
                    <div class="landing-health-grid">
                        {_landing_health_card("&#10084;", "Heart Rate", "72 bpm avg", "Normal", "green")}
                        {_landing_health_card("&#127769;", "Sleep", "7h 10m avg", "Good", "blue")}
                        {_landing_health_card("&#128694;", "Steps", "4,350 avg", "Daily", "amber")}
                        {_landing_health_card("&#127939;", "Activity", "45 min avg", "Daily", "green")}
                    </div>
                    <div class="landing-list-card">
                        <div><b>Recent Alerts</b><a>View all</a></div>
                        <div class="landing-alert-row"><span>&#128694;</span><b>Low Activity Detected</b><em>Low</em></div>
                        <div class="landing-alert-row"><span>&#128274;</span><b>Medication Missed</b><em>Medium</em></div>
                        <div class="landing-alert-row"><span>&#10084;</span><b>Unusual Heart Rate</b><em>High</em></div>
                    </div>
                    <div class="landing-contact">&#128222; Contact care team</div>
                </div>
            </div>
        </div>

        <div id="family-features" class="family-feature-panel">
            <h2>Everything families need, in one place</h2>
            <div class="family-feature-grid">
                {_family_feature("&#128172;", "Robot messages", "See Nesto messages and updates from home.")}
                {_family_feature("&#128249;", "Video call", "One-tap calls with your loved one.")}
                {_family_feature("&#128276;", "Smart alerts", "Get notified about important events.")}
                {_family_feature("&#128101;", "Care team", "Coordinate with family and clinicians.")}
                {_family_feature("&#128138;", "Medication tracker", "Track preset reminders and status.")}
                {_family_feature("&#128200;", "Health trends", "View history and progress over time.")}
                {_family_feature("&#128197;", "Calendar", "Stay on top of appointments.")}
                {_family_feature("&#128196;", "Reports", "Summaries for family review.")}
            </div>
        </div>

        <div id="family-how" class="family-how-panel">
            <div>
                <span class="family-pill">How it works</span>
                <h2>From home activity to family reassurance</h2>
                <p>Nesto records approved care events, the app turns them into simple updates, and {caregiver()} can respond with a note, call, or alert review.</p>
            </div>
            <div class="family-steps">
                <div><b>1</b><span>Nesto receives a request or care event.</span></div>
                <div><b>2</b><span>The event is saved to the connected care records.</span></div>
                <div><b>3</b><span>Family sees a clear update with time and next action.</span></div>
            </div>
        </div>

        <div id="family-security" class="family-security-strip">
            <div class="security-main"><span>&#128737;</span><b>Your loved one's privacy is our top priority.</b></div>
            <div><span>&#128274;</span><b>Privacy first</b><em>Consent before monitoring.</em></div>
            <div><span>&#128101;</span><b>Family only</b><em>You control who can see updates.</em></div>
            <div><span>&#9989;</span><b>Safety boundary</b><em>No diagnosis or dosage advice.</em></div>
            <div><span>&#8962;</span><b>Home friendly</b><em>Designed for calm daily care.</em></div>
        </div>

        <div id="family-faq" class="family-live-note">
            <b>Connected to the project data:</b> this landing page uses the same care metrics as the family app. Live Nesto records currently show {metrics["robot_updates"]} robot updates, {metrics["assistant_messages"]} care messages, and {metrics["room_events"]} room/object events.
            <div class="family-message-preview">{robot_messages}</div>
        </div>
        <div id="family-actions"></div>
    </section>
    """


def _landing_stat(icon, label, value, unit, state):
    unit_text = f"<small>{unit}</small>" if unit else ""
    return f"""
    <div class="landing-mini-stat">
        <span>{icon}</span><b>{label}</b><strong>{value}</strong>{unit_text}<em>{state}</em>
    </div>
    """


def _landing_health_card(icon, label, value, state, tone):
    return f"""
    <div class="landing-health-card {tone}">
        <span>{icon}</span><b>{label}</b><strong>{value}</strong><em>{state}</em>
        <svg viewBox="0 0 120 34" width="100%" height="34" aria-hidden="true">
            <polyline points="4,26 18,22 31,24 45,15 59,18 73,10 87,14 102,8 116,12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
        </svg>
    </div>
    """


def _family_feature(icon, title, copy):
    return f"""
    <div class="family-feature-card">
        <div>{icon}</div>
        <b>{title}</b>
        <p>{copy}</p>
    </div>
    """


def _family_web_interface(metrics, activity):
    robot_messages = _robot_message_rows(activity)
    return f"""
    <section class="caregiver-summary-stage web">
        <div class="summary-header">
            <div class="summary-brand"><span>&#8962;</span><b>Nesto Guardian / Caregiver</b></div>
            <div class="summary-header-actions">
                <a class="summary-bell" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=alerts#caregiver-action-panel">&#128276;<em>{metrics["alerts"]}</em></a>
                <a class="summary-avatar" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=edit">{_initial(caregiver())}</a>
            </div>
        </div>
        <div class="summary-greeting-row">
            <div>
                <p>Guardian view</p>
                <h2>{patient()}'s care status</h2>
            </div>
            <a class="summary-video-btn" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=call#caregiver-action-panel">&#128222; Call {patient()}</a>
        </div>
        <div class="summary-metric-grid">
            {_summary_metric_tile("&#10084;", "Wellbeing", str(metrics["score"]), "/100", metrics["mood"], "heart")}
            {_summary_metric_tile("&#128138;", "Medicine", metrics["medicine"], "", "Current", "medication")}
            {_summary_metric_tile("&#128694;", "Activity", metrics["activity"], "steps", "Today", "activity")}
            {_summary_metric_tile("&#129302;", "Robot", str(metrics["robot_updates"]), "events", "Live", "sleep")}
        </div>
        <div class="caregiver-live-grid">
            <div class="summary-section-card">
                <div class="summary-card-head"><b>Recent care activity</b><span>MongoDB live records</span></div>
                <div class="family-message-preview">{robot_messages}</div>
            </div>
            <div class="summary-section-card">
                <div class="summary-card-head"><b>Family actions</b><span>simple controls</span></div>
                <div class="summary-quick-grid">
                    <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel"><b>&#10003; Acknowledge</b><span>Mark latest update reviewed.</span></a>
                    <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=message#caregiver-action-panel"><b>&#128172; Message Nesto</b><span>Save a care note.</span></a>
                    <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=alerts#caregiver-action-panel"><b>&#128276; Review alerts</b><span>Check medicine and safety items.</span></a>
                    <a href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=edit"><b>&#128100; Profile</b><span>Update preferences.</span></a>
                </div>
            </div>
        </div>
    </section>
    """


def _family_companion_interface(metrics, activity):
    robot_messages = _robot_message_rows(activity)
    now_label = dt.datetime.now().strftime("%H:%M")
    latest_time = activity[0]["time"] if activity else "8:30 AM"
    return f"""
    <section class="caregiver-summary-stage">
        <div class="caregiver-phone-shell">
            <div class="caregiver-phone">
                <div class="ios-notch"></div>
                <div class="ios-status">
                    <b>{now_label}</b>
                    <span>&#9679;&#9679;&#9679; &#128246; &#9646;</span>
                </div>

                <header class="summary-header">
                    <div class="summary-brand"><span>&#8962;</span><b>Nesto</b></div>
                    <div class="summary-header-actions">
                        <a class="summary-bell" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=alerts#caregiver-action-panel">&#128276;<em>{metrics["alerts"]}</em></a>
                        <a class="summary-avatar" href="?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=edit">{_initial(caregiver())}</a>
                    </div>
                </header>

                <div class="summary-greeting-row">
                    <div>
                        <p>Good morning,</p>
                        <h2>{caregiver()} <span>&#127793;</span></h2>
                    </div>
                    <a class="summary-video-btn" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=call#caregiver-action-panel">&#128249; Video Call</a>
                </div>

                <a class="summary-status-card" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel">
                    <div class="summary-check">&#10003;</div>
                    <div>
                        <b>{patient()} is doing well</b>
                        <span>All vitals are normal</span>
                        <small>Updated: {latest_time}</small>
                    </div>
                    <div class="summary-patient-photo">{_initial(patient())}</div>
                </a>

                <a class="summary-ai-card" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=message#caregiver-action-panel">
                    <div class="summary-card-head"><b>&#10024; AI Daily Summary</b><span>View all</span></div>
                    <p>{patient()} completed the routine, took the morning medication, and had good activity. Nesto will show new messages here when live care records arrive.</p>
                    <small>Generated by Nesto AI - {latest_time}</small>
                    <div class="summary-bot">{_nesto_robot()}</div>
                </a>

                <div class="summary-section-card">
                    <div class="summary-card-head"><b>Today's Overview</b><span>Live care view</span></div>
                    <div class="summary-metric-grid">
                        {_summary_metric_tile("&#10084;", "Heart Rate", "72", "bpm", "Normal", "heart")}
                        {_summary_metric_tile("&#127769;", "Sleep", "7h 30m", "", "Good", "sleep")}
                        {_summary_metric_tile("&#128694;", "Activity", "4,350", "steps", "Today", "activity")}
                        {_summary_metric_tile("&#128138;", "Medication", metrics["medicine"], "", "Taken", "medication")}
                    </div>
                </div>

                <div class="summary-quick-grid">
                    {_summary_quick_link("&#128172;", "Robot Messages", "2", "?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=message#caregiver-action-panel")}
                    {_summary_quick_link("&#128101;", "Care Team", "", "?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=edit")}
                    {_summary_quick_link("&#128200;", "Health Trends", "", "?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel")}
                    {_summary_quick_link("&#129302;", "Devices", "", "?nav_role=Admin%20%2F%20team&nav_page=Robot%20Operations")}
                </div>

                <a class="summary-alert-card" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=alerts#caregiver-action-panel">
                    <div class="summary-card-head"><b>Recent Alerts</b><span>View all</span></div>
                    <div class="summary-alert-row">
                        <span>&#128737;</span>
                        <div><b>Low activity detected</b><small>{patient()} has been less active than usual today.</small></div>
                        <em>9:15 AM &#8250;</em>
                    </div>
                </a>

                <div class="summary-section-card">
                    <div class="summary-card-head"><b>Upcoming</b><a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel">View calendar</a></div>
                    <div class="summary-list-row"><span>&#128197;</span><div><b>Doctor appointment</b><small>May 24, 2024 - 10:00 AM</small></div></div>
                    <div class="summary-list-row"><span>&#129496;</span><div><b>Physiotherapy session</b><small>May 25, 2024 - 2:00 PM</small></div></div>
                </div>

                {_family_nav("Home")}
            </div>
        </div>

        <aside class="caregiver-live-panel">
            <span class="goal-label">Caregiver dashboard summary</span>
            <h3>What the caregiver sees first</h3>
            <p>The family app opens with the most important answer: is {patient()} okay, what did Nesto notice, and what should the caregiver do next?</p>
            <div class="caregiver-live-grid">
                <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel"><b>&#10003; Acknowledge</b><span>Mark the latest update as reviewed.</span></a>
                <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=call#caregiver-action-panel"><b>&#128222; Call {patient()}</b><span>Start a quick family check-in.</span></a>
                <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=message#caregiver-action-panel"><b>&#128172; Message Nesto</b><span>Ask Nesto or save a care note.</span></a>
                <a href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=alerts#caregiver-action-panel"><b>&#128276; Review alerts</b><span>Check activity, medicine, and safety items.</span></a>
            </div>
            <div class="caregiver-live-card">
                <div class="summary-card-head"><b>Latest Nesto messages</b><span>{metrics["assistant_messages"]} records</span></div>
                {robot_messages}
            </div>
            <div class="data-note"><b>Live care records:</b> Nesto messages, robot updates, and room/object activity stay connected when records are available. Health and reminder cards use safe family-facing values until more live records arrive.</div>
        </aside>
    </section>
    """


def _mini_stat(icon, label, value, unit, status, bg):
    unit_text = f"<span class=\"phone-sub\">{unit}</span>" if unit else ""
    return f"""
    <div style="border:1px solid #eadfcd;border-radius:16px;padding:12px;min-height:140px;background:#fff;">
        <div style="width:34px;height:34px;border-radius:50%;background:{bg};display:grid;place-items:center;">{icon}</div>
        <p class="phone-sub" style="margin-top:10px;">{label}</p>
        <div style="font-weight:950;font-size:1.3rem;color:#25413f;">{value}</div>{unit_text}
        <p class="phone-sub" style="color:#6fa7a6;">{status}</p>
    </div>
    """


def _summary_metric_tile(icon, label, value, unit, status, tone):
    unit_text = f"<small>{unit}</small>" if unit else ""
    return f"""
    <a class="summary-metric-tile {tone}" href="?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&caregiver_action=summary#caregiver-action-panel">
        <span>{icon}</span>
        <b>{label}</b>
        <strong>{value}</strong>
        {unit_text}
        <em>{status}</em>
        <svg viewBox="0 0 110 34" aria-hidden="true">
            <polyline points="4,26 17,22 30,25 43,16 56,20 69,11 82,15 96,8 106,12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    </a>
    """


def _summary_quick_link(icon, label, count, href):
    count_html = f'<em>{count}</em>' if count else ""
    return f"""
    <a class="summary-quick-link" href="{href}">
        {count_html}
        <span>{icon}</span>
        <b>{label}</b>
    </a>
    """


def _quick_tile(icon, label, count=None):
    badge_html = f'<span style="position:absolute;right:16px;top:12px;background:#ff453a;color:white;border-radius:999px;padding:2px 7px;font-size:.72rem;font-weight:950;">{count}</span>' if count else ""
    return f"""
    <div style="position:relative;background:#fff;border:1px solid #eadfcd;border-radius:16px;padding:18px 10px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,.05);">
        {badge_html}<div style="font-size:1.45rem;">{icon}</div><div style="font-weight:800;color:#25413f;margin-top:8px;font-size:.82rem;">{label}</div>
    </div>
    """


def _robot_message_rows(activity):
    messages = []
    for item in activity:
        if item["source"] in ("Assistant messages", "Robot updates", "Room and object events"):
            messages.append((item["title"], item["description"], item["time"]))
    if not messages:
        messages = [
            ("Morning exercise", f"{patient()} joined the morning exercise session.", "8:30 AM"),
            ("Mood update", f"{patient()} looked happy today.", "2:15 PM"),
        ]
    rows = ""
    for title, desc, time in messages[:2]:
        rows += (
            f'<div class="row"><span style="font-size:1.45rem;">&#129302;</span>'
            f'<div><div class="row-main">{escape(str(title))}</div><div class="row-sub">{escape(str(desc))}</div></div>'
            f'<span class="time">{escape(str(time))}</span></div>'
        )
    return rows


def _trend_svg():
    return """
    <svg viewBox="0 0 420 180" width="100%" height="180" role="img" aria-label="Heart rate trend">
        <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#7fa98c" stop-opacity=".28"/>
                <stop offset="100%" stop-color="#7fa98c" stop-opacity=".02"/>
            </linearGradient>
        </defs>
        <line x1="44" y1="35" x2="400" y2="35" stroke="#eadfcd"/>
        <line x1="44" y1="75" x2="400" y2="75" stroke="#eadfcd"/>
        <line x1="44" y1="115" x2="400" y2="115" stroke="#eadfcd"/>
        <text x="5" y="39" fill="#6f7d7b" font-size="13">120</text>
        <text x="12" y="79" fill="#6f7d7b" font-size="13">90</text>
        <text x="12" y="119" fill="#6f7d7b" font-size="13">60</text>
        <path d="M44 118 L76 112 L108 98 L142 106 L176 84 L210 88 L244 78 L278 94 L312 72 L346 89 L380 80 L400 86 L400 150 L44 150 Z" fill="url(#trendFill)"/>
        <polyline points="44,118 76,112 108,98 142,106 176,84 210,88 244,78 278,94 312,72 346,89 380,80 400,86" fill="none" stroke="#6fa76a" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="244" cy="78" r="7" fill="#fff" stroke="#6fa76a" stroke-width="4"/>
        <text x="68" y="168" fill="#6f7d7b" font-size="13">Mon</text><text x="125" y="168" fill="#6f7d7b" font-size="13">Tue</text><text x="181" y="168" fill="#6f7d7b" font-size="13">Wed</text><text x="240" y="168" fill="#6f7d7b" font-size="13">Thu</text><text x="300" y="168" fill="#6f7d7b" font-size="13">Fri</text><text x="357" y="168" fill="#6f7d7b" font-size="13">Sat</text>
    </svg>
    """


def _family_nav(active):
    items = ["Home", "Timeline", "Devices", "Alerts", "Profile"]
    cells = ""
    icons = {"Home": "&#8962;", "Timeline": "&#128197;", "Devices": "&#129302;", "Alerts": "&#128276;", "Profile": "&#128100;"}
    for item in items:
        color = "#6fa7a6" if item == active else "#6f7d7b"
        cells += f'<span style="color:{color};"><span style="display:block;font-size:1.25rem;">{icons[item]}</span>{item}</span>'
    return f'<div class="phone-nav">{cells}</div>'


def _robot_interface(selected_action=None):
    active = selected_action if selected_action in ELDERLY_ACTIONS else ""
    speech = ELDERLY_ACTIONS[active]["speech"] if active else "How can I help you today?"
    status = robot_status(use_live=True)

    def card(action, color=""):
        info = ELDERLY_ACTIONS[action]
        active_class = " active" if active == action else ""
        tone = f" {color}" if color else ""
        return (
            f'<a class="care-action-card{tone}{active_class}" href="?nav_role=Elderly%20user&nav_page=Elderly%20User%20Interface&nesto_action={action}#nesto-action-panel">'
            f'<div class="care-action-icon">{info["icon"]}</div>'
            f'<div><b>{info["title"]}</b><span>{info["short"]}</span></div>'
            f'</a>'
        )

    return f"""
    <section class="caregiver-summary-stage web">
        <div>
            <div class="summary-header">
                <div class="summary-brand"><span>&#8962;</span><b>{_robot_name()} Elderly User Interface</b></div>
                <div class="summary-header-actions">
                    <span class="summary-video-btn">&#128246; {'Connected' if status['online'] else 'Offline'}</span>
                </div>
            </div>
            <div class="summary-greeting-row">
                <div>
                    <p>Good morning</p>
                    <h2>{_care_name()}</h2>
                </div>
                <div class="summary-bot">{_nesto_robot()}</div>
            </div>
            <a class="summary-ai-card" href="?nav_role=Elderly%20user&nav_page=Elderly%20User%20Interface&nesto_action=chat#nesto-action-panel">
                <div class="summary-card-head"><b>{_robot_name()} says</b><span>Listen / Push-to-talk ready</span></div>
                <p>{speech}</p>
                <small>Tap Talk to Nesto to start a calm request.</small>
            </a>
            <div class="summary-metric-grid">
                {_summary_metric_tile("&#129302;", "Robot", status["status"], "", status["navigation"], "sleep")}
                {_summary_metric_tile("&#128267;", "Battery", str(status["battery"]), "%", "Current", "activity")}
                {_summary_metric_tile("&#128205;", "Location", status["room"], "", "Live", "heart")}
                {_summary_metric_tile("&#128276;", "Alerts", str(status["alerts"]), "", "Active", "medication")}
            </div>
        </div>
        <div class="summary-section-card">
            <div class="summary-card-head"><b>Simple care actions</b><span>creates MongoDB events</span></div>
            <div class="care-action-grid">
                {card("schedule")}
                {card("medication", "blue")}
                {card("call")}
                {card("chat", "purple")}
                {card("mood", "amber")}
                {card("find_cane", "purple")}
                {card("find_medicine", "blue")}
                {card("summon")}
                {card("emergency", "emergency")}
            </div>
        </div>
    </section>
    """


def _phone_home():
    _render_html(
        f"""
        <div class="phone">
            <div class="nesto-hero">
                <div>
                    <p class="phone-title">Good morning,<br>{patient()}</p>
                    <p class="phone-sub">Nesto is nearby and ready to help</p>
                    <div style="margin-top:10px;"><span class="nesto-note">&#127793; gentle mode on</span></div>
                </div>
                {_nesto_robot()}
            </div>
            <div class="phone-card" style="background:#e9f2ec;">
                <div class="metric-label">Current status</div><div class="metric-value" style="font-size:1.3rem;">Doing well</div><p class="phone-sub">Last updated 8:30 AM</p>
            </div>
            <div class="phone-card"><b>How are you feeling?</b><div style="display:grid;grid-template-columns:repeat(4,1fr);text-align:center;margin-top:14px;font-size:1.6rem;"><span>&#128522;</span><span>&#128578;</span><span>&#128528;</span><span>&#128543;</span></div></div>
            <div class="phone-card"><b>Today's plan</b><div class="row"><span class="time">08:00</span><span class="row-main">Breakfast</span>{badge("Done","green")}</div><div class="row"><span class="time">09:00</span><span class="row-main">Medication</span>{badge("Done","green")}</div><div class="row"><span class="time">12:00</span><span class="row-main">Lunch check-in</span>{badge("Next","purple")}</div></div>
            <div class="phone-nav"><span>Home</span><span>Health</span><span>+</span><span>Chat</span><span>Profile</span></div>
        </div>
        """
    )


def _phone_health():
    _render_html(
        f"""
        <div class="phone">
            <p class="phone-title">Health overview</p>
            <p class="phone-sub">Monitoring indicators only, not diagnosis</p>
            <div class="phone-card"><div class="metric-label">Heart rate</div><div class="metric-value" style="font-size:1.3rem;">72 bpm</div><p class="phone-sub" style="color:{GREEN};">Normal</p></div>
            <div class="phone-card"><div class="metric-label">Sleep</div><div class="metric-value" style="font-size:1.3rem;">7.2 h</div><p class="phone-sub">Good</p></div>
            <div class="phone-card"><b>Medications</b><div class="row"><span class="row-main">Morning medication</span>{badge("Taken","green")}</div><div class="row"><span class="row-main">Afternoon reminder</span>{badge("Upcoming","purple")}</div></div>
            <div class="phone-nav"><span>Home</span><span>Health</span><span>+</span><span>Chat</span><span>Profile</span></div>
        </div>
        """
    )


def _phone_assistant():
    _render_html(
        f"""
        <div class="phone">
            <div class="nesto-hero">
                <div>
                    <p class="phone-title">Nesto chat</p>
                    <p class="phone-sub">Supportive help for daily care tasks</p>
                </div>
                {_nesto_robot()}
            </div>
            <div class="phone-card" style="background:#e9f2ec;">Hi {patient()}. I can help with medication, finding your cane, or contacting {caregiver()}.</div>
            <div class="phone-card" style="background:{BLUE};color:white;margin-left:32px;">Can you help me find my cane?</div>
            <div class="phone-card" style="background:#e9f2ec;">I can help. I will check the living room and tell you where it is.</div>
            <div class="phone-card" style="border-color:#ffd1d1;background:#fff7f7;"><b style="color:{RED};">Emergency</b><p class="phone-sub">Alert family contacts for urgent support.</p></div>
            <div class="phone-nav"><span>Home</span><span>Health</span><span>+</span><span>Chat</span><span>Profile</span></div>
        </div>
        """
    )


def _nesto_robot():
    return """
    <div class="nesto-bot" aria-label="Animated friendly Nesto robot">
        <div class="nesto-shadow"></div>
        <div class="nesto-ear left"></div>
        <div class="nesto-ear right"></div>
        <div class="nesto-head"></div>
        <div class="nesto-face">
            <span class="nesto-eye left"></span>
            <span class="nesto-eye right"></span>
            <span class="nesto-smile"></span>
        </div>
        <div class="nesto-arm left"></div>
        <div class="nesto-arm right"></div>
        <div class="nesto-body"></div>
        <div class="nesto-heart">&#9829;</div>
        <div class="nesto-base"></div>
    </div>
    """
