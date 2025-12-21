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
            if r['id'] == gap_id and r['status'] == 'open':
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
        return [GapRecord(**r) for r in rows if r['status'] == 'open']


class GapStrategy:
    """Main strategy implementation. Detects gaps and monitors them."""

    def __init__(self, symbol='BTC_USDT', timeframes=None, data_dir='data', recent_bars: int = 15):
        self.symbol = symbol
        self.timeframes = timeframes or ['60M', '4H', '1D']
        self.downloader = PionexDownloader(symbol=self.symbol, data_dir=data_dir)
        self.gap_mgr = GapManager()
        self.data_dir = data_dir
        self.recent_bars = recent_bars

    def summarize_recent_gaps(self, timeframe: str, x: Optional[int] = None):
        """Summarize gaps found when scanning the last `x` bars for `timeframe`.

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
            res = self._detect_gap(window)
            if res is not None:
                gaps_found.append({'time': res['start_time'].isoformat(), 'type': res['type'], 'low': res['gap_low'], 'high': res['gap_high']})
        return {'count': len(gaps_found), 'gaps': gaps_found}

    def _fetch_last_n(self, interval: str, n: int = 3):
        df = self.downloader.get_bars(interval=interval, limit=n)
        if df is None:
            return None
        # Ensure sorted by time
        df = df.sort_index()
        if len(df) < n:
            return None
        return df.tail(n)

    def _detect_gap(self, df):
        """Detects a gap using last three bars. Returns dict or None.

        Criteria used:
        - Let bars be [b1, b2, b3] where b3 is the most recent.
        - Require b1 and b2 to overlap (no gap between them) to ensure the gap is new.
        - A gap exists if b3.low > b2.high (up gap) or b3.high < b2.low (down gap).
        """
        b1, b2, b3 = df.iloc[0], df.iloc[1], df.iloc[2]
        # Check b1/b2 overlap
        overlap = not (b1['high'] < b2['low'] or b1['low'] > b2['high'])
        if not overlap:
            return None
        # Up gap
        if b3['low'] > b2['high']:
            gap_low = float(b2['high'])
            gap_high = float(b3['low'])
            return {
                'type': 'up',
                'gap_low': gap_low,
                'gap_high': gap_high,
                'start_time': b3.name.to_pydatetime()
            }
        # Down gap
        if b3['high'] < b2['low']:
            gap_low = float(b3['high'])
            gap_high = float(b2['low'])
            return {
                'type': 'down',
                'gap_low': gap_low,
                'gap_high': gap_high,
                'start_time': b3.name.to_pydatetime()
            }
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
                times = ', '.join([g['time'] for g in summary['gaps']])
                msg = f"{count} gaps in the last {self.recent_bars} bars for {interval}: {times}"
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
            # seconds until the next scheduled job (None when no jobs are present)
            next_secs = schedule.idle_seconds()
            if next_secs is None:
                status = 'No scheduled jobs'
            else:
                status = f'Next check in {int(next_secs)}s'

            # Print a concise status line to stdout so an attached tmux session shows a live countdown
            print(f"\r{status} | Time: {datetime.utcnow().isoformat()}", end='', flush=True)

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
