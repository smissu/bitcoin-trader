#!/usr/bin/env python3
"""Bitcoin gap monitoring strategy

Uses the Pionex downloader to fetch OHLCV bars and detect "gaps".
Sends Discord messages when gaps are found/closed and records gaps to CSV.
Runs continuously until stopped by the user.
"""

import logging
import time
import csv
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import schedule
from typing import Optional, List

from pionex_downloader import PionexDownloader
from discord.messages import send_msg

# Configure logging to both file and stdout
log_handlers = [
    logging.FileHandler('trader_run.log'),
    logging.StreamHandler()
]
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=log_handlers)
logger = logging.getLogger('bitcoin-trader')

GAPS_DIR = Path('gaps')
GAPS_DIR.mkdir(exist_ok=True)
GAPS_CSV = GAPS_DIR / 'gaps.csv'


@dataclass
class GapRecord:
    id: str
    timeframe: str
    start_time: str  # ISO
    gap_type: str  # 'up' or 'down'
    gap_low: float
    gap_high: float
    status: str  # 'open' or 'closed'
    found_time: str  # ISO
    closed_time: Optional[str] = ''
    close_price: Optional[float] = None


class GapManager:
    """Manages gap records saved to CSV and status updates."""

    def __init__(self, csv_path: Path = GAPS_CSV):
        self.csv_path = csv_path
        if not self.csv_path.exists():
            from dataclasses import fields
            fieldnames = [fld.name for fld in fields(GapRecord)]
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

    def _next_id(self) -> str:
        # Simple incremental ID based on existing rows
        rows = self._read_all()
        return f"G{len(rows) + 1:05d}"

    def _read_all(self) -> List[dict]:
        with open(self.csv_path, newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def add_gap(self, timeframe: str, start_time: datetime, gap_type: str, gap_low: float, gap_high: float) -> GapRecord:
        rec = GapRecord(
            id=self._next_id(),
            timeframe=timeframe,
            start_time=start_time.isoformat(),
            gap_type=gap_type,
            gap_low=float(gap_low),
            gap_high=float(gap_high),
            status='open',
            found_time=datetime.utcnow().isoformat(),
        )
        self._append(rec)
        logger.info(f"Recorded gap {rec.id} {timeframe} {gap_type} {gap_low}-{gap_high}")
        return rec

    def _append(self, rec: GapRecord):
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(rec).keys()))
            writer.writerow(asdict(rec))

    def update_gap_closed(self, gap_id: str, closed_time: datetime, close_price: float):
        rows = self._read_all()
        updated = False
        for r in rows:
            if r.get('id') == gap_id and r.get('status') == 'open':
                r['status'] = 'closed'
                r['closed_time'] = closed_time.isoformat()
                r['close_price'] = f"{float(close_price):.8f}"
                updated = True
        if updated:
            # rewrite file
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            logger.info(f"Gap {gap_id} marked closed at {closed_time} price {close_price}")

    def list_open_gaps(self) -> List[GapRecord]:
        rows = self._read_all()
        return [GapRecord(**r) for r in rows if r.get('status') == 'open']


