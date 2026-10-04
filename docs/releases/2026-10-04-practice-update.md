# Practice update — 2026-10-04

本次推送用于在平台重新导入后测试 α、β 等练习卡。用户确认旧 GitHub 版本已经在线测试；本次尚无新版本平台结果。

- 修正模型连续调用和重试时的剩余时间计算，拒绝超出本次时间额度的回复。
- 加强 JSON、数值和建议字段检查；异常回复使用已有程序回退。
- 增加可选模型审计接缝及脱敏模块。默认不写审计文件，不改变默认启用模型的行为。
- 核心目标排序、几何搜索、曝光搜索未改变；研究候选 D 没有替换当前 Agent。
- 只提交这组 Agent 改动、相关构造测试与版本说明；实验运行原件、凭据及其它工作区改动不纳入此提交。

目录无需迁移。GitHub 项目的根 `observer.project.json` 继续以 `experiments/current/agent` 为工作目录，执行 `python3 -u agent.py`，镜像保持 `python:3.12-slim`。推送后需在平台重新导入或更新项目，核对版本再启动练习；仅推送不证明平台已采用新版本。

本次针对性验证为 28 项模型边界测试和 25 项审计测试，共 53 项；全部使用构造输入或假传输，不调用真实模型、不使用 Docker。提交归档另核对入口、新模块、文件数、大小和禁止路径。真实模型表现、平台耗时及非 16 根光纤适配仍需由练习运行确认。

复验入口：

```bash
/usr/bin/python3 -B -m unittest discover -s experiments/current/tests -p test_llm_boundaries.py
/usr/bin/python3 -B -m unittest discover -s experiments/current/tests -p test_model_audit.py
```
