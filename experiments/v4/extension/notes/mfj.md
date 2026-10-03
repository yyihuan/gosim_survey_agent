# N2：M/F/J 独立初版

共同底座为 `experiments/v4/agents/combined/source` 与 `configs/tdg/d-linear.json`。新源码位于 `extension/agents/mfj/source`，只新增 M/F/J 开关；T/G/C/W 关闭，D 指数固定 1，P 保持 3 锚点。每方向只登记一个初始配置，读分后不自行调参。仅运行 demo、dev-season。

## 实现前核对与固定配置

- **M：反馈最佳科学分。** 原 D 保存已估计最佳 factor，收益为 `weight × max(after-before, 0)`，未保存已反馈最佳单次科学分。新增 `best_score[i]` 只接受已收到 observe hits；state_resync 使用协议公开账本替换它，以处理撤销。预测分为 `weight × min(k×duration,1) × multiplier`，其中匹配预测 program 使用对应倍率，否则使用公开 mismatch 倍率。收益为 `max(预测分-best_score,0)`。候选优先级使用最大 program 倍率的乐观上界；当前可实现值使用已学习 sky scale 与公开 lunar/airmass 模型判断 band；曝光选择联合枚举原时长和三个 program。required/request 奖励、几何和装填规则不变。非 required 不再仅凭 factor≥0.95 提前剔除，因为旧曝光 program 倍率较低时仍可能有真实科学分增量。`M.enabled=true`，无额外强度参数。
- **F：有限候选场收益率。** 原路径在原 3 锚点的纤维中心试场中按最长曝光潜在总值选唯一场，再按原时长候选选曝光。新增只保留潜在总值最高的 6 个不同场及其原装填。每场调用原曝光规划的只读 preview，比较 `原 D 科学/required/request 规划收益 ÷ 曝光秒数`，最终只对最高收益率场提交 pending。分母沿用原定义，不另估开销。preview 在所有 pending/待反馈状态写入前返回。没有扩大锚点，也不重做每时长的纤维分配。原 fast_level 和无可装填场时的原 fallback 保留。`F.candidate_fields=6`。
- **J：Jain 正向边际奖励（截断近似）。** 用公开目录计算每 RA 条带总目标数 `N_b`，用已估计 factor≥公开 uniformity 阈值的进度计算 `r_b=n_b/N_b`。令 `S=Σr_b`、`Q=Σr_b²`、`B=条带数`，`J=S²/(B Q)`；Q=0 时沿用官方 J=0。单源跨阈值后 `δ=1/N_b`，`ΔJ=(S+δ)²/[B(Q+2r_bδ+δ²)]-J`。奖励 `min(10, uniformity.weight×max(ΔJ,0))`，只给原估计未达标且本次预测达标者；负 ΔJ 不施罚。封顶 10 低于 required 规划奖励 60，初始空进度不会让奖励压倒 required。`J.maximum_reward_per_target=10`。

J 的单目标有限增量是 Jain 公式的精确变化，但 factor 来自策略估计。一次曝光内多个目标奖励相加是局部近似，未联合更新各条带计数，不称精确多源或整季收益。M 的新预测分仍受 band/天气估计误差影响，不称已知真实新得分。

## 验证与运行契约

使用 `extension/harness/run_one.py` 的独立六槽锁，所有输出写入唯一 `runs/ext-*`。先验证全关两开发卡，与原 D 对应 `actions.jsonl`、`decisions.csv`、`observations.csv`、`score_report.json` 逐字节比较。随后 M/F/J 各运行两开发卡，保存完整官方 metrics、源码/参数散列与 `mfj:` 机制日志；不读新保留卡，不读终局报告维护策略状态，不修改 vendor 或旧源码。

局部验证覆盖：M 重复曝光不重复计收益、program 匹配和不匹配、已收反馈及 resync 替换；J 的有限变化与直接 Jain 重算一致及奖励边界；F preview 不写 pending、最终提交一致。端到端完整季结果是本轮主要反馈。

日志中的 M/J evaluations 是规划函数调用数（含重复评估），不当作独立目标数。M 记录旧 factor 代理为正而分数边际为零的调用、已积累分的选中目标与预测增量；F 记录生成/保留/合法试算场数、是否改变潜在总值第一场、原潜在排序名次、最终率；J 记录正/负 ΔJ 条带、阈值跨越调用与获奖励选中数。后处理只汇总 run 输出，不重评分。

## N3：仅 F 候选场数 6→12

主 Agent 依据 N2 选择仅继续 F 一次。固定原 3 锚点、源码、D 底座、所有原曝光与装填规则，关闭 M/J/T/G/C/W。只把 `F.candidate_fields` 从 6 改为 12。运行前预期：更多候选可能找到较高的当前收益率，同时增加曝光试算成本；不保证季末总分提高。检验两开发卡总分与分项、改选率、计算量和墙钟，保留所有 N2 记录；不自动继续调参。
