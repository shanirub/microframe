# System Design — Mainframe Simulation (Mainframe-Core Architecture)

> Successor to the retired shared-bus project (prior ADR-012). Architecture
> decision recorded in ADR-0001. This document is the high-level *what* and
> *how*; the detailed CAN message contract is a separate spec, pending the
> open decisions in §8.

---

## 1. Overview

An educational simulation of a banking mainframe. A **Raspberry Pi 3B+** acts as
the central processor complex, running the mainframe's software subsystems as
separate processes; **four ESP32-C3 MCUs** act as channel-attached peripherals
(console, terminal, job submitter, output writer). All devices are peers on a
shared **CAN bus**. The system processes deposit / withdraw / balance
transactions against durable storage and is built to be measured under load.

The point is to understand *why* each piece works at the protocol and hardware
level — not only to make it run.

---

## 2. Subsystem map

**On the Pi — software subsystems (separate Python processes, local IPC):**

| Process | Mainframe analogue | Responsibility |
|---------|--------------------|----------------|
| CICS router | CICS transaction middleware | Receive requests from the bus, route to the right subsystem, return acknowledgements |
| Transaction processor | Central Processor (CP) | Apply deposit/withdraw/balance logic against the database |
| JES | Job Entry Subsystem | Ingest and dispatch jobs (incl. synthetic job streams for load testing) |
| Storage | DASD | SQLite (WAL) — accounts + transaction log, local to the Pi |
| (Phase 2) Operator dashboard | Operator console (web) | Read-only system/health/history web view |

**On the MCUs — channel peripherals (one task per MCU):**

| MCU | Role | Basic peripherals (in hand) | Deferred upgrades |
|-----|------|------------------------------|-------------------|
| #1 | Operator Console | OLED, buttons, LEDs | Richer panel (PCF8574); web dashboard moves to Pi |
| #2 | Transaction Terminal | OLED, 4×4 keypad (via PCF8574), KY-040 encoder | Terminal web form (Phase 2) |
| #4 | Job Submitter | OLED, button(s), LED | RFID "card", transaction generator (Phase 2) |
| #5 | Output Writer | OLED (journal on screen) | CSN-A2 thermal printer (Phase 2+) |

---

## 3. Hardware & bus topology

A single CAN bus (two wires, CANH/CANL, plus common ground) links all five
nodes. Each MCU drives the bus through its on-chip TWAI controller and an
SN65HVD230 (3.3V) transceiver; the Pi joins via an MCP2515 CAN HAT through
SocketCAN (interface `can0`).

- **Termination:** exactly two 120Ω resistors, at the two physical *ends* of the
  bus only (≈60Ω total). Middle nodes must have any onboard termination removed.
- **Common ground:** every node and the Pi share a ground reference with the bus.
- **Speed:** 500 kbit/s default (a short bench bus handles it; can drop to
  125/250k for margin).
- **Debug:** logic analyzer with the sigrok CAN decoder on the bus, or `candump`
  on the Pi to watch every frame.

I2C survives only as each node's private OLED bus, plus the PCF8574 keypad
expander on the Transaction Terminal.

---

## 4. Data flow

**Deposit (end to end):**
```
Terminal (#2): operator enters acct + amount (keypad) and DEPOSIT (encoder), presses confirm
  → Terminal builds a transaction {uuid, DEPOSIT, acct, amount} and sends it on CAN to the Pi
Pi / CICS router: receives the frame(s), routes to the transaction processor
Pi / processor: reads balance, applies deposit, writes to SQLite (PENDING → balance → COMMITTED)
Pi / CICS router: sends an acknowledgement frame back to the Terminal
Terminal (#2): displays result on OLED
Pi / CICS router: sends a journal frame to the Output Writer (#5)
Output Writer (#5): renders the journal line on its OLED (later: prints it)
```

**Balance** is the same without the write step. **Withdraw** adds an
insufficient-funds rejection path (a business result, not a system error).

**Heartbeat / liveness:** the Pi pings each MCU channel on a fixed cadence (or
each MCU pings the Pi); a node that misses its window is flagged on the Operator
Console. Liveness is a per-node ping, not the fragile broadcast-ACK mesh of the
old design.

---

## 5. Data model & durability

