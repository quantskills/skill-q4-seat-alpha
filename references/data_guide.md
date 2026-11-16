# Q4 数据说明

## 数据源

PandaData（PandaAI data 数据拉取库）：

```python
import panda_data
panda_data.init_token(
    username=os.environ["PANDA_DATA_USERNAME"],
    password=os.environ["PANDA_DATA_PASSWORD"],
    base_url=os.environ.get("PANDA_DATA_BASE_URL", "http://pandadata.pandaaiquant.com"),
)
```

## 额定接口

### get_future_netposi_rank

- 用途：前 20 席位净持仓榜
- 入参：`start_date`、`end_date`、`underlying_symbol`（list）、`max_rank`、`type`（`long` / `short`）
- 关键字段：`date`、`underlying_symbol`、`broker_name`、`position_type`、`net_position`、`net_position_change`、`rank`
- 拉取方式：按品种 × 多空 × 季度循环，单次失败重试 5 次

### get_broker_netmarg

- 用途：席位净保证金
- 入参：`start_date`、`end_date`、`broker`、`underlying_symbol`（list）
- 关键字段：`date`、`underlying_symbol`、`broker`、`net_margin`
- 拉取方式：按品种 × 年度循环

## 本地数据

`config["data_dir"]` 或 `--data-dir` 需包含：

| 文件 | 必需字段 |
|---|---|
| `seat_rank.parquet` | date, underlying_symbol, broker_name, position_type, net_position, net_position_change |
| `net_margin.parquet` | date, underlying_symbol, broker, net_margin |

## 冻结基线（随仓库携带）

`references/baseline/`：

| 文件 | 内容 | 来源 |
|---|---|---|
| `cta_returns.parquet` | date + 18 品种盈亏（按 100 万归一）+ 组合 ret | Q2 固定日期换月 |
| `cta_signals.parquet` | 冻结信号 date / product / signal | Q2 |
| `carry.parquet` | 期限结构 carry date / product / carry | Q2 全合约日线 |
| `margin.parquet` | 品种保证金率中位数 | Q2 合约信息 |

基线可用 `scripts/prepare_baseline.py <q2_project_dir>` 从 Q2 真实数据重新生成。

## 清洗口径

- `date` 统一为 `YYYYMMDD` 字符串
- 席位数据按 `(date, underlying_symbol, broker_name, position_type)` 去重
- 净保证金按 `(date, underlying_symbol, broker)` 去重
- `net_position` / `net_position_change` / `net_margin` 转数值，异常值保留为空并剔除
- 家人席位：东方财富、徽商期货、平安期货；主力席位：永安期货、中信期货、国泰君安
- 不使用净持仓榜替代净保证金；两者结论不同

## 调用限制

- 席位接口按季度循环，批次间 sleep，避免限流
- 失败重试 5 次；仍失败则抛异常，不静默返回空表
- 凭据只从环境变量读取，不落盘
