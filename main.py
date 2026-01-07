import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from config import DISCORD_TOKEN, TRADING_MODE, TRADING_MODE_CHANNEL_2, DISCORD_CHANNEL_ID_2
from discord_scraper import DiscordScraper
from discord_scraper_2 import DiscordScraper2
from message_parser import MessageParser
from message_parser_2 import MessageParser2
from tradier_client import TradierClient
from option_resolver import OptionResolver
from order_executor import OrderExecutor
from db_logger import DBLogger
from position_tracker import PositionTracker
from db_client import DBClient
from size_calculator import SizeCalculator
from ntfy_notifier import send_trade_notification, send_scraper2_entry_notification, send_scraper2_failure_notification
from market_hours import is_market_open

os.makedirs('logs', exist_ok=True)

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
        self.scraper_2 = DiscordScraper2() if DISCORD_CHANNEL_ID_2 else None
        self.parser = MessageParser()
        self.parser_2 = MessageParser2() if DISCORD_CHANNEL_ID_2 else None
        self.tradier_client = TradierClient()
        self.db_client = DBClient()
        self.option_resolver = OptionResolver(self.tradier_client)
        self.db_logger = DBLogger(self.db_client, self.option_resolver)
        self.position_tracker = PositionTracker(self.db_client)
        self.order_executor = OrderExecutor(self.tradier_client, self.position_tracker)
        self.size_calculator = SizeCalculator(self.db_client) if DISCORD_CHANNEL_ID_2 else None
        
        if DISCORD_CHANNEL_ID_2:
            self.tradier_client_2 = TradierClient(TRADING_MODE_CHANNEL_2)
            self.option_resolver_2 = OptionResolver(self.tradier_client_2)
            self.order_executor_2 = OrderExecutor(self.tradier_client_2, self.position_tracker)
        else:
            self.tradier_client_2 = None
            self.option_resolver_2 = None
            self.order_executor_2 = None
        
    async def initialize(self):
        if not DISCORD_TOKEN:
            logger.error("DISCORD_TOKEN not set. Please set it in .env file or environment variable.")
            sys.exit(1)
        
        logger.info(f"Starting trading bot - Channel 1: {TRADING_MODE} mode")
        if DISCORD_CHANNEL_ID_2:
            logger.info(f"Channel 2 trading mode: {TRADING_MODE_CHANNEL_2}")
        await self.scraper.connect()
        if self.scraper_2:
            await self.scraper_2.connect()
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
                        logger.warning(f"Fraction calculation resulted in 0 or negative quantity: {numerator}/{denominator} of {position}. Closing entire position instead.")
                        trade_data["contracts"] = position
                        logger.info(f"Closing entire position: {position} contracts")
                    else:
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
                if price_diff > 0.05:
                    if trade_data["action"] == "BOUGHT" and chain_price < message_price:
                        logger.info(f"Price validation exception: Chain price ${chain_price:.2f} is lower than message price ${message_price:.2f}. Allowing order for better execution.")
                    else:
                        logger.warning(
                            f"Price validation failed: Message price ${message_price:.2f} differs from chain price ${chain_price:.2f} "
                            f"by ${price_diff:.2f} (max allowed: $0.05). Order rejected."
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
                
                if trade_data["action"] == "SOLD" and "price" not in trade_data:
                    logger.info(f"Fetching price for SOLD trade: {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    option_data = self.option_resolver.get_option_price(
                        trade_data["ticker"],
                        trade_data["strike"],
                        trade_data["option_type"]
                    )
                    
                    if option_data:
                        last_price = option_data.get("last")
                        bid = option_data.get("bid", 0) or 0
                        ask = option_data.get("ask", 0) or 0
                        
                        chain_price = None
                        if last_price and float(last_price) > 0:
                            chain_price = float(last_price)
                        elif bid > 0 and ask > 0:
                            chain_price = (float(bid) + float(ask)) / 2.0
                        elif ask > 0:
                            chain_price = float(ask)
                        elif bid > 0:
                            chain_price = float(bid)
                        
                        if chain_price:
                            trade_data["price"] = chain_price
                            logger.info(f"Fetched price for SOLD trade: ${chain_price:.2f}")
                        else:
                            logger.warning(f"Could not determine price for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - bid: {bid}, ask: {ask}, last: {last_price}")
                    else:
                        logger.warning(f"Could not fetch option data for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
            
            order_result = self.order_executor.execute_order(trade_data, option_symbol)
            
            if order_result.get("success"):
                actual_quantity = order_result.get("actual_quantity", trade_data["contracts"])
                trade_data_for_log = trade_data.copy()
                if actual_quantity != trade_data["contracts"]:
                    trade_data_for_log["contracts"] = actual_quantity
                
                self.db_logger.log_trade(message.id, trade_data_for_log, option_symbol, order_result)
                
                try:
                    trading_mode = self.tradier_client.get_trading_mode()
                    send_trade_notification(trade_data_for_log, order_result, trading_mode)
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}", exc_info=True)
                
                price = trade_data_for_log.get("price")
                self.position_tracker.update_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["action"],
                    actual_quantity,
                    price
                )
            else:
                logger.error(f"Order failed: {order_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}", exc_info=True)

    async def run(self):
        self.running = True
        logger.info("Bot started. Monitoring Discord channels...")
        
        while self.running:
            try:
                if not is_market_open():
                    logger.debug("Market is closed. Skipping Discord scraping.")
                    await asyncio.sleep(1)
                    continue
                
                messages = await self.scraper.get_new_messages()
                for message in messages:
                    await self.process_message(message)
                
                if self.scraper_2:
                    messages_2 = await self.scraper_2.get_new_messages()
                    for message in messages_2:
                        await self.process_message_2(message)
                
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

    async def process_message_2(self, message):
        try:
            content = message.content
            logger.info(f"Processing message (scraper 2) {message.id}: {content[:100]}")
            
            if not self.parser_2:
                logger.error("Parser 2 not initialized")
                return
            
            trading_mode_2 = self.tradier_client_2.get_trading_mode() if self.tradier_client_2 else "paper"
            
            trade_data = self.parser_2.parse(content)
            if not trade_data.get("valid"):
                logger.warning(f"Message {message.id} did not match trading format: {content}")
                return
            
            if trade_data.get("error"):
                error_msg = trade_data.get('error', 'Unknown parsing error')
                logger.warning(f"Message {message.id} parsing error: {error_msg}")
                try:
                    send_scraper2_failure_notification(
                        message.id,
                        "parsing_error",
                        error_msg,
                        trade_data,
                        trading_mode_2
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
                return
            
            action = trade_data["action"]
            option_symbol = None
            
            if action == "BOUGHT":
                if "size_indicator" not in trade_data:
                    logger.warning(f"BOUGHT order rejected: No size indicator found in message {message.id}")
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "validation_error",
                            "No size indicator found in BOUGHT order",
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                size_indicator = trade_data["size_indicator"]
                daily_pnl = None
                
                if size_indicator == "LOTTO" or size_indicator == "ROLLUP":
                    daily_pnl = self.db_client.get_daily_pnl()
                    if daily_pnl <= 0:
                        error_msg = f"{size_indicator} trade rejected: Daily P&L is ${daily_pnl:.2f} (must be positive)"
                        logger.warning(error_msg)
                        try:
                            send_scraper2_failure_notification(
                                message.id,
                                "validation_error",
                                error_msg,
                                trade_data,
                                trading_mode_2
                            )
                        except Exception as e:
                            logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                        if self.scraper_2:
                            self.scraper_2.mark_message_processed(message.id)
                        return
                
                option_data = self.option_resolver_2.get_option_price(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if not option_data:
                    error_msg = f"Could not get option price data for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.error(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "data_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
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
                    error_msg = f"Could not determine chain price for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - bid: {bid}, ask: {ask}, last: {last_price}"
                    logger.warning(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "data_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                dollar_amount = self.size_calculator.get_dollar_amount(size_indicator, daily_pnl)
                if dollar_amount is None:
                    error_msg = f"Could not determine dollar amount for size indicator: {size_indicator}"
                    logger.error(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "calculation_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                contracts = self.size_calculator.calculate_contracts(dollar_amount, chain_price)
                if contracts <= 0:
                    error_msg = f"Calculated contracts is 0 or negative for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.warning(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "calculation_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                trade_data["contracts"] = contracts
                trade_data["price"] = chain_price
                
                option_symbol = self.option_resolver_2.resolve_option_symbol_with_expiration(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["expiration_date"]
                )
                
                if not option_symbol:
                    error_msg = f"Could not resolve option symbol for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} exp {trade_data['expiration_date']}"
                    logger.error(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "symbol_resolution_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                logger.info(f"Parsed trade (scraper 2): {trade_data['action']} {trade_data['contracts']} {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} exp {trade_data['expiration_date']} [${dollar_amount:.2f}, {size_indicator}]")
                
            elif action == "SOLD":
                position = self.position_tracker.get_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if position <= 0:
                    error_msg = f"SOLD order rejected: No open position for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.warning(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "validation_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                if trade_data.get("all_out"):
                    trade_data["contracts"] = position
                    logger.info(f"ALL OUT detected: Using current position of {position} contracts")
                elif trade_data.get("use_fraction"):
                    numerator, denominator = trade_data["fraction"]
                    sold_quantity = int(position * numerator / denominator)
                    if sold_quantity <= 0:
                        logger.warning(f"Fraction calculation resulted in 0 or negative quantity: {numerator}/{denominator} of {position}. Closing entire position instead.")
                        trade_data["contracts"] = position
                        logger.info(f"Closing entire position: {position} contracts")
                    else:
                        remaining = position - sold_quantity
                        trade_data["contracts"] = remaining
                        logger.info(f"Fraction detected ({numerator}/{denominator}): Position {position}, selling {sold_quantity}, remaining {remaining} contracts")
                else:
                    error_msg = "SOLD order format not recognized"
                    logger.warning(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "validation_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                option_symbol = self.option_resolver_2.resolve_option_symbol_with_expiration(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["expiration_date"]
                )
                
                if not option_symbol:
                    error_msg = f"Could not resolve option symbol for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} exp {trade_data['expiration_date']}"
                    logger.error(error_msg)
                    try:
                        send_scraper2_failure_notification(
                            message.id,
                            "symbol_resolution_error",
                            error_msg,
                            trade_data,
                            trading_mode_2
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                    if self.scraper_2:
                        self.scraper_2.mark_message_processed(message.id)
                    return
                
                if "price" not in trade_data:
                    option_data = self.option_resolver_2.get_option_price_with_expiration(
                        trade_data["ticker"],
                        trade_data["strike"],
                        trade_data["option_type"],
                        trade_data["expiration_date"]
                    )
                    
                    if option_data:
                        last_price = option_data.get("last")
                        bid = option_data.get("bid", 0) or 0
                        ask = option_data.get("ask", 0) or 0
                        
                        chain_price = None
                        if last_price and float(last_price) > 0:
                            chain_price = float(last_price)
                        elif bid > 0 and ask > 0:
                            chain_price = (float(bid) + float(ask)) / 2.0
                        elif ask > 0:
                            chain_price = float(ask)
                        elif bid > 0:
                            chain_price = float(bid)
                        
                        if chain_price:
                            trade_data["price"] = chain_price
                            logger.info(f"Fetched price for SOLD trade: ${chain_price:.2f}")
                        else:
                            logger.warning(f"Could not determine price for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    else:
                        logger.warning(f"Could not fetch option data for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                
                logger.info(f"Parsed trade (scraper 2): {trade_data['action']} {trade_data['contracts']} {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} exp {trade_data['expiration_date']}")
            else:
                error_msg = f"Unknown action: {action}"
                logger.warning(error_msg)
                try:
                    send_scraper2_failure_notification(
                        message.id,
                        "validation_error",
                        error_msg,
                        trade_data,
                        trading_mode_2
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
                return
            
            if not option_symbol:
                error_msg = f"Option symbol not resolved for {trade_data.get('ticker', 'unknown')} {trade_data.get('strike', 'unknown')}{trade_data.get('option_type', 'unknown')}"
                logger.error(error_msg)
                try:
                    send_scraper2_failure_notification(
                        message.id,
                        "symbol_resolution_error",
                        error_msg,
                        trade_data,
                        trading_mode_2
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
                return
            
            order_result = self.order_executor_2.execute_order(trade_data, option_symbol)
            
            if order_result.get("success"):
                actual_quantity = order_result.get("actual_quantity", trade_data["contracts"])
                trade_data_for_log = trade_data.copy()
                if actual_quantity != trade_data["contracts"]:
                    trade_data_for_log["contracts"] = actual_quantity
                
                self.db_logger.log_trade(message.id, trade_data_for_log, option_symbol, order_result)
                
                try:
                    send_trade_notification(trade_data_for_log, order_result)
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}", exc_info=True)
                
                price = trade_data_for_log.get("price")
                self.position_tracker.update_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"],
                    trade_data["action"],
                    actual_quantity,
                    price
                )
                
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
            else:
                error_msg = order_result.get('error', 'Unknown error')
                logger.error(f"Order failed: {error_msg}")
                try:
                    send_scraper2_failure_notification(
                        message.id,
                        "order_failure",
                        error_msg,
                        trade_data,
                        trading_mode_2
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
                
        except Exception as e:
            logger.error(f"Error processing message (scraper 2) {message.id}: {e}", exc_info=True)
            try:
                trading_mode_2 = self.tradier_client_2.get_trading_mode() if self.tradier_client_2 else "paper"
                send_scraper2_failure_notification(
                    message.id,
                    "processing_error",
                    f"Unexpected error: {str(e)}",
                    None,
                    trading_mode_2
                )
            except Exception as notif_e:
                logger.error(f"Failed to send failure notification: {notif_e}", exc_info=True)
            if self.scraper_2:
                self.scraper_2.mark_message_processed(message.id)

    async def shutdown(self):
        logger.info("Shutting down bot...")
        self.running = False
        if self.scraper.session:
            await self.scraper.close()
        if self.scraper_2 and self.scraper_2.session:
            await self.scraper_2.close()

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

