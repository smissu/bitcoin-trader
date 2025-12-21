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
# Start a detached tmux session named 'btc-trader'
# (requires tmux installed via Homebrew: `brew install tmux`)

tmux new -s btc-trader -d "conda run -n bitcoin-trader bash -lc 'python $(pwd)/bitcoin-trader.py --mode schedule > trader_run.log 2>&1'"

# Attach to the session to view output live
tmux attach -t btc-trader
```

**Alternative: nohup (simple background):**

```bash
nohup conda run -n bitcoin-trader python $(pwd)/bitcoin-trader.py --mode schedule > trader_run.log 2>&1 &
echo $! > trader.pid
tail -f trader_run.log
```

**Quick local test (run once):**

```bash
conda run -n bitcoin-trader python bitcoin-trader.py --mode once --timeframes 60M 4H 1D
```

**Monitoring helpers:**

- `scripts/monitor_logs.py` — watches `trader_run.log` for ERROR/Exception/Gap events and writes a short `monitor_report.log` (runs 30 minutes by default).
- `scripts/live_test_session.py` — runs a short monitored live test and sends start/stop Discord messages.

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
