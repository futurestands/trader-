"""Simple Binance adapter using ccxt. Synchronous implementation wrapped for async use."""
from __future__ import annotations

import logging
from typing import Dict, Optional

import ccxt

logger = logging.getLogger(__name__)


class BinanceAdapter:
    def __init__(self, api_key: Optional[str], api_secret: Optional[str], testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        if not api_key or not api_secret:
            self.client = None
            logger.info("Binance adapter initialized without keys (dry-run)")
            return

        self.client = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        if testnet:
            self.client.set_sandbox_mode(True)

    def _lot_to_amount(self, symbol: str, lots: float, price: float) -> float:
        """Convert 'lots' to exchange amount. CCXT uses base asset amount.

        This is a mock conversion: amount = lots * contract_size where contract_size ~ 1000 for example.
        Replace with proper conversion per instrument.
        """
        contract_size = 1.0
        try:
            # crude heuristic: if symbol contains USDT assume lot is base units
            if "USDT" in symbol or "USD" in symbol:
                contract_size = 1.0
            return float(lots) * contract_size
        except Exception:
            return float(lots)

    def execute_order(self, order_payload: Dict) -> Dict:
        """Execute order payload: action, symbol, lots, price, stop_price, take_profit

        Returns standardized dict.
        """
        try:
            if self.client is None:
                logger.info("Binance dry-run order: %s", order_payload)
                return {"status": "SUCCESS", "ticket": "dryrun-1"}

            action = order_payload.get("action")
            symbol = order_payload.get("symbol")
            lots = float(order_payload.get("lots", 0))
            price = float(order_payload.get("price", 0))

            amount = self._lot_to_amount(symbol, lots, price)

            side = "buy" if action.upper() == "BUY" else "sell"
            type = "market" if price == 0 else "limit"

            params = {}
            if type == "limit":
                order = self.client.create_order(symbol, type, side, amount, price, params)
            else:
                order = self.client.create_market_order(symbol, side, amount, params)

            return {"status": "SUCCESS", "ticket": order.get("id")}
        except Exception as e:
            logger.exception("Binance order failed")
            return {"status": "FAILED", "error": str(e)}


__all__ = ["BinanceAdapter"]
