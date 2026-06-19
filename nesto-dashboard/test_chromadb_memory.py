"""
Terminal proof for NESTO ChromaDB profile and object memory.

This script is intentionally backend-facing. Normal dashboard users do not see
these details; Daniel can run it to verify profile/preferences and object
memory save/read behavior.
"""

from __future__ import annotations

from pprint import pformat

import memory_store


PROOF_USER_ID = "elderly_user_01"


def main() -> None:
    print("NESTO CHROMADB MEMORY PROOF")
    print()

    status = memory_store.get_chromadb_status()
    print("ChromaDB status:")
    print(pformat(status, sort_dicts=False))
    print(f"CHROMADB STATUS: {'connected' if status.get('available') else 'unavailable'}")
    print()

    profile_payload = {
        "user_id": PROOF_USER_ID,
        "full_name": "Connection Proof User",
        "preferred_name": "Proof User",
        "robot_name": "Nesto",
        "guardian_contact": {
            "name": "Proof Guardian",
            "relationship": "Guardian / Caregiver",
            "phone": "+44 7700 900123",
            "role": "Guardian / Caregiver",
        },
        "medicine_schedule": [{"medicine_name": "Morning medicine", "scheduled_time": "09:00"}],
        "preferences": {
            "important_object": "cane",
            "preferred_language": "English",
            "tone": "Calm and direct",
        },
    }

    profile_save = memory_store.save_profile_memory(profile_payload)
    print("Profile memory save:")
    print(pformat(profile_save, sort_dicts=False))
    print(f"PROFILE MEMORY SAVE: {'passed' if profile_save.get('connected') else 'failed'}")
    print()

    profile_read = memory_store.read_profile_memory(PROOF_USER_ID)
    print("Profile memory read:")
    print(pformat(profile_read, sort_dicts=False))
    print(f"PROFILE MEMORY READ: {'passed' if profile_read.get('status') == 'found' else 'failed'}")
    print()

    cane_save = memory_store.save_object_memory(
        PROOF_USER_ID,
        "cane",
        "living room beside the sofa",
        metadata={"source": "test_chromadb_memory.py", "proof": True},
    )
    print("Object memory save: cane")
    print(pformat(cane_save, sort_dicts=False))
    print(f"OBJECT MEMORY SAVE CANE: {'passed' if cane_save.get('connected') else 'failed'}")
    print()

    cane_read = memory_store.read_object_memory(PROOF_USER_ID, "cane")
    print("Object memory read: cane")
    print(pformat(cane_read, sort_dicts=False))
    print(f"OBJECT MEMORY READ CANE: {'passed' if cane_read.get('status') == 'found' else 'failed'}")
    print()

    medicine_save = memory_store.save_object_memory(
        PROOF_USER_ID,
        "medicine box",
        "kitchen counter",
        metadata={"source": "test_chromadb_memory.py", "proof": True, "webots_write_example": True},
    )
    medicine_read = memory_store.read_object_memory(PROOF_USER_ID, "medicine box")
    print("Object memory save/read: medicine box")
    print(pformat({"save": medicine_save, "read": medicine_read}, sort_dicts=False))
    print(f"OBJECT MEMORY MEDICINE BOX: {'passed' if medicine_save.get('connected') and medicine_read.get('status') == 'found' else 'failed'}")
    print()

    robot_save = memory_store.save_object_memory(
        PROOF_USER_ID,
        "robot location",
        "living room charging area",
        metadata={"source": "test_chromadb_memory.py", "proof": True, "memory_kind": "robot_mapping"},
    )
    robot_read = memory_store.read_object_memory(PROOF_USER_ID, "robot location")
    print("Robot mapping/location memory save/read:")
    print(pformat({"save": robot_save, "read": robot_read}, sort_dicts=False))
    print(f"ROBOT LOCATION MEMORY: {'passed' if robot_save.get('connected') and robot_read.get('status') == 'found' else 'failed'}")
    print()

    if (
        status.get("available")
        and profile_save.get("connected")
        and profile_read.get("status") == "found"
        and cane_save.get("connected")
        and cane_read.get("status") == "found"
        and medicine_save.get("connected")
        and medicine_read.get("status") == "found"
        and robot_save.get("connected")
        and robot_read.get("status") == "found"
    ):
        print("CHROMADB PROOF PASSED")
    else:
        print("CHROMADB UNAVAILABLE OR FALLBACK: proof reported honestly above.")


if __name__ == "__main__":
    main()
