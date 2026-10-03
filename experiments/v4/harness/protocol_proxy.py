#!/usr/bin/env python3
"""逐字节转发 Agent 协议，并记录收到的公开 wallclock 字段。"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> int:
    config = json.loads(Path(__file__).with_name("_harness_proxy_config.json").read_text())
    telemetry_path = Path(config["telemetry_path"])
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path = telemetry_path.with_name("proxy_pid.json")
    pid_path.write_text(json.dumps({"proxy_pid": os.getpid(), "proxy_pgid": os.getpgrp()}) + "\n")
    entry = Path(config["entry"])
    child = subprocess.Popen([sys.executable, "-B", str(entry)], cwd=entry.parent,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                             bufsize=0)

    def forward_output():
        try:
            while True:
                line = child.stdout.readline()
                if not line:
                    break
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        except (BrokenPipeError, OSError):
            pass

    pump = threading.Thread(target=forward_output, daemon=True)
    pump.start()
    try:
        with telemetry_path.open("w", encoding="utf-8", buffering=1) as telemetry:
            for raw in sys.stdin.buffer:
                try:
                    message = json.loads(raw)
                    if message.get("message_type") == "decision_request":
                        payload = message.get("payload", {})
                        record = {"decision_sequence": message.get("decision_sequence"),
                                  "now_utc": payload.get("now_utc"),
                                  "observe_action_index": payload.get("observe_action_index"),
                                  "wallclock": payload.get("wallclock"),
                                  "received_monotonic": time.monotonic(),
                                  "message_sha256": hashlib.sha256(raw).hexdigest()}
                        telemetry.write(json.dumps(record, sort_keys=True) + "\n")
                except (ValueError, TypeError):
                    pass
                child.stdin.write(raw)
                child.stdin.flush()
        child.stdin.close()
        code = child.wait()
        pump.join(timeout=2)
        return code
    except (BrokenPipeError, OSError):
        return child.wait(timeout=2)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
