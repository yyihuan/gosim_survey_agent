#!/usr/bin/env python3
"""仅执行已冻结三策略×四官方卡；使用未改harness，独立保存外部评估结果。"""
import concurrent.futures
import csv
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent
WORKSPACE = V4.parents[1]
sys.path.insert(0, str(V4 / "harness"))
from common import file_sha256, tree_manifest

LOCK = threading.Lock()
STOP = threading.Event()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def journal(value):
    with LOCK, (ROOT / "execution.jsonl").open("a") as handle:
        handle.write(json.dumps({"at_utc": now(), **value}, ensure_ascii=False) + "\n")


def verify(frozen):
    selection = frozen["selection"]
    assert file_sha256(ROOT / "selection_frozen.json") == frozen["selection_sha256"], "selection drift"
    assert file_sha256(ROOT / "card_inventory.json") == frozen["card_inventory_sha256"], "inventory drift"
    assert tree_manifest(V4 / "harness")["tree_sha256"] == selection["harness_tree_sha256"], "harness drift"
    assert tree_manifest(V4 / "vendor/starter_kit_v4")["tree_sha256"] == selection["vendor_tree_sha256"], "vendor drift"
    for candidate in selection["candidates"]:
        assert tree_manifest(WORKSPACE / candidate["source"])["tree_sha256"] == candidate["source_tree_sha256"], "source drift"
        value = file_sha256(WORKSPACE / candidate["config"]) if candidate["config"] else hashlib.sha256(b"{}\n").hexdigest()
        assert value == candidate["config_sha256"], "config drift"
    for card in frozen["cards"]:
        assert tree_manifest(ROOT / card["local_path"])["tree_sha256"] == card["tree_sha256"], "card drift"
    for path, value in selection["protected_old_artifact_sha256"].items():
        assert file_sha256(WORKSPACE / path) == value, "old artifact drift: " + path


