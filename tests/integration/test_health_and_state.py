"""Baseline integration test -- validates the Docker/CI plumbing itself
(container up, both ports reachable) before anything scenario-specific
is trusted."""

from __future__ import annotations

import httpx
from pymodbus.client import ModbusTcpClient

from .conftest import MODBUS_HOST, MODBUS_PORT


def test_health_endpoint(control_client: httpx.Client) -> None:
    resp = control_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_scenarios_endpoint_lists_library_and_generators(control_client: httpx.Client) -> None:
    resp = control_client.get("/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert "ramp-discharge-100-to-0" in body["library"]
    assert any("linear-" in pattern for pattern in body["generators"])


def test_modbus_port_is_reachable() -> None:
    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=3)
    try:
        assert client.connect() is True
    finally:
        client.close()


def test_state_endpoint_reports_connectivity(control_client: httpx.Client) -> None:
    resp = control_client.get("/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "connectivity" in body
    assert body["connectivity"]["online"] is True
