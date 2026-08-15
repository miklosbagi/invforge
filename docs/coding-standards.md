# Coding standards — InvForge (Python)

InvForge is internal test tooling (a fake Modbus TCP inverter/BESS for
integration testing), not the contributed/sellable artifact — the
[nut-sigenergy](../../nut-sigenergy) driver is. That changes the risk
profile (no hardware safety consequence from a bug here, no upstream
maintainers to satisfy) but not the bar for correctness: a wrong or
flaky emulator gives false confidence in the driver it's supposed to be
validating, which is worse than no emulator at all.

Enforced by the `invforge-review` skill (`.claude/skills/invforge-review/`),
which **must** be run before any push.

## Language choice

Python, confirmed 2026-08-14 (not re-litigated per push — see
[nut-sigenergy](../../nut-sigenergy)'s memory for context; revisit only on
a real limitation, not a preference). Rationale: `pymodbus` gives a
mature Modbus TCP *server* implementation for free, and Python's
ecosystem (`pyyaml`, `fastapi`) is well suited to declarative
YAML-driven scenario scripting and a small HTTP control surface — the
same reasoning `sigennut`'s original PRD used to keep its simulator in
Python even after its driver moved to Go. There is no comparable
lower-effort story for this specific job in a compiled/typed language.

## General engineering rules (adapted from the driver's C rules)

- Optimize first for correctness, simplicity, readability, and
  maintainability. Optimize for cleverness last.
- Before implementation, understand the existing engine
  (`invforge/core/`) — registers, profile, scenario, server, control
  API — and extend it rather than introducing a parallel mechanism.
  Vendor differences belong in `invforge/profiles/<vendor>/`, not as
  special-casing inside `core/`.
- Follow the existing style in this repo exactly (see "Tooling" below)
  over generic PEP 8 preference where they conflict.
- Keep control flow obvious. Prefer small, cohesive functions/methods
  with one clear responsibility. Avoid unnecessary abstraction,
  indirection, and premature generalization — this codebase generalized
  once already (single-vendor → multi-vendor); do not generalize a
  second time ahead of a second concrete need.
- Use type hints everywhere (`from __future__ import annotations` +
  annotations, per the existing modules) — this is a small codebase
  without a runtime type system, hints are the primary defense against
  wrong-shape data crossing module boundaries.
- Treat every external boundary as untrusted input and validate there:
  scenario YAML content, HTTP request bodies (already Pydantic-modeled —
  keep it that way, don't hand-parse JSON), Modbus wire data. Don't
  re-validate internal values whose shape a prior boundary already
  established.
- Check every operation that can meaningfully fail (file I/O, YAML
  parsing, dict lookups against attacker/test-controlled register
  addresses). Never silently swallow an unexpected exception.
- Names communicate domain meaning (`reg`, `raw`, `unit`, `elapsed` are
  fine in the narrow scopes the existing code uses them in — vague names
  like `data`/`tmp`/`thing` are not).
- Comments explain *why* — a hardware quirk, a protocol constraint, a
  non-obvious invariant (see `registers.py`'s comment on `30281`) — never
  what the code already says.
- Keep patches cohesive: don't mix a scenario/register change with an
  unrelated refactor.
- Do not add a dependency for something the standard library or an
  already-present dependency (`pymodbus`, `pyyaml`, `fastapi`,
  `uvicorn`) already does adequately.

## Before declaring a change complete, review it for

- correctness against the fixture(s) it touches — run the real recorded
  captures, not just synthetic scenarios;
- boundary conditions (empty scenario, register at a unit's block
  boundary, malformed/partial YAML);
- resource cleanup (threads, sockets) on every exit path;
- type-hint accuracy;
- test coverage (`tests/`) for the behavior actually changed;
- consistency with `invforge/core/`'s existing conventions;
- whether a vendor-specific quirk leaked into `core/` instead of staying
  in its profile.

## Tooling

- **Format/lint**: `ruff` (format + lint in one tool, fast, minimal
  config surface — add `pyproject.toml` config the first time a rule
  needs tuning, don't pre-configure speculatively).
- **Types**: `mypy --strict` on `invforge/`.
- **Tests**: `tests/unit/` (fast, no network — `pytest tests/unit`,
  `test_sigenergy_profile.py` is the reference example: loads every
  scenario YAML, decodes known values from a real capture, and confirms
  the real illegal-address exception reproduces) and `tests/integration/`
  (real Modbus TCP + HTTP against a running instance — see
  `scripts/integration-test.sh`, needs Docker). Run against real
  fixtures where they exist, not just synthetic ones.
- Treat new lint/type warnings as defects, same as the driver's compiler
  warnings.

## Adding a vendor profile

See the main `README.md`'s "Adding a new vendor profile" section for the
mechanical steps. In addition: every new profile needs at least one
`scenarios/recorded/` fixture before it's trusted for anything beyond
"the engine can load it" — a profile built entirely from invented
register values gives the same false confidence a driver built against
unverified register addresses would (see
`nut-sigenergy/docs/driver-coding-standards.md`'s note on `sigennut`'s
R1/R11).
