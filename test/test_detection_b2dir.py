import pandas as pd
import importlib.util
from pathlib import Path

proj = Path('.').resolve()
import sys
sys.path.insert(0, str(proj))
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy


def make_df(rows):
    # rows: list of dicts with keys time, open, close, high, low
    df = pd.DataFrame(rows)
    df = df.set_index(pd.to_datetime(df['time']))
    df = df[['open', 'close', 'high', 'low']]
    return df


def test_b2dir_detects_up_gap():
    rows = [
        {'time': '2025-01-01 00:00', 'open': 100, 'close': 105, 'high': 110, 'low': 95},  # b1
        {'time': '2025-01-01 01:00', 'open': 106, 'close': 108, 'high': 109, 'low': 105},  # b2 up bar
        {'time': '2025-01-01 02:00', 'open': 115, 'close': 118, 'high': 120, 'low': 115},  # b3 entirely above b1.high=110
    ]
    df = make_df(rows)
    g = GapStrategy()
    res = g._detect_gap(df, mode='b2dir')
    assert res is not None
    assert res['type'] == 'up'
    assert res['gap_low'] == 110
    assert res['gap_high'] == 115


def test_b2dir_detects_down_gap():
    rows = [
        {'time': '2025-01-02 00:00', 'open': 200, 'close': 195, 'high': 205, 'low': 190},  # b1
        {'time': '2025-01-02 01:00', 'open': 194, 'close': 190, 'high': 195, 'low': 189},  # b2 down bar
        {'time': '2025-01-02 02:00', 'open': 180, 'close': 178, 'high': 182, 'low': 176},  # b3 entirely below b1.low=190
    ]
    df = make_df(rows)
    g = GapStrategy()
    res = g._detect_gap(df, mode='b2dir')
    assert res is not None
    assert res['type'] == 'down'
    assert res['gap_low'] == 182
    assert res['gap_high'] == 190


def test_b2dir_no_gap_real_example():
    # Use the real 2025-12-21 00:00,01:00,02:00 snippet where b2 is down but b3 intersects b1
    rows = [
        {'time':'2025-12-21 00:00:00','open':88360.91,'close':88387.93,'high':88433.64,'low':88306.0},
        {'time':'2025-12-21 01:00:00','open':88387.93,'close':88011.84,'high':88387.93,'low':88011.83},
        {'time':'2025-12-21 02:00:00','open':88011.84,'close':87943.76,'high':88149.99,'low':87869.35},
    ]
    df = make_df(rows)
    g = GapStrategy()
    res = g._detect_gap(df, mode='b2dir')
    assert res is not None
    assert res['type'] == 'down'
    # gap_low should be b3.high, gap_high should be b1.low
    assert res['gap_low'] == 88149.99
    assert res['gap_high'] == 88306.0
