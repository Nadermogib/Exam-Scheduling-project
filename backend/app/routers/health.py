"""
GET /health — simple liveness check (P0-T1).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    """Returns a 200 OK with a status payload. Used by the frontend to verify
    the backend is reachable (P0-T4) and as a deployment smoke test."""
    return JSONResponse({"status": "ok"})
