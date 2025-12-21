"""
Vectorized-style backtest for ThreeBarGap pattern using vectorbt if installed.
Falls back to a small sequential engine if vectorbt is not available.

Usage:
    python vectorbt_backtest.py

If vectorbt is missing, install with:
    pip install vectorbt

This script will:
 - Load btc_1h_yf_clean.csv
 - Scan for the three-bar gap pattern (same rules as ThreeBarGapBTC)
 - Simulate stop-entry (default) or market-next entry behavior per parameter
 - Record trades and print a summary
 - If vectorbt is available, build a Portfolio and print its stats
"""

import sys
from datetime import datetime
import argparse
import pandas as pd

CSV = 'btc_1h_yf_clean.csv'
USE_MARKET_NEXT = False  # use market next bar or stop trigger
SIZE = 1


def load_data(path=CSV, start=None, end=None):
    df = pd.read_csv(path, header=None, parse_dates=[0])
    # original mapping: datetime=0, open=5, high=3, low=4, close=2, volume=6
    df = df.rename(columns={0: 'datetime', 2: 'close', 3: 'high', 4: 'low', 5: 'open', 6: 'volume'})
    df = df.set_index('datetime')
    # optionally restrict to a given time window
    if start is not None or end is not None:
        # pandas will handle None values correctly when slicing
        df = df.loc[start:end]
    return df


