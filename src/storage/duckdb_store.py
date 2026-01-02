import duckdb
from pathlib import Path
from datetime import datetime
from ..config import DATA_DIR

class DuckDBStore:
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = DATA_DIR / "db" / "trading.duckdb"
        self.db_path = str(db_path)
        self._init_schema()

    def _execute_query(self, query: str, params: tuple = None):
        max_retries = 5
        import time
        
        for i in range(max_retries):
            conn = None
            try:
                conn = duckdb.connect(self.db_path)
                if params:
                    conn.execute(query, params)
                else:
                    conn.execute(query)
                return
            except duckdb.IOException:
                # Locked
                if i < max_retries - 1:
                    time.sleep(0.1 * (i + 1))
                else:
                    raise
            except Exception as e:
                # Log error? 
                raise e
            finally:
                if conn:
                    conn.close()

    def _get_conn(self):
        # We try to avoid direct connection usage where possible
        # But if needed, just return connect.
        # This calls might fail if locked.
        return duckdb.connect(self.db_path)

    def _init_schema(self):
        conn = self._get_conn()
        
        # Bars table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bars_1m (
                time TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume INTEGER,
                PRIMARY KEY (time)
            )
        """)
        
        # Signals table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id VARCHAR,
                timestamp TIMESTAMP,
                symbol VARCHAR,
                direction VARCHAR,
                strategy_name VARCHAR,
                entry_price DOUBLE,
                stop_loss DOUBLE,
                take_profit DOUBLE,
                ai_decision VARCHAR,
                ai_rationale VARCHAR,
                raw_json VARCHAR
            )
        """)

        # Orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER,
                perm_id INTEGER,
                client_id INTEGER,
                symbol VARCHAR,
                action VARCHAR,
                total_quantity DOUBLE,
                order_type VARCHAR,
                lmt_price DOUBLE,
                aux_price DOUBLE,
                status VARCHAR,
                created_at TIMESTAMP
            )
        """)

        # Fills table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                exec_id VARCHAR,
                time TIMESTAMP,
                symbol VARCHAR,
                side VARCHAR,
                shares DOUBLE,
                price DOUBLE,
                perm_id INTEGER,
                commission DOUBLE
            )
        """)

        # Strategy State table (for dashboard)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_state (
                timestamp TIMESTAMP,
                orb_high DOUBLE,
                orb_low DOUBLE,
                ema20 DOUBLE,
                atr14 DOUBLE,
                current_state VARCHAR,
                active_signal_id VARCHAR
            )
        """)

        conn.close()

    def insert_bar(self, bar_data: dict):
        self._execute_query("""
            INSERT OR IGNORE INTO bars_1m (time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            bar_data['time'], bar_data['open'], bar_data['high'], 
            bar_data['low'], bar_data['close'], bar_data['volume']
        ))

    def insert_signal(self, signal_data: dict):
        self._execute_query("""
            INSERT INTO signals 
            (signal_id, timestamp, symbol, direction, strategy_name, 
            entry_price, stop_loss, take_profit, ai_decision, ai_rationale, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_data.get('signal_id'),
            signal_data.get('timestamp'),
            signal_data.get('symbol', 'MES'),
            signal_data.get('base_signal'),
            'ORB',
            signal_data.get('entry_price'),
            signal_data.get('stop_points'),
            signal_data.get('take_points'),
            signal_data.get('ai_decision'),
            signal_data.get('ai_rationale'),
            signal_data.get('raw_json')
        ))

    def insert_order(self, order_data: dict):
        self._execute_query("""
            INSERT INTO orders 
            (order_id, perm_id, client_id, symbol, action, total_quantity, 
            order_type, lmt_price, aux_price, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_data.get('orderId'),
            order_data.get('permId'),
            order_data.get('clientId'),
            order_data.get('symbol'),
            order_data.get('action'),
            order_data.get('totalQuantity'),
            order_data.get('orderType'),
            order_data.get('lmtPrice', 0.0),
            order_data.get('auxPrice', 0.0),
            order_data.get('status'),
            datetime.now()
        ))

    def insert_fill(self, fill_data: dict):
        self._execute_query("""
            INSERT INTO fills
            (exec_id, time, symbol, side, shares, price, perm_id, commission)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fill_data.get('execId'),
            fill_data.get('time'),
            fill_data.get('symbol'),
            fill_data.get('side'),
            fill_data.get('shares'),
            fill_data.get('price'),
            fill_data.get('permId'),
            fill_data.get('commission')
        ))

    def insert_strategy_state(self, state_data: dict):
        self._execute_query("""
            INSERT INTO strategy_state
            (timestamp, orb_high, orb_low, ema20, atr14, current_state, active_signal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(),
            state_data.get('orb_high'),
            state_data.get('orb_low'),
            state_data.get('ema20'),
            state_data.get('atr14'),
            state_data.get('status'),
            state_data.get('signal_id')
        ))

    def get_recent_bars(self, limit=100):
        conn = self._get_conn()
        try:
            return conn.execute(f"""
                SELECT * FROM bars_1m 
                ORDER BY time DESC 
                LIMIT {limit}
            """).df().sort_values('time')
        finally:
            conn.close()
