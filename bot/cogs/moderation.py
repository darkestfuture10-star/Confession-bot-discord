from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, RestrictionRepository, ServerRepository
from bot.services.logging_service import send_event_log
from bot.utils.embeds import theme_color
from bot.utils.helpers import parse_duration
from bot.utils.permissions import can_moderate


async def build_queue_embed(server, pending) -> discord.Embed:
    embed = discord.Embed(
        title="Confessions awaiting review",
        description=(
            "Approve or reject these from their original review message. "
            "This list is a recovery tool if that message was deleted or scrolled past."
        ),
        color=theme_color(server.theme),
    )
    for confession in pending:
        preview = confession.content if len(confession.content) <= 100 else confession.content[:97] + "..."
        submitted = discord.utils.format_dt(confession.submitted_at.replace(tzinfo=timezone.utc), style="R")
        embed.add_field(name=f"#{confession.id} — submitted {submitted}", value=preview, inline=False)
    return embed


async def build_dashboard_embed(server, session) -> discord.Embed:
    confessions = ConfessionRepository(session)
    restrictions = RestrictionRepository(session)

    counts = await confessions.count_by_status(server.id)
    active_restrictions = await restrictions.count_active(server.id)

    embed = discord.Embed(title="🛡️ Moderator Dashboard", color=theme_color(server.theme))
    embed.add_field(name="⏳ Pending", value=str(counts.get("pending", 0)), inline=True)
    embed.add_field(name="✅ Approved", value=str(counts.get("approved", 0)), inline=True)
    embed.add_field(name="❌ Rejected", value=str(counts.get("rejected", 0)), inline=True)
    embed.add_field(name="🗑️ Deleted", value=str(counts.get("deleted", 0)), inline=True)
    embed.add_field(name="🔨 Active Restrictions", value=str(active_restrictions), inline=True)
    embed.set_footer(text="Use the buttons below for quick actions.")
    return embed


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to view the dashboard.", ephemeral=True)
                return
            embed = await build_dashboard_embed(server, session)
        finally:
            await session.close()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📋 Queue", style=discord.ButtonStyle.primary)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to moderate confessions.", ephemeral=True)
                return
            pending = await ConfessionRepository(session).list_pending(interaction.guild.id)
            embed = await build_queue_embed(server, pending)
        finally:
            await session.close()
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Moderation(commands.Cog):
    """Moderator tools that sit alongside the per-message Approve/Reject buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="moderator-dashboard", description="View confession moderation stats (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    async def moderator_dashboard(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to view the dashboard.", ephemeral=True)
                return
            embed = await build_dashboard_embed(server, session)
        finally:
            await session.close()
        await interaction.response.send_message(embed=embed, view=DashboardView(), ephemeral=True)

    @app_commands.command(name="confession-queue", description="List confessions awaiting review (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
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
            if not pending:
                await interaction.response.send_message("✅ No confessions are currently awaiting review.", ephemeral=True)
                return
            embed = await build_queue_embed(server, pending)
        finally:
            await session.close()

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="confession-delete", description="Delete a posted confession (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(confession_id="The confession ID to delete", reason="Why this confession is being deleted")
    async def confession_delete(self, interaction: discord.Interaction, confession_id: int, reason: str) -> None:
        from bot.cogs.confession import delete_confession
        await delete_confession(interaction, confession_id, reason)

    @app_commands.command(name="restrict-user", description="Block a user from submitting confessions (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        user="The user to restrict",
        duration="e.g. 10m, 2h, 3d, 1w — leave empty for a permanent restriction",
        reason="Why this user is being restricted",
    )
    async def restrict_user(self, interaction: discord.Interaction, user: discord.Member, duration: str | None = None, reason: str | None = None) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        expires_at = None
        if duration:
            try:
                expires_at = datetime.utcnow() + parse_duration(duration)
            except ValueError as error:
                await interaction.response.send_message(f"❌ {error}", ephemeral=True)
                return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to restrict users.", ephemeral=True)
                return
            await RestrictionRepository(session).create(interaction.guild.id, user.id, interaction.user.id, reason, expires_at)
        finally:
            await session.close()

        duration_text = f"until {discord.utils.format_dt(expires_at.replace(tzinfo=timezone.utc), style='f')}" if expires_at else "permanently"
        fields = [("Reason", reason)] if reason else None
        await send_event_log(
            interaction.guild, server, "🔨 User Restricted",
            description=f"{user.mention} was restricted {duration_text} by {interaction.user.mention}.",
            fields=fields,
        )
        await interaction.response.send_message(f"✅ {user.mention} is restricted {duration_text}.", ephemeral=True)

    @app_commands.command(name="unrestrict-user", description="Lift a user's confession restriction (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(user="The user to unrestrict")
    async def unrestrict_user(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to unrestrict users.", ephemeral=True)
                return
            lifted = await RestrictionRepository(session).lift(interaction.guild.id, user.id, interaction.user.id)
        finally:
            await session.close()

        if not lifted:
            await interaction.response.send_message(f"ℹ️ {user.mention} doesn't have an active restriction.", ephemeral=True)
            return

        await send_event_log(
            interaction.guild, server, "🔓 Restriction Lifted",
            description=f"{user.mention}'s restriction was lifted by {interaction.user.mention}.",
        )
        await interaction.response.send_message(f"✅ {user.mention}'s restriction has been lifted.", ephemeral=True)

    @app_commands.command(name="restrictions", description="List currently restricted users (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    async def restrictions(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to view restrictions.", ephemeral=True)
                return
            active = await RestrictionRepository(session).list_active(interaction.guild.id)
        finally:
            await session.close()

        embed = discord.Embed(title="Currently restricted users", color=theme_color(server.theme))
        if not active:
            embed.description = "No active restrictions."
        else:
            for restriction in active:
                expiry = (
                    discord.utils.format_dt(restriction.expires_at.replace(tzinfo=timezone.utc), style="R")
                    if restriction.expires_at else "Permanent"
                )
                embed.add_field(
                    name=f"<@{restriction.user_id}>",
                    value=f"Expires: {expiry}\nReason: {restriction.reason or 'No reason given'}\nBy: <@{restriction.moderator_id}>",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))