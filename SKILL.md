---
name: seat-alpha
description: "Futures seat-position Alpha: computes F1 seat-change, F5 net-margin concentration, F6 family-seat reversal, and F8 family-vs-major divergence factors, then tests the equal-weight ensemble against a frozen CTA baseline with weekly signals, next-open execution, IC, and after-cost long-short returns. Use when an agent needs to build or audit futures seat factors, compare seat signals with CTA, check publication lag sensitivity, or reproduce the Q4 seat-signal study."
license: GPL-3.0-only
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-q4-seat-alpha
  repository_url: https://github.com/quantskills/skill-q4-seat-alpha
  project_type: skill
  collection: futures-seat-alpha
  creator: fuzijun
  maintainer: fuzijun
quantSkills:
  project_type: skill
  category: factor
  tags:
    - futures
    - seat-position
    - factor
    - alpha
    - pandadata
  platforms:
    - claude-code
    - codex
    - openclaw
    - cursor
  status: draft
  requires:
    - skill-pandadata-api
    - skill-q2-roll-cta
  validation_level: runnable
  maintainer_type: community
  summary_zh: "期货席位 Alpha：F1/F5/F6/F8 四因子与等权合成，校验未来函数、样本外与过拟合，并与冻结 CTA 做增量对照。"
  summary_en: "Futures seat Alpha: F1/F5/F6/F8 factors and an equal-weight ensemble, with look-ahead, out-of-sample, overfit checks and an incremental test against a frozen CTA baseline."
---

# 席位信号相对简单 CTA 是否有额外交易价值（净保证金严格口径）

Use this skill to compute futures seat-position factors and test whether they add value over a simple CTA baseline.

## 因子逻辑

| 因子 | 定义 | 处理 |
|---|---|---|
| F1 席位变化 | 前 20 多头合计变化率 − 空头合计变化率（净持仓） | 日频原值，截面 z |
| F5 会员持仓集中度 | `bear_ratio − bull_ratio`：前 5 空头保证金 / 总保证金 − 前 5 多头保证金 / 总保证金 | 逐品种 60 日时序 z |
| F6 家人席位反向 | `−(家人席位净保证金合计 / 总保证金)` | 逐日截面 rank 映射到 [-1,1] |
| F8 家人/主力分歧 | `(major_ratio − family_ratio) × 一致性强度`，分母含家人内部对冲调整 | 逐日截面 rank 映射到 [-1,1] |

合成：四因子逐日截面 z 后等权 0.25 相加，不做样本内权重优化。

- 家人席位：东方财富、徽商期货、平安期货
- 主力席位：永安期货、中信期货、国泰君安

## 输入数据

| 字段 | 类型 | 说明 |
|---|---|---|
| `seat_rank` | DataFrame | `get_future_netposi_rank`：date / underlying_symbol / broker_name / position_type / net_position / net_position_change / rank |
| `net_margin` | DataFrame | `get_broker_netmarg`：date / underlying_symbol / broker / net_margin |
| `cta_returns` | DataFrame | 冻结 CTA 逐日分品种盈亏（已归一为收益率）+ 组合 `ret` |
| `cta_signals` | DataFrame | 冻结信号（date / product / signal） |
| `carry` | DataFrame | 期限结构 carry（date / product / carry），可选 |

`cta_returns`、`cta_signals`、`carry` 随仓库携带（`references/baseline/`），来自 Q2 真实数据快照。

## 使用方式

```python
from scripts.factor import run as compute_factors
from scripts.backtest import run as run_backtest
from scripts.data import load_local, load_baseline

seat, nm = load_local("/path/to/q4_data")       # 或 data.fetch()
panel = compute_factors({"seat_rank": seat, "net_margin": nm})
result = run_backtest({"panel": panel, **load_baseline()})
print(result["metrics"])
```

命令行：

```bash
python scripts/factor.py --data-dir /path/to/q4_data
python scripts/backtest.py --data-dir /path/to/q4_data
python scripts/validate.py --data-dir /path/to/q4_data
python scripts/production.py --data-dir /path/to/q4_data
```

## 输出结果

- `factor.py`：date / product / f1 / f1_5d / f5 / f6 / f8 / seat 因子面板
- `backtest.py`：各策略收益、波动、Sharpe、最大回撤、IC 均值、换手，年度收益，相对 CTA 的 beta/alpha/相关
- `validate.py`：未来函数、样本外、过拟合、生产文件四项 PASS/FAIL
- `production.py`：标准 Alpha Parquet（`生产产物/数据库.parquet`）

## 验收要求

- 因子计算只用当日及以前数据；截断样本重算结果必须完全一致
- 信号在周末定方向，下一交易日执行，不允许同日成交
- 样本外单独报告，不允许在全样本上调参
- 合成权重固定 0.25，不做样本内优化
- 生产文件主键唯一、字段完整、`signal` 使用标准枚举

## 数据来源

- PandaData：`get_future_netposi_rank`、`get_broker_netmarg`
- CTA 基线来自 Q2 真实数据快照（2021-01-04 至 2025-12-31）
- 不使用随机数、模拟持仓或模拟价格

## 生产产物

- `生产产物/数据库.parquet`：逐日 × 品种的因子值与信号
- 字段与读取规则见 `生产产物/SKILL.md`

## 依赖

- pandas、numpy、scipy、pyarrow、panda_data
