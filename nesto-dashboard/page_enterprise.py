"""
Admin / Provider / NESTO Team dashboard, operations view, and system health UI.
"""

import datetime as dt
import textwrap
from html import escape

import streamlit as st

from data_layer import (
    care_metrics,
    caregiver,
    memories,
    patient,
    recent_activity,
    robot_status,
    save_memory,
    system_health,
)
from event_contracts import DANIEL_TO_DASHBOARD_EVENT_MAP, EVENT_SCHEMAS, KAFKA_TOPICS, MONGO_COLLECTIONS
from ui_theme import AMBER, BLUE, GREEN, PURPLE, RED, badge, page_header


APPROVED_SCENARIOS = [
    ("Find important object", f"Help {patient()} locate a cane or another important item.", PURPLE),
    ("Medication reminder", "Give a preset reminder and record whether it was acknowledged.", GREEN),
    ("Wellbeing support", "Offer calm support and show the family a wellbeing note.", "#ff7a59"),
    ("Safety check", "Flag inactivity or a safety concern for caregiver review.", AMBER),
    ("General assistant response", "Answer basic support questions without controlling the robot.", "#8a8fa3"),
]

CHAT_QUICK_PROMPTS = [
    ("object", "Find object", "Can you help me find my cane?", "&#128269;", "purple"),
    ("medicine", "Medication", "Please remind me about my medicine.", "&#128138;", "green"),
    ("mood", "Wellbeing", "I feel lonely today and need someone to talk to.", "&#128578;", "amber"),
    ("safety", "Safety", f"I am worried because {patient()} has not moved for a while.", "&#128737;", "red"),
]

PROVIDER_TABS = {
    "overview": ("&#8962;", "Overview", "Review care records, risk, robot status, and team workload in one place."),
    "patients": ("&#128101;", "Patients", "Open the patient list and see who needs attention first."),
    "robot": ("&#129302;", "Robot Fleet", "Check Nesto devices, battery, location, and readiness."),
    "alerts": ("&#128276;", "Alerts", "Review safety, medication, activity, and device alerts."),
    "risk": ("&#10022;", "AI Risk Scores", "See which patients may need follow-up based on care signals."),
    "plans": ("&#128197;", "Care Plans", "Track routines, reminders, wellbeing goals, and care-plan status."),
    "caregivers": ("&#129489;", "Caregivers", "See caregiver assignments and workload."),
    "reports": ("&#128202;", "Reports", "Prepare project evidence, summaries, and live care metrics."),
    "tickets": ("&#128172;", "Support Tickets", "Track app, reminder, device, and family support issues."),
    "organizations": ("&#127970;", "Organizations", "Review care sites, organization settings, and access ownership."),
    "users": ("&#128100;", "Users", "Review admin, caregiver, and family access for the Nesto Care workspace."),
    "integrations": ("&#128279;", "System Health", "Check MongoDB Atlas, Redis/cache, ChromaDB memory, Kafka readiness, and Daniel backend dataflow."),
    "settings": ("&#9881;", "Settings", "Manage safe product settings, consent, and Nesto access."),
}



def admin_overview():
    metrics = care_metrics()
    health = system_health()
    activity = recent_activity(limit=4)

    care_messages = int(metrics.get("assistant_messages") or 0)
    room_events = int(metrics.get("room_events") or 0)
    active_alerts = int(metrics.get("alerts") or 0)
    robot_updates = int(metrics.get("robot_updates") or 0)
    robots_online = 1 if robot_updates else 0
    total_robots = max(robots_online, 1)
    online_pct = round((robots_online / total_robots) * 100) if total_robots else 0

    mongo_connected = health.get("mongo", {}).get("available", False)
    cache_info = health.get("cache", {})
    redis_connected = cache_info.get("available", False)
    kafka_info = health.get("kafka", {})
    chroma_connected = health.get("chroma", {}).get("available", False)

    telemetry_rows = activity[:4] if activity else []

    log_html = ""
    for index, row in enumerate(telemetry_rows[:4], start=1):
        status = row.get("source", "Normal")
        tone = "warn" if str(status).lower() in {"low", "warning", "alert"} else "ok"
        log_html += (
            f'<tr><td>{escape(row.get("time", "09:30:00"))}</td>'
            f'<td>R-{1000 + index}</td><td>{escape(row.get("title", "Robot event"))}</td>'
            f'<td>{escape(row.get("description", "Living Room"))}</td><td><span class="admin-status {tone}">{escape(status)}</span></td></tr>'
        )

    def connected_label(value, label_when_false="Waiting"):
        return '<span class="admin-health ok">Connected</span>' if value else f'<span class="admin-health warn">{label_when_false}</span>'

    _render_html(
        f"""
        <style>
            .admin-page {{
                max-width: 1220px;
                margin: 0 auto;
                color: #102f32;
                padding: 4px 2px 28px;
            }}
            .admin-top {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 18px;
                margin-bottom: 20px;
            }}
            .admin-top h1 {{
                margin: 0 0 6px;
                font-size: clamp(1.55rem, 2.3vw, 2.1rem);
                letter-spacing: 0;
            }}
            .admin-top p {{
                margin: 0;
                color: #65736f;
                font-weight: 650;
            }}
            .admin-date {{
                border: 1px solid #e5ded2;
                border-radius: 12px;
                background: #fff;
                padding: 12px 18px;
                font-weight: 850;
                white-space: nowrap;
            }}
            .admin-kpis {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 14px;
                margin-bottom: 16px;
            }}
            .admin-card {{
                border: 1px solid #e5ded2;
                border-radius: 14px;
                background: rgba(255,255,255,.86);
                box-shadow: 0 12px 28px rgba(40,55,44,.07);
                padding: 18px;
            }}
            .admin-kpi-label {{
                display: block;
                color: #3e5350;
                font-weight: 900;
                font-size: .82rem;
                margin-bottom: 8px;
            }}
            .admin-kpi-value {{
                display: inline-block;
                font-size: 2rem;
                font-weight: 950;
                line-height: 1;
            }}
            .admin-kpi-value.green {{ color: #179461; }}
            .admin-kpi-value.red {{ color: #ef4444; }}
            .admin-kpi-value.blue {{ color: #4f727e; }}
            .admin-kpi-value.purple {{ color: #6fa7a6; }}
            .admin-kpi-sub {{
                display: block;
                color: #65736f;
                margin-top: 9px;
                font-weight: 700;
            }}
            .admin-main-grid {{
                display: grid;
                grid-template-columns: 1.08fr 1.35fr .95fr;
                gap: 16px;
                align-items: stretch;
            }}
            .admin-bottom-grid {{
                display: grid;
                grid-template-columns: 1.45fr 1fr .55fr;
                gap: 16px;
                margin-top: 16px;
                align-items: stretch;
            }}
            .admin-section-title {{
                margin: 0 0 14px;
                font-weight: 950;
                color: #102f32;
            }}
            .admin-donut {{
                width: 172px;
                height: 172px;
                border-radius: 999px;
                margin: 12px auto 16px;
                background: conic-gradient(#29a673 0 83%, #ef4444 83% 95%, #f59e0b 95% 100%);
                display: grid;
                place-items: center;
            }}
            .admin-donut div {{
                width: 98px;
                height: 98px;
                border-radius: 999px;
                background: #fffdf8;
                display: grid;
                place-items: center;
                text-align: center;
                box-shadow: inset 0 0 0 1px #eee6da;
            }}
            .admin-donut b {{
                display: block;
                font-size: 2rem;
                line-height: 1;
            }}
            .admin-donut span {{
                color: #65736f;
                font-size: .78rem;
                font-weight: 800;
            }}
            .admin-legend div {{
                display: grid;
                grid-template-columns: 14px 1fr auto;
                gap: 8px;
                align-items: center;
                margin: 10px 0;
                color: #3e5350;
                font-weight: 750;
            }}
            .admin-dot {{
                width: 10px;
                height: 10px;
                border-radius: 999px;
            }}
            .admin-alert {{
                display: grid;
                grid-template-columns: 38px 1fr auto;
                gap: 12px;
                align-items: center;
                padding: 14px 0;
                border-bottom: 1px solid #eee6da;
            }}
            .admin-alert:last-child {{ border-bottom: 0; }}
            .admin-alert-icon {{
                width: 34px;
                height: 34px;
                border-radius: 10px;
                display: grid;
                place-items: center;
                background: #fff0f0;
                color: #ef4444;
            }}
            .admin-alert b, .ticket-row b {{
                display: block;
                color: #102f32;
            }}
            .admin-alert small, .ticket-row small {{
                display: block;
                margin-top: 3px;
                color: #65736f;
                font-weight: 650;
            }}
            .severity {{
                border-radius: 999px;
                padding: 6px 10px;
                font-size: .76rem;
                font-weight: 950;
            }}
            .severity.high {{ color: #ef4444; background: #fff0f0; }}
            .severity.med {{ color: #b56b00; background: #fff6dd; }}
            .severity.low {{ color: #176b4d; background: #eaf5ee; }}
            .admin-robot-panel {{
                overflow: hidden;
                padding: 0;
            }}
            .admin-robot-top {{
                min-height: 155px;
                display: grid;
                place-items: center;
                background: #f7f4ee;
            }}
            .admin-robot-top .nesto-bot {{
                transform: scale(.82);
                margin: 8px auto;
            }}
            .admin-system {{
                padding: 16px 18px 18px;
                border-top: 1px solid #e5ded2;
            }}
            .admin-system-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin: 12px 0;
                color: #3e5350;
                font-weight: 750;
            }}
            .admin-health {{
                font-weight: 950;
                font-size: .82rem;
            }}
            .admin-health.ok {{ color: #179461; }}
            .admin-health.warn {{ color: #b56b00; }}
            .admin-link {{
                display: block;
                color: #176b4d;
                font-weight: 900;
                text-decoration: none;
                margin-top: 12px;
            }}
            .admin-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: .88rem;
            }}
            .admin-table th {{
                color: #65736f;
                font-weight: 900;
                text-align: left;
                padding: 0 10px 12px 0;
            }}
            .admin-table td {{
                border-top: 1px solid #eee6da;
                padding: 12px 10px 12px 0;
                color: #324a48;
                font-weight: 700;
            }}
            .admin-status {{
                border-radius: 999px;
                padding: 5px 9px;
                font-size: .74rem;
                font-weight: 950;
            }}
            .admin-status.ok {{ color: #176b4d; background: #eaf5ee; }}
            .admin-status.warn {{ color: #b56b00; background: #fff6dd; }}
            .ticket-row {{
                display: grid;
                grid-template-columns: 34px 1fr auto;
                gap: 10px;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid #eee6da;
            }}
            .ticket-row:last-child {{ border-bottom: 0; }}
            .ticket-icon {{
                width: 30px;
                height: 30px;
                border-radius: 9px;
                background: #eef5f1;
                display: grid;
                place-items: center;
            }}
            .admin-bot-small {{
                display: grid;
                place-items: center;
                min-height: 210px;
                overflow: hidden;
            }}
            .admin-bot-small .nesto-bot {{
                transform: scale(.78);
                margin: 8px auto;
            }}
            @media (max-width: 1050px) {{
                .admin-kpis, .admin-main-grid, .admin-bottom-grid {{
                    grid-template-columns: 1fr 1fr;
                }}
            }}
            @media (max-width: 700px) {{
                .admin-top {{
                    flex-direction: column;
                }}
                .admin-kpis, .admin-main-grid, .admin-bottom-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
        <div class="admin-page">
            <div class="admin-top">
                <div>
                    <h1>Nesto Care Operations</h1>
                    <p>Monitor robots, systems, and care delivery in real-time.</p>
                </div>
                <div class="admin-date">May 20 - May 26, 2024 &nbsp; &#128197;</div>
            </div>
            <div class="admin-kpis">
                <div class="admin-card"><span class="admin-kpi-label">Robots Online</span><span class="admin-kpi-value green">{robots_online}</span> <b>/ {total_robots}</b><span class="admin-kpi-sub">{online_pct}% of fleet</span></div>
                <div class="admin-card"><span class="admin-kpi-label">Active Alerts</span><span class="admin-kpi-value red">{active_alerts}</span><span class="admin-kpi-sub">Requires attention</span></div>
                <div class="admin-card"><span class="admin-kpi-label">Care Messages</span><span class="admin-kpi-value blue">{care_messages}</span><span class="admin-kpi-sub">Today</span></div>
                <div class="admin-card"><span class="admin-kpi-label">Room Events</span><span class="admin-kpi-value purple">{room_events}</span><span class="admin-kpi-sub">Active</span></div>
            </div>
            <div class="admin-main-grid">
                <div class="admin-card">
                    <h3 class="admin-section-title">Robot Fleet Status</h3>
                    <div class="admin-donut"><div><b>{robots_online}</b><span>Total Robots</span></div></div>
                    <div class="admin-legend">
                        <div><span class="admin-dot" style="background:#29a673;"></span><span>Online</span><b>198 (83%)</b></div>
                        <div><span class="admin-dot" style="background:#ef4444;"></span><span>Offline</span><b>28 (12%)</b></div>
                        <div><span class="admin-dot" style="background:#f59e0b;"></span><span>Low Battery</span><b>12 (5%)</b></div>
                    </div>
                </div>
                <div class="admin-card">
                    <h3 class="admin-section-title">Recent Alerts</h3>
                    <div class="admin-alert"><span class="admin-alert-icon">&#128205;</span><span><b>High heart rate detected</b><small>Elderly User 01 - 10:30 AM</small></span><span class="severity high">High</span></div>
                    <div class="admin-alert"><span class="admin-alert-icon">&#9888;</span><span><b>Possible fall detected</b><small>Patient 02 - 9:15 AM</small></span><span class="severity high">High</span></div>
                    <div class="admin-alert"><span class="admin-alert-icon">&#128276;</span><span><b>Missed medication reminder</b><small>Patient 03 - 8:45 AM</small></span><span class="severity med">Medium</span></div>
                    <div class="admin-alert"><span class="admin-alert-icon" style="background:#eaf5ee;color:#176b4d;">&#128267;</span><span><b>Low battery</b><small>Device R1058 - 6:30 AM</small></span><span class="severity low">Low</span></div>
                </div>
                <div class="admin-card admin-robot-panel">
                    <div class="admin-robot-top">{_nesto_robot()}</div>
                    <div class="admin-system">
                        <h3 class="admin-section-title">System Status</h3>
                        <div class="admin-system-row"><span>MongoDB</span>{connected_label(mongo_connected)}</div>
                        <div class="admin-system-row"><span>Redis Cache</span>{connected_label(redis_connected, "Local TTL fallback")}</div>
                        <div class="admin-system-row"><span>ChromaDB Memory</span>{connected_label(chroma_connected, "Unavailable")}</div>
                        <div class="admin-system-row"><span>Kafka</span><span class="admin-health warn">{escape(str(kafka_info.get("status", "not_connected")).replace("_", " ").title())}</span></div>
                        <a class="admin-link" href="#">View system logs -></a>
                    </div>
                </div>
            </div>
            <div class="admin-bottom-grid">
                <div class="admin-card">
                    <h3 class="admin-section-title">Latest Telemetry Logs <a class="admin-link" style="float:right;margin:0;" href="#">View all topics</a></h3>
                    <table class="admin-table">
                        <thead><tr><th>Time</th><th>Robot ID</th><th>Event</th><th>Room</th><th>Status</th></tr></thead>
                        <tbody>{log_html}</tbody>
                    </table>
                    <a class="admin-link" style="text-align:right;" href="#">View all logs -></a>
                </div>
                <div class="admin-card">
                    <h3 class="admin-section-title">Support Tickets</h3>
                    <div class="ticket-row"><span class="ticket-icon">&#128274;</span><span><b>Device not responding</b><small>Robot R1058</small></span><span class="severity high">Open</span></div>
                    <div class="ticket-row"><span class="ticket-icon">&#128203;</span><span><b>Medication reminder issue</b><small>Patient 04</small></span><span class="severity med">In Progress</span></div>
                    <div class="ticket-row"><span class="ticket-icon">&#9881;</span><span><b>App login problem</b><small>Caregiver app</small></span><span class="severity low">Resolved</span></div>
                    <a class="admin-link" style="text-align:right;" href="#">View all tickets -></a>
                </div>
                <div class="admin-card admin-bot-small">{_nesto_robot()}</div>
            </div>
        </div>
        """
    )



