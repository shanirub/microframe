# ADR-0002: The router process owns all CAN egress; subsystems return logical results over IPC

## Status
Accepted — 2026-07-10
Builds on ADR-0001 (Pi as central complex; router / processor / JES as separate
processes communicating via local IPC; "the Pi mediates all traffic").

---

## Context

ADR-0001 fixed that the CICS-analogue subsystems run as **separate Python
processes** on the Pi, talk to each other over **local IPC**, and that **the Pi
mediates all bus traffic** (no MCU↔MCU messaging). For *inbound* frames the
consequence is already clear: the router owns the ISO-TP receive path, decodes
the type-discriminator byte (protocol-spec §7.1), and routes to the right
subsystem.

What ADR-0001 did **not** pin is the *outbound* (Pi→bus) direction. When the
transaction processor finishes a transaction, or JES finishes a job, does that
subsystem **transmit its own** CAN frames, or does it hand a result back to the
router to transmit? Two paths depend on the answer — the transaction result
(`TXN_RESULT` → Terminal #2) and the job lifecycle (`JOB_ACCEPT` /
`JOB_COMPLETE` → Job Submitter #4).

The reference model is CICS multi-region operation (MRO). A **TOR**
(terminal-owning region) owns the terminals and *function-ships* a request to an
**AOR** (application-owning region); the AOR computes a result and returns it to
the TOR, which drives the terminal. **The AOR never writes the terminal
directly.** "Close to the original architecture" is measured against that shape.

---

## Decision

**The router process is the sole owner of a *transmitting* SocketCAN socket on
the Pi.**

- The transaction processor and JES compute **logical results only** — e.g.
  `status` / `reason` / `balance` for a transaction, `jobId` and accept/complete
  status for a job. They return those results to the router over **local IPC**,
  mirroring the request channel that already carries work *to* them.
- The **router** encodes each result via the `protocol` codec and performs the
  actual ISO-TP (or single-frame) transmit on `can0`.
- Ingress already flows through the router, so the router is the **bidirectional
  CAN gateway** — the TOR-analogue, and the concrete expression on the Pi's own
  side of ADR-0001's "the Pi mediates all traffic."

A direct consequence for the module graph: the `protocol` wire encoder/decoder
is imported **only by the router**. `processor` and `jes` depend on `storage`
and `common` plus the shared result data types — not on protocol byte layout.

---

## Alternatives considered

- **Each subsystem transmits its own frames.** The router would route ingress
  only; `processor` and `jes` would each own a transmit path to `can0`. Rejected:
  an AOR writing to terminals it does not own is not the CICS model; it diffuses
  framing/encoding responsibility across every process, obliges each worker to
  carry `protocol` + an ISO-TP transmit path, and blurs the mediation invariant
  *inside* the Pi. It saves one IPC hop — not worth the fidelity and clarity cost.
- **Hybrid — router owns the transaction egress; JES owns its own job-channel
  frames.** Genuinely defensible, because JES on a real mainframe is a *separate
  subsystem from CICS*, so JES owning its own I/O is arguably **more** faithful
  for JES specifically. Kept on file as a later refinement if we want JES to model
  a fully independent subsystem with its own bus attachment. Deferred to keep a
  single egress pattern and a single `can0` transmitter for Phase 1.

---

## Consequences

- A **result-return IPC channel** (worker → router) is required, symmetric to the
  existing request channel (router → worker). Low additional design cost.
- The router becomes a **single point of failure for egress**. Accepted: it is
  already the ingress gateway, and there is one physical CAN owner on the Pi
  regardless. Liveness is deliberately independent and receive-only (ADR-0003), so
  node monitoring keeps working across a router restart even though it cannot push
  to the console during the outage.
- The **dependency graph simplifies**: only the router imports the `protocol`
  codec (this resolves the previously ambiguous `protocol` import edges in the
  module dependency diagram).
- **Interacts with ADR-0003:** two sockets are bound to `can0` (router RX/TX;
  liveness RX-only), but exactly **one transmitter**.
- Any *future* Pi-originated frame (for example, a node-status push to the
  Operator Console, should one ever be added) also transmits through the router
  by this rule.
