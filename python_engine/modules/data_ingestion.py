"""CCXT-based asynchronous OHLCV data ingestion.

Provides DataIngestion.fetch_ohlcv which returns a pandas DataFrame indexed
by timestamp with columns: timestamp, open, high, low, close, volume.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import pandas as pd

try:
    import ccxt.async_support as ccxt_async
except Exception:  # pragma: no cover - ccxt may not be installed in test env
    ccxt_async = None

logger = logging.getLogger(__name__)


class DataIngestion:
    def __init__(self, exchange: str = "binance", api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        self.exchange_name = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    async def _create_client(self):
        if ccxt_async is None:
            raise RuntimeError("ccxt.async_support is required for DataIngestion")

        ex_class = getattr(ccxt_async, self.exchange_name)
        client = ex_class({"enableRateLimit": True})
        if self.api_key and self.api_secret:
            client.apiKey = self.api_key
            client.secret = self.api_secret
        if self.testnet and hasattr(client, "set_sandbox_mode"):
            try:
                client.set_sandbox_mode(True)
            except Exception:
                pass
        return client

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 250) -> pd.DataFrame:
        retries = 3
        backoff = 1.0
        last_exc = None
        for attempt in range(retries):
            client = None
            try:
                client = await self._create_client()
                ohlcv = await client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                # ohlcv rows: [timestamp, open, high, low, close, volume]
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
                await client.close()
                return df
            except Exception as e:
                last_exc = e
                logger.warning("fetch_ohlcv attempt %s failed: %s", attempt + 1, e)
                try:
                    if client is not None:
                        await client.close()
                except Exception:
                    pass
                await asyncio.sleep(backoff)
                backoff *= 2

        logger.error("fetch_ohlcv failed after %s attempts: %s", retries, last_exc)
        raise last_exc


__all__ = ["DataIngestion"]
