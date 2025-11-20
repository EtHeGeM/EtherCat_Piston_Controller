"""
Basit EtherCAT benzeri haberleşme katmanı.

Gerçek bir EtherCAT master/slave altyapısı için pysoem kullanılabilir.
Bu örnekte demo amacıyla komut ve durumları paylaşımlı hafızada
saklayan FakeEtherCATBus sınıfı eklenmiştir.
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
    İn-memory, thread-safe, EtherCAT benzeri bir master/slave posta kutusu.
    Master komut yazar, client (slave) okur. Client durum yazar, master okur.
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


# Demo varsayılanı: aynı proses içinde paylaşılacak bus
LOCAL_FAKE_BUS = FakeEtherCATBus()


def create_bus(interface_name: str | None = None) -> FakeEtherCATBus:
    """
    pysoem kullanılabilir durumda ve gerçek arayüz ismi verilmişse burada
    master kurulumu yapılabilir. Demo için FakeEtherCATBus döndürülür.
    """
    if interface_name:
        if pysoem is None:
            raise RuntimeError("Gerçek EtherCAT için pysoem gerekli fakat yüklü değil.")
        raise NotImplementedError(
            "pysoem ile gerçek EtherCAT master kurulumu bu örnekte stub. "
            "interface_name vermeden FakeEtherCATBus ile devam edebilirsiniz."
        )
    return LOCAL_FAKE_BUS
