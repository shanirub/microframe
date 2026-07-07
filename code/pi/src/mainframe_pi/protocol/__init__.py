"""Wire codec — encode/decode the CAN payloads defined in protocol-spec §7.

DELIBERATE STUB. The exact byte maps (leading type|version byte, little-endian
fields, per-type layouts) are specified in protocol-spec §7.7 and are built in
T-P2 / M3, not at scaffolding time. Filling these in now would mean guessing byte
offsets — against the verify-don't-assume rule. The interface is here so the
router/processor can import against a stable shape; the bodies raise until
implemented.

Do NOT invent field layouts here — copy them from protocol-spec §7.7.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecodedMessage:
    """Placeholder for a decoded app-layer message.

    Real fields (type nibble, version, tag, per-type payload) come from
    protocol-spec §7. Left minimal on purpose.
    """

    type_nibble: int
    version: int
    payload: bytes


def decode(data: bytes) -> DecodedMessage:  # noqa: ARG001
    """Decode a reassembled payload's leading discriminator + body (spec §7.1)."""
    raise NotImplementedError("protocol codec is built in T-P2/M3 — see protocol-spec §7.7")


def encode(msg: DecodedMessage) -> bytes:  # noqa: ARG001
    """Encode an app-layer message to its on-the-wire bytes (spec §7.7)."""
    raise NotImplementedError("protocol codec is built in T-P2/M3 — see protocol-spec §7.7")
