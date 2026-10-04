# 巡天智能体实验工作区

当前正式协议为v4，环境固定到2026-10-03核对的官方提交`149c659`，默认使用Python离线工作副本与完整公开L1–L4。

## 竞赛提交 / Competition submission

2026-10-04 练习测试更新：模型调用预算、回复校验和可选审计已修正，核心搜索策略保持原方案；范围与验证见 [本次版本说明](docs/releases/2026-10-04-practice-update.md)。

本仓库即比赛的**完整项目**来源：根目录 `observer.project.json` 是平台项目清单，`working_directory` 指向
`experiments/current/agent`，`run` 为 `python3 -u agent.py`。平台会把整仓归档校验为项目（清单须位于归档根、
上限 50 MB 压缩 / 100 MB 解压 / 10,000 文件），因此本地大体积运行产物、私有种子、正式任务卡与随仓库携带的
`.git` 均已由 `.gitignore` 排除。提交前可本地打成 ZIP 复核：

```bash
cd experiments/current/agent && /usr/bin/python3 -B pack_agent.py --out /tmp/python-agent.zip
```

主办方材料（`research/`、`docs/` 中转录内容）依 CC BY-NC 4.0 使用，署名与范围见 [NOTICE.md](NOTICE.md)。

- 后续session先读[文档索引](docs/README.md)、[交接状态](docs/session-handoff.md)、[当前环境](docs/current-environment.md)；历史证据见[实验历史](docs/experiment-history.md)。
- [完整规则与后端消息](docs/v4-rules-and-protocol.md)及[交互讲解HTML](docs/survey-rules-explorer.html)：跨slot、时间、消息、计分、源码边界和赛事政策。
- [Python源码地图](docs/python-source-map.md)：UML对象关系、决策流程、后端状态与本地graphify导航。
- [模拟与现实差异](docs/v4-observing-gaps.md)维护外推边界。
- 首版方案仍供评审：[大纲](docs/agent-optimizer-outline.md)、[核对记录](docs/agent-optimizer-decisions.md)、[方法论](docs/agent-optimizer-methodology.md)。
- [既有策略报告](docs/v4-strategy-study-report.md)及[策略讲解](docs/v4-strategy-study.html)保留84/97条v4研究证据；[程序与LLM协作](docs/v4-llm-collaboration.md)及[讲解](docs/v4-llm-collaboration.html)是后续设计，未验证真实模型收益。

## 运行与验证

双击`run_local.command`，或从根目录执行：

```bash
/usr/bin/python3 -B scripts/run_current.py --run-id my-L1-001 --card L1 --exclusive
/usr/bin/python3 -B experiments/current/validate.py
```

当前机械权威是[environment.json](experiments/current/environment.json)。[_local完整示例](research/2026-10-03/latest-149c659/examples/_local/)独立于Python子目录。当前结果写入`experiments/current/runs/`唯一目录，LLM关闭；不继承真实凭据。历史v4复现使用[原入口](experiments/v4/harness/README.md)，不得覆盖冻结数据和运行登记。

## 文档构建

正文在docs的Markdown中维护，图只改`docs/diagrams/*.mmd`并渲染同名SVG，HTML为生成产物。规则页整合规则正文和源码地图，没有第二份手写规则。以下操作不调用模型或运行模拟：

```bash
node /Users/cxjh168/.codex/skills/document-diagrams/scripts/diagram.mjs render-all docs/diagrams
node scripts/build_rules_explorer.mjs
node scripts/check_rules_explorer.mjs
/usr/bin/python3 -B scripts/build_strategy_study.py
node scripts/build_llm_collaboration.mjs
node /Users/cxjh168/.codex/skills/document-diagrams/scripts/diagram.mjs check-all docs/diagrams
```

本地AST关系图使用`/usr/bin/python3 -B scripts/build_source_graphs.py`重建；工具在临时源码副本分析，避免缓存进入官方只读快照。graphify Studio需本地静态服务，规则讲解HTML无需服务器。规则专项验证可指定新输出目录：

```bash
/usr/bin/python3 -B experiments/current/rules-audit/verify_interaction.py --out /tmp/survey-rules-check-001
```

重新核对规则时固定新提交，复核源码与协议，再更新规则权威和交接页，不把公开卡称为盲测。真实模型、账号与线上提交按根AGENTS的受控试用路由办理。
