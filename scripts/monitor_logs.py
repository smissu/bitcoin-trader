#!/usr/bin/env python3
"""Monitor trader_run.log for errors and gap events and write to monitor_report.log
Run duration is in seconds (default 1800 seconds = 30 minutes)
"""
import time
from datetime import datetime, timedelta
from pathlib import Path
import re

LOG = Path('trader_run.log')
REPORT = Path('monitor_report.log')
DURATION = 1800
INTERVAL = 30
PATTERNS = [re.compile(p) for p in [r"ERROR", r"Exception", r"Gap found", r"Gap closed"]]

end_time = datetime.utcnow() + timedelta(seconds=DURATION)
seen = set()

with REPORT.open('a') as rep:
    rep.write(f"\n=== Monitor start: {datetime.utcnow().isoformat()} (duration {DURATION}s) ===\n")

    while datetime.utcnow() < end_time:
        if LOG.exists():
            lines = LOG.read_text().splitlines()
            # Check new lines only
            for i, line in enumerate(lines[-200:]):
                key = (len(lines)-200+i, line)
                if key in seen:
                    continue
                seen.add(key)
                for pat in PATTERNS:
                    if pat.search(line):
                        rep.write(f"{datetime.utcnow().isoformat()} MATCH: {line}\n")
                        rep.flush()
        time.sleep(INTERVAL)

    rep.write(f"=== Monitor end: {datetime.utcnow().isoformat()} ===\n")

print('Monitoring finished; report written to', REPORT)
