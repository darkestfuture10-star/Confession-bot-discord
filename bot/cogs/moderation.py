from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.connection import get_session
from bot.database.repository import ConfessionRepository, RestrictionRepository, ServerRepository
from bot.services.logging_service import send_event_log
from bot.services.security_service import waive_next_submission
from bot.utils.embeds import theme_color
from bot.utils.helpers import parse_duration
from bot.utils.pagination import FieldPaginatorView
from bot.utils.permissions import can_moderate


ACTION_LABELS = {
    "submitted": "📝 Submitted",
    "approved": "✅ Approved",
    "rejected": "❌ Rejected",
    "publication_failed": "⚠️ Publication failed",
    "review_delivery_failed": "⚠️ Review delivery failed",
    "deleted": "🗑️ Deleted",
    "deleted_externally": "🗑️ Removed externally",
}
LIST_FETCH_LIMIT = 100  # generous fetch cap; the paginator handles display


async def build_dashboard_embed(server, session) -> discord.Embed:
    confessions = ConfessionRepository(session)
    restrictions = RestrictionRepository(session)

    counts = await confessions.count_by_status(server.id)
    active_restrictions = await restrictions.count_active(server.id)

    embed = discord.Embed(title="🛡️ Moderator Dashboard", color=theme_color(server.theme))
    embed.add_field(name="⏳ Pending", value=str(counts.get("pending", 0)), inline=True)
    embed.add_field(name="✅ Approved", value=str(counts.get("approved", 0)), inline=True)
    embed.add_field(name="❌ Rejected", value=str(counts.get("rejected", 0)), inline=True)
    deleted_count = counts.get("deleted", 0) + counts.get("deleted_externally", 0)
    embed.add_field(name="🗑️ Deleted", value=str(deleted_count), inline=True)
    embed.add_field(name="🔨 Active Restrictions", value=str(active_restrictions), inline=True)
    embed.set_footer(text="Search logs or view restricted users below.")
    return embed


async def build_logs_embed(confession_id: int, guild_id: int, server, session) -> discord.Embed | None:
    confessions = ConfessionRepository(session)
    confession = await confessions.get(confession_id, guild_id)
    if confession is None:
        return None
    entries = await confessions.get_logs(confession_id)

    embed = discord.Embed(title=f"Audit trail — Confession #{confession_id}", color=theme_color(server.theme))
    embed.add_field(name="Current status", value=confession.status, inline=False)
    if not entries:
        embed.description = "No log entries were recorded for this confession."
    else:
        for entry in entries:
            label = ACTION_LABELS.get(entry.action, entry.action)
            actor = f"<@{entry.actor_id}>" if entry.actor_id else "System"
            timestamp = discord.utils.format_dt(entry.created_at.replace(tzinfo=timezone.utc), style="f")
            value = f"By: {actor}\nAt: {timestamp}"
            if entry.details:
                value += f"\nDetails: {entry.details}"
            embed.add_field(name=label, value=value, inline=False)
    return embed


def _queue_fields(pending) -> list[tuple[str, str]]:
    fields = []
    for confession in pending:
        preview = confession.content if len(confession.content) <= 100 else confession.content[:97] + "..."
        submitted = discord.utils.format_dt(confession.submitted_at.replace(tzinfo=timezone.utc), style="R")
        fields.append((f"#{confession.id} — submitted {submitted}", preview))
    return fields


def _restriction_fields(restrictions) -> list[tuple[str, str]]:
    fields = []
    for restriction in restrictions:
        expiry = (
            discord.utils.format_dt(restriction.expires_at.replace(tzinfo=timezone.utc), style="R")
            if restriction.expires_at else "Permanent"
        )
        fields.append((
            f"<@{restriction.user_id}>",
            f"Expires: {expiry}\nReason: {restriction.reason or 'No reason given'}\nBy: <@{restriction.moderator_id}>",
        ))
    return fields


def _moderator_stat_fields(stats: dict) -> list[tuple[str, str]]:
    ranked = sorted(stats.items(), key=lambda item: sum(item[1].values()), reverse=True)
    fields = []
    for rank, (moderator_id, counts) in enumerate(ranked, start=1):
        total = sum(counts.values())
        fields.append((
            f"#{rank} — {total} actions",
            f"<@{moderator_id}>\n✅ Approved: {counts['approved']} · ❌ Rejected: {counts['rejected']} · 🗑️ Deleted: {counts['deleted']}",
        ))
    return fields


async def _send(interaction: discord.Interaction, content: str = None, **kwargs) -> None:
    """Route through followup if the interaction was already deferred/responded
    to, otherwise send a direct response."""
    if interaction.response.is_done():
        await interaction.followup.send(content, **kwargs)
    else:
        await interaction.response.send_message(content, **kwargs)


async def _authorize(interaction: discord.Interaction):
    """Fetches the server config and verifies the user can moderate.
    Sends an ephemeral error and returns None if not authorized; otherwise
    returns the Server. Safe to call before or after the caller has deferred."""
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await _send(interaction, "❌ This can only be used in a server.", ephemeral=True)
        return None
    session = get_session()
    try:
        server = await ServerRepository(session).get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await _send(interaction, "❌ You do not have permission to do this.", ephemeral=True)
            return None
        return server
    finally:
        await session.close()


