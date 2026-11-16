# Futures Seat-Position Alpha Skill

**English** | [简体中文](README.md)

> F1 seat change, F5 net-margin concentration, F6 family-seat reversal, and F8 family-vs-major divergence — four public seat factors, equal-weight ensemble, tested against a frozen CTA baseline.

<p align="center">
  <img alt="factors" src="https://img.shields.io/badge/factors-F1%20%7C%20F5%20%7C%20F6%20%7C%20F8-blue">
  <img alt="data source" src="https://img.shields.io/badge/data-PandaData-ff69b4">
  <img alt="alpha" src="https://img.shields.io/badge/Alpha-Q4-7c3aed">
</p>

---

## What it is

`seat-alpha` is an **Alpha factor skill** (Q4). It computes four futures seat factors under the strict net-margin convention, forms an equal-weight composite, and compares it with a frozen CTA and a term-structure carry baseline. It also ships look-ahead, out-of-sample, overfit, and publication-lag checks.

## Results (2021-01-25 to 2025-12-31)

| Strategy | Total | Annual | Vol | Sharpe | Max DD | Weekly IC |
|---|---:|---:|---:|---:|---:|---:|
| Four-factor ensemble | -42.19% | -10.81% | 25.82% | -0.419 | -68.84% | 0.0208 |
| Simple CTA (frozen Q2) | 6.26% | 1.28% | 11.21% | 0.114 | -22.19% | — |
| Term-structure carry | -64.15% | -19.28% | 30.43% | -0.634 | -77.35% | -0.0310 |
| F8 single | 97.50% | 15.27% | 29.00% | 0.527 | -50.04% | 0.0407 |
| F6 single | 47.49% | 8.45% | 25.10% | 0.337 | -38.73% | 0.0111 |

**Key finding: under the strict net-margin convention, the equal-weight ensemble adds no value over CTA.** Only F8 is positive, but with a -50% drawdown and no multi-factor robustness test. This is a negative research result, not a trading strategy.

## Quick start

```bash
pip install -r requirements.txt

python scripts/factor.py --data-dir /path/to/q4_data
python scripts/backtest.py --data-dir /path/to/q4_data
python scripts/validate.py --data-dir /path/to/q4_data
python scripts/production.py --data-dir /path/to/q4_data
```

## Data

- `get_future_netposi_rank`: top-20 seat net positions, daily
- `get_broker_netmarg`: seat-level net margin, daily
- CTA baseline: frozen Q2 signal and real-contract PnL snapshot
- Execution: weekly signal, next-open fill, 1.5 bp per side
- Never substitute net positions for net margin: the conclusion changes

## Limitations

- The ensemble is negative overall; F8's positive return comes with a -50% drawdown
- Family/major broker lists follow the public repository; list changes alter results
- No capacity, market-impact, or margin-constraint modeling
- Research and education only, not investment advice

## ⚠️ Disclaimer

- Research and education only. **Not investment advice.** No return is promised.
- Backtests rely on historical data and explicit assumptions; future results may differ materially.
- This is a QuantSkills community project, **not officially endorsed by PandaAI**.
- Verify data, parameters, costs, and risk boundaries before use.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
