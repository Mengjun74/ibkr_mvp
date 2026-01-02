import streamlit as st
import pandas as pd
import duckdb
import time
from pathlib import Path
import sys

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.config import DATA_DIR, LOG_DIR, KILL_SWITCH_FILE

st.set_page_config(page_title="IBKR Algo Dashboard", layout="wide")

# Database Connection - Transient with Retry
def run_query(query: str, as_df: bool = True):
    db_path = str(DATA_DIR / "db" / "trading.duckdb")
    max_retries = 5
    
    for i in range(max_retries):
        try:
            # Connect, Run, Close
            # read_only=True allows concurrent reads if no writer? 
            # But we want to avoid locking writer.
            # duckdb.connect() context manager automatically closes? Yes.
            with duckdb.connect(db_path, read_only=True) as conn:
                res = conn.execute(query)
                if as_df:
                    return res.df()
                return res.fetchall()
        except duckdb.IOException:
            # Locked. Wait and retry.
            time.sleep(0.1 * (i + 1))
        except Exception as e:
            st.error(f"DB Error: {e}")
            return pd.DataFrame() if as_df else []
            
    return pd.DataFrame() if as_df else []

def load_data():
    # Recent Bars
    bars = run_query("SELECT * FROM bars_1m ORDER BY time DESC LIMIT 100")
    if not bars.empty: bars = bars.sort_values('time')
    
    # Recent Signals
    signals = run_query("SELECT * FROM signals ORDER BY timestamp DESC LIMIT 20")
    
    # Strategy State
    state = run_query("SELECT * FROM strategy_state ORDER BY timestamp DESC LIMIT 1")
    
    # Fills
    fills = run_query("SELECT * FROM fills ORDER BY time DESC LIMIT 20")
    
    # Orders
    orders = run_query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 20")
    
    return bars, signals, state, fills, orders

# Sidebar
st.sidebar.title("Controls")

if st.sidebar.button("Refresh Data"):
    st.rerun()

auto_refresh = st.sidebar.checkbox("Auto Refresh (2s)", value=True)

# Kill Switch
st.sidebar.markdown("---")
st.sidebar.subheader("Risk Control")
ks_status = "ACTIVE" if KILL_SWITCH_FILE.exists() and KILL_SWITCH_FILE.read_text().strip() == "STOP" else "INACTIVE"
st.sidebar.metric("Kill Switch", ks_status)

if st.sidebar.button("ACTIVATE KILL SWITCH"):
    with open(KILL_SWITCH_FILE, "w") as f:
        f.write("STOP")
    st.sidebar.error("KILL SWITCH ACTIVATED")

if st.sidebar.button("RESET KILL SWITCH"):
    if KILL_SWITCH_FILE.exists():
        KILL_SWITCH_FILE.unlink()
    st.sidebar.success("Kill Switch Reset")

# Main Content
st.title("🤖 Algo Trading Dashboard (MES)")

bars_df, signals_df, state_df, fills_df, orders_df = load_data()

# Top Metrics
col1, col2, col3, col4 = st.columns(4)
current_price = bars_df['close'].iloc[-1] if not bars_df.empty else 0
col1.metric("Current Price", f"{current_price:.2f}")

last_state = state_df.iloc[0] if not state_df.empty else None
status = last_state['current_state'] if last_state is not None else "UNKNOWN"
col2.metric("Strategy Status", status)

# Charts
st.subheader("Market Data & Indicators")
if not bars_df.empty and last_state is not None:
    # Overlay lines
    # Streamlit line chart is simple, let's use it for MVP
    chart_data = bars_df[['time', 'close']].set_index('time')
    
    # Add ORB levels if available in state or bars (bars need computing)
    # We display what the strategy SAW (from state log)
    if 'orb_high' in last_state and pd.notnull(last_state['orb_high']):
        chart_data['orb_high'] = last_state['orb_high']
        chart_data['orb_low'] = last_state['orb_low']
    
    if 'ema20' in last_state:
        # This only shows LATEST ema. Ideally we want historical EMA on chart.
        # DB strategy_state has history? Yes.
        # Let's fetch history of state
        # Let's fetch history of state
        state_hist = run_query("SELECT timestamp, orb_high, orb_low, ema20 FROM strategy_state ORDER BY timestamp DESC LIMIT 100")
        if not state_hist.empty:
            state_hist = state_hist.sort_values('timestamp')
        
        # Merge lightly for visualization? Or just plot Close
        st.line_chart(chart_data)

# Signals & AI
col_sig, col_ai = st.columns(2)

with col_sig:
    st.subheader("Recent Signals")
    st.dataframe(signals_df[['timestamp', 'direction', 'entry_price', 'ai_decision']])

with col_ai:
    st.subheader("AI Rationale (Latest)")
    if not signals_df.empty:
        latest_sig = signals_df.iloc[0]
        st.info(f"Signal: {latest_sig['direction']} | AI: {latest_sig['ai_decision']}")
        st.write(f"Rationale: {latest_sig['ai_rationale']}")
        st.json(latest_sig['raw_json'])

# Orders & Fills
st.subheader("Orders & Fills")
tab1, tab2 = st.tabs(["Orders", "Fills"])
with tab1:
    st.dataframe(orders_df)
with tab2:
    st.dataframe(fills_df)

# Logs
st.subheader("System Logs")
log_file = LOG_DIR / "app.log"
if log_file.exists():
    lines = log_file.read_text().splitlines()[-20:]
    st.text("\n".join(lines))

if auto_refresh:
    time.sleep(2)
    st.rerun()
