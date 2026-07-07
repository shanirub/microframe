"""Durable storage — SQLite in WAL mode, local to the Pi (T-P1).

Implements the write-ahead pattern from system-design §5:

    insert row PENDING  ->  update balance  ->  mark row COMMITTED

...all inside one atomic SQLite transaction. On a clean commit the row is
COMMITTED and the balance is updated together, so a completed transaction
survives a reboot (requirements R-SYS-02, §4.5 — narrow Phase 1 boundary: a
completed txn persists; mid-write crash replay is Phase 2+).

Money is integer cents everywhere (ADR-0001 decision 4). Never float.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    balance    INTEGER NOT NULL          -- cents, never float
);

CREATE TABLE IF NOT EXISTS transactions (
    id         TEXT PRIMARY KEY,         -- UUID (str)
    account_id TEXT NOT NULL,
    txn_type   TEXT NOT NULL,            -- DEPOSIT | WITHDRAW | BALANCE
    amount     INTEGER NOT NULL,         -- cents
    new_bal    INTEGER,                  -- cents, NULL until known
    status     TEXT NOT NULL,            -- PENDING | COMMITTED
    ts         TEXT NOT NULL             -- ISO-8601
);
"""


class TxnType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    BALANCE = "BALANCE"


class TxnStatus(str, Enum):
    PENDING = "PENDING"
    COMMITTED = "COMMITTED"


class InsufficientFunds(Exception):
    """A withdraw for more than the balance.

    NOTE: this is a business *result*, not a system error (protocol-spec §7.4,
    learning-log 2026-06-27). The processor turns it into a FAILED TXN_RESULT
    with reason INSUFFICIENT_FUNDS — it must never be raised onto the ERROR
    channel. Defined here only so the storage layer can signal the caller.
    """


@dataclass(frozen=True)
class TxnResult:
    txn_id: str
    account_id: str
    txn_type: TxnType
    amount: int
    new_balance: int
    status: TxnStatus


class Storage:
    """Owns the SQLite connection. Single writer (system-design §5)."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._conn.executescript(SCHEMA)

    def _configure(self) -> None:
        # WAL: readers don't block the single writer (system-design §5).
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")

    def journal_mode(self) -> str:
        row = self._conn.execute("PRAGMA journal_mode;").fetchone()
        return str(row[0])

    def get_balance(self, account_id: str) -> int | None:
        row = self._conn.execute(
            "SELECT balance FROM accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        return None if row is None else int(row["balance"])

    def ensure_account(self, account_id: str, opening_balance: int = 0) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO accounts(account_id, balance) VALUES (?, ?)",
            (account_id, opening_balance),
        )

    def apply_transaction(
        self,
        *,
        txn_id: str,
        account_id: str,
        txn_type: TxnType,
        amount: int,
        ts: str,
    ) -> TxnResult:
        """Apply one deposit/withdraw atomically via the write-ahead pattern.

        BALANCE is read-only and never writes (requirements §4.2.4) — callers
        should use `get_balance` instead; it is rejected here to keep the write
        path honest.
        """
        if txn_type is TxnType.BALANCE:
            raise ValueError("BALANCE is read-only; use get_balance(), not apply_transaction()")
        if amount < 0:
            raise ValueError("amount must be non-negative (cents)")

        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE;")  # take the write lock up front

            current = self.get_balance(account_id)
            if current is None:
                # Phase 1: unknown account is created on first touch with 0 balance.
                # (Revisit if requirements later demand NOT_FOUND on deposit.)
                cur.execute(
                    "INSERT INTO accounts(account_id, balance) VALUES (?, 0)",
                    (account_id,),
                )
                current = 0

            # 1) insert PENDING
            cur.execute(
                "INSERT INTO transactions(id, account_id, txn_type, amount, new_bal, status, ts) "
                "VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (txn_id, account_id, txn_type.value, amount, TxnStatus.PENDING.value, ts),
            )

            # compute new balance
            if txn_type is TxnType.DEPOSIT:
                new_bal = current + amount
            else:  # WITHDRAW
                if amount > current:
                    raise InsufficientFunds(account_id)
                new_bal = current - amount

            # 2) update balance
            cur.execute(
                "UPDATE accounts SET balance = ? WHERE account_id = ?",
                (new_bal, account_id),
            )
            # 3) mark COMMITTED
            cur.execute(
                "UPDATE transactions SET new_bal = ?, status = ? WHERE id = ?",
                (new_bal, TxnStatus.COMMITTED.value, txn_id),
            )

            cur.execute("COMMIT;")
        except Exception:
            cur.execute("ROLLBACK;")
            raise

        return TxnResult(
            txn_id=txn_id,
            account_id=account_id,
            txn_type=txn_type,
            amount=amount,
            new_balance=new_bal,
            status=TxnStatus.COMMITTED,
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
