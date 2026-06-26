"""
Database-backed authentication helpers for Nesto Care.

MongoDB collection: auth_users
Passwords are stored as PBKDF2-SHA256 hashes only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
from typing import Any

AUTH_COLLECTION = "auth_users"
USER_PROFILE_COLLECTION = "user_profiles"
HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 210_000
LOCAL_SEED_PASSWORD = os.getenv("NESTO_SEED_PASSWORD", "NestoCare2026!")

_LOCAL_AUTH_USERS: list[dict[str, Any]] = []
_MONGO_AVAILABLE: bool | None = None


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _split_identifier(identifier: str) -> tuple[str, str]:
    clean = str(identifier or "").strip()
    if "@" in clean:
        return clean.split("@", 1)[0].strip().lower(), clean
    return clean.lower(), ""


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        bytes.fromhex(salt),
        HASH_ITERATIONS,
    )
    return f"{HASH_ALGORITHM}${HASH_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = str(password_hash or "").split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations_text),
        ).hex()
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def _collection():
    # Re-probe the connection on every call. We deliberately do NOT latch a failed
    # probe: a single slow Atlas cold-start (TLS handshake) used to set
    # _MONGO_AVAILABLE=False permanently, which silently degraded auth to the
    # in-memory seed users (maria/anna/daniel/admintest) for the whole process --
    # so real DB-registered users (e.g. testninep) got 401 "account not found"
    # until the server was restarted. The find_one ping below is cheap when Atlas
    # is up; when it is genuinely down we simply fall back to the seed users.
    global _MONGO_AVAILABLE
    try:
        import db_queries

        collection = db_queries._db[AUTH_COLLECTION]
        collection.find_one({}, {"_id": 1})
        _MONGO_AVAILABLE = True
        return collection
    except Exception:
        _MONGO_AVAILABLE = False
        return None


def _profile_collection():
    try:
        import db_queries

        return db_queries._db[USER_PROFILE_COLLECTION]
    except Exception:
        return None


def _seed_user_docs() -> list[dict[str, Any]]:
    created_at = _now_iso()
    seed_specs = [
        {
            "user_id": "elderly_user_01",
            "username": "maria",
            "email": "maria@example.com",
            "display_name": "Maria Johnson",
            "role": "elderly_user",
            "profile_id": "elderly_user_01",
            "linked_patient_ids": [],
            "linked_patients": [],
        },
        {
            "user_id": "guardian_01",
            "username": "anna",
            "email": "anna@example.com",
            "display_name": "Anna Smith",
            "role": "guardian_caregiver",
            "profile_id": "guardian_01",
            "linked_patient_ids": ["elderly_user_01"],
            "linked_patients": [
                {"patient_id": "elderly_user_01", "patient_name": "Maria Johnson", "preferred_name": "Maria"}
            ],
            "guardian_relationship": "Daughter",
            "guardian_phone": "+44 7700 900123",
        },
        {
            "user_id": "guardian_02",
            "username": "daniel",
            "email": "daniel@example.com",
            "display_name": "Daniel Lee",
            "role": "guardian_caregiver",
            "profile_id": "guardian_02",
            "linked_patient_ids": ["elderly_user_02"],
            "linked_patients": [
                {"patient_id": "elderly_user_02", "patient_name": "Rosa Patel", "preferred_name": "Rosa"}
            ],
            "guardian_relationship": "Son",
            "guardian_phone": "+44 7700 900456",
        },
        {
            "user_id": "admin_test_001",
            "username": "admintest",
            "email": "admintest@gmail.com",
            "display_name": "NESTO Admin",
            "role": "admin_provider",
            "profile_id": "admin_test_001",
            "linked_patient_ids": [],
            "linked_patients": [],
            "seed_password": "test1234",
        },
    ]
    docs = []
    for spec in seed_specs:
        doc = dict(spec)
        seed_password = str(doc.pop("seed_password", LOCAL_SEED_PASSWORD) or LOCAL_SEED_PASSWORD)
        doc.update(
            {
                "username_normalized": _normalize(doc.get("username")),
                "email_normalized": _normalize(doc.get("email")),
                "password_hash": hash_password(seed_password),
                "status": "active",
                "created_at": created_at,
                "updated_at": created_at,
                "seeded": True,
            }
        )
        docs.append(doc)
    return docs


def ensure_seed_auth_users() -> None:
    if _LOCAL_AUTH_USERS:
        return
    seed_docs = _seed_user_docs()
    collection = _collection()
    if collection is None:
        _LOCAL_AUTH_USERS.extend(seed_docs)
        return
    try:
        for doc in seed_docs:
            exists = collection.find_one(
                {
                    "$or": [
                        {"user_id": doc["user_id"]},
                        {"username_normalized": doc["username_normalized"]},
                        {"email_normalized": doc["email_normalized"]},
                    ]
                },
                {"_id": 1},
            )
            if not exists:
                collection.insert_one(doc)
    except Exception:
        _LOCAL_AUTH_USERS.extend(seed_docs)


def _clean_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    clean = dict(user)
    clean.pop("_id", None)
    return clean


def find_auth_user(identifier: str) -> dict[str, Any] | None:
    ensure_seed_auth_users()
    ident = _normalize(identifier)
    if not ident:
        return None
    collection = _collection()
    if collection is not None:
        try:
            return _clean_user(
                collection.find_one(
                    {
                        "$or": [
                            {"username_normalized": ident},
                            {"email_normalized": ident},
                            {"username": identifier},
                            {"email": identifier},
                        ]
                    }
                )
            )
        except Exception:
            pass
    for user in _LOCAL_AUTH_USERS:
        if ident in {_normalize(user.get("username")), _normalize(user.get("email"))}:
            return dict(user)
    return None


def authenticate_user(identifier: str, password: str) -> tuple[dict[str, Any] | None, str]:
    if not str(identifier or "").strip():
        return None, "Please enter your username or email."
    if not str(password or "").strip():
        return None, "Please enter your password."
    user = find_auth_user(identifier)
    if not user:
        return None, "We could not find that account."
    if str(user.get("status", "")).lower() != "active":
        return None, "This account is not active."
    if not verify_password(password, str(user.get("password_hash", ""))):
        return None, "Password does not match."
    return user, ""


def _stable_user_id(prefix: str, identifier: str) -> str:
    ident = _normalize(identifier)
    digest = hashlib.sha1(ident.encode("utf-8")).hexdigest()[:10] if ident else dt.datetime.now().strftime("%Y%m%d%H")
    return f"{prefix}_{digest}"


def _find_existing_account(identifier: str) -> dict[str, Any] | None:
    return find_auth_user(identifier)


def _same_patient_account(user: dict[str, Any] | None, patient_id: str) -> bool:
    if not user or user.get("role") != "elderly_user":
        return False
    return patient_id in {str(user.get("user_id", "")), str(user.get("profile_id", ""))}


def _guardian_linked_to_patient(user: dict[str, Any] | None, patient_id: str) -> bool:
    if not user or user.get("role") != "guardian_caregiver":
        return False
    linked_ids = {str(item) for item in user.get("linked_patient_ids") or []}
    for item in user.get("linked_patients") or []:
        linked_ids.add(str(item.get("patient_id", "")))
    return patient_id in linked_ids


def _merge_linked_patient(user: dict[str, Any], linked_patient: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    patient_id = str(linked_patient.get("patient_id", "") or "")
    rows = []
    replaced = False
    for item in user.get("linked_patients") or []:
        current = dict(item or {})
        if str(current.get("patient_id", "")) == patient_id:
            current.update(linked_patient)
            replaced = True
        rows.append(current)
    if patient_id and not replaced:
        rows.append(dict(linked_patient))
    linked_ids = []
    for item in rows:
        value = str(item.get("patient_id", "") or "")
        if value and value not in linked_ids:
            linked_ids.append(value)
    return rows, linked_ids


def _save_auth_doc(doc: dict[str, Any], existing: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, bool, str]:
    now = _now_iso()
    doc = dict(doc)
    doc["updated_at"] = now
    collection = _collection()
    if existing:
        update = dict(doc)
        update.pop("password_hash", None)
        update.pop("created_at", None)
        if collection is not None:
            try:
                collection.update_one({"user_id": existing.get("user_id")}, {"$set": update}, upsert=False)
                merged = dict(existing)
                merged.update(update)
                return _clean_user(merged), False, ""
            except Exception:
                return None, False, "We could not update the account right now. Please try again."
        for index, item in enumerate(_LOCAL_AUTH_USERS):
            if item.get("user_id") == existing.get("user_id"):
                merged = dict(item)
                merged.update(update)
                _LOCAL_AUTH_USERS[index] = merged
                return _clean_user(merged), False, ""
        merged = dict(existing)
        merged.update(update)
        return _clean_user(merged), False, ""

    if collection is not None:
        try:
            collection.insert_one(doc)
            return _clean_user(doc), True, ""
        except Exception:
            return None, False, "We could not save the account right now. Please try again."
    _LOCAL_AUTH_USERS.append(dict(doc))
    return _clean_user(doc), True, ""


def _prepare_auth_doc(
    *,
    user_id: str,
    identifier: str,
    password: str,
    role: str,
    display_name: str,
    profile_id: str,
    linked_patients: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    username, email = _split_identifier(identifier)
    linked_patients = list(linked_patients or [])
    now = _now_iso()
    doc = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "username_normalized": _normalize(username),
        "email_normalized": _normalize(email),
        "display_name": str(display_name or username or email or user_id).strip(),
        "password_hash": hash_password(password),
        "role": role,
        "profile_id": profile_id,
        "linked_patient_ids": [str(item.get("patient_id", "")).strip() for item in linked_patients if item.get("patient_id")],
        "linked_patients": linked_patients,
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }
    doc.update(extra or {})
    return doc


def registration_errors(account_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        ("patient_identifier", "Please enter the elderly user's username or email."),
        ("patient_password", "Please enter the elderly user's password."),
        ("patient_confirm_password", "Please confirm the elderly user's password."),
        ("guardian_identifier", "Please enter the Guardian / Caregiver username or email."),
        ("guardian_password", "Please enter the Guardian / Caregiver password."),
        ("guardian_confirm_password", "Please confirm the Guardian / Caregiver password."),
    ]
    for key, message in required:
        if not str(account_data.get(key, "") or "").strip():
            errors.append(message)
    if errors:
        return errors
    for key, label in [("patient_password", "Elderly user password"), ("guardian_password", "Guardian / Caregiver password")]:
        if len(str(account_data.get(key, ""))) < 8:
            errors.append(f"{label} must be at least 8 characters.")
    if account_data.get("patient_password") != account_data.get("patient_confirm_password"):
        errors.append("Elderly user passwords do not match.")
    if account_data.get("guardian_password") != account_data.get("guardian_confirm_password"):
        errors.append("Guardian / Caregiver passwords do not match.")
    return errors


def create_accounts_for_profile(profile: dict[str, Any], account_data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors = registration_errors(account_data)
    if errors:
        return None, errors
    patient_identifier = str(account_data["patient_identifier"]).strip()
    guardian_identifier = str(account_data["guardian_identifier"]).strip()
    existing_patient = _find_existing_account(patient_identifier)
    existing_guardian = _find_existing_account(guardian_identifier)

    patient_id = str(
        profile.get("user_id")
        or profile.get("patient_id")
        or (existing_patient or {}).get("user_id")
        or _stable_user_id("elderly_user", patient_identifier)
    )
    guardian_id = str((existing_guardian or {}).get("user_id") or _stable_user_id("guardian", guardian_identifier))
    patient_name = str(profile.get("patient_name") or "Elderly user").strip()
    preferred_name = str(profile.get("preferred_name") or patient_name).strip()
    guardian_name = str(profile.get("next_of_kin_name") or profile.get("caregiver_name") or "Guardian / Caregiver").strip()
    relationship = str(profile.get("relationship") or "Guardian / Caregiver").strip()
    phone = str(profile.get("next_of_kin_phone") or "").strip()
    linked_patient = {"patient_id": patient_id, "patient_name": patient_name, "preferred_name": preferred_name}

    if existing_patient and not _same_patient_account(existing_patient, patient_id):
        return None, ["This email is already registered. Please sign in or use another email."]
    if existing_guardian and not _guardian_linked_to_patient(existing_guardian, patient_id):
        return None, ["This email is already registered. Please sign in or use another email."]

    guardian_links = [linked_patient]
    guardian_link_ids = [patient_id]
    if existing_guardian:
        guardian_links, guardian_link_ids = _merge_linked_patient(existing_guardian, linked_patient)

    patient_doc = _prepare_auth_doc(
        user_id=patient_id,
        identifier=patient_identifier,
        password=str(account_data["patient_password"]),
        role="elderly_user",
        display_name=patient_name,
        profile_id=patient_id,
        linked_patients=[],
    )
    guardian_doc = _prepare_auth_doc(
        user_id=guardian_id,
        identifier=guardian_identifier,
        password=str(account_data["guardian_password"]),
        role="guardian_caregiver",
        display_name=guardian_name,
        profile_id=guardian_id,
        linked_patients=guardian_links,
        extra={"guardian_relationship": relationship, "guardian_phone": phone},
    )
    guardian_doc["linked_patient_ids"] = guardian_link_ids

    patient_user, patient_created, error = _save_auth_doc(patient_doc, existing_patient)
    if error:
        return None, [error]
    guardian_user, guardian_created, error = _save_auth_doc(guardian_doc, existing_guardian)
    if error:
        return None, [error]

    profile_record = {
        "profile_id": patient_id,
        "user_id": patient_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "preferred_name": preferred_name,
        "guardian_user_id": guardian_id,
        "guardian_name": guardian_name,
        "guardian_relationship": relationship,
        "guardian_phone": phone,
        "auth_user_ids": [patient_id, guardian_id],
        "updated_at": _now_iso(),
        "source": "profile_registration",
        "payload": dict(profile),
    }
    collection = _profile_collection()
    if collection is not None:
        try:
            collection.update_one({"profile_id": patient_id, "source": "profile_registration"}, {"$set": profile_record}, upsert=True)
        except Exception:
            pass

    return {
        "patient_user": patient_user,
        "guardian_user": guardian_user,
        "profile_id": patient_id,
        "collection": AUTH_COLLECTION,
        "created": bool(patient_created or guardian_created),
        "status": "created" if patient_created or guardian_created else "already_saved",
    }, []


def user_session(user: dict[str, Any], active_patient_id: str = "") -> dict[str, Any]:
    linked_patients = list(user.get("linked_patients") or [])
    active_patient = None
    if active_patient_id:
        active_patient = next((item for item in linked_patients if item.get("patient_id") == active_patient_id), None)
    if active_patient is None and linked_patients:
        active_patient = linked_patients[0]
    session = {
        "user_id": user.get("user_id", ""),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "display_name": user.get("display_name") or user.get("username") or "Nesto user",
        "role": user.get("role", ""),
        "profile_id": user.get("profile_id", ""),
        "linked_patient_ids": list(user.get("linked_patient_ids") or []),
        "linked_patients": linked_patients,
        "active_patient_id": (active_patient or {}).get("patient_id", active_patient_id),
    }
    return session


def guardian_care_session_from_user(user: dict[str, Any], active_patient_id: str = "") -> dict[str, Any]:
    linked_patients = list(user.get("linked_patients") or [])
    patient = None
    if active_patient_id:
        patient = next((item for item in linked_patients if item.get("patient_id") == active_patient_id), None)
    if patient is None and linked_patients:
        patient = linked_patients[0]
    if patient is None:
        patient = {"patient_id": "elderly_user", "patient_name": "Assigned care profile", "preferred_name": "Assigned care profile"}
    session = {
        "role": "guardian_caregiver",
        "guardian_id": user.get("user_id", "guardian"),
        "guardian_name": user.get("display_name") or user.get("username") or "Guardian / Caregiver",
        "guardian_phone": user.get("guardian_phone", ""),
        "guardian_relationship": user.get("guardian_relationship", "Guardian / Caregiver"),
        "assigned_patient_id": patient.get("patient_id", ""),
        "assigned_patient_name": patient.get("patient_name") or patient.get("preferred_name") or "Assigned care profile",
        "assigned_patient_preferred_name": patient.get("preferred_name") or patient.get("patient_name") or "Assigned care profile",
        "linked_patients": linked_patients,
        "source": "database_login",
    }
    session.update(
        {
            "userName": session["guardian_name"],
            "linkedPatientId": session["assigned_patient_id"],
            "linkedPatientName": session["assigned_patient_name"],
            "linkedPatientPreferredName": session["assigned_patient_preferred_name"],
        }
    )
    return session


def get_guardian_session_by_ids(guardian_id: str, patient_id: str = "") -> dict[str, Any] | None:
    ensure_seed_auth_users()
    user = None
    collection = _collection()
    if collection is not None:
        try:
            user = _clean_user(collection.find_one({"user_id": guardian_id, "role": "guardian_caregiver"}))
        except Exception:
            user = None
    if user is None:
        for item in _LOCAL_AUTH_USERS:
            if item.get("user_id") == guardian_id and item.get("role") == "guardian_caregiver":
                user = dict(item)
                break
    if not user:
        return None
    return guardian_care_session_from_user(user, patient_id)


def apply_user_session(session_state: Any, user: dict[str, Any], active_patient_id: str = "") -> dict[str, Any]:
    session = user_session(user, active_patient_id)
    session_state["active_user_session"] = session
    session_state["active_session"] = {
        "is_authenticated": True,
        "user_id": session.get("user_id", ""),
        "email": session.get("email") or user.get("email", ""),
        "role": session.get("role", ""),
        "display_name": session.get("display_name", ""),
        "profile_id": session.get("profile_id", ""),
        "linked_patient_ids": list(session.get("linked_patient_ids") or []),
    }
    if session.get("role") == "guardian_caregiver":
        session_state["active_care_session"] = guardian_care_session_from_user(user, active_patient_id)
    return session
