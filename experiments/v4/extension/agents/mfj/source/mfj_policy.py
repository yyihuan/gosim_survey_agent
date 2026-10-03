"""M/F/J 独立研究机制；仅使用公开配置与已反馈观测分数。"""
from __future__ import annotations

import json
import math
from collections import Counter


def jain(total, squares, count):
    return total * total / (count * squares) if count and squares > 0 else 0.0


class MFJPolicy:
    def __init__(self, planner, init, config, log):
        self.p = planner
        self.log = log
        self.m = bool(config.get("M", {}).get("enabled", False))
        self.f = bool(config.get("F", {}).get("enabled", False))
        self.j = bool(config.get("J", {}).get("enabled", False))
        if sum((self.m, self.f, self.j)) > 1:
            raise ValueError("MFJ 初版仅允许一个新因素")
        self.enabled = self.m or self.f or self.j
        self.field_limit = int(config.get("F", {}).get("candidate_fields", 6))
        self.j_cap = float(config.get("J", {}).get("maximum_reward_per_target", 10.0))
        if not 1 <= self.field_limit <= 16 or not math.isfinite(self.j_cap) or self.j_cap < 0:
            raise ValueError("invalid MFJ limits")
        uniformity = init["scoring"]["uniformity"]
        self.width = float(uniformity["ra_band_width_deg"])
        self.threshold = float(uniformity["observed_factor_threshold"])
        self.uniformity_weight = float(uniformity["weight"])
        self.bands = [int(ra // self.width) for ra in planner.ra]
        self.band_total = Counter(self.bands)
        self.best_score = [0.0] * len(planner.ids)
        self.feedback_updates = 0
        self.resync_count = 0
        self.plan_index = 0
        self.j_rewards = {}
        self.record = {}
        self.selected = {}

    def on_result(self, result):
        if not self.m or not result or result.get("action") != "observe":
            return
        for hit in result.get("hits", []):
            i = self.p.index_of.get(hit["target_id"])
            if i is not None:
                score = max(0.0, float(hit["score"]))
                if score > self.best_score[i]:
                    self.best_score[i] = score
                    self.feedback_updates += 1

    def resync(self, message):
        if not self.m:
            return
        # state_resync 是引擎公开的当前账本，替换而非保留可能被撤销的历史。
        best = {row["target_id"]: float(row["best_score"])
                for row in message.get("best_scores", [])}
        self.best_score = [max(0.0, best.get(target, 0.0)) for target in self.p.ids]
        self.resync_count += 1

    def begin_plan(self, now):
        if not self.enabled:
            return
        self.plan_index += 1
        self.record = {"record_type": "mfj_plan", "plan_index": self.plan_index,
                       "now_utc": now.isoformat(), "family": "M" if self.m else "F" if self.f else "J",
                       "m_evaluations": 0, "m_proxy_positive_actual_zero": 0,
                       "m_matched_evaluations": 0, "m_mismatch_evaluations": 0,
                       "j_threshold_evaluations": 0, "j_reward_evaluations": 0}
        self.selected = {}
        if self.j:
            observed = Counter(band for i, band in enumerate(self.bands)
                               if self.p.factor[i] >= self.threshold)
            ratios = {band: observed[band] / count for band, count in self.band_total.items()}
            total = sum(ratios.values())
            squares = sum(value * value for value in ratios.values())
            self.j_before = jain(total, squares, len(ratios))
            self.j_deltas = {}
            for band, ratio in ratios.items():
                step = 1.0 / self.band_total[band]
                delta = jain(total + step, squares + 2 * ratio * step + step * step,
                             len(ratios)) - self.j_before
                self.j_deltas[band] = delta if observed[band] < self.band_total[band] else 0.0
            self.j_rewards = {band: min(self.j_cap, self.uniformity_weight * max(0.0, delta))
                              for band, delta in self.j_deltas.items()}
            self.record.update(j_estimated_before=self.j_before,
                               j_positive_bands=sum(delta > 0 for delta in self.j_deltas.values()),
                               j_negative_bands=sum(delta < 0 for delta in self.j_deltas.values()),
                               j_max_reward=max(self.j_rewards.values(), default=0.0))

    def science_gain(self, i, after, model=None, program=None, count=True):
        if model is None:
            multiplier = max(self.p.multipliers.values())  # 仅候选优先级的乐观上界
            matched = None
        else:
            band = self.p._band(model * self.p.scale / 0.95)
            if program is None:
                multiplier = max(self.p.multipliers[band], self.p.mismatch)
                matched = None
            else:
                matched = program == band
                multiplier = self.p.multipliers[program] if matched else self.p.mismatch
        gain = max(0.0, self.p.weight[i] * after * multiplier - self.best_score[i])
        if count and self.record:
            self.record["m_evaluations"] += 1
            self.record["m_proxy_positive_actual_zero"] += int(after > self.p.factor[i] and gain == 0.0)
            if matched is not None:
                self.record["m_matched_evaluations" if matched else "m_mismatch_evaluations"] += 1
        return gain

    def uniformity_gain(self, i, before, after, count=True):
        crossed = before < self.threshold <= after
        reward = self.j_rewards.get(self.bands[i], 0.0) if crossed else 0.0
        if count and self.record:
            self.record["j_threshold_evaluations"] += int(crossed)
            self.record["j_reward_evaluations"] += int(reward > 0)
        return reward

    def select(self, info, duration, program):
        if not self.enabled:
            return
        items = [item for item in info.values() if item["up"] >= duration]
        if self.m:
            self.selected = {
                "m_selected_banked_targets": sum(self.best_score[item["i"]] > 0 for item in items),
                "m_selected_predicted_science_gain": sum(self.science_gain(
                    item["i"], min(1.0, item["k"] * duration), item["model"], program, count=False)
                    for item in items),
                "m_feedback_updates": self.feedback_updates, "m_resync_count": self.resync_count}
        elif self.j:
            rewards = [self.uniformity_gain(item["i"], self.p.factor[item["i"]],
                       min(1.0, item["k"] * duration), count=False) for item in items]
            self.selected = {"j_rewarded_selected": sum(value > 0 for value in rewards),
                             "j_selected_reward_sum": sum(rewards)}

    def end_plan(self, action):
        if not self.enabled:
            return
        self.record.update(self.selected)
        self.record["action"] = action.get("action") if action else None
        self.record["selected_count"] = len(action.get("assignments", {})) if action else 0
        self.log("mfj: " + json.dumps(self.record, separators=(",", ":"), sort_keys=True))
