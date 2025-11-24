# Hydraulic Piston Simulation — Presentation Summary

Use this summary to present the 3-piston hydraulic system: architecture, protocol, flow, and usage.

## Architecture
- **HMI / Server (master)**: `main.py` (Tkinter) or `streamlit_app.py` (web). Collects durations, sends commands, polls state.
- **Piston Client (slave)**: `piston_client.py`. Reads commands, runs the extend/retract sequence, publishes state.
- **Communication Layer**: `FakeEtherCATBus` in `ethercat_bus.py`. In-memory, thread-safe mailbox for commands/states.
- **Logging**: `log_buffer.py`. Thread-safe buffers for server/client logs (shown in Streamlit).

## Communication Protocol (API)
Master → Slave commands (`write_master_command`):
```json
{ "type": "start", "latched": true, "durations": [[1.5,1.0],[2.0,1.0],[2.5,1.0]] }
{ "type": "single", "durations": [[...],[...],[...]] }
{ "type": "stop" }
```
- `latched=true`: after completion, restarts automatically after 0.5 s.
- `durations`: (extend_s, retract_s) per piston; expects 3 entries, fills missing with defaults.

Slave → Master state (`write_slave_state`):
```json
{
  "status": "running|complete|stopped",
  "active_piston": 0,
  "direction": "extend|retract",
  "stage_index": 0,
  "latching": true,
  "cycle_count": 3,
  "remaining_ms": 850,
  "timestamp": 1710000000.12,
  "message": "Cycle started."
}
```

## Flow
1. **Init**: HMI creates Fake bus and `PistonClient`; loads default durations.
2. **Send command**: User clicks Start/Single/Stop. HMI writes to bus; logs capture outgoing commands.
3. **Process**: Client reads command, applies durations, sets latch flag, starts sequence.
4. **Sequence**: For each piston, extend then retract in ms. Remaining time calculated per step.
5. **Publish state**: Each transition writes state (active piston, remaining, latch, message) to bus; logs capture messages.
6. **Latch loop**: If `latched=true`, wait 0.5 s after completion then restart; otherwise stop at `complete`.
7. **Log view**: Streamlit shows server/client logs side by side; Tkinter shows server log in a text box.

## Timing / Threading
- Client runs its own thread, 10 ms loop (command handling + sequence).
- Fake bus guarded by `threading.Lock`; mailboxes kept as dicts.
- HMI polling: Tkinter `after(100ms)`; Streamlit refresh loop.

## Interfaces
- **Tkinter HMI (`main.py`)**: Duration spinboxes, Start/Stop/Single buttons, latch/state indicators, signal graph.
- **Streamlit (`streamlit_app.py`)**: Web form/buttons, status panel (metrics + table), server/client log text areas, 0.5 s auto-refresh.

## Example Usage
1. `streamlit run streamlit_app.py` (or `python run.py` for auto-setup).
2. Enter extend/retract durations for pistons 1–3, click **Save Durations**.
3. Click **Start (Latch)**; sequence repeats automatically when latched.
4. Track active piston and remaining time in the status panel; read master/slave messages in logs.
5. Use **Stop** to halt or **Single Cycle** to run once without latching.
