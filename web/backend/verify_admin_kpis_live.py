"""Live verification for the admin KPI route against the REAL MongoDB Atlas DB.

The sandbox used to develop this has no network route to Atlas, so run this on a
machine that can reach the cluster (the same one that runs the backend).

What it does, in order:
  1. Pings Atlas through the shared db_queries connection.
  2. Calls data_layer.admin_telemetry() once -> this PERSISTS dashboard_updated_at
     (top-level + payload) onto recent event docs, exactly as the provider
     dashboard does. Without this, MongoDB->Dashboard / End-to-End stay Unavailable.
  3. Calls the route's build_admin_kpis() (the same code GET /api/admin/kpis runs)
     and prints every latency segment with real numbers or "Unavailable".

Usage (from web/backend, in the backend venv):
    python verify_admin_kpis_live.py

For the full authenticated HTTP path (admin_provider sign-in), see the curl block
printed at the end, or README notes.
"""
from __future__ import annotations

import pathlib
import sys

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.nesto import data_layer, db_queries  # noqa: E402  (loads swarmsense/.env + Atlas)
from app.routers.admin import build_admin_kpis  # noqa: E402


def main() -> int:
    if getattr(db_queries, "_client_init_error", None):
        print("Atlas connection FAILED:", db_queries._client_init_error)
        return 1
    try:
        db_queries._db.client.admin.command("ping")
    except Exception as exc:
        print("Atlas ping FAILED:", type(exc).__name__, exc)
        return 1
    print(f"Atlas OK -> database '{db_queries._db.name}'")

    # Persist dashboard_updated_at on recent docs (provider-dashboard behaviour).
    rows = data_layer.admin_telemetry(limit=200)
    print(f"admin_telemetry() formatted {len(rows)} rows (dashboard_updated_at persisted where missing)")

    data = build_admin_kpis()

    print("\nLatency segments (real values only):")
    print(f"  {'stage':24} {'status':12} {'samples':>7}  {'median_ms':>10}")
    for seg in data["latency"]["segments"]:
        print(f"  {seg['stage']:24} {seg['status']:12} {str(seg['samples']):>7}  {str(seg['median_ms']):>10}")

    print("\nLatency top KPIs:")
    for k in data["top_kpis"]:
        if k["target"] == "latency":
            print(f"  {k['label']:26} {k['status']:12} {k['value']}")

    # A segment is "computable" if it produced a real median -- that includes
    # Partial (some sampled docs lack the field, but a real value exists).
    computable = [s["stage"] for s in data["latency"]["segments"] if s.get("median_ms") is not None]

    print("\nPer-field presence (present / parseable) on sampled docs:")
    parse = data["latency"].get("parseability", {}) or {}
    for field in [
        "ui_triggered_at", "backend_received_at", "bridge_received_at",
        "robot_action_started_at", "robot_action_completed_at",
        "mongodb_logged_at", "dashboard_updated_at",
    ]:
        info = parse.get(field, {}) if isinstance(parse.get(field), dict) else {}
        print(f"  {field:26} present={str(info.get('present')):5} parseable={info.get('parseable')}")

    print(f"\nComputable segments now: {computable or 'none'}")
    print(f"daniel_filter_matches={data['daniel_filter_matches']}  total_documents={data['total_documents']}")
    print("safety.writes_performed:", data["safety"]["writes_performed"], "(route stays read-only)")
    if computable:
        print("\nPASS: latency segments compute real values from live Atlas data.")
        print("Still-blocked segments need: robot_action_completed_at (robot must finish)")
        print("and dashboard_updated_at (run the telemetry streamer with --follow).")
        return 0
    print("\nNo segments computed yet. Generate a FRESH command end-to-end:")
    print("  1) start Webots (nao_assistant_supervisor) + dashboard_command_bridge")
    print("  2) trigger Find My Cane / Find My Medicine from the patient UI")
    print("  3) run the telemetry streamer: tools\\run_telemetry_streamer.cmd")
    print("  4) re-run this script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
