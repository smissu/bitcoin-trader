#!/usr/bin/env python3
"""Scan recent bars for gaps, record any unrecorded gaps, and send detailed Discord messages."""
from pathlib import Path
import importlib.util
import importlib
import os
from datetime import datetime

proj = Path('.').resolve()
import sys
sys.path.insert(0, str(proj))
# ensure parent directory is on sys.path so imports inside the module work
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy

# load env
try:
    with open('.env') as f:
        for ln in f:
            if '=' in ln:
                k,v = ln.split('=',1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
except FileNotFoundError:
    pass

import discord.messages as dm
importlib.reload(dm)

strategy = GapStrategy()
manager = strategy.gap_mgr

import argparse

parser = argparse.ArgumentParser(description='Scan recent bars for gaps, record any unrecorded gaps, and send Discord messages.')
parser.add_argument('-t', '--timeframes', default='60M',
                    help="Comma-separated list of timeframes to scan (e.g., '60M,4H,1D'). Default: 60M")
parser.add_argument('-m', '--mode', default=None,
                    help="Detection mode to use (e.g., 'strict','body','open','b2dir'). Default: module default")
parser.add_argument('-d', '--download-latest', action='store_true',
                    help='If set, download the latest bars for each timeframe before scanning')
parser.add_argument('--download-limit', type=int, default=48,
                    help='Number of latest bars to fetch when using --download-latest (default: 48)')
parser.add_argument('--dry-run', action='store_true',
                    help='If set, only print found gaps and do not record or send Discord messages')
parser.add_argument('--display-tz', type=str, default=None, help='Display timezone (IANA name like Europe/Berlin or UTC+1). If omitted, uses system local timezone')
parser.add_argument('--display-tz-format', type=str, choices=['full','local'], default='full', help='How to format displayed times: "full" = UTC + (local), "local" = local time only')
parser.add_argument('--gap-type', type=str, choices=['both','up','down'], default='both', help='Which gap types to include in the scan (default: both)')
parser.add_argument('--verbose', action='store_true',
                    help='If set, print the 3-bar window for each candidate gap and the detector output')
parser.add_argument('--output-file', type=str, default=None,
                    help='If provided, append verbose/dry-run output to this file (path)')
args = parser.parse_args()

# parse comma-separated timeframes into a list
timeframes = [tf.strip() for tf in args.timeframes.split(',') if tf.strip()]

for tf in timeframes:
    mode_str = args.mode or '(module default)'
    print(f"Scanning timeframe: {tf} using detection mode: {mode_str}")

    # Optionally fetch latest bars before scanning
    if args.download_latest:
        print(f"Downloading latest {args.download_limit} bars for {tf}...")
        try:
            # Use the strategy's downloader to fetch and append latest bars
            strategy.downloader.download_latest(interval=tf, limit=args.download_limit)
            print(f"Download complete for {tf}.")
        except Exception as e:
            print(f"Warning: failed to download latest bars for {tf}: {e}")

    summary = strategy.summarize_recent_gaps(tf, x=strategy.recent_bars, mode=args.mode, gap_type=args.gap_type)
    count = summary['count']
    if count == 0:
        print(f'No gaps found in last {strategy.recent_bars} bars for {tf} using mode {mode_str}.')
        continue
    print(f'Found {count} gaps for {tf}')
    for g in summary['gaps']:
        # normalize time
        found_time = datetime.fromisoformat(g['time'])

        # Verbose: print the 3-bar window around the found time and detector output
        if args.verbose:
            try:
                import pandas as pd
                fname = Path(strategy.downloader.data_dir) / f"{strategy.symbol.lower()}_{tf.lower()}_pionex.csv"
                df_full = pd.read_csv(fname, index_col=0, parse_dates=True).sort_index()
                if found_time in df_full.index:
                    idx = df_full.index.get_loc(found_time)
                else:
                    # find nearest index position
                    pos = df_full.index.get_indexer([found_time], method='nearest')[0]
                    idx = pos
                start = max(0, idx - 2)
                window = df_full.iloc[start: idx + 1]
                verbose_lines = []
                verbose_lines.append('Verbose: candidate window:')
                for ti, row in window.iterrows():
                    line = f"  {ti.isoformat()}  O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']}"
                    print(line)
                    verbose_lines.append(line)
                # show detector's return on this window
                det = strategy._detect_gap(window, mode=args.mode) if args.mode is not None else strategy._detect_gap(window)
                det_line = f"Verbose: detector output -> {det}"
                print(det_line)
                verbose_lines.append(det_line)
                # if an output file is provided, append verbose lines
                if args.output_file:
                    try:
                        with open(args.output_file, 'a') as of:
                            of.write(f"=== Run: {datetime.utcnow().isoformat()} | timeframe={tf} | mode={args.mode or '(default)'} ===\n")
                            for vl in verbose_lines:
                                of.write(vl + "\n")
                            of.write("\n")
                    except Exception as e:
                        print('Verbose: failed to write to output file:', e)
            except Exception as e:
                print('Verbose: could not load window or run detector:', e)

        # check whether gap already recorded (be robust to old/malformed CSV rows)
        recorded = False
        for r in manager._read_all():
            r_tf = r.get('timeframe')
            r_start = r.get('start_time') or r.get('start') or ''
            # Try to parse stored start_time and compare to found_time
            try:
                from datetime import datetime
                r_dt = datetime.fromisoformat(r_start) if r_start else None
            except Exception:
                r_dt = None
            if r_tf == tf and r_dt is not None and r_dt == found_time:
                recorded = True
                break
        if not recorded:
            # Prepare a preview message
            preview = f"Found gap {tf} {g['type']} {g['low']} - {g['high']} at {found_time.isoformat()}"
            if args.dry_run:
                # Dry-run: print what would be done and skip recording/sending
                print('Dry-run:', preview)
                if args.output_file:
                    try:
                        with open(args.output_file, 'a') as of:
                            of.write(f"DRY-RUN: {preview}\n")
                    except Exception as e:
                        print('Error writing dry-run to output file:', e)
            else:
                # add gap to CSV
                rec = manager.add_gap(tf, found_time, g['type'], g['low'], g['high'])
                # format short timestamp for messages (include UTC and configured display tz)
                date_str = found_time.strftime('%d%b%y').upper()
                from datetime import timezone
                if found_time.tzinfo is None:
                    found_utc = found_time.replace(tzinfo=timezone.utc)
                else:
                    found_utc = found_time.astimezone(timezone.utc)
                # determine display tz from args if provided
                if args.display_tz:
                    # parse same-style tz strings
                    def _parse_display_tz_local(tzstr: str):
                        try:
                            from zoneinfo import ZoneInfo
                        except Exception:
                            ZoneInfo = None
                        if ZoneInfo is not None:
                            try:
                                return ZoneInfo(tzstr)
                            except Exception:
                                pass
                        if tzstr.upper().startswith('UTC'):
                            off = tzstr[3:]
                            sign = 1
                            if off.startswith('+'):
                                sign = 1
                                off = off[1:]
                            elif off.startswith('-'):
                                sign = -1
                                off = off[1:]
                            parts = off.split(':')
                            try:
                                hours = int(parts[0]) if parts[0] else 0
                                mins = int(parts[1]) if len(parts) > 1 else 0
                                from datetime import timezone, timedelta
                                return timezone(timedelta(hours=sign*hours, minutes=sign*mins))
                            except Exception:
                                return None
                        return None
                    disp_tz = _parse_display_tz_local(args.display_tz)
                    if disp_tz:
                        found_local = found_utc.astimezone(disp_tz)
                    else:
                        found_local = found_utc.astimezone()
                else:
                    found_local = found_utc.astimezone()
                utc_str = found_utc.strftime('%H:%M:%S UTC')
                local_str = found_local.strftime('%H:%M:%S %Z')
                # respect requested format
                if args.display_tz_format == 'local':
                    when = f"@{date_str} - {found_local.strftime('%H:%M %Z')}"
                else:
                    when = f"@{date_str} - {utc_str} ({local_str})"
                msg = f"Gap found {rec.id} {tf} {g['type']} {g['low']} - {g['high']} {when} at {found_time.isoformat()}"
                print('Recording & sending:', msg)
                dm.send_msg(msg, strat='bitcoin-trader')
                if args.output_file:
                    try:
                        with open(args.output_file, 'a') as of:
                            of.write(f"RECORDED: {msg}\n")
                    except Exception as e:
                        print('Error writing record to output file:', e)
        else:
            print('Gap already recorded:', tf, g['time'])

print('Done.')
