# Sprint: Detection Improvements

Goal: Improve gap detection accuracy by implementing multiple detection modes and testing them on historical data.

Scope:
- Add detection modes: `strict`, `body`, `open`.
- Add unit tests for each mode and edge cases (partial windows, non-overlapping prior bars).
- Add a CLI/config option to choose detection mode and default to `body` (recommended).
- Add a short benchmark/backtest script to run the detectors over historical CSVs and report counts and timestamps.

Tasks:
1. Implement detection variants in `GapStrategy._detect_gap(df, mode='strict')`.
2. Add unit tests (`test/test_detection_variants.py`) covering each variant.
3. Add a small analytics script `scripts/detect_scan.py` that runs the chosen detector over a range and prints summary counts and examples.
4. Update README with explanation of detection modes and recommended default.

Acceptance Criteria
- All detector variants implement the intended logic and are tested.
- Tests pass in CI and locally.
- README documents the modes and trade-offs.

Estimated effort: 1 day (dev + tests + docs)
