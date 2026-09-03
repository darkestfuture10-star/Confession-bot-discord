"""Moderation Panel - Action buttons and modals for moderators."""
from datetime import datetime, timezone

import discord
from discord.ui import Modal, TextInput, View, Button

from bot.database.connection import get_session
from bot.database.repository import ServerRepository, RestrictionRepository
from bot.services.logging_service import send_event_log
from bot.utils.embeds import theme_color
from bot.utils.helpers import parse_duration
from bot.utils.permissions import can_moderate


class RestrictUserModal(Modal, title="Restrict User"):
    """Modal for restricting a user."""
    user_id = TextInput(
        label="User ID",
        placeholder="Enter the user's ID to restrict",
        style=discord.TextStyle.short,
        required=True,
    )
    duration = TextInput(
        label="Duration (optional)",
        placeholder="e.g. 10m, 2h, 3d, 1w — leave empty for permanent",
        style=discord.TextStyle.short,
        required=False,
    )
    reason = TextInput(
        label="Reason (optional)",
        placeholder="Why is this user being restricted?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        try:
            target_user_id = int(self.user_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please enter a valid numeric ID.", ephemeral=True)
            return

        expires_at = None
        if self.duration.value.strip():
            try:
                expires_at = datetime.utcnow() + parse_duration(self.duration.value.strip())
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

            await RestrictionRepository(session).create(
                interaction.guild.id, target_user_id, interaction.user.id, 
                self.reason.value.strip() or None, expires_at
            )
        finally:
            await session.close()

        target_user = interaction.guild.get_member(target_user_id)
        user_mention = target_user.mention if target_user else f"<@{target_user_id}>"
        duration_text = (
            f"until {discord.utils.format_dt(expires_at.replace(tzinfo=timezone.utc), style='f')}"
            if expires_at else "permanently"
        )

        fields = [("Reason", self.reason.value)] if self.reason.value else None
        await send_event_log(
            interaction.guild, server, "🔨 User Restricted",
            description=f"{user_mention} was restricted {duration_text} by {interaction.user.mention}.",
            fields=fields,
        )
        await interaction.response.send_message(f"✅ {user_mention} is restricted {duration_text}.", ephemeral=True)


class UnrestrictUserModal(Modal, title="Unrestrict User"):
    """Modal for unrestricting a user."""
    user_id = TextInput(
        label="User ID",
        placeholder="Enter the user's ID to unrestrict",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        try:
            target_user_id = int(self.user_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please enter a valid numeric ID.", ephemeral=True)
            return

        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message("❌ You do not have permission to unrestrict users.", ephemeral=True)
                return

            lifted = await RestrictionRepository(session).lift(
                interaction.guild.id, target_user_id, interaction.user.id
            )
        finally:
            await session.close()

        if not lifted:
            target_user = interaction.guild.get_member(target_user_id)
            user_mention = target_user.mention if target_user else f"<@{target_user_id}>"
            await interaction.response.send_message(
                f"ℹ️ {user_mention} doesn't have an active restriction.", ephemeral=True
            )
            return

        target_user = interaction.guild.get_member(target_user_id)
        user_mention = target_user.mention if target_user else f"<@{target_user_id}>"

        await send_event_log(
            interaction.guild, server, "🔓 Restriction Lifted",
            description=f"{user_mention}'s restriction was lifted by {interaction.user.mention}.",
        )
        await interaction.response.send_message(
            f"✅ {user_mention}'s restriction has been lifted.", ephemeral=True
        )


class DeleteConfessionModal(Modal, title="Delete Confession"):
    """Modal for deleting a confession."""
    confession_id = TextInput(
        label="Confession ID",
        placeholder="Enter the confession ID to delete",
        style=discord.TextStyle.short,
        required=True,
    )
    reason = TextInput(
        label="Reason",
        placeholder="Why is this confession being deleted?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        try:
            cid = int(self.confession_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid confession ID. Please enter a valid numeric ID.", ephemeral=True)
            return

        from bot.cogs.confession import delete_confession
        await delete_confession(interaction, cid, self.reason.value.strip())


class ModerationPanelView(View):
    """View for the Moderation Panel containing action buttons."""
    
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🔙 Back to Dashboard", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Return to the main Moderator Dashboard."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message(
                    "❌ You do not have permission to view the dashboard.", ephemeral=True
                )
                return
            
            from bot.cogs.moderation import build_dashboard_embed
            embed = await build_dashboard_embed(server, session)
        finally:
            await session.close()
        
        # Import DashboardView from moderation module
        from bot.cogs.moderation import DashboardView
        await interaction.response.edit_message(embed=embed, view=DashboardView())

    @discord.ui.button(label="🗑️ Delete Confession", style=discord.ButtonStyle.danger, row=1)
    async def delete_confession(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message(
                    "❌ You do not have permission to delete confessions.", ephemeral=True
                )
                return
        finally:
            await session.close()
        
        await interaction.response.send_modal(DeleteConfessionModal())

    @discord.ui.button(label="🔨 Restrict User", style=discord.ButtonStyle.danger, row=1)
    async def restrict_user(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message(
                    "❌ You do not have permission to restrict users.", ephemeral=True
                )
                return
        finally:
            await session.close()
        
        await interaction.response.send_modal(RestrictUserModal())

    @discord.ui.button(label="🔓 Unrestrict User", style=discord.ButtonStyle.success, row=1)
    async def unrestrict_user(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        session = get_session()
        try:
            servers = ServerRepository(session)
            server = await servers.get(interaction.guild.id)
            if server is None or not can_moderate(interaction.user, server.moderator_role_id):
                await interaction.response.send_message(
                    "❌ You do not have permission to unrestrict users.", ephemeral=True
                )
                return
        finally:
            await session.close()
        
        await interaction.response.send_modal(UnrestrictUserModal())
