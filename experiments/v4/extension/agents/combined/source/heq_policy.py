"""H/E/Q 开发集单因素钩子；只使用公开几何、夜历和已收到的反馈。"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import timedelta

from skymath import (Moon, SIDEREAL_DEG_PER_SECOND, local_sidereal_deg,
                     normalized_airmass, radec_to_altaz, wrap180)


class HEQPolicy:
    def __init__(self, planner, config):
        self.p = planner
        self.h = config.get("H", {})
        self.e = config.get("E", {})
        self.q = config.get("Q", {})
        self.h_enabled = bool(self.h.get("enabled", False))
        self.e_enabled = bool(self.e.get("enabled", False))
        self.q_enabled = bool(self.q.get("enabled", False))
        self.enabled = self.h_enabled or self.e_enabled or self.q_enabled
        self.strength = float(self.h.get("strength", 2.0))
        self.h_mode = self.h.get("mode", "eligible_nights")
        self.minimum_night_equivalents = float(self.h.get("minimum_night_equivalents", 0.5))
        self.include_saturation = bool(self.e.get("include_saturation", True))
        assert self.h_mode in ("eligible_nights", "night_fraction")
        assert self.minimum_night_equivalents > 0
        self.quantum = int(self.e.get("quantum_seconds", 30))
        self.quantile = float(self.q.get("quantile", 0.25))
        self.minimum_samples = int(self.q.get("minimum_samples", 8))
        self.minimum_margin = float(self.q.get("minimum_margin", 0.6))
        self.memory_hours = float(self.q.get("memory_hours", 2.0))
        assert self.strength >= 0 and self.quantum >= 1
        assert 0 <= self.quantile <= 0.5 and 0 < self.minimum_margin <= 1
        assert self.minimum_samples >= 1 and self.memory_hours > 0
        self.plan_index = 0
        self.required_assignments = Counter()
        self.q_margin = 1.0
        self.future_windows = (self._build_window_opportunities() if self.h_mode == "night_fraction"
                               else self._build_opportunities()) if self.h_enabled else {}

    @staticmethod
    def visibility_intervals(ra, hmax, start_lst, span_seconds):
        """夜内连续可见区间；显式处理跨0度及已在天空上的源。"""
        if hmax <= 0:
            return []
        if hmax >= 180:
            return [(0.0, span_seconds)]
        period = 360.0 / SIDEREAL_DEG_PER_SECOND
        rise = ((ra - hmax - start_lst) % 360.0) / SIDEREAL_DEG_PER_SECOND
        width = 2.0 * hmax / SIDEREAL_DEG_PER_SECOND
        intervals = []
        for shift in (-period, 0.0, period):
            low, high = max(0.0, rise + shift), min(span_seconds, rise + shift + width)
            if high > low:
                intervals.append((low, high))
        return intervals

    def _build_opportunities(self):
        p = self.p
        result = {}
        for i in p.active:
            if not p.required[i]:
                continue
            nights = []
            for start, end in p.nights:
                lst = local_sidereal_deg(start, p.lon)
                span = (end - start).total_seconds()
                intervals = self.visibility_intervals(p.ra[i], p.hmax[i], lst, span)
                eligible = False
                for low, high in intervals:
                    # 取区间内最接近过中天的时刻；这是公开清空模型下的机会估计。
                    transit = ((p.ra[i] - lst) % 360.0) / SIDEREAL_DEG_PER_SECOND
                    period = 360.0 / SIDEREAL_DEG_PER_SECOND
                    peak = min((min(high, max(low, transit + offset)) for offset in (-period, 0, period)),
                               key=lambda t: abs(wrap180(lst + t * SIDEREAL_DEG_PER_SECOND - p.ra[i])))
                    moment = start + timedelta(seconds=peak)
                    peak_lst = local_sidereal_deg(moment, p.lon)
                    alt, _ = radec_to_altaz(p.ra[i], p.dec[i], peak_lst, p.lat)
                    moon = Moon(moment, peak_lst, p.lat, p.lunar_model)
                    model = moon.lunar_factor(p.ra[i], p.dec[i]) / (
                        p.q0 * normalized_airmass(max(alt, 1.0)) ** p.airmass_exponent)
                    k = p.flux[i] * model * 0.9 / p.f0t0
                    needed = 0.5 / max(k, 1e-12)
                    if needed <= min(p.max_exposure, high - low):
                        eligible = True
                        break
                nights.append(eligible)
            result[i] = nights
        return result

    def _nominal_needed(self, i, start, low, high):
        """区间内峰值的公开清空模型；沿用初版 0.9 安全余量。"""
        p = self.p
        lst = local_sidereal_deg(start, p.lon)
        transit = ((p.ra[i] - lst) % 360.0) / SIDEREAL_DEG_PER_SECOND
        period = 360.0 / SIDEREAL_DEG_PER_SECOND
        peak = min((min(high, max(low, transit + offset)) for offset in (-period, 0, period)),
                   key=lambda t: abs(wrap180(lst + t * SIDEREAL_DEG_PER_SECOND - p.ra[i])))
        moment = start + timedelta(seconds=peak)
        peak_lst = local_sidereal_deg(moment, p.lon)
        alt, _ = radec_to_altaz(p.ra[i], p.dec[i], peak_lst, p.lat)
        moon = Moon(moment, peak_lst, p.lat, p.lunar_model)
        model = moon.lunar_factor(p.ra[i], p.dec[i]) / (
            p.q0 * normalized_airmass(max(alt, 1.0)) ** p.airmass_exponent)
        k = p.flux[i] * model * 0.9 / p.f0t0
        return 0.5 / max(k, 1e-12)

    def _build_window_opportunities(self):
        p = self.p
        result = {}
        for i in p.active:
            if not p.required[i]:
                continue
            nights = []
            for start, end in p.nights:
                span = (end - start).total_seconds()
                lst = local_sidereal_deg(start, p.lon)
                intervals = self.visibility_intervals(p.ra[i], p.hmax[i], lst, span)
                nights.append([(low, high, self._nominal_needed(i, start, low, high))
                               for low, high in intervals])
            result[i] = nights
        return result

    def remaining_opportunity(self, i):
        """返回整夜等效量（无量纲）及符合假定质量门槛的窗口总秒数。"""
        p = self.p
        equivalents = seconds = 0.0
        for n in range(self.night_index, len(p.nights)):
            start, end = p.nights[n]
            span = (end - start).total_seconds()
            elapsed = max(0.0, (self.now - start).total_seconds()) if n == self.night_index else 0.0
            for low, high, needed in self.future_windows[i][n]:
                remaining_low = max(low, elapsed)
                if high <= remaining_low:
                    continue
                if remaining_low != low:
                    needed = self._nominal_needed(i, start, remaining_low, high)
                length = high - remaining_low
                if needed <= min(p.max_exposure, length):
                    seconds += length
                    equivalents += length / span
        return equivalents, seconds

    def begin_plan(self, now, night_index, hours):
        if not self.enabled:
            return
        self.plan_index += 1
        self.now, self.night_index = now, night_index
        self.stats = Counter()
        self.h_evaluated = {}
        self.h_window_seconds = {}
        self.e_original = set()
        self.q_evaluated = {}
        self.q_margin = 1.0
        self.q_sample_count = 0
        self.q_lower = None
        if self.h_enabled:
            p = self.p
            self.current_moon = Moon(now + timedelta(seconds=450), local_sidereal_deg(now, p.lon), p.lat, p.lunar_model)
        if self.q_enabled:
            recent = sorted(ratio for when, ratio in self.p.samples if when >= hours - self.memory_hours)
            self.q_sample_count = len(recent)
            if len(recent) >= self.minimum_samples:
                self.q_lower = recent[int(math.floor((len(recent) - 1) * self.quantile))]
                self.q_margin = max(self.minimum_margin, min(1.0, self.q_lower / max(self.p.scale, 1e-12)))

    def urgency(self, i, original, lst, seconds_left):
        if not self.h_enabled or not self.p.required[i] or self.p.factor[i] >= 0.5:
            return original
        p = self.p
        alt, _ = radec_to_altaz(p.ra[i], p.dec[i], lst, p.lat)
        model = self.current_moon.lunar_factor(p.ra[i], p.dec[i]) / (
            p.q0 * normalized_airmass(max(alt, 1.0)) ** p.airmass_exponent)
        k = p.flux[i] * model * p.scale * 0.9 / p.f0t0
        up = (p.hmax[i] - wrap180(lst - p.ra[i])) / SIDEREAL_DEG_PER_SECOND if p.hmax[i] < 180 else 1e9
        if k * min(p.max_exposure, up, seconds_left) < 0.5:
            return original
        if self.h_mode == "night_fraction":
            opportunities, window_seconds = self.remaining_opportunity(i)
            self.h_window_seconds[i] = window_seconds
            factor = 1.0 + self.strength / max(self.minimum_night_equivalents, opportunities)
            self.stats["h_floor_applied_candidates"] += opportunities < self.minimum_night_equivalents
        else:
            opportunities = 1 + sum(self.future_windows[i][self.night_index + 1:])
            factor = 1.0 + self.strength / opportunities
        self.h_evaluated[i] = (opportunities, factor, original)
        self.stats["h_currently_reachable_required"] += 1
        self.stats["h_changed_urgency_candidates"] += factor != original
        return factor

    def required_reached(self, i, reached, raw_reached=None):
        if self.q_enabled and self.p.required[i] and self.p.factor[i] < 0.5:
            protected = min(1.0, (reached if raw_reached is None else raw_reached) * self.q_margin)
            self.stats["q_required_gate_evaluations"] += 1
            self.stats["q_suppressed_bonus_evaluations"] += reached >= 0.5 > protected
            return protected
        return reached

    def protected_k(self, i, k):
        return k * self.q_margin if self.q_enabled and self.p.required[i] and self.p.factor[i] < 0.5 else k

    def exposure_bases(self, info, original):
        if not self.e_enabled:
            return original
        self.e_original = set(original)
        candidates = set(original)
        p = self.p
        for item in info.values():
            i, k = item["i"], item["k"]
            thresholds = []
            if self.include_saturation and p.factor[i] < 1.0:
                thresholds.append(("saturation", 1.0))
            if p.required[i] and p.factor[i] < 0.5:
                thresholds.append(("required", 0.5))
            if p.request_bonus.get(i, 0.0) > 0.0:
                thresholds.append(("request", p.request_threshold[i]))
            for kind, threshold in thresholds:
                duration = int(math.ceil((threshold / max(k, 1e-12) - 1e-9) / self.quantum) * self.quantum)
                if p.min_exposure <= duration <= p.max_exposure and duration <= item["up"]:
                    self.stats["e_critical_" + kind + "_candidates"] += 1
                    candidates.add(duration)
        self.stats["e_extra_duration_candidates"] = len(candidates - self.e_original)
        return tuple(sorted(candidates))

    def end_plan(self, action):
        if not self.enabled:
            return
        selected = [self.p.index_of[target] for target in action.get("assignments", {}).values()] if action else []
        required_retry_selected = sum(self.p.required[i] and self.p.factor[i] < 0.5
                                      and self.required_assignments[i] > 0 for i in selected)
        for i in selected:
            if self.p.required[i]:
                self.required_assignments[i] += 1
        h_selected = [self.h_evaluated[i] for i in selected if i in self.h_evaluated]
        record = {"record_type": "heq_plan", "plan_index": self.plan_index,
                  "now_utc": self.now.isoformat(), "night_index": self.night_index,
                  "action": action.get("action") if action else None,
                  "duration_seconds": action.get("duration_seconds") if action else None,
                  "stats": dict(self.stats), "required_retry_selected": required_retry_selected,
                  "h_selected_opportunities": [x[0] for x in h_selected],
                  "h_opportunity_unit": "night_equivalents" if self.h_mode == "night_fraction" else "eligible_nights",
                  "h_selected_window_seconds": [self.h_window_seconds[i] for i in selected if i in self.h_window_seconds],
                  "h_selected_urgency_changed": sum(x[1] != x[2] for x in h_selected),
                  "e_selected_new_duration": bool(self.e_enabled and action and action.get("duration_seconds") not in self.e_original),
                  "q_sample_count": self.q_sample_count, "q_lower_quantile": self.q_lower,
                  "q_margin": self.q_margin,
                  "q_protected_required_selected": sum(self.p.required[i] and self.p.factor[i] < 0.5
                                                        for i in selected) if self.q_margin < 1.0 else 0}
        self.p.log("heq: " + json.dumps(record, separators=(",", ":"), sort_keys=True))
