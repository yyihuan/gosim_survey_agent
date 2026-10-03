# Documentation index

后续 session 先读 [交接状态](session-handoff.md)，再按任务进入以下权威来源。当前主入口采用 2026-10-03 下载的官方 Python 示例；既有v4实验仍按原版本归档。

总体方案已获用户确认，首版模拟数据已经构建，数据与三阶段评价见 [数据集契约](test-datasets.md)。[方案大纲](agent-optimizer-outline.md)和 [前置核对记录](agent-optimizer-decisions.md)继续保留供独立评审，涵盖首版架构和开发节点。研究原理见 [Agent 优化器方法论](agent-optimizer-methodology.md)，具体策略细节仍由历史报告维护。

| 要了解什么 | 权威入口 |
| --- | --- |
| 当前做到哪里、下一步与边界 | [session-handoff.md](session-handoff.md) |
| 模拟开发、官方复测、线上测试及数据构建 | [test-datasets.md](test-datasets.md) |
| 版本选择、目录、运行、隔离和验证 | [current-environment.md](current-environment.md)；机械设置见 [environment.json](../experiments/current/environment.json) |
| 已经跑过和讨论过什么 | [experiment-history.md](experiment-history.md) |
| 首版开发节点、组件边界、数据扩充和解耦方案 | [agent-optimizer-outline.md](agent-optimizer-outline.md)，当前供用户和其他 Agent 评审的大纲 |
| 用户已确认什么、哪些是建议、未知何时处理 | [agent-optimizer-decisions.md](agent-optimizer-decisions.md)，本轮无知审判核对结果 |
| 离线研究、在线规划与纠错的总体方法论；后续评审 | [agent-optimizer-methodology.md](agent-optimizer-methodology.md)，含职责、接口、能力边界、验证设计与未决问题；供评审草案 |
| 第一批与第二批策略的完整证据 | [策略报告](v4-strategy-study-report.md)、[交互讲解](v4-strategy-study.html) |
| 当前规则、跨slot、所有后端消息、实现差异 | [规则协议](v4-rules-and-protocol.md)、[完整交互讲解](survey-rules-explorer.html) |
| Python源码对象、流程、状态、graphify导航 | [源码地图](python-source-map.md)，讲解HTML同页收录 |
| 模拟与实际观测的外推边界 | [差异说明](v4-observing-gaps.md) |
| 固定程序与 LLM 的具体接入示例 | [协作设计](v4-llm-collaboration.md)、[交互说明](v4-llm-collaboration.html)；属于拟议协作设计，不是模型效果实测 |
| 最新官方协议 | [固定快照的中文指南](../research/2026-10-03/latest-149c659/docs/v4-participant-guide-zh.md) |

维护约定：原始报告和运行清单拥有分数；本文档只解释和引用。历史报告保持当时版本范围，最新状态放在交接页。HTML 属于生成产物，具体构建方法沿用根 README。官方文档可能同时保留旧制度段落，须根据 v4 协议和当前实现核对，不能把所有段落当作当前线上事实。
