"""Runtime configuration loaded from the environment / .env."""

import os
from dotenv import load_dotenv

load_dotenv()

CMC_API_KEY = os.getenv("CMC_API_KEY", "")
CMC_BASE_URL = os.getenv("CMC_BASE_URL", "https://pro-api.coinmarketcap.com")
