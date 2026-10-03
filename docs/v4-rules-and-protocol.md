# v4 rules and protocol

核对日期：2026-10-03。以官方仓库提交 `149c6590c49cf289c325b8e2fedfee1035975c6f` 的[参赛者指南](https://github.com/gosimfoundation/hackathon-survey26/blob/149c6590c49cf289c325b8e2fedfee1035975c6f/docs/v4-participant-guide-zh.md)、后端与公开运行器为依据。数值以每次 `initialize` 为准。官方指南标题仍带“草稿”，本工作区采用的比赛协议为正式 v4；文档标题不能替代任务卡配置。线上实际部署未在本轮验证。

本页是规则、消息语义与源码核对的权威解释，配套 [讲解 HTML](survey-rules-explorer.html) 从本页生成；不手改生成页。完整官方数学推导和图片保留在[最新只读指南](../research/2026-10-03/latest-149c659/docs/v4-participant-guide-zh.md)。本页中的示例是构造演示，不是未来天气或比赛结果。

## 1. 先回答跨 slot

**允许曝光跨越同一夜的普通 slot 边界，不允许一条夜间曝光跨越两夜。** slot 是天气数据网格，动作是 Agent 的控制单元，两者不是同一个周期。

| 边界 | 后端怎样处理 | Agent 何时再次决策 |
| --- | --- | --- |
| 普通900秒 slot边界 | 曝光继续，切换该片段的天气参数并分段积分 | 整次曝光结束后 |
| 方向事件起止 | Q积分再分段，部分片段可关闭；不返还时间 | 整次曝光结束后 |
| 夜末最后一个保留slot终点 | 夜间曝光截断，按实际时长计分，可短于60秒 | 若巡天仍未结束，在截断时刻 |
| 源跌破最低高度 | 该源整次不作为命中计分；不是只舍弃低高度片段 | 曝光结束后 |
| 请求截止时刻 | 曝光不会为请求自动截断；整次有效曝光须完全在请求窗内 | 曝光结束后 |
| 真实运行截止 | 当前未及时返回的响应不接受；结束巡天，结算已有结果 | 没有下一轮 |

例如从 `00:07:30Z` 开始曝光1800秒，正常结束于 `00:37:30Z`，跨 `00:15` 和 `00:30` 两个普通边界。Agent中途不能取消、改指向或改分配。若动作期间有两条公告，到下个请求才一起出现；`latest_bulletin` 只保留其中最新一条。长度3600秒的曝光完全可以跨多个slot。

太阳低于卡片阈值才属于天文夜。900秒网格与UTC整15分钟对齐：首个保留slot从不早于黄昏的网格点开始，最后一个保留slot在不晚于黎明的网格点结束，跨黄昏/黎明的边缘slot被舍弃。应采用公开 `survey.nights[].observing_start_utc/end_utc`，不能将最后一个slot的起点误当夜末。

![普通slot与夜末分别处理](diagrams/v4-slot-boundaries.svg)

源码证据：`v4_runner.py` 用 `bisect_right` 定位曝光开始的slot，只用 `night_ends[night_id]` 截断；`WeatherTruth.segments()` 遍历整段曝光涉及的slot；`score_target_exposure()` 继续细分积分。没有“每900秒重新提交动作”的分支。

本轮[官方引擎验证](../experiments/current/rules-audit/evidence-refresh/verification.json)：跨slot、夜末30秒截断、report原时刻回合/第33次拒绝、最大贡献与请求窗/失效账本均通过。时间边界使用脚本动作和空分配，验证的是交互规则，不是观测策略成绩。

<!-- interactive:slot -->

## 2. 任务与几何

初始化给出天区多边形和目标目录。`footprint` 每块由按序顶点连接，边是球面大圆弧。`targets.columns` 定义列序，逐行读取 `target_id`、`ra_deg`、`dec_deg`、`target_class`、`feature_flux`、`science_weight`、`required`，不可依赖示例目录的行序或硬编码目标ID。类别ELG/BGS/LRG/QSO/Star只描述目标，不额外加倍率；目录没有红移。

`feature_flux` 是相对亮度f，决定达到深度的难易；`science_weight` 是权重w，决定同样完成因子值多少分。必做标记影响终局罚分，不替代亮度或可见窗口。生成器保证每个目标至少在一个完整slot内满足最低高度，但不保证光纤、天气、请求和总时间预算下全部可完成。

地方恒星时和高度使用UTC计算，东经为正；`utc_offset_hours` 仅帮助理解当地日期。角度须转换为弧度后参与三角函数。记 `d=UnixSeconds/86400+2440587.5−2451545.0`，经度λ、纬度φ、赤经α、赤纬δ：

```text
LST = (280.46061837 + 360.98564736629 d + λ) mod 360°
H = LST − α
sin h = sin φ sin δ + cos φ cos δ cos H
sin A = −sin H cos δ / cos h
cos A = (sin δ − sin h sin φ)/(cos h cos φ)
A = atan2(sin A, cos A) mod 360°
```

太阳、月亮采用指南规定的低精度近似，不以高精度外部天文历表替代来复现比赛。太阳位置先从黄经L、平近点角g计算真黄经和黄赤交角，再转赤经赤纬求太阳高度。月亮由平均黄经、近点角与纬度参数求黄经黄纬，转赤道坐标后求高度和目标月距。完整系数见官方指南公式(5)–(13)，本地对应 `v4_scorer._lunar_geometry()` 与公共天球几何函数。

星空角距Θ、月面照亮比例I与月光因子L：

```text
cos Θ = sin δ1 sin δ2 + cos δ1 cos δ2 cos(α1−α2)
I = (1 − cos(太阳−月亮角距))/2
L_i(t) = 1 − P_M I sin(max(0,h_M))^γ_M exp(−ρ_i/θ_M)
```

月亮在地平线下时L=1。月面越亮、月亮越高、目标离月亮越近，损失越大；L按源和时间计算，不是先全场扣一次。P_M、γ_M、θ_M来自 `scoring.lunar_model`。

## 3. 指向、光纤与曝光

`observe` 必须有 `pointing`、`assignments` 和 `duration_seconds`；program可省略为BACKUP。指向alt在[0,90]、az在[0,360)，有限数值。30°等最低高度约束计分目标，指向中心低于它仍可合法；天顶alt=90也必须填az，az决定切平面网格方向。

每卡光纤数量和网格以 `instrument` 为准，不能把示例的16根推广到所有正式卡。示例4×4相邻方格，每格面积0.4平方度，边长约0.632°，全场边长约2.530°。行从低alt向高alt、列从低az向高az，编号 `grid_side×row+column`；示例0在左下、15在右上。局部方向随指向变化，不是固定赤经/赤纬轴。

后端在曝光起点根据实际指向做心射投影。目标方向u、中心c、向az/alt增大的切向单位向量t：

```text
x = (u·t_az)/(u·c) ×180/π
y = (u·t_alt)/(u·c) ×180/π
```

分母须为正。源须落在自己被指定光纤的方格；落在别格或场外不计分。只填指向不会自动分配目标，空 `assignments={}` 后端允许但只耗时；同源不能分给两根纤维。公共格边由后端唯一归属，外边缘归最外格，策略应避开边界。

命中分类只在曝光开始做一次，随后恒星跟踪；目标在网格内相对位置保持不变。但目标地平位置、月距、大气质量和方向事件效应会随时间变化，**最低高度须检查整段曝光，包括区间内部最低点**。通过几何和高度检查的命中源可以因天气关闭得到零分；“未命中”和“命中但零分”不可混作同一故障证据。

申报时长为卡片闭区间内整数秒，示例60–3600。正常曝光不必与slot边界对齐，夜末截断后的实际时长可少于60。源码在夜间开始曝光时才按该夜夜末截断；若白天乱发observe，代码并不提供同样的夜末保护，缺天气片段质量为零。策略应先判断公开夜历，这种代码容忍不构成白天观测保证。

## 4. 两套质量与计分公式

计算顺序：几何命中和整段高度检查 → 每目标Q积分 → 完成因子g → program判档B和倍率m → 本次贡献c → 有效历史最大值 → 终局罚分及奖惩。

以曝光实际时长T、片段中点t_p和Δt_p表示：

```text
X(h) = [1 + 0.50572×96.07995^(−1.6364)]
       / [sin h + 0.50572×(h+6.07995)^(−1.6364)]
Q_i,e = Σ Δt_p C_i,p η_i,p τ_i,p K_i,p L_i(t_p)
        / [s_i,p X(h_i(t_p))^β] / (q0 T)
g_i,e = min(f_i T Q_i,e/(f0 T0), 1)
s_i,e = w_i g_i,e
B_i,e = Σ Δt_p D_p τ_p K_p L_i(t_p)
        / [s_p X(h_i(t_p))^β] / (q0 T)
c_i,e = w_i g_i,e m_i,e
```

| 符号 | 含义与可见性 |
| --- | --- |
| X、L | 大气质量和月光；算法及配置公开，可按几何计算 |
| q0、β、f0、T0、w、f | 初始化公开，数值随卡读取 |
| η、τ、K、s | 效率、透过率、天空质量、视宁度；真值不直接发送 |
| C_i,p | 站点关闭或目标方向关闭则0，其他可观测片段1 |
| D_p | 只看站点关闭或缺夜间天气，不看方向关闭 |
| Q | 包含仪器效率、方向乘数和方向关闭的质量；不是公开反馈字段 |
| B | program质量：不含仪器效率、不加方向事件乘数、不应用方向关闭 |
| g | 原始完成因子，上限1，直接反馈未提供 |
| c | 含program倍率的本次源贡献，作为 `hits[].score` 发给Agent |

Q积分按slot和方向事件起止切段，再细分至不超过120秒，每片段按中点位置计算。关闭片段积分分子为0，仍占实际T的分母；不会停止曝光或退还秒数。B按slot切段并细分至≤120秒，使用站点天气、逐源月光和大气质量。Q可大于1，截断的是g。

示例B≥0.65对应DARK，B≥0.40对应BRIGHT，其余BACKUP；声明匹配分别×1.20、1.12、1.06，不匹配×1。整次曝光只声明一个program，但每个目标可有不同实际档位。B不直接乘入c，仪器效率下降也不会使program判档直接改变；不能用Q代替B。

不要从 `score/(w×最大倍率)` 认定精确g，也不能从一次亮源饱和结果反推唯一Q。可依据倍率范围形成g区间，结合自己的曝光和公开模型估计；估计仍不是真值。

<!-- interactive:quality -->

## 5. 终局账本与请求

每源记 `best_score=max有效曝光 c`，另记 `max_factor=max有效曝光 g`。二者可能来自不同曝光：w=1.7时，g=.8且匹配DARK得1.632，g=.9但不匹配得1.53；最好分来自前者，最大g来自后者。重复曝光不累加，多次g=.3仍只有.3。

required达标使用 `scoring.required.observed_factor_threshold`；示例.5。program不会帮助跨这个门槛。每未达标required扣P_req，示例50。普通源不会因此产生必做罚分。

均匀性按公开RA条带宽度划分，示例10°；只计算目录中有目标的条带。各带完成率r_b=达到公开uniformity门槛的有效目标数/该带全部目标数，包含普通和required，不按w加权：

```text
J = (Σ r_b)^2/(N_band Σ r_b^2)，全部r_b=0时J=0
S = Σ best_score − P_req×未完成required数 − U(1−J)
    + 已完成请求奖励 + report净奖惩
```

`running_total=Σ best_score`，不含上述罚分、请求和report。随data_loss可以下降。`survey_complete`说明模拟周期结束，不说明任务全部达标或分数为正。

限时请求自动适用，不发送接受动作，不在observe中填写request_id。引用已有目标，未发布前不可见；同次观测可推进多个重叠请求，同时保留普通科学分。

只有**完整处于闭区间[issued_at,deadline]内的有效曝光**参与请求；提前开始、晚于截止结束的整次曝光不参与，不能切下窗内片段凑数。每源至少一次g达到请求门槛；重复不足曝光不累加；完成不同目标数达到minimum_completed后一次性获得completion_reward。`remaining_count=max(0,minimum_completed−completed_count)`，不是未完成target_ids总数。请求未完成奖励0且罚分0。

窗口内实时进度在active_requests；now达到截止后移除，并在下一可用请求中发送result。若截止恰在最后动作末尾且巡天已结束，可能没有下一条request，最终报告仍自动结算。主动提前finish同样按已有账本结算已经发布的请求，不能保证收到每项通知。

<!-- interactive:settlement -->

## 6. 完整协议循环

外层只有三类后端消息：`initialize`、`decision_request`、`finish`。各种公告、请求、举报结果和状态更正在request内部的 `payload.new_messages`，不是另发同级协议消息。

![后端、Agent与结算的消息顺序](diagrams/v4-protocol-sequence.svg)

一次请求只回复一行JSON，stdout只传协议，stderr写日志。外层字段与动作同级，没有额外action对象。必须回答当前整数decision_sequence；收到initialize/后端finish无需回复。Agent可返回action=finish，此后后端也可能发message_type=finish，两个finish含义不同。

```json
{
  "protocol_version": "participant-agent-protocol-v4",
  "message_type": "decision_response",
  "decision_sequence": 17,
  "action": "observe",
  "pointing": {"alt_deg": 55, "az_deg": 120},
  "assignments": {"0": "V4T000001", "5": "V4T000002"},
  "duration_seconds": 1800,
  "program": "DARK",
  "reason": "示例：同一夜跨普通slot"
}
```

例中目标须真实出现在该卡目录，示例并非可直接对任一卡发送的动作。

### 6.1 Initialize字段

| 字段组 | 内容及使用方式 |
| --- | --- |
| protocol_version / message_type | 固定协议与外层消息类型 |
| payload.schema_version | 初始化结构版本 `v4-initialize-v1` |
| task_card | card_id，适用时含scenario_slug、phase；标识不是策略未来信息 |
| site | name、latitude_deg、longitude_deg、utc_offset_hours、sun_altitude_limit_deg、minimum_altitude_deg |
| survey | start_utc、end_utc、slot_seconds；nights里的night_id、night_date、observing_start/end_utc、slot_count |
| instrument | n_fibers、grid_side、fiber_area_deg2、gap_deg、glass_side_deg、pitch_deg、fov_side_deg、layout、exposure.min/max_duration_seconds |
| scoring | 第12节索引的完整公开评分配置，不含隐蔽环境真值 |
| footprint | 每项component_id和按序vertices，顶点为[ra,dec] |
| targets | columns和rows完整目录，required按布尔值解释 |
| limits | global_wallclock_seconds、max_consecutive_reports、response_max_bytes、decision_timeout |

night_date是夜的标识日期，不一定等于开夜UTC日期。survey.end_utc是整个周期最后slot终点，不能与单夜夜末或最后slot起点混淆。

### 6.2 Decision request字段

| 字段 | 含义、不能据此推断什么 |
| --- | --- |
| decision_sequence | 从1起的当前请求序号；原样答复，非观测动作编号 |
| payload.schema_version | `v4-decision-snapshot-v1` |
| now_utc | 当前模拟时刻；真实思考时不自行推进 |
| survey_end_utc | 整个模拟周期末时刻 |
| observe_action_index | 已执行observe数，下一个observe使用该0起编号；wait/report不增它 |
| running_total | 已有效源最高贡献之和，非最终S |
| wallclock.elapsed_seconds / remaining_seconds | 实际计时消耗与剩余秒数，模型等待也消耗 |
| latest_bulletin / latest_forecast | 最新已发布记录；无新消息时会重复旧记录，应看时间和ID |
| active_requests | 已发布且now<deadline的请求和重算进度 |
| new_messages | 新送达完整记录的批次；动作期间积累的消息一起送达 |
| last_result | 上一动作结果；首轮null；不是完整历史轨迹 |

后端先收集新公告、预报、请求，再送举报结果、状态更正与到期请求结果。数组按类别的源码收集次序组织，不保证所有类别之间严格按issued_at排序；若维护时间线，应使用各记录的issued_at和身份，不能只依赖数组位置。

`latest_*` 是快照引用，`new_messages` 是本轮事件流。首轮同一公告和预报两处都会出现，不要重复处理。长曝光结束后应先处理所有更正与到期事件，再形成一致状态；若同时有last_result和state_resync，结合曝光编号和自己的有效历史处理，不能把失效曝光又补回账本。

### 6.3 Last result字段

| 上一动作 | 字段与边界 |
| --- | --- |
| observe | action、observe_index、assigned_count、hit_count、hits；每hit只有target_id、score，不含fiber_id、g、Q、B、实际指向、真实天气或实际曝光时长 |
| wait | 只有action=wait；长until等待可能已在后端记录多行wait |
| report | action、correct、repaired、score_delta；同一结果也在new_messages中的report_result |

assigned_count是提交分配数，hit_count是通过光纤与整段高度检查数。hits含零分源；没在hits里不代表未填，可能错误纤维、偏差或低高度。实际曝光时长需用起点、夜历和下轮now核对，不能仅用申报T反推质量。

### 6.4 Finish字段与两种时间

后端finish payload含schema_version=v4-finish-v1、termination_reason、decisions、observe_actions、last_decision_sequence、grace_seconds。decisions是内部动作行数，长until_wait可能增加多行，不等于request数；finish本身不增加一条观测。

全局真实预算从首个decision_request阶段开始，源码在初始化发布完成后设置deadline；包含Agent计算、模型等待、协议传输和后端处理。没有独立每轮超时；单轮长思考会挤掉后续预算。编译/构建不计入这段观测计时，启动另有初始化限制。云端还将本地deadline与会话服务器deadline取较小值，本地runner不复制模型代理额度和第二个服务器时限。

动作推进模拟时间，计算与模型等待不推进模拟时间。两种900秒独立：slot是模拟天气步长，wallclock是整卡现实上限。

| termination_reason | 结束含义 |
| --- | --- |
| survey_complete | 模拟时间走完，仍按未达标和覆盖扣分 |
| agent_finished | 主动finish或实现等效主动结束，结算已执行动作 |
| global_wallclock_expired | 真实预算耗尽，不接受迟到响应，结算已有动作 |
| agent_error | 非法响应、进程/协议错误或连续report超限；非法动作不结算 |

正常结束尝试发送无需回复的finish，关闭输入，给默认30秒退出宽限；超时进程不保证收到finish。原始评分器保留先前分数和终局扣分；赛事规则关于隐藏卡“自身原因未完成记0”是排名层额外政策，不能直接等同引擎分数。需要组委会明确其超时边界，不能自行选择有利解释。

<!-- interactive:messages -->

## 7. New messages完整字典

### 7.1 Bulletin与forecast

| 记录与字段 | 语义 |
| --- | --- |
| bulletin.record_type | bulletin |
| slot_id / night_id | 所属slot和夜标识 |
| issued_at_utc | 对应slot起点；Agent可能在动作结束后才收到 |
| initial | 只有整季第一条公告为true，不是每夜第一条 |
| notices[].event_kind / direction | 类别和粗方向，无天气数字、准确扇区边界、强度或持续时长 |
| forecast.record_type | forecast |
| issued_at_utc / coverage_start/end_utc | 发布时间和覆盖区间 |
| notices[].event_kind / direction / nights | 夜粒度的事件类别与粗方向，nights对应公开night_date |

公告每slot发布；首夜同时收到首公告和首预报。预报按首夜起每7个日历日的开夜时刻发布，覆盖7天，不是固定周一，也不是逐slot概率预测。当前进入预报的事件必与所列夜的观测窗相交，但精确时刻、空间和强度未知；协议没有发生概率、命中率、漏报率或误报率字段。

notices=[]只表示无可公开事件，不保证背景天气好、站点开放、没有故障。粗方向N/NE/E/SE/S/SW/W/NW来自事件方位映射；ALL表示全场，不意味着可以把方向标签变成精确45°遮罩。保留初始地形公告的信息，因为后续公告不重复它。

| event_kind | 公布方式和影响 |
| --- | --- |
| rain / storm | 可预报、slot公告；受影响范围可关闭，背景关闭也可能没有公告 |
| overcast / haze | 可预报、公告；质量下降，全场或方向性影响，具体数值隐藏 |
| cold_snap | 可预报、公告；主要为全场质量恶化 |
| rocket_launch | 提前预报和发生期间slot公告；隐藏方位扇区和高度上限，方向关闭，最晚启动夜末结束 |
| earthquake | 不预报，发生后公告；效率损失逐夜减弱，重复公告不必是新地震；report不能修复它 |
| terrain_obstruction | 整季第一条公告公布粗方向，持续低空遮挡，之后不重复 |
| instrument_fault | 不进公告/预报；由得分反馈诊断，report修复 |

天气事件持续以可观测slot计数，白天暂停后可延续下一夜；火箭持续不能延续下一夜。公告和预报均不是对未来隐藏数值的完全观测。

### 7.2 Observation request

record_type=observation_request，schema_version=v4-observation-request-v1。字段request_id、issued_at_utc、deadline_utc、target_ids、minimum_completed、completion_factor_threshold、completion_reward、reason；语义见第5节。active_requests复制这些公开字段，再加completed_target_ids、completed_count、remaining_count，是后端给出的精确请求进度。

### 7.3 Observation request result

record_type=observation_request_result，schema_version=v4-observation-request-result-v1。含issued_at_utc、request_id、status=completed或expired、completed_target_ids、completed_count、minimum_completed、score_delta、revised。

`score_delta` 是本次奖励相对已公布奖励的差，不是累计奖励。revised=false首次结算；revised=true表示先前结果变更，可能撤销奖励并产生负delta，也可能恢复。应用时按request_id更新状态，不把每条completed都当新的独立奖励。

### 7.4 Report result

record_type=report_result，含issued_at_utc、correct、repaired、score_delta；与last_result里report的同一结果不能重复加两次。report作用于提交时当前未修复instrument_fault，正确首次+reward并立即修复该事件，提前/重复/无故障算误报。未来新故障需要另修。

**两种report计数分开：** 连续动作上限，示例允许32次，第33次agent_error；wait/observe使连续计数归零。误报免罚次数自开场或上次正确report累计，示例前2次免罚，第3次起每次−150；wait/observe不重置它。正确report重置误报免罚，但仍占一次连续report。report不推进模拟时间，真实处理时间照常消耗。

### 7.5 State resync（Hard mode）

record_type=state_resync，不是另一个外层message_type。data_loss触发后在下一可处理时点撤销一段以前observe，正在进行的曝光先完成，损失时间不返还。

| 字段 | 含义和处理 |
| --- | --- |
| issued_at_utc / trigger_event_id | 更正送达时模拟时间与触发事件ID |
| invalidated_window.action_count_at_trigger | 当时已执行observe总数N |
| action_index_start / action_index_end_exclusive | 0起observe编号半开失效区间[start,end)，wait/report不算 |
| window_start_fraction / window_end_fraction | 对应floor(iN)、floor(jN)的比例 |
| window_max_fraction | 失效区间比例宽度上限 |
| observed_target_ids | 失效后仍有有效观测条目的目标，不保证达标或正分 |
| best_scores | target_id、best_score；重新计算后的最高贡献 |
| observation_requests | 仍在活动期的请求及重算进度，与active_requests一致 |

不返回精确max_factor或required完成状态。若要精确恢复，应保存每次有效曝光与编号，并按失效窗撤销；但源g本身在协议中没有精确发送，应保留估计区间而非假装已获真值。失效后running_total重算；过期请求变化另外发revised=true结果。

pointing_offset只在Hard mode启用，从周期开始叠加固定alt/az偏差，用实际中心判命中；无公告、无偏差数值、无实际指向反馈。只能通过命中模式和主动探测估计，不应从文件读答案。data_loss也没有event_kind公告，凭resync处理。

## 8. 响应合法性与源码边界

| 动作 | 允许字段和时间行为 |
| --- | --- |
| observe | pointing、assignments、duration_seconds，program可选；推进模拟时间，夜间开始按夜末截断 |
| wait | duration_seconds或until_utc二选一；前者申报范围与曝光相同，后者须晚于now，不受3600秒总跳转范围限制 |
| report | 无动作附加字段；不推进模拟时间 |
| finish | 无动作附加字段；结束巡天 |

外层协议字段固定；reason、decision_source是可选字符串并在执行前剥离，不参与评分。未知/多余字段、非法JSON、错误协议/序号、超字节限制、非有限值/布尔伪数字、非整秒、未知目标、重复纤维/目标均可agent_error。

fiber键按整数解释，"5"和"05"会冲突。目标ID是目录字符串，不以数组下标冒充。示例响应上限512KiB，按UTF-8完整JSON行编码字节数，不含换行；不是字符数。

long wait until_utc由后端展开为≤max_duration的wait行，中途不请求Agent，已发布消息积攒在下轮批量发；跨过限时请求时可能已经到期。用until_utc快进白天节省往返，快进夜晚则可能丢机会，不是监听到事件自动唤醒。

核对到的协议与代码细节差异：

| 事项 | 指南 / 后端 / 本地示例的差别 | 本项目约定 |
| --- | --- | --- |
| until_utc后缀 | 指南要求Z；后端还接受+00:00；Python示例只接受Z且未完整查日期和未来性 | 统一输出合法Z字符串并校验晚于now |
| 时长的JSON类型 | 指南要求整数；后端允许数学上为整数的浮点900.0，拒绝bool；示例可能int()截断小数 | 直接输出整数，不依赖宽容行为 |
| 空分配 | 后端允许{}；示例校验主动拒绝至少一源以外的动作 | 测后端时可空分配；正常策略不浪费曝光 |
| resync完成状态 | 后端给最好分不给g；示例用最高倍率换算保守估计，非精确恢复 | 不把示例factor当官方完成状态 |
| 无notice文字 | 示例将空notices转成“clear”；协议不保证晴好 | 模型证据应写“无公开事件”，不能据此确诊天气正常 |

这些不改变“允许跨普通slot”的结论。示例做更保守或更宽松的校验不等于赛题硬规则，不修改官方评分器去迁就它。

## 9. 当前Python Agent实际交互逻辑

实际入口 `experiments/current/agent/agent.py`：启动检查密钥（本地USE_LLM=0豁免） → initialize建SurveyState/Planner → 每request调用Planner.decide → validate_action → note_action → send_response → 后端finish记录总结退出。异常捕获为合法wait回退，日志到stderr；回退不等于策略完成目标。

Planner先保存新预报，处理消息和state_resync，再消费上次曝光反馈，更新命中统计，按真实剩余时间调整fast_level。白天跳到下一夜；新夜调用两项模型建议；夜末剩余少于最小曝光就跳夜/finish；全场rain/storm公告时wait；否则先检查是否report，再选观测或wait。

锚点搜索给目标排序，在6个锚点、候选池300的设置下尝试纤维中心和近邻装填；时间紧时降搜索量。曝光候选为300/450/600/900/1200/1500/1800/2400/3000/3600秒，受模型duration_scale和30秒对齐调整。只限制夜末、目标可见时间与公开曝光范围，没有规则禁止跨slot。参数6/300、10档、required奖励60、安全系数.9、模型时长倍率都是示例策略选择，不是比赛硬规则。

模型两个每夜环节分别基于预报、公告加历史命中率，另有罕见仪器故障确认。它们只提供避让方向和时长倍率，目标装填及数值规划由程序完成。本地入口全部关闭LLM；默认客户端单次12秒、总300秒、100次、每问题最多3次尝试是软件预算，不是比赛规定。已有LLM协作设计是未来方案，不能当本Agent已实现。

当前示例局限须保留：没有完整处理限时请求的任务调度和结果账本；resync以最好分重建保守factor，不能精确恢复原始完成因子；状态与质量从得分反推，存在program匹配与饱和歧义。两份官方Python/Rust也有不同锚点数量和故障策略，直接比得分不等于语言性能对照。本轮不改变这些策略或宣称已修复。

UML对象图、逐步决策流程、后端状态图及本地graphify关系图见[Python源码地图](python-source-map.md)。

## 10. 本地示例在哪里

GitHub当前实际目录为 [examples/_local](https://github.com/gosimfoundation/hackathon-survey26/tree/149c6590c49cf289c325b8e2fedfee1035975c6f/examples/_local)。其中 `cards/L1`–`L4` 和 `runner/` 独立于 `examples/python/`；只打开Python子目录看不到它们。

Git源码布局是 `_local/cards`、`_local/runner`；下载成品ZIP说明使用 `local-cards`、`runner`，属于重排打包布局。源码版run_local.py按父目录找卡名时也存在说明与实际路径不完全一致，**本项目总是传完整卡路径**，不用裸L1依赖它的自动发现。

最新版在[本地目录](../research/2026-10-03/latest-149c659/examples/_local/)，初次下载版本仍在[原快照](../research/2026-10-03/examples/_local/)。L1–L4完整且公开，可离线评分；与正式α–δ是不同卡，不可互填成绩。当前运行方法见 [环境说明](current-environment.md)。

## 11. 赛事政策与仍需确认的边界

比赛使用完整项目GitHub或≤50MB ZIP，正式不接CSV；程序自主决策，语言不限，平台运行部分公开限制为2CPU/2GB。练习α–δ按卡最高，线上A–D按同次评测四卡均分，隐藏E–H评测最终版本四卡均分决定奖项。预算和每日额度以当前参赛页面为准；本轮未登录检查额度或云端部署。

评奖要求至少两个环节采用大模型驱动Agent技术，代码由组委会判断，不要求每回合模型调用；离线程序效果和资格是两件事。当前规则默认加密保存模型密钥，隐藏赛不能用无人打开的页面中转；本项目未配置真实密钥或提交。

### 11.1 参赛、提交与核验政策索引

| 项目 | 当前公开规定 |
| --- | --- |
| 资格与队伍 | 全球个人/团队，队伍1–3人；每人一个账号、只能属于一队。主办方、维护者及直接合作者不评奖，榜单隐藏 |
| 赛程 | 北京时间10月5日00:00至10月7日23:59；冻结后隐藏评测，预计10月10日前公布；10月17日颁奖，以公告为准 |
| 任务卡公开 | α–δ练习公开；A–D比赛开始公开输入，真值隐藏；E–H结束前不可见。每套第4张为超难卡 |
| 每日额度 | 参赛页显示，各队相同，UTC零点/北京时间8点重置；平台原因失败不计，项目构建/崩溃/协议失败计额度 |
| 提交确认 | 审阅并确认固定源码版本、启动设置和平台建议适配文件；不只是上传即生效 |
| 最终版本 | 任一成员可选择已确认且未撤回版本，截止前可更改/取消；截止锁定。未选默认线上最高评测版本；已选版本不能撤回 |
| 模型与算力 | 自备模型密钥/额度，可外部算力与服务；OpenAI兼容公网HTTPS接口，默认443，不接受IP或内网地址；容器限制只约束平台部分 |
| 密钥方式 | 默认加密保存；页面中转要求一直开页面，隐藏赛不可使用；保存模式赛后核实删除，切到不保存立即删服务器密钥 |
| 自动决策 | 每轮程序自动决定，不允许人工代做；不得读取其他队伍数据、篡改分数、故意耗尽平台资源 |
| 同分与榜单 | 练习同卡同分先提交者在前；线上同分先完成评测在前，可临近结束封榜；隐藏同分由主办方公布处理方式 |
| 核验 | 前列可重新运行、要求完整代码、外部服务/模型版本配置及调用记录；保留服务和密钥可用。无法复现、显著不符或人工干预可移除成绩 |
| 版本更正 | 评分器缺陷可重评；评分器/参数变动带版本号公告并适用于该阶段所有提交 |
| 奖项 | 一等奖2000美元1队、二等奖1000美元2队、三等奖500美元3队，税前；领奖不强制到场，获奖代码须公开开源；设计奖另公告 |
| 行为准则 | 尊重交流，不共享账号、不提交他队成果、不组多队扩额度；缺陷报主办方，不利用；资格和奖项最终裁定归主办方 |
| 数据与隐私 | 注册用于办赛；队名分数名次公开。私有ZIP/结果/日志供本队和主办方长期保存，可匿名研究发表；公开仓库Fork仍公开 |
| 许可 | 官方数据、卡片、程序、示例CC BY-NC 4.0，署名非商业；选手自编代码不受该许可限制。引用GOSIM 2026 Agentic Observer Hackathon，基准文章发布后引用文章 |
| 联系与兑换 | 联系hackathon@gosim.org；至少一次完整项目成功评分的练习队可获Kimi兑换码，隐藏/测试队不发，具体领取按控制台 |

以上是本轮固定源码中的政策摘要，不代表已完成账号、兑换、投稿或参赛。密钥、调用与提交操作的本项目边界见环境和根AGENTS。政策完整原文为本页末尾链接的rules.zh.md。

### 11.2 仍需官方确认

| 未决问题 | 已确认事实与待确认部分 |
| --- | --- |
| 隐藏卡超时/错误记分 | 引擎保留此前轨迹并终局结算；赛事隐藏排名条款另说自身原因未完成记0，需确认正常budget-expired与评测失败的边界 |
| 线上卡光纤配置 | 规则页描述16/25/9/100；例卡与本地卡不一定相同，应由各卡initialize确认，不能再称所有卡固定16 |
| 云端版本与资源成本 | 最新公开源码已固定，本地引擎散列验证；云端CPU、处理开销、代理额度和实际部署未本轮复验 |
| 待评测正式卡文件 | 现有α–δ下载预检缺产品，无本地正式成绩；新增L卡不能补造缺项 |

## 12. 公开配置完整索引

以下所有值从initialize获取；不从任务卡名字猜。配置不公开事件真值或种子。

| 配置key | 含义 |
| --- | --- |
| task_card.card_id / scenario_slug / phase | 任务、场景、阶段标识，后两项依卡可选 |
| site.name / latitude_deg / longitude_deg / utc_offset_hours | 台址与坐标/当地时区解释 |
| site.sun_altitude_limit_deg / minimum_altitude_deg | 夜界太阳高度、计分目标整段最低高度 |
| survey.start_utc / end_utc / slot_seconds | 周期与天气网格 |
| survey.nights[].night_id / night_date / observing_start_utc / observing_end_utc / slot_count | 各夜标识、日期、可观测起止和格数 |
| instrument.n_fibers / grid_side / fiber_area_deg2 / gap_deg | 纤维数、网格边数、单格面积、间隙 |
| instrument.glass_side_deg / pitch_deg / fov_side_deg / layout | 可分配格边长、格中心距、全场边长、投影编号 |
| instrument.exposure.min_duration_seconds / max_duration_seconds | observe和按秒wait申报范围 |
| scoring.schema_version | 公开评分结构版本 |
| scoring.q0 / flux_zero_point / exposure_zero_point_seconds / airmass_exponent | Q归一化q0、f0、T0、大气质量β |
| scoring.lunar_model.angular_decay_scale_deg / altitude_exponent / maximum_penalty | 月光θ_M、γ_M、P_M |
| scoring.program.bands.DARK / BRIGHT | B判档阈值，低于BRIGHT为BACKUP |
| scoring.program.multipliers.DARK / BRIGHT / BACKUP / mismatch_multiplier | 匹配和不匹配贡献倍率 |
| scoring.required.penalty_per_missing / observed_factor_threshold | 必做未完成罚分和g门槛 |
| scoring.uniformity.weight / ra_band_width_deg / observed_factor_threshold | U、RA条带宽度、纳入完成率g门槛 |
| scoring.reporting.correct_reward / false_penalty / false_report_free_allowance / max_consecutive_reports | 正确/错误奖惩、免罚数、连续report上限 |
| scoring.observation_requests.completion_factor_threshold / miss_penalty | 请求参考g门槛、未完成罚分（当前0）；每项请求还有公开门槛字段 |
| limits.global_wallclock_seconds / max_consecutive_reports / response_max_bytes / decision_timeout | 整卡真实预算、重复报告限制、单行字节上限、只有全局时限 |
| footprint[].component_id / vertices | 球面天区ID和有序[ra,dec]顶点 |
| targets.columns / rows | 目录schema和数据 |

## 13. 源码与验证导航

最新版源码已原样导出，裁判未修改；[源码对照](../experiments/current/rules-audit/source-comparison.json)核对引用文件与Git对象，以及打包裁判与根源码的一致性。固定revision避免main后续变化混进本轮解释。

| 问题 | 官方实现与本地证据 |
| --- | --- |
| 初始化、外层、序号、全局预算 | [v4_workflow.py](../research/2026-10-03/latest-149c659/challenge/v4_workflow.py)的initialize_payload、action_from_response、run |
| 模拟循环、批量消息、夜末、反馈、终局 | [v4_runner.py](../research/2026-10-03/latest-149c659/challenge/v4_runner.py)的run_scenario、normalize_action |
| Q/B、最大分/g、请求、均匀性、report | [v4_scorer.py](../research/2026-10-03/latest-149c659/challenge/v4_scorer.py)的WeatherTruth、score_target_exposure、BestLedger |
| 光纤投影、边界、整段高度 | [v4_fiber_map.py](../research/2026-10-03/latest-149c659/examples/_local/runner/challenge/v4_fiber_map.py) |
| JSONL发送接收、字节限制、退出 | [transport.py](../research/2026-10-03/latest-149c659/project_platform/transport.py) |
| 云端与本地deadline及finish组合 | [trusted_engine.py](../research/2026-10-03/latest-149c659/project_platform/trusted_engine.py)的run_v4_session |
| 本地Agent交互与状态估计 | [agent.py](../experiments/current/agent/agent.py)、[planner.py](../experiments/current/agent/agent_core/planner.py)、[state.py](../experiments/current/agent/agent_core/state.py)、[validation.py](../experiments/current/agent/agent_core/validation.py) |
| 四项专项核对与公开请求轨迹 | [verification.json](../experiments/current/rules-audit/evidence-refresh/verification.json)、[evidence](../experiments/current/rules-audit/evidence-refresh/) |
| 赛事政策原文 | [rules.zh.md](../research/2026-10-03/latest-149c659/web/src/content/rules.zh.md) |

规则解释与真实观测差异见 [差异说明](v4-observing-gaps.md)。历史策略的具体参数与跑分见原研究报告，不作为协议硬规则。后续如版本变化，先固定新源码、对照差异和验证，再更新本页并重建HTML。
