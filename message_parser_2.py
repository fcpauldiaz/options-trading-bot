import re
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class MessageParser2:
    def __init__(self):
        self.size_indicators = ["LOTTO", "SMALL", "GRADE B", "GRADE A", "ROLLUP"]
        
        self.bought_pattern = re.compile(
            r'#ALERT\s+BOUGHT\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+(\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\$?([\d.]+)\s+\[([^\]]+)\]',
            re.IGNORECASE
        )
        
        self.sold_pattern = re.compile(
            r'#ALERT\s+SOLD\s+(\d+)/(\d+)\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+(\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\$?([\d.]+)',
            re.IGNORECASE
        )
        
        self.sold_all_out_pattern = re.compile(
            r'#ALERT\s+SOLD\s+(?:ALL\s+OUT|all\s+out)\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+(\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\$?([\d.]+)',
            re.IGNORECASE
        )

    def _parse_date(self, date_str):
        try:
            parts = date_str.split('/')
            if len(parts) == 3:
                month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                return date(year, month, day)
            elif len(parts) == 2:
                month, day = int(parts[0]), int(parts[1])
                current_year = datetime.now().year
                today = datetime.now().date()
                parsed_date = date(current_year, month, day)
                
                if parsed_date < today:
                    parsed_date = date(current_year + 1, month, day)
                    logger.debug(f"Date {date_str} was in the past with current year, using next year: {parsed_date}")
                
                return parsed_date
            else:
                logger.error(f"Invalid date format: {date_str}")
                return None
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return None

    def _normalize_size_indicator(self, size_str):
        size_upper = size_str.upper().strip()
        for indicator in self.size_indicators:
            if indicator.upper() == size_upper:
                return indicator
        return None

    def parse(self, message_content):
        message_content = message_content.strip()
        
        match = self.bought_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            expiration_str = match.group(4)
            price = float(match.group(5))
            size_indicator_raw = match.group(6).strip()
            
            size_indicator = self._normalize_size_indicator(size_indicator_raw)
            if not size_indicator:
                logger.warning(f"Invalid or missing size indicator: {size_indicator_raw}. Must be one of: {', '.join(self.size_indicators)}")
                return {"valid": False, "error": f"Invalid size indicator: {size_indicator_raw}"}
            
            expiration_date = self._parse_date(expiration_str)
            if not expiration_date:
                logger.error(f"Could not parse expiration date: {expiration_str}")
                return {"valid": False, "error": f"Invalid expiration date: {expiration_str}"}
            
            return {
                "action": "BOUGHT",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "expiration_date": expiration_date,
                "price": price,
                "size_indicator": size_indicator,
                "valid": True
            }
        
        match = self.sold_pattern.search(message_content)
        if match:
            sold_numerator = int(match.group(1))
            sold_denominator = int(match.group(2))
            ticker = match.group(3).upper()
            strike = float(match.group(4))
            option_type = match.group(5).upper()
            expiration_str = match.group(6)
            price = float(match.group(7))
            
            expiration_date = self._parse_date(expiration_str)
            if not expiration_date:
                logger.error(f"Could not parse expiration date: {expiration_str}")
                return {"valid": False, "error": f"Invalid expiration date: {expiration_str}"}
            
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "expiration_date": expiration_date,
                "price": price,
                "fraction": (sold_numerator, sold_denominator),
                "use_fraction": True,
                "valid": True
            }
        
        match = self.sold_all_out_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            expiration_str = match.group(4)
            price = float(match.group(5))
            
            expiration_date = self._parse_date(expiration_str)
            if not expiration_date:
                logger.error(f"Could not parse expiration date: {expiration_str}")
                return {"valid": False, "error": f"Invalid expiration date: {expiration_str}"}
            
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "expiration_date": expiration_date,
                "price": price,
                "contracts": 0,
                "all_out": True,
                "valid": True
            }
        
        logger.debug(f"Message did not match any pattern: {message_content[:100]}")
        return {"valid": False}