class GapStrategy:
    """Main strategy implementation. Detects gaps and monitors them."""

    def __init__(self, symbol='BTC_USDT', timeframes=None, data_dir='data', recent_bars: int = 15):
        self.symbol = symbol
        self.timeframes = timeframes or ['60M', '4H', '1D']
        self.downloader = PionexDownloader(symbol=self.symbol, data_dir=data_dir)
        self.gap_mgr = GapManager()
        self.data_dir = data_dir
        self.recent_bars = recent_bars

    def summarize_recent_gaps(self, timeframe: str, x: Optional[int] = None, mode: str = None):
        """Summarize gaps found when scanning the last `x` bars for `timeframe`.

        If `mode` is provided it will be forwarded to the detector (e.g. 'b2dir', 'open', 'body').

        Returns a dict: {count: int, gaps: [{time: str, type: str, low: float, high: float}, ...]}
        """
        x = x or self.recent_bars
        # Load last X bars from CSV for the timeframe
        filename = Path(self.downloader.data_dir) / f"{self.symbol.lower()}_{timeframe.lower()}_pionex.csv"
        if not filename.exists():
            return {'count': 0, 'gaps': []}

        import pandas as pd
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        df = df.sort_index()
        last = df.tail(x)
        gaps_found = []
        # slide window of size 3
        for i in range(2, len(last)):
            window = last.iloc[i-2:i+1]
            # pass mode if provided, otherwise let _detect_gap use its default
            res = self._detect_gap(window, mode=mode) if mode is not None else self._detect_gap(window)
            if res is not None:
                gaps_found.append({'time': res['start_time'].isoformat(), 'type': res['type'], 'low': res['gap_low'], 'high': res['gap_high']})
        return {'count': len(gaps_found), 'gaps': gaps_found}

    def run_scan(self, timeframe: str, download_latest: bool = False, download_limit: int = 48, mode: str = None, dry_run: bool = False, verbose: bool = False, output_file: str = None):
        """Run a single scan for a given timeframe.

        Parameters mirror the script:
         - download_latest: if True, fetch latest bars before scanning
         - download_limit: how many bars to fetch when downloading
         - mode: detection mode (forwarded to summarize_recent_gaps)
         - dry_run: if True, don't record or send alerts, only preview
         - verbose: if True, include 3-bar windows and detector output in print/output_file
         - output_file: path to append verbose/dry-run lines for later analysis

        Returns a dict with keys: count, gaps, actions (list of action strings taken or previewed)
        """
        actions = []
        # Optionally download latest bars
        if download_latest:
            try:
                self.downloader.download_latest(interval=timeframe, limit=download_limit)
                actions.append(f"downloaded_latest:{download_limit}")
            except Exception as e:
                actions.append(f"download_failed:{e}")
        # Summarize
        summary = self.summarize_recent_gaps(timeframe, x=self.recent_bars, mode=mode)
        # For each found gap, decide whether to record/send or preview
        import pandas as pd
        fname = Path(self.downloader.data_dir) / f"{self.symbol.lower()}_{timeframe.lower()}_pionex.csv"
        df_full = None
        if verbose and fname.exists():
            try:
                df_full = pd.read_csv(fname, index_col=0, parse_dates=True).sort_index()
            except Exception:
                df_full = None
        for g in summary['gaps']:
            found_time = datetime.fromisoformat(g['time'])
            # Verbose lines
            verbose_lines = []
            if verbose and df_full is not None:
                try:
                    if found_time in df_full.index:
                        idx = df_full.index.get_loc(found_time)
                    else:
                        idx = df_full.index.get_indexer([found_time], method='nearest')[0]
                    start = max(0, idx - 2)
                    window = df_full.iloc[start: idx + 1]
                    verbose_lines.append('Verbose: candidate window:')
                    for ti, row in window.iterrows():
                        verbose_lines.append(f"  {ti.isoformat()}  O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']}")
                    det = self._detect_gap(window, mode=mode) if mode is not None else self._detect_gap(window)
                    verbose_lines.append(f"Verbose: detector output -> {det}")
                except Exception as e:
                    verbose_lines.append(f"Verbose: failed to prepare window: {e}")
            # Check if already recorded
            recorded = False
            for r in self.gap_mgr._read_all():
                r_tf = r.get('timeframe')
                r_start = r.get('start_time') or r.get('start') or ''
                try:
                    r_dt = datetime.fromisoformat(r_start) if r_start else None
                except Exception:
                    r_dt = None
                if r_tf == timeframe and r_dt is not None and r_dt == found_time:
                    recorded = True
                    break
            preview = f"Found gap {timeframe} {g['type']} {g['low']} - {g['high']} at {g['time']}"
            if dry_run:
                actions.append(f"DRY-RUN: {preview}")
                if output_file:
                    try:
                        with open(output_file, 'a') as of:
                            of.write(f"DRY-RUN: {preview}\n")
                            for vl in verbose_lines:
                                of.write(vl + "\n")
                            of.write("\n")
                    except Exception:
                        pass
            else:
                if not recorded:
                    rec = self.gap_mgr.add_gap(timeframe, datetime.fromisoformat(g['time']), g['type'], g['low'], g['high'])
                    msg = f"Gap found {rec.id} {timeframe} {g['type']} {g['low']} - {g['high']} at {g['time']}"
                    actions.append(f"RECORDED: {msg}")
                    send_msg(msg, strat='bitcoin-trader')
                    if output_file:
                        try:
                            with open(output_file, 'a') as of:
                                of.write(f"RECORDED: {msg}\n")
                                for vl in verbose_lines:
                                    of.write(vl + "\n")
                                of.write("\n")
                        except Exception:
                            pass
                else:
                    actions.append(f"ALREADY_RECORDED: {preview}")
        return {'count': summary['count'], 'gaps': summary['gaps'], 'actions': actions}

    def _fetch_last_n(self, interval: str, n: int = 3):
        df = self.downloader.get_bars(interval=interval, limit=n)
        if df is None:
            return None
        # Ensure sorted by time
        df = df.sort_index()
        if len(df) < n:
            return None
        return df.tail(n)

    def _detect_gap(self, df, mode: str = 'strict'):
        """Detects a gap using last three bars. Returns dict or None.

        Modes supported:
        - 'strict' (default): b1/b2 must overlap; b3.body low > b2.body high (up) or b3.body high < b2.body low (down)
        - 'body': same as strict but uses candle 'body' min/max explicitly (same behavior as strict by default)
        - 'open': compares b3.open against b2.high/b2.low (more permissive)
        - 'b2dir': determines potential direction from the middle bar (b2). If b2 is an "up" bar (open < close)
          then an UP gap exists if the entire b3 range is above the entire b1 range (no intersection): b3.low > b1.high.
          If b2 is a "down" bar (open > close) then a DOWN gap exists if the entire b3 range is below the entire b1 range: b3.high < b1.low.

        Returns a dict with keys: type ('up'/'down'), gap_low, gap_high, start_time.
        """
        b1, b2, b3 = df.iloc[0], df.iloc[1], df.iloc[2]

        # compute full-range values
        b1_low, b1_high = float(b1['low']), float(b1['high'])
        b2_low, b2_high = float(b2['low']), float(b2['high'])
        b3_low, b3_high = float(b3['low']), float(b3['high'])

        def body_range(b):
            return float(min(b['open'], b['close'])), float(max(b['open'], b['close']))

        b1_low_b, b1_high_b = body_range(b1)
        b2_low_b, b2_high_b = body_range(b2)
        b3_low_b, b3_high_b = body_range(b3)

        # New mode: use b2 direction and non-intersection between b3 and b1
        if mode == 'b2dir':
            # determine b2 direction by body
            if float(b2['open']) < float(b2['close']):
                # b2 is an up bar -> look for upward gap where b3 is entirely above b1
                if b3_low > b1_high:
                    return {'type': 'up', 'gap_low': float(b1_high), 'gap_high': float(b3_low), 'start_time': b3.name.to_pydatetime()}
            elif float(b2['open']) > float(b2['close']):
                # b2 is a down bar -> look for downward gap where b3 is entirely below b1
                if b3_high < b1_low:
                    return {'type': 'down', 'gap_low': float(b3_high), 'gap_high': float(b1_low), 'start_time': b3.name.to_pydatetime()}
            return None

        # For strict mode use full high/low; for body mode use body ranges
        if mode == 'strict':
            # overlap using full ranges
            overlap = not (b1_high < b2_low or b1_low > b2_high)
            if not overlap:
                return None
            # Up gap using full lows/highs
            if b3_low > b2_high:
                return {'type': 'up', 'gap_low': float(b2_high), 'gap_high': float(b3_low), 'start_time': b3.name.to_pydatetime()}
            if b3_high < b2_low:
                return {'type': 'down', 'gap_low': float(b3_high), 'gap_high': float(b2_low), 'start_time': b3.name.to_pydatetime()}
            return None

        if mode == 'open':
            # use open price of b3 compared to full b2 high/low
            if b3['open'] > b2_high:
                return {'type': 'up', 'gap_low': float(b2_high), 'gap_high': float(b3['open']), 'start_time': b3.name.to_pydatetime()}
            if b3['open'] < b2_low:
                return {'type': 'down', 'gap_low': float(b3['open']), 'gap_high': float(b2_low), 'start_time': b3.name.to_pydatetime()}
            return None

        # body mode (default if mode == 'body')
        # overlap using body ranges
        overlap = not (b1_high_b < b2_low_b or b1_low_b > b2_high_b)
        if not overlap:
            return None

        if b3_low_b > b2_high_b:
            return {'type': 'up', 'gap_low': float(b2_high_b), 'gap_high': float(b3_low_b), 'start_time': b3.name.to_pydatetime()}
        if b3_high_b < b2_low_b:
            return {'type': 'down', 'gap_low': float(b3_high_b), 'gap_high': float(b2_low_b), 'start_time': b3.name.to_pydatetime()}

        return None

    def _monitor_gaps_with_bar(self, interval: str, bar):
        """Check open gaps for closure using the incoming bar (Series with open/high/low/close)."""
        open_gaps = self.gap_mgr.list_open_gaps()
        for g in open_gaps:
            if g.timeframe != interval:
                continue
            # up gap closes if bar.low <= gap_low
            if g.gap_type == 'up' and bar['low'] <= float(g.gap_low):
                self.gap_mgr.update_gap_closed(g.id, datetime.utcnow(), bar['low'])
                send_msg(f"Gap closed {g.id} {interval} up gap filled at {bar['low']}", strat='bitcoin-trader')
            # down gap closes if bar.high >= gap_high
            if g.gap_type == 'down' and bar['high'] >= float(g.gap_high):
                self.gap_mgr.update_gap_closed(g.id, datetime.utcnow(), bar['high'])
                send_msg(f"Gap closed {g.id} {interval} down gap filled at {bar['high']}", strat='bitcoin-trader')

    def process_interval(self, interval: str):
        logger.info(f"Processing interval {interval}")
        # Ensure CSV is refreshed with latest bars before detection and monitoring
        try:
            self.downloader.download_latest(interval=interval, limit=48)
            logger.debug(f"Downloaded latest bars for {interval} at start of process_interval")
        except Exception as e:
            logger.warning(f"Failed to download latest bars for {interval} at start of process_interval: {e}")

        df = self._fetch_last_n(interval, n=3)
        if df is None:
            logger.debug(f"Not enough data for {interval}")
            return
        # Detect gap
        gap = self._detect_gap(df)
        if gap:
            rec = self.gap_mgr.add_gap(interval, gap['start_time'], gap['type'], gap['gap_low'], gap['gap_high'])
            send_msg(f"Gap found {rec.id} {interval} {gap['type']} {gap['gap_low']} - {gap['gap_high']}", strat='bitcoin-trader')
        # Monitor existing gaps using most recent bar
        latest_bar = df.iloc[-1]
        self._monitor_gaps_with_bar(interval, latest_bar)

        # Summarize recent gaps over the last X bars and send a Discord message with history
        try:
            summary = self.summarize_recent_gaps(interval, x=self.recent_bars)
            count = summary['count']
            if count == 0:
                msg = f"No gaps found in the last {self.recent_bars} bars for {interval}."
            else:
                # Build a more detailed summary listing times and low/high for each gap
                gap_lines = []
                for g in summary['gaps']:
                    gap_lines.append(f"{g['time']} {g['type'].upper()} low={g['low']} high={g['high']}")
                msg = f"{count} gaps in the last {self.recent_bars} bars for {interval}:\n" + "\n".join(gap_lines)
            send_msg(msg, strat='bitcoin-trader')
        except Exception as e:
            logger.error(f"Error summarizing recent gaps for {interval}: {e}")


