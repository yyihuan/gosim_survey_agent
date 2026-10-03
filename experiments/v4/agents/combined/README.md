# Combined strategy interface

代码入口为 `source/baseline_agent.py`，通过统一harness运行。此次集成沿用已测家族的参数格式：TDG顶层参数、C/W对象、P环境预算；不增加字段翻译层。

| 家族 | 现有参数 | 全关中性值 |
| --- | --- | --- |
| T | strict_slot、exposure_cap_seconds、conditional_long_exposure | false、缺省/null、false |
| D | science_exponent | 2.0 |
| G | geometry_strength | 0.0 |
| C | C.enabled 与 C.strength | enabled=false |
| W | W.enabled 与原方向/高度/事件参数 | enabled=false |
| P | environment.PACKING_ANCHORS | "3"或缺省 |

P在combined中的缺省值为3，其他中性值沿用TDG与CW原实现。单开关配置可以直接使用原家族JSON，不需重新物化参数。主Agent已在首批组合运行前冻结DP、DG和DTconditional配置，保存于 `../../configs/combined/`；只执行这三种，各两开发卡。

![家族作用位置](./docs/diagrams/combined-policy-hooks.svg)

TDG源码作为独立复制底座；追加CW的消息/规划钩子和原样CWPolicy，并将P预算接入现有环境参数。原策略路径与评分器保持独立。输入源码树hash和集成说明见 `integration_manifest.json`，每run仍保存自己的不可变源码快照。

验证全关及六个单家族配置，每种开发卡与原run四份官方核心产物逐字节比较：

```bash
/usr/bin/python3 -B experiments/v4/agents/combined/verify_equivalence.py --execute
```

可用 `--case control` 等或 `--card demo` 限定检查。已有验证run不覆盖；源码或配置hash变化时拒绝把旧结果当当前证明。此验证包含T条件900、D指数1、G强度0.5、C强度0.6、W罚幅0.2和P锚点12，都是已测原配置，属于迁移验收而非新参数筛选。

等价性报告为 `validation/equivalence.json`。关闭因子均保留中性计算路径；在D/G/C/W共同启用时，候选收益按原TDG收益、原方向权重、G高度软权重、C/W乘数顺序相乘。T负责原曝光合法区间与门槛兜底，P负责锚点搜索预算。多家族的交互效果必须由冻结后实验回答，单开关一致不能证明多开关收益可加。
