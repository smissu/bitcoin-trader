import importlib.util
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

# Ensure project root is on sys.path so imports inside the module work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Dynamically import the module with hyphenated filename
spec = importlib.util.spec_from_file_location("bitcoin_trader_mod", PROJECT_ROOT / "bitcoin-trader.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GapStrategy = mod.GapStrategy
GapManager = mod.GapManager


def make_three_bar_csv(path: Path):
    # create three bars where b2 is down and b3 is entirely below b1 -> b2dir should detect a DOWN gap
    t0 = datetime(2025, 12, 21, 9, 0)
    t1 = t0 + timedelta(hours=1)
    t2 = t1 + timedelta(hours=1)
    data = [
        # b1
        {'time': t0, 'open': 95.0, 'high': 100.0, 'low': 90.0, 'close': 96.0},
        # b2 (down)
        {'time': t1, 'open': 95.0, 'high': 96.0, 'low': 85.0, 'close': 85.0},
        # b3 entirely below b1 (gap)
        {'time': t2, 'open': 59.0, 'high': 60.0, 'low': 50.0, 'close': 55.0},
    ]
    df = pd.DataFrame(data).set_index('time')
    df.to_csv(path)


def test_run_scan_dry_run_and_record(tmp_path):
    data_dir = tmp_path
    csv_file = data_dir / 'btc_usdt_60m_pionex.csv'
    make_three_bar_csv(csv_file)

    gs = GapStrategy(symbol='BTC_USDT', data_dir=str(data_dir), recent_bars=5)
    # point gap manager to a temp file so we don't touch repo gaps file
    gs.gap_mgr = GapManager(csv_path=data_dir / 'gaps_test.csv')

    out_file = data_dir / 'out.txt'

    # dry-run first
    res = gs.run_scan('60M', download_latest=False, mode='b2dir', dry_run=True, verbose=True, output_file=str(out_file))
    assert res['count'] == 1
    assert any('DRY-RUN' in a and '60M' in a and 'down' in a for a in res['actions'])

    contents = out_file.read_text()
    assert 'DRY-RUN' in contents

    # now run a real scan that records the gap
    res2 = gs.run_scan('60M', download_latest=False, mode='b2dir', dry_run=False, verbose=False, output_file=str(out_file))
    assert res2['count'] == 1
    # gap should be recorded in gap_mgr
    open_gaps = gs.gap_mgr.list_open_gaps()
    assert len(open_gaps) == 1
    g = open_gaps[0]
    assert g.timeframe == '60M'
    assert g.gap_type == 'down'