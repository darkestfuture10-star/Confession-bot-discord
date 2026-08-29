from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, ServerRepository
from bot.utils.permissions import can_moderate


ACTION_LABELS = {
    "submitted": "📝 Submitted",
    "approved": "✅ Approved",
    "rejected": "❌ Rejected",
    "publication_failed": "⚠️ Publication failed",
    "review_delivery_failed": "⚠️ Review delivery failed",
}


class Logs(commands.Cog):
    """Read-only access to the moderation audit trail for individual confessions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="confession-logs",
        description="View the moderation audit trail for a confession (moderators only).",
    )
    @app_commands.describe(confession_id="The confession ID to look up")
    async def confession_logs(self, interaction: discord.Interaction, confession_id: int) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to view confession logs.", ephemeral=True)
                return

            confessions = ConfessionRepository(session)
            confession = await confessions.get(confession_id, interaction.guild.id)
            if confession is None:
                await interaction.response.send_message("❌ No confession with that ID exists in this server.", ephemeral=True)
                return

            entries = await confessions.get_logs(confession_id)
        finally:
            await session.close()

        embed = discord.Embed(
            title=f"Audit trail — Confession #{confession_id}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Current status", value=confession.status, inline=False)

        if not entries:
            embed.description = "No log entries were recorded for this confession."
        else:
            for entry in entries:
                label = ACTION_LABELS.get(entry.action, entry.action)
                actor = f"<@{entry.actor_id}>" if entry.actor_id else "System"
                timestamp = discord.utils.format_dt(
                    entry.created_at.replace(tzinfo=timezone.utc),
                    style="f",
                )
                value = f"By: {actor}\nAt: {timestamp}"
                if entry.details:
                    value += f"\nDetails: {entry.details}"
                embed.add_field(name=label, value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logs(bot))
