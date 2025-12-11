import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

TRADIER_PAPER_API_KEY = os.getenv("TRADIER_PAPER_API_KEY", "")
TRADIER_LIVE_API_KEY = os.getenv("TRADIER_LIVE_API_KEY", "")

TRADIER_PAPER_ACCOUNT_ID = os.getenv("TRADIER_PAPER_ACCOUNT_ID", "")
TRADIER_LIVE_ACCOUNT_ID = os.getenv("TRADIER_LIVE_ACCOUNT_ID", "")

TRADING_MODE = os.getenv("TRADING_MODE", "live")

DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")

TRADIER_BASE_URL_PAPER = "https://sandbox.tradier.com/v1"
TRADIER_BASE_URL_LIVE = "https://api.tradier.com/v1"

def get_tradier_api_key():
    return TRADIER_PAPER_API_KEY if TRADING_MODE == "paper" else TRADIER_LIVE_API_KEY

def get_tradier_account_id():
    return TRADIER_PAPER_ACCOUNT_ID if TRADING_MODE == "paper" else TRADIER_LIVE_ACCOUNT_ID

def get_tradier_base_url():
    return TRADIER_BASE_URL_PAPER if TRADING_MODE == "paper" else TRADIER_BASE_URL_LIVE

