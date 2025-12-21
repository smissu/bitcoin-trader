import importlib.util
import sys
from pathlib import Path
import pandas as pd
import tempfile

# load module
proj = Path('.').resolve()
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapStrategy = mod.GapStrategy


def mk_df(times, opens, highs, lows, closes):
    df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes}, index=pd.to_datetime(times))
    return df


def test_summarize_recent_gaps(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    symbol = 'BTC_USDT'
    tf = '60M'
    filename = data_dir / f"{symbol.lower()}_{tf.lower()}_pionex.csv"

    # create 6 bars where a gap appears on the 3rd and the 6th
    now = pd.Timestamp.utcnow().floor('T')
    times = [now - pd.Timedelta(minutes=60*i) for i in reversed(range(6))]

    bars = [
        (100, 105, 99, 104),
        (103, 108, 102, 107),
        (109, 112, 109, 111),  # up gap (109 > 108)
        (110, 115, 109, 114),
        (113, 118, 112, 117),
        (120, 125, 120, 122)   # up gap relative to previous
    ]

    df = mk_df(times, [b[0] for b in bars], [b[1] for b in bars], [b[2] for b in bars], [b[3] for b in bars])
    df.to_csv(filename)

    strat = GapStrategy(symbol=symbol, data_dir=str(data_dir), recent_bars=6)
    summary = strat.summarize_recent_gaps(tf, x=6)
    assert summary['count'] == 2
    assert len(summary['gaps']) == 2
    assert 'type' in summary['gaps'][0]