def run_sim(df, use_market_next=USE_MARKET_NEXT, size=SIZE):
    n = len(df)
    trades = []
    signals = []

    in_position = False
    pending_entry = None
    pos = None

    # iterate with index i representing current bar (like Backtrader next())
    for i in range(n):
        if i < 3:
            continue

        # 1) If currently in a position, check TP/SL on this bar and close if hit
        if in_position and pos is not None:
            highk = df.iloc[i]['high']
            lowk = df.iloc[i]['low']

            tp_hit = (pos.get('tp') is not None) and (highk >= pos['tp'])
            sl_hit = (pos.get('sl') is not None) and (lowk <= pos['sl'])

            exit_idx = None
            exit_price = None
            reason = None

            if tp_hit and not sl_hit:
                exit_idx = i
                exit_price = pos['tp']
                reason = 'TP'
            elif sl_hit and not tp_hit:
                exit_idx = i
                exit_price = pos['sl']
                reason = 'SL'
            elif tp_hit and sl_hit:
                # both hit same bar — select nearest by proximity heuristic
                openk = df.iloc[i]['open']
                d_tp = abs(df.iloc[i]['high'] - pos['tp']) + abs(openk - pos['tp'])
                d_sl = abs(df.iloc[i]['low'] - pos['sl']) + abs(openk - pos['sl'])
                if d_tp <= d_sl:
                    exit_idx = i
                    exit_price = pos['tp']
                    reason = 'TP'
                else:
                    exit_idx = i
                    exit_price = pos['sl']
                    reason = 'SL'

            if exit_idx is not None:
                pnl = (exit_price - pos['entry_price']) * size
                trades.append({
                    'signal_dt': pos.get('signal_dt'), 'entry_dt': pos.get('entry_dt'), 'entry_price': pos.get('entry_price'),
                    'exit_dt': df.index[exit_idx], 'exit_price': exit_price, 'reason': reason, 'pnl': pnl
                })
                in_position = False
                pos = None
            # while in a position we ignore any new signals
            continue

        # 2) Pending entry checks: stop/order fills block new signals until resolved
        if pending_entry is not None and not in_position:
            if pending_entry.get('type') == 'market_next':
                if i == pending_entry.get('entry_idx'):
                    # execute market next at this bar's open if price not specified
                    entry_price = pending_entry.get('entry_price') or df.iloc[i]['open']
                    entry_dt = pending_entry.get('entry_dt') or df.index[i]
                    pos = dict(signal_dt=pending_entry.get('signal_dt'), entry_dt=entry_dt, entry_price=entry_price,
                               tp=pending_entry.get('tp_price'), sl=pending_entry.get('sl_price'))
                    in_position = True
                    pending_entry = None
                else:
                    # still waiting for market-next bar — block new signals
                    continue
            elif pending_entry.get('type') == 'stop':
                stop_price = pending_entry.get('stop_price')
                if df.iloc[i]['high'] >= stop_price:
                    entry_price = stop_price
                    entry_dt = df.index[i]
                    pos = dict(signal_dt=pending_entry.get('signal_dt'), entry_dt=entry_dt, entry_price=entry_price,
                               tp=pending_entry.get('tp_price'), sl=pending_entry.get('sl_price'))
                    in_position = True
                    pending_entry = None
                else:
                    # still waiting for stop to trigger — block new signals
                    continue

        # 3) No active or pending entries — look for pattern signals
        if not in_position and pending_entry is None:
            # check pattern using bar1 = i-3 and bar3 = i-1
            bar1 = df.iloc[i-3]
            bar3 = df.iloc[i-1]

            cond_bar1_red = bar1['close'] < bar1['open']
            cond_gap = (bar3['high'] < bar1['low']) and (bar3['close'] < bar1['low'])

            if cond_bar1_red and cond_gap:
                # signal generated at current bar time
                signals.append(df.index[i])
                tp_price = bar1['low']
                sl_price = bar3['low']
                stop_price = bar3['high']
                signal_dt = df.index[i]

                # create entry depending on mode
                if use_market_next:
                    # entry at next bar open
                    entry_idx = i + 1
                    if entry_idx >= n:
                        # no next bar — create a pending market entry (blocks new signals)
                        pending_entry = dict(type='market_next', entry_idx=entry_idx, entry_price=None, entry_dt=None,
                                             signal_dt=signal_dt, tp_price=tp_price, sl_price=sl_price)
                        signals.append(signal_dt)
                        continue
                    entry_price = df.iloc[entry_idx]['open']
                    entry_dt = df.index[entry_idx]
                else:
                    # stop order — we place a pending stop entry that blocks further signals
                    entry_idx = None
                    entry_price = None
                    entry_dt = None
                    # mark a pending stop (will be checked on subsequent bars)
                    pending_entry = dict(type='stop', stop_price=stop_price, signal_dt=signal_dt,
                                         tp_price=tp_price, sl_price=sl_price)
                    # keep scanning future bars in the normal loop until the pending stop triggers
                    continue

                # position is opened at entry_idx (market-next and stop fills reached here)
                in_position = True

                # now find exit starting from entry_idx+1
                exit_idx = None
                exit_price = None
                for k in range(entry_idx+1, n):
                    highk = df.iloc[k]['high']
                    lowk = df.iloc[k]['low']

                    tp_hit = highk >= tp_price
                    sl_hit = lowk <= sl_price

                    if tp_hit and not sl_hit:
                        exit_idx = k
                        exit_price = tp_price
                        reason = 'TP'
                        break
                    if sl_hit and not tp_hit:
                        exit_idx = k
                        exit_price = sl_price
                        reason = 'SL'
                        break
                    if tp_hit and sl_hit:
                        # both hit same bar — choose first-to-hit by proximity heuristic
                        # assume price moved from open -> high -> low within bar or vice versa
                        # without intra-bar sequencing data, choose the closer level to the bar open
                        openk = df.iloc[k]['open']
                        # distance to tp and sl
                        d_tp = abs(highk - tp_price) + abs(openk - tp_price)
                        d_sl = abs(lowk - sl_price) + abs(openk - sl_price)
                        # prefer the nearer target
                        if d_tp <= d_sl:
                            exit_idx = k
                            exit_price = tp_price
                            reason = 'TP'
                        else:
                            exit_idx = k
                            exit_price = sl_price
                            reason = 'SL'
                        break

                if exit_idx is None:
                    # no exit within dataset — assume position remains open until end
                    trades.append({
                        'signal_dt': signal_dt, 'entry_dt': entry_dt, 'entry_price': entry_price,
                        'exit_dt': None, 'exit_price': None, 'reason': None, 'pnl': None
                    })
                    # leave in_position True and break (or we can continue scanning but strategy wouldn't allow another signal)
                    # keep 'pos' to indicate an active position and break out of scanning loop
                    pos = dict(signal_dt=signal_dt, entry_dt=entry_dt, entry_price=entry_price, tp=tp_price, sl=sl_price)
                    in_position = True
                    break
                else:
                    pnl = (exit_price - entry_price) * size
                    trades.append({
                        'signal_dt': signal_dt, 'entry_dt': entry_dt, 'entry_price': entry_price,
                        'exit_dt': df.index[exit_idx], 'exit_price': exit_price, 'reason': reason,
                        'pnl': pnl
                    })
                    in_position = False
                    pending_entry = None

        # else: if already in position, strategy blocks new signals

    return trades, signals


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run vectorbt-style ThreeBarGap backtest')
    parser.add_argument('--start', help='Start datetime (inclusive) e.g. 2024-01-01T00:00:00')
    parser.add_argument('--end', help='End datetime (inclusive) e.g. 2024-02-19T23:00:00')
    parser.add_argument('--csv', help='CSV file to load (default btc_1h_yf_clean.csv)', default=CSV)
    parser.add_argument('--market-next', action='store_true', help='Use market-on-next-bar entry semantics')
    args = parser.parse_args()

    df = load_data(args.csv, start=args.start, end=args.end)
    if args.market_next:
        USE_MARKET_NEXT = True
    print('Loaded', len(df), 'rows from', CSV)
    if args.start or args.end:
        print('Window start/end:', args.start, args.end)

    try:
        import vectorbt as vbt
        vbt_available = True
        print('vectorbt available, version', vbt.__version__)
    except Exception:
        vbt_available = False
        print('vectorbt not installed — running local simulator. To enable vectorbt features run: pip install vectorbt')

    trades, signals = run_sim(df, use_market_next=USE_MARKET_NEXT, size=SIZE)

    print('\nSimulated trades:', len(trades))
    print('Signals detected:', len(signals))
    wins = [t for t in trades if t['pnl'] is not None and t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] is not None and t['pnl'] <= 0]
    print('Closed trades:', len([t for t in trades if t['pnl'] is not None]))
    print('Wins:', len(wins), 'Losses:', len(losses))
    total_pnl = sum([t['pnl'] for t in trades if t['pnl'] is not None])
    print('Total PnL:', total_pnl)

    if len(trades) > 0:
        print('\nFirst 10 trades:')
        for t in trades[:10]:
            print(t)
    if len(signals) > 0:
        print('\nFirst 10 signals:')
        for s in signals[:10]:
            print('-', s)

    # If vectorbt is available, make a portfolio summary using trade-level returns
    if vbt_available:
        import numpy as np
        # build a simple cashflow series for each trade (entry negative, exit positive)
        cashflow = pd.Series(0.0, index=df.index)
        for t in trades:
            if t['entry_dt'] is not None:
                cashflow.loc[t['entry_dt']] -= t['entry_price'] * SIZE
            if t['exit_dt'] is not None:
                cashflow.loc[t['exit_dt']] += t['exit_price'] * SIZE
        if cashflow.abs().sum() == 0:
            print('No cashflows to feed vectorbt — falling back to from_signals')

        # Build boolean entries/exits series and use from_signals (safer and available)
        entries = pd.Series(False, index=df.index)
        exits = pd.Series(False, index=df.index)
        for t in trades:
            if t['entry_dt'] is not None:
                entries.loc[t['entry_dt']] = True
            if t['exit_dt'] is not None:
                exits.loc[t['exit_dt']] = True

        try:
            port = vbt.Portfolio.from_signals(
                close=df['close'], entries=entries, exits=exits,
                init_cash=100000.0, fees=0.0, size=SIZE
            )
            print('\nVectorbt portfolio stats:')
            print(port.stats())
        except Exception as e:
            print('vectorbt portfolio creation failed:', e)

    print('\nDone.')
