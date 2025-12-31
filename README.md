# IBKR Trading Bot MVP

A Minimum Viable Product (MVP) automated trading bot for CME MES futures using Interactive Brokers (IBKR) Gateway, Python, and Streamlit. Features an ORB strategy, AI-based filtering (Gemini), and a real-time dashboard.

## Prerequisites

- **Interactive Brokers Gateway**: Install and configure for Paper Trading.
  - API Settings: Enable "Enable ActiveX and Socket Clients".
  - Port: 4002 (Paper Trading default).
  - Uncheck "Read-Only API" if you want to place orders.
  - Trusted IPs: Add 127.0.0.1.
- **Python 3.11+**
- **Google Gemini API Key**: For AI strategy filtering.

## Installation

1.  Clone/Copy the project.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment:
    ```bash
    cp .env.example .env
    ```
    - Edit `.env` and set your `GEMINI_API_KEY` and `IB_ACCOUNT` (Paper account, e.g., DU...).

## Usage

### 1. Start IB Gateway
Ensure IB Gateway is running and logged in to your Paper Trading account.

### 2. Start the Trading Bot
The bot runs the strategy logic and processes data.
```bash
python -m src.main
```

### 3. Start the Dashboard
The dashboard visualizes the bot's state.
```bash
streamlit run dashboard/app.py
```

## Structure

- `src/`: Source code.
  - `broker/`: IBKR connection.
  - `market/`: Data ingestion (Bars).
  - `strategy/`: ORB Strategy logic.
  - `risk/`: Risk management (limits, kill switch).
  - `ai/`: Gemini AI integration.
  - `storage/`: CSV and DuckDB handling.
- `dashboard/`: Streamlit app.
- `data/`: Stored market data, signals, and DB.
- `logs/`: Application logs.

## Testing

Run connectivity test:
```bash
python scripts/test_connect.py
```

Run unit tests:
```bash
pytest
```
