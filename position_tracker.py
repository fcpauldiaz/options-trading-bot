import logging
from db_client import DBClient

logger = logging.getLogger(__name__)

class PositionTracker:
    def __init__(self, db_client=None):
        self.db_client = db_client or DBClient()
        self.positions = {}
        self._ensure_tables_exist()
        self.load_positions_from_db()
    
    def _get_position_key(self, ticker, strike, option_type):
        return (ticker.upper(), float(strike), option_type.upper())
    
    def _ensure_tables_exist(self):
        try:
            create_positions_table = """
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_entry_price REAL,
                last_updated TEXT NOT NULL,
                PRIMARY KEY (ticker, strike, option_type)
            )
            """
            
            self.db_client.execute_sync(create_positions_table)
            logger.info("Positions table initialized")
        except Exception as e:
            logger.error(f"Error creating positions table: {e}")
            raise
    
    def load_positions_from_db(self):
        try:
            select_query = """
            SELECT ticker, strike, option_type, quantity, avg_entry_price
            FROM positions
            WHERE quantity > 0
            """
            
            result = self.db_client.execute_sync(select_query)
            
            for row in result.rows:
                ticker = row[0]
                strike = float(row[1])
                option_type = row[2]
                quantity = int(row[3])
                avg_entry_price = float(row[4]) if row[4] is not None else None
                
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
            upsert_query = """
            INSERT INTO positions (ticker, strike, option_type, quantity, avg_entry_price, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, strike, option_type) DO UPDATE SET
                quantity = ?,
                avg_entry_price = ?,
                last_updated = ?
            """
            
            self.db_client.execute_sync(
                upsert_query,
                (
                    ticker.upper(), strike, option_type.upper(),
                    new_quantity, new_avg_price, last_updated,
                    new_quantity, new_avg_price, last_updated
                )
            )
        else:
            delete_query = """
            DELETE FROM positions
            WHERE ticker = ? AND strike = ? AND option_type = ?
            """
            
            self.db_client.execute_sync(
                delete_query,
                (ticker.upper(), strike, option_type.upper())
            )
        
        logger.info(f"Position updated: {ticker} {strike}{option_type} - {action} {quantity} contracts. New position: {new_quantity}, Avg entry: ${new_avg_price:.2f}" if new_avg_price else f"Position updated: {ticker} {strike}{option_type} - {action} {quantity} contracts. New position: {new_quantity}")
