"""Integration test: a parametric-generator scenario name (no YAML file
on disk for it), loaded via the control API, drives real Modbus reads
over the wire."""

from __future__ import annotations

import time

import httpx
from pymodbus.client import ModbusTcpClient

from .conftest import MODBUS_HOST, MODBUS_PORT


def test_generated_ramp_drains_over_real_time(control_client: httpx.Client) -> None:
    # A long-relative-to-jitter duration (30s), sampled well inside the
    # window rather than near the wrap boundary (the engine loops a
    # scenario back to t=0 once elapsed time passes its duration -- see
    # core/server.py's elapsed_seconds() -- so timing precision near
    # that edge isn't something this test needs to depend on).
    resp = control_client.post("/scenario", json={"name": "linear-drain-100-to-0-30s", "speed": 1.0})
    assert resp.status_code == 200
    assert resp.json()["duration"] == 30.0

    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=3)
    try:
        assert client.connect() is True

        def read_soc() -> float:
            r = client.read_holding_registers(address=30014, count=1, slave=247)
            return r.registers[0] / 10.0

        soc_early = read_soc()
        time.sleep(3.0)
        soc_later = read_soc()
    finally:
        client.close()

    assert soc_early <= 100.0
    assert soc_later < soc_early


def test_invalid_generated_ramp_is_rejected(control_client: httpx.Client) -> None:
    resp = control_client.post("/scenario", json={"name": "linear-drain-0-to-100-10s"})
    assert resp.status_code == 400


def test_unknown_scenario_name_is_404(control_client: httpx.Client) -> None:
    resp = control_client.post("/scenario", json={"name": "definitely-not-a-real-scenario"})
    assert resp.status_code == 404
