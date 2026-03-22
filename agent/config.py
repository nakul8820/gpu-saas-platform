from dotenv import load_dotenv
import os

load_dotenv()

# Platform API base URL
PLATFORM_URL = os.getenv("PLATFORM_URL", "http://127.0.0.1:8000")

# This server's API key — issued when server was registered
API_KEY = os.getenv("API_KEY")

# How often to poll for new jobs (seconds)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 5))

# How often to send heartbeat (seconds)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 30))

# Headers sent with every request to platform
AUTH_HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

if not API_KEY:
    raise ValueError("API_KEY is not set in .env file")