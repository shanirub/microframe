# ADR-0003: Liveness runs as its own process with a read-only SocketCAN socket (kernel fan-out)

## Status
Accepted — 2026-07-10
Extends ADR-0001 (separate address spaces, one process per subsystem). Does not
supersede it — it resolves how "separate address spaces" applies to the liveness
tracker, a concern ADR-0001 never explicitly placed.

---

## Context

ADR-0001 mandated **one process per subsystem, in separate address spaces**. A
later design note on the router (2026-07-01, ISO-TP verification) established the
use of `isotp.NotifierBasedCanStack` over `CanStack`, so that multiple consumers
sharing `can0` are fed by a single `can.Notifier` and one does not starve the
other by draining `bus.recv`.

Read literally, that note implies the **liveness tracker shares the router's
in-process `can.Notifier`**. But a `can.Notifier` is an **in-process object** — a
background thread fanning frames to listeners in the *same* address space.
Sharing it would require liveness and the ISO-TP stack to live in **one process**,
which contradicts ADR-0001's one-process-each. So the notifier decision (a
sound, still-valid *design* choice) silently assumed an *architecture* choice —
where liveness lives — that was never made. This ADR makes it.

A second consideration: liveness is a **monitoring** concern, and monitoring is
**not part of CICS**. Folding it into the CICS router (the TOR-analogue) is a
fidelity cost as well as an isolation cost.

---

## Decision

**Liveness runs as its own process (per ADR-0001) and opens its own
receive-only SocketCAN socket on `can0`, with a kernel `can_filter` for the
HEARTBEAT identifiers.**

- SocketCAN delivers a **copy of every matching frame to every socket** bound to
  the interface. So the router and liveness each receive heartbeats
  independently — **no cross-process frame plumbing, and no shared notifier.**
- The router's `can.Notifier` is therefore a **purely intra-router** mechanism:
  it fans frames to the router's *own* in-process consumers (the ISO-TP stack,
  and any future in-process reader). The 2026-07-01 note is re-scoped to say
  exactly that — a documentation correction, not a redesign.
- Liveness **does not transmit.** Its socket is receive-only; any Pi-originated
  frame goes through the router (ADR-0002).

### Verification
The property this rests on — two sockets on one interface each receiving a copy —
is a **SocketCAN kernel behaviour**, independent of the MCP2515 hardware, so it is
valid to confirm it on a virtual CAN interface (`vcan0`). Status at time of
writing: the software stack is present and SocketCAN-capable (`python-can` 4.6.1,
`can-isotp` 2.0.7; `socket.AF_CAN` and `socket.CAN_RAW` available), but the
dual-delivery test itself has **not yet been run against a live interface** — the
planning environment had no CAN-capable kernel. Run `verify_socketcan_fanout.py`
on the Pi (or on any host with `vcan`) to close this. Ties to the open bring-up
thread "confirm `python-can` against a live `can0`."

---

## Alternatives considered

- **Co-host liveness + the ISO-TP stack in one process and share the in-process
  notifier.** This is what the literal 2026-07-01 note implied. Rejected: it
  violates ADR-0001's one-process-each; it **couples failure domains** (a router
  crash takes liveness down with it); and it folds a non-CICS monitoring concern
  into the CICS region. The note is being re-scoped precisely because this reading
  was unintended.
- **A dedicated bus-reader process** that owns `can0` and fans frames to both the
  router and liveness over IPC — a software analogue of a mainframe *access
  method* (the layer that owns the physical lines and hands data up to regions).
  Higher fidelity to a line-owning region, but a whole new process plus an IPC
  fan-out, and another failure domain. Kept on file for later, if a single owner
  of `can0` becomes desirable (e.g. if socket count or filtering grows).

---

## Consequences

- **Two sockets** are bound to `can0` (router RX/TX; liveness RX-only). Each must
  set its own kernel filter set so liveness is not woken for ISO-TP traffic and
  the router is not woken for bare heartbeats it does not consume.
- **Failure isolation:** liveness and the router crash and restart independently —
  a real benefit for a monitoring process, which should outlive the thing it
  monitors.
- The router docstring's "shared `can.Notifier`" note is corrected to
  "intra-router only." Record the re-scoping in `learning-log.md`.
- **Open item, not resolved here — how the liveness verdict reaches Console #1.**
  Requirement §4.1 requires the console to show live/dead per node, but the locked
  §7 type registry has **no node-status message**. The most likely reading is that
  Console #1 (itself on the bus) derives status by listening to heartbeats
  directly, in which case the Pi transmits nothing for liveness at all. If instead
  the Pi must *push* status, that frame would go through the router (ADR-0002) and
  would need a new message type — but protocol-spec §1–§7 are **locked**, so that
  is a separate decision. Flagged, not decided.
