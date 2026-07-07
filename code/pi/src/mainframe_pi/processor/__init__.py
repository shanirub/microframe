"""Transaction processor (T-P3, roadmap M3).

Applies DEPOSIT/WITHDRAW/BALANCE against storage. INSUFFICIENT_FUNDS is a
business result (FAILED TXN_RESULT), never an ERROR frame (protocol §7.4).
"""
