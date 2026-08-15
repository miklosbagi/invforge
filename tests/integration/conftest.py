"""Integration test fixtures -- these tests need a real InvForge
instance already running (via `docker compose up -d --build`, or
`scripts/integration-test.sh` locally / in CI) and talk to it over real
Modbus TCP + HTTP, exactly as a driver under test would.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import httpx
import pytest
from pymodbus.client import ModbusTcpClient

MODBUS_HOST = os.environ.get("INVFORGE_MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.environ.get("INVFORGE_MODBUS_PORT", "5020"))
CONTROL_HOST = os.environ.get("INVFORGE_CONTROL_HOST", "127.0.0.1")
CONTROL_PORT = int(os.environ.get("INVFORGE_CONTROL_PORT", "8080"))
CONTROL_BASE_URL = f"http://{CONTROL_HOST}:{CONTROL_PORT}"


@pytest.fixture(scope="session", autouse=True)
def _require_running_instance() -> None:
    deadline = time.monotonic() + 10.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{CONTROL_BASE_URL}/health", timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as e:
            last_error = e
        time.sleep(0.5)
    pytest.fail(
        f"no InvForge instance reachable at {CONTROL_BASE_URL} after 10s "
        f"(last error: {last_error}) -- run `docker compose up -d --build` "
        f"(or scripts/integration-test.sh) first"
    )


@pytest.fixture
def control_client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=CONTROL_BASE_URL, timeout=5.0) as client:
        yield client


def can_read_modbus(address: int = 30014, unit: int = 247) -> bool:
    """A real protocol round-trip, not just a TCP handshake -- when a
    published port is forwarded through Docker's host-side proxy, the
    handshake alone can succeed even while nothing is actually listening
    in the container (the proxy accepts, then drops the connection once
    it can't reach a backend), so ModbusTcpClient.connect() alone is not
    a reliable "is the emulator actually reachable" check here."""
    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=2)
    try:
        if not client.connect():
            return False
        response = client.read_holding_registers(address=address, count=1, slave=unit)
        return not response.isError()
    except Exception:
        return False
    finally:
        client.close()
