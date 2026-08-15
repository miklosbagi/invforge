"""Integration test: a scenario's offline: window makes the Modbus TCP
listener genuinely unreachable for real, not just returning a Modbus
exception -- and it recovers automatically afterward."""

from __future__ import annotations

import time

import httpx

from .conftest import can_read_modbus


def test_offline_window_drops_and_recovers_the_connection(control_client: httpx.Client) -> None:
    resp = control_client.post("/scenario", json={"name": "offline-window", "speed": 1.0})
    assert resp.status_code == 200

    assert can_read_modbus() is True  # before the window (offline: start=3, end=8)

    time.sleep(4.0)  # inside the window
    assert can_read_modbus() is False

    time.sleep(5.0)  # past the window (t~9)
    assert can_read_modbus() is True
