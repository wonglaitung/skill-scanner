from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def main() -> int:
    failures: list[str] = []

    if os.getuid() == 0:
        failures.append("running as root")

    try:
        Path("/workspace/.escape-probe").write_text("x", encoding="utf-8")
        failures.append("workspace is writable")
    except OSError:
        pass

    try:
        Path("/etc/shadow").read_text(encoding="utf-8")
        failures.append("/etc/shadow is readable")
    except OSError:
        pass

    try:
        with socket.create_connection(("1.1.1.1", 80), timeout=2):
            failures.append("network is reachable")
    except OSError:
        pass

    if Path("/var/run/docker.sock").exists():
        failures.append("docker socket is mounted")

    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1

    print("PASS: sandbox escape checks blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
