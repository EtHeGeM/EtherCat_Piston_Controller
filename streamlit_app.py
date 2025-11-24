from __future__ import annotations

import time
from typing import List, Tuple

import streamlit as st

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
        st.session_state.server_log.add("Start komutu gönderildi (latching açık).")
    elif cmd == "single":
        bus.write_master_command(SLAVE_ID, {"type": "single", "durations": durations})
        st.session_state.server_log.add("Tek döngü komutu gönderildi (latching kapalı).")
    elif cmd == "stop":
        bus.write_master_command(SLAVE_ID, {"type": "stop"})
        st.session_state.server_log.add("Stop komutu gönderildi.")


def format_remaining(ms: int | None) -> str:
    if ms is None:
        return "-"
    if ms >= 1000:
        return f"{ms/1000:0.1f} sn"
    return f"{ms} ms"


def render_controls() -> None:
    st.subheader("Kontrol Paneli")
    form = st.form("duration_form", clear_on_submit=False)
    form.write("Süre Ayarları (saniye)")
    for idx in range(3):
        col1, col2, col3 = form.columns([1.2, 1, 1])
        col1.markdown(f"**Piston {idx + 1}**")
        col2.number_input(
            "Uzatma",
            min_value=0.1,
            max_value=30.0,
            step=0.1,
            key=f"extend_{idx}",
            value=st.session_state[f"extend_{idx}"],
        )
        col3.number_input(
            "Geri Çekme",
            min_value=0.1,
            max_value=30.0,
            step=0.1,
            key=f"retract_{idx}",
            value=st.session_state[f"retract_{idx}"],
        )
    submitted = form.form_submit_button("Süreleri Kaydet")
    if submitted:
        st.session_state.server_log.add("Süre ayarları güncellendi.")

    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    if col_btn1.button("Start (Latch)", use_container_width=True):
        send_master_command("start")
    if col_btn2.button("Stop", use_container_width=True):
        send_master_command("stop")
    if col_btn3.button("Tek Döngü", use_container_width=True):
        send_master_command("single")
    if col_btn4.button("Varsayılan Süreler", use_container_width=True):
        for idx, (ext, ret) in enumerate(DEFAULT_DURATIONS):
            st.session_state[f"extend_{idx}"] = ext
            st.session_state[f"retract_{idx}"] = ret
        st.session_state.server_log.add("Süreler varsayılanlara döndürüldü.")
        st.rerun()


def render_state_panel(state: dict) -> None:
    st.subheader("Anlık Durum")
    status = state.get("status") or "hazır"
    message = state.get("message")
    latch = bool(state.get("latching"))
    active = state.get("active_piston")
    direction = state.get("direction")
    remaining_ms = state.get("remaining_ms")
    cycle_count = state.get("cycle_count", 0)
    running = status == "running"

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Durum", status)
    col_b.metric("Latch", "Açık" if latch else "Kapalı")
    col_c.metric("Çevrim Sayısı", str(cycle_count))

    if message:
        st.info(message)

    rows = []
    durations = get_current_durations()
    for idx in range(3):
        is_active = running and active == idx
        rows.append(
            {
                "Piston": f"Piston {idx + 1}",
                "Hareket": "İleri" if (is_active and direction == "extend") else ("Geri" if is_active else "-"),
                "Geri Sayım": format_remaining(remaining_ms if is_active else None),
                "Süre (uzatma/geri)": f"{durations[idx][0]} s / {durations[idx][1]} s",
            }
        )
    st.dataframe(rows, use_container_width=True)


def render_logs() -> None:
    st.subheader("Loglar")
    col1, col2 = st.columns(2)
    col1.text_area(
        "Server Logu",
        st.session_state.server_log.as_text(limit=200),
        height=260,
    )
    col2.text_area(
        "Client Logu",
        st.session_state.client_log.as_text(limit=200),
        height=260,
    )


def main() -> None:
    st.set_page_config(
        page_title="Hidrolik Piston HMI (Streamlit)",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_app_state()

    st.title("Hidrolik Piston HMI (Streamlit)")
    st.caption("EtherCAT master/client demo; start-stop komutları ve log takibi.")

    st.sidebar.header("Yenileme")
    st.session_state.auto_refresh = st.sidebar.checkbox(
        "Otomatik yenile (0.5 sn)", value=st.session_state.auto_refresh
    )
    st.sidebar.write("Komutlar sayfa her yenilendiğinde bus durumunu okur.")

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
