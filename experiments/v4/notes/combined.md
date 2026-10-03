# Combined R4

2026-10-02，运行前记录。主Agent冻结单项：T=cap900-conditional、D=线性p1、G=soft0.5、P=12、C=soft0.6、W=forecast0.2。独立实现入口为 `../agents/combined/source`，输入源码hash链见该目录上一层的 `integration_manifest.json`。

![组合作用位置](../agents/combined/docs/diagrams/combined-policy-hooks.svg)

先验收全关及每个单开关，在demo/dev-season各一次。沿用原单项JSON，四份官方核心输出（actions、score_report、decisions、observations）须与原run逐字节一致；验证报告保存于 `../agents/combined/validation/equivalence.json`。这些run标为integration-verification，不作新方向筛选。

第一批只运行三个双项，各两开发卡，配置在运行前保存：

| 双项 | 配置 | 预期问题 |
| --- | --- | --- |
| D+P | `../configs/combined/dp-frozen01.json` | 线性边际收益与扩大可分配场比较是否互补；更多候选可能延续局部代理与整季轨迹的不一致 |
| D+G | `../configs/combined/dg-frozen01.json` | 广度收益与高高度质量是否互补，或额外高度偏好减少required机会 |
| D+Tconditional | `../configs/combined/dt-frozen01.json` | 两项都影响深度，检验冗余与门槛兜底的协同；不预设收益可加 |

其他家族均取中性值，所有强度沿用已测原单项，不重调。每个run独占，900秒预算，无LLM，仅公开初始化、当时消息与自身反馈。官方环境正常读取评分所需truth；策略与研究解释不读取truth。先完成等价验收，失败时保存材料并修集成，不能跳过验收跑组合。

记录每卡总分与分项、required、J、观测数、曝光分布、真实耗时及pace。交互量定义为 `组合增量−组成单项增量之和`，仅描述这些确定性卡片的结果，不称统计显著因果效应。第一批结果后停止，由主Agent选择是否开展复杂组合。保留集暂不运行。

## Results

14次等价验证全部通过；全关、T/D/G/C/W/P在两卡的四份官方核心输出均逐字节相同。首批6次组合run均完整结束、无pace降级。DP、DG、DT均在dev略高于D单项，在demo低于D；两卡平均增量均低于D单项。分项与交互汇总将在第二批完成后一起保存。

## Frozen second batch

2026-10-02，首批结果揭示后、第二批运行前，主Agent再且仅授权3种复杂组合，各两开发卡：

| 组合 | 配置 | 对照与预期问题 |
| --- | --- | --- |
| DPG | `../configs/combined/dpg-frozen02.json` | P/G在D之上的联合；局部更广搜索与高高度偏好可能互补或重叠 |
| DTGP | `../configs/combined/dtgp-frozen02.json` | 对DPG只增加T条件900秒及原门槛保护，检查深度限制与兜底路径 |
| DTGPCW | `../configs/combined/dtgpcw-frozen02.json` | 对DTGP联合加入C/W，诊断全启发式堆叠；差异不能单独归因C或W |

全部家族强度沿用冻结单项：T条件900、D指数1、G0.5、P12、C0.6、W0.2及原方向/高度参数。不调组合系数，不自动增加配置。运行后立即冻结组合源码和配置，并交付baseline、六单项、六组合的13配置R5接口；保留集仍未运行。

## Final R4 results

| Family | Card | Total | Delta | Required missing | Nonadditivity | Runtime s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DP | demo | 1331.730540 | +249.158399 | 0 | -516.398887 | 8.085 |
| DP | dev-season | -1800.826620 | +432.061235 | 58 | +91.006928 | 10.978 |
| DG | demo | 1407.185681 | +324.613540 | 0 | -352.348828 | 3.826 |
| DG | dev-season | -1811.494532 | +421.393323 | 58 | +32.983529 | 6.025 |
| DT | demo | 1411.216293 | +328.644152 | 0 | -497.628208 | 4.145 |
| DT | dev-season | -1800.378098 | +432.509757 | 58 | -300.742901 | 6.348 |
| DPG | demo | 1152.423555 | +69.851414 | 0 | -954.065793 | 7.013 |
| DPG | dev-season | -1781.489517 | +451.398338 | 58 | +103.760072 | 10.950 |
| DTGP | demo | 1507.024456 | +424.452315 | 0 | -1007.134805 | 9.379 |
| DTGP | dev-season | -1677.158161 | +555.729694 | 57 | -143.335395 | 12.500 |
| DTGPCW | demo | 1135.896485 | +53.324344 | 1 | -1318.071391 | 10.014 |
| DTGPCW | dev-season | -1767.380918 | +465.506937 | 58 | +63.915962 | 12.467 |

所有12次组合run均survey_complete且无pace降级。DTGP相对DPG只加入T：demo +354.600901、dev +104.331356。DTGPCW相对DTGP联合加入C/W：demo −371.127971、dev −90.222757；不能将这项差异单独归因于C或W。多于两项的非加性量包含所有交互，不能称为独立最高阶效应。

源码与六组合配置已冻结。R5接口为 `../agents/combined/R5_INTERFACE.json`，包含13个配置、不可变源目录和配置文件、hash及26次运行的命令模板。baseline使用精确官方Agent，六单项用原家族源码的不可变副本，六组合用当前冻结combined源码。没有运行或读取保留集，本任务不再运行其他开发配置。全量摘要为 `../agents/combined/validation/r4_summary.json`。

2026-10-02：R4结束；以上未运行保留集的表述记录当时状态。R5结果以 [evaluation/r5_results.json](../evaluation/r5_results.json) 及root报告为准。
