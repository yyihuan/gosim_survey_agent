#!/usr/bin/env python3
"""Derive TDG trigger proxies from official trajectories and public catalogue only."""
import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "source"))
from skymath import local_sidereal_deg, normalized_airmass, parse_utc, radec_to_altaz


def read_csv(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def distribution(values):
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "p10": None, "p90": None}
    ordered = sorted(values)
    return {"count": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
            "min": min(values), "max": max(values), "p10": ordered[int(0.1 * (len(values) - 1))],
            "p90": ordered[int(0.9 * (len(values) - 1))]}


def extract(run):
    manifest = json.loads((run / "manifest.json").read_text())
    card_path = manifest.get("card_snapshot", manifest.get("card_source"))
    if card_path is None:
        command = manifest["command"]
        card_path = command[command.index("--card") + 1]
    card = Path(card_path)
    scenario = json.loads((card / "config/v4_scenario.json").read_text())
    fiber = json.loads((card / "config/v4_fiber_config.json").read_text())
    calendar = read_csv(card / "public/v4_night_calendar.csv")
    nights = [(parse_utc(row["observing_start_utc"]), parse_utc(row["observing_end_utc"])) for row in calendar]
    targets = {row["target_id"]: row for row in read_csv(card / "public/targets.csv")}
    output = run / "output"
    decisions = read_csv(output / "decisions.csv")
    observes = [row for row in decisions if row["action"] == "observe"]
    actions = [json.loads(line) for line in (output / "actions.jsonl").read_text().splitlines() if line.strip()]
    requested = [row for row in actions if row["action"] == "observe"]
    assert len(observes) == len(requested), "observe pairing mismatch"
    # Public night calendar gives each grid origin. Official v4 uses 900-second slots.
    slot = 900
    crosses_actual = crosses_requested = duration_mismatches = 0
    night_wait_seconds = 0.0
    night_wait_rows = short_boundary_wait_rows = 0
    for row, action in zip(observes, requested):
        start = parse_utc(row["start_utc"])
        origin = next(a for a, b in nights if a <= start < b)
        remaining = slot - (start - origin).total_seconds() % slot
        crosses_actual += float(row["duration_seconds"]) > remaining
        crosses_requested += int(action["duration_seconds"]) > remaining
        duration_mismatches += int(action["duration_seconds"]) != float(row["duration_seconds"])
    for row in decisions:
        if row["action"] != "wait":
            continue
        start, end = parse_utc(row["start_utc"]), parse_utc(row["end_utc"])
        overlap = sum(max(0.0, (min(b, end) - max(a, start)).total_seconds()) for a, b in nights)
        if overlap:
            night_wait_rows += 1
            night_wait_seconds += overlap
        origin = next((a for a, b in nights if a <= start < b), None)
        if origin is not None:
            remaining = slot - (start - origin).total_seconds() % slot
            if remaining < fiber["exposure"]["min_duration_seconds"] and (end - start).total_seconds() == remaining:
                short_boundary_wait_rows += 1
    by_observe = {int(row["observe_index"]): row for row in observes}
    all_alt, valid_alt, positive_alt, all_airmass, positive_airmass = [], [], [], [], []
    factors = []
    for row in read_csv(output / "observations.csv"):
        exposure = by_observe[int(row["observe_index"])]
        start = parse_utc(exposure["start_utc"])
        target = targets[row["target_id"]]
        lst = local_sidereal_deg(start, scenario["site"]["longitude_deg"])
        altitude, azimuth = radec_to_altaz(float(target["ra_deg"]), float(target["dec_deg"]), lst,
                                         scenario["site"]["latitude_deg"])
        airmass = normalized_airmass(altitude)
        all_alt.append(altitude)
        all_airmass.append(airmass)
        if row.get("valid", "true").lower() == "true":
            valid_alt.append(altitude)
            factors.append(float(row["factor"]))
            if float(row["score"]) > 0:
                positive_alt.append(altitude)
                positive_airmass.append(airmass)
    durations = [int(row["duration_seconds"]) for row in observes]
    agent_log = (output / "agent.log").read_text()
    overrides = [tuple(map(int, match)) for match in re.findall(
        r"tdg: conditional cap override duration=(\d+) eligible_threshold_targets=(\d+)", agent_log)]
    return {"schema_version": "tdg-mechanisms-v3", "run_id": run.name,
            "T": {"observe_count": len(observes), "actual_cross_slot_count": crosses_actual,
                  "requested_cross_slot_count": crosses_requested,
                  "requested_actual_duration_mismatch_count": duration_mismatches,
                  "agent_internal_error_log_count": agent_log.count("baseline: error "),
                  "conditional_long_override_count": len(overrides),
                  "conditional_long_override_duration_histogram": dict(sorted(Counter(duration for duration, _ in overrides).items())),
                  "conditional_long_override_predicted_eligible_targets": sum(count for _, count in overrides),
                  "actual_cross_slot_fraction": crosses_actual / len(observes) if observes else None,
                  "requested_cross_slot_fraction": crosses_requested / len(observes) if observes else None,
                  "night_wait_rows": night_wait_rows, "night_wait_seconds": night_wait_seconds,
                  "below_minimum_remainder_boundary_wait_rows": short_boundary_wait_rows},
            "D": {"actual_duration_seconds": distribution(durations),
                  "actual_duration_histogram": dict(sorted(Counter(durations).items())),
                  "valid_hit_factor": distribution(factors),
                  "valid_hit_rows_factor_at_least_0_5": sum(f >= 0.5 for f in factors),
                  "valid_hit_rows_factor_at_least_0_95": sum(f >= 0.95 for f in factors)},
            "G": {"all_hit_start_altitude_deg": distribution(all_alt),
                  "valid_hit_start_altitude_deg": distribution(valid_alt),
                  "positive_valid_hit_start_altitude_deg": distribution(positive_alt),
                  "all_hit_start_airmass": distribution(all_airmass),
                  "positive_valid_hit_start_airmass": distribution(positive_airmass),
                  "valid_hit_fraction_below_45_deg": sum(a < 45 for a in valid_alt) / len(valid_alt) if valid_alt else None},
            "definitions": {"T": "请求时长来自actions；起点与实际时长来自decisions；当前900秒格以公开夜晚开始为原点；夜内等待是wait与观测窗口重叠秒数",
                            "D": "实际曝光来自decisions；factor来自有效observations，按hit行计数，可含重复目标；CSV六位舍入会影响门槛",
                            "G": "按命中行计算曝光起始时刻目标高度与airmass；仅读公开目录/站点和原始轨迹；positive仅含valid且score>0；不把视场中心当目标高度"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    metrics = extract(args.run.resolve())
    encoded = json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        with args.out.open("x") as handle:
            handle.write(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
