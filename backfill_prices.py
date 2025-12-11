import logging
import sys
from datetime import datetime
from db_client import DBClient
from tradier_client import TradierClient
from option_resolver import OptionResolver

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def extract_price_from_option_data(option_data):
    if not option_data:
        return None
    
    last_price = option_data.get("last")
    bid = option_data.get("bid", 0) or 0
    ask = option_data.get("ask", 0) or 0
    
    if last_price and float(last_price) > 0:
        return float(last_price)
    elif bid > 0 and ask > 0:
        return (float(bid) + float(ask)) / 2.0
    elif ask > 0:
        return float(ask)
    elif bid > 0:
        return float(bid)
    
    return None

def backfill_prices():
    try:
        db_client = DBClient()
        tradier_client = TradierClient()
        option_resolver = OptionResolver(tradier_client)
        
        logger.info("Fetching trades with NULL prices from database...")
        
        result = db_client.execute_sync(
            "SELECT id, ticker, strike, option_type, action, timestamp FROM trades WHERE price IS NULL ORDER BY timestamp ASC"
        )
        
        trades_without_prices = result.rows
        total_trades = len(trades_without_prices)
        
        if total_trades == 0:
            logger.info("No trades with missing prices found. Database is up to date.")
            return
        
        logger.info(f"Found {total_trades} trades with missing prices. Starting backfill...")
        
        updated_count = 0
        failed_count = 0
        
        for i, row in enumerate(trades_without_prices, 1):
            trade_id = row[0]
            ticker = row[1]
            strike = float(row[2])
            option_type = row[3]
            action = row[4]
            timestamp = row[5]
            
            logger.info(f"[{i}/{total_trades}] Processing trade ID {trade_id}: {action} {ticker} {strike}{option_type} (timestamp: {timestamp})")
            
            try:
                option_data = option_resolver.get_option_price(ticker, strike, option_type)
                
                if option_data:
                    price = extract_price_from_option_data(option_data)
                    
                    if price:
                        db_client.execute_sync(
                            "UPDATE trades SET price = ? WHERE id = ?",
                            (price, trade_id)
                        )
                        logger.info(f"  ✓ Updated trade ID {trade_id} with price ${price:.2f}")
                        updated_count += 1
                    else:
                        logger.warning(f"  ✗ Could not extract price from option data for trade ID {trade_id}")
                        failed_count += 1
                else:
                    logger.warning(f"  ✗ Could not fetch option data for trade ID {trade_id}: {ticker} {strike}{option_type}")
                    failed_count += 1
                
            except Exception as e:
                logger.error(f"  ✗ Error processing trade ID {trade_id}: {e}")
                failed_count += 1
                continue
        
        logger.info(f"\nBackfill completed:")
        logger.info(f"  Total trades processed: {total_trades}")
        logger.info(f"  Successfully updated: {updated_count}")
        logger.info(f"  Failed: {failed_count}")
        
    except Exception as e:
        logger.error(f"Error during backfill: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    backfill_prices()
