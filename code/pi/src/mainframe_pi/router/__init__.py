"""CICS-analogue router (T-P2, roadmap M3).

Receives ISO-TP payloads on the transaction channel, decodes the type nibble
(protocol §7.1), and routes to the right subsystem over local IPC.

DESIGN NOTE (ISO-TP verification, 2026-07-01): use isotp.NotifierBasedCanStack,
NOT CanStack. CanStack calls bus.recv and drains the RX queue, which would starve
the liveness reader sharing can0. NotifierBasedCanStack fans frames out via a
can.Notifier so both the ISO-TP layer and the liveness tracker see traffic.
Transport errors arrive via an async error_handler callback on ANOTHER thread —
marshal them to the main loop before emitting an ERROR frame (protocol §7.4).
"""
