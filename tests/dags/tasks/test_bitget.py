from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List

import pytest

import dags.tasks.bitget as bitget


@contextmanager
def _stub_session() -> Any:
    yield object()


def test_process_bitget_balances_converts_to_krw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bitget, "get_db_session", _stub_session)
    monkeypatch.setattr(bitget, "get_active_stable_coins", lambda db: {"USDT"})

    captured: List[List[str]] = []

    def fake_prices(currencies: List[str]) -> Dict[str, float]:
        captured.append(list(currencies))
        return {"USDT": 1.0, "ETH": 2000.0}

    monkeypatch.setattr(bitget, "fetch_bitget_prices", fake_prices)
    monkeypatch.setattr(bitget, "get_exchange_rates", lambda db: {"USD": 1350.0})

    balances = {"total": {"USDT": 75.0, "ETH": 3.0}}

    assets = bitget.process_bitget_balances(balances, revision=4)

    assert captured == [["USDT", "ETH"]]
    assert len(assets) == 2

    stable = next(asset for asset in assets if asset["symbol"] == "USDT")
    assert stable["category"] == "스테이블코인"
    assert stable["evaluation_amount"] == pytest.approx(75.0)
    assert stable["eval_amount_krw"] == pytest.approx(101250.0)

    crypto = next(asset for asset in assets if asset["symbol"] == "ETH")
    assert crypto["category"] == "암호화폐"
    assert crypto["evaluation_amount"] == pytest.approx(6000.0)
    assert crypto["eval_amount_krw"] == pytest.approx(8100000.0)


def test_process_bitget_balances_skips_missing_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bitget, "get_db_session", _stub_session)
    monkeypatch.setattr(bitget, "get_active_stable_coins", lambda db: set())
    monkeypatch.setattr(bitget, "fetch_bitget_prices", lambda currencies: {"BTC": 0.0})
    monkeypatch.setattr(bitget, "get_exchange_rates", lambda db: {"USD": 1300.0})

    balances = {"total": {"BTC": 0.5, "UNKNOWN": 1.0}}

    assets = bitget.process_bitget_balances(balances, revision=9)

    assert len(assets) == 1
    assert assets[0]["symbol"] == "BTC"
    assert assets[0]["evaluation_amount"] == pytest.approx(0.0)
    assert assets[0]["eval_amount_krw"] == pytest.approx(0.0)


def test_bitget_update_assets_in_db_invokes_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    records: List[Dict[str, Any]] = []

    @contextmanager
    def session_cm():
        yield "session"

    def fake_insert(db: Any, asset: Dict[str, Any]) -> None:
        records.append({**asset})

    monkeypatch.setattr(bitget, "get_db_session", session_cm)
    monkeypatch.setattr(bitget, "insert_asset", fake_insert)

    payload = [
        {"symbol": "BTC", "quantity": 1, "category": "암호화폐", "revision": 1},
        {"symbol": "ETH", "quantity": 2, "category": "암호화폐", "revision": 1},
    ]

    bitget.update_assets_in_db(payload)

    assert records == payload
