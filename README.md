# 期货席位 Alpha Skill

**简体中文** | [English](README.en.md)

> 前 20 席位净持仓、净保证金集中度、家人席位反向、家人/主力分歧——四个公开口径因子，等权合成后到底能不能打过简单 CTA？答案写在结果里。

<p align="center">
  <img alt="factors" src="https://img.shields.io/badge/factors-F1%20%7C%20F5%20%7C%20F6%20%7C%20F8-blue">
  <img alt="data source" src="https://img.shields.io/badge/data-PandaData-ff69b4">
  <img alt="alpha" src="https://img.shields.io/badge/Alpha-Q4-7c3aed">
</p>

---

## 这是什么

`seat-alpha` 是一个 **Alpha 因子技能**（Q4）：按公开仓库口径计算四个期货席位因子，等权合成后与冻结 CTA、期限结构 carry 对照，并做未来函数、样本外、过拟合与发布时间敏感性检查。

## 因子口径

| 因子 | 定义 | 处理 |
|---|---|---|
| F1 席位变化 | 前 20 多头合计变化率 − 空头合计变化率（净持仓） | 日频原值，截面 z |
| F5 会员持仓集中度 | `bear_ratio − bull_ratio` | 逐品种 60 日时序 z |
| F6 家人席位反向 | `−(家人席位净保证金合计 / 总保证金)` | 截面 rank → [-1,1] |
| F8 家人/主力分歧 | `(major_ratio − family_ratio) × 一致性强度` | 截面 rank → [-1,1] |

合成：四因子逐日截面 z 后等权 0.25，不加权优化。

## 回测结果（2021-01-25 至 2025-12-31）

| 策略 | 累计收益 | 年化 | 年化波动 | Sharpe | 最大回撤 | 周频 IC |
|---|---:|---:|---:|---:|---:|---:|
| 四因子等权合成 | -42.19% | -10.81% | 25.82% | -0.419 | -68.84% | 0.0208 |
| 简单 CTA（Q2 冻结） | 6.26% | 1.28% | 11.21% | 0.114 | -22.19% | — |
| 期限结构 carry | -64.15% | -19.28% | 30.43% | -0.634 | -77.35% | -0.0310 |
| F8 单因子 | 97.50% | 15.27% | 29.00% | 0.527 | -50.04% | 0.0407 |
| F6 单因子 | 47.49% | 8.45% | 25.10% | 0.337 | -38.73% | 0.0111 |
| F1 单因子 | -38.87% | -9.76% | 22.62% | -0.432 | -54.87% | -0.0053 |
| F5 单因子 | -77.02% | -26.43% | 21.31% | -1.240 | -79.31% | -0.0381 |

**核心结论：严格净保证金口径下，四因子等权合成没有增量价值**；只有 F8 单因子为正，但回撤仍达 -50%，且未做多因子稳健性检验。这是负结果，不是交易策略。

## 快速开始

```bash
pip install -r requirements.txt

# 方式一：本地 parquet（seat_rank.parquet / net_margin.parquet）
python scripts/factor.py --data-dir /path/to/q4_data
python scripts/backtest.py --data-dir /path/to/q4_data

# 方式二：PandaData 现拉
export PANDA_DATA_USERNAME=your_phone
export PANDA_DATA_PASSWORD=your_password
export PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com
python scripts/factor.py
```

### Python 调用

```python
from scripts.factor import run as compute_factors
from scripts.backtest import run as run_backtest
from scripts.data import load_local, load_baseline

seat, nm = load_local("/path/to/q4_data")
panel = compute_factors({"seat_rank": seat, "net_margin": nm})
result = run_backtest({"panel": panel, **load_baseline()})
print(result["metrics"])
```

## 因子验真

```bash
python scripts/validate.py --data-dir /path/to/q4_data
```

检查项：

- **未来函数**：截断到样本日重算，因子值与全样本完全一致
- **样本外**：2021–2023 与 2024–2025 分开报告
- **过拟合**：合成权重固定 0.25，与单因子对照
- **生产文件**：主键唯一、字段完整、信号枚举合法

## 目录结构

```
skill-q4-seat-alpha/
├── SKILL.md
├── skill.json
├── scripts/
│   ├── factor.py             # 因子计算（run / validate_input）
│   ├── backtest.py           # 周频多空回测 + IC
│   ├── validate.py           # 未来函数 / 样本外 / 过拟合
│   ├── production.py         # 生产 parquet
│   ├── data.py               # PandaData / 本地数据 / 基线
│   ├── prepare_baseline.py   # 从 Q2 固化基线
│   └── test.py
├── tests/
│   ├── make_fixtures.py
│   └── fixtures/             # 真实数据切片（RB/HC 2022）
├── references/
│   ├── data_guide.md
│   └── baseline/             # 冻结 CTA 收益 / 信号 / carry
├── agents/
├── 生产产物/
│   ├── SKILL.md
│   └── 数据库.parquet
└── README.md / README.en.md / INSTALL.md / LICENSE / requirements.txt
```

## 生产字段

| 字段 | 说明 |
|---|---|
| `trade_date` | 交易日 |
| `asset_type` | `future` |
| `symbol` | 品种代码 |
| `factor_id` | `Q4` |
| `factor_name` | `seat_ensemble` |
| `factor_value` | 合成因子值 |
| `score` | 截面分位（0–100） |
| `rank` | 截面排名（1 为最高） |
| `signal` | `buy` / `hold` / `sell` |
| `confidence` | 信号强度（0–1） |
| `data_version` | 数据版本 |
| `update_time` | 生成时间 |

## 数据来源与口径

- 席位净持仓榜：`get_future_netposi_rank`，前 20 名、日频
- 席位净保证金：`get_broker_netmarg`，按席位日频
- CTA 基线：Q2 冻结信号与实合约盈亏（2021-01-04 至 2025-12-31）
- 执行：周末定信号、下一交易日开盘、双边 1.5bp
- 不使用净持仓榜替代净保证金：两者会改变结论

## 局限

- 合成因子整体为负；F8 单因子正收益伴随 -50% 回撤，不能据此说“席位信号可交易”
- 家人/主力席位名单沿用公开仓库，名单变化会改变结果
- 未做容量、冲击成本、保证金约束建模
- 研究用途，不构成投资建议

## ⚠️ 免责声明

- 本项目仅供研究与教育用途，**不构成任何投资建议**，不承诺收益。
- 回测结果基于历史数据与明确假设，未来表现可能显著不同。
- 本项目是 QuantSkills 社区项目，**非 PandaAI 官方背书**，也不代表任何机构认证。
- 使用前请自行核对数据、参数、成本与风险边界。

## 许可证

GNU General Public License v3.0，见 [LICENSE](LICENSE)。
