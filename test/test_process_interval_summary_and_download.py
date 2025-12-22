import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import sys

# dynamic import
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
spec = importlib.util.spec_from_file_location("btmod", PROJECT_ROOT / "bitcoin-trader.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GapStrategy = mod.GapStrategy


def make_csv(path: Path, now: datetime):
    # create 5 bars where last bar will be a gap (down) relative to previous
    times = [now - timedelta(hours=4), now - timedelta(hours=3), now - timedelta(hours=2), now - timedelta(hours=1), now]
    data = []
    # b1..b5
    data.append({'time': times[0], 'open': 100, 'high': 105, 'low': 95, 'close': 102})
    data.append({'time': times[1], 'open': 101, 'high': 106, 'low': 100, 'close': 104})
    data.append({'time': times[2], 'open': 103, 'high': 108, 'low': 102, 'close': 107})
    data.append({'time': times[3], 'open': 105, 'high': 110, 'low': 104, 'close': 108})
    # gap bar (down) - entirely below previous
    data.append({'time': times[4], 'open': 50, 'high': 55, 'low': 48, 'close': 52})
    df = pd.DataFrame(data).set_index('time')
    df.to_csv(path)


def test_process_interval_calls_download_and_sends_summary(tmp_path, monkeypatch):
    data_dir = tmp_path
    csv_file = data_dir / 'btc_usdt_60m_pionex.csv'

    now = datetime(2025, 12, 21, 12, 0)
    make_csv(csv_file, now)

    gs = GapStrategy(symbol='BTC_USDT', data_dir=str(data_dir), recent_bars=5, detector_mode='strict')
    # use a temp gaps CSV so tests don't touch repo gaps file
    gs.gap_mgr = mod.GapManager(csv_path=data_dir / 'gaps_test.csv')

    called = {'download': False, 'send_msgs': []}

    # patch downloader.download_latest to set flag
    def fake_download_latest(interval='60M', limit=48):
        called['download'] = True

    monkeypatch.setattr(gs.downloader, 'download_latest', fake_download_latest)

    # patch get_bars to return a 3-bar df that triggers a gap detection
    def fake_get_bars(interval='60M', limit=3, start_time=None, end_time=None):
        # ensure download was called prior to fetching bars
        assert called['download'] is True, "download_latest must be called before get_bars"
        # return last three rows of csv
        import pandas as pd
        df = pd.read_csv(csv_file, index_col=0, parse_dates=True).sort_index()
        return df.tail(3)

    monkeypatch.setattr(gs.downloader, 'get_bars', fake_get_bars)

    # capture send_msg calls
    def fake_send_msg(msg, strat=None):
        called['send_msgs'].append(msg)

    monkeypatch.setattr(mod, 'send_msg', fake_send_msg)

    # run interval
    gs.process_interval('60M')

    assert called['download'] is True
    # should have sent at least two messages: one immediate gap found and one summary
    assert len(called['send_msgs']) >= 2
    summary_msgs = [m for m in called['send_msgs'] if 'gaps in the last' in m or 'No gaps found' in m]
    assert len(summary_msgs) == 1
    assert '1 gaps' in summary_msgs[0] or '1 gap' in summary_msgs[0] or '1 gaps' in summary_msgs[0]
    # gap details should be in the summary message
    assert 'low=' in summary_msgs[0] and 'high=' in summary_msgs[0]