"""Main orchestration for the AETMS Python engine.

This script wires adapters, risk manager and provides a minimal example flow
to send an order to the MT5 bridge with safety checks.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Dict

from dotenv import load_dotenv

from adapters.mt5_zmq import MT5ZMQClient
from modules.risk_manager import RiskManager
from modules.ai_signals import evaluate_market_state
from modules.telegram_alerts import TelegramAlerts
from adapters.binance_ccxt import BinanceAdapter


def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_order_payload(order: Dict) -> Dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "action": order.get("action"),
        "symbol": order.get("symbol"),
        "lots": order.get("lots"),
        "price": order.get("price"),
        "stop_price": order.get("stop_price"),
        "take_profit": order.get("take_profit"),
        "meta": {"source": "python_engine", "ts": int(time.time())},
    }


async def async_send_to_mt5(mt5_client: MT5ZMQClient, payload: Dict) -> Dict:
    return await asyncio.to_thread(mt5_client.send_order, payload)


async def async_execute_ccxt(adapter: BinanceAdapter, payload: Dict) -> Dict:
    # CCXT adapter may be synchronous; run in thread to avoid blocking
    return await asyncio.to_thread(adapter.execute_order, payload)


async def main_loop():
    load_dotenv()
    setup_logging()
    logger = logging.getLogger("aetms.main")

    account_balance = float(os.getenv("ACCOUNT_BALANCE", "100000"))
    avg_spread = float(os.getenv("AVG_SPREAD", "0.0001"))
    rm = RiskManager(account_balance=account_balance, max_risk_percent=float(os.getenv("MAX_RISK_PERCENT", "1.0")))
    mt5 = MT5ZMQClient()

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID")
    telegram = TelegramAlerts(tg_token, tg_chat) if tg_token and tg_chat else None

    # Optional Binance adapter
    binance_api_key = os.getenv("BINANCE_API_KEY")
    binance_api_secret = os.getenv("BINANCE_API_SECRET")
    binance = BinanceAdapter(binance_api_key, binance_api_secret) if binance_api_key and binance_api_secret else None

    poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "60"))

    # Initialize data ingestion
    from modules.data_ingestion import DataIngestion
    data_ingestion = DataIngestion(exchange=os.getenv("DATA_EXCHANGE", "binance"), api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET"), testnet=True)

    # initial price fallback
    price = float(os.getenv("START_PRICE", "1.1000"))

    while True:
        try:
            # fetch OHLCV via DataIngestion; fallback to local generator on error
            try:
                timeframe = os.getenv("TIMEFRAME", "1m")
                df = await data_ingestion.fetch_ohlcv(symbol, timeframe=timeframe, limit=250)
            except Exception:
                import pandas as pd
                import numpy as np
                n = 220
                noise = np.random.normal(0, 0.0002, size=n)
                closes = price + np.cumsum(noise)
                highs = closes + np.abs(np.random.normal(0, 0.0001, size=n))
                lows = closes - np.abs(np.random.normal(0, 0.0001, size=n))
                opens = np.concatenate([[price], closes[:-1]])
                vols = np.random.randint(1, 10, size=n)
                df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols})

            # evaluate signals
            symbol = os.getenv("SYMBOL", "EURUSD")
            signal = evaluate_market_state(df, symbol)
            logger.info("Signal: %s", signal)

            if signal.get("action") in ("BUY", "SELL"):
                side = signal["action"]
                last_price = df["close"].iloc[-1]
                atr_val = signal.get("atr", 0.0)
                sentiment = signal.get("sentiment", 0.0)
                current_spread = float(os.getenv("CURRENT_SPREAD", "0.00012"))

                decision = rm.evaluate_order(symbol=symbol, side=side, price=last_price, atr=atr_val, avg_spread=avg_spread, current_spread=current_spread, sentiment=sentiment)
                if not decision.get("approved"):
                    reason = decision.get("reason")
                    logger.info("RiskManager rejected order: %s", reason)
                    if telegram:
                        telegram.send_alert(f"Order rejected: {reason}", level="WARNING")
                else:
                    order_payload = build_order_payload(decision.get("order"))
                    # route to adapter (MT5 by default)
                    if binance and os.getenv("DEFAULT_BROKER", "mt5").lower() == "binance":
                        resp = await async_execute_ccxt(binance, order_payload)
                    else:
                        resp = await async_send_to_mt5(mt5, order_payload)

                    logger.info("Execution response: %s", resp)
                    if telegram:
                        if resp.get("status") == "SUCCESS":
                            telegram.send_alert(f"Order executed: {resp}", level="INFO")
                        else:
                            telegram.send_alert(f"Order failed: {resp}", level="CRITICAL")

            # advance price for next iteration
            price = df["close"].iloc[-1]
        except Exception:
            logger.exception("Error in main loop")
            if telegram:
                telegram.send_alert("Main loop exception occurred", level="CRITICAL")

        await asyncio.sleep(poll_interval)


def main():
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