def robot_dashboard():
    status = robot_status(use_live=True)
    metrics = care_metrics()
    activity = recent_activity(limit=7)
    memory_rows = memories(
        limit=4,
        allowed_types={"profile_customization", "care_note", "caregiver_note", "care_request"},
    )

    page_header(
        "Enterprise admin dashboard",
        "Nesto Robot Station",
        "See where Nesto is, what he is doing, and what action the admin can run next.",
        "Live care records",
    )
    _render_notice()

    _render_html(_robot_station_hero(status, metrics))

    _render_html(_robot_status_tiles(status))

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Start room check", use_container_width=True, key="station_room_check"):
        st.toast(f"Nesto will check the {status['room'].lower()}")
    if c2.button(f"Call {patient()}", use_container_width=True, key="station_call_patient"):
        st.toast(f"Calling {patient()}")
    if c3.button("Open chat workflow", use_container_width=True, key="station_chat"):
        _open_admin_page("Chat Monitor", "Chat Monitor opened", "Route a natural request to one approved Nesto action.")
    if c4.button(f"Alert {caregiver()}", use_container_width=True, key="station_alert_family"):
        st.toast(f"Alert prepared for {caregiver()}")

    left, right = st.columns([1.35, 1])
    with left:
        _render_html(f'<div class="card"><p class="section-title">Recent care activity</p>{_activity_rows(activity)}</div>')
    with right:
        _render_html(f'<div class="card"><p class="section-title">Personalization memory</p>{_memory_rows(memory_rows)}</div>')

    lower_left, lower_right = st.columns(2)
    with lower_left:
        _render_html(
            """
            <div class="card">
                <p class="section-title">Active care features</p>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Object finder</span><span class="badge badge-green">Ready</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Medication reminders</span><span class="badge badge-green">Ready</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Wellbeing check-ins</span><span class="badge badge-green">Ready</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Family alerts</span><span class="badge badge-green">Ready</span></div>
            </div>
            """
        )
    with lower_right:
        _render_html(
            """
            <div class="card">
                <p class="section-title">System health</p>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Sensors</span><span class="badge badge-green">OK</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Camera</span><span class="badge badge-green">OK</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Microphone</span><span class="badge badge-green">OK</span></div>
                <div class="row"><span class="dot" style="background:#10b981;"></span><span class="row-main">Care records</span><span class="badge badge-green">Connected</span></div>
            </div>
            """
        )


def ai_scenario_chat():
    activity = recent_activity(limit=8)
    page_header(
        "Enterprise admin dashboard",
        "Chat Monitor",
        "Choose a request, review Nesto's approved decision, then run the next care action.",
        "Admin access",
    )
    _render_notice()

    _render_html(_admin_chat_workflow())

    prompt_cols = st.columns(len(CHAT_QUICK_PROMPTS))
    for col, (_, label, prompt, _, _) in zip(prompt_cols, CHAT_QUICK_PROMPTS):
        if col.button(label, use_container_width=True):
            _submit_chat_request(prompt)

    with st.form("chat_monitor_form", clear_on_submit=True):
        user_text = st.text_input("Type a request for Nesto", placeholder="Example: Can you help me find my cane?")
        sent = st.form_submit_button("Send request")
    if sent and user_text.strip():
        _submit_chat_request(user_text.strip())

    _render_html(_chat_shell(activity))

    preview_text = st.session_state.get("last_chat_text") or st.session_state.get("chat_monitor_messages", [{}])[-1].get("text", "")
    route = _route_for(preview_text)
    _render_html(_decision_command_panel(route, preview_text))

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Run approved action", use_container_width=True):
        _record_chat_admin_action(route, preview_text)
        st.success(f"Nesto action prepared: {route['action']}")
    if c2.button("Open robot view", use_container_width=True):
        _open_admin_page("Robot Operations", "Robot Operations opened", "Check whether Nesto status and recent activity reflect the selected action.")
    if c3.button("Open family view", use_container_width=True):
        _open_role("Caregiver", "Health & Care", "Family Companion App opened", f"Review how {caregiver()} sees this care update.")
    if c4.button("Save to memory", use_container_width=True):
        _save_chat_memory(preview_text)

    left, right = st.columns([1.05, 1])
    with left:
        _render_html(f'<div class="card"><p class="section-title">Approved Nesto actions</p>{_scenario_rows(route["need"])}</div>')
    with right:
        _render_html(_admin_chat_action_log())


def care_activity_monitor():
    metrics = care_metrics()
    activity = recent_activity(limit=10)

    page_header(
        "Enterprise admin dashboard",
        "Wellbeing Monitor",
        "Apple Watch and Fitbit-style monitoring for wellbeing, movement, reminders, and alerts.",
        "Care insights",
    )
    _render_notice()

    _render_html(
        f"""
        <div class="watch-grid">
            <div class="watch-face">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:.78rem;color:#94a3b8;font-weight:900;text-transform:uppercase;letter-spacing:.08em;">Today</div>
                        <div style="font-size:1.35rem;font-weight:950;">{patient()} is doing well</div>
                    </div>
                    <div style="font-weight:900;color:#10b981;">Healthy</div>
                </div>
                <div class="ring-wrap">
                    <div class="ring"><div class="ring-inner"><div><div class="ring-score">{metrics["score"]}</div><div style="color:#94a3b8;font-weight:800;">care score</div></div></div></div>
                </div>
                <div class="watch-list">
                    <div class="watch-item"><span>Movement</span><b>{metrics["activity"]} steps</b></div>
                    <div class="watch-item"><span>Sleep</span><b>{metrics["sleep"]}</b></div>
                    <div class="watch-item"><span>Medication</span><b>{metrics["medicine"]}</b></div>
                    <div class="watch-item"><span>Mood</span><b>{metrics["mood"]}</b></div>
                </div>
            </div>
            <div>
                <div class="wellness-grid">
                    <div class="wellness-card"><div class="metric-label">Heart rate</div><div class="metric-value">72 bpm</div><p class="muted">normal range</p><div class="mini-bars"><span style="height:34%;"></span><span style="height:42%;"></span><span style="height:38%;"></span><span style="height:53%;"></span><span style="height:45%;"></span></div></div>
                    <div class="wellness-card"><div class="metric-label">Movement</div><div class="metric-value">{metrics["activity"]}</div><p class="muted">steps today</p><div class="mini-bars"><span style="height:24%;"></span><span style="height:36%;"></span><span style="height:48%;"></span><span style="height:62%;"></span><span style="height:56%;"></span></div></div>
                    <div class="wellness-card"><div class="metric-label">Sleep</div><div class="metric-value">{metrics["sleep"]}</div><p class="muted">last night</p><div class="mini-bars"><span style="height:50%;"></span><span style="height:56%;"></span><span style="height:42%;"></span><span style="height:66%;"></span><span style="height:60%;"></span></div></div>
                </div>
                <div class="card" style="margin-top:16px;">
                    <p class="section-title">Care rings</p>
                    <div class="row"><span class="row-main">Medication routine</span>{badge("On track","green")}</div>
                    <div class="row"><span class="row-main">Wellbeing check-ins</span>{badge("Good","green")}</div>
                    <div class="row"><span class="row-main">Object finder support</span>{badge("Available","purple")}</div>
                    <div class="row"><span class="row-main">Family alert readiness</span>{badge("Ready","amber")}</div>
                </div>
            </div>
        </div>
        """
    )

    _render_html(f'<div class="card"><p class="section-title">Recent wellbeing timeline</p>{_activity_rows(activity)}</div>')

    _render_html('<div class="card"><p class="section-title">Add a caregiver note</p><p class="muted">Saved notes help Nesto personalize reminders and support.</p></div>')
    with st.form("wellbeing_note_form", clear_on_submit=True):
        note = st.text_area("Care note", placeholder=f"Example: {patient()} prefers reminders in a calm voice after lunch.")
        note_saved = st.form_submit_button("Save care note")
    if note_saved:
        text = note.strip()
        if not text:
            st.warning("Please type a care note first.")
        else:
            now = dt.datetime.now()
            metadata = {
                "type": "care_note",
                "patient": patient(),
                "created": now.isoformat(timespec="seconds"),
                "display_time": now.strftime("%H:%M"),
                "display_date": now.strftime("%d %b %Y"),
            }
            if save_memory(text, metadata):
                st.success(f"Care note saved at {now.strftime('%H:%M')}.")
            else:
                st.warning("The note could not be saved to memory.")

    memory_rows = memories(limit=6, allowed_types={"care_note", "caregiver_note", "care_request"})
    _render_html(f'<div class="card"><p class="section-title">Saved care notes</p>{_memory_rows(memory_rows)}</div>')


