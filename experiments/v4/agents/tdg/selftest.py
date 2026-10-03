#!/usr/bin/env python3
"""Local checks using demo public inputs and synthetic result messages only."""
import csv
import importlib.util
import json
import math
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWN = Path(__file__).resolve().parent
OFFICIAL = ROOT / "vendor/starter_kit_v4/agent"
CARD = ROOT / "vendor/starter_kit_v4/cards/demo"
sys.path.insert(0, str(OWN / "source"))
from skymath import format_utc, parse_utc


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_initialize():
    scenario = json.loads((CARD / "config/v4_scenario.json").read_text())
    fiber = json.loads((CARD / "config/v4_fiber_config.json").read_text())
    score = json.loads((CARD / "config/v4_score_config.json").read_text())
    with (CARD / "public/v4_night_calendar.csv").open() as handle:
        nights = list(csv.DictReader(handle))
    with (CARD / "public/targets.csv").open() as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames)
        rows = []
        for row in reader:
            rows.append([row["target_id"], float(row["ra_deg"]), float(row["dec_deg"]), row["target_class"],
                         float(row["feature_flux"]), float(row["science_weight"]), row["required"] == "true"])
    glass = math.sqrt(fiber["field"]["fiber_area_deg2"])
    return {"site": {**scenario["site"], "minimum_altitude_deg": scenario["minimum_altitude_deg"]},
            "survey": {"start_utc": nights[0]["observing_start_utc"], "end_utc": nights[-1]["observing_end_utc"],
                       "slot_seconds": 900, "nights": nights},
            "instrument": {"n_fibers": 16, "grid_side": 4, "fiber_area_deg2": glass * glass,
                           "gap_deg": 0.0, "glass_side_deg": round(glass, 6), "pitch_deg": round(glass, 6),
                           "fov_side_deg": round(4 * glass, 6),
                           "exposure": fiber["exposure"]},
            "scoring": score, "targets": {"columns": columns, "rows": rows}}


def main():
    os.environ["USE_LLM"] = "0"
    os.environ.pop("EXPERIMENT_CONFIG_PATH", None)
    init = public_initialize()
    official_planner = load("official_planner", OFFICIAL / "planner.py")
    tdg_planner = load("tdg_planner", OWN / "source/planner.py")
    official_agent = load("official_agent", OFFICIAL / "baseline_agent.py")
    tdg_agent = load("tdg_agent", OWN / "source/baseline_agent.py")
    official_agent.log = lambda text: None
    tdg_agent.log = lambda text: None
    official_agent.Planner = official_planner.Planner
    tdg_agent.Planner = tdg_planner.Planner
    baseline = official_agent.BaselineAgent(init)
    control = tdg_agent.BaselineAgent(init)
    now = parse_utc(init["survey"]["start_utc"])
    last = None
    for sequence in range(180):
        payload = {"now_utc": format_utc(now), "new_messages": [], "last_result": last,
                   "active_requests": [], "wallclock": {"remaining_seconds": 900}}
        old, new = baseline.respond(payload), control.respond(payload)
        assert old == new, (sequence, old, new)
        if old["action"] == "finish":
            break
        last = {"action": old["action"], "hits": []}
        now = parse_utc(old["until_utc"]) if "until_utc" in old else now + timedelta(seconds=old.get("duration_seconds", 0))
    checked = sequence + 1

    t = tdg_agent.BaselineAgent(init)
    t.planner.strict_slot = True
    start = parse_utc(init["survey"]["start_utc"])
    tail = start + timedelta(seconds=750)
    action = t.respond({"now_utc": format_utc(tail), "wallclock": {"remaining_seconds": 900}})
    assert action["action"] == "observe", action
    assert action["duration_seconds"] == t.planner.pending_duration == 150
    assert tail + timedelta(seconds=action["duration_seconds"]) == start + timedelta(seconds=900)
    short = start + timedelta(seconds=870)
    wait = t.respond({"now_utc": format_utc(short), "wallclock": {"remaining_seconds": 900}})
    assert wait["action"] == "wait" and parse_utc(wait["until_utc"]) == start + timedelta(seconds=900)
    boundary = start + timedelta(seconds=900)
    assert t.planner.slot_end(boundary, start) == start + timedelta(seconds=1800)
    stale_action = t.planner._bounded_duration(900, 150)
    assert stale_action == 150

    os.environ["EXPERIMENT_CONFIG_PATH"] = str(ROOT / "configs/tdg/t-cap900.json")
    cap = tdg_agent.BaselineAgent(init)
    os.environ.pop("EXPERIMENT_CONFIG_PATH")
    assert cap.planner.max_exposure == 900 and cap.planner.strict_slot is False
    cap_action = cap.respond({"now_utc": format_utc(tail), "wallclock": {"remaining_seconds": 900}})
    assert cap_action["action"] == "observe" and 150 < cap_action["duration_seconds"] <= 900
    assert cap.planner.pending_duration == cap_action["duration_seconds"]

    os.environ["EXPERIMENT_CONFIG_PATH"] = str(ROOT / "configs/tdg/t-cap900-conditional.json")
    conditional = tdg_planner.Planner(init)
    os.environ.pop("EXPERIMENT_CONFIG_PATH")
    conditional.required[0] = True
    conditional.factor[0] = 0.4
    conditional.request_bonus[0] = 20
    conditional.request_threshold[0] = 0.8
    assert conditional._target_max_exposure(0) == 3600
    assert conditional._long_exposure_thresholds(0) == (0.5, 0.8)
    conditional.factor[0] = 1.0  # old survey factor does not complete a new active request
    assert conditional._long_exposure_thresholds(0) == (0.8,)
    conditional.request_bonus.clear()
    assert conditional._target_max_exposure(0) == 900

    d = tdg_planner.Planner(init)
    d.science_exponent = 1.0
    i = 0
    assert math.isclose(d._science_gain(i, 0.2, 0.7), d.weight[i] * 0.5)
    assert d._science_gain(i, 0.7, 0.2) == 0.0
    d.science_exponent = 2.0
    assert math.isclose(d._science_gain(i, 0.2, 0.7), d.weight[i] * 0.45)
    d.science_exponent = 1.5
    assert math.isclose(d._science_gain(i, 0.2, 0.7), d.weight[i] * (0.7 ** 1.5 - 0.2 ** 1.5))
    d.science_exponent = 0.75
    assert math.isclose(d._science_gain(i, 0.2, 0.7), d.weight[i] * (0.7 ** 0.75 - 0.2 ** 0.75))
    d.request_bonus[i], d.request_threshold[i] = 20, 0.5
    assert d._request_gain(i, 0.1, 0.49) == 0 and d._request_gain(i, 0.1, 0.5) == 20

    g = tdg_planner.Planner(init)
    g.geometry_strength = 0.5
    assert g.min_alt == 30.0
    weights = [g._geometry_preference(alt) for alt in (30, 45, 60, 90)]
    assert weights[0] == 1.0 and weights[-1] == 1.5 and weights == sorted(weights)
    print(json.dumps({"status": "passed", "python": sys.version.split()[0], "baseline_control_decisions": checked,
                      "t_tail_duration": action["duration_seconds"], "t_short_wait_seconds": 30,
                      "t_cap900_tail_duration": cap_action["duration_seconds"],
                      "g_weights_30_45_60_90": weights}, sort_keys=True))


if __name__ == "__main__":
    main()
