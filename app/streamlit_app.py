from __future__ import annotations

import time
from typing import List, Tuple

import sys
from pathlib import Path

import streamlit as st

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    # Ensure local imports work when Streamlit runs the script directly.
    sys.path.insert(0, str(APP_ROOT))

from ethercat_bus import create_bus
from log_buffer import LogBuffer
from piston_client import DEFAULT_DURATIONS, PistonClient

SLAVE_ID = "piston-client"
REFRESH_SECONDS = 0.5


def init_app_state() -> None:
    if "bus" not in st.session_state:
        st.session_state.bus = create_bus()
    if "client_log" not in st.session_state:
        st.session_state.client_log = LogBuffer()
    if "server_log" not in st.session_state:
        st.session_state.server_log = LogBuffer()
    if "client" not in st.session_state:
        st.session_state.client = PistonClient(
            st.session_state.bus,
            slave_id=SLAVE_ID,
            logger=st.session_state.client_log,
        )
    for idx, (ext, ret) in enumerate(DEFAULT_DURATIONS):
        st.session_state.setdefault(f"extend_{idx}", ext)
        st.session_state.setdefault(f"retract_{idx}", ret)
    st.session_state.setdefault("auto_refresh", True)


def get_current_durations() -> List[Tuple[float, float]]:
    durations: List[Tuple[float, float]] = []
    for idx in range(3):
        durations.append(
            (
                float(st.session_state.get(f"extend_{idx}", DEFAULT_DURATIONS[idx][0])),
                float(st.session_state.get(f"retract_{idx}", DEFAULT_DURATIONS[idx][1])),
            )
        )
    return durations


def send_master_command(cmd: str) -> None:
    bus = st.session_state.bus
    durations = get_current_durations()
    if cmd == "start":
        bus.write_master_command(
            SLAVE_ID, {"type": "start", "latched": True, "durations": durations}
        )
        st.session_state.server_log.add("Start command sent (latched).")
    elif cmd == "single":
        bus.write_master_command(SLAVE_ID, {"type": "single", "durations": durations})
        st.session_state.server_log.add("Single-cycle command sent (unlatched).")
    elif cmd == "stop":
        bus.write_master_command(SLAVE_ID, {"type": "stop"})
        st.session_state.server_log.add("Stop command sent.")


def format_remaining(ms: int | None) -> str:
    if ms is None:
        return "-"
    if ms >= 1000:
        return f"{ms/1000:0.1f} s"
    return f"{ms} ms"


def render_controls() -> None:
    st.subheader("Control Panel")
    with st.form("duration_form", clear_on_submit=False):
        st.write("Duration Settings (seconds)")
        for idx in range(3):
            col1, col2, col3 = st.columns([1.2, 1, 1])
            col1.markdown(f"**Piston {idx + 1}**")
            col2.number_input(
                "Extend",
                min_value=0.1,
                max_value=30.0,
                step=0.1,
                key=f"extend_{idx}",
                value=st.session_state[f"extend_{idx}"],
            )
            col3.number_input(
                "Retract",
                min_value=0.1,
                max_value=30.0,
                step=0.1,
                key=f"retract_{idx}",
                value=st.session_state[f"retract_{idx}"],
            )
        submitted = st.form_submit_button("Save Durations")
        if submitted:
            st.session_state.server_log.add("Durations updated.")

    st.markdown("---")
    btn_cols = st.columns(4)
    if btn_cols[0].button("Start (Latch)", use_container_width=True, key="btn_start"):
        send_master_command("start")
    if btn_cols[1].button("Stop", use_container_width=True, key="btn_stop"):
        send_master_command("stop")
    if btn_cols[2].button("Single Cycle", use_container_width=True, key="btn_single"):
        send_master_command("single")
    if btn_cols[3].button(
        "Reset Durations", use_container_width=True, key="btn_reset"
    ):
        for idx, (ext, ret) in enumerate(DEFAULT_DURATIONS):
            st.session_state[f"extend_{idx}"] = ext
            st.session_state[f"retract_{idx}"] = ret
        st.session_state.server_log.add("Durations reset to defaults.")
        st.rerun()


def render_state_panel(state: dict) -> None:
    st.subheader("Live State")
    status = state.get("status") or "ready"
    message = state.get("message")
    latch = bool(state.get("latching"))
    active = state.get("active_piston")
    direction = state.get("direction")
    remaining_ms = state.get("remaining_ms")
    cycle_count = state.get("cycle_count", 0)
    running = status == "running"

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Status", status)
    col_b.metric("Latch", "On" if latch else "Off")
    col_c.metric("Cycle Count", str(cycle_count))

    if message:
        st.info(message)

    rows = []
    durations = get_current_durations()
    for idx in range(3):
        is_active = running and active == idx
        rows.append(
            {
                "Piston": f"Piston {idx + 1}",
                "Direction": "Extend" if (is_active and direction == "extend") else ("Retract" if is_active else "-"),
                "Countdown": format_remaining(remaining_ms if is_active else None),
                "Duration (extend/retract)": f"{durations[idx][0]} s / {durations[idx][1]} s",
            }
        )
    st.dataframe(rows, use_container_width=True)


def render_logs() -> None:
    st.subheader("Logs")
    col1, col2 = st.columns(2)
    server_text = st.session_state.server_log.as_text(limit=200)
    client_text = st.session_state.client_log.as_text(limit=200)
    st.session_state["server_log_view"] = server_text
    st.session_state["client_log_view"] = client_text
    col1.text_area(
        "Server Log",
        key="server_log_view",
        height=260,
        disabled=True,
    )
    col2.text_area(
        "Client Log",
        key="client_log_view",
        height=260,
        disabled=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Hydraulic Piston HMI (Streamlit)",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_app_state()

    st.title("Hydraulic Piston HMI (Streamlit)")
    st.caption("EtherCAT-like master/client demo; start/stop commands and log tracking.")

    st.sidebar.header("Refresh")
    st.session_state.auto_refresh = st.sidebar.checkbox(
        "Auto-refresh (0.5s)", value=st.session_state.auto_refresh
    )
    st.sidebar.write("Commands poll bus state on each refresh.")

    cols = st.columns([1.2, 1])
    with cols[0]:
        render_controls()
    with cols[1]:
        state = st.session_state.bus.read_slave_state(SLAVE_ID) or {}
        render_state_panel(state)

    render_logs()

    if st.session_state.auto_refresh:
        time.sleep(REFRESH_SECONDS)
        st.rerun()


if __name__ == "__main__":
    main()
