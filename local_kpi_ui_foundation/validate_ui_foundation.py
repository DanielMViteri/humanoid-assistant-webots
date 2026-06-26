from __future__ import annotations

import json
import re
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent

REQUIRED_FILES = [
    "README.md",
    "MOHAMMAD_DANIEL_REQUIREMENTS.md",
    "real_analysis_snapshot.json",
    "admin_kpi_dashboard_ui.html",
    "admin-kpi-dashboard.css",
    "admin-kpi-dashboard.js",
    "admin_kpi_data_contract.json",
    "admin_kpi_types.ts",
    "AdminKpiDashboard.tsx",
    "admin_kpi_api_adapter.ts",
    "fastapi_admin_kpis_route_draft.py",
    "NEXT_FASTAPI_INTEGRATION_PLAN.md",
    "validate_ui_foundation.py",
]

REQUIRED_KPIS = [
    "Pipeline Status",
    "End-to-End Latency",
    "MongoDB Write Latency",
    "Dashboard Refresh Latency",
    "Event Success Rate",
    "Last Robot Action",
    "Active Collections",
    "Failed Events",
]

REQUIRED_SECTIONS = [
    "Pipeline Health Overview",
    "Latency KPIs",
    "Event Throughput and Success Rate",
    "Robot Action Status",
    "MongoDB Sync Monitor",
    "Recent Event Logs",
    "Missing Telemetry Fields",
]

UNRELATED_GUARDIAN_CONTENT = [
    "Loved Ones",
    "Active Alerts as guardian metric",
    "Messages",
    "Care Tasks",
    "Wellbeing Score",
    "My Loved Ones",
    "Upcoming Care Reminders",
]

UNRELATED_OPERATIONS_KPIS = [
    "Robots Online",
    "Patients Registered",
    "Battery Health",
    "Mood and Medication Trends",
    "Object Detection",
    "Live Robot Status",
]

INTERACTIVE_CONTROLS = {
    "refresh button": "data-refresh-button",
    "auto refresh control": "data-auto-refresh",
    "time range selector": "data-range-select",
    "recent logs search": "data-log-search",
    "collection filter": "data-collection-filter",
    "missing telemetry expander": "data-expand-missing",
}

PROHIBITED_WORDING = [
    "mock",
    "fake",
    "demo data",
    "placeholder data",
]

SECRET_PATTERNS = [
    "mongodb+srv",
    "MONGO_URI",
    "password",
    "secret",
    "api_key",
]

CONTRACT_KEYS = [
    "generated_at",
    "database",
    "source",
    "pipeline_status",
    "top_kpis",
    "latency",
    "event_success_rate",
    "last_robot_action",
    "active_collections",
    "failed_events",
    "mongo_sync",
    "recent_events",
    "missing_telemetry_fields",
    "nlp_guardrails",
    "safety",
]

