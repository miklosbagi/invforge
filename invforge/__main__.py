"""Entrypoint: starts the Modbus TCP server lifecycle (background
thread, via core/connectivity.py), the scenario ticker (background
thread), and the HTTP control API (main thread, via uvicorn) for a
chosen vendor profile. See core/control_api.py for the remote-control
surface a test runner uses.
"""

from __future__ import annotations

import argparse
import logging
import threading

import uvicorn

from . import profiles
from .core import server as sim_server
from .core.connectivity import ConnectivityController, run_forever
from .core.control_api import create_app
from .core.state import SimState

log = logging.getLogger("invforge")


def main() -> None:
    parser = argparse.ArgumentParser(description="InvForge -- multi-vendor inverter/BESS Modbus TCP emulator")
    parser.add_argument(
        "--vendor", default="sigenergy", choices=sorted(profiles.VENDORS), help="vendor profile to emulate"
    )
    parser.add_argument(
        "--firmware",
        default=None,
        help="firmware version to emulate (default: the vendor's only confirmed firmware, if exactly one)",
    )
    parser.add_argument("--modbus-host", default="0.0.0.0")
    parser.add_argument("--modbus-port", type=int, default=502)
    parser.add_argument("--control-host", default="0.0.0.0")
    parser.add_argument("--control-port", type=int, default=8080)
    parser.add_argument("--scenario", default=None, help="optional scenario name to preload at startup")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--tick", type=float, default=0.25)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    try:
        firmware = args.firmware or profiles.default_firmware(args.vendor)
        profile = profiles.get(args.vendor, firmware)
    except KeyError as e:
        parser.error(str(e))
        return
    blocks = sim_server.build_blocks(profile)
    context = sim_server.build_context(blocks)
    state = SimState()

    if args.scenario:
        from .core.state import resolve_scenario

        try:
            scenario = resolve_scenario(args.scenario, profile)
        except (KeyError, ValueError) as e:
            parser.error(str(e))
            return
        sim_server.apply_exceptions(blocks, scenario)
        sim_server.write_scenario_statics(blocks, profile, scenario)
        state.set_scenario(scenario, speed=args.speed)

    stop_event = threading.Event()
    ticker = threading.Thread(
        target=sim_server.run_ticker,
        args=(state, blocks, profile, args.tick, stop_event),
        daemon=True,
    )
    ticker.start()

    connectivity = ConnectivityController()
    modbus_ready = threading.Event()
    modbus_thread = threading.Thread(
        target=run_forever,
        args=(connectivity, state, context, args.modbus_host, args.modbus_port, args.tick, stop_event, modbus_ready),
        daemon=True,
    )
    modbus_thread.start()
    if not modbus_ready.wait(timeout=5):
        log.warning("Modbus TCP server did not report ready within 5s -- continuing anyway")

    app = create_app(profile, blocks, state, connectivity)
    try:
        uvicorn.run(
            app, host=args.control_host, port=args.control_port, log_level="info" if args.verbose else "warning"
        )
    finally:
        stop_event.set()
        ticker.join(timeout=2)
        modbus_thread.join(timeout=2)


if __name__ == "__main__":
    main()
