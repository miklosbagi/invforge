"""Owns the live Modbus TCP listener's online/offline lifecycle, so a
scenario (or an on-demand control-API call) can make the emulator go
genuinely unreachable for a window -- simulating a real device dropping
off the network, not just a register-level Modbus exception.

pymodbus's blocking `StartTcpServer` convenience wrapper can't be
stopped/restarted from outside once running, so this constructs
`pymodbus.server.async_io.ModbusTcpServer` directly inside its own
asyncio event loop: `await server.listen()` to come online,
`await server.shutdown()` to go offline (this also drops
already-connected clients, not just refuses new ones -- confirmed
against the pymodbus 3.6.9 source, the right behavior for "device went
offline mid-session"). A shut-down server object is not reused --
`_bring_online()` always constructs a fresh one.

Only the run() coroutine itself -- and coroutines scheduled onto its
loop via asyncio.run_coroutine_threadsafe() from set_override() -- ever
touch the live pymodbus server object, so it needs no lock. `_override`
and `_online` are read from arbitrary threads (the control API, running
under uvicorn) and are guarded by `self._lock`.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from pymodbus.datastore import ModbusServerContext
from pymodbus.framer import Framer
from pymodbus.server.async_io import ModbusTcpServer

from .server import elapsed_seconds
from .state import SimState

log = logging.getLogger("invforge")


class ConnectivityController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._override: bool | None = None  # None=auto (scenario-driven), True=forced offline, False=forced online
        self._online = False
        self._server: ModbusTcpServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state: SimState | None = None
        self._context: ModbusServerContext | None = None
        self._host = ""
        self._port = 0

    async def run(
        self,
        state: SimState,
        context: ModbusServerContext,
        host: str,
        port: int,
        tick_interval: float,
        stop_event: threading.Event,
        ready: threading.Event,
    ) -> None:
        self._state = state
        self._context = context
        self._host = host
        self._port = port

        # Assigning self._loop is the hand-off point after which
        # set_override() (called from other threads) may safely schedule
        # work onto this loop -- safe by construction: __main__.py only
        # starts the control API (the only other caller) after `ready`
        # is set below, which happens strictly after this assignment.
        self._loop = asyncio.get_running_loop()
        await self._bring_online()
        ready.set()

        while not stop_event.is_set():
            await self._apply_now()
            await asyncio.sleep(tick_interval)

        await self._bring_offline()

    def set_override(self, offline: bool | None) -> None:
        """offline=True forces offline, False forces online, None clears
        back to auto (scenario-driven). Blocks until the change is
        actually applied on the connectivity loop, so a caller (e.g. the
        control API) only returns once it's really taken effect."""
        with self._lock:
            self._override = offline
        loop = self._loop
        if loop is None:
            return  # run() hasn't started yet -- its first _apply_now() will pick up the initial value
        future = asyncio.run_coroutine_threadsafe(self._apply_now(), loop)
        future.result(timeout=5)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {"override": self._override, "online": self._online}

    def _desired_online(self) -> bool:
        with self._lock:
            override = self._override
        if override is not None:
            return not override
        assert self._state is not None
        mode, scenario, start_time, speed = self._state.snapshot()
        if mode == "scenario" and scenario is not None:
            elapsed = elapsed_seconds(scenario, start_time, speed)
            return not scenario.is_offline_at(elapsed)
        return True

    async def _apply_now(self) -> None:
        desired = self._desired_online()
        if desired and self._server is None:
            await self._bring_online()
        elif not desired and self._server is not None:
            await self._bring_offline()

    async def _bring_online(self) -> None:
        assert self._context is not None
        server = ModbusTcpServer(self._context, Framer.SOCKET, None, (self._host, self._port))
        await server.listen()
        self._server = server
        with self._lock:
            self._online = True
        log.info("Modbus TCP server online on %s:%d", self._host, self._port)

    async def _bring_offline(self) -> None:
        if self._server is not None:
            await self._server.shutdown()
            self._server = None
        with self._lock:
            self._online = False
        log.info("Modbus TCP server offline")


def run_forever(
    controller: ConnectivityController,
    state: SimState,
    context: ModbusServerContext,
    host: str,
    port: int,
    tick_interval: float,
    stop_event: threading.Event,
    ready: threading.Event,
) -> None:
    """Thread target: owns this thread's asyncio event loop for the
    lifetime of the connectivity controller's run() coroutine."""
    asyncio.run(controller.run(state, context, host, port, tick_interval, stop_event, ready))
