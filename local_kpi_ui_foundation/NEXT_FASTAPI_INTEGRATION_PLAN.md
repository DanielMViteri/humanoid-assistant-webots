# Next.js / FastAPI Integration Plan

This folder is ready to patch into Daniel's future web app once the branch is available.

## Frontend Patch

Copy these files into the future Next.js frontend:

- `AdminKpiDashboard.tsx`
- `admin_kpi_types.ts`
- `admin_kpi_api_adapter.ts`
- `admin-kpi-dashboard.css`

Keep the dashboard data prop-driven. The component should receive API results from the page layer and must not connect directly to MongoDB.

Suggested future route:

```text
/admin/kpis
```

The page should call:

```text
GET /api/admin/kpis
```

Enable polling every 30 seconds only after the real API route exists and the frontend fetch strategy is confirmed. Until then, the refresh and range controls are UI-ready but snapshot-scoped.

## Backend Patch

Use `fastapi_admin_kpis_route_draft.py` as a draft only. Add the final version inside Daniel's real FastAPI backend.

Backend requirements:

- Add read-only `GET /api/admin/kpis`.
- Keep credentials server-side only.
- Use read-only MongoDB operations only.
- Match `admin_kpi_data_contract.json`.
- Redact recent event logs.
- Do not calculate unavailable latency metrics until required timestamps are non-null and parseable.

Full latency waits on:

- `robot_action_completed_at`
- `dashboard_updated_at`

## Validation After Integration

- Dashboard route loads.
- API returns real MongoDB-derived values.
- Unavailable latency cards do not show numbers.
- Recent events are redacted.
- KPI Dashboard is the active operations sidebar item.
- The top KPI area renders as four columns by two rows on desktop.
- Collection monitor supports sorting and status filtering.
- No MongoDB writes are performed.
- No commit or push until reviewed.
