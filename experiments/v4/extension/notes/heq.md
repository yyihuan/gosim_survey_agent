# H / E / Q initial experiment

本轮日期为 2026-10-03。共同底座是冻结 `agents/combined/source` 配合 `configs/tdg/d-linear.json`：科学完成度指数为 1，3 个锚点；T、G、C、W 均关闭。源码只复制到本轮 `extension/agents/heq/source/`，不改旧源码或评分器。每个配置仅打开 H、E、Q 中的一项；构造函数禁止同时启用两项。开发卡只有 demo 和 dev-season。

准确参数、源码与配置 SHA256 已在运行前登记于 [heq-initial-registration.json](./heq-initial-registration.json)。执行使用环境 Agent 提供的 `extension/harness/run_one.py`，沿用官方 runner 和原指标提取，仅使用本轮独立六槽锁；8 个独立命令同时提交，实际模拟器受全局六槽约束。

![HEQ strategy hooks](../agents/heq/docs/diagrams/heq-hooks.svg)

## H — remaining opportunities

配置为 `h-opportunity2.json`，`H.strength=2.0`。只改变未达 required 0.5 门槛且当前预计可达标的目标的候选紧迫度；原 science、required 奖励、曝光时长、选场装填与 program 规则保持不变。

初始化时对每个 required 目标、每个公开夜历窗口，求在原高度安全界限 `30° + 0.6°` 以上的连续小时角区间。区间显式处理赤经跨 0°、窗口开始时已经升起、从不／总是可见的边界。取区间内最接近过中天的时刻，用公开月亮位置、airmass、原 `q0`、目标亮度及原 0.9 安全系数估计清空模型速率：

`k_clear = flux × lunar_factor / (q0 × airmass^airmass_exponent) × 0.9 / (f0×T0)`。

若 `0.5/k_clear ≤ min(3600s, 连续可见区间长度)`，该夜记为一个可能的达标机会。每夜最多一个；不计未来天气，也不假设未来反馈质量已知。当前是否预计可达标仍用 D 的当前质量估计与当前月亮模型，要求 `k_current × min(max_exposure, up, seconds_left) ≥ 0.5`。

对当前预计可达标的未完成 required，令 `N = 1 + 后续几何清空模型可达标夜数`，把原 `1 + 2/nights_left` 替换为 `1 + 2/N`。当前不可达标者保留原紧迫度。落下紧迫度、候选可见性过滤及其他目标的紧迫度均不变。

预期：在尚有很多日历夜、但实际公开几何窗口较少时更早处理 required。代价：稀缺窗口目标可能挤掉高效科学目标。机会只是公开几何与假定质量下的估计；区间峰值质量不保证整段曝光同样好，未计天气、竞争装填或地形阻挡，不是对真实未来天气或完成概率的预测。

日志保存当前预计可达标 required 数、紧迫度实际改变的候选数、入选 required 的机会数分布与入选紧迫度改变数。候选机会数包含当前这一夜。

## E — threshold exposure candidates

配置为 `e-threshold30.json`，`E.quantum_seconds=30`。保留原离散时长 `(300,450,600,900,1200,1500,1800,2400,3000,3600)`，只追加临界时长，不改变 600 秒候选可见性过滤、0.9 安全余量、硬高度门槛或选场准则；没有 T 的 900 秒上限。

对已经选定场中的目标，使用 D 原本的预测速率 `k`。未完成 required 追加 `τ=0.5`，未饱和目标追加 `τ=1`，活动请求目标追加该请求自己的完成门槛。候选时长为 `d = 30 × ceil((τ/k − 10⁻⁹)/30)`。只加入合法最短／最长范围内、目标还能保持在高度界限以上的时长。统一排序去重，再经过原夜末、中心落下等筛选，使用原单位时间收益准则选取。

预期：用更靠近门槛的曝光减少档位过曝。代价：预测误差可能使刚好达标变成未达标，进而增加重试和 required 缺失。日志记录各门槛生成数、额外时长数、实际选择新增时长的次数。生成数是进入候选集合前的目标级计数；额外时长数在最终夜末筛选前统计。

## Q — empirical conservative margin

配置为 `q-quantile25.json`：分位数 `0.25`，至少 `8` 个 hit 样本，时间窗为 `2` 个模拟小时，折扣下限 `0.6`。样本直接来自 D 已收到的未饱和正得分反馈比值；不读取未来预报、weather 文件或 truth。

取原 `samples` 队列中近两小时比值排序，`q25 = samples[floor((n−1)×0.25)]`。若 `n<8`，余量倍率 `m=1`；否则 `m=clamp(q25/scale,0.6,1)`。原 24 个样本的队列长度和中位数 scale 更新规则不变。

只为估计尚未完成的 required 奖励门槛使用 `k_protected=k×m`：候选场的 required 达标奖励和原离散曝光的 required 奖励都以 `min(1,k_protected×d)≥0.5` 判定。科学收益、普通目标、请求、program 投票和反馈学习继续使用原 `k`；不把保守系数写入实际 factor 更新。pending 时长仍由最终动作设置，原一致性断言保留。

这称为经验保守余量，不是校准置信度或成功概率。同一次曝光的多个目标反馈高度相关，8 个 hit 不等于 8 次独立天气采样。样本还排除了未命中、零分与饱和反馈，因此分布有选择偏差；历史比值可能在条件改变后过时。

预期：减少乐观 required 达标判断。代价：较长曝光可能减少覆盖和科学收益，也可能使短窗口 required 被放弃。日志保存样本数、下四分位数、余量倍率、被压掉的 required 奖励检查、被保护的已选 required，以及此前已尝试且估计仍未达标的 required 再次装填数。后处理另按官方观测因子复算 required 未达标重试，并报告平均实际曝光。

