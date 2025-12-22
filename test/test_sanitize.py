import importlib.util
from pathlib import Path
from datetime import datetime
import pandas as pd
import csv

# load module
proj = Path('.').resolve()
spec = importlib.util.spec_from_file_location('btmod', proj / 'bitcoin-trader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GapManager = mod.GapManager


def make_dummy_data(path: Path):
    # Create a small data CSV with reasonable prices
    idx = pd.date_range('2025-12-21 00:00', periods=10, freq='H')
    df = pd.DataFrame({
        'open': [50000 + i * 100 for i in range(10)],
        'high': [50100 + i * 100 for i in range(10)],
        'low': [49900 + i * 100 for i in range(10)],
        'close': [50050 + i * 100 for i in range(10)],
        'volume': [1 for _ in range(10)]
    }, index=idx)
    df.to_csv(path)


def test_sanitize_removes_unrealistic_and_duplicates(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    # create data csv for timeframe 60M
    data_file = data_dir / 'btc_usdt_60m_pionex.csv'
    make_dummy_data(data_file)

    gaps_dir = tmp_path / 'gaps'
    gaps_dir.mkdir()
    gaps_file = gaps_dir / 'gaps.csv'

    fieldnames = ['id', 'timeframe', 'start_time', 'gap_type', 'gap_low', 'gap_high', 'status', 'found_time', 'closed_time', 'close_price']
    rows = [
        {'id': 'G00001', 'timeframe': '60M', 'start_time': '2025-12-21T09:00:00', 'gap_type': 'up', 'gap_low': '50050', 'gap_high': '50100', 'status': 'open', 'found_time': '2025-12-21T09:05:00', 'closed_time': '', 'close_price': ''},
        # duplicate of first
        {'id': 'G00002', 'timeframe': '60M', 'start_time': '2025-12-21T09:00:00', 'gap_type': 'up', 'gap_low': '50050', 'gap_high': '50100', 'status': 'open', 'found_time': '2025-12-21T09:06:00', 'closed_time': '', 'close_price': ''},
        # unrealistic row
        {'id': 'G00003', 'timeframe': '60M', 'start_time': '2025-12-21T10:00:00', 'gap_type': 'down', 'gap_low': '55', 'gap_high': '104', 'status': 'open', 'found_time': '2025-12-21T10:05:00', 'closed_time': '', 'close_price': ''},
    ]
    with open(gaps_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    gm = GapManager(csv_path=gaps_file)
    removed = gm.sanitize_gaps(data_dir=str(data_dir))

    # two rows removed (one duplicate, one unrealistic)
    assert removed == 2
    remaining = gm._read_all()
    assert len(remaining) == 1
    assert remaining[0]['id'] == 'G00001'

    # dry-run preview should report the same rows (when run against original dataset)
    # recreate the original file and run preview
    with open(gaps_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    preview = gm.sanitize_gaps(data_dir=str(data_dir), dry_run=True)
    assert isinstance(preview, dict)
    assert preview['removed'] == 2
    assert len(preview['rows']) == 2


def test_add_gap_filters_implausible(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    data_file = data_dir / 'btc_usdt_60m_pionex.csv'
    make_dummy_data(data_file)

    gaps_file = tmp_path / 'gaps.csv'
    gm = GapManager(csv_path=gaps_file)

    # implausible
    rec = gm.add_gap('60M', datetime.fromisoformat('2025-12-21T10:00:00'), 'down', 55.0, 104.0, data_dir=str(data_dir))
    assert rec is None

    # plausible
    rec2 = gm.add_gap('60M', datetime.fromisoformat('2025-12-21T11:00:00'), 'up', 50100.0, 50200.0, data_dir=str(data_dir))
    assert rec2 is not None
    rows = gm._read_all()
    assert any(r['id'] == rec2.id for r in rows)
