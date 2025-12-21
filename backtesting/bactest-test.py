import backtrader as bt

# --- your strategy (placeholder) ---
class ThreeBarGapBTC(bt.Strategy):
    def next(self):
        # for now just print the first few bars to confirm data is OK
        dt = self.datas[0].datetime.datetime(0)
        o = self.data.open[0]
        h = self.data.high[0]
        l = self.data.low[0]
        c = self.data.close[0]
        v = self.data.volume[0]
        print(dt, o, h, l, c, v)


if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # open the CSV and skip the first 3 header rows (price/ticker/Datetime)
    # write a temporary cleaned CSV that has the first 3 header rows removed
    cleaned = 'btc_1h_yf_clean.csv'
    with open('btc_1h_yf.csv', 'r') as src, open(cleaned, 'w') as dst:
        for _ in range(3):
            next(src)
        for line in src:
            dst.write(line)

    data = bt.feeds.GenericCSVData(
        dataname=cleaned,
        dtformat='%Y-%m-%d %H:%M:%S%z',
        timeframe=bt.TimeFrame.Minutes,
        compression=60,

        datetime=0,
        open=5,
        high=3,
        low=4,
        close=2,
        volume=6,
        openinterest=-1,

        headers=False   # cleaned file contains only data rows
    )

    # add data and (optionally) resample to 4h
    data4h = cerebro.resampledata(
        data,
        timeframe=bt.TimeFrame.Minutes,
        compression=240,   # 4h bars
    )

    cerebro.addstrategy(ThreeBarGapBTC)
    cerebro.run()

