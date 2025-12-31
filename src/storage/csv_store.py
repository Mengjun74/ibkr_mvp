import csv
from pathlib import Path
from datetime import datetime
from ..config import DATA_DIR

class CSVStore:
    def __init__(self):
        pass

    def _get_path(self, category: str, filename: str) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        folder = DATA_DIR / category / today
        folder.mkdir(parents=True, exist_ok=True)
        return folder / filename

    def write_bar(self, bar_data: dict):
        """
        bar_data: {'time': datetime, 'open': float, 'high': ...}
        """
        filepath = self._get_path("market", "MES_1min.csv")
        file_exists = filepath.exists()
        
        fieldnames = ['time', 'open', 'high', 'low', 'close', 'volume']
        
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            # Ensure time is formatted consistently
            row = bar_data.copy()
            if isinstance(row['time'], datetime):
                row['time'] = row['time'].isoformat()
                
            writer.writerow(row)

    def write_signal(self, signal_data: dict):
        filepath = self._get_path("signals", "signals.csv")
        file_exists = filepath.exists()
        
        # Assume keys in signal_data are the headers
        if not signal_data:
            return

        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=signal_data.keys())
            if not file_exists:
                writer.writeheader()
            
            row = signal_data.copy()
            # Serialize non-serializable objects if necessary
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.isoformat()
            
            writer.writerow(row)

    def write_order(self, order_data: dict):
        filepath = self._get_path("orders", "orders.csv")
        file_exists = filepath.exists()
        
        if not order_data:
            return
            
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=order_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(order_data)

    def write_fill(self, fill_data: dict):
        filepath = self._get_path("fills", "fills.csv")
        file_exists = filepath.exists()
        
        if not fill_data:
            return
            
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fill_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(fill_data)
            
    def write_risk_event(self, event_data: dict):
        filepath = self._get_path("risk", "risk_events.csv")
        file_exists = filepath.exists()
        
        if not event_data:
            return
            
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=event_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(event_data)
