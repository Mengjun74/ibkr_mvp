import streamlit as st
import pandas as pd
import duckdb
import time
from pathlib import Path
import sys

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.config import DATA_DIR, LOG_DIR, KILL_SWITCH_FILE, TRADING_SYMBOL

st.set_page_config(page_title="IBKR Algo Dashboard", layout="wide")

# Database Connection - Transient with Retry
def run_query(query: str, as_df: bool = True):
    db_path = str(DATA_DIR / "db" / "trading.duckdb")
    max_retries = 5
    
    for i in range(max_retries):
        try:
            with duckdb.connect(db_path, read_only=True) as conn:
                res = conn.execute(query)
                if as_df:
                    return res.df()
                return res.fetchall()
        except duckdb.IOException:
            time.sleep(0.1 * (i + 1))
        except Exception as e:
            st.error(f"DB Error: {e}")
            return pd.DataFrame() if as_df else []
            
    return pd.DataFrame() if as_df else []

def load_data():
    # Recent Bars - show full day (1000 mins)
    bars = run_query("SELECT * FROM bars_1m ORDER BY time DESC LIMIT 1000")
    if not bars.empty: bars = bars.sort_values('time')
    
    # Recent Signals
    signals = run_query("SELECT * FROM signals ORDER BY timestamp DESC LIMIT 50")
    
    # Strategy State - latest for metrics
    state = run_query("SELECT * FROM strategy_state ORDER BY timestamp DESC LIMIT 1")
    
    # Historical State - for indicators
    state_hist = run_query("SELECT timestamp, orb_high, orb_low, ema20 FROM strategy_state ORDER BY timestamp DESC LIMIT 1000")
    if not state_hist.empty: state_hist = state_hist.sort_values('timestamp')
    
    # Fills & Orders
    fills = run_query("SELECT * FROM fills ORDER BY time DESC LIMIT 50")
    orders = run_query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 50")
    
    return bars, signals, state, state_hist, fills, orders

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

bars_df, signals_df, state_df, state_hist_df, fills_df, orders_df = load_data()

# Top Metrics
col1, col2, col3, col4 = st.columns(4)
current_price = bars_df['close'].iloc[-1] if not bars_df.empty else 0
col1.metric("Current Price", f"{current_price:.2f}")

if not state_df.empty:
    last_state = state_df.iloc[0]
    status = last_state.get('current_state', 'UNKNOWN')
    active_win = last_state.get('active_window', 'N/A')
    orb_h = last_state.get('orb_high')
    orb_l = last_state.get('orb_low')
else:
    status = "WAITING"
    active_win = "N/A"
    orb_h = None
    orb_l = None

col2.metric("Strategy Status", status)
col3.metric("Session", str(active_win))
col4.metric("Current ORB", f"{orb_l:.2f} - {orb_h:.2f}" if orb_l and orb_h else "N/A")

import plotly.graph_objects as go

# Charts
if not bars_df.empty:
    st.subheader(f"Interactive Chart ({TRADING_SYMBOL})")
    
    # Create figure
    fig = go.Figure()
    
    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=bars_df['time'],
        open=bars_df['open'],
        high=bars_df['high'],
        low=bars_df['low'],
        close=bars_df['close'],
        name='Price'
    ))
    
    # 2. Indicators from State History (Aligned to Market Time)
    if not state_hist_df.empty:
        # EMA20 - Aligned to market timestamp
        fig.add_trace(go.Scatter(
            x=state_hist_df['timestamp'], 
            y=state_hist_df['ema20'], 
            mode='lines', 
            name='EMA 20',
            line=dict(color='orange', width=2)
        ))
        
        # ORB Levels removed from chart as requested.

    # Layout optimization
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=700,
        margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, width='stretch')
else:
    st.subheader("Market Data & Indicators")
    st.info("No market data found in database. Is the bot running?")

# Signals & AI
col_sig, col_ai = st.columns(2)

with col_sig:
    st.subheader("Recent Signals")
    if not signals_df.empty:
        st.dataframe(signals_df[['timestamp', 'direction', 'entry_price', 'ai_decision']])
    else:
        st.info("No signals generated yet.")

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
