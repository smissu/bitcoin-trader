import backtrader as bt
import argparse

class ThreeBarGapBTC(bt.Strategy):
    params = dict(
        risk_pct=0.01,     # optional: risk per trade (position sizing stub)
        use_market_entry=False,  # use market order on next bar instead of Stop
    )

    def __init__(self):
        self.entry_ord = None
        self.tp_ord = None
        self.sl_ord = None
        # simple trade counters
        self.trades_closed = 0
        self.trades_won = 0
        self.trades_lost = 0
        self.pnl_total = 0.0
        # diagnostics
        self.bars_processed = 0
        self.signals_detected = 0
        self.signals = []  # store (dt, entry, tp, sl) for post-run inspection

    def log(self, txt):
        dt = self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} - {txt}')

    def cancel_exits(self):
        for o in [self.tp_ord, self.sl_ord]:
            if o and o.alive():
                self.cancel(o)
        self.tp_ord, self.sl_ord = None, None

    def next(self):
        data = self.datas[0]

        # count this bar for diagnostics
        self.bars_processed += 1

        # need at least 3 completed bars for pattern: bar1 = [-3], bar3 = [-1]
        if len(data) < 3:
            return

        # if any pending entry or open position, do nothing here
        if self.entry_ord or self.position:
            return

        # bar1 (three bars ago)
        open1  = data.open[-3]
        high1  = data.high[-3]
        low1   = data.low[-3]
        close1 = data.close[-3]

        # bar3 (one bar ago)
        high3  = data.high[-1]
        low3   = data.low[-1]
        close3 = data.close[-1]

        # --- PATTERN DEFINITION (bullish) ---
        # 1) bar1 red
        cond_bar1_red = close1 < open1

        # 2) upside gap: bar3's high and close stay below bar1's low
        cond_gap = (high3 < low1) and (close3 < low1)

        if cond_bar1_red and cond_gap:
            # store TP and SL levels for when entry fills
            self.tp_price = low1   # target: fill the gap up to bar1 low
            self.sl_price = low3   # stop: below bar3

            # entry as STOP at bar3 high; may trigger on future bars
            self.log(f'SIGNAL: gap long; entry stop={high3:.2f}, tp={self.tp_price:.2f}, sl={self.sl_price:.2f}')
            # count this as a generated signal
            self.signals_detected += 1
            # record signal details
            self.signals.append((self.datas[0].datetime.datetime(0), high3, self.tp_price, self.sl_price))

            if self.p.use_market_entry:
                # create a market order to be executed on the next bar
                self.entry_ord = self.buy(exectype=bt.Order.Market)
            else:
                # create a stop entry at bar3 high (may or may not fill later)
                self.entry_ord = self.buy(
                    exectype=bt.Order.Stop,
                    price=high3,
                )

    def notify_order(self, order):
        # log only useful order events
        st = order.getstatusname()
        self.log(f'ORDER event: id={getattr(order, "ref", None)} status={st} type={order.getordername()} price={getattr(order, "price", None)}')

        if order.status in [order.Submitted, order.Accepted]:
            return

        # entry filled (match by order ref instead of object identity)
        if getattr(order, 'ref', None) == getattr(self.entry_ord, 'ref', None) and order.status == order.Completed:
            self.log(f'ENTRY FILLED @ {order.executed.price:.2f}')

            # send bracket-like exits manually: TP (limit) and SL (stop)
            self.tp_ord = self.sell(
                exectype=bt.Order.Limit,
                price=self.tp_price,
            )
            self.sl_ord = self.sell(
                exectype=bt.Order.Stop,
                price=self.sl_price,
            )

        # entry cancelled / rejected
        if getattr(order, 'ref', None) == getattr(self.entry_ord, 'ref', None) and order.status in [order.Canceled, order.Rejected]:
            self.log('ENTRY CANCELLED / REJECTED')
            self.entry_ord = None

        # exits filled: when one hits, cancel the other
        # exits filled: when one hits, cancel the other
        order_ref = getattr(order, 'ref', None)
        tp_ref = getattr(self.tp_ord, 'ref', None)
        sl_ref = getattr(self.sl_ord, 'ref', None)

        if order_ref in [tp_ref, sl_ref] and order.status == order.Completed:
            side = 'TP' if order_ref == tp_ref else 'SL'
            self.log(f'{side} FILLED @ {order.executed.price:.2f}')
            self.cancel_exits()
            self.entry_ord = None

        # if an exit completed, clear any lingering references
        # clear references when exits are no longer active
        if order_ref in [tp_ref, sl_ref] and order.status in [order.Completed, order.Canceled, order.Rejected]:
            if order_ref == tp_ref:
                self.tp_ord = None
            if order_ref == sl_ref:
                self.sl_ord = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f'TRADE PnL: gross={trade.pnl:.2f}, net={trade.pnlcomm:.2f}')
            # update counters
            self.trades_closed += 1
            self.pnl_total += trade.pnl
            if trade.pnl > 0:
                self.trades_won += 1
            else:
                self.trades_lost += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Backtrader ThreeBarGap backtest')
    parser.add_argument('--csv', default='btc_1h_yf_clean.csv', help='CSV file to load (default: btc_1h_yf_clean.csv)')
    parser.add_argument('--compression', type=int, default=None, help='Bar compression in minutes (e.g. 60 for 1h, 240 for 4h). If omitted infer from filename.')
    parser.add_argument('--market-next', action='store_true', help='Use market-on-next-bar entries')
    args = parser.parse_args()

    # allow overriding strategy default for market entry
    ThreeBarGapBTC.params.use_market_entry = args.market_next

    cerebro = bt.Cerebro()
    csv_file = args.csv
    # infer compression if not specified
    comp = args.compression
    if comp is None:
        if '4h' in csv_file or '4H' in csv_file:
            comp = 240
        else:
            comp = 60

