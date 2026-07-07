"""Liveness tracker (T-P2.4, roadmap M2).

Tracks per-node HEARTBEAT frames; flags a node dead after LIVENESS_TIMEOUT_S.
Shares can0 with the ISO-TP stack — must read via the shared can.Notifier, not a
competing bus.recv loop (see router design note).
"""
