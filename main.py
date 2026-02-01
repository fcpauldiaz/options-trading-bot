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

log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Logging level set to: {log_level_str} (numeric: {log_level})")

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
        self.parser_2 = MessageParser2()
        self.tradier_client = TradierClient()
        self.db_client = DBClient()
        self.option_resolver = OptionResolver(self.tradier_client)
        self.db_logger = DBLogger(self.db_client, self.option_resolver)
        self.position_tracker = PositionTracker(self.db_client)
        self.order_executor = OrderExecutor(self.tradier_client, self.position_tracker)
        self.size_calculator = SizeCalculator(self.db_client)
        
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
    
    def _calculate_chain_price(self, option_data, use_bid_fallback=False):
        last_price = option_data.get("last")
        bid = option_data.get("bid", 0) or 0
        ask = option_data.get("ask", 0) or 0
        
        if last_price and last_price > 0:
            return float(last_price)
        elif bid > 0 and ask > 0:
            return (float(bid) + float(ask)) / 2.0
        elif ask > 0:
            return float(ask)
        elif use_bid_fallback and bid > 0:
            return float(bid)
        return None
    
    def _clear_option_chain_cache(self, option_resolver, ticker, expiration_date):
        if expiration_date:
            cache_key = f"{ticker}_{expiration_date}"
            if cache_key in option_resolver.chain_cache:
                del option_resolver.chain_cache[cache_key]
                logger.info(f"Cleared cache entry for {cache_key}")
                return True
        return False
        
    async def process_message(self, message):
        try:
            content = message.content
            logger.info(f"Processing message {message.id}: {content[:100]}")
            
            if "SWING" in content.upper():
                logger.info(f"Skipping SWING trade message {message.id}")
                return
            
            if message.is_spacemonkey():
                embed_titles = message.get_embed_titles()
                await self._process_spacemonkey_message(message, content, embed_titles)
                return
            
            trade_data = self.parser.parse(content)
            if not trade_data.get("valid"):
                #logger.warning(f"Message {message.id} did not match trading format: {content}")
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
            
            if trade_data["action"] == "BOUGHT":
                max_contracts = 10
                if trade_data["contracts"] > max_contracts:
                    logger.warning(f"Requested contracts ({trade_data['contracts']}) exceeds maximum ({max_contracts}). Capping to {max_contracts} contracts.")
                    trade_data["contracts"] = max_contracts
            
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
                
                chain_price = self._calculate_chain_price(option_data)
                if chain_price is None:
                    bid = option_data.get("bid", 0) or 0
                    ask = option_data.get("ask", 0) or 0
                    last_price = option_data.get("last")
                    logger.warning(f"Could not determine chain price for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - bid: {bid}, ask: {ask}, last: {last_price}")
                    return
                
                price_diff = abs(message_price - chain_price)
                if price_diff > 0.05:
                    if trade_data["action"] == "BOUGHT" and chain_price < message_price:
                        logger.info(f"Price validation exception: Chain price ${chain_price:.2f} is lower than message price ${message_price:.2f}. Allowing order for better execution.")
                    else:
                        logger.warning(
                            f"Price validation failed: Message price ${message_price:.2f} differs from chain price ${chain_price:.2f} "
                            f"by ${price_diff:.2f} (max allowed: $0.05). Retrying with fresh chain data..."
                        )
                        
                        exp_date = self.option_resolver._find_closest_expiration(trade_data["ticker"])
                        self._clear_option_chain_cache(self.option_resolver, trade_data["ticker"], exp_date)
                        
                        retry_option_data = self.option_resolver.get_option_price(
                            trade_data["ticker"],
                            trade_data["strike"],
                            trade_data["option_type"]
                        )
                        
                        if retry_option_data:
                            retry_chain_price = self._calculate_chain_price(retry_option_data)
                            if retry_chain_price is not None:
                                retry_price_diff = abs(message_price - retry_chain_price)
                                if retry_price_diff > 0.05:
                                    logger.warning(
                                        f"Price validation failed after retry: Message price ${message_price:.2f} differs from chain price ${retry_chain_price:.2f} "
                                        f"by ${retry_price_diff:.2f} (max allowed: $0.05). Order rejected."
                                    )
                                    return
                                else:
                                    logger.info(f"Price validation passed after retry: Message price ${message_price:.2f} vs chain price ${retry_chain_price:.2f} (diff: ${retry_price_diff:.2f})")
                                    chain_price = retry_chain_price
                                    option_data = retry_option_data
                                    option_symbol = retry_option_data.get("symbol")
                            else:
                                logger.warning(
                                    f"Price validation failed: Could not determine chain price after retry. Order rejected."
                                )
                                return
                        else:
                            logger.warning(
                                f"Price validation failed: Could not get option price data after retry. Order rejected."
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
                        chain_price = self._calculate_chain_price(option_data, use_bid_fallback=True)
                        if chain_price:
                            trade_data["price"] = chain_price
                            logger.info(f"Fetched price for SOLD trade: ${chain_price:.2f}")
                        else:
                            bid = option_data.get("bid", 0) or 0
                            ask = option_data.get("ask", 0) or 0
                            last_price = option_data.get("last")
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

    async def _process_spacemonkey_message(self, message, content, embed_titles=None):
        try:
            logger.info(f"Processing spacemonkey message {message.id}: {content[:100]}")
            
            trade_data = self.parser_2.parse_spacemonkey(content, embed_titles)
            if not trade_data.get("valid"):
                logger.warning(f"Spacemonkey message {message.id} did not match format: {content}")
                return
            
            if trade_data.get("error"):
                error_msg = trade_data.get('error', 'Unknown parsing error')
                logger.warning(f"Spacemonkey message {message.id} parsing error: {error_msg}")
                return
            
            action = trade_data["action"]
            option_symbol = None
            
            if action == "BOUGHT":
                if "size_indicator" not in trade_data:
                    logger.warning(f"BOUGHT order rejected: No size indicator found in spacemonkey message {message.id}")
                    return
                
                size_indicator = trade_data["size_indicator"]
                daily_pnl = None
                
                if size_indicator == "LOTTO":
                    daily_pnl = self.db_client.get_daily_pnl()
                    if daily_pnl <= 0:
                        error_msg = f"{size_indicator} trade rejected: Daily P&L is ${daily_pnl:.2f} (must be positive)"
                        logger.warning(error_msg)
                        return
                elif size_indicator == "ROLLUP":
                    daily_pnl = self.db_client.get_daily_pnl()
                
                option_data = self.option_resolver.get_option_price(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if not option_data:
                    error_msg = f"Could not get option price data for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.error(error_msg)
                    return
                
                chain_price = self._calculate_chain_price(option_data)
                if chain_price is None:
                    bid = option_data.get("bid", 0) or 0
                    ask = option_data.get("ask", 0) or 0
                    last_price = option_data.get("last")
                    error_msg = f"Could not determine chain price for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} - bid: {bid}, ask: {ask}, last: {last_price}"
                    logger.warning(error_msg)
                    return
                
                dollar_amount = self.size_calculator.get_dollar_amount(size_indicator, daily_pnl)
                if dollar_amount is None:
                    error_msg = f"Could not determine dollar amount for size indicator: {size_indicator}"
                    logger.error(error_msg)
                    return
                
                contracts = self.size_calculator.calculate_contracts(dollar_amount, chain_price)
                if contracts <= 0:
                    error_msg = f"Calculated contracts is 0 or negative for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.warning(f"{error_msg}. Using minimum 1 contract for entry order.")
                    contracts = 1
                
                max_contracts = 10
                if contracts > max_contracts:
                    logger.warning(f"Calculated contracts ({contracts}) exceeds maximum ({max_contracts}). Capping to {max_contracts} contracts.")
                    contracts = max_contracts
                
                alert_price = trade_data.get("price")
                use_limit_order = False
                if alert_price is not None:
                    price_diff = abs(alert_price - chain_price)
                    if price_diff > 0.30:
                        logger.warning(
                            f"Price validation failed: Alert price ${alert_price:.2f} differs from chain price ${chain_price:.2f} "
                            f"by ${price_diff:.2f} (max allowed: $0.30). Retrying with fresh chain data..."
                        )
                        
                        exp_date = self.option_resolver._find_closest_expiration(trade_data["ticker"])
                        self._clear_option_chain_cache(self.option_resolver, trade_data["ticker"], exp_date)
                        
                        retry_option_data = self.option_resolver.get_option_price(
                            trade_data["ticker"],
                            trade_data["strike"],
                            trade_data["option_type"]
                        )
                        
                        if retry_option_data:
                            retry_chain_price = self._calculate_chain_price(retry_option_data)
                            if retry_chain_price is not None:
                                retry_price_diff = abs(alert_price - retry_chain_price)
                                if retry_price_diff > 0.30:
                                    logger.warning(
                                        f"Price difference still exceeds threshold after retry: Alert price ${alert_price:.2f} differs from chain price ${retry_chain_price:.2f} "
                                        f"by ${retry_price_diff:.2f}. Creating limit order with alert price ${alert_price:.2f}."
                                    )
                                    use_limit_order = True
                                    chain_price = retry_chain_price
                                    option_data = retry_option_data
                                else:
                                    logger.info(f"Price validation passed after retry: Alert price ${alert_price:.2f} vs chain price ${retry_chain_price:.2f} (diff: ${retry_price_diff:.2f})")
                                    chain_price = retry_chain_price
                                    option_data = retry_option_data
                            else:
                                error_msg = f"Price validation failed: Could not determine chain price after retry for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                                logger.warning(error_msg)
                                return
                        else:
                            error_msg = f"Price validation failed: Could not get option price data after retry for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                            logger.warning(error_msg)
                            return
                    else:
                        logger.info(f"Price validation passed: Alert price ${alert_price:.2f} vs chain price ${chain_price:.2f} (diff: ${price_diff:.2f})")
                
                trade_data["contracts"] = contracts
                if alert_price is not None:
                    trade_data["price"] = alert_price
                    if use_limit_order:
                        logger.info(f"Using limit order with parsed alert price ${alert_price:.2f} (chain price: ${chain_price:.2f})")
                    else:
                        logger.info(f"Using limit order with parsed alert price ${alert_price:.2f} (chain price: ${chain_price:.2f}, diff: ${abs(alert_price - chain_price):.2f})")
                else:
                    trade_data["price"] = chain_price
                
                option_symbol = option_data.get("symbol")
                if not option_symbol:
                    error_msg = f"Could not extract option symbol for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.error(error_msg)
                    return
                
                logger.info(f"Parsed spacemonkey trade: {trade_data['action']} {trade_data['contracts']} {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} [${dollar_amount:.2f}, {size_indicator}]")
            elif action == "SOLD":
                position = self.position_tracker.get_position(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if position <= 0:
                    error_msg = f"SOLD order rejected: No open position for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.warning(error_msg)
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
                    return
                
                option_symbol = self.option_resolver.resolve_option_symbol(
                    trade_data["ticker"],
                    trade_data["strike"],
                    trade_data["option_type"]
                )
                
                if not option_symbol:
                    error_msg = f"Could not resolve option symbol for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                    logger.error(error_msg)
                    return
                
                if "price" not in trade_data:
                    logger.info(f"Fetching price for SOLD trade: {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    option_data = self.option_resolver.get_option_price(
                        trade_data["ticker"],
                        trade_data["strike"],
                        trade_data["option_type"]
                    )
                    
                    if option_data:
                        chain_price = self._calculate_chain_price(option_data, use_bid_fallback=True)
                        if chain_price:
                            trade_data["price"] = chain_price
                            logger.info(f"Fetched price for SOLD trade: ${chain_price:.2f}")
                        else:
                            logger.warning(f"Could not determine price for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                    else:
                        logger.warning(f"Could not fetch option data for SOLD trade {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
                
                logger.info(f"Parsed spacemonkey trade: {trade_data['action']} {trade_data['contracts']} {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}")
            else:
                logger.warning(f"Spacemonkey message {message.id} has unsupported action: {action}")
                return
            
            if not option_symbol:
                error_msg = f"Option symbol not resolved for {trade_data.get('ticker', 'unknown')} {trade_data.get('strike', 'unknown')}{trade_data.get('option_type', 'unknown')}"
                logger.error(error_msg)
                return
            
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
                error_msg = order_result.get('error', 'Unknown error')
                logger.error(f"Order failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error processing spacemonkey message {message.id}: {e}", exc_info=True)

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
            
            if "SWING" in content.upper():
                logger.info(f"Skipping SWING trade message {message.id}")
                if self.scraper_2:
                    self.scraper_2.mark_message_processed(message.id)
                return
            
            if not self.parser_2:
                logger.error("Parser 2 not initialized")
                return
            
            trading_mode_2 = self.tradier_client_2.get_trading_mode() if self.tradier_client_2 else "paper"
            
            trade_data = self.parser_2.parse(content)
            if not trade_data.get("valid"):
                #logger.warning(f"Message {message.id} did not match trading format: {content}")
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
                
                if size_indicator == "LOTTO":
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
                elif size_indicator == "ROLLUP":
                    daily_pnl = self.db_client.get_daily_pnl()
                
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
                
                chain_price = self._calculate_chain_price(option_data)
                if chain_price is None:
                    bid = option_data.get("bid", 0) or 0
                    ask = option_data.get("ask", 0) or 0
                    last_price = option_data.get("last")
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
                    logger.warning(f"{error_msg}. Using minimum 1 contract for entry order.")
                    contracts = 1
                
                max_contracts = 10
                if contracts > max_contracts:
                    logger.warning(f"Calculated contracts ({contracts}) exceeds maximum ({max_contracts}). Capping to {max_contracts} contracts.")
                    contracts = max_contracts
                
                alert_price = trade_data.get("price")
                if alert_price is not None:
                    price_diff = abs(alert_price - chain_price)
                    if price_diff > 0.30:
                        logger.warning(
                            f"Price validation failed: Alert price ${alert_price:.2f} differs from chain price ${chain_price:.2f} "
                            f"by ${price_diff:.2f} (max allowed: $0.30). Retrying with fresh chain data..."
                        )
                        
                        expiration_date = trade_data.get("expiration_date")
                        self._clear_option_chain_cache(self.option_resolver_2, trade_data["ticker"], expiration_date)
                        
                        retry_option_data = self.option_resolver_2.get_option_price_with_expiration(
                            trade_data["ticker"],
                            trade_data["strike"],
                            trade_data["option_type"],
                            expiration_date
                        )
                        
                        if retry_option_data:
                            retry_chain_price = self._calculate_chain_price(retry_option_data)
                            if retry_chain_price is not None:
                                retry_price_diff = abs(alert_price - retry_chain_price)
                                if retry_price_diff > 0.30:
                                    error_msg = f"Price validation failed after retry: Alert price ${alert_price:.2f} differs from chain price ${retry_chain_price:.2f} by ${retry_price_diff:.2f} (max allowed: $0.30). Order rejected."
                                    logger.warning(error_msg)
                                    
                                    logger.warning(f"Chain data for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']} (exp: {trade_data.get('expiration_date')}):")
                                    logger.warning(f"  Option Symbol: {retry_option_data.get('symbol', 'N/A')}")
                                    logger.warning(f"  Bid: ${retry_option_data.get('bid', 0) or 0:.2f}")
                                    logger.warning(f"  Ask: ${retry_option_data.get('ask', 0) or 0:.2f}")
                                    logger.warning(f"  Last: ${retry_option_data.get('last', 0) or 0:.2f}")
                                    logger.warning(f"  Volume: {retry_option_data.get('volume', 'N/A')}")
                                    logger.warning(f"  Open Interest: {retry_option_data.get('open_interest', 'N/A')}")
                                    logger.warning(f"  Strike: {retry_option_data.get('strike', 'N/A')}")
                                    logger.warning(f"  Expiration: {retry_option_data.get('expiration_date', 'N/A')}")
                                    logger.warning(f"  Calculated Chain Price: ${retry_chain_price:.2f}")
                                    logger.warning(f"  Alert Price: ${alert_price:.2f}")
                                    logger.warning(f"  Price Difference: ${retry_price_diff:.2f}")
                                    
                                    try:
                                        if expiration_date:
                                            chain = self.option_resolver_2._get_option_chain(
                                                trade_data["ticker"],
                                                expiration_date,
                                                use_cache=False
                                            )
                                            if chain:
                                                target_strike = trade_data["strike"]
                                                option_type_str = "call" if trade_data["option_type"].upper() == "C" else "put"
                                                nearby_options = []
                                                for opt in chain:
                                                    opt_strike = float(opt.get("strike", 0))
                                                    opt_type = opt.get("option_type", "").lower()
                                                    if opt_type == option_type_str and abs(opt_strike - target_strike) <= 10:
                                                        nearby_options.append({
                                                            "strike": opt_strike,
                                                            "bid": opt.get("bid", 0) or 0,
                                                            "ask": opt.get("ask", 0) or 0,
                                                            "last": opt.get("last", 0) or 0,
                                                            "symbol": opt.get("symbol", "N/A")
                                                        })
                                                
                                                if nearby_options:
                                                    logger.warning(f"  Nearby {option_type_str.upper()} options (within ±10 strikes):")
                                                    for opt in sorted(nearby_options, key=lambda x: abs(x["strike"] - target_strike))[:5]:
                                                        logger.warning(f"    Strike ${opt['strike']:.0f}: Bid=${opt['bid']:.2f}, Ask=${opt['ask']:.2f}, Last=${opt['last']:.2f}, Symbol={opt['symbol']}")
                                    except Exception as e:
                                        logger.warning(f"  Could not fetch nearby options for debugging: {e}")
                                    
                                    try:
                                        send_scraper2_failure_notification(
                                            message.id,
                                            "price_validation_error",
                                            error_msg,
                                            trade_data,
                                            trading_mode_2
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                                    if self.scraper_2:
                                        self.scraper_2.mark_message_processed(message.id)
                                    return
                                else:
                                    logger.info(f"Price validation passed after retry: Alert price ${alert_price:.2f} vs chain price ${retry_chain_price:.2f} (diff: ${retry_price_diff:.2f})")
                                    chain_price = retry_chain_price
                                    option_data = retry_option_data
                            else:
                                error_msg = f"Price validation failed: Could not determine chain price after retry for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                                logger.warning(error_msg)
                                try:
                                    send_scraper2_failure_notification(
                                        message.id,
                                        "price_validation_error",
                                        error_msg,
                                        trade_data,
                                        trading_mode_2
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                                if self.scraper_2:
                                    self.scraper_2.mark_message_processed(message.id)
                                return
                        else:
                            error_msg = f"Price validation failed: Could not get option price data after retry for {trade_data['ticker']} {trade_data['strike']}{trade_data['option_type']}"
                            logger.warning(error_msg)
                            try:
                                send_scraper2_failure_notification(
                                    message.id,
                                    "price_validation_error",
                                    error_msg,
                                    trade_data,
                                    trading_mode_2
                                )
                            except Exception as e:
                                logger.error(f"Failed to send failure notification: {e}", exc_info=True)
                            if self.scraper_2:
                                self.scraper_2.mark_message_processed(message.id)
                            return
                    else:
                        logger.info(f"Price validation passed: Alert price ${alert_price:.2f} vs chain price ${chain_price:.2f} (diff: ${price_diff:.2f})")
                
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
                        chain_price = self._calculate_chain_price(option_data, use_bid_fallback=True)
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

