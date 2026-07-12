#!/usr/bin/env python3
"""
verify_socketcan_fanout.py

Confirms the kernel property ADR-0003 (option B1) relies on:
    two sockets bound to the SAME CAN interface each receive a copy of every frame.

This is a SocketCAN *kernel* behaviour, independent of the MCP2515 hardware, so it
is valid to prove it on a virtual CAN interface (vcan0). It does NOT replace the
physical bring-up checks (bitrate, transceiver, HAT) — those stay separate.

--------------------------------------------------------------------------------
Setup on a virtual interface (no hardware needed):

    sudo modprobe vcan
    sudo ip link add dev vcan0 type vcan
    sudo ip link set up vcan0
    python3 verify_socketcan_fanout.py vcan0

Or point it at the real Pi interface. NOTE: this script also *sends* test frames,
so only aim it at can0 if you intend to put a little traffic on the live bus:

    python3 verify_socketcan_fanout.py can0

Requires: python-can >= 4.3   ->   pip install 'python-can>=4.3'
Exit code 0 = PASS, 1 = FAIL / setup problem.
--------------------------------------------------------------------------------
"""
import sys
import time

try:
    import can  # python-can
except ImportError:
    print("FAIL — python-can is not installed. Try: pip install 'python-can>=4.3'")
    sys.exit(1)

CHANNEL = sys.argv[1] if len(sys.argv) > 1 else "vcan0"
N = 10            # frames to send
TEST_ID = 0x123   # arbitration id used for the probe frames


def main() -> int:
    try:
        # Two INDEPENDENT receivers bound to the same interface, plus a sender.
        rx_a = can.Bus(interface="socketcan", channel=CHANNEL, receive_own_messages=False)
        rx_b = can.Bus(interface="socketcan", channel=CHANNEL, receive_own_messages=False)
        tx = can.Bus(interface="socketcan", channel=CHANNEL)
    except Exception as exc:  # interface missing, permissions, etc.
        print(f"FAIL — could not open '{CHANNEL}': {exc}")
        print("      Is the interface up?  ip -details link show " + CHANNEL)
        return 1

    got_a: list[int] = []
    got_b: list[int] = []
    try:
        for i in range(N):
            tx.send(can.Message(arbitration_id=TEST_ID, data=[i], is_extended_id=False))

        # Each socket has its own kernel RX queue, so draining one does not
        # consume the other's copy. Collect from both until complete or timeout.
        deadline = time.time() + 1.0
        while time.time() < deadline and (len(got_a) < N or len(got_b) < N):
            m = rx_a.recv(timeout=0.05)
            if m and m.arbitration_id == TEST_ID:
                got_a.append(m.data[0])
            m = rx_b.recv(timeout=0.05)
            if m and m.arbitration_id == TEST_ID:
                got_b.append(m.data[0])
    finally:
        for bus in (rx_a, rx_b, tx):
            try:
                bus.shutdown()
            except Exception:
                pass

    ok = len(got_a) == N and len(got_b) == N
    print(f"interface      : {CHANNEL}")
    print(f"frames sent    : {N}")
    print(f"receiver A got : {len(got_a)}")
    print(f"receiver B got : {len(got_b)}")
    if ok:
        print("RESULT         : PASS — both sockets received every frame "
              "(kernel fan-out confirmed; B1 is valid)")
    else:
        print("RESULT         : FAIL — the two sockets did not both receive all frames")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
