import requests
import logging
from datetime import datetime
from config import get_tradier_api_key, get_tradier_base_url, get_tradier_account_id

logger = logging.getLogger(__name__)

class TradierClient:
    def __init__(self):
        self.api_key = get_tradier_api_key()
        self.base_url = get_tradier_base_url()
        self.account_id = get_tradier_account_id()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        logger.info(f"Initialized Tradier client - Mode: {self.base_url}, Account: {self.account_id}")

    def _make_request(self, method, endpoint, params=None, data=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, data=data, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Tradier API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    def get_account_info(self):
        endpoint = f"/accounts/{self.account_id}"
        return self._make_request("GET", endpoint)

    def get_option_expirations(self, symbol, include_all_roots=True):
        endpoint = "/markets/options/expirations"
        params = {
            "symbol": symbol,
            "includeAllRoots": str(include_all_roots).lower()
        }
        return self._make_request("GET", endpoint, params=params)

    def get_option_strikes(self, symbol, expiration):
        endpoint = "/markets/options/strikes"
        params = {
            "symbol": symbol,
            "expiration": expiration
        }
        return self._make_request("GET", endpoint, params=params)

    def get_option_chain(self, symbol, expiration, greeks=False):
        endpoint = "/markets/options/chains"
        params = {
            "symbol": symbol,
            "expiration": expiration,
            "greeks": str(greeks).lower()
        }
        return self._make_request("GET", endpoint, params=params)

    def place_order(self, order_data):
        endpoint = f"/accounts/{self.account_id}/orders"
        return self._make_request("POST", endpoint, data=order_data)

