"""
Exam Scheduling System — FastAPI Backend
Entry point. All routes are registered here; logic lives in sub-modules.

Hardening (P7-T8):
  - File size limit via MAX_UPLOAD_BYTES env var (default 20 MB)
  - All API errors return structured JSON — no HTML stack traces
  - ALLOWED_ORIGINS env var controls CORS (change to move to a hosted server)
  - VITE_API_BASE_URL on the frontend mirrors this (no code edits needed)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.routers import health, db_status, upload, graph, schedule, export, reference, print_settings


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB on startup."""
    init_db()
    yield


app = FastAPI(
    title="Exam Scheduling System API",
    version="0.3.0",
    description="Conflict-free exam timetabling system for supplementary exams.",
    lifespan=lifespan,
    # Disable default HTML exception pages — all errors are JSON
    docs_url="/docs",
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# CORS — read from env var so moving to a hosted server requires only an
# environment change, no code edits. (AQ-4 / P7-T8)
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# File-size limit middleware (P7-T8 — configurable via MAX_UPLOAD_BYTES)
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))  # 20 MB default


@app.middleware("http")
async def enforce_upload_size(request: Request, call_next):
    """Reject requests with Content-Length above MAX_UPLOAD_BYTES."""
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "REQUEST_TOO_LARGE",
                    "detail": f"حجم الملف يتجاوز الحد المسموح ({MAX_UPLOAD_BYTES // (1024*1024)} ميغابايت).",
                    "max_bytes": MAX_UPLOAD_BYTES,
                },
            )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Structured JSON error handlers (P7-T7 / P7-T8) — no HTML stack traces
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Flatten pydantic validation errors into a readable Arabic-friendly format
    errors = [
        {"field": " → ".join(str(l) for l in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "detail": "طلب غير صالح — تحقق من البيانات المرسلة.",
            "fields": errors,
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all: never expose a traceback to the client."""
    import logging
    logging.getLogger("uvicorn.error").exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "detail": "حدث خطأ داخلي في الخادم. يُرجى المحاولة مجدداً.",
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(db_status.router)
app.include_router(upload.router)
app.include_router(graph.router)
app.include_router(schedule.router)
app.include_router(export.router)
app.include_router(reference.router)
app.include_router(print_settings.router)
