# Pi Subsystems

Raspberry Pi central-complex code for the Mainframe Simulation. Four subsystems
run as separate processes (CICS router, transaction processor, JES, liveness
tracker) sharing SQLite storage and a CAN wire codec.

## Setup

```bash
cd code/pi
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'      # or: uv pip install -e '.[dev]'
```

## Test

```bash
pytest                       # pythonpath is configured; no install needed just to test
```

## Status (2026-07-01)

| Module | Roadmap task | State |
|--------|--------------|-------|
| `storage` | T-P1 | Built + tested (WAL, write-ahead pattern, 6 tests passing) |
| `protocol` | T-P2/M3 | Deliberate stub — byte maps from protocol-spec §7.7 |
| `router` | T-P2 | Not started |
| `processor` | T-P3 | Not started |
| `liveness` | M2 | Not started |
| `jes` | M5 | Not started |

Next: verify `python-can` on the Pi, then T-P3 (processor) which builds on the
tested storage layer. See `../../docs/design/roadmap.md`.

## Notes

- Money is integer cents throughout. Never float.
- ISO-TP: use `NotifierBasedCanStack` (not `CanStack`) to avoid starving the
  liveness reader on shared `can0`. See `CLAUDE.md`.
- Bus runs at 125 kbit/s for bring-up (see `../../docs/design/bring-up-checklist.md`).
