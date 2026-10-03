#!/usr/bin/env python3
"""冻结R5清单并核对摘要；实际评估直接使用现有harness。"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPERIMENT = ROOT.parent
WORKSPACE = EXPERIMENT.parents[1]
sys.path.insert(0, str(EXPERIMENT / "harness"))
from common import file_sha256, tree_manifest

EXPECTED_IDS = {"baseline", "t", "d", "g", "p", "c", "w", "dp", "dg", "dt", "dpg", "dtgp", "dtgpcw"}
EXPECTED_CARDS = {"holdout-season", "holdout-stress"}
SINGLE_CASES = {"control", "T", "D", "G", "P", "C", "W"}
CORE_FILES = ("actions.jsonl", "score_report.json", "decisions.csv", "observations.csv")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seal_hashes(files):
    mapping = {item["relative_path"]: item["sha256"] for item in files}
    sealed = hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()
    canonical = "".join(f"{path}\0{digest}\n" for path, digest in sorted(mapping.items()))
    return sealed, hashlib.sha256(canonical.encode()).hexdigest()


def build_freeze(plan_path, manifest_path):
    require(not manifest_path.exists(), "冻结清单已存在，不覆盖或重建")
    plan = read(plan_path)
    candidates = plan["candidates"]
    require(len(candidates) == 13 and {row["id"] for row in candidates} == EXPECTED_IDS, "R5必须包含完整13配置")
    require(len(plan["cards"]) == 2 and set(plan["cards"]) == EXPECTED_CARDS, "R5必须使用原两保留卡")
    require(plan["wallclock_seconds"] == 900, "统一预算必须为900秒")
    snapshot_path = EXPERIMENT / "vendor/snapshot_manifest.json"
    snapshot = read(snapshot_path)
    require(plan["upstream_commit"] == snapshot["upstream_commit"], "固定commit不一致")
    require(tree_manifest(EXPERIMENT / "vendor/starter_kit_v4")["tree_sha256"] == snapshot["snapshot_tree_sha256"], "官方快照已变")
    sources = {row["source"]: tree_manifest(EXPERIMENT / row["source"]) for row in candidates}
    combined_hash = sources["agents/combined/source"]["tree_sha256"]
    equivalence_path = EXPERIMENT / plan["equivalence_report"]
    equivalence = read(equivalence_path)
    expected_pairs = {(case, card) for case in SINGLE_CASES for card in ("demo", "dev-season")}
    require(equivalence.get("all_equal") is True and len(equivalence["comparisons"]) == 14, "单开关等价证据不完整")
    require({(row["case"], row["card"]) for row in equivalence["comparisons"]} == expected_pairs, "等价验证案例不完整")
    require(equivalence["source_tree_sha256"] == combined_hash, "等价验证源码已过期")
    for row in equivalence["comparisons"]:
        require(row["all_core_files_equal"] is True and row["source_tree_sha256"] == combined_hash, "单开关等价失败")
        require(file_sha256(Path(row["config"])) == row["config_sha256"], "等价验证配置已变")
    registered = []
    for row in candidates:
        require(re.fullmatch(r"[a-z0-9-]+", row["id"]) is not None, "candidate id不合法")
        require(row["source"] == ("vendor/starter_kit_v4/agent" if row["id"] == "baseline" else "agents/combined/source"), "Agent来源不符合R5契约")
        config = EXPERIMENT / row["config"] if row["config"] else None
        config_hash = file_sha256(config) if config else hashlib.sha256(b"{}\n").hexdigest()
        if row["family"] in SINGLE_CASES:
            matches = [item for item in equivalence["comparisons"] if item["case"] == row["family"]]
            require(len(matches) == 2 and all(item["config_sha256"] == config_hash for item in matches), "冻结单项不同于已验收配置")
        evidence = []
        if len(row["family"]) > 1 and row["id"] != "baseline":
            for card in ("demo", "dev-season"):
                run_id = f"r4-{config.stem}-{card}"
                path = EXPERIMENT / "runs" / run_id / "manifest.json"
                run = read(path)
                require(run.get("status") == "completed" and run.get("official_termination_reason") == "survey_complete", f"R4尚未完整结束：{run_id}")
                require(run["source_tree_sha256"] == combined_hash and run["config_sha256"] == config_hash, "R4证据不同于冻结源码/配置")
                evidence.append({"run_id": run_id, "manifest_sha256": file_sha256(path)})
        registered.append({**row, "source_tree_sha256": sources[row["source"]]["tree_sha256"],
                           "config_sha256": config_hash, "development_evidence": evidence})
    seal_path = EXPERIMENT / plan["holdout_seal"]
    seal = read(seal_path)
    require(set(seal["holdout_card_ids"]) == EXPECTED_CARDS, "seal不是原两保留卡")
    cards = []
    for row in seal["cards"]:
        sealed, harness_tree = seal_hashes(row["files"])
        require(sealed == row["manifest_sha256"], "seal元数据摘要不一致")
        cards.append({**row, "harness_tree_sha256": harness_tree})
    matrix = []
    for row in registered:
        for card_id in plan["cards"]:
            card = next(item for item in cards if item["card_id"] == card_id)
            run_id = f"r5-{row['id']}-{card_id}"
            command = ["/usr/bin/python3", "-B", str(EXPERIMENT / "harness/run_one.py"),
                       "--run-id", run_id, "--stage", "R5", "--agent", str(EXPERIMENT / row["source"]),
                       "--card", str(WORKSPACE / card["local_path"]), "--wallclock", "900"]
            if row["config"]:
                command += ["--config", str(EXPERIMENT / row["config"])]
            matrix.append({"candidate": row["id"], "card": card_id, "run_id": run_id, "command": command})
    require(not any((EXPERIMENT / "runs" / pair["run_id"]).exists() for pair in matrix), "已有R5 run，不再新建冻结清单")
    selection_source = EXPERIMENT / plan["selection_document"]
    selection_snapshot = ROOT / "selection_snapshot/STUDY_DESIGN.md"
    require(not selection_snapshot.exists(), "选择依据快照已存在，不覆盖")
    selection_snapshot.parent.mkdir(parents=True, exist_ok=True)
    with selection_snapshot.open("xb") as handle:
        handle.write(selection_source.read_bytes())
    selection_snapshot.chmod(0o444)
    manifest = {"schema_version": "v4-r5-freeze-v1", "frozen_at_utc": now(), "plan": plan,
                "plan_path": str(plan_path.resolve()), "plan_sha256": file_sha256(plan_path),
                "upstream_commit": snapshot["upstream_commit"], "vendor_tree_sha256": snapshot["snapshot_tree_sha256"],
                "sources": sources, "candidates": registered, "cards": cards, "matrix": matrix,
                "holdout_seal_path": str(seal_path), "holdout_seal_sha256": file_sha256(seal_path),
                "selection_basis": {"original": str(selection_source), "snapshot": str(selection_snapshot),
                                    "sha256": file_sha256(selection_snapshot)},
                "equivalence_report": str(equivalence_path), "equivalence_report_sha256": file_sha256(equivalence_path),
                "harness_tree_sha256": tree_manifest(EXPERIMENT / "harness")["tree_sha256"],
                "evaluation_script_sha256": file_sha256(Path(__file__)),
                "authorization_status": "awaiting_Root_confirmation; manifest itself does not authorize opening"}
    save_new(manifest_path, manifest)
    manifest_path.chmod(0o444)
    return manifest


def verify(manifest, *, card_bytes=False):
    require(file_sha256(Path(manifest["plan_path"])) == manifest["plan_sha256"], "冻结计划已变")
    require(file_sha256(Path(__file__)) == manifest["evaluation_script_sha256"], "评估脚本已变")
    require(tree_manifest(EXPERIMENT / "harness")["tree_sha256"] == manifest["harness_tree_sha256"], "harness已变")
    require(tree_manifest(EXPERIMENT / "vendor/starter_kit_v4")["tree_sha256"] == manifest["vendor_tree_sha256"], "vendor已变")
    for source, recorded in manifest["sources"].items():
        require(tree_manifest(EXPERIMENT / source)["tree_sha256"] == recorded["tree_sha256"], "冻结源码已变：" + source)
    for row in manifest["candidates"]:
        if row["config"]:
            require(file_sha256(EXPERIMENT / row["config"]) == row["config_sha256"], "冻结配置已变：" + row["id"])
    require(file_sha256(Path(manifest["holdout_seal_path"])) == manifest["holdout_seal_sha256"], "seal记录已变")
    require(file_sha256(Path(manifest["selection_basis"]["snapshot"])) == manifest["selection_basis"]["sha256"], "选择依据快照已变")
    require(file_sha256(Path(manifest["equivalence_report"])) == manifest["equivalence_report_sha256"], "等价证据已变")
    if card_bytes:
        # 仅计算字节摘要；不解析、打印或分析天气/事件内容。
        for card in manifest["cards"]:
            root = WORKSPACE / card["local_path"]
            files = [{"relative_path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)}
                     for path in sorted(root.rglob("*")) if path.is_file()]
            sealed, harness_tree = seal_hashes(files)
            require(sealed == card["manifest_sha256"] and harness_tree == card["harness_tree_sha256"], "保留卡摘要已变：" + card["card_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--plan", type=Path, default=ROOT / "plan.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "freeze_manifest.json")
    parser.add_argument("--card-bytes", action="store_true", help="开封获准后仅校验卡片字节摘要，不解析内容")
    parser.add_argument("--run-id", help="跑后核对这个已登记R5 run的实际输入hash")
    args = parser.parse_args()
    if args.action == "freeze":
        result = build_freeze(args.plan.resolve(), args.manifest.resolve())
        print(json.dumps({"manifest": str(args.manifest.resolve()), "sha256": file_sha256(args.manifest),
                          "candidate_count": len(result["candidates"]), "run_count": len(result["matrix"])}))
    else:
        manifest = read(args.manifest)
        verify(manifest, card_bytes=args.card_bytes)
        if args.run_id:
            pair = next((pair for pair in manifest["matrix"] if pair["run_id"] == args.run_id), None)
            require(pair is not None, "run-id不在冻结清单")
            candidate = next(row for row in manifest["candidates"] if row["id"] == pair["candidate"])
            card = next(row for row in manifest["cards"] if row["card_id"] == pair["card"])
            actual = read(EXPERIMENT / "runs" / args.run_id / "manifest.json")
            require(actual["source_tree_sha256"] == candidate["source_tree_sha256"], "run源码与冻结值不符")
            require(actual["config_sha256"] == candidate["config_sha256"], "run配置与冻结值不符")
            require(actual["card_tree_sha256"] == card["harness_tree_sha256"], "run卡片与seal不符")
        print(json.dumps({"status": "passed", "card_content_hashed_only": args.card_bytes,
                          "run_id": args.run_id}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
