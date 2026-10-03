# Session handoff

更新时间：2026-10-03。最新完成：用户确认数据方案和模拟开发 → 官方练习卡复测 → 线上测试流程，已构建首版72张模拟卡。全部通过结构、几何、消息一致性校验；6张非冻结代表卡完整离线运行通过。配方、数据用途、信息边界和证据统一见 [数据集契约](test-datasets.md)，原始状态见 [数据清单](../experiments/current/datasets/sim-v1-20261003/manifest.json)，验收见 [acceptance.json](../experiments/current/datasets/sim-v1-20261003/acceptance.json)。没有改变规划算法、调用真实模型或线上提交。冻结组未运行候选；当前仍缺少对同一系统用户的OS访问隔离，天文扩展尚未做历史天气校准。

先前讨论成果保留：在 [方法论](agent-optimizer-methodology.md)基础上，经用户前置核对形成 [方案大纲](agent-optimizer-outline.md)与 [核对记录](agent-optimizer-decisions.md)。原讨论轮只交付大纲；用户后来确认方案并授权数据构建，本轮推进M1，未开展候选策略搜索或独立评审。此前的 Python 环境迁移与完整链路验证仍按下文保留。

## 开始工作先看什么

1. [当前环境](current-environment.md)：入口、运行方法、版本与边界。
2. [实验历史](experiment-history.md)：前两轮研究、四卡阻塞与LLM讨论。
3. [当前复核](../experiments/current/validation-current.json)和[专项验证](../experiments/current/rules-audit/evidence-refresh/verification.json)；初次实跑保留在[迁移原件](../experiments/current/validation.json)。
4. 按任务进入[文档索引](README.md)列出的详细报告与契约。
5. 模拟开发入口与三阶段测试使用 [数据集契约](test-datasets.md)；其验收脚本只核对结构和已有参照证据，不评分冻结组。

若任务是评审首版方案，先读 [大纲](agent-optimizer-outline.md)与 [核对记录](agent-optimizer-decisions.md)，再按问题进入 [方法论](agent-optimizer-methodology.md)及上述权威来源。用户要求大纲层级，具体实现以后细化，策略作为可替换实例。

当前机械环境定义为 [environment.json](../experiments/current/environment.json)；策略入口为 [agent.py](../experiments/current/agent/agent.py)。当前快照提交为 `149c6590c49cf289c325b8e2fedfee1035975c6f`，初次迁移原件为 `ce6b88b`，裁判引擎清单来源提交另为 `db4bddf3cc67fb5f0036d9fb2cf90b9e2b7e8f4a`。历史v4冻结研究仍为 `18be105`，不重写其版本。

## 已有环境证据与结论

[当前验证记录](../experiments/current/validation-current.json)全部检查通过；首次[迁移原件](../experiments/current/validation.json)保留当时版本；可运行 `/usr/bin/python3 -B experiments/current/validate.py` 复核已有材料，不重新跑模拟。

- 新版Python离线工作副本完整运行L1–L4，均为 `survey_complete`，每卡约21–24秒。L1–L4各有独立run，名字为 `migration-python-L1` 至 `migration-python-L4`。
- L1另跑一次，动作、决策、观测和评分报告逐字节一致；时间遥测不要求一致。
- 新Agent日志未出现初始化、规划或动作校验错误，五次新Agent运行均记录 `llm_calls=0`。离线单元测试确认即使存在伪造测试密钥也不会尝试HTTP；默认模式仍拒绝无密钥启动。
- 旧D源码与冻结配置在新裁判/L1下完整运行，记录为 `migration-old-D-L1`。这证明当前接口可接入这项历史参照；没有证明E、FE、DTGP全部兼容，也没有在新版上重新研究它们。
- 1秒超时试验为 `migration-guard-timeout`，退出124，完整分数为null，诊断材料保留。本轮所属runner/proxy与子进程均已退出。
- 官方16个引擎文件校验通过。旧vendor、旧harness和此前冻结清单保护的8个结果文件散列均保持一致；没有改写历史84/97条登记。
- 工作副本相对上游的差异见 [upstream-local.patch](../experiments/current/upstream-local.patch)：模型客户端增加离线开关，入口注释与本地说明更新；没有修改规划算法或评分器。验证记录保存本次每run的实际源码散列与当前工作副本散列。

当前公共卡均是调试与回归材料；正式α–δ状态仍是缺少本地完整产品，四次预检未启动Agent。新L卡不解除该阻塞，平台成绩仍需实际评测。

最新源码与初次迁移的裁判核心一致，新增L1复跑用于确认当前入口及快照引用。删除清单见[cleanup-v3.json](../experiments/current/rules-audit/cleanup-v3.json)；既有v4原始轨迹、分数、冻结配置和84/97条登记保留。

## 下一步如何选择

当前后续入口是 [模拟开发与评价](test-datasets.md)：基于已构建数据集进入M2对照底座或首个M3课题，先登记问题、固定参照、查询预算、指标与晋级门槛。用户已确认比赛效果优先、首版由 Codex 驱动本地研究工具；完整决定以 [核对记录](agent-optimizer-decisions.md)为准。首个研究问题、真实模型及其预算、数值门槛仍需在对应实施节点确定。总体大纲继续保留供独立评审，数据构建不等于其他节点已完成。以下是原有各方向的背景，继续执行时以新的明确任务范围为准。

若后续进入程序研究：数据扩充已有首版，先按 [大纲](agent-optimizer-outline.md)建立研究对照与查询约定，保留新版官方示例为参照。旧D/E/FE/DTGP可按原冻结参数逐项验证兼容、另建运行登记，不能直接认定某个方案在新卡最优。历史机制诊断使用既有轨迹，不在已经揭示的保留卡上继续筛参数。模拟冻结组正式评价前须补齐访问隔离与冻结候选的评价入口。

若继续LLM研究：按 [方法论](agent-optimizer-methodology.md)先确定验证对象及首个能力缺口，再形成最小闭环；[协作设计](v4-llm-collaboration.md)中的异常诊断和阶段规划是候选例子。先做模拟客户端、错误/超时与回退，再准备真实调用的授权包。新版每晚两问与统一协作层不是同一实现。现有材料没有真实模型效果、延迟、费用或评奖资格的实证。

若继续正式四卡：使用现有固定候选与原始公开包，先确认平台评测路径和当前规则；不补造天气/truth、不把本地L卡成绩填入α–δ。真实账号、凭据、模型调用与提交按全局受控试用路由办理。

## Session 协作与维护

运行前查看锁与现有进程；当前入口复用两槽锁，第一批、第二批的独立执行器不可与它无协调混跑。使用唯一run-id，不覆盖结果或在原件上调参。运行失败保存原件，区分执行故障、部分成绩和完整模拟中的科学负分。

更新版本时重新固定提交与快照清单，保留旧版本的证据链。文档分工见 [文档索引](README.md)：环境页维护运行契约，历史页引用证据，方法论页维护研究原理，大纲维护首版开发结构，核对记录维护决定及未知，本页维护当前状态与下一步。官方上游AGENTS/README中的密钥和上传教程不等于本session已获真实执行授权。
