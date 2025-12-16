import logging
from db_client import DBClient

logger = logging.getLogger(__name__)

class PositionTracker:
    def __init__(self, db_client=None):
        self.db_client = db_client or DBClient()
        self.positions = {}
        self.load_positions_from_db()
    
    def _get_position_key(self, ticker, strike, option_type):
        return (ticker.upper(), float(strike), option_type.upper())
    
    def load_positions_from_db(self):
        try:
            positions_data = self.db_client.select_positions(filters={"quantity_gt": 0})
            
            for row in positions_data:
                ticker = row["ticker"]
                strike = float(row["strike"])
                option_type = row["option_type"]
                quantity = int(row["quantity"])
                avg_entry_price = float(row["avg_entry_price"]) if row.get("avg_entry_price") is not None else None
                
                key = self._get_position_key(ticker, strike, option_type)
                self.positions[key] = {
                    "quantity": quantity,
                    "avg_entry_price": avg_entry_price
                }
            
            logger.info(f"Loaded {len(self.positions)} open positions from database")
        except Exception as e:
            logger.error(f"Error loading positions from database: {e}")
    
    def get_position(self, ticker, strike, option_type):
        key = self._get_position_key(ticker, strike, option_type)
        pos = self.positions.get(key)
        return pos["quantity"] if pos else 0
    
    def get_avg_entry_price(self, ticker, strike, option_type):
        key = self._get_position_key(ticker, strike, option_type)
        pos = self.positions.get(key)
        return pos["avg_entry_price"] if pos and pos["avg_entry_price"] else None
    
    def can_sell(self, ticker, strike, option_type, quantity):
        available = self.get_position(ticker, strike, option_type)
        return available >= quantity
    
    def get_available_quantity(self, ticker, strike, option_type, requested):
        available = self.get_position(ticker, strike, option_type)
        return min(requested, available) if available > 0 else 0
    
    def _calculate_avg_entry_price(self, ticker, strike, option_type, new_price, new_quantity):
        key = self._get_position_key(ticker, strike, option_type)
        current_pos = self.positions.get(key)
        
        if not current_pos or current_pos["quantity"] <= 0:
            return new_price
        
        current_quantity = current_pos["quantity"]
        current_avg = current_pos["avg_entry_price"] or 0
        
        total_cost = (current_avg * current_quantity) + (new_price * new_quantity)
        total_quantity = current_quantity + new_quantity
        
        return total_cost / total_quantity if total_quantity > 0 else new_price
    
    def update_position(self, ticker, strike, option_type, action, quantity, price=None):
        from datetime import datetime
        
        key = self._get_position_key(ticker, strike, option_type)
        current_pos = self.positions.get(key, {"quantity": 0, "avg_entry_price": None})
        current_quantity = current_pos["quantity"]
        current_avg_price = current_pos["avg_entry_price"]
        
        action_upper = action.upper()
        new_quantity = current_quantity
        new_avg_price = current_avg_price
        
        if action_upper == "BOUGHT":
            if price is not None:
                new_avg_price = self._calculate_avg_entry_price(ticker, strike, option_type, price, quantity)
            new_quantity = current_quantity + quantity
        elif action_upper == "SOLD":
            new_quantity = current_quantity - quantity
            if new_quantity <= 0:
                new_avg_price = None
        else:
            logger.warning(f"Unknown action for position update: {action}")
            return
        
        self.positions[key] = {
            "quantity": new_quantity,
            "avg_entry_price": new_avg_price
        }
        
        last_updated = datetime.now().isoformat()
        
        if new_quantity > 0:
            position_data = {
                "ticker": ticker.upper(),
                "strike": strike,
                "option_type": option_type.upper(),
                "quantity": new_quantity,
                "avg_entry_price": new_avg_price,
                "last_updated": last_updated
            }
            
            self.db_client.upsert_position(position_data)
        else:
            self.db_client.delete_position(ticker.upper(), strike, option_type.upper())
        
        logger.info(f"Position updated: {ticker} {strike}{option_type} - {action} {quantity} contracts. New position: {new_quantity}, Avg entry: ${new_avg_price:.2f}" if new_avg_price else f"Position updated: {ticker} {strike}{option_type} - {action} {quantity} contracts. New position: {new_quantity}")
