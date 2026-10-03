#!/usr/bin/env python3
"""从官方输出提取指标；不调用评分器、不读取卡片 truth 内容。"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from common import file_sha256, write_json


def read_json(path: Path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "sum": 0, "min": None, "max": None, "mean": None,
                "median": None, "histogram": {}}
    return {"count": len(values), "sum": sum(values), "min": min(values), "max": max(values),
            "mean": statistics.mean(values), "median": statistics.median(values),
            "histogram": dict(sorted(Counter(str(int(value)) if value.is_integer() else str(value)
                                              for value in values).items(), key=lambda item: float(item[0])))}


def canonical_json_hash(value) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def extract(run: Path) -> dict:
    run = run.resolve()
    output = run / "output"
    manifest = read_json(run / "manifest.json", {})
    report = read_json(output / "score_report.json", {})
    workflow = read_json(output / "workflow_result.json", {})
    decisions = read_csv(output / "decisions.csv")
    observations = read_csv(output / "observations.csv")
    actions = read_jsonl(output / "actions.jsonl")
    messages = read_jsonl(output / "messages.jsonl")
    telemetry = read_jsonl(output / "protocol_telemetry.jsonl")
    observe_rows = [row for row in decisions if row["action"] == "observe"]
    actual = [float(row["duration_seconds"]) for row in observe_rows]
    requested = [float(action["duration_seconds"]) for action in actions if action["action"] == "observe"]
    reports = [message for message in messages if message.get("record_type") == "report_result"]
    agent_log = (output / "agent.log").read_text(errors="replace") if (output / "agent.log").exists() else ""
    pace_changes = [{"level": int(match[0]), "milliseconds_per_decision_left": int(match[1])}
                    for match in re.findall(r"baseline: pace level (\d+) \((\d+) ms per decision left\)", agent_log)]
    wall_values = [float(row["wallclock"]["remaining_seconds"]) for row in telemetry
                   if row.get("wallclock") and row["wallclock"].get("remaining_seconds") is not None]
    card = Path(manifest.get("card_snapshot", manifest.get("card_source", "")))
    score_config = read_json(card / "config/v4_score_config.json", {})
    targets = read_csv(card / "public/targets.csv")
    calendar = read_csv(card / "public/v4_night_calendar.csv")
    uniformity_weight = score_config.get("uniformity", {}).get("weight")
    penalty = report.get("components", {}).get("uniformity_penalty")
    jain = 1 + penalty / uniformity_weight if penalty is not None and uniformity_weight else None
    valid = [row for row in observations if row.get("valid", "true").lower() == "true"]
    threshold = float(score_config.get("required", {}).get("observed_factor_threshold", 0.5))
    qualified = {row["target_id"] for row in valid if float(row["factor"]) >= threshold}
    target_counts = Counter(row["target_id"] for row in observations)
    assigned = sum(int(row["assigned_count"]) for row in observe_rows)
    hits = sum(int(row["hit_count"]) for row in observe_rows)
    simulated_span = None
    if decisions:
        start = datetime.fromisoformat(decisions[0]["start_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(decisions[-1]["end_utc"].replace("Z", "+00:00"))
        simulated_span = (end - start).total_seconds()
    hashes = {path.name: file_sha256(path) for path in output.iterdir() if path.is_file()} if output.exists() else {}
    return {
        "schema_version": "v4-experiment-metrics-v1", "run_id": manifest.get("run_id", manifest.get("name", run.name)),
        "stage": manifest.get("stage"), "official_report_available": bool(report),
        "total": report.get("total"), "components": report.get("components", {}),
        "counts": report.get("counts", {}), "by_class": report.get("by_class", {}),
        "termination_reason": manifest.get("termination_reason", workflow.get("termination_reason")),
        "termination_detail": workflow.get("termination_detail", manifest.get("failure_detail")),
        "exit_code": manifest.get("exit_code"), "runtime_seconds": manifest.get("runtime_seconds"),
        "runtime_with_setup_seconds": manifest.get("runtime_with_setup_seconds"),
        "accounted_wallclock_seconds": workflow.get("accounted_wallclock_seconds"),
        "agent_wallclock_seconds": workflow.get("agent_wallclock_seconds"),
        "global_wallclock_seconds": workflow.get("global_wallclock_seconds"),
        "decision_requests": workflow.get("decision_requests"),
        "exposure": {"requested_seconds": distribution(requested), "actual_seconds": distribution(actual),
                     "simulated_observe_seconds": sum(actual),
                     "simulated_wait_seconds": sum(float(row["duration_seconds"]) for row in decisions if row["action"] == "wait"),
                     "simulated_span_seconds": simulated_span,
                     "program_counts": dict(Counter(row["program"] for row in observe_rows)),
                     "assigned_targets": assigned, "hit_targets": hits,
                     "hit_fraction": hits / assigned if assigned else None,
                     "positive_observation_rows": sum(float(row["score"]) > 0 for row in observations),
                     "repeated_hit_targets": sum(count > 1 for count in target_counts.values()),
                     "extra_hit_rows_after_first": sum(count - 1 for count in target_counts.values())},
        "coverage": {"jain_from_official_penalty": jain, "uniformity_weight": uniformity_weight,
                     "uniformity_bands": report.get("uniformity_bands", {}),
                     "qualified_target_count": len(qualified), "factor_threshold": threshold,
                     "required_total": sum(row.get("required", "").lower() == "true" for row in targets)},
        "reports": {"count": len(reports), "correct": sum(bool(row.get("correct")) for row in reports),
                    "false": sum(not row.get("correct") for row in reports),
                    "deltas": [row.get("score_delta") for row in reports]},
        "requests": report.get("observation_requests", []),
        "pace": {"changes_logged": pace_changes, "change_count": len(pace_changes),
                 "telemetry_requests": len(telemetry),
                 "first_remaining_wallclock_seconds": wall_values[0] if wall_values else None,
                 "last_remaining_wallclock_seconds": wall_values[-1] if wall_values else None,
                 "minimum_remaining_wallclock_seconds": min(wall_values) if wall_values else None,
                 "telemetry_available": bool(telemetry)},
        "card": {"target_count": len(targets), "night_count": len(calendar),
                 "source": manifest.get("card_source"), "tree_sha256": manifest.get("card_tree_sha256")},
        "provenance": {key: manifest.get(key) for key in
                       ("source_tree_sha256", "effective_agent_tree_sha256", "config_sha256", "snapshot_tree_sha256",
                        "harness_tree_sha256", "python_version", "python_executable", "command", "cwd", "concurrency")},
        "hashes": {"raw_outputs": hashes, "normalized_actions_sha256": canonical_json_hash(actions),
                   "normalized_score_sha256": canonical_json_hash(report) if report else None},
        "definitions": {"scores": "官方 score_report 原值，未重评分",
                        "exposure": "requested 来自 actions；actual 和时间来自 decisions，包括后续失效的观测",
                        "jain": "1 + 官方 uniformity_penalty / 卡片公开 uniformity.weight；受官方6位舍入影响",
                        "qualified": "observations 中有效且 factor 达公开 required 阈值的不同 target；计数受CSV6位舍入影响",
                        "pace": "变化来自 agent.log；remaining wallclock 来自透传收到的 decision_request。缺少记录时为 null",
                        "hashes": "规范化 JSON 使用排序键和紧凑分隔符；官方 actions 本身已剔除 reason/envelope"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--write", action="store_true", help="写入 run/metrics.json")
    args = parser.parse_args()
    result = extract(args.run)
    if args.write:
        write_json(args.run / "metrics.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
