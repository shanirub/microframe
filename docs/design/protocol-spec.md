# Protocol / Interface Spec — Mainframe Simulation (CAN message contract)

> **Status: living document.** Built incrementally as each open decision in
> system-design §8 is resolved. Scope = the CAN *message contract*: framing,
> identity, field encoding, message types. Hardware/topology lives in
> system-design §3 + BOM; architecture rationale in ADR-0001; carried-over
> message semantics in RETIRED-message_protocol.md.
>
> Last updated: 2026-06-28.

## How to read this document

Each decision is recorded as **context → options considered → rated comparison →
decision → rationale → consequences**. Decided items are frozen unless a later
ADR supersedes them. Pending items are listed in §0 with what already constrains
them, so a future session can see the whole map at a glance.

Brief inline glosses are given on first use of a term `[gloss: ...]`; ask if you
want any expanded.

---

## §0 Decision status

| Open decision (system-design §8) | Status | Section |
|---|---|---|
| Segmentation / encoding | **DECIDED — ISO-TP** | §1 |
| Identity & correlation (UUID handling) | **DECIDED — A2 (tag on wire, UUID in log)** | §2 |
| Account field representation | **DECIDED — fixed 8-char (`PIC 9(8)`)** | §3 |
| CAN ID scheme (11/29-bit, priority) | **DECIDED — 11-bit partitioned (class/node/orig)** | §4 |
| Interaction model (req/resp vs fire-and-forget) | **DECIDED — hybrid by class (txn sync, job async)** | §5 |
| Heartbeat cadence + timeout | **DECIDED — D2 (MCU→Pi), 1s/3s; txn timeout 2s (provisional)** | §6 |
| Message-type mapping onto frames | **DECIDED — §7 complete (2026-06-28)** | §7 |

---

## §1 Segmentation / encoding — **ISO-TP**