ROUTE_FORBIDDEN_PATTERNS = [
    r"\.insert_one\s*\(",
    r"\.insert_many\s*\(",
    r"\.update_one\s*\(",
    r"\.update_many\s*\(",
    r"\.delete_one\s*\(",
    r"\.delete_many\s*\(",
    r"\.replace_one\s*\(",
    r"\.bulk_write\s*\(",
    r'"\$out"',
    r'"\$merge"',
    r"'\$out'",
    r"'\$merge'",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def read_text(name: str) -> str:
    return (BASE / name).read_text(encoding="utf-8")


def main() -> int:
    missing = [name for name in REQUIRED_FILES if not (BASE / name).exists()]
    if missing:
        fail(f"Missing required files: {missing}")

    html = read_text("admin_kpi_dashboard_ui.html")
    css = read_text("admin-kpi-dashboard.css")
    js = read_text("admin-kpi-dashboard.js")
    route = read_text("fastapi_admin_kpis_route_draft.py")
    snapshot = json.loads(read_text("real_analysis_snapshot.json"))
    contract = json.loads(read_text("admin_kpi_data_contract.json"))

    if "NESTO Care Operations" not in html:
        fail("HTML missing NESTO Care Operations title.")

    if "KPI Dashboard" not in html:
        fail("HTML missing KPI Dashboard label.")

    active_links = re.findall(r'<a[^>]*class="nav-link active"[^>]*>([\s\S]*?)</a>', html)
    active_text = " ".join(re.sub(r"<[^>]+>", " ", link) for link in active_links)

    if "KPI Dashboard" not in active_text:
        fail("Sidebar active item is not KPI Dashboard.")

    if "Overview" in active_text:
        fail("Overview is incorrectly marked as the active sidebar item.")

    for kpi in REQUIRED_KPIS:
        if kpi not in html:
            fail(f"HTML missing KPI card name: {kpi}")

    for section in REQUIRED_SECTIONS:
        if section not in html:
            fail(f"HTML missing required section: {section}")

    for control_name, marker in INTERACTIVE_CONTROLS.items():
        if marker not in html:
            fail(f"HTML missing interactive control: {control_name}")

    for widget in UNRELATED_GUARDIAN_CONTENT + UNRELATED_OPERATIONS_KPIS:
        if widget in html:
            fail(f"HTML contains unrelated dashboard content: {widget}")

    combined_ui = "\n".join([html, css, js])
    lower_ui = combined_ui.lower()
    for wording in PROHIBITED_WORDING:
        if wording in lower_ui:
            fail(f"UI contains prohibited wording: {wording}")

    for pattern in SECRET_PATTERNS:
        if re.search(re.escape(pattern), combined_ui, flags=re.IGNORECASE):
            fail(f"UI contains prohibited secret pattern: {pattern}")

    if "window.ADMIN_KPI_SNAPSHOT" not in html or "window.ADMIN_KPI_SNAPSHOT" not in js:
        fail("Embedded snapshot is not used by HTML and JS.")

    if "window.location.protocol" not in js:
        fail("JS does not check window.location.protocol before fetching.")

    if 'window.location.protocol === "file:"' not in js and "window.location.protocol === 'file:'" not in js:
        fail("JS does not explicitly skip fetch on file protocol.")

    fetch_index = js.find("fetch(")
    protocol_index = js.find("window.location.protocol")
    if fetch_index != -1 and (protocol_index == -1 or protocol_index > fetch_index):
        fail("JS appears to fetch before checking protocol.")

    if "top-kpi-grid" not in css or "grid-template-columns: repeat(4" not in css:
        fail("CSS does not define the required four-column top KPI grid.")

    for field in ["robot_action_completed_at", "dashboard_updated_at"]:
        if field not in html or field not in json.dumps(snapshot):
            fail(f"Missing telemetry field not listed: {field}")

    if '"label": "Event Success Rate"' not in html or '"status": "Partial"' not in html:
        fail("Event Success Rate is not visibly marked Partial in embedded snapshot.")

    for label in ["End-to-End Latency", "MongoDB Write Latency", "Dashboard Refresh Latency"]:
        if label not in html:
            fail(f"Missing unavailable latency KPI: {label}")

    top_kpis = {item["label"]: item for item in snapshot.get("top_kpis", [])}
    for label in ["End-to-End Latency", "MongoDB Write Latency", "Dashboard Refresh Latency"]:
        if top_kpis.get(label, {}).get("status") != "Unavailable":
            fail(f"{label} is not unavailable in real_analysis_snapshot.json")

    if top_kpis.get("Event Success Rate", {}).get("status") != "Partial":
        fail("Event Success Rate is not Partial in real_analysis_snapshot.json")

    safety = snapshot.get("safety", {})
    if safety.get("read_only") is not True:
        fail("real_analysis_snapshot safety.read_only is not true")
    if safety.get("writes_performed") is not False:
        fail("real_analysis_snapshot safety.writes_performed is not false")
    if safety.get("credentials_redacted") is not True:
        fail("real_analysis_snapshot safety.credentials_redacted is not true")

    for key in CONTRACT_KEYS:
        if key not in contract:
            fail(f"admin_kpi_data_contract.json missing top-level key: {key}")

    for pattern in ROUTE_FORBIDDEN_PATTERNS:
        if re.search(pattern, route):
            fail(f"Draft FastAPI route contains write/persist operation pattern: {pattern}")

    if "--nesto-cream" not in css or "--nesto-forest" not in css or "--nesto-green" not in css:
        fail("CSS missing required NESTO palette variables.")

    for required_variable in [
        "--nesto-cream-soft",
        "--nesto-green-deep",
        "--nesto-sage",
        "--nesto-mint",
        "--nesto-amber",
        "--nesto-red",
        "--nesto-gray",
        "--nesto-blue",
        "--card-border",
        "--shadow-soft",
    ]:
        if required_variable not in css:
            fail(f"CSS missing required NESTO palette variable: {required_variable}")

    print("PASS: UI foundation validation passed.")
    print(f"Checked files: {len(REQUIRED_FILES)}")
    print("Validated KPI cards, sections, excluded widgets, safety flags, data contract, and draft route.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
