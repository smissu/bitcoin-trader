# Plan: Bitcoin gap monitor (PGs followed)

## Goals (PGs)
- Detect price gaps across timeframes (60M, 4H, 1D).
- Send Discord notifications when gaps are found and when they close.
- Record gaps to CSV and update status when closed.
- Run continuously until stopped by the user with graceful start/stop messages.
- Keep secrets out of git history; use environment variables for Discord webhook auth.

## Tasks
1. Implement core strategy file (`bitcoin-trader.py`) ✅
   - Uses `PionexDownloader.get_bars` to fetch last 3 bars.
   - Detect gap using 3-bar rule (b1/b2 overlap, b3 gap relative to b2).
   - Record gap with `GapManager` to `gaps/gaps.csv`.
   - Send Discord messages when gaps found.
   - Monitor open gaps on each new bar and send msg when closed.

2. Scheduling & continuous run ✅
   - Schedule checks per timeframe and initial boot pass.
   - Send start/stop Discord messages.

3. Hardening / follow-ups (not implemented yet)
   - Remove any sensitive values from repo history (if needed).
   - Add unit tests for gap detection logic.
   - Add a `--mode` (paper/live) and more robust configuration.
   - Add logging rotation and better error handling.
   - Add `gaps/*.example` template and README entry for `.env` usage.

## Acceptance criteria
- Strategy runs and detects gaps using the algorithm described above.
- Gaps are appended to `gaps/gaps.csv` and updated to `closed` when filled.
- Discord messages are sent for start/stop, gap found, gap closed.
- No secret tokens are written to git tracked files.

---

Notes: If you'd like different gap criteria (e.g., require X% size, or gaps measured on opens), tell me and I will update the detection function and add tests.
