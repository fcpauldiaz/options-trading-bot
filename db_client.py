import os
import logging
from typing import Optional, Dict, List, Any
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

logger = logging.getLogger(__name__)

class DBClient:
    _instance = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        pass
    
    def _get_client(self) -> Client:
        if self._client is None:
            if not SUPABASE_URL:
                raise ValueError("SUPABASE_URL environment variable is not set")
            if not SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
            
            try:
                self._client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                logger.info("Successfully connected to Supabase database")
            except Exception as e:
                logger.error(f"Failed to connect to Supabase database: {e}")
                raise
        
        return self._client
    
    def insert_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        try:
            response = client.table('trades').insert(trade_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error inserting trade: {e}")
            raise
    
    def select_trades(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        client = self._get_client()
        try:
            query = client.table('trades').select('*')
            
            if filters:
                if 'price_is_null' in filters and filters['price_is_null']:
                    query = query.is_('price', 'null')
                if 'order_by' in filters:
                    order_by = filters['order_by']
                    ascending = filters.get('ascending', False)
                    query = query.order(order_by, desc=not ascending)
            
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error selecting trades: {e}")
            raise
    
    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        try:
            response = client.table('trades').update(updates).eq('id', trade_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error updating trade: {e}")
            raise
    
    def upsert_position(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        try:
            response = client.table('positions').upsert(position_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error upserting position: {e}")
            raise
    
    def select_positions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        client = self._get_client()
        try:
            query = client.table('positions').select('*')
            
            if filters:
                if 'quantity_gt' in filters:
                    query = query.gt('quantity', filters['quantity_gt'])
            
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error selecting positions: {e}")
            raise
    
    def delete_position(self, ticker: str, strike: float, option_type: str) -> None:
        client = self._get_client()
        try:
            client.table('positions').delete().eq('ticker', ticker).eq('strike', strike).eq('option_type', option_type).execute()
        except Exception as e:
            logger.error(f"Error deleting position: {e}")
            raise
    
    def close(self):
        self._client = None
        logger.info("Closed Supabase database connection")
