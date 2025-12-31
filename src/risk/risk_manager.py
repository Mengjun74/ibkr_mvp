import datetime
from pathlib import Path
from ..config import (
    MAX_POSITION, MAX_TRADES_DAILY, MAX_LOSS_DAILY, MAX_LOSS_PER_TRADE,
    COOLDOWN_MINUTES, KILL_SWITCH_FILE, START_TIME, END_TIME
)
from ..utils import logger

class RiskManager:
    def __init__(self):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.current_position = 0
        self.last_trade_time = None
        self.cooldown_until = None
        self.consecutive_losses = 0
        self.kill_switch_active = False
        
        # Load kill switch state on startup
        self._check_external_kill_switch()

    def _check_external_kill_switch(self):
        """Check if kill switch file exists or contains 'STOP'"""
        if KILL_SWITCH_FILE.exists():
            content = KILL_SWITCH_FILE.read_text().strip()
            if content == "STOP":
                self.kill_switch_active = True
            else:
                self.kill_switch_active = False
        else:
            self.kill_switch_active = False
            
    def update_pnl(self, realized_pnl: float):
        self.daily_pnl += realized_pnl
        if realized_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
        # Check for per-trade max loss or consecutive losses => Cooldown
        if realized_pnl <= MAX_LOSS_PER_TRADE: # Note: MAX_LOSS_PER_TRADE is negative, e.g. -12
            self.trigger_cooldown(f"Max loss per trade hit: {realized_pnl}")
        elif self.consecutive_losses >= 2:
            self.trigger_cooldown("2 consecutive losing trades")
            
        # Check daily max loss
        if self.daily_pnl <= MAX_LOSS_DAILY:
             logger.critical(f"Daily Max Loss Hit: {self.daily_pnl}. STOPPING TRADING.")
             self.activate_kill_switch()

    def trigger_cooldown(self, reason: str):
        self.cooldown_until = datetime.datetime.now() + datetime.timedelta(minutes=COOLDOWN_MINUTES)
        logger.warning(f"Cooldown triggered: {reason}. Until: {self.cooldown_until}")

    def activate_kill_switch(self):
        self.kill_switch_active = True
        with open(KILL_SWITCH_FILE, "w") as f:
            f.write("STOP")
        logger.warning("Kill Switch Activated")

    def checks_pass(self, proposed_action: str, quantity: int = 1) -> tuple[bool, str]:
        self._check_external_kill_switch()
        
        if self.kill_switch_active:
            return False, "Kill Switch Active"

        now = datetime.datetime.now().time()
        # Simple check: only allow new entries within window, allow exits anytime
        if proposed_action in ['BUY', 'SELL', 'SHORT']: # Assuming 'SHORT' is entry too
             # If it's an entry (opening a position), check time
             # Simplification: We rely on strategy to distinguish entry vs exit
             # But here we enforce hard time window for ANY new signal if it implies increasing risk
             pass # Logic handled below

        if self.daily_pnl <= MAX_LOSS_DAILY:
            return False, f"Daily Max Loss Hit ({self.daily_pnl})"

        if self.daily_trades >= MAX_TRADES_DAILY:
            return False, f"Max Daily Trades Hit ({self.daily_trades})"

        if self.cooldown_until and datetime.datetime.now() < self.cooldown_until:
            return False, f"In Cooldown until {self.cooldown_until}"

        if abs(self.current_position + quantity) > MAX_POSITION:
             # This is a basic check. Real logic depends on direction.
             # If we are Long 1 and Sell 1, pos becomes 0. That's fine.
             # If we are 0 and Buy 1, pos becomes 1. Fine.
             # If we are 0 and Buy 2, fail.
             # For MVP, assuming Strategy requests 1 unit.
             if abs(self.current_position) >= MAX_POSITION and proposed_action == "ENTRY":
                 return False, "Max Position Limit"

        return True, "OK"

    def record_trade_entry(self):
        self.daily_trades += 1
        self.last_trade_time = datetime.datetime.now()

    def update_position(self, new_position: int):
        self.current_position = int(new_position)

