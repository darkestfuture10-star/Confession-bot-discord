import os

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# DISCORD
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# VALIDATION
# ============================================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from the .env file."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing from the .env file."
    )