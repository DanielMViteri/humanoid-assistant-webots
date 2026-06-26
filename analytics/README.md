# NESTO MongoDB KPI Analysis

This folder contains a read-only MongoDB analysis tool for validating which telemetry KPIs are currently supported by the `humanoid_assistant` database.

It does not modify:

- MongoDB data
- event schemas
- telemetry streamers
- Webots code
- Next.js or FastAPI code
- Streamlit dashboards
- Kafka, Redis, or ChromaDB integration

## Files

- `mongo_kpi_analysis.py` - connects to MongoDB with the local `.env`, inspects collections, evaluates KPI availability, and generates reports.
- `test_kpi_formulas.py` - synthetic unit tests for latency, success-rate, percentile, and freshness formulas. It does not connect to MongoDB.
- `output/` - generated reports.

## Required Environment

Run from the app repository root with Python 3.11 and the local `.env`.

The `.env` must define either:

- `MONGODB_URI`
- `MONGO_URI`

The script never prints or exports the connection string.

## Commands

```powershell
python -m py_compile analytics/mongo_kpi_analysis.py
python -m py_compile analytics/test_kpi_formulas.py
python -m unittest analytics/test_kpi_formulas.py
python analytics/mongo_kpi_analysis.py
```

## Generated Outputs

- `analytics/output/collection_inventory.csv`
- `analytics/output/field_dictionary.csv`
- `analytics/output/kpi_availability_matrix.csv`
- `analytics/output/current_kpi_snapshot.json`
- `analytics/output/missing_telemetry_fields.md`
- `analytics/output/telemetry_dashboard_spec.md`

## KPI Availability Rule

A KPI is marked available only when MongoDB contains the required fields with usable values. If timestamps or latency fields are missing, the report says so directly instead of estimating.
