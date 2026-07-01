# Requirements & Definition of Done — Mainframe Simulation (Phase 1)

> **Scope: Phase 1 only** — a working system. Phase 2+ items are listed in §6
> so nothing is silently dropped. Architecture: ADR-0001. Wire contract:
> protocol-spec.md. Hardware: BOM.md.
>
> Requirements are written as **testable acceptance criteria** — the observable
> outcome, not the implementation. "Survives a reboot" means a deliberate
> power-cycle test, not an assumption.
>
> Three DoD levels, in dependency order:
> 1. **Per-node bring-up DoD** — hardware alive, CAN frames on bus, OLED lit.
>    Nothing else can be tested until this passes.
> 2. **Per-feature DoD** — each subsystem's functional behaviour.
> 3. **System DoD** — the full end-to-end flow, integrated.
>
> Last updated: 2026-06-28.

---

## §1 Scope

Phase 1 delivers a working system capable of:
- processing a deposit, withdrawal, and balance query end-to-end
- storing results durably (a completed transaction persists across a clean reboot)
- reporting per-node liveness on the Operator Console
- journalling each transaction result to the Output Writer's OLED
- submitting a canned job from the Job Submitter

**Not in Phase 1 scope** (see §6): crash-recovery replay of PENDING rows,
operator dashboard, transaction generator, throughput/loss measurement, thermal
printer, RFID job submission.

---

## §2 System-level functional requirements

These are the properties the system as a whole must satisfy. Per-node and
per-feature DoDs in §§3–5 are the acceptance criteria that prove them.

**R-SYS-01 — End-to-end transaction.** A deposit, withdrawal, and balance query
entered at Transaction Terminal #2 shall each complete: the result is displayed on
#2's OLED, stored in the Pi's SQLite database, and a journal line appears on
Output Writer #5's OLED.

**R-SYS-02 — Durability.** A transaction that has completed (COMMITTED row in
the database) shall be present in the database after a deliberate clean power-cycle
of the Pi.

**R-SYS-03 — Liveness.** Operator Console #1 shall show, for each of the four
MCU nodes, whether that node is alive or not, updating within the liveness timeout
window (currently provisionally 3 s — protocol-spec §6).

**R-SYS-04 — Job path.** A canned job submitted from Job Submitter #4 shall be
accepted by the Pi's JES process and a completion notification shall be displayed
on #4's OLED.

**R-SYS-05 — Bus integrity.** All inter-device communication shall pass over the
CAN bus. No fallback to direct USB serial, SSH, or other out-of-band paths for
any runtime message defined in the protocol spec.

**R-SYS-06 — Error visibility.** An ERROR frame (protocol-spec §7.4) generated
by any node shall be visible on `candump` on the Pi and shall be logged by the Pi.

---

## §3 Per-node bring-up DoD

**Purpose:** confirm hardware is functional before any firmware logic is tested.
Do this for each node before moving to §4. A node that fails bring-up blocks all
§4 and §5 tests that depend on it.

> **Prerequisite for all nodes:** `candump can0` running on the Pi and the logic
> analyzer attached to the bus. Every CAN frame sent during bring-up must appear
> in at least one of these before the node is declared brought up.

### §3.1 Raspberry Pi (CAN core)

- [ ] `ip link show can0` reports the interface UP at 500 kbit/s.
- [ ] `candump can0` starts and shows no error frames at idle (no bus-off, no
      passive-error spam).
- [ ] A test frame sent from any MCU appears in `candump` with the correct ID
      and data bytes (manual spot-check against protocol-spec §7.7).
- [ ] `python-can` and `python-can-isotp` import without error on the Pi's Python
      environment.
- [ ] SQLite opens in WAL mode; `PRAGMA journal_mode;` returns `wal`.

### §3.2 MCU #1 — Operator Console

- [ ] Firmware boots without panic; serial monitor shows no crash log.
- [ ] OLED lights up and displays a static "CONSOLE BOOT" splash (or equivalent).
- [ ] MCU transmits at least one HEARTBEAT frame (`ID=0x000`, 6 bytes,
      `source=1`) visible on `candump`.

### §3.3 MCU #2 — Transaction Terminal

- [ ] Firmware boots without panic.
- [ ] OLED displays a static boot splash.
- [ ] PCF8574 I²C expander acknowledged (I²C scan shows its address); keypad
      registers at least one key-press event in the serial monitor.
- [ ] KY-040 encoder rotation registered in the serial monitor.
- [ ] MCU transmits at least one HEARTBEAT frame (`ID=0x000`, `source=2`)
      visible on `candump`.

### §3.4 MCU #4 — Job Submitter

- [ ] Firmware boots without panic.
- [ ] OLED displays a static boot splash.
- [ ] Button press registered in the serial monitor.
- [ ] MCU transmits at least one HEARTBEAT frame (`ID=0x000`, `source=4`)
      visible on `candump`.

