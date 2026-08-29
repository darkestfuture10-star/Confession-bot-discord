from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, ServerRepository
from bot.utils.permissions import can_moderate


class Moderation(commands.Cog):
    """Moderator tools that sit alongside the per-message Approve/Reject buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="confession-queue",
        description="List confessions awaiting review (moderators only).",
    )
    async def confession_queue(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to moderate confessions.", ephemeral=True)
                return

            if not server.approval_enabled:
                await interaction.response.send_message("ℹ️ Moderator approval is currently disabled, so nothing is queued.", ephemeral=True)
                return

            pending = await ConfessionRepository(session).list_pending(interaction.guild.id)
        finally:
            await session.close()

        if not pending:
            await interaction.response.send_message("✅ No confessions are currently awaiting review.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Confessions awaiting review",
            description=(
                "Approve or reject these from their original review message. "
                "This list is a recovery tool if that message was deleted or scrolled past."
            ),
            color=discord.Color.gold(),
        )

        for confession in pending:
            preview = confession.content if len(confession.content) <= 100 else confession.content[:97] + "..."
            submitted = discord.utils.format_dt(
                confession.submitted_at.replace(tzinfo=timezone.utc),
                style="R",
            )
            embed.add_field(
                name=f"#{confession.id} — submitted {submitted}",
                value=preview,
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
