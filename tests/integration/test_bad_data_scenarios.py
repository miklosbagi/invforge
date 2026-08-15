"""Integration test: bad-data scenario fixtures round-trip their
deliberately out-of-spec values through a real Modbus TCP read -- proves
the wire encoding survives, not just that the YAML parses (see
invforge/core/registers.py's decode_numeric, reused here rather than
reimplemented)."""

from __future__ import annotations

import httpx
import pytest
from pymodbus.client import ModbusTcpClient

from invforge.core.registers import decode_numeric
from invforge.profiles.sigenergy.firmwares.V100R001C21SPC116 import PROFILE

from .conftest import MODBUS_HOST, MODBUS_PORT


@pytest.mark.parametrize(
    ("scenario_name", "address", "expected_decoded"),
    [
        ("bad-data-soc-over-100", 30014, 101.0),
        ("bad-data-soh-over-100", 30087, 150.0),
        ("bad-data-pv-power-negative", 30035, -0.5),
    ],
)
def test_bad_data_round_trips_through_real_modbus(
    control_client: httpx.Client, scenario_name: str, address: int, expected_decoded: float
) -> None:
    resp = control_client.post("/scenario", json={"name": scenario_name})
    assert resp.status_code == 200

    reg = PROFILE.find(247, address)
    assert reg is not None

    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=3)
    try:
        assert client.connect() is True
        r = client.read_holding_registers(address=address, count=reg.count, slave=247)
        decoded = decode_numeric(reg, r.registers)
    finally:
        client.close()

    assert decoded == expected_decoded
