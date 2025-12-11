# Discord Trading Bot

Automated trading bot that monitors a Discord channel for trading signals and executes market orders via Tradier API. Includes a React dashboard for viewing trades, positions, and P/L.

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

2. Create a `.env` file with your credentials (copy from `.env.example`):
```
DISCORD_TOKEN=your_discord_token_here
TRADING_MODE=paper
TRADIER_PAPER_API_KEY=your_key
TRADIER_LIVE_API_KEY=your_key
TRADIER_PAPER_ACCOUNT_ID=your_account_id
TRADIER_LIVE_ACCOUNT_ID=your_account_id
DISCORD_CHANNEL_ID=your_channel_id
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your_auth_token
```

3. Migrate existing CSV data to Turso (if applicable):
```bash
python migrate_csv_to_db.py
```

4. Run the Flask API:
```bash
python app.py
```

5. Run the React frontend (in another terminal):
```bash
cd frontend && npm run dev
```

The frontend will be available at http://localhost:3005 with hot module replacement.

### Docker Deployment

The Docker setup runs both the Flask API backend and React frontend together.

1. Create a `.env` file with all required environment variables (see `.env.example`)

2. Build and run with Docker Compose:
```bash
docker-compose up -d
```

Or use the convenience script:
```bash
./docker-start.sh
```

3. Access the application:
   - **Frontend Dashboard**: http://localhost:3005 (includes both UI and API proxy)
   - **Backend API directly**: http://localhost:4000/api

4. View logs:
```bash
docker-compose logs -f
```

5. Stop services:
```bash
docker-compose down
```

6. For production deployment:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Note**: The frontend nginx server automatically proxies `/api` requests to the backend service, so you only need to access the frontend URL.

## Configuration

- `TRADING_MODE`: Set to "paper" for paper trading or "live" for live trading
- `TURSO_DATABASE_URL`: Your Turso database URL
- `TURSO_AUTH_TOKEN`: Your Turso authentication token
- Discord token and Tradier credentials are read from `.env` file or environment variables

## Features

- Monitors Discord channel for trading signals
- Parses trading messages (BOUGHT/SOLD format) with support for Unicode fractions
- Resolves option symbols with closest expiry dates
- Places market/limit orders via Tradier API
- Stores trades in Turso (libsql) database
- React dashboard with:
  - Trade history with filtering
  - Open positions with unrealized P/L
  - Realized and unrealized P/L summary
  - Charts and statistics
- Comprehensive logging to file and console

