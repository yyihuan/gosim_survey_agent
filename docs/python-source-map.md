# Python source map

核对版本与配置以 [当前环境](current-environment.md)为准。本页解释已经运行的实现，规则以 [v4规则与协议](v4-rules-and-protocol.md)为准；[协作设计](v4-llm-collaboration.md)与[优化器大纲](agent-optimizer-outline.md)属于下一阶段方案，不能混作现成功能。

## 1. 先区分两套程序

Agent从公开JSONL消息做决策，维护自己的估计；可信后端读取完整卡、执行动作、维护有效账本并计分。Agent的ScoringModel是规划近似，后端Scorer是裁判。尤其不能因两边都有factor而认为Agent知道真值。

![可信后端主要关系](diagrams/v4-backend-classes.svg)

图中Runner、Scorer标为module，它们是函数模块而非源码类；其余节点对应真实类。V4Workflow把公开协议回调连接到run_scenario，不把truth发送给Agent。score_target_exposure计算Q/g，WeatherTruth.band_quality计算B；BestLedger分别维护最好分与最大完成因子。

## 2. Agent对象与模块

![Agent UML对象关系](diagrams/python-agent-classes.svg)

| 对象或模块 | 职责与源码入口 |
| --- | --- |
| agent.py / protocol.py | 读取三类外层消息、捕获错误、校验后发送一行响应；入口[main](../experiments/current/agent/agent.py) |
| SurveyState | 公开目录、夜历、邻域索引和估计完成状态；[state.py](../experiments/current/agent/agent_core/state.py) |
| Planner | 夜建议、举报判断、候选排程、曝光和program选择；[planner.py](../experiments/current/agent/agent_core/planner.py) |
| FiberGrid / geometry | 地平与赤道坐标、月亮、光纤方格；[geometry.py](../experiments/current/agent/agent_core/geometry.py) |
| ScoringModel | 公开公式的规划近似与program阈值；[scoring.py](../experiments/current/agent/agent_core/scoring.py) |
| LLMClient | JSON模型建议、预算、重试；USE_LLM=0不发HTTP；[llm_client.py](../experiments/current/agent/agent_core/llm_client.py) |
| validation.py | 示例本地动作约束，失败回退；与裁判校验存在差异，不能代替协议；[validation.py](../experiments/current/agent/agent_core/validation.py) |
| TraceLog | 诊断轨迹，不是评分账本；[memory.py](../experiments/current/agent/agent_core/memory.py) |

## 3. 一轮决策逐步走

![当前Python决策流程](diagrams/python-decision-flow.svg)

对应Planner.decide的调用顺序：保存新forecast → on_messages → on_result →累计命中率 → _pace → 查夜历 → 新夜建议 → 夜末处理 → 全场关闭 → _maybe_report → plan。校验与note_action在agent.main中，所以回退动作也会正确更新连续举报计数。

plan先更新scale，筛选仍有价值且可见的源，估计可达到的深度与必做收益，再挑锚点、尝试光纤位置并选近邻。_finish_plan比较候选时长与program，保存pending供下轮反馈反推。跨slot不是异常分支：候选时长包含1800至3600秒，限制来自夜末、可见窗口和曝光上下限。

每夜两项模型建议共享本地预算；失败或离线返回None，仍用程序。故障确认是另一触发路径，不是每轮调用。真实900秒会促使_pace缩小搜索，但不会把天气slot变成固定回合。

## 4. 后端生命周期

![后端动作状态图](diagrams/v4-action-state.svg)

这张状态图表达控制流，不表示存在同名状态类。普通slot切换留在Exposure内；后端直到动作结束才生成下个Decision。夜末截断是动作结束的条件之一。wait until可在Waiting内展开多行，report立即回到同一模拟时刻。模拟结束或真实截止后进入终局结算，finish通知仅尽力送达。

完整交互顺序见[序列图与字段字典](v4-rules-and-protocol.md)。跨slot、截断、连续举报和账本的[专项验证](../experiments/current/rules-audit/evidence-refresh/verification.json)使图中关键分支有实际引擎证据。

## 5. 需要避免的状态误读

- factor是Agent从score、program及质量模型反推的估计，不是后端max_factor。亮源饱和和program不匹配都使反推不唯一。
- on_messages先处理resync并清空pending，随后on_result不会再消费该pending。更正以最好分重建保守估计；当前没有精确的逐曝光完成因子恢复。
- 当前Planner没有利用active_requests建立完整任务调度；消息里有请求不代表示例已经优化它。
- latest_bulletin重复发送最新记录，new_messages仅发送新批次；方向notice缺失不保证晴好。
- validation拒绝空分配，后端允许。图中的合法性检查是本地防护，正式规则仍回到normalize_action。

这些是本轮已定位的实现边界，不是已修复事项。下一步修改策略时先定义需要改变的行为，再用新的独立run验证。

## 6. 本地graphify导航

本轮使用本机graphify的AST提取，显式scope=all，排除文档和非代码材料，不启用semantic/backend，不调用模型。Agent工作副本11个代码文件生成133节点、205关系；官方runner18文件生成379节点、819关系。统计指AST关系，不能当作全部运行时调用或正确性证明。

- [Agent静态交互图](../experiments/current/rules-audit/python-graph/.graphify/studio/index.html)
- [后端静态交互图](../experiments/current/rules-audit/backend-graph/.graphify/studio/index.html)
- [图与源码散列清单](../experiments/current/rules-audit/source-graphs.json)

graphify Studio需通过本地静态服务打开，以加载配套JSON；规则讲解HTML可直接离线打开。可从项目根目录执行以下命令，然后在浏览器打开`http://127.0.0.1:8090/python-graph/.graphify/studio/`或`http://127.0.0.1:8090/backend-graph/.graphify/studio/`：

```bash
/usr/bin/python3 -m http.server 8090 --bind 127.0.0.1 --directory experiments/current/rules-audit
```

重建命令为`/usr/bin/python3 -B scripts/build_source_graphs.py`，重建后应查看源码变动，再按本页函数入口核对；UML只修改docs/diagrams中的mmd并重新渲染。

图中推断需由源码验证：静态工具不能完整解析动态回调、嵌套闭包、字典动作及环境配置。这里的UML与流程图经过函数实现和专项验证核对，graphify用于定位关系。
