"""NESTO Care web API — a thin FastAPI layer over the existing nesto-dashboard
modules. The robot bridge / Webots / MongoDB are unchanged; this API writes the
same events the Streamlit app used."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, patient, robot

app = FastAPI(title="NESTO Care API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(robot.router)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "nesto-care-api", "version": app.version}
