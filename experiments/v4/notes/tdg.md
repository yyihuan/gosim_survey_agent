# TDG R2实验记录

日期：2026-10-02。实现与实验范围由 `EXPERIMENT_CONTRACT.md` 和 `STUDY_DESIGN.md` 约束。

## Implementation checkpoint

三个家族共享一份参数化代码权威入口 `../agents/tdg/source/`。该源码直接复制固定的官方 baseline，然后局部替换。共同harness通过 `EXPERIMENT_CONFIG_PATH` 传入归档配置，每run快照独立。`../agents/tdg/materialize.py` 也可将源码与一份配置复制成自包含 Agent；物化目录为生成物，修改只发生在 source 和 configs。R2每次只启用一个家族。

| 家族 | 配置权威文件 | strict_slot | science_exponent | geometry_strength |
| --- | --- | --- | --- | --- |
| T | `../configs/tdg/t-slot900.json` | true | 2.0 | 0.0 |
| D | `../configs/tdg/d-linear.json` | false | 1.0 | 0.0 |
| G | `../configs/tdg/g-soft05.json` | false | 2.0 | 0.5 |

R2每个家族仅此一个配置。未使用未授权新外部卡和保留集。Python为 `/usr/bin/python3`，版本3.9.6。没有额外依赖，保留 `USE_LLM=0`。

![TDG独立作用位置](../agents/tdg/docs/diagrams/tdg-planning-hooks.svg)

## T

预期：曝光承诺不跨900秒天气格，使每次动作结束前不引入下一格未知天气；代价是单次深度上限下降，不能靠多次短曝光累积。

实现：`plan` 的 horizon 限制到以当前夜晚开始为原点的当前格结束。最长可达收益、可见时长和最终曝光搜索都使用这个 horizon。原离散时长先按baseline处理，再截到格内剩余秒数；因此格尾不足300秒但达到合法最小60秒时，允许使用剩余时长。不足合法最短时长时用 `until_utc` 等到下一格，避免60秒等待越过边界。构建 pending 使用最终动作时长，并在响应前断言 `pending_duration` 与实际请求一致。没有required补偿或跨格兜底。

关键量：请求曝光跨格次数与比例、实际曝光跨格次数与比例、夜内等待秒数/次数、格尾等待次数；此外从代理回放复验每次 observe 的pending时长。所有曝光严格为格内截止；此策略不声称格边界等于物理风险边界。

## D

预期：从平方完成度收益改为线性边际贡献，会减少深曝光偏好，并可能增加覆盖源数。短曝光可能使required或request门槛失守。

实现：科学收益统一为 `weight * max(0, after**p-before**p)`；配置p=1。替换 `value` 的剩余科学价值、anchor/光纤装填用的最长可达科学收益、曝光搜索的科学收益。required 的60点代理奖励、0.5/0.62阈值、衰减、request的bonus与门槛均沿用官方baseline。程序声明、天气估计、DONE_FACTOR=0.95也沿用原规则。p=2时采用原乘法表达式，避免零效果控制引入浮点差异。

线性是公开v4公式的factor函数形状；这里仍沿用baseline的factor估计和program处理，不读取真实天气，也不是完整的真实best-score oracle边际。

关键量：曝光时长分布、均值/中位数、observe数、单次factor达到0.5/0.95的目标数、required缺失和request完成。

## G

预期：给低airmass额外软优先，可能改善条件质量，也可能饿死低高度或短窗口目标。

实现：只在 `achievable` 的target收益上乘以 `1 + 0.5*z`。`z` 是inverse-airmass从硬高度限制处到天顶的归一化区间位置，截到[0,1]。因此30度处权重1，天顶权重1.5。该值影响anchor排序和光纤/视场装填；曝光时长收益不再重复乘此权重。硬高度及其官方安全margin不改。

关键量：实际命中目标的起始高度、airmass分布、低于45度比例；这些从observations.csv及公开目录、原始天空公式复算。高高度本来已有条件收益，因此G检验的是额外偏好。

## Validation and runs

共同harness入口已收到，R2指定开发集为demo与 `data/cards/dev-season`。未进入任何保留卡。局部测试 `../agents/tdg/selftest.py` 用demo公开配置/目录和合成反馈，180次neutral决策与官方baseline一致；T格尾150秒曝光及30秒等待、D线性边际/request门槛、G30/45/60/90度单调软权重都通过。实际G权重依次为1、1.206959、1.365963、1.5。

