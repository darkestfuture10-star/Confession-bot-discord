import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, ServerRepository
from bot.utils.embeds import theme_color
from bot.utils.permissions import can_moderate


async def build_logs_embed(
    confession_id: int,
    guild_id: int,
    server,
    session,
) -> discord.Embed | None:
    confessions = ConfessionRepository(session)

    confession = await confessions.get(confession_id, guild_id)

    if confession is None:
        return None

    entries = await confessions.get_logs(confession_id)

    embed = discord.Embed(
        title=f"Audit trail — Confession #{confession_id}",
        color=theme_color(server.theme),
    )

    embed.add_field(
        name="Current status",
        value=confession.status,
        inline=False,
    )

    if not entries:
        embed.description = "No log entries were recorded for this confession."
        return embed

    for entry in entries:
        label = ACTION_LABELS.get(entry.action, entry.action)
        actor = f"<@{entry.actor_id}>" if entry.actor_id else "System"

        timestamp = discord.utils.format_dt(
            entry.created_at,
            style="f",
        )

        value = f"By: {actor}\nAt: {timestamp}"

        if entry.details:
            value += f"\nDetails: {entry.details}"

        embed.add_field(
            name=label,
            value=value,
            inline=False,
        )

    return embed


async def authorize_moderator(
    interaction: discord.Interaction,
):
    if (
        interaction.guild is None
        or not isinstance(interaction.user, discord.Member)
    ):
        await interaction.response.send_message(
            "❌ This can only be used in a server.",
            ephemeral=True,
        )
        return None

    session = get_session()

    try:
        server = await ServerRepository(session).get(
            interaction.guild.id
        )

        if server is None or not can_moderate(
            interaction.user,
            server.moderator_role_id,
        ):
            await interaction.response.send_message(
                "❌ You do not have permission to view confession logs.",
                ephemeral=True,
            )
            return None

        return server

    finally:
        await session.close()


class SearchLogsModal(discord.ui.Modal, title="Search confession logs"):
    confession_id = discord.ui.TextInput(
        label="Confession ID",
        required=True,
        max_length=10,
    )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        server = await authorize_moderator(interaction)

        if server is None:
            return

        try:
            confession_id = int(
                str(self.confession_id).strip()
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Confession ID must be a number.",
                ephemeral=True,
            )
            return

        session = get_session()

        try:
            embed = await build_logs_embed(
                confession_id,
                interaction.guild.id,
                server,
                session,
            )
        finally:
            await session.close()

        if embed is None:
            await interaction.response.send_message(
                "❌ No confession with that ID exists in this server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="confession-logs",
        description="View the moderation audit trail for a confession (moderators only).",
    )
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        confession_id="The confession ID to look up"
    )
    async def confession_logs(
        self,
        interaction: discord.Interaction,
        confession_id: int,
    ) -> None:
        server = await authorize_moderator(interaction)

        if server is None:
            return

        session = get_session()

        try:
            embed = await build_logs_embed(
                confession_id,
                interaction.guild.id,
                server,
                session,
            )
        finally:
            await session.close()

        if embed is None:
            await interaction.response.send_message(
                "❌ No confession with that ID exists in this server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Logs(bot))