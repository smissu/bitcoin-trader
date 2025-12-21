import yfinance as yf

# --------- CONFIG ---------
symbol   = "BTC-USD"     # or "BTC-EUR"
interval = "1h"          # Yahoo does not have native 4h; use 1h and resample later
start    = "2024-01-01"
end      = None          # None = up to latest
outfile  = "btc_1h_yf.csv"
# --------------------------


def main():
    # download OHLCV data
    df = yf.download(
        tickers=symbol,
        interval=interval,
        start=start,
        end=end,
        auto_adjust=False,   # keep raw OHLC
        progress=True,
    )

    if df.empty:
        print("No data returned; check symbol, interval, or date range.")
        return

    print(df.head())
    print(f"\nDownloaded {len(df)} rows of {symbol} ({interval})")

    # save to CSV
    df.to_csv(outfile)
    print(f"Saved to {outfile}")


if __name__ == "__main__":
    main()
