"""Engine Client — REST API + WebSocket + SHM bridge to the C++ engine."""

import json
from typing import Any

import requests

from rlaaer.config import ENGINE


class EngineClientError(Exception):
    """Raised on engine communication failures."""


class EngineClient:
    """Client for the C++ engine REST API and WebSocket."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or ENGINE["rest_api"]
        self.ws_url = ENGINE.get("websocket", "ws://localhost:8081")
        self.pillar_url = ENGINE.get("pillar_bridge", "http://localhost:8888")
        self.timeout = ENGINE.get("startup_timeout_sec", 30)
        self._session = requests.Session()

    def ping(self) -> bool:
        """Check if engine is reachable."""
        try:
            resp = self._session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def start_simulation(self, config: dict) -> dict:
        """Start a new simulation. Returns simulation ID."""
        resp = self._session.post(
            f"{self.base_url}/simulation/start",
            json=config,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def step(self, sim_id: str, ticks: int = 1) -> dict:
        """Advance simulation by N ticks."""
        resp = self._session.post(
            f"{self.base_url}/simulation/{sim_id}/step",
            json={"ticks": ticks},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_state(self, sim_id: str) -> dict:
        """Get current simulation state."""
        resp = self._session.get(
            f"{self.base_url}/simulation/{sim_id}/state",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_metrics(self, sim_id: str) -> dict:
        """Get simulation metrics."""
        resp = self._session.get(
            f"{self.base_url}/simulation/{sim_id}/metrics",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def stop_simulation(self, sim_id: str) -> bool:
        """Stop and cleanup a simulation."""
        try:
            resp = self._session.post(
                f"{self.base_url}/simulation/{sim_id}/stop",
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def set_parameter(self, sim_id: str, name: str, value: Any) -> dict:
        """Set a simulation parameter at runtime."""
        resp = self._session.post(
            f"{self.base_url}/simulation/{sim_id}/parameter",
            json={"name": name, "value": value},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._session.close()
