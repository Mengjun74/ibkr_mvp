import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
ROOT_PATH = Path(__file__).parent.parent
sys.path.append(str(ROOT_PATH))

# Import module to ensure it's loaded for patching
try:
    import src.market.bars
except ImportError as e:
    print(f"ImportError during setup: {e}")
    sys.exit(1)

def test_contract_logic():
    print("Testing Contract Logic...")
    
    # Mock IB
    mock_ib = MagicMock()
    
    # Test 1: STK
    print("Test 1: STK (Stock)")
    # We must patch where it is used. In bars.py, TRADING_SEC_TYPE is imported from config.
    # But wait, in bars.py we did `from ..config import ...`
    # So `TRADING_SEC_TYPE` is a name in `market.bars` namespace.
    # So patching `market.bars.TRADING_SEC_TYPE` should work IF `market.bars` is loaded.
    
    # Test 1: STK
    print("Test 1: STK (Stock)")
    
    with patch("src.market.bars.TRADING_SEC_TYPE", "STK"), \
         patch("src.market.bars.TRADING_SYMBOL", "AAPL"), \
         patch("src.market.bars.TRADING_EXCHANGE", "SMART"), \
         patch("src.market.bars.TRADING_CURRENCY", "USD"):
        
        # Re-import or instantiate
        from src.market.bars import BarManager
        
        bm = BarManager(mock_ib)
        print(f"Contract: {bm.contract}")
        
        if "Stock(symbol='AAPL'" in str(bm.contract):
            print("PASS: Created Stock contract")
        else:
            print(f"FAIL: Expected Stock, got {bm.contract}")

    # Test 2: FUT
    print("\nTest 2: FUT (Future)")
    with patch("src.market.bars.TRADING_SEC_TYPE", "FUT"), \
         patch("src.market.bars.TRADING_SYMBOL", "MES"):
        
        bm = BarManager(mock_ib)
        print(f"Contract: {bm.contract}")
        
        if "Future(symbol='MES'" in str(bm.contract):
            print("PASS: Created Future contract")
        else:
             print(f"FAIL: Expected Future, got {bm.contract}")

if __name__ == "__main__":
    test_contract_logic()
