# Sprint: Trading - gap-entry strategy (paper first)

Goal: Implement a paper-trading workflow for gap-entry strategies: place buy-stop at gap upper edge for down gaps, consider fills on subsequent bars, close when gap filled.

Scope:
- Paper-only initial implementation for safety.
- Order simulation, trade lifecycle (placed, filled, closed), and P&L recording in `trades/trades.csv`.
- Discord alerts for order placed/fill/close with P&L and timestamps.
- Configurable entry offset and stop loss.

Tasks:
1. Add `GapTrader` component for paper orders.
2. Integrate with `GapStrategy` to create paper orders when a gap is detected.
3. Add persistence and summary endpoints.
4. Add unit tests and a small simulation script to replay historical data.

Acceptance Criteria
- Paper trades are recorded and updated correctly with simulated fills.
- Discord messages are sent for simulated fills/close events.

Estimated effort: 1.5–2 days (paper only)