完整demo neutral run为 `../runs/r2-t-neutral-demo`，独占运行。其 `actions.jsonl`、`score_report.json` 与 `r1-official-demo-repeat` 字节一致，总分1082.572141；证据在 `../agents/tdg/validation/neutral-demo-equality.json`。

局部异常：首次合成initialize fixture漏了公开 `fov_side_deg` 字段，fixture修正；机制提取器首次遇到旧R1 manifest没有card路径字段，增加读取原始command的`--card`路径作为兼容入口。这两项均非策略或官方评分问题，日志在 `../agents/tdg/validation/history.jsonl`。baseline的demo机制代理为曝光跨格87/123（70.73%）、平均曝光1718.29秒、实际命中目标起始高度均值59.56度；文件在 `../agents/tdg/validation/baseline-demo-mechanism.json`。

运行统一使用以下命令结构，参数与真实执行命令另在各run manifest归档：

```bash
/usr/bin/python3 -B experiments/v4/harness/run_one.py \
  --run-id r2-t-slot900-demo --stage R2 \
  --agent experiments/v4/agents/tdg/source \
  --config experiments/v4/configs/tdg/t-slot900.json \
  --card experiments/v4/vendor/starter_kit_v4/cards/demo
```

机制代理脚本为 `../agents/tdg/mechanism_metrics.py`；以run为输入，仅读官方轨迹与公开目录，输出单独的 `mechanism_metrics.json`，不重写共同 `metrics.json`。

## R2 results

完整八次run（两个neutral控制、六个策略）都 `survey_complete`、exit_code=0、无内部错误、无pace切换。每个run保留官方原始产物、manifest、代码/配置/卡片hash、`metrics.json` 与 `mechanism_metrics-v2.json`。T两卡的requested与actual时长差异次数都为0；每次observe响应前pending与请求时长断言都通过。机制指标v1初稿保留在T-demo中，后增加requested/actual差异次数及内部错误计数后统一命名v2，未替换旧文件。

dev-season neutral控制也与 `r1-official-dev-season` 动作及评分文件字节一致；证据为 `../agents/tdg/validation/neutral-dev-season-equality.json`。R2共同source_tree_sha256为 `9dbd0cb0a4edc5027c063e3648b6e17ec6854b804bc056d5018868b779271f0a`，原source快照在各run内；后续改源码不会改动这些原产物。

| 卡 | 配置 | 总分 | 对baseline增量 | science | required缺失 | request完成 | Jain | observe数 | 平均曝光秒 | 平均命中高度度 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | neutral | 1082.572141 | 0 | 936.758408 | 1 | 1 | 0.979069 | 123 | 1718.29 | 59.56 |
| demo | t-slot900 | 800.871301 | -281.700840 | 1305.645974 | 12 | 0 | 0.976127 | 306 | 691.18 | 58.66 |
| demo | d-linear | 1501.174588 | +418.602447 | 1306.431365 | 0 | 1 | 0.973716 | 230 | 918.91 | 59.19 |
| demo | g-soft05 | 1340.932062 | +258.359921 | 1249.550287 | 0 | 0 | 0.956909 | 169 | 1255.03 | 63.47 |
| dev-season | neutral | -2232.887855 | 0 | 1109.285613 | 65 | 0 | 0.539133 | 154 | 1652.92 | 65.05 |
| dev-season | t-slot900 | -2602.567828 | -369.679973 | 1287.621190 | 76 | 0 | 0.549055 | 320 | 722.34 | 65.01 |
| dev-season | d-linear | -1851.062020 | +381.825835 | 1140.085039 | 58 | 0 | 0.544265 | 198 | 1227.27 | 64.46 |
| dev-season | g-soft05 | -2226.303896 | +6.583959 | 1122.814232 | 65 | 0 | 0.504409 | 158 | 1569.30 | 68.19 |

T机制已触发：跨格曝光从demo的87/123和dev-season的103/154降为0/306和0/320。夜内等待从10950/181950秒变成10800/205350秒。science分别增加368.89/178.34分，但required罚分两卡各恶化550分；demo还失去100分request奖励。这是策略负结果，未增加required兜底。

