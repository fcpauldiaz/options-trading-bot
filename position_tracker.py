import csv
import os
import logging

logger = logging.getLogger(__name__)

class PositionTracker:
    def __init__(self, csv_file="trades.csv"):
        self.csv_file = csv_file
        self.positions = {}
        self.load_positions_from_csv()

    def _get_position_key(self, ticker, strike, option_type):
        return (ticker.upper(), float(strike), option_type.upper())

    def load_positions_from_csv(self):
        if not os.path.exists(self.csv_file):
            logger.info(f"CSV file {self.csv_file} does not exist. Starting with no positions.")
            return

        try:
            with open(self.csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ticker = row.get("ticker", "").strip()
                        strike = float(row.get("strike", 0))
                        option_type = row.get("option_type", "").strip().upper()
                        action = row.get("action", "").strip().upper()
                        contracts = int(row.get("contracts", 0))

                        if not ticker or not option_type or contracts <= 0:
                            continue

                        key = self._get_position_key(ticker, strike, option_type)

                        if action == "BOUGHT":
                            self.positions[key] = self.positions.get(key, 0) + contracts
                        elif action == "SOLD":
                            self.positions[key] = self.positions.get(key, 0) - contracts

                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping invalid row in CSV: {e}")
                        continue

            total_positions = sum(1 for qty in self.positions.values() if qty > 0)
            logger.info(f"Loaded {total_positions} open positions from {self.csv_file}")
        except Exception as e:
            logger.error(f"Error loading positions from CSV: {e}")

    def get_position(self, ticker, strike, option_type):
        key = self._get_position_key(ticker, strike, option_type)
        return self.positions.get(key, 0)

    def can_sell(self, ticker, strike, option_type, quantity):
        available = self.get_position(ticker, strike, option_type)
        return available >= quantity

    def get_available_quantity(self, ticker, strike, option_type, requested):
        available = self.get_position(ticker, strike, option_type)
        return min(requested, available) if available > 0 else 0

    def update_position(self, ticker, strike, option_type, action, quantity):
        key = self._get_position_key(ticker, strike, option_type)
        current = self.positions.get(key, 0)

        action_upper = action.upper()
        if action_upper == "BOUGHT":
            self.positions[key] = current + quantity
        elif action_upper == "SOLD":
            self.positions[key] = current - quantity
        else:
            logger.warning(f"Unknown action for position update: {action}")

        new_quantity = self.positions[key]
        logger.info(f"Position updated: {ticker} {strike}{option_type} - {action} {quantity} contracts. New position: {new_quantity}")

