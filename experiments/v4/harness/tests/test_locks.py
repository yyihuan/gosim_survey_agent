"""验证跨进程的两槽上限、独占和锁 fd 的 runner 生命周期。"""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import SimulatorLease

WORKER = """
import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from common import SimulatorLease
with SimulatorLease(sys.argv[3], exclusive=sys.argv[4]=='1', lock_root=Path(sys.argv[2])) as lease:
    start=time.time()
    time.sleep(0.25)
    print(json.dumps({'name':sys.argv[3],'start':start,'end':time.time(), 'slots':lease.conditions['slots']}))
"""


class LockTests(unittest.TestCase):
    def workers(self, exclusive_flags):
        with tempfile.TemporaryDirectory() as temp:
            processes = []
            for index, exclusive in enumerate(exclusive_flags):
                processes.append(subprocess.Popen([sys.executable, "-B", "-c", WORKER, str(ROOT), temp,
                                                   str(index), str(int(exclusive))], stdout=subprocess.PIPE, text=True))
                time.sleep(0.03)
            return [json.loads(process.communicate(timeout=5)[0]) for process in processes]

    def test_never_more_than_two(self):
        intervals = self.workers([False] * 4)
        events = sorted([(row["start"], 1) for row in intervals] + [(row["end"], -1) for row in intervals])
        active = 0
        maximum = 0
        for _, delta in events:
            active += delta
            maximum = max(maximum, active)
        self.assertEqual(maximum, 2)

    def test_exclusive_has_no_overlap(self):
        intervals = self.workers([False, True, False])
        exclusive = intervals[1]
        self.assertEqual(exclusive["slots"], [0, 1])
        for peer in (intervals[0], intervals[2]):
            self.assertTrue(peer["end"] <= exclusive["start"] or peer["start"] >= exclusive["end"])

    def test_inherited_fd_holds_lock_after_owner_exits(self):
        with tempfile.TemporaryDirectory() as temp:
            code = """
import os,subprocess,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from common import SimulatorLease
lease=SimulatorLease('owner',exclusive=True,lock_root=Path(sys.argv[2])).__enter__()
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(0.6)'],pass_fds=lease.fds,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(child.pid,flush=True)
os._exit(0)
"""
            owner = subprocess.Popen([sys.executable, "-B", "-c", code, str(ROOT), temp],
                                     stdout=subprocess.PIPE, text=True)
            owner.communicate(timeout=2)
            with self.assertRaises(TimeoutError):
                with SimulatorLease("next", exclusive=True, timeout=0.1, lock_root=Path(temp)):
                    pass
            with SimulatorLease("later", exclusive=True, timeout=2, lock_root=Path(temp)):
                pass


if __name__ == "__main__":
    unittest.main()