def run_one(item, frozen):
    if STOP.is_set():
        return {**item, "executed": False, "execution_error": "stopped after input drift"}
    try:
        verify(frozen)
    except Exception:
        STOP.set()
        raise
    run = V4 / "runs" / item["run_id"]
    if run.exists():
        STOP.set()
        raise ValueError("run目录已存在，拒绝覆盖：" + item["run_id"])
    journal({"event": "run_started", "run_id": item["run_id"], "candidate": item["candidate"],
             "card": item["card"], "command": item["command"], "cwd": str(WORKSPACE), "pre_hash_check": True})
    log = ROOT / "execution_logs" / (item["run_id"] + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("x") as handle:
        process = subprocess.run(item["command"], cwd=WORKSPACE, stdout=handle, stderr=subprocess.STDOUT)
    try:
        verify(frozen)
    except Exception:
        STOP.set()
        raise
    manifest = read(run / "manifest.json")
    metrics = read(run / "metrics.json")
    candidate = next(candidate for candidate in frozen["selection"]["candidates"] if candidate["id"] == item["candidate"])
    card = next(card for card in frozen["cards"] if card["card_id"] == item["card"])
    assert manifest["source_tree_sha256"] == candidate["source_tree_sha256"]
    assert manifest["config_sha256"] == candidate["config_sha256"]
    assert manifest["card_tree_sha256"] == card["tree_sha256"]
    assert manifest["harness_tree_sha256"] == frozen["selection"]["harness_tree_sha256"]
    assert manifest["llm_enabled"] is False
    assert manifest["requested_wallclock_seconds"] == 900
    errors = []
    internal_errors = 0
    for path in (run / "runner_stderr.log", run / "output/agent.log", log):
        if path.exists():
            text = path.read_text(errors="replace")
            internal_errors += text.count("baseline: error")
            if "Traceback (most recent call last)" in text:
                errors.append(str(path.relative_to(V4)))
    raw_hashes_passed = all(file_sha256(run / "output" / name) == value
                            for name, value in metrics["hashes"]["raw_outputs"].items())
    journal({"event": "run_completed", "run_id": item["run_id"], "exit_code": process.returncode,
             "status": manifest["status"], "termination_reason": metrics["termination_reason"],
             "runtime_seconds": metrics["runtime_seconds"], "pace_change_count": metrics["pace"]["change_count"],
             "post_hash_check": True, "raw_output_hashes_passed": raw_hashes_passed})
    print(json.dumps({"run_id": item["run_id"], "total": metrics["total"], "status": manifest["status"],
                      "termination": metrics["termination_reason"], "runtime_seconds": metrics["runtime_seconds"]},
                     ensure_ascii=False), flush=True)
    return {**item, "executed": True, "manifest": manifest, "metrics": metrics,
            "internal_error_count": internal_errors, "traceback_files": errors,
            "wrapper_exit_code": process.returncode, "raw_output_hashes_passed": raw_hashes_passed,
            "artifact_sha256": {name: file_sha256(run / name) for name in ("manifest.json", "metrics.json", "output/score_report.json")}}


def row(result):
    metrics = result["metrics"]; manifest = result["manifest"]
    components = metrics["components"]; counts = metrics["counts"]
    run_relative = "../runs/" + result["run_id"]
    return {"run_id": result["run_id"], "stage": "R6-external", "stage_group": "R6-external",
            "experiment_category": "official_external_evaluation", "candidate": result["candidate"],
            "family": {"baseline": "baseline", "d": "D", "dtgp": "DTGP"}[result["candidate"]],
            "card": result["card"], "card_source": "official_public_bundle",
            "card_nights": metrics["card"]["night_count"], "card_targets": metrics["card"]["target_count"],
            "total": metrics["total"], "score_available": metrics["official_report_available"],
            "science": components["sum_best_scores"], "components": components,
            "required_missing": counts["required_missing"], "coverage_jain": metrics["coverage"]["jain_from_official_penalty"],
            "request_issued": counts["observation_requests_issued"], "request_completed": counts["observation_requests_completed"],
            "report_count": metrics["reports"]["count"], "report_correct": metrics["reports"]["correct"],
            "report_false": metrics["reports"]["false"], "observe_actions": counts["observe_actions"],
            "targets_observed": counts["targets_observed"], "runtime_seconds": metrics["runtime_seconds"],
            "runtime_with_setup_seconds": metrics["runtime_with_setup_seconds"],
            "accounted_wallclock_seconds": metrics["accounted_wallclock_seconds"],
            "global_wallclock_seconds": metrics["global_wallclock_seconds"],
            "pace_change_count": metrics["pace"]["change_count"], "pace_changes": metrics["pace"]["changes_logged"],
            "pace_telemetry_available": metrics["pace"]["telemetry_available"],
            "pace_minimum_remaining_seconds": metrics["pace"]["minimum_remaining_wallclock_seconds"],
            "run_status": manifest["status"], "exit_code": manifest["exit_code"],
            "process_complete": manifest["status"] == "completed" and manifest["exit_code"] == 0,
            "full_season_complete": metrics["termination_reason"] == "survey_complete" and manifest["exit_code"] == 0,
            "termination_reason": metrics["termination_reason"], "termination_detail": metrics["termination_detail"],
            "internal_error_count": result["internal_error_count"], "traceback_files": result["traceback_files"],
            "error": bool(result["internal_error_count"] or result["traceback_files"] or result["wrapper_exit_code"]),
            "hash_checks_passed": True, "raw_output_hashes_passed": result["raw_output_hashes_passed"],
            "source_tree_sha256": manifest["source_tree_sha256"], "config_sha256": manifest["config_sha256"],
            "card_tree_sha256": manifest["card_tree_sha256"], "harness_tree_sha256": manifest["harness_tree_sha256"],
            "start_utc": manifest["start_utc"], "end_utc": manifest["end_utc"],
            "command": result["command"], "concurrency": manifest["concurrency"],
            "artifact_sha256": result["artifact_sha256"],
            "evidence_links": {"run": run_relative, "manifest": run_relative + "/manifest.json",
                               "metrics": run_relative + "/metrics.json", "score_report": run_relative + "/output/score_report.json",
                               "actions": run_relative + "/output/actions.jsonl", "decisions": run_relative + "/output/decisions.csv",
                               "agent_log": run_relative + "/output/agent.log"}}


def main():
    selection = read(ROOT / "selection_frozen.json")
    inventory = read(ROOT / "card_inventory.json")
    assert inventory["all_four_verified"] and inventory["distinct_cards_by_manifest"] == 4
    assert len(selection["matrix"]) == 12
    frozen = {"schema_version": "v4-external-freeze-v1", "frozen_at_utc": now(), "selection": selection,
              "selection_sha256": file_sha256(ROOT / "selection_frozen.json"),
              "card_inventory_sha256": file_sha256(ROOT / "card_inventory.json"),
              "executor_sha256": file_sha256(Path(__file__)), "cards": []}
    for card in inventory["cards"]:
        assert card["verified"]
        frozen["cards"].append({"card_id": card["card_id"], "local_path": card["local_path"],
                                "tree_sha256": tree_manifest(ROOT / card["local_path"])["tree_sha256"],
                                "bundle_manifest_sha256": card["bundle_manifest_sha256"]})
    save_new(ROOT / "freeze_manifest.json", frozen)
    (ROOT / "freeze_manifest.json").chmod(0o444)
    verify(frozen)
    journal({"event": "evaluation_started", "expected_runs": 12, "maximum_concurrency": 2,
             "freeze_manifest_sha256": file_sha256(ROOT / "freeze_manifest.json")})
    outcomes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_one, item, frozen) for item in selection["matrix"]]
        for future in futures:
            outcomes.append(future.result())
    verify(frozen)
    rows = [row(outcome) for outcome in outcomes]
    baselines = {item["card"]: item for item in rows if item["candidate"] == "baseline"}
    for item in rows:
        item["delta_total_vs_baseline"] = item["total"] - baselines[item["card"]]["total"]
        item["baseline_run_id"] = baselines[item["card"]]["run_id"]
    values = {"schema_version": "v4-official-external-results-v1", "created_at_utc": now(), "row_count": len(rows),
              "expected_runs": 12, "executed_runs": len(rows), "complete_runs": sum(item["full_season_complete"] for item in rows),
              "cards": inventory["cards"], "card_source": "official_public_storage; checksum matches fixed official snapshot",
              "selection_file": "selection_frozen.json", "selection_sha256": frozen["selection_sha256"],
              "freeze_manifest": "freeze_manifest.json", "freeze_manifest_sha256": file_sha256(ROOT / "freeze_manifest.json"),
              "execution_journal": "execution.jsonl", "maximum_simultaneous_runs": 2,
              "pre_and_post_freeze_checks_passed": True, "protected_old_artifacts_unchanged": True,
              "pace_change_count": sum(item["pace_change_count"] for item in rows),
              "internal_error_count": sum(item["internal_error_count"] for item in rows),
              "traceback_files": [path for item in rows for path in item["traceback_files"]],
              "no_retries_or_extra_configuration": True, "rows": rows,
              "definitions": {"total": "official score_report total; no rescoring", "science": "official sum_best_scores",
                              "coverage_jain": "1 + official uniformity penalty / public weight; rounded score limit applies",
                              "delta_total_vs_baseline": "same-card official baseline subtraction",
                              "evidence_links": "paths relative to external_evaluation directory",
                              "pace": "agent log changes and decision_request remaining-wallclock telemetry",
                              "selection": "fixed three before any official-card score; preserve all twelve; no ranking or parameter changes"},
              "boundaries": selection["boundaries"]}
    save_new(ROOT / "results.json", values)
    columns = ["run_id", "candidate", "family", "card", "card_nights", "card_targets", "total", "science",
               "required_missing", "coverage_jain", "request_issued", "request_completed", "report_count", "report_correct",
               "report_false", "full_season_complete", "runtime_seconds", "accounted_wallclock_seconds", "pace_change_count",
               "internal_error_count", "error", "exit_code", "run_status", "termination_reason", "delta_total_vs_baseline",
               "baseline_run_id", "source_tree_sha256", "config_sha256", "card_tree_sha256", "hash_checks_passed", "artifact_path"]
    with (ROOT / "results.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for item in rows:
            writer.writerow({key: item["evidence_links"]["run"] if key == "artifact_path" else item.get(key) for key in columns})
    journal({"event": "evaluation_completed", "complete_runs": values["complete_runs"], "freeze_checks_passed": True,
             "results_json_sha256": file_sha256(ROOT / "results.json"), "results_csv_sha256": file_sha256(ROOT / "results.csv")})
    print(json.dumps({key: values[key] for key in ("expected_runs", "executed_runs", "complete_runs", "pace_change_count", "internal_error_count")}), flush=True)
    return 0 if values["complete_runs"] == 12 else 1


if __name__ == "__main__":
    raise SystemExit(main())
