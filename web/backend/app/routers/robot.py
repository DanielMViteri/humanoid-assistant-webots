"""Live robot status (one robot, shared)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..nesto import data_layer

router = APIRouter(prefix="/api/robot", tags=["robot"])


@router.get("/status")
def status(claims: dict = Depends(get_current_user)):
    return data_layer.robot_status(use_live=True)
