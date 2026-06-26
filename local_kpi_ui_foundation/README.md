# Admin KPI Dashboard UI Foundation

This folder contains the portable UI foundation for the NESTO Care Operations Admin KPI Dashboard on the `leona-nesto-dashboard-integration` branch. It is not the final integrated app and it is not connected to the old Streamlit dashboard.

The files live in this repository until the final Next.js/FastAPI frontend branch is ready for direct integration with a read-only API route.

## Scope

- UI foundation only.
- Real read-only MongoDB analysis snapshots only.
- No invented KPI values.
- No invented latency values.
- No MongoDB writes.
- No production app integration.
- No Streamlit fallback.
- No direct MongoDB connection from the frontend package.

## Source Snapshot

This foundation uses the local read-only analysis outputs where available:

```text
analytics/output/telemetry_field_check.json
analytics/output/latency_kpi_preview.json
analytics/output/current_kpi_snapshot.json
analytics/output/missing_telemetry_fields.md
```

The cleaned aggregate snapshot is stored in:

```text
local_kpi_ui_foundation/real_analysis_snapshot.json
```

The source is labelled:

```text
real_read_only_analysis_snapshot
```

## Mohammad KPI Requirements Covered

The UI follows the requested NESTO palette and shows the required KPI cards:

- Pipeline Status
- End-to-End Latency
- MongoDB Write Latency
- Dashboard Refresh Latency
- Event Success Rate
- Last Robot Action
- Active Collections
- Failed Events

The UI uses real MongoDB-derived values only. When a latency value cannot be calculated from complete timestamp pairs, it is shown as unavailable or waiting for telemetry.

The corrected UI now follows the approved operations-dashboard style:

- NESTO Care Operations header.
- KPI Dashboard active sidebar item with `NEW` badge.
- Two-row top KPI card grid.
- Service chips for MongoDB, Kafka, Redis, and ChromaDB.
- Interactive refresh control, range selector, collection filter, sortable collection table, recent logs search, expandable missing telemetry panel, and KPI-card section jumps.
- Embedded `window.ADMIN_KPI_SNAPSHOT` first, with HTTP JSON loading when served locally.

## Daniel MongoDB Analysis Requirements Covered

The UI includes Daniel's MongoDB verification findings:

- Database: `humanoid_assistant`
- Daniel filter matched `79` documents.
- Required timestamp fields are top-level only.
- No nested `timestamps.*` fields were found.
- `robot_action_completed_at` is present but null / not parseable where present.
- `dashboard_updated_at` is present but null / not parseable where present.

These two fields block full latency calculation.

## NLP Guardrails Note

NLP guardrails are documented as task-focused LLM instructions. They are not separately telemetry-validated in this dashboard snapshot, so the UI does not claim a live guardrails monitor.

## Open Locally

You can open the static dashboard directly:

```text
local_kpi_ui_foundation/admin_kpi_dashboard_ui.html
```

From the repository root, for the most reliable browser behavior, serve the folder locally:

```powershell
cd local_kpi_ui_foundation
python -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/admin_kpi_dashboard_ui.html
```

The page embeds the same sanitized snapshot as `window.ADMIN_KPI_SNAPSHOT`, so it can render when opened directly from disk. When served through a local HTTP server, it also attempts to load `real_analysis_snapshot.json`.

## Validate

Run:

```powershell
python local_kpi_ui_foundation/validate_ui_foundation.py
```

The validator checks required files, KPI names, sections, interactive controls, the KPI Dashboard active state, direct-file loading safety, missing telemetry fields, unavailable states, safety flags, excluded unrelated widgets, and draft FastAPI read-only guardrails.

## Future Next.js/FastAPI Patch

Frontend:

- Copy `AdminKpiDashboard.tsx`.
- Copy `admin_kpi_types.ts`.
- Copy `admin_kpi_api_adapter.ts`.
- Copy `admin-kpi-dashboard.css`.
- Add a future route such as `/admin/kpis`.

Backend:

- Add `GET /api/admin/kpis` in FastAPI.
- Keep credentials server-side only.
- Use read-only MongoDB operations only.
- Match `admin_kpi_data_contract.json`.
- Redact recent event rows.

No MongoDB writes are performed by this UI foundation.