SQLite in **WAL mode** (Write-Ahead Log — lets a reader run concurrently with a
writer without blocking), local to the Pi, accessed by the transaction processor
as sole writer.

- `accounts(account_id TEXT PK, balance INTEGER)` — balance in cents, never float.
- `transactions(id TEXT PK /*UUID*/, account_id, txn_type, amount, new_bal,
  status /*PENDING|COMMITTED*/, ts)`.

**Write-ahead pattern (one SQLite transaction, atomic):** insert the row PENDING
→ update the balance → mark the row COMMITTED. On boot, any PENDING rows that
never reached COMMITTED indicate an interrupted write and are replayed or flagged
(crash recovery, later phase). This is what makes a transaction survive a reboot.

---

## 6. Testability & performance measurement

The architecture is built to answer "how many transactions can it sustain, and
does it lose any?" Two ingredients make that measurable:

- **Unique IDs + durable log:** every transaction carries a UUID and lands in the
  log with timestamps, so throughput (rows/sec) and integrity (no drops, no
  duplicates) can be read straight from the database after a run.
- **Two transaction generators** (Phase 2):
  - *On MCU #4 (Job Submitter)* — fires a synthetic job stream over CAN, testing
    realistic **end-to-end** throughput including the bus.
  - *As a Pi-side injector* — feeds transactions directly into the CICS router
    process, bypassing CAN, testing the **core's** ceiling in isolation.
  Comparing the two tells you whether the bus or the database is the bottleneck.

---

## 7. Roadmap (phased)

**Phase 1 — working system (top priority):** CAN bring-up one node at a time;
the three Pi subsystems as processes with local IPC; SQLite with the
write-ahead pattern; Terminal (#2) submits a real deposit/withdraw/balance that
reaches storage and survives a reboot; Console (#1) shows liveness; Output
Writer (#5) journals to OLED; Job Submitter (#4) submits one canned job.

**Phase 2 — interfaces & load:** operator dashboard (web, on the Pi); terminal
web form (#2); transaction generator (#4 + Pi-side injector); throughput/loss
measurement.

**Phase 2+ / 3 — advanced:** thermal printer on #5; richer console panel;
crash-recovery replay of PENDING rows; COBOL reimplementation of the transaction
processor; Docker-per-subsystem isolation; RFID "card" on #4.

---

## 8. Open design decisions — RESOLVED (see protocol-spec §1–§7, now locked)

These were resolved in the protocol spec; kept here with their outcomes for
traceability. Timeouts remain provisional until measured at bring-up.

- **CAN ID scheme.** Resolved — 11-bit identifiers used as channel labels +
  arbitration priority; class in the high bits (protocol-spec §4).
- **Segmentation / encoding.** Resolved — **ISO-TP** (ISO 15765-2) for multi-frame
  messages; raw single frames for HEARTBEAT/ERROR (protocol-spec §5, §7).
  Compact-binary was rejected (charter non-goal: byte optimisation out of scope).
- **Interaction model.** Resolved — request/response with UUID correlation on the
  transaction path; TXN_RESULT carries the outcome (protocol-spec §7).
- **Heartbeat cadence and timeout.** Scheme resolved (per-node ping, class 0);
  **values still provisional** (1 s / 3 s) — measure at bring-up
  (bring-up-checklist §7, learning-log).

---

## 9. Recommended document set (best practice for this project)

| Document | Purpose | Status |
|----------|---------|--------|
| ADRs (`ADR-0001…`) | Record *why* each significant decision was made | ADR-0001 done |
| System Design (this doc) | High-level *what* and *how* | Living |
| BOM | Exact parts, per-node allocation, verify notes | Living; hardware verified 2026-07-01 |
| Protocol / interface spec | The CAN message contract (IDs, framing, types) | §1–§7 locked |
| Requirements / DoD | What the system must do, acceptance criteria | Done (Phase 1) |
| Roadmap | Milestones + dependency-ordered tasks derived from the DoD | Done (Phase 1) |
| Bring-up checklist | Pre-firmware hardware + toolchain verification | In progress (hardware arrived) |
| Charter | Purpose, goals & learning objectives | Ratified |
| Per-node README / build notes | Setup, pin map, build, definition-of-done | As each node is built |
| Test plan | Functional + load/throughput methodology | With Phase 2 |
