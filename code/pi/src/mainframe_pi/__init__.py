"""Mainframe Simulation — Raspberry Pi central-complex subsystems (Phase 1).

Each subsystem (router, processor, jes, liveness) runs as its own process — see
ADR-0001 (separate address spaces). Shared code lives in `protocol` (wire codec)
and `storage` (SQLite schema + write-ahead pattern).
"""

__version__ = "0.1.0"
