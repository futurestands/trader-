"""Risk management utilities for AETMS.

Features:
- 1% risk per trade calculation
- Daily drawdown kill-switch
- Spread filter
- Dynamic lot sizing

This module is written to be robust and database-backed for auditability.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _get_db_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "aetms_db"),
        user=os.getenv("POSTGRES_USER", "aeuser"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


class RiskManager:
    def __init__(self, account_balance: float, max_risk_percent: float = 1.0):
        self.account_balance = float(account_balance)
        self.max_risk_percent = float(max_risk_percent)

    def calculate_position_size(
        self,
        entry_price: float,
        stop_price: float,
        pip_value: Optional[float] = None,
        contract_size: float = 100000.0,
        risk_percent: Optional[float] = None,
    ) -> float:
        """Calculate lot size given entry/stop and desired risk percent.

        Simple formula:
        risk_amount = account_balance * (risk_percent/100)
        loss_per_lot = abs(entry-stop) * contract_size * (pip_value or 1)
        lots = risk_amount / loss_per_lot
        """
        try:
            risk_percent = float(risk_percent) if risk_percent is not None else self.max_risk_percent
            risk_amount = self.account_balance * (risk_percent / 100.0)
            distance = abs(entry_price - stop_price)
            if distance <= 0 or risk_amount <= 0:
                return 0.0

            pip_value = float(pip_value) if pip_value is not None else 1.0
            loss_per_lot = distance * contract_size * pip_value
            if loss_per_lot <= 0:
                return 0.0

            lots = risk_amount / loss_per_lot
            # round to sensible precision (2 decimals for forex lots)
            return round(max(0.0, lots), 2)
        except Exception:
            logger.exception("Error calculating position size")
            return 0.0

    def spread_allowed(self, avg_spread: float, current_spread: float, multiplier: float = 2.5) -> bool:
        try:
            if avg_spread <= 0:
                return True
            allowed = current_spread <= (avg_spread * multiplier)
            if not allowed:
                logger.info("Spread filter triggered: current=%s avg=%s", current_spread, avg_spread)
            return allowed
        except Exception:
            logger.exception("Error evaluating spread filter")
            return False

    def check_daily_drawdown(self, max_daily_drawdown_percent: float = 3.0) -> bool:
        """Return True if kill-switch should NOT be triggered (i.e., safe to trade).

        This queries `system_health` and `trade_ledger` to compute today's PnL.
        """
        try:
            conn = _get_db_conn()
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(realized_pnl),0) as pnl
                        FROM trade_ledger
                        WHERE closed_at::date = current_date
                        """
                    )
                    row = cur.fetchone()
                    todays_pnl = float(row["pnl"] or 0.0)

                    # load starting balance for the day if available
                    cur.execute(
                        """
                        SELECT starting_balance
                        FROM system_health
                        WHERE date = current_date
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    )
                    row2 = cur.fetchone()
                    starting_balance = float(row2["starting_balance"]) if row2 else self.account_balance

            drawdown = 0.0
            try:
                drawdown = max(0.0, (starting_balance - (starting_balance + todays_pnl)) / starting_balance * 100.0)
            except Exception:
                drawdown = 0.0

            if drawdown >= float(max_daily_drawdown_percent):
                logger.warning("Daily drawdown kill-switch: %.2f%% >= %.2f%%", drawdown, max_daily_drawdown_percent)
                return False
            return True
        except Exception:
            logger.exception("Error checking daily drawdown")
            # fail-safe: if DB error, refuse to allow trading
            return False

    def record_event(self, event_type: str, payload: dict):
        try:
            conn = _get_db_conn()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO system_events(trace_id, event_type, payload)
                        VALUES (gen_random_uuid(), %s, %s::jsonb)
                        """,
                        (event_type, psycopg2.extras.Json(payload)),
                    )
        except Exception:
            logger.exception("Failed to record system event")


__all__ = ["RiskManager"]
