import pytest

from python_engine.modules.risk_manager import RiskManager


def test_evaluate_order_lot_size():
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


def test_spread_filter_rejects():
    rm = RiskManager(account_balance=10000, max_risk_percent=1.0)
    # avg_spread 0.0001, current_spread 0.0003 which is > 2.5x (0.00025)
    decision = rm.evaluate_order(symbol="EURUSD", side="buy", price=1.0, atr=0.01, avg_spread=0.0001, current_spread=0.0003, sentiment=1.0)
    assert decision["approved"] is False
    assert decision["reason"] == "spread_too_wide"
