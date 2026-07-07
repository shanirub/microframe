# CLAUDE.md — Mainframe Simulation

Agent guidance for working in this repo. Read this before making changes.

## What this project is
An educational simulation of a banking mainframe. A Raspberry Pi 3B+ is the
central complex (CICS router, transaction processor, JES, SQLite) running as
separate Python processes; four ESP32-C3 MCUs are channel peripherals on a shared
CAN bus. Full context: `docs/design/system-design.md` and `docs/decisions/`.

## Load-bearing rules (do not violate)
- **Money is integer cents, never float.** Everywhere — firmware, protocol, DB.
- **The Pi mediates all traffic.** No MCU↔MCU messaging. (#3 does not exist — it
  was the retired DB controller.)
- **A business "no" is a result, not an error.** INSUFFICIENT_FUNDS / NOT_FOUND
  ride the result payload, never the ERROR channel (protocol-spec §7.4).
- **`docs/design/protocol-spec.md` §1–§7 are LOCKED.** Do not relitigate framing,
  the CAN ID scheme, or the type registry. Byte maps come from §7.7 verbatim —
  never invent field offsets.
- **Verify, don't assume.** For any FreeRTOS/ESP-IDF symbol, use the `mcp-api-doc`
  skill before writing code. For hardware, check the physical part / datasheet
  before depending on it.

## Documentation model
- **ADRs (`docs/decisions/`) are immutable.** Supersede, never edit.
- **Everything else is living** — design, spec, BOM, requirements, roadmap,
  glossaries. Update them as decisions are made (docs-as-we-go).
- Record lessons in `docs/design/learning-log.md`; project goals in
  `docs/design/charter.md`.
- `docs/design/RETIRED-message_protocol.md` describes the OLD architecture — it is
  a read-only traceability artifact, NOT a live spec.

## Where things are
- `docs/decisions/` — ADRs (why)
- `docs/design/` — system-design, protocol-spec (locked), BOM, requirements,
  roadmap, bring-up-checklist, charter, learning-log
- `docs/learning notes/` — glossaries, planning-process
- `code/pi/` — Raspberry Pi subsystems (Python). See `code/pi/CLAUDE.md`.
- `code/` (MCU firmware) — added per node as bring-up reaches it (roadmap M1+).

## Current state (2026-07-01)
Planning complete; hardware arrived. Working the Pi software track (roadmap
T-P1…T-P3) in parallel while bench bring-up (M0) proceeds. Bus runs at 125 kbit/s
for bring-up (bring-up-checklist §2.5).

## Working style
Options-with-reasoning before recommendations; the human decides. Ask, don't
assume. Professional terms with a brief inline gloss. Keep estimates calibrated
and honest.