async def _perform_restrict(interaction: discord.Interaction, target_id: int, duration_text: str | None, reason: str | None) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
        return

    expires_at = None
    if duration_text:
        try:
            expires_at = datetime.utcnow() + parse_duration(duration_text)
        except ValueError as error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.followup.send("❌ You do not have permission to restrict users.", ephemeral=True)
            return
        await RestrictionRepository(session).create(interaction.guild.id, target_id, interaction.user.id, reason, expires_at)
    finally:
        await session.close()

    duration_display = f"until {discord.utils.format_dt(expires_at.replace(tzinfo=timezone.utc), style='f')}" if expires_at else "permanently"
    fields = [("Reason", reason)] if reason else None
    await send_event_log(
        interaction.guild, server, "🔨 User Restricted",
        description=f"<@{target_id}> was restricted {duration_display} by {interaction.user.mention}.",
        fields=fields,
    )
    await interaction.followup.send(f"✅ <@{target_id}> is restricted {duration_display}.", ephemeral=True)


async def _perform_unrestrict(interaction: discord.Interaction, target_id: int) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
        return

    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.followup.send("❌ You do not have permission to unrestrict users.", ephemeral=True)
            return
        lifted = await RestrictionRepository(session).lift(interaction.guild.id, target_id, interaction.user.id)
    finally:
        await session.close()

    if not lifted:
        await interaction.followup.send(f"ℹ️ <@{target_id}> doesn't have an active restriction.", ephemeral=True)
        return

    await send_event_log(
        interaction.guild, server, "🔓 Restriction Lifted",
        description=f"<@{target_id}>'s restriction was lifted by {interaction.user.mention}.",
    )
    await interaction.followup.send(f"✅ <@{target_id}>'s restriction has been lifted.", ephemeral=True)


async def _perform_waive(interaction: discord.Interaction, target_id: int) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
        return

    server = None
    session = get_session()
    try:
        servers = ServerRepository(session)
        server = await servers.get(interaction.guild.id)
        if server is None or not can_moderate(interaction.user, server.moderator_role_id):
            await interaction.followup.send("❌ You do not have permission to do this.", ephemeral=True)
            return
    finally:
        await session.close()

    waive_next_submission(interaction.guild.id, target_id)

    await send_event_log(
        interaction.guild, server, "⏱️ Cooldown Waived",
        description=f"<@{target_id}>'s cooldown/rate-limit was waived for their next submission by {interaction.user.mention}.",
    )
    await interaction.followup.send(f"✅ <@{target_id}>'s cooldown is waived — their next submission will skip the cooldown and hourly limit.", ephemeral=True)


class PanelDeleteModal(discord.ui.Modal, title="Delete a confession"):
    confession_id = discord.ui.TextInput(label="Confession ID", required=True, max_length=10)
    reason = discord.ui.TextInput(label="Reason", required=True, max_length=500, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            confession_id = int(str(self.confession_id).strip())
        except ValueError:
            await interaction.response.send_message("❌ Confession ID must be a number.", ephemeral=True)
            return
        from bot.cogs.confession import delete_confession
        await delete_confession(interaction, confession_id, str(self.reason))


class PanelRestrictModal(discord.ui.Modal, title="Restrict user"):
    duration = discord.ui.TextInput(label="Duration (e.g. 2h, 3d) — blank = permanent", required=False, max_length=20)
    reason = discord.ui.TextInput(label="Reason (optional)", required=False, max_length=500, style=discord.TextStyle.paragraph)

    def __init__(self, target_id: int):
        super().__init__()
        self.target_id = target_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await _perform_restrict(
            interaction, self.target_id,
            str(self.duration).strip() or None,
            str(self.reason).strip() or None,
        )


class SearchLogsModal(discord.ui.Modal, title="Search confession logs"):
    confession_id = discord.ui.TextInput(label="Confession ID", required=True, max_length=10)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = await _authorize(interaction)
        if server is None:
            return
        try:
            confession_id = int(str(self.confession_id).strip())
        except ValueError:
            await interaction.followup.send("❌ Confession ID must be a number.", ephemeral=True)
            return

        session = get_session()
        try:
            embed = await build_logs_embed(confession_id, interaction.guild.id, server, session)
        finally:
            await session.close()

        if embed is None:
            await interaction.followup.send("❌ No confession with that ID exists in this server.", ephemeral=True)
            return
        await interaction.followup.send(embed=embed, ephemeral=True)


class UserPickerView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)
        self.mode = mode
        select = discord.ui.UserSelect(placeholder="Select a user")
        select.callback = self.on_select
        self.add_item(select)
        self.select = select

    async def on_select(self, interaction: discord.Interaction) -> None:
        target = self.select.values[0]
        if self.mode == "restrict":
            # Modals must be the direct/immediate response — cannot defer first.
            await interaction.response.send_modal(PanelRestrictModal(target.id))
        elif self.mode == "unrestrict":
            await _perform_unrestrict(interaction, target.id)
        elif self.mode == "waive":
            await _perform_waive(interaction, target.id)


class ModerationPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="📋 Queue", style=discord.ButtonStyle.primary)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = await _authorize(interaction)
        if server is None:
            return
        session = get_session()
        try:
            if not server.approval_enabled:
                await interaction.followup.send("ℹ️ Moderator approval is currently disabled, so nothing is queued.", ephemeral=True)
                return
            pending = await ConfessionRepository(session).list_pending(interaction.guild.id, limit=LIST_FETCH_LIMIT)
        finally:
            await session.close()

        if not pending:
            await interaction.followup.send("✅ No confessions are currently awaiting review.", ephemeral=True)
            return

        paginator = FieldPaginatorView(
            "Confessions awaiting review", theme_color(server.theme), _queue_fields(pending),
            empty_message="No confessions are currently awaiting review.",
        )
        await interaction.followup.send(embed=paginator.build_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        await interaction.response.send_modal(PanelDeleteModal())

    @discord.ui.button(label="🔨 Restrict User", style=discord.ButtonStyle.secondary)
    async def restrict(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        await interaction.response.send_message("Select a user to restrict.", view=UserPickerView("restrict"), ephemeral=True)

    @discord.ui.button(label="🔓 Unrestrict User", style=discord.ButtonStyle.secondary)
    async def unrestrict(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        await interaction.response.send_message("Select a user to unrestrict.", view=UserPickerView("unrestrict"), ephemeral=True)

    @discord.ui.button(label="⏱️ Waive Cooldown", style=discord.ButtonStyle.secondary)
    async def waive(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        await interaction.response.send_message(
            "Select a user to waive the cooldown/rate-limit for (their next submission only).",
            view=UserPickerView("waive"), ephemeral=True,
        )


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()

        server = await _authorize(interaction)
        if server is None:
            return
        session = get_session()
        try:
            embed = await build_dashboard_embed(server, session)
        finally:
            await session.close()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🔍 Search Logs", style=discord.ButtonStyle.primary)
    async def search_logs(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        await interaction.response.send_modal(SearchLogsModal())

    @discord.ui.button(label="👥 Restricted Users", style=discord.ButtonStyle.primary)
    async def restricted_users(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = await _authorize(interaction)
        if server is None:
            return
        session = get_session()
        try:
            active = await RestrictionRepository(session).list_active(interaction.guild.id, limit=LIST_FETCH_LIMIT)
        finally:
            await session.close()

        paginator = FieldPaginatorView(
            "Currently restricted users", theme_color(server.theme), _restriction_fields(active),
            empty_message="No active restrictions.",
        )
        await interaction.followup.send(embed=paginator.build_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="🔧 Permissions", style=discord.ButtonStyle.secondary)
    async def permissions(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        server = await _authorize(interaction)
        if server is None:
            return

        required = ["send_messages", "embed_links", "manage_messages", "read_message_history"]
        lines = []
        for label, channel_id in (("Confession channel", server.confession_channel_id), ("Logging channel", server.logging_channel_id)):
            if not channel_id:
                lines.append(f"**{label}:** not configured")
                continue
            channel = interaction.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                lines.append(f"**{label}:** channel not found")
                continue
            perms = channel.permissions_for(interaction.guild.me)
            missing = [name.replace("_", " ").title() for name in required if not getattr(perms, name)]
            lines.append(f"**{label}** ({channel.mention}): " + ("✅ All good" if not missing else "⚠️ Missing " + ", ".join(missing)))

        embed = discord.Embed(title="🔧 Bot Permission Check", description="\n".join(lines), color=theme_color(server.theme))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="👮 Moderator Stats", style=discord.ButtonStyle.secondary)
    async def moderator_stats(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = await _authorize(interaction)
        if server is None:
            return
        session = get_session()
        try:
            stats = await ConfessionRepository(session).moderator_stats(interaction.guild.id)
        finally:
            await session.close()

        paginator = FieldPaginatorView(
            "👮 Moderator Statistics", theme_color(server.theme), _moderator_stat_fields(stats),
            empty_message="No moderation actions recorded yet.",
        )
        await interaction.followup.send(embed=paginator.build_embed(), view=paginator, ephemeral=True)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="moderation-panel", description="Moderator action panel: queue, delete, restrict/unrestrict (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    async def moderation_panel(self, interaction: discord.Interaction) -> None:
        server = await _authorize(interaction)
        if server is None:
            return
        embed = discord.Embed(
            title="🛠️ Moderation Panel",
            description="Use the buttons below to manage confessions and users.",
            color=theme_color(server.theme),
        )
        await interaction.response.send_message(embed=embed, view=ModerationPanelView(), ephemeral=True)

    @app_commands.command(name="moderator-dashboard", description="View confession moderation stats and logs (moderators only).")
    @app_commands.default_permissions(manage_messages=True)
    async def moderator_dashboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = await _authorize(interaction)
        if server is None:
            return
        session = get_session()
        try:
            embed = await build_dashboard_embed(server, session)
        finally:
            await session.close()
        await interaction.followup.send(embed=embed, view=DashboardView(), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))