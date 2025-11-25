import tkinter as tk
from tkinter import ttk
from typing import List, Tuple
import time

from .ethercat_bus import create_bus
from .log_buffer import LogBuffer
from .piston_client import DEFAULT_DURATIONS, PistonClient


class SignalGraph:
    """Lightweight live signal monitor (step plot)."""

    def __init__(
        self,
        parent: tk.Widget,
        signals: List[tuple[str, str]],
        width: int = 820,
        height: int = 220,
        window_s: int = 20,
    ):
        self.signals = signals
        self.width = width
        self.height = height
        self.window_s = window_s
        self.history: dict[str, list[tuple[float, bool]]] = {name: [] for name, _ in signals}
        self.label_pad = 90

        frame = ttk.LabelFrame(parent, text="Signal Monitor (last 20s)")
        frame.pack(fill="both", expand=False, padx=4, pady=8)
        self.canvas = tk.Canvas(frame, width=width, height=height, bg="#0b1021", highlightthickness=1, highlightbackground="#334155")
        self.canvas.pack(fill="both", expand=True)

    def update(self, values: dict[str, bool]) -> None:
        now = time.monotonic()
        for name, _ in self.signals:
            val = bool(values.get(name, False))
            hist = self.history[name]
            if not hist or hist[-1][1] != val:
                hist.append((now, val))
            self._trim_history(name, now)
        self._draw(now)

    def _trim_history(self, name: str, now: float) -> None:
        hist = self.history[name]
        cutoff = now - self.window_s
        while hist and hist[0][0] < cutoff:
            hist.pop(0)
        if not hist:
            hist.append((now, False))

    def _draw(self, now: float) -> None:
        self.canvas.delete("all")
        row_h = self.height / (len(self.signals) + 1)

        for idx, (name, color) in enumerate(self.signals):
            y_mid = (idx + 1) * row_h
            self.canvas.create_text(8, y_mid, text=name, anchor="w", fill="#cbd5e1", font=("Segoe UI", 9, "bold"))
            hist = self.history[name]
            if not hist:
                continue
            points = hist.copy()
            last_val = points[-1][1]
            points.append((now, last_val))

            prev_t, prev_v = points[0]
            prev_x = self._to_x(prev_t, now)
            prev_y = y_mid - (row_h * 0.25 if prev_v else -row_h * 0.25)

            for t, v in points[1:]:
                x = self._to_x(t, now)
                y = y_mid - (row_h * 0.25 if prev_v else -row_h * 0.25)
                self.canvas.create_line(prev_x, y, x, y, fill=color, width=2)
                if v != prev_v:
                    y2 = y_mid - (row_h * 0.25 if v else -row_h * 0.25)
                    self.canvas.create_line(x, y, x, y2, fill=color, width=2)
                prev_x, prev_v = x, v

            # grid line
            self.canvas.create_line(self.label_pad, y_mid, self.width, y_mid, fill="#1e293b", dash=(2, 2))

    def _to_x(self, t: float, now: float) -> float:
        span = max(0.001, self.window_s)
        delta = now - t
        frac = max(0.0, min(1.0, delta / span))
        return self.width - frac * (self.width - self.label_pad)


