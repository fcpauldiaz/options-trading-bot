import csv
import os
import sys
import logging
from db_client import DBClient
from db_logger import DBLogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def migrate_csv_to_supabase(csv_file="trades.csv"):
    if not os.path.exists(csv_file):
        logger.warning(f"CSV file {csv_file} does not exist. Nothing to migrate.")
        return
    
    try:
        db_client = DBClient()
        
        logger.info(f"Starting migration from {csv_file} to Supabase database")
        
        with open(csv_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            count = 0
            
            for row in reader:
                try:
                    price = None
                    if "price" in row and row["price"]:
                        try:
                            price = float(row["price"])
                        except (ValueError, TypeError):
                            price = None
                    
                    order_type = "market"
                    if "order_type" in row and row["order_type"]:
                        order_type = row["order_type"]
                    
                    trade_record = {
                        "timestamp": row.get("timestamp", ""),
                        "message_id": row.get("message_id", ""),
                        "ticker": row.get("ticker", ""),
                        "strike": float(row.get("strike", 0)),
                        "option_type": row.get("option_type", ""),
                        "action": row.get("action", ""),
                        "contracts": int(row.get("contracts", 0)),
                        "price": price,
                        "option_symbol": row.get("option_symbol", ""),
                        "order_id": row.get("order_id", "N/A"),
                        "status": row.get("status", "N/A"),
                        "account_id": row.get("account_id", ""),
                        "order_type": order_type
                    }
                    
                    db_client.insert_trade(trade_record)
                    count += 1
                    
                except Exception as e:
                    logger.warning(f"Error migrating row: {e}. Row: {row}")
                    continue
        
        logger.info(f"Successfully migrated {count} trades from CSV to Supabase database")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    migrate_csv_to_supabase()

