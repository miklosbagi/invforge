"""Integration test: on-demand connectivity fault injection via
POST /fault, including that it's sticky over scenario offline: windows
and gets cleared by loading a new scenario."""

from __future__ import annotations

import time

import httpx

from .conftest import can_read_modbus


def test_forced_offline_and_online(control_client: httpx.Client) -> None:
    control_client.post("/scenario", json={"name": "ramp-discharge-100-to-0"})

    resp = control_client.post("/fault", json={"connectivity": "offline"})
    assert resp.status_code == 200
    assert can_read_modbus() is False

    resp = control_client.post("/fault", json={"connectivity": "online"})
    assert resp.status_code == 200
    assert can_read_modbus() is True

    resp = control_client.post("/fault", json={"connectivity": "auto"})
    assert resp.status_code == 200
    assert can_read_modbus() is True


def test_loading_a_scenario_clears_a_stale_forced_offline_override(control_client: httpx.Client) -> None:
    control_client.post("/scenario", json={"name": "ramp-discharge-100-to-0"})
    control_client.post("/fault", json={"connectivity": "offline"})
    assert can_read_modbus() is False

    resp = control_client.post("/scenario", json={"name": "ramp-discharge-100-to-0"})
    assert resp.status_code == 200
    time.sleep(0.5)  # give the connectivity loop one tick to notice the cleared override

    assert can_read_modbus() is True
