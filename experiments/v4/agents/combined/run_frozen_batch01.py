#!/usr/bin/env python3
"""执行主Agent冻结的R4批次；只接受明确登记的两批，不自动扩展。"""
from __future__ import annotations

import json
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPERIMENT = ROOT.parents[1]
WORKSPACE = EXPERIMENT.parents[1]
sys.path.insert(0, str(EXPERIMENT / "harness"))
from common import file_sha256, tree_manifest, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=("01", "02"), default="01")
    args = parser.parse_args()
    names = ("dp", "dg", "dt") if args.batch == "01" else ("dpg", "dtgp", "dtgpcw")
    proof = json.loads((ROOT / "validation/equivalence.json").read_text())
    required = {(case, card) for case in ("control", "T", "D", "G", "C", "W", "P")
                for card in ("demo", "dev-season")}
    found = {(row["case"], row["card"]) for row in proof["comparisons"] if row["all_core_files_equal"]}
    source_hash = tree_manifest(ROOT / "source")["tree_sha256"]
    if not proof["all_equal"] or found != required or source_hash != proof["source_tree_sha256"]:
        raise SystemExit("全关/六个单项两卡的当前源码等价验收尚未全部通过")
    for row in proof["comparisons"]:
        if file_sha256(Path(row["config"])) != row["config_sha256"]:
            raise SystemExit("原单项配置已变化，等价证明过期")
    config_paths = {name: EXPERIMENT / f"configs/combined/{name}-frozen{args.batch}.json" for name in names}
    freeze_path = ROOT / f"validation/frozen_batch{args.batch}.json"
    frozen = {"source_tree_sha256": source_hash,
              "configs": {name: {"path": str(path), "sha256": file_sha256(path)} for name, path in config_paths.items()},
              "scope": f"root-authorized R4 batch{args.batch}: {','.join(names)}; each on demo and dev-season; no tuning or holdout"}
    if freeze_path.exists() and json.loads(freeze_path.read_text()) != frozen:
        raise SystemExit("首批冻结hash已变化，拒绝继续同名run")
    write_json(freeze_path, frozen)
    results = []
    for name, config in config_paths.items():
        for card in ("demo", "dev-season"):
            run_id = f"r4-{name}-frozen{args.batch}-{card}"
            run = EXPERIMENT / "runs" / run_id
            card_dir = (EXPERIMENT / "vendor/starter_kit_v4/cards/demo" if card == "demo"
                        else EXPERIMENT / "data/cards/dev-season")
            command = ["/usr/bin/python3", "-B", str(EXPERIMENT / "harness/run_one.py"),
                       "--run-id", run_id, "--stage", "R4", "--agent", str(ROOT / "source"),
                       "--config", str(config), "--card", str(card_dir), "--exclusive"]
            if not run.exists():
                completed = subprocess.run(command, cwd=WORKSPACE)
                if completed.returncode:
                    raise SystemExit(completed.returncode)
            manifest = json.loads((run / "manifest.json").read_text())
            if manifest["source_tree_sha256"] != source_hash or manifest["config_sha256"] != frozen["configs"][name]["sha256"]:
                raise SystemExit(f"已有run与冻结源码/配置不符：{run_id}")
            if manifest["status"] != "completed" or manifest["termination_reason"] != "survey_complete":
                raise SystemExit(f"run未完整完成，不作策略结论：{run_id}")
            results.append({"combination": name.upper(), "card": card, "run_id": run_id,
                            "metrics": json.loads((run / "metrics.json").read_text())})
            write_json(ROOT / f"validation/batch{args.batch}_results.json", {"frozen": frozen, "results": results,
                       "complete": len(results) == 6})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
