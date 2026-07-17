# Pi Subsystems

Raspberry Pi central-complex code for the Mainframe Simulation. Four subsystems
run as separate processes (CICS router, transaction processor, JES, liveness
tracker) sharing SQLite storage and a CAN wire codec.

## Setup

```bash
cd code/pi

# uv (recommended — reads uv.lock, no separate venv activation step needed)
uv sync --extra dev

# or: venv + pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Test

```bash
# with uv (prefix every invocation with `uv run` — no activation step):
uv run pytest -v             # pythonpath is configured; no separate install needed
uv run ruff check .          # lint
uv run mypy                  # type-check (config in pyproject.toml points at src/)

# with an activated venv (pip path above), drop the `uv run` prefix:
pytest -v
ruff check .
mypy
```

Same three checks run in CI on every push/PR — see `.github/workflows/ci.yml`.

## Status (2026-07-16)

| Module | Roadmap task | State |
|--------|--------------|-------|
| `storage` | T-P1 | Built + tested (WAL, write-ahead pattern, 8 tests passing) |
| `protocol` | T-P2/M3 | Deliberate stub — byte maps from protocol-spec §7.7 |
| `router` | T-P2 | Not started |
| `processor` | T-P3 | Built + tested (logical-in/logical-out `handle()`, 7 tests passing) |
| `liveness` | M2 | Not started |
| `jes` | M5 | Not started |

`python-can` on the Pi — verified (imports and opens sockets; SocketCAN fan-out
confirmed on `vcan0`). 15/15 tests passing across `storage` + `processor`.

Next: T-P2 (router) is unblocked and next on the roadmap's dependency graph —
owns ingress decode, UUID minting (§2), the `tag ↔ UUID` binding, and egress
encode (ADR-0002). T-P4/`jes` and the `liveness` reader are also unblocked and
testable on `vcan0` today. See `../../docs/design/roadmap.md`.

## Notes

- Money is integer cents throughout. Never float.
- ISO-TP: use `NotifierBasedCanStack` (not `CanStack`) to avoid starving the
  liveness reader on shared `can0`. See `CLAUDE.md`.
- Bus runs at 125 kbit/s for bring-up (see `../../docs/design/bring-up-checklist.md`).