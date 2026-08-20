"""
Phase 8-B tests — print_settings SQLite persistence.

Tests:
  8B-T1  GET /api/print-settings returns None values when no settings saved yet
  8B-T2  PATCH /api/print-settings saves header_text and returns it
  8B-T3  PATCH /api/print-settings saves logo_data_url
  8B-T4  PATCH with only one field does not overwrite the other
  8B-T5  DELETE /api/print-settings/logo clears logo, header remains
  8B-T6  Settings persist (re-read from DB after writing)

All tests use a temporary SQLite DB (via env var override) to avoid
polluting the dev database.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ── Fixture: temp DB ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect SQLite to a fresh temp file for every test."""
    monkeypatch.setenv("DB_DIR", str(tmp_path))
    # Re-import database so the path is re-evaluated
    import importlib
    import app.database as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    # Also reload print_settings so it picks up the new DB path
    import app.routers.print_settings as ps_mod
    importlib.reload(ps_mod)

    yield

    # Reload again to reset module state after test
    importlib.reload(db_mod)


# ── Helper: call the router functions directly ────────────────────────────────

def _get():
    from app.routers.print_settings import _get_all
    return _get_all()

def _patch(header_text=None, logo_data_url=None):
    from app.routers.print_settings import _upsert
    if header_text is not None:
        _upsert("header_text", header_text)
    if logo_data_url is not None:
        _upsert("logo_data_url", logo_data_url)

def _delete_logo():
    from app.routers.print_settings import _delete
    _delete("logo_data_url")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_get_returns_none_when_empty():
    """8B-T1: Fresh DB returns None for both keys."""
    result = _get()
    assert result["header_text"] is None
    assert result["logo_data_url"] is None


def test_patch_saves_header_text():
    """8B-T2: Setting header_text persists and is returned."""
    _patch(header_text="جدول اختبارات الدور التكميلي للعام الجامعي 2025/2026")
    result = _get()
    assert result["header_text"] == "جدول اختبارات الدور التكميلي للعام الجامعي 2025/2026"
    assert result["logo_data_url"] is None  # other key unchanged


def test_patch_saves_logo_data_url():
    """8B-T3: Setting logo_data_url persists."""
    fake_logo = "data:image/jpeg;base64,/9j/fakebase64=="
    _patch(logo_data_url=fake_logo)
    result = _get()
    assert result["logo_data_url"] == fake_logo
    assert result["header_text"] is None


def test_patch_partial_does_not_overwrite_other_field():
    """8B-T4: Patching one field does not clear the other."""
    _patch(header_text="العنوان الأول")
    _patch(logo_data_url="data:image/jpeg;base64,abc==")
    # Now update only header — logo should survive
    _patch(header_text="العنوان الثاني")
    result = _get()
    assert result["header_text"] == "العنوان الثاني"
    assert result["logo_data_url"] == "data:image/jpeg;base64,abc=="


def test_delete_logo_clears_only_logo():
    """8B-T5: Deleting logo leaves header_text intact."""
    _patch(header_text="عنوان محفوظ", logo_data_url="data:image/jpeg;base64,xyz==")
    _delete_logo()
    result = _get()
    assert result["logo_data_url"] is None
    assert result["header_text"] == "عنوان محفوظ"


def test_settings_persist_after_reread():
    """8B-T6: Values survive a fresh _get_all() call (simulates server restart)."""
    _patch(header_text="نص ثابت", logo_data_url="data:image/png;base64,iVBORw==")
    # Simulate re-reading (new connection from DB)
    result = _get()
    assert result["header_text"] == "نص ثابت"
    assert result["logo_data_url"] == "data:image/png;base64,iVBORw=="
