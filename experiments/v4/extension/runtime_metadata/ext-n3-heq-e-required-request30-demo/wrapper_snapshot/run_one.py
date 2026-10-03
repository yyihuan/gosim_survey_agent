#!/usr/bin/env python3
"""本轮薄包装：原run/metrics原样执行，只替换为独立六槽锁并归档包装证据。"""
import argparse
import datetime
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
V4 = EXTENSION.parent
sys.path.insert(0, str(V4 / "harness"))
import run as original
from common import file_sha256, tree_manifest, write_json
import extension_lease


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run-id"); parser.add_argument("--stage"); parser.add_argument("--card", type=Path)
    known, _ = parser.parse_known_args(argv)
    if "--help" in argv or "-h" in argv:
        return original.main(argv)
    if not known.run_id or not re.fullmatch(r"ext-[A-Za-z0-9_.-]+", known.run_id):
        parser.error("本轮run-id必须为唯一ext-*，不能写旧run目录")
    if known.stage not in ("N1", "N2", "N3", "N4", "N5", "integration-verification"):
        parser.error("stage须为N1/N2/N3/N4/N5或integration-verification")
    card = (known.card or V4 / "vendor/starter_kit_v4/cards/demo").resolve()
    development = {(V4 / "vendor/starter_kit_v4/cards/demo").resolve(), (V4 / "data/cards/dev-season").resolve()}
    holdout_root = (EXTENSION / "data/cards").resolve()
    if card not in development:
        if card.parent != holdout_root or card.name not in {"ext-holdout-" + letter for letter in "abcd"}:
            parser.error("本轮只允许demo/dev-season或预注册四张新保留卡；不运行α–δ")
        authorization = EXTENSION / "evaluation/N5_AUTHORIZATION.json"
        if known.stage != "N5" or not authorization.is_file():
            parser.error("新保留卡封存；必须等Root明确冻结并写N5_AUTHORIZATION.json")
        permitted = json.loads(authorization.read_text())
        if permitted.get("authorized_by") != "Root" or known.run_id not in permitted.get("authorized_run_ids", []):
            parser.error("当前run-id不在Root冻结的N5授权清单")
    if (V4 / "runs" / known.run_id).exists():
        parser.error("run目录已经存在，拒绝覆盖")
    record = EXTENSION / "runtime_metadata" / known.run_id
    record.mkdir(parents=True, exist_ok=False)
    hashes = {}
    snapshot = record / "wrapper_snapshot"; snapshot.mkdir()
    for path in (Path(__file__).resolve(), Path(extension_lease.__file__).resolve()):
        raw = path.read_bytes()
        target = snapshot / path.name
        target.write_bytes(raw); target.chmod(0o444)
        hashes[path.name] = file_sha256(path)
    snapshot.chmod(0o555)
    evidence = {"schema_version": "v4-extension-wrapper-v1", "run_id": known.run_id,
                "started_at_utc": now(), "command": [sys.executable, "-B", str(Path(__file__).resolve()), *argv],
                "cwd": str(Path.cwd()), "wrapper_source_sha256": hashes,
                "original_harness_tree_sha256": tree_manifest(V4 / "harness")["tree_sha256"],
                "simulator_limit": 6, "lock_namespace": str(extension_lease.LOCK_ROOT),
                "runner_and_metrics": "unchanged experiments/v4/harness/run.py and metrics.py",
                "status": "running", "original_harness_files_modified": False}
    write_json(record / "launcher.json", evidence)
    # 模块对象只存在于本次独立Python进程；不改变原文件或其它worker的锁。
    original.SimulatorLease = extension_lease.SixSlotLease
    result = original.main(argv)
    evidence.update(status="completed" if result == 0 else "launcher_returned_nonzero",
                    exit_code=result, finished_at_utc=now())
    evidence["wrapper_source_unchanged_after_run"] = all(file_sha256(HERE / name) == value for name, value in hashes.items())
    evidence["original_harness_unchanged_after_run"] = tree_manifest(V4 / "harness")["tree_sha256"] == evidence["original_harness_tree_sha256"]
    write_json(record / "launcher.json", evidence)
    run = V4 / "runs" / known.run_id
    if (run / "manifest.json").is_file():
        manifest = json.loads((run / "manifest.json").read_text())
        manifest["extension_wrapper"] = evidence
        write_json(run / "manifest.json", manifest)
        # 每run保留本轮包装源码，原始官方输出及metrics值保持不动。
        from shutil import copytree
        copytree(snapshot, run / "extension_wrapper_snapshot")
        (run / "extension_wrapper_snapshot").chmod(0o555)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
