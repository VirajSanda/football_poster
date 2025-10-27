import os

class Config:
    FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
    FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
    API_BASE_URL = os.getenv("API_BASE_URL")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    # Your collector channel (or multiple ones)
    ALLOWED_CHANNELS = [
        ch.strip()
        for ch in os.getenv("ALLOWED_CHANNELS", "").split(",")
        if ch.strip()
    ]
