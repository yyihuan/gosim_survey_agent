# v4 experiment harness

从工作区根目录执行。官方 runner 与评分器来自只读 `../vendor/starter_kit_v4/`，本执行器只负责隔离、锁、记录和指标提取。

```bash
/usr/bin/python3 -B experiments/v4/harness/run_one.py \
  --run-id r2-my-direction-demo \
  --stage R2 \
  --agent experiments/v4/agents/my-direction \
  --card experiments/v4/vendor/starter_kit_v4/cards/demo
```

`--agent` 接受目录或 Python 入口文件。目录缺省寻找 `baseline_agent.py`、`agent.py`、`main.py`；其他名称使用 `--entry relative/path.py`。`--run-id` 必须唯一，已存在目录不会被覆盖。`run_one.py` 和 `run.py` 使用同一实现。

可选 `--config params.json`。JSON 原始字节归档为 `run/config.json`，并复制为 Agent 的 `experiment_config.json`。Agent 通过环境变量 `EXPERIMENT_CONFIG_PATH` 得到它相对自身 cwd 的路径。执行器不会解释策略参数；配置中的 `environment` 对象用于配置字符串环境值，也可使用重复的 `--env KEY=VALUE`。本轮强制 `USE_LLM=0`，不继承宿主环境、凭据或 `.env`。

所有调用共用最多两个 simulator 槽。`--exclusive` 原子占用两个槽，适用于 baseline 和可比性复验。锁等待时间和已有 peer 记录在 manifest。策略会读真实剩余 wallclock，故并发资源争用仍可能改变其自适应 pace；应检查 metrics 的 pace 记录。

每次输出到 `../runs/<run-id>/`：只读 `source_snapshot/`、只读 `card_snapshot/`、配置与 hash 清单、独立的可写 `agent/`、`work/`、`tmp/`、官方原始 `output/`、`runner_stdout.json`、`runner_stderr.log`、`manifest.json` 和统一 `metrics.json`。策略源码以 `source_tree_sha256` 比较；执行目录 hash 另含生成的运行元数据，可能随 run 路径变化。

重新提取某个 run 的指标，不重跑评分器：

```bash
/usr/bin/python3 -B experiments/v4/harness/metrics.py experiments/v4/runs/r1-harness-demo --write
```

检查进程锁：

```bash
/usr/bin/python3 -B -m unittest discover -s experiments/v4/harness/tests -v
```

`--wallclock` 默认900秒，只能由官方 runner 下调至卡片与平台允许值。外层 `--process-timeout` 默认 `min(wallclock,900)+init_timeout+grace+60`；超时或中断保留失败材料并只清理本轮记录的 PID/进程组。官方正常终止原因与外层失败状态分开保存；缺少官方报告时 `total=null`，不能当科学策略分数。

全季成本应实测。R1 七夜 demo 在本机约2秒，不能据此外推长季卡。完整官方流程最多占用900秒计时预算，另有初始化与退出宽限。本轮没有运行未授权外部卡或保留集。
