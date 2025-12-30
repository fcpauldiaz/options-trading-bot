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
    
    def get_daily_pnl(self) -> float:
        from datetime import datetime, date
        
        client = self._get_client()
        try:
            today = date.today()
            today_str = today.isoformat()
            
            query = client.table('trades').select('*')
            query = query.gte('timestamp', f"{today_str}T00:00:00")
            query = query.lt('timestamp', f"{today_str}T23:59:59")
            query = query.order('timestamp', desc=False)
            
            response = query.execute()
            trades = response.data if response.data else []
            
            if not trades:
                logger.debug("No trades found for today")
                return 0.0
            
            pnl = 0.0
            position_tracker = {}
            
            for trade in trades:
                ticker = trade.get('ticker', '').upper()
                strike = float(trade.get('strike', 0))
                option_type = trade.get('option_type', '').upper()
                action = trade.get('action', '').upper()
                contracts = int(trade.get('contracts', 0))
                price = float(trade.get('price', 0)) if trade.get('price') else 0
                
                if not price or contracts == 0:
                    continue
                
                key = (ticker, strike, option_type)
                
                if action == "BOUGHT":
                    if key not in position_tracker:
                        position_tracker[key] = {"quantity": 0, "total_cost": 0.0}
                    position_tracker[key]["quantity"] += contracts
                    position_tracker[key]["total_cost"] += price * contracts * 100
                elif action == "SOLD":
                    if key in position_tracker and position_tracker[key]["quantity"] > 0:
                        sold_quantity = min(contracts, position_tracker[key]["quantity"])
                        avg_cost = position_tracker[key]["total_cost"] / (position_tracker[key]["quantity"] * 100) if position_tracker[key]["quantity"] > 0 else 0
                        proceeds = price * sold_quantity * 100
                        cost_basis = avg_cost * sold_quantity * 100
                        trade_pnl = proceeds - cost_basis
                        pnl += trade_pnl
                        
                        position_tracker[key]["quantity"] -= sold_quantity
                        position_tracker[key]["total_cost"] -= avg_cost * sold_quantity * 100
                        
                        if position_tracker[key]["quantity"] <= 0:
                            position_tracker[key] = {"quantity": 0, "total_cost": 0.0}
            
            logger.info(f"Daily P&L calculated: ${pnl:.2f} from {len(trades)} trades")
            return pnl
        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}", exc_info=True)
            return 0.0
    
    def close(self):
        self._client = None
        logger.info("Closed Supabase database connection")
