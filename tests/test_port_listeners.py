"""Finding and stopping whatever holds a port, on every OS.

`_kill_port_owner` used to shell out to `lsof`/`fuser` unconditionally, so on Windows it raised
`FileNotFoundError` into a broad `except` on every `uv run dagster-ui`, and `kill-ports` carried a
second, divergent copy that also matched clients connected *to* the port.
"""

from __future__ import annotations

import socket
import subprocess
import sys

import psutil
import pytest

from just_dna_lite import process
from just_dna_lite.process import find_port_listeners, process_name, terminate_pids

_LISTENER = """
import socket, sys, time
s = socket.socket()
s.bind(("127.0.0.1", 0))
s.listen()
print(s.getsockname()[1], flush=True)
time.sleep(60)
"""

_CLIENT = """
import socket, sys, time
c = socket.create_connection(("127.0.0.1", int(sys.argv[1])))
print("connected", flush=True)
time.sleep(60)
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(
    sys.platform != "win32" and not any(
        subprocess.run(["which", tool], capture_output=True).returncode == 0 for tool in ("lsof", "fuser")
    ),
    reason="needs lsof or fuser",
)
def test_a_real_listener_is_found_named_and_stopped() -> None:
    child = subprocess.Popen([sys.executable, "-c", _LISTENER], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout is not None
        port = int(child.stdout.readline())
        assert find_port_listeners(port) == [child.pid]
        assert process_name(child.pid) == psutil.Process(child.pid).name()

        # A client connected to the port is not its owner (the old `lsof -ti :port` matched it).
        client = subprocess.Popen(
            [sys.executable, "-c", _CLIENT, str(port)], stdout=subprocess.PIPE, text=True
        )
        try:
            assert client.stdout is not None
            assert client.stdout.readline().strip() == "connected"
            assert find_port_listeners(port) == [child.pid]
        finally:
            client.kill()
            client.wait(timeout=5)

        terminate_pids([child.pid])
        child.wait(timeout=5)
        assert find_port_listeners(port) == []
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_a_free_port_has_no_listeners() -> None:
    assert find_port_listeners(_free_port()) == []


def test_windows_netstat_is_read_for_listeners_on_the_local_port_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`netstat -ano -p TCP` as Windows prints it: only LISTENING rows whose *local* address is
    the port count; an established client whose foreign address is :3000 does not."""
    netstat = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING       4120
  TCP    [::]:3000              [::]:0                 LISTENING       4120
  TCP    127.0.0.1:52011        127.0.0.1:3000         ESTABLISHED     9876
  TCP    0.0.0.0:30000          0.0.0.0:0              LISTENING       5555
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       7000
"""
    monkeypatch.setattr(
        process.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=netstat, stderr=""),
    )
    monkeypatch.setattr(process, "_IS_WINDOWS", True)
    assert find_port_listeners(3000) == [4120]
    assert find_port_listeners(8000) == [7000]
    assert find_port_listeners(3001) == []
