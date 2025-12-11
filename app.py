from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import logging
import json
import time
from datetime import datetime, timedelta
from db_client import DBClient
from option_resolver import OptionResolver
from tradier_client import TradierClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

db_client = DBClient()
tradier_client = TradierClient()
option_resolver = OptionResolver(tradier_client)

def run_migrations():
    try:
        create_trades_table = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            message_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            strike REAL NOT NULL,
            option_type TEXT NOT NULL,
            action TEXT NOT NULL,
            contracts INTEGER NOT NULL,
            price REAL,
            option_symbol TEXT NOT NULL,
            order_id TEXT,
            status TEXT,
            account_id TEXT,
            order_type TEXT
        )
        """
        
        create_positions_table = """
        CREATE TABLE IF NOT EXISTS positions (
            ticker TEXT NOT NULL,
            strike REAL NOT NULL,
            option_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_entry_price REAL,
            last_updated TEXT NOT NULL,
            PRIMARY KEY (ticker, strike, option_type)
        )
        """
        
        db_client.execute_sync(create_trades_table)
        logger.info("Trades table created/verified")
        
        db_client.execute_sync(create_positions_table)
        logger.info("Positions table created/verified")
        
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {e}", exc_info=True)
        raise

run_migrations()

def row_to_dict(row, columns):
    if hasattr(row, '__iter__') and not isinstance(row, (str, bytes)):
        return {col: row[i] if i < len(row) else None for i, col in enumerate(columns)}
    return {col: getattr(row, col, None) for col in columns}

@app.route('/api/trades', methods=['GET'])
def get_trades():
    try:
        ticker = request.args.get('ticker')
        action = request.args.get('action')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())
        
        if action:
            query += " AND action = ?"
            params.append(action.upper())
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        result = db_client.execute_sync(query, params)
        
        columns = ['id', 'timestamp', 'message_id', 'ticker', 'strike', 'option_type',
                   'action', 'contracts', 'price', 'option_symbol', 'order_id',
                   'status', 'account_id', 'order_type']
        
        trades = [row_to_dict(row, columns) for row in result.rows]
        
        count_query = "SELECT COUNT(*) FROM trades WHERE 1=1"
        count_params = []
        
        if ticker:
            count_query += " AND ticker = ?"
            count_params.append(ticker.upper())
        
        if action:
            count_query += " AND action = ?"
            count_params.append(action.upper())
        
        if start_date:
            count_query += " AND timestamp >= ?"
            count_params.append(start_date)
        
        if end_date:
            count_query += " AND timestamp <= ?"
            count_params.append(end_date)
        
        count_result = db_client.execute_sync(count_query, count_params)
        total = count_result.rows[0][0] if count_result.rows else 0
        
        return jsonify({
            'trades': trades,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"Error fetching trades: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades/<int:trade_id>', methods=['GET'])
def get_trade(trade_id):
    try:
        result = db_client.execute_sync(
            "SELECT * FROM trades WHERE id = ?",
            [trade_id]
        )
        
        if not result.rows:
            return jsonify({'error': 'Trade not found'}), 404
        
        columns = ['id', 'timestamp', 'message_id', 'ticker', 'strike', 'option_type',
                   'action', 'contracts', 'price', 'option_symbol', 'order_id',
                   'status', 'account_id', 'order_type']
        
        trade = row_to_dict(result.rows[0], columns)
        return jsonify(trade)
    except Exception as e:
        logger.error(f"Error fetching trade: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    try:
        result = db_client.execute_sync(
            "SELECT ticker, strike, option_type, quantity, avg_entry_price, last_updated FROM positions WHERE quantity > 0"
        )
        
        positions = []
        for row in result.rows:
            positions.append({
                'ticker': row[0],
                'strike': row[1],
                'option_type': row[2],
                'quantity': row[3],
                'avg_entry_price': row[4],
                'last_updated': row[5]
            })
        
        return jsonify({'positions': positions})
    except Exception as e:
        logger.error(f"Error fetching positions: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions/<ticker>/<float:strike>/<option_type>', methods=['GET'])
def get_position(ticker, strike, option_type):
    try:
        result = db_client.execute_sync(
            "SELECT ticker, strike, option_type, quantity, avg_entry_price, last_updated FROM positions WHERE ticker = ? AND strike = ? AND option_type = ?",
            [ticker.upper(), strike, option_type.upper()]
        )
        
        if not result.rows:
            return jsonify({'error': 'Position not found'}), 404
        
        row = result.rows[0]
        return jsonify({
            'ticker': row[0],
            'strike': row[1],
            'option_type': row[2],
            'quantity': row[3],
            'avg_entry_price': row[4],
            'last_updated': row[5]
        })
    except Exception as e:
        logger.error(f"Error fetching position: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total_trades_result = db_client.execute_sync("SELECT COUNT(*) FROM trades")
        total_trades = total_trades_result.rows[0][0] if total_trades_result.rows else 0
        
        bought_trades_result = db_client.execute_sync("SELECT COUNT(*) FROM trades WHERE action = 'BOUGHT'")
        bought_trades = bought_trades_result.rows[0][0] if bought_trades_result.rows else 0
        
        sold_trades_result = db_client.execute_sync("SELECT COUNT(*) FROM trades WHERE action = 'SOLD'")
        sold_trades = sold_trades_result.rows[0][0] if sold_trades_result.rows else 0
        
        realized_pl_result = db_client.execute_sync("""
            SELECT SUM((s.price - b.price) * s.contracts * 100) as realized_pl
            FROM trades s
            JOIN trades b ON s.ticker = b.ticker 
                AND s.strike = b.strike 
                AND s.option_type = b.option_type
                AND s.action = 'SOLD'
                AND b.action = 'BOUGHT'
                AND s.timestamp > b.timestamp
            WHERE s.price IS NOT NULL AND b.price IS NOT NULL
        """)
        
        realized_pl = realized_pl_result.rows[0][0] if realized_pl_result.rows and realized_pl_result.rows[0][0] else 0
        
        return jsonify({
            'total_trades': total_trades,
            'bought_trades': bought_trades,
            'sold_trades': sold_trades,
            'realized_pl': realized_pl
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/pl/history', methods=['GET'])
def get_pl_history():
    try:
        result = db_client.execute_sync("""
            SELECT 
                DATE(timestamp) as date,
                SUM(CASE WHEN action = 'BOUGHT' THEN -price * contracts * 100 ELSE 0 END) +
                SUM(CASE WHEN action = 'SOLD' THEN price * contracts * 100 ELSE 0 END) as daily_pl
            FROM trades
            WHERE price IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """)
        
        history = []
        cumulative_pl = 0
        
        for row in result.rows:
            date = row[0]
            daily_pl = row[1] if row[1] else 0
            cumulative_pl += daily_pl
            history.append({
                'date': date,
                'daily_pl': daily_pl,
                'cumulative_pl': cumulative_pl
            })
        
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error fetching P/L history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/pl/realized', methods=['GET'])
def get_realized_pl():
    try:
        result = db_client.execute_sync("""
            SELECT 
                s.ticker,
                s.strike,
                s.option_type,
                s.contracts,
                b.price as entry_price,
                s.price as exit_price,
                (s.price - b.price) * s.contracts * 100 as realized_pl
            FROM trades s
            JOIN trades b ON s.ticker = b.ticker 
                AND s.strike = b.strike 
                AND s.option_type = b.option_type
                AND s.action = 'SOLD'
                AND b.action = 'BOUGHT'
                AND s.timestamp > b.timestamp
            WHERE s.price IS NOT NULL AND b.price IS NOT NULL
            ORDER BY s.timestamp DESC
        """)
        
        realized = []
        for row in result.rows:
            realized.append({
                'ticker': row[0],
                'strike': row[1],
                'option_type': row[2],
                'contracts': row[3],
                'entry_price': row[4],
                'exit_price': row[5],
                'realized_pl': row[6]
            })
        
        return jsonify({'realized_pl': realized})
    except Exception as e:
        logger.error(f"Error fetching realized P/L: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/pl/unrealized', methods=['GET'])
def get_unrealized_pl():
    try:
        positions_result = db_client.execute_sync(
            "SELECT ticker, strike, option_type, quantity, avg_entry_price FROM positions WHERE quantity > 0"
        )
        
        unrealized = []
        
        for row in positions_result.rows:
            ticker = row[0]
            strike = row[1]
            option_type = row[2]
            quantity = row[3]
            avg_entry_price = row[4]
            
            if not avg_entry_price:
                continue
            
            try:
                option_data = option_resolver.get_option_price(ticker, strike, option_type)
                
                if option_data:
                    current_price = None
                    if option_data.get("last") and option_data.get("last") > 0:
                        current_price = float(option_data.get("last"))
                    elif option_data.get("bid") and option_data.get("ask"):
                        current_price = (float(option_data.get("bid", 0)) + float(option_data.get("ask", 0))) / 2.0
                    elif option_data.get("ask"):
                        current_price = float(option_data.get("ask", 0))
                    
                    if current_price:
                        unrealized_pl = (current_price - avg_entry_price) * quantity * 100
                        unrealized.append({
                            'ticker': ticker,
                            'strike': strike,
                            'option_type': option_type,
                            'quantity': quantity,
                            'avg_entry_price': avg_entry_price,
                            'current_price': current_price,
                            'unrealized_pl': unrealized_pl
                        })
            except Exception as e:
                logger.warning(f"Error fetching price for {ticker} {strike}{option_type}: {e}")
                continue
        
        return jsonify({'unrealized_pl': unrealized})
    except Exception as e:
        logger.error(f"Error fetching unrealized P/L: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def get_all_data():
    try:
        stats_result = db_client.execute_sync("SELECT COUNT(*) FROM trades")
        total_trades = stats_result.rows[0][0] if stats_result.rows else 0
        
        bought_trades_result = db_client.execute_sync("SELECT COUNT(*) FROM trades WHERE action = 'BOUGHT'")
        bought_trades = bought_trades_result.rows[0][0] if bought_trades_result.rows else 0
        
        sold_trades_result = db_client.execute_sync("SELECT COUNT(*) FROM trades WHERE action = 'SOLD'")
        sold_trades = sold_trades_result.rows[0][0] if sold_trades_result.rows else 0
        
        realized_pl_result = db_client.execute_sync("""
            SELECT SUM((s.price - b.price) * s.contracts * 100) as realized_pl
            FROM trades s
            JOIN trades b ON s.ticker = b.ticker 
                AND s.strike = b.strike 
                AND s.option_type = b.option_type
                AND s.action = 'SOLD'
                AND b.action = 'BOUGHT'
                AND s.timestamp > b.timestamp
            WHERE s.price IS NOT NULL AND b.price IS NOT NULL
        """)
        realized_pl = realized_pl_result.rows[0][0] if realized_pl_result.rows and realized_pl_result.rows[0][0] else 0
        
        last_trade_result = db_client.execute_sync("SELECT MAX(timestamp) FROM trades")
        last_trade_timestamp = last_trade_result.rows[0][0] if last_trade_result.rows and last_trade_result.rows[0][0] else None
        
        positions_result = db_client.execute_sync(
            "SELECT ticker, strike, option_type, quantity, avg_entry_price, last_updated FROM positions WHERE quantity > 0"
        )
        positions = []
        for row in positions_result.rows:
            positions.append({
                'ticker': row[0],
                'strike': row[1],
                'option_type': row[2],
                'quantity': row[3],
                'avg_entry_price': row[4],
                'last_updated': row[5]
            })
        
        last_position_update_result = db_client.execute_sync("SELECT MAX(last_updated) FROM positions")
        last_position_update = last_position_update_result.rows[0][0] if last_position_update_result.rows and last_position_update_result.rows[0][0] else None
        
        realized_pl_data_result = db_client.execute_sync("""
            SELECT 
                s.ticker,
                s.strike,
                s.option_type,
                s.contracts,
                b.price as entry_price,
                s.price as exit_price,
                (s.price - b.price) * s.contracts * 100 as realized_pl
            FROM trades s
            JOIN trades b ON s.ticker = b.ticker 
                AND s.strike = b.strike 
                AND s.option_type = b.option_type
                AND s.action = 'SOLD'
                AND b.action = 'BOUGHT'
                AND s.timestamp > b.timestamp
            WHERE s.price IS NOT NULL AND b.price IS NOT NULL
            ORDER BY s.timestamp DESC
        """)
        realized_pl_data = []
        for row in realized_pl_data_result.rows:
            realized_pl_data.append({
                'ticker': row[0],
                'strike': row[1],
                'option_type': row[2],
                'contracts': row[3],
                'entry_price': row[4],
                'exit_price': row[5],
                'realized_pl': row[6]
            })
        
        total_realized = sum(item['realized_pl'] for item in realized_pl_data)
        
        unrealized_pl_data = []
        for row in positions_result.rows:
            ticker = row[0]
            strike = row[1]
            option_type = row[2]
            quantity = row[3]
            avg_entry_price = row[4]
            
            if not avg_entry_price:
                continue
            
            try:
                option_data = option_resolver.get_option_price(ticker, strike, option_type)
                
                if option_data:
                    current_price = None
                    if option_data.get("last") and option_data.get("last") > 0:
                        current_price = float(option_data.get("last"))
                    elif option_data.get("bid") and option_data.get("ask"):
                        current_price = (float(option_data.get("bid", 0)) + float(option_data.get("ask", 0))) / 2.0
                    elif option_data.get("ask"):
                        current_price = float(option_data.get("ask", 0))
                    
                    if current_price:
                        unrealized_pl = (current_price - avg_entry_price) * quantity * 100
                        unrealized_pl_data.append({
                            'ticker': ticker,
                            'strike': strike,
                            'option_type': option_type,
                            'quantity': quantity,
                            'avg_entry_price': avg_entry_price,
                            'current_price': current_price,
                            'unrealized_pl': unrealized_pl
                        })
            except Exception as e:
                logger.warning(f"Error fetching price for {ticker} {strike}{option_type}: {e}")
                continue
        
        total_unrealized = sum(item['unrealized_pl'] for item in unrealized_pl_data)
        
        pl_history_result = db_client.execute_sync("""
            SELECT 
                DATE(timestamp) as date,
                SUM(CASE WHEN action = 'BOUGHT' THEN -price * contracts * 100 ELSE 0 END) +
                SUM(CASE WHEN action = 'SOLD' THEN price * contracts * 100 ELSE 0 END) as daily_pl
            FROM trades
            WHERE price IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """)
        pl_history = []
        cumulative_pl = 0
        for row in pl_history_result.rows:
            date = row[0]
            daily_pl = row[1] if row[1] else 0
            cumulative_pl += daily_pl
            pl_history.append({
                'date': date,
                'daily_pl': daily_pl,
                'cumulative_pl': cumulative_pl
            })
        
        ticker_pl = {}
        for item in realized_pl_data:
            ticker = item['ticker']
            if ticker not in ticker_pl:
                ticker_pl[ticker] = 0
            ticker_pl[ticker] += item['realized_pl']
        
        ticker_pl_data = [{'ticker': k, 'pl': v} for k, v in ticker_pl.items()]
        
        return {
            'stats': {
                'total_trades': total_trades,
                'bought_trades': bought_trades,
                'sold_trades': sold_trades,
                'realized_pl': realized_pl
            },
            'pl': {
                'realized': total_realized,
                'unrealized': total_unrealized,
                'realized_pl': realized_pl_data,
                'unrealized_pl': unrealized_pl_data
            },
            'positions': positions,
            'pl_history': pl_history,
            'ticker_pl': ticker_pl_data,
            'last_trade_timestamp': last_trade_timestamp,
            'last_position_update': last_position_update
        }
    except Exception as e:
        logger.error(f"Error fetching all data: {e}", exc_info=True)
        return None

@app.route('/api/stream', methods=['GET'])
def stream_data():
    def generate():
        last_data_hash = None
        
        while True:
            try:
                data = get_all_data()
                if not data:
                    time.sleep(2)
                    continue
                
                payload = {
                    'type': 'update',
                    'data': {
                        'stats': data['stats'],
                        'pl': data['pl'],
                        'positions': data['positions'],
                        'pl_history': data['pl_history'],
                        'ticker_pl': data['ticker_pl']
                    }
                }
                
                current_hash = hash(json.dumps(payload, sort_keys=True))
                
                if current_hash != last_data_hash:
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_data_hash = current_hash
                
                time.sleep(2)
            except Exception as e:
                logger.error(f"Error in stream: {e}", exc_info=True)
                error_payload = {
                    'type': 'error',
                    'message': str(e)
                }
                yield f"data: {json.dumps(error_payload)}\n\n"
                time.sleep(5)
    
    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 4000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')

