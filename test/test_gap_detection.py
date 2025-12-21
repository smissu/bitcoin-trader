import importlib.util
from datetime import datetime, timedelta
import pandas as pd
import sys, os
from pathlib import Path

import pytest

# Ensure project root is on sys.path so imports inside the module work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Dynamically import the module with hyphenated filename
spec = importlib.util.spec_from_file_location("bitcoin_trader_mod", PROJECT_ROOT / "bitcoin-trader.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GapStrategy = mod.GapStrategy


def mk_df(times, opens, highs, lows, closes, volumes=None):
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes or [0]*len(times),
    }, index=pd.to_datetime(times))
    return df


def test_detects_up_gap():
    # b1 and b2 overlap, b3.low > b2.high -> up gap
    now = datetime.utcnow()
    times = [now - timedelta(minutes=120), now - timedelta(minutes=60), now]
    b1 = (100, 105, 99, 104)
    b2 = (103, 108, 102, 107)
    b3 = (109, 112, 109, 111)  # low 109 > b2.high 108 => up gap

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    strategy = GapStrategy()
    res = strategy._detect_gap(df)
    assert res is not None
    assert res['type'] == 'up'
    assert res['gap_low'] == float(108)
    assert res['gap_high'] == float(109)


def test_detects_down_gap():
    now = datetime.utcnow()
    times = [now - timedelta(minutes=120), now - timedelta(minutes=60), now]
    b1 = (200, 210, 195, 205)
    b2 = (204, 208, 202, 207)
    b3 = (195, 198, 190, 196)  # high 198 < b2.low 202 => down gap

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    strategy = GapStrategy()
    res = strategy._detect_gap(df)
    assert res is not None
    assert res['type'] == 'down'
    assert res['gap_low'] == float(198)
    assert res['gap_high'] == float(202)


def test_no_gap_when_b1_b2_non_overlap():
    now = datetime.utcnow()
    times = [now - timedelta(minutes=120), now - timedelta(minutes=60), now]
    b1 = (300, 305, 295, 304)
    b2 = (400, 405, 395, 404)  # b1 and b2 do not overlap
    b3 = (410, 415, 409, 414)

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    strategy = GapStrategy()
    res = strategy._detect_gap(df)
    assert res is None


def test_no_gap_when_contiguous():
    now = datetime.utcnow()
    times = [now - timedelta(minutes=120), now - timedelta(minutes=60), now]
    b1 = (1000, 1010, 995, 1005)
    b2 = (1004, 1012, 1002, 1008)
    b3 = (1006, 1013, 1005, 1010)  # overlaps with b2, no gap

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    strategy = GapStrategy()
    res = strategy._detect_gap(df)
    assert res is None