### Context
A CAN 2.0 *classical* data frame carries at most **8 data bytes**; the
carried-over messages are ~65–110 bytes (RETIRED-message_protocol.md §"Message Size
Reference"). A transport layer that **segments** a message across multiple frames
and **reassembles** it on the far side is therefore required.
`[gloss: "transport" = the layer that turns 8-byte frames back into whole
messages — OSI layer 4, the same conceptual slot as TCP.]`

The MCP2515 (Pi HAT) and the ESP32-C3 TWAI controller are both classical CAN only
(no CAN FD's 64-byte frames), so the 8-byte cap has no hardware escape hatch.

### Options considered
- **ISO-TP (ISO 15765-2)** — the standard multi-frame CAN transport. Splits a
  message into a *First Frame* + *Consecutive Frames*; the receiver paces the
  sender with a *Flow Control* handshake (Block Size + STmin). Carries up to 4095
  bytes per message.
- **Compact binary** — a bespoke fixed byte-layout plus a hand-rolled
  segmentation/reassembly scheme, designed to minimise bytes/frames.

### Rated comparison
| Criterion | ISO-TP | Compact binary |
|---|---|---|
| Standardness | high | none (bespoke) |
| Library support (both ends) | high | build it yourself |
| Debuggability | high (sigrok / Wireshark / isotp tools decode it) | write your own decoder |
| Byte / frame efficiency | medium (PCI byte + FC round-trip) | high |
| Learning value | high (a real industry transport) | high (framing design) |
| Implementation effort | low | high |

### Decision
**ISO-TP.** Byte/throughput optimisation is explicitly **out of scope** for Phase
1 (learning project, no txn/sec target). That removes compact-binary's only
advantage — efficiency — and ISO-TP wins on every remaining axis.

### Verified library support (checked 2026-06-20)
- **Pi (SocketCAN):** ISO-TP is **in-kernel since Linux 5.10**;
  `python-can-isotp` (`pip install can-isotp`) wraps the kernel ISO-TP socket, or
  runs a pure-Python user-space implementation. Current Raspberry Pi OS (6.x
  kernel) has it — expect a one-time `modprobe can-isotp`. *Confirm on the actual
  image.*
- **ESP32-C3 (ESP-IDF):** official **`espressif/esp_isotp`** component — ISO
  15765-2 over TWAI, ≤4095 bytes, automatic segmentation/reassembly + flow
  control, non-blocking poll API. Fallbacks: platform-agnostic **`isotp-c`** (you
  inject CAN send/recv hooks); an Arduino-framework library (*not* used — this
  project is pure ESP-IDF).
- **Caveat (unverified):** `esp_isotp` appears to target the newer node-based
  TWAI driver (`twai_node_onchip`, recent ESP-IDF v5.x). Confirm the minimum IDF
  version and that the C3 is in the component's supported-targets list at setup.
  - *Verification attempt 2026-06-24 (`mcp-api-doc` tool):* looked up
    `twai_node_onchip`, `twai_new_node_onchip`, and `esp_isotp_poll` — **none in
    the index**. The tool's ESP-IDF coverage does not reach the v5.x node-based
    TWAI API and does not include third-party registry components like
    `esp_isotp`. This is absence of evidence, not evidence of absence: the caveat
    remains **open**, to be confirmed against the live ESP-IDF docs / component
    registry at setup, before any TWAI/ISO-TP firmware is written.

### Consequences (these constrain later sections)
1. ISO-TP is **point-to-point and addressed** — each transport instance binds a
   `(tx_id, rx_id)` CAN-ID pair. So each MCU↔Pi link is its own ISO-TP channel,
   and the Pi runs one instance per MCU (multi-instance is supported). → **§4**.
2. **Heartbeat must not use ISO-TP** — it is broadcast (one→all) and ≤8 bytes.
   Clean split: *data plane* (transactions, jobs) → ISO-TP; *control plane*
   (heartbeat/liveness) → raw single-frame CAN. → **§6**.
3. Firmware model: poll the transport (`esp_isotp_poll()`) every 1–10 ms inside a
   FreeRTOS task.

---

## §2 Identity & correlation — **A2: compact tag on the wire, UUID in the log**

### Decision
The durable 16-byte **UUID lives in the Pi's transaction log only** (already the
plan — system-design §5/§6). The CAN wire carries a short **correlation tag**:
a `uint16` where the high bits = source node ID and the low bits = a per-node
sequence number. The Pi mints the UUID on first receipt and stores the
`tag ↔ UUID` binding in the log.

### Mainframe basis
This mirrors how CICS actually tracks work (verified): a compact, region-local
**task number** drives dispatch, while the globally-unique **UOWID**
(unit-of-work ID) + NETNAME lives in the log for recovery and cross-region
correlation. Here: **tag ≈ task number; UUID ≈ UOWID.**
`[gloss: UOWID = the durable key CICS uses during crash recovery to find every
log record belonging to one unit of work and resolve it.]`

### Rationale / consequences
- Keeps the wire small **without discarding the UUID** — the UUID was always
  going to the log; A2 simply declines to *also* duplicate it on the wire.
- `uint16` tag sizing assumes ≤256 in-flight txns/node and a handful of nodes —
  true now; widen the sequence field if a Phase-2 load generator needs it.
- A future **A3 (hybrid)** — full UUID on the *entry* frame, tag thereafter — is
  a clean later upgrade if end-to-end cross-node tracing is wanted; A2 already
  establishes the binding it would build on.

---

## §3 Account field representation — **fixed 8-char (`PIC 9(8)`)**

### Decision
- **Logical / DB:** SQLite `account_id TEXT`, exactly **8 numeric chars,
  zero-padded** (`"00012345"`). Optional integrity constraint:
  `CHECK(length(account_id)=8 AND account_id GLOB '[0-9]*')` — the `PIC 9(8)` rule
  encoded in SQLite. In Python it is a `str`, never an `int`.
- **Wire:** the same fixed **8-byte ASCII** field, unpacked. With size
  deprioritised and ISO-TP giving ample room, this keeps the presentation layer
  (OSI L6) trivial and identical to storage.

### Rationale
- An account number is an **identifier, not a quantity** — no arithmetic is done
  on it, and leading zeros are significant (`00012345 ≠ 12345`). A binary integer
  would silently drop them → rejected.
- COBOL copybooks declare fixed-width `PIC` fields
  `[gloss: PIC = PICTURE clause, the fixed field-width/type declaration]`, so a
  fixed character field is the COBOL-faithful choice and forward-compatible with
  the planned GnuCOBOL processor (ADR-0001).
- **Revision note:** this supersedes the earlier "4-byte binary account"
  suggestion. That was a *size* optimisation; size is no longer being optimised,
  so the simpler, more faithful form wins.
- **Money** stays **`uint32` integer cents** (binary, 4 bytes) — it *is* a
  quantity, the opposite case from the account.
- DB form (TEXT) and wire form (ASCII) are independent layers; widening the field
  later needs no schema migration (TEXT stores any length).

---

## §4 CAN ID scheme — **11-bit partitioned (class / node / originator)**

### Context
The CAN identifier does double duty: it is both the message's **name** and its
**arbitration priority**. `[gloss: when two nodes transmit at once, arbitration
compares IDs bit-by-bit from the most-significant bit down; the first node to send
a dominant 0 against another's recessive 1 wins the bus and the loser backs off —
all in hardware, no collision. Lower ID = higher priority.]` So packing fields
into the ID simultaneously decides who beats whom for the wire.

Constraints already locked by earlier decisions:
- From **§1**: ISO-TP normal addressing is point-to-point — each MCU↔Pi data
  channel binds a `(tx_id, rx_id)` CAN-ID pair, and the heartbeat is raw
  single-frame **broadcast** needing its own high-priority (low-ID) slot, separate
  from the ISO-TP data plane.
- From **§2**: the correlation tag already encodes a **source-node ID** in its
  high bits, using the existing node numbering — the ID scheme should match it.
- From the **topology** (ADR-0001, system-design §2; confirmed this session):
  there is **no MCU↔MCU path**. The Pi is the central complex emulating the
  channel subsystem `[gloss: the mainframe's dedicated I/O machinery between the
  processor and its peripheral control units; peripherals talk to the channel, not
  to each other]`; all traffic is MCU↔Pi. The legacy `RETIRED-message_protocol.md` hops
  that looked peer-to-peer (#5→#4, #4→#2) collapse onto the Pi, since JES and the
  CICS router are Pi processes. This is a 5-node **star**, not a mesh.

### Options considered
- **A — 11-bit partitioned.** Carve the standard 11-bit ID into small fields
  (priority class / node / originator), priority falling out of class in the top
  bits. `[gloss: 11-bit "standard" CAN ID = 2048 values, the original identifier
  width.]`
- **B — 29-bit partitioned.** Same idea in the *extended* identifier, with 8-bit
  fields and large headroom (J1939-like). `[gloss: 29-bit "extended" ID, ~537M
  values; used for rich structured addressing.]`
- **C — 11-bit flat table.** No bit-fields; hand-assign a small table of literal
  IDs, one heartbeat + one `(tx,rx)` pair per channel.

### Rated comparison
| Criterion | A: 11-bit partitioned | B: 29-bit partitioned | C: 11-bit flat table |
|---|---|---|---|
| Fits 5 nodes + classes | high (comfortable) | high (vast headroom) | high |
| Priority control (heartbeat wins) | high (class in top bits) | high | medium (hand-tuned) |
| Structured-addressing fidelity | medium | high (J1939-like) | low |
| Debuggability (candump/sigrok) | high (decodable fields) | high | high (tiny table) |
| Design / decode effort | low | medium | lowest |
| Future MCU↔MCU / more nodes | medium | high | low |
| Bits on wire / arbitration overhead | best (11-bit) | slightly more | best (11-bit) |

### Decision
**Option A — 11-bit partitioned.** The ID's job here is **L2 channel addressing
for a 5-node star**, and 11 bits cover that with room to spare. B's headroom is
only earned by structured-addressing as a learning goal (not wanted) or a growing
mesh (topology confirmed flat) — neither holds, so its unused bits would be
decoration. C discards the structured-ID lesson that is the point of doing this in
a learning project. A is the sweet spot: it teaches the real mechanism (ID fields
→ arbitration priority) without over-provisioning.

`Learning/fidelity driver:` choosing a partitioned ID over a flat table (C) is
partly a learning choice — seeing priority emerge from a structured ID is the
lesson. *Technical cost accepted:* a few bits spent on field structure rather than
the absolute-minimum table. Negligible on a light 500 kbit/s bench bus.

### Bit layout
Bit 10 = MSB, so the field at the top dominates arbitration.

| Bits | Width | Field | Meaning |
|---|---|---|---|
| [10:8] | 3 | **class** | priority / message group (top bits ⇒ sets priority) |
| [7:5] | 3 | **node** | which MCU (#1/#2/#4/#5); 0 = broadcast |
| [4] | 1 | **originator** | 0 = Pi-originated, 1 = MCU-originated |
| [3:0] | 4 | **reserved** | 0 for now; `[3:0]` used by ERROR subcode (§7) |

`id = (class << 8) | (node << 5) | (originator << 4)`

- **Node field keeps the existing labels** (1, 2, 4, 5; 3 left as the documented
  gap from the retired DB controller). Costs one bit over a 0–3 renumber, but keeps
  the project's mental model intact and matches §2's correlation-tag numbering, so
  "node 2" means the Transaction Terminal on *both* the tag and the CAN ID.
- **Class is 3 bits (8 classes).** Class is the one field genuinely likely to grow
  — new message types want new priority levels — whereas node count is fixed by the
  confirmed flat topology. So the spare bit goes to class, not node.

### The originator bit — why not "direction"
Bit [4] is deliberately **"which endpoint emitted the frame"** (0 = Pi, 1 = MCU),
**not** "downlink vs uplink." In ISO-TP a node transmits everything it *originates*
on its `tx_id` — both its data frames when sending **and** its Flow Control frames
when receiving. `[gloss: Flow Control = the receiver's pacing frame, granting the
sender a Block Size and minimum gap (STmin).]` FC frames flow opposite to the data
they pace, so a "direction" bit would be ambiguous; an **originator** bit is
unambiguous on every frame and cleanly attributes each frame to one side on
`candump`. Each ISO-TP channel therefore consumes a consecutive ID pair: the Pi
binds `(tx = even, rx = odd)`, the MCU binds the mirror.

### Class assignments (priority order)
| class | Plane | Traffic | Notes |
|---|---|---|---|
| 0 | control (raw) | **heartbeat / liveness** | highest priority — liveness never starved |
| 1 | control (raw) | **error / alarm** | preempts normal data |
| 2 | data (ISO-TP) | **transaction** (deposit/withdraw/balance) | interactive |
| 3 | data (ISO-TP) | **job** (submit/accept/complete) | batch |
| 4 | data (ISO-TP) | **journal** (Pi→#5 output line) | post-transaction, async |
| 5–7 | — | reserved | Phase 2+ |

Transaction-above-job (class 2 < 3) is a small fidelity bonus: online CICS
transactions are conventionally prioritised over batch JES jobs, and that ordering
falls straight out of the class values.

### Worked IDs
| Frame | class | node | orig | ID |
|---|---|---|---|---|
| Heartbeat broadcast | 0 | 0 | 0 (Pi) | **0x000** |
| Transaction, Pi→#2 | 2 | 2 | 0 | **0x240** |
| Transaction, #2→Pi | 2 | 2 | 1 | **0x250** |
| Job, Pi→#4 | 3 | 4 | 0 | **0x380** |
| Job, #4→Pi | 3 | 4 | 1 | **0x390** |
| Journal, Pi→#5 | 4 | 5 | 0 | **0x4A0** |
| Journal, #5→Pi (FC only) | 4 | 5 | 1 | **0x4B0** |
| Error from #2 | 1 | 2 | 1 | 0x150 + subcode |

Bus priority, highest first: heartbeat `0x000` → errors `0x1xx` → transactions
`0x2xx` → jobs `0x3xx` → journal `0x4xx`.

### Consequences (these constrain later sections)
1. **§7** assigns each message type to a `(class, node)` channel and defines
   payload byte layouts. The 4 reserved low ID bits `[3:0]` are used by `ERROR`
   subcode (§7).
2. The `(tx_id, rx_id)` channel **bindings** depend on ISO-TP normal addressing as
   modelled by `python-can-isotp` / `esp_isotp`. The raw IDs above are valid CAN
   regardless, but the binding rests on the **same unverified `esp_isotp`/TWAI
   item flagged in §1** — confirm at setup before firmware.
3. **§6** (heartbeat) uses class 0, node 0, ID `0x000` as a raw single broadcast
   frame — already the highest-priority slot on the bus, so liveness is never
   starved by data traffic.

---

## §5 Interaction model — **hybrid by traffic class (transactions sync, jobs async)**

### Context
When a sender puts a message on the bus, does its application logic **wait for the
result** before continuing, or **send and continue**, matching the later result by
the §2 correlation tag? `[gloss: the uint16 tag — source-node high bits + per-node
sequence — that lets a reply be matched to its request.]`

Two facts reshape this from how it was first framed:
- **ISO-TP already guarantees delivery.** §1's transport is connection-oriented
  with a flow-control handshake, so the sender already knows the message *arrived*.
  §5 is therefore **not** about reliability — it is purely about whether the
  sender's **UX and state machine wait for the application *result*** (status +
  balance), which ISO-TP does not provide.
- **"Block" ≠ freeze the MCU.** On the C3's single FreeRTOS task `[gloss: the
  per-MCU RTOS thread driving its role]`, "request/response" means the *app* state
  machine sits in a `WAITING_FOR_RESULT` state **with a timeout** while the ISO-TP
  poll keeps running underneath. It is a UX/state choice, not a CPU busy-wait.

### Options considered
- **1 — Synchronous request/response everywhere.** Terminal *and* Job Submitter
  both block on their result. One uniform pattern.
- **2 — Fire-and-forget + correlate by tag, everywhere.** Every sender sends and
  moves on; all results arrive asynchronously, matched by the §2 tag.
- **3 — Hybrid by traffic class.** **Transactions** (interactive, #2) =
  request/response; **jobs** (batch, #4) = fire-and-forget (submit returns a quick
  "accepted, jobId=N"; completion notifies later). Mirrors §4's class 2 (txn) vs
  class 3 (job) split and the real CICS-online vs JES-batch distinction.

### Rated comparison
| Criterion | 1: sync everywhere | 2: async everywhere | 3: hybrid by class |
|---|---|---|---|
| CICS-online fidelity (txn path) | high | low | high |
| JES-batch fidelity (job path) | low | high | high |
| Terminal UX (operator sees result) | high | low–medium | high |
| Per-node firmware simplicity | high | medium | high* |
| Uses §2 tag machinery | partial | high | high |
| Concurrency headroom (Phase 2 load-gen) | low | high | high |

*\*Hybrid's complexity is in the **spec**, not the firmware: #2 implements only the
sync pattern, #4 only the async one — neither node gets more complex; the contract
just holds two patterns.*

### Decision
**Option 3 — hybrid by traffic class.** Each path gets the model that is *correct*
for it, along the class boundary §4 already drew:
- **Transaction path (#2 ↔ Pi):** synchronous request/response. The terminal
  enters `WAITING_FOR_RESULT` on submit and displays the outcome (e.g.
  "DEPOSIT OK, balance $X" / "INSUFFICIENT FUNDS") before accepting new input.
- **Job path (#4 ↔ Pi):** fire-and-forget. `JOB_SUBMIT` returns a fast accept
  ("accepted, jobId=N" or "queue full"); the eventual completion is delivered
  asynchronously and correlated by tag.

### Rationale
- **UX is decisive on the txn path on its own:** a banking terminal that doesn't
  tell the operator whether the deposit committed is a bad terminal, independent of
  fidelity. Fidelity agrees — a 3270 terminal input-inhibits the keyboard on an AID
  key-press until the host replies `[gloss: the 3270 locks input until the host
  unlocks it — genuinely synchronous from the operator's seat]`, so the operator's
  experience *is* synchronous.
- **The job path pulls the other way for equally good reasons:** a batch job is
  *defined* by not blocking on completion — submit, get notified later. Forcing #4
  to block (Option 1) is both unfaithful and pointless.
- So the split is not a compromise; each path is *right*, and it reuses §4's class
  boundary rather than inventing a new seam.

`Learning/fidelity driver:` the hybrid is chosen partly to reproduce the
**CICS-online-synchronous vs JES-batch-asynchronous** distinction faithfully.
*Technical cost accepted:* two interaction patterns in the contract instead of one
— slightly more to document and reason about, though no single node's firmware gets
more complex.

**Case against, recorded honestly:** Option 2 has a real edge — if a Phase-2 load
generator wants many transactions in flight *from the terminal itself*, a
synchronous terminal caps at one outstanding txn per terminal. Weighted low because
Phase 1 has a human at a keypad (one txn at a time), and the high-concurrency path
is the **Pi-side injector** (system-design §6), which bypasses the terminal
entirely. Revisit if the terminal itself ever needs concurrent in-flight txns.

### Consequences (these constrain later sections)
1. **Timeout re-derivation (open).** Request/response needs a timeout. The retired
   `RETIRED-message_protocol.md` used **500 ms**, but that predates the Pi doing a real
   SQLite WAL commit, which can exceed the old MCU-to-MCU hop. The value must be
   **re-derived**, best alongside §6's heartbeat timing — flagged there, not fixed
   here.
2. **Job-accept ack payload (→ §7).** The fast accept needs a defined payload —
   `jobId` + accepted / `QUEUE_FULL` — mapped onto the job channel. A §7 detail.
3. **Terminal state machine (→ per-node README #2):** `IDLE → SUBMITTING →
   WAITING_FOR_RESULT → DISPLAY → IDLE`, with the §5 timeout as the escape edge out
   of `WAITING_FOR_RESULT`.
4. **Tag correlation still required on both paths** (§2): synchronous on the txn
   path is a UX/state property; the reply is still matched to its request by tag
   underneath.

---

## §6 Heartbeat & timeouts — **D2 (each MCU → Pi); 1 s / 3 s; txn timeout 2 s (all provisional)**

### Context
§6 sets per-node **liveness** and, coupled in from §5, the **request/response
timeout**. Framing and priority are already fixed: heartbeat is **raw single-frame
CAN, not ISO-TP** (§1 consequence 2), broadcast on **class 0 / node 0 / ID
`0x000`** — the highest-priority slot on the bus (§4 consequence 3). So §6 decides
only **direction, cadence, timeout**, and the re-derived **txn timeout**.

The purpose of liveness here is to **detect a dead channel peripheral and flag it
on the Operator Console** (system-design §4). The retired project's heartbeat was a
fragile broadcast-**ACK mesh** (every node ACKing), which ADR-012 diagnosed as a
core failure; the new design explicitly wants **per-node liveness, not a mesh**.

### Direction — options considered
- **D1 — Pi → all MCUs.** Pi pings; each MCU learns "Pi alive." Does *not* give the
  console the per-node picture of *which MCU* died.
- **D2 — each MCU → Pi.** Each MCU announces itself; the Pi tracks per-node
  liveness and flags a silent node. This is exactly the console's specified job.
- **D3 — both.** Adds proactive Pi-down detection MCU-side, at double the traffic.

| Criterion | D1: Pi→all | D2: MCUs→Pi | D3: both |
|---|---|---|---|
| Detects a dead MCU (console's job) | low | high | high |
| Detects a dead Pi (MCU-side) | high | low–medium | high |
| Bus traffic (5 nodes, light) | lowest | medium | highest |
| Fidelity to "per-node liveness, not mesh" | medium | high | medium |
| Firmware simplicity | high | high | medium |

### Decision
**D2 — each MCU emits a heartbeat to the Pi.** It covers the stated requirement
(console shows which node died) with the least machinery and without reintroducing
the ACK-mesh. A dead **Pi** is detected by other means — a transaction request will
hit the §5 timeout the instant the operator tries to use a down Pi — so proactive
Pi-down detection (D3) is not worth doubling heartbeat traffic for in Phase 1.
*Revisit D3 if idle terminals should show "SYSTEM OFFLINE" without a user action.*

Note: all four MCUs share the broadcast ID `0x000`; the **source node** is read
from the frame's payload, not a distinct ID per node (heartbeat is control-plane,
not an addressed ISO-TP channel). Exact payload byte layout → §7.

### Cadence, timeout, and the coupled txn timeout
Pattern: **timeout = N × cadence**, N = 3, so a single dropped frame does not
false-alarm `[gloss: miss 3 consecutive beats before declaring a node dead]`.

| Value | Provisional setting | Basis |
|---|---|---|
| Heartbeat cadence | **1 s** | human-timescale liveness; light bus load |
| Liveness timeout | **3 s** (3 × cadence) | one missed beat tolerated |
| Txn req/resp timeout (§5) | **2 s** | must exceed worst-case Pi round-trip incl. **SQLite WAL commit** (an fsync — tens of ms, spiking higher under load); old 500 ms predates a real DB |

`[gloss: WAL commit forces an fsync to the Pi's SD card — the slow, variable part
of the round-trip, which is why 2 s ≫ the old 500 ms MCU-to-MCU figure.]`

### ⚠ Provisional — reassess at bring-up
These three numbers are **whiteboard defaults, not measured values.** A
bench-measured commit latency and observed bus timing should confirm or replace
them once the system is up — set each timeout to a healthy multiple of the *actual*
worst case. Per verify-don't-assume, a number that depends on physical timing is
confirmed on hardware, not frozen in design. *(A future `bring-up-checklist.md` —
the bring-up analogue of the BOM's verify-before-buy list — is the natural home to
collect this alongside the §1 `esp_isotp`/TWAI caveat and the BOM hardware checks;
proposed, not yet created. When the measurement happens, log the result in
`learning-log.md`.)*

### Consequences
1. **§7** defines the heartbeat payload (`source` node + `uptime` — see §7.6).
2. **Per-node firmware:** each MCU runs a 1 s periodic heartbeat emit; the Pi runs
   a per-node liveness tracker (last-seen timestamp, 3 s window) feeding the
   Operator Console (#1).
3. The txn timeout is the escape edge out of the terminal's `WAITING_FOR_RESULT`
   state (§5 consequence 3).

---

## §7 Message-type mapping — **DECIDED (2026-06-28)**

Maps the carried-over `RETIRED-message_protocol.md` types onto the §4 ID scheme and ISO-TP
payloads, and defines each payload's byte layout. Because `RETIRED-message_protocol.md`
describes the **retired peer-to-peer I2C architecture**, this is partly
*re-derivation, not a 1:1 mapping*: several legacy hops collapse onto the Pi (which
mediates all traffic — ADR-0001), the four `DB_*` types drop entirely, and the
interactive terminal path has **no legacy equivalent**.

### §7.0 Legacy-type disposition (the targets §7 must lay out)
`[gloss: disposition table = each inherited item assigned survive / re-express /
drop, so nothing is silently lost; traceability matrix = the row-per-item old→new
mapping below. See glossary-planning.]`

| Legacy type (old dir) | Disposition | New form |
|---|---|---|
| `JOB_SUBMIT` (#5→#4) | re-expressed (role/dir corrected) | #4 (Job Submitter) → Pi/JES |
| `JOB_DISPATCH` (#4→#2) | drops from wire | Pi-internal IPC (JES → transaction processor) |
| `JOB_COMPLETE` (#2→#4) | re-expressed | Pi → #4, async, correlate by jobId (§7.5) |
| `JOB_RESULT` (#4→#5) | collapses into journal | Pi → #5 `JOURNAL` frame (§7.3) |
| `DB_READ/_RESULT/_WRITE/_ACK` | drop entirely (locked) | `sqlite3` calls inside the processor |
| `HEARTBEAT` (#1→all) | re-expressed | each MCU → Pi, `0x000`, raw single frame (§6/§7.6) |
| `HEARTBEAT_ACK` (any→#1) | drops | no ACK mesh (§6) |
| `ERROR` (any→any) | re-expressed | class 1, code in ID `[3:0]` (§7.4) |
| *(none — new)* | new | `TXN_REQUEST` / `TXN_RESULT`, class 2 `(0x250, 0x240)` |
| *(none — from §5)* | new | `JOB_ACCEPT`: Pi → #4, `jobId` + accepted / `QUEUE_FULL` |

### §7.1 Payload encoding conventions — **DECIDED**
**Family (inherited from §3, not re-opened):** fixed-field **binary** payloads —
`uint32` cents (4 B), 8-byte ASCII account, enums as small integers. JSON is
foreclosed by §3's binary money field, and a fixed-width binary record is the
COBOL-copybook-faithful form (a copybook *is* a fixed-width record layout). Two
layout conventions are pinned on top of that inherited family:

1. **Leading discriminator byte: `type` (high nibble) + `version` (low nibble).**
   The CAN ID (§4) is an **L2** address — it names the *channel*, not the application
   message — and ISO-TP (**L4**) delivers an opaque reassembled blob whose PCI bytes
   `[gloss: ISO-TP header — frame type + length/sequence, transport only]` carry no
   app type. A single channel carries more than one app message (e.g. the job channel
   `(0x380, 0x390)`, Pi→#4, carries *both* `JOB_ACCEPT` and `JOB_COMPLETE`), so
   the app-layer type must live **in the payload**. *A version nibble is near-free
   insurance — the retired project was bitten by an undocumented wire-format change
   (the 16-byte BSC FIFO surprise, ADR-012).*
2. **Little-endian** for every multi-byte integer (`uint16` tag, `uint32` cents).
   Both the C3 and the Pi are little-endian-native, so an LE wire format needs **no
   byte-swap at either end**; network/big-endian order would only add a no-op
   conversion on a closed 5-node bus. `[gloss: endianness = multi-byte integer byte
   order; little-endian = least-significant byte first — see glossary.]`

*Learning/fidelity note:* the fixed-width binary record is the COBOL-copybook form
(charter A). *Technical cost accepted:* binary payloads are less self-describing on
`candump` than JSON would be — mitigated by the type/version byte and the fact that
sigrok/Wireshark decode the ISO-TP framing around them.

**Type nibble registry** (high nibble of byte 0 in every payload):

| nibble | type | transport |
|---|---|---|
| `0x1` | `HEARTBEAT` | raw single frame |
| `0x2` | `ERROR` | raw single frame (optional payload) |
| `0x3` | `TXN_REQUEST` | ISO-TP |
| `0x4` | `TXN_RESULT` | ISO-TP |
| `0x5` | `JOB_SUBMIT` | ISO-TP |
| `0x6` | `JOB_ACCEPT` | ISO-TP |
| `0x7` | `JOB_COMPLETE` | ISO-TP |
| `0x8` | `JOURNAL` | ISO-TP |
| `0x9–0xF` | reserved | — |

### §7.3 Output Writer journal — **DECIDED: class 4 (own reserved class)**

The journal frame (Pi→#5 post-transaction output line for OLED/printer) rides
**class 4**, not class 2.

**Rationale.** Class 2 = "transaction (interactive)" — the journal is neither
interactive nor a transaction; assigning it class 2 would make the §4 class table
partially lie and blur the `candump` picture. Class 4 gives it a clean semantic
slot: class 4 frames = journal, unambiguously. *Cost accepted:* one of four
reserved class slots consumed; three remain for Phase 2.

**Channel:** ISO-TP pair `(0x4A0, 0x4B0)` — Pi tx = `0x4A0`, #5 rx/FC = `0x4B0`.

### §7.4 `ERROR` encoding — **DECIDED: A+ (code in ID low bits + optional detail payload)**

`ERROR` is a **class-1 raw single frame** (control plane, like heartbeat — not
ISO-TP). The error code lives in the **ID low bits `[3:0]`** — the bits §4
reserved "e.g. error subcode" — so the ID alone is sufficient for triage on
`candump`/sigrok. An **optional** small detail payload may follow (inherits §7.1:
`type`+version byte, then context bytes — typically the offending `uint16`
correlation tag); no payload = code-only alarm.

**Deciding axis — must survive transport failure.** An `ERROR` has to be
reportable when the transport itself is the fault: `TIMEOUT` (L4/L5) and
`BUS_ERROR` (L2, only after the controller recovers from bus-off) are exactly the
cases where an ISO-TP session may be unestablishable, so a **raw single frame is
required** (rules out option C, full ISO-TP). `PARSE_ERROR` (L6) escalates on a
*healthy* transport but rides the same raw path harmlessly. Code-in-ID also gives
highest-priority preemption (§4's class-1 "preempts normal data" intent). The
optional payload buys back structured context without dragging `ERROR` onto ISO-TP.

*Cost accepted:* `ERROR` becomes a special "the-ID-is-the-message" case against
§7.1's uniform-payload convention. Chosen over **option B** (code in a payload
byte, keeps §7.1 uniformity) because B leaves §4's reserved `[3:0]` bits dead and
loses ID-alone triage. `Learning/fidelity note:` errors are *detected* across many
layers but *escalated* through one L7 type — the layered-error map (L1 silicon ⇄
L4 library ⇄ L7 app) is the lesson, logged in `learning-log.md` 2026-06-27.

*Caveat:* the precise ISO-TP abort surface that raises an L4 `TIMEOUT` is the
still-unverified §1 `esp_isotp` item — confirm the error/callback API before
firmware.

### §7.5 Job-accept ack — **DECIDED: A (two distinct types)**
The Pi→#4 job downlink is **two types**, not one status stream:
- `JOB_ACCEPT {jobId, ACCEPTED | QUEUE_FULL}` — the **synchronous** reply to
  `JOB_SUBMIT`; #4 correlates it by the §2 **tag** (req↔resp) and *learns its
  `jobId` here*.
- `JOB_COMPLETE {jobId, SUCCESS | FAILED, reason, [balance]}` — the **async**
  completion; correlated by **`jobId`** (the durable job handle), not the tag
  (whose per-node sequence may have cycled by then). `balance` present only when
  the job was a `BALANCE`.

**Rationale.** Two types make the sync-accept vs async-complete boundary legible on
the wire and in #4's state machine (type → handler) instead of hiding it in a
status value. `QUEUE_FULL` sits cleanly as an accept-time rejection. The **two
different correlators** (tag for accept, jobId for completion) reinforce that these
are two messages, not two values of one. *Cost accepted:* one more type than a
unified `JOB_STATUS`; a richer job lifecycle would need new types rather than new
enum values — deferred under YAGNI `[gloss: "you aren't gonna need it"]`.

### §7.6 Heartbeat payload — **DECIDED: `source` + `uptime` (`uint32`)**

**Options considered:** `source` + `uptime` (A), `source` + `ts` wall-clock (B),
both (C). B and C require a time-sync message before the first heartbeat is
meaningful — new protocol machinery not planned for Phase 1. `uptime` directly
serves the liveness goal: it resets visibly on reboot, which is exactly what the
Console tracks. `uint32` chosen over `uint16` (max ~18 h) to avoid mid-session
wraparound on a bench that may run longer.

### §7.7 Per-type byte layouts — **DECIDED (2026-06-28)**

All offsets from byte 0 of the CAN data field (raw frames) or ISO-TP reassembled
payload. All multi-byte integers little-endian (§7.1). Diagrams show the payload
as a byte strip; each box is one byte.

---

#### `HEARTBEAT` — raw single frame, class 0, ID `0x000`

```
 0        1        2        3        4        5
 +--------+--------+--------+--------+--------+--------+
 |type|ver| source |       uptime (uint32 LE)          |
 | 0x10   |  node  |  byte0 |  byte1 |  byte2 |  byte3 |
 +--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x10` — high nibble `0x1` (HEARTBEAT), low nibble `0x0` (v0) |
| 1 | 1 | `source` | node ID: 1, 2, 4, or 5 (`uint8`) |
| 2 | 4 | `uptime` | seconds since boot (`uint32` LE) |

**Total: 6 bytes.** Fits raw CAN frame (≤8 B). ✓

---

#### `ERROR` — raw single frame, class 1, ID `0x1xx` (subcode in `[3:0]`)

Error code lives in the CAN ID — no payload needed for a code-only alarm. Optional
detail payload when context is available.

**Code-only (no payload):** 0 bytes. The ID alone suffices for `candump` triage.

**With optional detail payload:**

```
 0        1        2
 +--------+--------+--------+
 |type|ver|   tag (uint16)  |
 | 0x20   |  byte0 |  byte1 |
 +--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x20` — high nibble `0x2` (ERROR), low nibble `0x0` |
| 1 | 2 | `tag` | offending correlation tag (`uint16` LE); `0x0000` if not applicable |

**Total with payload: 3 bytes.** ✓

**Subcode enum** (CAN ID bits `[3:0]`):

| value | name | meaning |
|---|---|---|
| `0x0` | — | reserved |
| `0x1` | `TIMEOUT` | no ISO-TP response within §6 txn timeout |
| `0x2` | `PARSE_ERROR` | received malformed payload |
| `0x3` | `BUS_ERROR` | L2 bus fault (after controller recovers from bus-off) |
| `0x4–0xF` | — | reserved |

---

#### `TXN_REQUEST` — ISO-TP, class 2, #2→Pi, channel `(0x250, 0x240)`

```
 0        1        2        3        4        5        6        7
 +--------+--------+--------+--------+--------+--------+--------+--------+
 |type|ver|   tag (uint16)  |txn_type|           account (8 bytes ASCII) |
 | 0x30   |  byte0 |  byte1 |  enum  |  [0]   |  [1]   |  [2]   |  [3]  |
 +--------+--------+--------+--------+--------+--------+--------+--------+
 8        9        10       11       12       13       14       15
 +--------+--------+--------+--------+--------+--------+--------+--------+
 |      account (cont)              |        amount (uint32 LE)          |
 |  [4]   |  [5]   |  [6]   |  [7]  |  byte0 |  byte1 |  byte2 |  byte3 |
 +--------+--------+--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x30` |
| 1 | 2 | `tag` | correlation tag (`uint16` LE) |
| 3 | 1 | `txn_type` | `0x1`=DEPOSIT, `0x2`=WITHDRAW, `0x3`=BALANCE |
| 4 | 8 | `account` | 8-byte ASCII, zero-padded (`PIC 9(8)`) |
| 12 | 4 | `amount` | integer cents (`uint32` LE); `0` for BALANCE |

**Total: 16 bytes.** ISO-TP FF + 1 CF, 2 frames. ✓

---

#### `TXN_RESULT` — ISO-TP, class 2, Pi→#2, channel `(0x240, 0x250)`

```
 0        1        2        3        4        5        6        7        8
 +--------+--------+--------+--------+--------+--------+--------+--------+--------+
 |type|ver|   tag (uint16)  | status | reason |        balance (uint32 LE)        |
 | 0x40   |  byte0 |  byte1 |  enum  |  enum  |  byte0 |  byte1 |  byte2 |  byte3 |
 +--------+--------+--------+--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x40` |
| 1 | 2 | `tag` | mirrors request tag (`uint16` LE) |
| 3 | 1 | `status` | `0x0`=SUCCESS, `0x1`=FAILED |
| 4 | 1 | `reason` | `0x0`=none, `0x1`=INSUFFICIENT_FUNDS, `0x2`=NOT_FOUND; `0x0` on SUCCESS |
| 5 | 4 | `balance` | current balance in cents (`uint32` LE); `0` when not a BALANCE txn |

**Total: 9 bytes.** ISO-TP FF + 1 CF, 2 frames. ✓

---

#### `JOB_SUBMIT` — ISO-TP, class 3, #4→Pi, channel `(0x390, 0x380)`

```
 0        1        2        3        4        5        6        7
 +--------+--------+--------+--------+--------+--------+--------+--------+
 |type|ver|   tag (uint16)  |txn_type|           account (8 bytes ASCII) |
 | 0x50   |  byte0 |  byte1 |  enum  |  [0]   |  [1]   |  [2]   |  [3]  |
 +--------+--------+--------+--------+--------+--------+--------+--------+
 8        9        10       11       12       13       14       15
 +--------+--------+--------+--------+--------+--------+--------+--------+
 |      account (cont)              |        amount (uint32 LE)          |
 |  [4]   |  [5]   |  [6]   |  [7]  |  byte0 |  byte1 |  byte2 |  byte3 |
 +--------+--------+--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x50` |
| 1 | 2 | `tag` | correlation tag (`uint16` LE) — #4 correlates `JOB_ACCEPT` reply by this |
| 3 | 1 | `txn_type` | same enum as `TXN_REQUEST` |
| 4 | 8 | `account` | 8-byte ASCII (`PIC 9(8)`) |
| 12 | 4 | `amount` | integer cents (`uint32` LE); `0` for BALANCE |

**Total: 16 bytes.** ✓

*Note: identical field layout to `TXN_REQUEST` from offset 1 onward — the Pi's JES
intake and CICS router share field-extraction logic. The `type` byte (`0x50` vs
`0x30`) is the sole distinguisher.*

---

#### `JOB_ACCEPT` — ISO-TP, class 3, Pi→#4, channel `(0x380, 0x390)`

```
 0        1        2        3        4        5
 +--------+--------+--------+--------+--------+--------+
 |type|ver|   tag (uint16)  |  jobId (uint16) | status |
 | 0x60   |  byte0 |  byte1 |  byte0 |  byte1 |  enum  |
 +--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x60` |
| 1 | 2 | `tag` | mirrors `JOB_SUBMIT` tag (`uint16` LE) |
| 3 | 2 | `jobId` | Pi-assigned job handle (`uint16` LE); `0` if `QUEUE_FULL` |
| 5 | 1 | `status` | `0x0`=ACCEPTED, `0x1`=QUEUE_FULL |

**Total: 6 bytes.** ✓

---

#### `JOB_COMPLETE` — ISO-TP, class 3, Pi→#4, channel `(0x380, 0x390)`

Rides the same channel as `JOB_ACCEPT` — distinguished by the `type` byte (`0x70`
vs `0x60`). This is the §7.1 discriminator doing its job.

```
 0        1        2        3        4        5        6        7        8
 +--------+--------+--------+--------+--------+--------+--------+--------+--------+
 |type|ver|  jobId (uint16) | status | reason |        balance (uint32 LE)        |
 | 0x70   |  byte0 |  byte1 |  enum  |  enum  |  byte0 |  byte1 |  byte2 |  byte3 |
 +--------+--------+--------+--------+--------+--------+--------+--------+--------+
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x70` |
| 1 | 2 | `jobId` | job handle (`uint16` LE) — correlator for async completion |
| 3 | 1 | `status` | `0x0`=SUCCESS, `0x1`=FAILED |
| 4 | 1 | `reason` | `0x0`=none, `0x1`=INSUFFICIENT_FUNDS, `0x2`=NOT_FOUND; `0x0` on SUCCESS |
| 5 | 4 | `balance` | cents (`uint32` LE); `0` when not a BALANCE job |

**Total: 9 bytes.** ✓

---

#### `JOURNAL` — ISO-TP, class 4, Pi→#5, channel `(0x4A0, 0x4B0)`

Pi pre-formats all four OLED lines; #5 writes each line directly to its
corresponding display row — no parsing or wrapping logic on the MCU. Each line is
exactly 21 bytes, space-padded to fill the row (SSD1306 0.96" at default 6×8 px
font = 21 chars × 4 rows).

```
 0        1       21       22       42       43       63       64       84
 +--------+--------  - - -  +--------+--------  - - -  +--------  - - -  +--------+
 |type|ver|     line0 (21 bytes ASCII)      |     line1 (21 bytes ASCII)  |  ...   |
 | 0x80   |  space-padded, no NUL needed    |                             |        |
 +--------+--------  - - -  +--------+--------  - - -  +--------  - - -  +--------+

 Byte ranges:
   [0]      type|version  0x80
   [1–21]   line0         OLED row 0
   [22–42]  line1         OLED row 1
   [43–63]  line2         OLED row 2
   [64–84]  line3         OLED row 3
```

| offset | width | field | value / notes |
|---|---|---|---|
| 0 | 1 | `type`\|`version` | `0x80` |
| 1 | 21 | `line0` | OLED row 0, ASCII, space-padded |
| 22 | 21 | `line1` | OLED row 1 |
| 43 | 21 | `line2` | OLED row 2 |
| 64 | 21 | `line3` | OLED row 3 |

**Total: 85 bytes.** ISO-TP multi-frame. ✓

*Phase 2 note:* when the thermal printer joins (#5 deferred — BOM §4), it
typically does 32 chars/line. If 32-char lines are wanted, widen each field to 32
bytes (total 129 bytes) and bump the version nibble to `0x81` — receivers on the
old version ignore the new frame gracefully if they check the version.

---

### §7 channel summary

| Type | Dir | Class | Channel (tx, rx) | Transport | Total bytes |
|---|---|---|---|---|---|
| `HEARTBEAT` | MCU→Pi | 0 | broadcast `0x000` | raw | 6 |
| `ERROR` | any→any | 1 | `0x1xx` + subcode | raw | 0 or 3 |
| `TXN_REQUEST` | #2→Pi | 2 | `(0x250, 0x240)` | ISO-TP | 16 |
| `TXN_RESULT` | Pi→#2 | 2 | `(0x240, 0x250)` | ISO-TP | 9 |
| `JOB_SUBMIT` | #4→Pi | 3 | `(0x390, 0x380)` | ISO-TP | 16 |
| `JOB_ACCEPT` | Pi→#4 | 3 | `(0x380, 0x390)` | ISO-TP | 6 |
| `JOB_COMPLETE` | Pi→#4 | 3 | `(0x380, 0x390)` | ISO-TP | 9 |
| `JOURNAL` | Pi→#5 | 4 | `(0x4A0, 0x4B0)` | ISO-TP | 85 |

---

## References
- **ADR-0001** — architecture (Pi core, C3 channels, shared CAN bus)
- **system-design** — §3 topology, §5 data model/WAL, §6 testability, §8 open decisions, §9 doc set
- **BOM** — parts + verified per-node pin budget
- **RETIRED-message_protocol.md** — carried-over message semantics to re-map
- **ISO 15765-2** (ISO-TP); `espressif/esp_isotp`; `python-can-isotp`
