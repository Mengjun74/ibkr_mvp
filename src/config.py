import os
import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
(DATA_DIR / "market").mkdir(exist_ok=True)
(DATA_DIR / "signals").mkdir(exist_ok=True)
(DATA_DIR / "orders").mkdir(exist_ok=True)
(DATA_DIR / "fills").mkdir(exist_ok=True)
(DATA_DIR / "db").mkdir(exist_ok=True)

# IBKR Config
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "10"))
IB_ACCOUNT = os.getenv("IB_ACCOUNT", "")

# AI Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Trading Config
TRADING_SYMBOL = os.getenv("TRADING_SYMBOL", "MES")
TRADING_SEC_TYPE = os.getenv("TRADING_SEC_TYPE", "FUT")
TRADING_EXCHANGE = os.getenv("TRADING_EXCHANGE", "GLOBEX")
TRADING_CURRENCY = os.getenv("TRADING_CURRENCY", "USD")

# Time Config
def _parse_time(env_val: str, default_h: int, default_m: int):
    try:
        if not env_val:
            return datetime.time(default_h, default_m)
        return datetime.datetime.strptime(env_val, "%H:%M").time()
    except Exception:
        return datetime.time(default_h, default_m)

START_TIME = _parse_time(os.getenv("START_TIME"), 6, 30)
END_TIME = _parse_time(os.getenv("END_TIME"), 10, 30)
FORCE_CLOSE_TIME = _parse_time(os.getenv("FORCE_CLOSE_TIME"), 10, 25)

# Multi-ORB Support: comma separated list of times, e.g. "06:30,09:30,12:30,14:30"
MULTI_ORB_STARTS = [
    _parse_time(t.strip(), 0, 0) 
    for t in os.getenv("MULTI_ORB_STARTS", "").split(",") 
    if t.strip()
] or [START_TIME] # Fallback to single START_TIME

# Risk Config
MAX_POSITION = 1
MAX_TRADES_DAILY = int(os.getenv("MAX_TRADES_DAILY", "8"))
MAX_LOSS_DAILY = -60.0
MAX_LOSS_PER_TRADE = -12.0
COOLDOWN_MINUTES = 15
KILL_SWITCH_FILE = DATA_DIR / "kill_switch.txt"

def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")
