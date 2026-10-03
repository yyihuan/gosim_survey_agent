# Current environment

日期：2026-10-03。当前选择 **Python**。已有策略、隔离运行器、指标工具和报告构建器均使用 Python；新示例只用标准库，不需要增加包管理或编译步骤。TypeScript 需要 Node ≥18 与构建依赖，Rust 需要 Cargo 和依赖编译。它们有各自价值，但本轮目标是接续现有实验，没有语言迁移收益的证据。

Python并不获得额外900秒，Rust也不会缩短模型等待或后端积分。真实上限对所有语言相同，编译发生在观测计时之外。Rust可降低策略CPU计算成本，只有当前算法受到计算瓶颈且策略一致时，才能据此扩大搜索；两份示例的搜索参数不同，尚无同算法Rust对照。当前Python四卡已经完整结束，因而先保留Python；此选择不证明Python最快或分数最高。

## 版本与来源

从 [官方 examples](https://github.com/gosimfoundation/hackathon-survey26/tree/149c6590c49cf289c325b8e2fedfee1035975c6f/examples) 下载固定提交 `149c6590c49cf289c325b8e2fedfee1035975c6f`，以 `git archive` 导出到 `research/2026-10-03/latest-149c659/`。包含三种语言的原件、完整 L1–L4、官方本地运行器及相关文档。逐文件散列在 [快照清单](../research/2026-10-03/latest-149c659/snapshot_manifest.json)；文件设为只读。原 `research/2026-10-02/upstream` 的 HEAD 仍为旧提交，仅更新了远端引用供下载。

裁判自带 [ENGINE_MANIFEST.json](../research/2026-10-03/latest-149c659/examples/_local/runner/ENGINE_MANIFEST.json)，标注引擎来源提交 `db4bddf3cc67fb5f0036d9fb2cf90b9e2b7e8f4a`；这与示例仓库快照提交不同，不能混写。16 个文件已通过自带校验。在官方 Git 历史中，旧 `18be105` 与当前提交的 `challenge/v4_workflow.py`、`v4_scorer.py`、`v4_runner.py` 没有差异；这不是整个环境或策略等价的证明。

![当前与历史环境关系](diagrams/current-experiment-environment.svg)

`examples/_local`已经包含在最新快照中，独立于Python目录；详情见[目录与规则](v4-rules-and-protocol.md)。`ce6b88b`初次迁移原件继续保留作v4证据，当前机械入口已切换到`149c659`。

## 路径与权威

| 路径 | 用途 |
| --- | --- |
| `experiments/current/environment.json` | 当前版本、运行时、卡片和默认入口的机械权威 |
| `experiments/current/agent/agent.py` | 可修改的新版 Python Agent 入口 |
| `experiments/current/agent/agent_core/` | 当前策略、状态、几何、估分、验证与模型客户端 |
| `scripts/run_current.py` | 当前实验入口，适配新官方 runner |
| `experiments/current/runs/<run-id>/` | 每次独立源码、卡片、配置、协议遥测和官方结果 |
| `research/2026-10-03/latest-149c659/examples/_local/runner/` | 未修改的官方裁判 |
| `research/2026-10-03/latest-149c659/examples/_local/cards/L1`–`L4` | 完整公开本地练习卡 |
| `experiments/v4/` | 旧提交上的冻结策略研究与复现入口 |
| `experiments/current/datasets/` | 模拟数据、用途、私有重现配置、结构校验和参照批次；契约见 [test-datasets.md](test-datasets.md) |
| `scripts/build_simulation_dataset.py` | 固定生成器构建入口，配方变化使用新数据版本 |
| `scripts/run_simulation_dataset.py` | 离线批量入口，复用本页运行契约并拒绝冻结组 |

当前本地使用已验证的 `/usr/bin/python3` 3.9.6；最低要求为3.9，平台项目清单仍指定 `python:3.12-slim`。本轮未安装依赖，也未验证平台镜像中的执行。工作区根目录不是 Git 仓库，当前变更以文件与散列追踪。

## 一次完整运行

从项目根目录执行：

```bash
/usr/bin/python3 -B scripts/run_current.py --run-id my-python-L1-001 --card L1 --exclusive
```

双击根目录 `run_local.command` 也可运行 L1，它自动生成新 run-id。已有目录会拒绝覆盖。用 `--card L2`、`L3`、`L4` 选择其他公开练习卡。`--agent` 接受目录或 Python 文件；`--entry` 指定目录内入口；`--config` 保存原始配置并提供 `EXPERIMENT_CONFIG_PATH`，具体策略是否使用该配置由策略实现决定。

每次至少读取 `manifest.json`、`metrics.json`、`output/score_report.json`、`output/workflow_result.json` 和 `output/agent.log`。分数来自官方原始报告，指标提取只读结果，不重新评分。确认终止原因、缺失项、动作数、程序耗时与错误日志；`survey_complete` 不保证所有任务完成。外层异常时 `metrics.total=null`；如有部分成绩则另存 `partial_total`，不能纳入完整策略对照。

复用旧策略时显式提供原源码与冻结配置，例如：

```bash
/usr/bin/python3 -B scripts/run_current.py --run-id old-D-new-L1-001 --card L1 \
  --agent experiments/v4/agents/combined/source \
  --config experiments/v4/configs/tdg/d-linear.json --exclusive
```

这会生成新环境下的独立结果，不能补写到旧84或97条研究登记。运行接口兼容也不表示新旧轨迹或分数相同。

## 离线与 LLM

新版官方 Agent 在读 stdin 之前强制检查 API key，原件无密钥会退出；也没有实现旧 `USE_LLM=0`。工作副本只在 `agent_core/llm_client.py` 增加一个局部开关：`USE_LLM=0` 时跳过密钥要求，`ask_json()` 返回 `None`，规划器继续已有程序回退。默认值为1，直接运行或打包的默认模型行为仍保持上游要求。

当前实验入口始终传 `USE_LLM=0`。不复制 `.env`、不继承用户 shell 凭据，拒绝配置中的密钥、token 与 `OPENAI_*` 字段。它向官方 runner 使用 `--inherit-env`，但继承的是入口主动构造的干净白名单。此措施防止意外继承，**不是 OS 网络或文件访问沙箱**；其他自定义 Agent 必须遵循实验契约。

新版默认每晚两项模型建议（预报、公告加命中率），另有罕见故障确认；源码默认单次12秒、整局300秒、最多100次、每题最多3次尝试。本轮只验证离线模式，没有使用真实模型、评估这些建议的收益或验证延迟。LLM 协作设计页仍是此前设计，不能当作新版已实现的功能清单。

## 隔离、超时与清理

每run复制只读 `source_snapshot/` 与 `card_snapshot/`，Agent 在独立可写副本运行，`tmp/`、`work/` 与输出分离。完整卡的 truth 由官方裁判读取；Agent 只接收公开协议。没有容器挂载隔离，可信研究代码不得自行读卡片文件。

入口复用旧 harness 的快照、指标、协议代理与两槽锁，避免维护第二套知识。当前默认最多两个模拟器；`--exclusive` 同时取得两槽。第二批旧实验曾使用独立六槽执行器，当前锁不能机械约束绕过它的运行。因此不要同时启动其他批次的独立执行器。

官方预算为卡片与900秒上限中的较小值。外层默认再加120秒供初始化、结束与清理；`--process-timeout` 可缩短故障验证。超时保留产物，只处理本次已记录且身份匹配的进程组。新运行前检查是否有旧进程或其他 session 在占用实验资源。

## 验证入口

```bash
/usr/bin/python3 -B research/2026-10-03/latest-149c659/examples/_local/runner/verify_engine.py
/usr/bin/python3 -B -m unittest discover -s experiments/current/tests -v
node /Users/cxjh168/.codex/skills/document-diagrams/scripts/diagram.mjs check docs/current-environment.md
```

初次迁移的端到端与故障证据见 [迁移验证](../experiments/current/validation.json)；最新快照复核见 [当前验证](../experiments/current/validation-current.json)，最新L1全链路结果见 [rules-refresh-python-L1](../experiments/current/runs/rules-refresh-python-L1/metrics.json)，协议专项验证见 [verification.json](../experiments/current/rules-audit/evidence-refresh/verification.json)。L1–L4 是公开开发/回归资料，与正式 α–δ、历史生成卡及未见保留集均不同；它们的分数不能与截图榜单直接比较。

模拟数据构建和三阶段评价见 [数据集契约](test-datasets.md)。数据工具复用本页的离线、两槽、超时与证据规则；当前Agent和官方评分器未因扩样而修改。
