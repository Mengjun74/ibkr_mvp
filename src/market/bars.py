from ib_insync import IB, Future, BarData, util
from datetime import datetime
import pandas as pd
from ..config import TRADING_SYMBOL, TRADING_EXCHANGE, TRADING_CURRENCY
from ..storage.csv_store import CSVStore
from ..storage.duckdb_store import DuckDBStore
from ..utils import logger

class BarManager:
    def __init__(self, ib: IB):
        self.ib = ib
        self.contract = Future(symbol=TRADING_SYMBOL, lastTradeDateOrContractMonth='202506', exchange=TRADING_EXCHANGE, currency=TRADING_CURRENCY)
        # Note: Contract month hardcoded for MVP example '202506' (June 2025). 
        # In a real app we'd resolve the front month dynamically.
        
        self.csv_store = CSVStore()
        self.db_store = DuckDBStore()
        self.bars = []
        self.df = pd.DataFrame()
        self.on_bar_update = [] # Callbacks

    def qualify_contract(self):
        logger.info("Qualifying contract...")
        details = self.ib.qualifyContracts(self.contract)
        if not details:
            # Fallback for continuous contract if specific fails
            self.contract = Future(TRADING_SYMBOL, 'CONT', TRADING_EXCHANGE, currency=TRADING_CURRENCY)
            self.ib.qualifyContracts(self.contract)
        logger.info(f"Contract qualified: {self.contract}")

    def start_streaming(self):
        self.qualify_contract()
        
        # Request historical to fill buffer (e.g. 1 day)
        # In ib_insync, reqHistoricalData can keepUpToDate=True
        logger.info("Requesting historical data + streaming...")
        self.bars_list = self.ib.reqHistoricalData(
            self.contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False,
            keepUpToDate=True
        )
        
        self.bars_list.updateEvent += self._on_bar_update_event

    def _on_bar_update_event(self, bars, has_new_bar):
        if has_new_bar:
            last_bar = bars[-1]
            # Process new bar
            bar_dict = {
                'time': last_bar.date,
                'open': last_bar.open,
                'high': last_bar.high,
                'low': last_bar.low,
                'close': last_bar.close,
                'volume': last_bar.volume
            }
            
            # Persist
            self.csv_store.write_bar(bar_dict)
            self.db_store.insert_bar(bar_dict)
            
            # Update local DF
            self.update_df(bars)
            
            # Notify strategies
            for callback in self.on_bar_update:
                callback(bar_dict)

    def update_df(self, bars):
        self.df = util.df(bars)
        if not self.df.empty:
            self.df.set_index('date', inplace=True)

    def get_latest_bars(self, n=50):
        # Prefer DB or Memory? Memory is faster for strategy
        if self.df.empty and self.bars_list:
             self.update_df(self.bars_list)
        return self.df.tail(n)
