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

### Webhook mode

Set `USE_WEBHOOK=true` to disable Discord API scraping and receive trading data via HTTP webhooks. The bot listens for `POST /webhook/discord` with JSON:

| Field | Type | Description |
|-------|------|-------------|
| `app_id` | string | App identifier (e.g. `com.hnc.Discord`). Must match one of the comma-separated values in `WEBHOOK_APP_ID_ALLOWED` (case-insensitive). |
| `title` | string | Notification title (e.g. server name). |
| `subtitle` | string | Notification subtitle (e.g. `#channel`). Used to route to channel 2 when listed in `WEBHOOK_SUBTITLE_CHANNEL_2`. |
| `body` | string | Message body (parseable trading text). |
| `delivered_date` | number \| null | Unix timestamp in seconds, or null. |
| `delivered_date_iso` | string | Human-readable UTC time, or empty string. |

Example payload formats:

- **body** (parseable trading text): `**BOUGHT** CRCL 4/17 150C $3.40 [SMALL] @everyone` (or equivalent SOLD formats with `[SMALL]`, `[LOTTO]`, `[GRADE A]`, etc.)
- **title** (source metadata): `Twinsight Bot⁩ (⁨#🚨︱pro-alerts⁩, ⁨TRADING FLOOR⁩)`
- **subtitle**: Used for channel routing; add e.g. `#🚨︱pro-alerts` to `WEBHOOK_SUBTITLE_CHANNEL_2` to route Twinsight alerts to channel 2.

- `WEBHOOK_PORT`: Port for the webhook server (default 8080).
- `WEBHOOK_SUBTITLE_CHANNEL_2`: Comma-separated subtitles that route to channel 2. If the body contains `@AlertTC`, the message is always routed to channel 2 (e.g. `#ALERT BOUGHT SPX 6900C 3/11 $2.4 [SMALL] @AlertTC`).

## Features

- Monitors Discord channel for trading signals (or receives them via webhook when `USE_WEBHOOK=true`)
- Parses trading messages (BOUGHT/SOLD format) with support for Unicode fractions
- Resolves option symbols with closest expiry dates
- Places market/limit orders via Tradier API
- Stores trades in Turso (libsql) database
- Comprehensive logging to file and console

### Logging on the server

Logs are written to `logs/trading_bot.log` and to **stderr** (so Nixpacks, Railway, Docker, etc. show them in deploy/runtime logs). The app uses line buffering when possible. For Nixpacks, `nixpacks.toml` sets `PYTHONUNBUFFERED=1`. If logs still don’t appear, set `PYTHONUNBUFFERED=1` in your platform’s environment. Use `LOG_LEVEL` (default `INFO`) to control verbosity.