def _provider_dashboard(metrics, status, activity, active_tab="overview"):
    _, active_title, active_copy = PROVIDER_TABS.get(active_tab, PROVIDER_TABS["overview"])
    live_activity = _provider_activity_rows(activity)
    live_note = (
        f"Live project records: {metrics['robot_updates']} robot updates, "
        f"{metrics['assistant_messages']} care messages, {metrics['room_events']} room events."
    )
    nav_items = _provider_nav_items(active_tab)
    online_badge = "Online" if status["online"] else "Offline"

    def count_value(*values, fallback=0):
        for value in values:
            try:
                number = int(value or 0)
            except (TypeError, ValueError):
                continue
            if number:
                return number
        return fallback

    provider_patients = count_value(metrics.get("connected_profiles"), metrics.get("patients"), fallback=1)
    provider_devices = count_value(metrics.get("active_devices"), metrics.get("nesto_units"), metrics.get("robot_updates"), fallback=0)
    provider_alerts = count_value(metrics.get("active_alerts"), metrics.get("alerts"), status.get("alerts"), fallback=0)
    provider_caregivers = count_value(metrics.get("caregivers"), fallback=1)

    return f"""
        <div id="provider-dashboard" class="provider-shell">
            <aside class="provider-navrail">
                <div class="provider-brand">
                    <a class="provider-logo" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=overview#provider-dashboard">&#8962;</a>
                    <div><b>Nesto Care</b><span>Provider workspace</span></div>
                </div>
                {nav_items}
                <div class="provider-nesto-promo">
                    {_nesto_robot()}
                    <b>Nesto AI</b>
                    <span>Care. Connect. Empower.</span>
                    <a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=robot#provider-focus-panel">Open robot fleet</a>
                </div>
            </aside>
            <main class="provider-main">
                <div class="provider-topbar">
                    <div class="provider-search">&#128269; Search patients, devices, tickets...</div>
                    <a class="provider-bell" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=alerts#provider-focus-panel">&#128276;<b>12</b></a>
                    <a class="provider-profile" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=users#provider-focus-panel">
                        <span class="small-avatar">A</span>
                        <span><b>Provider Admin</b><em>Care operations</em></span>
                        <i>&#8964;</i>
                    </a>
                </div>
                <div class="provider-main-top">
                    <div>
                        <h3>{active_title}</h3>
                        <p>{live_note if active_tab == "overview" else active_copy}</p>
                    </div>
                    <div class="date-pill">&#128197; May 20 - May 26, 2024</div>
                </div>
                <div class="provider-kpis">
                    {_provider_kpi("Connected profiles", str(provider_patients), "live", patient(), "up", "&#128101;")}
                    {_provider_kpi("Nesto units", str(provider_devices), "online" if provider_devices else "offline", f"{metrics['robot_updates']} robot records", "up" if provider_devices else "down", "&#129302;")}
                    {_provider_kpi("Active alerts", str(provider_alerts), "live", "from care records", "down" if provider_alerts else "up", "&#128276;")}
                    {_provider_kpi("Caregivers", str(provider_caregivers), "assigned", caregiver(), "up", "&#128100;")}
                </div>
                <div class="provider-overview-layout">
                    <div class="provider-overview-main">
                        <div class="provider-grid two">
                            <section class="provider-card">
                                <div class="panel-head"><b>Recent alerts</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=alerts#provider-focus-panel">View all</a></div>
                                {_provider_alert_rows()}
                            </section>
                            <section class="provider-card">
                                <div class="panel-head"><b>AI risk overview</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=risk#provider-focus-panel">View report</a></div>
                                <div class="donut-panel">
                                    {_provider_donut("248", "Total", "#5e9b6c 0 65%, #d8c38e 65% 90%, #e8584f 90% 100%")}
                                    <div class="legend">
                                        <div><span style="background:#e8584f;"></span><b>High risk</b><em>24 (10%)</em></div>
                                        <div><span style="background:#d8a12b;"></span><b>Medium risk</b><em>62 (25%)</em></div>
                                        <div><span style="background:#5e9b6c;"></span><b>Low risk</b><em>162 (65%)</em></div>
                                    </div>
                                </div>
                            </section>
                        </div>
                        <section class="provider-card">
                            <div class="panel-head"><b>Patients at a glance</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=patients#provider-focus-panel">View all</a></div>
                            {_provider_patient_rows()}
                        </section>
                        <div class="provider-grid two">
                            <section class="provider-card">
                                <div class="panel-head"><b>AI risk scores</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=risk#provider-focus-panel">View all</a></div>
                                {_provider_risk_chart()}
                            </section>
                            <section class="provider-card">
                                <div class="panel-head"><b>Caregiver workload</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=caregivers#provider-focus-panel">View all</a></div>
                                {_provider_workload_rows()}
                            </section>
                        </div>
                        <section class="provider-card">
                            <div class="panel-head"><b>Latest Nesto care activity</b><span>{online_badge} live records</span></div>
                            {live_activity}
                        </section>
                    </div>
                    <aside class="provider-side-stack">
                        <section class="provider-card">
                            <div class="panel-head"><b>Robot fleet status</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=robot#provider-focus-panel">View all</a></div>
                            <div class="donut-panel compact right-rail">
                                {_provider_donut("238", "Devices", "#62aa72 0 83%, #e8584f 83% 95%, #efa629 95% 100%")}
                                <div class="legend">
                                    <div><span style="background:#62aa72;"></span><b>Online</b><em>198 (83%)</em></div>
                                    <div><span style="background:#e8584f;"></span><b>Offline</b><em>28 (12%)</em></div>
                                    <div><span style="background:#efa629;"></span><b>Low battery</b><em>12 (5%)</em></div>
                                </div>
                            </div>
                        </section>
                        <section class="provider-card">
                            <div class="panel-head"><b>Care plans</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=plans#provider-focus-panel">View all</a></div>
                            {_provider_care_plan_rows()}
                        </section>
                        <section class="provider-card">
                            <div class="panel-head"><b>Support tickets</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=tickets#provider-focus-panel">View all</a></div>
                            {_provider_ticket_rows()}
                        </section>
                        <section class="provider-card">
                            <div class="panel-head"><b>Reports</b><a href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab=reports#provider-focus-panel">View all</a></div>
                            {_provider_report_rows()}
                        </section>
                    </aside>
                </div>
            </main>
        </div>
        <div class="provider-value-strip">
            <span>&#128202; Data-driven decisions</span>
            <span>&#9728; Operational efficiency</span>
            <span>&#9825; Better outcomes</span>
            <span>&#128274; Secure and compliant</span>
            <span>&#128172; Integrated care</span>
        </div>
    """


def _robot_station_hero(status, metrics):
    online_badge = "Online" if status["online"] else "Offline"
    battery = min(float(status["battery"]), 100)
    alert_text = "No urgent care alerts" if int(status["alerts"]) == 0 else f"{status['alerts']} care alerts need review"
    return f"""
    <section class="robot-station-hero">
        <div class="robot-station-identity">
            <span class="goal-label">Nesto live station</span>
            <h3>Nesto is with {patient()} in the {status["room"]}</h3>
            <p>Use this page when the admin needs to see Nesto immediately: location, battery, current task, recent care activity, and the next approved action.</p>
            <div class="robot-progress-wrap">
                <div class="robot-progress-head"><b>{status["battery"]:.1f}% battery</b>{badge(online_badge, "green" if status["online"] else "red")}</div>
                <div class="robot-progress"><span style="width:{battery}%;"></span></div>
            </div>
            <div class="robot-station-stats">
                <span><b>{status["status"]}</b> current task</span>
                <span><b>{status["navigation"]}</b> movement</span>
                <span><b>{metrics["assistant_messages"]}</b> care messages</span>
                <span><b>{alert_text}</b> safety check</span>
            </div>
        </div>
        <div class="robot-station-visual">
            <div class="robot-stage">
                {_nesto_robot()}
                <div class="robot-speech">I am Nesto. I am online, nearby, and ready to help {patient()}.</div>
            </div>
        </div>
    </section>
    """


def _robot_status_tiles(status):
    return f"""
    <div class="robot-status-grid">
        <div class="robot-status-card task">
            <div class="robot-status-icon">&#9654;</div>
            <span>What Nesto is doing</span>
            <b>{status["status"]}</b>
            <em>Ready for approved care tasks</em>
        </div>
        <div class="robot-status-card room">
            <div class="robot-status-icon">&#8962;</div>
            <span>Where Nesto is</span>
            <b>{status["room"]}</b>
            <em>Current room at home</em>
        </div>
        <div class="robot-status-card movement">
            <div class="robot-status-icon">&#128694;</div>
            <span>Movement</span>
            <b>{status["navigation"]}</b>
            <em>Navigation state</em>
        </div>
        <div class="robot-status-card alerts">
            <div class="robot-status-icon">&#128276;</div>
            <span>Care alerts</span>
            <b>{status["alerts"]}</b>
            <em>Needs review</em>
        </div>
    </div>
    """


def _provider_top_hero(metrics, status):
    online_badge = "Online" if status["online"] else "Offline"
    return f"""
    <section class="provider-hero-card">
        <div>
            <span class="goal-label">Nesto command center</span>
            <h3>Nesto Care is connected to {patient()}'s home support</h3>
            <p>Open the robot view, message Nesto, or check the family companion app. Live care records and personalization notes stay available behind the scenes.</p>
            <div class="provider-hero-metrics">
                <span><b>{status["battery"]:.1f}%</b> battery</span>
                <span><b>{status["room"]}</b> current room</span>
                <span><b>{metrics["assistant_messages"]}</b> care messages</span>
                <span><b>{metrics["room_events"]}</b> room updates</span>
            </div>
        </div>
        <div class="provider-hero-robot">
            {_nesto_robot()}
            {badge(online_badge, "green" if status["online"] else "red")}
        </div>
    </section>
    """


def _technical_health_panel():
    health = system_health()
    cache = health.get("cache", {})
    chroma = health.get("chroma", {})
    mongo = health.get("mongo", {})
    kafka = health.get("kafka", {})
    counts = mongo.get("counts", {})
    database_name = mongo.get("database_name", "humanoid_assistant")

    def state_badge(ok, true_label="Connected", false_label="Waiting"):
        return badge(true_label if ok else false_label, "green" if ok else "amber")

    collection_rows = "".join(
        f'<div class="row"><span class="row-main">{escape(name)}</span><span class="row-sub">{counts.get(name, 0)} records</span></div>'
        for name in MONGO_COLLECTIONS
    )
    topic_rows = "".join(
        f'<div class="row"><span class="row-main">{escape(topic)}</span><span class="row-sub">{escape(str(kafka.get("status", "not_connected")).replace("_", " "))}</span></div>'
        for topic in KAFKA_TOPICS
    )
    daniel_rows = "".join(
        f'<div class="row"><span class="row-main">{escape(key)}</span><span class="row-sub">{escape(value.get("dashboard_collection", ""))}</span></div>'
        for key, value in DANIEL_TO_DASHBOARD_EVENT_MAP.items()
    )
    return f"""
    <div class="card">
        <p class="section-title">System Health</p>
        <div class="row"><span class="row-main">MongoDB Atlas</span>{state_badge(mongo.get('available'), 'Connected', 'Unavailable')}</div>
        <div class="row"><span class="row-main">Database</span><span class="row-sub">{escape(str(database_name))}</span></div>
        <div class="row"><span class="row-main">Redis cache</span>{state_badge(cache.get('available'), 'Connected', 'Local TTL fallback')}</div>
        <div class="row"><span class="row-main">ChromaDB memory</span>{state_badge(chroma.get('available'), str(chroma.get('count', 0)) + ' memories', 'Unavailable')}</div>
        <div class="row"><span class="row-main">Kafka</span>{badge(str(kafka.get('status', 'not_connected')).replace('_', ' ').title(), 'amber')}</div>
        <div class="row"><span class="row-main">Daniel Backend Data Source</span>{badge('Compatible routes', 'green')}</div>
        <p class="muted">MongoDB is the persistent source. The Kafka bridge and consumer are implemented; when Kafka is running they stream new events into Redis/latest cache for dashboard reads.</p>
    </div>
    <div class="card">
        <p class="section-title">MongoDB collections</p>
        {collection_rows}
    </div>
    <div class="card">
        <p class="section-title">Kafka topic readiness</p>
        {topic_rows}
    </div>
    <div class="card">
        <p class="section-title">Daniel scenario mapping</p>
        {daniel_rows}
    </div>
    """

def _render_html(html):
    cleaned = str(html or "").strip()
    if not cleaned:
        return
    cleaned = " ".join(line.strip() for line in cleaned.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)

def _query_param(name):
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _provider_nav_items(active_tab):
    manage = ["overview", "patients", "robot", "alerts", "risk", "plans", "caregivers", "reports", "tickets"]
    admin = ["organizations", "users", "integrations", "settings"]

    def render_group(title, keys):
        html = f'<div class="provider-nav-label">{title}</div>'
        for key in keys:
            icon, label, _ = PROVIDER_TABS[key]
            active = " active" if key == active_tab else ""
            count = "<b>12</b>" if key == "alerts" else ""
            html += (
                f'<a class="provider-navitem{active}" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab={key}#provider-focus-panel">'
                f'{icon}<span>{label}</span>{count}</a>'
            )
        return html

    return render_group("Manage", manage) + render_group("Admin", admin)


def _provider_nesto_status(metrics, status):
    online_badge = "Online" if status["online"] else "Offline"
    return f"""
    <section class="provider-nesto-card">
        <div class="provider-nesto-copy">
            <span class="goal-label">Nesto assistant</span>
            <h3>Nesto is monitoring {patient()} at home</h3>
            <p>Connected care records are flowing into this provider view: robot status, assistant messages, and room/object updates.</p>
            <div class="provider-nesto-stats">
                <div><b>{status["battery"]:.1f}%</b><span>Battery</span></div>
                <div><b>{status["room"]}</b><span>Room</span></div>
                <div><b>{metrics["assistant_messages"]}</b><span>Messages</span></div>
                <div><b>{metrics["room_events"]}</b><span>Room events</span></div>
            </div>
        </div>
        <div class="provider-nesto-robot">
            {_nesto_robot()}
            {badge(online_badge, "green" if status["online"] else "red")}
        </div>
    </section>
    """


def _provider_next_step(tab, metrics, status):
    if tab == "overview":
        return "Use this view to review Nesto activity, patient risk, robot health, and support work."
    if tab == "patients":
        return f"Start with {patient()}, then compare risk and last-active status across the patient list."
    if tab == "robot":
        return f"Nesto is {status['status'].lower()} in the {status['room'].lower()} with {status['battery']:.1f}% battery."
    if tab == "alerts":
        return "Review high-priority alerts first, then decide whether the family needs a follow-up."
    if tab == "risk":
        return "Use risk scores as a review signal only. They do not replace clinical judgment."
    if tab == "plans":
        return "Check routines, reminders, wellbeing check-ins, and family notes."
    if tab == "caregivers":
        return "Balance caregiver workload and assign follow-up where needed."
    if tab == "reports":
        return f"Use {metrics['robot_updates']} robot updates and {metrics['assistant_messages']} messages as project evidence."
    if tab == "tickets":
        return "Resolve device, reminder, and app issues before they affect family trust."
    if tab == "organizations":
        return "Confirm the Nesto Care organization, provider workspace, and project ownership."
    if tab == "users":
        return "Review role-based access for elderly user, caregiver, admin, and technical team views."
    if tab == "integrations":
        return "Check that live care records, personalization memory, and the approved robot handoff are represented clearly."
    return "Check consent, safety boundaries, and approved Nesto settings."


