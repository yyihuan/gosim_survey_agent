"""局部公式与 F preview 状态隔离；公开 demo 输入，不读取 truth。"""
import copy
import csv
import json
import math
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve()
V4 = HERE.parents[4]
sys.path.insert(0, str(HERE.parents[1] / "source"))
from mfj_policy import MFJPolicy, jain
from planner import Planner
from skymath import Moon, local_sidereal_deg, parse_utc, radec_to_altaz


class Mechanisms(unittest.TestCase):
    def simple(self, family):
        p = SimpleNamespace(ids=["a", "b", "c", "d"], index_of={"a": 0, "b": 1, "c": 2, "d": 3},
            ra=[0.0, 1.0, 10.0, 11.0], factor=[0.8, 0.0, 0.0, 0.0], weight=[2.0] * 4,
            multipliers={"DARK": 1.2, "BRIGHT": 1.12, "BACKUP": 1.06}, mismatch=1.0,
            scale=1.0, _band=lambda model: "DARK" if model >= 0.65 else "BACKUP")
        init = {"scoring": {"uniformity": {"ra_band_width_deg": 10, "observed_factor_threshold": 0.5, "weight": 200}}}
        policy = MFJPolicy(p, init, {family: {"enabled": True}}, lambda message: None)
        return p, policy

    def test_m_best_score_and_program(self):
        p, policy = self.simple("M")
        policy.begin_plan(datetime.now(timezone.utc))
        policy.on_result({"action": "observe", "hits": [{"target_id": "a", "score": 2.16}]})
        self.assertEqual(policy.science_gain(0, 0.9, 0.9, "BACKUP"), 0.0)
        self.assertAlmostEqual(policy.science_gain(0, 1.0, 0.9, "DARK"), 0.24)
        policy.on_result({"action": "observe", "hits": [{"target_id": "a", "score": 1.0}]})
        self.assertEqual(policy.best_score[0], 2.16)
        policy.resync({"best_scores": [{"target_id": "a", "best_score": 1.0}]})
        self.assertEqual(policy.best_score[0], 1.0)
        self.assertEqual(policy.best_score[1], 0.0)
        self.assertEqual(policy.record["m_proxy_positive_actual_zero"], 1)

    def test_j_direct_recompute_and_bounds(self):
        p, policy = self.simple("J")
        p.factor = [0.6, 0.0, 0.0, 0.0]
        policy.begin_plan(datetime.now(timezone.utc))
        before = jain(0.5, 0.25, 2)
        after = jain(1.0, 0.5, 2)
        self.assertAlmostEqual(policy.j_deltas[1], after - before)
        self.assertEqual(policy.uniformity_gain(2, 0.0, 0.5), 10.0)
        self.assertEqual(policy.uniformity_gain(2, 0.5, 1.0), 0.0)
        self.assertEqual(policy.uniformity_gain(2, 0.0, 0.49), 0.0)
        self.assertEqual(policy.uniformity_gain(1, 0.0, 0.5), 0.0)
        p.factor = [0.0] * 4
        policy.begin_plan(datetime.now(timezone.utc))
        self.assertEqual(policy.j_before, 0.0)
        self.assertEqual(policy.j_deltas[0], 0.5)

    def test_reject_multi_factor(self):
        p, policy = self.simple("M")
        with self.assertRaises(ValueError):
            MFJPolicy(p, {"scoring": {}}, {"M": {"enabled": True}, "J": {"enabled": True}}, print)

    def test_f_preview_preserves_pending(self):
        card = V4 / "vendor/starter_kit_v4/cards/demo"
        scenario = json.loads((card / "config/v4_scenario.json").read_text())
        scoring = json.loads((card / "config/v4_score_config.json").read_text())
        fiber_config = json.loads((card / "config/v4_fiber_config.json").read_text())
        field = fiber_config["field"]
        side = int(math.sqrt(field["n_fibers"]))
        glass = math.sqrt(field["fiber_area_deg2"])
        pitch = glass + field["gap_deg"]
        instrument = {"grid_side": side, "n_fibers": field["n_fibers"], "glass_side_deg": glass,
                      "pitch_deg": pitch, "fov_side_deg": side * pitch - field["gap_deg"],
                      "exposure": fiber_config["exposure"]}
        with (card / "public/targets.csv").open() as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames
            rows = [[row[name].lower() == "true" if name == "required" else row[name] for name in columns]
                    for row in reader]
        with (card / "public/v4_night_calendar.csv").open() as handle:
            nights = list(csv.DictReader(handle))
        init = {"site": dict(scenario["site"], minimum_altitude_deg=scenario["minimum_altitude_deg"]),
            "survey": {"nights": nights, "end_utc": nights[-1]["observing_end_utc"], "slot_seconds": 900},
            "instrument": instrument, "scoring": scoring, "targets": {"columns": columns, "rows": rows}}
        config = V4 / "extension/configs/mfj/f-initial.json"
        old_path = os.environ.get("EXPERIMENT_CONFIG_PATH")
        os.environ["EXPERIMENT_CONFIG_PATH"] = str(config)
        try:
            p = Planner(init)
        finally:
            if old_path is None:
                del os.environ["EXPERIMENT_CONFIG_PATH"]
            else:
                os.environ["EXPERIMENT_CONFIG_PATH"] = old_path
        now = parse_utc(nights[0]["observing_start_utc"])
        lst = local_sidereal_deg(now, p.lon)
        altaz = lambda i: radec_to_altaz(p.ra[i], p.dec[i], lst, p.lat)
        i = next(i for i in p.active if 50 < altaz(i)[0] < 80)
        c_alt, c_az = altaz(i)
        moon = Moon(now + timedelta(seconds=450), lst, p.lat, p.lunar_model)
        p.night_index = 0
        p.mfj_policy.begin_plan(now)
        p.pending = {"sentinel": {"model": 1.0}}
        p.pending_program, p.pending_duration, p.pending_night = "BACKUP", 123, -2
        keys = ("pending", "pending_program", "pending_duration", "pending_night")
        before = {key: copy.deepcopy(getattr(p, key)) for key in keys}
        args = (now, lst, c_alt, c_az, {0: (1.0, i, 0.2)}, 32400, moon, altaz, 0.0)
        preview = p._finish_plan(*args, preview=True)
        self.assertIsNotNone(preview)
        self.assertEqual(before, {key: getattr(p, key) for key in keys})
        action = p._finish_plan(*args)
        self.assertEqual(action["duration_seconds"], preview["duration_seconds"])
        self.assertEqual(action["program"], preview["program"])
        self.assertNotIn("sentinel", p.pending)
        self.assertIn(p.ids[i], p.pending)


if __name__ == "__main__":
    unittest.main()
