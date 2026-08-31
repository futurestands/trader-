import pytest
from unittest.mock import patch

from python_engine.modules.risk_manager import RiskManager


class DummyCursor:
    def __init__(self, responses=None):
        self._responses = responses or []
        self._i = 0

    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        if self._i < len(self._responses):
            r = self._responses[self._i]
            self._i += 1
            return r
        return {"pnl": 0}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyConn:
    def __init__(self, responses=None):
        self._responses = responses

    def cursor(self, cursor_factory=None):
        return DummyCursor(self._responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_get_db_conn_ok():
    # First fetchone returns pnl=0, second returns starting_balance
    return DummyConn(responses=[{"pnl": 0}, {"starting_balance": 10000}])


@patch("python_engine.modules.risk_manager._get_db_conn", side_effect=fake_get_db_conn_ok)
def test_evaluate_order_lot_size(mock_db):
    rm = RiskManager(account_balance=10000, max_risk_percent=1.0)
    # entry 1.0, stop 0.99 -> distance 0.01; expected lots = (10000*0.01)/(0.01*100000)=0.1
    decision = rm.evaluate_order(symbol="EURUSD", side="buy", price=1.0, atr=0.01, avg_spread=0.0001, current_spread=0.0001, sentiment=1.0)
    assert decision["approved"] is True
    assert "order" in decision
    assert round(decision["order"]["lots"], 2) == 0.1


def test_kill_switch_triggers(monkeypatch):
    rm = RiskManager(account_balance=10000, max_risk_percent=1.0)
    # simulate kill-switch by forcing check_daily_drawdown to return False
    monkeypatch.setattr(rm, "check_daily_drawdown", lambda *args, **kwargs: False)
    decision = rm.evaluate_order(symbol="EURUSD", side="buy", price=1.0, atr=0.01, avg_spread=0.0001, current_spread=0.0001, sentiment=1.0)
    assert decision["approved"] is False
    assert decision["reason"] == "daily_drawdown_exceeded"


@patch("python_engine.modules.risk_manager._get_db_conn", side_effect=fake_get_db_conn_ok)
def test_spread_filter_rejects(mock_db):
    rm = RiskManager(account_balance=10000, max_risk_percent=1.0)
    # avg_spread 0.0001, current_spread 0.0003 which is > 2.5x (0.00025)
    decision = rm.evaluate_order(symbol="EURUSD", side="buy", price=1.0, atr=0.01, avg_spread=0.0001, current_spread=0.0003, sentiment=1.0)
    assert decision["approved"] is False
    assert decision["reason"] == "spread_too_wide"
