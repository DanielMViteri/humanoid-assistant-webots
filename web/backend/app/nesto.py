"""Bridge to the existing NESTO Streamlit-era Python modules, reused as-is.

The business/data logic in ``nesto-dashboard/`` is already free of Streamlit
(db_queries, data_layer, memory_store, auth_store) or has cleanly importable
pure helpers (profile_preferences). We add that folder to sys.path and import
the modules so the FastAPI layer is a thin wrapper over the same code the
Streamlit app and the robot bridge use. No changes to those files are required.
"""
from __future__ import annotations

import sys
from pathlib import Path

# web/backend/app/nesto.py -> parents[3] == swarmsense/
SWARM_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = SWARM_ROOT / "nesto-dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

# Importing db_queries connects to MongoDB Atlas (its own load_dotenv walks up to
# swarmsense/.env). memory_store/chromadb stay lazy until first used.
import auth_store  # noqa: E402
import data_layer  # noqa: E402
import db_queries  # noqa: E402
import memory_store  # noqa: E402
import profile_preferences  # noqa: E402

__all__ = [
    "auth_store",
    "data_layer",
    "db_queries",
    "memory_store",
    "profile_preferences",
    "SWARM_ROOT",
    "DASHBOARD_DIR",
]
