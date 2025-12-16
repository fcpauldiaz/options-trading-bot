import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)

NTFY_TOPIC = "fcpauldiaz_notifications"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

def send_trade_notification(trade_data: Dict, order_result: Dict) -> bool:
    """
    Send a notification to ntfy when a trade is successfully placed.
    
    Args:
        trade_data: Dictionary containing trade information (action, ticker, strike, option_type, contracts, price)
        order_result: Dictionary containing order result (order_id, status, order_type)
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        action = trade_data.get("action", "UNKNOWN")
        ticker = trade_data.get("ticker", "N/A")
        strike = trade_data.get("strike", "N/A")
        option_type = trade_data.get("option_type", "N/A")
        contracts = trade_data.get("contracts", 0)
        price = trade_data.get("price")
        order_id = order_result.get("order_id", "N/A")
        status = order_result.get("status", "N/A")
        order_type = order_result.get("order_type", "market")
        
        title = f"Trade Executed: {action} {ticker}"
        
        message_parts = [
            f"{action} {contracts} {ticker} {strike}{option_type}",
            f"Order ID: {order_id}",
            f"Status: {status}",
            f"Type: {order_type}"
        ]
        
        if price is not None:
            message_parts.insert(1, f"Price: ${price:.2f}")
        
        message = "\n".join(message_parts)
        
        response = requests.post(
            NTFY_URL,
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": "default"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"Notification sent successfully for trade: {ticker} {strike}{option_type}")
            return True
        else:
            logger.warning(f"Failed to send notification: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending notification: {e}", exc_info=True)
        return False

