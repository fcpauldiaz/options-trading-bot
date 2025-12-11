import csv
import os
import logging
from datetime import datetime
from config import get_tradier_account_id

logger = logging.getLogger(__name__)

class CSVLogger:
    def __init__(self, csv_file="trades.csv"):
        self.csv_file = csv_file
        self.fieldnames = [
            "timestamp",
            "message_id",
            "ticker",
            "strike",
            "option_type",
            "action",
            "contracts",
            "option_symbol",
            "order_id",
            "status",
            "account_id"
        ]
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
            logger.info(f"Created CSV file: {self.csv_file}")

    def log_trade(self, message_id, trade_data, option_symbol, order_result):
        try:
            timestamp = datetime.now().isoformat()
            account_id = get_tradier_account_id()
            
            row = {
                "timestamp": timestamp,
                "message_id": str(message_id),
                "ticker": trade_data["ticker"],
                "strike": trade_data["strike"],
                "option_type": trade_data["option_type"],
                "action": trade_data["action"],
                "contracts": trade_data["contracts"],
                "option_symbol": option_symbol,
                "order_id": order_result.get("order_id", "N/A"),
                "status": order_result.get("status", "N/A"),
                "account_id": account_id
            }
            
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(row)
            
            logger.info(f"Logged trade to CSV: {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - Order ID: {order_result.get('order_id', 'N/A')}")
        except Exception as e:
            logger.error(f"Error logging trade to CSV: {e}")

