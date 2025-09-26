from unittest.mock import MagicMock

import pytest

import app.utils.db as db


@pytest.fixture
def metadata_mock(monkeypatch):
    metadata = MagicMock(name="metadata")
    monkeypatch.setattr(db.Base, "metadata", metadata)
    return metadata


@pytest.fixture
def engine_mock(monkeypatch):
    engine = MagicMock(name="engine")
    monkeypatch.setattr(db, "engine", engine)
    return engine


def _setup_inspect(monkeypatch, existing_tables, created_tables=None):
    existing_inspector = MagicMock(name="existing_inspector")
    existing_inspector.get_table_names.return_value = existing_tables
    created_inspector = MagicMock(name="created_inspector")
    created_inspector.get_table_names.return_value = created_tables or existing_tables

    inspect_mock = MagicMock(side_effect=[existing_inspector, created_inspector])
    monkeypatch.setattr(db, "inspect", inspect_mock)
    return inspect_mock, existing_inspector, created_inspector


def test_initialize_db_without_drop_all(monkeypatch, metadata_mock, engine_mock):
    inspect_mock, existing_inspector, created_inspector = _setup_inspect(
        monkeypatch, existing_tables=["platforms", "assets"]
    )

    db.initialize_db(drop_all=False)

    metadata_mock.drop_all.assert_not_called()
    metadata_mock.create_all.assert_called_once_with(bind=engine_mock)
    assert inspect_mock.call_count == 2
    existing_inspector.get_table_names.assert_called_once()
    created_inspector.get_table_names.assert_called_once()


def test_initialize_db_with_drop_all(monkeypatch, metadata_mock, engine_mock):
    inspect_mock, _, _ = _setup_inspect(
        monkeypatch, existing_tables=["platforms"], created_tables=["platforms"]
    )

    db.initialize_db(drop_all=True)

    metadata_mock.drop_all.assert_called_once_with(bind=engine_mock)
    metadata_mock.create_all.assert_called_once_with(bind=engine_mock)
    assert inspect_mock.call_count == 2


def test_test_connection_success(monkeypatch, engine_mock):
    connection_mock = MagicMock(name="connection")
    context_manager = MagicMock(name="context_manager")
    context_manager.__enter__.return_value = connection_mock
    context_manager.__exit__.return_value = None
    engine_mock.connect.return_value = context_manager

    monkeypatch.setattr(db, "text", lambda query: query)

    success, message = db.test_connection()

    assert success is True
    assert message == "데이터베이스 연결 성공"
    connection_mock.execute.assert_called_once_with("SELECT 1")


def test_test_connection_failure(monkeypatch, engine_mock):
    error = RuntimeError("boom")
    engine_mock.connect.side_effect = error

    logger_mock = MagicMock()
    monkeypatch.setattr(db, "logger", logger_mock)

    success, message = db.test_connection()

    assert success is False
    assert message == "데이터베이스 연결 실패: boom"
    logger_mock.error.assert_called_once()
