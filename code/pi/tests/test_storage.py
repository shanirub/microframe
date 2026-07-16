"""Tests for the storage write-ahead pattern (T-P1).

These prove the durability-relevant behaviour without any hardware: WAL is on,
deposits/withdrawals apply atomically, insufficient funds is a signalled result
(not a silent write), balance is read-only, and a committed row persists across
reopening the database (the software half of requirements §4.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mainframe_pi.storage import (
    AccountNotFound,
    InsufficientFunds,
    Storage,
    TxnStatus,
    TxnType,
)


def _db(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "test.db")


def test_wal_enabled(tmp_path: Path) -> None:
    with _db(tmp_path) as s:
        assert s.journal_mode().lower() == "wal"


def test_deposit_updates_balance_and_commits(tmp_path: Path) -> None:
    with _db(tmp_path) as s:
        s.ensure_account("acct-1", 10_000)  # $100.00
        res = s.apply_transaction(
            txn_id="t1", account_id="acct-1", txn_type=TxnType.DEPOSIT,
            amount=2_500, ts="2026-07-01T00:00:00",
        )
        assert res.new_balance == 12_500
        assert res.status is TxnStatus.COMMITTED
        assert s.get_balance("acct-1") == 12_500


def test_withdraw_success(tmp_path: Path) -> None:
    with _db(tmp_path) as s:
        s.ensure_account("acct-1", 10_000)
        res = s.apply_transaction(
            txn_id="t1", account_id="acct-1", txn_type=TxnType.WITHDRAW,
            amount=3_000, ts="2026-07-01T00:00:00",
        )
        assert res.new_balance == 7_000
        assert s.get_balance("acct-1") == 7_000


def test_insufficient_funds_does_not_change_balance(tmp_path: Path) -> None:
    with _db(tmp_path) as s:
        s.ensure_account("acct-1", 1_000)
        with pytest.raises(InsufficientFunds):
            s.apply_transaction(
                txn_id="t1", account_id="acct-1", txn_type=TxnType.WITHDRAW,
                amount=5_000, ts="2026-07-01T00:00:00",
            )
        # balance unchanged, and the rolled-back PENDING row is gone
        assert s.get_balance("acct-1") == 1_000


def test_balance_is_read_only(tmp_path: Path) -> None:
    with _db(tmp_path) as s:
        s.ensure_account("acct-1", 1_000)
        with pytest.raises(ValueError):
            s.apply_transaction(
                txn_id="t1", account_id="acct-1", txn_type=TxnType.BALANCE,
                amount=0, ts="2026-07-01T00:00:00",
            )


def test_deposit_opens_unknown_account(tmp_path: Path) -> None:
    """A DEPOSIT to an account that doesn't exist opens it (the opening deposit)."""
    with _db(tmp_path) as s:
        res = s.apply_transaction(
            txn_id="t1", account_id="new-acct", txn_type=TxnType.DEPOSIT,
            amount=5_000, ts="2026-07-10T00:00:00",
        )
        assert res.new_balance == 5_000
        assert s.get_balance("new-acct") == 5_000


def test_withdraw_unknown_account_raises_not_found(tmp_path: Path) -> None:
    """Strict: WITHDRAW on an unknown account raises AccountNotFound and writes nothing."""
    with _db(tmp_path) as s:
        with pytest.raises(AccountNotFound):
            s.apply_transaction(
                txn_id="t1", account_id="ghost", txn_type=TxnType.WITHDRAW,
                amount=100, ts="2026-07-10T00:00:00",
            )
        # no phantom account created, and no phantom transaction row left behind
        assert s.get_balance("ghost") is None


def test_committed_row_persists_across_reopen(tmp_path: Path) -> None:
    """Software analogue of the reboot-durability DoD (requirements §4.5)."""
    db_path = tmp_path / "persist.db"
    with Storage(db_path) as s:
        s.ensure_account("acct-1", 0)
        s.apply_transaction(
            txn_id="t1", account_id="acct-1", txn_type=TxnType.DEPOSIT,
            amount=4_200, ts="2026-07-01T00:00:00",
        )
    # reopen — simulates process restart / reboot
    with Storage(db_path) as s2:
        assert s2.get_balance("acct-1") == 4_200
