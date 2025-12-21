# Sprint: Aggregate 1H → 4H / 1D

Goal: Implement local aggregation of 1H bars into 4H and 1D bars so the strategy can detect gaps on higher timeframes immediately after 1H bars arrive without making extra API calls.

Why: Faster gap detection on higher timeframes while minimizing API requests.

Tasks:
1. Design aggregation approach (handle boundaries, partial bars, timezone alignment). ✅
   - Define how to align 4H (windows starting at 00:00, 04:00, 08:00...) and 1D (calendar day, UTC by default).
2. Implement aggregator component
   - Add an in-memory store of recent 1H bars for each symbol (persist to disk optionally).
   - Provide functions: add_hourly_bar(bar), build_4h_from_1h(), build_1d_from_1h().
3. Integrate aggregator into `GapStrategy`
   - When a 1H bar is processed, aggregate to 4H/1D if the window completed and call process_interval('4H'/'1D') with the derived bar(s).
   - Ensure no duplicate gap alerts: check last processed higher-timeframe timestamp.
4. Unit tests
   - Add tests to verify aggregation correctness (edge cases: DST, time alignment, partial windows).
5. Docs & README
   - Add a short explanation to README about hourly aggregation option and behavior.
6. Performance & monitoring
   - Add logging when aggregation occurs; add tests for memory usage (basic).

Acceptance criteria
- Aggregator builds correct 4H / 1D bars from 1H input for multiple cases.
- No duplicate alerts when derived higher timeframe does not advance.
- Unit tests pass and new behavior documented.

Estimated effort: 1–2 days development + tests
