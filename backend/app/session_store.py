"""
In-memory session store.

Each upload is assigned a UUID session ID. The session holds:
  - The raw parsed DataFrame
  - The validation report
  - The (optional) corrected DataFrame (after inline cell edits)

Sessions are intentionally ephemeral — they live only in process memory.
Persistence of the course-code mapping is handled separately via SQLite (database.py).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Session:
    session_id: str
    df: pd.DataFrame                  # working copy (may be edited in-place)
    validation_report: Optional[dict] = field(default=None)


# module-level dict: session_id → Session
_store: dict[str, Session] = {}


def create_session(df: pd.DataFrame) -> Session:
    sid = str(uuid.uuid4())
    session = Session(session_id=sid, df=df.copy())
    _store[sid] = session
    return session


def get_session(session_id: str) -> Optional[Session]:
    return _store.get(session_id)


def update_session_df(session_id: str, df: pd.DataFrame) -> None:
    if session_id in _store:
        _store[session_id].df = df.copy()


def delete_session(session_id: str) -> None:
    _store.pop(session_id, None)