data = bt.feeds.GenericCSVData(
    # use the cleaned CSV (first 3 header rows removed)
    dataname=csv_file,
    dtformat='%Y-%m-%d %H:%M:%S%z',   # note %z for +00:00
    timeframe=bt.TimeFrame.Minutes,
    compression=comp,

    # --- column mapping (0‑based) ---
    datetime=0,       # "Datetime"
    open=5,           # "Open"
    high=3,           # "High"
    low=4,            # "Low"
    close=2,          # "Close"
    volume=6,         # "Volume"
    openinterest=-1,

    # cleaned file already contains only data rows
    headers=False
)

# add data and strategy, then run
cerebro.adddata(data)
cerebro.addstrategy(ThreeBarGapBTC)
# add a trade analyzer to collect trade stats
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='tradeanalyzer')
cerebro.broker.setcash(100000.0)
print('Starting portfolio value:', cerebro.broker.getvalue())
strats = cerebro.run()
print('Final portfolio value:', cerebro.broker.getvalue())

# If the run returned strategy instances, print our simple trade counters
if len(strats) > 0:
    strat = strats[0]
    # print our simple counters if present
    if hasattr(strat, 'trades_closed'):
        print('Trades closed (local):', strat.trades_closed)
        print('Won (local):', strat.trades_won, 'Lost (local):', strat.trades_lost)
        print(f'Total PnL (local): {strat.pnl_total:.2f}')

    # Print final position and any outstanding orders for debugging
    try:
        pos = strat.position
        print('\nFinal position: size=', pos.size, 'price=', getattr(pos, 'price', None))
    except Exception:
        print('\nFinal position: <no position>')

    print('entry_ord:', repr(getattr(strat, 'entry_ord', None)))
    print('tp_ord:', repr(getattr(strat, 'tp_ord', None)))
    print('sl_ord:', repr(getattr(strat, 'sl_ord', None)))

    # Print small diagnostics summary
    if hasattr(strat, 'bars_processed'):
        print('\nTotal bars processed:', strat.bars_processed)
    if hasattr(strat, 'signals_detected'):
        print('Signals detected:', strat.signals_detected)
        if hasattr(strat, 'signals') and len(strat.signals) > 0:
            print('\nSignals (timestamp, entry, tp, sl):')
            for dt, entry, tp, sl in strat.signals:
                print(f' - {dt.isoformat()} entry={entry:.2f} tp={tp:.2f} sl={sl:.2f}')

    # show the last datetime processed for the main data feed
    try:
        last_dt = strat.datas[0].datetime.datetime(0)
        print('\nLast bar processed by strategy:', last_dt.isoformat())
    except Exception:
        print('\nLast bar processed by strategy: <unknown>')

    # print analyzer summary if available
    if hasattr(strat, 'analyzers') and hasattr(strat.analyzers, 'tradeanalyzer'):
        ta = strat.analyzers.tradeanalyzer.get_analysis()
        total = ta.get('total', {})
        won = ta.get('won', {})
        lost = ta.get('lost', {})
        pnl = ta.get('pnl', {})

        print('\nTradeAnalyzer summary:')
        print('Total closed:', total.get('closed', 0))
        print('Total won:', total.get('won', 0), 'Total lost:', total.get('lost', 0))
        if 'won' in ta and 'total' in won:
            print('Won total:', won.get('total', 0.0))
        if 'lost' in ta and 'total' in lost:
            print('Lost total:', lost.get('total', 0.0))
        if 'net' in pnl:
            print('Net PnL:', pnl.get('net', 0.0))