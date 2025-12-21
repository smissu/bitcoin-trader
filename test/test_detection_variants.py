import importlib.util
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path('.').resolve()))
spec = importlib.util.spec_from_file_location('btmod', Path('.') / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy


def mk_df(times, opens, highs, lows, closes):
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
    }, index=pd.to_datetime(times))
    return df


def test_open_gap_detected():
    now = pd.Timestamp.utcnow()
    times = [now - pd.Timedelta(hours=2), now - pd.Timedelta(hours=1), now]
    b1 = (100, 105, 99, 104)
    b2 = (103, 108, 102, 107)
    b3 = (109, 112, 109, 111)  # open 109 > b2.high 108 -> open-gap

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    gs = GapStrategy()
    assert gs._detect_gap(df, mode='open')['type'] == 'up'


def test_body_gap_detected():
    now = pd.Timestamp.utcnow()
    times = [now - pd.Timedelta(hours=2), now - pd.Timedelta(hours=1), now]
    b1 = (100, 105, 100, 101)
    b2 = (101, 106, 100.5, 105)  # body high 105
    b3 = (106, 110, 106, 109)   # body low 106 > b2.body_high 105 -> up

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    gs = GapStrategy()
    assert gs._detect_gap(df, mode='body')['type'] == 'up'


def test_strict_requires_overlap():
    now = pd.Timestamp.utcnow()
    times = [now - pd.Timedelta(hours=2), now - pd.Timedelta(hours=1), now]
    b1 = (100, 110, 90, 105)
    b2 = (200, 210, 195, 205)  # b1 and b2 do not overlap
    b3 = (211, 215, 211, 213)

    df = mk_df(times, [b1[0], b2[0], b3[0]], [b1[1], b2[1], b3[1]], [b1[2], b2[2], b3[2]], [b1[3], b2[3], b3[3]])

    gs = GapStrategy()
    assert gs._detect_gap(df, mode='strict') is None
