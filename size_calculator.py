import logging
import math

logger = logging.getLogger(__name__)

class SizeCalculator:
    SIZE_AMOUNTS = {
        "LOTTO": 300,
        "SMALL": 1000,
        "GRADE B": 1500,
        "GRADE A": 2500
    }
    
    def __init__(self, db_client=None):
        self.db_client = db_client
    
    def get_dollar_amount(self, size_indicator, daily_pnl=None):
        size_upper = size_indicator.upper()
        
        if size_upper == "LOTTO":
            return self.get_lotto_size(daily_pnl)
        elif size_upper == "ROLLUP":
            return self.get_rollup_size(daily_pnl)
        elif size_upper in self.SIZE_AMOUNTS:
            return self.SIZE_AMOUNTS[size_upper]
        else:
            logger.error(f"Unknown size indicator: {size_indicator}")
            return None
    
    def get_lotto_size(self, daily_pnl):
        if daily_pnl is None or daily_pnl <= 0:
            logger.warning("LOTTO trade rejected: No daily gains or P&L unavailable")
            return None
        
        min_size = 300
        max_size = 600
        
        lotto_amount = daily_pnl * 0.30
        
        if lotto_amount < min_size:
            lotto_amount = min_size
        elif lotto_amount > max_size:
            lotto_amount = max_size
        
        logger.info(f"LOTTO size calculated: ${lotto_amount:.2f} based on daily P&L of ${daily_pnl:.2f}")
        return lotto_amount
    
    def get_rollup_size(self, daily_pnl):
        if daily_pnl is None or daily_pnl <= 0:
            logger.warning("ROLLUP trade rejected: No daily gains or P&L unavailable")
            return None
        
        min_size = 300
        max_size = 750
        
        rollup_amount = daily_pnl * 0.30
        
        if rollup_amount < min_size:
            rollup_amount = min_size
        elif rollup_amount > max_size:
            rollup_amount = max_size
        
        logger.info(f"ROLLUP size calculated: ${rollup_amount:.2f} based on daily P&L of ${daily_pnl:.2f}")
        return rollup_amount
    
    def calculate_contracts(self, dollar_amount, option_price):
        if dollar_amount is None or dollar_amount <= 0:
            logger.error(f"Invalid dollar amount: {dollar_amount}")
            return 0
        
        if option_price is None or option_price <= 0:
            logger.error(f"Invalid option price: {option_price}")
            return 0
        
        cost_per_contract = option_price * 100
        contracts = math.floor(dollar_amount / cost_per_contract)
        
        if contracts <= 0:
            logger.warning(f"Calculated contracts is 0 or negative: dollar_amount=${dollar_amount:.2f}, option_price=${option_price:.2f}")
            return 0
        
        logger.info(f"Calculated {contracts} contracts from ${dollar_amount:.2f} at ${option_price:.2f} per contract")
        return contracts

