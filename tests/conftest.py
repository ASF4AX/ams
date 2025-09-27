"""Global pytest fixtures for the AMS test-suite."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest
import sqlalchemy
from sqlalchemy import create_engine as sqla_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

_REAL_CREATE_ENGINE = sqla_create_engine


def _postgres_to_sqlite_engine(url: str, *args, **kwargs):
    """Route PostgreSQL URLs to an in-memory SQLite engine."""

    if url.startswith("postgresql"):
        return _REAL_CREATE_ENGINE(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _REAL_CREATE_ENGINE(url, *args, **kwargs)


sqlalchemy.create_engine = _postgres_to_sqlite_engine
sqlalchemy.engine.create_engine = _postgres_to_sqlite_engine

from models.models import (
    Asset,
    Base,
    DailyAssetMetrics,
    ExchangeRate,
    Platform,
    StableCoin,
    Transaction,
)

# Provide sensible defaults for database configuration to avoid accidental
# connections to developer machines while running tests.
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "password")


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return the PostgreSQL-style DSN used by the application."""

    return "postgresql+psycopg://user:password@localhost:5432/test_db"


@pytest.fixture()
def engine(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[Engine]:
    """Create an isolated in-memory engine and stub PostgreSQL creation."""

    # Construct the shared in-memory engine for the current test.
    test_engine = sqla_create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    real_create_engine = sqla_create_engine

    def _create_engine(url: str, *args, **kwargs):
        if url.startswith("postgresql"):
            return test_engine
        return real_create_engine(url, *args, **kwargs)

    # Patch both the top-level helper and the module-level function SQLAlchemy
    # exposes so the application code receives the in-memory engine.
    monkeypatch.setattr("sqlalchemy.create_engine", _create_engine)
    monkeypatch.setattr("sqlalchemy.engine.create_engine", _create_engine)

    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Iterator[Session]:
    """Yield a fresh SQLAlchemy session bound to the temporary engine."""

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
        session.flush()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class SampleDataFactory:
    """Utility helpers for generating minimal database fixtures."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._counters = defaultdict(int)

    def _unique(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}-{self._counters[prefix]}"

    def platform(self, *, name: str | None = None, category: str = "거래소") -> Platform:
        platform = Platform(name=name or self._unique("Platform"), category=category)
        self._session.add(platform)
        self._session.flush()
        return platform

    def asset(
        self,
        *,
        platform: Platform,
        name: str | None = None,
        symbol: str | None = None,
        category: str = "암호화폐",
        current_price: float = 1.0,
        quantity: float = 1.0,
        revision: int = 1,
        exchange: str | None = "Spot",
        currency: str | None = "USD",
        evaluation_amount: float | None = None,
        eval_amount_krw: float | None = None,
    ) -> Asset:
        asset = Asset(
            name=name or self._unique("Asset"),
            symbol=symbol or self._unique("SYM"),
            category=category,
            platform_id=platform.id,
            current_price=current_price,
            quantity=quantity,
            evaluation_amount=(evaluation_amount if evaluation_amount is not None else current_price * quantity),
            eval_amount_krw=eval_amount_krw,
            exchange=exchange,
            currency=currency,
            revision=revision,
        )
        self._session.add(asset)
        self._session.flush()
        return asset

    def transaction(
        self,
        *,
        asset: Asset,
        transaction_type: str = "매수",
        price: float = 1.0,
        quantity: float = 1.0,
        memo: str | None = None,
    ) -> Transaction:
        tx = Transaction(
            asset_id=asset.id,
            transaction_type=transaction_type,
            price=price,
            quantity=quantity,
            amount=price * quantity,
            memo=memo,
        )
        self._session.add(tx)
        self._session.flush()
        return tx

    def daily_metric(
        self,
        *,
        platform: Platform,
        symbol: str,
        revision: int,
        exchange: str = "Binance",
        after_value: float = 0.0,
        after_value_krw: float = 0.0,
        before_value: float | None = None,
        before_value_krw: float | None = None,
        created_at: datetime | None = None,
    ) -> DailyAssetMetrics:
        metric = DailyAssetMetrics(
            platform_id=platform.id,
            exchange=exchange,
            symbol=symbol,
            revision=revision,
            after_value=after_value,
            after_value_krw=after_value_krw,
            before_value=before_value,
            before_value_krw=before_value_krw,
            created_at=created_at or datetime.now(),
        )
        self._session.add(metric)
        self._session.flush()
        return metric

    def stable_coin(self, *, symbol: str, is_active: bool = True) -> StableCoin:
        coin = StableCoin(symbol=symbol, is_active=is_active)
        self._session.add(coin)
        self._session.flush()
        return coin

    def exchange_rate(
        self,
        *,
        base_currency: str,
        target_currency: str,
        rate: float,
    ) -> ExchangeRate:
        rate_obj = ExchangeRate(
            base_currency=base_currency,
            target_currency=target_currency,
            rate=rate,
        )
        self._session.add(rate_obj)
        self._session.flush()
        return rate_obj


@pytest.fixture()
def sample_data_factory(db_session: Session) -> Iterator[SampleDataFactory]:
    """Expose a lightweight factory for generating domain entities."""

    factory = SampleDataFactory(db_session)
    yield factory


@pytest.fixture(scope="session", autouse=True)
def external_dependency_stubs() -> None:
    """Provide lightweight stubs for network-bound dependencies."""

    if "ccxt" not in sys.modules:
        ccxt_module = ModuleType("ccxt")

        class _Exchange:  # pragma: no cover - simple stub container
            def __init__(self, *_args, **_kwargs) -> None:
                self._tickers = {}

            def fetch_balance(self):
                return {"total": {}}

            def fetch_ticker(self, symbol: str) -> dict:
                return self._tickers.get(symbol, {"last": 0.0})

            def sapi_get_simple_earn_flexible_position(self):
                return {"rows": []}

            def sapi_get_simple_earn_locked_position(self):
                return {"rows": []}

            def fapiprivatev2_get_balance(self):
                return []

        def _binance_factory(*args, **kwargs):  # pragma: no cover - trivial
            return _Exchange(*args, **kwargs)

        ccxt_module.binance = _binance_factory
        sys.modules["ccxt"] = ccxt_module

    if "requests" not in sys.modules:
        requests_module = ModuleType("requests")

        class _Response:  # pragma: no cover - trivial container
            def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
                self.status_code = status_code
                self._json_data = json_data or {}

            def json(self) -> dict:
                return self._json_data

        def _get(*_args, **_kwargs):  # pragma: no cover - trivial helper
            return _Response()

        class _Session:  # pragma: no cover - trivial container
            def get(self, *args, **kwargs):
                return _get(*args, **kwargs)

        requests_module.get = _get
        requests_module.Session = _Session
        sys.modules["requests"] = requests_module

    # Airflow stubs for DAG task imports are provided in the DAG-specific
    # conftest modules; no additional work is required here. This fixture simply
    # ensures import-time dependencies are satisfied when optional packages are
    # absent from the environment.
