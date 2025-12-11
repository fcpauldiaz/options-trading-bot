import re
import logging

logger = logging.getLogger(__name__)

class MessageParser:
    def __init__(self):
        self.unicode_fractions = {
            '½': (1, 2),
            '⅓': (1, 3),
            '⅔': (2, 3),
            '¼': (1, 4),
            '¾': (3, 4),
            '⅕': (1, 5),
            '⅖': (2, 5),
            '⅗': (3, 5),
            '⅘': (4, 5),
            '⅙': (1, 6),
            '⅚': (5, 6),
            '⅛': (1, 8),
            '⅜': (3, 8),
            '⅝': (5, 8),
            '⅞': (7, 8),
        }
        self.bought_pattern = re.compile(
            r'\*{0,2}BOUGHT\*{0,2}\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)\s+.*?\[(\d+)\s+contracts?\]',
            re.IGNORECASE
        )
        self.sold_full_pattern = re.compile(
            r'\*{0,2}SOLD\*{0,2}\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)\s+.*?\[(\d+)\s+contracts?\]',
            re.IGNORECASE
        )
        self.sold_partial_pattern = re.compile(
            r'\*{0,2}SOLD\*{0,2}\s+(\d+)/(\d+)\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)',
            re.IGNORECASE
        )
        self.sold_all_out_pattern = re.compile(
            r'\*{0,2}SOLD\*{0,2}\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)\s+ALL\s+OUT',
            re.IGNORECASE
        )
        self.sold_partial_after_pattern = re.compile(
            r'\*{0,2}SOLD\*{0,2}\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)\s+.*?(\d+)/(\d+)',
            re.IGNORECASE
        )
        self.sold_fraction_pattern = re.compile(
            r'\*{0,2}SOLD\*{0,2}\s+([A-Z]+)\s+(\d+\.?\d*)([CP])\s+\$?([\d.]+)\s+.*?([½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]|\d+/\d+)',
            re.IGNORECASE
        )

    def _parse_fraction(self, fraction_str):
        if fraction_str in self.unicode_fractions:
            return self.unicode_fractions[fraction_str]
        
        match = re.match(r'(\d+)/(\d+)', fraction_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        
        return None

    def parse(self, message_content):
        message_content = message_content.strip()
        
        match = self.bought_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            price = float(match.group(4))
            contracts = int(match.group(5))
            return {
                "action": "BOUGHT",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "price": price,
                "contracts": contracts,
                "valid": True
            }
        
        match = self.sold_full_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            price = float(match.group(4))
            contracts = int(match.group(5))
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "price": price,
                "contracts": contracts,
                "valid": True
            }
        
        match = self.sold_partial_pattern.search(message_content)
        if match:
            sold_quantity = int(match.group(1))
            total_quantity = int(match.group(2))
            ticker = match.group(3).upper()
            strike = float(match.group(4))
            option_type = match.group(5).upper()
            price = float(match.group(6))
            remaining = total_quantity - sold_quantity
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "price": price,
                "contracts": remaining,
                "valid": True
            }
        
        match = self.sold_all_out_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            price = float(match.group(4))
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "price": price,
                "contracts": 0,
                "all_out": True,
                "valid": True
            }
        
        match = self.sold_fraction_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            price = float(match.group(4))
            fraction_str = match.group(5)
            
            fraction = self._parse_fraction(fraction_str)
            if fraction:
                numerator, denominator = fraction
                return {
                    "action": "SOLD",
                    "ticker": ticker,
                    "strike": strike,
                    "option_type": option_type,
                    "price": price,
                    "fraction": (numerator, denominator),
                    "contracts": 0,
                    "use_fraction": True,
                    "valid": True
                }
        
        match = self.sold_partial_after_pattern.search(message_content)
        if match:
            ticker = match.group(1).upper()
            strike = float(match.group(2))
            option_type = match.group(3).upper()
            price = float(match.group(4))
            sold_quantity = int(match.group(5))
            total_quantity = int(match.group(6))
            remaining = total_quantity - sold_quantity
            return {
                "action": "SOLD",
                "ticker": ticker,
                "strike": strike,
                "option_type": option_type,
                "price": price,
                "contracts": remaining,
                "valid": True
            }
        
        logger.debug(f"Message did not match any pattern: {message_content[:100]}")
        return {"valid": False}

