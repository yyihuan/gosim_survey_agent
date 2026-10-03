# C/W 两个独立研究方向

阶段为 R2，目标是测量温和空间欠账和预报避险各自的因果作用。只在 demo 与 dev-season 运行；保留集不读取、不运行。先运行两个因子关闭的 control，确认它与官方 baseline 的动作轨迹及官方成绩一致；然后 C/W 各在两卡一次，不自动进入 R3。

本文实施说明按 document-diagrams 保留单一 Mermaid 源和同名 SVG。

![两个软优先输入](../agents/cw/docs/diagrams/soft-priority-inputs.svg)

## Preregistered motivation

C 的动机是基线收益优先可能让已较完整的 RA 条带继续吸收观测。用公开目录按官方公开 `uniformity.ra_band_width_deg`（当前 10°）分桶，分母为该条带全部公开目标；分子为 baseline 估计 factor 已达官方公开 uniformity 阈值的目标。各非空条带的完成率等权平均为 m，条带完成率为 r。预计收益乘数为 `1 + 0.6 × max(0,m-r)`，理论上位于 1–1.6。它只增加尚欠账条带的软优先，不使用真实 g，不改变曝光或 required 定义。配置为 `configs/cw/c-soft06.json`。

预期：可能提高官方覆盖 J 并降低不均匀扣分；也可能损失科学收益或错过 required/request。基线 factor 是估计值，条带还可能包含当前季节不可达的目标；乘数不是官方覆盖因子的精确梯度。

W 的动机是周预报可在最新简报发布前提供弱风险提示。只使用已通过 `new_messages` 收到、签发时刻不晚于当前决策的最近预报；只取该夜 `night_date` 名下的 rain/storm/overcast/haze/rocket_launch 方向。目标高度低于 75°、与预报八方向夹角不超过 67.5°时，候选预计收益乘 0.8；不叠加多个预报罚因子。ALL 没有可替代方向，因此不触发该乘数；预报不导致全夜停机。配置为 `configs/cw/w-forecast02.json`。

预期：可能减少预报风险方向的低收益观测；夜粒度预报也可能使本可成功的时段受到不必要的轻罚，降低总收益或增加 required 遗漏。温和乘数不保证完全避开风险方向。

## Implementation boundary

从 `agents/official/baseline` 复制独立研究 Agent，只在 planner 的候选 `achievable` 收益末尾增加 `CWPolicy.multiplier`。原始 baseline 源文件保持只读引用，研究副本保存在 `agents/cw/source`。C/W 每次分别从该共同 baseline 出发，未组合；关闭两个因子时乘数恒为 1，且跳过诊断日志。方向乘数没有进入 baseline 的 clean-sky/fault 诊断判断，因此预报不间接改变“天气解释故障”的定义。

触发记录写入标准错误的 `cw:` JSON 行，避免污染协议输出。记录每次规划中唯一被评估候选数、C 加权数、W 轻罚数、最终选择中的对应计数，以及已收到预报数量与当夜匹配方向。触发率为至少出现一个受影响候选的规划次数/全部规划次数；候选率与选择率另列。这些是规划影响的机会计数，不能视为官方天气命中率。

## Results

两个 control 都通过：`r2-c-control-demo` 与 `r1-official-demo-repeat`、`r2-c-control-dev-season` 与 `r1-official-dev-season` 的规范化 actions SHA-256 及规范化官方 score SHA-256 均完全相同。总分分别仍为 1082.572141 和 −2232.887855。验证材料为 `agents/cw/control-*-validation.json`。公开输入边界检查 `agents/cw/selftest.py` 验证关闭因子恒等、RA wrap、C 有界及阈值更新、未来签发预报拒绝、夜日期过滤、W 方向/高度边界、ALL 不全局轻罚、较新预报取代旧预报。

所有 R2 参数保持第一次跑分前写定的配置，没有根据成绩修参数或重跑。四次均 `survey_complete`、退出码 0、无 baseline 内部异常回退、无 pace level 改变。真实运行时约 2.4–4.5 秒，全球两个 simulator 槽锁生效；同源码并行发生的实际 peer 与 load 记录保存在 manifest。所有调用均关闭 LLM。开发 season 数据仅是该日期规模的本地合成样本，不代表线上 αβ。

| 方向 | 卡片 | 总分 | 相对 baseline | 必观测遗漏（baseline） | 官方覆盖 J | J 变化 |
|---|---|---:|---:|---:|---:|---:|
| C 0.6 | demo | 1213.370613 | +130.798472 | 1（1） | 0.974486695 | −0.004581970 |
| C 0.6 | dev-season | −2270.806958 | −37.919103 | 66（65） | 0.535032390 | −0.004100270 |
| W 0.2 | demo | 891.582284 | −190.989857 | 4（1） | 0.979489340 | +0.000420675 |
| W 0.2 | dev-season | −2492.442866 | −259.555011 | 70（65） | 0.544543475 | +0.005410815 |

| 方向 | 卡片 | 全部规划数 | 有触发的规划数 / 率 | 受影响候选次数 | 受影响最终分配数 | 已收预报 / 有当夜方向的规划数 |
|---|---|---:|---:|---:|---:|---:|
| C | demo | 143 | 142 / 99.30% | 14142 / 38827 | 767 / 1629 | 不适用 |
| C | dev-season | 271 | 98 / 36.16% | 23571 / 94160 | 140 / 1922 | 不适用 |
| W | demo | 122 | 17 / 13.93% | 1878 / 35600 | 18 / 1407 | 1 / 31 |
| W | dev-season | 268 | 174 / 64.93% | 34503 / 94588 | 286 / 1877 | 2 / 239 |

C 的实际最大乘数仅为 demo 1.0960、dev-season 1.1134，小于 1.6 理论边界。它在本轮改变了观测轨迹，但“改善覆盖”的初始假设未成立：两卡 J 都下降。demo 加分来自 `sum_best_scores` +131.714865，覆盖多扣 0.916394，required/request/report 不变；dev-season 的科学分 +12.900951 不足抵消多漏一个 required 的 50 分和覆盖多扣 0.820054。不能把 demo 增分归因于覆盖改善。

W 的机会提示确实进入规划：demo 有 17 次、dev-season 有 174 次规划评估了匹配方向的候选。它们是启用数量，不是成功躲开真实天气的数量。它在两卡略改善了 J，却分别多漏 3/5 个 required，新增 −150/−250 的扣分；科学分另降 41.073992/10.637174，覆盖回收 0.084135/1.082163，request/report 不变。当前轻罚配置的净效果为负；这一证据不证明所有预报策略无效，也未识别每次预报提示是否准确。

全量结果为 [JSON](../agents/cw/results.json) 与 [CSV](../agents/cw/results.csv)。JSON 包含各 run 全部官方分项、计数、请求、report、曝光分布、耗时、终止原因、hash、并发条件和机制反馈。原始材料在 `runs/r2-c-soft06-{demo,dev-season}`、`runs/r2-w-forecast02-{demo,dev-season}`；每个 run 另有 `mechanism_metrics.json`，标准错误中保留每次规划的 `cw:` JSON 记录。

阶段在此结束，由主 Agent 决定是否让任何方向进入 R3；没有自动进入 R3，也没有读取或运行保留卡。
