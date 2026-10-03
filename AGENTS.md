# Session routing

中文正文为规范文本。适用用户提供的全局核心原则与契约路由。

- 开始本项目工作，先读 `docs/README.md`、`docs/session-handoff.md`、`docs/current-environment.md`；结果与讨论背景见 `docs/experiment-history.md`。这些文档引用原始证据，不另抄一份分数或实验契约。
- 当前环境的机械权威为 `experiments/current/environment.json`，入口为 `scripts/run_current.py`。官方只读快照路径由 environment.json 的 snapshot_manifest 指定，最新为 `research/2026-10-03/latest-149c659/`。策略工作副本为 `experiments/current/agent/`。
- 当前正式协议为 v4。`experiments/v4/` 保留固定旧提交的 v4 历史研究；不要覆盖原始运行、登记、冻结配置或官方评分器。复现历史时使用对应历史入口。
- 规则与消息语义见 `docs/v4-rules-and-protocol.md`，源码理解与本地 graphify 入口见 `docs/python-source-map.md`；示例策略约束不等于裁判规则。
- 本地程序实验使用明确的离线模式；不得继承真实凭据或读取 `.env`。真实模型调用、线上提交与账号操作按全局受控试用路由处理，不从示例自带说明推导授权。
- Agent 只从公开协议消息获取观测信息。完整卡中的 truth 仅供官方环境运行与评分；不得挂给模型或用于策略未来信息。目录隔离不等于 OS 沙箱，研究 Agent 不主动读取卡文件。
- 已揭示的历史保留集只能做回归。公开 L1–L4 也不能称盲测；下一轮策略结论需要先登记数据分组与冻结条件。
- 更改当前入口、版本、验证结果或下一步决定后，同步 `docs/session-handoff.md` 与相关权威文档。图只改 `docs/diagrams/*.mmd` 并重新渲染、检查。生成 HTML 从已有构建脚本更新。
