🇬🇧 [English](README.md) | 🇭🇺 [Magyar](README.hu.md)

# InvForge

A fake Modbus TCP inverter/BESS, for testing Modbus-speaking clients
(NUT drivers, monitoring tools, anything else) without real hardware.
Multi-vendor by design: the Modbus/scenario/control-API engine is
vendor-agnostic (`invforge/core/`), and each vendor's register map,
units, and scenario fixtures live in their own profile
(`invforge/profiles/<vendor>/`).

Originally extracted and generalized from a single-vendor Sigenergy
simulator built for [sigennut](https://github.com/miklosbagi/sigennut);
ported here as the first profile (`invforge/profiles/sigenergy/`) so the
same emulator can grow to cover other inverter/BESS families
(Deye/SunSynk, Victron GX, Growatt, SolarEdge, ...) as they're needed by
the NUT driver work sigennut supports, or other consumers.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m invforge --vendor sigenergy --firmware V100R001C21SPC116 \
    --modbus-port 5020 --control-port 8080 [--scenario <name>]
```

`--firmware` can be omitted when a vendor has exactly one confirmed
firmware (as Sigenergy does today) — `--vendor sigenergy` alone resolves
to it. Once a second firmware is registered for a vendor, `--firmware`
becomes required and an unknown one exits with a clear list of what's
available, rather than silently guessing.

Then point any Modbus TCP client at `127.0.0.1:5020` — same units/register
addresses as the real device the profile models. Sigenergy's SigenStor
uses unit 247 (plant) and unit 1 (inverter strings).

## HTTP control API (port 8080 by default)

The test runner's remote control channel — HTTP+JSON, not gRPC (this is
low-throughput, single-consumer, and this way it's `curl`-able for free
while debugging a failed test).

- `GET /health` — for Docker healthchecks.
- `GET /scenarios` — `{"library": {name: relative_path, ...},
  "generators": [<naming-pattern>, ...]}` for the running profile.
- `POST /scenario {"name": "...", "speed": 1.0}` — loads and starts
  playing back a named scenario's timeseries (wall-clock, scaled by
  `speed`), looping at its duration. `name` resolves against the static
  YAML library first, then the parametric ramp generator (see below) if
  no library fixture matches. Also clears any forced `/fault` override
  back to "auto".
- `POST /fault {"connectivity": "offline"|"online"|"auto"}` — on-demand
  connection-level fault injection: forces the Modbus TCP listener
  offline/online, or clears back to scenario-driven ("auto"). This drops
  the real socket (already-connected clients too), not just a
  register-level Modbus exception. Sticky: takes precedence over a
  scenario's own `offline:` windows until cleared or a new scenario is
  loaded.
- `POST /state {"registers": {"30014": 50, "1:30500": "..."}}` —
  **instant override**: writes directly into the datastore right now and
  freezes the ticker (`mode: "manual"`) so nothing overwrites it until the
  next `/scenario` or `/state` call. A bare address key targets the
  profile's default unit; `"<unit>:<address>"` targets another unit
  explicitly. Values are raw wire values (bare int for single-register
  fields, `[hi, lo]` for S32/U32), same convention as scenario YAML files.
- `GET /state` — current raw+decoded value of every known register on
  every unit, plus current mode/scenario/speed/connectivity — for
  debugging.

## How it works

- `invforge/core/registers.py` — vendor-agnostic register model
  (address/count/dtype/gain/unit/dynamic) plus encode/decode helpers.
- `invforge/core/profile.py` — a `Profile` bundles one vendor+firmware's
  register list, default unit, and scenario fixtures directory. Register
  addresses/layouts shift across firmware versions in the real world
  (see `nut-sigenergy/docs/driver-coding-standards.md`'s note on
  Sigenergy's own firmware history), so a `Profile` is scoped to one
  specific firmware, not a whole vendor — see "Adding a new vendor
  profile" below.
- `invforge/core/scenario.py` — loads a scenario YAML (`static` /
  `timeseries` / `exceptions`), linearly interpolates numeric registers
  between consecutive timeseries samples in raw wire-value space.
- `invforge/core/server.py` — a pymodbus TCP server with one datastore
  block per unit id the profile defines. A background thread ticks
  registers marked `dynamic=True` forward on a wall-clock timer
  (`--speed` multiplier, `--tick` interval), decoupled from request
  handling — same as a real device's telemetry loop being independent of
  what a client happens to poll. Loops back to `t=0` once a scenario's
  duration elapses.
- `invforge/core/generator.py` — parametric ramp-scenario generator
  (see "Parametric ramp scenarios" below); vendor-agnostic mechanism
  only, a profile supplies the actual ramp-building logic via
  `Profile.ramp_builder`.
- `invforge/core/connectivity.py` — owns the live Modbus TCP listener's
  online/offline lifecycle (see "Offline / connection-drop simulation"
  below).
- `invforge/core/control_api.py` — the FastAPI control surface above.
- `invforge/profiles/<vendor>/firmwares/<firmware>/` — a `registers.py`
  (the `RegisterDef` list), a `scenarios/` directory, and an
  `__init__.py` exporting `PROFILE: Profile`. See
  `invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/` as the
  reference example.

Unmapped registers fail Modbus reads the same way a real device would
(illegal data address) — a datastore's own address bounds handle this
natively for registers never defined at all; a scenario's `exceptions:`
block can mark any other address as always-illegal too, for asserting a
client handles a real firmware's odd 400-response quirks correctly.

Some real firmware also rejects specific addresses as a read's
*starting* address specifically — a legitimate, in-range register that
simply can't be the first address of a Modbus request, even though a
range read starting elsewhere and covering it works fine. Confirmed
empirically against real Sigenergy hardware (register `30281`). This is
a permanent per-firmware trait, not scenario data, so it's modeled
separately: `Profile.non_anchor_addresses` (a frozenset of addresses),
enforced by every block regardless of which scenario is loaded. See
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/registers.py`'s
module docstring for the full story.

Sigenergy's own register table is deliberately not the full ~280-entry
spec — see that same module docstring for scope (the subset relevant to
a UPS/battery-backup driver, matching what the specific real
installation this was validated against actually has).

## Adding a new vendor profile

1. Create `invforge/profiles/<vendor>/firmwares/<firmware>/registers.py`
   with a `REGISTERS: list[RegisterDef]` and a `DEFAULT_UNIT: int`. Use
   the exact firmware version string as the directory name — this is
   also what `Profile.firmware` and `--firmware` resolve against, no
   slugifying/casing translation.
2. Create `invforge/profiles/<vendor>/firmwares/<firmware>/__init__.py`
   exporting a module-level `PROFILE: Profile` (see
   `invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/__init__.py`).
3. Add `invforge/profiles/<vendor>/__init__.py` exporting a
   `FIRMWARES: dict[str, Profile]` (see
   `invforge/profiles/sigenergy/__init__.py`), and register it in
   `invforge/profiles/__init__.py`'s `_load()`.
4. Add `scenarios/recorded/` (real captures, ground truth — validate
   anything testing against this profile against these before trusting a
   synthetic scenario) and/or `scenarios/synthetic/` (invented ramps,
   edge cases, bad-data — see below) YAML fixtures under
   `invforge/profiles/<vendor>/firmwares/<firmware>/scenarios/`. Since
   raw register addresses are firmware-specific, scenarios live under
   the firmware they were captured against/written for, not shared
   loosely across a vendor's firmware versions — a second firmware with
   different addresses must not be able to silently misinterpret an old
   scenario file.
5. A second confirmed firmware for an existing vendor is a new sibling
   directory under that vendor's `firmwares/`, nothing else changes.

## Scenario YAML format

```yaml
static:
  unit_<n>: { <address>: <raw int|word-list|string>, ... }
timeseries:
  - t: <seconds>
    <address>: <raw int|word-list>   # omit a register at a sample to mean
    ...                               # "not sampled here", not "zero" --
                                       # carries forward. Applies to the
                                       # profile's default_unit.
exceptions:
  unit_<n>: { <address>: {function_code: <n>, exception_code: <n>} }
offline:
  - { start: <seconds>, end: <seconds> }   # Modbus TCP is unreachable
    ...                                      # during each [start, end)
                                               # window, elapsed scenario
                                               # time.
```

All numeric values are RAW wire values (pre-gain), never the decoded
real-world value — a bare int for single-register fields, a `[hi, lo]`
word list for multi-register (S32/U32) fields.

## Parametric ramp scenarios

For common linear ramps, a scenario name matching
`linear-<drain|charge>-<start>-to-<end>-<duration>s` (e.g.
`linear-drain-100-to-0-60s`) is computed on the fly instead of needing a
hand-written YAML file per exact numeric variant — see
`invforge/core/generator.py`. Purely additive to the YAML library: an
existing fixture of the same name always wins on a collision. Requires
the profile to supply a `ramp_builder` (see
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/ramps.py` for
the reference example — it derives ramp power from the rated capacity
and requested SoC delta/duration rather than a guessed constant).
Invalid ramps (non-positive duration, a `drain` that doesn't decrease,
a `charge` that doesn't increase) are rejected with `ValueError`
(`POST /scenario` → HTTP 400).

## Offline / connection-drop simulation

A scenario's `offline:` section (above), or an on-demand
`POST /fault` call, makes the Modbus TCP listener genuinely unreachable
for a window — a real dropped/refused connection, not a Modbus-level
exception — simulating a device actually going offline (power loss,
network outage, Modbus support revoked). See
`invforge/core/connectivity.py`'s module docstring for how this is
implemented against pymodbus (constructing `ModbusTcpServer` directly
inside its own asyncio loop, since the blocking `StartTcpServer`
convenience wrapper can't be stopped/restarted from outside once
running) and why other Modbus exception codes (`SlaveBusy`,
`GatewayNoResponse`, etc.) aren't reachable through pymodbus's datastore
`validate()` path the way `IllegalAddress` is.

## Bad-data scenarios

A category of `scenarios/synthetic/` fixtures that need zero new engine
mechanism — just a deliberately out-of-spec `static:` value, since the
engine already writes whatever raw value a YAML gives it. These exist to
test whether a driver validates data rather than trusting it blindly:
wire-legal register encodings can still decode to values that are
physically/semantically impossible (a real firmware bug or a corrupted
read could hand a driver exactly this). See
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/scenarios/synthetic/`:

- `bad-data-soc-over-100.yaml` — `battery.charge`-equivalent register
  decodes to 101.0%.
- `bad-data-soh-over-100.yaml` — state-of-health register decodes to
  150.0%.
- `bad-data-pv-power-negative.yaml` — a magnitude-only (generation)
  power register decodes negative. Chosen over the bidirectional
  charge/discharge or import/export power registers, where negative is
  legitimately meaningful by design.

## Docker

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

Maps modbus `5020:502` and control-API `8080:8080` (matching the
Quickstart above). The image's `ENTRYPOINT` is `python -m invforge`
with a `CMD` giving sane defaults (`--vendor sigenergy --firmware
V100R001C21SPC116 ...`); override vendor/firmware/scenario per the
"param via Docker" pattern:

```bash
docker run <image> --vendor sigenergy --firmware V100R001C21SPC116 --scenario ramp-discharge-100-to-0
```

or a `command:` override in `docker-compose.yml`. `GET /health` backs
the container `HEALTHCHECK`.

## Testing

- `tests/unit/` — fast, no network: `pytest tests/unit -q`.
- `tests/integration/` — real Modbus TCP + HTTP against a running
  instance. One-command local run (build, wait for healthy, run, tear
  down): `scripts/integration-test.sh`. In CI
  (`.github/workflows/ci.yml`), the same steps run as two jobs (`unit`,
  `integration`) so a lint/type/unit failure fails fast before Docker
  ever builds.
- Every push to this repo must pass the `invforge-review` skill
  (`.claude/skills/invforge-review/`) first — see `CLAUDE.md`.

## License

MIT (`LICENSE`) — this is test tooling, not a sellable artifact; no
reason to restrict use.
