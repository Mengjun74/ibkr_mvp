from ib_insync import IB, util
from ..config import IB_HOST, IB_PORT, IB_CLIENT_ID
from ..utils import logger
import asyncio

class IBKRClient:
    def __init__(self):
        self.ib = IB()
        self.connected = False

    def connect(self):
        try:
            logger.info(f"Connecting to IBKR at {IB_HOST}:{IB_PORT} id={IB_CLIENT_ID}")
            self.ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
            self.connected = True
            logger.info("Connected to IBKR")
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.connected = False
            raise

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")

    def run(self):
        """Run the event loop"""
        self.ib.run()
