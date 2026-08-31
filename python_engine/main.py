"""Main orchestration for the AETMS Python engine.

This script wires adapters, risk manager and provides a minimal example flow
to send an order to the MT5 bridge with safety checks.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Dict

from dotenv import load_dotenv

from adapters.mt5_zmq import MT5ZMQClient
from modules.risk_manager import RiskManager


def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_order(symbol: str, side: str, lots: float, price: float, stop_price: float, take_profit: float) -> Dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "action": "order",
        "symbol": symbol,
        "side": side,
        "lots": lots,
        "price": price,
        "stop_price": stop_price,
        "take_profit": take_profit,
        "meta": {"source": "python_engine", "ts": int(time.time())},
    }


def main():
    load_dotenv()
    setup_logging()
    logger = logging.getLogger("aetms.main")

    account_balance = float(os.getenv("ACCOUNT_BALANCE", "100000"))
    avg_spread = float(os.getenv("AVG_SPREAD", "0.0001"))
    rm = RiskManager(account_balance=account_balance, max_risk_percent=float(os.getenv("MAX_RISK_PERCENT", "1.0")))
    mt5 = MT5ZMQClient()

    # Example: decide to send a long EURUSD order
    symbol = "EURUSD"
    entry_price = 1.1000
    stop_price = 1.0950
    take_profit = 1.1150
    current_spread = 0.00012

    if not rm.spread_allowed(avg_spread=avg_spread, current_spread=current_spread):
        logger.info("Spread too wide, aborting order placement")
        return

    if not rm.check_daily_drawdown(max_daily_drawdown_percent=float(os.getenv("MAX_DAILY_DRAWDOWN", "3.0"))):
        logger.info("Daily drawdown limit reached, aborting")
        return

    lots = rm.calculate_position_size(entry_price=entry_price, stop_price=stop_price, pip_value=1.0)
    if lots <= 0:
        logger.info("Calculated lot size is zero, aborting")
        return

    order = build_order(symbol=symbol, side="buy", lots=lots, price=entry_price, stop_price=stop_price, take_profit=take_profit)
    logger.info("Placing order: %s", order)
    report = mt5.send_order(order)
    logger.info("Execution report: %s", report)


if __name__ == "__main__":
    main()
