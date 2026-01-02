import duckdb
from pathlib import Path

db_path = Path("data/db/trading.duckdb")
if not db_path.exists():
    print(f"Database file {db_path} does not exist.")
else:
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            # Check tables
            tables = conn.execute("SHOW TABLES").fetchall()
            print(f"Tables: {tables}")
            
            for table in [t[0] for t in tables]:
                count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                print(f"Table {table}: {count} rows")
            
            print("\nChecking Bars around ORB window (06:30-06:45):")
            orb_bars = conn.execute("""
                SELECT time, high, low FROM bars_1m 
                WHERE time BETWEEN '2026-01-02 06:20:00' AND '2026-01-02 07:00:00'
                ORDER BY time ASC
            """).df()
            print(orb_bars)
            
            print("\nStrategy State (Latest 10):")
            print(conn.execute("SELECT timestamp, orb_high, orb_low, ema20, current_state FROM strategy_state ORDER BY timestamp DESC LIMIT 10").df())

    except Exception as e:
        print(f"Error: {e}")
