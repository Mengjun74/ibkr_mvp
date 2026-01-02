from ib_insync import IB, Future, Stock, Forex, BarData, util
from datetime import datetime
import pandas as pd
from ..config import TRADING_SYMBOL, TRADING_SEC_TYPE, TRADING_EXCHANGE, TRADING_CURRENCY
from ..storage.csv_store import CSVStore
from ..storage.duckdb_store import DuckDBStore
from ..utils import logger

class BarManager:
    def __init__(self, ib: IB):
        self.ib = ib
        
        if TRADING_SEC_TYPE == "STK":
            self.contract = Stock(symbol=TRADING_SYMBOL, exchange=TRADING_EXCHANGE, currency=TRADING_CURRENCY)
        elif TRADING_SEC_TYPE == "CASH":
            self.contract = Forex(pair=TRADING_SYMBOL)
        else:
            # Default to Future (FUT)
            contract_month = self._get_futures_month()
            logger.info(f"Using Calculated Contract Month: {contract_month}")
            self.contract = Future(symbol=TRADING_SYMBOL, lastTradeDateOrContractMonth=contract_month, exchange=TRADING_EXCHANGE, currency=TRADING_CURRENCY)
        
        self.csv_store = CSVStore()
        self.db_store = DuckDBStore()
        self.bars = []
        self.df = pd.DataFrame()
        self.on_bar_update = [] # Callbacks

    def _get_futures_month(self) -> str:
        """
        Calculates the front expirations for equity index futures (H, M, U, Z).
        Expires 3rd Friday of March (3), June (6), Sep (9), Dec (12).
        Simplification: If today > 15th of expire month, roll to next.
        """
        now = datetime.now()
        year = now.year
        month = now.month
        
        # Quarterly months
        quarters = [3, 6, 9, 12]
        
        target_month = None
        target_year = year
        
        for q in quarters:
            if month < q:
                target_month = q
                break
            elif month == q:
                # If we are in the expire month, check if roughly before expiration.
                # Expiration is 3rd Friday. ~21st max. 
                # To be safe, if day > 10, let's roll? Or assume liquid until near end.
                # Let's say if day > 14 (roughly 2nd full week), we look to next.
                if now.day < 15:
                   target_month = q
                   break
        
        if target_month is None:
            # Next year March
            target_month = 3
            target_year = year + 1
            
        return f"{target_year}{target_month:02d}"

    def qualify_contract(self):
        logger.info("Qualifying contract...")
        details = self.ib.qualifyContracts(self.contract)
        
        if not details:
            if TRADING_SEC_TYPE == "FUT":
                # Fallback for continuous contract if specific fails
                logger.warning(f"Specific future contract failed. Trying continuous contract for {TRADING_SYMBOL}...")
                self.contract = Future(TRADING_SYMBOL, 'CONT', TRADING_EXCHANGE, currency=TRADING_CURRENCY)
                self.ib.qualifyContracts(self.contract)
            else:
                logger.error(f"Failed to qualify contract: {self.contract}")

        logger.info(f"Contract qualified: {self.contract}")

    def start_streaming(self):
        self.qualify_contract()
        
        # Request historical to fill buffer
        # Smart Duration: Look back at least 10 hours OR enough to cover today's first ORB
        # To avoid replaying Jan 1st when it's Jan 2nd noon.
        now = datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_since_day_start = int((now - day_start).total_seconds() / 3600) + 1
        
        # We want at least 4-5 hours for warmup, but also to cover today
        duration_h = max(5, hours_since_day_start)
        duration_str = f"{duration_h} H"
        
        logger.info(f"Requesting {duration_str} of historical data + streaming...")
        self.bars_list = self.ib.reqHistoricalData(
            self.contract,
            endDateTime='',
            durationStr=duration_str,
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False,
            keepUpToDate=True
        )
        
        # Replay history to catch up strategy state
        full_df = util.df(self.bars_list)
        if full_df is not None and not full_df.empty:
            full_df.set_index('date', inplace=True)
            logger.info(f"Replaying {len(full_df)} historical bars to catch up strategy...")
            
            for i in range(len(full_df)):
                # Incrementally populate self.df so get_latest_bars() works correctly during replay
                self.df = full_df.iloc[:i+1]
                
                last_row = full_df.iloc[i]
                bar_dict = {
                    'time': last_row.name,
                    'open': last_row['open'],
                    'high': last_row['high'],
                    'low': last_row['low'],
                    'close': last_row['close'],
                    'volume': last_row['volume']
                }
                
                # Persist
                self.csv_store.write_bar(bar_dict)
                self.db_store.insert_bar(bar_dict)
                
                # Notify strategies
                for callback in self.on_bar_update:
                    callback(bar_dict, replaying=True)
        
        # Connect to live updates
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
                callback(bar_dict, replaying=False)

    def update_df(self, bars):
        df = util.df(bars)
        if df is None:
            self.df = pd.DataFrame()
        else:
            self.df = df
            
        if not self.df.empty:
            self.df.set_index('date', inplace=True)

    def get_latest_bars(self, n=50):
        # Prefer DB or Memory? Memory is faster for strategy
        if self.df.empty and self.bars_list:
             self.update_df(self.bars_list)
        return self.df.tail(n)
