#!/usr/bin/env python3
"""Short monitored live session for bitcoin gap monitor.
Runs a number of cycles calling process_interval for each timeframe and sends start/stop Discord messages.
"""
import os
import time
import importlib
import importlib.util
from pathlib import Path

# Load .env manually
try:
    with open('.env') as f:
        for ln in f:
            if '=' in ln:
                k,v = ln.split('=',1)
                k=k.strip()
                v=v.strip().strip('"').strip("'")
                os.environ[k]=v
except FileNotFoundError:
    pass

# Ensure project root is on sys.path and load bitcoin-trader module from file
proj = Path('.').resolve()
import sys
sys.path.insert(0, str(proj))
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy

# ensure discord messages picks up env var
import discord.messages as dm
importlib.reload(dm)
# enable messages
dm.output_msgs_flag = True

strategy = GapStrategy()
# Send start message
dm.send_msg('✅ Bitcoin gap monitor: short live test started (2 minutes).', strat='bitcoin-trader', toPrint=True)

# Run cycles
cycles = 4
SLEEP_SECONDS = 30
for i in range(cycles):
    print(f'Cycle {i+1}/{cycles}')
    for tf in strategy.timeframes:
        print(f'  Processing {tf}...')
        try:
            strategy.process_interval(tf)
        except Exception as e:
            print('   Error:', e)
    if i < cycles-1:
        time.sleep(SLEEP_SECONDS)

# Send stop message
dm.send_msg('🛑 Bitcoin gap monitor: short live test finished.', strat='bitcoin-trader', toPrint=True)

# Print gaps summary
gaps_path = Path('gaps/gaps.csv')
if gaps_path.exists():
    print('\nGaps file contents (last 20 rows):')
    for line in gaps_path.read_text().splitlines()[-20:]:
        print(line)
else:
    print('\nNo gaps recorded (gaps/gaps.csv missing)')
