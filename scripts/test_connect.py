import sys
from pathlib import Path
from ib_insync import IB, Future, util

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load config
from src.config import IB_HOST, IB_PORT, IB_CLIENT_ID

def test_connection():
    print(f"Testing connection to {IB_HOST}:{IB_PORT} ClientId: {IB_CLIENT_ID+1}")
    
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID + 100) # Use different ID
        print("✅ Connection Successful!")
        
        # Test Market Data
        print("Testing Market Data Subscription (MES)...")
        contract = Future('MES', '202506', 'GLOBEX')
        ib.qualifyContracts(contract)
        print(f"Contract Qualified: {contract}")
        
        market_data = ib.reqMktData(contract, '', False, False)
        print("Waiting for data (5s)...")
        
        for _ in range(50):
            ib.sleep(0.1)
            if market_data.last or market_data.bid or market_data.ask:
                print(f"✅ Data Received! Last: {market_data.last} Bid: {market_data.bid} Ask: {market_data.ask}")
                break
        else:
            print("⚠️ No data received (Are you subscribed?).")
            
        ib.disconnect()
        
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    test_connection()
