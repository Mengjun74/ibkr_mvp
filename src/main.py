import asyncio
import sys
import logging
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.config import IB_HOST, IB_PORT, IB_CLIENT_ID
from src.utils import logger
from src.broker.ibkr_client import IBKRClient
from src.market.bars import BarManager
from src.strategy.orb_strategy import ORBStrategy
from src.risk.risk_manager import RiskManager
from src.execution.executor import Executor
from src.ai.gemini_filter import GeminiFilter

async def main():
    logger.info("Starting IBKR Algo Bot...")
    
    # 1. Initialize Components
    risk_manager = RiskManager()
    ai_filter = GeminiFilter()
    
    ib_client = IBKRClient()
    
    # 2. Connect
    try:
        ib_client.connect()
    except Exception:
        logger.critical("Could not connect to IBKR. Exiting.")
        return

    # 3. Setup Market Data
    bar_manager = BarManager(ib_client.ib)
    
    # 4. Setup Strategy
    strategy = ORBStrategy(ai_filter)
    
    # 5. Setup Executor
    executor = Executor(ib_client, risk_manager)
    
    # 6. Wiring
    # Bar Update -> Strategy.on_bar
    def on_bar_wrapper(bar_dict):
        # We need the full dataframe for strategy
        df = bar_manager.get_latest_bars(100)
        signal = strategy.on_bar(df)
        
        if signal:
            logger.info(f"SIGNAL GENERATED: {signal['base_signal']} @ {signal['entry_price']}")
            executor.process_signal(signal, bar_manager.contract)
    
    bar_manager.on_bar_update.append(on_bar_wrapper)
    
    # 7. Start Streaming
    bar_manager.start_streaming()
    
    # 8. Keep Alive
    logger.info("Bot Running. Press Ctrl+C to stop.")
    try:
        # ib_insync's ib.run() is blocking, but we are in async main.
        # We should use ib.run() if not in async, or await ib.runAsync() ??
        # ib_insync 'run' method starts the loop. If we are in async def, we assume loop is running?
        # Standard: use ib.run() at top level if synchronous. 
        # Or await asyncio.sleep() loop here?
        # Since we are already in asyncio.run(main()), let's just keep alive.
        while True:
            await asyncio.sleep(1)
            ib_client.ib.sleep(1) # Pump events
            
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        ib_client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
