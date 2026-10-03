#!/usr/bin/env python3
"""为未取得完整官方卡的固定评估保存准确状态；不运行评分器。"""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent
WORKSPACE = V4.parents[1]
sys.path.insert(0, str(V4 / "harness"))
from common import file_sha256, tree_manifest


def save_new(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def main():
    selection = json.loads((ROOT / "selection_frozen.json").read_text())
    inventory = json.loads((ROOT / "card_inventory_complete.json").read_text())
    assert not any(card["verified"] for card in inventory["cards"]), "有完整卡，应改为执行它们而非归档全阻塞"
    checks = {"harness": tree_manifest(V4 / "harness")["tree_sha256"] == selection["harness_tree_sha256"],
              "vendor": tree_manifest(V4 / "vendor/starter_kit_v4")["tree_sha256"] == selection["vendor_tree_sha256"]}
    for candidate in selection["candidates"]:
        checks["source_" + candidate["id"]] = tree_manifest(WORKSPACE / candidate["source"])["tree_sha256"] == candidate["source_tree_sha256"]
        value = file_sha256(WORKSPACE / candidate["config"]) if candidate["config"] else hashlib.sha256(b"{}\n").hexdigest()
        checks["config_" + candidate["id"]] = value == candidate["config_sha256"]
    for path, value in selection["protected_old_artifact_sha256"].items():
        checks[path] = file_sha256(WORKSPACE / path) == value
    assert all(checks.values()), checks
    evidence = []
    for path in sorted((ROOT / "acquisition/collect01").glob("missing-*-attempt1.json")):
        record = json.loads(path.read_text())
        body = json.loads(record["body"])
        assert record["http_status"] == 400 and body["statusCode"] == "404" and body["code"] == "NoSuchKey"
        evidence.append({"url": record["url"], "http_status": record["http_status"], "body_status_code": body["statusCode"],
                         "body_code": body["code"], "body_message": body["message"],
                         "path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)})
    assert len(evidence) == 30
    cards = [{**card, "official_checksum_verification_status": "blocked_incomplete_bundle",
              "checksum_mismatch_interpretation": "partial six-file manifest differs; full bundle checksum cannot yet be checked"}
             for card in inventory["cards"]]
    diagnosis = {"schema_version": "v4-external-availability-diagnosis-v1", "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "status": "blocked_incomplete_official_cards", "cards": cards, "missing_object_evidence": evidence,
                 "confirmed": ["four cards each expose six files through anonymous storage listing",
                               "config has three files; public has footprint, targets, night_calendar only; truth listing returns []",
                               "all thirty expected missing objects were requested once; HTTP 400 with body 404/NoSuchKey; no new timeout or explicit 403",
                               "public scenario-table metadata request returns HTTP 401 with code42501 permission denied for table scenarios",
                               "current served public client taskCardSource-CbN0QFHu.js and fixed source both build ZIP only from released storage listings; no separate full-bundle endpoint in that client",
                               "official snapshot README describes full practice bundle publication, but current anonymous file set is incomplete"],
                 "unknown": ["whether inaccessible objects are absent from storage or withheld by release policy",
                             "whether live full-bundle checksum differs from fixed official checksum; full bundle and current metadata unavailable"],
                 "decision": "stop network probing; no scoring, no fabricated truth, no synthetic replacement, no account/session/service key",
                 "source_evidence": ["acquisition/probe01/", "acquisition/collect01/", "acquisition/client01/", "client_contract.json",
                                     "research/2026-10-02/upstream/web/src/lib/taskCardSource.ts",
                                     "research/2026-10-02/upstream/cards/README.md"],
                 "selection_input_and_old_artifact_checks": checks}
    save_new(ROOT / "availability_diagnosis.json", diagnosis)
    rows = []
    for item in selection["matrix"]:
        card = next(card for card in cards if card["card_id"] == item["card"])
        candidate = next(candidate for candidate in selection["candidates"] if candidate["id"] == item["candidate"])
        rows.append({"run_id": item["run_id"], "stage": "R6-external", "stage_group": "R6-external",
                     "experiment_category": "official_external_evaluation", "candidate": item["candidate"],
                     "family": {"baseline": "baseline", "d": "D", "dtgp": "DTGP"}[item["candidate"]],
                     "card": item["card"], "card_source": "official_public_storage_incomplete",
                     "card_nights": card["official_facts"]["nights"], "card_targets": card["official_facts"]["targets"],
                     "total": None, "science": None, "components": None, "required_missing": None, "coverage_jain": None,
                     "request_issued": None, "request_completed": None, "report_count": None, "report_correct": None,
                     "report_false": None, "runtime_seconds": None, "accounted_wallclock_seconds": None,
                     "pace_change_count": None, "pace_telemetry_available": False, "internal_error_count": None,
                     "full_season_complete": False, "process_complete": False, "score_available": False,
                     "executed": False, "run_status": "not_run_incomplete_official_bundle", "exit_code": None,
                     "error": None, "not_run_reason": "incomplete_official_bundle", "termination_reason": None, "delta_total_vs_baseline": None,
                     "command": item["command"], "source_tree_sha256": candidate["source_tree_sha256"],
                     "config_sha256": candidate["config_sha256"], "downloaded_file_count": card["file_count"],
                     "missing_required": card["missing_required"], "artifact_path": None,
                     "evidence_links": {"acquisition": "availability_diagnosis.json", "card_inventory": "card_inventory_complete.json",
                                        "selection": "selection_frozen.json"}})
    results = {"schema_version": "v4-official-external-results-v1", "created_at_utc": diagnosis["created_at_utc"],
               "status": "blocked_incomplete_official_cards", "row_count": 12, "expected_runs": 12,
               "executed_runs": 0, "complete_runs": 0, "score_rows": 0, "cards": cards, "rows": rows,
               "selection_file": "selection_frozen.json", "selection_sha256": file_sha256(ROOT / "selection_frozen.json"),
               "execution_journal": "execution.jsonl", "availability_diagnosis": "availability_diagnosis.json",
               "selection_inputs_unchanged": True, "protected_old_artifacts_unchanged": True,
               "network_probing_stopped": True, "executor_status": "prepared_not_executed_due_to_incomplete_cards",
               "definitions": {"rows": "twelve planned fixed configurations; executed=false; not twelve scored runs",
                               "null_metrics": "not measured; never zero-score substitutes",
                               "checksum": "only partial six-file manifest available; full bundle checksum blocked",
                               "evidence_links": "paths relative to external_evaluation directory"},
               "boundaries": selection["boundaries"]}
    save_new(ROOT / "results.json", results)
    columns = ["run_id", "candidate", "family", "card", "card_nights", "card_targets", "total", "science", "required_missing",
               "coverage_jain", "request_issued", "request_completed", "report_count", "report_correct", "report_false",
               "full_season_complete", "runtime_seconds", "accounted_wallclock_seconds", "pace_change_count", "internal_error_count",
               "error", "not_run_reason", "executed", "exit_code", "run_status", "termination_reason", "delta_total_vs_baseline", "artifact_path"]
    with (ROOT / "results.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader()
        for item in rows: writer.writerow({key: item[key] for key in columns})
    with (ROOT / "execution.jsonl").open("a") as handle:
        handle.write(json.dumps({"at_utc": diagnosis["created_at_utc"], "event": "evaluation_blocked_before_runs",
                                 "expected_runs": 12, "started_runs": 0, "complete_runs": 0,
                                 "reason": "all four official bundles incomplete; missing object GETs return NoSuchKey",
                                 "input_hashes_unchanged": True, "diagnosis_sha256": file_sha256(ROOT / "availability_diagnosis.json"),
                                 "results_json_sha256": file_sha256(ROOT / "results.json")}) + "\n")
    print(json.dumps({"expected_runs": 12, "executed_runs": 0, "verified_cards": 0, "missing_objects": 30,
                      "status": results["status"], "protected_old_artifacts_unchanged": True}))


if __name__ == "__main__":
    main()
