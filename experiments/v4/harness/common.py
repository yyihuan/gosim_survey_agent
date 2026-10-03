"""v4 实验的快照、摘要和进程锁；仅使用标准库。"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = HARNESS_ROOT.parent
KIT_ROOT = EXPERIMENT_ROOT / "vendor" / "starter_kit_v4"
SKIP_NAMES = {"__pycache__", ".git", ".env", ".DS_Store", ".locks"}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_manifest(root: Path) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_NAMES for part in rel.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"快照不接受符号链接：{path}")
        if path.is_file():
            files.append({"path": rel.as_posix(), "bytes": path.stat().st_size,
                          "sha256": file_sha256(path)})
    canonical = "".join(f"{item['path']}\0{item['sha256']}\n" for item in files)
    return {"tree_sha256": hashlib.sha256(canonical.encode()).hexdigest(), "files": files,
            "hash_definition": "sha256(sorted(relative_path NUL file_sha256 LF)); excludes bytecode, .git, .env"}


def copy_snapshot(source: Path, destination: Path, *, readonly: bool = True) -> dict:
    before = tree_manifest(source)
    shutil.copytree(source, destination,
                    ignore=shutil.ignore_patterns(*SKIP_NAMES, "*.pyc"))
    after = tree_manifest(destination)
    if before["tree_sha256"] != after["tree_sha256"]:
        raise ValueError(f"复制期间源文件发生变化：{source}")
    for path in destination.rglob("*"):
        path.chmod(0o555 if path.is_dir() and readonly else
                   0o444 if readonly else 0o755 if path.is_dir() else 0o644)
    destination.chmod(0o555 if readonly else 0o755)
    return after


class SimulatorLease:
    """所有 worker 共用两槽 flock；exclusive 原子取得两槽。"""

    def __init__(self, run_id: str, *, exclusive: bool = False, timeout: float = 1800,
                 lock_root: Path | None = None):
        self.run_id = run_id
        self.exclusive = exclusive
        self.timeout = timeout
        self.root = lock_root or HARNESS_ROOT / ".locks"
        self.handles = []
        self.wait_seconds = 0.0
        self.conditions = {}

    @property
    def fds(self) -> tuple[int, ...]:
        return tuple(handle.fileno() for _, handle in self.handles)

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        while True:
            held = []
            peers = []
            with (self.root / "gate.lock").open("a+") as gate:
                fcntl.flock(gate, fcntl.LOCK_EX)
                for index in range(2):
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
                enough = len(held) == 2 if self.exclusive else bool(held)
                if enough:
                    self.handles = held if self.exclusive else held[:1]
                    for _, handle in held[len(self.handles):]:
                        fcntl.flock(handle, fcntl.LOCK_UN)
                        handle.close()
                    self.wait_seconds = time.monotonic() - started
                    for index, handle in self.handles:
                        handle.seek(0)
                        handle.truncate()
                        json.dump({"run_id": self.run_id, "harness_pid": os.getpid(),
                                   "slot": index, "exclusive": self.exclusive}, handle)
                        handle.flush()
                    self.conditions = {"simulator_limit": 2, "exclusive": self.exclusive,
                                       "slots": [index for index, _ in self.handles],
                                       "peers_at_acquisition": peers,
                                       "cpu_count": os.cpu_count(), "load_average": os.getloadavg(),
                                       "lock_wait_seconds": self.wait_seconds}
                    return self
                for _, handle in held:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    handle.close()
            if time.monotonic() - started >= self.timeout:
                raise TimeoutError(f"等待 simulator 锁超过 {self.timeout:g} 秒")
            time.sleep(0.1)

    def __exit__(self, *_):
        # 调用方只在 runner 已退出后释放；锁 fd 同时传入 runner，防 harness 意外退出。
        for _, handle in self.handles:
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        self.handles = []
