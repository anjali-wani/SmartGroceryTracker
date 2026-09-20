#!/usr/bin/env python3
"""Script to restart the Smart Grocery Tracker FastAPI backend server on port 8001."""
import os
import sys
import time
import signal
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 8001
HOST = "127.0.0.1"
LOG_FILE = PROJECT_ROOT / "uvicorn.log"


def find_pids_on_port(port: int):
    """Find process IDs currently listening on the specified port."""
    try:
        output = subprocess.check_output(
            ["lsof", "-ti", f":{port}"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if output:
            return [int(pid) for pid in output.splitlines() if pid.isdigit()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return []


def kill_pids(pids):
    """Gracefully terminate processes, falling back to SIGKILL if necessary."""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    # Wait up to 5 seconds for release
    for _ in range(10):
        time.sleep(0.5)
        remaining = [p for p in pids if is_pid_running(p)]
        if not remaining:
            return True

    # Force kill
    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(0.5)
    return True


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def is_server_healthy(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    print("=" * 60)
    print(f"  Restarting Smart Grocery Tracker Backend Server (Port {PORT})")
    print("=" * 60)

    # 1. Check for running instance on port 8001
    existing_pids = find_pids_on_port(PORT)
    if existing_pids:
        print(f"🛑 Found existing process(es) on port {PORT}: {existing_pids}. Terminating...")
        kill_pids(existing_pids)
        print(f"✅ Port {PORT} successfully freed.")
    else:
        print(f"ℹ️  No existing process listening on port {PORT}.")

    # 2. Locate virtualenv uvicorn or python
    venv_uvicorn = PROJECT_ROOT / "venv" / "bin" / "uvicorn"
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"

    if venv_uvicorn.exists():
        cmd = [
            str(venv_uvicorn),
            "app.main:app",
            "--host", HOST,
            "--port", str(PORT),
            "--app-dir", str(PROJECT_ROOT),
            "--reload"
        ]
    elif venv_python.exists():
        cmd = [
            str(venv_python),
            "-m", "uvicorn",
            "app.main:app",
            "--host", HOST,
            "--port", str(PORT),
            "--app-dir", str(PROJECT_ROOT),
            "--reload"
        ]
    else:
        cmd = [
            sys.executable,
            "-m", "uvicorn",
            "app.main:app",
            "--host", HOST,
            "--port", str(PORT),
            "--app-dir", str(PROJECT_ROOT),
            "--reload"
        ]

    # 3. Launch in background
    print(f"🚀 Starting server on http://{HOST}:{PORT}...")
    log_fp = open(LOG_FILE, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

    print(f"   Spawned backend PID: {proc.pid}")
    print(f"   Writing server logs to: {LOG_FILE}")

    # 4. Wait for healthy response
    print("⏳ Checking server health...")
    health_url = f"http://{HOST}:{PORT}/"
    healthy = False
    for _ in range(16):
        time.sleep(0.5)
        if is_server_healthy(health_url):
            healthy = True
            break

    if healthy:
        print("=" * 60)
        print(f"✅ Backend server is online and healthy!")
        print(f"   API Base URL : http://{HOST}:{PORT}")
        print(f"   Interactive Docs : http://{HOST}:{PORT}/docs")
        print(f"   Log File : {LOG_FILE}")
        print("=" * 60)
    else:
        print("❌ Server did not respond within 8 seconds. Recent logs:")
        print("-" * 60)
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text().splitlines()[-25:]
            print("\n".join(lines))
        print("-" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
