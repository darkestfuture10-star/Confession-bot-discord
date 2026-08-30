import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from bot.database.connection import (
    close_database,
    initialize_database,
    test_database_connection,
)
from bot.cogs.confession import ModerationView, PublicConfessionView, ReplyOnlyView
from bot.errors.handlers import handle_app_command_error
from bot.utils.logger import get_logger, setup_logging


# Configuration

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from the .env file."
    )


# Logging

setup_logging()
logger = get_logger("confession_bot")


class ConfessionBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        """Initialize bot services before connecting to Discord."""

        logger.info("Running bot setup...")

        try:
            await test_database_connection()
            logger.info("Database connection successful.")

            await initialize_database()
            logger.info("Database initialized.")

        except Exception:
            logger.exception("Database setup failed.")
            raise

        # Persistent views

        # Approve/Reject buttons on review messages must be re-registered on every
        # restart, or clicks on messages sent before the restart silently fail.
        self.add_view(ModerationView())
        self.add_view(ReplyOnlyView())
        self.add_view(PublicConfessionView())

        # Cogs

        await self.load_extension("bot.cogs.config")
        await self.load_extension("bot.cogs.confession")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.cogs.logs")

        # Slash command synchronization

        synced = await self.tree.sync()

        logger.info(
            "Synced %s slash command(s).",
            len(synced),
        )

    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""

        logger.info(
            "Logged in as %s (ID: %s)",
            self.user,
            self.user.id,
        )

        logger.info(
            "Connected to %s server(s).",
            len(self.guilds),
        )

        logger.info("Confession Bot is ready.")

    async def close(self):
        """Cleanly shut down the bot and database."""

        logger.info("Shutting down Confession Bot...")

        try:
            await close_database()
            logger.info("Database connection closed.")

        except Exception:
            logger.exception(
                "Error while closing the database."
            )

        await super().close()

        logger.info("Confession Bot shutdown complete.")


bot = ConfessionBot()


# Command

@bot.tree.command(
    name="status",
    description="Check the current status of the confession bot.",
)
async def status(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🟢 **Confession Bot is online!**\n"
        f"Latency: `{latency}ms`"
    )


# Command Error Handler

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    await handle_app_command_error(
        interaction,
        error,
    )


# Start Bot

if __name__ == "__main__":
    logger.info("Starting Confession Bot...")
    bot.run(TOKEN)