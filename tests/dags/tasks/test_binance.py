from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List

import pytest

import dags.tasks.binance as binance


@contextmanager
def _stub_session() -> Any:
    yield object()


def test_process_binance_balances_classifies_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(binance, "get_db_session", _stub_session)
    monkeypatch.setattr(binance, "get_active_stable_coins", lambda db: {"USDT"})

    recorded_currencies: List[List[str]] = []

    def fake_prices(currencies: List[str]) -> Dict[str, float]:
        recorded_currencies.append(list(currencies))
        return {"USDT": 1.0, "BTC": 40000.0}

    monkeypatch.setattr(binance, "fetch_binance_prices", fake_prices)
    monkeypatch.setattr(
        binance, "get_exchange_rates", lambda db: {"USD": 1300.0, "KRW": 1.0}
    )

    balances = {"total": {"USDT": 150.0, "BTC": 0.5, "BAD": 2.0}}

    assets = binance.process_binance_balances(balances, revision=5)

    assert recorded_currencies == [["USDT", "BTC", "BAD"]]
    assert len(assets) == 2  # BAD 은 가격이 없어 제외됨

    stable = next(asset for asset in assets if asset["symbol"] == "USDT")
    assert stable["category"] == "스테이블코인"
    assert stable["exchange"] == "Spot"
    assert stable["evaluation_amount"] == pytest.approx(150.0)
    assert stable["eval_amount_krw"] == pytest.approx(195000.0)

    crypto = next(asset for asset in assets if asset["symbol"] == "BTC")
    assert crypto["category"] == "암호화폐"
    assert crypto["exchange"] == "Spot"
    assert crypto["evaluation_amount"] == pytest.approx(20000.0)
    assert crypto["eval_amount_krw"] == pytest.approx(26000000.0)


def test_process_binance_balances_marks_futures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(binance, "get_db_session", _stub_session)
    monkeypatch.setattr(binance, "get_active_stable_coins", lambda db: set())
    monkeypatch.setattr(
        binance, "fetch_binance_prices", lambda currencies: {"BTC": 30000.0}
    )
    monkeypatch.setattr(binance, "get_exchange_rates", lambda db: {"USD": 1200.0})

    balances = {"total": {"BTC": 0.1}}

    assets = binance.process_binance_balances(balances, revision=7, is_futures=True)

    assert len(assets) == 1
    assert assets[0]["exchange"] == "Futures"
    assert assets[0]["evaluation_amount"] == pytest.approx(3000.0)
    assert assets[0]["eval_amount_krw"] == pytest.approx(3600000.0)


def test_update_assets_in_db_calls_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    inserted: List[Dict[str, Any]] = []

    @contextmanager
    def session_cm():
        yield "session"

    def fake_insert(db: Any, asset: Dict[str, Any]) -> None:
        inserted.append({**asset})

    monkeypatch.setattr(binance, "get_db_session", session_cm)
    monkeypatch.setattr(binance, "insert_asset", fake_insert)

    assets = [
        {"symbol": "BTC", "quantity": 0.25, "category": "암호화폐", "revision": 2},
        {"symbol": "USDT", "quantity": 500, "category": "스테이블코인", "revision": 2},
    ]

    binance.update_assets_in_db(assets)

    assert inserted == assets
