---
name: invforge-review
description: Mandatory pre-push review for InvForge (Python). Runs ruff/mypy/pytest gates and reviews changed files against docs/coding-standards.md. Must be run and must pass before any `git push` in this repo.
---

# InvForge pre-push review

This is a **mandatory gate**, not an optional lint pass. No commit in this
repo gets pushed without this skill having been run against it and having
reported a clean result. If you are about to `git push` in this repo and
haven't run this skill against the commits being pushed, run it first.

## 1. Scope the review

Determine what's changed and being pushed:

```sh
git status --short
git diff --stat $(git merge-base HEAD origin/main 2>/dev/null || echo HEAD)..HEAD
```

If there's no `origin/main` yet (new repo, nothing pushed), review
everything staged/committed so far instead.

## 2. Mechanical gates — all must pass with zero errors/warnings

Run from the repo root, using the project venv:

```sh
.venv/bin/ruff format --check invforge tests
.venv/bin/ruff check invforge tests
.venv/bin/mypy
.venv/bin/python -m pytest tests/unit -q
```

`tests/unit/` is fast and network-free — always run it. If the change
under review touches anything in `invforge/core/connectivity.py`,
`invforge/core/server.py`, `invforge/core/control_api.py`, a scenario
fixture, or the Dockerfile/compose file, also run the integration suite
(needs Docker):

```sh
scripts/integration-test.sh
```

Any failure here is an automatic FAIL — fix it (or, for `ruff format`,
just run `ruff format invforge tests` and re-check) before doing the
semantic review below. Don't hand-wave a mypy or ruff error as
"pre-existing" without confirming it actually predates the change under
review — the whole codebase is expected to be clean at all times, see
`docs/coding-standards.md`.

## 3. Semantic review

Read `docs/coding-standards.md` in full, then walk every changed file
against it. In particular:

- **Correctness against real fixtures**, not just synthetic ones — does
  the change still work against `scenarios/recorded/*.yaml`, not only
  invented scenarios?
- **Boundary conditions**: empty scenario, register at a unit's block
  edge, malformed/partial YAML, an HTTP request with a missing/wrong-typed
  field.
- **Resource cleanup** on every exit path — threads, sockets, the
  ticker's stop_event.
- **Type-hint accuracy** — does the annotation actually match runtime
  behavior, or did mypy only pass because of an `Any` escape hatch
  (`# type: ignore`, unannotated `object`, etc.) that hides a real gap?
  Every `# type: ignore` in this codebase should have a comment
  explaining why (see `core/server.py`'s pymodbus-subclassing comment as
  the reference example) — a bare, unexplained one is itself a finding.
- **Test coverage** for the behavior actually changed — a new code path
  with no corresponding test is a finding, not just a suggestion.
- **Consistency with `invforge/core/`'s conventions** — did a
  vendor-specific quirk leak into `core/` instead of staying inside its
  `invforge/profiles/<vendor>/`? That's an architecture violation, not a
  style nit.
- **New dependency scrutiny** — anything added to `requirements.txt`
  that the stdlib or an existing dependency already covers is a finding.

## 4. Report

Use the `ReportFindings` tool with the verified findings, most severe
first. If nothing survives review, call it with an empty findings list —
don't skip the call.

## 5. Verdict

State explicitly, in plain text after the findings:

- **PASS — safe to push** if all mechanical gates passed and no
  CONFIRMED correctness finding remains, or
- **FAIL — do not push** otherwise, naming exactly what has to change
  first.

Do not push on a FAIL verdict, even if the user seems to be in a hurry —
say so and let them explicitly override if they choose to.
