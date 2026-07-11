# Glossary — Technical Terms

> Technical vocabulary used across the project, one to two lines each. Pairs with
> the planning glossary (`glossary-planning.md`). Living document — keep adding as
> new terms appear. Two reference diagrams are embedded: the bus topology (under
> CAN) and the OSI mapping (under OSI).

## CAN bus & physical / data-link layer

**CAN (Controller Area Network)** — a multi-master serial bus where nodes arbitrate
for the wire in hardware; no master/slave roles. The project's inter-device
transport.

**Classical CAN (CAN 2.0) vs CAN FD** — classical frames carry ≤8 data bytes; CAN FD
allows up to 64. The MCP2515 and the C3 TWAI are classical only, so 8 bytes is a
hard cap — the reason a transport layer is needed.

**TWAI** — Espressif's on-chip CAN 2.0 controller on the ESP32-C3 (CAN-compatible;
named TWAI for trademark reasons).

**MCP2515** — a standalone CAN controller chip; on the Pi it sits on a HAT and talks
to the Pi over SPI, exposed through SocketCAN.

**SN65HVD230** — the 3.3 V CAN transceiver converting a controller's TX/RX into the
differential bus signals. One per node.

**CANH / CANL** — the two differential signal wires; a bit is read from the voltage
*difference* between them (noise-resistant).

**CAN frame / data frame** — one bus message: ID + control bits + ≤8 data bytes +
CRC + ACK. The unit that arbitrates for the bus.

**CAN ID (identifier)** — 11-bit (standard) or 29-bit (extended); names the message
and, because lower ID wins arbitration, also sets its **priority**.

**Arbitration** — the hardware contest for the bus: nodes transmit their IDs at once
and the lowest ID wins without collision. Enables multi-master.

**Bit-stuffing / stuff bit** — after 5 identical consecutive bits the transmitter
inserts one opposite bit (stripped by receivers) to keep clocks synced. Makes frame
length data-dependent: a standard 8-byte frame is ~111 bit-times nominal, up to
~135 worst case (~24 stuff bits).

**NRZ (non-return-to-zero)** — line coding where the level holds for the whole bit
with no guaranteed per-bit edge; the reason bit-stuffing is needed.

**Termination (120 Ω)** — one 120 Ω resistor across CANH↔CANL at *each of the two
physical bus ends* (two total) to stop reflections. Middle nodes remove any onboard
terminator.

**Shared / multidrop bus** — all nodes tap the same two wires (vs a star, where each
node has a private link). Adding a node costs no extra pins on other nodes.

**SocketCAN / `can0` / `candump`** — Linux's CAN networking stack; `can0` is the
Pi's CAN interface; `candump` sniffs every frame for debugging.

```
Bus topology — ONE shared bus, 3 conductors total (CANH, CANL, GND):

  120Ω ▮                                                  ▮ 120Ω   ← terminators at
       ▮  (across CANH↔CANL)             (across CANH↔CANL)  ▮        the 2 bus ends
CANH ──╂────┬──────────┬──────────┬──────────┬──────────┬───╂──
       ▮    │          │          │          │          │   ▮
CANL ──╂────┼──────────┼──────────┼──────────┼──────────┼───╂──
            │          │          │          │          │
          XCVR       XCVR       XCVR       XCVR       XCVR      ← SN65HVD230 each
         ESP32      ESP32    MCP2515+Pi    ESP32      ESP32
          #1         #2       CORE(SPI)     #4         #5
  Each node taps BOTH CANH and CANL; all share a common GND.
```

## Transport: ISO-TP

**ISO-TP (ISO 15765-2)** — the standard transport layer over CAN: segments a message
(≤4095 bytes) into frames, reassembles, and flow-controls. Point-to-point, addressed
via a `(tx_id, rx_id)` ID pair.

**SF / FF / CF / FC** — ISO-TP frame types: Single Frame (whole short msg), First
Frame (opens a multi-frame transfer), Consecutive Frame (streamed, sequence-numbered
chunks), Flow Control (receiver→sender pacing).