def main():
    import signal
    import sys

    strategy = GapStrategy()

    # Send start message
    send_msg("Bitcoin gap monitor started", strat='bitcoin-trader')

    # Schedule jobs
    # 60M: every hour at :02
    schedule.every().hour.at(':02').do(strategy.process_interval, '60M')
    # 4H: every 4 hours at 00:06, 04:06, ... (approx)
    for hour in [0, 4, 8, 12, 16, 20]:
        schedule.every().day.at(f"{hour:02d}:06").do(strategy.process_interval, '4H')
    # 1D: daily at 00:12
    schedule.every().day.at('00:12').do(strategy.process_interval, '1D')

    # Run an initial pass
    for tf in strategy.timeframes:
        strategy.process_interval(tf)
        time.sleep(1)

    # Clean shutdown handling
    def _shutdown(signum, frame):
        logger.info('Shutting down...')
        send_msg('Bitcoin gap monitor stopped', strat='bitcoin-trader')
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Loop with a visible countdown in attached terminals
    logger.info('Scheduler started. Press Ctrl+C to stop.')
    try:
        while True:
            # Display per-timeframe countdowns to the next scheduled job run
            now = datetime.utcnow()
            # Find the minimum next_run for each timeframe (jobs can be duplicated)
            next_by_tf = {}
            for job in schedule.jobs:
                try:
                    args = getattr(job.job_func, 'args', None) or getattr(job, 'args', None)
                    tf = args[0] if args else None
                except Exception:
                    tf = None
                if tf is None:
                    continue
                if getattr(job, 'next_run', None):
                    delta = (job.next_run - now).total_seconds()
                    if delta < 0:
                        delta = 0
                    prev = next_by_tf.get(tf)
                    if prev is None or delta < prev:
                        next_by_tf[tf] = delta

            lines = ['Next Data Download:']
            # Keep configured timeframes ordering when possible
            for tf in strategy.timeframes:
                secs = int(next_by_tf.get(tf, 0))
                hours = secs // 3600
                mins = (secs % 3600) // 60
                lines.append(f"- {tf}: {hours:02d}:{mins:02d} hr:min")

            # Clear screen (simple) and print the multi-line status so tmux shows a live countdown block
            try:
                print("\033[2J\033[H", end='')
            except Exception:
                pass
            print("\n".join(lines))
            print(f"Time: {datetime.utcnow().isoformat()}\n", end='', flush=True)

            # Execute any pending jobs (this will also emit log lines)
            schedule.run_pending()

            # Sleep briefly to update the status frequently without excessive CPU usage
            time.sleep(1)
    except KeyboardInterrupt:
        # Ensure the status line ends with a newline before shutting down
        print('\n')
        _shutdown(None, None)


if __name__ == '__main__':
    main()
