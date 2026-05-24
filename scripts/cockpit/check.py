#!/usr/bin/env python3
"""
check.py — probe idempotente e auto-start do cockpit server.

FEAT-008 TASK-004.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from http.client import HTTPConnection
from pathlib import Path

DEFAULT_PORT = 8337
DEFAULT_HOST = "127.0.0.1"
PROBE_TIMEOUT_SECONDS = 1
STARTUP_TIMEOUT_SECONDS = 3

_THIS_FILE = Path(__file__).resolve()

# Global install: ~/.kanban-cortex-harness-agents/cockpit/check.py
# server.py is a sibling in the same directory
_SIBLING_SERVER = _THIS_FILE.parent / "server.py"

# Legacy install: <project>/scripts/cockpit/check.py
# server.py is 3 levels up: scripts/cockpit → scripts → project → scripts/cockpit
_LEGACY_SERVER = _THIS_FILE.parent.parent.parent / "scripts" / "cockpit" / "server.py"

SERVER_PY = _SIBLING_SERVER if _SIBLING_SERVER.exists() else _LEGACY_SERVER
PROJECT_ROOT = Path.cwd()  # board.yaml is always relative to where the command is run


def _pyyaml_available() -> bool:
    if os.environ.get("COCKPIT_SIMULATE_NO_PYYAML") == "1":
        return False
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def _port() -> int:
    raw = os.environ.get("COCKPIT_PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def probe(port: int, host: str = DEFAULT_HOST, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    try:
        conn = HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/api/board")
        response = conn.getresponse()
        response.read()
        conn.close()
        return response.status in (200, 500)
    except OSError:
        return False


def start_server(port: int) -> None:
    env = os.environ.copy()
    env["COCKPIT_PORT"] = str(port)
    env.setdefault("COCKPIT_ENABLED", "true")
    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    subprocess.Popen(
        [sys.executable, str(SERVER_PY)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )


def main() -> int:
    if not _pyyaml_available():
        print("PyYAML ausente. Usando parser YAML mínimo embutido.")

    port = _port()
    if probe(port):
        return 0

    try:
        start_server(port)
    except Exception:
        return 0

    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if probe(port, timeout=0.3):
            return 0
        time.sleep(0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
