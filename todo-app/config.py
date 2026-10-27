import os
from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if present (never committed)


class Config:
    # Signs the session cookie. If this changes, every existing sessionbecomes invalid 
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
 
    # How long a password-reset link stays valid.
    RESET_TOKEN_MAX_AGE_MINUTES = 30
