"""Start the example server, the host and a static client, then drive it.

One command, three processes, and a headless browser that asks a question
and waits for the card to say it has drawn. That last part is the whole
point: a card declares its name the moment its script runs, which is
before any data reaches it, so a test that waits for the name passes for a
card that mounted and rendered nothing.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_PORT = 8091
HOST_PORT = 8090


def free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def wait_for(port: int, what: str, seconds: float = 30.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not free(port):
            return
        time.sleep(0.25)
    raise SystemExit(f"{what} never came up on :{port}")


def main() -> int:
    dist = ROOT / "client" / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("client/dist is missing — run `make build` first")

    python = sys.executable
    env = {**os.environ, "EXAMPLE_PORT": str(EXAMPLE_PORT)}
    server = subprocess.Popen(
        [python, str(ROOT / "example-server" / "server.py")], env=env
    )
    wait_for(EXAMPLE_PORT, "the example server")

    host = subprocess.Popen(
        [python, "-m", "voice_display_host"],
        env={
            **os.environ,
            "MCP_URL": f"http://127.0.0.1:{EXAMPLE_PORT}/mcp",
            "PORT": str(HOST_PORT),
            "CLIENT_DIR": str(dist),
        },
    )
    wait_for(HOST_PORT, "the host")

    try:
        drive = subprocess.run(
            ["node", str(ROOT / "scripts" / "e2e" / "handshake.mjs")],
            env={**os.environ, "DISPLAY_URL": f"http://127.0.0.1:{HOST_PORT}/"},
            check=False,
        )
        return drive.returncode
    finally:
        for process in (host, server):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
