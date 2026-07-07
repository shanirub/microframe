# CLAUDE.md — Pi subsystems (`code/pi/`)

Python code for the Raspberry Pi central complex. Read the root `CLAUDE.md` first
for project-wide rules.

## Layout
`src/` layout, one installable package `mainframe_pi` with a submodule per
subsystem (each runs as its own process — ADR-0001 separate address spaces):

- `common/` — node IDs, CAN config, provisional timeouts (single source of truth)
- `storage/` — SQLite + WAL + write-ahead pattern. **Built and tested (T-P1).**
- `protocol/` — wire codec. **Deliberate stub** — byte maps come from
  protocol-spec §7.7 in T-P2/M3. Do not invent field layouts.
- `router/` — CICS-analogue (T-P2, M3). Not yet implemented.
- `processor/` — transaction logic (T-P3, M3). Not yet implemented.
- `jes/` — job entry subsystem (M5). Not yet implemented.
- `liveness/` — heartbeat tracker (M2). Not yet implemented.

## Env & tooling
- Target Python **>=3.11** (Pi runs 3.13). `pyproject.toml`, hatchling backend.
- Dev setup: `pip install -e '.[dev]'` (or `uv pip install -e '.[dev]'`).
- Test: `pytest` (configured with `pythonpath = ["src"]`, so no install needed
  to run tests).
- Lint/type: `ruff check src` and `mypy` (strict).

## ISO-TP — critical design constraint (verified 2026-07-01)
- Package: `can-isotp>=2.0.7` (import `isotp`). **v2.x is NOT compatible with
  v1.x** — ignore v1.x tutorials (`isotp.socket.bind` now needs `isotp.Address`).
- **Use `isotp.NotifierBasedCanStack`, NOT `CanStack`.** `CanStack` drains the RX
  queue via `bus.recv` and would starve the liveness reader sharing `can0`.
  `NotifierBasedCanStack` fans frames out via a `can.Notifier` so both the ISO-TP
  layer and the liveness tracker receive traffic.
- The transport `error_handler` fires on a **different thread** — marshal errors
  to the main loop before emitting an ERROR frame. Receive timeouts raise an
  exception (they no longer return None in v2.x).

## Conventions
- Money is `int` cents. Balances and amounts are never float.
- Storage is single-writer. Don't add a second writer to SQLite.
- Keep provisional timeouts in `common/` and cross-reference bring-up-checklist §7
  so they get replaced with measured values, not hardcoded ad hoc.
