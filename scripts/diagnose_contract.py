import sys
from pathlib import Path
from ib_insync import IB, Future, Stock, util

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load config
from src.config import IB_HOST, IB_PORT, IB_CLIENT_ID, TRADING_SYMBOL, TRADING_SEC_TYPE

def diagnose():
    ib = IB()
    try:
        print(f"Connecting to {IB_HOST}:{IB_PORT}...")
        ib.connect(IB_HOST, IB_PORT, clientId=99)
        
        print(f"\nSearching for Symbol: {TRADING_SYMBOL} ({TRADING_SEC_TYPE})...")
        
        # 1. Search for matching symbols
        matches = ib.reqMatchingSymbols(TRADING_SYMBOL)
        print(f"Found {len(matches)} matching symbol(s). Showing {TRADING_SEC_TYPE} types:")
        for m in matches:
            c = m.contract
            if c.secType == TRADING_SEC_TYPE or c.secType == 'IND':
                print(f" - Symbol: {c.symbol}, SecType: {c.secType}, PrimaryExchange: {c.primaryExchange}, Currency: {c.currency}")

        # 2. Try to get contract details for a few variations
        variations = []
        if TRADING_SEC_TYPE == 'FUT':
            variations = [
                Future(TRADING_SYMBOL, '202603', 'GLOBEX'),
                Future(TRADING_SYMBOL, '202603', 'CME'),
                Future(TRADING_SYMBOL, 'CONT', 'GLOBEX')
            ]
        elif TRADING_SEC_TYPE == 'STK':
            variations = [Stock(TRADING_SYMBOL, 'SMART', 'USD')]

        print(f"\nTrying to qualify variations...")
        for c in variations:
            try:
                details = ib.reqContractDetails(c)
                if details:
                    print(f"✅ SUCCESS for {c}: Found {len(details)} contract(s)")
                    # Just show the first one
                    full_contract = details[0].contract
                    print(f"   Full Details: {full_contract}")
                    
                    # 3. Test data request
                    print(f"   Testing data request for {full_contract.localSymbol}...")
                    bars = ib.reqHistoricalData(
                        full_contract, endDateTime='', durationStr='60 S',
                        barSizeSetting='1 min', whatToShow='TRADES', useRTH=False
                    )
                    if bars:
                        print(f"   📈 Data Received! Found {len(bars)} bars.")
                    else:
                        print(f"   ❌ No data received. Check subscriptions.")
                else:
                    print(f"❌ FAILED for {c}")
            except Exception as e:
                print(f"❌ ERROR for {c}: {e}")

        ib.disconnect()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    diagnose()