class HMIServer:
    """
    EtherCAT master side: send commands from HMI, read client states.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hydraulic Piston HMI (EtherCAT Server)")
        self.bus = create_bus()
        self.slave_id = "piston-client"
        self.server_log = LogBuffer()
        self.client_log = LogBuffer()
        self.client = PistonClient(self.bus, slave_id=self.slave_id, logger=self.client_log)

        self.pistons: List[dict] = []
        self.last_status = None
        self.last_timestamp = 0.0
        self._pulse_flags = {"start_cmd": False, "stop_cmd": False}
        self._server_log_cursor = 0
        self._client_log_cursor = 0

        self._build_ui()
        self._reset_states()
        self._poll_bus()

    def _build_ui(self) -> None:
        root = self.root
        root.geometry("840x460")
        root.configure(padx=10, pady=10)

        title = ttk.Label(
            root,
            text="3-Piston Hydraulic Simulation (EtherCAT Master/HMI)",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(pady=(0, 10))

        # Timing configuration panel
        config_frame = ttk.LabelFrame(root, text="Duration Settings (seconds)")
        config_frame.pack(fill="x", padx=4, pady=4)

        header = ["Piston", "Extend", "Retract", "State", "Countdown"]
        for col, text in enumerate(header):
            ttk.Label(config_frame, text=text, font=("Segoe UI", 10, "bold")).grid(
                row=0, column=col, padx=6, pady=6, sticky="w"
            )

        for idx in range(3):
            extend_default, retract_default = DEFAULT_DURATIONS[idx]
            extend_var = tk.DoubleVar(value=extend_default)
            retract_var = tk.DoubleVar(value=retract_default)
            state_var = tk.StringVar(value="Idle")
            timer_var = tk.StringVar(value="-")

            ttk.Label(config_frame, text=f"Piston {idx + 1}").grid(
                row=idx + 1, column=0, padx=6, pady=4, sticky="w"
            )

            extend_spin = ttk.Spinbox(
                config_frame,
                from_=0.1,
                to=30,
                increment=0.1,
                textvariable=extend_var,
                width=8,
            )
            extend_spin.grid(row=idx + 1, column=1, padx=6, pady=4)

            retract_spin = ttk.Spinbox(
                config_frame,
                from_=0.1,
                to=30,
                increment=0.1,
                textvariable=retract_var,
                width=8,
            )
            retract_spin.grid(row=idx + 1, column=2, padx=6, pady=4)

            state_label = tk.Label(
                config_frame,
                textvariable=state_var,
                width=18,
                bg="#d9d9d9",
                relief="groove",
            )
            state_label.grid(row=idx + 1, column=3, padx=6, pady=4, sticky="we")

            timer_label = tk.Label(
                config_frame,
                textvariable=timer_var,
                width=12,
                bg="#d9d9d9",
                relief="groove",
            )
            timer_label.grid(row=idx + 1, column=4, padx=6, pady=4, sticky="we")

            self.pistons.append(
                {
                    "extend_var": extend_var,
                    "retract_var": retract_var,
                    "state_var": state_var,
                    "state_label": state_label,
                    "timer_var": timer_var,
                    "timer_label": timer_label,
                    "name": f"Piston {idx + 1}",
                }
            )

        # Control and status area
        control_frame = ttk.Frame(root)
        control_frame.pack(fill="x", pady=10)

        self.bus_indicator = tk.Label(
            control_frame,
            text="EtherCAT Bus: Fake/Local",
            width=20,
            bg="#607d8b",
            fg="white",
            relief="ridge",
        )
        self.bus_indicator.pack(side="left", padx=6)

        self.latch_indicator = tk.Label(
            control_frame,
            text="Latching: Off",
            width=16,
            bg="#f44336",
            fg="white",
            relief="ridge",
        )
        self.latch_indicator.pack(side="left", padx=6)

        start_btn = ttk.Button(control_frame, text="Start (Latch)", command=self.start)
        start_btn.pack(side="left", padx=6)

        stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop)
        stop_btn.pack(side="left", padx=6)

        single_btn = ttk.Button(
            control_frame, text="Single Cycle", command=self.single_cycle
        )
        single_btn.pack(side="left", padx=6)

        reset_btn = ttk.Button(control_frame, text="Reset Durations", command=self._reset_times)
        reset_btn.pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            root, textvariable=self.status_var, background="#eef3ff", padding=(8, 4)
        )
        status_label.pack(fill="x", pady=(0, 4))

        # Logs panel (server + client)
        log_frame = ttk.LabelFrame(root, text="Logs")
        log_frame.pack(fill="both", expand=True, padx=4, pady=4)

        server_col = ttk.Frame(log_frame)
        server_col.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=4)
        ttk.Label(server_col, text="Server (HMI)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.server_log_box = tk.Text(
            server_col, height=10, state="disabled", bg="#0f172a", fg="#e2e8f0"
        )
        self.server_log_box.pack(fill="both", expand=True)

        client_col = ttk.Frame(log_frame)
        client_col.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        ttk.Label(client_col, text="Client (Piston)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.client_log_box = tk.Text(
            client_col, height=10, state="disabled", bg="#0f172a", fg="#e2e8f0"
        )
        self.client_log_box.pack(fill="both", expand=True)

        self.signal_graph = SignalGraph(
            root,
            signals=[
                ("start_cmd", "#22c55e"),
                ("stop_cmd", "#ef4444"),
                ("latch", "#fbbf24"),
                ("running", "#38bdf8"),
                ("p1_active", "#8bc34a"),
                ("p2_active", "#009688"),
                ("p3_active", "#9c27b0"),
            ],
            width=820,
            height=220,
            window_s=20,
        )

    def _collect_durations(self) -> List[Tuple[float, float]]:
        result: List[Tuple[float, float]] = []
        for piston in self.pistons:
            result.append((float(piston["extend_var"].get()), float(piston["retract_var"].get())))
        return result

    def _log(self, message: str) -> None:
        self.server_log.add(message)
        self._refresh_logs()

    def _reset_times(self) -> None:
        for idx, piston in enumerate(self.pistons):
            extend_default, retract_default = DEFAULT_DURATIONS[idx]
            piston["extend_var"].set(extend_default)
            piston["retract_var"].set(retract_default)
        self._log("Durations reset to defaults.")

    def _reset_states(self) -> None:
        for piston in self.pistons:
            piston["state_var"].set("Idle")
            piston["state_label"].configure(bg="#d9d9d9")
            piston["timer_var"].set("-")

    def _set_latch_indicator(self, latched: bool) -> None:
        if latched:
            self.latch_indicator.configure(text="Latching: On", bg="#4caf50")
        else:
            self.latch_indicator.configure(text="Latching: Off", bg="#f44336")

    def start(self) -> None:
        durations = self._collect_durations()
        self.bus.write_master_command(
            self.slave_id, {"type": "start", "latched": True, "durations": durations}
        )
        self.status_var.set("Start command sent (latched).")
        self._log("Start: latched command sent over EtherCAT.")
        self._set_latch_indicator(True)
        self._pulse_flags["start_cmd"] = True

    def stop(self) -> None:
        self.bus.write_master_command(self.slave_id, {"type": "stop"})
        self.status_var.set("Stop command sent.")
        self._log("Stop command sent over EtherCAT.")
        self._set_latch_indicator(False)
        self._pulse_flags["stop_cmd"] = True

    def single_cycle(self) -> None:
        durations = self._collect_durations()
        self.bus.write_master_command(
            self.slave_id, {"type": "single", "durations": durations}
        )
        self.status_var.set("Single-cycle command sent (not latched).")
        self._log("Single-cycle command sent over EtherCAT.")
        self._set_latch_indicator(False)
        self._pulse_flags["start_cmd"] = True

    def _apply_state_to_ui(self, state: dict) -> None:
        latch = bool(state.get("latching"))
        self._set_latch_indicator(latch)

        active = state.get("active_piston")
        direction = state.get("direction")
        status = state.get("status")
        message = state.get("message")
        timestamp = state.get("timestamp", 0)
        remaining_ms = state.get("remaining_ms", None)

        if status != self.last_status or message:
            self.status_var.set(message or f"Status: {status}")
            if status != self.last_status and status:
                self._log(f"State: {status}")
            if message:
                self._log(message)
            self.last_status = status
            self.last_timestamp = timestamp

        if active is not None and direction:
            for idx, piston in enumerate(self.pistons):
                if idx == active:
                    color = "#4caf50" if direction == "extend" else "#ff9800"
                    piston["state_var"].set("Extend" if direction == "extend" else "Retract")
                    piston["state_label"].configure(bg=color)
                    piston["timer_var"].set(self._format_remaining(remaining_ms))
                else:
                    piston["state_var"].set("Idle")
                    piston["state_label"].configure(bg="#d9d9d9")
                    piston["timer_var"].set("-")
        else:
            self._reset_states()

        self._update_signal_graph(active, latch, status)

    def _poll_bus(self) -> None:
        state = self.bus.read_slave_state(self.slave_id)
        if state and state.get("timestamp", 0) >= self.last_timestamp:
            self._apply_state_to_ui(state)
        self._refresh_logs()
        self.root.after(100, self._poll_bus)

    def _update_signal_graph(self, active: int | None, latch: bool, status: str | None) -> None:
        running = status == "running"
        signals = {
            "start_cmd": self._pulse_flags["start_cmd"],
            "stop_cmd": self._pulse_flags["stop_cmd"],
            "latch": latch,
            "running": running,
            "p1_active": active == 0 and running,
            "p2_active": active == 1 and running,
            "p3_active": active == 2 and running,
        }
        self.signal_graph.update(signals)
        # Pulse cleanup
        self._pulse_flags["start_cmd"] = False
        self._pulse_flags["stop_cmd"] = False

    def _refresh_logs(self) -> None:
        self._append_buffer(self.server_log_box, self.server_log, "_server_log_cursor")
        self._append_buffer(self.client_log_box, self.client_log, "_client_log_cursor")

    def _append_buffer(self, widget: tk.Text, buffer: LogBuffer, cursor_attr: str) -> None:
        lines = buffer.get_lines()
        cursor = getattr(self, cursor_attr)
        if cursor >= len(lines):
            return
        new_lines = lines[cursor:]
        widget.configure(state="normal")
        widget.insert("end", "\n".join(new_lines) + "\n")
        widget.see("end")
        widget.configure(state="disabled")
        setattr(self, cursor_attr, len(lines))

    @staticmethod
    def _format_remaining(remaining_ms: int | None) -> str:
        if remaining_ms is None:
            return "-"
        seconds = remaining_ms / 1000
        if seconds >= 1:
            return f"{seconds:0.1f} s"
        return f"{remaining_ms} ms"


def main() -> None:
    root = tk.Tk()
    HMIServer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