### §3.5 MCU #5 — Output Writer

- [ ] Firmware boots without panic.
- [ ] OLED displays a static boot splash.
- [ ] MCU transmits at least one HEARTBEAT frame (`ID=0x000`, `source=5`)
      visible on `candump`.

---

## §4 Per-feature DoD

Dependencies: §3 bring-up DoD for all involved nodes must pass first.

### §4.1 Heartbeat & liveness (MCUs + Pi + Console #1)

- [ ] All four MCUs emit a HEARTBEAT frame every ~1 s (cadence provisional —
      protocol-spec §6). Confirmed by `candump` timestamps over a 10 s window.
- [ ] Each HEARTBEAT payload decodes correctly: `type|version=0x10`,
      `source` matches the emitting node, `uptime` increments between frames.
- [ ] The Pi's liveness tracker registers each node as alive within 2 s of
      first heartbeat received.
- [ ] Console #1 OLED shows a live/dead status for each of the four MCU nodes.
- [ ] Powering off one MCU: Console #1 marks it dead within the liveness timeout
      (provisionally 3 s — protocol-spec §6). No other node's status is affected.
- [ ] Powering the MCU back on: Console #1 marks it alive again within 2 s of
      the first heartbeat received.

### §4.2 Transaction path — TXN_REQUEST / TXN_RESULT (#2 ↔ Pi)

#### §4.2.1 DEPOSIT

- [ ] Operator enters an 8-digit account number and an amount on keypad #2,
      selects DEPOSIT via the encoder, and confirms.
- [ ] A `TXN_REQUEST` ISO-TP frame (`type=0x30`) appears on `candump` on channel
      `(0x250, 0x240)` with correct `tag`, `txn_type=0x1`, account, and
      amount (in cents).
- [ ] Pi's CICS router receives the reassembled payload, routes to the
      transaction processor, and the processor writes the transaction to SQLite
      (PENDING → balance update → COMMITTED, one atomic SQLite transaction).
- [ ] Pi sends a `TXN_RESULT` ISO-TP frame (`type=0x40`) on `(0x240, 0x250)`
      with `status=0x0` (SUCCESS), mirrored `tag`, and the new balance.
- [ ] Terminal #2 displays the success result and new balance on its OLED.
- [ ] The COMMITTED row is present in the `transactions` table with correct
      `account_id`, `txn_type`, `amount`, `new_bal`, and `status=COMMITTED`.

#### §4.2.2 WITHDRAW — success path

- [ ] Same flow as DEPOSIT with `txn_type=0x2`. Balance decreases by the
      withdrawn amount in the database.

#### §4.2.3 WITHDRAW — insufficient funds

- [ ] Withdraw request where `amount > current balance` results in a
      `TXN_RESULT` with `status=0x1` (FAILED), `reason=0x1`
      (INSUFFICIENT_FUNDS).
- [ ] Terminal #2 displays the rejection (e.g. "INSUFFICIENT FUNDS") on its
      OLED.
- [ ] Database balance is unchanged; no COMMITTED row is written for this
      attempt.

#### §4.2.4 BALANCE

- [ ] Balance query (`txn_type=0x3`, `amount=0`) returns a `TXN_RESULT` with
      `status=0x0` and the correct current balance in the `balance` field.
- [ ] Terminal #2 displays the balance on its OLED.
- [ ] No write to the `accounts` or `transactions` table occurs.

#### §4.2.5 Transaction timeout

- [ ] Terminal #2, after sending a `TXN_REQUEST` with no Pi response, exits
      `WAITING_FOR_RESULT` after the txn timeout (provisionally 2 s —
      protocol-spec §6) and displays a timeout error on its OLED.
- [ ] A `TIMEOUT` ERROR frame (`class=1`, `subcode=0x1`) appears on `candump`.

### §4.3 Journal path (Pi → Output Writer #5)

- [ ] After each transaction result — SUCCESS **or** FAILED — the Pi sends a
      `JOURNAL` ISO-TP frame (`type=0x80`) on `(0x4A0, 0x4B0)`. FAILED results
      include the failure reason (e.g. "INSUFFICIENT FUNDS") in the journal
      lines, sourced from the `reason` byte of `TXN_RESULT` / `JOB_COMPLETE`
      (protocol-spec §7.7).
- [ ] The frame payload decodes correctly: 1 discriminator byte + 4 × 21-byte
      ASCII lines, space-padded.
- [ ] Output Writer #5 renders all four lines to the correct OLED rows
      (line0 → row 0, …, line3 → row 3).
- [ ] The OLED content reflects the transaction just completed (e.g. account,
      type, result, balance).

### §4.4 Job path — JOB_SUBMIT / JOB_ACCEPT / JOB_COMPLETE (#4 ↔ Pi)

