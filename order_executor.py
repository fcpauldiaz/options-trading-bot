import logging
from tradier_client import TradierClient

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

    def execute_order(self, trade_data, option_symbol):
        try:
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
            
            if action == "SOLD" and "price" in trade_data:
                order_type = "limit"
                order_data["type"] = "limit"
                order_data["price"] = str(trade_data["price"])
                logger.info(f"Using limit order for SOLD: price ${trade_data['price']}")
            
            logger.info(f"Placing order: {action} {actual_quantity} {option_symbol} ({side})")
            
            response = self.client.place_order(order_data)
            
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

