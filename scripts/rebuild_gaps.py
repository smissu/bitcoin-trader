#!/usr/bin/env python3
"""Rebuild gaps/gaps.csv by re-scanning historical data files.

Usage: python scripts/rebuild_gaps.py [--mode MODE] [--apply]

This script is conservative: by default it only previews how many gaps would be written.
Use --apply to replace the existing gaps CSV with the rebuilt one (a backup will be made).
"""
import argparse
from pathlib import Path
import importlib.util
import csv
from datetime import datetime

proj = Path('.').resolve()
import sys
sys.path.insert(0, str(proj))
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy
GapManager = mod.GapManager

parser = argparse.ArgumentParser()
parser.add_argument('--mode', default='b2dir', help='Detection mode to use for rebuild')
parser.add_argument('--apply', action='store_true', help='Replace existing gaps CSV with rebuilt one')
parser.add_argument('--data-dir', default='data', help='Data directory to scan')
args = parser.parse_args()

strategy = GapStrategy()
strategy.data_dir = args.data_dir
# We'll write to a temporary gaps file first
tmp_gaps = Path('gaps') / f"gaps.rebuild.{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
manager_tmp = GapManager(csv_path=tmp_gaps)

# scan all data files and detect gaps
files = list(Path(args.data_dir).glob('*_pionex.csv'))
count = 0
for f in files:
    tf = f.name.split('_')[-2].upper() if len(f.name.split('_')) >= 3 else None
    if not tf:
        continue
    import pandas as pd
    df = pd.read_csv(f, index_col=0, parse_dates=True).sort_index()
    for i in range(2, len(df)):
        window = df.iloc[i-2:i+1]
        det = strategy._detect_gap(window, mode=args.mode)
        if det:
            # add to manager_tmp using its data_dir context so the check is consistent
            manager_tmp.add_gap(tf, det['start_time'], det['type'], det['gap_low'], det['gap_high'], data_dir=str(args.data_dir))
            count += 1

print(f"Detected {count} candidate gaps across {len(files)} data files (mode={args.mode})")
if args.apply:
    cur = Path('gaps') / 'gaps.csv'
    if cur.exists():
        bak = cur.parent / f"gaps.backup.rebuild.{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
        cur.rename(bak)
        print(f"Backed up existing gaps CSV to {bak}")
    tmp_gaps.rename(cur)
    print(f"Replaced gaps CSV with rebuilt file ({count} gaps)")
else:
    print('Dry-run: the rebuilt CSV is at', tmp_gaps)
    print('Run with --apply to replace existing gaps CSV (a backup will be created).')
