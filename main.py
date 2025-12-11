import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from config import DISCORD_TOKEN, TRADING_MODE
from discord_scraper import DiscordScraper
from message_parser import MessageParser
from tradier_client import TradierClient
from option_resolver import OptionResolver
from order_executor import OrderExecutor
from csv_logger import CSVLogger
from position_tracker import PositionTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class DebugMessage:
    def __init__(self, content):
        self.id = 9999999999999999999
        self.content = content

class TradingBot:
    def __init__(self):
        self.running = False
        self.scraper = DiscordScraper()
        self.parser = MessageParser()
        self.tradier_client = TradierClient()
        self.csv_logger = CSVLogger()
        self.position_tracker = PositionTracker()
        self.option_resolver = OptionResolver(self.tradier_client)
        self.order_executor = OrderExecutor(self.tradier_client, self.position_tracker)
        
    async def initialize(self):
        if not DISCORD_TOKEN:
            logger.error("DISCORD_TOKEN not set. Please set it in .env file or environment variable.")
            sys.exit(1)
        
        logger.info(f"Starting trading bot in {TRADING_MODE} mode")
        await self.scraper.connect()
        await asyncio.sleep(2)
        
    async def process_message(self, message):
        try:
            content = message.content
            logger.info(f"Processing message {message.id}: {content[:100]}")
            
            trade_data = self.parser.parse(content)
            if not trade_data.get("valid"):
                logger.warning(f"Message {message.id} did not match trading format: {content}")
                return
            
            if trade_data.get("all_out"):
                position = self.position_tracker.get_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                if position > 0:
                    trade_data["contracts"] = position
                    logger.info(f"ALL OUT detected: Using current position of {position} contracts")
                else:
                    logger.warning(f"ALL OUT detected but no open position for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    return
            
            if trade_data.get("use_fraction"):
                position = self.position_tracker.get_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                if position > 0:
                    numerator, denominator = trade_data["fraction"]
                    sold_quantity = int(position * numerator / denominator)
                    if sold_quantity <= 0:
                        logger.warning(f"Fraction calculation resulted in 0 or negative quantity: {numerator}/{denominator} of {position}")
                        return
                    trade_data["contracts"] = sold_quantity
                    logger.info(f"Fraction detected ({numerator}/{denominator}): Position {position}, selling {sold_quantity} contracts")
                else:
                    logger.warning(f"Fraction detected but no open position for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    return
            
            logger.info(f"Parsed trade: {trade_data['action']} {trade_data['contracts']} {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
            
            option_symbol = None
            if trade_data["action"] == "BOUGHT" and "price" in trade_data:
                message_price = trade_data["price"]
                option_data = self.option_resolver.get_option_price(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if not option_data:
                    logger.error(f"Could not get option price data for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    return
                
                option_symbol = option_data.get("symbol")
                if not option_symbol:
                    logger.error(f"Could not extract option symbol from price data for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    return
                
                chain_price = None
                last_price = option_data.get("last")
                bid = option_data.get("bid", 0) or 0
                ask = option_data.get("ask", 0) or 0
                
                if last_price and last_price > 0:
                    chain_price = float(last_price)
                elif bid > 0 and ask > 0:
                    chain_price = (float(bid) + float(ask)) / 2.0
                elif ask > 0:
                    chain_price = float(ask)
                else:
                    logger.warning(f"Could not determine chain price for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - bid: {bid}, ask: {ask}, last: {last_price}")
                    return
                
                price_diff = abs(message_price - chain_price)
                if price_diff > 0.15:
                    logger.warning(
                        f"Price validation failed: Message price ${message_price:.2f} differs from chain price ${chain_price:.2f} "
                        f"by ${price_diff:.2f} (max allowed: $0.15). Order rejected."
                    )
                    return
                else:
                    logger.info(f"Price validation passed: Message price ${message_price:.2f} vs chain price ${chain_price:.2f} (diff: ${price_diff:.2f})")
            else:
                option_symbol = self.option_resolver.resolve_option_symbol(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if not option_symbol:
                    logger.error(f"Could not resolve option symbol for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    return
            
            order_result = self.order_executor.execute_order(trade_data, option_symbol)
            
            if order_result.get("success"):
                actual_quantity = order_result.get("actual_quantity", trade_data["contracts"])
                trade_data_for_log = trade_data.copy()
                if actual_quantity != trade_data["contracts"]:
                    trade_data_for_log["contracts"] = actual_quantity
                
                self.csv_logger.log_trade(message.id, trade_data_for_log, option_symbol, order_result)
                
                self.position_tracker.update_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["action"],
                    actual_quantity
                )
            else:
                logger.error(f"Order failed: {order_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}", exc_info=True)

    async def run(self):
        self.running = True
        logger.info("Bot started. Monitoring Discord channel...")
        
        while self.running:
            try:
                messages = await self.scraper.get_new_messages()
                for message in messages:
                    await self.process_message(message)
                
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def process_debug_text(self, text):
        logger.info(f"Debug mode: Processing text: {text}")
        debug_message = DebugMessage(text)
        await self.process_message(debug_message)
        logger.info("Debug mode: Processing complete")

    async def shutdown(self):
        logger.info("Shutting down bot...")
        self.running = False
        if self.scraper.session:
            await self.scraper.close()

def signal_handler(signum, frame):
    logger.info("Signal received, shutting down...")
    sys.exit(0)

async def main():
    parser = argparse.ArgumentParser(description="Discord Trading Bot")
    parser.add_argument(
        "--debug",
        type=str,
        help="Debug mode: Parse the provided text instead of scraping Discord messages"
    )
    args = parser.parse_args()
    
    bot = TradingBot()
    
    if args.debug:
        logger.info("Running in DEBUG mode")
        try:
            await bot.process_debug_text(args.debug)
            logger.info("Debug mode finished successfully")
        except Exception as e:
            logger.error(f"Fatal error in debug mode: {e}", exc_info=True)
            sys.exit(1)
    else:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await bot.initialize()
            await bot.run()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await bot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())

