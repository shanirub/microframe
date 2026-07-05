> # ⚠️ RETIRED — DO NOT USE AS A LIVE SPEC
>
> This document describes the **retired shared-bus / I2C architecture** (ADR-012).
> It is kept **read-only, as a traceability artifact only**: `protocol-spec.md`
> §7.0 maps each message type here onto the current CAN + ISO-TP design.
> For the live contract, see `protocol-spec.md`. Nothing here reflects the
> current system (no I2C addressing, no MCU↔MCU hops, no JSON envelope).

# Message Protocol — Inter-MCU Communication

## Envelope (all messages)

Every message shares this base structure:

```json
{
  "msgId": 1,
  "from":  8,
  "to":    9,
  "type":  "JOB_SUBMIT",
  "payload": { }
}
```

| Field | Type | Description |
|-------|------|-------------|
| msgId | uint16 | Unique ID, incremented per sender |
| from | uint8 | Sender I2C address (decimal: 8–12) |
| to | uint8 | Recipient I2C address, or 0 for broadcast |
| type | string | Message type — see below |
| payload | object | Type-specific data |

**Note on money:** All `amount` and `balance` fields are integer cents (uint32_t).
$100.00 = 10000. Never use float for money.

---

---

## Message Types

### JOB_SUBMIT
**Direction:** MCU #5 → MCU #4

```json
{
  "msgId": 1, "from": 12, "to": 11, "type": "JOB_SUBMIT",
  "payload": {
    "txnType":  "DEPOSIT",
    "account":  "12345678",
    "amount":   10000,
    "priority": "MEDIUM"
  }
}
```

| txnType | Values | Priority default |
|---------|--------|-----------------|
| DEPOSIT | — | MEDIUM |
| WITHDRAW | — | MEDIUM |
| TRANSFER | requires srcAccount + dstAccount | HIGH |
| BALANCE | read-only, no amount needed | LOW |

**Done when:** MCU #4 receives, assigns jobId, adds to queue, confirms serial.

---

### JOB_DISPATCH
**Direction:** MCU #4 → MCU #2

```json
{
  "msgId": 2, "from": 11, "to": 9, "type": "JOB_DISPATCH",
  "payload": {
    "jobId":    1,
    "txnType":  "DEPOSIT",
    "account":  "12345678",
    "amount":   10000
  }
}
```

**Done when:** MCU #2 receives, begins processing, MCU #4 marks job DISPATCHED.

---

### JOB_COMPLETE
**Direction:** MCU #2 → MCU #4

```json
{
  "msgId": 3, "from": 9, "to": 11, "type": "JOB_COMPLETE",
  "payload": {
    "jobId":   1,
    "status":  "SUCCESS",
    "reason":  "",
    "balance": 100000
  }
}
```

`balance` field only present when txnType was BALANCE. In cents. Omitted for
DEPOSIT/WITHDRAW/TRANSFER.

| status | reason |
|--------|--------|
| SUCCESS | empty |
| FAILED | INSUFFICIENT_FUNDS / DB_ERROR / TIMEOUT |

**Done when:** MCU #4 receives, removes job from queue, updates OLED.

---

### JOB_RESULT
**Direction:** MCU #4 → MCU #5

```json
{
  "msgId": 4, "from": 11, "to": 12, "type": "JOB_RESULT",
  "payload": {
    "jobId":  1,
    "status": "SUCCESS",
    "reason": ""
  }
}
```

**Done when:** MCU #5 receives, displays result on OLED, logs to MCU #1.

---

### DB_READ
**Direction:** MCU #2 → MCU #3

```json
{
  "msgId": 5, "from": 9, "to": 10, "type": "DB_READ",
  "payload": {
    "account": "12345678"
  }
}
```

---

### DB_READ_RESULT
**Direction:** MCU #3 → MCU #2

```json
{
  "msgId": 6, "from": 10, "to": 9, "type": "DB_READ_RESULT",
  "payload": {
    "account": "12345678",
    "balance": 100000,
    "status":  "OK"
  }
}
```

| status | meaning |
|--------|---------|
| OK | account found, balance valid |
| NOT_FOUND | account does not exist |
| ERROR | SD card read failure |

---

### DB_WRITE
**Direction:** MCU #2 → MCU #3

```json
{
  "msgId": 7, "from": 9, "to": 10, "type": "DB_WRITE",
  "payload": {
    "account":    "12345678",
    "newBalance": 110000,
    "txnType":    "DEPOSIT",
    "amount":     10000
  }
}
```

---

### DB_WRITE_ACK
**Direction:** MCU #3 → MCU #2

```json
{
  "msgId": 8, "from": 10, "to": 9, "type": "DB_WRITE_ACK",
  "payload": {
    "account": "12345678",
    "status":  "OK"
  }
}
```

| status | meaning |
|--------|---------|
| OK | write successful, log updated |
| ERROR | SD card write failure |

---

### HEARTBEAT
**Direction:** MCU #1 → all (broadcast, to: 0)

```json
{
  "msgId": 9, "from": 8, "to": 0, "type": "HEARTBEAT",
  "payload": {
    "ts": 1234567890
  }
}
```

---

### HEARTBEAT_ACK
**Direction:** any → MCU #1

```json
{
  "msgId": 10, "from": 9, "to": 8, "type": "HEARTBEAT_ACK",
  "payload": {
    "status": "OK",
    "uptime": 3600
  }
}
```

---

### ERROR
**Direction:** any → any (usually → MCU #1)

```json
{
  "msgId": 11, "from": 9, "to": 8, "type": "ERROR",
  "payload": {
    "code":    "TIMEOUT",
    "detail":  "No response from 0x0A after 500ms"
  }
}
```

| code | meaning |
|------|---------|
| TIMEOUT | no response within 500ms |
| PARSE_ERROR | received malformed JSON |
| BUS_ERROR | I2C transmission failed |
| QUEUE_FULL | MCU #4 job queue at capacity |

---

## Message Size Reference

| Type | Approx size |
|------|-------------|
| JOB_SUBMIT | ~110 bytes |
| JOB_DISPATCH | ~100 bytes |
| JOB_COMPLETE | ~80 bytes |
| DB_READ | ~70 bytes |
| DB_READ_RESULT | ~90 bytes |
| DB_WRITE | ~110 bytes |
| DB_WRITE_ACK | ~75 bytes |
| HEARTBEAT | ~65 bytes |
| HEARTBEAT_ACK | ~75 bytes |
| ERROR | ~90 bytes |

All within 256 byte limit. ✅
