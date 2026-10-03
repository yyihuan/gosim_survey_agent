# v4 experiment environment

权威约束见 [EXPERIMENT_CONTRACT.md](./EXPERIMENT_CONTRACT.md)。本轮固定官方快照 commit `18be105bc517938c8341ad79646cf397e3293016`，复制到 `vendor/starter_kit_v4/` 后设为只读，不改官方 runner、workflow、评分器或原 v3 Agent。35个文件的树 SHA-256 为 `90b39b0fee7133630bcc1ba2c30b509631458dd7b4529b13ff49f4bed703db5c`；文件清单与散列定义见 [snapshot_manifest.json](./vendor/snapshot_manifest.json)。

本机使用 `/usr/bin/python3` 3.9.6，标准库即可运行。官方要求≥3.9，平台使用3.12；本地R1锚点已经复现，不能据此宣称所有平台环境差异均不存在。每个run记录实际解释器、平台、精确argv/cwd、源代码/卡片/配置hash、开始结束UTC、退出码、终止原因和资源并发条件。

![运行隔离](./harness/docs/diagrams/v4-run-isolation.svg)

稳定入口为 [run_one.py](./harness/run_one.py)，参数说明与完整命令见 [harness README](./harness/README.md)。Agent挂载接受目录或入口文件，运行时只使用本次可写副本。源码、卡片、配置分别保留只读归档；官方输出、Agent cwd、临时目录和scratch各run独立。卡片truth仅供官方环境评分，Agent不读卡片。强制无LLM，不继承宿主环境或`.env`。

本harness的所有worker共用最多两个simulator槽。`--exclusive`原子取得两个槽。锁fd传入runner，使harness异常退出时仍由存活runner持锁；正常退出后释放。外层超时只清理本次记录且身份匹配的proxy进程组及本次runner，保留失败材料。外部直接绕过harness的命令不在锁的机械约束内。

协议转发器逐字节转发消息，额外记录每个公开decision_request中的remaining wallclock。它增加少量真实耗时，仍计入官方预算。官方baseline会按剩余预算调整pace，并发争用可能使轨迹变化，因此预算、并发条件、pace变化和wallclock轨迹必须一起解释。跨进程重叠验证使用UTC墙钟；本机Python3.9的monotonic零点为各进程独立，不能直接跨进程比较。

R1已保存的结果：

| Run | Total | Required missing | Observe actions | 实际耗时秒 | 终止原因 |
| --- | ---: | ---: | ---: | ---: | --- |
| r1-official-demo | 1082.572141 | 1 | 123 | 2.134 | survey_complete |
| r1-official-demo-repeat | 1082.572141 | 1 | 123 | 2.139 | survey_complete |
| r1-idle-demo | −6200 | 120 | 0 | 0.187 | agent_finished |
| r1-harness-demo | 1082.572141 | 1 | 123 | 2.337 | survey_complete |
| r1-official-dev-season | −2232.887855 | 65 | 154 | 4.150 | survey_complete |

两次原始demo baseline及harness demo的actions、score_report、decisions、observations逐字节一致。原始baseline的actions hash为 `84fc87d0de2e2e60a2f9cc6cebf02d05cc5c90d4cbbac1a8343f8dc27bfc7b1b`，score_report hash为 `220e1ea59e7edec3f5a35dd2017b8492315b2b7c91dbe5708140511dbf8e52cd`。最初三次直接运行没有协议遥测；其源码和卡片归档在运行后补充，并明确标记 `provenance_backfilled_after_run`，保留原命令、时间和输出。

跨进程验收通过三项：最多两槽、独占不重叠、harness退出后继承fd仍持锁。慢Agent的外层0.5秒故障验证保存在 `runs/r1-harness-guard/`，终止为 `harness_guard_timeout`、无官方分数；本次proxy和runner已退出。此记录不纳入科学策略比较。

统一 [metrics.py](./harness/metrics.py) 只读官方原始结果，不重评分。它保存总分与各分项、required、由官方覆盖扣分反推的J、请求、report、观测数、曝光分布、模拟观测时间、程序真实耗时、pace和hash。各派生量的定义及舍入限制在每份 `metrics.json` 的 `definitions` 中。

R1里程碑（2026-10-02）：当时已实测成本为七夜2400源demo约2.34秒、14夜4800源研究卡约4.15秒；长季四个月卡当时尚未运行，成本未知；当时保留集没有运行或提前分析。官方每卡最多900秒计时预算，另有初始化和结束宽限；默认外层保护上限为 `min(wallclock,900)+init_timeout+grace+60`（缺省1020秒）。不把demo耗时线性外推为全季保证。

dev公开几何分析见 [public_geometry.json](./runs/r1-official-dev-season/public_geometry.json) 和逐源CSV。只使用公开目录、夜历、场址、评分阈值与已有baseline轨迹；连续窗口以恒星时解析求交，并用官方exact minimum-altitude函数复核9507个60/900秒区间。所有required至少有60秒窗口，因此无窗口不能解释65个缺失；这不证明天气和深度可达标。没有重抽seed或修改数据。

R5最终状态（2026-10-02）：预注册的两张保留卡已开封，13个冻结配置共26/26次运行完整完成，均为 `survey_complete`，26份官方报告齐备，pace变化为0。运行前后冻结检查全部通过；没有重试或新增配置。最终执行与结果记录以 [r5_results.json](./evaluation/r5_results.json) 为准，全局解释以root报告为准。