def _provider_active_preview(tab, metrics, status):
    icon, title, copy = PROVIDER_TABS.get(tab, PROVIDER_TABS["overview"])
    return f"""
    <section class="provider-active-preview">
        <div class="provider-focus-icon">{icon}</div>
        <div>
            <span class="goal-label">Current dashboard area</span>
            <h4>{title}</h4>
            <p>{copy}</p>
            <b>{_provider_next_step(tab, metrics, status)}</b>
        </div>
    </section>
    """


def _provider_focus_panel(tab, metrics, status):
    icon, title, copy = PROVIDER_TABS.get(tab, PROVIDER_TABS["overview"])
    next_step = _provider_next_step(tab, metrics, status)

    _render_html(
        f"""
        <div id="provider-focus-panel" class="provider-focus-panel">
            <div class="provider-focus-icon">{icon}</div>
            <div>
                <span class="goal-label">Selected provider area</span>
                <h3>{title}</h3>
                <p>{copy}</p>
                <b>{next_step}</b>
            </div>
        </div>
        """
    )

    _render_html(_technical_health_panel())

    c1, c2, c3 = st.columns(3)
    if tab in ("overview", "alerts", "risk", "tickets"):
        if c1.button("Open chat workflow", use_container_width=True, key=f"{tab}_chat"):
            _open_admin_page("Chat Monitor", "Chat Monitor opened", "Review Nesto conversation flow and approved actions.")
        if c2.button("Review wellbeing", use_container_width=True, key=f"{tab}_wellbeing"):
            _open_admin_page("Wellbeing Monitor", "Wellbeing Monitor opened", "Review wellbeing rings, reminders, activity, and notes.")
        if c3.button("Check robot", use_container_width=True, key=f"{tab}_robot"):
            _open_admin_page("Robot Operations", "Robot Operations opened", "Review Nesto status, room, battery, and readiness.")
    elif tab == "robot":
        if c1.button("Open robot operations", use_container_width=True, key="focus_robot_ops"):
            _open_admin_page("Robot Operations", "Robot Operations opened", "Review Nesto status, room, battery, and readiness.")
        if c2.button("Start room check", use_container_width=True, key="focus_room_check"):
            st.toast("Room check prepared for Nesto")
        if c3.button(f"Alert {caregiver()}", use_container_width=True, key="focus_family_alert"):
            st.toast(f"Alert prepared for {caregiver()}")
    else:
        if c1.button("Open family app", use_container_width=True, key=f"{tab}_family"):
            _open_role("Caregiver", "Health & Care", "Family Companion App opened", f"Review {patient()}'s family-facing care summary.")
        if c2.button("Open care profile", use_container_width=True, key=f"{tab}_profile"):
            _open_role("Caregiver", "Care Profile", "Care Profile opened", "Review personalization details used by Nesto.")
        if c3.button("Open wellbeing", use_container_width=True, key=f"{tab}_wellbeing2"):
            _open_admin_page("Wellbeing Monitor", "Wellbeing Monitor opened", "Review wellbeing rings, reminders, activity, and notes.")


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


def _provider_kpi(label, value, change, subtext, direction, icon):
    change_class = "positive" if direction == "up" else "negative"
    arrow = "up" if direction == "up" else "down"
    return (
        f'<div class="provider-kpi"><i>{icon}</i><span>{label}</span><strong>{value}</strong>'
        f'<div><em class="{change_class}">{arrow} {change}</em><small>{subtext}</small></div></div>'
    )


def _provider_alert_rows():
    main_patient = patient()
    rows = [
        ("High heart rate", main_patient, "10:30 AM", "High", "red", "&#9829;"),
        ("Possible fall detected", "Patient 02", "9:15 AM", "High", "red", "&#128694;"),
        ("Missed medication", "Patient 03", "8:45 AM", "Medium", "amber", "&#128138;"),
        ("Low battery", "Device #1058", "6:30 AM", "Low", "green", "&#128267;"),
    ]
    html = ""
    for title, person, time, level, color, icon in rows:
        html += (
            f'<div class="provider-row"><div class="provider-icon {color}">{icon}</div>'
            f'<div><b>{title}</b><span>{escape(person)}</span></div><time>{time}</time>{badge(level, color)}</div>'
        )
    return html


def _provider_patient_rows():
    main_patient = patient()
    rows = [
        (main_patient, "78", "Heart Failure", "High", "10 min ago", "Active", "red"),
        ("Patient 02", "81", "Fall risk", "Medium", "15 min ago", "Active", "amber"),
        ("Patient 03", "74", "Medication support", "Medium", "30 min ago", "Active", "amber"),
        ("Patient 04", "80", "Wellbeing support", "Low", "1 hr ago", "Active", "green"),
        ("Patient 05", "76", "Routine monitoring", "Low", "2 hr ago", "Offline", "green"),
    ]
    html = (
        '<div class="provider-table patients provider-table-head">'
        '<span>Patient</span><span>Age</span><span>Condition</span><span>Risk level</span><span>Last active</span><span>Status</span></div>'
    )
    for name, age, condition, risk, active, state, color in rows:
        html += (
            f'<div class="provider-table patients"><span><i class="small-avatar">{escape(name[0])}</i>{escape(name)}</span>'
            f'<span>{age}</span><span>{escape(condition)}</span><span>{badge(risk, color)}</span><span>{active}</span><span>{state}</span></div>'
        )
    return html


def _provider_assignment_rows():
    rows = [("Care Team A", 16), ("Care Team B", 14), ("Care Team C", 12), ("Care Team D", 10)]
    html = ""
    for name, count in rows:
        html += (
            f'<div class="provider-row"><i class="small-avatar">{escape(name[0])}</i>'
            f'<div><b>{escape(name)}</b><span>{count} patients</span></div>'
            f'<div class="workbar"><span style="width:{count * 5}%;"></span></div></div>'
        )
    return html


def _provider_workload_rows():
    rows = [
        ("Care Team A", 85, 24),
        ("Care Team B", 64, 18),
        ("Care Team C", 57, 16),
        ("Care Team D", 50, 14),
        ("Care Team E", 43, 12),
    ]
    html = ""
    for name, percent, patients_count in rows:
        html += (
            f'<div class="provider-row workload"><i class="small-avatar">{escape(name[0])}</i>'
            f'<div><b>{escape(name)}</b><span>{patients_count} patients</span></div>'
            f'<div class="workbar"><span style="width:{percent}%;"></span></div><time>{percent}%</time></div>'
        )
    return html


def _provider_care_plan_rows():
    main_patient = patient()
    rows = [
        (main_patient, "Heart failure management", "On track", "green", "&#128203;"),
        ("Patient 02", "Fall prevention plan", "On track", "green", "&#128203;"),
        ("Patient 03", "Medication support plan", "Needs review", "amber", "&#128203;"),
        ("Patient 04", "Wellbeing support plan", "On track", "green", "&#128203;"),
    ]
    html = ""
    for name, plan, state, color, icon in rows:
        html += (
            f'<div class="provider-row"><div class="provider-icon {color}">{icon}</div>'
            f'<div><b>{escape(name)}</b><span>{escape(plan)}</span></div>{badge(state, color)}</div>'
        )
    return html


def _provider_ticket_rows():
    main_patient = patient()
    rows = [
        ("Device not responding", f"#1258 - {main_patient}", "Open", "red"),
        ("Medication reminder issue", "#1257 - Patient 03", "In progress", "amber"),
        ("App login problem", "#1156 - Patient 02", "Resolved", "green"),
    ]
    html = ""
    for title, sub, state, color in rows:
        html += (
            f'<div class="provider-row"><div class="provider-icon {color}">&#33;</div>'
            f'<div><b>{escape(title)}</b><span>{escape(sub)}</span></div>{badge(state, color)}</div>'
        )
    return html


def _provider_report_rows():
    rows = [
        ("Weekly care summary", "May 13 - May 19, 2024"),
        ("Device usage report", "May 13 - May 19, 2024"),
        ("Alert summary", "May 13 - May 19, 2024"),
        ("Care plan compliance", "May 13 - May 19, 2024"),
    ]
    html = ""
    for title, period in rows:
        html += (
            f'<div class="provider-row"><div class="provider-icon green">&#128196;</div>'
            f'<div><b>{escape(title)}</b><span>{escape(period)}</span></div></div>'
        )
    return html


def _provider_risk_chart():
    points = [72, 62, 59, 70, 66, 71, 68]
    high = "".join(f'<span style="height:{max(18, point - 42)}%;"></span>' for point in points)
    medium = "".join(f'<span style="height:{max(18, point - 28)}%;"></span>' for point in [36, 42, 35, 47, 33, 41, 42])
    low = "".join(f'<span style="height:{max(18, point - 8)}%;"></span>' for point in [12, 17, 12, 20, 13, 19, 18])
    return f"""
        <div class="provider-risk-chart">
            <div class="risk-legend">
                <span><i style="background:#e8584f;"></i>High risk <b>24</b></span>
                <span><i style="background:#efa629;"></i>Medium risk <b>62</b></span>
                <span><i style="background:#5e9b6c;"></i>Low risk <b>162</b></span>
            </div>
            <div class="risk-bars high">{high}</div>
            <div class="risk-bars medium">{medium}</div>
            <div class="risk-bars low">{low}</div>
            <div class="risk-days"><span>May 20</span><span>May 21</span><span>May 22</span><span>May 23</span><span>May 24</span><span>May 25</span><span>May 26</span></div>
        </div>
    """


def _provider_activity_rows(activity):
    if not activity:
        return '<p class="muted">No recent live Nesto care activity is available yet.</p>'
    rows = ""
    for item in activity[:6]:
        rows += (
            f'<div class="provider-row"><time>{escape(item["time"])}</time>'
            f'<div><b>{escape(item["title"])}</b><span>{escape(item["description"])}</span></div>'
            f'{badge(escape(item["source"]), _badge_for_source(item["source"]))}</div>'
        )
    return rows


def _provider_donut(value, label, gradient):
    return (
        f'<div class="provider-donut" style="background:conic-gradient({gradient});">'
        f'<div><strong>{value}</strong><span>{label}</span></div></div>'
    )


def _admin_chat_workflow():
    quick_cards = ""
    for _, label, prompt, icon, tone in CHAT_QUICK_PROMPTS:
        quick_cards += (
            f'<div class="admin-action-card {tone}"><div class="admin-action-icon">{icon}</div>'
            f'<b>{label}</b><span>{escape(prompt)}</span></div>'
        )
    return f"""
    <section id="chat-workflow" class="chat-workflow">
        <div class="chat-workflow-copy">
            <span class="goal-label">Admin workflow</span>
            <h3>Pick a care request, then approve what Nesto should do next.</h3>
            <p>This page is for monitoring and routing. Nesto can understand natural wording, but it only runs approved care actions.</p>
            <div class="chat-steps">
                <span><b>1</b> Choose request</span>
                <span><b>2</b> Review decision</span>
                <span><b>3</b> Run action</span>
                <span><b>4</b> Verify dashboard</span>
            </div>
        </div>
        <div class="admin-action-grid">{quick_cards}</div>
    </section>
    """


def _decision_command_panel(route, preview_text):
    text = preview_text.strip() if preview_text else "No request selected yet"
    return f"""
    <section class="decision-command-panel">
        <div class="decision-main">
            <span class="goal-label">Nesto decision</span>
            <h3>{route["need"]}</h3>
            <p>{_route_explanation(route["need"])}</p>
            <div class="decision-request"><b>Current request</b><span>{escape(text)}</span></div>
        </div>
        <div class="decision-next">
            <div class="decision-step"><span>&#10003;</span><div><b>Detected need</b><em>{route["need"]}</em></div></div>
            <div class="decision-step"><span>&#9654;</span><div><b>Next action</b><em>{route["action"]}</em></div></div>
            <div class="decision-step"><span>&#128737;</span><div><b>Safety rule</b><em>Approved actions only</em></div></div>
        </div>
    </section>
    """


def _route_explanation(need):
    if need == "Find important object":
        return "Nesto can start the object-finder scenario and show the result in robot and family views."
    if need == "Medication reminder":
        return "Nesto can give a preset reminder and record whether it was acknowledged."
    if need == "Wellbeing support":
        return "Nesto can respond calmly and create a wellbeing note for caregiver review."
    if need == "Safety check":
        return "Nesto can flag the concern so the family or care team can review it."
    return "Nesto can answer safely without controlling the robot or giving medical advice."


def _submit_chat_request(text):
    route = _route_for(text)
    now = dt.datetime.now().strftime("%H:%M")
    st.session_state.setdefault("chat_monitor_messages", []).append(
        {"speaker": patient(), "text": text.strip(), "time": now}
    )
    st.session_state["last_chat_text"] = text.strip()
    st.session_state["last_chat_route"] = route
    _append_admin_action(f"Request reviewed: {route['need']}.")
    st.toast(f"Nesto detected: {route['need']}")


def _record_chat_admin_action(route, preview_text):
    if not preview_text.strip():
        st.warning("Choose or type a request first.")
        return
    _append_admin_action(f"Approved action prepared: {route['action']} for {route['need']}.")