**PCI (Protocol Control Information)** — ISO-TP's header byte(s) at the start of each
frame's data, giving the frame type and length/sequence.

**Block Size (BS) / STmin** — flow-control parameters: how many CFs the sender may
send before the next FC (BS=0 = all), and the minimum gap between CFs. Like a TCP
credit window + a rate limit.

**Flow status (CTS / WAIT / OVFLW)** — the receiver's verdict in an FC frame:
clear-to-send, hold, or abort (overflow).

**Segmentation / reassembly** — splitting a message into frames and rebuilding it;
the core job ISO-TP does that raw CAN cannot.

**`esp_isotp` / `isotp-c` / `python-can-isotp`** — ISO-TP implementations: the
official Espressif component (ESP-IDF/TWAI), a platform-agnostic C core, and the
Python wrapper over the Linux kernel ISO-TP socket, respectively.

## OSI model

**OSI model** — a 7-layer reference splitting "what data means" (L7) from "how it's
encoded" (L6) from "how it's transported" (L4) from "how it's framed/wired" (L2/L1).
The discipline that keeps storage form, message meaning, and wire form independent.

```
 OSI LAYER          OUR STACK
 ─────────────────  ────────────────────────────────────────────────────────
 7 Application      message SEMANTICS (DEPOSIT/WITHDRAW/BALANCE, JOB_*, HEARTBEAT)
 6 Presentation     SERIALIZATION (integer cents, fixed-width PIC 9(8), endianness)
 5 Session          dialog control (req↔resp correlation by tag; heartbeat windows)
 4 Transport        ISO-TP (segments/reassembles; flow control)   ◄ raw CAN can't
 3 Network          (empty — one bus, no routing)
 2 Data-link        CAN controller: TWAI / MCP2515 (frame, ID, arbitration, CRC, ACK)
 1 Physical         CANH/CANL pair, SN65HVD230, NRZ, 120Ω, common GND
 ─────────────────  ────────────────────────────────────────────────────────
 CAN gives L1–L2; ISO-TP adds L4; we build L6–L7. L3/L5 stay minimal.
```

## Mainframe architecture & transaction processing

**CICS** — IBM's transaction-processing middleware: receives a request, routes it,
touches storage, acknowledges. The Pi's "CICS router" process is the analogue.

**Task / task number** — CICS runs each request as a *task* with a compact,
region-local **task number** for dispatch (recycled over time). The bus
**correlation tag** is the analogue.

**Unit of work (UOW)** — the recoverable scope: changes that commit or roll back
atomically (the ACID unit).

