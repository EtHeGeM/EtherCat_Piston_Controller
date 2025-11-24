"""
Lightweight EtherCAT-like communication layer.

For real EtherCAT master/slave, pysoem could be used. This demo ships
FakeEtherCATBus to share commands/states in-memory.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

try:
    import pysoem  # type: ignore
except Exception:  # pragma: no cover - pysoem opsiyonel
    pysoem = None


class FakeEtherCATBus:
    """
    In-memory, thread-safe master/slave mailbox.
    Master writes commands, client reads; client writes state, master reads.
    """

    def __init__(self) -> None:
        self._command_mailbox: Dict[str, Dict[str, Any]] = {}
        self._state_mailbox: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def write_master_command(self, slave_id: str, command: Dict[str, Any]) -> None:
        with self._lock:
            self._command_mailbox[slave_id] = command

    def pop_slave_command(self, slave_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._command_mailbox.pop(slave_id, None)

    def write_slave_state(self, slave_id: str, state: Dict[str, Any]) -> None:
        with self._lock:
            self._state_mailbox[slave_id] = state

    def read_slave_state(self, slave_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._state_mailbox.get(slave_id)
            return dict(data) if data else None


# Demo default: shared bus within the same process
LOCAL_FAKE_BUS = FakeEtherCATBus()


def create_bus(interface_name: str | None = None) -> FakeEtherCATBus:
    """
    If pysoem + real interface provided, real master init could happen here.
    For demo, returns FakeEtherCATBus.
    """
    if interface_name:
        if pysoem is None:
            raise RuntimeError("pysoem is required for real EtherCAT but not installed.")
        raise NotImplementedError(
            "Real EtherCAT master setup with pysoem is stubbed in this example. "
            "Call create_bus() without interface_name to use FakeEtherCATBus."
        )
    return LOCAL_FAKE_BUS
