import logging
from datetime import datetime, timedelta
from tradier_client import TradierClient

logger = logging.getLogger(__name__)

class OptionResolver:
    def __init__(self, tradier_client):
        self.client = tradier_client
        self.expiration_cache = {}
        self.chain_cache = {}

    def _parse_expiration_date(self, date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Failed to parse expiration date: {date_str}")
            return None

    def _get_expirations(self, symbol):
        cache_key = symbol
        if cache_key in self.expiration_cache:
            cache_time, expirations = self.expiration_cache[cache_key]
            if datetime.now() - cache_time < timedelta(hours=1):
                return expirations
        
        try:
            response = self.client.get_option_expirations(symbol)
            if "expirations" in response and "date" in response["expirations"]:
                dates = response["expirations"]["date"]
                if isinstance(dates, str):
                    dates = [dates]
                expirations = [self._parse_expiration_date(d) for d in dates if d]
                expirations = [d for d in expirations if d is not None]
                self.expiration_cache[cache_key] = (datetime.now(), expirations)
                logger.info(f"Retrieved {len(expirations)} expirations for {symbol}")
                return expirations
            else:
                logger.warning(f"No expirations found in response for {symbol}: {response}")
                return []
        except Exception as e:
            logger.error(f"Error fetching expirations for {symbol}: {e}")
            return []

    def _find_closest_expiration(self, symbol, today=None):
        if today is None:
            today = datetime.now().date()
        
        expirations = self._get_expirations(symbol)
        if not expirations:
            return None
        
        closest = None
        min_delta = None
        
        for exp_date in expirations:
            if exp_date >= today:
                delta = (exp_date - today).days
                if min_delta is None or delta < min_delta:
                    min_delta = delta
                    closest = exp_date
        
        if closest is None:
            closest = max(expirations)
            logger.warning(f"No future expiration found for {symbol}, using latest: {closest}")
        
        return closest

    def _get_option_chain(self, symbol, expiration_date, use_cache=True):
        cache_key = f"{symbol}_{expiration_date}"
        if use_cache and cache_key in self.chain_cache:
            cache_time, chain_data = self.chain_cache[cache_key]
            if datetime.now() - cache_time < timedelta(minutes=5):
                return chain_data
        
        try:
            expiration_str = expiration_date.strftime("%Y-%m-%d")
            response = self.client.get_option_chain(symbol, expiration_str, greeks=False)
            
            if "options" in response and "option" in response["options"]:
                options = response["options"]["option"]
                if isinstance(options, dict):
                    options = [options]
                if use_cache:
                    self.chain_cache[cache_key] = (datetime.now(), options)
                logger.info(f"Retrieved {len(options)} options from chain for {symbol} exp {expiration_str}")
                return options
            else:
                logger.warning(f"No options found in chain response for {symbol} exp {expiration_str}: {response}")
                return []
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol} exp {expiration_date}: {e}")
            return []

    def _find_option_in_chain(self, chain, strike, option_type, return_full_option=False):
        option_type_upper = option_type.upper()
        option_type_map = {"C": "call", "P": "put"}
        target_type = option_type_map.get(option_type_upper)
        
        if not target_type:
            return None
        
        for option in chain:
            option_strike = float(option.get("strike", 0))
            option_type_str = option.get("option_type", "").lower()
            
            if abs(option_strike - strike) < 0.01 and option_type_str == target_type:
                if return_full_option:
                    return option
                else:
                    symbol = option.get("symbol")
                    if symbol:
                        return symbol
        return None

    def get_option_price(self, ticker, strike, option_type):
        try:
            option_type_upper = option_type.upper()
            
            if option_type_upper not in ["C", "P"]:
                logger.error(f"Invalid option type: {option_type}")
                return None
            
            exp_date = self._find_closest_expiration(ticker)
            if exp_date is None:
                logger.error(f"Could not find expiration for {ticker}")
                return None
            
            chain = self._get_option_chain(ticker, exp_date, use_cache=False)
            if not chain:
                logger.error(f"Could not retrieve option chain for {ticker} exp {exp_date}")
                return None
            
            option = self._find_option_in_chain(chain, strike, option_type, return_full_option=True)
            
            if option:
                return option
            else:
                logger.error(f"Could not find option in chain: {ticker} {strike}{option_type} (exp: {exp_date})")
                return None
        except Exception as e:
            logger.error(f"Error getting option price for {ticker} {strike}{option_type}: {e}", exc_info=True)
            return None

    def resolve_option_symbol(self, ticker, strike, option_type):
        try:
            option_type_upper = option_type.upper()
            
            if option_type_upper not in ["C", "P"]:
                logger.error(f"Invalid option type: {option_type}")
                return None
            
            exp_date = self._find_closest_expiration(ticker)
            if exp_date is None:
                logger.error(f"Could not find expiration for {ticker}")
                return None
            logger.info(f"Found expiration for {ticker}: {exp_date}")
            chain = self._get_option_chain(ticker, exp_date)
            if not chain:
                logger.error(f"Could not retrieve option chain for {ticker} exp {exp_date}")
                return None
            
            option_symbol = self._find_option_in_chain(chain, strike, option_type)
            
            if option_symbol:
                logger.info(f"Resolved option symbol: {ticker} {strike}{option_type} -> {option_symbol} (exp: {exp_date})")
                return option_symbol
            else:
                logger.error(f"Could not find option in chain: {ticker} {strike}{option_type} (exp: {exp_date})")
                return None
        except Exception as e:
            logger.error(f"Error resolving option symbol for {ticker} {strike}{option_type}: {e}", exc_info=True)
            return None

