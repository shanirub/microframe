# Project Charter — Mainframe Simulation

> The project's **purpose, goals, and learning objectives** in one stable place.
> Introduced by the three-way learning-doc split (planning-process.md): project-
> level *learning goals* live here so the whole set sits in one place rather than
> scattered across ADRs. Decision-level learning **drivers** stay labelled inside
> each ADR/spec (`Learning/fidelity driver:`); retrospective **lessons** go to
> `learning-log.md`.
>
> Living document. Last updated: 2026-06-25.

---

## Purpose of this document
A learning project has two kinds of goal — the *thing built* and the
*understanding gained* — and they are easy to conflate. This charter is the
stable home for both, especially the learning objectives, so they are explicit
and revisable rather than implied across the design docs.

## What the project is
An educational simulation of a banking mainframe. A **Raspberry Pi 3B+** is the
central processor complex running the mainframe's software subsystems as separate
processes; **four ESP32-C3 MCUs** are channel-attached peripherals; all five are
peers on one shared **CAN bus**. (Architecture: ADR-0001. What/how: system-design.
Successor to the retired shared-bus project — ADR-012.)

## Functional goal
A minimal analogue of **CICS** `[gloss: IBM's transaction-processing middleware —
receive a request, route it, touch storage, acknowledge]`: a request arrives, is
routed to the right subsystem, touches durable storage, and is acknowledged —
covering heartbeat/liveness and a deposit / withdraw / balance flow that **survives
a reboot**. Acceptance criteria are owned by the requirements / Definition-of-Done
doc, not here.

---

## Goals & learning objectives

> **First-pass — inferred from the existing docs, not yet ratified.** These were
> assembled from goals stated implicitly across ADR-0001, system-design,
> planning-process, and the glossaries. Correct, cut, or extend freely; this
> section is meant to be edited.

The recurring stated intent is **"understand *why* each piece works at the
protocol and hardware level — not only make it run"** (system-design §1), plus
**"understanding the *process* is itself a goal"** (planning-process.md). Grouped:

### A. Mainframe architecture & transaction-processing fidelity
- Understand how a real transaction monitor is structured *and why* — router,
  transaction processor, and job scheduler as separate address spaces on one
  complex, not separate machines (ADR-0001 decision 1).
- Map mainframe concepts faithfully, not just by name: task number vs **UOWID**,
  **syncpoint**, two-phase commit, **in-doubt**, recovery/backout, JES, DASD
  (glossary — mainframe section).
- Keep a credible **COBOL** authenticity path open (fixed-width `PIC` fields now;
  GnuCOBOL reimplementation of the processor later — §3, ADR-0001).

### B. Bus & protocol-level understanding
- Understand *why* CAN fits where I2C did not — hardware arbitration, no
  master/slave roles, no mode-switching (ADR-0001; ADR-012's diagnosis).
- Understand why an 8-byte frame **forces a transport layer**, and how ISO-TP
  segments, reassembles, and flow-controls (§1; glossary — ISO-TP).
- Internalise **OSI layering as a discipline** — storage form, message meaning,
  and wire form kept independent (glossary OSI map; §3).
- Understand the CAN identifier as *both* name and arbitration **priority** (§4).

### C. Durability & correctness
- Understand SQLite **WAL** and the write-ahead **PENDING → balance → COMMITTED**
  pattern, and how it makes a transaction survive a crash (system-design §5).
- **Integer cents, never float** — money as a quantity vs the account as an
  identifier (§3; throughout).
- See how a **UUID + durable log** make throughput and loss/duplicate detection
  measurable under load (system-design §6).

### D. Engineering process & documentation discipline
*(Explicitly a goal, per planning-process.md — not incidental.)*
- **Decision-centric** working: every choice gets ≥2 options with reasoning and a
  **rated comparison** before a recommendation; the human decides.
- **Verify-don't-assume / verify-before-buy** — check claims against source or the
  physical part before money or design depends on them.
- Separate the **immutable "why" (ADRs)** from the **living "what" (everything
  else)**.
- **First-principles re-grounding** and **diagnosis-before-redesign** — remove the
  root cause, don't relocate it (the ADR-012 → ADR-0001 lesson).
- **Docs-as-we-go** — checkpoint each decision from volatile working memory into
  durable docs as it is made.

---

## Non-goals / out of scope (Phase 1)
Stated so the learning objectives stay honest about what is *not* being optimised
or built:
- **Byte / throughput optimisation** — explicitly out of scope (§1); this is why
  ISO-TP beat compact-binary and why fields are not bit-packed for size.
- **Production-grade banking** — no real authentication, access control, or
  multi-writer concurrency beyond WAL's single-writer model.
- **Networked / microservice transport** — rejected for the bus (ADR-0001);
  networking returns only as the optional Phase-2 operator dashboard.
- **MCU↔MCU messaging** — none; the Pi mediates all traffic (confirmed; §4 context).

## Scope & phasing
Phase 1 = a working system (the functional goal above). Phase 2 = interfaces &
load (dashboard, web terminal, transaction generators, throughput/loss
measurement). Phase 2+ = advanced (printer, crash-recovery replay, COBOL
reimplementation, Docker isolation). Detail: system-design §7.

## Related documents
| Document | Owns |
|---|---|
| ADR-0001, ADR-012 | *Why* — architecture decisions (immutable) |
| system-design | *What / how* + open decisions |
| protocol-spec | the CAN message contract |
| BOM | parts, per-node pin budget |
| planning-process + glossaries | how planning is done; vocabulary |
| **this charter** | goals & learning objectives |
| learning-log | dated lessons learned |