D机制已触发：平均曝光1718.29→918.91秒和1652.92→1227.27秒，中位数两卡均变为600秒。demo主要增加science369.67分并少缺1个required；dev-season主要少缺7个required贡献350分，science只提高30.80分。线性收益带来的改进机制并非两卡完全相同。

G机制已触发：平均目标起始高度59.56→63.47度和65.05→68.19度；平均airmass1.23694→1.15181和1.13130→1.09992。demo低于45度命中比例18.11%→4.92%，而dev原baseline就没有低于45度命中。dev science增加13.53分，均匀性扣分却增加6.94分，总分仅+6.58。该卡上不称为确定提升，也不据此调高几何强度。

机器可读汇总为 `../agents/tdg/validation/r2_summary.json`。run-id为 `r2-t-slot900-{demo,dev-season}`、`r2-d-linear-{demo,dev-season}`、`r2-g-soft05-{demo,dev-season}`；共同metrics位置为 `../runs/<run-id>/metrics.json`，额外机制位置为同目录`mechanism_metrics-v2.json`。真实耗时分别为T 4.01/7.17秒、D 3.79/5.60秒、G 3.03/4.63秒；资源并发条件逐run保存在manifest。

## R3 preregistration

主Agent在看齐R2后只批准下列两个新配置，两卡各一次。G不迭代，保留0.5供后续迁移检查。不自行扫参数，不提前使用保留集。

| 轮次 | 配置 | 参数 | 预期 |
| --- | --- | --- | --- |
| R3-T1 | `../configs/tdg/t-cap900.json` | strict_slot=false；exposure_cap_seconds=900；science_exponent=2；geometry_strength=0 | 区分900秒曝光上限与边界对齐。若门槛损失主要由上限造成，required仍恶化；若格尾碎片/天气反馈路径影响大，分项与T-slot900会明显不同。可跨格，仍单次最长900秒。 |
| R3-D1 | `../configs/tdg/d-power15.json` | strict_slot=false；science_exponent=1.5；geometry_strength=0；无额外曝光上限 | 用连续插值检验深度偏好的权衡。预期时长介于指数1与2之间，science/required收益不保证单调。 |

两项都从同一baseline规则单独激活，request/required代理奖励沿用。运行后先交付结果，再等待主Agent选择下一轮；每家族最多4次反馈实验上限没有改变。

## R3 first results

四次run均完整结束、exit_code=0、无内部错误、无pace变化，原始产物及机制代理在各run；汇总在 `../agents/tdg/validation/r3_first_summary.json`。R3第一组source hash为 `8afb2ce86ee6aa66909f56987ae242efba03c2f982e44f7c4ba5c35210af1320`。

| 卡 | 配置 | 总分 | 对baseline增量 | 对R2同家族增量 | required缺失 | 平均曝光秒 | 跨格次数/observe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | t-cap900 | 776.965038 | -305.607103 | -23.906263 | 12 | 749.47 | 172/282 |
| dev-season | t-cap900 | -2636.446556 | -403.558701 | -33.878728 | 77 | 765.35 | 165/303 |
| demo | d-power15 | 1126.551687 | +43.979546 | -374.622901 | 3 | 1378.25 | 104/154 |
| dev-season | d-power15 | -2218.766109 | +14.121746 | -367.704089 | 65 | 1540.99 | 103/161 |

T-cap900的required缺失为12/77，与T-slot900的12/76接近；曝光可跨格的机制确实触发，但两卡总分均未恢复。此对照支持“短曝光上限是门槛损失的主要路径”的推断，不能据此把所有轨迹差异单独归因于同一原因。D-power15曝光平均值落在指数1与2之间，但required没有保住指数1的收益，两卡总分都大幅弱于指数1。

## R3 second preregistration

主Agent在第一组结果后批准以下两个配置，各两开发卡一次，仍不自动继续网格。当前各家族仅消耗第2次反馈迭代；G保持R2配置不迭代。

| 轮次 | 配置 | 参数 | 预期 |
| --- | --- | --- | --- |
| R3-T2 | `../configs/tdg/t-cap900-conditional.json` | 默认exposure_cap_seconds=900；conditional_long_exposure=true；strict_slot=false；science_exponent=2；geometry_strength=0 | 未达到0.5的required和活动request的未完成目标在选场前仍可按原合法最长3600秒计算可达收益。若默认900秒不够达到该目标门槛，则该场可搜索原长曝光，但每个超过900秒的候选必须至少让一个此类目标跨越门槛。预计降低required损失，并检查普通science广度是否保留。 |
| R3-D2 | `../configs/tdg/d-power075.json` | science_exponent=0.75；strict_slot=false；geometry_strength=0；无额外曝光上限 | 比线性更偏向低完成度目标的广度。可能降低平均时长，但best曝光不累积，目标完成和request收益可能恶化。 |

