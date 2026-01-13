import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)

NTFY_TOPIC = "fcpauldiaz_notifications"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

def send_trade_notification(trade_data: Dict, order_result: Dict, trading_mode: str = "live") -> bool:
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
        
        mode_display = trading_mode.upper()
        title = f"[{mode_display}] Trade Executed: {action} {ticker}"
        
        message_parts = [
            f"[{mode_display}] {action} {contracts} {ticker} {strike}{option_type}",
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

def send_order_placement_notification(trade_data: Dict, order_data: Dict, trading_mode: str = "live") -> bool:
    """
    Send a notification to ntfy when an order is placed to Tradier.
    
    Args:
        trade_data: Dictionary containing trade information (action, ticker, strike, option_type, contracts, price)
        order_data: Dictionary containing order data (option_symbol, side, quantity, type, etc.)
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        action = trade_data.get("action", "UNKNOWN")
        ticker = trade_data.get("ticker", "N/A")
        strike = trade_data.get("strike", "N/A")
        option_type = trade_data.get("option_type", "N/A")
        contracts = trade_data.get("contracts", 0)
        option_symbol = order_data.get("option_symbol", "N/A")
        side = order_data.get("side", "N/A")
        order_type = order_data.get("type", "market")
        
        mode_display = trading_mode.upper()
        title = f"[{mode_display}] Order Placed: {action} {ticker}"
        
        message_parts = [
            f"[{mode_display}] {action} {contracts} {ticker} {strike}{option_type}",
            f"Option Symbol: {option_symbol}",
            f"Side: {side}",
            f"Type: {order_type}"
        ]
        
        if "price" in order_data:
            message_parts.append(f"Limit Price: ${float(order_data['price']):.2f}")
        
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
            logger.info(f"Order placement notification sent: {ticker} {strike}{option_type}")
            return True
        else:
            logger.warning(f"Failed to send order placement notification: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending order placement notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending order placement notification: {e}", exc_info=True)
        return False

def send_scraper2_entry_notification(trade_data: Dict, order_result: Dict, trading_mode: str = "paper") -> bool:
    """
    Send a notification to ntfy when scraper 2 successfully executes a trade.
    
    Args:
        trade_data: Dictionary containing trade information (action, ticker, strike, option_type, contracts, price, expiration_date)
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
        expiration_date = trade_data.get("expiration_date")
        order_id = order_result.get("order_id", "N/A")
        status = order_result.get("status", "N/A")
        
        mode_display = trading_mode.upper()
        title = f"[{mode_display}] Scraper 2 Entry: {action} {ticker}"
        
        message_parts = [
            f"[{mode_display}] {action} {contracts} {ticker} {strike}{option_type}",
            f"Order ID: {order_id}",
            f"Status: {status}"
        ]
        
        if expiration_date:
            exp_str = expiration_date.strftime("%Y-%m-%d") if hasattr(expiration_date, 'strftime') else str(expiration_date)
            message_parts.append(f"Expiration: {exp_str}")
        
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
            logger.info(f"Scraper 2 entry notification sent: {ticker} {strike}{option_type}")
            return True
        else:
            logger.warning(f"Failed to send scraper 2 entry notification: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending scraper 2 entry notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending scraper 2 entry notification: {e}", exc_info=True)
        return False

def send_scraper2_failure_notification(message_id: int, error_type: str, error_message: str, trade_data: Optional[Dict] = None, trading_mode: str = "paper") -> bool:
    """
    Send a notification to ntfy when scraper 2 encounters a failure.
    
    Args:
        message_id: Discord message ID that failed
        error_type: Type of error (e.g., "parsing_error", "validation_error", "order_failure")
        error_message: Detailed error message
        trade_data: Optional dictionary containing trade information if available
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        mode_display = trading_mode.upper()
        title = f"[{mode_display}] Scraper 2 Failure: {error_type}"
        
        message_parts = [
            f"[{mode_display}]",
            f"Error: {error_message}"
        ]
        
        if trade_data:
            ticker = trade_data.get("ticker", "N/A")
            strike = trade_data.get("strike", "N/A")
            option_type = trade_data.get("option_type", "N/A")
            expiration_date = trade_data.get("expiration_date")
            
            trade_info = f"Trade: {ticker} {strike}{option_type}"
            if expiration_date:
                exp_str = expiration_date.strftime("%Y-%m-%d") if hasattr(expiration_date, 'strftime') else str(expiration_date)
                trade_info += f" exp {exp_str}"
            message_parts.insert(0, trade_info)
        
        message = "\n".join(message_parts)
        
        response = requests.post(
            NTFY_URL,
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": "high"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"Scraper 2 failure notification sent: {error_type}")
            return True
        else:
            logger.warning(f"Failed to send scraper 2 failure notification: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending scraper 2 failure notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending scraper 2 failure notification: {e}", exc_info=True)
        return False

