# Glossary — Project Planning & Process

> The vocabulary of *how the planning is done*, separate from the technical
> glossary (`glossary.md`, CAN / ISO-TP / CICS terms — compiled at session end).
> Living document. Each entry is one to two lines; ask to expand any.

---

**ADR (Architecture Decision Record)** — a short document capturing one
significant decision: its context, the decision, the alternatives considered, and
the consequences. *Immutable* once accepted — you supersede it, you don't edit it.

**Supersede** — replace an earlier decision/ADR with a newer one while leaving the
old on record (not deleted), so the history of reasoning is preserved. (ADR-012
superseded the old ADR-011 line.)

**System design document** — the high-level "what and how": subsystem map, data
flow, topology, data model, roadmap, and the list of still-open decisions. A
living document, not a frozen record.

**BOM (Bill of Materials)** — the exact parts list with quantities, costs,
per-node allocation, and a verify-before-buy checklist. Grounds the design in
hardware/cost reality and catches "won't fit" early (e.g. the PCF8574 pin-budget
finding).

**Protocol / interface spec** — the detailed *contract* at a boundary between
components. Here: the CAN message contract — framing, identity, encoding, message
types. Both sides must honour it to interoperate.

**Requirements / Definition of Done (DoD)** — what the system must do, plus the
concrete acceptance criteria that mark a piece of work finished and testable.

**Living document vs immutable record** — living docs (design, spec, BOM) are
expected to change as decisions resolve; immutable records (ADRs) are append-only
history. Keeping the "why" immutable stops it being quietly rewritten.

**Decision log / decision record** — the durable note of *what* was decided and
*why*, so it is not relitigated and a fresh session can pick up the rationale.
(In this project the protocol spec doubles as the decision log for interface
choices.)

**Options-with-reasoning** — the working rule of always presenting ≥2 viable
options with their trade-offs — never a single path presented as the answer — and
letting the human decide.

**Rated comparison** — scoring options against named criteria before choosing, so
the decision is justified rather than asserted. (The ISO-TP vs compact-binary
table.)

**Dependency ordering** — sequencing decisions so the one that unblocks the most
others is settled first. (Segmentation before ID scheme / message mapping.)

**Verify-don't-assume / verify-before-buy** — checking a claim against
documentation, source, or the physical part instead of trusting memory, *before*
money or design depends on it. (The ISO-TP library check; the BOM crystal/address
checks.)

**Spike** — a small, time-boxed investigation done purely to reduce uncertainty
before committing to a path.

**First-principles re-grounding** — rederiving a design from base constraints
rather than patching the previous approach. (ADR-012 → ADR-0001.)

**Diagnosis-before-redesign** — identifying the *root structural cause* of
failures before choosing a fix, so you remove the problem instead of moving it.
(The ADR-012 lesson: each prior fix relocated the same I2C mismatch.)

**Disposition table** — a migration artifact that assigns every inherited item from
a retired design a *disposition* — retire, re-host, re-architect, or retain (the
"6 R's" family from cloud migration) — so nothing is silently dropped or carried
over unexamined. (In protocol-spec §7, each `RETIRED-message_protocol.md` type is
dispositioned: survives / re-expressed / drops.)

**Traceability matrix** — a row-per-item mapping showing where each element of an old
artifact lands in the new one (or why it disappears), making coverage provable and
stopping anything being lost in translation. (The §7 legacy-type → new-form table is
one.)

**Bring-up** — the first power-on / integration of hardware, brought online one
piece at a time so a fault can be isolated. ("CAN bring-up one node at a time.")

**Phased roadmap** — splitting delivery into phases (Phase 1 working system,
Phase 2 interfaces/load, Phase 2+ advanced) to keep early focus narrow.

**Feedback loop (in planning)** — where a later step forces revisiting an earlier
one: hardware reality → design change; a verification result → a flipped
recommendation; a bring-up failure → a new decision.

**Working memory vs durable memory (in planning)** — the volatile session/chat
context vs the persistent docs. Decisions are checkpointed from the former into
the latter, so nothing is lost when a session ends. (Mirrors the project's own
RAM-vs-durable-log pattern.)

**Handoff prompt** — a written summary that lets a fresh session (or another
person) resume with full context: what's decided, what's open, what's next. This
session began from one.

**Checkpoint** — recording the current decided state into durable docs (+ a
handoff prompt) at a natural boundary, so work can stop or roll to a new session
cleanly.