**UOWID / NETNAME** — the durable, globally-unique unit-of-work identifier (derived
from task-attach time + the origin system's NETNAME). The project's **UUID** is the
analogue; both live in the log.

**Syncpoint** — the commit boundary of a UOW; changes become durable once the
syncpoint is recorded on the log. The SQLite `COMMIT` is the analogue.

**Two-phase commit (2PC)** — for a UOW spanning multiple resource managers: phase 1
"prepare" (all vote + log), then phase 2 "commit" (all harden). Needed only with >1
store; the project has one (SQLite), so a plain commit suffices.

**In-doubt** — the dangerous gap when a participant has voted to commit but hasn't
heard the final decision; a crash here leaves the UOW unresolved until recovery. The
project's PENDING-without-COMMITTED rows are the analogue.

**Recovery manager / backout** — on restart, walks the log, finds in-flight/in-doubt
UOWs by UOWID, and resolves each (rolls back or completes). The boot-time replay of
PENDING rows is the analogue.

**JES (Job Entry Subsystem)** — the mainframe job scheduler; ingests/dispatches jobs.
The Pi's JES process + MCU #4 (Job Submitter) are the analogue.

**DASD** — mainframe durable disk storage. The Pi's local SQLite is the analogue.

**MRO (Multi-Region Operation)** — CICS split across cooperating regions (separate
address spaces) by role, so terminals, application logic, and files scale and fail
independently. The Pi's separate router / processor / storage processes are the
analogue (ADR-0001).

**TOR (Terminal-Owning Region)** — the CICS region that owns the terminals and
*function-ships* each request to whichever region can service it; results return
*through* the TOR to the terminal. The Pi's **router** process is the analogue — the
sole CAN gateway, inbound and outbound (ADR-0002).

**AOR (Application-Owning Region)** — the CICS region that runs the application
(business logic), reached by function shipping from the TOR; it never drives a
terminal directly. The Pi's **transaction processor** is the analogue.

**FOR (File-Owning Region)** — the CICS region that owns the data files/records;
AORs reach data by function-shipping file requests to it. The Pi's **storage** module
(SQLite, the DASD-analogue) is the analogue.

**Function shipping** — CICS's mechanism for forwarding a request for a resource
(terminal, file, program) owned by *another* region to that region, and returning the
reply. The Pi's local IPC between router / processor / storage is the analogue.

## Storage & durability

**SQLite WAL (Write-Ahead Log)** — a journaling mode letting a reader run
concurrently with a writer. Local to the Pi; sole writer = the transaction
processor.

**Write-ahead pattern** — insert row PENDING → update balance → mark COMMITTED, in
one atomic transaction. On reboot, PENDING-without-COMMITTED = an interrupted write
to replay/flag. This is what makes a transaction survive a crash.

**Integer cents** — money is stored/sent as a `uint32` count of cents, never a float
($100.00 = 10000). Avoids floating-point rounding error.

## Encoding & COBOL

**Endianness (big-endian / little-endian)** — the byte order of a multi-byte integer
on the wire or in memory. **Big-endian** stores the most-significant byte first (the
"big end") and is the conventional *network byte order*; **little-endian** stores the
least-significant byte first. Both the ESP32-C3 and the Pi are little-endian
natively, so an LE wire format needs no byte-swap at either end — the project's choice
for the `uint16` tag and `uint32` cents (protocol-spec §7.1). Mnemonic: **big-endian =
big end first.** (The name is from *Gulliver's Travels* — the warring Big-Endian and
Little-Endian factions who disagree on which end of a boiled egg to crack — applied to
computing by Danny Cohen in 1980. A literary joke, not jargon with a history to
retire.)

**COBOL copybook** — a shared record-layout definition programs `COPY` in; fields are
fixed-width via PICTURE clauses.

**PIC (PICTURE) clause** — declares a field's fixed type/width, e.g. `PIC 9(8)` =
exactly 8 numeric digits. The account number's model.

**DISPLAY / COMP-3 / COMP** — three COBOL representations of the same numeric field:
zoned decimal (one byte per digit, 8 B), packed decimal (two digits per byte, ~5 B),
binary (4 B). Same logical value, different size.

**GnuCOBOL** — an open-source COBOL compiler; the planned later reimplementation of
the transaction processor (an authenticity upgrade).

## Protocol conventions

> Terms specific to this project's wire contract (protocol-spec), surfaced while
> defining the §7 byte maps.

**Type discriminator byte** — byte 0 of every payload in this project: high nibble =
message type (e.g. `0x3` = `TXN_REQUEST`), low nibble = format version (currently
`0x0`). Needed because ISO-TP delivers an opaque blob with no app-layer type
information, and a single channel may carry more than one message type (e.g. the job
channel carries both `JOB_ACCEPT` and `JOB_COMPLETE`). The version nibble provides
forward compatibility — a receiver that doesn't recognise the version can reject
gracefully rather than misparse. `ERROR` is the deliberate exception: its subcode
rides the CAN ID bits `[3:0]` instead, because the payload may never arrive when the
transport itself is the fault.

**Fire-and-forget** — an interaction pattern where the sender transmits a message and
immediately continues without waiting for an application-level result; any eventual
reply is matched to the original request by a correlation identifier (the §2 tag or
`jobId`). Contrasted with **request/response**, where the sender's state machine waits
in a `WAITING_FOR_RESULT` state until the reply arrives or a timeout fires. In this
project: the job path (#4 ↔ Pi) is fire-and-forget; the transaction path (#2 ↔ Pi)
is request/response. Note that ISO-TP's flow-control handshake already guarantees
*delivery* on both paths — fire-and-forget is a choice about the *application* state
machine, not about reliability.

## Project-specific conventions

**Correlation tag (A2)** — the compact `uint16` (source-node + per-node sequence)
carried on the bus in place of the full UUID; the Pi maps tag↔UUID in the log.
Models a CICS task number.

**Heartbeat / liveness** — a periodic ping confirming a node is alive; a missed
window flags the node on the Operator Console. Sent as a raw single CAN frame, not
ISO-TP.

**Request/response vs fire-and-forget** — whether the terminal blocks waiting for an
ack, or sends and correlates the later result by tag. Transaction path (#2) =
request/response; job path (#4) = fire-and-forget. See "Protocol conventions" above
for the full definition.

**PCF8574** — an I2C GPIO expander; on the Transaction Terminal it hosts the 4×4
keypad (8 pins) over I2C, freeing the C3's scarce GPIO.

**FreeRTOS task** — the real-time-OS thread model on the MCUs; one task per MCU drives
its role (and would poll `esp_isotp` on a 1–10 ms cadence).

**RTC (real-time clock)** — a dedicated timekeeping circuit that maintains wall-clock
time independently of the main processor, typically battery-backed so time is
preserved across power cycles. The ESP32-C3 has no RTC — which is why the `HEARTBEAT`
payload uses `uptime` (seconds since boot, self-contained) rather than a wall-clock
timestamp `ts` (which would require a time-sync message from the Pi before the first
heartbeat is meaningful).

**Ingress / egress** — the direction of traffic across a boundary: **ingress** =
frames arriving into the Pi from the CAN bus; **egress** = frames the Pi sends out
onto the bus (generic networking terms; also called north–south traffic). In this
project both directions funnel through the **router** process — it decodes and routes
ingress, and is the *sole transmitter* of egress (ADR-0002).

## Error handling & observability (software patterns)

> Cross-cutting patterns, not CAN-specific — surfaced while deciding §7.4 (`ERROR`).
> The throughline: errors are *detected* at many layers but *handled* where there's
> context, and *escalation/reporting* is centralized even when handling is not.

**Separation of detection from handling** — the principle that an error should be
*handled* at the level that has enough context to act on it, not necessarily where it
is *detected*; layers without that context propagate rather than swallow it.
Exceptions embody it: `throw` where detected, `catch` at a boundary.

**Centralized observability / error reporting** — funnelling errors from many sources
into one sink (syslog · journald · Sentry · the ELK stack) so failures are seen in one
place. The project's Operator Console (#1) / Pi log is the analogue: detection stays
distributed across nodes/layers, *reporting* converges.

**Supervisor tree / "let it crash"** — the Erlang/OTP pattern: worker processes
detect-and-die on a fault; a dedicated **supervisor** centrally decides restart vs
escalate. Detection distributed, recovery *decision* centralized. React **error
boundaries** are the UI analogue.

**Dead-letter queue (DLQ)** — a quarantine queue for messages that cannot be processed
(malformed, or a poison message) — moved off the main queue so one bad item does not
block the rest, then re-driven after a fix, inspected by an operator, or consumed by a
dead-letter handler. Name from the postal "dead letter office." Cousin of the project's
boot-time PENDING-row replay.

**Poison message** — a message that fails (often crashing its consumer) on *every*
delivery attempt, so a naïve retry loop never terminates; the reason a DLQ exists.

**Head-of-line blocking** — when a stuck or slow item at the *front* of a queue/stream
stalls everything behind it that could otherwise proceed.

**End-to-end argument** (Saltzer, Reed & Clark, 1984) — a foundational systems paper:
certain correctness checks must live at the application **endpoints** regardless of how
reliable the layers beneath are, because only the endpoints know what "correct" means.
Why business validation (e.g. insufficient-funds) is **L7** and cannot be delegated down
to the transport.
