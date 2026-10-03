# v4 公开环境与练习榜快照

记录时间：北京时间 2026-10-02 21:15。官方仓库固定为 `18be105bc517938c8341ad79646cf397e3293016`。精确时间见机器清单。

已按主 Agent 在成绩揭示前预注册的独立 seed 方案，用未改官方生成器完成 **3 个完整本地研究卡**。开发为 demo+dev-season，保留为 holdout-season+holdout-stress。各卡文件完整、公开 schema 与规模验证通过，bundle 散列互异，官方生成器和参考配置前后散列一致。没有运行新卡策略或基线，没有解析 truth 内容用于分析。

官方公开卡 α、β、γ 的完整文件仍未取得。公开描述显示四卡校验和不同，但描述与校验和不替代实际下载和文件校验。独立合成研究卡与官方练习卡分开标识。

## Public source

官方站点入口为 [资源页](https://create.gosim.org/survey26/platform/resources)、[任务卡页](https://create.gosim.org/survey26/platform/cards) 和 [排行榜](https://create.gosim.org/survey26/platform/leaderboard)。匿名访问可取得站点 HTML 和前端静态脚本。入口证据保存在 `data/public-source/leaderboard-index.html`；它引用 `supabase-HbgHf8cp.js`，其中公开站点使用的 Supabase 主机为 `https://vdiemcofukuxglqsmlyz.supabase.co`。本次只使用该前端内公开的 anon 权限，不使用账号、用户 session、服务端凭据或隐藏卡入口。

固定仓库 `web/src/lib/taskCards.ts` 明确列出练习卡 `v4-practice-alpha/beta/gamma/delta`，`taskCardSource.ts` 规定对这四卡分别列出 `config/public/truth` 文件夹，再逐个下载。`scripts/build-v4-practice-cards.py` 说明真实练习卡由组织者秘密 seed 生成，完整 bundle 发布在 `scenarios` 桶，仓库只保留公开事实与 bundle 校验和。该信息与本地 `starter_kit_v4/cards/demo` 区分清楚：demo 为 7 夜、2,400 目标，公开固定 seed 为 5021。

## Download checkpoint

`POST /storage/v1/object/list/scenarios` 的已知练习卡路径连续返回 HTTP 544，正文为 `DatabaseTimeout / The connection to the database timed out`。α 的固定已知对象路径 `GET /storage/v1/object/scenarios/v4-practice-alpha/config/v4_scenario.json` 又返回 HTTP 429，正文为 `too_many_connections / Too many connections issued to the database`。因此已停止重复 listing。错误证据在 `data/api-snapshots/*listing.json`、`single-alpha-config.json`。这些都是服务端返回，不是把 403/404 误判为公开文件缺失。

以下仅为固定官方快照的公开事实，尚未用实际 bundle 核验：

| 卡片 | 夜数 | 目标 | 必观测 | 面积 deg² | 时段 | Stress | Bundle 校验和前缀 |
|---|---:|---:|---:|---:|---|---|---|
| α | 38 | 10,000 | 500 | 2,000 | 10-04 至 11-10 | 否 | `5455aaaf048d` |
| β | 38 | 9,600 | 480 | 1,920 | 10-18 至 11-24 | 否 | `29d6245f65e9` |
| γ | 38 | 9,900 | 495 | 1,980 | 10-09 至 11-15 | 是 | `df414b2818c1` |
| δ | 38 | 9,400 | 564 | 1,880 | 10-24 至 11-30 | 是 | `f1bfbd194276` |

四卡公开描述均为帕拉纳尔虚拟站点，3 块天区，16 根光纤，4×4 无间隙，每格 0.4 deg²，总视场 6.4 deg²；曝光范围 60–3600 秒，每卡总真实时长 900 秒。完整事实、源文件 SHA-256 与 demo 文件清单保存在 `data/inventory.json`。truth 文件只允许下载及散列计算，不用于内容分析。

公开卡方案因后台故障未能落地；主 Agent 已明确替换为下面的本地研究卡预注册方案。失败时的原始清单在 `data/inventory-public-discovery.json`。当前权威清单为 `data/inventory.json`，明确 `independent_complete_new_bundles_verified=3`。

## Leaderboard checkpoint

排行榜网页的标题、导航和页脚渲染成功，正文未渲染，未见任何分数行。公开前端的 `current_competition` 与旧练习榜 RPC 有界探测没有取得有效响应，其中当前阶段请求两次各 25 秒读超时。没有获得有效 v4 榜或 v3 榜 payload，因此两者的可见队数、中位数、最低和最高分均为**无法核实**；不能记为 0，也不能称为空榜。

机器快照在 `data/leaderboard.json`，CSV 仅有表头；JSON 的 `status=unavailable_not_verified_empty` 明确说明失败口径。当前证据不足以声明 v4 练习榜只有 v3 成绩，或声明没有参赛队。

固定源码的榜单口径需在日后成功取数时继续保留：v4 `observer_card_board` 从每队完整评估中选**整体均分最高的一次批次**；每卡榜使用该同一批次的对应卡成绩，不是每卡各自历史最高。overall 为该批次多卡平均。v3 `leaderboard` 的每场景榜则选每队该场景最高分。中位数应在每队入榜一条成绩上计算，并注明公开匿名榜、500 条请求上限、抓取日期；它不是所有提交的分布。依据为 `web/src/lib/cardBoard.ts` 与 `supabase/migrations/20260928004100_card_boards.sql`、`20260924000400_leaderboard_by_scenario.sql`，不把源码契约当成已核实的线上分数。

## Registered local cards

实际使用官方 `challenge/v4_bundle.py::build_card_bundle(root, spec)`。它使用标准库、固定官方 reference 配置和 `sha256-v1` 分流 seed；生成前做跨配置校验，输出目录必须不存在。普通卡生成 3 个 config、5 个 public、5 个 truth 文件；stress 卡再增加 `v4_stress_events.csv`。官方 `tests/v4_support.py` 和 `tests/test_v4_practice_cards.py` 也使用此入口。执行命令为 `/usr/bin/python3 experiments/v4/data/generate_registered.py`，退出码 0。

生成前保存的权威选择为 `data/generated-cards-plan.json`。主 Agent 固定开发 seed `2026100201`、常规保留 seed `2026100202`、stress 保留 seed `2026100203`，均为 4,800 目标、1,600 deg²、900 秒、默认 16 光纤；普通卡从 10-01 到 10-15，stress 从 10-15 到 10-29，生成器结束日期为排他边界。没有重抽 seed 或修改默认计分参数。早先未执行的 38 夜方案仅保留为历史草案 `generated-alternative-plan.json`，不构成实验配置。

| 本地研究卡 | 分组 | 实际夜间日期 | 夜数 | 目标 / 必观测 | 区域数 | 文件数 | 字节数 | Bundle SHA-256 前缀 |
|---|---|---|---:|---:|---:|---:|---:|---|
| dev-season | 开发 | 10-01 至 10-14 | 14 | 4800 / 240 | 2 | 13 | 499720 | `de2b0d8800dd` |
| holdout-season | 最终保留 | 10-01 至 10-14 | 14 | 4800 / 240 | 2 | 13 | 511217 | `46b6ff33fe69` |
| holdout-stress | 最终保留 | 10-15 至 10-28 | 14 | 4800 / 240 | 2 | 14 | 501095 | `c280b9293efb` |

文件位于 `data/cards/<card-id>/`。各卡机器清单为 `data/<card-id>-inventory.json`，保存每个文件字节数与 SHA-256。主清单与 `data/generation-record.json` 保存生成前计划散列、Python 版本、实际命令、耗时和官方源文件/参考配置前后散列；后者验证全部一致。`data/HOLDOUT_SEAL.json` 在首次跑分前固定两个保留卡的全文件散列和禁止调参使用的边界。

该简便入口在面积小于 3,000 deg² 时固定生成 **2 块**天区，使用公开模板默认中心，官方练习卡为 **3 块**；日期和规模也不同。因此这些卡可用于官方引擎上的独立合成数据实验，不能代表精确的线上练习卡复现。生成无需改动中心或其他可观测性参数；默认 reference 配置的站点名称为 `VISTA/Paranal (4MOST)`，经纬度与虚拟帕拉纳尔一致。这是生成器默认内容，不构成现实仪器一致性的声明。

`data/collect_public.py` 保存公开数据采集程序。后台恢复后可继续使用；当前失败的 API 原始证据应保留，不覆盖成“空结果”。
