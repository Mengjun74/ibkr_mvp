from ib_insync import IB, Order, MarketOrder, LimitOrder, StopOrder, Trade
from datetime import datetime
from typing import Dict, Any, Optional

from ..broker.ibkr_client import IBKRClient
from ..risk.risk_manager import RiskManager
from ..storage.duckdb_store import DuckDBStore
from ..storage.csv_store import CSVStore
from ..utils import logger

class Executor:
    def __init__(self, ib_client: IBKRClient, risk_manager: RiskManager):
        self.ib = ib_client.ib
        self.risk_manager = risk_manager
        self.db_store = DuckDBStore()
        self.csv_store = CSVStore()
        self.active_signals = set()
        
        # Subscribe to execution updates
        self.ib.execDetailsEvent += self._on_exec_details

    def process_signal(self, signal: Dict[str, Any], contract):
        """
        signal: {
            'signal_id': str,
            'base_signal': 'BUY'/'SELL',
            'stop_points': float,
            'take_points': float,
            ...
        }
        """
        if not signal:
            return

        sid = signal['signal_id']
        if sid in self.active_signals:
            logger.info(f"Signal {sid} already processed.")
            return

        # Check Risk
        action = signal['base_signal']
        qty = 1 # fixed for MVP
        
        allowed, reason = self.risk_manager.checks_pass("ENTRY", qty)
        if not allowed:
            logger.warning(f"Risk Check Failed for {sid}: {reason}")
            # Log refusal?
            return

        # Execute
        logger.info(f"Executing Signal {sid}: {action} {qty} @ Market")
        
        # Create Bracket Order
        # Parent: Market
        # Children: Stop / Take Profit
        # We need specific prices for SL/TP relative to fill price? 
        # Market order fill price is unknown at submission. 
        # IBKR Bracket with Market Parent? 
        # Usually we attach child orders after fill or use 'Relative' orders. 
        # For simplicity in IBKR API, we can submit a Bracket where parent is Market.
        # However, for Stop/Limit prices of children, we need an absolute price or an offset.
        # IB InSync helps, but we don't know entry price yet.
        # Strategy provided 'entry_price' (current close) as estimate. 
        # We can use that for calculating SL/TP absolute levels, or use relative if supported.
        # Let's use the estimated 'entry_price' from signal to calculate absolute SL/TP levels for the bracket.
        # It's an approximation but standard for "Market entry".
        
        est_entry = signal['entry_price']
        sl_points = signal['stop_points']
        tp_points = signal['take_points']
        
        if action == 'BUY':
             sl_price = est_entry - sl_points
             tp_price = est_entry + tp_points
             parent = MarketOrder('BUY', qty)
        else: # SELL
             sl_price = est_entry + sl_points
             tp_price = est_entry - tp_points
             parent = MarketOrder('SELL', qty)
             
        # Round prices (MES tick size 0.25)
        sl_price = round(sl_price * 4) / 4
        tp_price = round(tp_price * 4) / 4
        
        # Bracket
        bracket = self.ib.bracketOrder(
            action,
            qty,
            limitPrice=0, # Market
            takeProfitPrice=tp_price,
            stopLossPrice=sl_price
        )
        
        # Set Parent to Market
        bracket[0].orderType = 'MKT'
        bracket[0].lmtPrice = 0
        
        # Place Orders
        for o in bracket:
            self.ib.placeOrder(contract, o)
            
        self.active_signals.add(sid)
        self.risk_manager.record_trade_entry()
        
        # Log Orders
        # We can't log IDs yet efficiently until placed, but we can rely on exec details for DB
        logger.info(f"Orders placed for {sid}. SL: {sl_price}, TP: {tp_price}")

    def _on_exec_details(self, trade: Trade, fill):
        """
        Fill detected.
        """
        logger.info(f"Fill: {fill.execution.side} {fill.execution.shares} @ {fill.execution.price}")
        
        # Store
        fill_dict = {
            'execId': fill.execution.execId,
            'time': fill.time,
            'symbol': fill.contract.symbol,
            'side': fill.execution.side,
            'shares': fill.execution.shares,
            'price': fill.execution.price,
            'permId': fill.execution.permId,
            'commission': 0.0 # Paper often 0
        }
        self.csv_store.write_fill(fill_dict)
        self.db_store.insert_fill(fill_dict)
        
        # Update Risk Manager Position
        # We need to reconcile total position.
        # IBKR updates positions automatically, we can poll it or track fills.
        # Safer to read self.ib.positions()
        self._sync_position()
        
        # If Realized PnL is available (from closing trade), update daily PnL
        # getting realized PnL from ib_insync is tricky without PnL events.
        # We can approximate or subscribe to reqPnL.
        # For MVP, let's try to track simple trade output if possible, or rely on PnL subscription in Main.
        
    def _sync_position(self):
        positions = self.ib.positions()
        # Find our symbol
        net_pos = 0
        for p in positions:
            if p.contract.symbol == 'MES': # Simplification
                net_pos += p.position
                
        self.risk_manager.update_position(net_pos)

    def cancel_all(self):
        logger.warning("Cancelling ALL open orders")
        # cancel all
        for trade in self.ib.openTrades():
            self.ib.cancelOrder(trade.order)
