# TDG组合接口

源码权威入口是 `source/`，策略运行入口为 `source/baseline_agent.py`。共同harness传入 `EXPERIMENT_CONFIG_PATH`；缺省则读取入口旁`strategy_config.json`，不存在时使用neutral默认值。准确信息与全部开发结果以 `../../notes/tdg.md` 为准，不从当前源码推断旧run版本；旧run保留`source_snapshot`和hash。

![TDG作用位置](./docs/diagrams/tdg-planning-hooks.svg)

| 配置字段 | neutral默认值 | 作用位置 |
| --- | --- | --- |
| strict_slot | false | `plan` horizon、离散duration截断、格尾wait；当前格以夜晚开始为原点 |
| exposure_cap_seconds | 缺省，沿用公开instrument max | 只改变规划的`max_exposure`；原合法上限另保存在`instrument_max_exposure` |
| conditional_long_exposure | false | 应急目标在`achievable`前用原上限估计；最终超过cap的候选须使至少一个应急目标跨越当时未达门槛 |
| science_exponent | 2.0 | `_science_gain`：value剩余收益、achievable、曝光搜索三处同一科学代理；required/request奖励不变 |
| geometry_strength | 0.0 | 只乘`achievable`，从30度到天顶增加0～strength的软权重；曝光搜索不重复乘 |

T条件上限用两个阈值来源：未达到0.5的required；当前`request_bonus>0`代表的未完成活动request及其`request_threshold`。同一个目标可有两类阈值，各自检查；只要最终长曝光跨越其中一个在短曝光下不可达的门槛，即有长曝光资格。新request不以全季factor代替其进度。仍沿用baseline的value/DONE规则及门槛，没有额外科学加权。

最终`_finish_plan`构建pending时使用选出的最终duration。Agent每个observe响应前断言`pending_duration == duration_seconds`；strict_slot再断言不跨格。条件上限的每次长曝光写一条 `tdg: conditional cap override duration=... eligible_threshold_targets=...`，eligible是预测中达门槛的不同目标数，不能当作官方真实完成数。

组合集成必须复验：

1. 所有因子关闭，在demo与dev-season用共同harness独占复验；`actions.jsonl`、`score_report.json`与官方baseline字节一致。TDG在R2已经分别通过；合入其他家族后应重新通过。
2. 每个单开关使用已测配置，分别在两开发卡与原run比较normalized actions和官方score，不能只看总分近似。当前R2与R3的source版本不同，但inactive新增hook都保持baseline运算。
3. T strict与conditional-cap是两个不同已测变体；不要把strict=true误带入conditional配置，否则slot horizon仍限制应急长曝光。D p=1与G strength=0.5也分别是独立参数。
4. 组合运行的源码/配置hash另存；不改原run、不读取保留集选参数。`../tdg/mechanism_metrics.py`可从结果与公开目录复算时长、跨格、命中高度及条件覆写次数，生成物用新文件名防覆盖。

局部测试入口：`/usr/bin/python3 -B experiments/v4/agents/tdg/selftest.py`。测试只使用demo公开initialize与合成反馈，含180次neutral与baseline逐动作一致、严格T的150秒格尾曝光/30秒等待、900秒cap可跨格、required/request重叠阈值、新request进度、D指数形状、G软权重边界。

详细R2/R3预注册、负结果、命令和指标位置位于 `../../notes/tdg.md`；机器汇总位于本目录`validation/r2_summary.json`、`validation/r3_first_summary.json`及第二组汇总。单族最终选择由主Agent确认。

主Agent已经确认冻结T=`configs/tdg/t-cap900-conditional.json`、D=`configs/tdg/d-linear.json`、G=`configs/tdg/g-soft05.json`（路径相对v4根）。当前源码hash为 `acfac5e70c1cd8977ee3c9b46a91dd807736ead6b063b0a8b3277140def1278e`。源码和这些配置可用于组合集成，TDG不再改参数。T2两卡25/41次长曝光均有预测门槛触发日志，长曝光计数与日志数量一致，pending/请求/实际时长检查通过。D/G在R2版本的原run已测；当前版本新增inactive hook通过180次neutral局部等价测试，组合版本仍必须对照原run复验单开关。
