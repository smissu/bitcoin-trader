#!/usr/bin/env python3
"""Preview and apply sanitization to gaps CSV to remove implausible/duplicate rows.

Usage:
  python scripts/sanitize_gaps.py [--apply] [--data-dir DATA_DIR]
"""
import argparse
from pathlib import Path
import importlib.util

proj = Path('.').resolve()
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GM = mod.GapManager

parser = argparse.ArgumentParser(description='Preview or apply sanitization to gaps CSV')
parser.add_argument('--apply', action='store_true', help='Apply the sanitization (default is dry-run)')
parser.add_argument('--data-dir', default='data', help='Data directory to use for price checks')
args = parser.parse_args()

mgr = GM()
res = mgr.sanitize_gaps(data_dir=args.data_dir, dry_run=True)
print(f"Found {res['removed']} rows that would be removed.")
if res['removed']:
    for r in res['rows']:
        print(r)
    if args.apply:
        n = mgr.sanitize_gaps(data_dir=args.data_dir, dry_run=False)
        print(f"Applied sanitization -> removed {n} rows and backed up original CSV.")
    else:
        print('Run with --apply to perform the removal.')
else:
    print('No problematic rows found.')
