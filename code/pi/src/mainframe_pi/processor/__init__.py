"""Transaction processor (T-P3) — applies DEPOSIT / WITHDRAW / BALANCE.

Position (ADR-0002): the router decodes a CAN/ISO-TP frame into a *logical*
request and hands it here over local IPC; this module computes a *logical*
result and hands it back; the router encodes that into a TXN_RESULT (§7.7) and
transmits it. So this module never imports `protocol` and never touches a byte
offset — it speaks domain terms only.

Two exception types from `storage` are business *results*, not errors
(protocol-spec §7.4): InsufficientFunds -> FAILED/INSUFFICIENT_FUNDS, and
AccountNotFound -> FAILED/NOT_FOUND. They are caught here and returned as a
TxnOutcome, never propagated onto the ERROR channel. A genuinely malformed
request (e.g. a negative amount) raises out of `handle()` for the caller to map
to an ERROR frame — that is the §7.4 line between a business "no" and a fault.

UUID minting (2026-07-10 decision): the txn_id is minted here, at apply time.
Correct for Phase 1 (request/response, no dedup). If a lost result is retried,
the resend would mint a new id and double-apply; the Phase-2 upgrade is to pin
the id at ingress, keyed by the correlation tag. Recorded so it stays a
conscious deferral, not an accident.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

from mainframe_pi.storage import (
    AccountNotFound,
    InsufficientFunds,
    Storage,
    TxnType,
)


class Status(IntEnum):
    """Result status. Logical codes; the router maps these to the §7.7 status byte."""

    SUCCESS = 0x0
    FAILED = 0x1


class Reason(IntEnum):
    """Why a result FAILED (NONE on success). Router maps these to the §7.7 reason byte."""

    NONE = 0x0
    INSUFFICIENT_FUNDS = 0x1
    NOT_FOUND = 0x2


@dataclass(frozen=True)
class TxnRequest:
    """A decoded transaction request — the logical IPC message, not wire bytes.

    `tag` is the uint16 correlation tag, carried through untouched so the result
    can echo it (the router matches result -> request by it). `amount_cents` is
    ignored for BALANCE.
    """

    tag: int
    txn_type: TxnType
    account_id: str
    amount_cents: int = 0


@dataclass(frozen=True)
class TxnOutcome:
    """The logical result the router will encode into a TXN_RESULT.

    `balance_cents` is populated only for a BALANCE query — that is the one
    operation whose *result* is a balance; a write's result is its success or
    failure. (This matches the §7.7 rule that balance is a BALANCE-only field,
    but the reason here is domain, not wire.)
    """

    tag: int
    status: Status
    reason: Reason
    balance_cents: int = 0


class Processor:
    """Applies transactions against durable storage. One storage handle, single writer."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def handle(self, req: TxnRequest) -> TxnOutcome:
        """Apply one request and return its logical result.

        A business "no" (insufficient funds, unknown account) comes back as a
        FAILED TxnOutcome. A malformed request raises — the caller maps that to
        an ERROR frame.
        """
        if req.txn_type is TxnType.BALANCE:
            balance = self._storage.get_balance(req.account_id)
            if balance is None:
                return TxnOutcome(req.tag, Status.FAILED, Reason.NOT_FOUND)
            return TxnOutcome(req.tag, Status.SUCCESS, Reason.NONE, balance_cents=balance)

        # DEPOSIT / WITHDRAW — a durable write.
        try:
            self._storage.apply_transaction(
                txn_id=str(uuid.uuid4()),
                account_id=req.account_id,
                txn_type=req.txn_type,
                amount=req.amount_cents,
                ts=datetime.now(timezone.utc).isoformat(),
            )
        except InsufficientFunds:
            return TxnOutcome(req.tag, Status.FAILED, Reason.INSUFFICIENT_FUNDS)
        except AccountNotFound:
            return TxnOutcome(req.tag, Status.FAILED, Reason.NOT_FOUND)
        return TxnOutcome(req.tag, Status.SUCCESS, Reason.NONE)
