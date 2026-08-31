import pandas as pd

from python_engine.modules import ai_signals


def test_evaluate_market_state_buy(monkeypatch):
    # Create synthetic increasing price series of length 220
    n = 220
    closes = [1.0 + i * 0.0001 for i in range(n)]
    highs = [c + 0.00005 for c in closes]
    lows = [c - 0.00005 for c in closes]
    opens = [closes[0]] + closes[:-1]
    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1]*n})

    # Force high positive sentiment
    monkeypatch.setattr(ai_signals, "get_ai_sentiment", lambda s: 0.8)

    # Force RSI to simulate a cross: prev <50, last >=50
    def fake_rsi(series, period=14):
        idx = series.index
        vals = [40.0] * (len(series) - 2) + [49.0, 51.0]
        return pd.Series(vals, index=idx)

    monkeypatch.setattr(ai_signals, "rsi", fake_rsi)

    res = ai_signals.evaluate_market_state(df, symbol="TESTSYMBOL")
    assert res["action"] == "BUY"