def _save_chat_memory(preview_text):
    text = preview_text.strip()
    if not text:
        st.warning("Choose or type a request first.")
        return

    now = dt.datetime.now()
    metadata = {
        "type": "care_request",
        "patient": patient(),
        "created": now.isoformat(timespec="seconds"),
        "display_time": now.strftime("%H:%M"),
        "display_date": now.strftime("%d %b %Y"),
    }
    if save_memory(text, metadata):
        _append_admin_action(f"Request saved to personalization memory at {now.strftime('%H:%M')}.")
        st.success(f"Request saved at {now.strftime('%H:%M')}.")
    else:
        st.warning("The request could not be saved to memory.")


def _append_admin_action(text):
    st.session_state.setdefault("chat_admin_actions", []).append(
        {"text": text, "time": dt.datetime.now().strftime("%H:%M")}
    )


def _admin_chat_action_log():
    actions = st.session_state.get("chat_admin_actions", [])[-6:]
    if not actions:
        return """
        <div class="card">
            <p class="section-title">Admin action log</p>
            <div class="empty-action-log">&#128073; Choose a request above to start. Your approvals and saved notes will appear here.</div>
        </div>
        """
    rows = ""
    for action in reversed(actions):
        if isinstance(action, dict):
            text = str(action.get("text", ""))
            time = str(action.get("time", ""))
        else:
            text = str(action)
            time = ""
        time_html = f'<span class="time">{escape(time)}</span>' if time else '<span class="activity-icon">&#10003;</span>'
        rows += f'<div class="row">{time_html}<div><div class="row-main">{escape(text)}</div><div class="row-sub">Admin update</div></div></div>'
    return f'<div class="card"><p class="section-title">Admin action log</p>{rows}</div>'


def _scenario_rows(active_need=None):
    rows = ""
    for title, desc, color in APPROVED_SCENARIOS:
        active = " active" if title == active_need else ""
        rows += (
            f'<div class="scenario-row{active}"><span class="dot" style="background:{color};"></span>'
            f'<div><div class="row-main">{title}</div><div class="row-sub">{desc}</div></div></div>'
        )
    return rows


def _activity_rows(activity):
    if not activity:
        return '<p class="muted">No recent live care activity is available yet.</p>'
    rows = ""
    for item in activity:
        rows += (
            f'<div class="row"><span class="time">{item["time"]}</span>'
            f'<div><div class="row-main">{item["title"]}</div>'
            f'<div class="row-sub">{item["description"]}</div></div>'
            f'{badge(item["source"], _badge_for_source(item["source"]))}</div>'
        )
    return rows


def _chat_shell(activity):
    session_messages = st.session_state.get("chat_monitor_messages", [])
    live_messages = []
    for item in reversed(activity):
        if item["title"] == "User request":
            live_messages.append({"side": "right", "speaker": patient(), "text": item["description"], "time": item["time"]})
        elif item["title"] == "Assistant response":
            live_messages.append({"side": "left", "speaker": "Nesto", "text": item["description"], "time": item["time"]})

    messages = live_messages[-4:]
    for item in session_messages[-4:]:
        route = _route_for(item["text"])
        messages.append({"side": "right", "speaker": item["speaker"], "text": item["text"], "time": item["time"]})
        messages.append({"side": "left", "speaker": "Nesto", "text": f"I can route that to {route['need']} and update the care dashboard.", "time": item["time"]})

    if not messages:
        messages = [
            {"side": "left", "speaker": "Nesto", "text": f"Hi {patient()}. Tell me what you need help with.", "time": "now"},
            {"side": "right", "speaker": patient(), "text": "Can you help me find my cane?", "time": "09:30"},
            {"side": "left", "speaker": "Nesto", "text": "I can help. I will check the living room and update your caregiver if needed.", "time": "09:31"},
        ]

    bubbles = ""
    for item in messages:
        bubbles += (
            f'<div class="bubble-row {item["side"]}"><div class="bubble-pack"><div class="bubble">{item["text"]}</div>'
            f'<div class="chat-meta" style="text-align:{"right" if item["side"] == "right" else "left"};">{item["speaker"]}, {item["time"]}</div></div></div>'
        )

    return f"""
        <div class="chat-shell">
            <div class="chat-top">
            <div class="chat-avatar">N</div>
                <div>
                    <div class="row-main">{patient()} and Nesto</div>
                    <div class="row-sub">Live messages plus current-session requests</div>
                </div>
                <span class="badge badge-green" style="margin-left:auto;">Monitored</span>
            </div>
            {bubbles}
        </div>
    """


def _badge_for_source(source):
    if "Assistant" in source:
        return "purple"
    if "Room" in source:
        return "amber"
    if "alert" in source.lower():
        return "red"
    return "green"


def _open_admin_page(page_name, title, message):
    tab_map = {
        "Chat Monitor": "integrations",
        "Wellbeing Monitor": "risk",
        "Robot Operations": "robot",
        "Admin Overview": "overview",
        "Admin / Provider / NESTO Team Dashboard": "overview",
    }
    st.session_state["pending_role"] = "Admin / team"
    st.session_state["pending_page"] = "Admin / Provider / NESTO Team Dashboard"
    st.session_state["provider_tab"] = tab_map.get(page_name, "overview")
    st.session_state["app_notice"] = {"title": title, "message": message}
    st.rerun()


def _open_role(role, page_name, title, message):
    page_aliases = {
        "Health & Care": "Guardian / Caregiver Dashboard",
        "Family App Landing Page": "Guardian / Caregiver Dashboard",
        "Care Profile": "User Creation + Preferences Page",
        "Setup & Consent": "User Creation + Preferences Page",
        "Consent Details": "Consent",
        "Home": "Elderly User Interface",
        "Admin Overview": "Admin / Provider / NESTO Team Dashboard",
        "Chat Monitor": "Admin / Provider / NESTO Team Dashboard",
        "Robot Operations": "Admin / Provider / NESTO Team Dashboard",
        "Wellbeing Monitor": "Admin / Provider / NESTO Team Dashboard",
    }
    st.session_state["pending_role"] = role
    st.session_state["pending_page"] = page_aliases.get(page_name, page_name)
    st.session_state["app_notice"] = {"title": title, "message": message}
    st.rerun()


def _render_notice():
    notice = st.session_state.pop("app_notice", None)
    if not notice:
        return
    _render_html(
        f"""
        <div class="notice-pop">
            {notice["title"]}
            <span class="notice-sub">{notice["message"]}</span>
        </div>
        """
    )


def _memory_rows(memory_rows):
    if not memory_rows:
        return '<p class="muted">No care notes saved yet.</p>'
    rows = ""
    for item in memory_rows:
        if isinstance(item, dict):
            text = str(item.get("text", ""))
            metadata = item.get("metadata") or {}
            saved_at = item.get("saved_at") or metadata.get("saved_at") or metadata.get("created")
            time_label = metadata.get("display_time") or _memory_time(saved_at)
            date_label = metadata.get("display_date") or _memory_date(saved_at)
            kind = _memory_type_label(metadata.get("type"))
        else:
            text = str(item)
            time_label = ""
            date_label = ""
            kind = "Care note"
        time_html = f'<span class="time">{escape(time_label)}</span>' if time_label else f'<span class="dot" style="background:{BLUE};"></span>'
        sub = " - ".join(part for part in [kind, date_label] if part)
        rows += (
            f'<div class="row">{time_html}<div>'
            f'<div class="row-main">{escape(text)}</div>'
            f'<div class="row-sub">{escape(sub)}</div>'
            f'</div></div>'
        )
    return rows


def _memory_time(value):
    if not value:
        return ""
    try:
        return dt.datetime.fromisoformat(str(value)).strftime("%H:%M")
    except ValueError:
        text = str(value)
        return text[:5] if ":" in text else ""


def _memory_date(value):
    if not value:
        return ""
    try:
        return dt.datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except ValueError:
        return ""


def _memory_type_label(kind):
    labels = {
        "care_note": "Caregiver note",
        "caregiver_note": "Family note",
        "care_request": "Chat request",
        "profile_customization": "Profile preference",
        "scenario": "Care scenario",
    }
    return labels.get(kind, "Care note")


def _route_for(user_text):
    text = (user_text or "").lower()
    if any(
        word in text
        for word in (
            "cane",
            "object",
            "find",
            "lost",
            "missing",
            "where is",
            "where's",
            "remote",
            "glasses",
            "keys",
            "important item",
        )
    ):
        return {"need": "Find important object", "action": "Start object finder"}
    if any(word in text for word in ("medicine", "medication", "pill", "dose", "remind", "reminder")):
        return {"need": "Medication reminder", "action": "Show reminder"}
    if any(word in text for word in ("sad", "lonely", "stressed", "worried", "upset", "mood", "feel", "talk")):
        return {"need": "Wellbeing support", "action": "Offer calm support"}
    if any(word in text for word in ("fall", "fell", "emergency", "not moved", "safety", "danger", "urgent")):
        return {"need": "Safety check", "action": "Alert caregiver"}
    return {"need": "General support", "action": "Answer safely"}


# ----------------------------------------------------------------------
# Task 9 final Admin / Provider dashboard
# ----------------------------------------------------------------------

TASK9_TABS = {
    "overview": "Overview",
    "robot_fleet": "Robot Fleet",
    "patients": "Patients",
    "guardians": "Guardian / Caregivers",
    "alerts": "Alerts",
    "telemetry": "Telemetry & Logs",
    "care_plans": "Care Plans",
    "reports": "Reports",
    "system_health": "System Health",
    "support_tickets": "Support Tickets",
    "settings": "Settings",
}

TASK9_TAB_ALIASES = {
    "robot": "robot_fleet",
    "caregivers": "guardians",
    "plans": "care_plans",
    "integrations": "system_health",
    "tickets": "support_tickets",
    "logs": "telemetry",
}


def _task9_active_tab():
    raw = (_query_param("provider_tab") or st.session_state.get("provider_tab") or "overview").strip().lower()
    tab = TASK9_TAB_ALIASES.get(raw, raw)
    return tab if tab in TASK9_TABS else "overview"


def _task9_link(tab, label, extra=""):
    href = f"?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab={tab}{extra}#admin-{tab.replace('_', '-')}"
    return f'<a class="task9-link" href="{href}">{label}</a>'


def _task9_badge(text, tone="green"):
    tone = tone if tone in {"green", "amber", "red", "blue", "gray", "purple"} else "gray"
    return f'<span class="task9-badge {tone}">{escape(str(text))}</span>'


def _task9_status_tone(text):
    lower = str(text or "").lower()
    if any(word in lower for word in ("connected", "active", "online", "accepted", "normal", "ready", "resolved", "passed", "running", "readable")):
        return "green"
    if any(word in lower for word in ("high", "open", "error", "failed", "offline", "unavailable")):
        return "red"
    if any(word in lower for word in ("planned", "waiting", "pending", "fallback", "medium", "progress")):
        return "amber"
    return "gray"


def _task9_kpi(label, value, subtext, tone="green"):
    return f"""
    <div class="task9-kpi">
        <span>{escape(label)}</span>
        <b class="{tone}">{escape(str(value))}</b>
        <em>{escape(str(subtext))}</em>
    </div>
    """


