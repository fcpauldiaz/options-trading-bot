import os
import logging
import libsql

logger = logging.getLogger(__name__)

class DBClient:
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        pass
    
    def _get_connection(self):
        if self._conn is None:
            database_url = os.getenv("TURSO_DATABASE_URL")
            auth_token = os.getenv("TURSO_AUTH_TOKEN")
            
            if not database_url:
                raise ValueError("TURSO_DATABASE_URL environment variable is not set")
            if not auth_token:
                raise ValueError("TURSO_AUTH_TOKEN environment variable is not set")
            
            try:
                self._conn = libsql.connect(database_url, auth_token=auth_token)
                logger.info("Successfully connected to Turso database")
            except Exception as e:
                logger.error(f"Failed to connect to Turso database: {e}")
                raise
        
        return self._conn
    
    def execute_sync(self, query, params=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            
            class Result:
                def __init__(self, cursor):
                    self.cursor = cursor
                    self.rows = cursor.fetchall()
            
            return Result(cursor)
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Closed Turso database connection")

