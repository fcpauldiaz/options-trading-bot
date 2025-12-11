import logging
from datetime import datetime
from config import get_tradier_account_id
from db_client import DBClient

logger = logging.getLogger(__name__)

class DBLogger:
    def __init__(self, db_client=None):
        self.db_client = db_client or DBClient()
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        try:
            create_trades_table = """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                message_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                action TEXT NOT NULL,
                contracts INTEGER NOT NULL,
                price REAL,
                option_symbol TEXT NOT NULL,
                order_id TEXT,
                status TEXT,
                account_id TEXT,
                order_type TEXT
            )
            """
            
            self.db_client.execute_sync(create_trades_table)
            logger.info("Trades table initialized")
        except Exception as e:
            logger.error(f"Error creating trades table: {e}")
            raise
    
    def log_trade(self, message_id, trade_data, option_symbol, order_result):
        try:
            timestamp = datetime.now().isoformat()
            account_id = get_tradier_account_id()
            
            price = trade_data.get("price")
            order_type = order_result.get("order_type", "market")
            
            insert_query = """
            INSERT INTO trades (
                timestamp, message_id, ticker, strike, option_type, action,
                contracts, price, option_symbol, order_id, status, account_id, order_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.db_client.execute_sync(
                insert_query,
                (
                    timestamp,
                    str(message_id),
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["action"],
                    trade_data["contracts"],
                    price,
                    option_symbol,
                    order_result.get("order_id", "N/A"),
                    order_result.get("status", "N/A"),
                    account_id,
                    order_type
                )
            )
            
            logger.info(f"Logged trade to database: {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - Order ID: {order_result.get('order_id', 'N/A')}")
        except Exception as e:
            logger.error(f"Error logging trade to database: {e}", exc_info=True)