def _task9_styles():
    return """
    <style>
    section[data-testid="stSidebar"],
    div[data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }
    .block-container {
        max-width: 1580px !important;
        padding: 16px !important;
    }
    .task9-admin-shell {
        display: grid;
        grid-template-columns: 260px minmax(0, 1fr);
        gap: 18px;
        max-width: 1550px;
        margin: 0 auto 34px;
        color: #183f3a;
        letter-spacing: 0;
    }
    .task9-admin-shell * {
        box-sizing: border-box;
    }
    .task9-sidebar {
        min-height: 780px;
        border: 1px solid #e7ded0;
        border-radius: 22px;
        background: rgba(255,253,248,.92);
        box-shadow: 0 18px 46px rgba(40,55,44,.08);
        padding: 20px 18px;
        display: flex;
        flex-direction: column;
        position: sticky;
        top: 14px;
    }
    .task9-main {
        min-width: 0;
    }
    .task9-side-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #123536;
        font-weight: 950;
        margin-bottom: 20px;
        font-size: 1.06rem;
    }
    .task9-side-brand span {
        font-size: 1.75rem;
    }
    .task9-side-label {
        color: #6b7d78;
        font-size: .72rem;
        font-weight: 950;
        margin: 0 0 10px;
        text-transform: uppercase;
    }
    .task9-side-nav {
        display: grid;
        gap: 6px;
    }
    .task9-side-nav a,
    .task9-side-logout {
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
    }
    .task9-side-nav a.active,
    .task9-side-nav a:hover {
        background: #e7f1eb;
    }
    .task9-side-nav span {
        width: 18px;
        text-align: center;
    }
    .task9-side-robot {
        margin-top: auto;
        border: 1px solid #e3d8c7;
        border-radius: 18px;
        background: #fffdf8;
        padding: 14px;
        text-align: center;
        color: #123536;
        overflow: hidden;
        pointer-events: none;
        cursor: default;
    }
    .task9-side-robot .nesto-bot {
        transform: scale(.58);
        margin: -22px auto -34px;
        pointer-events: none;
    }
    .task9-side-robot b,
    .task9-side-robot small {
        display: block;
    }
    .task9-side-robot small {
        color: #176b4d;
        font-weight: 950;
        margin-top: 4px;
    }
    .task9-side-logout {
        justify-content: center;
        border: 1px solid #f1d1ca;
        background: #fff7f5;
        color: #8a2b2b !important;
        margin-top: 10px;
    }
    .task9-admin {
        color: #183f3a;
        max-width: none;
        margin: 0 auto 30px;
        letter-spacing: 0;
    }
    .task9-admin * {
        box-sizing: border-box;
    }
    .task9-admin a {
        color: #176b4d !important;
        text-decoration: none !important;
        font-weight: 900;
    }
    .task9-link {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 32px;
        border-radius: 999px;
        border: 1px solid #cbdccb;
        background: #fffdf8;
        color: #176b4d !important;
        padding: 7px 11px;
        box-shadow: 0 8px 18px rgba(37,65,63,.05);
        white-space: nowrap;
    }
    .task9-link:hover {
        border-color: #7fa98c;
        background: #edf4ee;
    }
    .task9-hero {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: start;
        gap: 24px;
        margin-bottom: 18px;
    }
    .task9-hero h1 {
        margin: 0 0 6px;
        font-size: clamp(1.7rem, 2.4vw, 2.25rem);
        letter-spacing: 0;
        color: #183f3a;
    }
    .task9-hero p {
        margin: 0;
        color: #65736f;
        font-weight: 700;
    }
    .task9-source {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
    }
    .task9-admin-profile {
        border: 1px solid #e5ded2;
        background: rgba(255,253,248,.9);
        border-radius: 16px;
        padding: 9px 12px;
        color: #183f3a;
        font-weight: 950;
        box-shadow: 0 10px 24px rgba(37,65,63,.06);
    }
    .task9-admin-profile em {
        display: block;
        color: #65736f;
        font-style: normal;
        font-size: .76rem;
        font-weight: 800;
    }
    .task9-logout {
        min-height: 40px;
        border-radius: 999px;
        border: 1px solid #f1d1ca;
        background: #fff7f5;
        color: #8a2b2b !important;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 8px 14px;
        font-weight: 950;
        text-decoration: none !important;
        box-shadow: 0 10px 24px rgba(138,43,43,.05);
    }
    .task9-date {
        border: 1px solid #e5ded2;
        background: rgba(255,253,248,.86);
        border-radius: 16px;
        padding: 11px 16px;
        color: #183f3a;
        font-weight: 900;
        box-shadow: 0 10px 24px rgba(37,65,63,.06);
    }
    .task9-tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 0 0 18px;
    }
    .task9-tabs a {
        border: 1px solid #e3d8c7;
        background: rgba(255,253,248,.86);
        border-radius: 999px;
        padding: 9px 13px;
        color: #183f3a !important;
        font-size: .85rem;
        box-shadow: 0 8px 18px rgba(37,65,63,.05);
    }
    .task9-tabs a.active {
        background: #176b4d;
        border-color: #176b4d;
        color: white !important;
    }
    .task9-kpis {
        display: grid;
        grid-template-columns: repeat(6, minmax(130px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
    }
    .task9-kpi,
    .task9-card,
    .task9-panel {
        border: 1px solid #e5ded2;
        background: rgba(255,253,248,.88);
        border-radius: 22px;
        box-shadow: 0 18px 40px rgba(37,65,63,.075);
        backdrop-filter: blur(12px);
    }
    .task9-kpi {
        padding: 16px;
        min-height: 112px;
    }
    .task9-kpi span {
        display: block;
        color: #3e5350;
        font-size: .78rem;
        font-weight: 950;
        margin-bottom: 8px;
    }
    .task9-kpi b {
        display: block;
        font-size: 1.85rem;
        line-height: 1;
        color: #176b4d;
    }
    .task9-kpi b.red { color: #ef4444; }
    .task9-kpi b.blue { color: #4f727e; }
    .task9-kpi b.purple { color: #6fa7a6; }
    .task9-kpi b.amber { color: #b56b00; }
    .task9-kpi em {
        display: block;
        margin-top: 9px;
        color: #65736f;
        font-style: normal;
        font-weight: 750;
        font-size: .82rem;
    }
    .task9-grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 16px;
        align-items: stretch;
    }
    .task9-card {
        padding: 18px;
        overflow: hidden;
    }
    .task9-card h3 {
        margin: 0 0 14px;
        color: #123536;
        font-size: 1rem;
        font-weight: 950;
    }
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .task9-row {
        display: grid;
        grid-template-columns: 36px 1fr auto;
        gap: 12px;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #eee6da;
    }
    .task9-row:last-child { border-bottom: 0; }
    .task9-icon {
        width: 34px;
        height: 34px;
        border-radius: 11px;
        background: #e9f2ec;
        color: #176b4d;
        display: grid;
        place-items: center;
        font-weight: 950;
    }
    .task9-row b,
    .task9-table b {
        display: block;
        color: #183f3a;
        font-weight: 950;
    }
    .task9-row small,
    .task9-table small,
    .task9-muted {
        display: block;
        color: #65736f;
        font-weight: 700;
        margin-top: 3px;
    }
    .task9-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        padding: 5px 10px;
        font-size: .74rem;
        font-weight: 950;
        white-space: nowrap;
    }
    .task9-badge.green { color: #176b4d; background: #eaf5ee; }
    .task9-badge.amber { color: #a86300; background: #fff4d8; }
    .task9-badge.red { color: #ef4444; background: #fff0f0; }
    .task9-badge.blue { color: #4f727e; background: #edf4f5; }
    .task9-badge.purple { color: #547f7e; background: #e7f0ef; }
    .task9-badge.gray { color: #65736f; background: #f2f0eb; }
    .task9-table {
        width: 100%;
        border-collapse: collapse;
        font-size: .86rem;
    }
    .task9-table th {
        color: #65736f;
        text-align: left;
        font-size: .76rem;
        font-weight: 950;
        padding: 0 10px 10px 0;
    }
    .task9-table td {
        border-top: 1px solid #eee6da;
        padding: 11px 10px 11px 0;
        color: #324a48;
        font-weight: 750;
        vertical-align: top;
    }
    .task9-donut {
        width: 160px;
        height: 160px;
        margin: 12px auto 16px;
        border-radius: 999px;
        background: conic-gradient(#29a673 0 70%, #ef4444 70% 88%, #f59e0b 88% 100%);
        display: grid;
        place-items: center;
    }
    .task9-donut div {
        width: 92px;
        height: 92px;
        border-radius: 999px;
        background: #fffdf8;
        display: grid;
        place-items: center;
        text-align: center;
        box-shadow: inset 0 0 0 1px #eee6da;
    }
    .task9-donut b {
        color: #123536;
        font-size: 1.8rem;
        line-height: 1;
    }
    .task9-donut span {
        color: #65736f;
        font-size: .74rem;
        font-weight: 850;
    }
    .task9-legend div {
        display: grid;
        grid-template-columns: 12px 1fr auto;
        gap: 8px;
        align-items: center;
        margin: 9px 0;
        color: #3e5350;
        font-weight: 800;
    }
    .task9-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
    }
    .task9-robot-card {
        padding: 0;
    }
    .task9-robot-top {
        min-height: 156px;
        display: grid;
        place-items: center;
        background:
            linear-gradient(rgba(255, 253, 248, .86), rgba(255, 253, 248, .86)),
            var(--nesto-brand-pattern),
            linear-gradient(135deg, #f7f4ee, #eef5f1);
        background-size: auto, 150px 150px, auto;
        border-bottom: 1px solid #e5ded2;
    }
    .task9-robot-top .nesto-bot {
        transform: scale(.8);
        margin: 4px auto;
        pointer-events: none;
    }
    .task9-system-list {
        padding: 16px 18px 18px;
    }
    .task9-system-row {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        padding: 9px 0;
        color: #3e5350;
        font-weight: 820;
    }
    .task9-detail {
        background: linear-gradient(135deg, rgba(234,245,238,.84), rgba(255,253,248,.9));
        border-color: #cbdccb;
    }
    .task9-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 14px;
    }
    .task9-action {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 38px;
        border-radius: 999px;
        padding: 8px 13px;
        border: 1px solid #cbdccb;
        background: #fffdf8;
        color: #176b4d !important;
        font-weight: 950;
    }
    .task9-action.primary {
        background: #176b4d;
        border-color: #176b4d;
        color: white !important;
    }
    .task9-report-grid,
    .task9-settings-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
    }
    .task9-mini-card {
        border: 1px solid #e5ded2;
        background: rgba(255,253,248,.84);
        border-radius: 18px;
        padding: 16px;
    }
    .task9-mini-card b {
        color: #183f3a;
        display: block;
        margin-bottom: 8px;
    }
    @media (max-width: 1100px) {
        .task9-admin-shell { grid-template-columns: 1fr; }
        .task9-sidebar { min-height: auto; position: relative; top: auto; }
        .task9-kpis { grid-template-columns: repeat(3, minmax(150px, 1fr)); }
        .span-3, .span-4, .span-5, .span-6, .span-7, .span-8 { grid-column: span 12; }
        .task9-report-grid, .task9-settings-grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 720px) {
        .task9-hero { grid-template-columns: 1fr; }
        .task9-source { justify-content: flex-start; }
        .task9-kpis { grid-template-columns: 1fr; }
        .task9-report-grid, .task9-settings-grid { grid-template-columns: 1fr; }
    }
    </style>
    """


def _task9_tabs(active_tab):
    items = ""
    for key, label in TASK9_TABS.items():
        active = " active" if key == active_tab else ""
        items += f'<a class="{active}" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab={key}#admin-{key.replace("_", "-")}">{escape(label)}</a>'
    return f'<nav class="task9-tabs">{items}</nav>'


def _task9_sidebar(active_tab):
    icons = {
        "overview": "&#8962;",
        "robot_fleet": "&#129302;",
        "patients": "&#128101;",
        "guardians": "&#129489;",
        "alerts": "&#128276;",
        "telemetry": "&#128200;",
        "care_plans": "&#128203;",
        "reports": "&#128196;",
        "system_health": "&#9881;",
        "support_tickets": "&#128172;",
        "settings": "&#9881;",
    }
    links = ""
    for key, label in TASK9_TABS.items():
        active = " active" if key == active_tab else ""
        links += (
            f'<a class="{active}" href="?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview&provider_tab={key}#admin-{key.replace("_", "-")}">'
            f'<span>{icons.get(key, "&#9635;")}</span>{escape(label)}</a>'
        )
    return f"""
    <aside class="task9-sidebar">
        <div class="task9-side-brand"><span>&#127968;</span><b>Nesto Care</b></div>
        <div class="task9-side-label">Main Menu</div>
        <nav class="task9-side-nav">{links}</nav>
        <div class="task9-side-robot">
            {_nesto_robot()}
            <b>Nesto systems ready</b>
            <small>&#9679; Operations online</small>
        </div>
        <a class="task9-side-logout" href="?logout=1">Log out</a>
    </aside>
    """


def _task9_header(snapshot, active_tab):
    system = snapshot["system"]
    cache_mode = snapshot.get("source", {}).get("cache_mode", "unknown")
    date_label = dt.datetime.now().strftime("%b %d, %Y")
    mongo = system.get("mongo", {})
    chroma = system.get("chroma", {})
    kafka = system.get("kafka", {})
    mongo_label = "Loaded from MongoDB" if mongo.get("available") else "MongoDB unavailable"
    chroma_label = "ChromaDB connected" if chroma.get("available") else "ChromaDB unavailable"
    kafka_label = "Kafka connected" if kafka.get("available") else "Kafka unavailable"
    return f"""
    <div class="task9-admin" id="admin-{active_tab.replace('_', '-')}">
        <div class="task9-hero">
            <div>
                <h1>Nesto Care Operations</h1>
                <p>Monitor robots, systems, and care delivery in real time.</p>
            </div>
            <div class="task9-source">
                {_task9_badge(mongo_label, _task9_status_tone(mongo_label))}
                {_task9_badge(f"Cache: {cache_mode}", _task9_status_tone(cache_mode))}
                {_task9_badge(chroma_label, _task9_status_tone(chroma_label))}
                {_task9_badge(kafka_label, _task9_status_tone(kafka_label))}
                <span class="task9-date">{date_label}</span>
                <span class="task9-admin-profile"><b>Provider Admin</b><em>Admin</em></span>
                <a class="task9-logout" href="?logout=1">Log out</a>
            </div>
        </div>
        {_task9_tabs(active_tab)}
    </div>
    """


def _task9_shell(snapshot, active_tab, body_html):
    return f"""
    <div class="task9-admin-shell">
        {_task9_sidebar(active_tab)}
        <main class="task9-main">
            {_task9_header(snapshot, active_tab)}
            {body_html}
        </main>
    </div>
    """


def _task9_kpis(snapshot):
    kpis = snapshot["kpis"]
    total = max(int(kpis.get("robots_total", 0)), 1)
    online = int(kpis.get("robots_online", 0))
    pct = round((online / total) * 100) if total else 0
    return f"""
    <div class="task9-kpis">
        {_task9_kpi("Robots Online", f"{online} / {total}", f"{pct}% of fleet", "green")}
        {_task9_kpi("Active Alerts", kpis.get("active_alerts", 0), "Requires attention", "red")}
        {_task9_kpi("Care Messages", kpis.get("care_messages", 0), "Conversation events", "blue")}
        {_task9_kpi("Room Events", kpis.get("room_events", 0), "Environment events", "purple")}
        {_task9_kpi("Registered Patients", kpis.get("registered_patients", 0), "Profiles/accounts", "green")}
        {_task9_kpi("Guardian / Caregivers", kpis.get("guardian_caregivers", 0), "Linked accounts", "amber")}
    </div>
    """


