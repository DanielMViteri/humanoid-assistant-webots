"""One-time demo data fix: reset the elderly_user_01 patient profile.

Both the seeded `maria` account and self-registered patient accounts resolve to
the shared profile id `elderly_user_01`. An earlier test run saved a profile
whose name / robot_name / important_object are all "test", so the patient portal
renders "Good day, test", "Talk to test", "Find My test", etc.

This script writes a clean `user_profiles` document (correct shape, newest
timestamp so it wins the most-recent sort) and removes the stale ones. It uses
the app's own MongoDB handle, so it talks to the same Atlas the dashboard uses.

Run from the repo root with the main venv (which has the Atlas URI / dnspython):

    .venv\\Scripts\\python.exe tools\\fix_demo_profile.py

Optional overrides:
    --preferred-name Maria --robot-name Nesto --important-object cane \
    --guardian-name "Anna Smith" --relationship Daughter --phone "+44 7700 900123" \
    --medicine-name "Morning medicine" --medicine-time "09:00 AM" --user-id elderly_user_01
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DASH_DIR = REPO_ROOT / "nesto-dashboard"
sys.path.insert(0, str(DASH_DIR))
os.chdir(DASH_DIR)  # so db_queries' find_dotenv walks up to swarmsense\.env (Atlas)


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset a demo patient profile in MongoDB.")
    ap.add_argument("--user-id", default="elderly_user_01")
    ap.add_argument("--preferred-name", default="Maria")
    ap.add_argument("--full-name", default="Maria Johnson")
    ap.add_argument("--robot-name", default="Nesto")
    ap.add_argument("--important-object", default="cane")
    ap.add_argument("--medicine-name", default="Morning medicine")
    ap.add_argument("--medicine-time", default="09:00 AM")
    ap.add_argument("--guardian-name", default="Anna Smith")
    ap.add_argument("--relationship", default="Daughter")
    ap.add_argument("--phone", default="+44 7700 900123")
    ap.add_argument("--keep-old", action="store_true", help="Do not delete stale profile docs.")
    args = ap.parse_args()

    import db_queries

    db = db_queries._db
    if db is None:
        print("ERROR: MongoDB handle is not initialised. Check .env / Atlas connectivity.")
        return 1

    uid = args.user_id
    now_ms = int(time.time() * 1000)
    now_iso = datetime.now(timezone.utc).isoformat()

    match = {
        "$or": [
            {"user_id": uid},
            {"patient_id": uid},
            {"profile_id": uid},
            {"event_id": f"profile_{uid}"},
            {"payload.user_id": uid},
            {"payload.patient_id": uid},
        ]
    }

    payload = {
        "user_id": uid,
        "full_name": args.full_name,
        "preferred_name": args.preferred_name,
        "robot_name": args.robot_name,
        "robot_id": "H1",
        "guardian_contact": {
            "name": args.guardian_name,
            "relationship": args.relationship,
            "phone": args.phone,
            "caregiver_name": args.guardian_name,
            "role": "Guardian / Caregiver",
        },
        "medicine_routine": [
            {"medicine_name": args.medicine_name, "dose": "", "frequency": "", "reminder_time": args.medicine_time}
        ],
        "preferences": {
            "important_object": args.important_object,
            "nesto_tone": "",
            "preferred_language": "",
            "care_notes": "",
        },
        "consent": {"terms_accepted": True, "privacy_accepted": True, "consent_checklist_accepted": True, "accepted_at": now_iso},
    }
    doc = {
        "event_id": f"profile_{uid}",
        "event_type": "user_profile_updated",
        "user_id": uid,
        "patient_id": uid,
        "profile_id": uid,
        "timestamp": now_ms,
        "updated_at": now_iso,
        "source": "fix_demo_profile",
        "payload": payload,
    }

    coll = db["user_profiles"]
    existing = coll.count_documents(match)
    print(f"Found {existing} existing user_profiles doc(s) for {uid}.")

    if not args.keep_old:
        deleted = coll.delete_many(match).deleted_count
        print(f"Deleted {deleted} stale doc(s).")

    coll.insert_one(doc)
    print(
        "Inserted clean profile -> "
        f"name={args.preferred_name!r}, robot={args.robot_name!r}, object={args.important_object!r}, "
        f"guardian={args.guardian_name!r}."
    )
    print("Done. Reload the patient portal (it reads live).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
