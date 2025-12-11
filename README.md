# Discord Trading Bot

Automated trading bot that monitors a Discord channel for trading signals and executes market orders via Tradier API.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Discord token:
```
DISCORD_TOKEN=your_discord_token_here
TRADING_MODE=paper
```

3. Run the bot:
```bash
python main.py
```

## Configuration

- `TRADING_MODE`: Set to "paper" for paper trading or "live" for live trading
- Discord token is read from `.env` file or environment variable
- Tradier API keys and account IDs are configured in `config.py`

## Features

- Monitors Discord channel every 1 second
- Parses trading messages (BOUGHT/SOLD format)
- Resolves option symbols with closest expiry dates
- Places market orders via Tradier API
- Logs successful trades to CSV
- Comprehensive logging to file and console

