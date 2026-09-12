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
# FEEDBACK
# ============================================================

FEEDBACK_FORM_URL = os.getenv("FEEDBACK_FORM_URL")  # optional — feedback page is hidden from /help if unset

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