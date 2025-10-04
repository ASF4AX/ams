from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List

import pytest

import dags.tasks.binance as binance


# ---------------------------
# Shared test utilities
# ---------------------------


class FakeExchange:
    """Small, explicit fake for ccxt.binance used in pagination tests."""

    def __init__(self, *, page_size: int = 100) -> None:
        self.page_size = page_size
        self.flex_calls: List[Dict[str, Any]] = []
        self.locked_calls: List[Dict[str, Any]] = []

    # Spot
    def fetch_balance(self) -> Dict[str, Any]:
        return {"total": {"USDT": 150.0}}

    # Earn (flexible): exactly one full page, then empty
    def sapi_get_simple_earn_flexible_position(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.flex_calls.append(dict(params))
        current = int(params.get("current", 1))
        rows = (
            [{"asset": "BUSD", "totalAmount": "1"} for _ in range(self.page_size)]
            if current == 1
            else []
        )
        return {"rows": rows}

    # Earn (locked): one full page, then a short page, then empty
    def sapi_get_simple_earn_locked_position(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.locked_calls.append(dict(params))
        current = int(params.get("current", 1))
        if current == 1:
            rows = [{"asset": "BNB", "amount": "1"} for _ in range(self.page_size)]
        elif current == 2:
            rows = [{"asset": "BNB", "amount": "0.5"}]
        else:
            rows = []
        return {"rows": rows}


@contextmanager
def _stub_session() -> Any:
    yield object()


def test_balances_paginates_simple_earn_until_short_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an exchange that returns a full page then empty (flex)
    #        and a full page then a short page (locked)
    fake = FakeExchange(page_size=100)
    monkeypatch.setattr(binance.ccxt, "binance", lambda *_a, **_k: fake)

    # When
    balances = binance.fetch_binance_balances({"apiKey": "k", "secret": "s"})

    # Then: both flexible and locked were paginated twice (1 -> 2)
    assert fake.flex_calls == [
        {"current": 1, "size": 100},
        {"current": 2, "size": 100},
    ]
    assert fake.locked_calls == [
        {"current": 1, "size": 100},
        {"current": 2, "size": 100},
    ]

    # And: spot + earn totals are aggregated correctly
    assert balances["total"]["USDT"] == pytest.approx(150.0)
    assert balances["total"]["BUSD"] == pytest.approx(100.0)
    assert balances["total"]["BNB"] == pytest.approx(100.5)


def test_process_balances_classifies_and_values_with_fx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    # When
    assets = binance.process_binance_balances(balances, revision=5)

    # Then
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


def test_process_balances_marks_futures_and_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(binance, "get_db_session", _stub_session)
    monkeypatch.setattr(binance, "get_active_stable_coins", lambda db: set())
    monkeypatch.setattr(
        binance, "fetch_binance_prices", lambda currencies: {"BTC": 30000.0}
    )
    monkeypatch.setattr(binance, "get_exchange_rates", lambda db: {"USD": 1200.0})

    balances = {"total": {"BTC": 0.1}}

    # When
    assets = binance.process_binance_balances(balances, revision=7, is_futures=True)

    # Then
    assert len(assets) == 1
    assert assets[0]["exchange"] == "Futures"
    assert assets[0]["evaluation_amount"] == pytest.approx(3000.0)
    assert assets[0]["eval_amount_krw"] == pytest.approx(3600000.0)


def test_update_assets_in_db_inserts_each_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    # When
    binance.update_assets_in_db(assets)

    assert inserted == assets
