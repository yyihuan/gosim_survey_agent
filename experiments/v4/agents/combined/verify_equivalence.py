#!/usr/bin/env python3
"""只验证全关和单家族等价性；不创建或执行多家族组合配置。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPERIMENT = ROOT.parents[1]
WORKSPACE = EXPERIMENT.parents[1]
sys.path.insert(0, str(EXPERIMENT / "harness"))
from common import file_sha256, tree_manifest, write_json

CASES = {
    "control": ("tdg/neutral-control.json", "r1-harness-demo", "r1-official-dev-season"),
    "T": ("tdg/t-cap900-conditional.json", "r3-t-cap900-conditional-demo", "r3-t-cap900-conditional-dev-season"),
    "D": ("tdg/d-linear.json", "r2-d-linear-demo", "r2-d-linear-dev-season"),
    "G": ("tdg/g-soft05.json", "r2-g-soft05-demo", "r2-g-soft05-dev-season"),
    "C": ("cw/c-soft06.json", "r2-c-soft06-demo", "r2-c-soft06-dev-season"),
    "W": ("cw/w-forecast02.json", "r2-w-forecast02-demo", "r2-w-forecast02-dev-season"),
    "P": ("packing/p12.json", "r3-p-p12-demo", "r3-p-p12-dev-season"),
}
CORE_FILES = ("actions.jsonl", "score_report.json", "decisions.csv", "observations.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="运行缺少的单家族验证；已存在run只读取")
    parser.add_argument("--case", action="append", choices=CASES, help="省略时验证全关和六家族")
    parser.add_argument("--card", action="append", choices=("demo", "dev-season"))
    args = parser.parse_args()
    comparisons = []
    for case in args.case or CASES:
        config_relative, demo_reference, dev_reference = CASES[case]
        config = EXPERIMENT / "configs" / config_relative
        for card in args.card or ("demo", "dev-season"):
            run_id = f"r4-equivalence-{case.lower()}-{card}"
            run = EXPERIMENT / "runs" / run_id
            reference = EXPERIMENT / "runs" / (demo_reference if card == "demo" else dev_reference)
            card_dir = (EXPERIMENT / "vendor/starter_kit_v4/cards/demo" if card == "demo"
                        else EXPERIMENT / "data/cards/dev-season")
            command = ["/usr/bin/python3", "-B", str(EXPERIMENT / "harness/run_one.py"),
                       "--run-id", run_id, "--stage", "integration-verification",
                       "--agent", str(ROOT / "source"), "--config", str(config),
                       "--card", str(card_dir), "--exclusive"]
            if not run.exists() and args.execute:
                result = subprocess.run(command, cwd=WORKSPACE)
                if result.returncode:
                    raise SystemExit(result.returncode)
            if not (run / "output/score_report.json").is_file():
                raise SystemExit(f"缺少验证输出：{run}; 使用 --execute 显式运行")
            manifest = json.loads((run / "manifest.json").read_text())
            if manifest["source_tree_sha256"] != tree_manifest(ROOT / "source")["tree_sha256"]:
                raise SystemExit(f"当前源码已不同于旧验证run：{run}; 不复用过期证明")
            if manifest["config_sha256"] != file_sha256(config):
                raise SystemExit(f"当前配置已不同于旧验证run：{run}")
            match = {name: {"same_bytes": (run / "output" / name).read_bytes() == (reference / "output" / name).read_bytes(),
                            "combined_sha256": file_sha256(run / "output" / name),
                            "reference_sha256": file_sha256(reference / "output" / name)} for name in CORE_FILES}
            metrics = json.loads((run / "metrics.json").read_text())
            comparisons.append({"case": case, "card": card, "run_id": run_id, "reference": str(reference),
                                "config": str(config), "config_sha256": file_sha256(config),
                                "source_tree_sha256": manifest["source_tree_sha256"],
                                "command": command, "total": metrics["total"],
                                "runtime_seconds": metrics["runtime_seconds"], "files": match,
                                "all_core_files_equal": all(value["same_bytes"] for value in match.values())})
            print(json.dumps({"case": case, "card": card,
                              "all_core_files_equal": comparisons[-1]["all_core_files_equal"]}, sort_keys=True), flush=True)
    artifact = {"schema_version": "combined-equivalence-v1", "source": str(ROOT / "source"),
                "source_tree_sha256": tree_manifest(ROOT / "source")["tree_sha256"],
                "comparisons": comparisons, "all_equal": all(row["all_core_files_equal"] for row in comparisons),
                "scope": "all-off and one active family on each development card; no multi-family combinations or holdout"}
    write_json(ROOT / "validation/equivalence.json", artifact)
    return 0 if artifact["all_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
