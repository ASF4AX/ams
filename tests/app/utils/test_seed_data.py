"""Tests for the sample seed data helper."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest
from sqlalchemy.orm import sessionmaker

from models.models import Asset, Base, Platform, Transaction

from app.utils import db as app_utils_db

utils_module = sys.modules.get("utils")
if utils_module is None:
    utils_module = ModuleType("utils")
    sys.modules["utils"] = utils_module

utils_module.db = app_utils_db
sys.modules["utils.db"] = app_utils_db

seed_data = importlib.import_module("app.utils.seed_data")


def test_seed_database_populates_expected_entities(monkeypatch, engine):
    """Seed the database and ensure core entities are created."""

    SessionLocal = sessionmaker(bind=engine, future=True)

    def _get_session():
        return SessionLocal()

    initialize_calls: list[bool] = []

    def _initialize_db():
        initialize_calls.append(True)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(seed_data, "get_db_session", _get_session)
    monkeypatch.setattr(seed_data, "initialize_db", _initialize_db)

    seed_data.seed_database()

    session = SessionLocal()
    try:
        assert session.query(Platform).count() == 5
        assert session.query(Asset).count() == 9
        assert session.query(Transaction).count() == 14
    finally:
        session.close()

    assert initialize_calls == [True]


class _FailingSession:
    """Minimal stub that mimics SQLAlchemy session behavior."""

    def __init__(self) -> None:
        self.rollback_called = False
        self.closed = False
        self._last_added = None
        self._next_id = 1

    def add(self, obj):  # pragma: no cover - simple data container
        self._last_added = obj

    def flush(self):  # pragma: no cover - deterministic id assignment
        if self._last_added is not None and hasattr(self._last_added, "id"):
            setattr(self._last_added, "id", self._next_id)
            self._next_id += 1

    def commit(self):
        raise RuntimeError("commit failed")

    def rollback(self):  # pragma: no cover - simple flag setter
        self.rollback_called = True

    def close(self):  # pragma: no cover - simple flag setter
        self.closed = True


def test_seed_database_rolls_back_on_failure(monkeypatch):
    session = _FailingSession()

    monkeypatch.setattr(seed_data, "get_db_session", lambda: session)
    monkeypatch.setattr(seed_data, "initialize_db", lambda: None)

    with pytest.raises(RuntimeError, match="commit failed"):
        seed_data.seed_database()

    assert session.rollback_called is True
    assert session.closed is True
