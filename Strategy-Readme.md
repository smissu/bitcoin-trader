# Three-Bar Gap Strategy (ThreeBarGap) 🔍

## Overview

The Three-Bar Gap strategy detects a bullish gap pattern and attempts to trade the gap fill. It is implemented in Backtrader (`backtest-1.py`) and in a vectorized/local simulator (`vectorbt_backtest.py`).

---

## Pattern definition

- Bars used:
  - **bar1** = i-3 (three bars ago)
  - **bar3** = i-1 (one bar ago)
- Conditions (bullish signal):
  1. **bar1 is red**: close1 < open1
  2. **upside gap**: bar3.high < bar1.low AND bar3.close < bar1.low

When both conditions are true a signal is generated at the current bar (i).

---

## Entry / Exit rules

- **Entry**: Default is a Stop order placed at `bar3.high` (waits for a later bar to trigger). Optionally use `market_next` mode to enter at the next bar open (settable via `--market-next` or strategy param `use_market_entry`).
- **Take Profit (TP)**: `bar1.low` (fills the gap up to bar1 low)
- **Stop Loss (SL)**: `bar3.low` (below the most recent bar low)

On entry fill the strategy places a Limit exit (TP) and a Stop exit (SL).

---

## Implementation details

- **Backtrader file**: `backtesting/backtest-1.py`
  - Detection in `ThreeBarGapBTC.next()`
  - Order management in `notify_order()` / `notify_trade()`
  - Configurable params: `risk_pct` (stub) and `use_market_entry` (bool)
  - CSV input expects the cleaned file `btc_1h_yf_clean.csv` (mapping columns as in the file header comments)

- **Vectorized/local simulator**: `backtesting/vectorbt_backtest.py`
  - Function `run_sim()` scans the series and simulates stop and market-next semantics
  - Handles same-bar TP/SL hits with a proximity heuristic when both are hit in the same bar

---

## How to run

- Backtrader (hourly data, 4H compressed via `--compression`):

```bash
# run with default CSV and 1h compression
python backtesting/backtest-1.py --csv btc_1h_yf_clean.csv

# run with 4h compression and market-next entry
python backtesting/backtest-1.py --csv btc_1h_yf_clean.csv --compression 240 --market-next
```

- Vector-style simulator:

```bash
# run the vectorized/local simulator
python backtesting/vectorbt_backtest.py --csv btc_1h_yf_clean.csv
# use market-next semantics
python backtesting/vectorbt_backtest.py --market-next
```

---

## Notes, assumptions, and edge cases ⚠️

- The strategy requires at least **3 completed bars** before pattern detection (so detection happens on bar index i when bars at i-3..i are available).
- CSV date parsing expects `'%Y-%m-%d %H:%M:%S%z'` (see `backtest-1.py` dtformat).
- API/CSV data must be cleaned to match the expected column mapping (see `backtest-1.py` column mappings).
- When TP and SL are both hit on the same bar, the simulator resolves the outcome using a proximity heuristic (vectorbt implementation). Backtrader will resolve according to fills/orders and exchange simulation behavior.

---

## Testing suggestions ✅

- Add unit tests (pytest) that feed minimal synthetic bar sequences and assert:
  - Signals are only generated when both pattern conditions are met
  - Entry orders are created at the correct price type (Stop vs Market)
  - TP and SL behavior on single-bar and same-bar hit conditions

- Create small CSV fixtures covering positive and negative cases (gap present, no gap, same-bar both hit)

---

## Potential improvements / experiments 💡

- Parameterize criteria (e.g., require minimum gap size, or allow gap tolerance as fraction of bar range)
- Add logging/plotting of detected signals for visual verification (matplotlib/plotly)
- Add position sizing using `risk_pct` and account equity
- Build an automated parameter sweep (grid search) to find best TP/SL or filter thresholds

---

If you'd like, I can add unit tests and a small test dataset for this strategy next. Which would you prefer I do first? (Tests, visualization, or parameterization.)
