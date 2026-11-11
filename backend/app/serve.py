"""Supervise the web process and a separate refresh process in one Render service."""

import logging
import os
import signal
import subprocess
import sys
import time


def main():
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("forecast.supervisor")
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.getenv("PORT", "8000"),
        ],
        [sys.executable, "-m", "backend.app.ingest", "--watch"],
    ]
    processes = [subprocess.Popen(command) for command in commands]
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping:
            if any(process.poll() is not None for process in processes):
                log.error("A managed process exited; stopping service for host restart")
                return 1
            time.sleep(1)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