def _task9_alert_rows(rows, limit=4):
    html = ""
    for row in rows[:limit]:
        tone = _task9_status_tone(row.get("severity"))
        html += (
            f'<div class="task9-row"><span class="task9-icon">!</span><span>'
            f'<b>{escape(str(row.get("type", "Care alert")))}</b>'
            f'<small>{escape(str(row.get("patient", "-")))} - {escape(str(row.get("time", "-")))}</small>'
            f'</span>{_task9_badge(row.get("severity", "Medium"), tone)}</div>'
        )
    return html


def _task9_ticket_rows(rows, limit=4):
    html = ""
    for row in rows[:limit]:
        html += (
            f'<div class="task9-row"><span class="task9-icon">T</span><span>'
            f'<b>{escape(str(row.get("title", "Support ticket")))}</b>'
            f'<small>{escape(str(row.get("robot", "-")))} - {escape(str(row.get("patient", "-")))}</small>'
            f'</span>{_task9_badge(row.get("status", "Open"), _task9_status_tone(row.get("status")))}</div>'
        )
    return html


def _task9_robot_fleet(snapshot):
    fleet = snapshot["fleet"]
    total = max(int(fleet.get("total", 0)), 1)
    online_pct = round((int(fleet.get("online", 0)) / total) * 100)
    offline_pct = round((int(fleet.get("offline", 0)) / total) * 100)
    low_pct = max(0, 100 - online_pct - offline_pct)
    return f"""
    <div class="task9-donut" style="background:conic-gradient(#29a673 0 {online_pct}%, #ef4444 {online_pct}% {online_pct + offline_pct}%, #f59e0b {online_pct + offline_pct}% 100%);">
        <div><b>{fleet.get("total", 0)}</b><span>Total Robots</span></div>
    </div>
    <div class="task9-legend">
        <div><span class="task9-dot" style="background:#29a673;"></span><span>Online</span><b>{fleet.get("online", 0)}</b></div>
        <div><span class="task9-dot" style="background:#ef4444;"></span><span>Offline</span><b>{fleet.get("offline", 0)}</b></div>
        <div><span class="task9-dot" style="background:#f59e0b;"></span><span>Low Battery</span><b>{fleet.get("low_battery", 0)}</b></div>
    </div>
    """


def _task9_system_card(snapshot):
    system = snapshot["system"]
    mongo = system.get("mongo", {})
    cache = system.get("cache", {})
    chroma = system.get("chroma", {})
    kafka = system.get("kafka", {})
    kafka_runtime = kafka.get("runtime", {}) if isinstance(kafka.get("runtime"), dict) else {}
    producer_state = (kafka_runtime.get("producer") or {}).get("status", "not running")
    consumer_state = (kafka_runtime.get("consumer") or {}).get("status", "not running")
    bridge_state = (kafka_runtime.get("bridge") or {}).get("status", "not running")
    listener_state = (kafka_runtime.get("listener") or {}).get("status", "not running")
    kafka_status = str(kafka.get("status", "not_connected")).replace("_", " ").title()
    return f"""
    <div class="task9-card task9-robot-card">
        <div class="task9-robot-top">{_nesto_robot()}</div>
        <div class="task9-system-list">
            <h3>System Status</h3>
            <div class="task9-system-row"><span>MongoDB</span>{_task9_badge("Connected" if mongo.get("available") else "Unavailable", "green" if mongo.get("available") else "red")}</div>
            <div class="task9-system-row"><span>Redis Cache</span>{_task9_badge("Connected" if cache.get("available") else "Local TTL fallback", "green" if cache.get("available") else "amber")}</div>
            <div class="task9-system-row"><span>ChromaDB Memory</span>{_task9_badge("Connected" if chroma.get("available") else "Unavailable", "green" if chroma.get("available") else "amber")}</div>
            <div class="task9-system-row"><span>Kafka</span>{_task9_badge(kafka_status, _task9_status_tone(kafka_status))}</div>
            {_task9_link("system_health", "View system health ->")}
        </div>
    </div>
    """


def _task9_telemetry_table(rows, limit=6):
    body = ""
    for row in rows[:limit]:
        body += (
            f'<tr><td>{escape(str(row.get("time", "-")))}</td>'
            f'<td>{escape(str(row.get("robot_id", "-")))}</td>'
            f'<td><b>{escape(str(row.get("event_type", "Event")))}</b><small>{escape(str(row.get("summary", "")))}</small></td>'
            f'<td>{escape(str(row.get("room", "-")))}</td>'
            f'<td>{_task9_badge(row.get("status", "Normal"), _task9_status_tone(row.get("status")))}</td>'
            f'<td>{escape(str(row.get("source_collection", "-")))}</td></tr>'
        )
    return f"""
    <table class="task9-table">
        <thead><tr><th>Time</th><th>Robot ID</th><th>Event</th><th>Room</th><th>Status</th><th>Source</th></tr></thead>
        <tbody>{body}</tbody>
    </table>
    """


def _task9_overview(snapshot):
    return f"""
    <div class="task9-admin">
        {_task9_kpis(snapshot)}
        <div class="task9-grid">
            <section class="task9-card span-3"><h3>Robot Fleet Status</h3>{_task9_robot_fleet(snapshot)}</section>
            <section class="task9-card span-5"><h3>Recent Alerts</h3>{_task9_alert_rows(snapshot["alerts"])}</section>
            <section class="span-4">{_task9_system_card(snapshot)}</section>
            <section class="task9-card span-8">
                <h3>Latest Telemetry Logs <span style="float:right;">{_task9_link("telemetry", "View all topics")}</span></h3>
                {_task9_telemetry_table(snapshot["telemetry"], limit=5)}
                <div class="task9-actions">{_task9_link("telemetry", "View all logs ->")}</div>
            </section>
            <section class="task9-card span-4">
                <h3>Support Tickets</h3>
                {_task9_ticket_rows(snapshot["support_tickets"], limit=4)}
                <div class="task9-actions">{_task9_link("support_tickets", "View all tickets ->")}</div>
            </section>
        </div>
    </div>
    """


def _task9_patients_page(snapshot):
    selected = _query_param("admin_patient_id")
    rows = ""
    for row in snapshot["patients"]:
        detail = f"&admin_patient_id={escape(str(row['id']))}"
        rows += (
            f'<tr><td><b>{escape(str(row["id"]))}</b></td><td><b>{escape(str(row["full_name"]))}</b><small>{escape(str(row["preferred_name"]))}</small></td>'
            f'<td>{escape(str(row["age"]))}</td><td>{escape(str(row["guardian"]))}</td><td>{escape(str(row["medicine_count"]))}</td>'
            f'<td>{escape(str(row["important_object"]))}</td><td>{escape(str(row["robot_name"]))}</td>'
            f'<td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td><td>{_task9_badge(row["consent_status"], _task9_status_tone(row["consent_status"]))}</td>'
            f'<td>{_task9_link("patients", "View", detail)}</td></tr>'
        )
    detail_html = ""
    if selected:
        patient_row = next((item for item in snapshot["patients"] if str(item["id"]) == str(selected)), None)
        if patient_row:
            detail_html = f"""
            <section id="admin-patient-detail" class="task9-card task9-detail span-12">
                <h3>Patient Detail</h3>
                <div class="task9-grid">
                    <div class="span-3"><b>{escape(str(patient_row["full_name"]))}</b><span class="task9-muted">Preferred name: {escape(str(patient_row["preferred_name"]))}</span></div>
                    <div class="span-3"><b>Guardian / Caregiver</b><span class="task9-muted">{escape(str(patient_row["guardian"]))} - {escape(str(patient_row["relationship"]))}</span></div>
                    <div class="span-3"><b>Medicine routine</b><span class="task9-muted">{escape(str(patient_row["medicine_count"]))} item(s)</span></div>
                    <div class="span-3"><b>ChromaDB memory</b><span class="task9-muted">{escape(str(snapshot["system"].get("chroma", {}).get("count", 0)))} memories</span></div>
                </div>
                <div class="task9-actions">{_task9_link("alerts", "Recent alerts")} {_task9_link("telemetry", "Recent care activity")} {_task9_link("system_health", "System health")}</div>
            </section>
            """
    return f"""
    <div class="task9-admin">
        <section class="task9-card span-12">
            <h3>Registered Patients</h3>
            <table class="task9-table">
                <thead><tr><th>Patient ID</th><th>Name</th><th>Age</th><th>Guardian / Caregiver</th><th>Medicine</th><th>Important Object</th><th>Robot</th><th>Status</th><th>Consent</th><th></th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </section>
        <div class="task9-grid">{detail_html}</div>
    </div>
    """


def _task9_guardians_page(snapshot):
    selected = _query_param("admin_guardian_id")
    rows = ""
    for row in snapshot["guardians"]:
        detail = f"&admin_guardian_id={escape(str(row['id']))}"
        rows += (
            f'<tr><td><b>{escape(str(row["id"]))}</b></td><td><b>{escape(str(row["name"]))}</b><small>{escape(str(row["username"]))}</small></td>'
            f'<td>{escape(str(row["linked_patients"]))}</td><td>{escape(str(row["relationship"]))}</td><td>{escape(str(row["phone"]))}</td>'
            f'<td>{escape(str(row["last_login"]))}</td><td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td><td>{_task9_link("guardians", "View", detail)}</td></tr>'
        )
    detail_html = ""
    if selected:
        item = next((row for row in snapshot["guardians"] if str(row["id"]) == str(selected)), None)
        if item:
            detail_html = f"""
            <section class="task9-card task9-detail">
                <h3>Guardian / Caregiver Detail</h3>
                <div class="task9-row"><span class="task9-icon">G</span><span><b>{escape(str(item["name"]))}</b><small>{escape(str(item["username"]))}</small></span>{_task9_badge(item["status"], _task9_status_tone(item["status"]))}</div>
                <div class="task9-row"><span class="task9-icon">P</span><span><b>Linked patient(s)</b><small>{escape(str(item["linked_patients"]))}</small></span></div>
                <div class="task9-row"><span class="task9-icon">N</span><span><b>Recent notes and actions</b><small>Read from caregiver_notes / conversation events when available.</small></span></div>
            </section>
            """
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Guardian / Caregiver Accounts</h3>
            <table class="task9-table">
                <thead><tr><th>ID</th><th>Name</th><th>Linked patient(s)</th><th>Relationship</th><th>Phone</th><th>Last login</th><th>Status</th><th></th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </section>
        {detail_html}
    </div>
    """


def _task9_robot_page(snapshot):
    selected = _query_param("admin_robot_id")
    rows = ""
    for row in snapshot["robots"]:
        detail = f"&admin_robot_id={escape(str(row['id']))}"
        battery = f'{float(row.get("battery", 0.0)):.1f}%'
        rows += (
            f'<tr><td><b>{escape(str(row["id"]))}</b></td><td>{escape(str(row["patient"]))}</td><td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td>'
            f'<td>{battery}</td><td>{escape(str(row["location"]))}</td><td>{escape(str(row["movement"]))}</td><td>{escape(str(row["last_sync"]))}</td>'
            f'<td>{escape(str(row["sensor_status"]))}</td><td>{escape(str(row["maintenance_status"]))}</td><td>{_task9_link("robot_fleet", "View", detail)}</td></tr>'
        )
    detail_html = ""
    if selected:
        robot = next((item for item in snapshot["robots"] if str(item["id"]) == str(selected)), None)
        if robot:
            detail_html = f"""
            <section class="task9-card task9-detail">
                <h3>Robot Detail</h3>
                <div class="task9-grid">
                    <div class="span-3"><b>Battery</b><span class="task9-muted">{float(robot.get("battery", 0.0)):.1f}%</span></div>
                    <div class="span-3"><b>Location</b><span class="task9-muted">{escape(str(robot["location"]))}</span></div>
                    <div class="span-3"><b>Movement</b><span class="task9-muted">{escape(str(robot["movement"]))}</span></div>
                    <div class="span-3"><b>Recent events</b><span class="task9-muted">{len(snapshot["telemetry"])} telemetry rows available</span></div>
                </div>
            </section>
            """
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Robot Fleet</h3>
            <table class="task9-table">
                <thead><tr><th>Robot ID</th><th>Assigned patient</th><th>Status</th><th>Battery</th><th>Location</th><th>Movement</th><th>Last sync</th><th>Sensors</th><th>Maintenance</th><th></th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </section>
        {detail_html}
    </div>
    """


def _task9_alerts_page(snapshot):
    rows = ""
    for row in snapshot["alerts"]:
        rows += (
            f'<tr><td><b>{escape(str(row["id"]))}</b></td><td>{escape(str(row["patient"]))}</td><td>{escape(str(row["robot"]))}</td>'
            f'<td><b>{escape(str(row["type"]))}</b><small>{escape(str(row["summary"]))}</small></td><td>{_task9_badge(row["severity"], _task9_status_tone(row["severity"]))}</td>'
            f'<td>{escape(str(row["time"]))}</td><td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td><td>{escape(str(row["source"]))}</td></tr>'
        )
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Alerts</h3>
            <div class="task9-actions">
                <span class="task9-action">Active</span><span class="task9-action">Resolved</span><span class="task9-action">High</span><span class="task9-action">Medium</span><span class="task9-action">Low</span>
            </div>
            <table class="task9-table">
                <thead><tr><th>Alert ID</th><th>Patient</th><th>Robot</th><th>Type</th><th>Severity</th><th>Time</th><th>Status</th><th>Source</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <div class="task9-actions"><span class="task9-action primary">Mark as reviewed</span><span class="task9-action">Resolve alert</span><span class="task9-action">Assign to support ticket</span></div>
        </section>
    </div>
    """


def _task9_telemetry_page(snapshot):
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Telemetry & Logs</h3>
            <div class="task9-actions">
                <span class="task9-action">Source collection</span><span class="task9-action">Event type</span><span class="task9-action">Patient</span><span class="task9-action">Robot</span><span class="task9-action">Date / time</span>
            </div>
            {_task9_telemetry_table(snapshot["telemetry"], limit=30)}
            <div class="task9-actions"><span class="task9-action primary">View all logs</span><span class="task9-action">View all topics</span><span class="task9-action">Export logs placeholder</span></div>
        </section>
    </div>
    """


