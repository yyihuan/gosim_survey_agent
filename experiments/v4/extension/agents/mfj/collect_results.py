#!/usr/bin/env python3
"""只读汇总 MFJ N2 run；不运行模拟或重评分。"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

V4 = Path(__file__).resolve().parents[3]
NOTES = V4 / "extension/notes"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    registered = json.loads((NOTES / "mfj-preregistration.json").read_text())
    source = V4 / "extension/agents/mfj/source"
    source_unchanged = {p.name: digest(p) for p in source.iterdir() if p.is_file()} == registered["source_files_sha256"]
    config_dir = V4 / "extension/configs/mfj"
    config_unchanged = {name: digest(config_dir / name) for name in registered["config_sha256"]} == registered["config_sha256"]
    n3 = json.loads((NOTES / "mfj-f-n3-preregistration.json").read_text())
    config_unchanged = config_unchanged and digest(Path(n3["config_path"])) == n3["config_sha256"]
    old_data_unchanged = digest(V4 / "results/all_runs.json") == registered["old_all_runs_sha256"]
    base = json.loads((NOTES / "mfj-source-base.json").read_text())
    baseline_unchanged = {p.name: digest(p) for p in Path(base["baseline_source"]).iterdir() if p.is_file()} == base["baseline_files_sha256"]
    rows = []
    cases = [("control", "ext-n2-mfj-control-"), ("m", "ext-n2-m-initial-"),
             ("f", "ext-n2-f-initial-"), ("j", "ext-n2-j-initial-"), ("f", "ext-n3-f-fields12-")]
    snapshot_checks = []
    wrapper_checks = []
    for family, prefix in cases:
        for card in ("demo", "dev-season"):
            run_id = prefix + card
            run = V4 / "runs" / run_id
            metrics = json.loads((run / "metrics.json").read_text())
            manifest = json.loads((run / "manifest.json").read_text())
            snapshot_checks.append(all(digest(run / "source_snapshot" / name) == value
                                       for name, value in registered["source_files_sha256"].items()))
            wrapper_checks.append(manifest["extension_wrapper"]["original_harness_unchanged_after_run"]
                                  and manifest["extension_wrapper"]["wrapper_source_unchanged_after_run"])
            log = (run / "output/agent.log").read_text()
            plans = [json.loads(line[5:]) for line in log.splitlines() if line.startswith("mfj: ")]
            observes = [plan for plan in plans if plan["action"] == "observe"]
            control = json.loads((V4 / "runs" / ("ext-n2-mfj-control-" + card) / "metrics.json").read_text())
            mechanism = {"logged_plans": len(plans), "logged_observe_plans": len(observes)}
            if family == "m":
                mechanism.update({key: sum(plan.get(key, 0) for plan in plans) for key in
                    ("m_evaluations", "m_proxy_positive_actual_zero", "m_matched_evaluations", "m_mismatch_evaluations",
                     "m_selected_banked_targets", "m_selected_predicted_science_gain")})
                mechanism["suppression_call_fraction"] = mechanism["m_proxy_positive_actual_zero"] / max(1, mechanism["m_evaluations"])
                mechanism["suppression_plan_count"] = sum(plan.get("m_proxy_positive_actual_zero", 0) > 0 for plan in plans)
                mechanism["m_feedback_updates"] = max((plan.get("m_feedback_updates", 0) for plan in plans), default=0)
                mechanism["m_resync_count"] = max((plan.get("m_resync_count", 0) for plan in plans), default=0)
            if family == "f":
                mechanism.update({key: sum(plan.get(key, 0) for plan in plans) for key in
                    ("f_generated_fields", "f_retained_fields", "f_evaluated_fields", "f_changed_from_potential_best")})
                mechanism["changed_field_fraction_of_observe_plans"] = mechanism["f_changed_from_potential_best"] / max(1, len(observes))
                mechanism["selected_potential_rank_distribution"] = dict(Counter(str(plan.get("f_selected_potential_rank")) for plan in observes))
                mechanism["maximum_anchor_count"] = max((plan.get("f_anchor_count", 0) for plan in plans), default=0)
            if family == "j":
                mechanism.update({key: sum(plan.get(key, 0) for plan in plans) for key in
                    ("j_threshold_evaluations", "j_reward_evaluations", "j_rewarded_selected", "j_selected_reward_sum")})
                mechanism["rewarded_observe_plans"] = sum(plan.get("j_rewarded_selected", 0) > 0 for plan in observes)
                mechanism["rewarded_observe_fraction"] = mechanism["rewarded_observe_plans"] / max(1, len(observes))
                mechanism["maximum_single_target_reward"] = max((plan.get("j_max_reward", 0) for plan in plans), default=0)
            req = metrics["requests"]
            row = {"run_id": run_id, "stage": manifest["stage"], "family": family.upper(), "card": card,
                "total": metrics["total"], "delta_total_vs_d_control": metrics["total"] - control["total"],
                "components": metrics["components"],
                "delta_components_vs_d_control": {key: value - control["components"][key] for key, value in metrics["components"].items()},
                "required_missing": metrics["counts"]["required_missing"], "J": metrics["coverage"]["jain_from_official_penalty"],
                "qualified_target_count": metrics["coverage"]["qualified_target_count"],
                "observe_actions": metrics["counts"]["observe_actions"], "mean_exposure_seconds": metrics["exposure"]["actual_seconds"]["mean"],
                "request_issued": len(req), "request_completed": sum(bool(r["completed"]) for r in req), "requests": req,
                "reports": metrics["reports"], "runtime_seconds": metrics["runtime_seconds"],
                "accounted_wallclock_seconds": metrics["accounted_wallclock_seconds"], "agent_wallclock_seconds": metrics["agent_wallclock_seconds"],
                "pace": metrics["pace"], "termination_reason": metrics["termination_reason"], "exit_code": metrics["exit_code"],
                "source_tree_sha256": manifest["source_tree_sha256"], "config_sha256": manifest["config_sha256"],
                "config": json.loads((run / "config.json").read_text()), "concurrency": manifest["concurrency"],
                "mechanism": mechanism, "internal_errors": [line for line in log.splitlines() if "baseline: error" in line],
                "evidence_links": {name: str((run / relative).relative_to(V4.parents[1])) for name, relative in
                    {"manifest": "manifest.json", "metrics": "metrics.json", "score": "output/score_report.json", "agent_log": "output/agent.log", "actions": "output/actions.jsonl"}.items()}}
            rows.append(row)
    for row in rows:
        row["variant"] = row["config"]["variant"]
        if row["stage"] == "N3":
            previous = next(candidate for candidate in rows if candidate["family"] == "F" and candidate["stage"] == "N2" and candidate["card"] == row["card"])
            row["delta_total_vs_f6"] = row["total"] - previous["total"]
            row["delta_components_vs_f6"] = {key: value - previous["components"][key] for key, value in row["components"].items()}
    result = {"schema_version": "mfj-n2-n3-results-v1", "rows": rows, "row_count": len(rows), "strategy_run_count": 8,
        "postcheck": {"source_unchanged": source_unchanged, "config_unchanged": config_unchanged,
                      "all_run_source_snapshots_match": all(snapshot_checks), "all_wrappers_and_original_harness_unchanged": all(wrapper_checks),
                      "old_all_runs_unchanged": old_data_unchanged, "combined_baseline_source_unchanged": baseline_unchanged,
                      "all_complete": all(row["termination_reason"] == "survey_complete" and row["exit_code"] == 0 for row in rows),
                      "all_pace_zero": all(row["pace"]["change_count"] == 0 for row in rows),
                      "no_internal_errors": all(not row["internal_errors"] for row in rows)},
        "definitions": {"scores": "official metrics unchanged; deltas vs same-card MFJ all-off D control",
            "M_trigger": "proxy-positive/actual-zero planning calls; duplicate evaluations included; not unique targets",
            "F_trigger": "chosen field differs from highest longest-exposure potential among original anchor search",
            "J_trigger": "observes with at least one positive truncated single-target Jain reward; summed rewards are local approximation",
            "feedback_metrics": "M feedback/resync maxima as of last logged plan; a later final protocol result may not be included"}}
    (NOTES / "mfj-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    flat = []
    for row in rows:
        flat.append({key: row[key] for key in ("run_id", "stage", "family", "variant", "card", "total", "delta_total_vs_d_control", "required_missing", "J", "qualified_target_count", "observe_actions", "mean_exposure_seconds", "request_issued", "request_completed", "runtime_seconds", "accounted_wallclock_seconds", "termination_reason", "exit_code", "source_tree_sha256", "config_sha256")})
        flat[-1].update(row["components"])
        flat[-1].update(report_count=row["reports"]["count"], report_correct=row["reports"]["correct"], report_false=row["reports"]["false"], pace_change_count=row["pace"]["change_count"])
    with (NOTES / "mfj-results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
        writer.writeheader(); writer.writerows(flat)
    print(json.dumps({"row_count": len(rows), "postcheck": result["postcheck"], "rows": flat}, ensure_ascii=False))
    return 0 if all(result["postcheck"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
