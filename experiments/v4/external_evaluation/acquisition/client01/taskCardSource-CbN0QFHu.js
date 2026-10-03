import{n as e}from"./supabase-HbgHf8cp.js";import{i as t}from"./browser-C9LvnZ1m.js";import{i as n}from"./storage-Cn8gmHG1.js";var r=[{id:`alpha`,slug:`v4-practice-alpha`,stage:`practice`,symbol:`α`},{id:`beta`,slug:`v4-practice-beta`,stage:`practice`,symbol:`β`},{id:`gamma`,slug:`v4-practice-gamma`,stage:`practice`,symbol:`γ`},{id:`delta`,slug:`v4-practice-delta`,stage:`practice`,symbol:`δ`}],i=[`a`,`b`,`c`,`d`].map(e=>({id:e,slug:`v4-${e}`,stage:`formal`,symbol:e.toUpperCase()})),a=[`config`,`public`,`truth`],o=e=>`public/taskcard.${e}.md`;function s(e){let t=new Set(e.map(e=>/taskcard\.([a-z]+)\.v4\.(?:zh|en)\.md$/.exec(e)?.[1]).filter(Boolean));return r.filter(e=>t.has(e.id))}function c(e){return[...r,...i].find(t=>t.id===e)??null}function l(e,t){return e?.match(/^#\s+(.+)$/m)?.[1]?.trim()??t.symbol}function u(e,t){return/^(config|public|truth)\/[A-Za-z0-9_.-]+$/.test(t)&&!t.includes(`..`)?`${e.id}/${t}`:null}var d=Object.assign({"../content/taskcard.alpha.v4.en.md":`# Task card α (alpha): Opening season

A full season at Paranal with only the weather to handle.

## At a glance

| | |
|---|---|
| Site | Paranal, Chile (virtual). Latitude −24.62°, longitude −70.40°. |
| Survey | 2026-10-04 to 2026-11-10, 38 nights. You observe when the sun is below −18°. |
| Targets | 10,000 targets on 2,000 deg² of sky, in 3 regions. 500 are required. |
| Instrument | 16 contiguous fibre assignment cells in a 4 × 4 grid. The field covers 6.4 deg² and is about 2.53° across. |
| Time limit | 900 s of wall-clock time for the whole survey. |
| Weather | Not public. During a run the agent receives a briefing every 15 minutes and a forecast about once a week. |
| Extra messages | Time-limited observation requests (\`observation_request\`) and their results (\`observation_request_result\`). |

## Your goal

1. Observe as many valuable targets as you can, as well as you can.
2. Observe every **required** target well enough. Each one you miss costs 50 points.
3. Spread your work across the sky. Leaving parts of the sky empty costs up to 200 points.

## What your agent gets

**Once, at the start (\`initialize\`):**
- the site, the list of nights and when each night starts and ends;
- every target: position, class, brightness, weight and whether it is required;
- the sky regions, the instrument layout and the full score settings;
- the time limit.

**At every decision (\`decision_request\`):**
- the current time;
- the latest bulletin and forecast, and all messages since your last decision;
- the result of your last observation: which targets hit their fibre, and their scores;
- the time-limited observation requests in progress and how far along they are (\`active_requests\`);
- the time you have left.

## What your agent sends

One action per decision:

| Action | Meaning |
|---|---|
| \`observe\` | Point the telescope, put up to 16 targets on fibres, expose for 60–3600 s, and declare a program (DARK, BRIGHT or BACKUP). |
| \`wait\` | Let time pass: a number of seconds, or until a given time (for example the next night). |
| \`report\` | Say that the instrument is faulty now. Right: +100. After each correct report, wrong reports are free up to the card's configured allowance, then −150 each; consecutive report actions have a separate cap. |
| \`finish\` | End the survey now. |

## How the score works

- A target scores only if it falls in its assigned fibre's cell and stays at or above 30° altitude.
- Its score grows with brightness, exposure time and sky quality, up to a cap.
- A matching program adds 20% (DARK), 12% (BRIGHT) or 6% (BACKUP). A wrong program adds nothing.
- Only the best exposure of each target counts.
- Time-limited observation requests: complete enough of a request's targets inside its time window to earn its reward; a missed request costs nothing.
- Final score = sum of best scores − 50 × missing required targets − unevenness penalty ± reports + request rewards.

**Example.** A target has brightness 0.60 and weight 1.0. You expose it for 900 s. The sky quality is 0.75.
Its factor is 0.60 × 900 × 0.75 ÷ 450 = 0.90. You declared DARK and the sky was DARK, so the score is
1.0 × 0.90 × 1.20 = **1.08**. With a 300 s exposure the factor is only 0.30. A required target needs at
least 0.50, so it would still count as missing.

## Common mistakes

- Printing logs to stdout. Only JSON answers go to stdout. Logs go to stderr.
- Answering with the wrong \`decision_sequence\`, or adding unknown fields. The run stops with \`agent_error\`.
- Calling a language model on every decision. The time limit runs out long before the survey ends.
- Short exposures on faint targets. Exposures do not add up; only the best one counts.
- Pointing low in a direction a bulletin warns about.
- Reporting a fault after one bad exposure. Weather also lowers scores.

## Try it

Pack your whole agent project as a zip and upload it on the Participate page. Practice runs all practice cards α, β, γ and δ in the cloud, with the same 900 s limit. Daily limits are on the Rules page.

Practice scores do not decide awards.
`,"../content/taskcard.alpha.v4.zh.md":`# 任务卡 α（alpha）：开局之季

帕拉纳尔的一整个季节，只有天气需要应对。

## 一览

| | |
|---|---|
| 站点 | 智利帕拉纳尔（虚拟站点）。纬度 −24.62°，经度 −70.40°。 |
| 巡天时间 | 2026-10-04 至 2026-11-10，共 38 夜。太阳低于 −18° 时可以观测。 |
| 目标 | 天区共 2,000 平方度，分为 3 块，有 10,000 个目标。其中 500 个是必观测目标。 |
| 仪器 | 16 个光纤可指派方格，排成 4 × 4、无间隙。总面积 6.4 平方度，视场宽约 2.53°。 |
| 时间限制 | 整个巡天最多用 900 秒真实时间。 |
| 天气 | 不公开。运行中智能体会收到每 15 分钟一条的简报和大约每周一次的预报。 |
| 额外消息 | 限时观测请求（\`observation_request\`）及其结果（\`observation_request_result\`）。 |

## 你的目标

1. 尽量多观测有价值的目标，并且观测得好。
2. 每个**必观测**目标都要观测到位。漏掉一个扣 50 分。
3. 观测要覆盖整片天区。某些区域空着，最多扣 200 分。

## 智能体收到什么

**开始时一次（\`initialize\`）：**
- 站点、每一夜的列表，以及每夜的开始和结束时间；
- 全部目标：位置、类别、亮度、权重、是否必观测；
- 天区范围、仪器布局和完整的计分参数；
- 时间限制。

**每次决策时（\`decision_request\`）：**
- 当前时间；
- 最新的简报和预报，以及上次决策之后的所有消息；
- 上一次观测的结果：哪些目标落在了分配的光纤上，各得多少分；
- 进行中的限时观测请求及其进度（\`active_requests\`）；
- 剩余时间。

## 智能体发送什么

每次决策发送一个动作：

| 动作 | 含义 |
|---|---|
| \`observe\` | 指向天空某处，给最多 16 根光纤各分配一个目标，曝光 60–3600 秒，并声明一个观测程序（DARK、BRIGHT 或 BACKUP）。 |
| \`wait\` | 等待：等若干秒，或等到某个时刻（例如下一夜开始）。 |
| \`report\` | 报告仪器现在有故障。报对 +100；每次正确举报后，误报在任务卡配置的免罚次数内不扣分，之后每次 −150。连续提交 \`report\` 另有次数上限。 |
| \`finish\` | 立即结束巡天。 |

## 怎么计分

- 目标必须落在分配给它的那根光纤的可指派方格内，并且全程不低于 30° 高度角，才能得分。
- 目标越亮、曝光越长、天空越好，得分越高，但有上限。
- 程序声明正确时加分：DARK 加 20%，BRIGHT 加 12%，BACKUP 加 6%。声明错误不加分。
- 每个目标只算它最好的一次曝光。
- 限时观测请求：在请求的时间窗内完成足够多的指定目标即获得请求奖励，未完成不扣分。
- 最终得分 = 各目标最好得分之和 − 50 × 漏掉的必观测目标数 − 不均匀扣分 ± 故障报告得失 + 观测请求奖励。

**例子。** 某目标亮度 0.60，权重 1.0。你曝光 900 秒。天空质量是 0.75。
它的系数是 0.60 × 900 × 0.75 ÷ 450 = 0.90。你声明 DARK，天空也是 DARK，得分是
1.0 × 0.90 × 1.20 = **1.08**。如果只曝光 300 秒，系数只有 0.30。必观测目标至少要 0.50，
所以它仍然算作漏掉。

## 常见错误

- 把日志打印到标准输出。标准输出只能写 JSON 回复，日志写到标准错误。
- \`decision_sequence\` 填错，或者加了未知字段。运行会以 \`agent_error\` 结束。
- 每次决策都调用大模型。时间限制会在巡天结束前用完。
- 对暗目标用短曝光。多次曝光不会累加，只算最好的一次。
- 在简报警告的方向上指向低仰角。
- 一次曝光变差就报告故障。天气也会让分数变低。

## 动手试试

把整个智能体项目打包成 zip，在「参赛」页上传。练习赛会在云端运行全部练习卡 α、β、γ、δ，时间限制同样是 900 秒。每日次数见规则页。

练习赛成绩只用于练习，不决定奖项。
`,"../content/taskcard.beta.v4.en.md":`# Task card β (beta): Moving sky

A season from mid-October: the sky moves with the season, and the targets lie in other parts of it.

## At a glance

| | |
|---|---|
| Site | Paranal, Chile (virtual). Latitude −24.62°, longitude −70.40°. |
| Survey | 2026-10-18 to 2026-11-24, 38 nights. You observe when the sun is below −18°. |
| Targets | 9,600 targets on 1,920 deg² of sky, in 3 regions. 480 are required. |
| Instrument | 16 contiguous fibre assignment cells in a 4 × 4 grid. The field covers 6.4 deg² and is about 2.53° across. |
| Time limit | 900 s of wall-clock time for the whole survey. |
| Weather | Not public. During a run the agent receives a briefing every 15 minutes and a forecast about once a week. |
| Extra messages | Time-limited observation requests (\`observation_request\`) and their results (\`observation_request_result\`). |

## Your goal

1. Observe as many valuable targets as you can, as well as you can.
2. Observe every **required** target well enough. Each one you miss costs 50 points.
3. Spread your work across the sky. Leaving parts of the sky empty costs up to 200 points.

## What your agent gets

**Once, at the start (\`initialize\`):**
- the site, the list of nights and when each night starts and ends;
- every target: position, class, brightness, weight and whether it is required;
- the sky regions, the instrument layout and the full score settings;
- the time limit.

**At every decision (\`decision_request\`):**
- the current time;
- the latest bulletin and forecast, and all messages since your last decision;
- the result of your last observation: which targets hit their fibre, and their scores;
- the time-limited observation requests in progress and how far along they are (\`active_requests\`);
- the time you have left.

## What your agent sends

One action per decision:

| Action | Meaning |
|---|---|
| \`observe\` | Point the telescope, put up to 16 targets on fibres, expose for 60–3600 s, and declare a program (DARK, BRIGHT or BACKUP). |
| \`wait\` | Let time pass: a number of seconds, or until a given time (for example the next night). |
| \`report\` | Say that the instrument is faulty now. Right: +100. After each correct report, wrong reports are free up to the card's configured allowance, then −150 each; consecutive report actions have a separate cap. |
| \`finish\` | End the survey now. |

## How the score works

- A target scores only if it falls in its assigned fibre's cell and stays at or above 30° altitude.
- Its score grows with brightness, exposure time and sky quality, up to a cap.
- A matching program adds 20% (DARK), 12% (BRIGHT) or 6% (BACKUP). A wrong program adds nothing.
- Only the best exposure of each target counts.
- Time-limited observation requests: complete enough of a request's targets inside its time window to earn its reward; a missed request costs nothing.
- Final score = sum of best scores − 50 × missing required targets − unevenness penalty ± reports + request rewards.

**Example.** A target has brightness 0.60 and weight 1.0. You expose it for 900 s. The sky quality is 0.75.
Its factor is 0.60 × 900 × 0.75 ÷ 450 = 0.90. You declared DARK and the sky was DARK, so the score is
1.0 × 0.90 × 1.20 = **1.08**. With a 300 s exposure the factor is only 0.30. A required target needs at
least 0.50, so it would still count as missing.

## Common mistakes

- Printing logs to stdout. Only JSON answers go to stdout. Logs go to stderr.
- Answering with the wrong \`decision_sequence\`, or adding unknown fields. The run stops with \`agent_error\`.
- Calling a language model on every decision. The time limit runs out long before the survey ends.
- Short exposures on faint targets. Exposures do not add up; only the best one counts.
- Pointing low in a direction a bulletin warns about.
- Reporting a fault after one bad exposure. Weather also lowers scores.

## Try it

Pack your whole agent project as a zip and upload it on the Participate page. Practice runs all practice cards α, β, γ and δ in the cloud, with the same 900 s limit. Daily limits are on the Rules page.

Practice scores do not decide awards.
`,"../content/taskcard.beta.v4.zh.md":`# 任务卡 β（beta）：移动的天空

从十月中旬开始的一季：天空随季节移动，目标分布在天空的其他位置。

## 一览

| | |
|---|---|
| 站点 | 智利帕拉纳尔（虚拟站点）。纬度 −24.62°，经度 −70.40°。 |
| 巡天时间 | 2026-10-18 至 2026-11-24，共 38 夜。太阳低于 −18° 时可以观测。 |
| 目标 | 天区共 1,920 平方度，分为 3 块，有 9,600 个目标。其中 480 个是必观测目标。 |
| 仪器 | 16 个光纤可指派方格，排成 4 × 4、无间隙。总面积 6.4 平方度，视场宽约 2.53°。 |
| 时间限制 | 整个巡天最多用 900 秒真实时间。 |
| 天气 | 不公开。运行中智能体会收到每 15 分钟一条的简报和大约每周一次的预报。 |
| 额外消息 | 限时观测请求（\`observation_request\`）及其结果（\`observation_request_result\`）。 |

## 你的目标

1. 尽量多观测有价值的目标，并且观测得好。
2. 每个**必观测**目标都要观测到位。漏掉一个扣 50 分。
3. 观测要覆盖整片天区。某些区域空着，最多扣 200 分。

## 智能体收到什么

**开始时一次（\`initialize\`）：**
- 站点、每一夜的列表，以及每夜的开始和结束时间；
- 全部目标：位置、类别、亮度、权重、是否必观测；
- 天区范围、仪器布局和完整的计分参数；
- 时间限制。

**每次决策时（\`decision_request\`）：**
- 当前时间；
- 最新的简报和预报，以及上次决策之后的所有消息；
- 上一次观测的结果：哪些目标落在了分配的光纤上，各得多少分；
- 进行中的限时观测请求及其进度（\`active_requests\`）；
- 剩余时间。

## 智能体发送什么

每次决策发送一个动作：

| 动作 | 含义 |
|---|---|
| \`observe\` | 指向天空某处，给最多 16 根光纤各分配一个目标，曝光 60–3600 秒，并声明一个观测程序（DARK、BRIGHT 或 BACKUP）。 |
| \`wait\` | 等待：等若干秒，或等到某个时刻（例如下一夜开始）。 |
| \`report\` | 报告仪器现在有故障。报对 +100；每次正确举报后，误报在任务卡配置的免罚次数内不扣分，之后每次 −150。连续提交 \`report\` 另有次数上限。 |
| \`finish\` | 立即结束巡天。 |

## 怎么计分

- 目标必须落在分配给它的那根光纤的可指派方格内，并且全程不低于 30° 高度角，才能得分。
- 目标越亮、曝光越长、天空越好，得分越高，但有上限。
- 程序声明正确时加分：DARK 加 20%，BRIGHT 加 12%，BACKUP 加 6%。声明错误不加分。
- 每个目标只算它最好的一次曝光。
- 限时观测请求：在请求的时间窗内完成足够多的指定目标即获得请求奖励，未完成不扣分。
- 最终得分 = 各目标最好得分之和 − 50 × 漏掉的必观测目标数 − 不均匀扣分 ± 故障报告得失 + 观测请求奖励。

**例子。** 某目标亮度 0.60，权重 1.0。你曝光 900 秒。天空质量是 0.75。
它的系数是 0.60 × 900 × 0.75 ÷ 450 = 0.90。你声明 DARK，天空也是 DARK，得分是
1.0 × 0.90 × 1.20 = **1.08**。如果只曝光 300 秒，系数只有 0.30。必观测目标至少要 0.50，
所以它仍然算作漏掉。

## 常见错误

- 把日志打印到标准输出。标准输出只能写 JSON 回复，日志写到标准错误。
- \`decision_sequence\` 填错，或者加了未知字段。运行会以 \`agent_error\` 结束。
- 每次决策都调用大模型。时间限制会在巡天结束前用完。
- 对暗目标用短曝光。多次曝光不会累加，只算最好的一次。
- 在简报警告的方向上指向低仰角。
- 一次曝光变差就报告故障。天气也会让分数变低。

## 动手试试

把整个智能体项目打包成 zip，在「参赛」页上传。练习赛会在云端运行全部练习卡 α、β、γ、δ，时间限制同样是 900 秒。每日次数见规则页。

练习赛成绩只用于练习，不决定奖项。
`,"../content/taskcard.delta.v4.en.md":`# Task card δ (delta): Extreme season

A larger share of the targets is required, and part of your recent data can be lost once.

## At a glance

| | |
|---|---|
| Site | Paranal, Chile (virtual). Latitude −24.62°, longitude −70.40°. |
| Survey | 2026-10-24 to 2026-11-30, 38 nights. You observe when the sun is below −18°. |
| Targets | 9,400 targets on 1,880 deg² of sky, in 3 regions. 564 are required. |
| Instrument | 16 contiguous fibre assignment cells in a 4 × 4 grid. The field covers 6.4 deg² and is about 2.53° across. |
| Time limit | 900 s of wall-clock time for the whole survey. |
| Weather | Not public. During a run the agent receives a briefing every 15 minutes and a forecast about once a week. |
| Extra messages | Time-limited observation requests (\`observation_request\`) and their results (\`observation_request_result\`). Possibly one \`state_resync\` message. It means part of your recent data was lost. It lists the targets that still count and their best scores. Rebuild your list of finished targets from it. The time already spent is not returned. |

## Your goal

1. Observe as many valuable targets as you can, as well as you can.
2. Observe every **required** target well enough. Each one you miss costs 50 points.
3. Spread your work across the sky. Leaving parts of the sky empty costs up to 200 points.

## What your agent gets

**Once, at the start (\`initialize\`):**
- the site, the list of nights and when each night starts and ends;
- every target: position, class, brightness, weight and whether it is required;
- the sky regions, the instrument layout and the full score settings;
- the time limit.

**At every decision (\`decision_request\`):**
- the current time;
- the latest bulletin and forecast, and all messages since your last decision;
- the result of your last observation: which targets hit their fibre, and their scores;
- the time-limited observation requests in progress and how far along they are (\`active_requests\`);
- the time you have left.

## What your agent sends

One action per decision:

| Action | Meaning |
|---|---|
| \`observe\` | Point the telescope, put up to 16 targets on fibres, expose for 60–3600 s, and declare a program (DARK, BRIGHT or BACKUP). |
| \`wait\` | Let time pass: a number of seconds, or until a given time (for example the next night). |
| \`report\` | Say that the instrument is faulty now. Right: +100. After each correct report, wrong reports are free up to the card's configured allowance, then −150 each; consecutive report actions have a separate cap. |
| \`finish\` | End the survey now. |

## How the score works

- A target scores only if it falls in its assigned fibre's cell and stays at or above 30° altitude.
- Its score grows with brightness, exposure time and sky quality, up to a cap.
- A matching program adds 20% (DARK), 12% (BRIGHT) or 6% (BACKUP). A wrong program adds nothing.
- Only the best exposure of each target counts.
- Time-limited observation requests: complete enough of a request's targets inside its time window to earn its reward; a missed request costs nothing.
- Final score = sum of best scores − 50 × missing required targets − unevenness penalty ± reports + request rewards.

**Example.** A target has brightness 0.60 and weight 1.0. You expose it for 900 s. The sky quality is 0.75.
Its factor is 0.60 × 900 × 0.75 ÷ 450 = 0.90. You declared DARK and the sky was DARK, so the score is
1.0 × 0.90 × 1.20 = **1.08**. With a 300 s exposure the factor is only 0.30. A required target needs at
least 0.50, so it would still count as missing.

## Common mistakes

- Printing logs to stdout. Only JSON answers go to stdout. Logs go to stderr.
- Answering with the wrong \`decision_sequence\`, or adding unknown fields. The run stops with \`agent_error\`.
- Calling a language model on every decision. The time limit runs out long before the survey ends.
- Short exposures on faint targets. Exposures do not add up; only the best one counts.
- Pointing low in a direction a bulletin warns about.
- Reporting a fault after one bad exposure. Weather also lowers scores.

## Try it

Pack your whole agent project as a zip and upload it on the Participate page. Practice runs all practice cards α, β, γ and δ in the cloud, with the same 900 s limit. Daily limits are on the Rules page.

Practice scores do not decide awards.
`,"../content/taskcard.delta.v4.zh.md":`# 任务卡 δ（delta）：极限之季

必观测目标的比例更高，最近的一部分数据还可能丢失一次。

## 一览

| | |
|---|---|
| 站点 | 智利帕拉纳尔（虚拟站点）。纬度 −24.62°，经度 −70.40°。 |
| 巡天时间 | 2026-10-24 至 2026-11-30，共 38 夜。太阳低于 −18° 时可以观测。 |
| 目标 | 天区共 1,880 平方度，分为 3 块，有 9,400 个目标。其中 564 个是必观测目标。 |
| 仪器 | 16 个光纤可指派方格，排成 4 × 4、无间隙。总面积 6.4 平方度，视场宽约 2.53°。 |
| 时间限制 | 整个巡天最多用 900 秒真实时间。 |
| 天气 | 不公开。运行中智能体会收到每 15 分钟一条的简报和大约每周一次的预报。 |
| 额外消息 | 限时观测请求（\`observation_request\`）及其结果（\`observation_request_result\`）。另外可能收到一条 \`state_resync\` 消息。它表示最近的一部分数据丢失了。消息里列出仍然有效的目标和各自的最好得分。请据此重建"已完成目标"列表。已经用掉的时间不会退回。 |

## 你的目标

1. 尽量多观测有价值的目标，并且观测得好。
2. 每个**必观测**目标都要观测到位。漏掉一个扣 50 分。
3. 观测要覆盖整片天区。某些区域空着，最多扣 200 分。

## 智能体收到什么

**开始时一次（\`initialize\`）：**
- 站点、每一夜的列表，以及每夜的开始和结束时间；
- 全部目标：位置、类别、亮度、权重、是否必观测；
- 天区范围、仪器布局和完整的计分参数；
- 时间限制。

**每次决策时（\`decision_request\`）：**
- 当前时间；
- 最新的简报和预报，以及上次决策之后的所有消息；
- 上一次观测的结果：哪些目标落在了分配的光纤上，各得多少分；
- 进行中的限时观测请求及其进度（\`active_requests\`）；
- 剩余时间。

## 智能体发送什么

每次决策发送一个动作：

| 动作 | 含义 |
|---|---|
| \`observe\` | 指向天空某处，给最多 16 根光纤各分配一个目标，曝光 60–3600 秒，并声明一个观测程序（DARK、BRIGHT 或 BACKUP）。 |
| \`wait\` | 等待：等若干秒，或等到某个时刻（例如下一夜开始）。 |
| \`report\` | 报告仪器现在有故障。报对 +100；每次正确举报后，误报在任务卡配置的免罚次数内不扣分，之后每次 −150。连续提交 \`report\` 另有次数上限。 |
| \`finish\` | 立即结束巡天。 |

## 怎么计分

- 目标必须落在分配给它的那根光纤的可指派方格内，并且全程不低于 30° 高度角，才能得分。
- 目标越亮、曝光越长、天空越好，得分越高，但有上限。
- 程序声明正确时加分：DARK 加 20%，BRIGHT 加 12%，BACKUP 加 6%。声明错误不加分。
- 每个目标只算它最好的一次曝光。
- 限时观测请求：在请求的时间窗内完成足够多的指定目标即获得请求奖励，未完成不扣分。
- 最终得分 = 各目标最好得分之和 − 50 × 漏掉的必观测目标数 − 不均匀扣分 ± 故障报告得失 + 观测请求奖励。

**例子。** 某目标亮度 0.60，权重 1.0。你曝光 900 秒。天空质量是 0.75。
它的系数是 0.60 × 900 × 0.75 ÷ 450 = 0.90。你声明 DARK，天空也是 DARK，得分是
1.0 × 0.90 × 1.20 = **1.08**。如果只曝光 300 秒，系数只有 0.30。必观测目标至少要 0.50，
所以它仍然算作漏掉。

## 常见错误

- 把日志打印到标准输出。标准输出只能写 JSON 回复，日志写到标准错误。
- \`decision_sequence\` 填错，或者加了未知字段。运行会以 \`agent_error\` 结束。
- 每次决策都调用大模型。时间限制会在巡天结束前用完。
- 对暗目标用短曝光。多次曝光不会累加，只算最好的一次。
- 在简报警告的方向上指向低仰角。
- 一次曝光变差就报告故障。天气也会让分数变低。

## 动手试试

把整个智能体项目打包成 zip，在「参赛」页上传。练习赛会在云端运行全部练习卡 α、β、γ、δ，时间限制同样是 900 秒。每日次数见规则页。

练习赛成绩只用于练习，不决定奖项。
`,"../content/taskcard.gamma.v4.en.md":`# Task card γ (gamma): Unsettled season

On top of the weather, part of your recent data can be lost once.

## At a glance

| | |
|---|---|
| Site | Paranal, Chile (virtual). Latitude −24.62°, longitude −70.40°. |
| Survey | 2026-10-09 to 2026-11-15, 38 nights. You observe when the sun is below −18°. |
| Targets | 9,900 targets on 1,980 deg² of sky, in 3 regions. 495 are required. |
| Instrument | 16 contiguous fibre assignment cells in a 4 × 4 grid. The field covers 6.4 deg² and is about 2.53° across. |
| Time limit | 900 s of wall-clock time for the whole survey. |
| Weather | Not public. During a run the agent receives a briefing every 15 minutes and a forecast about once a week. |
| Extra messages | Time-limited observation requests (\`observation_request\`) and their results (\`observation_request_result\`). Possibly one \`state_resync\` message. It means part of your recent data was lost. It lists the targets that still count and their best scores. Rebuild your list of finished targets from it. The time already spent is not returned. |

## Your goal

1. Observe as many valuable targets as you can, as well as you can.
2. Observe every **required** target well enough. Each one you miss costs 50 points.
3. Spread your work across the sky. Leaving parts of the sky empty costs up to 200 points.

## What your agent gets

**Once, at the start (\`initialize\`):**
- the site, the list of nights and when each night starts and ends;
- every target: position, class, brightness, weight and whether it is required;
- the sky regions, the instrument layout and the full score settings;
- the time limit.

**At every decision (\`decision_request\`):**
- the current time;
- the latest bulletin and forecast, and all messages since your last decision;
- the result of your last observation: which targets hit their fibre, and their scores;
- the time-limited observation requests in progress and how far along they are (\`active_requests\`);
- the time you have left.

## What your agent sends

One action per decision:

| Action | Meaning |
|---|---|
| \`observe\` | Point the telescope, put up to 16 targets on fibres, expose for 60–3600 s, and declare a program (DARK, BRIGHT or BACKUP). |
| \`wait\` | Let time pass: a number of seconds, or until a given time (for example the next night). |
| \`report\` | Say that the instrument is faulty now. Right: +100. After each correct report, wrong reports are free up to the card's configured allowance, then −150 each; consecutive report actions have a separate cap. |
| \`finish\` | End the survey now. |

## How the score works

- A target scores only if it falls in its assigned fibre's cell and stays at or above 30° altitude.
- Its score grows with brightness, exposure time and sky quality, up to a cap.
- A matching program adds 20% (DARK), 12% (BRIGHT) or 6% (BACKUP). A wrong program adds nothing.
- Only the best exposure of each target counts.
- Time-limited observation requests: complete enough of a request's targets inside its time window to earn its reward; a missed request costs nothing.
- Final score = sum of best scores − 50 × missing required targets − unevenness penalty ± reports + request rewards.

**Example.** A target has brightness 0.60 and weight 1.0. You expose it for 900 s. The sky quality is 0.75.
Its factor is 0.60 × 900 × 0.75 ÷ 450 = 0.90. You declared DARK and the sky was DARK, so the score is
1.0 × 0.90 × 1.20 = **1.08**. With a 300 s exposure the factor is only 0.30. A required target needs at
least 0.50, so it would still count as missing.

## Common mistakes

- Printing logs to stdout. Only JSON answers go to stdout. Logs go to stderr.
- Answering with the wrong \`decision_sequence\`, or adding unknown fields. The run stops with \`agent_error\`.
- Calling a language model on every decision. The time limit runs out long before the survey ends.
- Short exposures on faint targets. Exposures do not add up; only the best one counts.
- Pointing low in a direction a bulletin warns about.
- Reporting a fault after one bad exposure. Weather also lowers scores.

## Try it

Pack your whole agent project as a zip and upload it on the Participate page. Practice runs all practice cards α, β, γ and δ in the cloud, with the same 900 s limit. Daily limits are on the Rules page.

Practice scores do not decide awards.
`,"../content/taskcard.gamma.v4.zh.md":`# 任务卡 γ（gamma）：动荡之季

除了天气，最近的一部分数据还可能丢失一次。

## 一览

| | |
|---|---|
| 站点 | 智利帕拉纳尔（虚拟站点）。纬度 −24.62°，经度 −70.40°。 |
| 巡天时间 | 2026-10-09 至 2026-11-15，共 38 夜。太阳低于 −18° 时可以观测。 |
| 目标 | 天区共 1,980 平方度，分为 3 块，有 9,900 个目标。其中 495 个是必观测目标。 |
| 仪器 | 16 个光纤可指派方格，排成 4 × 4、无间隙。总面积 6.4 平方度，视场宽约 2.53°。 |
| 时间限制 | 整个巡天最多用 900 秒真实时间。 |
| 天气 | 不公开。运行中智能体会收到每 15 分钟一条的简报和大约每周一次的预报。 |
| 额外消息 | 限时观测请求（\`observation_request\`）及其结果（\`observation_request_result\`）。另外可能收到一条 \`state_resync\` 消息。它表示最近的一部分数据丢失了。消息里列出仍然有效的目标和各自的最好得分。请据此重建"已完成目标"列表。已经用掉的时间不会退回。 |

## 你的目标

1. 尽量多观测有价值的目标，并且观测得好。
2. 每个**必观测**目标都要观测到位。漏掉一个扣 50 分。
3. 观测要覆盖整片天区。某些区域空着，最多扣 200 分。

## 智能体收到什么

**开始时一次（\`initialize\`）：**
- 站点、每一夜的列表，以及每夜的开始和结束时间；
- 全部目标：位置、类别、亮度、权重、是否必观测；
- 天区范围、仪器布局和完整的计分参数；
- 时间限制。

**每次决策时（\`decision_request\`）：**
- 当前时间；
- 最新的简报和预报，以及上次决策之后的所有消息；
- 上一次观测的结果：哪些目标落在了分配的光纤上，各得多少分；
- 进行中的限时观测请求及其进度（\`active_requests\`）；
- 剩余时间。

## 智能体发送什么

每次决策发送一个动作：

| 动作 | 含义 |
|---|---|
| \`observe\` | 指向天空某处，给最多 16 根光纤各分配一个目标，曝光 60–3600 秒，并声明一个观测程序（DARK、BRIGHT 或 BACKUP）。 |
| \`wait\` | 等待：等若干秒，或等到某个时刻（例如下一夜开始）。 |
| \`report\` | 报告仪器现在有故障。报对 +100；每次正确举报后，误报在任务卡配置的免罚次数内不扣分，之后每次 −150。连续提交 \`report\` 另有次数上限。 |
| \`finish\` | 立即结束巡天。 |

## 怎么计分

- 目标必须落在分配给它的那根光纤的可指派方格内，并且全程不低于 30° 高度角，才能得分。
- 目标越亮、曝光越长、天空越好，得分越高，但有上限。
- 程序声明正确时加分：DARK 加 20%，BRIGHT 加 12%，BACKUP 加 6%。声明错误不加分。
- 每个目标只算它最好的一次曝光。
- 限时观测请求：在请求的时间窗内完成足够多的指定目标即获得请求奖励，未完成不扣分。
- 最终得分 = 各目标最好得分之和 − 50 × 漏掉的必观测目标数 − 不均匀扣分 ± 故障报告得失 + 观测请求奖励。

**例子。** 某目标亮度 0.60，权重 1.0。你曝光 900 秒。天空质量是 0.75。
它的系数是 0.60 × 900 × 0.75 ÷ 450 = 0.90。你声明 DARK，天空也是 DARK，得分是
1.0 × 0.90 × 1.20 = **1.08**。如果只曝光 300 秒，系数只有 0.30。必观测目标至少要 0.50，
所以它仍然算作漏掉。

## 常见错误

- 把日志打印到标准输出。标准输出只能写 JSON 回复，日志写到标准错误。
- \`decision_sequence\` 填错，或者加了未知字段。运行会以 \`agent_error\` 结束。
- 每次决策都调用大模型。时间限制会在巡天结束前用完。
- 对暗目标用短曝光。多次曝光不会累加，只算最好的一次。
- 在简报警告的方向上指向低仰角。
- 一次曝光变差就报告故障。天气也会让分数变低。

## 动手试试

把整个智能体项目打包成 zip，在「参赛」页上传。练习赛会在云端运行全部练习卡 α、β、γ、δ，时间限制同样是 900 秒。每日次数见规则页。

练习赛成绩只用于练习，不决定奖项。
`}),f=s(Object.keys(d));function p(e,t){return r.includes(e)?d[`../content/taskcard.${e.id}.v4.${t}.md`]??null:null}function m(e,t){return l(p(e,t),e)}async function h(t){return(await Promise.all(a.map(async n=>{let{data:r,error:i}=await e.storage.from(`scenarios`).list(`${t.slug}/${n}`,{limit:1e3});return i||!r?[]:r.filter(e=>e.id||e.metadata).map(e=>`${n}/${e.name}`)}))).flat().filter(e=>u(t,e)).sort()}async function g(t,n,r){let i=n===`zh`?`en`:`zh`,a=p(t,n)??p(t,i);if(a)return a;let s=r??await h(t);for(let r of[n,i]){let n=o(r);if(!s.includes(n))continue;let{data:i}=await e.storage.from(`scenarios`).download(`${t.slug}/${n}`);if(i)return i.text()}return null}async function _(r,i){let a={};for(let t of i){let n=u(r,t);if(!n)continue;let{data:i,error:o}=await e.storage.from(`scenarios`).download(`${r.slug}/${t}`);if(o||!i)throw o??Error(`download_failed`);a[n]=new Uint8Array(await i.arrayBuffer())}if(!Object.keys(a).length)throw Error(`no_files`);let o=t(a,{level:6});n(new Blob([o],{type:`application/zip`}),`taskcard-${r.id}.zip`)}export{h as a,f as i,g as n,i as o,_ as r,c as s,m as t};