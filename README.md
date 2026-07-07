# Mainframe Simulation

An educational simulation of a banking mainframe on hobby hardware. A **Raspberry Pi 3B+** acts as the central processor complex; four **ESP32-C3 MCUs** act as channel-attached peripherals (operator console, transaction terminal, job submitter, output writer). All five devices communicate over a shared **CAN bus** (Controller Area Network — a multi-master serial bus with hardware arbitration, originally designed for automotive use).

The system processes deposit, withdrawal, and balance transactions against durable storage, and is built to be understood at the protocol and hardware level — not just to run.

> **Architecture:** ADR-0001 · **Status:** Phase 1 in progress (hardware arriving)

---

## What this simulates

The design is a minimal analogue of **CICS** (IBM's Customer Information Control System — transaction-processing middleware that receives a request, routes it to the right subsystem, touches storage, and acknowledges). The Pi runs the CICS router, transaction processor, and job scheduler (JES — Job Entry Subsystem) as separate Python processes. The MCUs are channel-attached peripherals, the way a real mainframe attaches I/O devices — not co-equal peers with their own business logic.

The functional goal: a deposit/withdraw/balance flow that touches durable storage and **survives a reboot**, with per-node liveness monitoring and a journal of each transaction result.

---

## Hardware

| Device | Role | Mainframe analogue |
|---|---|---|
| Raspberry Pi 3B+ | Central processor complex | Central Processing Complex |
| ESP32-C3 #1 | Operator Console | System operator interface |
| ESP32-C3 #2 | Transaction Terminal | 3270-style terminal |
| ESP32-C3 #4 | Job Submitter | Card reader / JES input |
| ESP32-C3 #5 | Output Writer | Printer / output writer |

All five are peers on one CAN bus. Each MCU has a private SSD1306 OLED display (I²C — Inter-Integrated Circuit, a two-wire local bus) and drives the CAN bus through an SN65HVD230 3.3V transceiver. The Pi joins via a Waveshare MCP2515 CAN HAT exposed through Linux **SocketCAN** (the kernel's standard CAN networking stack).

Full parts list, per-node pin allocation, and verify-before-buy notes: [`docs/design/BOM.md`](docs/design/BOM.md).

---

## Repository layout

```
.
├── CLAUDE.md                    # Agent guidance (project-wide rules)
├── code/
│   └── pi/                      # Raspberry Pi subsystems (Python package)
│       ├── CLAUDE.md            #   Pi-specific agent guidance
│       ├── pyproject.toml
│       ├── src/mainframe_pi/    #   router, processor, jes, liveness, storage, protocol
│       └── tests/
└── docs/
    ├── decisions/               # ADRs — immutable "why" records
    │   └── ADR-0001-mainframe-core-architecture.md
    ├── design/                  # Living "what and how" documents
    │   ├── system-design.md
    │   ├── protocol-spec.md     #   §1–§7 locked
    │   ├── BOM.md
    │   ├── requirements.md
    │   ├── roadmap.md
    │   ├── bring-up-checklist.md
    │   └── RETIRED-message_protocol.md   # retired shared-bus spec (traceability only)
    ├── learning notes/          # Goals, vocabulary, and lessons
    │   ├── charter.md
    │   ├── glossary.md
    │   ├── glossary-planning.md
    │   ├── learning-log.md
    │   └── planning-process.md
    └── reference/               # External standards / datasheets (e.g. TI CAN intro)
```

> Note: `charter.md` and `learning-log.md` currently live under `docs/learning
> notes/` in the repo; the charter is the ratified home for goals and learning
> objectives.

---

## Document guide

### Architecture decisions — `docs/decisions/`

**ADRs** (Architecture Decision Records) are immutable records of significant decisions: context, the decision made, alternatives considered, and consequences. They are never edited — only superseded by a new ADR. This preserves the reasoning trail.

| File | Decision |
|---|---|
| [`ADR-0001`](docs/decisions/ADR-0001-mainframe-core-architecture.md) | Pi as central complex, ESP32-C3s as channel peripherals, CAN as the inter-device bus. The foundational architecture decision. |

> The predecessor project was retired in ADR-012 (kept in the retired repo). Its failure — I2C used for multi-master peer messaging and slave mode on devices with weak slave support — is the direct motivation for ADR-0001.

---

### Design documents — `docs/design/`

Living documents. Expected to evolve as decisions resolve and hardware is brought up.

**[`system-design.md`](docs/design/system-design.md)** — The high-level *what* and *how*: subsystem map (Pi processes + MCU roles), hardware topology, end-to-end data flow (deposit → storage → journal), the data model (SQLite in WAL mode — Write-Ahead Log, which allows concurrent reads without blocking writes), testability approach, and the phased roadmap (Phase 1 working system → Phase 2 interfaces and load → Phase 2+ advanced).

**[`protocol-spec.md`](docs/design/protocol-spec.md)** — The CAN message contract. Covers the CAN ID scheme (11-bit identifiers used as channel labels and arbitration priority), message classes (0–4), ISO-TP segmentation (ISO 15765-2 — the standard multi-frame transport that lets messages longer than 8 bytes cross a CAN bus), all eight message types with full byte maps, and the provisional timeout values (to be measured at bring-up and replaced with actuals). §1–§7 are locked.

**[`BOM.md`](docs/design/BOM.md)** — Bill of Materials. Hardware in hand, hardware to order, per-node GPIO pin allocation (including why the Transaction Terminal requires a PCF8574 I²C GPIO expander for the 4×4 keypad), and a verify-before-buy checklist for parts where a wrong variant would cause a silent failure (transceiver voltage rating, HAT crystal value, expander I²C address).

**[`requirements.md`](docs/design/requirements.md)** — What the system must do and when it is done, written as testable acceptance criteria. Three levels: per-node bring-up DoD (Definition of Done — the observable gate that must pass before functional testing), per-feature DoD (heartbeat, transaction path, journal, job path, durability), and system DoD (full end-to-end flow). Also contains the Phase 2+ deferred items so nothing is silently dropped.

**[`roadmap.md`](docs/design/roadmap.md)** — The build plan derived from the DoD: seven milestones (M0–M6) plus a parallel Pi-software track, with dependency-ordered tasks under each. Every task carries acceptance criteria cross-referenced to `requirements.md`, a rough estimate, and a risk flag. Opens with a Mermaid task-dependency graph and names the critical path.

**[`bring-up-checklist.md`](docs/design/bring-up-checklist.md)** — Pre-firmware hardware and toolchain verification. A pre-condition gate to complete before any firmware is written or flashed. Covers: CAN bus wiring and termination, transceiver verification, Pi HAT crystal and SocketCAN setup, PCF8574 I²C address check, ESP-IDF version and `esp_isotp` component verification, bench power and safety, and a timeout measurement section (to be filled in at bring-up and used to replace the provisional values in `protocol-spec.md` §6).

---

### Learning notes — `docs/learning notes/`

**[`charter.md`](docs/learning%20notes/charter.md)** — Project purpose, functional goal, and learning objectives (grouped: mainframe architecture fidelity, bus and protocol understanding, durability and correctness, engineering process discipline). The stable home for *why this project exists* and *what understanding it is meant to build*.

**[`glossary.md`](docs/learning%20notes/glossary.md)** — Technical vocabulary: CAN, ISO-TP, CICS, OSI layer map, SQLite WAL, FreeRTOS concepts, and the mainframe terms used in the design (UOWID, syncpoint, JES, DASD, and others).

**[`glossary-planning.md`](docs/learning%20notes/glossary-planning.md)** — Vocabulary of the planning process itself: ADR, living document, options-with-reasoning, rated comparison, disposition table, traceability matrix, bring-up, handoff prompt, and others.

**[`planning-process.md`](docs/learning%20notes/planning-process.md)** — How decisions are made and recorded on this project. The immutable-ADR vs living-document split, the decision loop (dependency ordering, options + reasoning, verify-before-assuming, record-as-you-go), and the feedback loops (hardware → design, decision → decision, bring-up → decisions). Understanding the process is itself a stated goal.

**[`learning-log.md`](docs/learning%20notes/learning-log.md)** — Dated devlog of lessons learned. Append-only in spirit. Current entries: the root-cause diagnosis that retired the predecessor project (2026-06-18), the PCF8574 pin-budget catch (2026-06-18), the layered error-handling pattern (2026-06-27), and the CAN ID as channel label vs payload byte as type discriminator (2026-06-28).

---

## Phasing

**Phase 1 (current):** working system — CAN bring-up, three Pi subsystems as processes, SQLite with the write-ahead pattern, full deposit/withdraw/balance flow that survives a reboot, liveness on the Console, journal on the Output Writer, canned job from the Job Submitter.

**Phase 2:** operator dashboard (web), terminal web form, transaction generators (MCU #4 + Pi-side injector), throughput and loss measurement.

**Phase 2+:** thermal printer on #5, crash-recovery replay of PENDING rows, GnuCOBOL reimplementation of the transaction processor, Docker-per-subsystem isolation, RFID job submission on #4.

---

## Key design principles

- **Diagnose before redesigning** — the predecessor project went through four fixes that each relocated the same I2C mismatch without removing it. ADR-0001 re-grounds from first principles.
- **Verify, don't assume** — hardware claims are checked against datasheets or the physical part before money or design depends on them (`esp_isotp` target support, HAT crystal value, transceiver voltage rating).
- **Integer cents, never float** — all monetary values are `uint32` cents throughout firmware, protocol, and database.
- **Immutable "why", living "what"** — ADRs record decisions permanently; everything else evolves.
- **Understanding over throughput** — ISO-TP is used over a compact hand-rolled encoding because the learning goal is to understand how a standard segmentation layer works, not to minimise bytes on the wire.
