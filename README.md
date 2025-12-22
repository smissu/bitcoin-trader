# Bitcoin Trader — Gap Monitor 📥

Main app: `bitcoin-trader.py` (gap monitoring strategy). This repository contains two primary components:

- **`bitcoin-trader.py`** — the gap monitoring strategy that uses Pionex bar data, detects gaps, sends Discord alerts, and records gaps to `gaps/gaps.csv`.
- **`pionex_downloader.py`** — helper utility that fetches OHLCV Bars from Pionex and saves CSV files (used by the strategy).

The project fetches OHLCV Bars (candles) and supports multiple timeframes in scheduled mode:

- 1-hour bars (`60M`) — downloaded every hour
- 4-hour bars (`4H`) — downloaded every 4 hours
- Daily bars (`1D`) — downloaded once per day

---

## ✅ Features

- Download latest Bars for configurable timeframes
- Scheduled mode to automatically fetch at the correct times
- Historical mode to fetch multiple days of data (request batching)
- Safe CSV saving with de-duplication and append
- Logging to `pionex_downloader.log`

---

## 🔧 Requirements

- Python 3.11 (conda environment recommended)
- Packages: `requests`, `pandas`, `schedule`
- `tmux` (optional but *recommended* for running the scheduler in a managed session) — install via Homebrew:

```bash
brew install tmux
```

You can install Python dependencies with pip:

```bash
pip install requests pandas schedule
```

Or use your existing `conda` environment (this project was tested in `bitcoin-trader` conda env).

---

## ⚙️ Files

- `pionex_downloader.py` — main app
- `data/` — CSV files are stored here (e.g. `btc_usdt_4h_pionex.csv`)
- `pionex_downloader.log` — application log

---

## 🚀 Usage

Basic usage examples:

- Run scheduler (continuous):

```bash
python pionex_downloader.py --mode schedule
```

- Download historical data (e.g., last 365 days):

```bash
python pionex_downloader.py --mode historical --days 365 --timeframes 4H
```

- Download once and exit (good for testing):

```bash
python pionex_downloader.py --mode once --timeframes 60M 4H 1D --symbol BTC_USDT
```

Options:
- `--symbol` default: `BTC_USDT`
- `--timeframes` default: `60M 4H 1D` (accepted formats: `60M`, `4H`, `1D`, also `1h`, `daily` map internally)
- `--data-dir` default: `data`

---

## ▶️ Running the strategy (tmux recommended)

This repository's main runtime is the gap monitor app `bitcoin-trader.py`. The recommended way to run the scheduler on a machine you control is under `tmux` so you can detach/reattach and inspect logs.

**Start the monitor (recommended, tmux):**

```bash
# Start attached (shows output immediately) — preferred for debugging:
# (uses `conda run -n bitcoin-trader` so the conda env is activated reliably in non-interactive shells)

tmux new -s btc-trader bash -lc "conda run -n bitcoin-trader --no-capture-output python /Users/ericsmith/Documents/bitcoin-trader/bitcoin-trader.py"

# Or start detached and attach later (log to file):

tmux new -d -s btc-trader bash -lc "conda run -n bitcoin-trader --no-capture-output python /Users/ericsmith/Documents/bitcoin-trader/bitcoin-trader.py >> /Users/ericsmith/Documents/bitcoin-trader/trader_run.log 2>&1"

# Attach to the session to view output live
tmux attach -t btc-trader

### Detach a tmux session from another terminal 🔧
If you need to detach an attached tmux client from a different terminal (for example, to take over the session or stop an attached user), use the following commands from *another* terminal window:

- List active sessions:

```bash
tmux ls
```

- List clients (shows attached terminals):

```bash
tmux list-clients
```

- Detach *all* clients from a session (non-destructive):

```bash
tmux detach-client -a -s btc-trader
# shorthand: tmux detach -a -s btc-trader
```

- Detach a *specific* client (use the client name from `tmux list-clients`):

```bash
tmux detach-client -t <client-name>
```

- If you want to stop the session entirely (destructive):

```bash
tmux kill-session -t btc-trader
```

Note: run these commands as the same user that owns the tmux server, or point at the correct socket with `-S /path/to/socket` if necessary.
```

**Optional helper: start script**

A convenience script `scripts/start_btc_trader.sh` is included to simplify starting the monitor under tmux. It supports attached and detached modes, custom session names, and log redirection.

Usage examples:

```bash
# start attached (interactive)
./scripts/start_btc_trader.sh

# start detached and log to ./trader_run.log
./scripts/start_btc_trader.sh -d

# start detached with a custom session name and log file
./scripts/start_btc_trader.sh -d -s my-session -l /path/to/my_trader.log

# start detached and override the number of recent bars used in summary messages
./scripts/start_btc_trader.sh -d -r 30  # pass --recent-bars 30 to the strategy

# start detached and force display timezone used in messages (e.g. Europe/Berlin or UTC+1)
./scripts/start_btc_trader.sh -d -z Europe/Berlin  # messages will show local times in Europe/Berlin (CET/CEST)

# show local-time-only format (omit the UTC part):
./scripts/start_btc_trader.sh -d -z Europe/Berlin -f local  # messages show local times only (e.g., @19DEC25 - 09:00 CET)
```

