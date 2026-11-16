---
name: seat-alpha-production
description: 生产环境的期货席位 Alpha 因子读取。从标准 Parquet 读取逐日 × 品种的因子值、评分、排名与信号，供交易/研究 agent 查询。
tags: [quant, alpha, production, futures, seat-position]
---

# 席位 Alpha（生产）

## 结果文件

`生产产物/数据库.parquet`

## 主键

- `trade_date`
- `symbol`
- `factor_id`

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `trade_date` | string | 交易日 YYYYMMDD |
| `asset_type` | string | `future` |
| `symbol` | string | 品种代码（RB / HC / …） |
| `factor_id` | string | `Q4` |
| `factor_name` | string | `seat_ensemble` |
| `factor_value` | float | 四因子等权合成值 |
| `score` | float | 截面分位（0–100） |
| `rank` | int | 截面排名（1 为最高） |
| `signal` | string | `buy` / `hold` / `sell` |
| `confidence` | float | 信号强度（0–1） |
| `data_version` | string | 数据版本 |
| `update_time` | string | 生成时间 |

## 读取规则

```python
import pandas as pd

df = pd.read_parquet("生产产物/数据库.parquet")
latest = df[df["trade_date"] == df["trade_date"].max()]
buys = latest[latest["signal"] == "buy"].sort_values("rank")
print(buys[["symbol", "factor_value", "score", "rank", "confidence"]])
```

1. 先按 `trade_date` 取最新有效交易日。
2. `rank` 为截面排名，1 为最高；`signal` 只按 Top/Bottom 3 生成。
3. `score` 是截面分位，不是收益预测。
4. 最新结果缺失时可回退最近有效交易日，但必须说明数据日期。
5. 不允许调用开发脚本临时重算替代生产结果。

## 禁止行为

- 不得把 `signal` 当作交易指令或收益承诺
- 不得修改 `factor_value` / `score` / `rank` 后回写
- 不得在缺少 `trade_date` / `symbol` / `factor_id` 时合并数据