- [ ] Pressing the button on Job Submitter #4 sends a `JOB_SUBMIT` ISO-TP frame
      (`type=0x50`) on `(0x390, 0x380)` with the hardcoded payload (fixed
      account, fixed amount, fixed `txn_type`).
- [ ] Pi's JES process receives the frame, assigns a `jobId`, and sends a
      `JOB_ACCEPT` frame (`type=0x60`) on `(0x380, 0x390)` with
      `status=0x0` (ACCEPTED) and the assigned `jobId`.
- [ ] #4 displays "JOB ACCEPTED, id=N" (or equivalent) on its OLED.
- [ ] JES dispatches the job to the transaction processor; the transaction is
      executed and committed to SQLite.
- [ ] Pi sends a `JOB_COMPLETE` frame (`type=0x70`) on `(0x380, 0x390)` with
      the `jobId`, `status=0x0` (SUCCESS), and (if BALANCE) the balance.
- [ ] #4 displays the completion result on its OLED.

### §4.5 Durability (clean reboot)

- [ ] Execute at least one DEPOSIT that reaches COMMITTED in the database.
- [ ] Power-cycle the Pi cleanly (graceful shutdown, not a pull).
- [ ] After reboot, the `transactions` row is present with `status=COMMITTED`
      and the `accounts` balance matches.
- [ ] No PENDING rows remain from the completed transaction.

*Note: this DoD covers the narrow Phase 1 boundary (Q1). A mid-write crash that
leaves a PENDING row is flagged — not auto-recovered — until Phase 2+.*

---

## §5 System DoD

The complete end-to-end flow. All §3 bring-up DoDs and all §4 per-feature DoDs
must pass before this is attempted.

- [ ] **Full deposit flow:** operator enters account + amount at #2, confirms →
      result displayed on #2 → journal line on #5 OLED → COMMITTED row in
      SQLite → all four MCUs remain "alive" on Console #1 throughout.
- [ ] **Full withdrawal flow (success):** same as deposit; balance decreases.
- [ ] **Insufficient funds:** rejection displayed on #2; no balance change;
      JOURNAL frame sent to #5 with the failure reason visible on the OLED.
- [ ] **Balance query:** balance displayed on #2; no write to DB; JOURNAL frame
      sent to #5 showing the queried balance.
- [ ] **Canned job:** button on #4 → DEPOSIT committed to SQLite → completion
      on #4 OLED.
- [ ] **Reboot durability:** one of the above deposit flows survives a clean
      Pi power-cycle (per §4.5).
- [ ] **Liveness under load:** Console #1 continues updating liveness correctly
      while a transaction is in progress (heartbeat is not starved by the data
      plane — class 0 priority, protocol-spec §4).
- [ ] **Error visibility:** one deliberately triggered TIMEOUT (e.g. Pi process
      stopped) produces an ERROR frame visible on `candump`.

---

## §6 Deferred to Phase 2 (not in Phase 1 scope)

Listed so nothing is silently dropped.

| Item | Reason deferred |
|---|---|
| Crash-recovery replay of PENDING rows | Phase 2+ (system-design §7; Q1 answer) |
| Operator dashboard (web, on Pi) | Phase 2 (system-design §7) |
| Transaction web form on #2 | Phase 2 |
| Transaction generator on #4 + Pi-side injector | Phase 2 |
| Throughput / loss measurement | Phase 2 |
| CSN-A2 thermal printer on #5 | Phase 2+ (BOM §4) |
| Richer Console panel (more buttons/LEDs, PCF8574) | Phase 2+ (BOM §4) |
| RFID "card" job submission on #4 | Phase 2+ (BOM §4) |
| JOURNAL version bump to 0x81 (32-byte lines for printer) | Phase 2+ (protocol-spec §7.7) |
| Docker-per-subsystem isolation | Phase 2+ (ADR-0001 alternatives) |
| GnuCOBOL transaction processor | Phase 2+ (ADR-0001 alternatives) |
| `bring-up-checklist.md` | Deferred until hardware arrives (~end of week) |

---

## §7 Resolved questions

**OQ-1 — JOURNAL on FAILED transactions? → DECIDED: journal all results.**
The Pi sends a `JOURNAL` frame to #5 for every transaction result, SUCCESS or
FAILED. FAILED results include the failure reason from the `reason` byte of
`TXN_RESULT` / `JOB_COMPLETE`. Reflected in §4.3 and §5.

**OQ-2 — `bring-up-checklist.md` timing? → DECIDED: draft now, fill at bring-up.**
`bring-up-checklist.md` created as a template (hardware arrives ~end of week
2026-06-28). Sections: bus wiring, transceivers, Pi HAT, PCF8574, ESP-IDF /
`esp_isotp`, bench power, timeout measurements.
