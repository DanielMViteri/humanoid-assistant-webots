"""Import Webots-generated event JSONL into MongoDB Atlas.

Two modes:
- One-shot (default): import the whole file (or the last --tail N events) once.
- Continuous (--follow): tail the file and stream newly appended events to Atlas
  as the Webots controllers write them, so the dashboard shows live telemetry
  without re-running anything. New events are tracked by byte offset (no
  duplicates), and the follower handles the log being archived/reset.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from event_schema import validate_event
from mongo_client import MongoEventClient, PROJECT_ROOT, mongo_error_hint


DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "webots_humanoid_events.jsonl"
DEFAULT_POLL_SECONDS = 2.0

# Collections whose recent docs should carry dashboard_updated_at so the admin KPI
# dashboard's MongoDB->Dashboard and End-to-End latency segments stay live.
DASHBOARD_STAMP_COLLECTIONS = (
    "robot_status",
    "scenario_events",
    "conversation_events",
    "environment_events",
    "mood_events",
    "alerts",
    "medicine_events",
    "schedule_events",
)


def _now_ms() -> int:
    return int(time.time() * 1000)


def stamp_dashboard_updated_at(mongo: MongoEventClient, *, window_ms: int) -> int:
    """Stamp dashboard_updated_at (top-level + payload) on recently-created docs
    that do not have it yet, so the admin KPI dashboard's MongoDB->Dashboard and
    End-to-End latency segments stay live as telemetry streams in.

    Real value only: it is set to "now" (the moment the live telemetry pipeline
    surfaced the event), and only for docs whose own ``timestamp`` is within the
    recent window -- so backfilled/old events never produce inflated latencies.
    Write-once: docs that already have the field are left untouched.
    """
    now = _now_ms()
    cutoff = now - max(0, window_ms)
    query = {
        "$and": [
            {"$or": [{"dashboard_updated_at": {"$exists": False}}, {"dashboard_updated_at": None}]},
            {"timestamp": {"$gte": cutoff}},
        ]
    }
    update = {"$set": {"dashboard_updated_at": now, "payload.dashboard_updated_at": now}}
    stamped = 0
    for name in DASHBOARD_STAMP_COLLECTIONS:
        try:
            result = mongo.db[name].update_many(query, update)
            stamped += int(getattr(result, "modified_count", 0) or 0)
        except Exception:
            continue
    return stamped


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


def parse_line(line: str, skip_types: set[str]) -> dict | None:
    """Parse one JSONL line into a valid event, or None to skip it."""
    line = line.strip()
    if not line:
        return None
    try:
        event = json.loads(line)
    except Exception:
        return None
    if skip_types and event.get("event_type") in skip_types:
        return None
    if validate_event(event):
        return None
    return event


def insert_batch(mongo: MongoEventClient | None, events: list[dict], dry_run: bool) -> dict[str, int]:
    if not events:
        return {}
    if dry_run or mongo is None:
        return dict(Counter(event["event_type"] for event in events))
    return mongo.insert_events(events)


def follow_events(
    path: Path,
    mongo: MongoEventClient | None,
    *,
    poll_seconds: float,
    from_start: bool,
    skip_types: set[str],
    dry_run: bool,
    stamp_dashboard: bool = True,
    stamp_window_ms: int = 300_000,
) -> int:
    """Continuously stream newly appended events to MongoDB."""
    offset = 0 if from_start else (path.stat().st_size if path.exists() else 0)
    pending = b""
    total = 0
    verb = "would import" if dry_run else "imported"
    print(f"Following {path}")
    print(f"  starting offset={offset} bytes, poll={poll_seconds:.1f}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                if path.exists():
                    size = path.stat().st_size
                    if size < offset:  # archived / reset / truncated
                        print("Log shrank (archived or reset); restarting from the new file's start.")
                        offset = 0
                        pending = b""
                    if size > offset:
                        with path.open("rb") as handle:
                            handle.seek(offset)
                            chunk = handle.read()
                            offset = handle.tell()
                        pending += chunk
                        parts = pending.split(b"\n")
                        pending = parts.pop()  # keep any incomplete trailing line
                        events = []
                        for raw in parts:
                            event = parse_line(raw.decode("utf-8", "replace"), skip_types)
                            if event is not None:
                                events.append(event)
                        if events:
                            counts = insert_batch(mongo, events, dry_run)
                            total += sum(counts.values())
                            print(f"{verb} {sum(counts.values())} events {dict(counts)} (total {total})")
            except OSError:
                # Transient file error (e.g. Windows/OneDrive EINVAL); retry next poll.
                pass
            if stamp_dashboard and mongo is not None and not dry_run:
                try:
                    stamped = stamp_dashboard_updated_at(mongo, window_ms=stamp_window_ms)
                    if stamped:
                        print(f"stamped dashboard_updated_at on {stamped} recent docs")
                except Exception as exc:
                    print(f"  warning: dashboard stamp failed: {exc.__class__.__name__}: {exc}")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print(f"\nStopped. {verb.capitalize()} {total} events this session.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Webots humanoid sensor events into MongoDB Atlas.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Webots JSONL event file.")
    parser.add_argument("--tail", type=int, default=0, help="One-shot: only import the last N events. 0 imports all.")
    parser.add_argument("--follow", action="store_true", help="Continuously stream new events as they are appended.")
    parser.add_argument("--from-start", action="store_true", help="With --follow, also stream events already in the file.")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS, help="Polling interval for --follow.")
    parser.add_argument(
        "--skip-types",
        default="",
        help="Comma-separated event_types to skip (e.g. object_detected,object_distance_estimated,scene_described).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and count events but do not insert into MongoDB.")
    parser.add_argument("--no-dashboard-stamp", action="store_true", help="Do not stamp dashboard_updated_at on recent docs.")
    parser.add_argument("--dashboard-window-seconds", type=float, default=300.0, help="Only stamp dashboard_updated_at on docs newer than this many seconds.")
    args = parser.parse_args()

    skip_types = {token.strip() for token in args.skip_types.split(",") if token.strip()}

    mongo: MongoEventClient | None = None
    if not args.dry_run:
        try:
            mongo = MongoEventClient.from_env()
            mongo.ping()
        except Exception as exc:
            print("MongoDB import: FAILED")
            print(f"Reason: {exc.__class__.__name__}: {exc}")
            print(f"Hint: {mongo_error_hint(exc)}")
            return 1

    if args.follow:
        return follow_events(
            args.input,
            mongo,
            poll_seconds=args.poll_seconds,
            from_start=args.from_start,
            skip_types=skip_types,
            dry_run=args.dry_run,
            stamp_dashboard=not args.no_dashboard_stamp,
            stamp_window_ms=int(args.dashboard_window_seconds * 1000),
        )

    # One-shot import.
    try:
        events = read_events(args.input)
    except Exception as exc:
        print(f"Could not read events: {exc.__class__.__name__}: {exc}")
        return 1
    if args.tail > 0:
        events = events[-args.tail :]
    if skip_types:
        events = [event for event in events if event.get("event_type") not in skip_types]
    if not events:
        print(f"No events found in {args.input}")
        return 0

    try:
        counts = insert_batch(mongo, events, args.dry_run)
    except Exception as exc:
        print("MongoDB import: FAILED")
        print(f"Reason: {exc.__class__.__name__}: {exc}")
        print(f"Hint: {mongo_error_hint(exc)}")
        return 1

    verb = "Would import" if args.dry_run else "Imported"
    print(f"{verb} {sum(counts.values())} Webots events into MongoDB Atlas: {dict(counts)}")
    if mongo is not None and not args.dry_run and not args.no_dashboard_stamp:
        try:
            stamped = stamp_dashboard_updated_at(mongo, window_ms=int(args.dashboard_window_seconds * 1000))
            print(f"Stamped dashboard_updated_at on {stamped} recent docs.")
        except Exception as exc:
            print(f"Dashboard stamp failed: {exc.__class__.__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
