import logging
import time
import requests
from tradier_client import TradierClient
from market_hours import is_market_open
from ntfy_notifier import send_order_placement_notification

logger = logging.getLogger(__name__)

class OrderExecutor:
    def __init__(self, tradier_client, position_tracker=None):
        self.client = tradier_client
        self.position_tracker = position_tracker

    def _map_action_to_side(self, action):
        action_upper = action.upper()
        if action_upper == "BOUGHT":
            return "buy_to_open"
        elif action_upper == "SOLD":
            return "sell_to_close"
        else:
            raise ValueError(f"Unknown action: {action}")

    def _is_retryable_error(self, exception):
        if isinstance(exception, requests.exceptions.RequestException):
            if hasattr(exception, 'response') and exception.response is not None:
                status_code = exception.response.status_code
                return status_code >= 500 or status_code == 429
        return False

    def execute_order(self, trade_data, option_symbol):
        try:
            if not is_market_open():
                logger.warning("Order rejected: Market is currently closed")
                return {
                    "success": False,
                    "error": "Market is currently closed",
                    "response": None
                }
            
            action = trade_data["action"].upper()
            ticker = trade_data["ticker"]
            strike = trade_data["strike"]
            option_type = trade_data["option_type"]
            requested_quantity = trade_data["contracts"]
            actual_quantity = requested_quantity

            if action == "SOLD" and self.position_tracker:
                available = self.position_tracker.get_position(ticker, strike, option_type)
                
                if available <= 0:
                    logger.warning(f"Cannot execute SOLD order: No open position for {ticker} {strike}{option_type}")
                    return {
                        "success": False,
                        "error": f"No open position for {ticker} {strike}{option_type}",
                        "response": None
                    }
                
                if available < requested_quantity:
                    actual_quantity = self.position_tracker.get_available_quantity(ticker, strike, option_type, requested_quantity)
                    logger.warning(f"Partial fill: Requested {requested_quantity} contracts, but only {available} available. Executing {actual_quantity} contracts.")
                else:
                    logger.info(f"Position validated: {available} contracts available for {ticker} {strike}{option_type}")

            side = self._map_action_to_side(action)
            
            order_type = "market"
            order_data = {
                "class": "option",
                "symbol": ticker,
                "option_symbol": option_symbol,
                "side": side,
                "quantity": str(actual_quantity),
                "type": order_type,
                "duration": "day"
            }
            
            if action == "SOLD" and "price" in trade_data and ticker.upper() != "SPX":
                order_type = "limit"
                order_data["type"] = "limit"
                original_price = float(trade_data["price"])
                adjusted_price = max(original_price - 0.15, 0.01)
                order_data["price"] = str(adjusted_price)
                logger.info(f"Using limit order for SOLD: original price ${original_price:.2f}, adjusted price ${adjusted_price:.2f} (${original_price - adjusted_price:.2f} below)")
            elif action == "BOUGHT" and "price" in trade_data:
                order_type = "limit"
                order_data["type"] = "limit"
                limit_price = float(trade_data["price"])
                order_data["price"] = str(limit_price)
                logger.info(f"Using limit order for BOUGHT: limit price ${limit_price:.2f}")
            
            logger.info(f"Placing order: {action} {actual_quantity} {option_symbol} ({side})")
            
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    response = self.client.place_order(order_data)
                    try:
                        trading_mode = self.client.get_trading_mode()
                        send_order_placement_notification(trade_data, order_data, trading_mode)
                    except Exception as e:
                        logger.error(f"Failed to send order placement notification: {e}", exc_info=True)
                    break
                except Exception as e:
                    if attempt < max_retries - 1 and self._is_retryable_error(e):
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f"Order placement failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        raise
            
            if "order" in response:
                order_info = response["order"]
                order_id = order_info.get("id", "unknown")
                status = order_info.get("status", "unknown")
                logger.info(f"Order placed successfully - ID: {order_id}, Status: {status}")
                
                result = {
                    "success": True,
                    "order_id": order_id,
                    "status": status,
                    "response": response,
                    "actual_quantity": actual_quantity,
                    "order_type": order_type
                }
                
                if actual_quantity != requested_quantity:
                    result["partial_fill"] = True
                    result["requested_quantity"] = requested_quantity
                
                return result
            else:
                logger.error(f"Unexpected response format: {response}")
                return {
                    "success": False,
                    "error": "Unexpected response format",
                    "response": response
                }
        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": None
            }

