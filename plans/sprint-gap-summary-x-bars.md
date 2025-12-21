# Sprint: Gap summary over last X bars and per-timeframe reporting

Goal: When data is downloaded/processed for a timeframe, review the last X bars (configurable; default 15) and send a Discord message summarizing how many gaps were found in that window and list the times they were found. Persist the gap history in `gaps/gaps.csv` (already contains timeframe and timestamps), and include per-timeframe counts.

Tasks:
1. Config option
   - Add `--recent-bars` CLI option / config value and default to 15. Expose as parameter to processing functions.
2. Implement summary function
   - Function `summarize_recent_gaps(timeframe, x=15)`:
     - Load recent price bars for timeframe (either from CSV for the timeframe or from the in-memory store), examine the last X bars using existing detection logic, and count gaps found.
     - Return structured summary: {count, gaps: [{id, found_time, type, low, high}, ...]}.
3. Persistence and history
   - Ensure gaps are appended to `gaps/gaps.csv` with timeframe field (already present).
   - Optionally add a compact per-timeframe summary file `gaps/summary_{timeframe}.csv` (timestamp, count).
4. Discord messaging
   - When `process_interval` runs for a timeframe, call `summarize_recent_gaps` and send a Discord message containing: timeframe, count of gaps in last X bars, and short list of found-times and types.
5. Unit tests
   - Test that summary returns correct counts and messages are formatted as expected.
6. Docs
   - Update README and plans to describe the feature and CLI option.

Acceptance criteria
- When timeframe data is downloaded, a message is sent with the last-X summary (count and timestamps).
- Gaps are persisted and queryable; unit tests cover the summary logic.

Estimated effort: 1 day development + tests
