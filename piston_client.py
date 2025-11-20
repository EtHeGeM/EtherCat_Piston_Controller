import threading
import time
from dataclasses import dataclass
from typing import List, Tuple

from ethercat_bus import FakeEtherCATBus, create_bus


@dataclass
class Stage:
    piston_index: int
    action: str  # "extend" or "retract"
    duration_ms: int


DEFAULT_DURATIONS: List[Tuple[float, float]] = [(1.5, 1.0), (2.0, 1.0), (2.5, 1.0)]


class PistonClient:
    """
    EtherCAT üzerindeki slave (client) tarafı: piston hareketlerini yönetir,
    HMI master'dan gelen komutları uygular.
    """

    def __init__(self, bus: FakeEtherCATBus, slave_id: str = "piston-client") -> None:
        self.bus = bus
        self.slave_id = slave_id
        self.latched = False
        self.running = False
        self.durations = DEFAULT_DURATIONS.copy()
        self.sequence: List[Stage] = []
        self.stage_index = 0
        self.stage_started_at = 0.0
        self.cycle_count = 0
        self._next_cycle_at: float | None = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            self._handle_commands()
            self._process_cycle()
            time.sleep(0.01)

    def _handle_commands(self) -> None:
        cmd = self.bus.pop_slave_command(self.slave_id)
        if not cmd:
            return
        ctype = cmd.get("type")
        if ctype == "start":
            durations = cmd.get("durations") or self.durations
            self._apply_durations(durations)
            self.latched = bool(cmd.get("latched", True))
            self._start_cycle()
        elif ctype == "single":
            durations = cmd.get("durations") or self.durations
            self._apply_durations(durations)
            self.latched = False
            self._start_cycle()
        elif ctype == "stop":
            self.latched = False
            self.running = False
            self._next_cycle_at = None
            self.stage_index = 0
            self.stage_started_at = 0.0
            self._publish_state(
                status="stopped",
                direction=None,
                active_piston=None,
                remaining_ms=0,
                message="Stop komutu alındı.",
            )

    def _apply_durations(self, durations: List[Tuple[float, float]]) -> None:
        clean = []
        for pair in durations:
            try:
                extend, retract = float(pair[0]), float(pair[1])
            except Exception:
                extend, retract = 1.0, 1.0
            clean.append((max(0.05, extend), max(0.05, retract)))
        while len(clean) < 3:
            clean.append(DEFAULT_DURATIONS[len(clean)])
        self.durations = clean[:3]

    def _start_cycle(self) -> None:
        self.sequence = self._build_sequence()
        self.stage_index = 0
        self.stage_started_at = time.monotonic()
        self.running = True
        if not self.sequence:
            self.running = False
            self._publish_state(
                status="stopped",
                direction=None,
                active_piston=None,
                remaining_ms=0,
                message="Sekans boş.",
            )
            return
        self._publish_state(
            status="running",
            direction=self.sequence[0].action,
            active_piston=self.sequence[0].piston_index,
            remaining_ms=self.sequence[0].duration_ms,
            message="Döngü başlatıldı.",
        )

    def _build_sequence(self) -> List[Stage]:
        result: List[Stage] = []
        for idx, pair in enumerate(self.durations):
            extend_ms = int(pair[0] * 1000)
            retract_ms = int(pair[1] * 1000)
            result.append(Stage(idx, "extend", extend_ms))
            result.append(Stage(idx, "retract", retract_ms))
        return result

    def _process_cycle(self) -> None:
        now = time.monotonic()

        if not self.running and self.latched and self._next_cycle_at and now >= self._next_cycle_at:
            self._start_cycle()
            self._next_cycle_at = None
            return

        if not self.running:
            return

        if self.stage_index >= len(self.sequence):
            self.running = False
            self.cycle_count += 1
            self._publish_state(
                status="complete",
                direction=None,
                active_piston=None,
                remaining_ms=0,
                message="Döngü tamamlandı.",
            )
            if self.latched:
                self._next_cycle_at = now + 0.5
            return

        stage = self.sequence[self.stage_index]
        elapsed_ms = (now - self.stage_started_at) * 1000
        if elapsed_ms >= max(stage.duration_ms, 50):
            self.stage_index += 1
            if self.stage_index >= len(self.sequence):
                self.running = False
                self.cycle_count += 1
                self._publish_state(
                    status="complete",
                    direction=None,
                    active_piston=None,
                    remaining_ms=0,
                    message="Döngü tamamlandı.",
                )
                if self.latched:
                    self._next_cycle_at = now + 0.5
                return

            self.stage_started_at = now
            next_stage = self.sequence[self.stage_index]
            self._publish_state(
                status="running",
                direction=next_stage.action,
                active_piston=next_stage.piston_index,
                remaining_ms=next_stage.duration_ms,
            )

    def _publish_state(
        self,
        status: str,
        direction: str | None,
        active_piston: int | None,
        remaining_ms: int | None = None,
        message: str | None = None,
    ) -> None:
        state = {
            "status": status,
            "active_piston": active_piston,
            "direction": direction,
            "stage_index": self.stage_index,
            "latching": self.latched,
            "cycle_count": self.cycle_count,
            "timestamp": time.time(),
        }
        if remaining_ms is None:
            remaining_ms = self._calculate_remaining_ms()
        state["remaining_ms"] = max(0, int(remaining_ms))
        if message:
            state["message"] = message
        self.bus.write_slave_state(self.slave_id, state)

    def _calculate_remaining_ms(self) -> int:
        if not self.running or self.stage_index >= len(self.sequence):
            return 0
        stage = self.sequence[self.stage_index]
        elapsed_ms = (time.monotonic() - self.stage_started_at) * 1000
        return max(0, int(stage.duration_ms - elapsed_ms))


def run_demo() -> None:
    """
    Başka bir terminalden master/HMI çalıştırırken shared FakeEtherCATBus
    üzerinde piston client'ı başlatmak için kullanılabilir.
    """
    bus = create_bus()
    PistonClient(bus)
    print("Piston client açık. Çıkmak için Ctrl+C.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    run_demo()
