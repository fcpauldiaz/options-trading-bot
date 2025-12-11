import os
import logging
from libsql_client import create_client

logger = logging.getLogger(__name__)

class DBClient:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
    
    def _initialize_client(self):
        database_url = os.getenv("TURSO_DATABASE_URL")
        auth_token = os.getenv("TURSO_AUTH_TOKEN")
        
        if not database_url:
            raise ValueError("TURSO_DATABASE_URL environment variable is not set")
        if not auth_token:
            raise ValueError("TURSO_AUTH_TOKEN environment variable is not set")
        
        try:
            self._client = create_client(
                url=database_url,
                auth_token=auth_token
            )
            logger.info("Successfully connected to Turso database")
        except Exception as e:
            logger.error(f"Failed to connect to Turso database: {e}")
            raise
    
    def get_client(self):
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Closed Turso database connection")

