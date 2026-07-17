"""Tests for the transaction processor (T-P3).

Pure logic over storage — no hardware, no IPC transport. Proves the
DEPOSIT / WITHDRAW / BALANCE branch, that a business "no" comes back as a FAILED
result (never raised), strict NOT_FOUND on unknown accounts, that the
correlation tag is echoed, and that a malformed request raises instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mainframe_pi.processor import Processor, Reason, Status, TxnRequest
from mainframe_pi.storage import Storage, TxnType


def _proc(tmp_path: Path) -> Processor:
    return Processor(Storage(tmp_path / "proc.db"))


def test_deposit_success_opens_account(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    out = p.handle(
        TxnRequest(
            tag=1, txn_type=TxnType.DEPOSIT, account_id="a", txn_id="t1", amount_cents=5_000
        )
    )
    assert out.status is Status.SUCCESS
    assert out.reason is Reason.NONE
    assert out.tag == 1


def test_balance_returns_current_balance(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    p.handle(
        TxnRequest(tag=1, txn_type=TxnType.DEPOSIT, account_id="a", txn_id="t1", amount_cents=5_000)
    )
    out = p.handle(TxnRequest(tag=2, txn_type=TxnType.BALANCE, account_id="a", txn_id="t2"))
    assert out.status is Status.SUCCESS
    assert out.balance_cents == 5_000
    assert out.tag == 2


def test_withdraw_within_funds_applies(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    p.handle(
        TxnRequest(tag=1, txn_type=TxnType.DEPOSIT, account_id="a", txn_id="t1", amount_cents=5_000)
    )
    out = p.handle(
        TxnRequest(
            tag=2, txn_type=TxnType.WITHDRAW, account_id="a", txn_id="t2", amount_cents=2_000
        )
    )
    assert out.status is Status.SUCCESS
    # confirm it actually applied
    bal = p.handle(TxnRequest(tag=3, txn_type=TxnType.BALANCE, account_id="a", txn_id="t3"))
    assert bal.balance_cents == 3_000


def test_insufficient_funds_is_a_failed_result_not_an_exception(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    p.handle(
        TxnRequest(tag=1, txn_type=TxnType.DEPOSIT, account_id="a", txn_id="t1", amount_cents=1_000)
    )
    out = p.handle(
        TxnRequest(
            tag=2, txn_type=TxnType.WITHDRAW, account_id="a", txn_id="t2", amount_cents=5_000
        )
    )
    assert out.status is Status.FAILED
    assert out.reason is Reason.INSUFFICIENT_FUNDS
    # balance untouched
    bal = p.handle(TxnRequest(tag=3, txn_type=TxnType.BALANCE, account_id="a", txn_id="t3"))
    assert bal.balance_cents == 1_000


def test_withdraw_unknown_account_is_not_found(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    out = p.handle(
        TxnRequest(
            tag=7, txn_type=TxnType.WITHDRAW, account_id="ghost", txn_id="t7", amount_cents=100
        )
    )
    assert out.status is Status.FAILED
    assert out.reason is Reason.NOT_FOUND
    assert out.tag == 7


def test_balance_unknown_account_is_not_found(tmp_path: Path) -> None:
    p = _proc(tmp_path)
    out = p.handle(TxnRequest(tag=9, txn_type=TxnType.BALANCE, account_id="ghost", txn_id="t9"))
    assert out.status is Status.FAILED
    assert out.reason is Reason.NOT_FOUND


def test_malformed_negative_amount_raises(tmp_path: Path) -> None:
    """A malformed request is a fault, not a business result — it raises for the
    router to map to an ERROR frame (protocol-spec §7.4)."""
    p = _proc(tmp_path)
    p.handle(
        TxnRequest(tag=1, txn_type=TxnType.DEPOSIT, account_id="a", txn_id="t1", amount_cents=1_000)
    )
    with pytest.raises(ValueError):
        p.handle(
            TxnRequest(
                tag=2, txn_type=TxnType.WITHDRAW, account_id="a", txn_id="t2", amount_cents=-5
            )
        )