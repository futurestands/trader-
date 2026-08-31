"""Simple Telegram alert helper using requests with timeout and basic level formatting."""
from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class TelegramAlerts:
    def __init__(self, bot_token: str, chat_id: str, timeout: float = 3.0):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = float(timeout)
        self.api = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def _level_prefix(self, level: str) -> str:
        lvl = (level or "INFO").upper()
        if lvl == "CRITICAL":
            return "🔴 [CRITICAL]"
        if lvl == "WARNING":
            return "🟡 [WARNING]"
        return "ℹ️ [INFO]"

    def send_alert(self, message: str, level: str = "INFO") -> bool:
        text = f"{self._level_prefix(level)} {message}"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            resp = requests.post(self.api, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                return True
            else:
                logger.warning("Telegram alert failed: %s %s", resp.status_code, resp.text)
                return False
        except requests.RequestException:
            logger.exception("Exception sending telegram alert")
            return False


__all__ = ["TelegramAlerts"]
