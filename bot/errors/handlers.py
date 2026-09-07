import logging

import discord
from discord import app_commands


logger = logging.getLogger("confession_bot.errors")


async def handle_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    """
    Centralized handler for slash-command errors.
    """

    logger.error(
        "Command error in %s",
        interaction.command.name if interaction.command else "unknown",
        exc_info=error,
    )

    message = (
        "❌ Something went wrong while processing that command.\n"
        "Please try again later."
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )
    except discord.HTTPException:
        # The interaction may already be invalid/expired (e.g. it timed out
        # before the original command could respond) — nothing more we can
        # do to notify the user. Without this, that secondary failure
        # surfaces as an unhandled "exception was never retrieved" instead
        # of a clean log line.
        logger.warning(
            "Could not deliver error message for command %s — interaction likely expired.",
            interaction.command.name if interaction.command else "unknown",
        )