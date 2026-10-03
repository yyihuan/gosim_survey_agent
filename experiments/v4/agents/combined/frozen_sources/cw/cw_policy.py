"""C/W 单因素研究钩子：仅改变基线候选目标预计收益的软权重。"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import timedelta
from pathlib import Path

from skymath import parse_utc, wrap180

DIRECTION_AZ = {"N": 0.0, "NE": 45.0, "E": 90.0, "SE": 135.0,
                "S": 180.0, "SW": 225.0, "W": 270.0, "NW": 315.0}


class CWPolicy:
    def __init__(self, planner, init, log):
        self.planner = planner
        self.log = log
        path = os.environ.get("EXPERIMENT_CONFIG_PATH")
        config = json.loads(Path(path).read_text()) if path else {}
        self.c = config.get("C", {"enabled": False})
        self.w = config.get("W", {"enabled": False})
        self.c_enabled = bool(self.c.get("enabled", False))
        self.w_enabled = bool(self.w.get("enabled", False))
        self.enabled = self.c_enabled or self.w_enabled
        self.c_strength = float(self.c.get("strength", 0.6))
        self.w_penalty = float(self.w.get("penalty_fraction", 0.2))
        self.w_half_width = float(self.w.get("angular_half_width_deg", 67.5))
        self.w_altitude = float(self.w.get("maximum_altitude_deg", 75.0))
        self.w_kinds = set(self.w.get("event_kinds", ["rain", "storm", "overcast", "haze", "rocket_launch"]))
        assert math.isfinite(self.c_strength) and 0.0 <= self.c_strength <= 1.0
        assert math.isfinite(self.w_penalty) and 0.0 <= self.w_penalty <= 0.5
        assert 0.0 < self.w_half_width <= 90.0 and 0.0 < self.w_altitude <= 90.0
        uniformity = init["scoring"].get("uniformity", {})
        self.band_width = float(uniformity.get("ra_band_width_deg", 10.0))
        self.threshold = float(uniformity.get("observed_factor_threshold", 0.5))
        self.bands = [int((ra % 360.0) // self.band_width) for ra in planner.ra]
        self.band_total = Counter(self.bands)
        self.night_dates = [(start - timedelta(hours=12)).date().isoformat()
                            for start, _end in planner.nights]
        self.forecasts = []
        self.forecast_directions = set()
        self.c_multipliers = {}
        self.mean_completion = 0.0
        self.evaluated = {}
        self.plan_index = 0
        self.forecasts_received = 0
        self.last_forecast = None

    def on_messages(self, messages):
        if not self.w_enabled:
            return
        for message in messages:
            if message.get("record_type") == "forecast":
                # 此队列仅来自 simulator 已经发送给 Agent 的消息，绝不加载预报文件。
                self.forecasts.append(message)
                self.forecasts_received += 1

    def begin_plan(self, now, _night_end, night_index):
        if not self.enabled:
            return
        self.plan_index += 1
        self.now = now
        self.night_index = night_index
        self.evaluated = {}
        self.forecast_directions = set()
        if self.c_enabled:
            observed = Counter(band for i, band in enumerate(self.bands)
                               if self.planner.factor[i] >= self.threshold)
            fractions = {band: observed[band] / total for band, total in self.band_total.items()}
            self.mean_completion = sum(fractions.values()) / len(fractions)
            self.c_multipliers = {band: 1.0 + self.c_strength * max(0.0, self.mean_completion-fraction)
                                  for band, fraction in fractions.items()}
        if self.w_enabled:
            received = [forecast for forecast in self.forecasts
                        if parse_utc(forecast["issued_at_utc"]) <= now]
            latest = max(received, key=lambda f: parse_utc(f["issued_at_utc"])) if received else None
            self.last_forecast = latest
            if latest:
                tonight = self.night_dates[night_index]
                self.forecast_directions = {notice.get("direction") for notice in latest.get("notices", [])
                    if tonight in notice.get("nights", []) and notice.get("event_kind") in self.w_kinds
                    and notice.get("direction") in DIRECTION_AZ}

    def weather_multiplier(self, alt, az):
        if self.w_enabled and alt < self.w_altitude and any(
                abs(wrap180(az-DIRECTION_AZ[direction])) <= self.w_half_width
                for direction in self.forecast_directions):
            return 1.0-self.w_penalty
        return 1.0

    def multiplier(self, i, alt, az):
        if not self.enabled:
            return 1.0
        c = self.c_multipliers.get(self.bands[i], 1.0) if self.c_enabled else 1.0
        w = self.weather_multiplier(alt, az)
        self.evaluated[i] = (c, w)
        return c*w

    def end_plan(self, action):
        if not self.enabled:
            return
        chosen = []
        if action and action.get("action") == "observe":
            chosen = [self.evaluated[self.planner.index_of[target]]
                      for target in action.get("assignments", {}).values()
                      if self.planner.index_of[target] in self.evaluated]
        record = {"record_type": "cw_plan", "plan_index": self.plan_index,
                  "now_utc": self.now.isoformat(), "night_index": self.night_index,
                  "action": action.get("action") if action else None,
                  "candidate_count": len(self.evaluated),
                  "c_boosted_candidates": sum(c > 1.0 for c, _w in self.evaluated.values()),
                  "w_penalized_candidates": sum(w < 1.0 for _c, w in self.evaluated.values()),
                  "selected_count": len(chosen),
                  "c_boosted_selected": sum(c > 1.0 for c, _w in chosen),
                  "w_penalized_selected": sum(w < 1.0 for _c, w in chosen),
                  "c_mean_band_completion": self.mean_completion if self.c_enabled else None,
                  "c_max_multiplier": max(self.c_multipliers.values(), default=1.0),
                  "forecast_directions": sorted(self.forecast_directions),
                  "forecasts_received": self.forecasts_received,
                  "forecast_issued_at_utc": self.last_forecast.get("issued_at_utc") if self.last_forecast else None}
        self.log("cw: " + json.dumps(record, separators=(",", ":"), sort_keys=True))
