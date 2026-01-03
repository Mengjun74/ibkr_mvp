import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy
from ..config import START_TIME, FORCE_CLOSE_TIME, MULTI_ORB_STARTS
from ..ai.gemini_filter import GeminiFilter
from ..utils import logger
from ..storage.duckdb_store import DuckDBStore

class ORBStrategy(BaseStrategy):
    def __init__(self, ai_filter: GeminiFilter):
        super().__init__("ORB_MES_1min")
        self.ai_filter = ai_filter
        self.db_store = DuckDBStore()
        
        # State
        self.orb_high = None
        self.orb_low = None
        self.current_window_start = None
        self.daily_reset_date = None
        self.active_position = None
        
        # Params
        self.ema_period = 20
        self.atr_period = 14
        self.atr_min = 0.6
        self.atr_max = 4.0
        
        # Windows
        self.orb_starts = sorted(MULTI_ORB_STARTS)
        logger.info(f"ORB Strategy initialized with {len(self.orb_starts)} windows: {self.orb_starts}")
        logger.info(f"Trading End / Force Close time set to: {FORCE_CLOSE_TIME}")
        self.trading_end = FORCE_CLOSE_TIME
        
    def _reset_daily(self, current_date):
        logger.info(f"Resetting Strategy for {current_date}")
        self.orb_high = None
        self.orb_low = None
        self.current_window_start = None
        self.daily_reset_date = current_date
        self.active_position = None

    def on_bar(self, df: pd.DataFrame, replaying: bool = False) -> Optional[Dict[str, Any]]:
        if df.empty:
            return None
            
        current_bar = df.iloc[-1]
        current_time = current_bar.name.to_pydatetime() # Index is datetime
        current_date = current_time.date()
        current_time_time = current_time.time()
        
        if self.daily_reset_date != current_date:
            self._reset_daily(current_date)

        signal = None
        # Detect current ORB window
        active_window_start = None
        for start in reversed(self.orb_starts):
            if current_time_time >= start:
                active_window_start = start
                break
        
        if active_window_start and active_window_start != self.current_window_start:
            prefix = "[REPLAY] " if replaying else ""
            logger.info(f"{prefix}New ORB Window detection: {active_window_start}. Cleared previous levels {self.orb_high}/{self.orb_low}")
            
            self.orb_high = None
            self.orb_low = None
            self.current_window_start = active_window_start

        # Calculate Indicators
        # We need enough history. If df is small, return.
        if len(df) < 50:
            return None
            
        df = df.copy()
        df['ema20'] = df['close'].ewm(span=self.ema_period).mean()
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr14'] = df['tr'].rolling(self.atr_period).mean()
        
        latest = df.iloc[-1]
        ema20 = latest['ema20']
        atr14 = latest['atr14']
        
        # Log state for dashboard
        state_log = {
            'orb_high': self.orb_high,
            'orb_low': self.orb_low,
            'ema20': ema20,
            'atr14': atr14,
            'status': 'WAITING',
            'signal_id': None,
            'active_window': self.current_window_start
        }

        if not active_window_start:
            self.db_store.insert_strategy_state(current_time, state_log)
            return None

        orb_end_time = (datetime.combine(datetime.today(), active_window_start) + timedelta(minutes=15)).time()

        # 1. Update ORB
        if active_window_start <= current_time_time < orb_end_time:
            # Accumulating ORB
            if self.orb_high is None:
                self.orb_high = current_bar['high']
                self.orb_low = current_bar['low']
            else:
                self.orb_high = max(self.orb_high, current_bar['high'])
                self.orb_low = min(self.orb_low, current_bar['low'])
            state_log['status'] = 'FORMING_ORB'
            state_log['orb_high'] = self.orb_high
            state_log['orb_low'] = self.orb_low
        
        elif current_time_time >= orb_end_time:
             if current_time_time < self.trading_end:
                 if not self.orb_high:
                     # Should have formed, but maybe data missing
                     state_log['status'] = 'ORB_FAILED'
                 else:
                     state_log['status'] = 'TRADING'
                     
                     # Periodically log monitoring status (every 10 mins)
                     if not replaying and current_time_time.second == 0 and current_time_time.minute % 10 == 0:
                         logger.info(f"Monitoring breakout for {active_window_start} session. Range: {self.orb_low} - {self.orb_high}. Price: {latest['close']}")

                     # Generate Signal checks
                     signal = self._check_entry(latest, ema20, atr14)
                     if signal:
                          # Add AI Filter
                          if replaying:
                              # Skip AI during replay to save quota and avoid old order triggers
                              self.db_store.insert_strategy_state(current_time, state_log)
                              return None

                          context = {
                              'time': str(current_time),
                              'signal': signal['base_signal'],
                              'market_data': {
                                  'close': latest['close'],
                                  'atr14': atr14,
                                  'ema20': ema20,
                                  'dist_orb_high': latest['close'] - self.orb_high,
                                  'dist_orb_low': self.orb_low - latest['close']
                              },
                              'pnl': 0.0,
                              'risk_state': {} 
                          }
                          
                          ai_result = self.ai_filter.analyze_signal(context)
                          signal['ai_decision'] = ai_result['decision']
                          signal['ai_rationale'] = ai_result['rationale']
                          signal['raw_json'] = ai_result.get('raw_json', '')
                          
                          if signal['ai_decision'] == 'DENY':
                              logger.info(f"Signal Denied by AI: {ai_result['rationale']}")
                              signal = None
                          else:
                              logger.info(f"Signal Approved by AI ({signal['ai_decision']})")
                              state_log['active_signal_id'] = signal['signal_id']
                              # Explicitly save signal to DB for dashboard
                              self.db_store.insert_signal(signal)
             else:
                 # Past trading end
                 if not replaying and current_time_time.second == 0 and current_time_time.minute % 5 == 0: # Reduce log spam
                     logger.debug(f"Time {current_time_time} is past Trading End {self.trading_end}. Window {active_window_start} ignored.")
                 state_log['status'] = 'WAITING'

        self.db_store.insert_strategy_state(current_time, state_log)
        return signal

    def _check_entry(self, bar, ema20, atr14) -> Optional[Dict[str, Any]]:
        # Filter: ATR Range
        if not (self.atr_min <= atr14 <= self.atr_max):
            return None
            
        close = bar['close']
        
        # Long
        if (close > self.orb_high + 0.25) and (close > ema20):
             # Basic check to avoid repeating signal same minute? 
             # Logic needs robustness. For MVP, we signal. Executor handles dupes.
             stop_loss = max(2.5, 1.2 * atr14)
             entry_price = close
             
             return {
                 'signal_id': f"{bar.name.isoformat()}_LONG",
                 'timestamp': bar.name.to_pydatetime(),
                 'base_signal': 'BUY',
                 'entry_price': entry_price,
                 'stop_points': stop_loss,
                 'take_points': 1.6 * stop_loss,
                 'orb_high': self.orb_high,
                 'orb_low': self.orb_low
             }

        # Short
        elif (close < self.orb_low - 0.25) and (close < ema20):
             stop_loss = max(2.5, 1.2 * atr14)
             entry_price = close
             
             return {
                 'signal_id': f"{bar.name.isoformat()}_SHORT",
                 'timestamp': bar.name.to_pydatetime(),
                 'base_signal': 'SELL',
                 'entry_price': entry_price,
                 'stop_points': stop_loss,
                 'take_points': 1.6 * stop_loss,
                 'orb_high': self.orb_high,
                 'orb_low': self.orb_low
             }
             
        return None

    def on_tick(self, tick):
        pass