T2不改变科学权重、required奖励或门槛、request奖励或门槛、天气估计。请求是否未完成来自当前`request_bonus`所代表的活动request进度，不用全季最高factor误判新request已经完成。长曝光资格在`achievable`前保留，避免先被900秒排除；最终曝光候选再检验“超过900秒是否实际跨越至少一个门槛”。普通同行目标可获得同一次长曝光的原baseline科学收益，不额外增加科学权重。pending用最终duration构建，并对每次observe统一断言其与动作一致。长曝光覆写次数与触发目标数写agent.log，后续可复算。

## R3 second results and handoff

四次run均`survey_complete`、exit_code=0、无内部错误、无pace变化；requested与actual曝光时长差异次数为0。各run保留原始输出、共同`metrics.json`和额外`mechanism_metrics-v3.json`。v3仅增加条件长曝光覆写数、时长分布与预测触发目标数，不重评分。机器汇总为 `../agents/tdg/validation/r3_second_summary.json`。

| 卡 | 配置 | 总分 | 对baseline增量 | required缺失 | science | request完成 | report结算 | 平均曝光秒 | 长曝光覆写次数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | t-cap900-conditional | 1490.242054 | +407.669913 | 0 | 1294.711771 | 1 | 100 | 897.45 | 25 |
| dev-season | t-cap900-conditional | -1881.461032 | +351.426823 | 58 | 1110.466818 | 0 | 0 | 1067.05 | 41 |
| demo | d-power075 | 950.098582 | -132.473559 | 3 | 1003.982186 | 1 | 0 | 869.75 | 0 |
| dev-season | d-power075 | -1796.669579 | +436.218276 | 57 | 1147.336312 | 0 | 0 | 884.62 | 0 |

T条件上限相对固定900上限恢复了required门槛：12/77缺失变成0/58；demo request奖励也恢复100。25/41次原长曝光候选真正被采用，预测可跨门槛的不同目标计数为27/46（按每次曝光重复计数）。这些是Agent预测门槛，官方实际完成由score_report确定；不把预测数当真实完成数。T2两卡均优于baseline，但dev主要改善来自少缺7个required，science只比baseline增加1.18分。

D指数0.75在dev比指数1再提高54.39分，却在demo下降551.08分。demo相对baseline的science仍增加67.22分，但required多缺2个扣100，report结算少100，导致总分低于baseline132.47。未改report规则；策略轨迹变化影响其证据链的具体原因尚未追查，不把少报自动归因于某个天气或故障。该结果说明更偏广度并非两卡都更好，不继续向下扫指数。

主Agent已经按预注册的两开发卡平均增量确认冻结T=`t-cap900-conditional`（平均+379.548368）、D=`d-linear`（平均+400.214141），G仍为`g-soft05`（平均+132.471940，dev仅+6.58需谨慎）。T2与D1最差卡增量均为正；D0.75平均只+151.872359且有负卡，不取代D1。R3到此停止；后续只可协助组合的TDG单开关等价验证，不改冻结单族逻辑、不运行保留集。

最终源码接口已写 `../agents/tdg/INTEGRATION.md`，供environment_baseline整合。代码在 `../agents/tdg/source/`；当前source_tree_sha256为 `acfac5e70c1cd8977ee3c9b46a91dd807736ead6b063b0a8b3277140def1278e`，T2配置hash `5ee26c130f7d005017c4bc22d4a9ce30f51f142545541b19f7c0a86151cb6516`，D1配置hash `12738a8c2deb63a185756944e47aeb3253aa27af8fe00997002ce8419120b443`，G配置hash `6735114b6d3014bc0bcd70cfecf5e81ef8bda358aabc4fe246a2665093dd08a2`。代码不再调整参数；组合必须在新run复验单开关等价与neutral逐动作等价，不用旧总分近似代替。

两次反馈组后停止，没有用满每家族4次上限，也未运行或读取保留集内容。全部16次授权run（R2八次、R3八次）及所有局部异常产物均保留。文档图freshness检查通过。
