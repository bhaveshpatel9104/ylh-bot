"""
YouLikeHits YouTube Likes Automation Bot
=========================================
Configuration settings — credentials hardcoded as fallback
"""

import os
from dotenv import load_dotenv

load_dotenv()

# YouLikeHits credentials
YLH_USERNAME  = os.getenv("YLH_USERNAME",  "bhavesh647383")
YLH_PASSWORD  = os.getenv("YLH_PASSWORD",  "BHAVESH91045678VV")

# YouLikeHits login accepts email too
YLH_LOGIN_ID  = os.getenv("YLH_LOGIN_ID",  "patelbhavesh9130@gmail.com")

# Google/YouTube credentials
GOOGLE_EMAIL    = os.getenv("GOOGLE_EMAIL",    "patelbhavesh9130@gmail.com")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "BHAVESH9104VV")

# Bot behavior
HEADLESS              = os.getenv("HEADLESS", "false").lower() == "true"
MIN_DELAY             = int(os.getenv("MIN_DELAY", "3"))
MAX_DELAY             = int(os.getenv("MAX_DELAY", "7"))
MAX_LIKES_PER_SESSION = int(os.getenv("MAX_LIKES_PER_SESSION", "0"))  # 0 = unlimited

# URLs
YLH_LOGIN_URL        = "https://www.youlikehits.com/login.php"
YLH_YOUTUBE_LIKES_URL = "https://www.youlikehits.com/youtubelikes.php"

# Logging
LOG_FILE = "logs/activity.log"
