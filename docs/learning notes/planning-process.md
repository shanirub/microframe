# Planning Process — Mainframe Simulation

> A **meta-document**: not part of the system, but a record of *how the planning
> and documentation are done* on this project. Living document. Pairs with the
> planning glossary (`glossary-planning.md`).
>
> Last updated: 2026-06-21.

## Why this document exists
Understanding the *process* is itself a goal of a learning project. This captures
the documentation discipline so a future session — or future-you — can see not
just *what* was decided but *how* decisions get made and recorded.

## The core split: immutable "why" vs living "what"
Two kinds of document, treated differently:

- **Immutable records (ADRs)** — append-only history of significant decisions. An
  accepted ADR is never edited; it is *superseded* by a new one, leaving the old
  on record. This protects the reasoning from being quietly rewritten and
  preserves the trail of *why*.
- **Living documents (everything else)** — the design, the spec, the BOM, the
  glossaries. Expected to evolve as decisions resolve.

## Who owns which question

| Document | Question it owns | Lifecycle |
|---|---|---|
| **ADR** | *Why* did we choose this? | immutable (superseded, not edited) |
| **System design** | *What / how*, and *what's still open*? | living |
| **BOM** | *With what* hardware, and does it fit? | living |
| **Protocol spec** | What's the exact *contract* at the boundary? | living |
| **Requirements / DoD** | What must it do; when is it *done*? | living |
| **Per-node README** | How do I *build* this node? | per-node |
| **Test plan** | How do I *verify* it? | living (with Phase 2) |
| **Glossaries** | What do the *words* mean (technical + planning)? | living |

The load-bearing split is **immutable "why" (ADR) vs living "what/how"
(everything else)**.

## The flow

```
   trigger / diagnosis           ← root-cause the failure, don't patch it
        │  (ADR-012)
        ▼
   foundational ADR              ← the big "why", immutable
        │  (ADR-0001)
        ▼
   system design ───────────┐    ← "what/how" + a BACKLOG of open decisions (§8)
        │                   │
        ▼                   │  feedback: hardware reality
   BOM (hardware) ──────────┘     can force a design change
        │
        ▼
 ┌──────────────────────── DECISION LOOP ────────────────────────┐
 │  pick next open decision ◄── dependency order (unblock most)  │
 │        ▼                                                       │
 │  options + reasoning + rated comparison                       │
 │        ▼                                                       │
 │  verify claims vs source ── can flip the recommendation       │
 │        ▼                                                       │
 │  human decides  (never assume)                                │
 │        ▼                                                       │
 │  RECORD in the living spec ── constrains the next decision ─┐ │
 │        └────────── backlog not empty? ──────────────────────┘ │
 └──────────────────────────────│────────────────────────────────┘
                                ▼  backlog clear enough
                   per-node READMEs · test plan · build & bring-up
                                │
                                └─ bring-up surprises feed new decisions back in
```

## The loop is where the work is
The straight line at the top (diagnosis → ADR → design → BOM) happens once. The
**decision loop** is the day-to-day: pick the next open decision in dependency
order, lay out options with reasoning and a rated comparison, verify any claim
against source, let the human decide, record the result in the living spec —
repeat until the backlog is clear enough to build.

## The feedback loops matter more than the straight line
- **Hardware → design:** physical reality can rewrite the design (the PCF8574
  pin-budget finding).
- **Decision → decision:** each choice constrains the next (segmentation fixed
  the framing, which constrains the CAN-ID scheme).
- **Verification → recommendation:** a fact-check can overturn a lean (the ISO-TP
  library check could have forced compact-binary).
- **Bring-up → decisions:** integration failures feed new decisions back in.

## Working memory vs durable memory
The conversation is volatile working memory; the docs are durable storage. Every
decision is checkpointed from chat into the docs as it is made, so a session can
end — or hit its context limit — at any point and a new one resumes from the
docs, optionally via a **handoff prompt** stating what's decided, what's open, and
what's next. (This project's sessions begin from exactly such a prompt. The
pattern mirrors the system's own RAM-vs-durable-log design.)

## Principles, in one line
Decision-centric · options-with-reasoning · verify-don't-assume ·
write-it-down-as-you-go · separate the immutable "why" from the living "what."

## Documenting the learning aspect — DECIDED (three-way split)
Resolved 2026-06-21. Learning is documented in three places, by *kind* — never all
dumped into a decision's `Z` ("use X to achieve Y because Z"):

1. **Learning goals** (project-level objectives) → the **charter** (`charter.md`),
   in a "Goals & learning objectives" section. The whole set lives in one stable
   place, not scattered across ADRs.
2. **Learning as a decision driver** → inside the relevant **ADR / spec context**,
   explicitly labeled `Learning/fidelity driver: …` so it stays distinguishable
   from the technical rationale. Discipline: when a learning/fidelity driver wins,
   the **technical cost being accepted is still stated** (per ADR-0001's
   CAN-over-Ethernet model), so the rated comparison stays honest and "good for
   learning" can't quietly excuse a weak technical case.
3. **Lessons learned** (retrospective) → a dated **learning log / devlog**
   (`learning-log.md`), plus per-node README "lessons" sections. Failure-ADRs
   (e.g. the old ADR-008→012) are a special case of a recorded lesson.

*`charter.md` and `learning-log.md` are to be scaffolded next session.*
