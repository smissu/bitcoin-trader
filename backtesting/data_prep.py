#!/usr/bin/env python3
"""Create 4H resample from existing 1H CSV and download 1D bars from yfinance.

Outputs:
 - btc_4h_yf_clean.csv  (resampled from btc_1h_yf_clean.csv)
 - btc_1d_yf_clean.csv  (downloaded from Yahoo/ yfinance)

Both files are written in the same column layout as your existing cleaned file
so they can be used with Backtrader GenericCSVData and vectorbt scripts.

Date/time strings are timezone-aware UTC like '2024-01-01 00:00:00+00:00'.
"""

import os
import sys
import pandas as pd

CSV_1H = 'btc_1h_yf_clean.csv'
CSV_4H = 'btc_4h_yf_clean.csv'
CSV_1D = 'btc_1d_yf_clean.csv'


def resample_4h(input_csv=CSV_1H, out_csv=CSV_4H):
    if not os.path.exists(input_csv):
        print(f'input file not found: {input_csv}', file=sys.stderr)
        return None

    df = pd.read_csv(input_csv, header=None, parse_dates=[0])
    # column mapping in cleaned file:
    # 0: datetime, 1: adjclose, 2: close, 3: high, 4: low, 5: open, 6: volume
    df = df.rename(columns={0: 'datetime', 1: 'adjclose', 2: 'close', 3: 'high', 4: 'low', 5: 'open', 6: 'volume'})
    df = df.set_index('datetime')
    # ensure UTC tz-aware datetimes
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')

    # resample to 4H
    agg = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'adjclose': 'last',
    }

    df4 = df.resample('4H').agg(agg)
    df4.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

    # reorder columns to match original cleaned CSV: datetime, adjclose, close, high, low, open, volume
    out = df4[['adjclose', 'close', 'high', 'low', 'open', 'volume']].copy()
    # Write without header and using utc offset in datetime
    out.index = out.index.tz_convert('UTC')
    out.reset_index(inplace=True)
    out['datetime'] = out['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S%z')
    out = out[['datetime', 'adjclose', 'close', 'high', 'low', 'open', 'volume']]
    out.to_csv(out_csv, index=False, header=False)

    print(f'Wrote {len(out)} rows to {out_csv}')
    return out_csv


def download_1d(out_csv=CSV_1D, symbol='BTC-USD', period='max'):
    try:
        import yfinance as yf
    except Exception as e:
        print('yfinance package is not installed — please install it in your environment', file=sys.stderr)
        raise

    print(f'Downloading {symbol} daily bars (period={period})')
    df = yf.download(symbol, interval='1d', period=period, auto_adjust=False, progress=False)
    if df is None or df.empty:
        print('No data downloaded', file=sys.stderr)
        return None

    # ensure datetime index tz-aware UTC
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')

    # Expect df columns: Open, High, Low, Close, Adj Close, Volume
    if 'Adj Close' not in df.columns and 'Adj_Close' not in df.columns:
        df['Adj Close'] = df['Close']

    # Build columns in the same layout as cleaned CSV
    out = pd.DataFrame(index=df.index)
    out['adjclose'] = df.get('Adj Close', df['Close'])
    out['close'] = df['Close']
    out['high'] = df['High']
    out['low'] = df['Low']
    out['open'] = df['Open']
    out['volume'] = df['Volume'].fillna(0).astype(int)

    out.reset_index(inplace=True)
    out['datetime'] = out['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S%z')
    out = out[['datetime', 'adjclose', 'close', 'high', 'low', 'open', 'volume']]
    out.to_csv(out_csv, index=False, header=False)

    print(f'Wrote {len(out)} rows to {out_csv}')
    return out_csv


if __name__ == '__main__':
    print('Starting data prep')
    r4 = resample_4h()

    try:
        d1 = download_1d()
    except Exception:
        print('Failed to download 1d bars — try installing yfinance in the active env: pip install yfinance', file=sys.stderr)
        d1 = None

    print('Done.')
