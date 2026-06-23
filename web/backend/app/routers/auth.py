"""Unified login + current-user, reusing auth_store (PBKDF2 + user roles)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_current_user
from ..nesto import auth_store
from ..security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    identifier: str
    password: str


def _public_user(session: dict) -> dict:
    role = session.get("role", "")
    if role == "elderly_user":
        patient_id = session.get("user_id")
    else:
        patient_id = session.get("active_patient_id") or next(iter(session.get("linked_patient_ids") or []), None)
    return {
        "id": session.get("user_id"),
        "name": session.get("display_name"),
        "role": role,
        "patient_id": patient_id,
        "linked_patients": session.get("linked_patients", []),
    }


@router.post("/login")
def login(body: LoginBody):
    user, error = auth_store.authenticate_user(body.identifier, body.password)
    if not user:
        raise HTTPException(status_code=401, detail=error or "Login failed")
    pub = _public_user(auth_store.user_session(user))
    token = create_access_token(
        {"sub": pub["id"], "role": pub["role"], "name": pub["name"], "patient_id": pub["patient_id"]}
    )
    return {"access_token": token, "token_type": "bearer", "user": pub}


@router.get("/me")
def me(claims: dict = Depends(get_current_user)):
    return {
        "id": claims.get("sub"),
        "name": claims.get("name"),
        "role": claims.get("role"),
        "patient_id": claims.get("patient_id"),
    }
