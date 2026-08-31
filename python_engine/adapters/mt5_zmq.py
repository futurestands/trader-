"""ZeroMQ-based adapter to send orders to the MQL5 bridge.

Python side uses a REQ socket to send JSON order requests and waits for execution reports.
"""
from __future__ import annotations

import os
import json
import time
import logging
from typing import Any, Dict, Optional

import zmq

logger = logging.getLogger(__name__)


class MT5ZMQClient:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, timeout_ms: int = 5000):
        host = host or os.getenv("MT5_HOST", "127.0.0.1")
        port = int(port or os.getenv("MT5_PORT", "5555"))
        self.endpoint = f"tcp://{host}:{port}"
        self.timeout_ms = int(timeout_ms)
        self._ctx = zmq.Context.instance()
        self._socket = self._ctx.socket(zmq.REQ)
        self._socket.linger = 0
        self._poller = zmq.Poller()
        self._poller.register(self._socket, zmq.POLLIN)
        self._socket.connect(self.endpoint)
        logger.info("MT5ZMQClient connected to %s", self.endpoint)

    def send_order(self, order: Dict[str, Any], retry: int = 2) -> Dict[str, Any]:
        """Send an order dict to MT5 and wait for JSON reply.

        The order format is a JSON-serializable dict. Returns the execution report dict.
        """
        payload = json.dumps(order)
        attempt = 0
        while attempt <= retry:
            try:
                attempt += 1
                logger.debug("Sending order to MT5 (attempt %s): %s", attempt, payload)
                self._socket.send_string(payload)

                socks = dict(self._poller.poll(self.timeout_ms))
                if socks.get(self._socket) == zmq.POLLIN:
                    msg = self._socket.recv_string()
                    try:
                        report = json.loads(msg)
                        return report
                    except Exception:
                        logger.exception("Invalid JSON from MT5: %s", msg)
                        return {"ok": False, "error": "invalid_json", "raw": msg}
                else:
                    logger.warning("MT5 bridge timeout waiting for reply (attempt %s)", attempt)
                    # socket state for REQ/REP requires reconnect on timeout
                    self._socket.setsockopt(zmq.LINGER, 0)
                    self._socket.close()
                    time.sleep(0.1)
                    self._socket = self._ctx.socket(zmq.REQ)
                    self._socket.linger = 0
                    self._socket.connect(self.endpoint)
                    self._poller.register(self._socket, zmq.POLLIN)
            except Exception:
                logger.exception("Error sending order to MT5 (attempt %s)", attempt)
                time.sleep(0.2)

        return {"ok": False, "error": "timeout_or_no_reply"}


if __name__ == "__main__":
    # quick smoke test
    logging.basicConfig(level=logging.DEBUG)
    client = MT5ZMQClient()
    report = client.send_order({"action": "ping"}, retry=1)
    print(report)
