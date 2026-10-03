"""本轮独立六槽锁；沿用原锁FD继承与释放语义，不修改原二槽锁。"""
import fcntl
import json
import os
from pathlib import Path
import time

from common import SimulatorLease

LOCK_ROOT = Path(__file__).resolve().parent / ".locks"
SIMULATOR_LIMIT = 6


class SixSlotLease(SimulatorLease):
    def __init__(self, run_id, *, exclusive=False, timeout=1800, lock_root=None):
        super().__init__(run_id, exclusive=exclusive, timeout=timeout, lock_root=lock_root or LOCK_ROOT)

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        while True:
            held = []; peers = []
            with (self.root / "gate.lock").open("a+") as gate:
                fcntl.flock(gate, fcntl.LOCK_EX)
                for index in range(SIMULATOR_LIMIT):
                    handle = (self.root / f"slot-{index}.lock").open("a+")
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        held.append((index, handle))
                    except BlockingIOError:
                        handle.seek(0)
                        try:
                            peers.append(json.load(handle))
                        except ValueError:
                            peers.append({"slot": index, "metadata": "not yet written"})
                        handle.close()
                enough = len(held) == SIMULATOR_LIMIT if self.exclusive else bool(held)
                if enough:
                    self.handles = held if self.exclusive else held[:1]
                    for _, handle in held[len(self.handles):]:
                        fcntl.flock(handle, fcntl.LOCK_UN); handle.close()
                    self.wait_seconds = time.monotonic() - started
                    for index, handle in self.handles:
                        handle.seek(0); handle.truncate()
                        json.dump({"run_id": self.run_id, "harness_pid": os.getpid(), "slot": index,
                                   "exclusive": self.exclusive, "limit": SIMULATOR_LIMIT}, handle)
                        handle.flush()
                    self.conditions = {"simulator_limit": SIMULATOR_LIMIT, "exclusive": self.exclusive,
                                       "slots": [index for index, _ in self.handles], "peers_at_acquisition": peers,
                                       "cpu_count": os.cpu_count(), "load_average": os.getloadavg(),
                                       "lock_wait_seconds": self.wait_seconds,
                                       "lock_namespace": str(self.root)}
                    return self
                for _, handle in held:
                    fcntl.flock(handle, fcntl.LOCK_UN); handle.close()
            if time.monotonic() - started >= self.timeout:
                raise TimeoutError(f"等待extension simulator锁超过 {self.timeout:g} 秒")
            time.sleep(0.1)