## Validation and results

边界自测结果见 [initial-boundaries.json](../agents/heq/validation/initial-boundaries.json)，包括小时角跨界、经验余量样本下限／上下界、未截断预测因子的门槛判断、三类临界时长和单因素约束。

全关控制将与冻结 D 在两卡的四个核心输出逐字节比较：`actions.jsonl`、`score_report.json`、`decisions.csv`、`observations.csv`。原始产物均保留在唯一 `runs/ext-n2-heq-*` 目录；命令和退出码在 [initial-execution.jsonl](../agents/heq/validation/initial-execution.jsonl)。机器结果汇总完成后追加引用；所有负结果保留。只做初版各一组，等待 Root 决定 N3。

## N2 completed evidence

两卡全关控制与冻结 D 的 actions、score_report、decisions、observations 四个文件均逐字节相同，详见 [heq-n2-results.json](./heq-n2-results.json)。八次均 survey_complete、pace 改变为 0、内部异常为 0。

|配置|demo total|dev-season total|
|---|---:|---:|
|neutral|1501.174588|-1851.062020|
|h-opportunity2|1501.174588|-1851.062020|
|e-threshold30|1330.149261|-1787.209694|
|q-quantile25|1498.742159|-1796.002899|

H 初版在 demo/dev 分别评估 3458/10728 次当前可达标 required，候选紧迫度变化 0/2 次，最终入选 required 的紧迫度变化均为 0。相同分数来自机制几乎未区别原末夜倒数；不是触发后获得同样收益。

E 初版的 required/saturation/request 临界候选为 demo 182/2263/9、dev 300/2234/5，新增时长实际选用 188/177 次。普通饱和门槛占候选多数，但其对科学分的因果影响留给 N3 对照。

Q 初版平均实际曝光为 demo 925.00s（D 918.91s）、dev 1145.97s（D 1227.27s）。按官方已收到观测重算的未达标 required 重试赋值为 58/68（D 56/85），当次未命中或未达标次数为 64/83（D 60/97）。这不是成功概率校准。

## N3 preregistration

本轮只追加 H、E 各一个候选，Q 保留初版。N2 源码与配置不改；N3 源码在 `agents/heq/n3_source`。准确源码/配置 SHA256 和时刻见 [heq-n3-registration.json](./heq-n3-registration.json)，登记先于模拟。

H 配置为 `h-window-fraction2`：强度 2，整夜等效量下限 0.5。保持初版当前可达标门槛。对当前夜未消耗部分与所有后续夜的公开几何连续窗口，沿用初版峰值清空速率及 0.9 余量；仅当所需 0.5/k_clear 不超过 max_exposure 与剩余窗口长度时，计入该窗口。当前窗口经过截短时重新计算剩余区间峰值。

令各夜完整公开黑夜长度为 L_n（秒），符合门槛的剩余窗口长度为 V_nj（秒），定义 R=Σ V_nj/L_n（无量纲、整夜等效量）。完整可见黑夜贡献 1，半夜贡献 0.5。未完成且当前预计可达标 required 的紧迫度改为 1+2/max(0.5,R)，上限 5；其他目标、落下项、曝光选择、安全余量不变。日志同时保留 R、窗口总秒数、候选/实际入选紧迫度变化及下限触发量。

预期：让同有一夜机会但只有短窗口的目标获得更高优先级，确认连续窗口机制实际改变选择。代价是 required 可能挤掉更高科学效率目标；峰值假定不保证整次质量，没有预测真实未来天气。该量也不计装填竞争、读出、转场或地形阻挡。

E 配置为 `e-required-request30`：30 秒量化、`include_saturation=false`；只生成未完成 required 0.5 与活动 request 门槛临界时长。原十档时长、600 秒候选可见过滤、0.9 余量及选场/安全检查不变。预期：隔离普通源饱和断点的影响，降低其造成的曝光分布变化；接近 required 门槛仍可能因误差增加重试。

本轮四个独立运行同时提交至六槽包装器；仅 demo/dev-season，各一遍，无新 holdout。边界检查见 [n3-boundaries.json](../agents/heq/validation/n3-boundaries.json)。

## N3 completed evidence

四次 survey_complete，pace 改变与内部异常均为 0；源码与配置前后哈希一致。完整分项、请求、report、曝光分布、机制诊断和原始路径见 [heq-n3-results.json](./heq-n3-results.json)，命令见 [n3-execution.jsonl](../agents/heq/validation/n3-execution.jsonl)。

|配置|卡|total|science|required 缺失|J|实际平均曝光(s)|
|---|---|---:|---:|---:|---:|---:|
|h-window-fraction2|demo|1261.444193|1118.242729|1|0.966007325|1010.00|
|h-window-fraction2|dev-season|-1777.976853|1116.237709|56|0.528927185|1269.17|
|e-required-request30|demo|1340.274555|1145.150718|0|0.975619185|933.19|
|e-required-request30|dev-season|-1805.248564|1137.736095|57|0.535076705|1042.76|

H 连续窗口确实改变入选 required 的紧迫度，已区别初版夜数代理。它在两卡的科学分都下降，demo 多缺一个 required；dev required 缺失下降至 56。此处仅登记局部结果，选择与总体判断归 Root。

E 仅 required/request 后普通饱和候选为零；实际新增时长选择仍有触发。demo 科学分仍显著低于 D，因此“去掉普通饱和断点就恢复科学分”的预期未得到支持；候选门槛曝露与后续轨迹耦合，不能只由候选数量归因。两版 E 的原始负结果均保留。
