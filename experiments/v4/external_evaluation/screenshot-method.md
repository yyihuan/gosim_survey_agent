# Leaderboard screenshot evidence

这组数据来自用户提供的四张排行榜截图，拍摄时间未知。它们是截图快照，不是实时排行榜；本次整理没有抓取榜单、登录或上传。

原截图按用户给定顺序编号：第 1 张 α（alpha）、第 2 张 β（beta）、第 3 张 δ（delta）、第 4 张 γ（gamma）。原始文件复制到 [screenshots](./screenshots/)，复制前后 SHA256 一致。JSON 为每张图保留临时来源绝对路径、稳定截图路径和 SHA256；`capture_time` 为 `null`，`ingested_at` 仅表示整理时间。

![Screenshot evidence lineage](./screenshots/docs/diagrams/screenshot-evidence-lineage.svg)

## Transcription and precision

[CSV](./leaderboard-screenshots.csv) 是逐行人工核对的转录表，保留分数的两位小数字面值；[JSON](./leaderboard-screenshots.json) 是它的派生数据，供 HTML 读取。四张图均转录全部 8 队，共 32 行，包含负分。图像检查为转录依据，本地 OCR 只辅助核对，OCR 识别错误不覆盖图像中可见的值。

截图列与字段对应如下。

| 截图列 | 字段 | 含义 |
| --- | --- | --- |
| # | `rank` | 当前截图显示的排名 |
| 队伍／智能体 | `team_display` | 截图中的显示名称 |
| 总分 | `total` | 截图总分 |
| 最佳得分 | `science` | 截图所列最佳得分分项 |
| 必观测惩罚 | `required_penalty` | 保留原符号 |
| 报告结算 | `report` | 保留原显示值 |
| 均匀性惩罚 | `uniformity_penalty` | 保留原符号 |
| 限时观测请求 | `request` | 保留原显示值 |
| 观测目标 | `observed_targets` | 截图计数 |
| REQ 缺失 | `required_missing` | 截图计数 |
| 结果提交 | `submissions` | 截图计数 |

`team` 用作四卡关联键。β、γ 的 `cloudbrain` 名称前可见小点，`team_display` 分别保留 `.cloudbrain`；α、δ 为 `cloudbrain`。`team` 均记为 `cloudbrain`，只作关联，不改变分数。其他显示名称原样保留，包括 `Clarrycy`、`Nothern131` 的拼写。

每卡中位数按全部 8 个截图总分排序，用中间两个数的算术平均计算。所有计算使用 `Decimal`，最终显示两位小数并使用 `ROUND_HALF_UP`。因此 δ 的中间值平均为 `3069.515`，显示 `3069.52`；γ 为 `3753.005`，显示 `3753.01`。这些是截图舍入值的统计量，不是 API 精确原数。

总分与显示分项之和允许最多 `0.02` 差异；`total_minus_displayed_components` 保存该差值。实际有 4 行非零差异，最大绝对值为 `0.01`：β 第 4 行为 `-0.01`，δ 第 5 行为 `0.01`，γ 第 1、3 行均为 `0.01`。所有录入值均保持截图原值，没有为凑总分而修改分项。

## HTML data interface

JSON 顶层为 `source_type`、`capture_time`、`ingested_at` 和 `cards`。每卡包含 `source_number`、`card_id`、`label`、`name`、`source_path`、`screenshot_path`、`sha256`、`rows`、`summary` 和 `validation`。

`rows` 中分数为 JSON number，计数为 integer，显示时统一格式化到两位小数。`summary.median_total`、`top_total`、`min_total` 为已经按上述规则格式化的十进制字符串，可直接显示；`median_middle_totals` 保存参与平均的两个截图总分。不要用浏览器浮点运算重新舍入中位数。

`screenshot_path` 以工作区根目录为基准，JSON 的 `path_base` 为 `workspace_root`。HTML 在其他目录时需按其文件位置转换相对路径。展示名称优先使用 `team_display`，跨卡关联使用 `team`。截图出处和时间限制应随统计量一起展示。

| 卡片 | 行数 | 中位数 | 最高分 | 最低分 |
| --- | ---: | ---: | ---: | ---: |
| α | 8 | 3605.31 | 4907.42 | -25200.00 |
| β | 8 | 4029.90 | 5323.42 | -24200.00 |
| δ | 8 | 3069.52 | 4787.54 | -28400.00 |
| γ | 8 | 3753.01 | 4620.30 | -24950.00 |

本文件仅说明来源、转录、精度和接口，不对策略作总体分析。
