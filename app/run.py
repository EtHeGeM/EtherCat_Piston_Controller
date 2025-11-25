"""
Unified launcher to run the hydraulic piston demo from a single entry point.
Installs Python dependencies, then can start Streamlit HMI (includes client),
Tkinter HMI, headless client, or static web server.

Usage examples:
  python run.py                 # install deps + Tkinter HMI (default)
  python run.py --mode tk
  python run.py --mode streamlit
  python run.py --mode web --port 3000
  python run.py --mode client   # headless piston client only
"""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    # Ensure package imports (app.*) work regardless of entrypoint style.
    sys.path.insert(0, str(ROOT))


def ensure_venv() -> str:
    """Ensure local .venv exists and return its python executable path."""
    root = Path(__file__).resolve().parent.parent
    venv_dir = root / ".venv"
    if not venv_dir.exists():
        print("Creating virtual environment at ./.venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python_bin = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    return str(python_bin)


def maybe_reexec_into_venv(venv_python: str) -> None:
    """Re-exec into .venv python if current interpreter is different."""
    if os.path.abspath(sys.executable) == os.path.abspath(venv_python):
        return
    if os.environ.get("HYDRO_IN_VENV") == "1":
        return
    env = os.environ.copy()
    env["HYDRO_IN_VENV"] = "1"
    print(f"Re-launching inside virtualenv: {venv_python}")
    os.execvpe(venv_python, [venv_python, __file__, *sys.argv[1:]], env)


def install_deps() -> None:
    """Install Python requirements using current interpreter (expected to be venv)."""
    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    if not req_path.exists():
        print("requirements.txt not found; skipping pip install.")
        return
    print("Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_path)], check=True)
    print("Dependencies installed.")


def run_tkinter() -> None:
    from app.main import main as tk_main

    tk_main()


def run_streamlit(port: int) -> None:
    app_dir = Path(__file__).resolve().parent
    app_path = app_dir / "streamlit_app.py"
    if not app_path.exists():
        raise FileNotFoundError(f"Streamlit app not found at {app_path}")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
    ]
    subprocess.run(cmd, check=True, cwd=str(app_dir))


def run_client_only() -> None:
    from app.ethercat_bus import create_bus
    from app.piston_client import PistonClient

    bus = create_bus()
    PistonClient(bus)
    print("Client running on shared FakeEtherCATBus. Press Ctrl+C to exit.")
    try:
        while True:
            # lightweight wait to keep thread alive
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        return


def run_static_web(host: str, port: int, open_browser: bool) -> None:
    web_dir = os.path.join(Path(__file__).resolve().parent.parent, "web")
    os.chdir(web_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer((host, port), handler) as httpd:
        url = f"http://{host}:{port}/"
        print(f"Serving static web (presentation / 3D / landing) at {url}")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down web server.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hydraulic Piston demo launcher")
    parser.add_argument(
        "--mode",
        choices=["all", "tk", "streamlit", "web", "client"],
        default="tk",
        help="default tk (Tkinter HMI), streamlit, web (static), client (headless), all (install + Streamlit)",
    )
    parser.add_argument("--port", type=int, default=3000, help="Port for streamlit or web server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host bind address for web server")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser for web mode")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation")
    return parser.parse_args()


def main() -> None:
    venv_python = ensure_venv()
    maybe_reexec_into_venv(venv_python)

    args = parse_args()
    if not args.skip_install:
        install_deps()

    if args.mode == "tk":
        run_tkinter()
    elif args.mode in ("streamlit", "all"):
        run_streamlit(args.port)
    elif args.mode == "client":
        run_client_only()
    elif args.mode == "web":
        run_static_web(args.host, args.port, not args.no_browser)
    else:
        raise SystemExit(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
