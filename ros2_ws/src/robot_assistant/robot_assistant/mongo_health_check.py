"""MongoDB Atlas health check for Clara's Sprint 2 reporting."""

from __future__ import annotations

from datetime import datetime, timezone

from event_schema import COLLECTIONS
from mongo_client import MongoEventClient


def format_epoch_ms(value: int | None) -> str:
    if value is None:
        return "no records"
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def main() -> int:
    try:
        mongo = MongoEventClient.from_env()
        mongo.ping()
    except Exception as exc:
        print("MongoDB connection: FAILED")
        print(f"Reason: {exc}")
        return 1

    print("MongoDB connection: OK")
    print(f"Database: {mongo.database_name}")

    counts = mongo.collection_counts()
    latest = mongo.latest_timestamps()
    missing = mongo.missing_required_field_counts()

    print("\nCollection health")
    for collection in COLLECTIONS:
        print(
            f"- {collection}: "
            f"records={counts[collection]}, "
            f"latest_timestamp={format_epoch_ms(latest[collection])}, "
            f"missing_required_fields={missing[collection]}"
        )

    total_missing = sum(missing.values())
    if total_missing:
        print(f"\nRequired field check: FAILED ({total_missing} records have missing required fields)")
        return 1

    print("\nRequired field check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
