import logging


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)


def setup_logging():
    """
    Configure the application's logging system.

    This should be called once when the bot starts.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger for the requested module.
    """

    return logging.getLogger(name)