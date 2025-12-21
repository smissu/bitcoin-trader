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


def test_summarize_recent_gaps_b2dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    symbol = 'BTC_USDT'
    tf = '60M'
    filename = data_dir / f"{symbol.lower()}_{tf.lower()}_pionex.csv"

    # three-bar window matching the failing example where b2 is down and b3 is entirely below b1 (down gap expected)
    rows = [
        ('2025-12-21 00:00:00', 88360.91, 88433.64, 88306.0, 88387.93),
        ('2025-12-21 01:00:00', 88387.93, 88387.93, 88011.83, 88011.84),
        ('2025-12-21 02:00:00', 88011.84, 88149.99, 87869.35, 87943.76),
    ]
    # NOTE: order is open, high, low, close for our writer
    times = [r[0] for r in rows]
    opens = [r[1] for r in rows]
    highs = [r[2] for r in rows]
    lows = [r[3] for r in rows]
    closes = [r[4] for r in rows]

    df = mk_df(times, opens, highs, lows, closes)
    df.to_csv(filename)

    strat = GapStrategy(symbol=symbol, data_dir=str(data_dir), recent_bars=3)
    summary = strat.summarize_recent_gaps(tf, x=3, mode='b2dir')
    assert summary['count'] == 1
    assert len(summary['gaps']) == 1
    assert summary['gaps'][0]['type'] == 'down'