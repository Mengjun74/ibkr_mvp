import sys
import math
from pathlib import Path
from ib_insync import IB, Future, Stock, Contract, util

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load config
from src.config import (
    IB_HOST, IB_PORT, IB_CLIENT_ID,
    TRADING_SYMBOL, TRADING_SEC_TYPE, TRADING_EXCHANGE, TRADING_CURRENCY
)

def test_connection():
    print(f"Testing connection to {IB_HOST}:{IB_PORT} ClientId: {IB_CLIENT_ID+1}")
    
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID + 100) # Use different ID
        print("✅ Connection Successful!")
        
        # Create Contract based on Config
        print(f"Testing Market Data Subscription for {TRADING_SYMBOL} ({TRADING_SEC_TYPE})...")
        
        if TRADING_SEC_TYPE == 'FUT':
            # For futures, we might need expiration. For test, hardcode or try continuous? 
            # Or just keep it simple/hardcoded for MES if config is MES, but generic is better.
            # Assuming config might not have expiration, we might default to a manual one or current.
            # But to keep it robust for the user's current MES setup:
            if TRADING_SYMBOL == 'MES':
                contract = Future(TRADING_SYMBOL, '202506', TRADING_EXCHANGE)
            else:
                 # Fallback for other futures if configured
                contract = Future(TRADING_SYMBOL, '202506', TRADING_EXCHANGE)
        elif TRADING_SEC_TYPE == 'STK':
            contract = Stock(TRADING_SYMBOL, TRADING_EXCHANGE, TRADING_CURRENCY)
        else:
            contract = Contract()
            contract.symbol = TRADING_SYMBOL
            contract.secType = TRADING_SEC_TYPE
            contract.exchange = TRADING_EXCHANGE
            contract.currency = TRADING_CURRENCY

        ib.qualifyContracts(contract)
        print(f"Contract Qualified: {contract}")
        
        market_data = ib.reqMktData(contract, '', False, False)
        print("Waiting for data (5s)...")
        
        for _ in range(50):
            ib.sleep(0.1)
            # Check for non-NaN data
            # util.isNan check or math.isnan
            last = market_data.last
            bid = market_data.bid
            ask = market_data.ask
            
            has_data = False
            if last and not math.isnan(last): has_data = True
            if bid and not math.isnan(bid) and bid > 0: has_data = True
            if ask and not math.isnan(ask) and ask > 0: has_data = True

            if has_data:
                print(f"✅ Data Received! Last: {last} Bid: {bid} Ask: {ask}")
                break
        else:
            print("⚠️ No data received (Are you subscribed? Market open?). values: ", market_data)
            
        ib.disconnect()
        
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    test_connection()
