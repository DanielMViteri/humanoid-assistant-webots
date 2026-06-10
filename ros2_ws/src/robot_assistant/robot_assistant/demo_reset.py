"""Backup and reset MongoDB demo collections for a clean class demo."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from event_schema import COLLECTIONS
from mongo_client import MongoEventClient, PROJECT_ROOT, mongo_error_hint


DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "processed" / "mongo_backups"


def json_safe(value: Any) -> Any:
    """Convert MongoDB-specific values into JSON-safe values."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "binary") and hasattr(value, "generation_time"):
        return str(value)
    return value


def backup_collections(mongo: MongoEventClient, backup_dir: Path = DEFAULT_BACKUP_DIR) -> tuple[Path, dict[str, int]]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"humanoid_assistant_backup_{timestamp}.json"

    backup: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for collection in COLLECTIONS:
        documents = list(mongo.db[collection].find({}))
        backup[collection] = [json_safe(document) for document in documents]
        counts[collection] = len(documents)

    backup_path.write_text(json.dumps(backup, indent=2), encoding="utf-8")
    return backup_path, counts


def clear_collections(mongo: MongoEventClient) -> dict[str, int]:
    deleted_counts: dict[str, int] = {}
    for collection in COLLECTIONS:
        result = mongo.db[collection].delete_many({})
        deleted_counts[collection] = result.deleted_count
    return deleted_counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup then reset MongoDB demo collections.")
    parser.add_argument("--backup-only", action="store_true", help="Create a backup without deleting records.")
    parser.add_argument("--yes", action="store_true", help="Skip the RESET confirmation prompt.")
    args = parser.parse_args()

    try:
        mongo = MongoEventClient.from_env()
        mongo.ping()
    except Exception as exc:
        print("MongoDB connection: FAILED")
        print(f"Reason: {exc.__class__.__name__}: {exc}")
        print(f"Hint: {mongo_error_hint(exc)}")
        return 1

    backup_path, counts = backup_collections(mongo)
    print(f"Backup written to: {backup_path}")
    print(f"Backed up records: {counts}")

    if args.backup_only:
        print("Backup-only mode complete. No records were deleted.")
        return 0

    if not args.yes:
        confirmation = input("Type RESET to clear MongoDB demo collections: ").strip()
        if confirmation != "RESET":
            print("Reset cancelled. Backup was kept; MongoDB data was not deleted.")
            return 0

    deleted_counts = clear_collections(mongo)
    print(f"Deleted records: {deleted_counts}")
    print("Demo collections are now clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
