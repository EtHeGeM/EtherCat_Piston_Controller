# Hydraulic Piston PLC / HMI (EtherCAT-style)

Three-piston hydraulic simulation with Python. HMI (master) and piston client (slave) share commands/states over a Fake EtherCAT bus; optional Streamlit web UI and animated presentations are included. All Python code is under `app/`.

## Features
- 3 pistons with separate extend/retract duration inputs (seconds)
- Start (latched) and Stop; latched mode auto-restarts after each cycle
- Single Cycle without latching
- Fake EtherCAT bus (thread-safe mailbox) or pysoem placeholder for real EtherCAT
- Tkinter HMI with signal monitor; Streamlit HMI with server/client logs
- Animated web presentation and 3D Three.js visualization

## Setup
```bash
python app/run.py  # auto-creates .venv, installs requirements, starts Streamlit HMI
```
Options:
```bash
python app/run.py --mode streamlit --port 8501  # Web HMI
python app/run.py --mode tk                     # Tkinter HMI
python app/run.py --mode web --port 3000        # Serve presentation/3D static pages
python app/run.py --mode client                  # Headless piston client only
python app/run.py --skip-install                 # Skip pip install
```

If you prefer manual install:
```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Running HMIs
- Tkinter: `python -m app.main`
- Streamlit: `streamlit run app/streamlit_app.py`

## Static web / Node server
- `npm install` (only generates lockfile; no deps)
- `npm start` (serves `web/` at 0.0.0.0:3000)
- Open:
  - Presentation: `http://localhost:3000/presentation.html`
  - Landing: `http://localhost:3000/index.html`
  - 3D view: `http://localhost:3000/interactive-3d.html`
  - Deep dive: `http://localhost:3000/tech-deep-dive.html`

## Architecture
- **HMI (master)**: Tkinter or Streamlit UI. Collects durations, writes commands with `write_master_command`, polls state with `read_slave_state`.
- **Client (slave)**: `PistonClient` reads commands, builds extend/retract sequence, publishes state (status, active piston, direction, remaining_ms, latch, cycle_count, message).
- **Fake EtherCAT Bus**: in-memory, thread-safe mailbox in `ethercat_bus.py`.
- **Logging**: `LogBuffer` for server/client messages (Streamlit); Tkinter Text for server log.

## Command / State payloads
Master → Slave:
```json
{ "type": "start", "latched": true, "durations": [[1.5,1.0],[2.0,1.0],[2.5,1.0]] }
{ "type": "single", "durations": [[...],[...],[...]] }
{ "type": "stop" }
```
Slave → Master:
```json
{
  "status": "running|complete|stopped",
  "active_piston": 0,
  "direction": "extend|retract",
  "remaining_ms": 850,
  "cycle_count": 3,
  "latching": true,
  "message": "Cycle started."
}
```

## Notes
- Latch: when `latched=true`, client restarts 0.5s after completing the sequence.
- Minimum stage time: 50 ms safeguard; durations sanitized to ≥0.05 s.
- Fake bus keeps commands/states per `slave_id` and clones state on read to avoid mutation.
