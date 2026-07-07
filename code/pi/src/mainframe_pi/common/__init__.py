"""Shared constants for the Pi subsystems.

Values here are the single source of truth on the Pi side for things fixed by the
protocol spec and the bring-up decisions. Where a value is provisional, it is
marked and cross-referenced so it gets replaced with a measured value later
(bring-up-checklist §7).
"""

from __future__ import annotations

from enum import IntEnum

# --- CAN bus (bring-up-checklist §2.5 / §3.5) --------------------------------
CAN_INTERFACE = "can0"
# Bring-up speed. Middle-node VP230s keep their fixed 120R, lowering bus
# impedance, so bring-up runs at 125k for margin. 500k is a stretch goal once the
# bus is proven stable (checklist 2.5). Keep in sync with the `ip link` bitrate.
CAN_BITRATE_BRINGUP = 125_000
CAN_BITRATE_TARGET = 500_000


class NodeId(IntEnum):
    """Node IDs as they appear in the HEARTBEAT `source` byte (protocol-spec §7).

    The Pi is the central complex; #1/#2/#4/#5 are the channel MCUs. (#3 does not
    exist in this architecture — it was the retired DB controller.)
    """

    PI = 0
    CONSOLE = 1  # #1 Operator Console
    TERMINAL = 2  # #2 Transaction Terminal
    JOB_SUBMITTER = 4  # #4 Job Submitter
    OUTPUT_WRITER = 5  # #5 Output Writer


# --- Provisional timeouts (protocol-spec §6) --------------------------------
# PROVISIONAL — measure at bring-up and replace (bring-up-checklist §7).
# Do not treat these as final.
HEARTBEAT_CADENCE_S = 1.0  # provisional
LIVENESS_TIMEOUT_S = 3.0   # provisional (target: 3x measured cadence)
TXN_TIMEOUT_S = 2.0        # provisional (target: >=3x measured round-trip)
