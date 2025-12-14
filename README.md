# Discord Trading Bot

Automated trading bot that monitors a Discord channel for trading signals and executes market orders via Tradier API.

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
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

4. Run the Discord trading bot:
```bash
python main.py
```

### Docker Deployment

1. Create a `.env` file with all required environment variables (see `.env.example`)

2. Build and run with Docker Compose:
```bash
docker-compose up -d
```

Or use the convenience script:
```bash
./docker-start.sh
```

3. View logs:
```bash
docker-compose logs -f
```

4. Stop services:
```bash
docker-compose down
```

5. For production deployment:
```bash
docker-compose -f docker-compose.prod.yaml up -d
```

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
- Comprehensive logging to file and console