def _task9_care_plans_page(snapshot):
    rows = ""
    for row in snapshot["care_plans"]:
        rows += (
            f'<tr><td><b>{escape(str(row["patient"]))}</b><small>{escape(str(row["id"]))}</small></td><td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td>'
            f'<td>{escape(str(row["medicine"]))}</td><td>{escape(str(row["schedule"]))}</td><td>{escape(str(row["guardian"]))}</td>'
            f'<td>{escape(str(row["support"]))}</td><td>{escape(str(row["objects"]))}</td><td>{escape(str(row["notes"]))}</td><td>{escape(str(row["updated"]))}</td></tr>'
        )
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Care Plans</h3>
            <table class="task9-table">
                <thead><tr><th>Patient</th><th>Status</th><th>Medicine routine</th><th>Reminder schedule</th><th>Guardian / Caregiver</th><th>Support needs</th><th>Important objects</th><th>Care notes</th><th>Last updated</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <div class="task9-actions"><span class="task9-action primary">View care plan</span><span class="task9-action">Update status</span><span class="task9-action">Add note</span></div>
        </section>
    </div>
    """


def _task9_reports_page(snapshot):
    cards = ""
    for row in snapshot["reports"]:
        cards += f'<div class="task9-mini-card"><b>{escape(str(row["title"]))}</b><span class="task9-muted">{escape(str(row["metric"]))}</span>{_task9_badge(row["source"], "blue")}</div>'
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Reports</h3>
            <div class="task9-report-grid">{cards}</div>
            <div class="task9-actions"><span class="task9-action primary">Generate report</span><span class="task9-action">View weekly summary</span><span class="task9-action">Export placeholder</span></div>
        </section>
    </div>
    """


def _task9_system_health_page(snapshot):
    system = snapshot["system"]
    counts = snapshot["counts"]
    mongo = system.get("mongo", {})
    cache = system.get("cache", {})
    chroma = system.get("chroma", {})
    kafka = system.get("kafka", {})
    collection_rows = ""
    for name in system.get("collections", []):
        collection_rows += f'<tr><td>{escape(str(name))}</td><td>{counts.get(name, 0)}</td><td>{_task9_badge("Detected" if counts.get(name, 0) else "Waiting", "green" if counts.get(name, 0) else "amber")}</td></tr>'
    topic_rows = ""
    kafka_runtime = kafka.get("runtime", {}) if isinstance(kafka.get("runtime", {}), dict) else {}
    producer_state = (kafka_runtime.get("producer", {}) or {}).get("status") or ("ready" if kafka.get("available") else kafka.get("status", "not_connected"))
    consumer_state = (kafka_runtime.get("consumer", {}) or {}).get("status") or ("ready" if kafka.get("available") else kafka.get("status", "not_connected"))
    bridge_state = (kafka_runtime.get("bridge", {}) or {}).get("status") or ("ready" if kafka.get("available") else kafka.get("status", "not_connected"))
    listener_state = (kafka_runtime.get("listener", {}) or {}).get("status") or ("ready" if kafka.get("available") else kafka.get("status", "not_connected"))
    kafka_state = str(kafka.get("status", "not_connected")).replace("_", " ").title()
    for topic in system.get("topics", []):
        topic_rows += f'<tr><td>{escape(str(topic))}</td><td>{_task9_badge(kafka_state, _task9_status_tone(kafka_state))}</td><td>Producer/listener readiness tracked in kafka_bridge_plan.py</td></tr>'
    webots_status = "Connected" if kafka.get("available") and bridge_state in {"running", "passed"} else ("Readable" if any(counts.get(name, 0) for name in ("robot_status", "environment_events", "scenario_events")) else "Waiting")
    dashboard_status = "Connected" if kafka.get("available") and producer_state == "passed" else ("Readable" if any(counts.get(name, 0) for name in ("scenario_events", "medicine_events", "mood_events", "alerts", "conversation_events", "caregiver_notes", "schedule_events")) else "Ready")
    profile_status = "Connected" if chroma.get("available") else "Unavailable/Fallback"
    cache_status = "Connected" if cache.get("available") else "Fallback"
    matrix_rows = "".join([
        f"<tr><td>Webots/MongoDB</td><td>MongoDB polling bridge</td><td>Kafka topic</td><td>Dashboard consumer</td><td>Redis</td><td>{_task9_badge(webots_status, _task9_status_tone(webots_status))}</td></tr>",
        f"<tr><td>Dashboard UI actions</td><td>db_queries.py + Kafka producer</td><td>Kafka topic</td><td>Dashboard consumer</td><td>Redis</td><td>{_task9_badge(dashboard_status, _task9_status_tone(dashboard_status))}</td></tr>",
        f"<tr><td>MongoDB persistent store</td><td>data_layer.py</td><td>Dashboard fallback read</td><td>Streamlit dashboard</td><td>Redis/local TTL</td><td>{_task9_badge('Connected' if mongo.get('available') else 'Unavailable', 'green' if mongo.get('available') else 'red')}</td></tr>",
        f"<tr><td>Profile/preferences</td><td>memory_store.py</td><td>ChromaDB</td><td>Dashboard/Webots memory lookup</td><td>none</td><td>{_task9_badge(profile_status, _task9_status_tone(profile_status))}</td></tr>",
        f"<tr><td>Dashboard summaries</td><td>Kafka consumer</td><td>Redis cache_layer.py</td><td>Dashboard pages</td><td>Redis</td><td>{_task9_badge(cache_status, _task9_status_tone(cache_status))}</td></tr>",
    ])
    return f"""
    <div class="task9-admin">
        <div class="task9-grid">
            <section class="task9-card span-6">
                <h3>Backend Health and Data Handoff</h3>
                <div class="task9-system-row"><span>MongoDB Atlas</span>{_task9_badge(mongo.get("status", "unavailable"), _task9_status_tone(mongo.get("status")))}</div>
                <div class="task9-system-row"><span>Database</span><b>{escape(str(mongo.get("database_name", "humanoid_assistant")))}</b></div>
                <div class="task9-system-row"><span>Redis Cache</span>{_task9_badge(cache.get("mode", "not configured"), _task9_status_tone(cache.get("mode")))}</div>
                <div class="task9-system-row"><span>ChromaDB Memory</span>{_task9_badge(f'{chroma.get("count", 0)} memories' if chroma.get("available") else "Unavailable", "green" if chroma.get("available") else "amber")}</div>
                <div class="task9-system-row"><span>Kafka Broker</span>{_task9_badge(kafka_state, _task9_status_tone(kafka_state))}</div>
                <div class="task9-system-row"><span>Kafka Producer</span>{_task9_badge(str(producer_state).replace("_", " ").title(), _task9_status_tone(producer_state))}</div>
                <div class="task9-system-row"><span>Kafka Consumer</span>{_task9_badge(str(consumer_state).replace("_", " ").title(), _task9_status_tone(consumer_state))}</div>
                <div class="task9-system-row"><span>MongoDB to Kafka Bridge</span>{_task9_badge(str(bridge_state).replace("_", " ").title(), _task9_status_tone(bridge_state))}</div>
                <div class="task9-system-row"><span>Dashboard Listener</span>{_task9_badge(str(listener_state).replace("_", " ").title(), _task9_status_tone(listener_state))}</div>
                <p class="task9-muted">MongoDB is the persistent source. The Python bridge publishes new MongoDB events to Kafka when enabled. The dashboard consumer listens to Kafka and updates Redis/latest cache keys. Dashboard pages read Redis first and fall back to MongoDB.</p>
            </section>
            <section class="task9-card span-6">
                <h3>Daniel Backend Data Source</h3>
                <div class="task9-row"><span class="task9-icon">D</span><span><b>Daniel Webots repo</b><small>https://github.com/DanielMViteri/humanoid-assistant-webots</small></span>{_task9_badge("Reference", "blue")}</div>
                <div class="task9-row"><span class="task9-icon">M</span><span><b>MongoDB database used</b><small>{escape(str(mongo.get("database_name", "humanoid_assistant")))}</small></span>{_task9_badge("Mapped", "green")}</div>
                <div class="task9-row"><span class="task9-icon">K</span><span><b>Kafka topics</b><small>{len(system.get("topics", []))} expected topic(s)</small></span>{_task9_badge(kafka_state, _task9_status_tone(kafka_state))}</div>
            </section>
            <section class="task9-card span-6">
                <h3>MongoDB Health</h3>
                <table class="task9-table"><thead><tr><th>Collection</th><th>Records</th><th>Status</th></tr></thead><tbody>{collection_rows}</tbody></table>
            </section>
            <section class="task9-card span-6">
                <h3>Kafka Topic Readiness</h3>
                <table class="task9-table"><thead><tr><th>Topic</th><th>Status</th><th>Notes</th></tr></thead><tbody>{topic_rows}</tbody></table>
            </section>
            <section class="task9-card span-12">
                <h3>Producer / Consumer Matrix</h3>
                <table class="task9-table"><thead><tr><th>Source</th><th>Producer</th><th>Topic/Target</th><th>Consumer</th><th>Cache</th><th>Status</th></tr></thead><tbody>{matrix_rows}</tbody></table>
            </section>
        </div>
    </div>
    """


def _task9_support_tickets_page(snapshot):
    rows = ""
    for row in snapshot["support_tickets"]:
        rows += (
            f'<tr><td><b>{escape(str(row["id"]))}</b></td><td>{escape(str(row["title"]))}</td><td>{escape(str(row["type"]))}</td><td>{escape(str(row["patient"]))}</td>'
            f'<td>{escape(str(row["robot"]))}</td><td>{_task9_badge(row["priority"], _task9_status_tone(row["priority"]))}</td><td>{_task9_badge(row["status"], _task9_status_tone(row["status"]))}</td>'
            f'<td>{escape(str(row["created"]))}</td><td>{escape(str(row["assigned"]))}</td></tr>'
        )
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Support Tickets</h3>
            <table class="task9-table">
                <thead><tr><th>Ticket ID</th><th>Title</th><th>Type</th><th>Patient</th><th>Robot</th><th>Priority</th><th>Status</th><th>Created</th><th>Assigned</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <div class="task9-actions"><span class="task9-action primary">Open ticket</span><span class="task9-action">Mark in progress</span><span class="task9-action">Resolve ticket</span><span class="task9-action">Link to alert</span></div>
        </section>
    </div>
    """


def _task9_settings_page(snapshot):
    cards = [
        ("Admin profile", "Provider Admin, role access, account status."),
        ("Organization settings", "NESTO Care workspace and provider ownership."),
        ("Notification settings", "Admin alert and support ticket preferences."),
        ("Integration settings", "MongoDB, Redis, ChromaDB, Kafka, and Webots handoff settings."),
        ("Data retention", "Retention placeholder for project documentation."),
        ("Access control", "Role-based access placeholder for elderly, Guardian / Caregiver, and admin users."),
        ("System preferences", "Safe product settings and consent-aware defaults."),
    ]
    html = "".join(f'<div class="task9-mini-card"><b>{escape(title)}</b><span class="task9-muted">{escape(copy)}</span></div>' for title, copy in cards)
    return f"""
    <div class="task9-admin">
        <section class="task9-card">
            <h3>Settings</h3>
            <div class="task9-settings-grid">{html}</div>
        </section>
    </div>
    """


def admin_overview():
    from data_layer import admin_dashboard_snapshot

    snapshot = admin_dashboard_snapshot()
    active_tab = _task9_active_tab()
    st.session_state["provider_tab"] = active_tab
    _render_notice()
    _render_html(_task9_styles())

    if active_tab == "overview":
        body_html = _task9_overview(snapshot)
    elif active_tab == "patients":
        body_html = _task9_patients_page(snapshot)
    elif active_tab == "guardians":
        body_html = _task9_guardians_page(snapshot)
    elif active_tab == "robot_fleet":
        body_html = _task9_robot_page(snapshot)
    elif active_tab == "alerts":
        body_html = _task9_alerts_page(snapshot)
    elif active_tab == "telemetry":
        body_html = _task9_telemetry_page(snapshot)
    elif active_tab == "care_plans":
        body_html = _task9_care_plans_page(snapshot)
    elif active_tab == "reports":
        body_html = _task9_reports_page(snapshot)
    elif active_tab == "system_health":
        body_html = _task9_system_health_page(snapshot)
    elif active_tab == "support_tickets":
        body_html = _task9_support_tickets_page(snapshot)
    elif active_tab == "settings":
        body_html = _task9_settings_page(snapshot)
    else:
        body_html = _task9_overview(snapshot)
    _render_html(_task9_shell(snapshot, active_tab, body_html))
