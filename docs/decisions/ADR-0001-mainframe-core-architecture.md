# ADR-0001: Mainframe-core architecture — RPi central complex, ESP32-C3 channels, shared CAN bus

## Status
Accepted — 2026-06-18
Foundational ADR for the successor project. Lineage: the previous project was
retired in its ADR-012 ("Retire the shared-bus subsystem architecture").

---

## Context

The previous project placed five co-equal subsystems on a shared **I2C** bus
and tried to make the Raspberry Pi an I2C slave. It was retired (prior ADR-012)
after diagnosing the recurring failures as a structural mismatch: I2C used for
two roles it is poorly suited to — multi-master peer messaging with runtime
master/slave mode-switching, and slave mode on devices with weak slave support
(ESP32 slave init, Linux/BSC slave).

The functional goal is unchanged: a minimal analogue of **CICS** — a request
arrives, is routed to the right subsystem, touches durable storage, and is
acknowledged — covering heartbeat/liveness and a deposit/withdraw/balance flow
that survives a reboot. This ADR re-grounds *how* that is delivered, from first
principles, across three questions: what is the bus, who computes, and where
storage lives.

---

## Decision

**1. The Raspberry Pi 3B+ is the mainframe central complex.**
The CICS-analogue (router/dispatcher), the transaction processor, and the job
scheduler (JES) run **on the Pi as separate Python processes**, communicating
via local IPC (sockets / queues). Durable storage (SQLite, WAL mode) is **local
to the Pi**. This mirrors how a real mainframe is actually structured — those
subsystems are software running in separate address spaces on the central
complex, not separate physical machines — and it moves the hard
"subsystem-to-subsystem over a bus" problem into reliable, observable local IPC.

**2. The four ESP32-C3 MCUs are channel-attached peripherals**, not co-equal bus
subsystems:

| MCU | Channel role | Mainframe analogue |
|-----|--------------|--------------------|
| #1  | Operator Console | System console / operator interface |
| #2  | Transaction Terminal | 3270-style terminal |
| #4  | Job Submitter | Card reader / job-stream driver into JES |
| #5  | Output Writer | Printer / output writer (OLED-only until printer rejoins) |

**3. The inter-device bus is CAN** (Controller Area Network). Each MCU uses its
on-chip TWAI controller via an external SN65HVD230 (3.3V) transceiver; the Pi
joins via an MCP2515 CAN HAT exposed through Linux SocketCAN. All nodes are CAN
**peers** — message addressing and arbitration are done in hardware, so there is
**no slave mode and no master/slave mode-switching anywhere**. This directly
removes the class of failure that retired the previous project.

**4. Conventions for correctness and testability.** All monetary values are
integer cents (never float). Every transaction carries a UUID; the durable log
retains the UUID plus timestamps, which is what makes throughput measurement and
loss/duplicate detection possible under load (see system-design §6).

---

## Alternatives considered

- **RS-485 multidrop bus, master-polled.** Viable and very debuggable, and it
  resembles a mainframe channel polling its control units. Rejected as the
  default because you must hand-build the MAC layer (addressing + polling),
  whereas CAN gives arbitration, ACK, and retransmission in hardware. Kept on
  file as a fallback if CAN bring-up disappoints.
- **SPI star (Pi master, point-to-point).** Cheapest (no transceivers) but
  reintroduces a **slave-mode peripheral** on each MCU — the exact category we
  are leaving. Rejected.
- **Networked / Ethernet.** Maximally reliable but spends the "real shared bus"
  fidelity that is the point of the simulation; turns the project into
  microservices. Rejected for the transport; networking returns only as the
  optional operator dashboard (Phase 2).
- **Keep I2C.** The retired trap. Rejected.
- **Threads vs processes vs containers (Pi).** Threads are lighter but less
  isolated and less faithful. **Processes** chosen for fault isolation and
  fidelity to real mainframe address-space separation. Docker (containers ≈
  LPARs) is a satisfying later isolation upgrade, deferred to keep early focus on
  the protocol/hardware learning.
- **Python vs COBOL.** Python first, for library fit (`sqlite3`, `python-can`)
  and speed of iteration. CICS+COBOL is the canonical mainframe pairing, so a
  later authenticity upgrade is to reimplement *only* the transaction processor
  in GnuCOBOL — the process boundary makes that a drop-in, no other subsystem
  changes.

---

## Consequences

- **New hardware** is required: 5× SN65HVD230 transceivers, 1× Pi CAN HAT, 2×
  120Ω terminators, and 1–2× PCF8574 I2C GPIO expanders (verified pin-budget
  need on the Transaction Terminal — see BOM). Printer and dashboards are
  deferred.
- **CAN frames carry only 8 data bytes**, while messages are ~65–110 bytes. A
  segmentation or compact-encoding scheme is therefore **required** and is the
  first item for the protocol spec (system-design §8). Unlike the 16-byte FIFO
  surprise that retired the last project, this is a documented, designed-for
  constraint with standard solutions (ISO-TP, or compact binary across a few
  frames).
- **Debuggability is preserved**: the logic analyzer decodes CAN (sigrok CAN
  PD), and the Pi can sniff the whole bus with `candump`.
- The previous project's I2C `shared_bus` libraries and the BSC slave code are
  retired; per-node MCU firmware becomes much simpler (no bus mesh, no DB logic).
- I2C does **not** disappear — it remains the private OLED bus on every node and
  the bus for the PCF8574 keypad expander.
