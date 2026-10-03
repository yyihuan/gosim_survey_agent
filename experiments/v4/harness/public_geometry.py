#!/usr/bin/env python3
"""仅用公开目录、夜历、场址分析连续高度窗口，并与既有官方轨迹对照。"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

from common import KIT_ROOT, file_sha256, write_json
from metrics import read_csv

sys.path.insert(0, str(KIT_ROOT / "agent"))
from skymath import SIDEREAL_DEG_PER_SECOND, local_sidereal_deg, max_hour_angle_deg, parse_utc, wrap180
sys.path.insert(0, str(KIT_ROOT))
from challenge.v4_fiber_map import min_altitude_during


def windows(ra: float, dec: float, nights: list, latitude: float, longitude: float, limit: float) -> list:
    half_width = max_hour_angle_deg(dec, latitude, limit)
    if half_width <= 0:
        return []
    result = []
    for night_id, start, end in nights:
        length = (end - start).total_seconds()
        angle = wrap180(local_sidereal_deg(start, longitude) - ra)
        for turn in (-1, 0, 1):
            lower = max(0.0, (-half_width + 360 * turn - angle) / SIDEREAL_DEG_PER_SECOND)
            upper = min(length, (half_width + 360 * turn - angle) / SIDEREAL_DEG_PER_SECOND)
            if upper > lower:
                result.append((upper - lower, night_id, start + timedelta(seconds=lower), start + timedelta(seconds=upper)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", required=True, type=Path)
    parser.add_argument("--baseline-run", required=True, type=Path)
    args = parser.parse_args()
    card = args.card.resolve()
    run = args.baseline_run.resolve()
    scenario_path = card / "config/v4_scenario.json"
    targets_path = card / "public/targets.csv"
    calendar_path = card / "public/v4_night_calendar.csv"
    score_path = card / "config/v4_score_config.json"
    scenario = json.loads(scenario_path.read_text())
    score = json.loads(score_path.read_text())
    latitude = scenario["site"]["latitude_deg"]
    longitude = scenario["site"]["longitude_deg"]
    limit = float(scenario["minimum_altitude_deg"])
    threshold = float(score["required"]["observed_factor_threshold"])
    penalty = float(score["required"]["penalty_per_missing"])
    calendar = read_csv(calendar_path)
    nights = [(row["night_id"], parse_utc(row["observing_start_utc"]), parse_utc(row["observing_end_utc"])) for row in calendar]
    best_factor = {}
    for row in read_csv(run / "output/observations.csv"):
        if row.get("valid", "true").lower() == "true":
            target = row["target_id"]
            best_factor[target] = max(best_factor.get(target, 0), float(row["factor"]))
    rows = []
    exact_checks = 0
    for target in read_csv(targets_path):
        ra, dec = float(target["ra_deg"]), float(target["dec_deg"])
        intervals = windows(ra, dec, nights, latitude, longitude, limit)
        longest = max(intervals, default=(0, None, None, None))
        required = target["required"].lower() == "true"
        maximum = longest[0]
        # 每个可行源用官方 exact-min 函数复核一个完全包含的60/900秒区间。
        for duration in (60, 900):
            if maximum >= duration:
                start = longest[2] + timedelta(seconds=(maximum - duration) / 2)
                altitude = min_altitude_during(ra, dec, start, start + timedelta(seconds=duration), scenario)
                if altitude < limit - 1e-6:
                    raise AssertionError((target["target_id"], duration, altitude))
                exact_checks += 1
        factor = best_factor.get(target["target_id"], 0)
        rows.append({"target_id": target["target_id"], "ra_deg": ra, "dec_deg": dec,
                     "required": required, "max_contiguous_window_seconds": maximum,
                     "longest_window_night_id": longest[1], "ever_above_limit_in_nights": maximum > 0,
                     "window_ge_60": maximum >= 60, "window_ge_900": maximum >= 900,
                     "global_transit_altitude_deg": 90 - abs(dec - latitude),
                     "baseline_best_valid_factor_csv": factor,
                     "baseline_required_missing": required and factor < threshold})
    required_rows = [row for row in rows if row["required"]]
    missing = [row for row in required_rows if row["baseline_required_missing"]]
    no_window = [row for row in required_rows if not row["ever_above_limit_in_nights"]]
    report = json.loads((run / "output/score_report.json").read_text())
    if len(missing) != report["counts"]["required_missing"]:
        raise AssertionError("CSV舍入导致required缺失计数不符；不能据此精确列交集")
    categories = {
        "required_no_window_any_length": no_window,
        "baseline_missing_no_window": [row for row in missing if not row["ever_above_limit_in_nights"]],
        "baseline_missing_window_ge_60": [row for row in missing if row["window_ge_60"]],
        "baseline_missing_window_ge_900": [row for row in missing if row["window_ge_900"]],
        "baseline_missing_positive_window_lt_60": [row for row in missing if 0 < row["max_contiguous_window_seconds"] < 60],
        "baseline_missing_window_60_to_900": [row for row in missing if row["window_ge_60"] and not row["window_ge_900"]],
    }
    result = {
        "schema_version": "v4-public-geometry-v1", "card": str(card), "baseline_run": str(run),
        "command": [sys.executable, "-B", str(Path(__file__).resolve()), *sys.argv[1:]],
        "public_input_sha256": {str(path.relative_to(card)): file_sha256(path)
                                for path in (scenario_path, targets_path, calendar_path, score_path)},
        "night_count": len(nights), "survey_window_start_utc": str(nights[0][1]),
        "survey_window_end_utc": str(nights[-1][2]), "altitude_limit_deg": limit,
        "targets": {"total": len(rows), "any_positive_window": sum(row["ever_above_limit_in_nights"] for row in rows),
                    "window_ge_60": sum(row["window_ge_60"] for row in rows),
                    "window_ge_900": sum(row["window_ge_900"] for row in rows)},
        "required": {"total": len(required_rows), "any_positive_window": sum(row["ever_above_limit_in_nights"] for row in required_rows),
                     "window_ge_60": sum(row["window_ge_60"] for row in required_rows),
                     "window_ge_900": sum(row["window_ge_900"] for row in required_rows),
                     "no_window_any_length": len(no_window),
                     "always_below_limit_at_any_sidereal_time": sum(row["global_transit_altitude_deg"] < limit for row in required_rows),
                     "baseline_missing": len(missing), "unavoidable_missing_lower_bound": len(no_window),
                     "unavoidable_required_penalty": -penalty * len(no_window)},
        "intersections": {key: {"count": len(value), "target_ids": [row["target_id"] for row in value]}
                          for key, value in categories.items()},
        "verification": {"official_exact_min_altitude_checks": exact_checks,
                         "baseline_missing_count_matches_official": True,
                         "no_window_but_baseline_factor_positive": sum(best_factor.get(row["target_id"], 0) > 0 for row in no_window)},
        "limitations": ["范围是本卡公开夜历14夜，不是365日全年；不读取任何truth文件。",
                        "几何窗口只保证目标高度，未保证天气、光纤可分配、有效深度或多个目标的调度兼容性。",
                        "无任何正时长窗口是不可避免required缺失的下界。几何可行不能给实际缺失上界。",
                        "60秒/900秒门槛只表示连续窗口。夜末官方可截断到60秒以下，故无60秒窗口不等同绝对不可能。",
                        "baseline因子来自官方CSV的6位舍入；本次重建缺失数与官方计数一致。"],
    }
    with (run / "public_geometry.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(run / "public_geometry.json", result)
    print(json.dumps({"targets": result["targets"], "required": result["required"],
                      "intersections": {key: value["count"] for key, value in result["intersections"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
