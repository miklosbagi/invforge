"""Integration test: a static YAML scenario, loaded via the control API,
actually drives real Modbus reads over the wire."""

from __future__ import annotations

import time

import httpx
from pymodbus.client import ModbusTcpClient

from .conftest import MODBUS_HOST, MODBUS_PORT


def test_ramp_scenario_soc_decreases_over_real_modbus(control_client: httpx.Client) -> None:
    resp = control_client.post("/scenario", json={"name": "ramp-discharge-100-to-0", "speed": 20.0})
    assert resp.status_code == 200

    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=3)
    try:
        assert client.connect() is True
        r0 = client.read_holding_registers(address=30014, count=1, slave=247)
        soc0 = r0.registers[0] / 10.0
        time.sleep(1.5)  # at 20x speed, ~30 scenario-seconds elapse
        r1 = client.read_holding_registers(address=30014, count=1, slave=247)
        soc1 = r1.registers[0] / 10.0
    finally:
        client.close()

    assert soc1 < soc0
