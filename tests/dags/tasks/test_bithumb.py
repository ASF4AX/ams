from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

import dags.tasks.bithumb as bithumb


@contextmanager
def _stub_session() -> Any:
    yield object()


def test_process_bithumb_balances_assigns_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bithumb, "get_db_session", _stub_session)
    monkeypatch.setattr(bithumb, "get_active_stable_coins", lambda db: {"USDT"})

    balances = {
        "total": {"KRW": 100000.0, "USDT": 50.0, "XRP": 250.0},
        "prices": {"KRW": 1.0, "USDT": 1350.0, "XRP": 700.0},
    }

    assets = bithumb.process_bithumb_balances(balances, revision=3)

    assert len(assets) == 3

    krw = next(asset for asset in assets if asset["symbol"] == "KRW")
    assert krw["category"] == "현금"
    assert krw["evaluation_amount"] == pytest.approx(100000.0)
    assert krw["eval_amount_krw"] == pytest.approx(100000.0)

    stable = next(asset for asset in assets if asset["symbol"] == "USDT")
    assert stable["category"] == "스테이블코인"
    assert stable["evaluation_amount"] == pytest.approx(67500.0)
    assert stable["eval_amount_krw"] == pytest.approx(67500.0)

    crypto = next(asset for asset in assets if asset["symbol"] == "XRP")
    assert crypto["category"] == "암호화폐"
    assert crypto["evaluation_amount"] == pytest.approx(175000.0)
    assert crypto["eval_amount_krw"] == pytest.approx(175000.0)


def test_process_bithumb_balances_handles_missing_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bithumb, "get_db_session", _stub_session)
    monkeypatch.setattr(bithumb, "get_active_stable_coins", lambda db: set())

    balances = {
        "total": {"BTC": 0.5},
        "prices": {},
    }

    assets = bithumb.process_bithumb_balances(balances, revision=11)

    assert len(assets) == 1
    btc = assets[0]
    assert btc["symbol"] == "BTC"
    assert btc["current_price"] == 0
    assert btc["evaluation_amount"] == pytest.approx(0.0)
    assert btc["eval_amount_krw"] == pytest.approx(0.0)
