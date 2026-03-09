import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

TRADIER_PAPER_API_KEY = os.getenv("TRADIER_PAPER_API_KEY", "")
TRADIER_LIVE_API_KEY = os.getenv("TRADIER_LIVE_API_KEY", "")

TRADIER_PAPER_ACCOUNT_ID = os.getenv("TRADIER_PAPER_ACCOUNT_ID", "")
TRADIER_LIVE_ACCOUNT_ID = os.getenv("TRADIER_LIVE_ACCOUNT_ID", "")

TRADING_MODE = os.getenv("TRADING_MODE", "live")
TRADING_MODE_CHANNEL_2 = os.getenv("TRADING_MODE_CHANNEL_2", "paper")

DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")
DISCORD_CHANNEL_ID_2 = os.getenv("DISCORD_CHANNEL_ID_2", "")

USE_WEBHOOK = os.getenv("USE_WEBHOOK", "").lower() in ("1", "true", "yes")
WEBHOOK_APP_ID_ALLOWED = os.getenv("WEBHOOK_APP_ID_ALLOWED", "com.hnc.Discord,com.hnc.discord")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "80"))
WEBHOOK_SUBTITLE_CHANNEL_2 = os.getenv("WEBHOOK_SUBTITLE_CHANNEL_2", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

TRADIER_BASE_URL_PAPER = "https://sandbox.tradier.com/v1"
TRADIER_BASE_URL_LIVE = "https://api.tradier.com/v1"

def get_tradier_api_key(mode=None):
    if mode is None:
        mode = TRADING_MODE
    return TRADIER_PAPER_API_KEY if mode == "paper" else TRADIER_LIVE_API_KEY

def get_tradier_account_id(mode=None):
    if mode is None:
        mode = TRADING_MODE
    return TRADIER_PAPER_ACCOUNT_ID if mode == "paper" else TRADIER_LIVE_ACCOUNT_ID

def get_tradier_base_url(mode=None):
    if mode is None:
        mode = TRADING_MODE
    return TRADIER_BASE_URL_PAPER if mode == "paper" else TRADIER_BASE_URL_LIVE

