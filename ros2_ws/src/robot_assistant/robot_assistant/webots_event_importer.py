"""Import Webots-generated event JSONL into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from event_schema import validate_event
from mongo_client import MongoEventClient, PROJECT_ROOT, mongo_error_hint


DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "webots_humanoid_events.jsonl"


def read_events(path: Path) -> list[dict]:
    events: list[dict] = []
    if not path.exists():
        raise FileNotFoundError(f"Webots event file not found: {path}")

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        event = json.loads(line)
        errors = validate_event(event)
        if errors:
            raise ValueError(f"Invalid event on line {line_number}: {'; '.join(errors)}")
        events.append(event)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Webots humanoid sensor events into MongoDB Atlas.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Webots JSONL event file.")
    parser.add_argument("--tail", type=int, default=0, help="Only import the last N events. 0 imports all.")
    args = parser.parse_args()

    events = read_events(args.input)
    if args.tail > 0:
        events = events[-args.tail :]

    if not events:
        print(f"No events found in {args.input}")
        return 0

    try:
        mongo = MongoEventClient.from_env()
        mongo.ping()
        inserted_counts = mongo.insert_events(events)
    except Exception as exc:
        print("MongoDB import: FAILED")
        print(f"Reason: {exc.__class__.__name__}: {exc}")
        print(f"Hint: {mongo_error_hint(exc)}")
        return 1

    print(f"Imported {sum(inserted_counts.values())} Webots events into MongoDB Atlas: {inserted_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
