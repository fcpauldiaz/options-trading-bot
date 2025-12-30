import pytz
from datetime import datetime

EASTERN = pytz.timezone('US/Eastern')

def is_market_open():
    """
    Check if the US stock market is currently open.
    Market hours: 9:00 AM - 4:00 PM Eastern Time, Monday through Friday.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    now_et = datetime.now(EASTERN)
    
    weekday = now_et.weekday()
    if weekday >= 5:
        return False
    
    current_time = now_et.time()
    market_open_time = datetime.strptime("09:00", "%H:%M").time()
    market_close_time = datetime.strptime("16:00", "%H:%M").time()
    
    return market_open_time <= current_time <= market_close_time

