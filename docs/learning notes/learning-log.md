# Learning Log — Mainframe Simulation

> A dated **devlog of lessons learned** — the retrospective leg of the three-way
> learning-doc split (planning-process.md). Project-level learning *goals* live in
> `charter.md`; learning as a decision *driver* is labelled inside each ADR/spec;
> *lessons* — what was surprising, what was got wrong then right, what a failure
> taught — land here, dated, as they occur. Per-node README "lessons" sections are
> the sibling of this file at the build stage.
>
> Append-only in spirit: add entries, don't quietly rewrite past ones.
> Living document. Last updated: 2026-06-27.

---

## Entry format
Each entry: **date — short title**, then *Context* (what happened) and *Lesson*
(what to carry forward). One to three lines each; link the ADR/spec/BOM section
that records the underlying decision where one exists.

---

## Carried-over founding lessons
> Back-filled from the retired project and the existing docs — these pre-date this
> log, so they carry their original dates, not today's. They are the lessons the
> current architecture is built on.

### 2026-06-18 — A wrong-bus-for-the-role mismatch can't be patched away
**Context:** I2C was used for two roles it suits poorly — multi-master peer
messaging with runtime master/slave mode-switching, and slave mode on devices with
weak slave support. Four successive fixes (ADR-008→011) each *relocated* the same
failure instead of removing it; the project was retired (ADR-012).
**Lesson:** **Diagnose the root structural cause before redesigning.** When every
fix moves the problem rather than removing it, the architecture forcing the role is
wrong — change that, not the wire beneath it. (→ first-principles re-grounding in
ADR-0001.)

### 2026-06-18 — Hardware reality can rewrite the design
**Context:** the BOM per-node pin-budget check found the 4×4 keypad's 8 raw pins
don't fit the Transaction Terminal's free GPIO, forcing a PCF8574 I2C expander —
caught *before* purchase, not at bring-up.
**Lesson:** **Verify-before-buy.** Physical constraints feed back into the design;
checking the pin budget on paper turned a would-be bring-up failure into a line
item. (→ BOM §3; the hardware→design feedback loop in planning-process.)

---

## Lessons (current project — newest first)

### 2026-06-28 — The CAN ID is a channel label, not a message type; the payload byte is

**Context:** completing §7 (D7.3, D7.6, D7.7) forced a concrete encounter with the
OSI L2-vs-L7 distinction that had been abstract until now. Two moments made it
tangible: (1) the job channel `(0x380, 0x390)` carries *both* `JOB_ACCEPT` and
`JOB_COMPLETE` — the ID alone cannot tell you which arrived; the `type` nibble in
byte 0 is what disambiguates. (2) `ERROR` is the inverse: the CAN ID *does* carry
the subcode in bits `[3:0]`, by design, because the payload may never arrive when
the transport is the fault — a rare case where L2 intentionally carries L7 meaning,
justified by the constraint.

**Lesson:** the §7.1 discriminator byte (`type`|`version`) is not boilerplate — it
is what makes one ISO-TP channel reusable for multiple app-layer message types,
keeping the channel count small while keeping message semantics unambiguous.
`ERROR`'s code-in-ID is the deliberate exception, chosen because raw frames must
survive without ISO-TP. Recognising *when* the rule applies and *when* the
exception is justified is the layering discipline in practice. (→ protocol-spec
§7.1, §7.4; glossary OSI map; learning-log 2026-06-27 for the layered-error map.)

### 2026-06-27 — Errors detect across many layers but escalate through one
**Context:** deciding §7.4 (`ERROR` encoding) forced mapping *where* each fault is
caught vs *where* it's reported. Options weighed: **A** code in CAN ID low bits `[3:0]`
(raw single frame), **A+** same + optional detail payload, **B** code in a payload byte
(ID bits stay reserved), **C** full ISO-TP structured error. Chose **A+**. The layered
map: L1/L2 faults (CRC, ACK, bit-error, bus-off) are handled in **silicon** by the TWAI/
MCP2515 controller — your code only reads TEC/REC counters after; L4 ISO-TP aborts are
handled by the **library** (`esp_isotp` / `python-can-isotp`); L5 timeout, L6 parse, L7
business logic are handled by **your** code (C++ on MCUs, Python on Pi).
**Lesson:** **error detection + local recovery are distributed across layers; escalation
+ observability are centralized** — many layers detect, but only a subset escalate,
through one L7 type (`class-1 ERROR`) to one sink (Console #1 / Pi log). Two corollaries
that shaped the decision: (1) an `ERROR` must be reportable when the *transport itself*
is the fault (`TIMEOUT`, `BUS_ERROR`), so it must be a **raw single frame, not ISO-TP** —
this is the decisive axis that killed option C; (2) a business "no" (`INSUFFICIENT_FUNDS`,
`NOT_FOUND`) is a **result, not an error** — it rides the result payload, never an alarm
(the end-to-end argument: only L7 knows what "correct" means). This is a load-bearing
pattern in general SW — supervisor trees, dead-letter queues, centralized logging all
rhyme with it. (→ protocol-spec §7.4; glossary "Error handling & observability".)

### 2026-06-25 — Log scaffolded
**Context:** `charter.md` and this log created, completing the three-way learning-
doc split adopted 2026-06-21. §4 (CAN ID scheme) was the first decision recorded
after the split; its learning driver is labelled in the spec, and its goals now
have a home in the charter.
**Lesson:** stand up the process scaffolding early — recording a decision against
an incomplete structure means retrofitting later.

