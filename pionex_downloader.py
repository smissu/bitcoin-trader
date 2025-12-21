#!/usr/bin/env python3
"""
Pionex Data Downloader
Downloads OHLCV Bars data from Pionex at scheduled intervals.
Supports multiple timeframes: 60M (hourly), 4H (4-hour), 1D (daily)
"""

import requests
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import schedule
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pionex_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PionexDownloader:
    """Downloads and manages Bars data from Pionex exchange."""
    
    BASE_URL = "https://api.pionex.com"
    KLINES_ENDPOINT = "/api/v1/market/klines"
    
    # Interval mapping
    INTERVALS = {
        '1m': '1M',
        '5m': '5M',
        '15m': '15M',
        '30m': '30M',
        '60m': '60M',
        '1h': '60M',
        '4h': '4H',
        '8h': '8H',
        '12h': '12H',
        '1d': '1D',
        'daily': '1D'
    }
    
    # Interval to minutes mapping for scheduling
    INTERVAL_MINUTES = {
        '60M': 60,
        '4H': 240,
        '1D': 1440
    }
    
    def __init__(self, symbol='BTC_USDT', data_dir='data'):
        """
        Initialize the downloader.
        
        Args:
            symbol: Trading pair symbol (default: BTC_USDT)
            data_dir: Directory to store downloaded data
        """
        self.symbol = symbol
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    def get_bars(self, interval='4H', limit=500, start_time=None, end_time=None):
        """
        Fetch Bars data from Pionex.
        
        Args:
            interval: Bar interval (1M, 5M, 15M, 30M, 60M, 4H, 8H, 12H, 1D)
            limit: Number of bars to fetch (default 100, max 500)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            
        Returns:
            DataFrame with OHLCV data
        """
        # Normalize interval
        interval = self.INTERVALS.get(interval.lower(), interval)
        
        params = {
            'symbol': self.symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = int(start_time)
        if end_time:
            params['endTime'] = int(end_time)
            
        try:
            url = f"{self.BASE_URL}{self.KLINES_ENDPOINT}"
            logger.info(f"Fetching {interval} Bars for {self.symbol} (limit={limit})")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('result'):
                logger.error(f"API request failed: {data}")
                return None
                
            # Note: API field name is 'klines' and must remain unchanged for the endpoint
            bars = data.get('data', {}).get('klines', [])
            
            if not bars:
                logger.warning("No Bars data returned")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            
            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            
            # Convert OHLCV to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Set time as index
            df.set_index('time', inplace=True)
            
            logger.info(f"Successfully fetched {len(df)} Bars")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    
    def save_to_csv(self, df, interval, append=True):
        """
        Save DataFrame to CSV file.
        
        Args:
            df: DataFrame to save
            interval: Interval identifier for filename
            append: If True, append to existing file; if False, overwrite
        """
        if df is None or df.empty:
            logger.warning("No data to save")
            return
            
        filename = self.data_dir / f"{self.symbol.lower()}_{interval.lower()}_pionex.csv"
        
        try:
            if append and filename.exists():
                # Load existing data
                existing_df = pd.read_csv(filename, index_col=0, parse_dates=True)
                
                # Combine and remove duplicates
                combined_df = pd.concat([existing_df, df])
                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                combined_df.sort_index(inplace=True)
                
                combined_df.to_csv(filename)
                logger.info(f"Appended {len(df)} rows to {filename} (total: {len(combined_df)})")
            else:
                df.to_csv(filename)
                logger.info(f"Saved {len(df)} rows to {filename}")
                
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def download_latest(self, interval='4H', limit=10):
        """
        Download the latest Bars and append to CSV.
        
        Args:
            interval: Bar interval
            limit: Number of latest bars to fetch
        """
        logger.info(f"Downloading latest {interval} bars for {self.symbol}")
        df = self.get_bars(interval=interval, limit=limit)
        
        if df is not None:
            self.save_to_csv(df, interval, append=True)
            logger.info(f"Latest {interval} download complete")
        else:
            logger.error(f"Failed to download {interval} data")
    
    def download_historical(self, interval='4H', days=365):
        """
        Download historical data for specified number of days.
        
        Args:
            interval: Bar interval
            days: Number of days of historical data
        """
        # Calculate time range
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        logger.info(f"Downloading {days} days of {interval} historical data")
        
        # Pionex allows max 500 records per request
        # Calculate how many requests needed
        interval_normalized = self.INTERVALS.get(interval.lower(), interval)
        interval_minutes = self.INTERVAL_MINUTES.get(interval_normalized, 60)
        
        total_bars = (days * 24 * 60) // interval_minutes
        num_requests = (total_bars // 500) + 1
        
        all_data = []
        current_start = start_time
        
        for i in range(num_requests):
            df = self.get_bars(
                interval=interval,
                limit=500,
                start_time=current_start,
                end_time=end_time
            )
            
            if df is not None and not df.empty:
                all_data.append(df)
                # Update start time for next request
                current_start = int(df.index[-1].timestamp() * 1000) + 1
                time.sleep(0.5)  # Rate limiting
            else:
                break
        
        if all_data:
            combined_df = pd.concat(all_data)
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df.sort_index(inplace=True)
            
            self.save_to_csv(combined_df, interval, append=False)
            logger.info(f"Historical download complete: {len(combined_df)} bars")
        else:
            logger.error("No historical data downloaded")


class ScheduledDownloader:
    """Manages scheduled downloads for multiple timeframes."""
    
    def __init__(self, symbol='BTC_USDT', data_dir='data', timeframes=None):
        """
        Initialize scheduled downloader.
        
        Args:
            symbol: Trading pair symbol
            data_dir: Directory to store data
            timeframes: List of timeframes to download (e.g., ['60M', '4H', '1D'])
        """
        self.downloader = PionexDownloader(symbol=symbol, data_dir=data_dir)
        self.timeframes = timeframes or ['60M', '4H', '1D']
        
    def job_60m(self):
        """Job to download 60M bars."""
        self.downloader.download_latest(interval='60M', limit=5)
    
    def job_4h(self):
        """Job to download 4H bars."""
        self.downloader.download_latest(interval='4H', limit=5)
    
    def job_1d(self):
        """Job to download 1D bars."""
        self.downloader.download_latest(interval='1D', limit=5)
    
    def setup_schedule(self):
        """Setup scheduled jobs for all timeframes."""
        logger.info("Setting up download schedule...")
        
        if '60M' in self.timeframes or '1h' in self.timeframes:
            # Run at minute 1 of every hour (HH:01:00)
            schedule.every().hour.at(":01").do(self.job_60m)
            logger.info("Scheduled: 60M bars every hour at :01")
        
        if '4H' in self.timeframes or '4h' in self.timeframes:
            # Run at 00:05, 04:05, 08:05, 12:05, 16:05, 20:05
            for hour in [0, 4, 8, 12, 16, 20]:
                schedule.every().day.at(f"{hour:02d}:05").do(self.job_4h)
            logger.info("Scheduled: 4H bars at 00:05, 04:05, 08:05, 12:05, 16:05, 20:05")
        
        if '1D' in self.timeframes or 'daily' in self.timeframes:
            # Run daily at 00:10
            schedule.every().day.at("00:10").do(self.job_1d)
            logger.info("Scheduled: 1D bars daily at 00:10")
    
    def run(self, download_initial=True):
        """
        Run the scheduled downloader.
        
        Args:
            download_initial: If True, download latest data immediately on start
        """
        logger.info(f"Starting Pionex Downloader for {self.downloader.symbol}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
        
        # Download initial data
        if download_initial:
            logger.info("Downloading initial data...")
            for tf in self.timeframes:
                self.downloader.download_latest(interval=tf, limit=10)
                time.sleep(1)
        
        # Setup schedule
        self.setup_schedule()
        
        # Run scheduler
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pionex Bars Downloader')
    parser.add_argument('--symbol', default='BTC_USDT', help='Trading pair symbol')
    parser.add_argument('--timeframes', nargs='+', default=['60M', '4H', '1D'],
                        help='Timeframes to download (e.g., 60M 4H 1D)')
    parser.add_argument('--data-dir', default='data', help='Data directory')
    parser.add_argument('--mode', choices=['schedule', 'historical', 'once'],
                        default='schedule', help='Run mode')
    parser.add_argument('--days', type=int, default=365,
                        help='Days of historical data (for historical mode)')
    
    args = parser.parse_args()
    
    if args.mode == 'schedule':
        # Run scheduled downloader
        scheduler = ScheduledDownloader(
            symbol=args.symbol,
            data_dir=args.data_dir,
            timeframes=args.timeframes
        )
        scheduler.run()
        
    elif args.mode == 'historical':
        # Download historical data
        downloader = PionexDownloader(symbol=args.symbol, data_dir=args.data_dir)
        for tf in args.timeframes:
            logger.info(f"Downloading historical {tf} data...")
            downloader.download_historical(interval=tf, days=args.days)
            time.sleep(2)
            
    elif args.mode == 'once':
        # Download once and exit
        downloader = PionexDownloader(symbol=args.symbol, data_dir=args.data_dir)
        for tf in args.timeframes:
            downloader.download_latest(interval=tf, limit=100)
            time.sleep(1)


if __name__ == '__main__':
    main()
