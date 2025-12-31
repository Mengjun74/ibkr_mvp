from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]):
        """
        Process a new bar and return a Signal or None.
        """
        pass

    @abstractmethod
    def on_tick(self, tick: Any):
        pass
