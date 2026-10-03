#!/usr/bin/env python3
"""实际调用官方local_runner验证手动四卡；拒绝时不生成策略成绩。"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent
WORKSPACE = V4.parents[1]
sys.path.insert(0, str(V4 / "harness"))
from common import copy_snapshot, file_sha256, tree_manifest


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main():
    old = json.loads((V4 / "external_evaluation/selection_frozen.json").read_text())
    imported = json.loads((ROOT / "card_inventory.json").read_text())
    for candidate in old["candidates"]:
        assert tree_manifest(WORKSPACE / candidate["source"])["tree_sha256"] == candidate["source_tree_sha256"]
        config_hash = file_sha256(WORKSPACE / candidate["config"]) if candidate["config"] else hashlib.sha256(b"{}\n").hexdigest()
        assert config_hash == candidate["config_sha256"]
    assert tree_manifest(V4 / "harness")["tree_sha256"] == old["harness_tree_sha256"]
    assert tree_manifest(V4 / "vendor/starter_kit_v4")["tree_sha256"] == old["vendor_tree_sha256"]
    protected = dict(old["protected_old_artifact_sha256"])
    for path in (V4 / "external_evaluation/results.json", V4 / "external_evaluation/results.csv"):
        protected[str(path.relative_to(WORKSPACE))] = file_sha256(path)
    frozen = {"schema_version": "v4-manual-selection-v1", "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "candidates": old["candidates"], "cards": [{key: card[key] for key in ("card_id", "archive", "archive_sha256", "tree_sha256")}
                                                       for card in imported["cards"]],
              "harness_tree_sha256": old["harness_tree_sha256"], "vendor_tree_sha256": old["vendor_tree_sha256"],
              "protected_old_artifact_sha256": protected, "stage": "R7-manual-official", "expected_strategy_runs": 12,
              "concurrency_authorization": {"strategy_groups": 3, "cards_serial_per_strategy": True,
                                             "preferred_simulators": 3, "maximum_if_resources_allow": 6,
                                             "old_two_slot_harness_not_used_for_three_concurrent_claim": True,
                                             "wrapper_created": False, "reason": "only implement new execution scheduling if official local bundle passes validation"},
              "scope": "local import and exact official execution feasibility; no actual upload, online session, model call, tuning, or fabricated weather",
              "selection_basis": "user preserves previously frozen official baseline, D linear, DTGP; fixed before any four-card score"}
    save_new(ROOT / "selection_frozen.json", frozen)
    (ROOT / "selection_frozen.json").chmod(0o444)
    rows = []
    for card in imported["cards"]:
        name = card["card_id"]
        run = ROOT / "preflight" / ("r7-preflight-official-" + name)
        run.mkdir(parents=True, exist_ok=False)
        copy_snapshot(V4 / "vendor/starter_kit_v4/agent", run / "agent", readonly=False)
        command = ["/usr/bin/python3", "-B", str(V4 / "vendor/starter_kit_v4/local_runner.py"),
                   "--agent", str(run / "agent"), "--card", str(ROOT / "cards" / name),
                   "--out", str(run / "output"), "--python", "/usr/bin/python3", "--wallclock", "900", "--quiet"]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        began = time.monotonic()
        with (run / "stdout.log").open("x") as stdout, (run / "stderr.log").open("x") as stderr:
            result = subprocess.run(command, cwd=WORKSPACE, stdout=stdout, stderr=stderr, timeout=30,
                                    env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "USE_LLM": "0", "PYTHONDONTWRITEBYTECODE": "1"})
        text = (run / "stderr.log").read_text()
        assert result.returncode == 1 and "ValueError: bundle product '../public/v4_bulletins.jsonl' is missing or outside the bundle" in text
        assert not (run / "output").exists(), "拒绝应发生在output/Agent启动之前"
        assert tree_manifest(ROOT / "cards" / name)["tree_sha256"] == card["tree_sha256"]
        assert file_sha256(WORKSPACE / card["archive"]) == card["archive_sha256"]
        row = {"preflight_id": run.name, "card": name, "command": command, "cwd": str(WORKSPACE),
               "started_at_utc": started, "finished_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "runtime_seconds": time.monotonic() - began, "python_version": subprocess.check_output(["/usr/bin/python3", "--version"], text=True).strip(),
               "exit_code": result.returncode, "status": "official_bundle_validation_rejected",
               "exception": "ValueError: bundle product '../public/v4_bulletins.jsonl' is missing or outside the bundle",
               "agent_process_started": False, "official_score_available": False, "total": None,
               "stdout_sha256": file_sha256(run / "stdout.log"), "stderr_sha256": file_sha256(run / "stderr.log"),
               "evidence_path": str(run.relative_to(ROOT))}
        save_new(run / "manifest.json", row)
        rows.append(row)
        print(json.dumps({key: row[key] for key in ("preflight_id", "exit_code", "status", "runtime_seconds")}), flush=True)
    checks = {path: file_sha256(WORKSPACE / path) == value for path, value in protected.items()}
    assert all(checks.values())
    assert tree_manifest(V4 / "harness")["tree_sha256"] == frozen["harness_tree_sha256"]
    assert tree_manifest(V4 / "vendor/starter_kit_v4")["tree_sha256"] == frozen["vendor_tree_sha256"]
    for candidate in frozen["candidates"]:
        assert tree_manifest(WORKSPACE / candidate["source"])["tree_sha256"] == candidate["source_tree_sha256"]
        value = file_sha256(WORKSPACE / candidate["config"]) if candidate["config"] else hashlib.sha256(b"{}\n").hexdigest()
        assert value == candidate["config_sha256"]
    save_new(ROOT / "preflight_results.json", {"schema_version": "v4-official-local-preflight-v1", "rows": rows,
                                                "tested_cards": 4, "accepted_cards": 0, "strategy_score_runs": 0,
                                                "frozen_inputs_unchanged": True, "old_artifact_hash_checks": checks,
                                                "interpretation": "actual official startup validation, not twelve failed strategy runs; no Agent started"})


if __name__ == "__main__":
    main()