Note: when the app performs its initial pass on startup it prints already-closed gaps to the terminal and logs them instead of sending Discord notifications (this prevents a flood of "Gap closed" Discord messages at startup). If you prefer the old behavior, scheduled closures still send Discord messages as before. The default summary window uses the last **20** bars; override this with `--recent-bars` on the command line or by passing `recent_bars` when creating `GapStrategy`. The default detector mode is now **b2dir** (this treats a mid-bar directional move as a gap when the next bar does not intersect the prior bar). Override with `--detector-mode` if needed.

Note: `Gap found` messages now include timestamps, for example: `Gap found G00073 60M up 88658.22 - 88712.11 @21DEC25 - 13:00:00 UTC (14:00 CET)`. Messages show the gap's start bar time in **UTC** and also include your local timezone (so they match chart labels shown in your trading client). If you run the app in a different timezone, the parenthesized local time will reflect the system local timezone.
**Alternative: nohup (simple background):**

```bash
nohup conda run -n bitcoin-trader python $(pwd)/bitcoin-trader.py --mode schedule > trader_run.log 2>&1 &
echo $! > trader.pid
tail -f trader_run.log
```

**Quick local test (run once):**

```bash
# run once with default settings (default recent_bars: 20)
conda run -n bitcoin-trader python bitcoin-trader.py --mode once --timeframes 60M 4H 1D

# or override the recent bars window used in summary messages:
conda run -n bitcoin-trader python bitcoin-trader.py --mode once --timeframes 60M 4H 1D --recent-bars 30
```
**Monitoring helpers:**

- `scripts/monitor_logs.py` — watches `trader_run.log` for ERROR/Exception/Gap events and writes a short `monitor_report.log` (runs 30 minutes by default).
- `scripts/live_test_session.py` — runs a short monitored live test and sends start/stop Discord messages.

**Find & report gaps script:**

You can run the helper script `scripts/find_and_report_gaps.py` to scan recent bars for gaps, record any unrecorded gaps to `gaps/gaps.csv`, and send detailed Discord messages for newly found gaps.

Preferred test usage (dry-run):

```bash
# Preferred command for testing: preview found gaps without recording/sending
conda run -n bitcoin-trader python scripts/find_and_report_gaps.py -t 60M -m b2dir -d --download-limit 48 --dry-run
```

Example (scan 60M, use the `b2dir` detector, and download latest bars first):

```bash
# Scan hourly bars (60M) using the b2dir detection mode and fetch the latest 48 bars before scanning
conda run -n bitcoin-trader python scripts/find_and_report_gaps.py -t 60M -m b2dir -d --download-limit 48
```

Flags:
- `-t, --timeframes` — comma-separated list of timeframes to scan (default: `60M`).
- `-m, --mode` — detection mode (`strict`, `body`, `open`, `b2dir`). If omitted, the module's default detector is used.
- `-d, --download-latest` — if provided, the script downloads the latest bars for each timeframe before scanning.
- `--download-limit` — how many latest bars to fetch when `--download-latest` is used (default: 48).
- `--dry-run` — preview found gaps; do not record to CSV or send Discord messages.
- `--verbose` — when used, prints the 3-bar window for each candidate gap and the detector output (helpful for debugging).
- `--output-file` — append verbose/dry-run output to a specified file for later analysis.

The script is useful for one-off scans or cron-style runs and can be added to scheduled workflows or run locally to capture and alert on recent gaps.

Short note — running from tmux or cron:

- tmux (detached):

```bash
# start a detached session that runs the scan and logs output
tmux new -s gap-scan -d "conda run -n bitcoin-trader python $(pwd)/scripts/find_and_report_gaps.py -t 60M -m b2dir -d --download-limit 48 > find_gaps.log 2>&1"
```

- cron (example, run daily at 02:10 UTC):

```cron
10 2 * * * cd /path/to/bitcoin-trader && /usr/bin/conda run -n bitcoin-trader python scripts/find_and_report_gaps.py -t 60M -m b2dir -d --download-limit 48 >> /path/to/find_gaps.log 2>&1
```

Notes:
- Use absolute paths in cron entries and ensure the `conda run` path is correct for your system.
- Redirect output to a log file and manage log rotation (e.g., `logrotate`) to avoid unbounded growth.

---

## ⏰ Scheduling details

The scheduler is configured to run at sensible times (UTC-style behavior):

- `60M` (hourly): runs at `:01` every hour
- `4H` (four-hour): runs at `00:05, 04:05, 08:05, 12:05, 16:05, 20:05`
- `1D` (daily): runs at `00:10` daily

You can run the script under `tmux`, `screen`, or as a system service (systemd/launchd) to keep it running.

---

## 📁 Output format

CSV files are saved to the `--data-dir` with names like:

```
{symbol_lowercase}_{interval_lowercase}_pionex.csv
# e.g. data/btc_usdt_4h_pionex.csv
```

Each file contains timestamped OHLCV rows with the Pionex-provided `time` (converted to datetime index).

---

## ⚠️ Notes & Troubleshooting

- Market data (`/api/v1/market/klines`) is public — no API key required.
- For very large historical downloads, the API limits the number of records per request (default/limit up to 500). Use `--mode historical` and the `--days` option to batch requests.
- Check `pionex_downloader.log` for detailed error messages if a download fails.
- If you need a different timezone interpretation, convert timestamps when loading the CSV into your analysis pipeline.

---

## ✨ Tips

- To run in background on macOS: use `tmux`/`screen` or create a `launchd` job.
- To integrate into backtesting: point your backtest scripts at the CSV files inside `data/`.

---

If you'd like, I can also add a `requirements.txt`, a `systemd`/`launchd` service example, or a small wrapper to rotate/compact data files — tell me which one and I'll add it. ✅
